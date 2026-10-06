#!/bin/bash
# Logs every gitnexus-hook call (session, tool, input, injected context) so augmentation can be verified per run.
# Wraps upstream's Claude hook ($GITNEXUS_PKG/hooks/claude/gitnexus-hook.cjs) unchanged. Used by runner/bench.py
# (arms with hooks=True) and ab-ripgrep/run.py (augH2, augHk).
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_config.sh"
IN=$(cat)
OUT=$(printf '%s' "$IN" | "${NODE_BIN:?set NODE_BIN}" "${GITNEXUS_PKG:?set GITNEXUS_PKG}/hooks/claude/gitnexus-hook.cjs" 2>>"${HOOKLOG_DIR:-/dev/null}/hook-stderr.log")
rc=$?
META=$(printf '%s' "$IN" | /usr/bin/python3 -c 'import json,sys
d=json.load(sys.stdin); print(d.get("session_id"), d.get("hook_event_name"), d.get("tool_name"), json.dumps(d.get("tool_input"))[:160], sep="\t")' 2>/dev/null)
CTX=$(printf '%s' "$OUT" | /usr/bin/python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("hookSpecificOutput",{}).get("additionalContext","")[:400].replace("\n"," | "))
except Exception: print("")' 2>/dev/null)
[ -n "${HOOKLOG_DIR:-}" ] && printf '%s\t%s\t%s\n' "$(date +%s)" "$META" "$CTX" >> "$HOOKLOG_DIR/hook-calls.log"
printf '%s' "$OUT"
exit $rc
