# Solving and Generating Sudoku as a Constraint Satisfaction Problem

An interactive demo that treats Sudoku as a formal reasoning problem rather than trial-and-error.
Given any valid partial 9×9 grid it returns the unique solution; it can also generate fresh
puzzles guaranteed to have exactly one solution — and it *shows its work*, so you can watch
backtracking search and constraint propagation narrow the domains in real time.

**▶ Live demo:** `https://<your-username>.github.io/sudoku-csp/`
_(replace with your URL after enabling GitHub Pages — see below)_

> Group 3 · Course project on Constraint Satisfaction Problems

---

## What it does

- **Solver.** Fills any valid partial grid and returns the completed board, a validity flag, and
  solver statistics (backtracks, search nodes, run time).
- **Live visualization.** Empty cells display their candidate pencil-marks (the CSP *domains*).
  As values are assigned, propagation prunes those candidates; the MRV cell is ringed, assignments
  flash blue, and dead ends flash red on backtrack. Step through one move at a time or animate it.
- **Baseline comparison.** Benchmarks the smart solver against plain backtracking on the same grid,
  reporting the reduction in backtracks and time.
- **Generator.** Removes cells from a solved grid one at a time, re-checking uniqueness after every
  removal, to produce puzzles of a target difficulty (clue count).

## The approach

Sudoku is modeled as a constraint satisfaction problem: **81 variables**, each with domain **1–9**,
subject to *all-different* constraints across every row, every column, and every 3×3 box.

**Smart solver** — backtracking search with:
- **Forward-checking constraint propagation:** when a value is assigned, it is removed from the
  candidate domains of all 20 peer cells; a domain wipeout triggers an immediate backtrack.
- **Minimum Remaining Values (MRV) heuristic:** always branch on the unfilled cell with the fewest
  remaining candidates.

**Plain solver** — naive row-major backtracking (try 1–9, check validity, recurse). Used as the
baseline so the effect of the heuristics is measurable. It runs under a node cap so the browser
never hangs on the hardest puzzles.

**Generator** — starts from a randomly completed solved grid, then digs out cells in random order,
keeping a removal only if the puzzle still has exactly one solution (verified by a solution counter
that stops at two).

## Representative results

Measured by the solvers in this repo:

| Puzzle            | Clues | Smart backtracks | Plain backtracks |
|-------------------|:-----:|:----------------:|:----------------:|
| Easy              |  30   |        0         |     ~4,200       |
| AI Escargot       |  23   |       ~150       |     ~8,900       |
| 17-clue minimal   |  17   |      ~4,000      | exceeds node cap |

An easy puzzle solves with **zero backtracks** (pure propagation); the smart solver finishes the
17-clue puzzle in milliseconds while plain backtracking gives up.

## Run it locally

No build step, no dependencies — it's a single HTML file.

```bash
# just open it
open index.html          # macOS
xdg-open index.html      # Linux
# or serve it
python3 -m http.server   # then visit http://localhost:8000
```

## Repository layout

```
sudoku-csp/
├── index.html   # the entire demo: UI + CSP solvers + generator
└── README.md
```

All logic lives in `index.html` (vanilla JS, no frameworks): `solveSmart`, `solveNaive`,
`countSolutions`, and `generate`.

## Team

- Arjun Mohunta
- Haoyang Ding
- Rajat Choudhary

## License

Released under the MIT License — see [LICENSE](LICENSE).
