# Jiangbanya v5, sparse tiers (intro, scale, stress)

Jiangbanya v4's hard-tier search plus S1 (integer, goal-directed negotiated searches; exact
trees at commit), run on the tiers v1–v4 never submitted. Checker scores, one timed run per
case, seed 1, 4 threads, Intel Xeon @ 2.10 GHz (4 vCPU), 16 GB, one case at a time:

| tier | v5 | target (rank among entries reporting runtime) | rank | total delay | budget per case | total runtime | legal |
|---|---:|---|---:|---:|---:|---:|:---:|
| intro | **1.1406** | > 1.1254 for #2 (1.1514 for #1) | 2 | 347,104 | 60 s | 1,122 s | 20/20 |
| scale | **1.1152** | > 1.1010 for #3 | 3 | 544,138 | 300 s | 2,393 s | 8/8 |
| stress | **1.0798** | any legal run for #3 | 3 | 1,060,258 | 2,400 s | 2,399 s | 1/1 |

Entries reporting runtime on these tiers: intro pathfinder_lns 1.1514 (46,477 s), iamparv7043
1.1254 (2,214 s); scale pathfinder_lns 1.1277 (62,411 s), warm_lns_refinement 1.1274 (7,543 s,
derived), iamparv7043 1.1010 (3,095 s); stress pathfinder_lns 1.0914 (43,263 s),
warm_lns_refinement 1.0911 (2,070 s, derived).

- Router commit: `858a703` on `m3d_research`.
- Flags (all three tiers): `--threads 4 --set lns=1 --set gneg=6 --set lns_k=6 --set fan_alpha=0.3
  --set lns_mix=1 --set tie_rand=1 --set ta_t0=32 --set kick_after=300 --set restore_after=2000
  --set gneg_sel=1 --set astar=1 --set par_sync=120 --set bandit=1 --set neg_int=4 --set neg_goal=1.5`
- stress adds `--set refine_stop=0.01 --set deadline_guard=3`.
- Timed runs: `research/tools/run_router.py --label submit-v5-<tier>-20261018 --jobs 1 --threads 4`.

## How it was chosen (exp-040, exp-042)

- Screen (exp-040, seed 1): intro case_13–20 at 60 s beat iamparv7043 on 8/8 (+2.31%) and
  trail pathfinder_lns on 8/8 (−1.56%); scale case_01/08 at 300 s beat iamparv7043 (+1.34%,
  +1.30%) and trail pathfinder_lns (−0.59%, −1.63%).
- Stress probe (exp-042, 2,400 s limit): S1 makes a negotiation round take ~33 s instead of
  ~180 s; first legal solution at 1,025 s (32 rounds; the escalation at 35% of the run
  closes it in 7 rounds), leaving 57% of the run after legality. The exact-reroute sweeps
  that follow kept improving 2–5 nets per 21 s sweep until 1,922 s, so `refine_stop=0.01`
  ends them once fewer than 1% of nets improve. The probe ended at 2,399.2 s: the deadline
  overshoot of the 2026-10-16 readiness run (+49 s) is gone (the congestion-free pass now
  stops at the deadline; `deadline_guard=3` keeps 1.6–2.1 s moves from crossing it).

The timed stress run ended at 2,399.4 s (first legal 1,025 s). It is 0.09% worse than the
probe (1,059,256 with sweeps run to exhaustion): on stress, cutting the sweeps short did not
pay; moves cost 1.6–2.1 s each there and gain little.

## Files

- `submission_intro.tar.gz`, `submission_scale.tar.gz`, `submission_stress.tar.gz`:
  `submissions/<tier>/Jiangbanya/` with the route files, the unchanged `runtime.json` of the
  timed run and `meta.json` (threads 4, commit 858a703). Extract from the repo root on the
  submission branch.
