import sqlite3
import os
from typing import List, Tuple, Optional

class Database:
    def __init__(self, db_path: str = "fingerprints.db"):
        self.db_path = db_path
        self._setup()

    def _setup(self):
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Songs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS songs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    path TEXT NOT NULL UNIQUE,
                    duration REAL
                )
            """)
            
            # Fingerprints table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fingerprints (
                    hash INTEGER NOT NULL,
                    song_id INTEGER NOT NULL,
                    offset INTEGER NOT NULL,
                    FOREIGN KEY (song_id) REFERENCES songs (id)
                )
            """)
            
            # Create indexing for fast hash lookups
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_hash ON fingerprints (hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_song_id ON fingerprints (song_id)")
            conn.commit()

    def add_song(self, name: str, path: str, duration: Optional[float] = None) -> int:
        """Add a song and return its ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO songs (name, path, duration) VALUES (?, ?, ?)",
                (name, path, duration)
            )
            if cursor.rowcount == 0:
                # Already exists, fetch ID
                cursor.execute("SELECT id FROM songs WHERE path = ?", (path,))
                return cursor.fetchone()[0]
            
            conn.commit()
            return cursor.lastrowid

    def add_fingerprints(self, song_id: int, fingerprints: List[Tuple[int, int]]):
        """Add multiple fingerprints for a song in one transaction."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Convert numpy ints to plain Python ints so SQLite stores them as INTEGER, not BLOB
            params = [(int(f[0]), song_id, int(f[1])) for f in fingerprints]
            cursor.executemany(
                "INSERT INTO fingerprints (hash, song_id, offset) VALUES (?, ?, ?)",
                params
            )
            conn.commit()

    def get_song_count(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM songs")
            return cursor.fetchone()[0]

    def get_fingerprint_count(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM fingerprints")
            return cursor.fetchone()[0]

    def fetch_matches(self, hashes: List[int]) -> List[Tuple[int, int, int]]:
        """
        Identify all (song_id, hash, offset) triples for a given list of query hashes.
        Returns pairs of (song_id, db_offset).
        """
        if not hashes:
            return []
            
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Using placeholders for a large number of hashes can be problematic in SQLite.
            # We will use a temporary table for massive lists of hashes if needed,
            # but for typical query sizes (a few thousand), standard IN is fine.
            # Max limit is usually 999 or 32766 depending on compilation.
            
            # Use chunks if large, otherwise simple IN query.
            chunk_size = 900
            all_matches = []
            
            for i in range(0, len(hashes), chunk_size):
                chunk = hashes[i : i + chunk_size]
                placeholders = ",".join(["?"] * len(chunk))
                query = f"SELECT song_id, offset, hash FROM fingerprints WHERE hash IN ({placeholders})"
                cursor.execute(query, chunk)
                all_matches.extend(cursor.fetchall())
                
            return all_matches

    def get_song_metadata(self, song_id: int) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name, path, duration FROM songs WHERE id = ?", (song_id,))
            row = cursor.fetchone()
            if row:
                return {"name": row[0], "path": row[1], "duration": row[2]}
            return None

    def get_all_songs_with_stats(self) -> List[dict]:
        """Fetch all songs along with their fingerprint count."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            query = """
                SELECT s.id, s.name, s.path, s.duration, COUNT(f.song_id) as fingerprint_count
                FROM songs s
                LEFT JOIN fingerprints f ON s.id = f.song_id
                GROUP BY s.id
                ORDER BY s.name ASC
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "name": row[1],
                    "path": row[2],
                    "duration": row[3],
                    "fingerprints": row[4]
                } for row in rows
            ]

    def is_song_indexed(self, path: str) -> bool:
        """Check if a song path is already in the database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM songs WHERE path = ?", (path,))
            return cursor.fetchone() is not None

    def get_db_size_mb(self) -> float:
        """Return the physical database size in MB."""
        if os.path.exists(self.db_path):
            size_bytes = os.path.getsize(self.db_path)
            return round(size_bytes / (1024 * 1024), 2)
        return 0.0
