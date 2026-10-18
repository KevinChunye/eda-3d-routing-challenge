"""Tier-balanced verdict (S2) for a candidate run against a baseline run of the same batch.

Every delay comes from m3d.checker. Terms:
  r            100 x log(baseline delay / candidate delay) for one (tier, case, seed); r > 0 =
               candidate better
  tier mean r  mean of r over that tier's runs
  balanced     mean over tiers of the tier mean r (each tier counts once, however many cases)

Rule (research/state/ideas.md S2): adopt on a tier if its mean r > +0.2% and at least 2/3 of
its runs improve; any illegal candidate route -> failed-correctness for that tier.

Usage (from repo root):
  python3 research/tools/tier_verdict.py --run research/runs/exp-036-s1 \
      --base research/runs/exp-036-base --cases "hard:case_01,case_05,case_09+congested:case_01,case_02+designs:ctrl,int2float"
  add --log --exp-id exp-036 --idea S1 to append a result row to experiments.jsonl
"""
import argparse
import datetime
import os

import numpy as np
import pandas as pd

from common import instance_path, seed_dirs, select_cases
from m3d.checker import check
from m3d.model import Instance, Submission


def delays(run_dir, cases):
    rows = []
    for sd in seed_dirs(run_dir):
        for tier, names in cases.items():
            for case in names:
                sol = os.path.join(sd, tier, f"{case}.sol.json")
                if not os.path.exists(sol):
                    rows.append(dict(seed=os.path.basename(sd), tier=tier, case=case, legal=False, delay=np.nan))
                    continue
                res = check(Instance.load(instance_path(tier, case)), Submission.load(sol))
                rows.append(dict(seed=os.path.basename(sd), tier=tier, case=case, legal=bool(res.legal),
                                 delay=res.total_delay if res.legal else np.nan))
    return pd.DataFrame(rows)


def verdict(cand, base, min_r=0.2, min_share=2 / 3):
    df = cand.merge(base, on=["seed", "tier", "case"], suffixes=("", "_base"))
    df["r"] = 100 * np.log(df["delay_base"] / df["delay"])
    tiers = df.groupby("tier").agg(runs=("r", "size"), mean_r=("r", "mean"), sd_r=("r", "std"),
                                   improved=("r", lambda x: (x > 0).mean()),
                                   illegal=("legal", lambda x: int((~x).sum())))
    tiers["decision"] = np.where(tiers.illegal > 0, "failed-correctness",
                                 np.where((tiers.mean_r > min_r) & (tiers.improved >= min_share - 1e-9),
                                          "adopt", np.where(tiers.mean_r > 0, "inconclusive", "reject")))
    return df, tiers, float(tiers.mean_r.mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--cases", required=True)
    ap.add_argument("--log", action="store_true")
    ap.add_argument("--exp-id")
    ap.add_argument("--idea", default="")
    args = ap.parse_args()
    cases = select_cases(args.cases)
    df, tiers, balanced = verdict(delays(args.run, cases), delays(args.base, cases))
    pd.set_option("display.width", 200)
    print(df.pivot_table(index=["tier", "case"], columns="seed", values="r").round(3).to_string())
    print()
    print(tiers.round(3).to_string())
    print(f"\nbalanced mean r (mean over tiers) = {balanced:+.3f}%   runs improved = {(df.r > 0).mean():.0%}")
    if args.log:
        from exp_log import append
        append(dict(kind="result", exp_id=args.exp_id, idea=args.idea, run=args.run, compare=args.base,
                    date=datetime.datetime.now().isoformat(timespec="seconds"),
                    balanced_mean_r_pct=round(balanced, 3),
                    tiers={t: {"runs": int(r.runs), "mean_r_pct": round(float(r.mean_r), 3),
                               "frac_improved": round(float(r.improved), 3), "decision": r.decision}
                           for t, r in tiers.iterrows()}))
        print("logged result row for", args.exp_id)


if __name__ == "__main__":
    main()
