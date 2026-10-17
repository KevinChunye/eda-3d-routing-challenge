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
- **B2 · Fanout-weighted congestion prices** — status: adopted (exp-005, alpha 0.3, mean r +1.37%)
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
- **B5 · Compact trees for big nets** — status: open — priority: medium-high (explore 2026-10-16: designs 9+-sink nets 10.8% over ideal vs single-sink 55.9%; hard single-sink nets carry 43.7% of excess)
  - Evidence: designs' 9+-sink nets sit 2.9% over ideal while single-sink nets sit 46% over.
  - Mechanism: let multi-sink nets trade a little sink delay for fewer middle-layer points
    (Prim–Dijkstra / shallow-light trade-off), freeing room for small nets.
  - Expect: designs +3–6%, hard +1–3%. Cost: M. Falsify: no gain on designs.
- **B6 · Acceptance that escapes local optima** — status: inconclusive (exp-002, mean r +0.15%, 6/11; code kept behind sa_t0, off)
  - Mechanism: threshold or annealed acceptance in B1 (accept small worsening early).
  - Expect: +1–3% at long budgets. Cost: S. Falsify: no gain at 120 s/case.
- **B8 · Negotiated group repair inside LNS** — status: adopted (exp-003, mean r +1.30%; hard +2.2%, congested/designs worse from 15x fewer moves/s)
  - Evidence: exp-001 LNS saturates (90 s vs 30 s: +0.2%); public method lines (lns_negotiated,
    warm_lns_refinement, reubalink) all negotiate inside the ripped group.
  - Mechanism: up to 6 PathFinder rounds among the ripped group with all other nets fixed;
    overlap-free result is polished by exact per-net reroutes; else sequential exact.
- **B7 · Exact repair of small groups** — status: open — priority: low
  - Mechanism: for 2–4 nets in a window, solve exactly (conflict-based search or a small
    MIP with OR-Tools CP-SAT / HiGHS).
  - Expect: small, late-stage. Cost: L.

## Explore 2026-10-16 additions (ranked; see findings memo of the same date)

- **E1 · Adaptive neighborhood portfolio** — status: adopted (exp-007, window half-size 3 + roulette, mean r +0.54%; hard +0.73%). Open follow-up: adapt group size k, add blocker random walks
  - Evidence: B1 alone saturates (90 s vs 30 s +0.2%); MAPF-LNS (Li et al., IJCAI 2021) mixes
    random, agent-based (blocker random walk) and map-based (junction) destroy heuristics
    with roulette weights; BALANCE (arXiv 2312.16767) also adapts neighborhood size.
  - Mechanism: add a window neighborhood (all nets with tree points in a random box around a
    random high-excess sink) next to B1's ideal-tree blockers; choose by roulette weights
    updated with delay gained per second; sizes k in {4, 6, 8}.
  - Expect: +1–2% mean r. Cost: M. Falsify: < +0.5% vs B1 alone at 30 s.
- **E2 · Cheaper group negotiation** — status: open — priority: high
  - Evidence: B8 cut LNS moves/s 15× (hard 5.9k → 0.39k; congested 0.11k/s); every round
    reroutes every group net with a heap search.
  - Mechanism: (a) after round 1 reroute only group nets touching an overused point
    (`gneg_sel`, implemented, off); (b) integer costs + bucket queue for the negotiated search.
  - Expect: 2× moves/s, +0.5–1% mean r. Cost: S (a), M (b). Falsify: < 1.5× moves/s.
- **E3 · Faster legality on large grids** — status: open — priority: high (exp-006: legality takes 40–121 s of 300 on congested, 1693 s of 1800 on stress; stress overshot its limit by 49 s)
  - Evidence: congested/designs at 30 s spend 12–13 s (40%) reaching legality; escalation
    fires at 35% of budget.
  - Mechanism: start present-cost growth faster on large grids by a size-free rule (e.g.
    escalate when overuse stops falling for R rounds), or window each net's negotiated search
    to its pin bounding box + margin.
  - Expect: +1–2% congested/designs at 30 s; ~0 on hard. Cost: S–M. Falsify: legal time not
    halved.

## Phase C — speed (multiplies Phase B)

- **C1 · Bucket queue + A*** — status: window part inconclusive (exp-004, lns_win=3, mean r +0.43%, 7/11; moves/s barely changed). Exact searches already use a bucket queue; open: A*/bucket queue for the negotiated (heap) search
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

## Ranked proposals, 2026-10-17 (status after exp-013..026)

Ranked by expected gain × confidence ÷ cost at the time of proposal; measured mean r vs a
fresh base where available.

1. **P1 longer honest budget** — inconclusive (exp-026: +0.14% for 5× time with v3).
2. **P4 combine adopted ideas** — adopted (exp-022 +0.91% single-thread; exp-024/025 +0.83/+0.90% on 4 threads) → Jiangbanya v3.
3. **P2 deeper group moves** — rejected at 30 s (exp-015 −0.21%). Open: switch to deep moves only after stagnation (late search).
4. **P8 big-grid escalation** — inconclusive (exp-017; congested +0.72%, designs −0.56%).
5. **P3 operator-selector fix** — inconclusive (exp-013 +0.07%); keep the fix, it is correct.
6. **P9 random equal-delay ties** — adopted (exp-014; part of v3).
7. **P6 slower start** — rejected (exp-016).
8. **P5 thread diversity (sync 10 s)** — noise vs 2 s (exp-025); used in v3.
9. **P7 same-die long-sink neighborhoods** — open, not tested. Evidence: same-die 21–40-step
   sinks carry the largest share of the gap to leonid-popryho.
10. **P10 exact small-window repair (MILP / CP-SAT)** — open, not tested; cost L.

Next (from the calibration lesson, search-dynamics first): adaptive depth (deep moves after
stagnation), path relinking between thread-best solutions, P7, then P10.
