from nonogram.solver import UNKNOWN, FILLED, EMPTY


def print_board(board, row_clues=None, col_clues=None, errors=None, hint_pos=None, show_numbers=True):
    if not board:
        return
    nrows = len(board)
    ncols = len(board[0]) if nrows > 0 else 0

    error_set = set()
    if errors:
        for e in errors:
            error_set.add((e["row"] - 1, e["col"] - 1))

    hint_r, hint_c = -1, -1
    if hint_pos:
        hint_r, hint_c = hint_pos[0] - 1, hint_pos[1] - 1

    max_row_clue = 0
    if row_clues:
        max_row_clue = max((len(rc) for rc in row_clues), default=0)

    max_col_clue = 0
    if col_clues:
        max_col_clue = max((len(cc) for cc in col_clues), default=0)

    def _fmt_clue(clue_list, width, vertical=False):
        if not clue_list:
            return " " * width
        parts = [str(x) for x in clue_list]
        if vertical:
            return parts
        s = " ".join(parts)
        if len(s) > width:
            s = ",".join(parts)
        return s.rjust(width)

    left_pad = max_row_clue * 4 + 2 if show_numbers and row_clues else 0
    left_sep = "  " if left_pad > 0 else ""

    if show_numbers and col_clues and max_col_clue > 0:
        for level in range(max_col_clue):
            line = " " * left_pad + left_sep
            for c in range(ncols):
                clues = col_clues[c]
                idx = len(clues) - max_col_clue + level
                if idx >= 0 and idx < len(clues):
                    val = str(clues[idx])
                    line += val.rjust(3)
                else:
                    line += "   "
                if (c + 1) % 5 == 0 and c != ncols - 1:
                    line += "│"
                else:
                    line += " "
            print(line)
        print(" " * left_pad + left_sep + "─" * (ncols * 4))

    for r in range(nrows):
        prefix = ""
        if show_numbers and row_clues:
            rc = row_clues[r] if r < len(row_clues) else []
            parts = [str(x) for x in rc]
            clue_str = " ".join(parts).rjust(max_row_clue * 4 - 1)
            prefix = clue_str + " │"

        line = prefix + " "
        for c in range(ncols):
            ch = board[r][c]
            is_err = (r, c) in error_set
            is_hint = (r == hint_r and c == hint_c)

            if ch == FILLED:
                cell = "██"
            elif ch == EMPTY:
                cell = "·X"
            else:
                cell = "  "

            if is_hint:
                line += f"({cell})"
            elif is_err:
                line += f"<{cell}>"
            else:
                line += f" {cell} "

            if (c + 1) % 5 == 0 and c != ncols - 1:
                line += "│"
        print(line)

        if (r + 1) % 5 == 0 and r != nrows - 1:
            sep = " " * left_pad + left_sep
            sep += "─" * (ncols * 4 + (ncols - 1) // 5)
            print(sep)


def print_compact(board):
    for row in board:
        print("".join(row))


def format_clues(row_clues, col_clues):
    lines = []
    lines.append(f"行提示 ({len(row_clues)} 行):")
    for i, rc in enumerate(row_clues, 1):
        lines.append(f"  R{i:>2}: {rc}")
    lines.append(f"列提示 ({len(col_clues)} 列):")
    for i, cc in enumerate(col_clues, 1):
        lines.append(f"  C{i:>2}: {cc}")
    return "\n".join(lines)
