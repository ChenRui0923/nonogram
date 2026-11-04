import unittest
import cv2
import numpy as np
from nonogram.ocr_nonogram import _glyph_score, _GLYPH_SHIFTS


class GlyphScoreTests(unittest.TestCase):
    def test_vectorized_scores_match_shifted_maps(self):
        rng = np.random.default_rng(42)
        for shape in [(7, 9), (32, 40)]:
            for _ in range(50):
                a, b = [(rng.random(shape) > 0.7).astype(np.uint8) for _ in range(2)]
                da, db = [cv2.distanceTransform(1 - m, cv2.DIST_L2, 3) for m in (a, b)]
                ya, xa = np.nonzero(a)
                yb, xb = np.nonzero(b)
                expected = min((float(np.roll(np.roll(db, -dy, 0), -dx, 1)[ya, xa].mean()) +
                                float(np.roll(np.roll(da, dy, 0), dx, 1)[yb, xb].mean())) / 2
                               for dy, dx in _GLYPH_SHIFTS)
                self.assertEqual(_glyph_score(a, da, b, db), expected)
