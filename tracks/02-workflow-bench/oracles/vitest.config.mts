// Harness-owned config: benchmark candidates must not be able to weaken test
// discovery, setup hooks, or pass-with-no-tests behavior through repo config.
export default {
  root: process.cwd(),
  test: {
    environment: 'node',
    globals: false,
    setupFiles: [],
    globalSetup: [],
    passWithNoTests: false,
    // Bench adaptation: a cold first `status` on a fresh checkout copy takes ~15 s (default 5 s timeout).
    testTimeout: 120000,
    include: ['../.wfbench-oracle-*/*.oracle.test.ts'],
    exclude: [],
  },
};
