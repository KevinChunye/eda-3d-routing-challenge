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

## 2026-10-16 — ideas 1–5 measured (exp-008..012; 30 s, seeds 1–3, vs exp-007)

Diagnostics that motivated them (hard, vs leonid-popryho's routes): we carry 9,334 more
delay; 80% of it in nets with 2+ sinks, 83% on same-die sinks; ~45% of our multi-sink trees
are both slower and larger than leonid's; we use 4.8% more grid points (17.7 vs 16.9 per
sink). 60 s → 300 s gives only 1.0–1.7% on hard case_01/05/09.

| idea | predicted | actual mean r | cases better | decision |
|---|---:|---:|---:|---|
| 1 sink-by-sink negotiated trees (`tree_seq=2`) | +2–3% | −0.12% | 6/11 | reject |
| 2 space-saving ties (`tie_share=1`) | +1–2% | +0.03% | 5/11 | inconclusive |
| 3 threshold + kick + return to best | ~0 at 30 s, +1–2% at 300 s | +0.36% (+0.75% at 300 s, 3 cases) | 10/11 | adopt |
| 4 `gneg_sel` + A* single-sink | +0.5–1% | +0.36% | 6/11 | inconclusive |
| 5 4 threads, sync every 2 s | +1–1.5% | +0.82% | 11/11 | adopt |

- Ideas 1 and 2 missed by far. Both target tree shape, and neither changes which nets get
  the middle layers; the LNS acceptance already sees true delay. The per-net diagnostics
  (bigger and slower trees) are a symptom of allocation, not of tree construction.
- Idea 1 everywhere cut group-move throughput 2.5× (k searches per net, each seeded with the
  whole tree) and lost 1.7% on hard (seed 1).
- Idea 4 is a large-grid win (congested +1.8%, designs +2.1%) and mixed on hard; worth a
  tier-aware retest.
- Ideas 3, 4 and 5 are independent; their combination is untested.

## 2026-10-16 — how the top entries work, and where our search runs out

**Leaderboard methods** (meta.json method lines, write-ups in `submissions/*/*/README.md`,
the public README of spt_lns; no code copied).
- The two leaders do not disclose their methods: leonid-popryho ("own router") and
  cuda-have-been-shorter ("GPU-accelerated routing engine"). coordinated_refinement (#1) is a
  best-per-case mix of their routes plus "exact A* and bounded group refinement", which gained
  only a handful of delay units over them. warm_lns_refinement refining pathfinder_lns's
  routes gained +2 delay on one case. The best public routes are deep local optima for this
  whole method family.
- spt_lns (1.397, open): our exact family (SPT nets, slow fanout-scaled PathFinder, exact
  per-net refinement, annealed LNS with ideal-tree and window moves). Differences: groups up
  to 12 nets and up to 60 negotiation rounds, sequential vs negotiated rebuild mixed 50/50,
  and scale: overnight workers warm-starting from the best file on disk, occasional restarts
  from scratch, ~300 thread-hours in total (runtime not reported).
- pathfinder_lns reports 61,369 s (congested) and 47,268 s (designs); iamparv7043 7,333 s
  (hard). Our v2 uses 531 s on hard.

**Where our search runs out** (hard case_02/05/08, 60 s, 1 thread, verbose counters).
- Improving moves are rare: 0.9–5.4% of moves lower the delay; 40–54% are accepted, almost
  all as equal-delay plateau moves. A move costs 3–8 ms. Group negotiation ends illegal in
  3–21% of moves (then sequential exact rebuild).
- Bug: the adaptive move selector never adapted. Weights (delay per microsecond, ~1e-5) sat
  at the absolute floor 1e-4, so the choice stayed 50/50 although window moves improve more
  often (1.4–5.4% vs 0.9–4.1%) and cost less per move.
- Seed spread is small: max-min over 3 seeds 0.8% of delay, best-of-3 only 0.34% better than
  the mean. Restarts cannot close a 6% gap; the search converges to the same level.
- Same-die sinks are 1,316 of 1,709 hard sinks and carry most of the gap to leonid-popryho
  (+6,972 of +8,496 extra delay vs v2): mostly slow-layer (+4,680) and detour (+2,052)
  steps on 21–40-step sinks (34% vs 26% over their congestion-free delay).

**Forecast calibration so far.** Ideas 1–5 delivered about 30–40% of the predicted gain;
compute ideas (threads, longer budget) came closest, structural tree-shape ideas (1, 2) missed
almost entirely. Predictions from exp-013 on are shrunk accordingly.

## 2026-10-17 — proposals P1–P10, calibration, combinations (exp-013..026)

**Screening** (30 s, seeds 1–3, single thread, vs cached exp-007): P3 selector fix +0.07%,
P9 random ties +0.35% (10/11), P2 deeper group moves (8 nets, 12 rounds) −0.21%, P6 slower
start −0.01%, P8 big-grid escalation +0.09% (its hard cases are untouched and still read
+0.09%: a null test).

**Measurement drift (a protocol bug, not a router bug).** exp-018 reran the unchanged
incumbent: +0.145% vs the cached exp-007, 9/11 "better", i.e. adopt under the old rule. The
cache was recorded while an 1,800 s stress run shared the machine. Against a fresh base the
single winners shrink to +0.21% (escape), +0.22% (cheap moves), +0.21% (random ties). Rule
changed: fresh baseline in the same batch and `--min-r 0.2` (research/README.md). The
threaded base had no drift (exp-023 vs exp-012: −0.04%).

**Calibration.** Over 10 single ideas, Spearman(predicted, measured) = −0.20. Structural
ideas (tree construction, deeper moves) predicted +1.47% on average and measured −0.10%;
search-dynamics ideas (ties, escape, selector) predicted +0.12% and measured +0.26%. The
static diagnostics (bigger, slower trees than leonid-popryho) describe where a weaker search
ends up; they do not identify a lever. Prefer ideas that change what the search can reach.

**Combinations** (vs fresh base exp-018): ties+escape +0.66% (11/11; singles sum 0.42),
ties+cheap +0.43% (additive), escape+cheap +0.59%, all three +0.91% (8/11; sum 0.64). No
cancellation; ties and escape reinforce each other (random equal-delay states give the
threshold walk somewhere to go). With 4 threads: +0.83% vs fresh v2 (10/11; congested +1.5%,
designs +1.4%); syncing every 10 s instead of 2 s: +0.07% (noise).

**Budget (P1).** v3 settings at 300 s vs 60 s: +0.14% on hard case_01/05/09 (one case worse).
v3 at 60 s already matches v1 at 300 s; extra minutes do not get below that floor. The gap
to the top entries needs moves that restructure more, or the hundreds of thread-hours they
used, not a few more minutes per case.
## 2026-10-17 — v4: which optimizer for the search policy (literature → our levers)

Terms: a *move* rips up a group of up to 6 nets and reroutes them; *Δ* is the move's change
in total sink delay (Δ > 0 = worse); a *threshold* thr accepts a worse move when Δ ≤ thr.

| Kevin's idea | standard name | what it means here | status |
|---|---|---|---|
| take a 1-step-worse decision for a better long run | non-monotone acceptance: simulated annealing, threshold accepting (Dueck & Scheuer 1990), record-to-record travel (Dueck 1993), late acceptance (Burke & Bykov 2017) | accept Δ > 0 sometimes so the walk can leave a local optimum | TA in v3 (thr 8); race exp-027 |
| more random early, less random late | cooling schedule (SA), ε-decay (RL) | thr falls from ta_t0 to 0 over the run; shape `ta_pow`, reheats `ta_cycles` | v4 tuning |
| short-term weight high, long-term weight small but non-zero | discounted credit assignment (discounted bandits, DyMAB; γ in RL) | a move type's success record decays by `bandit_decay` per move (0.995 → ~200-move memory) | bandit in v4 |
| "watering": where the water goes gets weighted | water-filling / Lagrangian prices | demand map from congestion-free trees (pressure shaping); PathFinder history costs are the same idea | shaping tested: noise |
| RL with 10% random steps | ε-greedy operator selection = a one-state RL problem (bandit) | pick among 5 move types; Thompson sampling explores in proportion to uncertainty, plus a uniform random-target arm (the "10% random") | bandit in v4 |
| gradient descent / other optimizer | no gradient over discrete routes; subgradient ascent applies to the dual prices (lower bound) | useful for certification, not for the allocation search | not pursued for v4 |
| tune it | automatic algorithm configuration: racing (irace / F-Race), SMAC | successive halving over (case, seed) pairs, `tune_race.py` | exp-027, exp-029 |

Why not a learned RL policy (a neural network choosing moves): it needs thousands of training
episodes across many instances to beat a hand-made rule; we have 16 public cases, a run
makes ~10^4–10^5 moves, and a policy tuned on the same cases it is scored on is overfitting
by another name. The within-run version of RL that fits this problem is the bandit (learn
which move type pays off now, forget old evidence at rate γ) plus an annealed acceptance rule
(the exploration schedule). Parallel threads add a third lever: replica-style search, where
threads run at different thresholds and all adopt the best every 10 s (`ta_list`).

**Measurements (exp-027..034; r = log(v3 delay / candidate delay), checker numbers).**
- Short tuning runs pick the wrong winner. At 30 s, late acceptance lost 4% and higher
  thresholds looked like noise (exp-027); at 60–600 s, threshold 16 + bandit beat v3 by
  +1.3% on hard case_01/05/09, one thread, at both 60 s and 600 s (exp-028).
- Threshold height is the lever; shape is not. At 300 s, one thread, 8 pairs: threshold
  16–64 all +0.7% to +0.9% vs v3 (indistinguishable), 96 past the peak (+0.4%). Fast or slow
  decay, decaying reheats, and bandit memory (γ = 0.99 / 0.999) were no better than plain
  linear decay (exp-029, exp-030).
- Exploration needs moves per net. Hard case_01 gets ~11,800 moves per net in 300 s; designs
  ctrl gets ~215 (and spends 35 s reaching legality). Designs loses with high thresholds at
  300 s (−1.0% to −2.4%). At 1,800 s the second descent shows (trace plot,
  `research/models/jiangbanya_v4/`): threshold 32 is 2.2% behind v3 at 1,243 s and 0.28%
  at the end, so on designs exploration only catches up (exp-032). The rate-controlled
  threshold (target share of worse moves accepted, 0.25 → 0) tracks v3 there (+0.02%).
- Threads cut walks short. With 4 threads syncing to the best every 10 s, the one-thread
  gain mostly vanishes (+0.14% vs v3, exp-031); syncing every 60 s recovers part of it
  (+0.28% over 10 s; hard case_05/09 +1.15/+1.34%, congested +0.89% vs v3; exp-033).
  Per-thread thresholds 16/32/48/64 did not help (−0.08%).
- Budget is the big lever on large cases: designs ctrl with v3 settings, 1 thread 1,800 s
  (50,250) beats 4 threads 300 s (50,858–50,948) by 1.2–1.4%. One long walk uses CPU about
  twice as well as four walks reset every 10 s.

## 2026-10-18 — dispatch-engine audit: where a move's CPU goes, and two falsified directions

Measured outside the dev protocol: scratch builds on a 2-vCPU machine, 1 thread, 120 s per
run unless stated, every delay checker-verified. Terms: a *search* is one shortest-path tree
computation for one net; *settled* = grid points a search finalises; *r* = log(baseline delay /
candidate delay) × 100, so r > 0 means the candidate is better.

**Where the CPU goes** (gprof, 90 s). Hard case_05 (v4 hard flags): 79% of CPU is the
group-negotiation searches (binary heap on fractional costs); the exact reroutes that place
the final trees take 7%. Designs ctrl (v3 flags): group negotiation 56%, initial negotiation
37% (32 s of 90 s before the first legal solution).

**Search volume vs the answer** (instrumented copy). A group-negotiation search for a
multi-sink net settles 13,266 points (37% of the 35,574-point grid) on designs ctrl to return
a 234-point tree (57×), and 2,084 points (34% of the grid) on hard case_05 for a 65-point
tree (32×). Per settled point the heap search costs ~67 ns; the bucket queue the exact search
already uses costs ~11.5 ns (`dial_bench`), 5.9× less. On designs, 4 nets with 9+ sinks take
31% of the search work and 2–4-sink nets 48%; single-sink nets, which carry most of the excess,
take 16%. Trees leave their terminal bounding box + 8 in ≤ 4% of searches, but the boxes are
large, so windowing alone saves only 30–50%. Partial rip-up of big nets would save < 2×:
67–85% of a big victim's sink paths enter the target's box + 3.

**S1: approximate while negotiating, exact at commit** (`research/patches/s1_neg_int.patch`,
flags `neg_int` = integer cost scale, `neg_goal` = goal weight). Negotiated searches run on
integer costs round(4 × cost) with a circular bucket queue. Group searches are goal-directed:
key = distance + 1.5 × (cheapest step × L1 distance to the sinks' box + via × layer gap); a
weight above 1 makes them inexact. The initial negotiation uses weight 1 (exact A*). The tree
that is placed still comes from the exact search. Flags off: byte-identical to router c05f101
with time-free flags (hard case_01/02/07, max_iters 400); flags on: legal on intro 01/03/05,
hard 01, designs ctrl, scale 01; deterministic at a fixed move cap.

| case | seed | baseline | S1 | r % | moves/s | s to first legal |
|---|---:|---:|---:|---:|---|---|
| hard case_05 | 1 | 15,645 | 15,395 | +1.61 | 244 → 665 | 3.1 → 2.6 |
| hard case_05 | 2 | 15,401 | 15,385 | +0.10 | 269 → 714 | 3.0 → 2.2 |
| hard case_09 | 3 | 21,814 | 21,572 | +1.12 | 180 → 505 | 5.7 → 4.4 |
| congested case_01 | 1 | 55,641 | 54,755 | +1.61 | 81 → 189 | 29.3 → 19.5 |
| congested case_01 | 2 | 55,545 | 54,655 | +1.62 | 78 → 177 | 29.5 → 19.7 |
| designs ctrl | 1 | 51,988 | 51,516 | +0.91 | 69 → 122 | 33.1 → 24.0 |
| designs ctrl | 3 | 51,614 | 51,680 | −0.13 | 72 → 121 | 32.0 → 23.7 |

Mean r +0.98%, 6/7 better. These rows used the patch before the initial negotiation got
weight 1; with it, designs ctrl seed 3 reached 51,318 (r +0.57%, first legal at 17.7 s) and scale
case_08 at 240 s went 111,625 → 110,397 (r +1.11%, first legal 91 → 68 s). Per move, the
inexact search improves less often on big grids (designs 11.4% → 8.2% of moves, congested
9.2% → 6.2%) but costs 2.1–2.8× less; on hard the rate is unchanged. Inexact goal direction in
the *initial* negotiation (weight 2) reached legality twice as fast but started from a worse
allocation: congested −1.9%, designs −1.0% at 120 s. Keep the initial phase exact.

**Batch matching is falsified here** (`research/tools/pool_selection.py`, hard case_05,
given solution = our 15,645 route). Surge-price mode: 120 rounds, 8,881 candidate trees
(median 105 per net); the LP relaxation over the pool and the integer optimum both equal the
given 15,645. Column generation with the LP's own dual prices: 40 rounds, 4,111 trees with
reduced cost down to −300 every round; the LP value never moved. Each priced tree needs
coordinated partners that independent pricing never produces. Improving routes must be built
against the live occupancy, one displaced net after another (chains), not selected from
independently generated alternatives. Drop route-pool set packing (#3 in next_moves.md).

**Protocol blind spot.** exp-011 (A*): congested +1.8%, designs +2.1%, hard 0.0%; the dev mean
was +0.36% → "inconclusive", because 9 of 11 dev cases are hard, where search is saturated
(~11,800 moves per net in 300 s vs ~215 on designs). Speed ideas need a tier-balanced verdict:
the mean of per-tier mean r, with each tier also checked separately.

## 2026-10-18 — S1 measured (exp-036..038), S3 built

Terms: *r* = 100 × log(baseline delay / candidate delay) per (case, seed), checker numbers;
*tier mean r* = mean over that tier's runs; *balanced* = mean of the tier means (S2).
Baseline = Jiangbanya v4 per-tier flags; S1 = `--set neg_int=4 --set neg_goal=1.5`; 300 s,
1 thread, seeds 1–3, baseline and candidate in the same batch (2 + 2 jobs on 4 cores).

| tier | cases | mean r | runs better | S2 decision |
|---|---|---:|---:|---|
| hard | case_01/05/09 | +0.22% | 4/9 | inconclusive (r per run −0.34 … +1.21) |
| congested | case_01/02 | +0.78% | 6/6 | adopt |
| designs | ctrl, int2float | +1.09% | 6/6 | adopt |

Balanced mean +0.69% (predicted +0.8%; per tier +0.4 / +1.2 / +0.7). The speed-up pays
where the search is unsaturated: big grids (~200–300 moves per net in 300 s) gain on every
run; hard (thousands of moves per net) only shuffles noise. The old dev protocol (9 of 11
cases hard) would have called this inconclusive.

Goal weight (exp-037, congested + designs, one interleaved batch with a fresh 1.5): 1.0 vs
1.5 congested −0.44% (0/6), designs +0.08% (3/6, a tie); 2.0 vs 1.5 congested −0.12%,
designs −0.27%. Keep 1.5. The fresh 1.5 runs reproduce exp-036 against the v4 baseline
(congested +0.79%, designs +1.01%): the effect is stable across batches.

Confirmation at submission settings (exp-038: 4 threads, 1,800 s, seed 1; baseline = the
v4 timed run on the same machine type, budget, threads and seed, not rerun):

| case | v4 | v4 + S1 | r |
|---|---:|---:|---:|
| congested case_01 | 53,517 | 53,667 | −0.28% |
| congested case_02 | 95,382 | 95,456 | −0.08% |
| designs ctrl | 50,434 | 50,084 | +0.70% |
| designs int2float | 92,280 | 91,752 | +0.57% |

S1 holds on designs (+0.64%, 2/2) and vanishes on congested (−0.18%, 0/2): 4 threads × 1,800 s
is ~24× the compute of the 300 s single-thread test, enough to saturate congested as well.
A speed idea's gain must be checked at the budget it will run with; the 300 s single-thread
screen overstates it on mid-size cases. Next config candidate: v4 + S1 on designs only.

S3 (ejection chains, `ej_p`, router f132009): flags off byte-identical; deterministic with
S1 + S3; legal on all router tests and on congested case_01. Smoke runs (contended, not a
measurement): chains cost 0.65–3.2 ms per move vs 4.3–7.8 ms for group moves; delay gained
per CPU-second ~3× the group moves' on hard case_05 (8 s) and ~1.1× the window move's on
congested case_01 (240 s). First test registered as exp-039 (not run).

## 2026-10-18 — sparse tiers timed (exp-040..043), stress deadline fixed, congested split registered

Config: v4 hard flags + S1 (`--set neg_int=4 --set neg_goal=1.5`), 4 threads, router 858a703.
Checker aggregates, ranks among entries that report runtime:

| tier | v5 | runtime | rank | entries with runtime ahead / behind |
|---|---:|---:|---:|---|
| intro (60 s/case) | 1.1406 | 1,122 s | 2 | pathfinder_lns 1.1514 (46,477 s) / iamparv7043 1.1254 |
| scale (300 s/case) | 1.1152 | 2,393 s | 3 | pathfinder_lns 1.1277, warm_lns_refinement 1.1274 (derived) / iamparv7043 1.1010 |
| stress (2,400 s) | 1.0798 | 2,399 s | 3 | pathfinder_lns 1.0914, warm_lns_refinement 1.0911 (derived) / — |

- Screen (exp-040): on intro case_13–20 we beat iamparv7043 on 8/8 (+2.31%) and trail
  pathfinder_lns on 8/8 (−1.56%); on scale case_01/08 +1.3% vs iamparv7043, −0.6/−1.6% vs
  pathfinder_lns. Intro #1 needs ~+0.95% on the aggregate.
- Stress (exp-042): S1 cuts a negotiation round from ~180 s to ~33 s; first legal at 1,025 s
  of a 2,400 s limit (escalation at 35% closes it in 7 rounds). The +49 s overshoot of
  2026-10-16 is gone: the congestion-free pass now stops at the deadline (routes unchanged)
  and `deadline_guard` stops starting moves that would cross it; both stress runs ended at
  2,399.2–2,399.4 s. Exact-reroute sweeps after legality ran 42 × 21 s (2–5 nets improved
  each at the end); cutting them (`refine_stop=0.01`) cost 0.09% because stress moves cost
  1.6–2.1 s and gain as little.
- Congested (exp-041, registered, not run): `run_router.py --time-total '{"congested": 7200}'`
  gives case_01..04 1,209.7 / 1,668.8 / 2,120.6 / 2,200.8 s (166/229/291/302 nets); the
  formula goes into meta.json as `time_limit_policy` (`package_submission.py --time-policy`).

Designs sync (exp-044, 4 threads, 1,800 s, seed 1, S1): par_sync 600 vs 10 (the exp-038 runs):
ctrl 49,880 vs 50,084 (+0.41%), int2float +0.51%. With S1 and the low threshold, longer
independent walks pay on designs. Timed designs run at 3,600 s/case with S1 + par_sync 600
registered as exp-045 (not run; needs Kevin's OK).

## 2026-10-19 — best config per tier, and what more time buys (from existing runs)

Gain from more time, same config, 4 threads unless stated (r = 100 × log(short / long delay)):

| tier, config | case | short → long | r | r per doubling |
|---|---|---|---:|---:|
| hard, v4 | case_01 / 05 / 09 | 300 → 600 s | +0.92 / +0.76 / +0.01% | +0.56% (mean) |
| congested, v4 | case_01 | 300 → 1,800 s | +1.31% | +0.51% |
| designs, v3 search | ctrl | 300 → 1,800 s | +0.84% | +0.32% |
| designs, v3 search, 1 thread | ctrl | 300 → 1,800 s | +1.87% | +0.72% |

About +0.3–0.6% per doubling, falling with size of the remaining gap (hard case_09 is flat).
There is nothing to train: the router is a search; "fine-tuning" here means choosing the
schedule (threshold, sync) at the budget it will run with (short-budget tuning picks the
wrong winners, exp-027..030) and buying time. Warm starts from saved routes are excluded
(CLAUDE.md rule 3).
