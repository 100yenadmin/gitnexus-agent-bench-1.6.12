#!/bin/bash
# bench-refresh.sh — (re-)analyze the bench's GitNexus indexes. A copy of the index refresh script we use day to day,
# pointed at a bench launcher and state dir by the setup/ scripts (GITNEXUS_REFRESH_LAUNCHER, GITNEXUS_REFRESH_STATE).
# Usage: bench-refresh.sh [--force] [--wait] [--allow-reembed] [alias|owner/repo ...]   (no alias = every row)
#   --wait: if a refresh is already running, wait for it (up to 1 h) instead of exiting 75.
#   --allow-reembed: accept a changed embedding identity (model/dims/text version) and re-embed (paid).
#   owner/repo maps to its alias; a repo that is not indexed is a no-op.
#        bench-refresh.sh --seed-rows               (one-time: write rows.tsv from the registry)
# Embeddings: rows with embed=1 (or an index that already has vectors) are embedded with the launcher's
# GN_EMBED_* pins; unchanged code reuses its vectors by content hash, so a refresh only pays for changed
# nodes. Graph-only rows make no provider calls.
# Published version: the launcher pins are evaluated (they read harness/config.env), the embedding key is
# VOYAGE_API_KEY from harness/config.env (the original read the macOS keychain), and `timeout` is found on PATH.
# Exit: 0 ok, 1 some row failed, 2 usage, 3 registry damage (run aborted), 75 already running.
# (no set -u: bash 3.2 treats an empty "$@" as unbound)
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_config.sh"

LAUNCHER=${GITNEXUS_REFRESH_LAUNCHER:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/launcher-ro.sh}
STATE=${GITNEXUS_REFRESH_STATE:-${BENCH_ROOT:?set BENCH_ROOT}/refresh-state}
ROWS=$STATE/rows.tsv          # name<TAB>path<TAB>storagePath<TAB>pin(0|1)[<TAB>embed(0|1)]; pin = never advance source
LOG=$STATE/refresh.log
TIMEOUT=${GITNEXUS_REFRESH_TIMEOUT:-$(command -v gtimeout || command -v timeout)}
ANALYZE_SECS=${GITNEXUS_REFRESH_ANALYZE_SECS:-3600}
# Runs that embed get longer: a killed run discards its staged build, including vectors already paid for.
EMBED_SECS=${GITNEXUS_REFRESH_EMBED_SECS:-21600}
pin() { # evaluate the launcher's `NAME=...` pin line (it may reference config variables)
  ( . "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_config.sh"
    eval "$(grep "^$1=" "$LAUNCHER" | head -n 1)" 2>/dev/null; eval "printf %s \"\${$1:-}\"" )
}
GN_NODE=$(pin GN_NODE)
GN_CLI=$(pin GN_CLI)
GN_HOME=$(pin GN_HOME)
REGISTRY=$GN_HOME/registry.json
GN_EMBED_MODEL=$(pin GN_EMBED_MODEL)
GN_EMBED_DIMS=$(pin GN_EMBED_DIMS)
# Vectors are only reusable while model, width and upstream's embedding-text version all stay the same.
TEXTVER=$(sed -n "s/^export const EMBEDDING_TEXT_VERSION = '\(.*\)';/\1/p" \
  "${GN_CLI%/cli/index.js}/core/embeddings/embedding-pipeline.js" 2>/dev/null)
EMBED_ID="$GN_EMBED_MODEL/$GN_EMBED_DIMS/${TEXTVER:-unknown}"

export PATH=/usr/bin:/bin:/usr/sbin:/sbin${EXTRA_PATH:+:$EXTRA_PATH}
export GIT_TERMINAL_PROMPT=0 GIT_LFS_SKIP_SMUDGE=1
mkdir -p "$STATE/logs"
[ -n "$GN_NODE" ] && [ -n "$GN_CLI" ] && [ -d "$GN_HOME" ] && [ -x "$TIMEOUT" ] \
  || { echo "gitnexus-refresh: launcher pins or $TIMEOUT missing" >&2; exit 2; }

if [ "${1:-}" = "--seed-rows" ]; then
  [ -e "$ROWS" ] && { echo "$ROWS exists; edit it instead" >&2; exit 2; }
  jq -r '.[] | [.name, .path, .storagePath, (if .name == "gitnexus" then 1 else 0 end)] | @tsv' \
    "$REGISTRY" > "$ROWS.tmp" && [ -s "$ROWS.tmp" ] && mv "$ROWS.tmp" "$ROWS" && wc -l < "$ROWS" && exit 0
  rm -f "$ROWS.tmp"; exit 2
fi

FORCE=0; WAIT=0; REEMBED=0
while :; do
  case "${1:-}" in --force) FORCE=1; shift ;; --wait) WAIT=1; shift ;; --allow-reembed) REEMBED=1; shift ;; *) break ;; esac
done
[ -f "$ROWS" ] || { echo "no $ROWS; run --seed-rows first" >&2; exit 2; }
jq -e 'type == "array"' "$REGISTRY" >/dev/null 2>&1 || { echo "gitnexus-refresh: cannot read $REGISTRY" >&2; exit 2; }
aliases=""
# Remote URL normal form: lowercase, no trailing slash or .git, scp-style "host:owner" -> "host/owner".
norm='ascii_downcase | sub("/+$"; "") | sub("\\.git$"; "") | gsub(":"; "/")'
for a in "$@"; do
  case "$a" in
    */*) # owner/repo -> every managed alias whose registry remote ends in /owner/repo; none = nothing to do
      ms=$(jq -r --arg r "$a" ".[] | select((.remoteUrl // \"\" | $norm) | endswith(\"/\" + (\$r | $norm))) | .name" \
        "$REGISTRY" | while read -r n; do cut -f1 "$ROWS" | grep -xF -- "$n" || true; done)
      [ -n "$ms" ] || { echo "gitnexus-refresh: $a is not indexed; nothing to do"; continue; }
      aliases="$aliases $ms"; continue ;;   # newline-separated; split by set -- below
  esac
  cut -f1 "$ROWS" | grep -qixF -- "$a" || { echo "unknown alias: $a" >&2; exit 2; }
  aliases="$aliases $a"
done
[ "$#" -gt 0 ] && [ -z "$aliases" ] && exit 0
set -- $aliases

exec 9>>"$STATE/lock"
if [ "$WAIT" = 1 ]; then LOCKWAIT=3600; else LOCKWAIT=0; fi
/usr/bin/lockf -s -t "$LOCKWAIT" 9 || { echo "gitnexus-refresh: already running" >&2; exit 75; }

ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }
mkdir -p "$STATE/pending" "$STATE/embedded"
KEY=${GITNEXUS_REFRESH_EMBED_KEY:-${VOYAGE_API_KEY:-}}   # GITNEXUS_REFRESH_EMBED_KEY override is for the fixture test
ok=0; skip=0; fail=0; failed=""

record() { # status name stage old new secs
  printf '%s\t%s\t%s\t%s\t%s→%s\t%ss\n' "$(ts)" "$2" "$1" "$3" "${4:0:8}" "${5:0:8}" "$6" >> "$LOG"
  case "$1" in OK) ok=$((ok+1));; SKIP) skip=$((skip+1));; *) fail=$((fail+1)); failed="$failed $2:$3";; esac
}

# Index metadata: gitnexus.json is authoritative; meta.json is upstream's best-effort mirror.
idx_field() { # storagePath field
  local f="$1/gitnexus.json"; [ -f "$f" ] || f="$1/meta.json"
  jq -r ".$2 // \"\"" "$f" 2>/dev/null
}

bound() { # name path storagePath — this row's registry entry exists unchanged
  jq -e --arg n "$1" --arg p "$2" --arg s "$3" \
    'any(.[]; .name == $n and .path == $p and .storagePath == $s)' "$REGISTRY" >/dev/null 2>&1
}

managed_rows_lost() { # managed rows (storage present) whose registry entry vanished
  jq -r '.[] | [.name, .path, .storagePath] | @tsv' "$REGISTRY" 2>/dev/null | sort > "$STATE/.reg.now"
  while IFS="$(printf '\t')" read -r n p s _; do
    [ -d "$s" ] && ! grep -qxF "$(printf '%s\t%s\t%s' "$n" "$p" "$s")" "$STATE/.reg.now" && echo "$n"
  done < "$ROWS"
}

refresh_row() { # name path storagePath pin embed
  local name=$1 p=$2 sp=$3 pin=$4 embed=${5:-0} start=$SECONDS branch target indexed head lost rc have stamp emb_ok eargs=""
  case "$name" in ''|.|..|*[!A-Za-z0-9._-]*) record FAIL "$name" bad-alias "" "" 0; return ;; esac
  [ -d "$p" ] && [ -d "$sp" ] || { record FAIL "$name" missing-path "" "" 0; return; }
  indexed=$(idx_field "$sp" lastCommit)
  head=$(git -C "$p" rev-parse HEAD 2>/dev/null)
  if [ "$pin" = 1 ]; then
    target=$head
  else
    branch=$("$TIMEOUT" 60 git -C "$p" ls-remote --symref origin HEAD </dev/null 2>/dev/null \
      | awk '/^ref:/ { sub("refs/heads/", "", $2); print $2; exit }')
    [ -n "$branch" ] || { record FAIL "$name" ls-remote "$indexed" "" $((SECONDS-start)); return; }
    "$TIMEOUT" -k 30 900 git -C "$p" fetch -q --no-tags origin \
      "+refs/heads/$branch:refs/remotes/origin/$branch" </dev/null >/dev/null 2>&1 \
      || { record FAIL "$name" fetch "$indexed" "" $((SECONDS-start)); return; }
    target=$(git -C "$p" rev-parse "refs/remotes/origin/$branch^{commit}")
  fi
  # The stamp records the identity of the vectors the index actually holds; a row with a stamp stays
  # embedded even if a failed run left it with zero vectors. A current index is only skipped when its
  # vectors already match the pins (a pin change must surface as embed-identity, not as SKIP).
  have=$(idx_field "$sp" stats.embeddings); case "$have" in ''|*[!0-9]*) have=0 ;; esac
  stamp=$(cat "$STATE/embedded/$name" 2>/dev/null)
  emb_ok=1
  if [ "$embed" = 1 ] || [ "$have" -gt 0 ] || [ -n "$stamp" ]; then
    [ "$stamp" = "$EMBED_ID" ] && [ "$have" -gt 0 ] && [ "$(idx_field "$sp" embeddingDims)" = "$GN_EMBED_DIMS" ] || emb_ok=0
  fi
  # pending/<name> survives any failure after analyze starts, so a failed verify is retried next run.
  if [ "$FORCE" = 0 ] && [ "$target" = "$indexed" ] && [ "$target" = "$head" ] \
     && [ ! -e "$STATE/pending/$name" ] && [ -z "$(idx_field "$sp" incrementalInProgress)" ] \
     && [ "$emb_ok" = 1 ] && bound "$name" "$p" "$sp"; then
    # A current embedded index still needs the key: without it, semantic queries cannot embed.
    { [ "$embed" != 1 ] && [ "$have" = 0 ] && [ -z "$stamp" ]; } || [ -n "$KEY" ] \
      || { record FAIL "$name" no-embedding-key "$indexed" "$target" $((SECONDS-start)); return; }
    record SKIP "$name" current "$indexed" "$target" $((SECONDS-start)); return
  fi
  # Never index uncommitted content (also on --force / pending retries at the same commit).
  [ -z "$(git -C "$p" status --porcelain --untracked-files=normal -- . ':(exclude).gitnexus' 2>&1)" ] \
    || { record FAIL "$name" dirty-checkout "$indexed" "$target" $((SECONDS-start)); return; }
  # Embedding guards (before any change): never let a run discard paid vectors or mix vector spaces.
  if [ "$embed" = 1 ] || [ "$have" -gt 0 ] || [ -n "$stamp" ]; then
    [ -n "$TEXTVER" ] || { record FAIL "$name" embed-textver-unknown "$indexed" "$target" $((SECONDS-start)); return; }
    # Any stamp mismatch (even at zero vectors: upstream's cache is keyed by text, not model) or vectors
    # without a matching stamp/width needs a deliberate --allow-reembed.
    if { [ -n "$stamp" ] && [ "$stamp" != "$EMBED_ID" ]; } || { [ "$have" -gt 0 ] && { [ "$stamp" != "$EMBED_ID" ] \
         || [ "$(idx_field "$sp" embeddingDims)" != "$GN_EMBED_DIMS" ]; }; }; then
      [ "$REEMBED" = 1 ] || { record FAIL "$name" "embed-identity:${stamp:-unstamped}" "$indexed" "$target" $((SECONDS-start)); return; }
      eargs="--drop-embeddings"
    fi
    [ -n "$KEY" ] || { record FAIL "$name" no-embedding-key "$indexed" "$target" $((SECONDS-start)); return; }
    eargs="$eargs --embeddings 0"   # 0 = no node cap; unchanged nodes reuse their vectors
  fi
  if [ "$target" != "$head" ]; then
    git -C "$p" symbolic-ref -q HEAD >/dev/null 2>&1 && git -C "$p" checkout -q --detach </dev/null >/dev/null 2>&1
    # reset may download blobs (partial clones), so it gets a timeout like fetch.
    "$TIMEOUT" -k 30 1800 git -C "$p" -c core.hooksPath=/dev/null reset -q --keep "$target" </dev/null >/dev/null 2>&1 \
      || { record FAIL "$name" checkout "$indexed" "$target" $((SECONDS-start)); return; }
  fi
  # A repo-local .gitnexusrc can turn embeddings on (spend), drop them, or point the endpoint (with our
  # key) elsewhere; none of the managed repos ships one, so refuse rather than trust it.
  for d in "$p" "$(git -C "$p" rev-parse --show-toplevel 2>/dev/null)"; do
    [ -z "$d" ] || [ ! -e "$d/.gitnexusrc" ] \
      || { record FAIL "$name" gitnexusrc "$indexed" "$target" $((SECONDS-start)); return; }
  done
  : > "$STATE/pending/$name"
  # Staged build + atomic swap: live MCP readers reopen the new graph on their next freshness check (~5 s). The embedding env is
  # always set: without it upstream falls back to a local 384-d model and discards 1024-d vectors.
  # env -i runs first so the key is only in the environment, never in a long-lived process's argv.
  # LBUG_MAX_DB_SIZE: upstream's 16 GiB address-space cap aborted the first embed of one of our larger repos
  # (306k nodes) at a WAL checkpoint ~100k vectors in; analyze-only, a reservation not RAM.
  /usr/bin/env -i \
    HOME="$HOME" USER="${USER:-bench}" PATH=/usr/bin:/bin:/usr/sbin:/sbin TMPDIR="${TMPDIR:-/tmp}" \
    LANG="${LANG:-en_US.UTF-8}" GITNEXUS_HOME="$GN_HOME" GITNEXUS_STORAGE_PATH="$sp" \
    GITNEXUS_NO_UPDATE_NOTIFIER=1 GITNEXUS_PARSE_CHUNK_CONCURRENCY=1 \
    NODE_OPTIONS=--max-old-space-size=6144 \
    GITNEXUS_EMBEDDING_URL=https://api.voyageai.com/v1 GITNEXUS_EMBEDDING_MODEL="$GN_EMBED_MODEL" \
    GITNEXUS_EMBEDDING_DIMS="$GN_EMBED_DIMS" GITNEXUS_EMBEDDING_REQUEST_DIMS=omit \
    GITNEXUS_EMBEDDING_API_KEY="$KEY" GITNEXUS_LOG_LEVEL=info GITNEXUS_LBUG_MAX_DB_SIZE=137438953472 \
    "$TIMEOUT" -k 60 "$([ -n "$eargs" ] && echo "$EMBED_SECS" || echo "$ANALYZE_SECS")" \
    "$GN_NODE" "$GN_CLI" analyze "$p" --name "$name" --workers 2 --force --index-only $eargs ${GITNEXUS_BENCH_ANALYZE_EXTRA:-} \
    </dev/null >"$STATE/logs/$name.log" 2>&1
  rc=$?
  # rc 0 = the new build was swapped in, so its vectors now carry this run's identity (even if partial).
  [ "$rc" != 0 ] || [ -z "$eargs" ] || echo "$EMBED_ID" > "$STATE/embedded/$name"
  lost=$(managed_rows_lost)
  [ -z "$lost" ] || { record FAIL "$name" "registry-lost:$(echo $lost | tr ' ' ,)" "$indexed" "$target" $((SECONDS-start)); return 3; }
  [ "$rc" = 0 ] || { record FAIL "$name" analyze "$indexed" "$target" $((SECONDS-start)); return; }
  bound "$name" "$p" "$sp" || { record FAIL "$name" registry-binding "$indexed" "$target" $((SECONDS-start)); return; }
  [ "$(idx_field "$sp" lastCommit)" = "$target" ] \
    || { record FAIL "$name" verify-commit "$indexed" "$target" $((SECONDS-start)); return; }
  (cd / && "$LAUNCHER" query main --repo "$name" --limit 1 </dev/null >/dev/null 2>&1) \
    || { record FAIL "$name" verify-query "$indexed" "$target" $((SECONDS-start)); return; }
  if [ -n "$eargs" ]; then
    # Upstream exits 0 when provider calls fail and drops those rows; the pending marker retries them.
    ! grep -q 'dropped after embed failures' "$STATE/logs/$name.log" \
      || { record FAIL "$name" embed-partial "$indexed" "$target" $((SECONDS-start)); return; }
    have=$(idx_field "$sp" stats.embeddings)
    [ "${have:-0}" -gt 0 ] 2>/dev/null && [ "$(idx_field "$sp" embeddingDims)" = "$GN_EMBED_DIMS" ] \
      || { record FAIL "$name" embed-verify "$indexed" "$target" $((SECONDS-start)); return; }
  fi
  rm -f "$STATE/pending/$name"
  record OK "$name" "refreshed${eargs:+:emb=$have}" "$indexed" "$target" $((SECONDS-start))
}

cp -p "$REGISTRY" "$STATE/registry.before-run.json" 2>/dev/null   # restore point for a registry abort
echo "$(ts)	RUN-START	force=$FORCE	${*:-all}" >> "$LOG"
while IFS="$(printf '\t')" read -r name p sp pin embed <&3; do
  if [ "$#" -gt 0 ]; then
    match=0; for a in "$@"; do [ "$(printf %s "$a" | tr A-Z a-z)" = "$(printf %s "$name" | tr A-Z a-z)" ] && match=1; done
    [ "$match" = 1 ] || continue
  fi
  refresh_row "$name" "$p" "$sp" "$pin" "$embed"
  if [ "$?" = 3 ]; then
    echo "$(ts)	RUN-ABORT	registry lost rows after $name; restore point $STATE/registry.before-run.json" >> "$LOG"
    exit 3
  fi
done 3< "$ROWS"

if [ "$#" = 0 ]; then
  latest=$(curl -fsS --max-time 20 https://registry.npmjs.org/gitnexus/latest 2>/dev/null | jq -r '.version // ""')
  installed=$("$GN_NODE" "$GN_CLI" --version 2>/dev/null)
  [ -n "$latest" ] && [ "$latest" != "$installed" ] \
    && echo "$(ts)	UPGRADE-AVAILABLE	installed=$installed	latest=$latest" >> "$LOG"
fi
summary="$(ts)	RUN-END	ok=$ok	skip=$skip	fail=$fail${failed:+	failed=$failed}"
echo "$summary" >> "$LOG"; echo "$summary"
[ "$fail" = 0 ]
