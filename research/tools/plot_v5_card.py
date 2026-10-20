"""Explanatory figures for the Jiangbanya v5 model card (research/models/jiangbanya_v5/).

  v5_problem.png    the layer stack and how full each layer is in v5's routes
  v5_gap.png        where v5 still loses delay (excess over the congestion-free ideal, by cause)
  v5_who_pays.png   which sinks carry that excess (single-sink nets give up the middle layers)
  v5_pipeline.png   the router's stages and the search loop, with main.cpp line numbers
  v5_schedule.png   one run over time: delay (top) and the acceptance threshold and thread
                    syncs (bottom), from the 300 s demonstration run behind the search GIF
  v5_levers.png     measured effect of each v5 ingredient (checker numbers, experiment ids)
  v5_per_case.png   v5 vs v4 per case on congested and designs against the extra time used

Numbers: gap and layer use from `gap_decompose.py --run research/runs/v5-all` (the six-tier
submission routes) and `--best-public`; per-case delays from m3d.checker on the v4 and v5
submission routes; lever effects from research/state/experiments.jsonl and findings.md.

Usage (from repo root):
  python3 research/tools/plot_v5_card.py --out research/models/jiangbanya_v5 \
      --frames research/runs/anim-v5-congested01/frames.csv
"""
import argparse
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e4e3df"
BLUE, ORANGE, AQUA, RED = "#2a78d6", "#eb6834", "#1baf7a", "#e34948"
TIERS = ["hard", "congested", "designs"]

# grid points used per layer z = 0..5, % (gap_decompose.py --run research/runs/v5-all)
LAYER_USE = pd.DataFrame({
    "hard": [23.9, 46.7, 87.8, 88.5, 47.2, 21.8],
    "congested": [10.4, 34.6, 86.2, 84.9, 34.1, 9.1],
    "designs": [8.3, 39.2, 79.2, 79.3, 36.8, 7.6],
})
# excess over the congestion-free ideal, as % of the ideal, split by cause
GAP = pd.DataFrame([
    ("hard", "Jiangbanya v5", 114031, 22042, 8124, 1860),
    ("hard", "best public mix", 114031, 20302, 6396, 1578),
    ("congested", "Jiangbanya v5", 389539, 64048, 21324, 13404),
    ("congested", "best public mix", 389539, 54698, 21044, 10950),
    ("designs", "Jiangbanya v5", 164853, 36788, 3524, 4602),
    ("designs", "best public mix", 164853, 31498, 3700, 4446),
], columns=["tier", "who", "ideal", "layer", "detour", "via"])
LB_HARD = 123656.0  # sum over hard cases of the toll lower bound (reference_points.csv lb_best)
# share of sinks and of excess by sinks per net (v5 routes)
WHO_PAYS = pd.DataFrame([
    ("hard", "1", 25.4, 43.7, 65.7), ("hard", "2", 8.0, 10.3, 39.6), ("hard", "3-4", 24.3, 22.3, 25.1),
    ("hard", "5-8", 42.4, 23.8, 13.6),
    ("congested", "1", 26.3, 50.4, 70.2), ("congested", "2", 8.1, 10.8, 36.9),
    ("congested", "3-4", 22.1, 17.1, 20.1), ("congested", "5-8", 43.5, 21.6, 10.4),
    ("designs", "1", 40.1, 63.5, 44.9), ("designs", "2", 18.8, 18.6, 28.1), ("designs", "3-4", 14.6, 9.7, 18.7),
    ("designs", "5-8", 1.9, 0.6, 9.0), ("designs", "9+", 24.6, 7.7, 7.6),
], columns=["tier", "sinks_per_net", "share_sinks", "share_excess", "over_ideal"])
# measured effect of each ingredient: r = 100 x log(before delay / after delay), checker numbers
LEVERS = pd.DataFrame([
    ("Threshold 16 + bandit vs v3", "hard case_01/05/09, 1 thread, 60 and 600 s", "exp-028", 1.3),
    ("Sync threads every 60 s, not 10 s", "hard, congested, 4 threads", "exp-033", 0.28),
    ("Integer goal-directed negotiation (S1)", "designs, 4 threads, 1,800 s", "exp-038", 0.64),
    ("Integer goal-directed negotiation (S1)", "congested, 4 threads, 1,800 s", "exp-038", -0.18),
    ("Sync every 600 s with S1", "designs, 4 threads", "exp-044", 0.46),
    ("Double the time", "hard, congested, designs (mean per doubling)", "findings 10-19", 0.46),
    ("v5 long run vs v4", "designs, 3,600 vs 1,800 s per case", "exp-045", 1.27),
    ("v5 long run vs v4", "congested, 28,800 s split vs 1,800 s per case", "exp-046", 1.18),
], columns=["lever", "condition", "source", "r"])
PER_CASE = pd.DataFrame([
    ("congested", "case_01", 166, 53517, 53319, 1799.0, 4838.0),
    ("congested", "case_02", 229, 95382, 94828, 1799.1, 6674.4),
    ("congested", "case_03", 291, 166519, 163731, 1799.1, 8481.8),
    ("congested", "case_04", 302, 180163, 176437, 1799.2, 8802.4),
    ("designs", "ctrl", 182, 50434, 49652, 1799.1, 3599.0),
    ("designs", "int2float", 271, 92280, 91050, 1799.0, 3599.0),
    ("designs", "router", 344, 69683, 69065, 1799.1, 3599.0),
], columns=["tier", "case", "nets", "v4", "v5", "t4", "t5"])


def style(ax, grid_axis="x"):
    ax.set_facecolor(SURFACE)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    for s in ["left", "bottom"]:
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=8)
    if grid_axis:
        ax.grid(axis=grid_axis, color=GRID, lw=0.8)
    ax.set_axisbelow(True)


def save(fig, out, name):
    path = os.path.join(out, name)
    fig.savefig(path, dpi=130, facecolor=SURFACE)
    plt.close(fig)
    print("wrote", path)


def problem(out):
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.0), facecolor=SURFACE, gridspec_kw={"width_ratios": [1, 1.35]})
    a.set_facecolor(SURFACE)
    a.axis("off")
    step = [6, 4, 2, 2, 4, 6]
    color = [ORANGE, AQUA, BLUE, BLUE, AQUA, ORANGE]
    for z in range(6):
        y = z * 0.8
        a.add_patch(FancyBboxPatch((0.15, y + 0.12), 0.55, 0.5, boxstyle="round,pad=0,rounding_size=0.05",
                                   facecolor=color[z], edgecolor="none", alpha=0.9))
        a.text(0.425, y + 0.37, f"z = {z}", ha="center", va="center", fontsize=9, color="white", weight="bold")
        a.text(0.78, y + 0.37, f"{step[z]} per step", ha="left", va="center", fontsize=9, color=INK)
    a.text(0.425, -0.25, "die A (pins)", ha="center", fontsize=8.5, color=INK2)
    a.text(0.425, 4.95, "die B (pins)", ha="center", fontsize=8.5, color=INK2)
    a.annotate("", xy=(0.08, 0.37), xytext=(0.08, 1.17), arrowprops=dict(arrowstyle="<->", color=INK2, lw=1))
    a.text(0.04, 0.77, "layer change\n3", ha="right", va="center", fontsize=8, color=INK2)
    a.set_xlim(-0.35, 1.4)
    a.set_ylim(-0.5, 5.2)
    a.set_title("Six layers between two dies: the middle two are 3x\ncheaper than the outer two",
                fontsize=10, color=INK, loc="left")
    style(b, "y")
    x = np.arange(6)
    w = 0.26
    for i, (tier, c) in enumerate(zip(TIERS, [BLUE, ORANGE, AQUA])):
        b.bar(x + (i - 1) * w, LAYER_USE[tier], width=w - 0.03, color=c, label=tier)
    b.set_xticks(x, [f"z = {z}\n({s}/step)" for z, s in enumerate(step)])
    b.set_ylabel("grid points in use, %", fontsize=9, color=INK2)
    b.set_ylim(0, 100)
    b.legend(frameon=False, fontsize=8, labelcolor=INK2, loc="upper left")
    b.text(2.5, 95, "middle layers 79-89% full", ha="center", fontsize=8.5, color=INK)
    b.set_title("v5 routes: the cheap layers are nearly full; who gets them is the problem",
                fontsize=10, color=INK, loc="left")
    fig.tight_layout()
    save(fig, out, "v5_problem.png")


def gap(out):
    d = GAP.copy()
    for c in ["layer", "detour", "via"]:
        d[c] = 100 * d[c] / d["ideal"]
    fig, ax = plt.subplots(figsize=(10, 4.4), facecolor=SURFACE)
    style(ax)
    labels, y = [], []
    for i, (_, r) in enumerate(d.iterrows()):
        yi = len(d) - 1 - i + (i // 2) * -0.5
        left = 0.0
        for c, col in [("layer", ORANGE), ("detour", AQUA), ("via", MUTED)]:
            ax.barh(yi, r[c], left=left, color=col, height=0.62, edgecolor=SURFACE, linewidth=2,
                    label=c if i == 0 else None)
            left += r[c]
        ax.text(left + 0.4, yi, f"{left:.1f}%", va="center", fontsize=8.5,
                color=INK if r.who.startswith("Jiang") else INK2, weight="bold" if r.who.startswith("Jiang") else None)
        labels.append(f"{r.tier}: {r.who}")
        y.append(yi)
    yh = y[0] + 0.5
    lb = 100 * (LB_HARD / 114031 - 1)
    ax.plot([lb, lb], [y[1] - 0.4, y[0] + 0.4], color=INK, lw=1.2, ls="--")
    ax.text(lb, yh, f"hard: toll lower bound {lb:.1f}%", ha="center", va="bottom", fontsize=8, color=INK)
    ax.set_yticks(y, labels)
    ax.set_xlabel("excess delay over the congestion-free ideal, % of the ideal", fontsize=9, color=INK2)
    ax.set_xlim(0, 32)
    ax.legend(frameon=False, fontsize=8.5, labelcolor=INK2, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.2))
    ax.set_title("Where v5 still loses delay: mostly sinks pushed off the fast layers", fontsize=10, color=INK,
                 loc="left")
    fig.text(0.01, 0.02, "layer = steps on slower layers than the ideal path; detour = extra steps beyond the shortest "
             "distance; via = extra layer changes.\nbest public mix = the best route per case over every public entry "
             "(with or without runtime).", fontsize=7.5, color=INK2)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    save(fig, out, "v5_gap.png")


def who_pays(out):
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.4), facecolor=SURFACE, sharey=True)
    for ax, tier in zip(axes, TIERS):
        d = WHO_PAYS[WHO_PAYS.tier == tier]
        style(ax, "y")
        x = np.arange(len(d))
        ax.bar(x - 0.19, d.share_sinks, width=0.36, color=MUTED, label="share of sinks")
        ax.bar(x + 0.19, d.share_excess, width=0.36, color=ORANGE, label="share of excess delay")
        ax.set_xticks(x, d.sinks_per_net)
        ax.set_xlabel("sinks per net", fontsize=9, color=INK2)
        ax.set_title(tier, fontsize=10, color=INK, loc="left")
        top = d.iloc[0]
        ax.text(0.19, top.share_excess + 1.5, f"{top.share_excess:.0f}%", ha="center", fontsize=8.5, color=INK)
    axes[0].set_ylabel("%", fontsize=9, color=INK2)
    axes[0].legend(frameon=False, fontsize=8, labelcolor=INK2, loc="upper right")
    fig.suptitle("Single-sink nets carry 44-64% of the excess: one fast trunk serves many sinks of a big net, "
                 "so the search gives the cheap layers to big nets", fontsize=10, color=INK, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    save(fig, out, "v5_who_pays.png")


def box(ax, x, y, w, h, title, body, color, ref):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                facecolor=SURFACE, edgecolor=color, linewidth=2))
    ax.add_patch(FancyBboxPatch((x, y + h - 0.05), w, 0.05, boxstyle="square,pad=0", facecolor=color,
                                edgecolor="none"))
    ax.text(x + 0.1, y + h - 0.2, title, fontsize=9.5, weight="bold", color=INK, va="top")
    ax.text(x + 0.1, y + h - 0.55, body, fontsize=8, color=INK2, va="top", linespacing=1.35)
    ax.text(x + w - 0.08, y + 0.1, ref, fontsize=7.5, color=MUTED, ha="right", va="bottom", family="monospace")


def arrow(ax, a, b, text=None, rad=0.0):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=12, color=INK2, lw=1.2,
                                 connectionstyle=f"arc3,rad={rad}"))
    if text:
        ax.text((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + 0.12, text, fontsize=7.5, color=INK2, ha="center")


def pipeline(out):
    fig, ax = plt.subplots(figsize=(13, 8.6), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    ax.axis("off")
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 8.6)
    top = 6.75
    box(ax, 0.2, top, 2.6, 1.6, "Input", "instance JSON only\n(grid, layer delays,\nnets: driver + sinks)", MUTED,
        "main() :1668")
    box(ax, 3.3, top, 3.0, 1.6, "A1  Negotiate (PathFinder)",
        "route every net; points used\nby 2+ nets get rising penalties;\nrepeat until none is shared",
        RED, "negotiate() :310")
    box(ax, 6.8, top, 2.9, 1.6, "A2  Exact reroute",
        "rip one net, route its true\nshortest-path tree around the\nothers; sweep until no gain", AQUA,
        "refine() :369")
    box(ax, 10.2, top, 2.6, 1.6, "Output",
        "best solution seen;\nwritten before the\ndeadline margin", MUTED, "write() :983")
    arrow(ax, (2.85, top + 0.8), (3.25, top + 0.8))
    arrow(ax, (6.35, top + 0.8), (6.75, top + 0.8), "legal")
    arrow(ax, (8.25, top - 0.05), (8.25, 6.45))
    arrow(ax, (12.2, 6.45), (12.2, top - 0.05))
    ax.text(12.3, 6.5, "deadline", fontsize=7.5, color=INK2)
    # search loop
    ax.add_patch(FancyBboxPatch((0.2, 1.95), 12.6, 4.45, boxstyle="round,pad=0.02,rounding_size=0.12",
                                facecolor="#f4f3f0", edgecolor=GRID, linewidth=1))
    ax.text(0.4, 6.1, "B  Neighborhood search: one move = rip up a group of nets and reroute them together "
            "(lns_run() :442)", fontsize=10, weight="bold", color=INK)
    by = 3.85
    box(ax, 0.5, by, 2.7, 1.95, "1  Pick a target",
        "net chosen in proportion to its\nexcess over its ideal delay;\nbandit picks the move type\n"
        "(5 arms, Thompson sampling)", BLUE, ":468-491")
    box(ax, 3.6, by, 2.7, 1.95, "2  Build the group",
        "target + up to 5 nets on its\nideal tree, or in a window\naround it; then rip all of\nthem up",
        BLUE, ":530-558")
    box(ax, 6.7, by, 2.9, 1.95, "3  Repair the group",
        "PathFinder among the group\n(<= 6 rounds, others fixed);\nS1: integer, goal-directed\nbucket-queue searches",
        RED, "group_negotiate() :942\nroute_neg_int() :1520")
    box(ax, 10.0, by, 2.6, 1.95, "4  Place exactly",
        "each net's exact shortest-\npath tree; random among\nequal-delay routes", AQUA,
        "route_exact() :1199\nbuild_tree_rand() :1289")
    box(ax, 0.5, 2.15, 12.1, 1.3, "5  Accept or undo",
        "keep the move if the group's delay rises by at most the threshold (32 falling linearly to 0 over the run; "
        "8 on designs), else restore the old trees.\nEvery 300 moves without a gain: a bigger kick group. "
        "2,000 moves without a new best: return to the best solution.", ORANGE,
        ":619-685   ta_threshold() :810")
    arrow(ax, (3.25, by + 1.0), (3.55, by + 1.0))
    arrow(ax, (6.35, by + 1.0), (6.65, by + 1.0))
    arrow(ax, (9.65, by + 1.0), (9.95, by + 1.0))
    arrow(ax, (11.3, by - 0.05), (11.3, 3.5))
    arrow(ax, (1.85, 3.5), (1.85, by - 0.05))
    ax.text(1.95, 3.62, "next move", fontsize=7.5, color=INK2)
    box(ax, 0.2, 0.15, 12.6, 1.45, "Around the loop: 4 threads (parallel_lns() :1619)",
        "4 copies of the router search from the same solution with different seeds. At each sync (every fifth of "
        "the run on hard and congested,\n600 s on designs, 120 s on intro, scale and stress) all adopt the best one; "
        "between syncs each walk explores on its own.", MUTED, "adopt() :866")
    fig.suptitle("How the Jiangbanya router works (router/src/main.cpp, one file; line numbers at commit 94e4fbc)",
                 fontsize=11, color=INK, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    save(fig, out, "v5_pipeline.png")


def schedule(out, frames_csv):
    f = pd.read_csv(frames_csv)
    T = 300.0
    fig, (a, b) = plt.subplots(2, 1, figsize=(10, 5.6), facecolor=SURFACE, sharex=True,
                               gridspec_kw={"height_ratios": [2.2, 1]})
    style(a, "y")
    neg = f[~f.legal]
    leg = f[f.legal]
    a.plot(neg.t, neg.delay, color=RED, lw=2, ls=(0, (2, 1.5)), label="negotiating (routes still overlap)")
    a.plot(leg.t, leg.delay, color=BLUE, lw=2, label="legal: exact reroutes, then neighborhood search")
    a.axhline(52233, color=MUTED, lw=1, ls=(0, (1, 2)))
    a.text(T, 52233, " best public entry 52,233", va="center", fontsize=8, color=INK2)
    a.axhline(71049, color=MUTED, lw=1, ls=(0, (1, 2)))
    a.text(T, 71049, " reference router 71,049", va="center", fontsize=8, color=INK2)
    first = leg.iloc[0]
    a.annotate(f"first legal routing\n{first.t:.0f} s, {first.delay:,.0f}", (first.t, first.delay),
               xytext=(first.t + 25, first.delay + 4500), fontsize=8, color=INK,
               arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
    last = f.iloc[-1]
    a.text(last.t, last.delay - 900, f"{last.delay:,.0f}", ha="right", va="top", fontsize=8.5, color=INK, weight="bold")
    a.set_ylabel("total sink delay", fontsize=9, color=INK2)
    a.legend(frameon=False, fontsize=8, labelcolor=INK2, loc="upper right", bbox_to_anchor=(1.0, 0.86))
    share = 100 * (T - first.t) / T
    a.set_title(f"One congested case_01 run (300 s demo, congested settings): {share:.0f}% of the time goes to "
                "improving a legal routing", fontsize=10, color=INK, loc="left")
    style(b, "y")
    end = T - min(1.0, 0.03 * T + 0.05)  # the router's deadline (time limit minus its safety margin)
    t_lns = float(f[f.phase == "search"].t.min())  # neighborhood search starts after the exact sweeps
    tt = np.linspace(t_lns, end, 200)
    b.plot(tt, 32 * (1 - (tt - t_lns) / (end - t_lns)), color=ORANGE, lw=2)
    for k in range(1, 5):
        b.axvline(t_lns + k * 0.2 * end, color=MUTED, lw=1, ls="--")
    b.text(t_lns + 0.2 * end + 3, 31, "threads adopt the best\n(every fifth of the run)", fontsize=7.5, color=INK2,
           va="top")
    b.text(t_lns + 2 * 0.2 * end + 3, 6, "accept a move that costs at most\nthis much extra delay", fontsize=7.5,
           color=INK2)
    b.set_ylabel("threshold", fontsize=9, color=INK2)
    b.set_xlabel("seconds since start", fontsize=9, color=INK2)
    b.set_ylim(0, 34)
    b.set_xlim(0, T * 1.18)
    fig.tight_layout()
    save(fig, out, "v5_schedule.png")


def levers(out):
    d = LEVERS.iloc[::-1].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(10, 4.2), facecolor=SURFACE)
    style(ax)
    for i, r in d.iterrows():
        col = BLUE if r.r > 0 else RED
        ax.plot([0, r.r], [i, i], color=col, lw=2, solid_capstyle="round")
        ax.plot(r.r, i, "o", ms=8, color=col, markeredgecolor=SURFACE, markeredgewidth=2, zorder=3)
        ax.text(max(r.r, 0) + 0.05, i, f"{r.r:+.2f}%  ({r.source})", va="center", fontsize=8, color=INK2)
    ax.axvline(0, color=INK2, lw=0.8)
    ax.set_yticks(range(len(d)), [f"{r.lever}\n{r.condition}" for _, r in d.iterrows()], fontsize=7.5)
    ax.set_xlim(-0.5, 2.0)
    ax.set_xlabel("r = 100 x log(delay before / delay after); > 0 = better (checker numbers)", fontsize=9, color=INK2)
    ax.set_title("What each v5 ingredient bought, measured at the settings it runs with", fontsize=10, color=INK,
                 loc="left")
    fig.tight_layout()
    save(fig, out, "v5_levers.png")


def per_case(out):
    d = PER_CASE.copy()
    d["r"] = 100 * np.log(d.v4 / d.v5)
    d["x"] = d.t5 / d.t4
    fig, ax = plt.subplots(figsize=(8, 4.2), facecolor=SURFACE)
    style(ax, "both")
    for tier, col in [("congested", ORANGE), ("designs", AQUA)]:
        s = d[d.tier == tier]
        ax.plot(s.x, s.r, "o", ms=9, color=col, markeredgecolor=SURFACE, markeredgewidth=2, label=tier, zorder=3)
        for _, r in s.iterrows():
            ax.text(r.x + 0.08, r.r, f"{r.case} ({r.nets} nets) {r.r:+.2f}%", va="center", fontsize=8, color=INK2)
    ax.set_xlim(1.5, 6.6)
    ax.set_ylim(0, 2.4)
    ax.set_xlabel("v5 time / v4 time for the case (v4: 1,800 s per case)", fontsize=9, color=INK2)
    ax.set_ylabel("v5 gain over v4, r %", fontsize=9, color=INK2)
    ax.legend(frameon=False, fontsize=8.5, labelcolor=INK2, loc="upper left")
    ax.set_title("Every case improved; the big congested cases got the most time and gained most", fontsize=10,
                 color=INK, loc="left")
    fig.tight_layout()
    save(fig, out, "v5_per_case.png")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--frames", required=True, help="frames.csv written by animate_run.py")
    args = ap.parse_args()
    problem(args.out)
    gap(args.out)
    who_pays(args.out)
    pipeline(args.out)
    schedule(args.out, args.frames)
    levers(args.out)
    per_case(args.out)


if __name__ == "__main__":
    main()
