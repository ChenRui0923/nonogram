import json
from solver import UNKNOWN, FILLED, EMPTY

FILLED_CHARS = {FILLED, 'O', 'o', '0', '#', '@', '*', '■', '█', 'B', 'b'}
EMPTY_CHARS = {EMPTY, 'x'}
UNKNOWN_CHARS = {UNKNOWN, '?', 'U', 'u', '.'}


def normalize_char(ch):
    if ch in FILLED_CHARS:
        return FILLED
    if ch in EMPTY_CHARS:
        return EMPTY
    if ch in UNKNOWN_CHARS:
        return UNKNOWN
    if ch == EMPTY:
        return EMPTY
    return UNKNOWN


def normalize_current(current):
    if not current:
        return current
    result = []
    for row in current:
        if isinstance(row, list):
            new_row = [normalize_char(ch) for ch in row]
            result.append("".join(new_row))
        else:
            new_row = [normalize_char(ch) for ch in row]
            result.append("".join(new_row))
    return result


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "current" in data:
        data["current"] = normalize_current(data["current"])
    if "rows" in data and "row_clues" not in data:
        data["row_clues"] = data["rows"]
    if "cols" in data and "col_clues" not in data:
        data["col_clues"] = data["cols"]
    if "size" in data and "row_clues" in data and "col_clues" in data:
        sz = data["size"]
        while len(data["row_clues"]) < sz.get("rows", 0):
            data["row_clues"].append([])
        while len(data["col_clues"]) < sz.get("cols", 0):
            data["col_clues"].append([])
        data["row_clues"] = data["row_clues"][:sz.get("rows", len(data["row_clues"]))]
        data["col_clues"] = data["col_clues"][:sz.get("cols", len(data["col_clues"]))]
    return data
