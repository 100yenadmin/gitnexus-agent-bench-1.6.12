# hermes-agent tracks: setup notes

This directory holds two benchmark tracks run on the public repository
[NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) with GitNexus 1.6.12:

| Track | Directory | Tasks | Arms | Runs |
|---|---|---|---|---|
| Impact Q&A ("what must change if this signature changes?") | `impact/` | 8 targets at base `d62fbea7e110c6008e1ffe1b226d1f593ba4bc28` | A0, A1f, A1m, C0, C1f (16 runs each = 8 tasks x 2 trials) | 80 |
| Bug fixes from merged upstream PRs | `fix-sol/` | 8 tasks (base/fix SHAs in `fix-sol/tasks.json`) | C0, C1f (16 runs each = 8 tasks x 2 trials) | 32 |

Every run used its own APFS clone of the task base on macOS. Runs were headless and single-shot, with no retries for answer quality.

## Arms

| Arm | Engine | Model | Effort | GitNexus MCP | Prompt addition | Our private instruction file | Our global Codex configuration |
|---|---|---|---|---|---|---|---|
| A0 | Claude Code (`claude -p`) | claude-opus-5-5 | medium | off (empty MCP config) | none | **yes**, appended as a system prompt, plus a short note saying GitNexus is not available and to use normal search and file reads | n/a |
| A1f | Claude Code | claude-opus-5-5 | medium | on, read-only tools | "GitNexus first": the graph is available; run `context` on the symbols involved and upstream `impact` on the target before answering; normal search may be used to verify | **yes** | n/a |
| A1m | Claude Code | claude-opus-5-5 | medium | on, read-only tools | "GitNexus must": you must call `context` and upstream `impact` on the target first; an answer without an `impact` call is invalid; verify and add anything the graph missed | **yes** | n/a |
| C0 | Codex CLI (`codex exec`) | gpt-6.1-sol | medium | off (`mcp_servers.gitnexus.enabled=false`) | a short note saying GitNexus is not available, placed before the task | n/a | **yes** |
| C1f | Codex CLI | gpt-6.1-sol | medium | on, read-only tools (`mcp_servers.gitnexus.enabled=true`) | the same "GitNexus first" addition as A1f | n/a | **yes** |

The fix track ran only the C0 and C1f arms. The prompt additions above are paraphrased here. The exact strings are in the
harness (`harness/`), not in this directory.

Disclosures:

- **Private instruction file (A0, A1f, A1m).** All 48 Claude impact runs carried our private user-level instruction file
  as an appended system prompt. That file is a general working-practices document and is not published. In A0 the same
  file was followed by the "GitNexus is not available" note.
- **Global Codex configuration (C0, C1f).** Codex runs used our live global Codex configuration (global instructions,
  skills and memory directories). At run time it described GitNexus as optional. Each arm set the GitNexus MCP server
  on or off explicitly on the command line.
- **Skills.** A1f and A1m also had our local copies of the `gitnexus-*` skills copied into the clone's `.claude/skills/`.
  A0, C0 and C1f got no skills from the harness.
- **No hooks.** No arm in these tracks installed GitNexus hooks, so `hooks` is `null` in every `runs.jsonl` row.

GitNexus isolation:

- The task base carried a GitNexus 1.6.12 index of the base commit.
- In GitNexus arms, each run registered its clone's index in its own private GitNexus home, so `list_repos` could reach only that run's checkout.
- The read-only tool set was `list_repos, query, context, check, impact, explain, pdg_query, route_map, tool_map,
  shape_check, api_impact, trace, detect_changes`. There was no `rename`.
- In no-GitNexus arms the clone's index was deleted, `GITNEXUS_HOME` pointed at an empty directory, and any `gitnexus` on
  `PATH` was a not-found stub.

Sandboxing: Claude ran with `--permission-mode dontAsk` and its Bash sandbox enabled, with Write/Edit scoped to the
clone. Codex ran with `--sandbox workspace-write --ephemeral`. In both tracks a `hermes` shim on `PATH` ran the clone's own CLI
(`.venv/bin/python -m hermes_cli.main`) against a per-run temporary `HERMES_HOME`, never an installed Hermes.

## Placeholders

Absolute local paths were replaced as follows:

| Placeholder | Meaning |
|---|---|
| `$TASK_BASE` | the prepared checkout of the task base commit (with `.venv`) |
| `$WORK` | the per-run APFS clone root |
| `$BENCH_ROOT` | the benchmark working directory |
| `$HARNESS` | the bundle's `harness/` directory; `$HARNESS/hermes/mining/hermes_pytest.sh` is the hermetic pytest wrapper |
| `$BUNDLE` | the root of this bundle |
| `$PYRIGHT_PKG` | the pyright 1.1.414 npm package used for the ground truth |
| `$PYTHON_HOME` | the uv-managed CPython install |
| `$TMPDIR` | the per-user temp directory |
| `{TMP}`, `{RUNDIR}` | per-run harness placeholders (temp root, clone directory), kept as the harness wrote them |

`impact/references/*.jsonl` quote source lines from the upstream repository. Two upstream lines held contributor email
addresses, and we replaced those with `<email-redacted>`.

## Field conventions in `runs.jsonl`

- **`tokens`.**
  - Claude rows copy the CLI's usage (`in` = uncached input).
  - For Codex rows, `in` = input tokens minus cached input tokens and `cache_read` = cached input tokens. Codex reports no cache-creation count, so `cache_create` is `null`.
- **`cost_usd`.**
  - Claude: the CLI's `total_cost_usd` (`cost_basis: cli_total_cost_usd`).
  - Codex: tokens x list price for gpt-6.1-sol, which is $2.00/MTok uncached input, $0.10/MTok cached input and $10.00/MTok output (`cost_basis: tokens_x_list_price`). The Codex costs in this directory recompute exactly from `tokens`.
- **`turns`.** Claude: the turn count the harness parsed from the CLI's stream-json output. Codex: `turn.completed` events (always 1 for `codex exec`).
- **`tool_calls`.**
  - Claude: tool-use counts by tool name, including `mcp__gitnexus__*`.
  - Codex: completed item counts by item type (`command_execution`, `file_change`, `mcp_tool_call`, `todo_list`). The `agent_message` and `error` items are dropped.
- **`gitnexus_calls`.** GitNexus MCP calls by tool name (`impact`, `context`, `list_repos`, ...).
- **`outcome`.**
  - Impact: `recall`, `precision`, `tp`, `gt` and `answered` (number of distinct locations listed), from `impact/score.json`. A listed location matches a ground-truth site on the same repo-relative path within +-2 lines, one-to-one, nearest first.
  - Fix: `hidden_tests_pass` and `regression_clean` from `fix-sol/grades.jsonl`, the grade of record, plus `regression_failed_tests` when the regression suite failed. A regression failure counts only after two isolated reruns of the failing tests.
- **`excluded`.** `false` on every row here.
- **Not published.** A Claude (claude-opus-5-5) fix run set on this track (arms A0 and A1m) was stopped early after 7 result rows (4 graded). It is not part of any published number except the bundle-wide `spend.*` totals in `tracks/report-data/metrics.json`, and no rows or files from it are included.

## Ground truth (impact)

- **How the key was built.** `impact/gt.json` holds 147 sites across 8 targets. For each target, a probe adds a required parameter (`impact/pyright/<target>.probe.diff`). Pyright 1.1.414 is then run on the whole repository on Darwin, Linux and Windows, and every newly reported error is a site (`*.pyright-diff.json`, compared against `pyright/baseline-*.json.gz`).
- **Runtime-only sites.** Two sites that break only at runtime were added by hand (`adjudication.json`, `adjudication-notes.md`).
- **Completeness checks.** `impact/references/` classifies every same-name token. `impact/verify-jedi/` cross-checks the key with jedi.
- **Spare targets.** `targets.json` and the pyright files cover 10 candidate targets. Only the 8 marked `selected` in `gt-summary.json` were run.
- **Impact tool alone.** `impact/toolonly.json` scores GitNexus `impact` (upstream) run directly on each target against the same key. A site counts as covered when one of impact's depth-1 symbols is the function or method enclosing it (or its file, for module-level sites).
