"""
figures.py -- regenerate every figure in the final report from results/results.json.

Run benchmark.py first, then:  python3 figures.py

Writes PNGs into results/. Nothing here recomputes a number; every value is read
from the JSON the harness produced, so the figures and the tables in the report
cannot drift apart.
"""
from __future__ import annotations

import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

import sudoku as s

RESULTS = "results/results.json"
OUT = "results"

INK = "#1a1a1a"
SMART = "#2b6cb0"
NAIVE = "#c53030"
MUTED = "#718096"
ACCENT = "#dd6b20"


def style(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(MUTED)
    ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(colors=INK, labelsize=9)
    ax.grid(axis="y", color="#e2e8f0", linewidth=0.8)
    ax.set_axisbelow(True)


def load():
    with open(RESULTS, "r", encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------- #
# Figure 1 -- the constraint structure: one cell and its 20 peers
# --------------------------------------------------------------------------- #
def fig_peers(path="results/fig1_peers.png"):
    target = 40  # centre cell, row 4 col 4
    peers = set(s.PEERS[target])
    fig, ax = plt.subplots(figsize=(4.6, 4.6))
    for i in range(81):
        r, c = divmod(i, 9)
        x, y = c, 8 - r
        if i == target:
            fc, label, lc = ACCENT, "cell", "white"
        elif i in peers:
            fc, label, lc = "#bee3f8", "", INK
        else:
            fc, label, lc = "white", "", INK
        ax.add_patch(Rectangle((x, y), 1, 1, facecolor=fc,
                               edgecolor="#cbd5e0", linewidth=0.8))
        if label:
            ax.text(x + 0.5, y + 0.5, label, ha="center", va="center",
                    fontsize=7, color=lc, fontweight="bold")
    for k in range(0, 10, 3):
        ax.plot([k, k], [0, 9], color=INK, linewidth=1.6)
        ax.plot([0, 9], [k, k], color=INK, linewidth=1.6)
    ax.set_xlim(-0.1, 9.1)
    ax.set_ylim(-0.1, 9.1)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Each cell shares a constraint with exactly 20 peers\n"
                 "(its row, its column, its box)", fontsize=10, color=INK, pad=12)
    fig.tight_layout()
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)
    return path


# --------------------------------------------------------------------------- #
# Figure 2 -- smart vs. baseline search effort on the presets (log scale)
# --------------------------------------------------------------------------- #
def fig_presets(data, path="results/fig2_presets.png"):
    rows = data.get("presets")
    if not rows:
        return None
    names = [r["puzzle"] for r in rows]
    smart = [max(r["smart_nodes"], 1) for r in rows]
    naive = [max(r["naive_nodes"], 1) for r in rows]
    x = range(len(rows))
    w = 0.38

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    b1 = ax.bar([i - w / 2 for i in x], smart, w, label="MRV + forward checking",
                color=SMART)
    b2 = ax.bar([i + w / 2 for i in x], naive, w, label="plain backtracking",
                color=NAIVE)
    ax.set_yscale("log")
    ax.set_ylabel("search nodes expanded (log scale)", fontsize=9, color=INK)
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{n}\n{r['clues']} clues" for n, r in zip(names, rows)],
                       fontsize=9)
    style(ax)

    for rect, r in zip(b1, rows):
        ax.text(rect.get_x() + rect.get_width() / 2, rect.get_height() * 1.15,
                f"{r['smart_nodes']:,}", ha="center", fontsize=8, color=SMART)
    for rect, r in zip(b2, rows):
        tag = f">{r['naive_nodes']:,}" if r["naive_capped"] else f"{r['naive_nodes']:,}"
        ax.text(rect.get_x() + rect.get_width() / 2, rect.get_height() * 1.15,
                tag, ha="center", fontsize=8, color=NAIVE)

    capped = [r for r in rows if r["naive_capped"]]
    note = ""
    if capped:
        cap = data["meta"]["args"]["cap"]
        note = (f"  baseline hit its {cap:,}-node cap without solving "
                f"{', '.join(r['puzzle'] for r in capped)}; those bars are lower bounds")
    ax.set_title("Search effort: informed vs. uninformed backtracking" + "\n"
                 + note.strip(), fontsize=10, color=INK, pad=10)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)
    return path


# --------------------------------------------------------------------------- #
# Figure 3 -- generator calibration: effort distribution per difficulty level
# --------------------------------------------------------------------------- #
def fig_generator(data, path="results/fig3_generator.png"):
    rows = data.get("generator")
    if not rows:
        return None
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.4, 4.0))

    levels = [r["level"] for r in rows]
    clues = [r["clues"]["mean"] for r in rows]
    ax1.bar(levels, clues, 0.55, color=SMART)
    for i, r in enumerate(rows):
        ax1.text(i, r["clues"]["mean"] + 0.8, f"{r['clues']['mean']:.0f}",
                 ha="center", fontsize=9, color=INK)
    ax1.set_ylabel("clues (givens)", fontsize=9, color=INK)
    ax1.set_title("Clue count separates the levels cleanly",
                  fontsize=10, color=INK, pad=8)
    ax1.set_ylim(0, max(clues) * 1.25)
    style(ax1)

    zero = [r["zero_backtrack_count"] / r["n"] * 100 for r in rows]
    med = [r["backtracks"]["median"] for r in rows]
    mx = [r["backtracks"]["max"] for r in rows]
    ax2.bar(levels, zero, 0.55, color="#68a3d8", label="% needing zero backtracking")
    ax2.set_ylabel("% of puzzles solved with no search", fontsize=9, color=INK)
    ax2.set_ylim(0, 118)
    for i, r in enumerate(rows):
        ax2.text(i, zero[i] + 3,
                 f"{r['zero_backtrack_count']}/{r['n']}", ha="center",
                 fontsize=9, color=INK)
    ax2.set_xticks(list(range(len(rows))))
    ax2.set_xticklabels(
        [f"{r['level']}\nmedian {med[i]:,.0f} · max {mx[i]:,.0f}"
         for i, r in enumerate(rows)], fontsize=8.5)
    ax2.set_title("But solver effort overlaps: difficulty is only a proxy",
                  fontsize=10, color=INK, pad=8)
    style(ax2)

    n = rows[0]["n"]
    fig.suptitle(f"Generator calibration: {n} puzzles per level, seeds 0-{n-1}",
                 fontsize=11, color=INK, y=1.0)
    fig.tight_layout()
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)
    return path


# --------------------------------------------------------------------------- #
# Figure 4 -- solve rate and effort across the public benchmark sets
# --------------------------------------------------------------------------- #
def fig_datasets(data, path="results/fig4_datasets.png"):
    rows = data.get("datasets")
    if not rows:
        return None
    rows = sorted(rows, key=lambda r: r["backtracks"]["mean"])
    names = [f"{r['dataset']}\nn={r['n_solved_attempted']:,}" for r in rows]
    med = [r["backtracks"]["median"] for r in rows]
    p95 = [r["backtracks"]["p95"] for r in rows]
    mx = [r["backtracks"]["max"] for r in rows]
    x = range(len(rows))

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8.6, 6.6),
                                   gridspec_kw={"height_ratios": [1, 1.25]})

    rate = [r["solve_rate"] * 100 for r in rows]
    ax1.bar(list(x), rate, 0.55, color=SMART)
    for i, v in enumerate(rate):
        ax1.text(i, v + 1.5, f"{v:.1f}%", ha="center", fontsize=9, color=INK)
    ax1.set_ylim(0, 118)
    ax1.set_ylabel("solve rate (%)", fontsize=9, color=INK)
    ax1.set_xticks(list(x))
    ax1.set_xticklabels([r["dataset"] for r in rows], fontsize=9)
    ax1.set_title("Every puzzle in every benchmark set is solved and verified",
                  fontsize=10, color=INK, pad=8)
    style(ax1)

    w = 0.26
    ax2.bar([i - w for i in x], med, w, label="median", color="#90cdf4")
    ax2.bar(list(x), p95, w, label="95th percentile", color=SMART)
    ax2.bar([i + w for i in x], mx, w, label="worst case", color="#2c5282")
    ax2.set_yscale("symlog", linthresh=1)
    ax2.set_ylabel("backtracks (symlog)", fontsize=9, color=INK)
    ax2.set_xticks(list(x))
    ax2.set_xticklabels(names, fontsize=8.5)
    for i, r in enumerate(rows):
        if r["backtracks"]["max"] == 0:
            ax2.text(i, 0.6, "0 backtracks —\nno search at all", ha="center",
                     va="bottom", fontsize=7.5, color=MUTED)
    ax2.set_ylim(bottom=-0.5)
    ax2.set_title("Search effort spans six orders of magnitude across the sets",
                  fontsize=10, color=INK, pad=8)
    ax2.legend(frameon=False, fontsize=8.5, ncol=3, loc="upper left")
    style(ax2)

    fig.tight_layout()
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)
    return path


# --------------------------------------------------------------------------- #
# Figure 5 -- search effort as a function of clue count
# --------------------------------------------------------------------------- #
def fig_scaling(data, path="results/fig5_scaling.png"):
    rows = [r for r in data.get("scaling", []) if r.get("n", 0) >= 5]
    if not rows:
        return None
    clues = [r["clues"] for r in rows]
    med = [r["median"] for r in rows]
    mean = [r["mean"] for r in rows]
    p95 = [r["p95"] for r in rows]

    # The benchmark sets contain no puzzles in some clue-count ranges. Break the
    # series at those gaps rather than interpolating a line across missing data.
    segments, cur = [], [0]
    for k in range(1, len(clues)):
        if clues[k] - clues[k - 1] > 1:
            segments.append(cur)
            cur = [k]
        else:
            cur.append(k)
    segments.append(cur)

    fig, ax = plt.subplots(figsize=(7.9, 4.3))
    for gi, seg in enumerate(segments):
        cs = [clues[i] for i in seg]
        ax.fill_between(cs, [med[i] for i in seg], [p95[i] for i in seg],
                        color="#bee3f8", alpha=0.75,
                        label="median to 95th percentile" if gi == 0 else None)
        ax.plot(cs, [mean[i] for i in seg], color=NAIVE, linewidth=1.8,
                marker="o", markersize=3.5, label="mean" if gi == 0 else None)
        ax.plot(cs, [med[i] for i in seg], color=SMART, linewidth=1.8,
                marker="o", markersize=3.5, label="median" if gi == 0 else None)
    for a, b in zip(segments, segments[1:]):
        lo, hi = clues[a[-1]], clues[b[0]]
        ax.axvspan(lo, hi, color="#f7fafc", zorder=0)
        ax.text((lo + hi) / 2, 0.35, "fewer than 5\npuzzles here", ha="center",
                va="bottom", fontsize=7.5, color=MUTED)
    ax.set_yscale("symlog", linthresh=1)
    ax.set_xlabel("clues given", fontsize=9, color=INK)
    ax.set_ylabel("backtracks (symlog)", fontsize=9, color=INK)
    ax.set_title("Fewer clues means more search — but the spread at any clue count\n"
                 "rivals the trend, which is why clue count is a weak difficulty "
                 "measure", fontsize=10, color=INK, pad=10)
    ax.set_ylim(bottom=-0.4)
    ax.legend(frameon=False, fontsize=9)
    style(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)
    return path


# --------------------------------------------------------------------------- #
# Figure 6 -- the cost/benefit crossover of stronger propagation
# --------------------------------------------------------------------------- #
def fig_crossover(data, path="results/fig6_crossover.png"):
    rows = data.get("solvers")
    if not rows:
        return None
    rows = sorted(rows, key=lambda r: r["node_reduction"])
    names = [r["dataset"] for r in rows]
    x = range(len(rows))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.6, 4.4))

    red = [r["node_reduction"] for r in rows]
    ax1.barh(list(x), red, 0.6, color=SMART)
    ax1.set_yticks(list(x))
    ax1.set_yticklabels(names, fontsize=9)
    ax1.set_xscale("log")
    ax1.set_xlabel("times fewer search nodes (log scale)", fontsize=9, color=INK)
    for i, v in enumerate(red):
        ax1.text(v * 1.15, i, f"{v:,.0f}x", va="center", fontsize=8.5, color=INK)
    ax1.set_xlim(1, max(red) * 6)
    ax1.set_title("Hidden singles always cut the search",
                  fontsize=10, color=INK, pad=8)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.grid(axis="x", color="#e2e8f0", linewidth=0.8)
    ax1.set_axisbelow(True)
    ax1.tick_params(colors=INK, labelsize=9)

    ratio = [r["time_ratio"] for r in rows]
    colors = [NAIVE if v > 1 else SMART for v in ratio]
    ax2.barh(list(x), ratio, 0.6, color=colors)
    ax2.axvline(1.0, color=INK, linewidth=1.2, linestyle="--")
    ax2.text(1.02, len(rows) - 0.35, "break-even", fontsize=8, color=INK)
    ax2.set_yticks(list(x))
    ax2.set_yticklabels(names, fontsize=9)
    ax2.set_xscale("log")
    ax2.set_xlabel("wall-clock time, strong / FC+MRV  (<1 is faster)",
                   fontsize=9, color=INK)
    for i, v in enumerate(ratio):
        ax2.text(v * 1.2, i, f"{v:.2f}x", va="center", ha="left",
                 fontsize=8.5, color=INK)
    ax2.set_xlim(min(ratio) * 0.6, max(ratio) * 4.5)
    ax2.set_title("But it only pays off where search was the bottleneck",
                  fontsize=10, color=INK, pad=8)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.grid(axis="x", color="#e2e8f0", linewidth=0.8)
    ax2.set_axisbelow(True)
    ax2.tick_params(colors=INK, labelsize=9)

    fig.suptitle("Stronger propagation: node savings are universal, time savings are not",
                 fontsize=11, color=INK, y=1.0)
    fig.tight_layout()
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)
    return path


def main():
    os.makedirs(OUT, exist_ok=True)
    data = load()
    made = [
        fig_peers(),
        fig_presets(data),
        fig_generator(data),
        fig_datasets(data),
        fig_scaling(data),
        fig_crossover(data),
    ]
    for p in made:
        if p:
            print(f"  wrote {p}")
        else:
            print("  (skipped a figure: matching experiment not in results.json)")


if __name__ == "__main__":
    main()
