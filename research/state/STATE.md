# STATE

Read this first in every session; update it last. Keep it short: it is the handoff note
between sessions on possibly different machines.

## Next action
Run `research/prompts/00_bootstrap.md` on the VM, then `01_build_v0.md`.

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
- none yet (Phase A)

## Machine log
- (00_bootstrap appends: date, CPU model, logical CPUs, RAM, dial_bench µs/search)

## Submitted
- nothing yet

## Open questions for Kevin
- Fork is public: research commits are visible. Move router work to a private repo?
