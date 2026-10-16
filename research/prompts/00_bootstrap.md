# 00 · Bootstrap a machine

**Goal.** Make this machine ready for experiments and confirm the harness reproduces known
numbers. Run once per new VM; safe to re-run.

**Read first.** `CLAUDE.md`, `research/state/STATE.md`, `research/README.md`.

## Steps

1. **Git.**
   - `git fetch origin && git switch m3d_research && git pull --ff-only`.
   - Add the upstream remote if missing:
     `git remote add upstream https://github.com/partcleda/eda-3d-routing-challenge`, then
     `git fetch upstream main`.
   - If `upstream/main` has commits that `m3d_research` lacks, merge them
     (`git merge --no-edit upstream/main`). If the merge touches `benchmarks*/`, `m3d/` or
     `CONTRIBUTING.md`, read the diff and write one line per rule or scoring change in a new
     dated memo in `research/state/findings.md`.
2. **Toolchain.**
   - Python ≥ 3.9 with numpy, scipy, pandas
     (`pip install --user numpy scipy pandas`; add `--break-system-packages` if pip refuses).
   - g++ ≥ 11 (C++20) and make; cmake if available. Install with the system package manager
     if missing.
   - Optional for `30_bound`: `pip install --user highspy ortools`.
3. **Sanity (all must pass).**
   - `python3 -m unittest discover -s tests -q`
   - `python3 scripts/verify_submissions.py`
4. **Reference points.** `python3 research/tools/reference_points.py --exclude kevin_toll_lns`
   (use the `entry_name` from STATE.md). Check against `research/state/findings.md`:
   - the hard congestion-free bound total must be exactly 114031;
   - the best-public totals may be lower than recorded if upstream merged new entries.
     Note any change in the findings memo.
5. **Speed reference.**
   - `g++ -O2 -std=c++20 -o /tmp/dial_bench research/tools/dial_bench.cpp`
   - `/tmp/dial_bench 40 40 6` and `/tmp/dial_bench 105 105 6`.
6. **Machine log.** Append one line to "Machine log" in STATE.md: date, CPU model, logical
   CPUs, RAM, the two µs/search numbers.
7. **Toll bounds.** Run `lagrange_bound.py` only for dev cases that have no row in
   `research/state/toll_bounds.jsonl`. Hard cases take 1–4 minutes each; skip the 25–35
   minute cases unless the machine has more than 16 cores. Then re-run step 4.
8. **Handoff.**
   - Set "Next action" in STATE.md to `01_build_v0` if `router/` does not exist, else
     `10_iterate`.
   - Commit `bootstrap: <host> <date>` and push `m3d_research`.

## Stop when
All steps pass. If a sanity check fails, stop and report it (do not "fix" the toolkit).

## Report (≤ 10 lines)
Machine, any upstream changes, the hard-bound check, dial_bench numbers, next action.
