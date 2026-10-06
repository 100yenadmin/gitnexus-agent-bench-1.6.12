#!/bin/bash
# Engine-only check for P4: same seeded flows, but with NAMED Express handlers (plus one intra-procedural control and a
# closure-returned handler). Copy of the P4 base, module swapped, snapshot commit amended (--no-verify: no reformat),
# re-analyzed with --pdg in its own home/state. Then `explain` is called directly (no agents).
set -euo pipefail
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../isolation" && pwd)/_config.sh"
ISO=$_HARNESS/isolation
B=${BENCH_ARTIFACTS:?set BENCH_ARTIFACTS}
BR=${BENCH_ROOT:?set BENCH_ROOT}
SRC=$BR/tasks/p4/gnxu-taint
BASE=$BR/tasks/p4/gnxu-taint-named
ST=$BR/refresh-state-p4n; H=$BR/home-p4n
export PATH=${NODE_BIN_DIR:-$(dirname "${NODE_BIN:?set NODE_BIN}")}:/usr/bin:/bin:/usr/sbin:/sbin${EXTRA_PATH:+:$EXTRA_PATH}
[ -e "$BASE" ] && { echo "exists: $BASE"; exit 1; }
mkdir -p "$ST/embedded" "$ST/logs" "$ST/pending" "$H"
cp -cR "$SRC" "$BASE"
cp "$B/probes/p4/repo-tools-named.ts" "$BASE/gitnexus/src/server/repo-tools.ts"
(cd "$BASE/gitnexus" && ./node_modules/.bin/tsc --noEmit -p .) || { echo "tsc failed"; exit 1; }
git -C "$BASE" add -A gitnexus/src/server
git -C "$BASE" -c user.name=bench -c user.email=bench@localhost commit -q --amend --no-edit --no-verify
[ "$(git -C "$BASE" rev-list --count HEAD)" = 1 ] || { echo "not parentless"; exit 1; }
[ -z "$(git -C "$BASE" status --porcelain --untracked-files=normal)" ] || { echo dirty; git -C "$BASE" status --porcelain | head; exit 1; }
cmp -s "$B/probes/p4/repo-tools-named.ts" "$BASE/gitnexus/src/server/repo-tools.ts" || { echo "module changed by commit hooks"; exit 1; }
/usr/bin/python3 - "$BASE" <<'PY'
import json, os, sys
d = sys.argv[1]
for fn in ("gitnexus.json", "meta.json"):
    p = os.path.join(d, ".gitnexus", fn)
    if os.path.exists(p):
        m = json.load(open(p)); m["repoPath"], m["storagePath"] = d, os.path.join(d, ".gitnexus"); json.dump(m, open(p, "w"))
PY
[ -f "$H/registry.json" ] || echo '[]' > "$H/registry.json"
BENCH_GN_HOME=$H "$ISO/bench-admin.sh" index "$BASE" > "$ST/logs/register.log" 2>&1
cp "$BR/refresh-state-p4/embedded/gnxu-taint" "$ST/embedded/gnxu-taint-named"
printf '%s\t%s\t%s\t1\t1\n' gnxu-taint-named "$BASE" "$BASE/.gitnexus" > "$ST/rows.tsv"
sed "s#^GN_HOME=.*#GN_HOME=$H#" "$ISO/launcher-ro.sh" > "$ISO/launcher-ro-p4n.sh"; chmod +x "$ISO/launcher-ro-p4n.sh"
GITNEXUS_REFRESH_LAUNCHER=$ISO/launcher-ro-p4n.sh GITNEXUS_REFRESH_STATE=$ST GITNEXUS_BENCH_ANALYZE_EXTRA=--pdg \
  "$ISO/bench-refresh.sh" --force --wait || true
tail -2 "$ST/refresh.log"
