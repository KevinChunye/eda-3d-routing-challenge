"""Statistics from a router move log (router flag --set move_log=PATH), for next_moves.md.

Each log line: <s> <target> <type> <complete> <accepted> <delta> <x0> <y0> <x1> <y1> <k> <nets...>
(type 0 ideal-tree, 1 window, 2 kick; delta < 0 = better; box covers old and new routes).

Reported:
  improve rate by move type, and the share of all gain each type delivered
  conflict      share of accepted moves sharing a net with one of the previous 3 accepted
                moves: a lower bound on how often a concurrent shared-walk commit would fail
  box_conflict  same with overlapping boxes (an upper bound)
  quadrant      share of improving moves (and of their gain) whose box fits in one quadrant
  retry         improve rate of a target retried when no accepted move touched its last box
                since its last failure ("unchanged"), vs retried after a change

Usage: python3 research/tools/move_log_stats.py --log moves.txt --width 24 --height 24
"""
import argparse

import numpy as np
import pandas as pd


def load(path):
    rows = []
    for line in open(path):
        p = line.split()
        rows.append(dict(t=float(p[0]), target=int(p[1]), type=int(p[2]), complete=int(p[3]),
                         accepted=int(p[4]), delta=int(p[5]), x0=int(p[6]), y0=int(p[7]),
                         x1=int(p[8]), y1=int(p[9]), nets=frozenset(int(x) for x in p[11:])))
    return pd.DataFrame(rows)


def overlap(a, b):
    return a.x0 <= b.x1 and b.x0 <= a.x1 and a.y0 <= b.y1 and b.y0 <= a.y1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    ap.add_argument("--width", type=int, required=True)
    ap.add_argument("--height", type=int, required=True)
    args = ap.parse_args()
    df = load(args.log)
    df["improved"] = (df.accepted == 1) & (df.delta < 0)
    df["gain"] = np.where(df.improved, -df.delta, 0)
    by = df.groupby("type").agg(moves=("t", "size"), improve_rate=("improved", "mean"), gain=("gain", "sum"))
    by["gain_share"] = by.gain / max(by.gain.sum(), 1)
    print(f"{len(df)} moves, {df.improved.sum()} improving, total gain {df.gain.sum()}")
    print(by.round(4).to_string())

    acc = df[df.accepted == 1].reset_index(drop=True)
    net_hits = box_hits = 0
    for i in range(3, len(acc)):
        prev = acc.iloc[i - 3:i]
        net_hits += any(acc.nets[i] & s for s in prev.nets)
        box_hits += any(overlap(acc.iloc[i], prev.iloc[j]) for j in range(3))
    n = max(len(acc) - 3, 1)
    print(f"\nconflict (shares a net with one of the previous 3 accepted moves): {net_hits / n:.3f}")
    print(f"box_conflict (box overlaps one of the previous 3): {box_hits / n:.3f}")

    hx, hy = args.width / 2, args.height / 2
    imp = df[df.improved]
    fits = ((imp.x1 < hx) | (imp.x0 >= hx)) & ((imp.y1 < hy) | (imp.y0 >= hy))
    print(f"\nquadrant: {fits.mean():.3f} of improving moves, {imp.gain[fits].sum() / max(imp.gain.sum(), 1):.3f} of their gain")

    last_fail, accepted_boxes = {}, []
    retry = []
    for r in df.itertuples():
        if r.target in last_fail:
            idx, box = last_fail[r.target]
            changed = any(overlap(box, b) for b in accepted_boxes[idx:])
            retry.append(dict(changed=changed, improved=r.improved))
        if r.improved:
            last_fail.pop(r.target, None)
        else:
            last_fail[r.target] = (len(accepted_boxes), r)
        if r.accepted:
            accepted_boxes.append(r)
    rt = pd.DataFrame(retry)
    if len(rt):
        print("\nretry after a failed move (improve rate):")
        print(rt.groupby("changed").improved.agg(["size", "mean"]).round(4).to_string())


if __name__ == "__main__":
    main()
