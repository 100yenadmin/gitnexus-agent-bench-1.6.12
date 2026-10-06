#!/usr/bin/env node
// Bench stand-in for upstream's project-local runner (.gitnexus/run.cjs): forwards to the pinned GitNexus CLI for this
// run. runner/bench.py copies this file into each run's .gitnexus/ and replaces __LAUNCH_RUN__ with the absolute path
// of isolation/launcher-run.sh (the original hardcoded that path).
const { spawnSync } = require('child_process');
const r = spawnSync(__LAUNCH_RUN__, process.argv.slice(2), { stdio: 'inherit' });
process.exit(r.status === null ? 1 : r.status);
