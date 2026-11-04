"""Exercise the CI smoke path under windowless-process conditions."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class DesktopSmokeTests(unittest.TestCase):
    def test_windowless_startup_without_native_gui(self):
        root = Path(__file__).resolve().parents[1]
        script = '''
import builtins, runpy, sys
original_import = builtins.__import__
def no_gui(name, *args, **kwargs):
    if name.split('.')[0] in ('webview', 'tkinter'):
        raise RuntimeError('Smoke check must not initialize native GUI')
    return original_import(name, *args, **kwargs)
builtins.__import__ = no_gui
sys.stdout = sys.stderr = None
sys.argv = ['desktop_launcher.py', '--smoke-test', '--port', '0']
runpy.run_path('packaging/runtime_diagnostics.py')
runpy.run_path('desktop_launcher.py', run_name='__main__')
'''
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / 'startup.log'
            env = dict(os.environ, NONOGRAM_STARTUP_LOG=str(log))
            completed = subprocess.run([sys.executable, '-B', '-c', script],
                                       cwd=root, env=env, timeout=30,
                                       capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr + (log.read_text() if log.exists() else ''))
            self.assertIn('Smoke test passed', log.read_text())
