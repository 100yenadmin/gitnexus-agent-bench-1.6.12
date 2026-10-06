#!/bin/bash
# Track H base for one mined hermes-agent task (adapted from Track O's setup_o_base.sh):
#   1. history-sanitized clone: ancestors of base_sha only (depth 500), no tags, no remote, reflog expired + gc,
#      so the fix commit is unreachable AND absent from the object store (verified);
#   2. deps: the .venv of the validated mining checkout (APFS copy; built --no-install-project, so it holds no
#      path back into the mining checkout);
#   3. index: APFS copy of a seed hermes-agent index (indexed at d62fbea7; SEED_INDEX_HERMES), meta paths rebound;
#   4. re-analyze at base_sha with the bench refresh in the dedicated Track H home/state
#      (home-h-hermes, refresh-state-h-hermes, launcher-ro-h-hermes.sh). SKIP_ANALYZE=1 stops before step 4.
# The clone source is mining/_src/hermes-agent.git, a full-blob bare clone of NousResearch/hermes-agent main
# (shallow since 2026-09-28; it contains the bench src's origin/main tip 4787e4d56f). The bench src itself
# ($BENCH_ROOT/src/hermes-agent) is a blobless partial clone: a file:// clone of it
# cannot serve history blobs, and Track O's bases carried full history blobs at depth 500.
# Parallel builds (build_h_bases.sh runs 2): steps 1-3 run in parallel; the rows.tsv append and the analyze
# run under one lock per state ($ST/.analyze.lock). Reason: bench-refresh.sh aborts a run (registry-lost)
# when another row in its rows.tsv has storage but no registry entry yet, and its own refresh lock waits at
# most 1 h, while a hermes-agent analyze took 1-3 h on our machine.
# Usage: setup_h_base.sh <task-id> [tasks-json]
set -euo pipefail
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../isolation" && pwd)/_config.sh"
ISO=$_HARNESS/isolation
B=${HERMES_ARTIFACTS:?set HERMES_ARTIFACTS}
M=${HERMES_MINING_DIR:-$B/mining}
BR=${BENCH_ROOT:?set BENCH_ROOT}
ST=$BR/refresh-state-h-hermes
GH=$BR/home-h-hermes
L=$ISO/launcher-ro-h-hermes.sh
export PATH=/usr/bin:/bin:/usr/sbin:/sbin${EXTRA_PATH:+:$EXTRA_PATH}

if [ "${1:-}" = "--locked-step" ]; then
  # Runs under $ST/.analyze.lock (see below): register the row, then (unless SKIP_ANALYZE=1) analyze.
  ID=$2; BASE=$BR/tasks/h/$ID
  grep -q "^$ID	" "$ST/rows.tsv" 2>/dev/null \
    || printf '%s\t%s\t%s\t1\t1\n' "$ID" "$BASE" "$BASE/.gitnexus" >> "$ST/rows.tsv"
  if [ "${SKIP_ANALYZE:-0}" = 1 ]; then
    echo "SKIP_ANALYZE=1: base ready, row registered, not analyzed: $BASE"; exit 0
  fi
  # No --force: in bench-refresh.sh it only bypasses the "already current" SKIP. Every Track H base has
  # HEAD = base_sha != d62fbea7 (the copied index's lastCommit), so the row is never skipped on a first build,
  # and analyze always runs with the CLI's own --force (full graph rebuild that reuses the copied parse cache
  # and the vectors of unchanged nodes by content hash). On a rerun after a successful analyze the SKIP is
  # correct; a failed analyze leaves pending/<id>, which forces the retry anyway.
  GITNEXUS_REFRESH_LAUNCHER=$L GITNEXUS_REFRESH_STATE=$ST "$ISO/bench-refresh.sh" --wait "$ID" || true
  grep "	$ID	" "$ST/refresh.log" | tail -1
  exit 0
fi

ID=$1
TJ=${2:-$M/tasks-h.json}
read -r BASE_SHA FIX_SHA < <(/usr/bin/python3 -c "
import json; t=[x for x in json.load(open('$TJ')) if x['id']=='$ID'][0]; print(t['base_sha'], t['fix_sha'])")
SRC=$M/_src/hermes-agent.git
LIVEIDX=${SEED_INDEX_HERMES:-$BR/src/hermes-agent/.gitnexus}     # seed index storage dir (lastCommit d62fbea7); read-only here
BASE=$BR/tasks/h/$ID
MR=$M/$ID/repo
[ -e "$BASE" ] && { echo "exists: $BASE"; exit 1; }
[ -x "$L" ] || { echo "missing launcher $L"; exit 1; }
[ -x "$MR/.venv/bin/python" ] || { echo "no validated mining venv: $MR/.venv"; exit 1; }
[ "$(git -C "$MR" rev-parse HEAD)" = "$BASE_SHA" ] || { echo "mining checkout not at base"; exit 1; }
mkdir -p "$BR/tasks/h" "$ST/embedded" "$ST/logs" "$ST/pending" "$GH"
[ -s "$GH/registry.json" ] || { echo '[]' > "$GH/registry.json"; chmod 600 "$GH/registry.json"; }

# 1. Sanitized clone.
git -C "$SRC" branch -f "bench-$ID" "$BASE_SHA"
git clone -q --no-tags --single-branch --branch "bench-$ID" --depth 500 "file://$SRC" "$BASE"
git -C "$SRC" branch -D -q "bench-$ID"
git -C "$BASE" branch -m "bench-$ID" main
git -C "$BASE" remote remove origin
git -C "$BASE" reflog expire --expire=now --all
git -C "$BASE" gc -q --prune=now
[ "$(git -C "$BASE" rev-parse HEAD)" = "$BASE_SHA" ] || { echo "HEAD mismatch"; exit 1; }
if git -C "$BASE" cat-file -e "$FIX_SHA" 2>/dev/null; then echo "FIX OBJECT PRESENT"; exit 1; fi
[ "$(git -C "$BASE" for-each-ref --format='%(refname)')" = "refs/heads/main" ] || { echo "extra refs"; exit 1; }
[ -z "$(git -C "$BASE" remote)" ] || { echo "remote left"; exit 1; }
[ -z "$(git -C "$BASE" tag -l)" ] || { echo "tags left"; exit 1; }

# 2. Deps: exactly the ignored .venv the validated mining checkout ran the controls with.
cp -cR "$MR/.venv" "$BASE/.venv"
echo ".gitnexus" >> "$BASE/.git/info/exclude"
[ -z "$(git -C "$BASE" status --porcelain --untracked-files=normal)" ] || { echo "dirty base"; git -C "$BASE" status --porcelain | head; exit 1; }

# 3. Index: the seed hermes-agent index (d62fbea7) with its meta rebound to this base.
cp -cR "$LIVEIDX" "$BASE/.gitnexus"
/usr/bin/python3 - "$BASE" <<'PY'
import json, os, sys
d = sys.argv[1]
for fn in ("gitnexus.json", "meta.json"):
    p = os.path.join(d, ".gitnexus", fn)
    if os.path.exists(p):
        m = json.load(open(p)); m["repoPath"], m["storagePath"] = d, os.path.join(d, ".gitnexus"); json.dump(m, open(p, "w"))
PY
cp "${SEED_EMBED_STAMP_DIR:?set SEED_EMBED_STAMP_DIR}/hermes-agent" "$ST/embedded/$ID"   # vector identity stamp

# 4. Register + analyze, serialized per state.
exec /usr/bin/lockf -k -t 43200 "$ST/.analyze.lock" /bin/bash "$(cd "$(dirname "$0")" && pwd)/$(basename "$0")" --locked-step "$ID"
