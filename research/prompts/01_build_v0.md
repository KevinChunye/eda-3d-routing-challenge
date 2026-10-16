# 01 · Build the first router (v0)

**Goal.** A correct, deterministic C++20 router in `router/` that is legal on every dev case
and reaches the Phase A targets in `research/state/ideas.md`:
- **A1**: legal, hard aggregate ≈ 1.00, much faster than `m3d/negotiated.py`;
- **A2**: exact per-net reroute, hard aggregate ≈ 1.15.

It becomes the incumbent that `10_iterate` improves. Correctness first, then quality, then
speed.

**Read first.** `CLAUDE.md`, `research/state/STATE.md`, `research/state/findings.md`,
`docs/FORMATS.md`, `m3d/negotiated.py` (the reference algorithm), `m3d/checker.py` (what
legal means).

## Interface (fixed; every later prompt relies on it)

```
router/build/m3d_route --instance X.json --out Y.sol.json --time-limit SECONDS \
    --seed N --threads T [--set key=value ...]
```

- Writes a valid `m3d-submission` JSON (one `routes` entry per net).
- Anytime: keep the best legal solution found; write it before the time limit.
  Exit non-zero only if no legal solution exists at the deadline.
- Prints one JSON line last on stdout: `{"legal": true, "delay": <self-computed>,
  "iterations": ..., "moves": ..., "moves_per_s": ...}`. This is for diagnostics only;
  scores always come from the checker.
- `--set key=value` switches experimental behavior. Every later idea lands behind such a
  flag, so incumbent and candidate are the same binary.
- Build: `make -C router` (or cmake) producing `router/build/m3d_route`.
  - JSON: vendor nlohmann/json's single header (MIT) under `router/third_party/`, or write a
    minimal parser for the fixed format in `docs/FORMATS.md`.

## Suggested design

- **Grid.** Flat vertex index `v = (z*H + y)*W + x`, where W = width, H = height, z = layer.
  An `owner[v]` array holds the net id or -1. Pins of other nets are blocked.
- **Per-net routing.** Grow a shortest-path tree from the driver. Each sink gets its own
  minimum-delay path, because the objective sums driver→sink delays.
- **Negotiation (A1).** Mirror `m3d/negotiated.py`:
  - cost on a point = delay × (1 + history + present-factor × present use);
  - after the first pass, reroute only nets touching an overused point;
  - raise history cost where points stay overused.
- **Refinement (A2).** Once legal, sweep nets: rip one, route its true-delay shortest-path
  tree with every other net fixed, keep it if its delay drops. Repeat until a full sweep
  improves nothing or time runs out.
- **Determinism.** All randomness comes from one seeded RNG. The same seed and the same
  iteration cap must produce byte-identical output.

## Tests (router/tests/, runnable with one command)

- Build, then route `benchmarks/case_01..05` and `benchmarks_hard/case_01`; verify each with
  the repo checker:
  `python3 -m m3d.cli evaluate --case <case.json> --sol <out> --suite <suite dir>`.
- Determinism: run twice with the same seed and an iteration cap (`--set max_iters=...`),
  then diff the outputs.

## Measure and register the incumbent

1. Register first: `python3 research/tools/exp_log.py register --exp-id exp-000 --idea A1+A2`
   with the hypothesis, prediction, `--budget 30` and `--seeds 1 2 3`.
2. Run on the dev set:
   ```
   python3 research/tools/run_router.py --label exp-000 --cases dev --seeds 1 2 3 \
     --time-limit 30 --jobs $(nproc) --threads 1 \
     --cmd "router/build/m3d_route --instance {instance} --out {out} --time-limit {time} --seed {seed} --threads {threads} {extra}"
   ```
3. Score and log: `python3 research/tools/evaluate.py --run research/runs/exp-000 --log --exp-id exp-000 --idea A1+A2`.
4. If legal everywhere:
   - copy `research/runs/exp-000` to `research/runs/incumbent`;
   - `exp_log.py decide --decision adopt --learned "..."`;
   - set STATE.md "Incumbent" (git sha, flags, dev aggregate per tier, gap to bound) and
     "Next action: 10_iterate";
   - mark A1/A2 in ideas.md.
5. Run `python3 research/tools/gap_decompose.py --run research/runs/incumbent`. Add a short
   dated memo to findings.md comparing v0's loss profile with the best public one.
6. Commit `exp-000 v0 router: <hard aggregate>` and push `m3d_research`.

## Stop when
v0 is legal on all dev cases and logged (A2 target met or not; record it). If after a
serious effort v0 is still illegal on some case, stop: commit the work on `m3d_research`,
log `failed-correctness` with what fails, and report.
