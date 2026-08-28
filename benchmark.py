"""
benchmark.py -- evaluation harness for the Sudoku CSP project.

Every number reported in the final report is produced by this file, and every
run writes its raw results to JSON so figures and tables can be regenerated
without re-running the experiments.

Experiments
-----------
presets    : smart vs. naive baseline on the three preset puzzles, with a
             configurable node cap and repeated timing.
datasets   : solve rate, timing and search effort over the public benchmark
             sets (top95, Kaggle export, 17-clue collection, top1465).
generator  : difficulty calibration -- N puzzles per level under fixed seeds,
             reporting the distribution of solver effort, not just clue count.
scaling    : search effort as a function of clue count.
all        : run everything and write results/results.json.

Usage
-----
  python3 benchmark.py all
  python3 benchmark.py datasets --limit 2000
  python3 benchmark.py presets --cap 10000000 --repeats 50
  python3 benchmark.py generator --per-level 30
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

import sudoku as s

RESULTS_DIR = "results"

# The benchmark sets. `path` files with thousands of puzzles are sampled.
DATASETS = [
    ("top95",      "puzzles/top95.txt",     "95 hard puzzles collected by Norvig"),
    ("hardest11",  "puzzles/hardest11.txt", "11 'hardest' puzzles collected by Norvig"),
    ("kaggle",     "data/kaggle100k.txt",   "100k-puzzle export of the Kaggle 1M set"),
    ("minimal17",  "data/minimal17.txt",    "49,158 minimal 17-clue puzzles"),
    ("top1465",    "data/top1465.txt",      "1,465 hard puzzles (magictour)"),
    ("forum1106",  "data/forum_hardest1106.txt", "forum 'hardest' collection"),
]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def ensure_results_dir():
    os.makedirs(RESULTS_DIR, exist_ok=True)


def percentile(values, q):
    """Nearest-rank percentile; q in [0, 100]. Empty input -> 0."""
    if not values:
        return 0
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, int(round((q / 100) * (len(ordered) - 1)))))
    return ordered[k]


def summarize(values):
    """Distribution summary used for every effort/timing table in the report."""
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "mean": statistics.fmean(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
        "median": statistics.median(values),
        "min": min(values),
        "p95": percentile(values, 95),
        "p99": percentile(values, 99),
        "max": max(values),
    }


def timed_solve(board, repeats=1):
    """Solve `repeats` times, return (solution, stats, timing_summary).

    Search is deterministic: every repeat expands exactly the same nodes, so
    repeating only characterises timing noise. We report the minimum alongside
    the median because the minimum is the closest estimate of the solver's own
    cost on a machine that is doing other work, while the median and spread
    show how much the measurement moves under load. Node and backtrack counts
    are the primary metric precisely because they do not vary at all.
    """
    first = None
    times = []
    for _ in range(max(1, repeats)):
        t0 = time.perf_counter()
        sol, st, _ = s.solve_smart(board)
        times.append((time.perf_counter() - t0) * 1000)
        if first is None:
            first = (sol, st)
    summary = {
        "min_ms": min(times),
        "median_ms": statistics.median(times),
        "mean_ms": statistics.fmean(times),
        "stdev_ms": statistics.stdev(times) if len(times) > 1 else 0.0,
        "repeats": len(times),
    }
    return first[0], first[1], summary


def verify(puzzle, solution):
    """A solution counts as correct only if it is complete, legal and consistent."""
    if solution is None:
        return False
    if any(v == 0 for v in solution) or s.conflicts(solution):
        return False
    return all(p == 0 or p == q for p, q in zip(puzzle, solution))


# --------------------------------------------------------------------------- #
# experiment 1: presets, smart vs. naive baseline
# --------------------------------------------------------------------------- #
def run_presets(cap=10_000_000, repeats=50, verbose=True):
    rows = []
    for name, text in s.PRESETS.items():
        board = s.parse(text)
        sol, st, timing = timed_solve(board, repeats)
        naive_sol, nst = s.solve_naive(board, cap=cap)
        rows.append({
            "puzzle": name,
            "clues": s.clue_count(board),
            "smart_backtracks": st.backtracks,
            "smart_nodes": st.nodes,
            "smart_min_ms": timing["min_ms"],
            "smart_median_ms": timing["median_ms"],
            "smart_mean_ms": timing["mean_ms"],
            "smart_stdev_ms": timing["stdev_ms"],
            "timing_repeats": timing["repeats"],
            "smart_solved": verify(board, sol),
            "naive_backtracks": nst.backtracks,
            "naive_nodes": nst.nodes,
            "naive_time_ms": nst.time_ms,
            "naive_solved": nst.solved and verify(board, naive_sol),
            "naive_capped": nst.capped,
            "node_ratio": (nst.nodes / st.nodes) if st.nodes else None,
            "backtrack_ratio": (nst.backtracks / st.backtracks) if st.backtracks else None,
        })
    if verbose:
        print(f"\nPRESETS  (baseline node cap {cap:,}; timing = median of {repeats} runs)")
        print("-" * 100)
        print(f"{'puzzle':<12}{'clues':>6}{'smart bt':>11}{'smart nodes':>13}"
              f"{'plain bt':>14}{'plain nodes':>14}{'node ratio':>12}"
              f"{'min ms':>9}{'med ms':>9}")
        print("-" * 96)
        for r in rows:
            pb = f">{r['naive_backtracks']:,}" if r["naive_capped"] else f"{r['naive_backtracks']:,}"
            pn = f">{r['naive_nodes']:,}" if r["naive_capped"] else f"{r['naive_nodes']:,}"
            ratio = f"{r['node_ratio']:,.0f}x" if r["node_ratio"] else "n/a"
            if r["naive_capped"]:
                ratio = ">" + ratio
            print(f"{r['puzzle']:<12}{r['clues']:>6}{r['smart_backtracks']:>11,}"
                  f"{r['smart_nodes']:>13,}{pb:>14}{pn:>14}{ratio:>12}"
                  f"{r['smart_min_ms']:>9.3f}{r['smart_median_ms']:>9.3f}")
        print("-" * 96)
        print("node and backtrack counts are exact and deterministic; timings vary with")
        print("machine load, so the minimum over the repeats is the cleanest estimate.")
        capped = [r["puzzle"] for r in rows if r["naive_capped"]]
        if capped:
            print(f"baseline hit the {cap:,}-node cap without solving: {', '.join(capped)}")
            print("their ratios are lower bounds, not measured values.")
    return rows


# --------------------------------------------------------------------------- #
# experiment 2: datasets -- solve rate, timing, effort
# --------------------------------------------------------------------------- #
def run_datasets(limit=2000, sample_seed=0, baseline_limit=200,
                 baseline_cap=1_000_000, verbose=True):
    """Solve every puzzle in each available set (sampled if large).

    The baseline is run on a smaller subsample (`baseline_limit`) because on the
    hard sets it is orders of magnitude slower; that subsample is drawn from the
    same shuffled sample, so it is representative.
    """
    out = []
    for name, path, desc in DATASETS:
        if not os.path.exists(path):
            if verbose:
                print(f"  (skipping {name}: {path} not found -- run fetch_data.py)")
            continue
        boards = s.load_many(path, limit=limit, sample_seed=sample_seed)
        if not boards:
            continue

        bts, nodes, times, clues, failures = [], [], [], [], 0
        t_wall = time.perf_counter()
        for b in boards:
            t0 = time.perf_counter()
            sol, st, _ = s.solve_smart(b)
            elapsed = (time.perf_counter() - t0) * 1000
            if not verify(b, sol):
                failures += 1
                continue
            bts.append(st.backtracks)
            nodes.append(st.nodes)
            times.append(elapsed)
            clues.append(s.clue_count(b))
        wall = time.perf_counter() - t_wall

        # baseline on a subsample
        sub = boards[:min(baseline_limit, len(boards))]
        nb, n_capped, n_solved = [], 0, 0
        for b in sub:
            nsol, nst = s.solve_naive(b, cap=baseline_cap)
            nb.append(nst.nodes)
            n_capped += 1 if nst.capped else 0
            n_solved += 1 if (nst.solved and verify(b, nsol)) else 0

        smart_nodes_sub = []
        for b in sub:
            _, st, _ = s.solve_smart(b)
            smart_nodes_sub.append(st.nodes)

        entry = {
            "dataset": name,
            "description": desc,
            "path": path,
            "n_solved_attempted": len(boards),
            "solve_rate": (len(bts) / len(boards)) if boards else 0.0,
            "failures": failures,
            "wall_seconds": wall,
            "clues": summarize(clues),
            "backtracks": summarize(bts),
            "nodes": summarize(nodes),
            "time_ms": summarize(times),
            "zero_backtrack_fraction": (sum(1 for b in bts if b == 0) / len(bts)) if bts else 0.0,
            "baseline": {
                "n": len(sub),
                "cap": baseline_cap,
                "solve_rate": n_solved / len(sub) if sub else 0.0,
                "capped_fraction": n_capped / len(sub) if sub else 0.0,
                "nodes": summarize(nb),
                "smart_nodes_same_subset": summarize(smart_nodes_sub),
                "mean_node_ratio": (statistics.fmean(nb) / statistics.fmean(smart_nodes_sub))
                                   if smart_nodes_sub and statistics.fmean(smart_nodes_sub) else None,
            },
        }
        out.append(entry)

        if verbose:
            bs, ts = entry["backtracks"], entry["time_ms"]
            print(f"\n{name}  --  {desc}")
            print(f"  puzzles attempted     {entry['n_solved_attempted']:,}"
                  f"   (sampled with seed {sample_seed})" if len(boards) == limit else
                  f"  puzzles attempted     {entry['n_solved_attempted']:,}")
            print(f"  solve rate            {entry['solve_rate']*100:.2f}%"
                  f"   ({entry['failures']} failures)")
            print(f"  clues                 mean {entry['clues']['mean']:.1f}"
                  f"  range {entry['clues']['min']}-{entry['clues']['max']}")
            print(f"  backtracks            mean {bs['mean']:,.1f}   median {bs['median']:,.0f}"
                  f"   p95 {bs['p95']:,.0f}   max {bs['max']:,.0f}")
            print(f"  solved with 0 backtracks  {entry['zero_backtrack_fraction']*100:.1f}%")
            print(f"  time per puzzle       mean {ts['mean']:.3f} ms"
                  f"   median {ts['median']:.3f} ms   max {ts['max']:.1f} ms")
            print(f"  total wall time       {wall:.1f} s")
            bl = entry["baseline"]
            print(f"  baseline (n={bl['n']}, cap {bl['cap']:,}):"
                  f" solve rate {bl['solve_rate']*100:.1f}%,"
                  f" gave up on {bl['capped_fraction']*100:.1f}%")
            if bl["mean_node_ratio"]:
                print(f"  mean node ratio       {bl['mean_node_ratio']:,.1f}x"
                      + ("  (lower bound: baseline capped)" if bl["capped_fraction"] else ""))
    return out


# --------------------------------------------------------------------------- #
# experiment 3: generator difficulty calibration
# --------------------------------------------------------------------------- #
def run_generator(per_level=30, verbose=True):
    rows = []
    for level in ("easy", "medium", "hard"):
        bts, clue_list, unique_ok = [], [], 0
        t0 = time.perf_counter()
        for seed in range(per_level):
            puzzle, solution, givens = s.generate(level, seed=seed)
            if s.count_solutions(puzzle, 2) == 1:
                unique_ok += 1
            _, st, _ = s.solve_smart(puzzle)
            bts.append(st.backtracks)
            clue_list.append(givens)
        wall = time.perf_counter() - t0
        rows.append({
            "level": level,
            "target_clues": s.DIFFICULTY_TARGETS[level],
            "n": per_level,
            "seeds": f"0-{per_level - 1}",
            "unique_fraction": unique_ok / per_level,
            "clues": summarize(clue_list),
            "backtracks": summarize(bts),
            "zero_backtrack_count": sum(1 for b in bts if b == 0),
            "wall_seconds": wall,
        })
    if verbose:
        print(f"\nGENERATOR CALIBRATION  ({per_level} puzzles per level, seeds 0-{per_level-1})")
        print("-" * 92)
        print(f"{'level':<8}{'target':>7}{'clues':>8}{'unique':>9}"
              f"{'0-backtrack':>13}{'median bt':>11}{'mean bt':>10}{'max bt':>9}")
        print("-" * 92)
        for r in rows:
            print(f"{r['level']:<8}{r['target_clues']:>7}{r['clues']['mean']:>8.1f}"
                  f"{r['unique_fraction']*100:>8.0f}%{r['zero_backtrack_count']:>9}/{r['n']:<3}"
                  f"{r['backtracks']['median']:>11,.1f}{r['backtracks']['mean']:>10,.1f}"
                  f"{r['backtracks']['max']:>9,.0f}")
        print("-" * 92)
        print("clue count separates the levels, but effort distributions overlap:")
        print("some hard-level puzzles still need zero backtracking.")
    return rows


# --------------------------------------------------------------------------- #
# experiment 4: effort vs. clue count
# --------------------------------------------------------------------------- #
def run_scaling(limit=4000, sample_seed=0, verbose=True):
    """Search effort grouped by clue count, pooled across the benchmark sets."""
    by_clues = {}
    for name, path, _ in DATASETS:
        if not os.path.exists(path):
            continue
        for b in s.load_many(path, limit=limit, sample_seed=sample_seed):
            _, st, _ = s.solve_smart(b)
            by_clues.setdefault(s.clue_count(b), []).append(st.backtracks)
    rows = [{"clues": c, **summarize(v)} for c, v in sorted(by_clues.items())]
    if verbose:
        print("\nSEARCH EFFORT vs. CLUE COUNT")
        print("-" * 66)
        print(f"{'clues':>6}{'n':>8}{'median bt':>12}{'mean bt':>12}{'p95':>12}{'max':>12}")
        print("-" * 66)
        for r in rows:
            if r["n"] < 5:
                continue
            print(f"{r['clues']:>6}{r['n']:>8,}{r['median']:>12,.0f}"
                  f"{r['mean']:>12,.1f}{r['p95']:>12,.0f}{r['max']:>12,.0f}")
        print("-" * 66)
    return rows


# --------------------------------------------------------------------------- #
# experiment 5: three-way solver comparison (baseline / FC+MRV / +hidden singles)
# --------------------------------------------------------------------------- #
def run_solvers(limit=400, sample_seed=0, repeats=5, verbose=True):
    """Compare all three solvers on the same puzzles.

    Reports nodes (deterministic) and time (noisy) for the two informed solvers,
    so the cost/benefit crossover of the extra inference is visible: stronger
    propagation always expands fewer nodes, but each node costs more.
    """
    out = []
    for name, path, desc in DATASETS:
        if not os.path.exists(path):
            continue
        boards = s.load_many(path, limit=limit, sample_seed=sample_seed)
        if not boards:
            continue
        sm_nodes, st_nodes, sm_ms, st_ms = [], [], [], []
        sm_bt, st_bt, mismatches = [], [], 0
        for b in boards:
            t0 = time.perf_counter()
            sol_a, sa, _ = s.solve_smart(b)
            a_ms = (time.perf_counter() - t0) * 1000
            t0 = time.perf_counter()
            sol_b, sb = s.solve_strong(b)
            b_ms = (time.perf_counter() - t0) * 1000
            if not verify(b, sol_a) or not verify(b, sol_b) or sol_a != sol_b:
                mismatches += 1
                continue
            sm_nodes.append(sa.nodes); st_nodes.append(sb.nodes)
            sm_bt.append(sa.backtracks); st_bt.append(sb.backtracks)
            sm_ms.append(a_ms); st_ms.append(b_ms)
        if not sm_nodes:
            continue
        entry = {
            "dataset": name,
            "description": desc,
            "n": len(sm_nodes),
            "mismatches": mismatches,
            "smart": {"nodes": summarize(sm_nodes), "backtracks": summarize(sm_bt),
                      "time_ms": summarize(sm_ms)},
            "strong": {"nodes": summarize(st_nodes), "backtracks": summarize(st_bt),
                       "time_ms": summarize(st_ms)},
            "node_reduction": (statistics.fmean(sm_nodes) / statistics.fmean(st_nodes))
                              if statistics.fmean(st_nodes) else None,
            "time_ratio": (statistics.fmean(st_ms) / statistics.fmean(sm_ms))
                          if statistics.fmean(sm_ms) else None,
            "strong_zero_search_fraction":
                sum(1 for n in st_nodes if n == 1) / len(st_nodes),
            "smart_zero_search_fraction":
                sum(1 for b in sm_bt if b == 0) / len(sm_bt),
        }
        out.append(entry)
        if verbose:
            print(f"\n{name}  (n={entry['n']}, {mismatches} disagreements)")
            print(f"  nodes   FC+MRV mean {entry['smart']['nodes']['mean']:>12,.1f}"
                  f"   +hidden singles mean {entry['strong']['nodes']['mean']:>10,.1f}"
                  f"   -> {entry['node_reduction']:,.1f}x fewer")
            print(f"  worst   FC+MRV      {entry['smart']['nodes']['max']:>12,.0f}"
                  f"   +hidden singles      {entry['strong']['nodes']['max']:>10,.0f}")
            print(f"  time    FC+MRV mean {entry['smart']['time_ms']['mean']:>10.3f} ms"
                  f"   +hidden singles mean {entry['strong']['time_ms']['mean']:>8.3f} ms"
                  f"   -> {entry['time_ratio']:.2f}x")
            print(f"  solved without any search:"
                  f"  FC+MRV {entry['smart_zero_search_fraction']*100:5.1f}%"
                  f"   +hidden singles {entry['strong_zero_search_fraction']*100:5.1f}%")
    if verbose and out:
        print("\nstronger propagation always expands fewer nodes; whether it is faster")
        print("depends on whether the nodes it saves cost more than the fixpoint it runs.")
    return out


def run_presets_strong(cap=10_000_000, repeats=25, verbose=True):
    """The preset table, extended with the strong solver."""
    rows = []
    for name, text in s.PRESETS.items():
        board = s.parse(text)
        sol_a, sa, timing_a = timed_solve(board, repeats)
        times_b = []
        sol_b = sb = None
        for _ in range(max(1, repeats)):
            t0 = time.perf_counter()
            sol_b, sb = s.solve_strong(board)
            times_b.append((time.perf_counter() - t0) * 1000)
        rows.append({
            "puzzle": name,
            "clues": s.clue_count(board),
            "agree": sol_a == sol_b and verify(board, sol_b),
            "smart_nodes": sa.nodes, "smart_backtracks": sa.backtracks,
            "smart_min_ms": timing_a["min_ms"], "smart_median_ms": timing_a["median_ms"],
            "strong_nodes": sb.nodes, "strong_backtracks": sb.backtracks,
            "strong_min_ms": min(times_b), "strong_median_ms": statistics.median(times_b),
        })
    if verbose:
        print(f"\nPRESETS, THREE-WAY  (timing = min/median of {repeats} runs)")
        print("-" * 94)
        print(f"{'puzzle':<11}{'clues':>6}{'FC+MRV nodes':>14}{'FC+MRV bt':>11}"
              f"{'strong nodes':>14}{'strong bt':>11}{'FC min ms':>11}{'str min ms':>12}")
        print("-" * 94)
        for r in rows:
            print(f"{r['puzzle']:<11}{r['clues']:>6}{r['smart_nodes']:>14,}"
                  f"{r['smart_backtracks']:>11,}{r['strong_nodes']:>14,}"
                  f"{r['strong_backtracks']:>11,}{r['smart_min_ms']:>11.3f}"
                  f"{r['strong_min_ms']:>12.3f}")
        print("-" * 94)
        if all(r["agree"] for r in rows):
            print("both solvers returned the same verified solution on every preset.")
    return rows


# --------------------------------------------------------------------------- #
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("experiment", nargs="?", default="all",
                    choices=["all", "presets", "datasets", "generator", "scaling",
                             "solvers"])
    ap.add_argument("--cap", type=int, default=10_000_000,
                    help="node cap for the naive baseline on the presets")
    ap.add_argument("--repeats", type=int, default=50,
                    help="timing repeats per preset (median reported)")
    ap.add_argument("--limit", type=int, default=2000,
                    help="puzzles sampled per dataset")
    ap.add_argument("--baseline-limit", type=int, default=200,
                    help="puzzles per dataset also run through the baseline")
    ap.add_argument("--baseline-cap", type=int, default=1_000_000,
                    help="node cap for the baseline on datasets")
    ap.add_argument("--per-level", type=int, default=30,
                    help="generated puzzles per difficulty level")
    ap.add_argument("--seed", type=int, default=0, help="sampling seed")
    ap.add_argument("--out", default=os.path.join(RESULTS_DIR, "results.json"))
    args = ap.parse_args(argv)

    ensure_results_dir()
    results = {
        "meta": {
            "python": sys.version.split()[0],
            "platform": sys.platform,
            "args": vars(args),
        }
    }
    which = args.experiment

    if which in ("all", "presets"):
        results["presets"] = run_presets(cap=args.cap, repeats=args.repeats)
    if which in ("all", "generator"):
        results["generator"] = run_generator(per_level=args.per_level)
    if which in ("all", "datasets"):
        results["datasets"] = run_datasets(limit=args.limit, sample_seed=args.seed,
                                          baseline_limit=args.baseline_limit,
                                          baseline_cap=args.baseline_cap)
    if which in ("all", "scaling"):
        results["scaling"] = run_scaling(limit=args.limit, sample_seed=args.seed)
    if which in ("all", "solvers"):
        results["presets_three_way"] = run_presets_strong(cap=args.cap,
                                                          repeats=args.repeats)
        results["solvers"] = run_solvers(limit=min(args.limit, 400),
                                         sample_seed=args.seed)

    # Merge into any existing results file rather than overwriting it, so that
    # running one experiment does not discard the others.
    merged = {}
    if os.path.exists(args.out):
        try:
            with open(args.out, "r", encoding="utf-8") as fh:
                merged = json.load(fh)
        except (json.JSONDecodeError, OSError):
            merged = {}
    merged.update(results)
    merged.setdefault("meta", {}).update(results.get("meta", {}))
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, indent=2)
    print(f"\nraw results written to {args.out}")
    return results


if __name__ == "__main__":
    main()
