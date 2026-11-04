"""Convert the approved icon artwork into desktop packaging formats.

Run with: python packaging/build_icons.py
Requires Pillow (already included in requirements-build.txt).
"""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs/icon-concepts/nonogram-c-corrected.png'
OUTPUT = ROOT / 'assets/icons'


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with Image.open(SOURCE) as artwork:
        icon = artwork.convert('RGBA').resize((1024, 1024), Image.Resampling.LANCZOS)
    icon.save(OUTPUT / 'nonogram.png')
    icon.save(OUTPUT / 'nonogram.ico', sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    icon.save(OUTPUT / 'nonogram.icns')
    print('Created PNG, Windows ICO and macOS ICNS in assets/icons')


if __name__ == '__main__':
    main()
