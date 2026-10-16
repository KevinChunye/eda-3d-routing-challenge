# STATE

Read this first in every session; update it last. Keep it short: it is the handoff note
between sessions on possibly different machines.

## Next action
1. Kevin: replace PR #63's files with Jiangbanya v2 (`research/models/jiangbanya_v2/`,
   commands in its README's parent message) and update the PR description.
2. Then `research/prompts/10_iterate.md`. Next experiments: combine ideas 3 + 4 on top of v2;
   tier-aware idea 4 (large grids); faster legality on large grids (E3).

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
- exp-012 = Jiangbanya v2: router sha a235bf8, `--threads 4` plus
  `--set lns=1 --set gneg=6 --set lns_k=6 --set fan_alpha=0.3 --set lns_mix=1`
- dev @30 s, seeds 1-3 (run with --jobs 1): mean r +0.82% over exp-007, 11/11 cases
- timed submission run: hard 1.3368, congested 1.2490, designs 1.3744 (v1: 1.3303, 1.2367, 1.3685)
- also adopted but not in v2: exp-010 (threshold + kick + return to best, +0.36%)
- model cards with animations and submission tarballs: `research/models/jiangbanya_v1/`, `jiangbanya_v2/`

## Machine log
- (00_bootstrap appends: date, CPU model, logical CPUs, RAM, dial_bench µs/search)
- 2026-10-16 · claude-code cloud VM · Intel Xeon @ 2.10GHz · 4 logical CPUs · 15 GB RAM · dial_bench 40×40×6: 138 µs, 105×105×6: 600 µs

## Submitted
- v1 (2026-10-16): PR #63 from `submit_jiangbanya_20261016`, router 2b51d4c, 1 thread · hard
  1.3303, congested 1.2367, designs 1.3685 · `research/models/jiangbanya_v1/`
- v2 (2026-10-16): packaged, not yet pushed (Kevin pushes) · router a235bf8, 4 threads · hard
  1.3368, congested 1.2490, designs 1.3744 · `research/models/jiangbanya_v2/`

## Open questions for Kevin
- The tag `entry-kevin_toll_lns-20261016` could not be pushed (git proxy refused tags);
  meta.json pins the commit, so it is optional.
- Fork is public: research commits are visible. Move router work to a private repo?
