"""Run a router on a set of cases, timing each case end to end (instance JSON -> .sol.json).

The same runner is used for experiments and for the submission run, so the runtime that
goes into runtime.json is measured exactly the way every dev number was measured.

Usage (from repo root):
  python research/tools/run_router.py --label exp-004 --cases dev --seeds 1 2 3 \
      --time-limit 30 --jobs 8 --threads 1 \
      --cmd "router/build/m3d_route --instance {instance} --out {out} --time-limit {time} --seed {seed} --threads {threads} {extra}"

Placeholders in --cmd: {instance} {out} {time} {seed} {threads} {tier} {case} {extra}.
Writes research/runs/<label>/seed<N>/<tier>/<case>.sol.json, a runtime.json per tier
({case: wall seconds}), stats.jsonl (the router's last stdout line, if it is JSON) and
research/runs/<label>/run_info.json (command, git sha, machine, budgets).

--jobs > 1 runs cases concurrently: fine for experiments, but the submission run must use
--jobs 1 on an otherwise idle machine so each case's wall clock is clean.
"""
import argparse
import datetime
import json
import os
import platform
import shlex
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

from common import REPO, RUNS, instance_path, select_cases


def machine():
    model = platform.processor() or "unknown CPU"
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                model = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    mem_gb = None
    try:
        for line in open("/proc/meminfo"):
            if line.startswith("MemTotal"):
                mem_gb = round(int(line.split()[1]) / 1024 / 1024)
                break
    except OSError:
        pass
    return {"cpu": model, "logical_cpus": os.cpu_count(), "ram_gb": mem_gb,
            "host": platform.node()}


def git_sha():
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                             capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                               cwd=REPO, capture_output=True, text=True).stdout.strip()
        return sha + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def run_one(job):
    cmd = job["cmd"]
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(shlex.split(cmd), cwd=REPO, capture_output=True, text=True,
                              timeout=job["hard_timeout"])
        rc, out, err = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        rc, out, err = "timeout", "", "killed after hard timeout"
    secs = time.perf_counter() - t0
    stats = None
    lines = [ln for ln in out.strip().splitlines() if ln.strip()]
    if lines:
        try:
            stats = json.loads(lines[-1])
        except ValueError:
            stats = None
    ok = rc == 0 and os.path.exists(job["out"])
    return dict(job, secs=secs, rc=rc, ok=ok, stats=stats, stderr_tail=err[-2000:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--cmd", required=True)
    ap.add_argument("--cases", default="dev")
    ap.add_argument("--seeds", type=int, nargs="+", default=[1])
    ap.add_argument("--time-limit", type=float, default=30.0, help="seconds per case")
    ap.add_argument("--time-limits", default="{}", help='per-tier override, e.g. {"stress": 1800}')
    ap.add_argument("--threads", type=int, default=1, help="threads the router may use per case")
    ap.add_argument("--jobs", type=int, default=1, help="cases run concurrently")
    ap.add_argument("--extra", default="", help="extra router flags (the candidate's switch)")
    args = ap.parse_args()

    per_tier = json.loads(args.time_limits)
    root = os.path.join(RUNS, args.label)
    jobs = []
    for seed in args.seeds:
        for tier, cases in select_cases(args.cases).items():
            tdir = os.path.join(root, f"seed{seed}", tier)
            os.makedirs(tdir, exist_ok=True)
            tl = float(per_tier.get(tier, args.time_limit))
            for case in cases:
                out = os.path.join(tdir, f"{case}.sol.json")
                if os.path.exists(out):
                    os.remove(out)
                cmd = args.cmd.format(instance=instance_path(tier, case), out=out, time=tl,
                                      seed=seed, threads=args.threads, tier=tier, case=case,
                                      extra=args.extra)
                jobs.append(dict(seed=seed, tier=tier, case=case, out=out, cmd=cmd,
                                 time_limit=tl, hard_timeout=1.5 * tl + 60))

    info = dict(label=args.label, cmd=args.cmd, extra=args.extra, cases=args.cases,
                seeds=args.seeds, time_limit=args.time_limit, time_limits=per_tier,
                threads=args.threads, jobs=args.jobs, git_sha=git_sha(), machine=machine(),
                started=datetime.datetime.now().isoformat(timespec="seconds"))
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(root, "run_info.json"), "w") as fh:
        json.dump(info, fh, indent=1)

    results = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for r in pool.map(run_one, jobs):
            results.append(r)
            flag = "ok" if r["ok"] else f"FAILED rc={r['rc']}"
            print(f"seed{r['seed']} {r['tier']}/{r['case']}: {r['secs']:.1f}s {flag}", flush=True)
            if not r["ok"]:
                print(r["stderr_tail"][-500:], flush=True)

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
                fh.write(json.dumps(dict(case=r["case"], secs=round(r["secs"], 3), rc=r["rc"],
                                         ok=r["ok"], stats=r["stats"])) + "\n")
    n_bad = sum(1 for r in results if not r["ok"])
    print(f"\n{len(results) - n_bad}/{len(results)} runs produced a file -> {root}")
    print("next: python research/tools/evaluate.py --run", root)


if __name__ == "__main__":
    main()
