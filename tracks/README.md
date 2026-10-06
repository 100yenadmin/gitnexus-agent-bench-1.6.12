# Claims bench, tracks 1-8 (GitNexus 1.6.12)

This directory holds the per-run data for the claims bench in Discussion #3493 and issue #3500. There are 340 graded agent runs over 7 tracks, plus the hook usage counts (track 8). Transcripts, system prompts and command lines are not included. The run summaries, grades, patches, structured answers, answer keys and tool outputs are.

Run `python3 verify_tracks.py` to recompute the published numbers from these files alone. It prints one OK or MISMATCH line per check and exits 0 when every check matches.

## Layout

| Directory | Track | Runs | Contents |
|---|---|---|---|
| `01-fixes/` | 1. Bug fixes from merged PRs (lcm-x, WorldOS) | 108 scored, 8 superseded | `tasks.json` (repo, PR, base and fix SHA, bug-report statement), `oracle/<task>/` (hidden tests), `validate/<task>.json` (base fails, fix passes twice, regression green), `controls.jsonl` and `controls/` (BASE and FIX control grades and diffs), `runs.jsonl`, `grades.jsonl`, `patches/` |
| `02-workflow-bench/` | 2. Upstream `eval/workflow_bench` change tasks | 24 scored, 4 excluded | `tasks.json`, `oracles/` (repaired oracles plus `upstream-orig.diff`), `excluded.txt`, `runs.jsonl`, `grades.jsonl`, `patches/` |
| `03-impact-ts/` | 3. Impact questions, TypeScript compiler key | 80 scored, 10 excluded | `tasks.json`, `gt.json`, `gt.mjs`, `enumerate.mjs`, `answers/`, `runs.jsonl`, `grades.jsonl` |
| `04-rename/` | 4. Renames | 42 scored | `tasks.json`, `spec_v2.json`, `rename_gt_v2.mjs` (oracle), `validate_v2.sh`/`.log` (oracle controls), `tool-edit-lists/` (the `rename` tool's own edit lists and their scoring), `runs.jsonl`, `grades.jsonl`, `patches/` |
| `05-structural/` | 5. Route map, tool map, API consumers | 30 scored, 1 excluded | `tasks.json`, `gt.json`, `gt.mjs`, `tool-output/` (`route_map`, `tool_map`, `api_impact` called directly), `answers/`, `runs.jsonl`, `grades.jsonl` |
| `06-taint/` | 6. Seeded taint flows | 8 scored | `seed.patch`, `seed-named.patch`, `gt.json`, `tool-output/` (`explain` called directly), `answers/`, `runs.jsonl`, `grades.jsonl` |
| `07-review/` | 7. Upstream review cases | 48 scored | `tasks.json` (upstream label and patch paths with sha256), `review-output/`, `runs.jsonl`, `scores.json` |
| `08-usage/` | 8. GitNexus and hook usage | | `hook-stats.jsonl` (per run), `usage-by-arm.json` |
| `haiku-view.md` | Haiku arms H0/H2 across tracks 1, 3, 4 and 5 | 66 | index |
| `report-data/` | Scorer outputs used for the report | | `O, U, P1, P2, P3, P4, RV.json`, `metrics.json` |
| `not-scored-smoke.jsonl` | Harness smoke runs before the tracks | 4 | excluded rows only |

## Run ids and the summary schema

Every `runs.jsonl` row uses the bundle's shared schema (`run, track, task, arm, engine, model, effort, trial, wall_s, cost_usd, cost_basis, tokens, turns, tool_calls, gitnexus_calls, hooks, outcome, graded_by, excluded, exclude_reason`).

- `run` is `<source run directory>/<run name>`, for example `runs-u-pdg/u-trivial-U_mcp-t1`. The directory prefix is needed because tracks 2 and 5 reuse run names across directories. Patch and answer files use the same path: `patches/<run>.diff`, `answers/<run>.json`.
- `track` uses the harness codes: O = 1, U = 2, P1 = 3, P2 = 4, P3 = 5, P4 = 6, RV = 7.
- `outcome` holds the grade of record. Change tasks (O, U, P2) use `hidden_tests_pass`, `regression_clean` and `resolved_clean` (hidden tests pass and the regression command did not fail) from `regrade.py`, which re-applied each saved patch to a fresh copy of the base. The in-run grades are left out. Probes use the scorer's per-run output (recall, precision, tp, gt and so on).
- `cost_basis`: Claude rows use the CLI's `total_cost_usd`. Codex rows are token counts times list price ($2 input, $0.10 cached input, $10 output per million tokens). Codex `tokens.in` is uncached input (input minus cached input), as for Claude rows; `cache_read` is the cached input.
- `turns` is null for Codex, because `codex exec` reports one turn per run.
- `gitnexus_calls` counts MCP calls by tool name, and `cli` counts GitNexus CLI calls made through the shell.
- `hooks` is set only for the arms that had the upstream hooks installed (A2, A3, H2). It is computed from the hook log: `calls` = hook invocations, `pre`/`post` = PreToolUse/PostToolUse, `enriched` = graph context injected, `hint` = the "augment is unavailable, use MCP" hint, `stale` = index-stale notice, `no_context` = nothing injected.
- `effort` comes from each run's command line. Claude runs used `--effort medium`. Codex runs used `model_reasoning_effort=medium`, except the review arms CR0 and CR1, which used `high`.

## Arms

| Arm | Setup |
|---|---|
| A0 / H0 / C0 | Opus 5.5 / Haiku 4.5 / Sol (gpt-6.1-sol), no GitNexus |
| A1 / C1 | Opus / Sol, our everyday setup: read-only GitNexus MCP (Opus also had our own GitNexus skills, not published) |
| A2 / H2 / C2 | Opus / Haiku / Sol, full upstream install: read-write MCP including `rename`, upstream skills, the AGENTS.md/CLAUDE.md block, and (Claude only) the hooks |
| A3 | Opus, full upstream install plus direct mode (`gitnexus-work` skill prompt) |
| U_nomcp / U_mcp / U_direct | Track 2: Opus, upstream's own workflow_bench arms (no GitNexus, MCP baseline, MCP plus skills plus direct mode) |
| R_plain / R_gnx / CR0 / CR1 | Track 7: Opus plain review, Opus with the `gitnexus-review` skill, Sol plain review, Sol with read-only MCP |

The exact arm definitions and prompt templates are in the harness. On tracks 1 and 3-6 every Claude arm (A0-A3, H0, H2) also carried our private instruction file, which told agents to prefer GitNexus; the no-GitNexus arms got a "GitNexus is not available" note on top of it. Every Codex arm (C0-C2, CR0, CR1) ran with our global Codex configuration (instruction file, skills and memories), whose instruction file told agents to use GitNexus first; C0 and CR0 also got the "not available" note. Neither is published; see Disclosures in the top-level README. Tasks where the Claude instruction file was applied have `user_instruction_file_on_claude_arms: true`.

## Exclusions (all present as rows with `excluded: true`)

- Track 1: 8 superseded rows (`#attempt1`, `#attempt2`) for four `worldos-c02` runs that a provider session limit or a relaunch stopped. The run directory and grade belong to the last row.
- Track 2: the 4 `runs-u/*-U_nomcp-t1` rows. Under the old isolation the audit found 2 of them (u-feat, u-cbug) reached the live GitNexus index, so the whole batch was rerun as `runs-u-nomcp-clean`. Their grades are kept in `outcome` but not counted.
- Track 3: the 10 rows of `runs-p1-aborted-npx-leak`, a batch discarded because an `npx` call escaped the isolation layer. No answers are shipped for them.
- Track 5: `runs-p3/p3-routes-C2-t1`, killed by a Codex "model at capacity" error. `runs-p3b/p3-routes-C2-t1` is the rerun.
- Not in any track: 4 harness smoke runs (`not-scored-smoke.jsonl`) and the 24 BASE/FIX controls (`01-fixes/controls.jsonl`).

## Path placeholders

Absolute paths from the bench machine (macOS, APFS clones) are replaced by placeholders: `$BENCH_ROOT` (the bench's artifacts directory, where `mining/_scripts/lcmx_pytest.sh` and `lcmx_setup.sh` live), `$BENCH_DIR` (its parent), `$WORK` (bench state), `$TASK_BASE` (task base checkouts), `$GITNEXUS_SRC` (upstream GitNexus checkout at c4ecf398), `$GITNEXUS_PKG` (the installed 1.6.12 package), `$NODE_BIN`, `$LOCAL_BIN`, `$BREW_PREFIX`, `$TMPDIR`, `$HOME`. `{TMP}`, `{IDS}` and `{ORACLE_DIR}` are the harness's own per-run placeholders. Patches, answers and review outputs contained no absolute paths, so none were rewritten.

## Notes

- Bases are not shipped. GitNexus tasks run on upstream c4ecf398de637cf779ab2238e69958cfd5d601ce; track 1's bases are the `base_sha` of each public PR. Track 6 adds `seed.patch` (the inline-callback module, as committed into the base after formatting, plus the `api.ts` mount). `seed-named.patch` turns it into the named-handler variant used only for the direct `explain` check.
- Track 2 `oracles/inv-bug-c-system-include.oracle.test.ts` has no upstream-orig because it was used unchanged. `upstream-orig.diff` shows the repairs made to the other three oracles and the vitest config.
- Track 3 `answers/` has 79 files for 80 runs. One H2 run wrote no answer in its run directory and scored as empty, as the scorer does.
- Track 4 `tool-edit-lists/<target>.json` holds every `rename` result returned to the Haiku H2 run for that target. `apply_and_check.py` applied `calls[0]` (for `getPhaseOutput` that is the dry-run list, which has the same edits as the applied call) to a fresh base and ran the v2 oracle, giving `engine-direct.json`.
- Track 7 labels are upstream files (`eval/workflow_bench/oracles/*.labels.json` at c4ecf398); `tasks.json` records their sha256. `score_review.py` is a port of upstream `review_scoring.py`.
- `08-usage/usage-by-arm.json` counts one row per run over these tracks only. The published usage figures were computed over every results row, including the 8 superseded track-1 rows (which re-read the final run's logs) and the hermes-agent runs. That changes three of the published figures. Opus with the full install was 18 of 37 runs (49%); one row per run gives 18 of 35 (51%). Direct mode was 13 of 14 (93%); one row per run gives 12 of 12 (100%). For the hooks, 81 contexts added in 1338 PreToolUse calls with 64 hints becomes 75 in 1136 with 58 hints. The Codex (100%, 97%) and Opus read-only (21%) figures are unchanged.
