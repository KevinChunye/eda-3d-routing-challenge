# Jiangbanya v4

v3's router with a different search policy and longer budgets: accept worse group moves
more freely early in the run and cool to 0 by the end (threshold 32 instead of 8), let a
discounted bandit choose among five move types, and let threads explore for a fifth of the
run before they sync to the best (instead of every 10 s). Designs keeps v3's search, with a
longer budget. Settings are per tier (the rules allow one config per tier).

Checker scores, one timed run per case, seed 1, 4 threads, Intel Xeon @ 2.10 GHz
(4 vCPU), 16 GB, one case at a time:

| tier | v3 | **v4** | v4 vs v3 | cases better | total delay (v4) | budget per case | total runtime | legal |
|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| hard | 1.3471 | **1.3786** | +2.31% | 9/9 | 146,057 | 600 s (v3 60 s) | 5,391 s | 9/9 |
| congested | 1.2644 | **1.3034** | +3.04% | 4/4 | 495,581 | 1,800 s (v3 300 s) | 7,196 s | 4/4 |
| designs | 1.3853 | **1.4150** | +2.13% | 3/3 | 212,397 | 1,800 s (v3 300 s) | 5,397 s | 3/3 |

"v4 vs v3" is the mean over cases of log(v3 delay / v4 delay). v4 beats v3 on all 16
cases; mean over tiers +2.49%. Predicted before the run (exp-035): hard +1.0%, congested
+1.5%, designs +1.3%. Ranks on the current board: hard 7, congested 7, designs 7 (v3: 8, 7,
7); congested is 0.4% short of rank 6.

- Router commit: `457c4df` on `m3d_research`.
- Base flags (v3): `--threads 4 --set lns=1 --set gneg=6 --set lns_k=6 --set fan_alpha=0.3
  --set lns_mix=1 --set tie_rand=1 --set ta_t0=8 --set kick_after=300 --set restore_after=2000
  --set gneg_sel=1 --set astar=1 --set par_sync=10`
- hard: base + `--set ta_t0=32 --set bandit=1 --set par_sync=120`, `--time-limit 600`
- congested: base + `--set ta_t0=32 --set bandit=1 --set par_sync=360`, `--time-limit 1800`
- designs: base, `--time-limit 1800`
- Timed runs: `research/tools/run_router.py --label submit-v4-<tier>-20261017 --jobs 1
  --threads 4` per tier. The container restarted during the first congested attempt (no
  files kept); congested and designs were rerun from the start.

## How v4 was chosen (exp-027..035)

Kevin's brief: a step that is worse now can pay later; explore early and exploit late;
weight recent results more than old ones; tune at long budgets, because these methods only
show their second descent late.

| step | question | answer (checker numbers) |
|---|---|---|
| exp-027 | 16 acceptance / move-choice variants, 30 s | most within ±0.4%; late acceptance −4%; more exploration better |
| exp-028 | does it hold at long budgets? (1 thread) | threshold 16 + bandit beats v3 by +1.3% at 60 s and at 600 s |
| exp-029/030 | threshold height and schedule shape, 300 s | height 16–64 all +0.7–0.9%; shape, reheats, bandit memory: no gain |
| exp-031 | 4 threads, sync every 10 s | gain mostly gone (+0.14%): syncing cuts the walks off |
| exp-032 | designs at 1,800 s (1 thread) | high thresholds only catch up there (see `trace_designs_ctrl_1800s.png`); the budget itself gains 1.2–1.4% |
| exp-033/034 | sync every 60 / 150 s | +0.6–0.8% vs v3 at 300 s; any sync between a fifth and half of the run works |

## Files

- `submission.tar.gz`: `submissions/{hard,congested,designs}/Jiangbanya/` with the route
  files, the unchanged `runtime.json` of each timed run and `meta.json` (threads 4, commit
  457c4df). Extract from the repo root on the submission branch.
- `trace_designs_ctrl_1800s.png`: the second descent. Designs ctrl, 1 thread, 1,800 s,
  threshold 8 (v3) vs 16 and 32: higher thresholds wander above their start, then fall
  steeply as the threshold cools to 0.
- `surge_congested_case04.png`: v3 routes on congested case_04, 8×8 tiles: demand for the
  fast layers piles up in the centre, where no fast point is free; corners keep 30–50% free.
- `layers_hard_case01.gif`: the submitted v4 hard case_01 routes, layer by layer.
