"""Append pre-registration and decision rows to research/state/experiments.jsonl.

An experiment is the set of rows sharing one exp_id:
  kind=registered   written BEFORE running: hypothesis, change, prediction, budget, seeds
  kind=result       written by evaluate.py --log
  kind=decision     written after reading the result: adopt / reject / inconclusive /
                    failed-correctness, plus what was learned

Usage (from repo root):
  python research/tools/exp_log.py next-id
  python research/tools/exp_log.py register --exp-id exp-004 --idea I2 \
      --hypothesis "..." --change "..." --prediction "..." --budget 30 --seeds 1 2 3
  python research/tools/exp_log.py decide --exp-id exp-004 --decision adopt --learned "..."
  python research/tools/exp_log.py show [--last 15]
"""
import argparse
import datetime
import json
import os

import pandas as pd

from common import STATE

LOG = os.path.join(STATE, "experiments.jsonl")


def read_log():
    if not os.path.exists(LOG) or os.path.getsize(LOG) == 0:
        return pd.DataFrame(columns=["kind", "exp_id"])
    return pd.read_json(LOG, lines=True)


def append(row):
    row["date"] = datetime.datetime.now().isoformat(timespec="seconds")
    with open(LOG, "a") as fh:
        fh.write(json.dumps(row) + "\n")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("next-id")
    r = sub.add_parser("register")
    r.add_argument("--exp-id", required=True)
    r.add_argument("--idea", required=True)
    r.add_argument("--hypothesis", required=True)
    r.add_argument("--change", required=True)
    r.add_argument("--prediction", required=True)
    r.add_argument("--budget", type=float, required=True, help="seconds per case")
    r.add_argument("--seeds", type=int, nargs="+", required=True)
    r.add_argument("--cases", default="dev")
    d = sub.add_parser("decide")
    d.add_argument("--exp-id", required=True)
    d.add_argument("--decision", required=True,
                   choices=["adopt", "reject", "inconclusive", "failed-correctness"])
    d.add_argument("--learned", required=True)
    s = sub.add_parser("show")
    s.add_argument("--last", type=int, default=15)
    args = ap.parse_args()

    log = read_log()
    if args.cmd == "next-id":
        ids = log["exp_id"].dropna().astype(str)
        nums = ids.str.extract(r"exp-(\d+)")[0].dropna().astype(int)
        print(f"exp-{(nums.max() + 1 if len(nums) else 0):03d}")
    elif args.cmd == "register":
        if (log["exp_id"] == args.exp_id).any():
            raise SystemExit(f"{args.exp_id} already exists")
        append(dict(kind="registered", exp_id=args.exp_id, idea=args.idea,
                    hypothesis=args.hypothesis, change=args.change, prediction=args.prediction,
                    budget_s=args.budget, seeds=args.seeds, cases=args.cases))
        print(f"registered {args.exp_id}")
    elif args.cmd == "decide":
        if not ((log["exp_id"] == args.exp_id) & (log["kind"] == "result")).any():
            raise SystemExit(f"{args.exp_id} has no result row yet (run evaluate.py --log)")
        append(dict(kind="decision", exp_id=args.exp_id, decision=args.decision,
                    learned=args.learned))
        print(f"{args.exp_id}: {args.decision}")
    elif args.cmd == "show":
        cols = [c for c in ["exp_id", "kind", "idea", "decision", "mean_r_pct",
                            "frac_cases_improved", "prediction", "learned"] if c in log.columns]
        pd.set_option("display.width", 220)
        pd.set_option("display.max_colwidth", 70)
        print(log[cols].tail(args.last).to_string(index=False))


if __name__ == "__main__":
    main()
