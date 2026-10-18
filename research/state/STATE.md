# STATE

Read this first in every session; update it last. Keep it short: it is the handoff note
between sessions on possibly different machines.

## Next action
1. Done 2026-10-18: Jiangbanya v4 scored, packaged and documented
   (`research/models/jiangbanya_v4/`: README, submission.tar.gz, GIF, plots). Kevin
   replaces PR #63's files with it himself (no submission branch work here).
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
- Jiangbanya v4 (exp-035): router sha 457c4df, `--threads 4`, per-tier settings:
  base = v3 flags (below); hard base + `--set ta_t0=32 --set bandit=1 --set par_sync=120` at
  600 s; congested base + `--set ta_t0=32 --set bandit=1 --set par_sync=360` at 1,800 s;
  designs base at 1,800 s.
- timed run: hard 1.3786, congested 1.3034, designs 1.4150 (v3: 1.3471, 1.2644, 1.3853);
  16/16 cases better; runs `research/runs/submit-v4-{hard,congested,designs}-20261017`.
- v3 flags: `--set lns=1 --set gneg=6 --set lns_k=6 --set fan_alpha=0.3 --set lns_mix=1
  --set tie_rand=1 --set ta_t0=8 --set kick_after=300 --set restore_after=2000 --set gneg_sel=1
  --set astar=1 --set par_sync=10` (router 404e0c0 for v3 itself).
- model cards: `research/models/jiangbanya_v1/` … `jiangbanya_v4/`

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
- v4 (2026-10-18, prepared): router 457c4df, 4 threads, 600/1,800/1,800 s · hard 1.3786,
  congested 1.3034, designs 1.4150 · `research/models/jiangbanya_v4/` (Kevin pushes)

## Open questions for Kevin
- The tag `entry-kevin_toll_lns-20261016` could not be pushed (git proxy refused tags);
  meta.json pins the commit, so it is optional.
- Fork is public: research commits are visible. Move router work to a private repo?
