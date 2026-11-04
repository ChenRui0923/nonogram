from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import cv2

from nonogram import ocr_nonogram as ocr
from nonogram.result_cache import ResultCache
from nonogram.web_app import solve_data
from nonogram.solver import Solver

ROOT = Path(__file__).resolve().parents[1]


class PuzzleReuseTests(unittest.TestCase):
    def test_changed_board_reuses_clues_and_unique_solution(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = ResultCache(Path(folder) / 'clues.db')
            solution_cache = ResultCache(Path(folder) / 'solutions.db')
            original = ocr.ocr_nonogram(str(ROOT / 'examples/images/debug.png'), clue_cache=cache)
            result = solve_data(original, solution_cache=solution_cache)
            image = cv2.imread(str(ROOT / 'examples/images/debug.png'))
            v, h = ocr.detect_grid_lines(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY))
            vs, ve, hs, he = ocr.find_board_region(v, h)
            r, c = 20, 20
            self.assertEqual(original['current'][r][c], '.')
            cv2.rectangle(image, (v[vs+c]+4, h[hs+r]+4),
                          (v[vs+c+1]-4, h[hs+r+1]-4), (0, 0, 0), -1)
            changed = str(Path(folder) / 'changed.png')
            cv2.imwrite(changed, image)
            with patch.object(ocr, 'read_clue_area', side_effect=AssertionError('Clues re-read')):
                data = ocr.ocr_nonogram(changed, clue_cache=ResultCache(cache.path))
            self.assertEqual(data['clue_cache_hits'], 100)
            self.assertEqual(data['current'][r][c], 'O')
            with patch.object(Solver, 'solve', side_effect=AssertionError('Unique solution re-solved')):
                latest = solve_data(data, solution_cache=ResultCache(solution_cache.path))
            self.assertTrue(latest['solution_cache_hit'])
            self.assertEqual(latest['solution'], result['solution'])
            fresh = solve_data(ocr.ocr_nonogram(changed))
            latest.pop('solution_cache_hit')
            self.assertEqual(latest, fresh)

    def test_real_different_progress_and_changed_clue_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = ResultCache(Path(folder) / 'headers.db')
            strips = ResultCache(Path(folder) / 'strips.db', max_entries=512)
            ocr.ocr_nonogram(str(ROOT / 'examples/images/progress-30x25.png'), clue_cache=cache, strip_cache=strips)
            changed = ocr.ocr_nonogram(str(ROOT / 'examples/images/progress-30x25-later.png'), clue_cache=cache, strip_cache=strips)
            self.assertGreater(changed['clue_cache_hits'], 0)
            self.assertLess(changed['clue_cache_hits'], 55)
            fresh = ocr.ocr_nonogram(str(ROOT / 'examples/images/progress-30x25-later.png'))
            for key in ('row_clues', 'col_clues', 'current'):
                self.assertEqual(changed[key], fresh[key])
            image = cv2.imread(str(ROOT / 'examples/images/progress-30x25-later.png'))
            v, h = ocr.detect_grid_lines(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY))
            vs, ve, hs, he = ocr.find_board_region(v, h)
            image[h[hs]+3:h[hs+1]-3, :v[vs]-3] = 255  # Remove just one clue.
            path = str(Path(folder) / 'new-clue.png')
            cv2.imwrite(path, image)
            changed = ocr.ocr_nonogram(path, clue_cache=cache, strip_cache=strips)
            self.assertEqual(changed['row_clues'][0], [])
            self.assertNotEqual(changed['row_clues'][0], fresh['row_clues'][0])

    def test_multiple_solutions_use_latest_marks(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = ResultCache(Path(folder) / 'solutions.db')
            a = solve_data({'row_clues': [[1], [1]], 'col_clues': [[1], [1]],
                            'current': ['O.', '..']}, solution_cache=cache)
            b = solve_data({'row_clues': [[1], [1]], 'col_clues': [[1], [1]],
                            'current': ['.O', '..']}, solution_cache=cache)
            self.assertNotEqual(a['solution'], b['solution'])
            self.assertEqual(b['errors'], [])
            self.assertFalse(b['solution_cache_hit'])
