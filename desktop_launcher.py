"""Desktop entry point used by the Windows and macOS bundles."""

import argparse
import platform
import subprocess
import threading
import time
import webbrowser
import urllib.request
import base64
import io


class ClipboardApi:
    def get_clipboard_image(self):
        """Return the system clipboard image as a data URL for the web UI."""
        try:
            if platform.system() == "Windows":
                from PIL import ImageGrab
                image = ImageGrab.grabclipboard()
                if image is None:
                    return {"error": "剪贴板中没有图片"}
                buf = io.BytesIO()
                image.save(buf, format="PNG")
                return {"data_url": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()}
            from AppKit import NSPasteboard, NSPasteboardTypePNG, NSPasteboardTypeTIFF
            pasteboard = NSPasteboard.generalPasteboard()
            for paste_type, mime in ((NSPasteboardTypePNG, "image/png"),
                                     (NSPasteboardTypeTIFF, "image/tiff")):
                data = pasteboard.dataForType_(paste_type)
                if data:
                    raw = bytes(data)
                    return {"data_url": f"data:{mime};base64,{base64.b64encode(raw).decode()}"}
        except Exception as exc:
            return {"error": str(exc)}
        return {"error": "剪贴板中没有图片"}

from web_app import HOST, PORT, ThreadingHTTPServer, Handler


def main():
    parser = argparse.ArgumentParser(description="Nonogram OCR")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", default=PORT, type=int)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--smoke-test", action="store_true", help="Check bundled resources and HTTP startup without opening a window")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{server.server_address[1]}"
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def open_browser():
        if platform.system() == "Darwin":
            subprocess.Popen(["open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            webbrowser.open(url)

    if args.smoke_test:
        print("HTTP server started; checking bundled HTML", flush=True)
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(url, timeout=10) as response:
                assert b"Nonogram OCR" in response.read(), "Missing bundled HTML"
            print("Checking OCR font templates", flush=True)
            from ocr_nonogram import _glyph_templates
            assert any(key[0] == "DejaVuSans-Bold.ttf" for key in _glyph_templates()), "Missing bundled font"
            print("Checking solver", flush=True)
            from solver import Solver
            assert Solver([[1]], [[1]]).solve() == [["O"]], "Solver failed"
        finally:
            server.shutdown()
            server.server_close()
        print("Smoke test passed", flush=True)
        return

    # The smoke check does not need native GUI/CLR initialization.
    try:
        import webview
    except ImportError:
        webview = None
    try:
        import tkinter as tk
        from tkinter import messagebox
    except ImportError:
        tk = None
        messagebox = None

    if webview is not None:
        webview.create_window("Nonogram OCR", url, width=1200, height=850,
                              min_size=(900, 650), confirm_close=True,
                              js_api=ClipboardApi())
        webview.start()
        server.shutdown()
        server.server_close()
        return

    # Some Python distributions (including python.org/Homebrew minimal builds)
    # do not ship Tk. The web app remains fully usable in that case.
    if tk is None:
        print(f"Nonogram 服务已启动: {url}")
        if not args.no_browser:
            threading.Timer(0.5, open_browser).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return

    root = tk.Tk()
    root.title("Nonogram OCR")
    root.geometry("430x220")
    root.resizable(False, False)
    tk.Label(root, text="Nonogram OCR", font=("Arial", 20, "bold")).pack(pady=(22, 8))
    tk.Label(root, text="本地服务正在运行", fg="#16803c", font=("Arial", 12)).pack()
    address = tk.Label(root, text=url, fg="#555", cursor="hand2")
    address.pack(pady=5)
    buttons = tk.Frame(root)
    buttons.pack(pady=12)
    tk.Button(buttons, text="打开网页", width=12, command=open_browser).pack(side="left", padx=5)
    tk.Button(buttons, text="复制地址", width=12,
              command=lambda: (root.clipboard_clear(), root.clipboard_append(url))).pack(side="left", padx=5)

    def close():
        if messagebox.askyesno("退出 Nonogram", "确定要停止本地服务并退出吗？"):
            server.shutdown()
            root.destroy()

    tk.Button(root, text="退出服务", width=14, command=close).pack(pady=2)
    root.protocol("WM_DELETE_WINDOW", close)
    if not args.no_browser:
        root.after(700, open_browser)
    root.mainloop()
    server.server_close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import sys
        import traceback
        traceback.print_exc()
        if "--smoke-test" in sys.argv:
            # Avoid a frozen windowless error dialog blocking CI indefinitely.
            raise SystemExit(1)
        raise
