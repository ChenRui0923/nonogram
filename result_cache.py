"""Bounded, versioned local cache of results; uploaded images are not retained."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import threading
import time

# Bump when recognition, solver semantics, or the cached response schema changes.
CACHE_VERSION = 'v0.1.6'


def default_cache_path():
    if sys.platform == 'darwin':
        root = Path.home() / 'Library' / 'Caches'
    elif sys.platform == 'win32':
        root = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local')
    else:
        root = Path(os.environ.get('XDG_CACHE_HOME') or Path.home() / '.cache')
    return root / 'nonogram-helper' / 'results.sqlite3'


class ResultCache:
    def __init__(self, path=None, max_entries=32, version=CACHE_VERSION):
        self.path = Path(path) if path is not None else default_cache_path()
        self.max_entries = max_entries
        self.version = version
        self.lock = threading.Lock()

    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=2)
        conn.execute('CREATE TABLE IF NOT EXISTS results (key TEXT PRIMARY KEY, value TEXT NOT NULL, accessed INTEGER NOT NULL)')
        return conn

    def get_or_compute(self, image, compute):
        key = hashlib.sha256(self.version.encode() + b'\0' + image).hexdigest()
        # Prevent simultaneous duplicate uploads from repeating OCR and solving.
        with self.lock:
            conn = None
            try:
                conn = self._connect()
                row = conn.execute('SELECT value FROM results WHERE key=?', (key,)).fetchone()
                if row:
                    value = json.loads(row[0])
                    conn.execute('UPDATE results SET accessed=? WHERE key=?', (time.time_ns(), key))
                    conn.commit()
                    return value, True
            except (OSError, sqlite3.Error, ValueError):
                # Cache availability never blocks recognition.
                pass
            finally:
                if conn is not None:
                    conn.close()

            value = compute()  # Exceptions propagate and are never cached.
            conn = None
            try:
                encoded = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
                if len(encoded.encode('utf-8')) <= 2 * 1024 * 1024:
                    conn = self._connect()
                    conn.execute('INSERT OR REPLACE INTO results VALUES (?, ?, ?)', (key, encoded, time.time_ns()))
                    conn.execute('DELETE FROM results WHERE key NOT IN (SELECT key FROM results ORDER BY accessed DESC LIMIT ?)', (self.max_entries,))
                    conn.commit()
            except (OSError, sqlite3.Error):
                pass
            finally:
                if conn is not None:
                    conn.close()
            return value, False
