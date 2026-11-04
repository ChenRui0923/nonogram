from itertools import product

UNKNOWN = "."
FILLED = "O"
EMPTY = "X"


def generate_patterns(length, clues):
    """枚举一行/列的所有可行排布（保留向后兼容，新求解器不再调用）。"""
    result = []

    def dfs(idx, pos, line):
        if idx == len(clues):
            result.append("".join(line + [EMPTY] * (length - len(line))))
            return
        need = sum(clues[idx:]) + len(clues[idx:]) - 1
        block = clues[idx]
        for start in range(pos, length - need + 1):
            cur = line + [EMPTY] * (start - len(line))
            cur += [FILLED] * block
            if idx != len(clues) - 1:
                cur += [EMPTY]
            dfs(idx + 1, start + block + (1 if idx != len(clues) - 1 else 0), cur)

    if not clues or (len(clues) == 1 and clues[0] == 0):
        return [EMPTY * length]

    dfs(0, 0, [])
    return result


def compatible(pattern, current):
    return all(a == b or b == UNKNOWN for a, b in zip(pattern, current))


# ---------------------------------------------------------------------------
# DP-based line solver — polynomial time, no pattern materialization.
# ---------------------------------------------------------------------------

def line_satisfiable(length, clues, current):
    """检查在 current 约束下，clues 是否有可行排布。

    DP: reachable 存放"上一块结束后位置"的集合，逐块推进。
    用前缀和做 O(1) 区间检查，整体 O(length × num_clues)。
    """
    if not clues or (len(clues) == 1 and clues[0] == 0):
        return all(ch != FILLED for ch in current)

    n = len(clues)

    # 前缀和：empty_pref[i] = current[0..i-1] 中 EMPTY 的个数
    # filled_pref[i] = current[0..i-1] 中 FILLED 的个数
    # 区间 [a, b) 有 EMPTY ⟺ empty_pref[b] - empty_pref[a] > 0
    empty_pref = [0] * (length + 1)
    filled_pref = [0] * (length + 1)
    for i in range(length):
        empty_pref[i + 1] = empty_pref[i] + (1 if current[i] == EMPTY else 0)
        filled_pref[i + 1] = filled_pref[i] + (1 if current[i] == FILLED else 0)

    def has_empty(a, b):
        return empty_pref[b] - empty_pref[a] > 0

    def has_filled(a, b):
        return filled_pref[b] - filled_pref[a] > 0

    # min_pos[j] / max_pos[j]：第 j 块起始位置的紧凑下界/上界
    min_pos = [0] * n
    p = 0
    for j in range(n):
        min_pos[j] = p
        p += clues[j] + 1
    max_pos = [0] * n
    p = length
    for j in range(n - 1, -1, -1):
        p -= clues[j]
        max_pos[j] = p
        p -= 1

    reachable = {0}
    for j in range(n):
        block = clues[j]
        next_reachable = set()
        for prev_end in reachable:
            min_start = prev_end + 1 if j > 0 else prev_end
            lo = max(min_start, min_pos[j])
            hi = max_pos[j]
            for s in range(lo, hi + 1):
                e = s + block
                if e > length:
                    break
                if has_empty(s, e):
                    continue
                if has_filled(prev_end, s):
                    continue
                if j == n - 1:
                    if has_filled(e, length):
                        continue
                    next_reachable.add(length)
                else:
                    next_reachable.add(e)
        reachable = next_reachable
        if not reachable:
            return False
    return length in reachable


def solve_line(length, clues, current):
    """返回一条新线，每个位置为 FILLED/EMPTY（如果所有可行排布一致）或 UNKNOWN。

    若无可行排布返回 None。
    O(length × num_clues) 判断 + O(length² × num_clues) 逐格确定。
    对 50×50 约几万次操作，瞬间完成。
    """
    # 先检查整体可行性
    if not line_satisfiable(length, clues, current):
        return None

    result = list(current)
    for i in range(length):
        if current[i] != UNKNOWN:
            continue
        # 尝试该位置为 EMPTY
        trial_empty = current[:i] + EMPTY + current[i + 1:]
        can_empty = line_satisfiable(length, clues, trial_empty)
        # 尝试该位置为 FILLED
        trial_filled = current[:i] + FILLED + current[i + 1:]
        can_filled = line_satisfiable(length, clues, trial_filled)

        if can_filled and not can_empty:
            result[i] = FILLED
        elif can_empty and not can_filled:
            result[i] = EMPTY
        # else: 两者皆可或皆不可（皆不可不应发生，因为整体可行），保持 UNKNOWN

    return "".join(result)


class Solver:
    def __init__(self, rows, cols, current=None):
        self.rows = rows
        self.cols = cols
        self.nrows = len(rows)
        self.ncols = len(cols)
        if current:
            self.board = [list(x) for x in current]
        else:
            self.board = [[UNKNOWN] * self.ncols for _ in range(self.nrows)]

    def propagate(self):
        """用 DP 行/列求解器做约束传播，直到稳定。"""
        changed = True
        while changed:
            changed = False
            for r in range(self.nrows):
                cur_row = "".join(self.board[r])
                solved = solve_line(self.ncols, self.rows[r], cur_row)
                if solved is None:
                    return False
                for c in range(self.ncols):
                    if solved[c] != UNKNOWN and self.board[r][c] != solved[c]:
                        self.board[r][c] = solved[c]
                        changed = True
            for c in range(self.ncols):
                cur_col = "".join(self.board[r][c] for r in range(self.nrows))
                solved = solve_line(self.nrows, self.cols[c], cur_col)
                if solved is None:
                    return False
                for r in range(self.nrows):
                    if solved[r] != UNKNOWN and self.board[r][c] != solved[r]:
                        self.board[r][c] = solved[r]
                        changed = True
        return True

    def solve(self):
        try:
            if not self.propagate():
                return None
        except RecursionError:
            return None
        # 检查是否已完全确定
        for r in range(self.nrows):
            for c in range(self.ncols):
                if self.board[r][c] == UNKNOWN:
                    return self.search()
        return [row[:] for row in self.board]

    def search(self):
        # 找一个未确定的格子，优先选行/列已确定格子最多的（约束最紧）
        target_r, target_c = -1, -1
        best_score = -1
        for r in range(self.nrows):
            row_done = sum(1 for x in self.board[r] if x != UNKNOWN)
            for c in range(self.ncols):
                if self.board[r][c] == UNKNOWN:
                    col_done = sum(1 for rr in range(self.nrows) if self.board[rr][c] != UNKNOWN)
                    score = row_done + col_done
                    if score > best_score:
                        best_score = score
                        target_r, target_c = r, c

        if target_r < 0:
            return [row[:] for row in self.board]

        for v in (FILLED, EMPTY):
            clone = Solver(self.rows, self.cols)
            clone.board = [row[:] for row in self.board]
            clone.board[target_r][target_c] = v
            try:
                ans = clone.solve()
                if ans:
                    return ans
            except RecursionError:
                continue
        return None

    def get_filled_count(self):
        return sum(1 for r in self.board for c in r if c != UNKNOWN)
