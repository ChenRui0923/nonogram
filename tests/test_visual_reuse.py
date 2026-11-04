from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import ocr_nonogram as ocr
from result_cache import ResultCache
from visual_puzzle_cache import VisualPuzzleCache

ROOT = Path(__file__).resolve().parents[1]


class VisualReuseTests(unittest.TestCase):
    def test_confusable_digits_do_not_match(self):
        font = ImageFont.truetype(str(ROOT / 'assets/fonts/DejaVuSans-Bold.ttf'), 24)
        strips = []
        for digit in range(10):
            im = Image.new('RGB', (80, 40), 'white')
            ImageDraw.Draw(im).text((25, 5), str(digit), font=font, fill='black')
            strips.append(np.array(im))
        for a in range(10):
            self.assertTrue(VisualPuzzleCache._same_strip(strips[a], strips[a], [a]))
            for b in range(10):
                if a != b:
                    self.assertFalse(VisualPuzzleCache._same_strip(strips[a], strips[b], [a]), (a, b))

    def test_scaled_real_screenshots_and_persistent_reference(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ResultCache(Path(folder) / 'visual.db', max_entries=4)
            visual = VisualPuzzleCache(store)
            first = ocr.ocr_nonogram(str(ROOT / 'debug.png'), visual_cache=visual)
            visual = VisualPuzzleCache(ResultCache(store.path, max_entries=4))
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

    def test_changed_clue_after_alignment_is_reidentified(self):
        with tempfile.TemporaryDirectory() as folder:
            visual = VisualPuzzleCache(ResultCache(Path(folder) / 'visual.db', max_entries=4))
            first = ocr.ocr_nonogram(str(ROOT / 'debug.png'), visual_cache=visual)
            image = cv2.imread(str(ROOT / 'debug.png'))
            v, h = ocr.detect_grid_lines(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY))
            vs, ve, hs, he = ocr.find_board_region(v, h)
            # Remove only ONE digit, so global similarity still exceeds 99.5%.
            top = h[hs] + 3
            strip = image[top:h[hs+1]-3, 3:v[vs]-3]
            n, labels, stats, _ = cv2.connectedComponentsWithStats(ocr._ink_mask(strip))
            glyphs = [s for s in stats[1:] if s[4] >= 6 and 5 <= s[3] < strip.shape[0] * .95 and 2 <= s[2] < strip.shape[1] * .5]
            x, y, w, height, _ = min(glyphs, key=lambda s: s[0])
            image[top+y:top+y+height, 3+x:3+x+w] = 255
            path = str(Path(folder) / 'different.png')
            cv2.imwrite(path, image)
            latest = ocr.ocr_nonogram(path, visual_cache=visual)
            self.assertTrue(latest['auto_puzzle_match'])
            self.assertGreaterEqual(latest['puzzle_similarity'], .995)
            self.assertNotEqual(latest['row_clues'][0], first['row_clues'][0])
            # Changed digit must not be masked by the high global score.
            fresh = ocr.ocr_nonogram(path)
            for key in ('row_clues', 'col_clues', 'current'):
                self.assertEqual(latest[key], fresh[key])
