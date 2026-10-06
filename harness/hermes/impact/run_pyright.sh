#!/bin/bash
# Run pinned pyright over the in-scope production files of a checkout.
# Usage: run_pyright.sh <checkout> <out.json> [Darwin|Linux|Windows]   (platform default: Darwin = this host)
# No pyrightconfig/[tool.pyright] exists in hermes-agent at d62fbea7e110, so pyright defaults apply (basic mode);
# the checkout's own uv venv (.venv, uv sync --frozen) resolves third-party imports. --pythonplatform only changes how
# pyright narrows sys.platform / os.name checks (code under a non-matching platform guard is unreachable and unchecked).
# Published version: pyright 1.1.414 lives in $PYRIGHT_DIR (npm install pyright@1.1.414 there), scope-files.txt in
# $HERMES_ARTIFACTS/impact.
set -uo pipefail
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../../isolation" && pwd)/_config.sh"
ROOT=$1; OUT=$2; PLAT=${3:-Darwin}
A=${HERMES_ARTIFACTS:?set HERMES_ARTIFACTS}/impact
PYR=${PYRIGHT_DIR:-${BENCH_ROOT:?set BENCH_ROOT}/tools/pyright-1.1.414}/node_modules/.bin/pyright
export PATH=${NODE_BIN_DIR:-$(dirname "${NODE_BIN:?set NODE_BIN}")}:/usr/bin:/bin
cd "$ROOT"
xargs "$PYR" --outputjson --pythonplatform "$PLAT" --pythonpath "$ROOT/.venv/bin/python" < "$A/scope-files.txt" > "$OUT" 2> "$OUT.err"
echo "rc=$?"
