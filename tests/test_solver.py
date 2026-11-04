import itertools
from pathlib import Path
import unittest
from solver import solve_line, generate_patterns, compatible


class LineConsensusTests(unittest.TestCase):
    def test_all_small_lines_against_enumeration(self):
        # Every clue shape and partial marking through length six, including conflicts.
        for length in range(1, 7):
            shapes = {tuple(len(list(g)) for ch, g in itertools.groupby(bits) if ch == 'O')
                      for bits in itertools.product('OX', repeat=length)}
            for clues in shapes:
                patterns = generate_patterns(length, clues)
                for marks in itertools.product('.OX', repeat=length):
                    current = ''.join(marks)
                    valid = [p for p in patterns if compatible(p, current)]
                    expected = (''.join(next(iter(v)) if len(v) == 1 else '.'
                                        for v in map(set, zip(*valid))) if valid else None)
                    self.assertEqual(solve_line(length, clues, current), expected,
                                     (length, clues, current))

    def test_large_puzzle_solution_and_conflicts(self):
        from web_app import solve_data
        from ocr_nonogram import ocr_nonogram, validate_and_fix
        fixture = Path(__file__).resolve().parents[1] / 'debug.png'
        puzzle = validate_and_fix(ocr_nonogram(str(fixture)))
        self.assertEqual(len(puzzle['row_clues']), 50)
        result = solve_data(puzzle)
        self.assertTrue(result['solvable'])
        shape = lambda line: [len(list(g)) for ch, g in itertools.groupby(line) if ch == 'O']
        self.assertEqual([shape(r) for r in result['solution']], puzzle['row_clues'])
        self.assertEqual([shape(c) for c in zip(*result['solution'])], puzzle['col_clues'])
        self.assertEqual({(e['row'], e['col']) for e in result['errors']},
                         {(44, 40), (44, 45), (45, 40), (45, 43),
                          (49, 40), (49, 45), (50, 40), (50, 43)})

    def test_impossible_and_zero_clues(self):
        self.assertIsNone(solve_line(4, [5], '....'))
        self.assertEqual(solve_line(4, [0], '....'), 'XXXX')
        self.assertIsNone(solve_line(4, [], '..O.'))


if __name__ == '__main__':
    unittest.main()
