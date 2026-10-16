"""Where does a routing lose delay? Per-sink breakdown of the excess over the ideal.

ideal(sink)  = its congestion-free cheapest path: climb to some layer k*, do all X/Y steps
               there, come back down (what it would cost with no other nets on the grid)
excess       = actual path delay in the submitted tree - ideal, split exactly into
  layer      steps taken on slower layers than the ideal path used
  detour     extra X/Y steps beyond the Manhattan distance (valued at the cheapest step, 2)
  via        extra layer changes beyond the ideal path's
Also reports which nets carry the excess (by sinks per net and by driver-sink distance),
how concentrated it is, and how full each layer is.

Usage (from repo root):
  python research/tools/gap_decompose.py --run research/runs/incumbent      (seed1, dev cases)
  python research/tools/gap_decompose.py --best-public --cases hard+congested+designs
  add --csv out.csv to keep the per-sink table
"""
import argparse
import os
from collections import deque

import pandas as pd

from common import REPO, STATE, instance_path, load_json, seed_dirs, select_cases


def sink_rows(tier, case, inst, sol):
    W, H, L = inst["grid"]["width"], inst["grid"]["height"], inst["grid"]["layers"]
    ld, via = inst["delay"]["layer_delay"], inst["delay"]["via_delay"]
    cheapest = min(ld)
    pins = {p["id"]: p for p in inst["pins"]}
    nets = {n["id"]: n for n in inst["nets"]}
    rows, used = [], set()
    for r in sol["routes"]:
        net = nets[r["net"]]
        adj = {}
        for u, v in r["edges"]:
            u, v = tuple(u), tuple(v)
            for a, b in ((u, v), (v, u)):
                if a not in adj:
                    adj[a] = []
                adj[a].append(b)
            used.add(u)
            used.add(v)
        d = pins[net["driver"]]
        root = (d["x"], d["y"], d["z"])
        state = {root: ([0] * L, 0)}  # vertex -> (X/Y steps per layer, vias) from driver
        q = deque([root])
        while q:
            u = q.popleft()
            hz, nv = state[u]
            for v in adj.get(u, []):
                if v in state:
                    continue
                if v[2] == u[2]:
                    h2 = list(hz)
                    h2[u[2]] += 1
                    state[v] = (h2, nv)
                else:
                    state[v] = (hz, nv + 1)
                q.append(v)
        for sid in net["sinks"]:
            s = pins[sid]
            hz, nv = state[(s["x"], s["y"], s["z"])]
            dist = abs(d["x"] - s["x"]) + abs(d["y"] - s["y"])
            costs = [via * (abs(d["z"] - k) + abs(k - s["z"])) + dist * ld[k] for k in range(L)]
            kstar = costs.index(min(costs))
            steps = sum(hz)
            rows.append(dict(
                tier=tier, case=case, net=net["id"], fanout=len(net["sinks"]), dist=dist,
                cross_die=d["z"] != s["z"], ideal=min(costs),
                actual=sum(h * ld[z] for z, h in enumerate(hz)) + via * nv,
                detour=cheapest * (steps - dist),
                layer=sum(h * (ld[z] - cheapest) for z, h in enumerate(hz))
                - dist * (ld[kstar] - cheapest),
                via=via * (nv - (abs(d["z"] - kstar) + abs(kstar - s["z"])))))
    util = [dict(tier=tier, case=case, z=z, util=sum(1 for v in used if v[2] == z) / (W * H))
            for z in range(L)]
    return rows, util


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", help="run dir (first seed is used)")
    ap.add_argument("--best-public", action="store_true",
                    help="use the best public route per case (reference_points.csv)")
    ap.add_argument("--cases", default="dev")
    ap.add_argument("--csv")
    args = ap.parse_args()
    if not args.run and not args.best_public:
        raise SystemExit("give --run DIR or --best-public")

    ref = pd.read_csv(os.path.join(STATE, "reference_points.csv")).set_index(["tier", "case"])
    sinks, utils = [], []
    for tier, cases in select_cases(args.cases).items():
        for case in cases:
            if args.best_public:
                entry = ref.loc[(tier, case), "best_public_entry"]
                sol_path = os.path.join(REPO, "submissions", tier, entry, f"{case}.sol.json")
            else:
                sol_path = os.path.join(seed_dirs(args.run)[0], tier, f"{case}.sol.json")
            if not os.path.exists(sol_path):
                print(f"skip {tier}/{case}: no route file")
                continue
            rows, util = sink_rows(tier, case, load_json(instance_path(tier, case)),
                                   load_json(sol_path))
            sinks += rows
            utils += util

    df = pd.DataFrame(sinks)
    df["excess"] = df["actual"] - df["ideal"]
    assert (df["excess"] == df["detour"] + df["layer"] + df["via"]).all()
    if args.csv:
        df.to_csv(args.csv, index=False)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", None)

    tot = df.groupby("tier")[["ideal", "excess", "layer", "detour", "via"]].sum()
    for c in ["layer", "detour", "via"]:
        tot[f"{c}_share_%"] = 100 * tot[c] / tot["excess"]
    tot["excess_over_ideal_%"] = 100 * tot["excess"] / tot["ideal"]
    print("== excess by cause\n", tot.round(1).to_string())

    df["sinks_per_net"] = pd.cut(df["fanout"], [0, 1, 2, 4, 8, 10_000],
                                 labels=["1", "2", "3-4", "5-8", "9+"])
    df["distance"] = pd.cut(df["dist"], [-1, 2, 5, 10, 20, 10_000],
                            labels=["0-2", "3-5", "6-10", "11-20", "21+"])
    for col in ["sinks_per_net", "distance"]:
        g = df.groupby(["tier", col], observed=True).agg(
            sinks=("excess", "size"), ideal=("ideal", "sum"), excess=("excess", "sum"))
        g["share_of_sinks_%"] = 100 * g["sinks"] / g.groupby(level="tier")["sinks"].transform("sum")
        g["share_of_excess_%"] = 100 * g["excess"] / g.groupby(level="tier")["excess"].transform("sum")
        g["excess_over_ideal_%"] = 100 * g["excess"] / g["ideal"]
        print(f"\n== by {col}\n", g.round(1).to_string())

    print("\n== concentration (share of sinks carrying 50% / 80% of the excess)")
    for tier, g in df.groupby("tier"):
        g = g.sort_values("excess", ascending=False)
        share = g["excess"].cumsum() / max(g["excess"].sum(), 1)
        print(f"  {tier}: {100 * (share < 0.5).mean():.1f}% / {100 * (share < 0.8).mean():.1f}%"
              f"   sinks at their ideal: {100 * (g['excess'] == 0).mean():.1f}%")

    lay = pd.DataFrame(utils).groupby(["tier", "z"])["util"].mean().unstack("z")
    print("\n== grid points used per layer, % (mean over cases)\n", (100 * lay).round(1).to_string())


if __name__ == "__main__":
    main()
