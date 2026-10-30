# Build with: pyinstaller --clean nonogram.spec
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = [("web_index.html", ".")]
hiddenimports = ["cv2", "numpy", "PIL", "pytesseract", "webview"]
hiddenimports += collect_submodules("cv2")

a = Analysis(
    ["desktop_launcher.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Nonogram",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # Double-click friendly: the app opens the browser and does not show a
    # terminal window. Use ``--console`` during development if needed.
    console=False,
)
