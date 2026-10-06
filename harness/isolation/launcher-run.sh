#!/bin/bash
# Per-run bench launcher: the GitNexus home comes from BENCH_GN_HOME (one registry per run, so an agent can only
# see its own checkout); BENCH_GN_RO=1 gives the read-only MCP (our day-to-day setup), otherwise rename/cypher are
# available. Re-indexing (analyze/setup/clean/wiki/...) is refused: the bench keeps each index current for the task commit.
# Published version: node, the GitNexus package and the Voyage key come from harness/config.env (see _config.sh);
# the original read the key from the macOS keychain.
set -eu
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_config.sh"
GN_NODE=${NODE_BIN:?set NODE_BIN in harness/config.env}
GN_CLI=${GITNEXUS_PKG:?set GITNEXUS_PKG in harness/config.env}/dist/cli/index.js
GN_HOME=${BENCH_GN_HOME:?BENCH_GN_HOME not set}
RO=${BENCH_GN_RO:-}
GN_EMBED_MODEL=voyage-code-4
GN_EMBED_DIMS=1024
run() {
  exec /usr/bin/env -i \
    HOME="${HOME:?}" USER="${USER:-bench}" LOGNAME="${LOGNAME:-${USER:-bench}}" \
    PATH=/usr/bin:/bin:/usr/sbin:/sbin TMPDIR="${TMPDIR:-/tmp}" LANG="${LANG:-en_US.UTF-8}" \
    GITNEXUS_HOME="$GN_HOME" ${RO:+GITNEXUS_MCP_READ_ONLY=1} GITNEXUS_NO_UPDATE_NOTIFIER=1 \
    GITNEXUS_EMBEDDING_URL=https://api.voyageai.com/v1 GITNEXUS_EMBEDDING_MODEL="$GN_EMBED_MODEL" \
    GITNEXUS_EMBEDDING_DIMS="$GN_EMBED_DIMS" GITNEXUS_EMBEDDING_REQUEST_DIMS=omit \
    GITNEXUS_EMBEDDING_MAX_ATTEMPTS=1 GITNEXUS_EMBEDDING_API_KEY="${VOYAGE_API_KEY:-}" \
    GITNEXUS_VECTOR_MAX_DISTANCE=1.0 \
    "$GN_NODE" "$GN_CLI" "$@"
}
case "${1:-}" in
  ''|mcp|list|status|doctor|augment|query|context|impact|trace|detect-changes|detect_changes|check|cypher|help|-h|--help|-V|--version)
    run "$@" ;;
  *)
    echo "gitnexus: '${1}' is not available in this benchmark; the index is already current for this task's commit." >&2
    exit 2 ;;
esac
