# Build with: pyinstaller --clean nonogram_macos.spec
from PyInstaller.utils.hooks import collect_submodules

a = Analysis(
    ["desktop_launcher.py"], pathex=["."],
    binaries=[], datas=[("web_index.html", "."), ("assets/fonts", "assets/fonts")],
    hiddenimports=["cv2", "numpy", "PIL", "pytesseract", "webview", "AppKit"] + collect_submodules("cv2"),
    hookspath=[], hooksconfig={}, runtime_hooks=["packaging/runtime_diagnostics.py"], excludes=[], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], [], [], name="nonogram助手",
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, exclude_binaries=True)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="nonogram助手")
app = BUNDLE(coll, name="nonogram助手.app", icon="assets/icons/nonogram.icns",
             bundle_identifier="com.chenrui0923.nonogram",
             info_plist={"CFBundleName": "nonogram助手", "CFBundleDisplayName": "nonogram助手"})
