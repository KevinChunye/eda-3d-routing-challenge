"""Who blocks whom? Structure of the excess delay in a routing, for designing new moves.

Terms (per case, our own route files only):
  ideal(sink)     cheapest driver-to-sink delay on an empty grid (other nets ignored)
  excess(sink)    actual path delay in the net's tree - ideal(sink)
  corridor(sink)  grid points on at least one cheapest empty-grid path from the driver to
                  the sink: dist(driver, v) + dist(v, sink) == ideal(sink)
  blocker         another net that occupies a corridor point of a sink with excess > 0
  fast            the two middle layers (step delay 2)

Reported per case:
  conc50/conc80   share of nets that carry 50% / 80% of the excess
  blk_med         median number of distinct blocker nets per sink with excess
  blk_le2         share of the excess on sinks with at most 2 blockers in the whole corridor
  path_blk        distinct nets on the least-obstructed cheapest path (fewest points owned by
                  other nets; ties broken arbitrarily): how many nets a move must reroute to
                  give the sink its ideal delay. path_le1 / path_le3 / path_le5 = share of the
                  excess on sinks with at most 1 / 3 / 5 such nets
  blk_ideal       share of blocker incidences where the blocker itself has no excess
  mutual          share of the excess on sinks whose net and some blocker block each other
                  (an exchange move could help both)
  comp_n, comp_max  connected groups of the blocking graph (nets with excess + blockers);
                  comp_max = largest group as a share of all nets
  comp_area       bounding box of the largest group as a share of the grid area
  hot10           share of the excess (spread over corridor points) inside the hottest 10%
                  of 8x8 tiles: how local the trouble is

Usage (from repo root):
  python3 research/tools/conflict_map.py --run research/runs/submit-v3-20261017 \
      --cases hard+congested+designs --csv research/state/conflict_map_v3.csv
"""
import argparse
import os
from collections import deque

import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components, dijkstra

from common import instance_path, load_json, seed_dirs, select_cases


def grid_graph(W, H, L, ld, via):
    idx = np.arange(W * H * L).reshape(L, H, W)
    rows, cols, wts = [], [], []
    for z in range(L):
        a, b = idx[z, :, :-1].ravel(), idx[z, :, 1:].ravel()
        rows += [a, b]; cols += [b, a]; wts += [np.full(a.size, ld[z])] * 2
        a, b = idx[z, :-1, :].ravel(), idx[z, 1:, :].ravel()
        rows += [a, b]; cols += [b, a]; wts += [np.full(a.size, ld[z])] * 2
    for z in range(L - 1):
        a, b = idx[z].ravel(), idx[z + 1].ravel()
        rows += [a, b]; cols += [b, a]; wts += [np.full(a.size, via)] * 2
    n = W * H * L
    return coo_matrix((np.concatenate(wts).astype(float), (np.concatenate(rows), np.concatenate(cols))),
                      shape=(n, n)).tocsr()


def tree_delays(edges, root, ld, via):
    adj = {}
    for u, v in edges:
        u, v = tuple(u), tuple(v)
        for a, b in ((u, v), (v, u)):
            if a not in adj:
                adj[a] = []
            adj[a].append(b)
    dist = {root: 0}
    q = deque([root])
    while q:
        u = q.popleft()
        for v in adj.get(u, []):
            if v not in dist:
                dist[v] = dist[u] + (ld[u[2]] if v[2] == u[2] else via)
                q.append(v)
    return dist


def path_blockers(corr, dD, owner, nid, sink_v, W, H, L, ld, via):
    """0-1 BFS over tight corridor edges from the driver side (dD == 0) to the sink, with
    cost 1 for entering a point owned by another net; returns the distinct owners on it."""
    inside = np.zeros(W * H * L, bool)
    inside[corr] = True
    src = corr[dD[corr] == 0][0]
    cost = {src: 0}
    prev = {src: -1}
    dq = deque([src])
    plane = W * H
    while dq:
        u = dq.popleft()
        z, rem = divmod(u, plane)
        y, x = divmod(rem, W)
        for v, w in ((u - 1, ld[z]) if x > 0 else (-1, 0), (u + 1, ld[z]) if x < W - 1 else (-1, 0),
                     (u - W, ld[z]) if y > 0 else (-1, 0), (u + W, ld[z]) if y < H - 1 else (-1, 0),
                     (u - plane, via) if z > 0 else (-1, 0), (u + plane, via) if z < L - 1 else (-1, 0)):
            if v < 0 or not inside[v] or dD[v] != dD[u] + w:
                continue
            c = cost[u] + (1 if owner[v] not in (-1, nid) else 0)
            if v not in cost or c < cost[v]:
                cost[v] = c
                prev[v] = u
                if c == cost[u]:
                    dq.appendleft(v)
                else:
                    dq.append(v)
    owners, v = set(), sink_v
    while v != -1:
        if owner[v] not in (-1, nid):
            owners.add(int(owner[v]))
        v = prev.get(v, -1)
    return len(owners)


def analyze(tier, case, inst, sol):
    W, H, L = inst["grid"]["width"], inst["grid"]["height"], inst["grid"]["layers"]
    ld, via = inst["delay"]["layer_delay"], inst["delay"]["via_delay"]
    graph = grid_graph(W, H, L, ld, via)
    vid = lambda p: (p[2] * H + p[1]) * W + p[0]  # noqa: E731
    pins = {p["id"]: p for p in inst["pins"]}
    nets = {n["id"]: n for n in inst["nets"]}
    owner = np.full(W * H * L, -1)
    routes = {r["net"]: r for r in sol["routes"]}
    for nid, r in routes.items():
        for u, v in r["edges"]:
            owner[vid(u)] = nid
            owner[vid(v)] = nid

    sink_rows, inc_rows = [], []
    heat = np.zeros((H, W))
    for nid, net in nets.items():
        d = pins[net["driver"]]
        root = (d["x"], d["y"], d["z"])
        dD = dijkstra(graph, indices=vid(root))
        actual = tree_delays(routes[nid]["edges"], root, ld, via)
        for sid in net["sinks"]:
            s = pins[sid]
            sp = (s["x"], s["y"], s["z"])
            ideal = dD[vid(sp)]
            exc = actual[sp] - ideal
            sink_rows.append(dict(net=nid, sink=sid, ideal=ideal, excess=exc))
            if exc <= 0:
                continue
            dS = dijkstra(graph, indices=vid(sp))
            corr = np.flatnonzero(np.abs(dD + dS - ideal) < 1e-9)
            blockers = set(owner[corr]) - {-1, nid}
            z = corr // (W * H)
            fast_blockers = set(owner[corr[(z == 2) | (z == 3)]]) - {-1, nid}
            yx = corr % (W * H)
            np.add.at(heat, (yx // W, yx % W), exc / corr.size)
            pb = path_blockers(corr, dD, owner, nid, vid(sp), W, H, L, ld, via)
            sink_rows[-1].update(blockers=len(blockers), fast_blockers=len(fast_blockers),
                                 corridor=corr.size, path_blk=pb)
            for m in blockers:
                inc_rows.append(dict(net=nid, sink=sid, excess=exc, blocker=int(m)))

    sinks = pd.DataFrame(sink_rows)
    inc = pd.DataFrame(inc_rows, columns=["net", "sink", "excess", "blocker"])
    net_exc = sinks.groupby("net")["excess"].sum()
    total = net_exc.sum()
    srt = net_exc.sort_values(ascending=False)
    share = srt.cumsum() / max(total, 1)
    exc_sinks = sinks[sinks.excess > 0]

    pairs = set(zip(inc["net"], inc["blocker"]))
    inc["mutual"] = [(b, n) in pairs for n, b in zip(inc["net"], inc["blocker"])]
    mutual_sinks = inc[inc.mutual].drop_duplicates("sink")
    inc["blocker_ideal"] = inc["blocker"].map(net_exc).fillna(0) <= 0

    ids = sorted(nets)
    pos = {n: i for i, n in enumerate(ids)}
    if len(inc):
        g = coo_matrix((np.ones(len(inc)), ([pos[n] for n in inc.net], [pos[b] for b in inc.blocker])),
                       shape=(len(ids), len(ids)))
        ncomp, lab = connected_components(g, directed=False)
        involved = set(inc.net) | set(inc.blocker)
        sizes = pd.Series([lab[pos[n]] for n in involved]).value_counts()
        big = sizes.index[0]
        members = [n for n in involved if lab[pos[n]] == big]
        xs, ys = [], []
        for n in members:
            for u, v in routes[n]["edges"]:
                xs += [u[0], v[0]]; ys += [u[1], v[1]]
        comp_area = (max(xs) - min(xs) + 1) * (max(ys) - min(ys) + 1) / (W * H)
        comp_n, comp_max = len(sizes), sizes.iloc[0] / len(ids)
    else:
        comp_n, comp_max, comp_area = 0, 0.0, 0.0
    t = 8
    tiles = np.add.reduceat(np.add.reduceat(heat, np.arange(0, H, t), axis=0), np.arange(0, W, t), axis=1).ravel()
    tiles = np.sort(tiles)[::-1]
    hot10 = tiles[:max(1, int(np.ceil(0.1 * tiles.size)))].sum() / max(tiles.sum(), 1e-9)
    fast = np.isin(np.arange(W * H * L) // (W * H), [2, 3])
    return dict(
        tier=tier, case=case, nets=len(ids), sinks=len(sinks), excess_pct=100 * total / sinks.ideal.sum(),
        conc50=(share < 0.5).mean() * len(srt) / len(ids), conc80=(share < 0.8).mean() * len(srt) / len(ids),
        blk_med=exc_sinks.blockers.median(), fast_blk_med=exc_sinks.fast_blockers.median(),
        blk_le2=exc_sinks.loc[exc_sinks.blockers <= 2, "excess"].sum() / total,
        path_med=exc_sinks.path_blk.median(),
        path_le1=exc_sinks.loc[exc_sinks.path_blk <= 1, "excess"].sum() / total,
        path_le3=exc_sinks.loc[exc_sinks.path_blk <= 3, "excess"].sum() / total,
        path_le5=exc_sinks.loc[exc_sinks.path_blk <= 5, "excess"].sum() / total,
        blk_ideal=inc.blocker_ideal.mean() if len(inc) else np.nan,
        mutual=mutual_sinks.excess.sum() / total if len(inc) else 0.0,
        comp_n=comp_n, comp_max=comp_max, comp_area=comp_area, hot10=hot10,
        fast_used=(owner[fast] >= 0).mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--cases", default="dev")
    ap.add_argument("--csv")
    args = ap.parse_args()
    rows = []
    for tier, cases in select_cases(args.cases).items():
        for case in cases:
            sol_path = os.path.join(seed_dirs(args.run)[0], tier, f"{case}.sol.json")
            if not os.path.exists(sol_path):
                continue
            rows.append(analyze(tier, case, load_json(instance_path(tier, case)), load_json(sol_path)))
            print(f"{tier}/{case} done", flush=True)
    df = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", None)
    print(df.round(3).to_string(index=False))
    print("\nby tier (mean):")
    print(df.drop(columns="case").groupby("tier").mean().round(3).to_string())
    if args.csv:
        df.to_csv(args.csv, index=False)


if __name__ == "__main__":
    main()
