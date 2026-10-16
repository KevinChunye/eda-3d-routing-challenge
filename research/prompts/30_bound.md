# 30 · Bound: certify how far from optimal we are

**Goal.** Shrink the certified gap, meaning (our delay ÷ best lower bound) − 1, by
strengthening the bound. Also measure the router's true optimality gap on instances small
enough to solve exactly. This tells the iterate loop where real headroom is and when to stop.

**Background (one-line recap).** `research/tools/lagrange_bound.py` (method `avg-toll-v1`)
replaces the one-net-per-grid-point rule with tolls. Each net pays the tolls on the points it
uses. Any toll setting gives a valid lower bound, and tolls rise where nets overlap. Its
known weakness: a net with k sinks is charged only the average toll of its k paths, so
branching trees are under-charged. On hard, the residual gap correlates 0.82 with the share
of sinks in multi-sink nets.

**Read first.** `CLAUDE.md`; STATE.md; the bound sections of `research/state/findings.md`;
`research/tools/lagrange_bound.py`; ideas D1 and D2 in `research/state/ideas.md`.

## Steps

1. **Validity harness (always first).** Write `research/tools/bound_tests.py`:
   - **Tiny instances.** Generate 20 instances with `m3d/generator.py`: 6×6 to 10×10, 6
     layers, 3–8 nets, fixed seeds.
   - **Exact optima.** Solve each exactly with a MIP: OR-Tools CP-SAT or HiGHS (`highspy`).
     - Variables: one binary per net per grid point and per edge; per sink, flow on
       directed edges.
     - Constraints: each point and edge used by at most one net; a net's edges form a
       connected tree spanning its pins; a sink's flow may use only its own net's edges.
     - Objective: the sum of sink path delays.
     - Validate each MIP solution with the repo checker.
   - **Bound check.** Any bound must satisfy bound ≤ optimum on every tiny instance, and
     bound ≤ checker-verified delay on every dev case.
   - **Router gap.** Record the router's true gap to optimum on the tiny instances.
2. **Strengthen per-net charging (D1).** Make one change at a time, each with its own method
   tag:
   - `max-toll-v2`: per net, the max of the averaged-toll bound and, for each sink s, (s's
     full-toll shortest path) + (the other sinks' toll-free shortest paths). Both are valid,
     so their max is too.
   - `exact-net-v3`: for nets with ≤ 8 sinks, the exact cheapest "delay + tolls" tree,
     solved as a small MIP inside the net's bounding box plus a margin.
   - Optional: add edge capacities, and block other nets' pins in each net's subproblem.

   For each change: pass the validity harness, run on hard, append method-tagged rows to
   `toll_bounds.jsonl`, re-run `reference_points.py`, and log it with `exp_log.py` (idea D1).
3. **Toll export (feeds idea B3).** Save the final tolls per case to
   `research/runs/tolls/<tier>/<case>.npy` (gitignored). Add an option to regenerate them.
4. **Memo.** Append a dated memo to findings.md:
   - a per-case certified gap table for hard (plus any larger cases computed);
   - how much each method moved the bound;
   - the router's true gap on tiny instances;
   - a one-paragraph read on whether the remaining gap is mostly bound looseness or real
     headroom.
5. **Commit and push.** Commit `bound <method>: hard certified gap <x.x>%` and push
   `m3d_research`.

## Stop when
A method fails the validity harness (fix or drop it; never publish an invalid bound), or the
session budget is used. Large cases (64×64 and up) take 25+ minutes each with v1; run them
only with spare cores.
