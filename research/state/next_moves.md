# Next moves: design brief built on measurements (2026-10-17, during the v4 timed run)

Goal for the next version: the 2–3% that tuning the search policy (v4) did not deliver.
Each section states a question, what we measured on our own routes, and the design it
points to. Predictions are shrunk per findings.md (structural ideas have historically
delivered 0–40% of their predicted gain; search-dynamics ideas more than predicted).

## The question, made specific

A move rips up some nets and routes them again. Our moves pick a target net (by its excess
delay) and up to 5 more nets around it, renegotiate them and keep the result if the total
does not rise (or rises less than the threshold). For the next version we need answers to:

- **Q1 size.** How many nets must change at once to remove a typical sink's excess?
- **Q2 value.** Is the scarce fast area held by the nets that gain most from it?
- **Q3 locality.** Is the trouble concentrated in places, and are conflicts separable into
  independent regions (which decides how to parallelize)?
- **Q4 waste.** How much of the threads' work is thrown away, and can it be kept?
- **Q5 headroom.** Given unlimited effort on one window, does our repair find better routes
  (is the solution locally optimal for our move type, or just under-searched)?

## What the routes say (v3 submission, 16 cases; `research/tools/conflict_map.py`,
## `research/state/conflict_map_v3.csv`)

Terms: *ideal* = a sink's cheapest delay on an empty grid; *excess* = actual − ideal;
*corridor* = points on any cheapest empty-grid path of a sink; *blocker* = another net in
that corridor; *least-obstructed path* = the cheapest path crossing the fewest points of
other nets.

| measure (mean over cases) | hard | congested | designs |
|---|---:|---:|---:|
| excess over ideal | 31% | 30% | 31% |
| middle (fast) layers occupied | 88% | 85% | 79% |
| nets carrying 50% / 80% of the excess | 26% / 53% | 27% / 54% | 24% / 52% |
| distinct nets on the least-obstructed cheapest path (median) | 7.6 | 20 | 9 |
| share of excess on sinks with ≤ 3 such nets | 7% | 1% | 4% |
| blockers that are themselves at ideal | 1.5% | 0.3% | 0.9% |
| excess on pairs of nets that block each other | 87% | 96% | 92% |
| largest group of mutually blocking nets (share of nets) | 95% | 96% | 99% |
| share of excess in the hottest 10% of 8×8 tiles | 46% | 46% | 30% |

Fast-layer use (planar steps on the two middle layers, v3 routes):

| | hard | congested | designs |
|---|---:|---:|---:|
| fast steps serving only same-die sinks | 67% | 63% | 69% |
| downstream sinks per fast step (mean) | 2.6 | 2.6 | 1.6 |
| fast steps serving exactly one sink | 39% | 41% | 76% |

Answers so far:
- **Q1 size:** large. Clearing one sink's cheapest path needs 8–20 other nets moved, and
  each of those holds excess too. Our 6-net moves can only shuffle small amounts; this is
  why only 1–5% of moves improve. Bigger groups failed before (exp-015) because group
  negotiation cost grows faster than the group: the repair, not the destroy size, limits.
- **Q2 value:** a fast step is worth about 2 delay units per downstream sink. 39–76% of
  fast steps serve a single sink, so fast area on single-sink branches is the cheapest to
  give up, and trunks shared by several sinks the most valuable. Nothing in our moves uses
  this; targets are chosen by excess only.
- **Q3 locality:** trouble is concentrated (top 10% of tiles hold 30–46% of the excess,
  3–5× uniform) but not separable: one blocking group spans the grid. Parallel search can
  focus on hot tiles but cannot split the problem into independent parts; concurrent moves
  must be checked for collisions at commit time.
- **Q4 waste:** at every sync the 3 non-best threads' work is dropped. A merge that adopts
  another thread's improving nets plus the nets they displaced (`par_merge`, built tonight,
  exact gain, legal by construction) merged 2 closures in a starved 30 s smoke test; the
  real measurement needs the machine.
- **Q5 headroom:** not measured yet (needs CPU).

Test 0 (from existing logs): 4 threads make 3.7–4.2× the moves of 1 thread (hard
case_01 2,458 vs 598 moves/s; designs ctrl 149 vs 38). The hardware scales; the search
wastes it. On designs ctrl one walk made 67k moves in 1,800 s and reached 50,250; four
threads made 39k moves in 300 s and reached 50,858.

## Candidate designs, ranked (literature: two review agents, 2026-10-17; predictions shrunk)

Both reviews independently put "keep the threads' work" first. One notes a 2024
re-evaluation of LNS for multi-agent path finding in which plain random-walk neighbourhoods
over blocking agents beat adaptive and learned selection (arXiv 2407.09451): gains should
come from combining work and reaching further, not from smarter selection among the same
moves.

| # | design | evidence | predicted | cost | falsify |
|---|---|---|---:|---|---|
| 1 | **Merge at sync** (`par_merge`, built): the best thread adopts each improving net of another thread plus the nets it displaced; exact gain, legal by construction. Generalised partition crossover would pick per differing-net cluster. | Q4, Test 0; GPX2 for TSP ([Tinós et al.](https://storre.stir.ac.uk/bitstream/1893/28894/1/Gen_Partitition-crossover-ecj2019.pdf)) | +0.1–0.4% | S (done) | gain < 0.05% per sync, or closures blocked > 90% |
| 2 | **One shared walk, concurrent moves**: threads compute moves on snapshots, commit under a lock if their nets are unchanged and new points still free (optimistic concurrency); no reset to best | Test 0, designs 1 walk vs 4 threads; DROP-LNS for MAPF ([arXiv 2402.01961](https://arxiv.org/abs/2402.01961)); parallel annealing placement (Kravitz–Rutenbar) | +0.3–0.8% on big cases | M | log accepted moves: if > 30% would fail the commit check against the previous 3, drop |
| 3 | **Route-pool set packing**: keep 20–30 distinct trees per net from all threads; every few minutes an integer program (HiGHS) picks one tree per net with no shared point and least total delay | generalises #1 to many parents; GRIP global routing by integer programming over candidate routes ([DAC'09](https://doi.org/10.1145/1629911.1629999)); set partitioning over route pools in vehicle routing | +0.2–0.5% | M (prototype offline with `scipy.optimize.milp`) | < 0.2% over the best pooled solution in 60 s |
| 4 | **Corridor ejection moves sized by Q1**: give a long excess sink its least-obstructed cheapest path, evict the 8–20 nets on it, repair them one at a time by exact reroute (an ejection chain, no group negotiation, which is what made 8-net groups slow) | Q1; ejection chains for assignment problems; SISR partial ruin ([Christiaens & Vanden Berghe](https://pubsonline.informs.org/doi/10.1287/trsc.2019.0914)) | 0 to +0.5% | M | delay gained per CPU-second ≤ the window move's |
| 5 | **Value-aware victims and targets**: evict first the occupants whose fast steps serve one sink; target nets by regret against a priced best tree rather than raw excess | Q2 (39–76% of fast steps serve one sink); RINS-style relaxation-guided neighbourhoods | 0 to +0.3% | S–M | regret predicts move success no better than excess |
| 6 | **Focus**: skip a target after a failed move until a net near it changes (don't-look bits); weight hot tiles | Q3 (top 10% of tiles hold 30–46% of the excess) | 0 to +0.3% | S | P(improve | nothing changed since last failure) ≥ half the base rate |
| — | **Exact window integer program** as a diagnostic for Q5, not a move: solve 50 small windows of final solutions exactly | an optimal clip router took ~840 s per clip (OptRouter); fast replanning beat optimal replanning in MAPF | — | M | if < 10% of windows improve, the gap is not local → favour 1–4 |

Skipped: GPU maze routing (our grids are 36k points at most), Steiner-topology moves and
tree-shape changes (measured −0.12% / +0.03% before), auctions (exact only for small
instances).

## Experiment plan once the machine is free (in order)

1. **E1 merge** (75 min): 4 threads, 300 s, threshold 32 + bandit, sync 60 s, merge on vs
   off, hard case_01/05/09, congested case_01, designs ctrl; MERGE counters logged.
2. **E2 move log** (30 min): one run per tier that logs every accepted move (nets, bounding
   box, gain); offline: commit-conflict rate for #2, share of improving moves whose box fits a
   quadrant (region-parallel), don't-look statistics for #6.
3. **E3 window diagnostic** (offline, 1–2 h CPU): exact integer program on 50 windows of
   the v4 routes (`scipy.optimize.milp`); answers Q5.
4. Build #2 (shared walk) or #3 (route pool) depending on E1–E3; then #4.

Honest expectation: #1–#3 address the measured waste (threads) and could add +0.5–1%;
reaching +2–3% over v4 needs #4-type moves to work as well, which history says to doubt
until measured.
