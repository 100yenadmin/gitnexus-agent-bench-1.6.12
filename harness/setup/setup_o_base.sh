#!/bin/bash
# Track O base for one mined task: history-sanitized clone (ancestors of base_sha only, depth 500, no tags, no
# remote, so the fix commit is unreachable AND absent from the object store), deps copied from the validated mining
# checkout, index = APFS copy of the live index for that repo, re-analyzed at base_sha by the bench refresh in a
# SEPARATE bench home/state per repo (home-o-<repo>, refresh-state-o-<repo>) so it can run alongside the review-base builds.
# Usage: setup_o_base.sh <task-id> [tasks-json]
# Published version: "the live index" = a seed index you provide per repo (SEED_INDEX_LCMX / SEED_INDEX_WORLDOS:
# a checkout dir that holds a .gitnexus/ built by `gitnexus analyze`, ours were our everyday indexes of those repos)
# plus its embedding-identity stamp file in SEED_EMBED_STAMP_DIR (one line "voyage-code-4/1024/<text version>").
# The mining checkouts (mining/_src/<repo>, mining/<id>/repo) come from harness/mining/validate.py.
set -euo pipefail
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../isolation" && pwd)/_config.sh"
ISO=$_HARNESS/isolation
ID=$1
B=${BENCH_ARTIFACTS:?set BENCH_ARTIFACTS}
M=${MINING_DIR:-$B/mining}
TJ=${2:-$M/tasks-o.json}
BR=${BENCH_ROOT:?set BENCH_ROOT}
export PATH=/usr/bin:/bin:/usr/sbin:/sbin${EXTRA_PATH:+:$EXTRA_PATH}
read -r ALIAS BASE_SHA FIX_SHA < <(/usr/bin/python3 -c "
import json,sys; t=[x for x in json.load(open('$TJ')) if x['id']=='$ID'][0]; print(t['repo_alias'], t['base_sha'], t['fix_sha'])")
case "$ALIAS" in
  lcm-x)  SRC=$M/_src/lcm-x;  LIVE=lcm-x;  LIVEP=${SEED_INDEX_LCMX:?set SEED_INDEX_LCMX} ;;
  worldos|WorldOS) SRC=$M/_src/worldos; LIVE=worldos; LIVEP=${SEED_INDEX_WORLDOS:?set SEED_INDEX_WORLDOS} ;;
  *) echo "unknown alias $ALIAS"; exit 1 ;;
esac
A=$( [ "$ALIAS" = lcm-x ] && echo lcmx || echo worldos )
ST=$BR/refresh-state-o-$A   # one state + home per repo, so the two chains run in parallel without registry races
BASE=$BR/tasks/o/$ID
[ -e "$BASE" ] && { echo "exists: $BASE"; exit 1; }
mkdir -p "$BR/tasks/o" "$ST/embedded" "$ST/logs" "$ST/pending"
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
# Deps: exactly the ignored dirs the validated mining checkout had.
MR=$M/$ID/repo
if [ "$ALIAS" = lcm-x ]; then
  cp -cR "$MR/.venv" "$BASE/.venv"; cp -cR "$MR/agent" "$BASE/agent"
else
  cp -cR "$MR/servers/engine/.venv" "$BASE/servers/engine/.venv"
  # Same file subset as the live worldos index (its sparse worktree excludes data/media), via .gitnexusignore.
  printf '%s\n' '*.jsonl' '*.db' '*.sqlite' '*.png' '*.jpg' '*.jpeg' '*.webp' '*.gif' '*.mp4' '*.wav' '*.mp3' > "$BASE/.gitnexusignore"
  echo ".gitnexusignore" >> "$BASE/.git/info/exclude"
fi
echo ".gitnexus" >> "$BASE/.git/info/exclude"
[ -z "$(git -C "$BASE" status --porcelain --untracked-files=normal)" ] || { echo "dirty base"; git -C "$BASE" status --porcelain | head; exit 1; }
cp -cR "$LIVEP/.gitnexus" "$BASE/.gitnexus"
/usr/bin/python3 - "$BASE" <<'PY'
import json, os, sys
d = sys.argv[1]
for fn in ("gitnexus.json", "meta.json"):
    p = os.path.join(d, ".gitnexus", fn)
    if os.path.exists(p):
        m = json.load(open(p)); m["repoPath"], m["storagePath"] = d, os.path.join(d, ".gitnexus"); json.dump(m, open(p, "w"))
PY
cp "${SEED_EMBED_STAMP_DIR:?set SEED_EMBED_STAMP_DIR}/$LIVE" "$ST/embedded/$ID"
( flock 9 2>/dev/null || true; printf '%s\t%s\t%s\t1\t1\n' "$ID" "$BASE" "$BASE/.gitnexus" >> "$ST/rows.tsv" ) 9>"$ST/.rows.lock"
GITNEXUS_REFRESH_LAUNCHER=$ISO/launcher-ro-o-$A.sh GITNEXUS_REFRESH_STATE=$ST \
  "$ISO/bench-refresh.sh" --force --wait "$ID" || true
grep "	$ID	" "$ST/refresh.log" | tail -1
