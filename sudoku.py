"""
sudoku.py — Sudoku as a Constraint Satisfaction Problem.

81 variables, each with domain {1..9}, subject to all-different constraints
across every row, every column, and every 3x3 box.

Solvers
-------
solve_smart : backtracking + forward-checking constraint propagation
              + Minimum Remaining Values (MRV) variable ordering.
solve_naive : plain row-major backtracking (baseline for comparison).

Also: count_solutions (uniqueness test) and generate (puzzle creation).

A board is a list of 81 ints, row-major, with 0 for an empty cell.
"""
from __future__ import annotations
import os
import random
import time
from dataclasses import dataclass

ALL = 0x1FF  # bitmask for candidates 1..9  (bit v-1 set == value v allowed)


def _compute_peers():
    peers = [set() for _ in range(81)]
    for i in range(81):
        r, c = divmod(i, 9)
        br, bc = (r // 3) * 3, (c // 3) * 3
        for k in range(9):
            peers[i].add(r * 9 + k)
            peers[i].add(k * 9 + c)
        for dr in range(3):
            for dc in range(3):
                peers[i].add((br + dr) * 9 + (bc + dc))
        peers[i].discard(i)
    return [tuple(p) for p in peers]


PEERS = _compute_peers()          # the 20 cells constrained with each cell
_POPCOUNT = [bin(m).count("1") for m in range(ALL + 1)]


def _compute_units():
    """The 27 all-different units: 9 rows, 9 columns, 9 boxes."""
    units = []
    for r in range(9):
        units.append(tuple(r * 9 + c for c in range(9)))
    for c in range(9):
        units.append(tuple(r * 9 + c for r in range(9)))
    for br in range(0, 9, 3):
        for bc in range(0, 9, 3):
            units.append(tuple((br + dr) * 9 + (bc + dc)
                               for dr in range(3) for dc in range(3)))
    return units


UNITS = _compute_units()          # the 27 constraint scopes


# --------------------------------------------------------------------------- #
# Parsing / formatting
# --------------------------------------------------------------------------- #
def parse(source: str) -> list[int]:
    """Parse a board from an 81-char string, or from a path to a text file.

    Accepts '0' or '.' for blank cells; ignores any other whitespace/characters.
    """
    text = source
    if os.path.exists(source):
        with open(source, "r", encoding="utf-8") as fh:
            text = fh.read()
    digits = [ch for ch in text if ch in "0123456789."]
    if len(digits) < 81:
        raise ValueError(f"need 81 cells, found {len(digits)}")
    board = [0 if ch in "0." else int(ch) for ch in digits[:81]]
    return board


def to_string(board: list[int]) -> str:
    return "".join(str(v) for v in board)


def load_many(path: str, limit: int | None = None,
              sample_seed: int | None = None) -> list[list[int]]:
    """Load a multi-puzzle file: one 81-character grid per line.

    Lines beginning with '#' are treated as comments and skipped, as are lines
    that do not contain exactly 81 grid characters. This is the format used by
    the public benchmark sets (top95, the Kaggle export, the 17-clue
    collection).

    limit       : keep at most this many puzzles.
    sample_seed : if given (with limit), take a random sample of that size with
                  this seed instead of the first `limit` puzzles, so a subset is
                  representative of the whole file and reproducible.
    """
    boards = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            cells = [ch for ch in line if ch in "0123456789."]
            if len(cells) != 81:
                continue
            boards.append([0 if ch in "0." else int(ch) for ch in cells])
    if limit is not None and len(boards) > limit:
        if sample_seed is not None:
            boards = random.Random(sample_seed).sample(boards, limit)
        else:
            boards = boards[:limit]
    return boards


def clue_count(board: list[int]) -> int:
    """Number of filled cells (givens) in a board."""
    return sum(1 for v in board if v)


def conflicts(board: list[int]) -> set[int]:
    """Indices of cells whose given value clashes with a peer (invalid board)."""
    bad = set()
    for i in range(81):
        if board[i]:
            for p in PEERS[i]:
                if board[p] == board[i]:
                    bad.add(i)
                    bad.add(p)
    return bad


def format_grid(board: list[int]) -> str:
    """A plain framed 9x9 grid, '.' for blanks."""
    lines = []
    for r in range(9):
        if r % 3 == 0:
            lines.append("+-------+-------+-------+")
        row = "| "
        for c in range(9):
            v = board[r * 9 + c]
            row += (str(v) if v else ".") + " "
            if c % 3 == 2:
                row += "| "
        lines.append(row.rstrip())
    lines.append("+-------+-------+-------+")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Statistics container
# --------------------------------------------------------------------------- #
@dataclass
class Stats:
    solved: bool
    backtracks: int
    nodes: int
    time_ms: float
    capped: bool = False

    def line(self) -> str:
        n = f">{self.nodes:,}" if self.capped else f"{self.nodes:,}"
        b = f">{self.backtracks:,}" if self.capped else f"{self.backtracks:,}"
        t = f"{self.time_ms:8.2f} ms"
        status = "solved" if self.solved else ("capped" if self.capped else "no solution")
        return f"{status:<11}  backtracks={b:>12}  nodes={n:>12}  time={t}"


# --------------------------------------------------------------------------- #
# Smart solver:  MRV + forward-checking constraint propagation
# --------------------------------------------------------------------------- #
def solve_smart(board: list[int], record: bool = False, randomize: bool = False):
    """Return (solution_or_None, Stats, events).

    events is a list of ('sel', i) / ('place', i, v) / ('undo', i) tuples when
    record=True, used to drive the step-by-step visualization.
    """
    val = board[:]
    cand = [0] * 81
    for i in range(81):
        if val[i]:
            continue
        m = ALL
        for p in PEERS[i]:
            if val[p]:
                m &= ~(1 << (val[p] - 1))
        cand[i] = m

    events = [] if record else None
    stats = {"nodes": 0, "back": 0}
    start = time.perf_counter()

    def select_mrv():
        best, best_cnt = -1, 10
        for i in range(81):
            if val[i] == 0:
                cnt = _POPCOUNT[cand[i]]
                if cnt < best_cnt:
                    best_cnt, best = cnt, i
                    if cnt <= 1:
                        break
        return best

    def bt():
        stats["nodes"] += 1
        idx = select_mrv()
        if idx == -1:
            return True
        mask = cand[idx]
        if record:
            events.append(("sel", idx))
        values = [v for v in range(1, 10) if mask & (1 << (v - 1))]
        if randomize:
            random.shuffle(values)
        for v in values:
            val[idx] = v
            bit = 1 << (v - 1)
            removed = []
            ok = True
            if record:
                events.append(("place", idx, v))
            for p in PEERS[idx]:
                if val[p] == 0 and (cand[p] & bit):
                    cand[p] &= ~bit
                    removed.append(p)
                    if cand[p] == 0:
                        ok = False
            saved, cand[idx] = cand[idx], 0
            if ok and bt():
                return True
            val[idx] = 0
            cand[idx] = saved
            for p in removed:
                cand[p] |= bit
            if record:
                events.append(("undo", idx))
        stats["back"] += 1
        return False

    solved = bt()
    st = Stats(solved, stats["back"], stats["nodes"],
               (time.perf_counter() - start) * 1000)
    return (val if solved else None), st, events


# --------------------------------------------------------------------------- #
# Strong solver:  MRV + forward checking + hidden singles, propagated to a
# fixpoint before every branching decision.
# --------------------------------------------------------------------------- #
def _assign(i, v, val, cand):
    """Assign v to cell i and prune v from every peer domain.

    Returns False if the assignment is immediately inconsistent (the value is
    not in i's domain, a peer already holds it, or a peer domain is wiped out).
    """
    bit = 1 << (v - 1)
    if not (cand[i] & bit):
        return False
    val[i] = v
    cand[i] = 0
    for p in PEERS[i]:
        if val[p] == v:
            return False
        if val[p] == 0:
            if cand[p] & bit:
                cand[p] &= ~bit
                if cand[p] == 0:
                    return False
    return True


def _propagate(val, cand):
    """Run naked singles and hidden singles to a fixpoint.

    naked single  -- a cell with exactly one candidate left must take it.
    hidden single -- if a value can go in only one cell of a unit, it goes there,
                     even when that cell still has several candidates.

    Forward checking alone only ever reasons from an assignment outward to its
    peers. Hidden singles reason in the other direction: from a *unit* inward to
    the one cell that can still host a value. That inference is invisible to
    forward checking, and it is what lets this solver place values that MRV
    would otherwise have to guess.

    Returns False if a contradiction is derived.
    """
    changed = True
    while changed:
        changed = False
        for i in range(81):
            if val[i] == 0:
                m = cand[i]
                if m == 0:
                    return False
                if _POPCOUNT[m] == 1:
                    if not _assign(i, m.bit_length(), val, cand):
                        return False
                    changed = True
        for unit in UNITS:
            for v in range(1, 10):
                bit = 1 << (v - 1)
                spot = -1
                count = 0
                taken = False
                for i in unit:
                    if val[i] == v:
                        taken = True
                        break
                    if val[i] == 0 and (cand[i] & bit):
                        count += 1
                        spot = i
                        if count > 1:
                            break
                if taken:
                    continue
                if count == 0:
                    return False          # no cell in this unit can hold v
                if count == 1:
                    if not _assign(spot, v, val, cand):
                        return False
                    changed = True
    return True


def solve_strong(board: list[int]):
    """Return (solution_or_None, Stats).

    Same MRV branching as solve_smart, but each node first propagates naked and
    hidden singles to a fixpoint. Domains are copied per branch rather than
    trail-undone, which costs a little memory per node and buys a much simpler
    correctness argument.
    """
    stats = {"nodes": 0, "back": 0}
    start = time.perf_counter()

    val = [0] * 81
    cand = [ALL] * 81
    ok = True
    for i, v in enumerate(board):
        if v and not _assign(i, v, val, cand):
            ok = False
            break
    if ok:
        ok = _propagate(val, cand)

    def bt(val, cand):
        stats["nodes"] += 1
        best, best_cnt = -1, 10
        for i in range(81):
            if val[i] == 0:
                cnt = _POPCOUNT[cand[i]]
                if cnt < best_cnt:
                    best_cnt, best = cnt, i
                    if cnt <= 1:
                        break
        if best == -1:
            return val
        mask = cand[best]
        for v in range(1, 10):
            if not (mask & (1 << (v - 1))):
                continue
            nval, ncand = val[:], cand[:]
            if _assign(best, v, nval, ncand) and _propagate(nval, ncand):
                got = bt(nval, ncand)
                if got is not None:
                    return got
        stats["back"] += 1
        return None

    solution = bt(val, cand) if ok else None
    st = Stats(solution is not None, stats["back"], stats["nodes"],
               (time.perf_counter() - start) * 1000)
    return solution, st


# --------------------------------------------------------------------------- #
# Naive baseline:  plain row-major backtracking
# --------------------------------------------------------------------------- #
def solve_naive(board: list[int], cap: int = 500_000):
    """Return (solution_or_None, Stats). Bails out after `cap` nodes."""
    b = board[:]
    stats = {"nodes": 0, "back": 0, "capped": False}
    start = time.perf_counter()

    def valid(idx, v):
        r, c = divmod(idx, 9)
        for k in range(9):
            if b[r * 9 + k] == v or b[k * 9 + c] == v:
                return False
        br, bc = (r // 3) * 3, (c // 3) * 3
        for dr in range(3):
            for dc in range(3):
                if b[(br + dr) * 9 + (bc + dc)] == v:
                    return False
        return True

    def bt():
        if stats["capped"]:
            return False
        stats["nodes"] += 1
        if stats["nodes"] > cap:
            stats["capped"] = True
            return False
        idx = -1
        for i in range(81):
            if b[i] == 0:
                idx = i
                break
        if idx == -1:
            return True
        for v in range(1, 10):
            if valid(idx, v):
                b[idx] = v
                if bt():
                    return True
                b[idx] = 0
        stats["back"] += 1
        return False

    solved = bt()
    st = Stats(solved, stats["back"], stats["nodes"],
               (time.perf_counter() - start) * 1000, stats["capped"])
    return (b if solved else None), st


# --------------------------------------------------------------------------- #
# Uniqueness test + generator
# --------------------------------------------------------------------------- #
def count_solutions(board: list[int], limit: int = 2) -> int:
    """Count solutions, stopping once `limit` is reached."""
    val = board[:]
    cand = [0] * 81
    for i in range(81):
        if val[i]:
            continue
        m = ALL
        for p in PEERS[i]:
            if val[p]:
                m &= ~(1 << (val[p] - 1))
        cand[i] = m
    count = [0]

    def select():
        best, best_cnt = -1, 10
        for i in range(81):
            if val[i] == 0:
                cnt = _POPCOUNT[cand[i]]
                if cnt < best_cnt:
                    best_cnt, best = cnt, i
                    if cnt <= 1:
                        break
        return best

    def bt():
        if count[0] >= limit:
            return
        idx = select()
        if idx == -1:
            count[0] += 1
            return
        mask = cand[idx]
        for v in range(1, 10):
            if not (mask & (1 << (v - 1))):
                continue
            val[idx] = v
            bit = 1 << (v - 1)
            removed = []
            ok = True
            for p in PEERS[idx]:
                if val[p] == 0 and (cand[p] & bit):
                    cand[p] &= ~bit
                    removed.append(p)
                    if cand[p] == 0:
                        ok = False
            saved, cand[idx] = cand[idx], 0
            if ok:
                bt()
            val[idx] = 0
            cand[idx] = saved
            for p in removed:
                cand[p] |= bit
            if count[0] >= limit:
                return

    bt()
    return count[0]


DIFFICULTY_TARGETS = {"easy": 45, "medium": 34, "hard": 26}


def generate(difficulty: str = "medium", seed: int | None = None):
    """Create a puzzle with a unique solution at the given difficulty.

    Returns (puzzle, solution, given_count).
    """
    if seed is not None:
        random.seed(seed)
    target = DIFFICULTY_TARGETS.get(difficulty, 34)
    solution, _, _ = solve_smart([0] * 81, randomize=True)
    puzzle = solution[:]
    givens = 81
    order = list(range(81))
    random.shuffle(order)
    for pos in order:
        if givens <= target:
            break
        if puzzle[pos] == 0:
            continue
        saved = puzzle[pos]
        puzzle[pos] = 0
        if count_solutions(puzzle, 2) != 1:
            puzzle[pos] = saved  # removal broke uniqueness — put it back
        else:
            givens -= 1
    return puzzle, solution, givens


# --------------------------------------------------------------------------- #
# Well-known preset puzzles
# --------------------------------------------------------------------------- #
PRESETS = {
    "easy":     "530070000600195000098000060800060003400803001700020006060000280000419005000080079",
    "escargot": "100007090030020008009600500005300900010080002600004000300000010040000007007000300",
    "extreme":  "000000010400000000020000000000050407008000300001090000300400200050100000000806000",
}

# --------------------------------------------------------------------------- #
# Difficulty rating
# --------------------------------------------------------------------------- #
# Thresholds are calibrated in the report from the distribution of smart-solver
# backtracks over the public benchmark sets; see benchmark.py --calibrate.
RATING_BANDS = [
    (0, "trivial"),        # solved by propagation alone, no search
    (10, "easy"),
    (100, "medium"),
    (1000, "hard"),
    (float("inf"), "extreme"),
]


def rate_difficulty(board: list[int]) -> tuple[str, int, int]:
    """Rate a puzzle by the search effort the smart solver actually needs.

    Returns (label, backtracks, clues). Clue count alone is a weak proxy for
    difficulty -- two puzzles with the same number of givens can differ by
    orders of magnitude in search effort -- so the operational measure here is
    the number of backtracks the MRV + forward-checking solver performs.
    """
    _, st, _ = solve_smart(board)
    for threshold, label in RATING_BANDS:
        if st.backtracks <= threshold:
            return label, st.backtracks, clue_count(board)
    return "extreme", st.backtracks, clue_count(board)
