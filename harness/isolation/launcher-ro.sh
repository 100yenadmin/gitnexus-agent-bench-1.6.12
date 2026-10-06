#!/bin/bash
# Read-only GitNexus launcher for the shared bench home: MCP plus read CLI commands.
# bench-refresh.sh evaluates this file's GN_* pin lines; setup_p4_base.sh / setup_p4_named.sh make per-home copies of
# launcher-ro.sh by rewriting the GN_HOME line. Published version: node, the GitNexus package and the Voyage key come
# from harness/config.env (see _config.sh); the original launcher read the key from the macOS keychain.
set -eu
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_config.sh"

# Version pins (bench-refresh.sh evaluates these lines).
GN_NODE=${NODE_BIN:?set NODE_BIN in harness/config.env}
GN_CLI=${GITNEXUS_PKG:?set GITNEXUS_PKG in harness/config.env}/dist/cli/index.js
GN_HOME=${BENCH_ROOT:?set BENCH_ROOT in harness/config.env}/home
# Embedding pins: one vector space for every index (queries must embed with the same model and width).
GN_EMBED_MODEL=voyage-code-4
GN_EMBED_DIMS=1024

run() {
  # env -i: drop client-injected GITNEXUS_* overrides, GIT_DIR, storage overrides and provider keys; the registry in
  # GN_HOME is the whole membership list. The embedding env is always set so a query never falls back to the local
  # 384-d model; graph-only indexes make no provider calls.
  # VECTOR_MAX_DISTANCE: upstream's MCP default (0.6) filtered out most voyage-code-4 matches for plain-English
  # queries in an exploratory probe (2026-10-01): 1.0 found 29/32 targets vs 20/32 at 0.6, 17/32 keyword-only.
  exec /usr/bin/env -i \
    HOME="${HOME:?}" USER="${USER:-bench}" LOGNAME="${LOGNAME:-${USER:-bench}}" \
    PATH=/usr/bin:/bin:/usr/sbin:/sbin TMPDIR="${TMPDIR:-/tmp}" LANG="${LANG:-en_US.UTF-8}" \
    GITNEXUS_HOME="$GN_HOME" GITNEXUS_MCP_READ_ONLY=1 GITNEXUS_NO_UPDATE_NOTIFIER=1 \
    GITNEXUS_EMBEDDING_URL=https://api.voyageai.com/v1 GITNEXUS_EMBEDDING_MODEL="$GN_EMBED_MODEL" \
    GITNEXUS_EMBEDDING_DIMS="$GN_EMBED_DIMS" GITNEXUS_EMBEDDING_REQUEST_DIMS=omit \
    GITNEXUS_EMBEDDING_MAX_ATTEMPTS=1 GITNEXUS_EMBEDDING_API_KEY="${VOYAGE_API_KEY:-}" \
    GITNEXUS_VECTOR_MAX_DISTANCE=1.0 \
    "$GN_NODE" "$GN_CLI" "$@"
}

case "${1:-}" in
  ''|mcp|list|status|doctor|augment|query|context|impact|trace|detect-changes|check|help|-h|--help|-V|--version)
    run "$@" ;;
  *)
    echo "gitnexus: '${1}' is not available here; indexes are re-analyzed only through bench-refresh.sh." >&2
    exit 2 ;;
esac
