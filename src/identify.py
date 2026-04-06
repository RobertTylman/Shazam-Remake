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

def _load_dotenv() -> None:
    """Load key=value pairs from project-root .env into os.environ (non-destructive)."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env_path = os.path.join(root_dir, ".env")
    if not os.path.exists(env_path):
        return

    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[len("export "):].strip()
                if "=" not in line:
                    continue

                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                if not key:
                    continue

                # Strip simple surrounding quotes.
                if len(value) >= 2 and ((value[0] == value[-1]) and value[0] in ("'", '"')):
                    value = value[1:-1]

                # Do not overwrite already-exported process env vars.
                os.environ.setdefault(key, value)
    except OSError:
        # If .env cannot be read, continue with defaults/process env.
        return

_load_dotenv()

def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default

def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default

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

    #get fingerprints from snippet audio
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
    score_gap = best_score - second_score

    # Coherence concentration inside the winning song:
    # how much the best single offset bucket dominates that song's total hash hits.
    coherence_ratio = (best_score / best_total) if best_total > 0 else 0.0

    # Total hash hits across all songs for the query hashes
    total_db_hits = len(db_matches)

    # Conservative defaults to reduce false positives ("always returns something").
    # Override with env vars for tuning without code changes:
    # - ID_MIN_QUERY_FPS
    # - ID_MIN_SCORE
    # - ID_MIN_MATCH_DENSITY
    # - ID_MIN_DOMINANCE
    # - ID_MIN_COHERENCE_RATIO
    # - ID_MIN_SCORE_GAP
    min_query_fps = _env_int("ID_MIN_QUERY_FPS", 25)
    min_score = _env_int("ID_MIN_SCORE", 12)
    min_match_density = _env_float("ID_MIN_MATCH_DENSITY", 8.0)
    min_dominance = _env_float("ID_MIN_DOMINANCE", 1.8)
    min_coherence_ratio = _env_float("ID_MIN_COHERENCE_RATIO", 0.18)
    min_score_gap = _env_int("ID_MIN_SCORE_GAP", 4)

    # Reject weak/ambiguous matches.
    if len(snippet_fingerprints) < min_query_fps:
        return None
    if best_score < min_score:
        return None
    if match_density < min_match_density:
        return None
    if dominance != float('inf') and dominance < min_dominance:
        return None
    if coherence_ratio < min_coherence_ratio:
        return None
    if second_score > 0 and score_gap < min_score_gap:
        return None

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
        "coherence_ratio": round(coherence_ratio, 4),
        "offset_s": round(best_offset * time_per_frame, 2)
    }

if __name__ == "__main__":
    if len(sys.argv) > 1:
        result = identify_audio(sys.argv[1])
        if result:
            print(f"Match Found: {result['name']} (Score: {result['score']}, Confidence: {result['confidence']}%)")
        else:
            print("No match found.")
