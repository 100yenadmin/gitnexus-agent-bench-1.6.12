#!/usr/bin/env bash
# hermes-agent hermetic pytest wrapper (Track H): run from the repository root after hermes_setup.sh.
# Mirrors scripts/run_tests.sh's hermetic environment (env -i; TZ=UTC, LANG/LC_ALL=C.UTF-8, PYTHONHASHSEED=0,
# PYTHONUTF8=1; no credential or proxy variables) and points HOME at a temp dir so no commit can reach the
# operator's real ~/.hermes. HERMES_HOME is deliberately NOT set: tests/conftest.py isolates it per test, and
# its home-I/O guard treats a pre-set HERMES_HOME as a real root and fails any test that writes there.
# TMPDIR is resolved through /private (macOS symlink).
#   hermes_pytest.sh <pytest args>             one pytest process over the given files/ids
#   hermes_pytest.sh --suite <paths> [flags]   the repo's per-file isolated runner (scripts/run_tests_parallel.py),
#                                              as scripts/run_tests.sh runs it in CI
set -uo pipefail
ulimit -n 4096 2>/dev/null || true
R=$(pwd -P)
PY=$R/.venv/bin/python
[ -x "$PY" ] || { echo "hermes_pytest.sh: no $PY (run from the repo root of a prepared checkout)" >&2; exit 2; }
H=$(mktemp -d)
trap 'rm -rf "$H"' EXIT
mkdir -p "$H/home"
T=$(cd "${TMPDIR:-/tmp}" && pwd -P)
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../../isolation" && pwd)/_config.sh"   # HERMES_PYTEST_EXTRA_PATH
# PATH: the venv, then a shim dir holding only `uv` (the pm worker-contract tests require a real uv; the rest of
# our user-level bin dir, e.g. the agent CLIs and a gitnexus wrapper, stays out of reach), then HERMES_PYTEST_EXTRA_PATH and the system.
ENVV=(PATH="$R/.venv/bin:$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/bin:${HERMES_PYTEST_EXTRA_PATH:+$HERMES_PYTEST_EXTRA_PATH:}/usr/bin:/bin:/usr/sbin:/sbin" HOME="$H/home"
      USER="${USER:-bench}" LOGNAME="${USER:-bench}" TMPDIR="$T" TZ=UTC LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONHASHSEED=0 PYTHONUTF8=1
      PYTHONPATH="$R" HERMES_PYTHON="$PY")
for v in HERMES_TEST_WORKERS HERMES_TEST_FILE_TIMEOUT HERMES_TEST_FILE_RETRIES; do
  [ -n "${!v:-}" ] && ENVV+=("$v=${!v}")
done
if [ "${1:-}" = "--suite" ]; then
  shift
  env -i "${ENVV[@]}" "$PY" scripts/run_tests_parallel.py "$@"
else
  env -i "${ENVV[@]}" "$PY" -m pytest -p no:cacheprovider "$@"
fi
