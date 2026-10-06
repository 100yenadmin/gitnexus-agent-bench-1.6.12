#!/usr/bin/env bash
# lcm-x hermetic pytest wrapper: run from the repo root after lcmx_setup.sh.
# Isolates HERMES_HOME (old commits otherwise read the operator's real ~/.hermes LCM db)
# and resolves TMPDIR through /private (macOS symlink breaks path-containment tests).
set -uo pipefail
ulimit -n 4096
H=$(mktemp -d)
trap 'rm -rf "$H"' EXIT
export HERMES_HOME="$H" HOME="$H"
export TMPDIR="$(cd "${TMPDIR:-/tmp}" && pwd -P)"
.venv/bin/python -m pytest -p no:cacheprovider "$@"
