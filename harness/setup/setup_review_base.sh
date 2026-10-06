#!/bin/bash
# Review-case base: parentless snapshot of GitNexus at <sha> without eval/workflow_bench (hidden labels) and
# without .claude/skills (v1.6.12 skills are installed per run, untracked), deps installed, index = APFS copy of
# the Track U index re-analyzed here with --pdg (upstream's review bench uses PDG indexes) by the bench refresh.
set -euo pipefail
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../isolation" && pwd)/_config.sh"
ISO=$_HARNESS/isolation
SHA=$1; NAME=$2
BR=${BENCH_ROOT:?set BENCH_ROOT}
SRC=${GITNEXUS_SRC:?set GITNEXUS_SRC (a full clone of abhigyanpatwari/GitNexus)}
BASE=$BR/tasks/review/$NAME
export PATH=${NODE_BIN_DIR:-$(dirname "${NODE_BIN:?set NODE_BIN}")}:/usr/bin:/bin:/usr/sbin:/sbin${EXTRA_PATH:+:$EXTRA_PATH}
[ -e "$BASE" ] && { echo "exists: $BASE"; exit 1; }
mkdir -p "$BASE"
git -C "$SRC" archive "$SHA" | tar -x -C "$BASE"
rm -rf "$BASE/eval/workflow_bench" "$BASE/.claude/skills"
cd "$BASE"
git init -q -b main
git -c user.name=bench -c user.email=bench@localhost add -A
git -c user.name=bench -c user.email=bench@localhost commit -q -m "GitNexus $SHA bench snapshot"
echo ".gitnexus" >> .git/info/exclude
(npm ci --no-audit --no-fund --loglevel=error) > "$BASE/../$NAME-npm-root.log" 2>&1 || echo "WARN root npm ci failed"
(cd gitnexus-shared && npm ci --no-audit --no-fund --loglevel=error && npm run build) > "$BASE/../$NAME-npm-shared.log" 2>&1 || echo "WARN shared failed"
(cd gitnexus && npm ci --no-audit --no-fund --loglevel=error) > "$BASE/../$NAME-npm-gitnexus.log" 2>&1 || echo "WARN gitnexus npm ci failed"
[ -e node_modules/gitnexus-shared ] || ln -s ../gitnexus-shared node_modules/gitnexus-shared
git status --porcelain --untracked-files=normal | head -3
cp -cR "$BR/tasks/gnxu/gnxu-base/.gitnexus" "$BASE/.gitnexus"
/usr/bin/python3 - "$BASE" <<'PY'
import json, os, sys
d = sys.argv[1]
for fn in ("gitnexus.json", "meta.json"):
    p = os.path.join(d, ".gitnexus", fn)
    if os.path.exists(p):
        m = json.load(open(p)); m["repoPath"], m["storagePath"] = d, os.path.join(d, ".gitnexus"); json.dump(m, open(p, "w"))
PY
cp "$BR/refresh-state/embedded/gnxu-base" "$BR/refresh-state/embedded/$NAME"
( flock 9 2>/dev/null || true; printf '%s\t%s\t%s\t1\t1\n' "$NAME" "$BASE" "$BASE/.gitnexus" >> "$BR/refresh-state/rows.tsv" ) 9>"$BR/refresh-state/.rows.lock"
GITNEXUS_REFRESH_LAUNCHER=$ISO/launcher-ro.sh GITNEXUS_REFRESH_STATE=$BR/refresh-state GITNEXUS_BENCH_ANALYZE_EXTRA=--pdg \
  "$ISO/bench-refresh.sh" --force --wait "$NAME" || true
grep "	$NAME	" "$BR/refresh-state/refresh.log" | tail -1
