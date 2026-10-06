#!/bin/bash
# Controls for rename oracle v2 in one scratch clone of the P2 base (tracked files reset between controls).
#   negative: unrenamed base fails; positive: TS's own rename passes for every target; an agent's full rename through
#   the re-export passes for getPhaseOutput; naive whole-word find-and-replace fails on the namesake targets.
set -u
B=$BENCH_ROOT
P=$B/probes/p2
export PATH=$NODE_BIN:/usr/bin:/bin:/usr/sbin:/sbin:$BREW_PREFIX/bin
T=$(mktemp -d "$TMPDIR/v2ctl.XXXX"); cp -cR $TASK_BASE/gnxu/gnxu-base "$T/repo"; cd "$T/repo/gitnexus"
chk() { node "$P/rename_gt_v2.mjs" check "$P/spec_v2.json" "$1" | /usr/bin/python3 -c "import json,sys; r=json.loads(sys.stdin.read()); print('$2', '$1', 'PASS' if r['pass'] else 'FAIL', {k:v for k,v in r['checks'].items() if not v})"; }
reset() { git -C "$T/repo" checkout -q -- . ; }
chk getPhaseOutput negative-base
for t in close resolve declare drainFinalizerPending getPhaseOutput facts; do
  node "$P/rename_gt_v2.mjs" apply "$P/spec_v2.json" "$t" >/dev/null; chk "$t" positive-ts-rename; reset
done
git -C "$T/repo" apply "$B/runs-p2/runs/p2-getPhaseOutput-A0-t1/patch.diff" && chk getPhaseOutput positive-agent-full-rename; reset
for t in close:closeWriter resolve:resolveBinding declare:declareBinding; do
  o=${t%%:*}; n=${t##*:}
  grep -rlw --include='*.ts' "$o" src test | xargs sed -i '' -E "s/[[:<:]]$o[[:>:]]/$n/g"  # BSD sed word boundaries
  echo "naive-replace $o: $(git -C "$T/repo" diff --numstat | wc -l | tr -d ' ') files changed"; chk "$o" negative-naive-replace; reset
done
cd /; rm -rf "$T"
