#!/bin/bash
# Blind cross-model grading: one Codex Sol (high) read-only run per question, in parallel.
set -u
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../isolation" && pwd)/_config.sh"
A=${AB_ARTIFACTS:?set AB_ARTIFACTS}
cd "$A/judge" || exit 1
pids=()
for p in *.prompt.md; do
  q=${p%.prompt.md}
  cwd=$(/usr/bin/python3 -c "import json;print(json.load(open('$q.map.json'))['cwd'])")
  "${CODEX_BIN:-codex}" exec -m gpt-6.1-sol -c model_reasoning_effort=high --sandbox read-only --skip-git-repo-check --ephemeral \
    -C "$cwd" -o "$A/judge/$q.out.md" "$(cat "$p")" < /dev/null > "$A/judge/$q.log" 2>&1 &
  pids+=($!)
done
rc=0; for p in "${pids[@]}"; do wait "$p" || rc=1; done
ls -la "$A"/judge/*.out.md 2>/dev/null; echo "judges done rc=$rc"
