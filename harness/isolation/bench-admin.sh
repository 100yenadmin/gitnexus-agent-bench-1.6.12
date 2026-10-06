#!/bin/bash
# Bench-only registry admin: register/remove per-run index copies in a BENCH home (never your everyday home).
set -eu
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_config.sh"
GN_NODE=${NODE_BIN:?set NODE_BIN in harness/config.env}
GN_CLI=${GITNEXUS_PKG:?set GITNEXUS_PKG in harness/config.env}/dist/cli/index.js
GN_HOME=${BENCH_GN_HOME:-${BENCH_ROOT:?set BENCH_ROOT in harness/config.env}/home}
case "${1:-}" in
  index|remove|list|status) ;;
  *) echo "bench-admin: only index|remove|list|status" >&2; exit 2 ;;
esac
exec /usr/bin/env -i HOME="${HOME:?}" USER="${USER:-bench}" PATH=/usr/bin:/bin:/usr/sbin:/sbin \
  TMPDIR="${TMPDIR:-/tmp}" LANG="${LANG:-en_US.UTF-8}" GITNEXUS_HOME="$GN_HOME" GITNEXUS_NO_UPDATE_NOTIFIER=1 \
  "$GN_NODE" "$GN_CLI" "$@"
