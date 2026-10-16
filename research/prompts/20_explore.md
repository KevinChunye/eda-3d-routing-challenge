# 20 · Explore: decide what to try next, from evidence

**Goal.** Re-ground the backlog in where the incumbent actually loses delay, what changed
upstream, and what the literature says about the open question. No router changes in this
step, only diagnostics.

**Read first.** `CLAUDE.md`, STATE.md, the experiment log (`exp_log.py show --last 30`),
`research/state/ideas.md` and `research/state/findings.md`.

## Steps

1. **Where is the loss now?**
   - Run `python3 research/tools/gap_decompose.py --run research/runs/incumbent` and
     `python3 research/tools/evaluate.py --run research/runs/incumbent`.
   - Answer with numbers:
     - Which cause dominates: slow layer, detour or via?
     - Which nets carry the excess (sinks per net, distance)?
     - Which 3 dev cases have the largest gap to the bound, and what dominates in them?
   - Compare against the previous explore memo: what moved, and what didn't?
2. **What did the experiments teach?** Across the decisions since the last memo, find
   patterns. For example: ideas of one kind keep failing, or gains shrink at longer budgets
   (the search, not the start, is limiting). Check predictions against results: are we
   systematically over-optimistic?
3. **What changed outside?**
   - `git fetch upstream`, then diff `upstream/main` against what `m3d_research` last
     merged.
   - Look for new or updated entries under `submissions/` and their `meta.json` method
     lines.
   - Look for changes to `CONTRIBUTING.md`, the scorer, or `ENFORCE_RUNTIME` in
     `m3d/cli.py`.
   - If upstream moved, re-run `reference_points.py --exclude <entry_name>`.
4. **Literature.** At most 3 targeted web searches, each aimed at a specific open question
   from steps 1–2. Examples:
   - neighborhood selection in MAPF large-neighborhood search;
   - Lagrangian-price routing;
   - delay versus area trade-offs in routing trees.

   Record the source for anything you use.
5. **Rewrite the backlog.**
   - Add 3–6 ideas. Each needs: id, the evidence it addresses (a number from steps 1–2),
     mechanism, expected effect on the dev aggregate, cost (S/M/L), a falsification test and
     a priority.
   - Re-rank all open ideas.
   - Mark ideas that the evidence now contradicts as `rejected (evidence: ...)`.
   - Merge duplicates.
6. **Memo.** Append a dated memo of at most 20 lines to findings.md:
   - where the remaining loss is;
   - what the last experiments showed;
   - why the top 3 ideas are next.

   Define any new symbol in plain words.
7. **Commit and push.** Commit `explore <date>: <one-line summary>` and push
   `m3d_research`. Return to the calling prompt.
