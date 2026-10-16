# Jiangbanya v2

v1 plus idea 5 from the 2026-10-16 trial of ideas 1–5: four search threads that each run the
neighborhood search with their own seed and, every 2 s, all adopt the best solution. Picked
because it had the largest measured gain (exp-012: +0.82% mean r over v1's settings on the
dev set, better on 11/11 cases).

Checker scores, one timed run per case, seed 1, **4 threads**, Intel Xeon @ 2.10 GHz
(4 vCPU), 16 GB, same per-case limits as v1:

| tier | v2 score | v1 score | change | total delay (v2) | total runtime | legal |
|---|---:|---:|---:|---:|---:|:---:|
| hard | 1.3368 | 1.3303 | +0.49% | 150,909 | 531 s (60 s/case) | 9/9 |
| congested | 1.2490 | 1.2367 | +0.99% | 518,395 | 1,197 s (300 s/case) | 4/4 |
| designs | 1.3744 | 1.3685 | +0.43% | 218,717 | 897 s (300 s/case) | 3/3 |

Per case, v2 beats v1 on 14 of 16 cases (mean r +0.61%); hard case_03 (−0.09%) and case_04
(−1.09%) are slightly worse. Ranks on the current board stay hard 8, congested 7, designs 7
with higher scores; among entries that report runtime: hard 1st, congested 3rd, designs 3rd.

- Router commit: `a235bf8` on `m3d_research`.
- Command: `m3d_route --threads 4 --set lns=1 --set gneg=6 --set lns_k=6 --set fan_alpha=0.3 --set lns_mix=1`
- Timed run: `research/tools/run_router.py --label submit-v2-20261016 --jobs 1 --threads 4`
  (one case at a time, otherwise idle machine).

## Ideas 1–5: predicted vs measured (30 s/case, seeds 1–3, vs v1 settings)

| idea | predicted | measured mean r | cases better | decision |
|---|---:|---:|---:|---|
| 1 sink-by-sink negotiated trees | +2–3% | −0.12% | 6/11 | reject |
| 2 space-saving tie-break | +1–2% | +0.03% | 5/11 | inconclusive |
| 3 threshold acceptance + kicks + return to best | ~0 (30 s), +1–2% (300 s) | +0.36% (+0.75% at 300 s) | 10/11 | adopt |
| 4 cheaper group moves (gneg_sel + A*) | +0.5–1% | +0.36% | 6/11 | inconclusive |
| **5 four threads** | +1–1.5% | **+0.82%** | 11/11 | **adopt → v2** |

## Files

- `submission.tar.gz`: `submissions/{hard,congested,designs}/Jiangbanya/` with route files,
  the unchanged `runtime.json` from the timed run and `meta.json` (threads 4, commit a235bf8).
  Extract from the repo root on the submission branch.
- `run_hard_case01.gif`: one 60 s run of hard case_01 with the v2 settings, saving snapshots
  (legal after 1.6 s at 9,872; 8,924 at 59 s). Threaded runs differ from run to run; this demo
  run ended slightly above v1's demo (8,908), while the submitted v2 case_01 is 8,832 (v1 8,872).
- `layers_hard_case01.gif`: the submitted v2 hard case_01 routes, layer by layer.
