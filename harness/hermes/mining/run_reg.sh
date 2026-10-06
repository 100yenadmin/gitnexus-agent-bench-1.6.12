#!/bin/bash
# Regression control for one Track H task: at fix_sha in the mining checkout, run the per-file regression
# over <id>/regression-files.txt (plus optional extra pytest flags), log to <id>/logs/fix_regression[-TAG].log,
# then return the checkout to base_sha. usage: run_reg.sh <id> [tag] [extra pytest flags...]
# AT=base runs the same list at base_sha (no oracle files) to find pre-existing / environment-induced failures.
set -uo pipefail
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../../isolation" && pwd)/_config.sh"
M=${HERMES_MINING_DIR:-${HERMES_ARTIFACTS:?set HERMES_ARTIFACTS}/mining}
SD=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ID=$1; TAG=${2:-}; shift; [ $# -gt 0 ] && shift
R=$M/$ID/repo
read -r BASE FIX < <(python3 -c "import json;r=json.load(open('$M/$ID/validate.json'));print(r['base'],r['fix'])")
if [ "${AT:-fix}" = base ]; then REV=$BASE; PFX=base; else REV=$FIX; PFX=fix; fi
cd "$R" && git checkout -q --detach "$REV" || exit 1
LOG=$M/$ID/logs/${PFX}_regression${TAG:+-$TAG}.log
CMD="bash $SD/hermes_pytest.sh --suite --files-from $M/$ID/regression-files.txt -q $*"
S=$SECONDS
{ echo "\$ $CMD"; eval "$CMD"; echo "# exit=$? secs=$((SECONDS-S))"; } > "$LOG" 2>&1
git checkout -q --detach "$BASE"
tail -1 "$LOG"
