import time
from itertools import combinations

from nonogram.solver import Solver, generate_patterns, compatible, line_satisfiable, solve_line, UNKNOWN, FILLED, EMPTY


def conflicting_line(row_clues, col_clues, current):
    """只用行列约束做传播，找出第一个被填成矛盾的行/列。

    返回 ("row"|"col", index) 或 None。不修改 current。
    """
    nrows = len(current)
    ncols = len(current[0]) if nrows else 0
    board = [list(x) for x in current]

    changed = True
    while changed:
        changed = False
        for r in range(nrows):
            solved = solve_line(ncols, row_clues[r], "".join(board[r]))
            if solved is None:
                return ("row", r)
            for c in range(ncols):
                if solved[c] != UNKNOWN and board[r][c] != solved[c]:
                    board[r][c] = solved[c]
                    changed = True
        for c in range(ncols):
            line = "".join(board[r][c] for r in range(nrows))
            solved = solve_line(nrows, col_clues[c], line)
            if solved is None:
                return ("col", c)
            for r in range(nrows):
                if solved[r] != UNKNOWN and board[r][c] != solved[r]:
                    board[r][c] = solved[r]
                    changed = True
    return None


def find_conflicts(row_clues, col_clues, current, solution, unique,
                   budget_sec=20.0, max_calls=200):
    """找出 current 中与解答冲突、导致无法求解的格子。

    unique=True 时解答唯一，差异格即为确定的错误格。
    否则退回"释放若干格后是否能解"的搜索，受时间/次数预算限制。
    返回 (cells, definite)：cells 为 [(row, col), ...]（0 基）。
    """
    if not current or not solution:
        return [], False
    nrows = len(current)
    ncols = len(current[0]) if nrows else 0
    diffs = [(r, c) for r in range(nrows) for c in range(ncols)
             if current[r][c] != UNKNOWN and current[r][c] != solution[r][c]]

    if unique or not diffs:
        return diffs, unique

    def solvable_dropping(drop):
        trial = [list(x) for x in current]
        for (r, c) in drop:
            trial[r][c] = UNKNOWN
        return Solver(row_clues, col_clues, ["".join(x) for x in trial]).solve() is not None

    t0 = time.time()
    calls = 0
    # 先确认"只释放差异格"就能救活，否则这些差异格不是全部原因
    if not solvable_dropping(diffs):
        return diffs, False

    limit = 3 if len(diffs) > 4 else len(diffs)
    for size in range(1, limit + 1):
        for combo in combinations(diffs, size):
            if calls >= max_calls or time.time() - t0 > budget_sec:
                return diffs, False
            calls += 1
            if solvable_dropping(combo):
                return list(combo), True
    return diffs, False


def get_line_reasoning(clues, line, line_idx, axis):
    length = len(line)
    solved = solve_line(length, clues, line)

    if solved is None:
        return None, None, "矛盾：该行/列没有可行的模式"

    definite_positions = {}
    for i in range(length):
        if line[i] == UNKNOWN and solved[i] != UNKNOWN:
            definite_positions[i] = solved[i]

    if definite_positions:
        reasoning_parts = []
        for clue_val in clues:
            reasoning_parts.append(str(clue_val))
        clue_str = ",".join(reasoning_parts)

        pos, val = next(iter(definite_positions.items()))

        overlap = _find_overlap_reason(clues, line, length)
        if overlap:
            reason = f"交叠法：提示[{clue_str}]中{overlap}"
        else:
            reason = f"枚举消去：提示[{clue_str}]在该位置所有可行方案都为{'黑格' if val == FILLED else '空格'}"

        return pos, val, reason
    return None, None, None


def _find_overlap_reason(clues, line, length):
    if not clues or sum(clues) == 0:
        return None

    min_start = [0] * len(clues)
    max_end = [0] * len(clues)

    pos = 0
    for i, c in enumerate(clues):
        min_start[i] = pos
        pos += c + 1

    pos = length
    for i in range(len(clues) - 1, -1, -1):
        max_end[i] = pos
        pos -= clues[i] + 1

    for i, c in enumerate(clues):
        earliest_end = min_start[i] + c
        latest_start = max_end[i] - clues[i]
        overlap_start = max(min_start[i], latest_start)
        overlap_end = min(earliest_end, max_end[i])
        if overlap_start < overlap_end:
            for p in range(overlap_start, overlap_end):
                if line[p] == UNKNOWN:
                    return f"第{i+1}个黑块({c}格)必定覆盖位置{p+1}"
    return None


def next_hint(current, solution, row_clues=None, col_clues=None):
    nrows = len(current)
    ncols = len(current[0]) if nrows > 0 else 0

    progress_priority = []
    for r in range(nrows):
        for c in range(ncols):
            if current[r][c] == UNKNOWN and solution[r][c] != UNKNOWN:
                row_done = sum(1 for x in current[r] if x != UNKNOWN)
                col = "".join(current[rr][c] for rr in range(nrows))
                col_done = sum(1 for x in col if x != UNKNOWN)
                priority = (row_done / ncols) + (col_done / nrows)
                progress_priority.append((priority, r, c))

    if not progress_priority:
        return None

    progress_priority.sort(reverse=True)

    if row_clues and col_clues:
        for _, r, c in progress_priority:
            row_line = current[r]
            col_line = "".join(current[rr][c] for rr in range(nrows))

            pos_in_row, val_r, reason_r = get_line_reasoning(row_clues[r], row_line, r, 0)
            pos_in_col, val_c, reason_c = get_line_reasoning(col_clues[c], col_line, c, 1)

            if pos_in_row == c:
                hint_val = solution[r][c]
                return {
                    "row": r + 1,
                    "col": c + 1,
                    "value": hint_val,
                    "value_cn": "黑格(O)" if hint_val == FILLED else "空格(X)",
                    "reason": f"第{r+1}行: {reason_r}",
                    "line_type": "row",
                    "line_idx": r + 1,
                }
            if pos_in_col == r:
                hint_val = solution[r][c]
                return {
                    "row": r + 1,
                    "col": c + 1,
                    "value": hint_val,
                    "value_cn": "黑格(O)" if hint_val == FILLED else "空格(X)",
                    "reason": f"第{c+1}列: {reason_c}",
                    "line_type": "col",
                    "line_idx": c + 1,
                }

    _, r, c = progress_priority[0]
    hint_val = solution[r][c]
    return {
        "row": r + 1,
        "col": c + 1,
        "value": hint_val,
        "value_cn": "黑格(O)" if hint_val == FILLED else "空格(X)",
        "reason": "结合行/列约束推理可得（搜索消去法）",
        "line_type": "search",
        "line_idx": None,
    }


def find_errors(current, solution):
    errors = []
    if not current or not solution:
        return errors
    for r, row in enumerate(current):
        for c, x in enumerate(row):
            if r < len(solution) and c < len(solution[r]):
                if x != UNKNOWN and x != solution[r][c]:
                    errors.append({
                        "row": r + 1,
                        "col": c + 1,
                        "current": x,
                        "current_cn": "黑格(O)" if x == FILLED else "空格(X)",
                        "correct": solution[r][c],
                        "correct_cn": "黑格(O)" if solution[r][c] == FILLED else "空格(X)",
                    })
    return errors


def validate_current_board(current, row_clues, col_clues):
    nrows = len(current)
    ncols = len(current[0]) if nrows > 0 else 0
    issues = []

    for r in range(nrows):
        line = current[r]
        clues = row_clues[r] if r < len(row_clues) else []
        if not line_satisfiable(ncols, clues, line):
            issues.append({
                "type": "row_conflict",
                "idx": r + 1,
                "message": f"第{r+1}行与提示{clues}矛盾，无可行解",
            })

    for c in range(ncols):
        line = "".join(current[r][c] for r in range(nrows))
        clues = col_clues[c] if c < len(col_clues) else []
        if not line_satisfiable(nrows, clues, line):
            issues.append({
                "type": "col_conflict",
                "idx": c + 1,
                "message": f"第{c+1}列与提示{clues}矛盾，无可行解",
            })

    return issues


def progress(current):
    if not current:
        return 0, 0
    total = sum(len(row) for row in current)
    filled = sum(1 for row in current for ch in row if ch != UNKNOWN)
    return filled, total
