"""Difficulty-level regression tests for the Sudoku CSP project.

The generator defines difficulty by clue-count targets:

* easy: 45 clues
* medium: 34 clues
* hard: 26 clues

Every generated puzzle must also be conflict-free, reproducible with a fixed
seed, solvable, and uniquely solvable.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest

import sudoku


ROOT = Path(__file__).resolve().parent
DIGITS = set(range(1, 10))

EASY_SOLUTION = (
    "534678912"
    "672195348"
    "198342567"
    "859761423"
    "426853791"
    "713924856"
    "961537284"
    "287419635"
    "345286179"
)

AI_ESCARGOT_SOLUTION = (
    "162857493"
    "534129678"
    "789643521"
    "475312986"
    "913586742"
    "628794135"
    "356478219"
    "241935867"
    "897261354"
)

EXTREME_SOLUTION = (
    "693784512"
    "487512936"
    "125963874"
    "932651487"
    "568247391"
    "741398625"
    "319475268"
    "856129743"
    "274836159"
)

# There are no immediately repeated clues, but changing the extreme preset's
# R2C1 from 4 to 5 makes the board impossible to complete.
CONSISTENT_LOOKING_UNSAT = (
    "000000010"
    "500000000"
    "020000000"
    "000050407"
    "008000300"
    "001090000"
    "300400200"
    "050100000"
    "000806000"
)


class SudokuAssertions:
    """Assertions that do not rely on the solver's conflict checker."""

    def assert_valid_solution(self, puzzle, solution):
        self.assertIsNotNone(solution)
        self.assertEqual(81, len(solution))

        for index, given in enumerate(puzzle):
            if given:
                self.assertEqual(
                    given,
                    solution[index],
                    f"solution changed the clue at cell {index}",
                )

        for row in range(9):
            self.assertEqual(DIGITS, set(solution[row * 9 : row * 9 + 9]))

        for column in range(9):
            values = {solution[row * 9 + column] for row in range(9)}
            self.assertEqual(DIGITS, values)

        for box_row in range(0, 9, 3):
            for box_column in range(0, 9, 3):
                values = {
                    solution[(box_row + dr) * 9 + box_column + dc]
                    for dr in range(3)
                    for dc in range(3)
                }
                self.assertEqual(DIGITS, values)

    def assert_generated_level(self, level, seed):
        first = sudoku.generate(level, seed=seed)
        second = sudoku.generate(level, seed=seed)
        puzzle, generated_solution, given_count = first

        self.assertEqual(first, second, "a fixed seed must reproduce the same game")
        self.assertEqual(sudoku.DIFFICULTY_TARGETS[level], given_count)
        self.assertEqual(given_count, sum(value != 0 for value in puzzle))
        self.assertEqual(set(), sudoku.conflicts(puzzle))
        self.assertEqual(1, sudoku.count_solutions(puzzle, limit=2))
        self.assert_valid_solution(puzzle, generated_solution)

        solved, stats, _ = sudoku.solve_smart(puzzle)
        self.assertTrue(stats.solved)
        self.assertEqual(generated_solution, solved)
        return puzzle, stats


class DifficultyLevelGenerationTests(SudokuAssertions, unittest.TestCase):
    """One explicit generation test case for each supported difficulty."""

    def test_difficulty_targets_are_easy_medium_hard(self):
        self.assertEqual(45, sudoku.DIFFICULTY_TARGETS["easy"])
        self.assertEqual(34, sudoku.DIFFICULTY_TARGETS["medium"])
        self.assertEqual(26, sudoku.DIFFICULTY_TARGETS["hard"])
        self.assertGreater(
            sudoku.DIFFICULTY_TARGETS["easy"],
            sudoku.DIFFICULTY_TARGETS["medium"],
        )
        self.assertGreater(
            sudoku.DIFFICULTY_TARGETS["medium"],
            sudoku.DIFFICULTY_TARGETS["hard"],
        )

    def test_easy_level_generates_45_clue_unique_game(self):
        puzzle, _ = self.assert_generated_level("easy", seed=101)
        self.assertEqual(36, puzzle.count(0))

    def test_medium_level_generates_34_clue_unique_game(self):
        puzzle, _ = self.assert_generated_level("medium", seed=202)
        self.assertEqual(47, puzzle.count(0))

    def test_hard_level_generates_26_clue_unique_game(self):
        puzzle, _ = self.assert_generated_level("hard", seed=303)
        self.assertEqual(55, puzzle.count(0))


class BuiltInPuzzleDifficultyTests(SudokuAssertions, unittest.TestCase):
    """Regression cases for the repository's built-in challenge boards."""

    def assert_preset_solution(self, name, expected):
        puzzle = sudoku.parse(sudoku.PRESETS[name])
        original = puzzle[:]
        solution, stats, events = sudoku.solve_smart(puzzle)

        self.assertTrue(stats.solved)
        self.assertFalse(stats.capped)
        self.assertIsNone(events)
        self.assertEqual(original, puzzle, "solve_smart must not mutate its input")
        self.assertEqual(expected, sudoku.to_string(solution))
        self.assertEqual(1, sudoku.count_solutions(puzzle, limit=2))
        self.assert_valid_solution(puzzle, solution)
        return stats

    def test_easy_preset_solves_without_backtracking(self):
        stats = self.assert_preset_solution("easy", EASY_SOLUTION)
        self.assertEqual(0, stats.backtracks)

    def test_ai_escargot_has_the_known_unique_solution(self):
        stats = self.assert_preset_solution("escargot", AI_ESCARGOT_SOLUTION)
        self.assertGreater(stats.backtracks, 0)

    def test_extreme_17_clue_puzzle_has_the_known_unique_solution(self):
        puzzle = sudoku.parse(sudoku.PRESETS["extreme"])
        self.assertEqual(17, sum(value != 0 for value in puzzle))
        stats = self.assert_preset_solution("extreme", EXTREME_SOLUTION)
        self.assertGreater(stats.backtracks, 0)

    def test_hard_backtracking_trace_replays_to_the_solution(self):
        puzzle = sudoku.parse(sudoku.PRESETS["escargot"])
        solution, stats, events = sudoku.solve_smart(puzzle, record=True)
        replay = puzzle[:]
        event_kinds = {event[0] for event in events}

        for event in events:
            kind, index, *rest = event
            self.assertIn(index, range(81))
            if kind == "place":
                self.assertEqual(0, replay[index])
                replay[index] = rest[0]
            elif kind == "undo":
                self.assertNotEqual(0, replay[index])
                replay[index] = 0
            else:
                self.assertEqual("sel", kind)

        self.assertTrue(stats.solved)
        self.assertEqual({"sel", "place", "undo"}, event_kinds)
        self.assertEqual(solution, replay)
        self.assertEqual(AI_ESCARGOT_SOLUTION, sudoku.to_string(replay))


class DifficultyBoundaryAndWorkflowTests(SudokuAssertions, unittest.TestCase):
    """Boundary behavior shared by every game difficulty."""

    def test_consistent_looking_but_unsatisfiable_board_is_rejected(self):
        puzzle = sudoku.parse(CONSISTENT_LOOKING_UNSAT)
        original = puzzle[:]

        self.assertEqual(set(), sudoku.conflicts(puzzle))
        self.assertEqual(0, sudoku.count_solutions(puzzle, limit=2))
        solution, stats, _ = sudoku.solve_smart(puzzle)

        self.assertIsNone(solution)
        self.assertFalse(stats.solved)
        self.assertGreater(stats.backtracks, 0)
        self.assertEqual(original, puzzle)

    def test_solution_counter_honors_limit_for_a_multiple_solution_game(self):
        puzzle = [0] * 81

        self.assertEqual(1, sudoku.count_solutions(puzzle, limit=1))
        self.assertEqual(2, sudoku.count_solutions(puzzle, limit=2))
        self.assertEqual([0] * 81, puzzle)

    def test_naive_solver_hits_its_cap_on_the_extreme_game(self):
        puzzle = sudoku.parse(sudoku.PRESETS["extreme"])

        naive_solution, naive_stats = sudoku.solve_naive(puzzle, cap=1_000)
        smart_solution, smart_stats, _ = sudoku.solve_smart(puzzle)

        self.assertIsNone(naive_solution)
        self.assertFalse(naive_stats.solved)
        self.assertTrue(naive_stats.capped)
        self.assertEqual(1_001, naive_stats.nodes)
        self.assertTrue(smart_stats.solved)
        self.assert_valid_solution(puzzle, smart_solution)

    def test_formatted_escargot_file_matches_the_builtin_game(self):
        from_file = sudoku.parse(str(ROOT / "puzzles" / "escargot.txt"))
        from_preset = sudoku.parse(sudoku.PRESETS["escargot"])

        self.assertEqual(from_preset, from_file)

    def test_cli_solves_every_builtin_difficulty_case(self):
        for preset, expected_clues in (("easy", 30), ("escargot", 23), ("extreme", 17)):
            with self.subTest(preset=preset):
                result = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "demo.py"),
                        "solve",
                        preset,
                        "--no-color",
                    ],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )

                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn(f"({expected_clues} clues)", result.stdout)
                self.assertIn("Solution", result.stdout)
                self.assertIn("valid", result.stdout)


if __name__ == "__main__":
    unittest.main()
