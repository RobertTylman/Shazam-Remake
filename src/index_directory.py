import os
import sys
import time

# Add current path to PYTHONPATH
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.database import Database
from src.audioprocessing import process_audio_pipeline, load_audio
from src.fingerprinting import extract_peaks
from src.hashing import hashingAlgorithm

def index_folder(target_dir: str, db_path: str = "fingerprints.db"):
    db = Database(db_path)
    
    # Supported extensions
    supported_exts = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aiff"}
    
    files_to_process = []
    for root, _, files in os.walk(target_dir):
        for f in files:
            if os.path.splitext(f)[1].lower() in supported_exts:
                full_path = os.path.join(root, f)
                if not db.is_song_indexed(full_path):
                    files_to_process.append(full_path)
    
    total = len(files_to_process)
    print(f"Found {total} new files to index in {target_dir}.")
    
    start_time = time.time()
    
    for idx, filepath in enumerate(files_to_process):
        try:
            song_name = os.path.basename(filepath)
            print(f"[{idx+1}/{total}] Processing: {song_name}...")
            
            # 1. Processing pipeline (Spec & SR)
            frame_size = 1024
            spec, sr = process_audio_pipeline(filepath, frame_size=frame_size)
            
            # 2. Extract constellation peaks
            peaks = extract_peaks(spec, coefficient=1.0)
            
            # 3. Generate hashes
            fingerprints = hashingAlgorithm(
                peaks,
                target_zone_time=50,
                target_zone_freq=80,
                max_targets_per_anchor=5,
                include_metadata=False
            )
            
            # 4. Get song duration
            # Load audio (lightly) for metadata
            actual_sr, audio_data = load_audio(filepath)
            duration = len(audio_data) / actual_sr
            
            # 5. Insert into DB
            song_id = db.add_song(song_name, filepath, duration)
            db.add_fingerprints(song_id, fingerprints)
            
            print(f"   Done. Generated {len(fingerprints)} hashes.")
            
        except Exception as e:
            print(f"   ERROR processing {filepath}: {str(e)}")
            continue
            
    end_time = time.time()
    elapsed = end_time - start_time
    
    print("\n" + "="*40)
    print("Indexing Complete!")
    print(f"Processed {total} files in {elapsed:.2f} seconds.")
    print(f"Total songs in DB: {db.get_song_count()}")
    print(f"Total fingerprints in DB: {db.get_fingerprint_count()}")
    print("="*40)

if __name__ == "__main__":
    target = "/Users/robbietylman/Desktop/DJ SET"
    index_folder(target)
