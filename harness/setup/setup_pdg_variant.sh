#!/bin/bash
# PDG variant of a bench base: APFS copy (deps + index), rebind index metadata, force re-analyze with --pdg.
set -euo pipefail
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../isolation" && pwd)/_config.sh"
ISO=$_HARNESS/isolation
BR=${BENCH_ROOT:?set BENCH_ROOT}
SRC_BASE=$1; NAME=$2   # e.g. tasks/gnxu/gnxu-base gnxu-pdg
DST=$(dirname "$BR/$SRC_BASE")/$NAME
[ -e "$DST" ] && { echo "exists: $DST"; exit 1; }
cp -cR "$BR/$SRC_BASE" "$DST"
/usr/bin/python3 - "$DST" <<'PY'
import json, os, sys
d = sys.argv[1]
for fn in ("gitnexus.json", "meta.json"):
    p = os.path.join(d, ".gitnexus", fn)
    if os.path.exists(p):
        m = json.load(open(p)); m["repoPath"], m["storagePath"] = d, os.path.join(d, ".gitnexus"); json.dump(m, open(p, "w"))
PY
cp "$BR/refresh-state/embedded/$(basename "$SRC_BASE")" "$BR/refresh-state/embedded/$NAME"
printf '%s\t%s\t%s\t1\t1\n' "$NAME" "$DST" "$DST/.gitnexus" >> "$BR/refresh-state/rows.tsv"
GITNEXUS_REFRESH_LAUNCHER=$ISO/launcher-ro.sh GITNEXUS_REFRESH_STATE=$BR/refresh-state GITNEXUS_BENCH_ANALYZE_EXTRA=--pdg \
  "$ISO/bench-refresh.sh" --force "$NAME" || true
tail -2 "$BR/refresh-state/refresh.log"
jq -c '{lastCommit, emb:.stats.embeddings, pdg:(.capabilities.pdg // .analysisFeatures.pdg // null)}' "$DST/.gitnexus/gitnexus.json"
