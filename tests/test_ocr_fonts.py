"""Verify template generation with the paths used by frozen Windows bundles."""
from pathlib import Path, PureWindowsPath
import unittest
from unittest.mock import patch

from PIL import ImageFont
import ocr_nonogram as ocr


class FontTemplateTests(unittest.TestCase):
    def test_windows_bundle_font_path(self):
        bundled_font = Path(__file__).resolve().parents[1] / 'assets/fonts/DejaVuSans-Bold.ttf'
        windows_path = str(PureWindowsPath('C:/Users/runner/AppData/Local/Temp/_MEI12345/assets/fonts/DejaVuSans-Bold.ttf'))
        original_loader = ImageFont.truetype

        def load_font(path, *args, **kwargs):
            self.assertEqual(path, windows_path)
            return original_loader(str(bundled_font), *args, **kwargs)

        # Render real glyphs, simulating only the Windows filesystem path.
        with patch.object(ocr, '_FONT_CANDIDATES', [windows_path]), \
             patch.object(ocr, '_GLYPH_TEMPLATES', None), \
             patch.object(ocr.os.path, 'exists', return_value=True), \
             patch.object(ImageFont, 'truetype', side_effect=load_font):
            templates = ocr._glyph_templates()
        self.assertEqual(set(templates), {('DejaVuSans-Bold.ttf', d) for d in range(10)})
