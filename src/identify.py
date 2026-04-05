import os
import sys
from typing import List, Tuple, Dict, Optional
from collections import defaultdict

# Add current path to PYTHONPATH
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.database import Database
from src.audioprocessing import process_audio_pipeline
from src.fingerprinting import extract_peaks
from src.hashing import hashingAlgorithm

def identify_audio(filepath: str, db_path: str = "fingerprints.db") -> Optional[Dict]:
    """
    Given a snippet, identify it from the database.
    
    Algorithm:
    1. Generate fingerprints (hash, offset_snippet)
    2. Fetch all matching (song_id, offset_db) from DB
    3. Calculate diff = offset_db - offset_snippet
    4. Find the most common (song_id, diff)
    """
    db = Database(db_path)
    
    # 1. Process snippet
    try:
        frame_size = 1024
        spec, sr = process_audio_pipeline(filepath, frame_size=frame_size)
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return None
        
    # Must match the coefficient used during indexing (1.0) to produce the same hashes.
    peaks = extract_peaks(spec, coefficient=1.0)
    snippet_fingerprints = hashingAlgorithm(peaks, include_metadata=False)
    
    if not snippet_fingerprints:
        return None
        
    # Map snippet fingerprints for quick lookup
    # Convert to plain int so dict keys match the int type returned by SQLite
    hashes_to_offsets = defaultdict(list)
    for h, offset in snippet_fingerprints:
        hashes_to_offsets[int(h)].append(int(offset))

    # 2. Query DB
    all_query_hashes = list(hashes_to_offsets.keys())
    db_matches = db.fetch_matches(all_query_hashes)
    
    if not db_matches:
        return None
        
    # 3. Time Coherence Scoring
    # score_map: song_id -> { diff -> count }
    score_map = defaultdict(lambda: defaultdict(int))
    
    for song_id, db_offset, h in db_matches:
        # One hash can occur multiple times in the snippet (rare, but possible)
        for snippet_offset in hashes_to_offsets[h]:
            diff = db_offset - snippet_offset
            score_map[song_id][diff] += 1
            
    # 4. Find the best and second-best matches
    ranked = []
    for song_id, diffs in score_map.items():
        song_best_diff = max(diffs, key=diffs.get)
        song_best_score = diffs[song_best_diff]
        ranked.append((song_id, song_best_score, song_best_diff, sum(diffs.values())))

    ranked.sort(key=lambda x: x[1], reverse=True)

    if not ranked:
        return None

    best_song_id, best_score, best_offset, best_total = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0

    metadata = db.get_song_metadata(best_song_id)
    if not metadata:
        return None

    # Match density: fraction of query fingerprints that are time-coherent
    match_density = (best_score / len(snippet_fingerprints)) * 100

    # Dominance: how much the best match stands out vs the runner-up
    # A ratio > 2 is a strong identification
    dominance = best_score / second_score if second_score > 0 else float('inf')

    # Total hash hits across all songs for the query hashes
    total_db_hits = len(db_matches)

    time_per_frame = 512 / 11025

    return {
        "song_id": best_song_id,
        "name": metadata["name"],
        "path": metadata["path"],
        "duration": metadata["duration"],
        "score": best_score,
        "match_density": round(match_density, 2),
        "dominance": round(dominance, 2) if dominance != float('inf') else 999,
        "confidence": round(match_density, 2),
        "query_fingerprints": len(snippet_fingerprints),
        "query_peaks": len(peaks),
        "db_hits": total_db_hits,
        "songs_matched": len(ranked),
        "second_score": second_score,
        "offset_s": round(best_offset * time_per_frame, 2)
    }

if __name__ == "__main__":
    if len(sys.argv) > 1:
        result = identify_audio(sys.argv[1])
        if result:
            print(f"Match Found: {result['name']} (Score: {result['score']}, Confidence: {result['confidence']}%)")
        else:
            print("No match found.")
