#!/bin/bash
# P4 taint probe base: APFS copy of gnxu-pdg + seeded module (3 tainted flows, 2 decoys) folded into the parentless
# snapshot commit (no tell-tale extra commit), type-checked, then re-analyzed with --pdg by the bench refresh in its
# own home/state (home-p4, refresh-state-p4) with the row pre-registered.
# Published version: the seeded module is $BENCH_ARTIFACTS/probes/p4/repo-tools.ts; the generated
# launcher-ro-p4.sh is written next to launcher-ro.sh in harness/isolation/.
set -euo pipefail
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../isolation" && pwd)/_config.sh"
ISO=$_HARNESS/isolation
B=${BENCH_ARTIFACTS:?set BENCH_ARTIFACTS}
BR=${BENCH_ROOT:?set BENCH_ROOT}
BASE=$BR/tasks/p4/gnxu-taint
ST=$BR/refresh-state-p4; H=$BR/home-p4
export PATH=${NODE_BIN_DIR:-$(dirname "${NODE_BIN:?set NODE_BIN}")}:/usr/bin:/bin:/usr/sbin:/sbin${EXTRA_PATH:+:$EXTRA_PATH}
[ -e "$BASE" ] && { echo "exists: $BASE"; exit 1; }
mkdir -p "$BR/tasks/p4" "$ST/embedded" "$ST/logs" "$ST/pending" "$H"
cp -cR "$BR/tasks/gnxu/gnxu-pdg" "$BASE"
cp "$B/probes/p4/repo-tools.ts" "$BASE/gitnexus/src/server/repo-tools.ts"
/usr/bin/python3 - "$BASE/gitnexus/src/server/api.ts" <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
a = "import { installServeMcpAuth, mountMCPEndpoints } from './mcp-http.js';\n"
assert s.count(a) == 1; s = s.replace(a, a + "import { mountRepoTools } from './repo-tools.js';\n")
b = "  const cleanupMcp = await mountMCPEndpoints(app, backend);\n"
assert s.count(b) == 1; s = s.replace(b, b + "  mountRepoTools(app, async () => []);\n")
open(p, "w").write(s)
PY
(cd "$BASE/gitnexus" && ./node_modules/.bin/tsc --noEmit -p .) || { echo "tsc failed"; exit 1; }
git -C "$BASE" add -A gitnexus/src/server
git -C "$BASE" -c user.name=bench -c user.email=bench@localhost commit -q --amend --no-edit
[ "$(git -C "$BASE" rev-list --count HEAD)" = 1 ] || { echo "not parentless"; exit 1; }
[ -z "$(git -C "$BASE" status --porcelain --untracked-files=normal)" ] || { echo dirty; git -C "$BASE" status --porcelain | head; exit 1; }
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
cp "$BR/refresh-state/embedded/gnxu-pdg" "$ST/embedded/gnxu-taint"
printf '%s\t%s\t%s\t1\t1\n' gnxu-taint "$BASE" "$BASE/.gitnexus" > "$ST/rows.tsv"
sed "s#^GN_HOME=.*#GN_HOME=$H#" "$ISO/launcher-ro.sh" > "$ISO/launcher-ro-p4.sh"; chmod +x "$ISO/launcher-ro-p4.sh"
GITNEXUS_REFRESH_LAUNCHER=$ISO/launcher-ro-p4.sh GITNEXUS_REFRESH_STATE=$ST GITNEXUS_BENCH_ANALYZE_EXTRA=--pdg \
  "$ISO/bench-refresh.sh" --force --wait || true
tail -2 "$ST/refresh.log"
