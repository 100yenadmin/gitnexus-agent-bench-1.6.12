#!/bin/bash
# APFS copy of the bench hermes-agent source (everything except its .gitnexus index), detached at a commit.
# usage: mkcheckout.sh <dest> <sha>
set -euo pipefail
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../../isolation" && pwd)/_config.sh"
S=${HERMES_SRC:-${BENCH_ROOT:?set BENCH_ROOT}/src/hermes-agent}   # a clone of NousResearch/hermes-agent
D=$1; SHA=$2
[ -e "$D" ] && { echo "exists: $D"; exit 1; }
mkdir -p "$D"
for f in "$S"/.[!.]* "$S"/*; do
  [ "$(basename "$f")" = .gitnexus ] && continue
  cp -cR "$f" "$D/"
done
git -C "$D" checkout -q --detach "$SHA"
git -C "$D" status --porcelain | head -3
