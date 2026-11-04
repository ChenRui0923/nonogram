import sqlite3
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import unittest

from result_cache import ResultCache


class ResultCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'results.sqlite3'

    def test_persistence_changed_image_and_version(self):
        calls = []
        def compute():
            calls.append(1)
            return {'solution': ['OX']}
        self.assertFalse(ResultCache(self.path).get_or_compute(b'a', compute)[1])
        self.assertTrue(ResultCache(self.path).get_or_compute(b'a', compute)[1])
        self.assertFalse(ResultCache(self.path).get_or_compute(b'b', compute)[1])
        self.assertFalse(ResultCache(self.path, version='new').get_or_compute(b'a', compute)[1])
        self.assertEqual(len(calls), 3)

    def test_concurrent_duplicate_and_eviction(self):
        cache = ResultCache(self.path, max_entries=2)
        calls = []
        def compute():
            calls.append(1)
            return {'solution': ['O']}
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: cache.get_or_compute(b'a', compute), range(4)))
        self.assertEqual(len(calls), 1)
        self.assertEqual(sum(hit for _, hit in results), 3)
        cache.get_or_compute(b'b', compute)
        cache.get_or_compute(b'c', compute)
        self.assertFalse(cache.get_or_compute(b'a', compute)[1])
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM results').fetchone()[0], 2)

    def test_errors_not_cached_and_unwritable_cache_is_optional(self):
        cache = ResultCache(self.path)
        def fail():
            raise RuntimeError('OCR failed')
        with self.assertRaises(RuntimeError):
            cache.get_or_compute(b'a', fail)
        self.assertFalse(cache.get_or_compute(b'a', lambda: {'solvable': True})[1])
        self.path.unlink()
        self.path.mkdir()
        self.assertEqual(ResultCache(self.path).get_or_compute(b'b', lambda: {'ok': True}), ({'ok': True}, False))
