"""Ensure packaged app icons do not reintroduce an opaque square background."""
from pathlib import Path
import unittest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


class IconTransparencyTests(unittest.TestCase):
    def check_corners(self, image):
        alpha = image.convert('RGBA').getchannel('A')
        width, height = image.size
        for x, y in ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)):
            self.assertEqual(alpha.getpixel((x, y)), 0)
        self.assertGreater(alpha.getpixel((width // 2, height // 2)), 240)

    def test_png_and_windows_sizes(self):
        with Image.open(ROOT / 'assets/icons/nonogram.png') as image:
            self.check_corners(image)
            self.assertEqual(image.getchannel('A').crop((0, 0, 1024, 80)).getextrema(), (0, 0))
        with Image.open(ROOT / 'assets/icons/nonogram.ico') as image:
            for size in image.ico.sizes():
                self.check_corners(image.ico.getimage(size))

    def test_macos_sizes(self):
        with Image.open(ROOT / 'assets/icons/nonogram.icns') as image:
            for size in image.info['sizes']:
                self.check_corners(image.icns.getimage(size))
