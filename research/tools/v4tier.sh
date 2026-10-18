#!/usr/bin/env bash
# Run the router with Jiangbanya v4 per-tier flags: v4tier.sh <binary> <tier> <router args...>
# Tier flags come first, so --set flags in <router args> override them (last value wins).
# Used by exp-036..038 and exp-044 (as /tmp/claude-0/v4tier.sh; before exp-044 the order was
# reversed, which made no difference there: their extra flags were not tier flags).
bin=$1; tier=$2; shift 2
BASE="--set lns=1 --set gneg=6 --set lns_k=6 --set fan_alpha=0.3 --set lns_mix=1 --set tie_rand=1 --set ta_t0=8 --set kick_after=300 --set restore_after=2000 --set gneg_sel=1 --set astar=1 --set par_sync=10"
case $tier in
  hard) T="--set ta_t0=32 --set bandit=1 --set par_sync=120" ;;
  congested) T="--set ta_t0=32 --set bandit=1 --set par_sync=360" ;;
  *) T="" ;;
esac
exec $bin $BASE $T "$@"
