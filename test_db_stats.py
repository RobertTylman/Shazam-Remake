import sys
import os
sys.path.append(os.path.dirname(__file__))
from src.database import Database

try:
    db = Database("fingerprints.db")
    print(f"Song count: {db.get_song_count()}")
    print("Fetching library stats...")
    songs = db.get_all_songs_with_stats()
    print(f"Success! Found {len(songs)} songs.")
    for s in songs[:3]:
        print(f" - {s['name']}: {s['fingerprints']} hashes")
    
    print(f"DB size: {db.get_db_size_mb()} MB")
except Exception as e:
    print(f"FAILED: {e}")
    import traceback
    traceback.print_exc()
