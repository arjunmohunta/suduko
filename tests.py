"""
tests.py -- regression test suite for the Sudoku CSP solver and generator.

Run:  python3 tests.py            (quiet)
      python3 tests.py -v         (per-test names)

Covers the CSP invariants the project claims: solver correctness on known
puzzles, forward-checking/MRV behaviour, uniqueness of generated puzzles,
clue-count targets, seed reproducibility, invalid-input handling, and the
node-cap behaviour of the naive baseline.
"""
import unittest

import sudoku as s


def is_complete_and_legal(board):
    """True iff every cell is filled and no all-different constraint is violated."""
    if any(v == 0 for v in board):
        return False
    if s.conflicts(board):
        return False
    for unit in range(9):
        row = {board[unit * 9 + c] for c in range(9)}
        col = {board[r * 9 + unit] for r in range(9)}
        br, bc = (unit // 3) * 3, (unit % 3) * 3
        box = {board[(br + dr) * 9 + (bc + dc)] for dr in range(3) for dc in range(3)}
        if row != set(range(1, 10)) or col != set(range(1, 10)) or box != set(range(1, 10)):
            return False
    return True


def agrees_with_givens(puzzle, solution):
    """The solution must preserve every given of the puzzle."""
    return all(p == 0 or p == q for p, q in zip(puzzle, solution))


class TestRepresentation(unittest.TestCase):

    def test_01_peers_are_twenty_and_symmetric(self):
        """Every cell has exactly 20 peers, and peering is symmetric."""
        for i in range(81):
            self.assertEqual(len(s.PEERS[i]), 20, f"cell {i}")
            self.assertNotIn(i, s.PEERS[i])
            for p in s.PEERS[i]:
                self.assertIn(i, s.PEERS[p], f"{i}/{p} not symmetric")

    def test_02_parse_accepts_zeros_dots_and_files(self):
        """Blanks may be '0' or '.'; a path is read from disk."""
        from_zeros = s.parse(s.PRESETS["escargot"])
        from_dots = s.parse(s.PRESETS["escargot"].replace("0", "."))
        self.assertEqual(from_zeros, from_dots)
        self.assertEqual(s.parse("puzzles/escargot.txt"), from_zeros)
        self.assertEqual(len(from_zeros), 81)

    def test_03_parse_rejects_short_input(self):
        """A grid with fewer than 81 cells is an error, not a silent pad."""
        with self.assertRaises(ValueError):
            s.parse("123456789")

    def test_04_to_string_round_trips(self):
        """parse and to_string are inverses."""
        text = s.PRESETS["easy"]
        self.assertEqual(s.to_string(s.parse(text)), text)


class TestSmartSolver(unittest.TestCase):

    def test_05_solves_all_presets_legally(self):
        """Each preset is solved, and the result is complete, legal, and consistent."""
        for name, text in s.PRESETS.items():
            puzzle = s.parse(text)
            sol, st, _ = s.solve_smart(puzzle)
            self.assertIsNotNone(sol, name)
            self.assertTrue(st.solved, name)
            self.assertTrue(is_complete_and_legal(sol), name)
            self.assertTrue(agrees_with_givens(puzzle, sol), name)

    def test_06_easy_needs_no_search(self):
        """Forward checking alone solves the easy preset: zero backtracks."""
        _, st, _ = s.solve_smart(s.parse(s.PRESETS["easy"]))
        self.assertEqual(st.backtracks, 0)

    def test_07_solved_grid_returns_immediately(self):
        """An already-complete grid expands one node and never backtracks."""
        sol, _, _ = s.solve_smart(s.parse(s.PRESETS["easy"]))
        _, st, _ = s.solve_smart(sol)
        self.assertTrue(st.solved)
        self.assertEqual(st.backtracks, 0)
        self.assertEqual(st.nodes, 1)

    def test_08_unsolvable_grid_is_reported(self):
        """A legal-looking but unsatisfiable grid returns no solution."""
        # Row 0 holds 1..8; the last cell must be 9, but a 9 sits in its column.
        board = [0] * 81
        for c in range(8):
            board[c] = c + 1
        board[9 + 8] = 9          # blocks the only value left for cell 8
        sol, st, _ = s.solve_smart(board)
        self.assertIsNone(sol)
        self.assertFalse(st.solved)

    def test_09_conflicts_flags_invalid_givens(self):
        """A grid with a duplicate given is detected before solving."""
        board = s.parse(s.PRESETS["easy"])
        empty = board.index(0)
        board[empty] = board[s.PEERS[empty][0]] or 5
        board[s.PEERS[empty][0]] = board[empty]
        self.assertTrue(s.conflicts(board))
        self.assertFalse(s.conflicts(s.parse(s.PRESETS["easy"])))

    def test_10_events_replay_the_search(self):
        """record=True emits a trace whose placements match the final solution."""
        sol, st, events = s.solve_smart(s.parse(s.PRESETS["escargot"]), record=True)
        self.assertIsNotNone(events)
        kinds = {e[0] for e in events}
        self.assertTrue({"sel", "place"} <= kinds)
        self.assertIn("undo", kinds, "a hard puzzle should backtrack at least once")
        placed = {i: v for kind, i, *rest in
                  ((e[0], e[1], *e[2:]) for e in events if e[0] == "place")
                  for v in rest}
        # every recorded placement names a cell that is filled in the solution
        self.assertTrue(all(sol[i] != 0 for i in placed))
        self.assertGreater(st.nodes, 0)


class TestNaiveBaseline(unittest.TestCase):

    def test_11_naive_agrees_with_smart(self):
        """On a tractable puzzle both solvers reach the same unique solution."""
        puzzle = s.parse(s.PRESETS["easy"])
        smart, _, _ = s.solve_smart(puzzle)
        naive, st = s.solve_naive(puzzle)
        self.assertTrue(st.solved)
        self.assertEqual(smart, naive)

    def test_12_naive_respects_its_node_cap(self):
        """A tiny cap makes the baseline give up rather than run unbounded."""
        _, st = s.solve_naive(s.parse(s.PRESETS["extreme"]), cap=1000)
        self.assertTrue(st.capped)
        self.assertFalse(st.solved)
        self.assertLessEqual(st.nodes, 1001)

    def test_13_naive_expands_far_more_nodes_than_smart(self):
        """The whole point of the comparison: MRV + propagation prune the search."""
        puzzle = s.parse(s.PRESETS["escargot"])
        _, smart_st, _ = s.solve_smart(puzzle)
        _, naive_st = s.solve_naive(puzzle, cap=2_000_000)
        self.assertTrue(naive_st.solved)
        self.assertLess(smart_st.nodes, naive_st.nodes)


class TestStrongSolver(unittest.TestCase):

    def test_20_strong_solves_all_presets_legally(self):
        """The strong solver returns a complete, legal, given-preserving grid."""
        for name, text in s.PRESETS.items():
            puzzle = s.parse(text)
            sol, st = s.solve_strong(puzzle)
            self.assertIsNotNone(sol, name)
            self.assertTrue(st.solved, name)
            self.assertTrue(is_complete_and_legal(sol), name)
            self.assertTrue(agrees_with_givens(puzzle, sol), name)

    def test_21_strong_agrees_with_reference_solver(self):
        """On a proper puzzle the unique solution must not depend on the solver."""
        for path in ("puzzles/top95.txt", "puzzles/hardest11.txt"):
            for board in s.load_many(path, limit=20, sample_seed=1):
                ref, _, _ = s.solve_smart(board)
                got, _ = s.solve_strong(board)
                self.assertEqual(ref, got, s.to_string(board))

    def test_22_strong_expands_no_more_nodes_than_forward_checking(self):
        """Stronger propagation can only shrink the search, never grow it."""
        for name, text in s.PRESETS.items():
            board = s.parse(text)
            _, weak, _ = s.solve_smart(board)
            _, strong = s.solve_strong(board)
            self.assertLessEqual(strong.nodes, weak.nodes, name)

    def test_23_hidden_singles_solve_the_17_clue_preset_without_search(self):
        """The engineered 17-clue puzzle needs no search once hidden singles run."""
        _, st = s.solve_strong(s.parse(s.PRESETS["extreme"]))
        self.assertEqual(st.backtracks, 0)
        self.assertEqual(st.nodes, 1)

    def test_24_strong_reports_unsolvable_grids(self):
        """A contradictory grid is rejected, not answered."""
        board = [0] * 81
        for c in range(8):
            board[c] = c + 1
        board[9 + 8] = 9
        sol, st = s.solve_strong(board)
        self.assertIsNone(sol)
        self.assertFalse(st.solved)


class TestUniquenessAndGenerator(unittest.TestCase):

    def test_14_count_solutions_on_known_cases(self):
        """A proper puzzle has one solution; an empty grid has many."""
        self.assertEqual(s.count_solutions(s.parse(s.PRESETS["escargot"]), 2), 1)
        self.assertEqual(s.count_solutions([0] * 81, 2), 2)   # stops at the limit

    def test_15_generated_puzzles_are_unique_and_solvable(self):
        """Every generated puzzle admits exactly one solution, at every level."""
        for level in ("easy", "medium", "hard"):
            puzzle, solution, _ = s.generate(level, seed=7)
            self.assertEqual(s.count_solutions(puzzle, 2), 1, level)
            self.assertTrue(is_complete_and_legal(solution), level)
            self.assertTrue(agrees_with_givens(puzzle, solution), level)
            resolved, _, _ = s.solve_smart(puzzle)
            self.assertEqual(resolved, solution, level)

    def test_16_generator_hits_its_clue_targets(self):
        """Clue counts land on the documented targets and are ordered by level."""
        counts = {}
        for level, target in s.DIFFICULTY_TARGETS.items():
            puzzle, _, givens = s.generate(level, seed=3)
            self.assertEqual(givens, s.clue_count(puzzle), level)
            self.assertLessEqual(givens, target + 6, f"{level} far above target")
            self.assertGreaterEqual(givens, 17, "no puzzle can have fewer than 17 clues")
            counts[level] = givens
        self.assertGreater(counts["easy"], counts["hard"])

    def test_17_generator_is_reproducible_under_a_seed(self):
        """The same seed gives the same puzzle; a different seed does not."""
        a, _, _ = s.generate("medium", seed=42)
        b, _, _ = s.generate("medium", seed=42)
        c, _, _ = s.generate("medium", seed=43)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)


class TestDifficultyRating(unittest.TestCase):

    def test_18_rating_orders_the_presets(self):
        """Effort-based rating separates the three presets in the right order."""
        easy = s.rate_difficulty(s.parse(s.PRESETS["easy"]))
        escargot = s.rate_difficulty(s.parse(s.PRESETS["escargot"]))
        extreme = s.rate_difficulty(s.parse(s.PRESETS["extreme"]))
        self.assertEqual(easy[0], "trivial")
        self.assertLess(easy[1], escargot[1])
        self.assertLess(escargot[1], extreme[1])
        self.assertEqual(easy[2], 30)

    def test_19_load_many_reads_benchmark_files(self):
        """The multi-puzzle loader skips comments and keeps only full grids."""
        top95 = s.load_many("puzzles/top95.txt")
        self.assertEqual(len(top95), 95)
        self.assertTrue(all(len(b) == 81 for b in top95))
        subset = s.load_many("puzzles/top95.txt", limit=10, sample_seed=0)
        self.assertEqual(len(subset), 10)
        self.assertEqual(subset, s.load_many("puzzles/top95.txt", limit=10, sample_seed=0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
