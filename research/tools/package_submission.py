"""Package a timed run as a ready-to-extract submission tarball (never touches submissions/).

The tarball holds submissions/<tier>/<entry>/{<case>.sol.json, runtime.json, meta.json} for
each tier, so on a submission branch `tar xzf <tarball>` from the repo root puts the files in
place. runtime.json is copied unchanged from the run (wall clock measured by run_router.py).

Usage (from repo root):
  python3 research/tools/package_submission.py --run research/runs/submit-YYYYMMDD \
      --entry Jiangbanya --tiers hard congested designs --sha <router commit> --threads 1 \
      --method "..." --out research/models/<model>/submission.tar.gz
"""
import argparse
import datetime
import io
import json
import os
import subprocess
import tarfile

from common import load_json, seed_dirs


def machine_string():
    """"<CPU> (<logical CPUs> vCPU), <RAM> GB" on Linux (/proc) or macOS (sysctl)."""
    cpu, mem_gb = "unknown CPU", None
    try:
        with open("/proc/cpuinfo") as fh:
            for line in fh:
                if line.startswith("model name"):
                    cpu = line.split(":", 1)[1].strip()
                    break
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemTotal"):
                    mem_gb = round(int(line.split()[1]) / 1024 / 1024)
                    break
    except OSError:
        def sysctl(key):
            return subprocess.run(["sysctl", "-n", key], capture_output=True, text=True).stdout.strip()
        cpu = sysctl("machdep.cpu.brand_string") or cpu
        mem = sysctl("hw.memsize")
        mem_gb = round(int(mem) / 1024 ** 3) if mem.isdigit() else None
    return f"{cpu} ({os.cpu_count()} vCPU), {mem_gb} GB"


def add_bytes(tar, name, data):
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mtime = 0
    info.mode = 0o644
    tar.addfile(info, io.BytesIO(data))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--entry", required=True)
    ap.add_argument("--tiers", nargs="+", required=True)
    ap.add_argument("--sha", required=True, help="router commit on m3d_research")
    ap.add_argument("--threads", type=int, required=True)
    ap.add_argument("--method", required=True)
    ap.add_argument("--author", default="Kevin Wang (KevinChunye)")
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--out", required=True)
    ap.add_argument("--hardware", default=None, help="override the detected hardware string")
    args = ap.parse_args()

    run_seed = seed_dirs(args.run)[0]
    meta = {
        "author": args.author,
        "url": f"https://github.com/KevinChunye/eda-3d-routing-challenge/tree/{args.sha}/router",
        "method": args.method,
        "date": args.date,
        "hardware": args.hardware or machine_string(),
        "threads": args.threads,
        "router_commit": args.sha,
    }
    meta_bytes = (json.dumps(meta, indent=1) + "\n").encode()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with tarfile.open(args.out, "w:gz") as tar:
        for tier in args.tiers:
            src = os.path.join(run_seed, tier)
            dst = f"submissions/{tier}/{args.entry}"
            runtimes = load_json(os.path.join(src, "runtime.json"))
            for case in sorted(runtimes):
                with open(os.path.join(src, f"{case}.sol.json"), "rb") as fh:
                    add_bytes(tar, f"{dst}/{case}.sol.json", fh.read())
            with open(os.path.join(src, "runtime.json"), "rb") as fh:
                add_bytes(tar, f"{dst}/runtime.json", fh.read())
            add_bytes(tar, f"{dst}/meta.json", meta_bytes)
            print(f"{dst}: {len(runtimes)} routes")
    print("wrote", args.out)


if __name__ == "__main__":
    main()
