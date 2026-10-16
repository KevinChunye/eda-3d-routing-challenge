# Research loop

A small set of prompts that let Claude Code work on this challenge over many sessions,
improving one measured step at a time and producing submissions that pass every rule.
All memory lives in `research/state/`, so any session on any machine can pick up.

## The prompts

| prompt | when | what it produces |
|---|---|---|
| `prompts/00_bootstrap.md` | once per new VM | toolchain, upstream remote, sanity checks, machine log |
| `prompts/01_build_v0.md` | once | first legal C++ router = incumbent (Phase A) |
| `prompts/10_iterate.md` | every working session | 1 pre-registered experiment per cycle, auto-chained |
| `prompts/20_explore.md` | every 5 cycles, thin backlog, or 3 misses in a row | evidence memo + re-ranked ideas |
| `prompts/30_bound.md` | research track, any time | tighter certified bound, tiny-instance ground truth |
| `prompts/40_submit.md` | when the incumbent beats a target | timed run, validated submission branch, PR draft |

`10_iterate` calls `20_explore` itself when its triggers fire, so a normal session is just:
"follow research/prompts/10_iterate.md".

## One cycle of 10_iterate

```
orient -> pick top idea -> pre-register -> implement behind a flag -> correctness gate
       -> paired measurement vs incumbent -> fixed decision rule -> log + learn -> commit/push
```

**Decision rule** (fixed in advance, applied by `tools/evaluate.py`). For each dev case and
seed, `r` = log(incumbent delay / candidate delay); `r > 0` means the candidate is better.
- any illegal route → failed-correctness (fix once, else revert)
- mean `r` > 0 and `r` > 0 on at least 2/3 of dev cases → adopt
- mean `r` > 0 otherwise → inconclusive (one rerun with 3 more seeds allowed)
- mean `r` ≤ 0 → reject

**Since exp-018 (2026-10-16).** A fresh rerun of the unchanged incumbent scored mean `r` =
+0.145% (9/11 cases "better") against the cached incumbent, so the rule above adopts a
do-nothing change. Compare every candidate against a baseline run fresh in the same batch,
on the same `--jobs`/`--threads`, and adopt only if mean `r` > +0.2%
(`evaluate.py --min-r 0.2`). Mean `r` within ±0.2% is noise.

Engineering-only changes (meant to be faster, not different) must reproduce identical routes
at a fixed iteration count and show more moves per second.

## Tools (run from the repo root)

| tool | purpose |
|---|---|
| `tools/run_router.py` | time a router per case, end to end; writes `runtime.json` (also used for submissions) |
| `tools/evaluate.py` | checker-verified scoring, gap to bound, paired comparison, decision, logging |
| `tools/exp_log.py` | `next-id`, `register` (before running), `decide` (after), `show` |
| `tools/gap_decompose.py` | where delay is lost: slow layer / detour / via; by fanout and distance |
| `tools/reference_points.py` | baseline, bounds and best public route per case → `state/reference_points.csv` |
| `tools/lagrange_bound.py` | congestion-aware lower bound (tolls on grid points) → `state/toll_bounds.jsonl` |
| `tools/dial_bench.cpp` | inner-loop speed reference: bucket-queue shortest path on a flat grid |

## State files

| file | role |
|---|---|
| `state/STATE.md` | handoff note: next action, entry config, incumbent, machine log |
| `state/ideas.md` | ranked backlog with evidence, mechanism, expected effect, falsification test |
| `state/experiments.jsonl` | append-only: registered / result / decision rows per experiment |
| `state/findings.md` | dated evidence memos |
| `state/reference_points.csv` | per-case baseline, bounds, best public route |
| `state/toll_bounds.jsonl` | every bound computation (method-tagged) |
| `state/dev_set.json` | the cases experiments are judged on |

## Kickoff text for a Claude Code session

> Work in the repo KevinChunye/eda-3d-routing-challenge on branch `m3d_research`. Read
> CLAUDE.md and research/state/STATE.md, then follow the prompt STATE.md names under
> research/prompts/. Work autonomously until that prompt's stop condition; commit and push
> `m3d_research` after each step. Do not open pull requests.
