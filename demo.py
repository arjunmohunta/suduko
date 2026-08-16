"""
demo.py — run the Sudoku CSP project as a live demo.

Usage
-----
  python3 demo.py                     guided walkthrough (best for presenting)
  python3 demo.py --auto              guided walkthrough, no "press Enter" pauses
  python3 demo.py solve <puzzle>      solve one puzzle, print grid + stats
  python3 demo.py compare [puzzle]    smart vs. naive on presets (or one puzzle)
  python3 demo.py generate <level>    make an easy | medium | hard puzzle
  python3 demo.py animate <puzzle>    animated step-by-step solve in the terminal

<puzzle> may be a preset name (easy, escargot, extreme), an 81-character
string, or a path to a text file.

Options: --speed <sec>  (frame delay, default 0.03)   --no-color
"""
import sys
import time

import sudoku as s


USE_COLOR = sys.stdout.isatty()


def _c(code, text):
    if not USE_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


DIM = lambda t: _c("2", t)
BOLD = lambda t: _c("1", t)
GREEN = lambda t: _c("32", t)
RED = lambda t: _c("1;31", t)
CYAN = lambda t: _c("36", t)
YELLOW = lambda t: _c("1;33", t)
INV_BLUE = lambda t: _c("44;97", t)
INV_RED = lambda t: _c("41;97", t)
INV_YEL = lambda t: _c("43;30", t)


def resolve(arg: str) -> list[int]:
    if arg in s.PRESETS:
        return s.parse(s.PRESETS[arg])
    return s.parse(arg)


def render(board, givens_mask, sel=-1, active=-1, back=-1):
    out = []
    for r in range(9):
        if r % 3 == 0:
            out.append(DIM("+-------+-------+-------+"))
        row = DIM("| ")
        for c in range(9):
            i = r * 9 + c
            v = board[i]
            cell = str(v) if v else "."
            if i == back:
                cell = INV_RED(f"{cell}")
            elif i == active:
                cell = INV_BLUE(f"{cell}")
            elif i == sel:
                cell = INV_YEL(f"{cell}")
            elif v and givens_mask[i]:
                cell = BOLD(cell)
            elif v:
                cell = GREEN(cell)
            else:
                cell = DIM(cell)
            row += cell + " "
            if c % 3 == 2:
                row += DIM("| ")
        out.append(row.rstrip())
    out.append(DIM("+-------+-------+-------+"))
    return "\n".join(out)


GRID_LINES = 13


def animate(board, speed=0.03):
    givens_mask = [v != 0 for v in board]
    conf = s.conflicts(board)
    if conf:
        print(RED("Invalid puzzle — a clue repeats in a row, column, or box."))
        return
    if s.count_solutions(board, 2) == 0:
        print(RED("No solution — these clues cannot be completed."))
        return

    _, stats, events = s.solve_smart(board, record=True)
    work = board[:]

    print(BOLD("Watching the CSP solver — ") +
          DIM("givens=bold  ") + GREEN("placed=green  ") +
          INV_YEL(" MRV ") + " " + INV_BLUE(" try ") + " " + INV_RED(" undo "))
    print(render(work, givens_mask))
    sys.stdout.write(f"\033[{GRID_LINES}A")

    for kind, *rest in events:
        sel = active = back = -1
        if kind == "sel":
            sel = rest[0]
        elif kind == "place":
            i, v = rest
            work[i] = v
            active = i
        elif kind == "undo":
            i = rest[0]
            work[i] = 0
            back = i
        sys.stdout.write(render(work, givens_mask, sel, active, back))
        sys.stdout.write(f"\033[{GRID_LINES}A")
        sys.stdout.flush()
        time.sleep(speed)


    solved, st, _ = s.solve_smart(board)
    sys.stdout.write(render(solved, givens_mask) + "\n")
    print()
    print(GREEN("Solved & valid.") +
          f"  backtracks={st.backtracks}  nodes={st.nodes}  "
          f"time={st.time_ms:.2f} ms")


def solve_one(board):
    givens_mask = [v != 0 for v in board]
    print(BOLD("Puzzle") + DIM(f"   ({sum(givens_mask)} clues)"))
    print(render(board, givens_mask))
    conf = s.conflicts(board)
    if conf:
        print(RED("\nInvalid puzzle — a clue repeats in a row, column, or box."))
        return
    n = s.count_solutions(board, 2)
    if n == 0:
        print(RED("\nNo solution."))
        return
    solved, st, _ = s.solve_smart(board)
    print(BOLD("\nSolution"))
    print(render(solved, givens_mask))
    note = YELLOW("  (warning: multiple solutions)") if n > 1 else ""
    print(f"\n{GREEN('valid')}  backtracks={st.backtracks}  "
          f"nodes={st.nodes}  time={st.time_ms:.2f} ms{note}")


def compare(boards):
    print(BOLD("Smart (MRV + propagation)  vs.  plain backtracking"))
    print(DIM("-" * 74))
    hdr = f"{'puzzle':<12}{'clues':>6}{'smart bt':>11}{'plain bt':>12}"          f"{'reduction':>12}{'smart ms':>11}"
    print(hdr)
    print(DIM("-" * 74))
    for label, board in boards:
        _, ss, _ = s.solve_smart(board)
        _, ns = s.solve_naive(board, cap=10_000_000)
        clues = sum(1 for x in board if x)
        pbt = f">{ns.backtracks:,}" if ns.capped else f"{ns.backtracks:,}"
        if ns.capped:
            word, paint = "gave up", RED
        elif ss.backtracks == 0:
            word, paint = "propagation", GREEN
        else:
            word, paint = f"{ns.backtracks / max(1, ss.backtracks):.0f}x", GREEN

        row = (f"{label:<12}{clues:>6}{ss.backtracks:>11,}{pbt:>12}"
               f"{paint(f'{word:>12}')}{ss.time_ms:>9.2f} ms")
        print(row)
    print(DIM("-" * 74))
    print(DIM("plain backtracking is capped at 10,000,000 nodes (~1 min); "
              "'gave up' means it hit the cap."))


def pause(auto):
    if auto:
        print()
        return
    try:
        input(DIM("\n   [ press Enter to continue ] "))
    except (EOFError, KeyboardInterrupt):
        print()


def guided(auto=False, speed=0.03, animated=True):
    def head(n, title):
        print()
        print(BOLD(CYAN(f"  {n}. {title}")))
        print(DIM("  " + "-" * (len(title) + 4)))

    print()
    print(BOLD("  SUDOKU AS A CONSTRAINT SATISFACTION PROBLEM"))
    print(DIM("  Group 3 — Arjun Mohunta · Haoyang Ding · Rajat Choudhary"))
    print(DIM("  81 variables, domains 1-9, all-different over rows, columns, boxes."))

    head(1, "A hard puzzle: AI Escargot")
    escargot = s.parse(s.PRESETS["escargot"])
    print(render(escargot, [v != 0 for v in escargot]))
    print(DIM(f"   {sum(1 for x in escargot if x)} clues · engineered to defeat naive search"))
    pause(auto)

    head(2, "Watch the solver: MRV picks the most-constrained cell, "
            "propagation prunes")
    if animated:
        animate(escargot, speed=speed)
    else:
        solve_one(escargot)
    pause(auto)

    head(3, "Smart vs. plain backtracking on every preset")
    compare([("easy", s.parse(s.PRESETS["easy"])),
             ("escargot", escargot),
             ("extreme(17)", s.parse(s.PRESETS["extreme"]))])
    print(DIM("   easy solves with 0 backtracks (pure propagation); "
              "on the 17-clue puzzle plain search never finishes."))
    pause(auto)

    head(4, "Generating a fresh puzzle with a guaranteed unique solution")
    puzzle, solution, givens = s.generate("hard", seed=None)
    print(render(puzzle, [v != 0 for v in puzzle]))
    print(DIM(f"   {givens} clues · "
              f"unique solution: {s.count_solutions(puzzle, 2) == 1}"))
    pause(auto)

    head(5, "Sanity checks")
    inv = s.parse(s.PRESETS["easy"]); inv[1] = inv[0]
    print("   invalid grid  -> " +
          (RED("flagged") if s.conflicts(inv) else "??"))
    empty = [0] * 81
    print("   empty grid    -> " +
          GREEN(f"{s.count_solutions(empty, 2)}+ solutions (correctly not unique)"))
    solved_grid = s.solve_smart(escargot)[0]
    _, st0, _ = s.solve_smart(solved_grid)
    print("   solved grid   -> " +
          GREEN(f"returns instantly ({st0.backtracks} backtracks)"))
    print()
    print(BOLD(GREEN("  Demo complete.")))
    print()


def main(argv):
    global USE_COLOR
    args = list(argv)
    speed = 0.03
    if "--no-color" in args:
        USE_COLOR = False
        args.remove("--no-color")
    auto = "--auto" in args
    if auto:
        args.remove("--auto")
    animated = "--no-anim" not in args
    if not animated:
        args.remove("--no-anim")
    if "--speed" in args:
        i = args.index("--speed")
        speed = float(args[i + 1])
        del args[i:i + 2]

    if not args:
        guided(auto=auto, speed=speed, animated=animated)
        return

    cmd = args[0]
    if cmd == "solve":
        solve_one(resolve(args[1]))
    elif cmd == "animate":
        animate(resolve(args[1]), speed=speed)
    elif cmd == "generate":
        level = args[1] if len(args) > 1 else "medium"
        puzzle, solution, givens = s.generate(level)
        print(BOLD(f"Generated {level} puzzle") + DIM(f"  ({givens} clues)"))
        print(render(puzzle, [v != 0 for v in puzzle]))
        print(DIM(f"\n81-char string: {s.to_string(puzzle)}"))
        print(DIM(f"unique solution: {s.count_solutions(puzzle, 2) == 1}"))
    elif cmd == "compare":
        if len(args) > 1:
            compare([(args[1][:12], resolve(args[1]))])
        else:
            compare([(k, s.parse(v)) for k, v in s.PRESETS.items()])
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
