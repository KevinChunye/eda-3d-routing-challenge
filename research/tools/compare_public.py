"""Score every public entry and one of our runs, case by case, with the repo checker.

Per tier and entry: legal cases, total delay, aggregate (geometric mean over cases of
baseline / delay, the leaderboard score; only for complete entries), total runtime (only if
runtime.json covers every case, as on the leaderboard) and whether meta.json declares a
derived_from (or warm_start) parent, as the leaderboard marks it (another entry's routes reused).

Usage (from repo root):
  python3 research/tools/compare_public.py --run research/runs/submit-20261016 \
      --tiers hard congested designs --label kevin_toll_lns --out research/state/compare_public_20261016.csv
"""
import argparse
import glob
import os

import numpy as np
import pandas as pd

from common import REPO, STATE, case_names, instance_path, load_json, seed_dirs
from m3d.model import Instance, Submission
from m3d.scorer import score_case


def score_dir(tier, entry, sol_dir, insts, ref):
    rt_path = os.path.join(sol_dir, "runtime.json")
    runtimes = load_json(rt_path) if os.path.exists(rt_path) else {}
    meta_path = os.path.join(sol_dir, "meta.json")
    meta = load_json(meta_path) if os.path.exists(meta_path) else {}
    rows = []
    for case, inst in insts.items():
        sol = os.path.join(sol_dir, f"{case}.sol.json")
        base = int(ref.loc[(tier, case), "baseline"])
        legal, delay = False, np.nan
        if os.path.exists(sol):
            cs = score_case(inst, Submission.load(sol), base, runtimes.get(case))
            legal, delay = bool(cs.legal), (cs.total_delay if cs.legal else np.nan)
        rows.append(dict(tier=tier, entry=entry, case=case, legal=legal, delay=delay,
                         runtime=runtimes.get(case, np.nan), baseline=base,
                         lb_best=ref.loc[(tier, case), "lb_best"],
                         derived=bool(meta.get("derived_from") or meta.get("warm_start"))))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="our run dir (first seed is used)")
    ap.add_argument("--label", required=True)
    ap.add_argument("--tiers", nargs="+", default=["hard", "congested", "designs"])
    ap.add_argument("--out", required=True, help="per-case CSV")
    args = ap.parse_args()

    ref = pd.read_csv(os.path.join(STATE, "reference_points.csv")).set_index(["tier", "case"])
    ours = seed_dirs(args.run)[0]
    rows = []
    for tier in args.tiers:
        insts = {c: Instance.load(instance_path(tier, c)) for c in case_names(tier)}
        for d in sorted(glob.glob(os.path.join(REPO, "submissions", tier, "*"))):
            entry = os.path.basename(d)
            if os.path.isdir(d) and entry != args.label:
                rows += score_dir(tier, entry, d, insts, ref)
        rows += score_dir(tier, args.label, os.path.join(ours, tier), insts, ref)
    df = pd.DataFrame(rows)
    df["ratio"] = df["baseline"] / df["delay"]
    df.to_csv(args.out, index=False)

    summary = df.assign(logratio=np.log(df["ratio"])).groupby(["tier", "entry"]).agg(
        cases=("case", "size"), legal=("legal", "sum"), delay=("delay", "sum"),
        logratio=("logratio", "mean"), runtime=("runtime", "sum"),
        runtime_cases=("runtime", "count"), derived=("derived", "first"))
    complete = summary["legal"] == summary["cases"]
    summary["aggregate"] = np.where(complete, np.exp(summary["logratio"]), np.nan)
    summary["delay"] = np.where(complete, summary["delay"], np.nan)
    summary["runtime"] = np.where(summary["runtime_cases"] == summary["cases"], summary["runtime"], np.nan)
    summary = summary.drop(columns=["logratio", "runtime_cases"]).reset_index()
    summary = summary.sort_values(["tier", "aggregate"], ascending=[True, False])
    summary.to_csv(os.path.splitext(args.out)[0] + "_summary.csv", index=False)
    pd.set_option("display.width", 200)
    print(summary.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
