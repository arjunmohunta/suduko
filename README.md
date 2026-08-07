# Solving and Generating Sudoku as a Constraint Satisfaction Problem

Sudoku treated as a formal reasoning problem: **81 variables**, each with domain **1–9**,
subject to *all-different* constraints across every row, every column, and every 3×3 box.
The system **solves** any valid partial grid, **generates** new puzzles guaranteed to have a
unique solution, and **shows its work** so you can watch backtracking search and constraint
propagation narrow the domains.

> Group 3 · Course project on Constraint Satisfaction Problems

There are two front ends:

- **`demo.py`** — a Python command-line program (matches the proposal's I/O: 81-char string or
  text file in, solved grid + solver statistics out). Includes a live animated solve in the
  terminal and a guided walkthrough for presenting.
- **`index.html`** — a self-contained interactive web version. Open it in a browser, or host it
  with GitHub Pages for a shareable link.

---

## Run the demo (Python)

No dependencies — standard library only, Python 3.9+.

```bash
python3 demo.py                  # guided walkthrough — best for presenting live
python3 demo.py --auto           # same, without the "press Enter" pauses

python3 demo.py solve escargot           # solve a preset (easy | escargot | extreme)
python3 demo.py solve <81-char-string>   # or an inline string
python3 demo.py solve puzzles/escargot.txt   # or a text file
python3 demo.py animate escargot         # animated step-by-step solve in the terminal
python3 demo.py compare                  # smart vs. plain backtracking on all presets
python3 demo.py generate hard            # make an easy | medium | hard puzzle

# options:  --speed <sec> (animation delay)   --no-color   --no-anim
```

The guided walkthrough runs five beats: a hard puzzle, an animated solve, the
smart-vs-plain comparison table, puzzle generation, and the sanity checks.

## The approach

**Smart solver** — backtracking search with:
- **Forward-checking constraint propagation:** assigning a value removes it from the candidate
  domains of all 20 peer cells; a domain wipeout triggers an immediate backtrack.
- **Minimum Remaining Values (MRV) heuristic:** always branch on the unfilled cell with the
  fewest remaining candidates.

**Plain solver** — naive row-major backtracking (baseline). Runs under a node cap so it can't hang.

**Generator** — starts from a randomly completed grid, removes cells in random order, and keeps a
removal only if the puzzle still has exactly one solution (checked by a solution counter that stops
at two).

Domains are stored as 9-bit masks; peer sets are precomputed once.

## Representative results

Produced by the solvers in this repo (`python3 demo.py compare`):

| Puzzle          | Clues | Smart backtracks | Plain backtracks    |
|-----------------|:-----:|:----------------:|:-------------------:|
| Easy            |  30   |        0         |       4,157         |
| AI Escargot     |  23   |       151        |       8,911         |
| 17-clue minimal |  17   |      4,048       | exceeds node cap    |

An easy puzzle solves with **0 backtracks** (pure propagation); the smart solver clears the
17-clue puzzle in milliseconds while plain backtracking never finishes.

## The web demo

`index.html` is the whole interactive app (vanilla JS, no build step). Empty cells show their live
candidate pencil-marks; the MRV cell is ringed, assignments flash, dead ends flash red on backtrack.

```bash
open index.html            # macOS   (xdg-open on Linux)
python3 -m http.server     # then visit http://localhost:8000
```

**Host it on GitHub Pages:** push this repo, then Settings → Pages → Deploy from branch →
`main` / root. Live at `https://<your-username>.github.io/sudoku-csp/`.

## Repository layout

```
sudoku-csp/
├── sudoku.py            # core CSP library: solvers, uniqueness test, generator
├── demo.py             # command-line demo runner + terminal animation
├── index.html          # interactive web demo
├── puzzles/
│   └── escargot.txt    # example puzzle for file input
├── README.md
└── LICENSE
```

## Team

- Arjun Mohunta
- Haoyang Ding
- Rajat Choudhary

## License

MIT — see [LICENSE](LICENSE).
