# Haiku runs (H0 / H2) across tracks
The Haiku setups have no directory of their own. They are the `H0` (Haiku 4.5, no GitNexus) and `H2` (Haiku 4.5, full upstream GitNexus install: MCP, skills, hooks, AGENTS.md block) arms inside tracks 1, 3, 4 and 5. This file indexes all 66 of them. Run ids match the `run` field of that track's `runs.jsonl`, where the full summary row is.

## 01-fixes (24 runs)
- **H0**: 7/12 resolved with no regressions; mean cost $0.92
- **H2**: 5/12 resolved with no regressions; mean cost $0.87

| run | task | arm | outcome | cost USD | GitNexus calls |
|---|---|---|---|---|---|
| `runs-o2/lcmx-c01-H0-t1` | lcmx-c01 | H0 | hidden tests fail, regression FAIL | 0.58 | 0 |
| `runs-o2/lcmx-c01-H2-t1` | lcmx-c01 | H2 | hidden tests fail, regression FAIL | 0.67 | 0 |
| `runs-o2/lcmx-c03-H0-t1` | lcmx-c03 | H0 | hidden tests fail, regression FAIL | 1.05 | 0 |
| `runs-o2/lcmx-c03-H2-t1` | lcmx-c03 | H2 | hidden tests pass, regression clean | 0.99 | 0 |
| `runs-o/lcmx-i01-H0-t1` | lcmx-i01 | H0 | hidden tests fail, regression FAIL | 0.62 | 0 |
| `runs-o/lcmx-i01-H2-t1` | lcmx-i01 | H2 | hidden tests fail, regression FAIL | 0.71 | 0 |
| `runs-o/lcmx-i03-H0-t1` | lcmx-i03 | H0 | hidden tests pass, regression clean | 1.40 | 0 |
| `runs-o/lcmx-i03-H2-t1` | lcmx-i03 | H2 | hidden tests pass, regression clean | 0.67 | 2 |
| `runs-o/lcmx-t02-H0-t1` | lcmx-t02 | H0 | hidden tests pass, regression clean | 0.81 | 0 |
| `runs-o/lcmx-t02-H2-t1` | lcmx-t02 | H2 | hidden tests pass, regression clean | 0.70 | 0 |
| `runs-o/lcmx-t03-H0-t1` | lcmx-t03 | H0 | hidden tests pass, regression clean | 0.73 | 0 |
| `runs-o/lcmx-t03-H2-t1` | lcmx-t03 | H2 | hidden tests fail, regression FAIL | 0.88 | 0 |
| `runs-o/lcmx-t04-H0-t1` | lcmx-t04 | H0 | hidden tests pass, regression clean | 0.44 | 0 |
| `runs-o/lcmx-t04-H2-t1` | lcmx-t04 | H2 | hidden tests pass, regression clean | 0.67 | 0 |
| `runs-o/worldos-c01-H0-t1` | worldos-c01 | H0 | hidden tests fail, regression FAIL | 1.32 | 0 |
| `runs-o/worldos-c01-H2-t1` | worldos-c01 | H2 | hidden tests fail, regression FAIL | 1.17 | 3 |
| `runs-o/worldos-c02-H0-t1` | worldos-c02 | H0 | hidden tests fail, regression FAIL | 1.48 | 0 |
| `runs-o/worldos-c02-H2-t1` | worldos-c02 | H2 | hidden tests fail, regression FAIL | 1.58 | 2 |
| `runs-o/worldos-i01-H0-t1` | worldos-i01 | H0 | hidden tests pass, regression clean | 0.70 | 0 |
| `runs-o/worldos-i01-H2-t1` | worldos-i01 | H2 | hidden tests fail, regression FAIL | 0.71 | 0 |
| `runs-o/worldos-i02-H0-t1` | worldos-i02 | H0 | hidden tests pass, regression clean | 0.99 | 0 |
| `runs-o/worldos-i02-H2-t1` | worldos-i02 | H2 | hidden tests fail, regression FAIL | 0.92 | 2 |
| `runs-o/worldos-t01-H0-t1` | worldos-t01 | H0 | hidden tests pass, regression clean | 0.90 | 0 |
| `runs-o/worldos-t01-H2-t1` | worldos-t01 | H2 | hidden tests pass, regression clean | 0.73 | 4 |

## 03-impact-ts (20 runs)
- **H0**: mean recall 0.992, mean precision 0.917, 8/10 exact; mean cost $0.19
- **H2**: mean recall 0.870, mean precision 0.822, 6/10 exact; mean cost $0.19

| run | task | arm | outcome | cost USD | GitNexus calls |
|---|---|---|---|---|---|
| `runs-p1/p1-close-H0-t1` | p1-close | H0 | recall 1.00, precision 1.00 | 0.22 | 2 |
| `runs-p1/p1-close-H2-t1` | p1-close | H2 | recall 0.00, precision 0.00 | 0.18 | 0 |
| `runs-p1/p1-drainFinalizerPending-H0-t1` | p1-drainFinalizerPending | H0 | recall 1.00, precision 1.00 | 0.16 | 1 |
| `runs-p1/p1-drainFinalizerPending-H2-t1` | p1-drainFinalizerPending | H2 | recall 1.00, precision 1.00 | 0.14 | 1 |
| `runs-p1/p1-getPhaseOutput-H0-t1` | p1-getPhaseOutput | H0 | recall 1.00, precision 1.00 | 0.16 | 0 |
| `runs-p1/p1-getPhaseOutput-H2-t1` | p1-getPhaseOutput | H2 | recall 0.79, precision 1.00 | 0.17 | 3 |
| `runs-p1/p1-init-H0-t1` | p1-init | H0 | recall 0.92, precision 0.92 | 0.26 | 0 |
| `runs-p1/p1-init-H2-t1` | p1-init | H2 | recall 0.92, precision 1.00 | 0.16 | 2 |
| `runs-p1/p1-parseSourceSafe-H0-t1` | p1-parseSourceSafe | H0 | recall 1.00, precision 1.00 | 0.18 | 1 |
| `runs-p1/p1-parseSourceSafe-H2-t1` | p1-parseSourceSafe | H2 | recall 1.00, precision 1.00 | 0.14 | 2 |
| `runs-p1/p1-resolve-H0-t1` | p1-resolve | H0 | recall 1.00, precision 0.25 | 0.15 | 0 |
| `runs-p1/p1-resolve-H2-t1` | p1-resolve | H2 | recall 1.00, precision 1.00 | 0.22 | 2 |
| `runs-p1/p1-resolveCallerGraphId-H0-t1` | p1-resolveCallerGraphId | H0 | recall 1.00, precision 1.00 | 0.21 | 0 |
| `runs-p1/p1-resolveCallerGraphId-H2-t1` | p1-resolveCallerGraphId | H2 | recall 1.00, precision 1.00 | 0.14 | 2 |
| `runs-p1/p1-resolveConstant-H0-t1` | p1-resolveConstant | H0 | recall 1.00, precision 1.00 | 0.22 | 1 |
| `runs-p1/p1-resolveConstant-H2-t1` | p1-resolveConstant | H2 | recall 1.00, precision 1.00 | 0.33 | 1 |
| `runs-p1/p1-sortSinkKinds-H0-t1` | p1-sortSinkKinds | H0 | recall 1.00, precision 1.00 | 0.15 | 0 |
| `runs-p1/p1-sortSinkKinds-H2-t1` | p1-sortSinkKinds | H2 | recall 1.00, precision 1.00 | 0.15 | 1 |
| `runs-p1/p1-validateBranchName-H0-t1` | p1-validateBranchName | H0 | recall 1.00, precision 1.00 | 0.22 | 0 |
| `runs-p1/p1-validateBranchName-H2-t1` | p1-validateBranchName | H2 | recall 1.00, precision 0.22 | 0.24 | 3 |

## 04-rename (12 runs)
- **H0**: 6/6 resolved with no regressions; mean cost $0.59
- **H2**: 5/6 resolved with no regressions; mean cost $0.65

| run | task | arm | outcome | cost USD | GitNexus calls |
|---|---|---|---|---|---|
| `runs-p2/p2-close-H0-t1` | p2-close | H0 | hidden tests pass, regression clean | 0.45 | 1 |
| `runs-p2/p2-close-H2-t1` | p2-close | H2 | hidden tests pass, regression clean | 0.50 | 5 |
| `runs-p2/p2-declare-H0-t1` | p2-declare | H0 | hidden tests pass, regression clean | 0.82 | 1 |
| `runs-p2/p2-declare-H2-t1` | p2-declare | H2 | hidden tests pass, regression clean | 0.50 | 4 |
| `runs-p2/p2-drainFinalizerPending-H0-t1` | p2-drainFinalizerPending | H0 | hidden tests pass, regression clean | 0.77 | 0 |
| `runs-p2/p2-drainFinalizerPending-H2-t1` | p2-drainFinalizerPending | H2 | hidden tests pass, regression clean | 0.40 | 4 |
| `runs-p2/p2-facts-H0-t1` | p2-facts | H0 | hidden tests pass, regression clean | 0.42 | 1 |
| `runs-p2/p2-facts-H2-t1` | p2-facts | H2 | hidden tests pass, regression clean | 0.70 | 4 |
| `runs-p2/p2-getPhaseOutput-H0-t1` | p2-getPhaseOutput | H0 | hidden tests pass, regression clean | 0.43 | 0 |
| `runs-p2/p2-getPhaseOutput-H2-t1` | p2-getPhaseOutput | H2 | hidden tests pass, regression clean | 0.52 | 5 |
| `runs-p2/p2-resolve-H0-t1` | p2-resolve | H0 | hidden tests pass, regression clean | 0.67 | 0 |
| `runs-p2/p2-resolve-H2-t1` | p2-resolve | H2 | hidden tests fail, regression clean | 1.30 | 4 |

## 05-structural (10 runs)
- **H0**: mean recall 0.926, mean precision 0.933, 3/5 exact; mean cost $0.23
- **H2**: mean recall 0.896, mean precision 0.863, 3/5 exact; mean cost $0.14

| run | task | arm | outcome | cost USD | GitNexus calls |
|---|---|---|---|---|---|
| `runs-p3/p3-consumers-file-H0-t1` | p3-consumers-file | H0 | recall 0.67, precision 0.67 | 0.35 | 1 |
| `runs-p3/p3-consumers-file-H2-t1` | p3-consumers-file | H2 | recall 0.67, precision 0.50 | 0.15 | 6 |
| `runs-p3/p3-consumers-query-H0-t1` | p3-consumers-query | H0 | recall 1.00, precision 1.00 | 0.18 | 0 |
| `runs-p3/p3-consumers-query-H2-t1` | p3-consumers-query | H2 | recall 1.00, precision 1.00 | 0.20 | 9 |
| `runs-p3/p3-consumers-repos-H0-t1` | p3-consumers-repos | H0 | recall 1.00, precision 1.00 | 0.18 | 0 |
| `runs-p3/p3-consumers-repos-H2-t1` | p3-consumers-repos | H2 | recall 1.00, precision 1.00 | 0.15 | 6 |
| `runs-p3/p3-routes-H0-t1` | p3-routes | H0 | recall 0.96, precision 1.00 | 0.26 | 0 |
| `runs-p3/p3-routes-H2-t1` | p3-routes | H2 | recall 0.81, precision 0.81 | 0.12 | 1 |
| `runs-p3/p3-tools-H0-t1` | p3-tools | H0 | recall 1.00, precision 1.00 | 0.17 | 0 |
| `runs-p3/p3-tools-H2-t1` | p3-tools | H2 | recall 1.00, precision 1.00 | 0.09 | 0 |
