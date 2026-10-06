#!/bin/bash
# Final regression control with the recorded env-induced deselects (meta deselect = fails at fix AND at base).
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../../isolation" && pwd)/_config.sh"
M=${HERMES_MINING_DIR:-${HERMES_ARTIFACTS:?set HERMES_ARTIFACTS}/mining}
SD=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
for id in "$@"; do
  mf=$SD/meta.json; grep -q "\"$id\"" $mf || mf=$SD/meta_alternates.json
  args=$(python3 -c "import json,shlex;m=json.load(open('$mf'))['$id'];print(' '.join(shlex.quote('--deselect='+d) for d in m.get('deselect',[])))")
  [ -f $M/$id/logs/fix_regression.log ] && mv $M/$id/logs/fix_regression.log $M/$id/logs/fix_regression-nodeselect.log
  echo "== $id"; bash $SD/run_reg.sh "$id" "" $args
done
