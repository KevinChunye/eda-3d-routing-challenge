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

## 2026-10-16 — v0 router (exp-000) loss profile

v0 = C++ PathFinder negotiation (present-cost factor starts 0.2, ×1.03 per round, history
+0.1 per overuse) then exact per-net shortest-path-tree reroute sweeps. Dev @30 s: hard
1.178, congested 1.118, designs 1.262; legal 33/33; it stops after 1.5–14 s because A2
converges, so most of the budget is unused.
- Present-cost growth is the main v0 knob: ×1.7 (reference value) gave hard 1.048, ×1.15
  1.131, ×1.05 1.169, ×1.02 1.200 (self-reported, seed 1). Slow growth lets nets negotiate
  for the middle layers on true delay instead of being pushed out by penalties. ×1.03 plus a
  time-based escalation (×1.7 past 35% of budget, ×3 past 60%) keeps designs legal in 14 s.
- Loss profile vs best public (`gap_decompose.py`): v0 is 49.8% over ideal on hard (public
  24.8%); slow-layer share 74% (public 72%), detour 20% (23%), via 6% (6%). Same shape, twice
  the size: v0 loses where the public entries lose, just more, so the allocation search
  (B1) is the lever, not a different cost model.
- Single-sink nets are 70% over ideal on hard (public 66%); 5–8-sink nets 36%. Medium
  distance sinks (11–20 steps) 83% over ideal.
- Middle layers 85–88% used on hard and congested, 73–75% on designs.

## 2026-10-16 — LNS saturates; group negotiation helps, at a speed cost (exp-001..003)

- exp-001 LNS (group of 4 = a high-excess net + nets on its congestion-free tree, exact
  reroute in random order, accept if not worse): hard 1.178 → 1.270. It saturates: the same
  config at 90 s/case scores 1.2739 vs 1.2716 at 30 s (seed 1, hard). Moves are cheap
  (~5.9k/s on hard) but almost never accepted, so search speed (C1) alone is worth little.
- exp-002 annealed acceptance (B6): +0.15% mean r, inconclusive; predicted +2% (missed by
  >2×): accepting worse *greedy* reroutes does not lead anywhere new; the move generator
  cannot produce coordinated swaps.
- exp-003 group negotiation (B8): hard +2.2%, but congested −3.2%, designs −2.5%. Moves/s fell
  15× (heap search over the whole grid per net per round); on 64×64+ grids the initial
  negotiation already takes 12–13 s of the 30 s. Next lever: windowed (local) searches.

## 2026-10-16 — explore after 5 cycles (incumbent exp-005)

- **Where the loss is.** Hard 35.1% over ideal (public 24.8%): slow layer 70%, detour 24%,
  via 6%. Congested 36.1% (64/21/15), designs 34.9% (75/8/17). "Ideal" = each sink's
  cheapest path with no other nets present.
- **Who carries it.** After fanout weighting (B2) the loss moved to small nets: on hard,
  single-sink nets are 82% over ideal and carry 43.7% of the excess (25% of sinks); 5–8-sink
  nets 16.9%. Designs: single-sink 55.9% over ideal, 9+-sink nets 10.8%. Medium-distance
  sinks (11–20 steps) on hard 75% over ideal.
- **Largest gaps to bound** (bound = best certified lower bound): designs ctrl 32.2%, hard
  case_02 30.6%, hard case_07 29.7%. Vs best public: congested +12.7%, designs +11.8%, hard
  +8.3% (case_08 +10.9%).
- **What experiments taught.** Gains come from changing *how a group is rerouted* (B1 +7.2%,
  B8 +1.3%) and *who yields* (B2 +1.4%); accepting worse states (B6 +0.15%) and windowing
  (C1 +0.43%) do little. Budget barely matters with the current moves (3× budget +0.2%).
  Predictions: 2 of 5 met, B1 and B6/C1 over-optimistic (B6 by 13×).
- **Outside.** upstream/main unchanged since the fork point.
- **Literature.** MAPF-LNS (Li et al., IJCAI 2021) mixes three destroy heuristics with
  adaptive roulette weights; BALANCE (arXiv 2312.16767) adapts heuristic and neighborhood
  size by bandits. Source for E1.
- **Next three.** E1 adaptive neighborhood portfolio (attacks saturation directly), E2
  cheaper group negotiation (B8's 15× move-rate loss), B5 compact big-net trees (evidence:
  big nets near ideal, single-sink nets far from it).

## 2026-10-16 — readiness check at submission limits (exp-006, exp-005 flags, seed 1)

- Legal 45/45. Aggregates: intro 1.126, hard 1.315 (60 s), scale 1.093, stress 1.039,
  congested 1.239 (300 s), designs 1.365 (300 s).
- **Time to legality dominates large grids.** Negotiation (present-cost growth ×1.03, escalating
  at 35%/60% of budget) reaches legality in 2–10 s on hard, but 40–121 s of 300 on congested,
  54–106 s on designs and 1693 s of 1800 on stress (9 rounds of full-grid heap searches on a
  530×530×6 grid). Stress overshot its limit by 49 s: the congestion-free tree pass and LNS
  moves do not check the deadline on huge grids. Fix before submitting stress.
- **Sparse tiers are not solved by this router.** Intro is 8.1% over the bound (public 3.0%),
  scale 6.4% (public 1.9%), stress 6.3% (public 0.6%); small intro cases are within 1.5% of
  public, big ones (case_13–20) 3–8% worse. Same cause: little time left for LNS after
  negotiation on big grids, and every LNS search spans the whole grid. E2/E3 (and A* for
  sparse nets) are the levers there.

## 2026-10-16 — submission run vs every public entry (`compare_public.py`)

Checker scores of every public entry next to our timed run (`submit-20261016`, seed 1); the
aggregates reproduce LEADERBOARD.md exactly.
- Hard 1.3303: rank 8 of 18; first of 7 entries that report runtime (next: iamparv7043
  1.3019 at 7,333 s; ours 531 s). We trail the best public route by 4–9% on every hard case
  (case_09 6.4%, case_08 8.8%): an even gap, not a few bad cases.
- Congested 1.2367 (rank 7 of 11, 3rd of 5 with runtime) and designs 1.3685 (7 of 13, 3rd of
  6): the runtime-reporting entries above us total 3,600 s and 47,000–61,000 s vs our
  1,196 s / 897 s; warm_lns_refinement's runtime excludes its warm start.
- Score ceiling from the best lower bound (geometric mean of baseline / lb_best): hard 1.62,
  congested 1.62, designs 1.80.
- Router flag `snap_dir` (diagnostics, off by default; routes byte-identical with it off)
  plus `animate_run.py` render one run as a GIF; hard case_01 turns legal at 1.7 s (9,872)
  and reaches 8,908 by 59 s.
