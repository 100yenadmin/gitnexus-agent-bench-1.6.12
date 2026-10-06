# Sourced by the harness shell scripts. Loads harness/config.env (or $BENCH_CONFIG): KEY=VALUE lines, values may use
# ${OTHER}. A variable already set in the environment wins. Values are shell variables only (not exported); each
# script passes what it needs explicitly (the launchers run GitNexus under `env -i`).
_HARNESS=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
_CONF=${BENCH_CONFIG:-$_HARNESS/config.env}
if [ -f "$_CONF" ]; then
  while IFS= read -r _line || [ -n "$_line" ]; do
    case "$_line" in ''|\#*) continue ;; esac
    _k=${_line%%=*}; _v=${_line#*=}
    case "$_k" in *[!A-Za-z0-9_]*|'') continue ;; esac
    [ -n "${!_k:-}" ] || eval "$_k=$_v"
  done < "$_CONF"
fi
unset _line _k _v
