#!/bin/bash
# Track U base: parentless snapshot of GitNexus at c4ecf398 (upstream v1.6.12) without eval/workflow_bench
# (hidden oracles), deps installed, live gitnexus index copied (APFS clone) and re-indexed in the BENCH home
# by the refresh script (pin=1, incremental embeddings, no re-embed).
# Published version: "live index" = SEED_INDEX_GITNEXUS, the storage dir (.gitnexus) of an index of GitNexus you built
# with `gitnexus analyze` (ours was our everyday index of the repo), plus its embedding stamp in SEED_EMBED_STAMP_DIR;
# the refresh is harness/isolation/bench-refresh.sh (a copy of the refresh script the original called).
set -euo pipefail
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../isolation" && pwd)/_config.sh"
ISO=$_HARNESS/isolation
BR=${BENCH_ROOT:?set BENCH_ROOT}
SRC=${GITNEXUS_SRC:?set GITNEXUS_SRC (a full clone of abhigyanpatwari/GitNexus)}
LIVE_SP=${SEED_INDEX_GITNEXUS:?set SEED_INDEX_GITNEXUS}
LIVE_STAMP=${SEED_EMBED_STAMP_DIR:?set SEED_EMBED_STAMP_DIR}/gitnexus
BASE=$BR/tasks/gnxu/gnxu-base
export PATH=${NODE_BIN_DIR:-$(dirname "${NODE_BIN:?set NODE_BIN}")}:/usr/bin:/bin:/usr/sbin:/sbin${EXTRA_PATH:+:$EXTRA_PATH}
[ -e "$BASE" ] && { echo "exists: $BASE"; exit 1; }
mkdir -p "$BASE"
git -C "$SRC" archive c4ecf398de637cf779ab2238e69958cfd5d601ce | tar -x -C "$BASE"
rm -rf "$BASE/eval/workflow_bench"
cd "$BASE"
git init -q -b main
git -c user.name=bench -c user.email=bench@localhost add -A
git -c user.name=bench -c user.email=bench@localhost commit -q -m "GitNexus v1.6.12 (c4ecf398) bench snapshot"
echo "snapshot: $(git rev-parse HEAD)"
grep -qE '^\.gitnexus' .gitignore 2>/dev/null || echo ".gitnexus" >> .git/info/exclude
echo "deps: root"; (npm ci --no-audit --no-fund --loglevel=error) > "$BASE/../npm-root.log" 2>&1
echo "deps: gitnexus-shared"; (cd gitnexus-shared && npm ci --no-audit --no-fund --loglevel=error && npm run build) > "$BASE/../npm-shared.log" 2>&1
echo "deps: gitnexus"; (cd gitnexus && npm ci --no-audit --no-fund --loglevel=error) > "$BASE/../npm-gitnexus.log" 2>&1
git status --porcelain --untracked-files=normal | head -5
echo "index copy"; cp -cR "$LIVE_SP" "$BASE/.gitnexus"
cp "$LIVE_STAMP" "$BR/refresh-state/embedded/gnxu-base"
printf 'gnxu-base\t%s\t%s\t1\t1\n' "$BASE" "$BASE/.gitnexus" >> "$BR/refresh-state/rows.tsv"
echo "refresh"; GITNEXUS_REFRESH_LAUNCHER=$ISO/launcher-ro.sh GITNEXUS_REFRESH_STATE=$BR/refresh-state \
  "$ISO/bench-refresh.sh" gnxu-base || true
tail -3 "$BR/refresh-state/refresh.log"
