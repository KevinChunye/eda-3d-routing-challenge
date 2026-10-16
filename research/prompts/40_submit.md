# 40 · Submit: timed run → validated submission branch → PR draft

**Goal.** Produce a leaderboard submission from the frozen incumbent that passes every check
CI runs, on a clean branch cut from upstream. Then hand it to Kevin. Do not open the PR.

**Read first.** `CLAUDE.md`; "Entry config" in `research/state/STATE.md` (entry name,
author, code url, tiers, per-tier time limits, threads); `CONTRIBUTING.md` (re-read it:
rules change); `scripts/check_submission_meta.py`.

## Steps

1. **Freeze.**
   - On `m3d_research` with a clean tree, rebuild the router from scratch and run the router
     tests.
   - Record `SHA=$(git rev-parse HEAD)`. Tag it `entry-<entry_name>-<yyyymmdd>` and push the
     tag.
2. **Machine.**
   - hardware string: `"<CPU model> (<logical CPUs> vCPU), <RAM> GB"`, from `/proc/cpuinfo`
     and `/proc/meminfo`;
   - threads: the value passed to the router.
3. **Timed run, one per case.**
   - Stop any other heavy process first.
   - Use `--jobs 1` so each case's wall clock is clean. Use one seed, fixed in STATE.md
     (default 1).
   - Use the incumbent flags and the per-tier limits, for every tier in `tiers_to_submit`:
     ```
     python3 research/tools/run_router.py --label submit-<yyyymmdd> --cases <tier> --seeds 1 \
       --time-limit <tier limit> --threads <threads> --jobs 1 --extra "<incumbent flags>" \
       --cmd "router/build/m3d_route --instance {instance} --out {out} --time-limit {time} --seed {seed} --threads {threads} {extra}"
     ```
   - `runtime.json` is written by the runner. Never edit it.
4. **Validate before packaging.** `python3 research/tools/evaluate.py --run research/runs/submit-<yyyymmdd> --cases <tiers joined by +>`.
   - Every case must be legal. Drop any tier with an illegal case and report it.
   - Compare each tier's aggregate with the dev expectation in STATE.md, and explain any
     drop > 2%.
5. **Package on a clean branch.**
   - Fetch and branch:
     ```
     git fetch upstream main
     git switch -c submit_<entry_name>_<yyyymmdd> upstream/main
     ```
   - For each tier, create `submissions/<tier>/<entry_name>/` containing:
     - every `<case>.sol.json` and the `runtime.json` from
       `research/runs/submit-<yyyymmdd>/seed1/<tier>/` (copy `runtime.json` unchanged);
     - `meta.json` with: `author`; `url` = `https://github.com/KevinChunye/eda-3d-routing-challenge/tree/<SHA>/router`;
       `method` (one honest line, e.g. "C++20 PathFinder negotiation + exact per-net
       shortest-path-tree reroute + excess-targeted neighborhood search; from scratch");
       `date`; `hardware`; `threads` (int); `router_commit` = SHA;
     - no `derived_from` (from-scratch entry).
   - If an entry with this name already exists upstream, this is an update of our own entry;
     keep the name only if the method is the same.
6. **Checks (all must pass, or stop and report).**
   - `python3 scripts/check_submission_meta.py submissions/<tier>/<entry_name>`, for each
     tier.
   - `python3 scripts/verify_submissions.py`
   - `python3 -m m3d.cli leaderboard-all`, then `python3 -m m3d.cli leaderboard-all --check`
   - `python3 -m unittest discover -s tests -q`
   - `git diff --name-only upstream/main`: only `submissions/<tier>/<entry_name>/...`,
     `LEADERBOARD.md` and `README.md` may appear.
   - README changes must stay inside the generated block:
     ```
     diff <(git show upstream/main:README.md | sed '/^<!-- leaderboard:start/,/^<!-- leaderboard:end -->/d') \
          <(sed '/^<!-- leaderboard:start/,/^<!-- leaderboard:end -->/d' README.md)
     ```
     This must print nothing.
7. **Commit and push.**
   - Commit `Add <entry_name> submissions (<tiers>)` and push the branch to `origin` (the
     fork).
   - Do not open a PR. Do not push to `main`.
8. **PR draft.** Switch back to `m3d_research` and write
   `research/state/pr_draft_<yyyymmdd>.md`:
   - title;
   - body: method summary in 3–5 lines; hardware and threads; a per-tier table (aggregate,
     total delay, total runtime, legal x/y); the router code link at SHA; a "from scratch,
     no other entry's routes used" statement;
   - the exact branch name.
9. **Record.** Update STATE.md "Submitted" (date, tiers, aggregates, branch, SHA). Commit
   and push `m3d_research`.

## Report (≤ 10 lines)
Branch name, per-tier aggregate and runtime, where they would rank on the current board,
and that the PR is ready for Kevin to open.
