# STATE

Read this first in every session; update it last. Keep it short: it is the handoff note
between sessions on possibly different machines.

## Next action
Run `research/prompts/10_iterate.md` (continue the cycle list; see ideas.md).

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
- exp-007 (v0 + B1 LNS + B8 group negotiation + B2 fanout weights + E1 window moves),
  router sha 8cebc0d, flags:
  `--set lns=1 --set gneg=6 --set lns_k=6 --set fan_alpha=0.3 --set lns_mix=1`
- dev aggregate @30 s, seeds 1-3: hard 1.3196 · congested 1.2004 · designs 1.3353
- gap to best bound: hard 23.8% · congested 28.2% · designs 32.4%; vs best public +7.5% / +13.3% / +12.0%
- change vs exp-005: mean r +0.54% (hard +0.73% on 9/9; congested -0.5%, designs -0.1%)

## Machine log
- (00_bootstrap appends: date, CPU model, logical CPUs, RAM, dial_bench µs/search)
- 2026-10-16 · claude-code cloud VM · Intel Xeon @ 2.10GHz · 4 logical CPUs · 15 GB RAM · dial_bench 40×40×6: 138 µs, 105×105×6: 600 µs

## Submitted
- nothing yet

## Open questions for Kevin
- Fork is public: research commits are visible. Move router work to a private repo?
