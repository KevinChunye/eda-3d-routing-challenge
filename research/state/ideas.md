# Idea backlog

Ranked by priority = expected gain × confidence ÷ cost. `10_iterate` takes the top `open`
idea; `20_explore` adds, re-ranks and prunes. Keep each idea to the fields below. Status is
one of: open, in-progress, adopted (exp id, Δ), rejected (exp id, Δ), blocked (why), merged.

Expected effects for router ideas are on the hard-tier dev aggregate (baseline = 1.00).

## Phase A — a correct, fast incumbent (01_build_v0 covers A1–A2)

- **A1 · C++ negotiated router to legality** — status: adopted (exp-000, legal 33/33; hard 1.178 with A2)
  - Evidence: reference `m3d/negotiated.py` scores 1.00 on hard in 85 s (Python).
  - Mechanism: PathFinder costs (present + history) on grid points; per-net shortest-path
    tree; reroute only nets on overused points.
  - Expect: legal 9/9 hard, aggregate ≈ 1.00, ≥ 20× faster than the Python reference.
  - Cost: M. Falsify: any illegal case, or slower than the Python reference.
- **A2 · Exact per-net reroute after legality** — status: adopted (exp-000, hard 1.178 ≥ 1.15 target)
  - Evidence: negotiated_delay entry went 1.00 → 1.15 for +20 s.
  - Mechanism: rip one net, route its true-delay shortest-path tree with all others fixed,
    keep if its delay drops; sweep nets until a full pass finds nothing.
  - Expect: ≈ 1.15. Cost: S. Falsify: < 1.10.

## Phase B — the allocation search (where the score is)

- **B1 · Excess-targeted neighborhood search** — status: adopted (exp-001, mean r +7.2%; hard 1.270)
  - Evidence: 17% of hard sinks carry 50% of excess; slow-layer loss is 72% of it.
  - Mechanism: pick a sink with large excess; rip up its net plus the nets occupying the
    middle-layer points its ideal path needs; reroute the group in random orders (with
    negotiation inside the group); accept if total delay does not increase.
  - Expect: +15–20% over A2 at 60 s/case. Cost: M. Falsify: < +5% vs random neighborhoods.
- **B2 · Fanout-weighted congestion prices** — status: open — priority: high
  - Evidence: single-sink nets run 66% over ideal on hard; a trunk serves k sinks.
  - Mechanism: scale a net's congestion cost by 1/k (k = its sink count) during negotiation,
    so big nets keep the middle layers and small nets yield first. Sweep the exponent.
  - Expect: +3–8% at equal budget. Cost: S. Falsify: no gain at any exponent.
- **B3 · Toll-seeded history costs** — status: open — priority: medium
  - Evidence: PathFinder history costs act as Lagrange multipliers (Hu, Kim, Markov, DAC
    2013); our bound already computes good tolls per grid point.
  - Mechanism: initialize history costs from `lagrange_bound.py` tolls (export them), so the
    first legal solution already reflects scarcity prices.
  - Expect: better start; +1–3% at short budgets, less at long. Cost: S–M (needs toll export).
  - Falsify: no gain at 10 s/case.
- **B4 · Space-saving ties** — status: open — priority: medium
  - Mechanism: among equal-delay paths, prefer the one using fewer free middle-layer points
    or points other nets' ideal paths want (leave room for others).
  - Expect: +1–3%. Cost: S. Falsify: no gain.
- **B5 · Compact trees for big nets** — status: open — priority: medium
  - Evidence: designs' 9+-sink nets sit 2.9% over ideal while single-sink nets sit 46% over.
  - Mechanism: let multi-sink nets trade a little sink delay for fewer middle-layer points
    (Prim–Dijkstra / shallow-light trade-off), freeing room for small nets.
  - Expect: designs +3–6%, hard +1–3%. Cost: M. Falsify: no gain on designs.
- **B6 · Acceptance that escapes local optima** — status: open — priority: medium
  - Mechanism: threshold or annealed acceptance in B1 (accept small worsening early).
  - Expect: +1–3% at long budgets. Cost: S. Falsify: no gain at 120 s/case.
- **B7 · Exact repair of small groups** — status: open — priority: low
  - Mechanism: for 2–4 nets in a window, solve exactly (conflict-based search or a small
    MIP with OR-Tools CP-SAT / HiGHS).
  - Expect: small, late-stage. Cost: L.

## Phase C — speed (multiplies Phase B)

- **C1 · Bucket queue + A*** — status: open — priority: high once B1 exists
  - Evidence: bucket queue alone ~100× over Python (dial_bench). Each sink's congestion-free
    cost never overestimates, so it is a valid A* heuristic.
  - Mechanism: integer costs (scale fractional congestion costs), A* toward the next sink,
    search window around the net, stop when all sinks are reached.
  - Expect: 3–10× more neighborhood moves per second → better delay at equal budget.
  - Cost: M. Falsify: < 2× moves/s.
- **C2 · Multi-start inside one run** — status: open — priority: medium
  - Mechanism: T threads run independent seeds; keep the best; report threads honestly.
  - Expect: +1–2% per doubling of threads. Cost: S.

## Phase D — knowing the true gap (30_bound)

- **D1 · Stronger per-net bound for multi-sink nets** — status: open
  - Evidence: residual gap correlates 0.82 with multi-sink share; designs barely moved.
  - Mechanism: per net, use the max of the averaged-toll bound and the single-sink full-toll
    bound; then an exact "delay + tolls" tree via a small MIP for nets with ≤ 8 sinks.
- **D2 · Ground truth on tiny instances** — status: open
  - Mechanism: generate 6×6–10×10 instances with `m3d/generator.py`, solve exactly by MIP,
    check bound ≤ optimum and measure the router's true optimality gap.
