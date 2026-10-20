"""Where the router's CPU goes, for router/AUDIT.md.

Reads gprof flat profiles (research/models/jiangbanya_v5/profile/flat_<tier>.txt: static -pg
build, 1 thread, 120 s, the tier's v5 settings) and draws
  router_profile.png   share of sampled CPU time by kind of work, per tier (heat table)
  router_code_map.png  router/src/main.cpp as a strip of functions by line number, shaded by
                       their share of CPU per tier; code behind flags that v5 leaves off is gray

Usage (from repo root):
  python3 research/tools/plot_router_audit.py --profiles research/models/jiangbanya_v5/profile \
      --out research/models/jiangbanya_v5
"""
import argparse
import os
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e4e3df"
RAMP = LinearSegmentedColormap.from_list("blue", ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])
TIERS = ["hard", "congested", "designs", "scale"]
ROW = re.compile(r"^\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(?:\d+\s+[\d.]+\s+[\d.]+\s+)?(.+)$")

# kind of work: first matching pattern wins (gprof names; lambdas belong to their function)
KINDS = [
    ("group repair searches (B3)", r"route_neg(_int|_astar)?<true>"),
    ("initial negotiation searches (A1)", r"route_neg(_int|_astar)?<false>"),
    ("S1 goal bound hsink()", r"hsink"),
    ("S1 cost rounding (libm lround)", r"^lround$"),
    ("exact searches + tree build (A2, B4)", r"route_exact|build_tree"),
    ("queue pushes (vector push_back)", r"push_back"),
    ("move loop, bandit, threads, other", r"."),
]
# main.cpp at 94e4fbc: (first line, last line, label, gprof pattern, used by v5)
BLOCKS = [
    (41, 109, "options, instance loading", r"Options|load_instance", True),
    (115, 307, "Router(): flags, flat arrays", r"Router::Router", True),
    (310, 366, "negotiate()  A1", r"Router::negotiate\(", True),
    (369, 393, "refine()  A2", r"Router::refine", True),
    (400, 439, "lns(), lns_setup()", r"lns_setup|Router::lns\(", True),
    (442, 687, "lns_run()  move loop", r"lns_run", True),
    (689, 808, "ejection chains (S3)", r"route_evict|ej_|ejection", False),
    (810, 858, "threshold, restore, finish", r"ta_threshold|restore_best|lns_finish|update_pressure", True),
    (860, 930, "thread sync: adopt, merge", r"epoch_end|adopt|merge_from", True),
    (939, 977, "group_negotiate()  B3", r"group_negotiate", True),
    (983, 1143, "write(), snapshots", r"Router::(?:write|snapshot|final_snapshot)\b", True),
    (1150, 1170, "for_nb, rip, place", r"Router::(?:for_nb|rip|place|add_occ|sub_occ)\b", True),
    (1171, 1195, "build_tree_into()", r"build_tree_into", True),
    (1197, 1242, "route_exact()  B4", r"route_exact<", True),
    (1244, 1286, "route_exact_astar()", r"route_exact_astar", True),
    (1288, 1320, "build_tree_rand()", r"build_tree_rand", True),
    (1322, 1371, "build_tree_share()", r"build_tree_share", False),
    (1373, 1420, "route_neg()  binary heap", r"route_neg<", True),
    (1422, 1484, "route_neg_seq()", r"route_neg_seq", False),
    (1486, 1512, "sink_boxes(), hsink()  S1", r"hsink|sink_boxes", True),
    (1514, 1574, "route_neg_int()  S1 buckets", r"route_neg_int<|^lround$", True),
    (1576, 1613, "route_neg_astar()", r"route_neg_astar<", True),
    (1616, 1666, "parallel_lns()  threads", r"^parallel_lns", True),
    (1668, 1734, "main()", r"^main", True),
]


def read_flat(path):
    rows = []
    with open(path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            m = ROW.match(line)
            if m and not line.strip().startswith("%"):
                rows.append(dict(self_s=float(m.group(3)), name=m.group(4).strip()))
    df = pd.DataFrame(rows)
    df["share"] = 100 * df.self_s / df.self_s.sum()
    return df


def classify(name, table):
    for label, pat in table:
        if re.search(pat, name):
            return label
    return None


def profile_table(profiles):
    out = {}
    for tier in TIERS:
        df = read_flat(os.path.join(profiles, f"flat_{tier}.txt"))
        df["kind"] = [classify(n, KINDS) for n in df.name]
        out[tier] = df.groupby("kind")["share"].sum()
    return pd.DataFrame(out).reindex([k for k, _ in KINDS]).fillna(0.0)


def heat(out, t):
    fig, ax = plt.subplots(figsize=(9.5, 4.2), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    vmax = 60.0
    for i, kind in enumerate(t.index):
        for j, tier in enumerate(t.columns):
            v = t.loc[kind, tier]
            ax.add_patch(Rectangle((j, i), 0.96, 0.92, facecolor=RAMP(min(v, vmax) / vmax), edgecolor=SURFACE))
            ax.text(j + 0.48, i + 0.46, f"{v:.0f}%" if v >= 0.5 else "<1%", ha="center", va="center", fontsize=9,
                    color="white" if v > 0.45 * vmax else INK)
    ax.set_xlim(0, len(t.columns))
    ax.set_ylim(len(t.index), 0)
    ax.set_xticks(np.arange(len(t.columns)) + 0.48, [f"{c}\n{'S1 on' if c in ('designs', 'scale') else 'S1 off'}"
                                                     for c in t.columns], fontsize=9, color=INK)
    ax.set_yticks(np.arange(len(t.index)) + 0.46, t.index, fontsize=9, color=INK)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.xaxis.tick_top()
    ax.set_title("Share of CPU by kind of work (gprof, 1 thread, 120 s per run, each tier's v5 settings)",
                 fontsize=10, color=INK, loc="left", pad=34)
    fig.text(0.01, 0.01, "Over 95% of CPU is shortest-path search; the move loop, bandit and thread code are 0.4-2.3%. "
             "In these 120 s runs the first negotiation takes 6-43 s;\nin the 1-2.5 hour submission runs it is a few "
             "percent, so group repair searches dominate even more.", fontsize=8, color=INK2)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    path = os.path.join(out, "router_profile.png")
    fig.savefig(path, dpi=130, facecolor=SURFACE)
    plt.close(fig)
    print("wrote", path)


def code_map(out, profiles):
    shares = {}
    for tier in TIERS:
        df = read_flat(os.path.join(profiles, f"flat_{tier}.txt"))
        shares[tier] = [df[df.name.str.contains(pat, regex=True)].share.sum() for _, _, _, pat, _ in BLOCKS]
    fig, ax = plt.subplots(figsize=(10, 9.5), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    vmax = 60.0
    x0 = 0.0
    for k, (a, b, label, _, used) in enumerate(BLOCKS):
        h = b - a + 1
        ax.text(x0 - 0.05, a + h / 2, f"{label}  :{a}", ha="right", va="center", fontsize=8,
                color=INK if used else MUTED)
        for j, tier in enumerate(TIERS):
            v = shares[tier][k]
            if used:
                face = RAMP(min(v, vmax) / vmax) if v >= 0.5 else "#f1f0ec"
                ax.add_patch(Rectangle((x0 + j, a), 0.94, h - 2, facecolor=face, edgecolor="none"))
                if v >= 1.0:
                    ax.text(x0 + j + 0.47, a + h / 2, f"{v:.0f}%", ha="center", va="center", fontsize=8,
                            color="white" if v > 0.45 * vmax else INK)
            else:
                ax.add_patch(Rectangle((x0 + j, a), 0.94, h - 2, facecolor=SURFACE, edgecolor=MUTED, hatch="///",
                                       linewidth=0.5))
    for j, tier in enumerate(TIERS):
        ax.text(x0 + j + 0.47, 15, tier, ha="center", va="bottom", fontsize=9, color=INK)
    ax.set_xlim(-3.3, len(TIERS) + 1.6)
    ax.set_ylim(1745, 0)
    ax.axis("off")
    ax.add_patch(Rectangle((len(TIERS) + 0.2, 120), 0.3, 40, facecolor=SURFACE, edgecolor=MUTED, hatch="///",
                           linewidth=0.5))
    ax.text(len(TIERS) + 0.6, 140, "flag off in v5:\nskip on a first audit", va="center", fontsize=8, color=INK2)
    ax.add_patch(Rectangle((len(TIERS) + 0.2, 200), 0.3, 40, facecolor=RAMP(1.0), edgecolor="none"))
    ax.text(len(TIERS) + 0.6, 220, "darker = more CPU", va="center", fontsize=8, color=INK2)
    ax.set_title("router/src/main.cpp from top (line 1) to bottom (line 1,734): share of CPU per function and tier",
                 fontsize=10, color=INK, loc="left")
    fig.tight_layout()
    path = os.path.join(out, "router_code_map.png")
    fig.savefig(path, dpi=130, facecolor=SURFACE)
    plt.close(fig)
    print("wrote", path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profiles", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    t = profile_table(args.profiles)
    print(t.round(1).to_string())
    heat(args.out, t)
    code_map(args.out, args.profiles)


if __name__ == "__main__":
    main()
