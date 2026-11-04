import argparse
import json
import os
import sys
import tempfile
import time

from nonogram.result_cache import ResultCache, CACHE_VERSION
from nonogram.visual_puzzle_cache import VisualPuzzleCache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from nonogram.hint import (
    find_errors,
    validate_current_board,
    get_line_reasoning,
    next_hint,
    progress,
)
from nonogram.ocr_nonogram import ocr_nonogram, validate_and_fix
from nonogram.solver import Solver, UNKNOWN


HOST = "127.0.0.1"
PORT = 8765
RESULT_CACHE = ResultCache()
CLUE_CACHE = ResultCache(path=RESULT_CACHE.path.with_name("clues.sqlite3"),
                         version=CACHE_VERSION + ":clues")
CLUE_STRIP_CACHE = ResultCache(path=CLUE_CACHE.path.with_name("clue-strips.sqlite3"),
                              max_entries=512, version=CACHE_VERSION + ":strips")
SOLUTION_CACHE = ResultCache(path=RESULT_CACHE.path.with_name("solutions.sqlite3"),
                             version=CACHE_VERSION + ":solutions")
VISUAL_CACHE = VisualPuzzleCache(ResultCache(path=RESULT_CACHE.path.with_name("visual-puzzles.sqlite3"),
                                           max_entries=4, version=CACHE_VERSION + ":visual"))

# In a PyInstaller bundle resources are unpacked under ``sys._MEIPASS``.
# Keep source-tree execution working while allowing nonogram/web/index.html to be
# included as a bundled data file.
from nonogram.resources import resource_path
ROOT = str(resource_path("nonogram/web"))


def collect_hints(current, solution, rows, cols):
    """Collect all currently explainable cells, ordered by usefulness."""
    if not current or not solution:
        return []

    nrows = len(rows)
    ncols = len(cols)

    # Pre-compute line reasoning once per row and per column (not per cell).
    row_reasons = []
    for r in range(nrows):
        row_reasons.append(get_line_reasoning(rows[r], current[r], r, 0))
    col_lines = ["".join(current[rr][c] for rr in range(nrows)) for c in range(ncols)]
    col_reasons = []
    for c in range(ncols):
        col_reasons.append(get_line_reasoning(cols[c], col_lines[c], c, 1))

    # Pre-compute per-column done counts once.
    col_done_by_c = [
        sum(current[rr][c] != UNKNOWN for rr in range(nrows))
        for c in range(ncols)
    ]

    candidates = []
    for r in range(nrows):
        row_done = sum(ch != UNKNOWN for ch in current[r])
        row_pos, row_value, row_reason = row_reasons[r]
        for c in range(ncols):
            if current[r][c] != UNKNOWN or solution[r][c] == UNKNOWN:
                continue

            col_pos, col_value, col_reason = col_reasons[c]

            if row_pos == c:
                reason = f"第{r + 1}行: {row_reason}"
                line_type = "row"
            elif col_pos == r:
                reason = f"第{c + 1}列: {col_reason}"
                line_type = "col"
            else:
                continue

            candidates.append(
                (
                    -((row_done / ncols) + (col_done_by_c[c] / nrows)),
                    r,
                    c,
                    {
                        "row": r + 1,
                        "col": c + 1,
                        "value": solution[r][c],
                        "value_cn": "黑格(O)"
                        if solution[r][c] == "O"
                        else "空格(X)",
                        "reason": reason,
                        "line_type": line_type,
                        "line_idx": r + 1 if line_type == "row" else c + 1,
                    },
                )
            )

    candidates.sort(key=lambda item: item[:3])
    hints = []
    seen = set()
    for _, _, _, hint in candidates:
        key = (hint["row"], hint["col"])
        if key not in seen:
            seen.add(key)
            hints.append(hint)

    # Always provide something useful when reasoning cannot isolate a cell.
    if not hints:
        fallback = next_hint(current, solution, rows, cols)
        if fallback:
            hints.append(fallback)
    return hints


def solve_data(data, solution_cache=None):
    rows = data["row_clues"]
    cols = data["col_clues"]
    current = data.get("current")
    solution_cache_hit = False
    # Only a clue-only solution completed by propagation is provably unique.
    # Reusing an arbitrary solution on a multi-solution puzzle would flag valid moves.
    reusable = None
    if solution_cache is not None:
        key = json.dumps([rows, cols], separators=(",", ":")).encode()
        def propagate_clues():
            probe = Solver(rows, cols)
            consistent = probe.propagate()
            unique = consistent and probe.get_filled_count() == len(rows) * len(cols)
            return {"unique_solution": probe.board if unique else None}
        entry, solution_cache_hit = solution_cache.get_or_compute(key, propagate_clues)
        reusable = entry["unique_solution"]
    if reusable is not None:
        solution = reusable
    else:
        solution = Solver(rows, cols, current).solve() if current else Solver(rows, cols).solve()
        if solution is None and current:
            solution = Solver(rows, cols).solve()
    issues = validate_current_board(current, rows, cols) if current else []
    errors = find_errors(current, solution) if current and solution else []
    hints = collect_hints(current, solution, rows, cols)
    filled, total = progress(current) if current else (0, len(rows) * len(cols))
    result = {
        "row_clues": rows,
        "col_clues": cols,
        "current": current,
        "solution": solution,
        "issues": issues,
        "errors": errors,
        "hints": hints,
        "hint": hints[0] if hints else None,
        "filled": filled,
        "total": total,
        "solvable": solution is not None,
    }
    if solution_cache is not None:
        result["solution_cache_hit"] = solution_cache_hit and reusable is not None
    return result


def recognize_image(image, suffix=".png"):
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
            f.write(image)
            temp_path = f.name
        data = validate_and_fix(ocr_nonogram(temp_path, clue_cache=CLUE_CACHE, strip_cache=CLUE_STRIP_CACHE, visual_cache=VISUAL_CACHE))
        result = solve_data(data, solution_cache=SOLUTION_CACHE)
        for field in ("clue_cache_hit", "clue_cache_hits", "clue_cache_total", "auto_puzzle_match", "puzzle_similarity"):
            result[field] = data.get(field, False if field in ("clue_cache_hit", "auto_puzzle_match") else 0)
        return result
    finally:
        if temp_path:
            os.unlink(temp_path)


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, body, content_type="application/json; charset=utf-8"):
        if isinstance(body, bytes):
            raw = body
        elif isinstance(body, str):
            raw = body.encode("utf-8")
        else:
            raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            with open(os.path.join(ROOT, "index.html"), "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")
            return
        self._send(404, {"error": "Not found"})

    def do_POST(self):
        if urlparse(self.path).path != "/api/recognize":
            self._send(404, {"error": "Not found"})
            return

        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self._send(400, {"error": "请使用 multipart/form-data 上传图片"})
            return

        length = int(self.headers.get("Content-Length", "0"))
        payload = self.rfile.read(length)
        boundary = content_type.split("boundary=", 1)[-1].strip().strip('"').encode()
        marker = b"--" + boundary
        parts = payload.split(marker)
        image = None
        filename = "upload.png"
        for part in parts:
            if b"\r\n\r\n" not in part:
                continue
            headers, content = part.split(b"\r\n\r\n", 1)
            if b'name="image"' not in headers:
                continue
            if b'filename="' in headers:
                filename = headers.split(b'filename="', 1)[1].split(b'"', 1)[0].decode(
                    "utf-8", "ignore"
                )
            image = content[:-2] if content.endswith(b"\r\n") else content
            # Continue parsing: multipart field order is not significant.

        if not image:
            self._send(400, {"error": "没有找到图片文件"})
            return

        suffix = os.path.splitext(filename)[1].lower() or ".png"
        try:
            started = time.perf_counter()
            result, cache_hit = RESULT_CACHE.get_or_compute(
                image, lambda: recognize_image(image, suffix))
            self._send(200, {**result, "cache_hit": cache_hit,
                             "elapsed_seconds": round(time.perf_counter() - started, 3)})
        except Exception as exc:
            self._send(500, {"error": str(exc)})

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))


def main():
    parser = argparse.ArgumentParser(description="Nonogram 本地 Web 版")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", default=PORT, type=int)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Nonogram Web 版已启动: http://{args.host}:{args.port}")
    print("按 Ctrl+C 停止服务")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在停止...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
