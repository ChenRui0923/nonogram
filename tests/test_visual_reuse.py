from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np
import ocr_nonogram as ocr
from result_cache import ResultCache
from visual_puzzle_cache import VisualPuzzleCache

ROOT = Path(__file__).resolve().parents[1]


class VisualReuseTests(unittest.TestCase):
    def test_scaled_real_screenshots_and_persistent_reference(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ResultCache(Path(folder) / 'visual.db', max_entries=4)
            visual = VisualPuzzleCache(store)
            first = ocr.ocr_nonogram(str(ROOT / 'debug.png'), visual_cache=visual)
            visual = VisualPuzzleCache(ResultCache(store.path, max_entries=4))
            with patch.object(ocr, 'read_clue_area', side_effect=AssertionError('Matched puzzle ran clue OCR')):
                cached = ocr.ocr_nonogram(str(ROOT / 'debug2.png'), visual_cache=visual)
            self.assertTrue(cached['auto_puzzle_match'])
            fresh = ocr.ocr_nonogram(str(ROOT / 'debug2.png'))
            for key in ('row_clues', 'col_clues', 'current'):
                self.assertEqual(cached[key], fresh[key])
            self.assertNotEqual(cached['current'], first['current'])
            # The persistent reference must contain no player's filled board.
            record = visual.entries[0]
            board = record['pixels'][record['h'][0]:, record['v'][0]:]
            self.assertTrue(np.all(board == 255))

    def test_similarity_threshold_forces_full_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ResultCache(Path(folder) / 'visual.db', max_entries=4)
            visual = VisualPuzzleCache(store)
            ocr.ocr_nonogram(str(ROOT / 'debug.png'), visual_cache=visual)
            # Even a valid registration must not bypass the configured threshold.
            visual.minimum_similarity = 1.01
            latest = ocr.ocr_nonogram(str(ROOT / 'debug2.png'), visual_cache=visual)
            self.assertFalse(latest['auto_puzzle_match'])
            fresh = ocr.ocr_nonogram(str(ROOT / 'debug2.png'))
            self.assertEqual(latest['row_clues'], fresh['row_clues'])
            self.assertEqual(latest['col_clues'], fresh['col_clues'])

    def test_50x50_transform_regressions(self):
        from robustness_benchmark import transformed_images
        with tempfile.TemporaryDirectory() as folder:
            store = ResultCache(Path(folder) / 'visual.db', max_entries=4)
            visual = VisualPuzzleCache(store)
            ocr.ocr_nonogram(str(ROOT / 'debug.png'), visual_cache=visual)
            reference = visual.entries[0]
            expected = ocr.ocr_nonogram(str(ROOT / 'debug2.png'))
            source = cv2.imread(str(ROOT / 'debug2.png'))
            selected = {'scale-0.5', 'white-padding', 'rotation-2', 'perspective-20', 'jpeg-80'}
            for name, changed in transformed_images(source):
                if name not in selected:
                    continue
                with self.subTest(name=name):
                    cv2.setRNGSeed(42)
                    visual.entries = [reference]
                    path = str(Path(folder) / (name + '.png'))
                    cv2.imwrite(path, changed)
                    with patch.object(ocr, 'read_clue_area', side_effect=AssertionError('Matched transform ran clue OCR')):
                        latest = ocr.ocr_nonogram(path, visual_cache=visual)
                    self.assertTrue(latest['auto_puzzle_match'])
                    for key in ('row_clues', 'col_clues', 'current'):
                        self.assertEqual(latest[key], expected[key])

    def test_same_grid_different_puzzle_is_not_reused(self):
        with tempfile.TemporaryDirectory() as folder:
            visual = VisualPuzzleCache(ResultCache(Path(folder) / 'visual.db', max_entries=4))
            ocr.ocr_nonogram(str(ROOT / 'debug.png'), visual_cache=visual)
            image = cv2.imread(str(ROOT / 'debug.png'))
            v, h = ocr.detect_grid_lines(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY))
            vs, ve, hs, he = ocr.find_board_region(v, h)
            # Keep all board lines and fills, replace clue text in every row/column.
            for i in range(hs, he):
                image[h[i]+3:h[i+1]-3, 3:v[vs]-3] = 255
                cv2.putText(image, '1 2 3', (v[vs]-85, h[i+1]-7),
                            cv2.FONT_HERSHEY_SIMPLEX, .45, (0, 0, 0), 1)
            for i in range(vs, ve):
                image[3:h[hs]-3, v[i]+3:v[i+1]-3] = 255
                cv2.putText(image, '1', (v[i]+7, h[hs]-10),
                            cv2.FONT_HERSHEY_SIMPLEX, .45, (0, 0, 0), 1)
            aligned, record = visual.align(image)
            self.assertIsNone(record)
