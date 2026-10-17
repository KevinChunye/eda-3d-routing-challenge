"""Race router configurations by successive halving (the idea behind irace / F-Race).

Every stage runs the reference configuration and each surviving candidate on the same new
(tier, case, seed) pairs, scores every route with m3d.checker, and ranks candidates by mean
r over all pairs seen so far, where r = log(reference delay / candidate delay) for the same
pair (r > 0: candidate better). The worse half is dropped after each stage.

Usage (from repo root):
  python3 research/tools/tune_race.py --label race-v4 --binary router/build/m3d_route \
      --base "<reference flags>" --configs research/state/race_v4_configs.json \
      --budget 30 --jobs 4
configs JSON: [{"name": "...", "flags": "..."}]; flags are appended to --base.
"""
import argparse
import json
import os
import shlex
import subprocess
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from common import RUNS, STATE, instance_path
from m3d.checker import check
from m3d.model import Instance, Submission

STAGES = [  # new (tier, case, seed) pairs per stage
    [("hard", "case_02", 1), ("hard", "case_06", 1), ("hard", "case_09", 1), ("congested", "case_01", 1)],
    [("hard", "case_01", 2), ("hard", "case_04", 2), ("hard", "case_07", 2), ("designs", "ctrl", 1)],
    [("hard", "case_03", 1), ("hard", "case_05", 1), ("hard", "case_08", 1), ("hard", "case_02", 2),
     ("hard", "case_06", 2), ("hard", "case_09", 2), ("congested", "case_01", 2), ("designs", "ctrl", 2)],
    [("hard", "case_01", 3), ("hard", "case_03", 3), ("hard", "case_04", 3), ("hard", "case_05", 3),
     ("hard", "case_07", 3), ("hard", "case_08", 3), ("congested", "case_01", 3), ("designs", "ctrl", 3)],
]
KEEP = [8, 4, 2, 2]


def run_one(job):
    os.makedirs(os.path.dirname(job["out"]), exist_ok=True)
    if not os.path.exists(job["out"]):
        cmd = (f"{job['binary']} --instance {instance_path(job['tier'], job['case'])} --out {job['out']} "
               f"--time-limit {job['budget']} --seed {job['seed']} --threads 1 {job['flags']}")
        subprocess.run(shlex.split(cmd), capture_output=True, text=True, timeout=job["budget"] * 2 + 60)
    inst = Instance.load(instance_path(job["tier"], job["case"]))
    res = check(inst, Submission.load(job["out"]))
    return dict(config=job["config"], tier=job["tier"], case=job["case"], seed=job["seed"],
                legal=res.legal, delay=res.total_delay if res.legal else np.nan)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--binary", required=True)
    ap.add_argument("--base", required=True, help="reference flags")
    ap.add_argument("--configs", required=True)
    ap.add_argument("--budget", type=float, default=30)
    ap.add_argument("--jobs", type=int, default=4)
    args = ap.parse_args()

    configs = {c["name"]: c["flags"] for c in json.load(open(args.configs))}
    alive = list(configs)
    root = os.path.join(RUNS, args.label)
    rows = []
    for stage, (pairs, keep) in enumerate(zip(STAGES, KEEP), start=1):
        jobs = []
        for name in ["REF"] + alive:
            flags = args.base + ("" if name == "REF" else " " + configs[name])
            for tier, case, seed in pairs:
                out = os.path.join(root, name, f"{tier}_{case}_s{seed}.sol.json")
                jobs.append(dict(config=name, tier=tier, case=case, seed=seed, out=out, flags=flags,
                                 binary=args.binary, budget=args.budget))
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            rows += list(pool.map(run_one, jobs))
        df = pd.DataFrame(rows)
        ref = df[df.config == "REF"].set_index(["tier", "case", "seed"])["delay"]
        cand = df[df.config != "REF"].join(ref.rename("ref"), on=["tier", "case", "seed"])
        cand["r"] = 100 * np.log(cand["ref"] / cand["delay"])
        score = (cand[cand.config.isin(alive)].groupby("config")
                 .agg(pairs=("r", "size"), mean_r=("r", "mean"), sd_r=("r", "std"),
                      better=("r", lambda x: (x > 0).mean()), illegal=("legal", lambda x: (~x).sum()))
                 .sort_values("mean_r", ascending=False))
        print(f"\n== stage {stage}: {len(pairs)} new pairs, {len(alive)} candidates")
        print(score.round(3).to_string())
        alive = [c for c in score.index if score.loc[c, "illegal"] == 0][:keep]
        pd.DataFrame(rows).to_csv(os.path.join(STATE, f"tune_{args.label}.csv"), index=False)
    print("\nsurvivors:", alive)


if __name__ == "__main__":
    main()
