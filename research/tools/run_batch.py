"""Run several router configurations as one interleaved batch (dev experiments only).

Every (config, tier, case, seed) job goes into one pool of --jobs workers, so all configs
share the machine at the same time and drift between them cancels. Each config writes the
same layout as run_router.py: research/runs/<label>/seed<N>/<tier>/<case>.sol.json, plus
runtime.json and stats.jsonl per tier (with the router's STAT / ARMS / MERGE lines when it
runs with --set verbose=1). Timed submission runs still use run_router.py.

Usage (from repo root):
  python3 research/tools/run_batch.py --cases "hard:case_01+designs:ctrl" --seeds 1 2 3 \
      --time-limit 300 --jobs 4 --threads 1 --cmd "<router command with {instance} {out}
      {time} {seed} {threads} {tier} {extra}>" \
      --config exp-037-g10="--set neg_goal=1.0" --config exp-037-g20="--set neg_goal=2.0"
"""
import argparse
import datetime
import json
import os
from concurrent.futures import ThreadPoolExecutor

from common import RUNS, instance_path, select_cases
from run_router import git_sha, machine, run_one


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cmd", required=True)
    ap.add_argument("--cases", required=True)
    ap.add_argument("--seeds", type=int, nargs="+", default=[1])
    ap.add_argument("--time-limit", type=float, default=30.0)
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--config", action="append", required=True, help="label=extra flags")
    args = ap.parse_args()

    configs = [c.split("=", 1) for c in args.config]
    cases = select_cases(args.cases)
    jobs = []
    for seed in args.seeds:  # seed-major, configs interleaved: every config advances together
        for tier, names in cases.items():
            for case in names:
                for label, extra in configs:
                    tdir = os.path.join(RUNS, label, f"seed{seed}", tier)
                    os.makedirs(tdir, exist_ok=True)
                    out = os.path.join(tdir, f"{case}.sol.json")
                    if os.path.exists(out):
                        os.remove(out)
                    cmd = args.cmd.format(instance=instance_path(tier, case), out=out, time=args.time_limit,
                                          seed=seed, threads=args.threads, tier=tier, case=case, extra=extra)
                    jobs.append(dict(label=label, seed=seed, tier=tier, case=case, out=out, cmd=cmd,
                                     time_limit=args.time_limit, hard_timeout=1.5 * args.time_limit + 60))
    for label, extra in configs:
        os.makedirs(os.path.join(RUNS, label), exist_ok=True)
        with open(os.path.join(RUNS, label, "run_info.json"), "w") as fh:
            json.dump(dict(label=label, cmd=args.cmd, extra=extra, cases=args.cases, seeds=args.seeds,
                           time_limit=args.time_limit, threads=args.threads, jobs=args.jobs,
                           batch=[c[0] for c in configs], git_sha=git_sha(), machine=machine(),
                           started=datetime.datetime.now().isoformat(timespec="seconds")), fh, indent=1)

    results = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for r in pool.map(run_one, jobs):
            results.append(r)
            flag = "ok" if r["ok"] else f"FAILED rc={r['rc']}"
            print(f"{r['label']} seed{r['seed']} {r['tier']}/{r['case']}: {r['secs']:.1f}s {flag}", flush=True)

    by_dir = {}
    for r in results:
        key = os.path.dirname(r["out"])
        if key not in by_dir:
            by_dir[key] = []
        by_dir[key].append(r)
    for tdir, rs in by_dir.items():
        with open(os.path.join(tdir, "runtime.json"), "w") as fh:
            json.dump({r["case"]: round(r["secs"], 3) for r in rs if r["ok"]}, fh, indent=1)
        with open(os.path.join(tdir, "stats.jsonl"), "w") as fh:
            for r in rs:
                stat = [ln for ln in r["stderr_tail"].splitlines() if ln.startswith(("STAT", "ARMS", "MERGE"))]
                fh.write(json.dumps(dict(case=r["case"], secs=round(r["secs"], 3), rc=r["rc"],
                                         ok=r["ok"], stats=r["stats"], move_stats=stat)) + "\n")
    print(f"\n{sum(r['ok'] for r in results)}/{len(results)} runs produced a file")


if __name__ == "__main__":
    main()
