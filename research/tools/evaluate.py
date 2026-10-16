"""Score a run with the repo's independent checker, and optionally compare it to another run.

Every delay here is recomputed by m3d.checker from the route files; router self-reports
are never used.

Terms used in the output:
  ratio          baseline_total / delay for one case (the leaderboard's per-case score)
  aggregate      geometric mean of ratios over the evaluated cases (per seed, then averaged)
  gap_to_bound   delay / lb_best - 1, where lb_best is the best certified lower bound
                 (research/state/reference_points.csv); the share of delay we cannot rule
                 out as avoidable
  vs_public      delay / best public route - 1 (negative = we beat every public entry)
  r              log(incumbent delay / candidate delay) for the same case and seed;
                 r > 0 means the candidate is better

Decision rule (fixed in advance; research/README.md):
  any illegal case                       -> failed-correctness
  mean r > 0 and r > 0 on >= 2/3 cases   -> adopt
  mean r > 0 otherwise                   -> inconclusive
  mean r <= 0                            -> reject

Usage (from repo root):
  python research/tools/evaluate.py --run research/runs/exp-004
  python research/tools/evaluate.py --run research/runs/exp-004 --compare research/runs/incumbent
  ... --log --exp-id exp-004 --idea I2      (append the result row to experiments.jsonl)
"""
import argparse
import datetime
import json
import os

import numpy as np
import pandas as pd

from common import STATE, TIERS, instance_path, load_json, seed_dirs, select_cases
from m3d.model import Instance, Submission
from m3d.scorer import score_case


def score_run(run_dir, cases):
    ref = pd.read_csv(os.path.join(STATE, "reference_points.csv")).set_index(["tier", "case"])
    rows = []
    for sd in seed_dirs(run_dir):
        seed = os.path.basename(sd) if sd != run_dir else "seed?"
        for tier, names in cases.items():
            rt_path = os.path.join(sd, tier, "runtime.json")
            runtimes = load_json(rt_path) if os.path.exists(rt_path) else {}
            for case in names:
                sol = os.path.join(sd, tier, f"{case}.sol.json")
                base = int(ref.loc[(tier, case), "baseline"])
                if not os.path.exists(sol):
                    rows.append(dict(seed=seed, tier=tier, case=case, legal=False, delay=np.nan,
                                     runtime=np.nan, reason="missing"))
                    continue
                cs = score_case(Instance.load(instance_path(tier, case)), Submission.load(sol),
                                base, runtimes.get(case))
                rows.append(dict(seed=seed, tier=tier, case=case, legal=bool(cs.legal),
                                 delay=cs.total_delay if cs.legal else np.nan,
                                 runtime=runtimes.get(case, np.nan),
                                 reason="; ".join(cs.reasons[:2]) if not cs.legal else ""))
    df = pd.DataFrame(rows)
    df = df.join(ref[["baseline", "lb_best", "best_public"]], on=["tier", "case"])
    df["ratio"] = df["baseline"] / df["delay"]
    return df


def summarize(df):
    per_case = df.groupby(["tier", "case"], sort=False).agg(
        legal=("legal", "all"), delay_mean=("delay", "mean"), delay_min=("delay", "min"),
        lb_best=("lb_best", "first"), best_public=("best_public", "first"),
        runtime_mean=("runtime", "mean"))
    per_case["gap_to_bound_%"] = 100 * (per_case["delay_mean"] / per_case["lb_best"] - 1)
    per_case["vs_public_%"] = 100 * (per_case["delay_mean"] / per_case["best_public"] - 1)
    agg = (df.assign(logratio=np.log(df["ratio"]))
             .groupby(["tier", "seed"])["logratio"].mean().groupby("tier").mean())
    tiers = df.groupby("tier").agg(cases=("case", "nunique"), legal=("legal", "all"),
                                   delay=("delay", "sum"), lb_best=("lb_best", "sum"),
                                   best_public=("best_public", "sum"))
    n_seeds = df["seed"].nunique()
    tiers["delay"] = tiers["delay"] / n_seeds
    tiers["lb_best"] = tiers["lb_best"] / n_seeds
    tiers["best_public"] = tiers["best_public"] / n_seeds
    tiers["aggregate"] = np.exp(agg)
    tiers["gap_to_bound_%"] = 100 * (tiers["delay"] / tiers["lb_best"] - 1)
    tiers["vs_public_%"] = 100 * (tiers["delay"] / tiers["best_public"] - 1)
    order = [t for t in TIERS if t in tiers.index]
    return per_case, tiers.loc[order]


def compare(cand, inc, min_r_pct=0.0):
    key = ["seed", "tier", "case"]
    m = cand[key + ["delay", "legal"]].merge(inc[key + ["delay", "legal"]], on=key,
                                             suffixes=("_cand", "_inc"))
    m["r"] = np.log(m["delay_inc"] / m["delay_cand"])
    per_case = m.groupby(["tier", "case"])["r"].mean()
    mean_r = float(per_case.mean())
    frac = float((per_case > 0).mean())
    if not cand["legal"].all():
        decision = "failed-correctness"
    elif mean_r > min_r_pct / 100 and frac >= 2 / 3:
        decision = "adopt"
    elif mean_r > 0:
        decision = "inconclusive"
    else:
        decision = "reject"
    return per_case, mean_r, frac, decision, len(m)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--cases", default="dev")
    ap.add_argument("--compare", help="incumbent run dir (same cases and seeds)")
    ap.add_argument("--log", action="store_true")
    ap.add_argument("--exp-id")
    ap.add_argument("--idea")
    ap.add_argument("--note", default="")
    ap.add_argument("--min-r", type=float, default=0.0,
                    help="adopt needs mean r above this many percent (0.2 with a fresh base)")
    args = ap.parse_args()

    cases = select_cases(args.cases)
    df = score_run(args.run, cases)
    per_case, tiers = summarize(df)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", None)
    print(f"== {args.run}  ({df['seed'].nunique()} seed(s), {len(df)} case-runs)")
    bad = df[~df["legal"]]
    if len(bad):
        print("ILLEGAL or missing:\n", bad[["seed", "tier", "case", "reason"]].to_string(index=False))
    print(per_case.round(2).to_string())
    print("\n", tiers.round(4).to_string())

    result = dict(kind="result", exp_id=args.exp_id, idea=args.idea, run=args.run,
                  cases=args.cases, date=datetime.datetime.now().isoformat(timespec="seconds"),
                  seeds=sorted(df["seed"].unique().tolist()),
                  all_legal=bool(df["legal"].all()),
                  tiers={t: {k: (None if pd.isna(v) else round(float(v), 4))
                             for k, v in row.items() if k != "legal"}
                         for t, row in tiers.iterrows()},
                  per_case={f"{t}/{c}": round(float(v), 1)
                            for (t, c), v in per_case["delay_mean"].items() if pd.notna(v)},
                  note=args.note)
    run_info = os.path.join(args.run, "run_info.json")
    if os.path.exists(run_info):
        info = load_json(run_info)
        result.update(git_sha=info.get("git_sha"), machine=info.get("machine"),
                      time_limit=info.get("time_limit"), extra=info.get("extra"))

    if args.compare:
        inc = score_run(args.compare, cases)
        pc, mean_r, frac, decision, n = compare(df, inc, args.min_r)
        print(f"\n== vs {args.compare}: {n} paired case-runs")
        print((100 * pc).round(3).rename("r_% (log-ratio x100, + = candidate better)").to_string())
        print(f"mean r = {100 * mean_r:+.3f}%   cases improved = {frac:.0%}   "
              f"-> suggested decision: {decision}")
        if os.path.exists(os.path.join(args.compare, "run_info.json")) and os.path.exists(run_info):
            m1 = load_json(run_info).get("machine")
            m2 = load_json(os.path.join(args.compare, "run_info.json")).get("machine")
            if m1 != m2:
                print("WARNING: runs come from different machines; re-run the incumbent here.")
        result.update(compare_to=args.compare, mean_r_pct=round(100 * mean_r, 4),
                      frac_cases_improved=round(frac, 3), suggested_decision=decision)

    if args.log:
        if not args.exp_id:
            raise SystemExit("--log needs --exp-id")
        with open(os.path.join(STATE, "experiments.jsonl"), "a") as fh:
            fh.write(json.dumps(result) + "\n")
        print(f"\nlogged result row for {args.exp_id}")


if __name__ == "__main__":
    main()
