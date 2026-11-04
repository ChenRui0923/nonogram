"""Resolve shared resources in a source checkout and PyInstaller bundles."""
from pathlib import Path
import sys


def resource_path(relative):
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
    return root / relative
