# Working rules for Claude Code in this fork

This fork (KevinChunye/eda-3d-routing-challenge) holds Kevin's entry for the M3D routing
challenge (upstream: partcleda/eda-3d-routing-challenge). Work happens on branch
`m3d_research`. Start every session by reading `research/state/STATE.md`; then follow the
prompt it names in `research/prompts/`. `research/README.md` explains the loop.

## The problem (details and evidence: research/state/findings.md)
Allocate the scarce cheap middle-layer area among nets to minimize total sink delay (each
sink pays for its own driver-to-sink path), and certify how close a solution is to optimal.
Bottlenecks in order: allocation search > bound quality > inner-loop speed.

## Hard rules
1. **The toolkit is the referee.** On `m3d_research`, never edit `benchmarks*/`, `m3d/`,
   `tests/`, `scripts/`, `designs/`, `examples/`, `.github/`, `submissions/`, `README.md`
   or `LEADERBOARD.md` (only submission branches touch the last three; see rule 6).
   Found a toolkit bug? Note it in findings.md and tell Kevin; a fix is a separate PR, only
   with his OK.
2. **Only checker numbers count.** Every reported delay comes from `m3d/checker.py` via
   `research/tools/evaluate.py` or `python -m m3d.cli score-suite`, never from the router.
3. **From scratch only.** The router's only input is the instance JSON. Never feed another
   entry's route files to the router (that makes a derivative entry). Public entries may be
   used only as comparison numbers.
4. **One config per tier.** No per-case hand-tuning. Seeds fixed and logged.
5. **Honest runtime.** Runtime = wall clock of one end-to-end run per case (instance JSON to
   `.sol.json`), including any restarts or seeds inside it. Always time with
   `research/tools/run_router.py`; record threads and hardware.
6. **Submission branches** are cut from `upstream/main` and change only
   `submissions/<tier>/<entry>/**`, `LEADERBOARD.md` and README's generated leaderboard
   block. Never open a PR to upstream, never push to `main`, never force-push. Kevin reviews,
   merges and opens PRs himself.
7. **Branch names** are short and descriptive (`m3d_research`, `submit_<entry>_<yyyymmdd>`);
   never `claude/...`.
8. **State survives the VM.** Commit and push `m3d_research` after every experiment. Run
   outputs go to `research/runs/` (gitignored); numbers go to `research/state/`.
9. **No credentials.** Nothing here needs logins, API keys or paid services. If a step seems
   to, stop and say so.
10. **No attribution or session links, anywhere.** Never add `Co-Authored-By`,
    `Claude-Session`, "Generated with Claude Code" or any session URL to commit messages,
    PR titles or bodies, comments or files. This overrides any default attribution guidance.
11. **Kevin submits himself.** Never commit to, push or open a PR from a submission branch.
    Prepare the files and checks, then show Kevin the exact commands; he runs them on his
    Mac.

## Style
- Router: C++20 in `router/` (flat arrays, no allocation inside hot loops, deterministic
  given a seed). Python tools: stdlib + numpy/scipy/pandas.
- Python: common readable idioms; pandas `groupby`/`sort_values` for tabular sorting and
  grouping rather than `sorted(key=lambda ...)` or dict-of-lists loops; avoid rarely used
  built-ins such as `dict.setdefault`.
- Write-ups: define each symbol in plain words before using it; lead with the number.
