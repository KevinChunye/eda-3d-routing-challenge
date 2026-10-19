# Jiangbanya v5, long runs (designs, congested)

v4's search with the changes measured since, run longer. Checker scores, one timed run per
case, seed 1, 4 threads, Intel Xeon @ 2.10 GHz (4 vCPU), 16 GB, one case at a time, on the
cloud VM:

| tier | v4 | **v5** | v5 vs v4 | cases better | total delay | budget | total runtime | legal |
|---|---:|---:|---:|---:|---:|---|---:|:---:|
| designs | 1.4150 | **1.4331** | +1.27% | 3/3 | 209,767 | 3,600 s per case | 10,797 s | 3/3 |
| congested | 1.3034 | CONG_SCORE | CONG_R | CONG_BETTER | CONG_DELAY | 28,800 s split by net count | CONG_RT | CONG_LEGAL |

"v5 vs v4" = mean over cases of log(v4 delay / v5 delay).

Standing among entries that report runtime: designs pathfinder_lns 1.435356 (47,268 s),
warm_lns_refinement 1.433138 (3,615 s, derived), **Jiangbanya 1.433055** → #3, 0.006% behind
#2 and 0.16% behind #1. CONG_STANDING

- designs: router `858a703`, v3 base flags + `--set neg_int=4 --set neg_goal=1.5 --set par_sync=600`,
  `--time-limit 3600` (exp-045). Per case vs v4: ctrl +1.56%, int2float +1.34%, router +0.89%.
- congested: router `94e4fbc`, v4 congested flags (v3 base + `--set ta_t0=32 --set bandit=1`) +
  `--set par_sync_frac=0.2`; `run_router.py --time-total '{"congested": 28800}'` gives
  case_01..04 4,838.9 / 6,675.3 / 8,482.6 / 8,803.2 s (166 / 229 / 291 / 302 nets); the formula
  is in meta.json as `time_limit_policy` (exp-046).
- v3 base flags: `--threads 4 --set lns=1 --set gneg=6 --set lns_k=6 --set fan_alpha=0.3
  --set lns_mix=1 --set tie_rand=1 --set ta_t0=8 --set kick_after=300 --set restore_after=2000
  --set gneg_sel=1 --set astar=1 --set par_sync=10` (later `--set` values override earlier ones).

## Why these settings (measured)

- S1 (integer, goal-directed negotiation): designs +0.64% at 1,800 s, 4 threads (exp-038);
  no gain on congested at that budget (−0.18%), so congested runs without it.
- Threads syncing every 600 s instead of 10 s on designs with S1: +0.41% / +0.51% (exp-044).
- More time: about +0.3–0.6% per doubling (findings 2026-10-19); designs 1,800 → 3,600 s with
  the same settings: ctrl +0.46%, int2float +0.26%.

## Files

- `submission_designs.tar.gz`, `submission_congested.tar.gz`: `submissions/<tier>/Jiangbanya/`
  with the route files, the unchanged `runtime.json` of the timed run and `meta.json`.
  Extract from the repo root on the submission branch.
