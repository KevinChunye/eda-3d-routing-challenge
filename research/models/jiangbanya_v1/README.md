# Jiangbanya v1

Submitted as PR #63 (`partcleda/eda-3d-routing-challenge`), branch
`submit_jiangbanya_20261016` on the fork. Checker scores, one timed run per case, seed 1,
1 thread, Intel Xeon @ 2.10 GHz (4 vCPU), 16 GB:

| tier | score | total delay | total runtime | legal |
|---|---:|---:|---:|:---:|
| hard | 1.3303 | 151,747 | 531 s (60 s/case) | 9/9 |
| congested | 1.2367 | 524,333 | 1,196 s (300 s/case) | 4/4 |
| designs | 1.3685 | 219,751 | 897 s (300 s/case) | 3/3 |

- Router commit: `2b51d4c` on `m3d_research` (experiment exp-007).
- Flags: `--set lns=1 --set gneg=6 --set lns_k=6 --set fan_alpha=0.3 --set lns_mix=1`
- Method: PathFinder negotiation (present cost ×1.03/round, congestion × k^-0.3 for a k-sink
  net) → exact per-net shortest-path-tree reroute → neighborhood search (groups of up to 6
  nets from the target's congestion-free tree or a 7×7 window, chosen adaptively; negotiation
  inside the group; keep if the group's delay does not rise).

## Files

- `submission.tar.gz`: the exact files in PR #63 (`submissions/{hard,congested,designs}/Jiangbanya/`).
  Extract from the repo root on a submission branch: `tar xzf research/models/jiangbanya_v1/submission.tar.gz`.
- `run_hard_case01.gif`: one 60 s run of hard case_01 with snapshots (same flags). Red rings are
  grid points shared by two nets; legal after 1.7 s at delay 9,872, 8,908 at 59 s.
- `layers_hard_case01.gif`: the submitted hard case_01 routes, layer by layer (`m3d animate`).
