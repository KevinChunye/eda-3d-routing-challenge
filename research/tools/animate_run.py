"""Animate one router run from its snapshots (router flag --set snap_dir=DIR).

Every frame is one snapshot. Delay of a legal snapshot comes from m3d.checker; while the
routing is still illegal (nets share grid points) the delay shown is the router's own sum and
the shared points are drawn as red rings.

Left panel: the routing seen from above. Wires are colored by layer class: the two fast
middle layers (step delay 2), the two layers next to them (4), the two outer layers next to
the dies (6). Right panel: total delay over time (log time axis) against the reference
router (the baseline), the best public entry, the best lower bound and the congestion-free
ideal.

Usage (from repo root):
  router/build/m3d_route --instance benchmarks_hard/case_01.json --out D/final.sol.json \
      --time-limit 60 --seed 1 <flags> --set snap_dir=D --set snap_neg=10 --set snap_s=2
  python3 research/tools/animate_run.py --dir D --tier hard --case case_01 --out D/run.gif
"""
import argparse
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

from common import STATE, instance_path  # noqa: E402
from m3d.anim import _fig_to_pil, _save_gif  # noqa: E402
from m3d.checker import check  # noqa: E402
from m3d.model import Instance, Submission  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#8a8984"
GRID = "#e4e3df"
LAYER_CLASS = [  # (layers, label, color): reference palette slots 1-3
    ((2, 3), "fast middle layers (delay 2/step)", "#2a78d6"),
    ((1, 4), "next layers (delay 4/step)", "#1baf7a"),
    ((0, 5), "outer layers (delay 6/step)", "#eb6834"),
]
CRITICAL = "#e34948"
PHASE_TEXT = {
    "negotiate": "1  negotiating: nets still share grid points",
    "legal": "1  negotiation done: first legal routing",
    "refine": "2  exact reroute of one net at a time",
    "search": "3  neighborhood search (rip up groups of nets, reroute together)",
    "final": "final routing",
}


def score_snapshots(run_dir, inst):
    idx = pd.read_json(os.path.join(run_dir, "index.jsonl"), lines=True)
    rows = []
    for snap in idx.itertuples():
        sub = Submission.load(os.path.join(run_dir, snap.file))
        res = check(inst, sub)
        rows.append(dict(i=snap.i, legal=res.legal,
                         delay=res.total_delay if res.legal else snap.self_delay,
                         conflicts=[tuple(v) for v in res.conflict_vertices], sub=sub))
    return idx.join(pd.DataFrame(rows).set_index("i"), on="i")


def draw_routing(ax, inst, sub, conflicts):
    by_z = {z: [] for z in range(inst.layers)}
    for r in sub.routes:
        for a, b in r.edges:
            if a[2] == b[2]:
                off = (a[2] - (inst.layers - 1) / 2) * 0.07
                by_z[a[2]].append([(a[0] + off, a[1] + off), (b[0] + off, b[1] + off)])
    for layers, _, color in reversed(LAYER_CLASS):  # slow first, fast on top
        segs = [s for z in layers for s in by_z[z]]
        ax.add_collection(LineCollection(segs, colors=color, linewidths=1.1, alpha=0.9,
                                         capstyle="round"))
    pins = np.array([[p.x, p.y] for p in inst.pins])
    ax.scatter(pins[:, 0], pins[:, 1], s=5, c=INK2, linewidths=0, zorder=3)
    if conflicts:
        c = np.array([[v[0], v[1]] for v in conflicts])
        ax.scatter(c[:, 0], c[:, 1], s=34, facecolors="none", edgecolors=CRITICAL,
                   linewidths=1.2, zorder=4)
    ax.set_xlim(-0.8, inst.width - 0.2)
    ax.set_ylim(-0.8, inst.height - 0.2)
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color(GRID)


def draw_curve(ax, frames, k, refs):
    t = frames["t"].clip(lower=0.02).to_numpy()
    d = frames["delay"].to_numpy()
    legal = frames["legal"].to_numpy()
    first_legal = int(np.argmax(legal)) if legal.any() else len(frames)
    ax.plot(t, d, color=GRID, linewidth=2, zorder=1)  # whole run, faint
    upto = min(k, first_legal - 1)
    if upto >= 0:
        ax.plot(t[:upto + 1], d[:upto + 1], color=CRITICAL, linewidth=2, linestyle=(0, (2, 1.5)), zorder=2)
    if k >= first_legal:
        ax.plot(t[first_legal:k + 1], d[first_legal:k + 1], color=LAYER_CLASS[0][2], linewidth=2, zorder=2)
    ax.scatter([t[k]], [d[k]], s=64, color=CRITICAL if not legal[k] else LAYER_CLASS[0][2],
               edgecolors=SURFACE, linewidths=2, zorder=3)
    for name, val in refs:
        ax.axhline(val, color=MUTED, linewidth=1, linestyle=(0, (1, 2)), zorder=0)
        ax.text(t.max() * 1.08, val, f"{name}  {val:,.0f}", va="center", ha="left", fontsize=8.5, color=INK2)
    ax.set_xscale("log")
    ax.set_xlim(0.015, t.max() * 1.05)
    lo = min(r[1] for r in refs) * 0.97
    hi = max(max(d), max(r[1] for r in refs)) * 1.02
    ax.set_ylim(lo, hi)
    ax.set_xlabel("seconds since start (log scale)", fontsize=9, color=INK2)
    ax.set_ylabel("total sink delay (lower is better)", fontsize=9, color=INK2)
    ax.tick_params(labelsize=8, colors=INK2)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--tier", required=True)
    ap.add_argument("--case", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--width", type=int, default=1100)
    args = ap.parse_args()

    inst = Instance.load(instance_path(args.tier, args.case))
    ref = pd.read_csv(os.path.join(STATE, "reference_points.csv")).set_index(["tier", "case"])
    rp = ref.loc[(args.tier, args.case)]
    refs = [("reference router", rp["baseline"]), ("best public entry", rp["best_public"]),
            ("lower bound", rp["lb_best"]), ("congestion-free ideal", rp["lb_free"])]
    frames = score_snapshots(args.dir, inst)
    frames.drop(columns="sub").to_csv(os.path.join(args.dir, "frames.csv"), index=False)

    images, durations = [], []
    for k, fr in enumerate(frames.itertuples()):
        fig = plt.figure(figsize=(11, 5.6), dpi=100, facecolor=SURFACE)
        ax_r = fig.add_axes([0.03, 0.08, 0.42, 0.78], facecolor=SURFACE)
        ax_c = fig.add_axes([0.53, 0.14, 0.255, 0.66], facecolor=SURFACE)
        draw_routing(ax_r, inst, fr.sub, fr.conflicts)
        draw_curve(ax_c, frames, k, refs)
        score = rp["baseline"] / fr.delay
        status = (f"legal · delay {fr.delay:,} (checker) · score {score:.3f}" if fr.legal
                  else f"ILLEGAL · {len(fr.conflicts)} shared grid points · router's own delay {fr.delay:,}")
        fig.text(0.03, 0.95, f"hard/{args.case}  ({inst.width}×{inst.height}×{inst.layers} grid, "
                 f"{len(inst.nets)} nets) · t = {fr.t:5.2f} s", fontsize=12, color=INK, weight="bold")
        fig.text(0.03, 0.905, PHASE_TEXT[fr.phase], fontsize=10.5, color=INK2)
        fig.text(0.53, 0.905, status, fontsize=10.5, color=CRITICAL if not fr.legal else INK)
        handles = [Line2D([], [], color=c, linewidth=2.5, label=l) for _, l, c in LAYER_CLASS]
        handles.append(Line2D([], [], marker="o", linestyle="none", markerfacecolor="none",
                              markeredgecolor=CRITICAL, markersize=7, label="grid point used by 2+ nets"))
        handles.append(Line2D([], [], marker="o", linestyle="none", color=INK2, markersize=3, label="pin"))
        fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.03, 0.0), ncol=5, frameon=False,
                   fontsize=8, labelcolor=INK2, handlelength=1.6, columnspacing=1.2)
        images.append(_fig_to_pil(fig, args.width))
        plt.close(fig)
        durations.append(2600 if k == len(frames) - 1 else (650 if fr.phase in ("legal", "refine") else 380))
    _save_gif(images, durations, args.out)
    images[-1].save(os.path.splitext(args.out)[0] + "_final.png")
    print(f"wrote {args.out} ({len(images)} frames)")


if __name__ == "__main__":
    main()
