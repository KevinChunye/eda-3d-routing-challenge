# STATE

Read this first in every session; update it last. Keep it short: it is the handoff note
between sessions on possibly different machines.

## Next action
1. In progress (2026-10-17): Jiangbanya v4 timed run, router 457c4df, 4 threads, one case at
   a time. hard done (`research/runs/submit-v4-hard-20261017`, 600 s/case, aggregate 1.3786,
   +2.31% vs v3, 9/9 better). congested (1,800 s/case) and designs (1,800 s/case) restarted
   23:01 UTC after a container restart killed the first attempt; script
   `/tmp/claude-0/submit4.sh` (skips finished tiers). Then: package with
   `package_submission.py --tier-runs`, GIFs, `research/models/jiangbanya_v4/`, Kevin's
   commands (exp-035).
2. Then the re-ranked v5 plan at the top of `research/state/next_moves.md` (2026-10-18):
   apply `research/patches/s1_neg_int.patch` and evaluate S1 with a tier-balanced verdict
   (S2), then S3 ejection chains, then E1 merge. Route-pool set packing is rejected.

## Entry config (used by 40_submit; Kevin may edit)
- entry_name: `Jiangbanya` (renamed from kevin_toll_lns by Kevin 2026-10-16; one directory per distinct method)
- author: `Kevin Wang (KevinChunye)`
- code_url: `https://github.com/KevinChunye/eda-3d-routing-challenge/tree/m3d_research/router`
  (40_submit pins it to the frozen commit)
- tiers_to_submit: hard, congested, designs first; intro, scale, stress once runtime is good
- time_limit_s per case (submission): hard 60, congested 300, designs 300, intro 30,
  scale 120, stress 1800 (revisit after Phase B)
- threads per case: 4 since v2 (report it); dev runs for threaded candidates use --jobs 1

## Dev protocol
- dev set: `research/state/dev_set.json` (hard ×9, congested case_01, designs ctrl)
- budget: 30 s per case; seeds 1 2 3; `--jobs` = number of cores
- incumbent run cache: `research/runs/incumbent/` (gitignored; rebuild on a new machine)

## Incumbent
- Jiangbanya v3 (exp-025 settings): router sha 404e0c0, `--threads 4` plus
  `--set lns=1 --set gneg=6 --set lns_k=6 --set fan_alpha=0.3 --set lns_mix=1 --set tie_rand=1
  --set ta_t0=8 --set kick_after=300 --set restore_after=2000 --set gneg_sel=1 --set astar=1
  --set par_sync=10`
- dev @30 s, seeds 1-3, --jobs 1: +0.90% mean r vs fresh v2 (exp-023), 9/11; dev run cache:
  `research/runs/exp-025`
- timed submission run: hard 1.3471, congested 1.2644, designs 1.3853 (v2: 1.3368, 1.2490, 1.3744)
- model cards: `research/models/jiangbanya_v1/`, `jiangbanya_v2/`, `jiangbanya_v3/`

## Machine log
- (00_bootstrap appends: date, CPU model, logical CPUs, RAM, dial_bench µs/search)
- 2026-10-16 · claude-code cloud VM · Intel Xeon @ 2.10GHz · 4 logical CPUs · 15 GB RAM · dial_bench 40×40×6: 138 µs, 105×105×6: 600 µs

## Submitted
- v1 (2026-10-16): PR #63 from `submit_jiangbanya_20261016`, router 2b51d4c, 1 thread · hard
  1.3303, congested 1.2367, designs 1.3685 · `research/models/jiangbanya_v1/`
- v2 (2026-10-16): router a235bf8, 4 threads · hard 1.3368, congested 1.2490, designs 1.3744 ·
  `research/models/jiangbanya_v2/` (Kevin pushes)
- v3 (2026-10-17): router 404e0c0, 4 threads · hard 1.3471, congested 1.2644, designs 1.3853 ·
  `research/models/jiangbanya_v3/` (Kevin pushes)

## Open questions for Kevin
- The tag `entry-kevin_toll_lns-20261016` could not be pushed (git proxy refused tags);
  meta.json pins the commit, so it is optional.
- Fork is public: research commits are visible. Move router work to a private repo?
