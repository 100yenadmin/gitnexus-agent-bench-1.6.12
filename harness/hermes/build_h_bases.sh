#!/bin/bash
# Build every Track H base, 2 setup_h_base.sh processes at a time. Clone/deps/index-copy overlap; the analyze
# steps serialize inside setup_h_base.sh on the per-state lock (one hermes-agent analyze at a time).
# Usage: build_h_bases.sh [id ...]   (default: every task in mining/tasks-h.json, in file order)
# Env: SKIP_ANALYZE=1 is passed through. Logs: $HERMES_ARTIFACTS/logs/setup_h_<id>.log + .../logs/build_h_bases.log
B=${HERMES_ARTIFACTS:?set HERMES_ARTIFACTS}
HD=$(cd "$(dirname "$0")" && pwd)
LOGS=$B/logs
SELF="$HD/build_h_bases.sh"
mkdir -p "$LOGS"
if [ "${1:-}" = "--one" ]; then   # worker: one task
  id=$2; log=$LOGS/setup_h_$id.log
  echo "== $id start $(date -u +%FT%TZ)" > "$log"
  if "$HD/setup_h_base.sh" "$id" >> "$log" 2>&1; then r=OK; else r="FAILED rc=$?"; fi
  echo "== $id $r $(date -u +%FT%TZ)" | tee -a "$log" >> "$LOGS/build_h_bases.log"
  exit 0
fi
if [ "$#" -gt 0 ]; then
  IDS="$*"
else
  IDS=$(/usr/bin/python3 -c "import json; print(' '.join(t['id'] for t in json.load(open('$B/mining/tasks-h.json'))))")
fi
echo "== start $(date -u +%FT%TZ) ids: $IDS" >> "$LOGS/build_h_bases.log"
printf '%s\n' $IDS | /usr/bin/xargs -P 2 -n 1 /bin/bash "$SELF" --one
echo "== done $(date -u +%FT%TZ)" >> "$LOGS/build_h_bases.log"
tail -n 30 "$LOGS/build_h_bases.log"
