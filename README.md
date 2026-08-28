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

python3 demo.py rate escargot            # rate a puzzle by the search effort it needs
python3 demo.py generate hard --seed 5   # reproducible generation

# options:  --speed <sec> (animation delay)   --no-color   --no-anim
#           --seed <int> (generator seed)     --cap <int>  (baseline node cap)
```

## Evaluation

The full evaluation is a separate harness, so the reported numbers can be regenerated from
scratch. Node and backtrack counts are exact and deterministic; wall-clock timings depend on
machine load, which is why search effort is the primary metric.

```bash
python3 fetch_data.py        # download the public benchmark sets (~12 MB into data/)
python3 benchmark.py all     # run every experiment, write results/results.json
python3 figures.py           # regenerate every figure in the report from that JSON
python3 tests.py             # 24-case regression suite
python3 make_docx.py         # render FINAL_REPORT.md -> CS175_Final_Report_Group3.docx
```

Rendering the report needs one extra package (the solvers themselves need nothing):

```bash
pip3 install python-docx
```

The `.docx` carries the heading styles, tables, monospaced pseudocode, superscripts, and the
three figures already placed, so it converts cleanly when opened in Google Docs or Word.

Individual experiments:

```bash
python3 benchmark.py presets   --cap 10000000 --repeats 50
python3 benchmark.py datasets  --limit 2000 --baseline-limit 50
python3 benchmark.py generator --per-level 30
python3 benchmark.py scaling   --limit 2000
```

### Benchmark sets

| Set | Puzzles | Source |
|---|---:|---|
| `puzzles/top95.txt` | 95 | hard puzzles collected by Peter Norvig |
| `puzzles/hardest11.txt` | 11 | "hardest" set collected by Peter Norvig |
| `data/kaggle100k.txt` | 100,000 | export of the Kaggle "1 million Sudoku games" set |
| `data/minimal17.txt` | 49,158 | minimal 17-clue puzzles (Royle's collection, extended) |
| `data/top1465.txt` | 1,465 | hard puzzles ("top1465", magictour) |
| `data/forum_hardest1106.txt` | 375 | forum-curated "hardest" collection |

The small sets are committed. The large ones are fetched on demand by `fetch_data.py` and are
gitignored.

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

Produced by `python3 benchmark.py presets`. Backtracks and nodes are exact; the baseline is
capped, and a capped row is a lower bound rather than a measurement.

| Puzzle          | Clues | Smart backtracks | Smart nodes | Plain nodes | Node ratio |
|-----------------|:-----:|:----------------:|:-----------:|:-----------:|:----------:|
| Easy            |  30   |        0         |     52      |    4,209    |    81x     |
| AI Escargot     |  23   |       151        |    210      |    8,970    |    43x     |
| 17-clue minimal |  17   |      4,048       |   4,113     | hit the cap | lower bound |

An easy puzzle solves with **0 backtracks** — pure propagation, no search. The smart solver
clears the 17-clue puzzle in milliseconds while plain backtracking exhausts its node budget
without finding a solution.

See [FINAL_REPORT.md](FINAL_REPORT.md) for solve rates over the full benchmark sets.

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
├── sudoku.py           # core CSP library: solvers, uniqueness test, generator, rating
├── demo.py             # command-line demo runner + terminal animation
├── benchmark.py        # evaluation harness -> results/results.json
├── figures.py          # regenerates every report figure from that JSON
├── fetch_data.py       # downloads the public benchmark sets
├── tests.py            # 24-case regression suite
├── index.html          # interactive web demo
├── puzzles/            # small committed puzzle sets
│   ├── escargot.txt
│   ├── top95.txt
│   └── hardest11.txt
├── data/               # large benchmark sets (fetched, gitignored)
├── results/            # benchmark JSON + figures (generated, gitignored)
├── FINAL_REPORT.md     # the written report (source of truth)
├── make_docx.py        # renders the report to a submission-ready .docx
├── README.md
└── LICENSE
```

## Team

- Arjun Mohunta
- Haoyang Ding
- Rajat Choudhary

## License

MIT — see [LICENSE](LICENSE).
