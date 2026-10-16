# STATE

Read this first in every session; update it last. Keep it short: it is the handoff note
between sessions on possibly different machines.

## Next action
Run `research/prompts/10_iterate.md` (top idea: B1 excess-targeted neighborhood search).

## Entry config (used by 40_submit; Kevin may edit)
- entry_name: `kevin_toll_lns` (one directory per distinct method; rename if the method changes)
- author: `Kevin Wang (KevinChunye)`
- code_url: `https://github.com/KevinChunye/eda-3d-routing-challenge/tree/m3d_research/router`
  (40_submit pins it to the frozen commit)
- tiers_to_submit: hard, congested, designs first; intro, scale, stress once runtime is good
- time_limit_s per case (submission): hard 60, congested 300, designs 300, intro 30,
  scale 120, stress 1800 (revisit after Phase B)
- threads per case: 1 (raise only with C2, and report it)

## Dev protocol
- dev set: `research/state/dev_set.json` (hard ×9, congested case_01, designs ctrl)
- budget: 30 s per case; seeds 1 2 3; `--jobs` = number of cores
- incumbent run cache: `research/runs/incumbent/` (gitignored; rebuild on a new machine)

## Incumbent
- exp-000 (v0, A1+A2), router sha 5dcb597, flags: none (defaults: neg_pres0=0.2,
  neg_pres_mult=1.03, neg_hist=0.1, escalation at 35%/60% of budget)
- dev aggregate @30 s, seeds 1-3: hard 1.1780 · congested 1.1179 · designs 1.2621
- gap to best bound: hard 38.0% · congested 37.7% · designs 40.1%; vs best public +19.9% / +21.7% / +18.4%
- v0 stops early (A2 converges): legal in 1.5-13 s, total ≤ 14 s per dev case

## Machine log
- (00_bootstrap appends: date, CPU model, logical CPUs, RAM, dial_bench µs/search)
- 2026-10-16 · claude-code cloud VM · Intel Xeon @ 2.10GHz · 4 logical CPUs · 15 GB RAM · dial_bench 40×40×6: 138 µs, 105×105×6: 600 µs

## Submitted
- nothing yet

## Open questions for Kevin
- Fork is public: research commits are visible. Move router work to a private repo?
