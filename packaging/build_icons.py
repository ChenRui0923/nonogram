"""Convert the approved icon artwork into desktop packaging formats.

Run with: python packaging/build_icons.py
Requires Pillow (already included in requirements/build.txt).
"""
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'assets/icons/source.png'
OUTPUT = ROOT / 'assets/icons'


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with Image.open(SOURCE) as artwork:
        icon = artwork.convert('RGBA').resize((1024, 1024), Image.Resampling.LANCZOS)
    # Apply a precise, antialiased platform silhouette during icon export.
    # The approved artwork has a white rounded tile inset from the canvas;
    # the export mask removes any remaining cutout fringe outside that tile.
    mask = Image.new('L', (4096, 4096), 0)
    ImageDraw.Draw(mask).rounded_rectangle((368, 368, 3728, 3728), radius=800, fill=255)
    mask = mask.resize((1024, 1024), Image.Resampling.LANCZOS)
    icon.putalpha(ImageChops.multiply(icon.getchannel('A'), mask))
    icon.save(OUTPUT / 'nonogram.png')
    icon.save(OUTPUT / 'nonogram.ico', sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    icon.save(OUTPUT / 'nonogram.icns')
    print('Created PNG, Windows ICO and macOS ICNS in assets/icons')


if __name__ == '__main__':
    main()
