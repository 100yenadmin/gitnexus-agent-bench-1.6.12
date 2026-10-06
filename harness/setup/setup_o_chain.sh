#!/bin/bash
# Build Track O bases sequentially for one repo chain: setup_o_chain.sh <id> [<id> ...]
B=$(cd "$(dirname "$0")" && pwd)
for id in "$@"; do
  echo "== $id $(date -u +%H:%MZ)"
  "$B/setup_o_base.sh" "$id" 2>&1 | tail -15 || echo "FAILED $id"
done
echo "== chain done $(date -u +%H:%MZ)"
