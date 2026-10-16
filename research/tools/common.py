"""Shared helpers for the research tools. Run every tool from the repository root."""
import glob
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATE = os.path.join(REPO, "research", "state")
RUNS = os.path.join(REPO, "research", "runs")
sys.path.insert(0, REPO)

from m3d.cli import _tier_dir_map, _load_manifest  # noqa: E402

TIERS = ["intro", "hard", "scale", "stress", "congested", "designs"]


def suite_dir(tier):
    d = _tier_dir_map()[tier]
    return d if os.path.isabs(d) else os.path.join(REPO, d)


def manifest(tier):
    return _load_manifest(suite_dir(tier))


def case_names(tier):
    return [c["name"] for c in manifest(tier)["cases"]]


def instance_path(tier, case):
    return os.path.join(suite_dir(tier), f"{case}.json")


def load_json(path):
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)


def dev_set():
    """{tier: [cases]} used for experiments (research/state/dev_set.json)."""
    return load_json(os.path.join(STATE, "dev_set.json"))


def select_cases(spec):
    """'dev' -> dev set; 'all' -> every case of every tier; 'hard' or 'hard:case_01,case_02'
    -> that tier (or those cases); several specs may be joined with '+'."""
    if spec == "dev":
        return dev_set()
    if spec == "all":
        return {t: case_names(t) for t in TIERS}
    out = {}
    for part in spec.split("+"):
        tier, _, cases = part.partition(":")
        out[tier] = cases.split(",") if cases else case_names(tier)
    return out


def seed_dirs(run_dir):
    """A run dir holds seed<N>/<tier>/<case>.sol.json; a bare <tier>/ layout counts as one seed."""
    seeds = sorted(glob.glob(os.path.join(run_dir, "seed*")))
    return seeds if seeds else [run_dir]
