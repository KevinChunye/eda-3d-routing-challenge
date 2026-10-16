# Findings

Evidence log. Newest memo at the bottom. Every number is checker-verified or reproducible
with a command from `research/tools/`. Define a symbol in plain words before using it.

## 2026-10-15 — problem definition (pre-router)

**The problem.** Route one tree per net on a 3D grid (6 layers between two dies) so no grid
point or edge is shared between nets, minimizing the sum over sinks of each sink's own
driver-to-sink path delay. Step delay by layer is 6/4/2/2/4/6; a layer change (via) costs 3.
Because every sink pays for its own path, a net alone is best routed as a shortest-path tree;
sharing wire earns nothing. All difficulty is congestion: the two middle layers (step cost 2)
are scarce. So the task is *allocating middle-layer area among nets*, with path-finding inside
each allocation, and *certifying how close a solution is to optimal*.

**Where the best public routes lose delay** (`gap_decompose.py --best-public`). "Ideal" =
each sink's cheapest path with no other nets present.

| tier | over ideal | slow-layer share | detour share | via share | middle layers used |
|---|---:|---:|---:|---:|---:|
| hard | 24.8% | 72% | 23% | 6% | 86–87% |
| congested | 22.3% | 63% | 24% | 13% | 85–86% |
| designs | 24.0% | 80% | 9% | 11% | 81% |
| intro | 3.0% | 32% | 4% | 64% | 47–49% |

- Single-sink nets are sacrificed: hard 25% of sinks carry 50% of the excess (66% over ideal);
  designs 40% of sinks carry 74%. One middle-layer trunk serves many sinks of a big net, so
  this is rational, but it is the allocation decision the score hinges on.
- Hard: 17% of sinks carry half of the excess; 39% carry 80%.
- Medium-distance sinks (11–20 steps) on hard are 57% over ideal; long ones (21+) 21%.
- Sparse tiers (intro, scale, stress) are within 0.6–3.0% of the congestion-free bound; ~90%
  of their remaining via excess is on same-die sinks, probably nets hopping between the two
  middle layers to cross. Treat them as solved; they matter only for runtime.

**How much headroom is real** (`lagrange_bound.py`, method avg-toll-v1). Tolls on grid points
replace the one-net-per-point rule; any toll setting gives a valid lower bound.

| | gap to congestion-free bound | gap to toll bound |
|---|---:|---:|
| hard (9 cases) | 24.8% | 15.1% (9.9–19.6% per case) |
| congested case_01 | 21.0% | 13.2% |
| designs ctrl | 20.6% | 18.3% |

- Residual gap vs share of sinks in multi-sink nets: correlation 0.82 across hard cases. The
  bound charges a branching tree only the average toll of its paths, so it is weakest exactly
  there; designs (largest nets) barely moved. True headroom is probably well under 15%.
- Bound runtime: 1–4 min per hard case; 25–35 min for 64×64 and 77×77 cases (numpy/scipy).

**Algorithm vs speed** (self-reported leaderboard runtimes, mixed hardware: orders of
magnitude only).
- Algorithm dominates: on intro, 25,290 s scored 1.058 while 2,214 s scored 1.125.
- Hard ladder: reference negotiated 85 s → 1.00; + exact per-net reroute, 105 s → 1.15;
  + neighborhood search, ~7,300 s → 1.30; ~34 core-hours → 1.39.
- Inner loop (one full shortest-path search; `research/tools/dial_bench.cpp`):
  40×40×6: 10.8 ms pure Python, 0.85 ms scipy, 0.11 ms C++ bucket queue (~100×);
  105×105×6: 69 ms Python vs 0.59 ms C++.

**Bottlenecks, ranked.** (1) allocation search: which nets give up the middle layers, and
escaping local optima; (2) a stronger bound to know the true gap; (3) inner-loop speed, a
~100× multiplier on (1). Model compression (pruning/quantization) does not apply: no neural
model is involved. Its analogs here are search pruning (A* with each sink's congestion-free
cost as heuristic, windowed search, early exit) and integer costs (bucket queue).

**Leaderboard context.** Top hard aggregate 1.4136 (best per-case mix of public routes).
Entries without runtime.json become unranked once maintainers enforce the 2026-10-15 rule;
then the best ranked hard entry is 1.3019 (iamparv7043, 7,333 s).
