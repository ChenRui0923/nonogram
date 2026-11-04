"""PyInstaller runtime hook: preserve diagnostics for windowless smoke checks."""
import faulthandler
import os
import sys
import tempfile

if '--smoke-test' in sys.argv:
    path = os.environ.get('NONOGRAM_STARTUP_LOG') or os.path.join(tempfile.gettempdir(), 'nonogram-smoke.log')
    stream = open(path, 'a', encoding='utf-8', buffering=1)
    sys.stdout = stream
    sys.stderr = stream
    faulthandler.enable(file=stream)
    faulthandler.dump_traceback_later(90, file=stream)
    print('Runtime initialized; loading application', flush=True)
