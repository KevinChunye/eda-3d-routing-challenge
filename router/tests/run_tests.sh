#!/usr/bin/env bash
# Router tests: build, route a few cases and verify each with the repo checker, then check
# determinism (same seed + iteration cap -> byte-identical output).
# Usage (from repo root or router/): bash router/tests/run_tests.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
make -s -C router
BIN=router/build/m3d_route
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
EXTRA=("$@")

check() {  # suite case time
  local suite=$1 case=$2 t=$3
  local out="$TMP/${suite}_${case}.sol.json"
  "$BIN" --instance "$suite/$case.json" --out "$out" --time-limit "$t" --seed 1 --threads 1 "${EXTRA[@]}" > "$TMP/stdout"
  python3 -m m3d.cli evaluate --case "$suite/$case.json" --sol "$out" --suite "$suite" > "$TMP/eval.txt"
  if ! grep -q "legal=True" "$TMP/eval.txt"; then
    echo "FAIL $suite/$case"; cat "$TMP/eval.txt"; exit 1
  fi
  echo "ok   $suite/$case  $(tail -1 "$TMP/stdout")"
}

for c in case_01 case_02 case_03 case_04 case_05; do check benchmarks $c 3; done
check benchmarks_hard case_01 5

# determinism: same seed and move cap -> identical bytes
for i in 1 2; do
  "$BIN" --instance benchmarks_hard/case_02.json --out "$TMP/det$i.sol.json" --time-limit 60 --seed 7 \
    --threads 1 --set max_iters=300 "${EXTRA[@]}" > /dev/null
done
cmp "$TMP/det1.sol.json" "$TMP/det2.sol.json" && echo "ok   determinism (seed 7, max_iters=300)"
echo "all router tests passed"
