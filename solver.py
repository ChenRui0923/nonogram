from itertools import product

UNKNOWN = "."
FILLED = "O"
EMPTY = "X"


def generate_patterns(length, clues):
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


class Solver:
    def __init__(self, rows, cols, current=None):
        self.rows = rows
        self.cols = cols
        self.nrows = len(rows)
        self.ncols = len(cols)
        self.rpat = [generate_patterns(self.ncols, x) for x in rows]
        self.cpat = [generate_patterns(self.nrows, x) for x in cols]
        if current:
            self.board = [list(x) for x in current]
        else:
            self.board = [[UNKNOWN] * self.ncols for _ in range(self.nrows)]

    def propagate(self):
        changed = True
        while changed:
            changed = False
            for r in range(self.nrows):
                cur_row = "".join(self.board[r])
                cand = [x for x in self.rpat[r] if compatible(x, cur_row)]
                if not cand:
                    return False
                if len(cand) < len(self.rpat[r]):
                    self.rpat[r] = cand
                    changed = True
                for c in range(self.ncols):
                    vals = {x[c] for x in cand}
                    if len(vals) == 1:
                        v = vals.pop()
                        if self.board[r][c] != v:
                            self.board[r][c] = v
                            changed = True
            for c in range(self.ncols):
                cur_col = "".join(self.board[r][c] for r in range(self.nrows))
                cand = [x for x in self.cpat[c] if compatible(x, cur_col)]
                if not cand:
                    return False
                if len(cand) < len(self.cpat[c]):
                    self.cpat[c] = cand
                    changed = True
                for r in range(self.nrows):
                    vals = {x[r] for x in cand}
                    if len(vals) == 1:
                        v = vals.pop()
                        if self.board[r][c] != v:
                            self.board[r][c] = v
                            changed = True
        return True

    def solve(self):
        try:
            if not self.propagate():
                return None
        except RecursionError:
            return None
        if all(len(x) == 1 for x in self.rpat + self.cpat):
            return [row[:] for row in self.board]
        return self.search()

    def search(self):
        target_r, target_c = -1, -1
        min_branch = float('inf')
        for r in range(self.nrows):
            for c in range(self.ncols):
                if self.board[r][c] == UNKNOWN:
                    row_cur = "".join(self.board[r])
                    col_cur = "".join(self.board[rr][c] for rr in range(self.nrows))
                    r_cand = [x for x in self.rpat[r] if compatible(x, row_cur)]
                    c_cand = [x for x in self.cpat[c] if compatible(x, col_cur)]
                    branch = min(len(r_cand), len(c_cand))
                    if branch < min_branch:
                        min_branch = branch
                        target_r, target_c = r, c
                    if branch <= 2:
                        break
            if min_branch <= 2:
                break

        if target_r < 0:
            return [row[:] for row in self.board]

        for v in [FILLED, EMPTY]:
            try:
                clone_board = ["".join(row) for row in self.board]
                clone = Solver(self.rows, self.cols, clone_board)
                clone.rpat = [p[:] for p in self.rpat]
                clone.cpat = [p[:] for p in self.cpat]
                clone.board[target_r][target_c] = v
                ans = clone.solve()
                if ans:
                    return ans
            except RecursionError:
                continue
        return None

    def get_filled_count(self):
        return sum(1 for r in self.board for c in r if c != UNKNOWN)
