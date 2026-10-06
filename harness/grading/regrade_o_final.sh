#!/usr/bin/env bash
# Final Track O grading after both batches finish: three disjoint --only-missing graders.
# lcm-x graders run the suite with -n 8, so they get one job each; WorldOS runs serial pytest, so it gets 4.
# Run only once batch-o-a, batch-o-b and the pass-1 regrade chain have exited (no other grader on these dirs).
# Published version: cwd = $BENCH_ARTIFACTS (the run dirs and logs/ live there); the graders live in this harness.
set -u
B=${BENCH_ARTIFACTS:?set BENCH_ARTIFACTS (see harness/config.example.env)}
G=$(cd "$(dirname "$0")" && pwd)
cd "$B" || exit 1
for f in batch-o-a batch-o-b regrade-o regrade-o-early-lcmx regrade-o-early-wos; do
  if [ -f "logs/$f.pid" ] && ps -p "$(cat "logs/$f.pid")" >/dev/null 2>&1; then echo "still running: $f" >&2; exit 2; fi
done
T=tasks-o-bench.json
nohup python3 "$G/regrade.py" $T runs-o --jobs 1 --only-missing --only lcmx-t02,lcmx-t03,lcmx-t04,lcmx-i01,lcmx-i03 \
  > logs/regrade-o-final-lcmx.log 2>&1 & echo $! > logs/regrade-o-final-lcmx.pid
nohup python3 "$G/regrade.py" $T runs-o2 --jobs 1 --only-missing > logs/regrade-o-final-o2.log 2>&1 & echo $! > logs/regrade-o-final-o2.pid
nohup python3 "$G/regrade.py" $T runs-o --jobs 4 --only-missing --only worldos-t01,worldos-i01,worldos-i02,worldos-c01,worldos-c02 \
  > logs/regrade-o-final-wos.log 2>&1 & echo $! > logs/regrade-o-final-wos.pid
echo "launched: $(cat logs/regrade-o-final-lcmx.pid) $(cat logs/regrade-o-final-o2.pid) $(cat logs/regrade-o-final-wos.pid)"
