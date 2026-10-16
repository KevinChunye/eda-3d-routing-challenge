"""Reference points per case: baseline, lower bounds, and the best public route.

Writes research/state/reference_points.csv with, per case:
  baseline     the tier's normalization total (suite.json); score ratio = baseline / ours
  lb_free      congestion-free lower bound: every sink routed alone on an empty grid along
               its cheapest path (climb to some layer k, all X/Y steps there, come back)
  lb_toll      best congestion-aware (Lagrangian) bound in research/state/toll_bounds.jsonl
  lb_best      max(lb_free, lb_toll): the certified floor used for "gap to bound"
  best_public  lowest checker-verified total among submissions/<tier>/* (excluding --exclude)

Usage: python research/tools/reference_points.py [--exclude our_entry_name ...]
"""
import argparse
import os

import pandas as pd

from common import STATE, TIERS, load_json, manifest, suite_dir, REPO
from m3d.scorer import score_submission_set


def lb_free(inst):
    ld = inst["delay"]["layer_delay"]
    via = inst["delay"]["via_delay"]
    pins = {p["id"]: p for p in inst["pins"]}
    total = 0
    for net in inst["nets"]:
        d = pins[net["driver"]]
        for sid in net["sinks"]:
            s = pins[sid]
            dist = abs(d["x"] - s["x"]) + abs(d["y"] - s["y"])
            total += min(via * (abs(d["z"] - k) + abs(k - s["z"])) + dist * ld[k]
                         for k in range(len(ld)))
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exclude", nargs="*", default=[], help="entry names to ignore (ours)")
    args = ap.parse_args()

    rows, public = [], []
    for tier in TIERS:
        man = manifest(tier)
        for c in man["cases"]:
            inst = load_json(os.path.join(suite_dir(tier), c["instance_file"]))
            rows.append(dict(tier=tier, case=c["name"], baseline=c["baseline_total"],
                             lb_free=lb_free(inst)))
        troot = os.path.join(REPO, "submissions", tier)
        for name in sorted(os.listdir(troot)) if os.path.isdir(troot) else []:
            d = os.path.join(troot, name)
            if name.startswith("_") or name in args.exclude or not os.path.isdir(d):
                continue
            s = score_submission_set(man, suite_dir(tier), d, name)
            public += [dict(tier=tier, case=cs.case, entry=name, delay=cs.total_delay)
                       for cs in s.cases if cs.legal]

    ref = pd.DataFrame(rows)
    pub = pd.DataFrame(public).sort_values("delay")
    best = pub.groupby(["tier", "case"]).first().reset_index()
    best = best.rename(columns={"delay": "best_public", "entry": "best_public_entry"})
    ref = ref.merge(best, on=["tier", "case"], how="left")

    toll_path = os.path.join(STATE, "toll_bounds.jsonl")
    if os.path.exists(toll_path) and os.path.getsize(toll_path) > 0:
        toll = pd.read_json(toll_path, lines=True)
        toll = toll.groupby(["tier", "case"])["lagrange_lb"].max().rename("lb_toll").reset_index()
        ref = ref.merge(toll, on=["tier", "case"], how="left")
    else:
        ref["lb_toll"] = float("nan")
    ref["lb_best"] = ref[["lb_free", "lb_toll"]].max(axis=1)
    ref = ref[["tier", "case", "baseline", "lb_free", "lb_toll", "lb_best",
               "best_public", "best_public_entry"]]
    ref.to_csv(os.path.join(STATE, "reference_points.csv"), index=False)

    tot = ref.groupby("tier", sort=False)[["baseline", "lb_free", "lb_best", "best_public"]].sum()
    tot["best_public_over_lb_free_%"] = 100 * (tot["best_public"] / tot["lb_free"] - 1)
    tot["best_public_over_lb_best_%"] = 100 * (tot["best_public"] / tot["lb_best"] - 1)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", None)
    print(tot.round(2))
    print(f"\nwrote {os.path.join(STATE, 'reference_points.csv')}")


if __name__ == "__main__":
    main()
