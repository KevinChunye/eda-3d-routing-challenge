"""Congestion-aware lower bound via Lagrangian relaxation (method tag: avg-toll-v1).

Usage (from repo root):
  python research/tools/lagrange_bound.py --cases hard --jobs 8
  python research/tools/lagrange_bound.py --cases congested:case_01+designs:ctrl --jobs 2
Appends one JSON line per case to research/state/toll_bounds.jsonl; then re-run
reference_points.py so evaluate.py uses the new bounds. Needs numpy + scipy.
Runtime: hard cases 1-4 min each; 64x64-77x77 cases 25-35 min each.

Rule relaxed: each grid point (vertex) may be used by at most one net.
Price it instead: lam[v] >= 0 is a toll on grid point v. For any tolls,
  L(lam) = sum_n h_n(lam) - sum_v lam[v]  <=  optimal total delay,
where h_n is a lower bound on net n's best "delay + tolls" tree:
  h_n = sum over its k sinks of  min_path [ delay(path) + tolls(path) / k ].
(Valid: a tree's tolls >= the average toll of its k driver->sink paths, since each
path lies inside the tree.) For 2-pin nets (k=1) h_n is exact.
Tolls are raised by subgradient ascent where nets overlap; every L(lam) seen is a
valid bound, so we keep the max.
"""
import argparse
import datetime
import json
import os
import time
from multiprocessing import Pool

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from common import STATE, instance_path, load_json, select_cases

PATIENCE = 40  # halve the step size after this many iterations without a new best bound


def build(inst):
    W, H, L = inst["grid"]["width"], inst["grid"]["height"], inst["grid"]["layers"]
    ld, via = inst["delay"]["layer_delay"], inst["delay"]["via_delay"]
    idx = np.arange(W * H * L).reshape(L, H, W)
    tails, heads, base = [], [], []
    for z in range(L):
        for a, b in [(idx[z, :, :-1], idx[z, :, 1:]), (idx[z, :-1, :], idx[z, 1:, :])]:
            a, b = a.ravel(), b.ravel()
            tails += [a, b]
            heads += [b, a]
            base += [np.full(2 * a.size, ld[z])]
    for z in range(L - 1):
        a, b = idx[z].ravel(), idx[z + 1].ravel()
        tails += [a, b]
        heads += [b, a]
        base += [np.full(2 * a.size, via)]
    tails, heads = np.concatenate(tails), np.concatenate(heads)
    base = np.concatenate(base).astype(float)
    order = np.lexsort((heads, tails))  # CSR row order, so data aligns with heads
    tails, heads, base = tails[order], heads[order], base[order]
    pins = {p["id"]: int(idx[p["z"], p["y"], p["x"]]) for p in inst["pins"]}
    nets = [(pins[n["driver"]], [pins[s] for s in n["sinks"]]) for n in inst["nets"]]
    return W * H * L, tails, heads, base, nets


def evaluate(nv, tails, heads, base, nets, lam):
    """Return L(lam) and the subgradient (weighted usage - 1)."""
    usage = np.zeros(nv)
    total = -lam.sum()
    by_k = {}  # nets grouped by sink count k: they share one toll scale 1/k
    for drv, sinks in nets:
        k = len(sinks)
        if k not in by_k:
            by_k[k] = []
        by_k[k].append((drv, sinks))
    for k, group in by_k.items():
        w = 1.0 / k
        g = csr_matrix((base + w * lam[heads], (tails, heads)), shape=(nv, nv))
        drivers = [d for d, _ in group]
        dist, pred = dijkstra(g, directed=True, indices=drivers, return_predecessors=True)
        for row, (drv, sinks) in enumerate(group):
            for s in sinks:
                total += dist[row, s] + w * lam[drv]
                v = s
                while v != drv:
                    usage[v] += w
                    v = pred[row, v]
                usage[drv] += w
    return total, usage - 1.0


def bound(inst, ub, iters=400, theta=1.0, verbose=False):
    nv, tails, heads, base, nets = build(inst)
    lam = np.zeros(nv)
    best, stall = -np.inf, 0
    t0 = time.time()
    for it in range(iters):
        val, g = evaluate(nv, tails, heads, base, nets, lam)
        if val > best + 1e-6:
            best, stall = val, 0
        else:
            stall += 1
            if stall >= PATIENCE:
                theta, stall = theta / 2, 0
        g = np.where((lam <= 0) & (g < 0), 0.0, g)  # projected direction
        gg = float(g @ g)
        if gg < 1e-12 or theta < 1e-5:
            break
        lam = np.maximum(0.0, lam + theta * (ub - val) / gg * g)
        if verbose and it % 25 == 0:
            print(f"  it {it:4d}  L={val:9.1f}  best={best:9.1f}  theta={theta:.4f}  {time.time()-t0:.0f}s", flush=True)
    return best, it + 1, time.time() - t0


def _one(job):
    tier, case, ub, iters = job
    inst = load_json(instance_path(tier, case))
    b, n, secs = bound(inst, ub, iters)
    return dict(tier=tier, case=case, lagrange_lb=round(b, 1), ub_used=ub,
                gap_to_ub_pct=round(100 * (ub / b - 1), 2), iters=n, secs=round(secs, 1),
                method="avg-toll-v1", date=datetime.date.today().isoformat())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="hard", help="dev | all | tier | tier:c1,c2 (join with +)")
    ap.add_argument("--iters", type=int, default=4000)
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    args = ap.parse_args()
    ref = pd.read_csv(os.path.join(STATE, "reference_points.csv")).set_index(["tier", "case"])
    jobs = []
    for tier, cases in select_cases(args.cases).items():
        for case in cases:
            r = ref.loc[(tier, case)]
            # any feasible total works as the step target; validity never depends on it
            ub = float(r["best_public"]) if pd.notna(r["best_public"]) else float(r["baseline"])
            jobs.append((tier, case, ub, args.iters))
    out = os.path.join(STATE, "toll_bounds.jsonl")
    with Pool(min(args.jobs, len(jobs))) as pool:
        for res in pool.imap_unordered(_one, jobs):
            print(json.dumps(res), flush=True)
            with open(out, "a") as fh:
                fh.write(json.dumps(res) + "\n")
