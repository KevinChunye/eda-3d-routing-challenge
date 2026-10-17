# Jiangbanya v3

v2 plus three search-dynamics changes that were each small alone and reinforced each other
in combination (exp-019..025): random equal-delay ties in exact reroutes, threshold
acceptance with kicks and return to the best solution, and cheaper group moves (A* for
single-sink nets, rerouting only conflicting nets after the first negotiation round).
Threads sync every 10 s.

Checker scores, one timed run per case, seed 1, 4 threads, Intel Xeon @ 2.10 GHz (4 vCPU),
16 GB, the same per-case limits as v1 and v2 (60 s hard, 300 s congested and designs):

| tier | v1 | v2 | **v3** | v3 vs v2 | total delay (v3) | total runtime | legal |
|---|---:|---:|---:|---:|---:|---:|:---:|
| hard | 1.3303 | 1.3368 | **1.3471** | +0.77% | 149,777 | 531 s | 9/9 |
| congested | 1.2367 | 1.2490 | **1.2644** | +1.23% | 511,923 | 1,196 s | 4/4 |
| designs | 1.3685 | 1.3744 | **1.3853** | +0.79% | 217,425 | 897 s | 3/3 |

Per case v3 beats v2 on 13 of 16 cases (mean r +0.89%); hard case_05 (−0.06%), case_06
(−0.41%) and designs int2float (−0.09%) are slightly worse. Ranks on the current board stay
hard 8, congested 7, designs 7; among entries that report runtime, hard 1st, congested and
designs 3rd.

- Router commit: `404e0c0` on `m3d_research`.
- Command: `m3d_route --threads 4 --set lns=1 --set gneg=6 --set lns_k=6 --set fan_alpha=0.3
  --set lns_mix=1 --set tie_rand=1 --set ta_t0=8 --set kick_after=300 --set restore_after=2000
  --set gneg_sel=1 --set astar=1 --set par_sync=10`
- Timed run: `research/tools/run_router.py --label submit-v3-20261017 --jobs 1 --threads 4`.

## How v3 was chosen (dev set, 30 s/case, seeds 1–3)

| step | change | mean r | cases better |
|---|---|---:|---:|
| exp-014 | random equal-delay ties (vs cached base) | +0.35% | 10/11 |
| exp-018 | unchanged incumbent rerun (null test) vs cached base | +0.15% | 9/11 |
| exp-019 | ties + escape (vs fresh base) | +0.66% | 11/11 |
| exp-022 | ties + escape + cheap moves (vs fresh base) | +0.91% | 8/11 |
| exp-024 | same on 4 threads, sync 2 s (vs fresh v2) | +0.83% | 10/11 |
| exp-025 | same, sync 10 s (vs fresh v2) | +0.90% | 9/11 |
| exp-026 | v3 at 300 s vs 60 s, hard case_01/05/09 | +0.14% | 2/3 |

Rejected this round: deeper group moves (−0.21%), slower initial negotiation (−0.01%);
noise-level: operator-selector fix (+0.07%), big-grid escalation (+0.09%).

## Files

- `submission.tar.gz`: `submissions/{hard,congested,designs}/Jiangbanya/` with the route
  files, the unchanged `runtime.json` from the timed run, and `meta.json` (threads 4, commit
  404e0c0). Extract from the repo root on the submission branch.
- `run_hard_case01.gif`: one 60 s run of hard case_01 with the v3 settings, saving snapshots:
  legal after 1.3 s at 10,006, 8,786 at 59 s (v2's demo run ended at 8,924, v1's at 8,908).
  The submitted v3 case_01 is 8,822.
- `layers_hard_case01.gif`: the submitted v3 hard case_01 routes, layer by layer.
