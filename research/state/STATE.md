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
- exp-003 (v0 + B1 LNS + B8 group negotiation), router sha e8e6d4b, flags:
  `--set lns=1 --set gneg=6 --set lns_k=6`
- dev aggregate @30 s, seeds 1-3: hard 1.2982 · congested 1.1694 · designs 1.2871
- gap to best bound: hard 25.5% · congested 31.6% · designs 37.3%; vs best public +9.1% / +16.3% / +16.1%
- change vs exp-001: mean r +1.30% (hard +2.2%, congested -3.2%, designs -2.5%: 15x fewer moves/s)

## Machine log
- (00_bootstrap appends: date, CPU model, logical CPUs, RAM, dial_bench µs/search)
- 2026-10-16 · claude-code cloud VM · Intel Xeon @ 2.10GHz · 4 logical CPUs · 15 GB RAM · dial_bench 40×40×6: 138 µs, 105×105×6: 600 µs

## Submitted
- nothing yet

## Open questions for Kevin
- Fork is public: research commits are visible. Move router work to a private repo?
