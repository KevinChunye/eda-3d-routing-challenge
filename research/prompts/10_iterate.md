# 10 · Iterate: one measured improvement per cycle

**Goal.** Improve the incumbent router on the dev set through small, pre-registered,
checker-verified experiments, and leave a trail the next session can continue from.

**Session budget.** Up to 6 cycles or 4 hours, whichever comes first, unless Kevin's message
says otherwise.

**Read first.** `CLAUDE.md`; `research/state/STATE.md`; `exp_log.py show --last 15`; the top
5 `open` ideas in `research/state/ideas.md`; the newest memo in `research/state/findings.md`.

**Shorthands.** `RUN` is `python3 research/tools/run_router.py`. `CMD` is
`router/build/m3d_route --instance {instance} --out {out} --time-limit {time} --seed {seed} --threads {threads} {extra}`.

## 0. Session setup

- `git switch m3d_research && git pull --ff-only`, then build the router. The tree must be
  clean.
- **Incumbent cache.** If `research/runs/incumbent/run_info.json` is missing, or its machine
  differs from this one, rebuild it at the incumbent's git sha and flags (from STATE.md):
  `RUN --label incumbent --cases dev --seeds 1 2 3 --time-limit 30 --jobs $(nproc) --cmd "CMD" --extra "<incumbent flags>"`.
  All comparisons use this cache.

## 1. Cycle

1. **Pick.** Take the highest-priority `open` idea whose prerequisites are met; set it
   `in-progress`. If no idea qualifies, run `20_explore` first.
2. **Pre-register** before writing code:
   - `python3 research/tools/exp_log.py next-id`, then
     `python3 research/tools/exp_log.py register --exp-id <id> --idea <idea> --hypothesis "..." --change "..." --prediction "<direction and rough size, e.g. +3% hard aggregate>" --budget 30 --seeds 1 2 3`.
   - The prediction is a number you commit to, not a hope.
3. **Implement the smallest version** behind a `--set` flag so the incumbent behavior is
   unchanged when the flag is off.
   - Add or extend a test in `router/tests/`.
   - With the flag off, output must be byte-identical to before at a fixed iteration cap.
     Check this.
4. **Correctness gate.** Run the candidate on the dev set:
   `RUN --label <id> --cases dev --seeds 1 2 3 --time-limit 30 --jobs $(nproc) --cmd "CMD" --extra "<incumbent flags> <new flag>"`.
   - Then `python3 research/tools/evaluate.py --run research/runs/<id>`.
   - Any illegal case: fix once and rerun. If it is still illegal, log `failed-correctness`,
     revert the code, set the idea to `blocked` with the reason, and go to step 8.
5. **Measure and log:**
   `python3 research/tools/evaluate.py --run research/runs/<id> --compare research/runs/incumbent --log --exp-id <id> --idea <idea>`.
6. **Decide** with the printed rule; never override it.
   - **inconclusive**: you may rerun once with seeds 4 5 6 (and the incumbent on the same
     seeds), then decide on all 6 seeds.
   - **Engineering-only change**: require identical routes at a fixed iteration cap and
     higher `moves_per_s`.
   - Record it: `python3 research/tools/exp_log.py decide --exp-id <id> --decision <d> --learned "<one sentence with the number>"`.
7. **Apply the decision.**
   - **Adopt.** The new flag joins the incumbent flags (or becomes the default with the old
     path kept under a flag). Copy `research/runs/<id>` to `research/runs/incumbent`. Update
     STATE.md "Incumbent" (sha, flags, dev aggregate per tier, gap to bound, change vs the
     previous incumbent). Run
     `python3 research/tools/gap_decompose.py --run research/runs/incumbent`; if the loss
     profile moved, add 1–3 bullets to findings.md.
   - **Reject or inconclusive.** Leave the code behind its flag (off) if it is small and
     clean; otherwise revert it. Mark the idea with the experiment id and the number.
   - **Prediction check.** If the result missed the prediction by more than 2×, write one
     line in findings.md on why. A miss is information.
8. **Learn.** Add at most 2 new ideas to ideas.md, and only if this cycle's evidence suggests
   them. Each needs evidence, mechanism, expected effect, cost and a falsification test.
9. **Commit and push.** Commit `<id> <idea>: <decision> (mean r <+x.xx>%)` and push
   `m3d_research`.

## 2. Triggers between cycles

- **Run `20_explore` before the next cycle when any of these hold:**
  - 5 cycles since the last explore memo;
  - fewer than 3 `open` ideas;
  - 3 non-adoptions in a row.
- **Every 3 adoptions, run a full-tier readiness check:**
  - every tier at the per-tier submission time limits in STATE.md, seed 1;
  - `--jobs` may be > 1, because the timing here is only a sanity check;
  - skip stress if its time limit exceeds the remaining session budget;
  - log it as an experiment with `--cases all` and decision `adopt` if legal everywhere.
- **Hand off to `40_submit`** when all three hold:
  - the readiness check is legal on every tier being submitted;
  - the hard dev aggregate beats the target in STATE.md;
  - Kevin has not said to hold.

  Default target: 1.31, i.e. above the best entry that reports its runtime.

## 3. End of session

- Update STATE.md: incumbent, next action, open questions.
- Commit and push.
- Report in at most 15 lines: cycles run, each with its decision and mean r; dev aggregate
  per tier and gap to bound now vs at session start; the next idea; anything Kevin needs to
  decide.

## Guardrails

- One idea per experiment. A change that mixes two ideas cannot be attributed; split it.
- Same budget, seeds, dev set and machine for candidate and incumbent, or the comparison
  is void.
- Don't tune on a single case. Don't add per-case special cases.
- Router input is the instance JSON only (CLAUDE.md rule 3).
- If a session finds a bug in a past adopted change, log it as its own experiment
  (revert or fix), not as a silent edit.
