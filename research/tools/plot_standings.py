"""Two figures for a model card: where Jiangbanya stands per tier among entries that report
runtime (dot plot), and how each tier's checker aggregate moved from v1 to v5.

Aggregates are checker numbers (geometric mean over a tier's cases of baseline / delay):
ours from research/models/*/README.md, the others from the upstream leaderboard.

Usage (from repo root):
  python3 research/tools/plot_standings.py --out research/models/jiangbanya_v5
"""
import argparse
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e4e3df"
OURS = "#2a78d6"
SERIES = {"hard": "#2a78d6", "congested": "#eb6834", "designs": "#1baf7a"}

# entries that report runtime (upstream leaderboard 2026-10-08) plus Jiangbanya v5
STANDINGS = pd.DataFrame([
    ("hard", "Jiangbanya", 1.3786), ("hard", "iamparv7043", 1.3019), ("hard", "ly", 1.1500),
    ("hard", "negotiated_delay", 1.1499),
    ("congested", "Jiangbanya", 1.3189), ("congested", "pathfinder_lns", 1.3111),
    ("congested", "warm_lns_refinement", 1.3085), ("congested", "iamparv7043", 1.1252),
    ("designs", "pathfinder_lns", 1.4354), ("designs", "warm_lns_refinement", 1.43314),
    ("designs", "Jiangbanya", 1.43306), ("designs", "iamparv7043", 1.3276),
    ("intro", "pathfinder_lns", 1.1514), ("intro", "Jiangbanya", 1.1406), ("intro", "iamparv7043", 1.1254),
    ("intro", "negotiated_delay", 1.0906),
    ("scale", "pathfinder_lns", 1.1277), ("scale", "warm_lns_refinement", 1.1274), ("scale", "Jiangbanya", 1.1152),
    ("scale", "iamparv7043", 1.1010),
    ("stress", "pathfinder_lns", 1.0914), ("stress", "warm_lns_refinement", 1.0911), ("stress", "Jiangbanya", 1.0798),
], columns=["tier", "entry", "score"])
BEST_OVERALL = {"hard": 1.4136, "congested": 1.3508, "designs": 1.4673, "intro": 1.1566, "scale": 1.1399,
                "stress": 1.0984}
PROGRESS = pd.DataFrame({
    "version": ["v1", "v2", "v3", "v4", "v5"],
    "hard": [1.3303, 1.3368, 1.3471, 1.3786, 1.3786],
    "congested": [1.2367, 1.2490, 1.2644, 1.3034, 1.3189],
    "designs": [1.3685, 1.3744, 1.3853, 1.4150, 1.4331],
})
RIVAL = {"hard": ("iamparv7043", 1.3019), "congested": ("pathfinder_lns", 1.3111),
         "designs": ("pathfinder_lns", 1.4354)}


def style(ax):
    ax.set_facecolor(SURFACE)
    for s in ["top", "right", "left"]:
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=8)
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)


def standings(out):
    tiers = ["hard", "congested", "designs", "intro", "scale", "stress"]
    fig, axes = plt.subplots(2, 3, figsize=(12, 6.2), facecolor=SURFACE)
    for ax, tier in zip(axes.ravel(), tiers):
        d = STANDINGS[STANDINGS.tier == tier].sort_values("score", ascending=False).reset_index(drop=True)
        style(ax)
        y = range(len(d))[::-1]
        for yi, (_, r) in zip(y, d.iterrows()):
            ours = r.entry == "Jiangbanya"
            ax.plot(r.score, yi, "o", ms=9 if ours else 7, color=OURS if ours else MUTED, zorder=3,
                    markeredgecolor=SURFACE, markeredgewidth=2)
            ax.text(r.score, yi + 0.32, f"{r.entry}  {r.score:.4f}", ha="center", va="bottom", fontsize=7.5,
                    color=INK if ours else INK2, fontweight="bold" if ours else "normal")
        rank = int(d.index[d.entry == "Jiangbanya"][0]) + 1
        ax.axvline(BEST_OVERALL[tier], color=MUTED, lw=1, ls="--", zorder=1)
        ax.text(BEST_OVERALL[tier], -0.85, "best overall\n(no runtime)", ha="center", va="top", fontsize=6.5,
                color=MUTED)
        lo = min(d.score.min(), BEST_OVERALL[tier])
        hi = max(d.score.max(), BEST_OVERALL[tier])
        pad = (hi - lo) * 0.18 + 0.002
        ax.set_xlim(lo - pad, hi + pad)
        ax.set_ylim(-1.6, len(d) - 0.2)
        ax.set_yticks([])
        ax.set_title(f"{tier}: #{rank} of entries with runtime", fontsize=10, color=INK, loc="left")
    fig.suptitle("Jiangbanya v5 (blue) among entries that report runtime; checker aggregate, higher is better",
                 fontsize=11, color=INK, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    path = os.path.join(out, "standings_v5.png")
    fig.savefig(path, dpi=130, facecolor=SURFACE)
    print("wrote", path)


def progress(out):
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6), facecolor=SURFACE)
    for ax, tier in zip(axes, ["hard", "congested", "designs"]):
        style(ax)
        ax.grid(axis="y", color=GRID, lw=0.8)
        x = range(len(PROGRESS))
        ax.plot(x, PROGRESS[tier], color=SERIES[tier], lw=2, marker="o", ms=8, markeredgecolor=SURFACE,
                markeredgewidth=2, zorder=3)
        for xi, v in zip(x, PROGRESS[tier]):
            ax.text(xi, v + 0.003, f"{v:.4f}", ha="center", va="bottom", fontsize=7.5, color=INK2)
        name, val = RIVAL[tier]
        ax.axhline(val, color=MUTED, lw=1, ls="--", zorder=1)
        below = val < PROGRESS[tier].min()
        ax.text(-0.1, val + (-0.0015 if below else 0.0015), f"{name} {val:.4f}", ha="left",
                va="top" if below else "bottom", fontsize=7.5, color=MUTED)
        ax.set_xticks(list(x), PROGRESS["version"])
        lo, hi = min(PROGRESS[tier].min(), val), max(PROGRESS[tier].max(), val)
        ax.set_ylim(lo - 0.008, hi + 0.012)
        ax.set_title(tier, fontsize=10, color=INK, loc="left")
    fig.suptitle("Checker aggregate per version (dashed: best other entry that reports runtime)", fontsize=11,
                 color=INK, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    path = os.path.join(out, "progress_v1_v5.png")
    fig.savefig(path, dpi=130, facecolor=SURFACE)
    print("wrote", path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    standings(args.out)
    progress(args.out)


if __name__ == "__main__":
    main()
