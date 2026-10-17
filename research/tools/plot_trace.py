"""Plot the search trajectory of router runs from their TRACE lines (router flag --set trace_s=S).

Each TRACE line is "TRACE <seconds since start> <current total delay> <best total delay>
<threshold>", printed by the main search thread. The current total rises while the search
accepts worse moves (exploration) and falls again as the threshold cools; the best total
only falls. Both are the router's own sums (diagnostic only); the final route's delay is
checked by m3d.checker and printed in the legend.

Usage (from repo root):
  python3 research/tools/plot_trace.py --out trace.png --title "hard case_01, 600 s" \
      --run "v3=D1/run.log=D1/final.sol.json" --run "v4=D2/run.log=D2/final.sol.json" \
      --tier hard --case case_01
"""
import argparse

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from common import instance_path  # noqa: E402
from m3d.checker import check  # noqa: E402
from m3d.model import Instance, Submission  # noqa: E402


def read_trace(path):
    rows = [line.split()[1:5] for line in open(path) if line.startswith("TRACE ")]
    df = pd.DataFrame(rows, columns=["t", "current", "best", "thr"]).astype(float)
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="append", required=True, help="label=log path=route file")
    ap.add_argument("--tier", required=True)
    ap.add_argument("--case", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    inst = Instance.load(instance_path(args.tier, args.case))
    fig, (ax, ax_thr) = plt.subplots(2, 1, figsize=(9, 6.5), sharex=True,
                                     gridspec_kw={"height_ratios": [3, 1]})
    for i, spec in enumerate(args.run):
        label, log, sol = spec.split("=")
        df = read_trace(log)
        res = check(inst, Submission.load(sol))
        color = f"C{i}"
        final = f"checker {res.total_delay:,}" if res.legal else "illegal"
        ax.plot(df.t, df.current, color=color, lw=0.8, alpha=0.55, label=f"{label}: current")
        ax.plot(df.t, df.best, color=color, lw=2.0, label=f"{label}: best ({final})")
        ax_thr.plot(df.t, df.thr, color=color, lw=1.5, label=label)
    ax.set_ylabel("total sink delay (router sum)")
    ax.set_title(args.title)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    ax_thr.set_ylabel("threshold")
    ax_thr.set_xlabel("seconds")
    ax_thr.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(args.out, dpi=110)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
