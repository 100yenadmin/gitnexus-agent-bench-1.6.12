# GitNexus 1.6.12 agent benchmark: data bundle

This bundle holds the data behind
[Discussion #3493](https://github.com/abhigyanpatwari/GitNexus/discussions/3493) and
[issue #3500](https://github.com/abhigyanpatwari/GitNexus/issues/3500) on abhigyanpatwari/GitNexus. Those posts report a
benchmark of GitNexus 1.6.12 (commit `c4ecf398de637cf779ab2238e69958cfd5d601ce`) used as a code-navigation layer by
coding agents. The agents were:

- Opus 5.5 (`claude-opus-5-5`) and Haiku 4.5 (`claude-haiku-4-5-20251001`), through headless Claude Code;
- Sol 6.1 (`gpt-6.1-sol`), through `codex exec`.

The bundle contains the harness, task definitions, graders, answer keys, per-run patches and answers, and a summary of
each run. It does not contain the agent transcripts. Each run's summary (tool calls, GitNexus calls, tokens, cost,
wall time and grade) is published in their place; [What is withheld](#what-is-withheld-and-why) explains why.

The tool-level findings are filed separately as #3486-#3492 and #3497-#3499.

## Layout

| Directory | What it holds | Runs (scored + excluded rows) |
|---|---|---|
| `tracks/` | Claims bench, tracks 1-8 (#3493 opening post, #3500 claims table). Index: `tracks/README.md`. | 340 + 23 |
| `hermes-agent/impact/` | Impact questions on NousResearch/hermes-agent (#3493 first follow-up) | 80 |
| `hermes-agent/fix-sol/` | Sol fix tasks on hermes-agent (#3493 second follow-up) | 32 |
| `ab-ripgrep/` | Public subset of the earlier GitNexus vs ripgrep A/B (#3493 "What worked", #3500 hybrid-query row) | 137 + 14 |
| `harness/` | The code that ran and graded everything, with local paths moved into a config file. Index: `harness/README.md`. | - |
| `schema/run-summary.schema.json` | JSON Schema for every `runs.jsonl` row in the bundle | - |
| `LICENSE-NOTES.md` | Licenses for our files and for the upstream files copied into the bundle | - |

`hermes-agent/SETUP-NOTES.md` and `ab-ripgrep/README.md` describe those two studies in detail.

### Per-run summaries

Every `runs.jsonl` row has the same 20 keys:
`run, track, task, arm, engine, model, effort, trial, wall_s, cost_usd, cost_basis, tokens, turns, tool_calls,
gitnexus_calls, hooks, outcome, graded_by, excluded, exclude_reason`.
They are defined in `schema/run-summary.schema.json`, and all 630 rows in the bundle conform to it.

- `outcome` is the grade of record, not the grade computed during the run. For change tasks it comes from
  `regrade.jsonl` (shipped as `grades.jsonl`): each saved patch was re-applied to a fresh copy of the base, then the hidden tests and the
  regression command were run.
- Excluded runs are present as rows with `excluded: true` and a reason, so totals reconcile with the posts.

## Published claims and the files behind them

Counts are scored runs. "of 12" and similar refer to tasks. The posts name setups X0-X3; in the data X is A (Opus), C (Sol)
or H (Haiku), so "Opus X0-X3" means A0-A3.

### Discussion #3493, opening post, and the #3500 claims table

| Claim | Value | Files | Count |
|---|---|---|---|
| Graded runs | 340 (66 of them Haiku) | `tracks/*/runs.jsonl` (rows with `excluded: false`), `tracks/haiku-view.md` | 340 |
| Notional spend, including smoke tests and discarded runs | about $243 | `tracks/*/runs.jsonl` (all rows) + `tracks/not-scored-smoke.jsonl` | 363 + 4 rows; sum $242.62 |
| Track 1: resolved with no regressions, Opus X0-X3 | 8 / 7 / 9 / 8 of 12 | `tracks/01-fixes/runs.jsonl`, `grades.jsonl`, `patches/`, `oracle/`, `tasks.json` | 108 runs, 108 patches, 12 tasks, 16 hidden-test files |
| Track 1: Sol X0-X2 / Haiku X0, X2 | 11 / 10 / 10 and 7 / 5 of 12 | same | same |
| Track 1: cost vs X0 | Opus 1.07 / 1.11 / 1.41x, Sol 1.10 / 1.20x, Haiku 0.95x | `tracks/01-fixes/runs.jsonl` (`cost_usd`), `tracks/report-data/O.json` | 108 |
| Track 1: GitNexus calls per run | Opus 0.0 / 1.1 / 4.7, Sol 3.0 / 7.8, Haiku 1.1 | `tracks/01-fixes/runs.jsonl` (`gitnexus_calls`) | 108 |
| Track 1: tasks are valid (base fails, fix passes) | 12 / 12 | `tracks/01-fixes/validate/`, `controls.jsonl`, `controls/` | 12 files, 24 controls |
| Noise floor: A1 made 0 GitNexus calls but differed from A0 on 3 of 12 tasks | 1 better, 2 worse | `tracks/01-fixes/runs.jsonl` | 24 |
| Track 2: upstream workflow_bench, every arm | 2 of 4 on both index variants | `tracks/02-workflow-bench/runs.jsonl`, `grades.jsonl`, `patches/`, `oracles/` (+ `upstream-orig.diff`), `excluded.txt` | 24 scored, 4 excluded |
| Track 2: mean cost per run | $1.09 / $1.22 / $1.78; cross-module task $1.85 / $1.66 / $2.97 | `tracks/02-workflow-bench/runs.jsonl` | 24 |
| Track 3: impact recall / precision | Opus and Sol 1.00 / 1.00; Haiku 0.99 / 0.92 (H0), 0.87 / 0.82 (H2) | `tracks/03-impact-ts/answers/`, `gt.json`, `gt.mjs`, `runs.jsonl`, `grades.jsonl` | 80 runs, 79 answer files (one H2 run wrote none) |
| Track 3: Sol cost per question | $0.12 (C0) / $0.18 (C2) | `tracks/03-impact-ts/runs.jsonl` | 20 |
| Track 4: agent renames | 41 of 42 runs | `tracks/04-rename/runs.jsonl`, `grades.jsonl`, `patches/`, `spec_v2.json`, `rename_gt_v2.mjs` | 42 |
| Track 4: the `rename` tool's own edit lists (#3486) | pass 2 of 6; 138 of 146 locations; 38 comment edits; 185 edits labelled "graph" | `tracks/04-rename/tool-edit-lists/` (`summary.json`, `tool-vs-ts.json`, `engine-direct.json`, 6 per-target lists) | 6 targets |
| Track 5: `tool_map`, `route_map` (#3487), `api_impact` (#3488) | 17/17, 21/27 (+32 extra entries), 0/9 | `tracks/05-structural/tool-output/`, `gt.json`, `gt.mjs` | 7 tool-output files |
| Track 5: agents answered all three questions exactly (Opus, Sol) | - | `tracks/05-structural/answers/`, `runs.jsonl`, `grades.jsonl` | 30 |
| Track 6: `explain` taint (#3489, #3490, #3491) | 0 of 3 flows on inline callbacks; 3 of 4 on named handlers | `tracks/06-taint/tool-output/`, `seed.patch`, `seed-named.patch`, `gt.json` | 4 `explain` outputs |
| Track 6: agents | 3 of 3 flows, 0 decoys, in all 8 runs | `tracks/06-taint/answers/`, `runs.jsonl`, `grades.jsonl` | 8 |
| Track 7: labelled review issues found | 2 / 2 / 2 / 4 of 42; $0.81 / $1.05 / $0.41 / $0.48 per review | `tracks/07-review/review-output/`, `runs.jsonl`, `scores.json`, `tasks.json` (upstream label paths + sha256) | 48 |
| Track 8: share of runs that called GitNexus | Codex 100% / 97%; Opus 21% / 49% / 93% | `tracks/report-data/metrics.json` (`use.*`); per run: `tracks/08-usage/` | see [Known differences](#known-differences-between-the-data-and-the-posts) |
| Track 8: hook enrichment in the full install | 81 contexts in 1338 PreToolUse calls, 64 hints | `tracks/report-data/metrics.json` (`hooks.*`), `tracks/08-usage/hook-stats.jsonl` | 86 rows (80 runs + 6 superseded rows); see Known differences |
| Contamination guard: 0 contaminated scored runs | - | `tracks/report-data/metrics.json` (`audit`) | - |

### #3493 follow-up: hermes-agent impact questions (comment 18771219) and the #3500 "MUST run impact" row

| Claim | Value | Files | Count |
|---|---|---|---|
| Answer key | 147 sites over 8 targets | `hermes-agent/impact/gt.json`, `pyright/` (probes, per-platform diffs, baselines), `adjudication.json`, `adjudication-notes.md`, `references/`, `verify-jedi/` | 8 targets, 44 pyright files |
| `impact` on its own | 133 of 147 sites covered; `exact` on all 8 targets; symbol precision 1.00 | `hermes-agent/impact/toolonly.json` | 8 |
| Agents found every site | 79 of 80 runs | `hermes-agent/impact/answers/`, `runs.jsonl`, `score.json` | 80 runs, 80 answers |
| Recall / precision / cost / GitNexus calls per arm | A0 1.000 / 0.998 / $0.50 / 0; A1f 1.000 / 0.998 / $0.55 / 0.2; A1m 0.997 / 1.000 / $0.60 / 2.2; C0 1.000 / 1.000 / $0.17 / 0; C1f 1.000 / 1.000 / $0.22 / 3.1 | `hermes-agent/impact/runs.jsonl`, `score.json` | 16 per arm |
| Cost increase vs the no-GitNexus arm | +10% / +20% / +30% | same | 80 |

### #3493 follow-up: hermes-agent fix tasks, Sol only (comment 18771958)

| Claim | Value | Files | Count |
|---|---|---|---|
| Hidden tests pass | 16/16 and 16/16 | `hermes-agent/fix-sol/runs.jsonl`, `grades.jsonl`, `patches/`, `oracle/`, `regression-files/`, `tasks.json` | 32 runs, 32 patches, 8 tasks, 11 hidden-test files |
| Also no regressions | 15/16 vs 14/16 | same | 32 |
| Mean cost / wall time / GitNexus calls | $0.32 vs $0.39 (+24%); 127 s vs 144 s (+13%); 9.4 calls | `hermes-agent/fix-sol/runs.jsonl` | 32 |

### #3493 "What worked" and the #3500 hybrid-query row: the A/B

The A/B had 163 runs on 16 repositories. Three of those repositories are private, so this bundle holds only the public
subset: 137 runs on 13 repositories, with all 70 blind-graded answers (every graded question was on a public
repository).

| Claim | Public-subset value | Files |
|---|---|---|
| Accuracy matched ripgrep plus reading | Find top-1 of 13: rg 12, gnx 13, gnxf 12 (the miss is the ambiguous P10); callers and Opus impact perfect in every arm; blind grades unchanged | `ab-ripgrep/runs.public.jsonl`, `ground-truth.public.json`, `blind-grades.public.json` |
| 20-60% higher cost on find-and-understand | +24% to +26% (find), +21% (realF), +40% (cxB) where GitNexus was called; three setups fall outside the range | `ab-ripgrep/scores.public.json` (`cost_comparisons`) |
| Opus 14-43% cheaper on 2 of 3 multi-hop questions | Both cheaper questions (I01, I03) are public: -14% to -43%. The third question is on a private repository and is not here. | `ab-ripgrep/scores.public.json` (`multi_hop_impact_opus_n1`) |
| Hooks-only test: context added to 25% of calls | 22 of 88 hook calls | `ab-ripgrep/runs.public.jsonl` (`hooks`) |

`ab-ripgrep/README.md` checks each statement against the subset and gives the full-set figures where they differ.

## Setups (arms)

| Arm | Where | Model | GitNexus |
|---|---|---|---|
| A0 / H0 / C0 | tracks 1, 3-6 (H0: 1, 3-5); hermes (A0, C0) | Opus / Haiku / Sol | none; "GitNexus is not available" note |
| A1 / C1 | tracks 1, 3 (A1 also 4) | Opus / Sol | read-only MCP (Opus also had our own GitNexus skills) |
| A2 / H2 / C2 | tracks 1, 3-6 (H2: 1, 3-5) | Opus / Haiku / Sol | full upstream install: read-write MCP with `rename`, upstream skills, the AGENTS.md/CLAUDE.md block, hooks (Claude only) |
| A3 | track 1 | Opus | A2 plus the `gitnexus-work` direct-mode prompt |
| U_nomcp / U_mcp / U_direct | track 2 | Opus | upstream workflow_bench arms and prompts, verbatim |
| R_plain / R_gnx | track 7 | Opus | upstream review prompts: plain, and with the `gitnexus-review` skill |
| CR0 / CR1 | track 7 | Sol, high effort | none / read-only MCP |
| A1f / C1f | hermes | Opus / Sol | read-only MCP and a "use GitNexus first" prompt |
| A1m | hermes impact | Opus | read-only MCP and a prompt that requires `impact` |
| rg, gnx, gnxf, realA/B/F, augH0/Hk, cxA/B | A/B | Opus / Sol | see `ab-ripgrep/README.md` |

Claude arms ran at medium effort. Codex arms ran at medium effort, except CR0 and CR1 (high). The full arm table,
with MCP mode, skills, prompt template, system prompt and hooks for each arm, is in `harness/README.md`. The prompt
constants are in `harness/runner/bench.py`.

Scored runs per arm:

| Track | Arms | Runs |
|---|---|---|
| 1 (O) | A0, A1, A2, A3, C0, C1, C2, H0, H2: 12 each | 108 |
| 2 (U) | U_nomcp, U_mcp, U_direct: 8 each | 24 |
| 3 (P1) | A0, A1, A2, C0, C1, C2, H0, H2: 10 each | 80 |
| 4 (P2) | A0, A1, A2, C0, C2, H0, H2: 6 each | 42 |
| 5 (P3) | A0, A2, C0, C2, H0, H2: 5 each | 30 |
| 6 (P4) | A0, A2, C0, C2: 2 each | 8 |
| 7 (RV) | R_plain, R_gnx, CR0, CR1: 12 each | 48 |
| hermes impact | A0, A1f, A1m, C0, C1f: 16 each | 80 |
| hermes fix | C0, C1f: 16 each | 32 |
| A/B (public subset) | rg, gnx, gnxf: 17 each; realA, realB, realF: 10 each; augH0, augHk, cxA, cxB: 14 each | 137 |

## Disclosures

These affect how the results should be read.

- **Beyond our posted correction.** Comment 18772530 listed the Codex setups and the hermes impact Claude setups. Two
  more items were not in any post: the A/B `real*` and `aug*` Claude setups also carried our instruction file, and the
  hermes impact setups A1f and A1m also had our own `gitnexus-*` skills. The A/B setups behind the multi-hop result
  (`rg`, `gnx`, `gnxf`) carried neither.
- **Our private instruction file.** The following Claude setups carried our global agent instruction file:
  - every Claude setup in claims-bench tracks 1 and 3-6 (A0, A1, A2, A3, H0, H2);
  - every Claude setup in the hermes impact track (A0, A1f, A1m);
  - the A/B `real*` setups (through our user-level Claude settings, which also loaded our skills and plugins) and
    `aug*` setups (appended as a system prompt).

  The file is general-purpose and is withheld. Its sha256 and size are in
  `harness/runner/owner-instructions.PLACEHOLDER.md`. At the time of the runs, one section told agents to prefer
  GitNexus over grep and whole-file reads on indexed repositories.
- **"Not available" note.** Setups without GitNexus got a one-line note that GitNexus is not available, which overrides
  that section: A0, H0 and C0 in the claims bench, CR0 in track 7, A0 and C0 in the hermes tracks, and realA, augH0
  and cxA in the A/B. The exact strings are in `harness/runner/bench.py` (`NOTE_OFF`) and `ab-ripgrep/README.md`.
- **Our skills.** A1 (claims bench) and A1f/A1m (hermes impact) also had our own local versions of ten `gitnexus-*`
  skills. They have since been deleted, so no hash is available.
- **Our Codex configuration.** Every Codex setup ran with our global Codex configuration: instruction file, skills
  and memories. In the claims bench (C0-C2, CR0, CR1) and the A/B (cxA, cxB), that instruction file told agents to use
  GitNexus first. In the hermes tracks (C0, C1f) it described GitNexus as optional. Some
  Codex runs read files from that configuration, including the memory directory, during the run. This is one reason
  the transcripts are withheld.
- **Upstream prompts.** Tracks 2 and 7 used upstream's prompts verbatim. Their Claude setups carried none of our
  instructions. The track 7 Codex setups (CR0, CR1) still ran with our Codex configuration.
- **Cost basis.** Costs are notional, at API list prices:
  - Claude: the CLI's `total_cost_usd` (`cost_basis: cli_total_cost_usd`).
  - Codex: token counts x the `gpt-6.1-sol` list price of $2.00 per million uncached input tokens, $0.10 per million
    cached input tokens and $10.00 per million output tokens (`cost_basis: tokens_x_list_price`).

  Compare costs within a batch only.
- **Wall time.** Measured on a loaded machine. Indicative only.
- **Isolation.** Runs used our own harness on macOS, with each run on its own APFS clone of the task base, its own
  GitNexus home, temp directory and npm prefix. This is not upstream's Bubblewrap runner. In setups without GitNexus,
  every entry point (MCP, CLI, `npx`, `.gitnexus/run.cjs`) was stubbed to "not found". A `gitnexus_calls.cli` count in
  those setups is an attempt that reached the stub.
- **Embeddings.** Indexes used voyage-code-4 embeddings (1024 dimensions), and the MCP server ran with
  `GITNEXUS_VECTOR_MAX_DISTANCE=1.0` instead of the default 0.6 (#3457).
- **Hermes fix-task index.** That track used the nightly index at `d62fbea7`, which was 14-301 first-parent commits
  older than each task base. It was not rebuilt per task.

## What is withheld and why

- **Agent transcripts.** They are withheld because they contain our private instruction files, local paths and
  private context that agents read during runs. They are replaced by the per-run summaries in each `runs.jsonl`.
  The agents' free-text final messages are also withheld.
- **Per-run prompt and command files.** The per-run system prompt, command line and stderr files carry the same
  content.
- **Our instruction file, skills, Codex configuration and user-level Claude settings.** These are private. The
  harness reads them from configuration variables (`OWNER_INSTRUCTIONS_FILE`, `OWNER_SKILLS_DIR`,
  `CODEX_HOME_FOR_RUNS`), and the placeholder file records the instruction file's hash.
- **Local paths.** These are replaced throughout by placeholders such as `$BENCH_ROOT`, `$BENCH_ARTIFACTS`,
  `$TASK_BASE`, `$WORK` and `$GITNEXUS_PKG`. Each directory's README lists the placeholders it uses.
- **Three private A/B repositories.** Their tasks (P04, P07, P13, C03, C04, I02) and all 26 runs on them are removed.
- **Repository checkouts and task bases.** They are not shipped. Every base can be rebuilt from public commits: GitNexus
  `c4ecf398`; the lcm-x and WorldOS base and fix SHAs in `tracks/01-fixes/tasks.json`; the hermes-agent SHAs in
  `hermes-agent/fix-sol/tasks.json` and the impact base `d62fbea7`; and the A/B commits in
  `ab-ripgrep/tasks.public.json`. The track 6 seeded code ships as `tracks/06-taint/seed.patch`. The steps are under
  "Rebuilding bases" in `harness/README.md`.
- **Outputs that cannot be regenerated without transcripts.** `scan_gnx.py`, `scan_writes.py` and the rename tool's
  `apply_and_check.py` read the transcripts, so their published outputs can't be regenerated from this bundle. Those
  outputs are the contamination audit in `tracks/report-data/metrics.json` and `tracks/04-rename/tool-edit-lists/`.

## Exclusions

Every excluded row is in the relevant `runs.jsonl` with `excluded: true` and a reason.

| Where | Rows | Reason |
|---|---|---|
| `tracks/01-fixes` | 8 | Superseded attempts (`#attempt1`, `#attempt2`) of four `worldos-c02` runs that a provider session limit or a relaunch stopped. The last row is the run of record. |
| `tracks/02-workflow-bench` | 4 | The first U_nomcp batch (`runs-u/*-U_nomcp-t1`). Under the old isolation, the audit found 2 of these runs reached the live GitNexus index, so the batch was rerun as `runs-u-nomcp-clean`. The grades are kept but not counted. |
| `tracks/03-impact-ts` | 10 | A discarded batch (`runs-p1-aborted-npx-leak`): an `npx` call reached a GitNexus install outside the isolation layer. No answers are shipped. |
| `tracks/05-structural` | 1 | `runs-p3/p3-routes-C2-t1`, killed by a Codex "model at capacity" error. It was rerun as `runs-p3b/p3-routes-C2-t1`. |
| `tracks/not-scored-smoke.jsonl` | 4 | Harness smoke tests run before the tracks. |
| `ab-ripgrep` | 14 | `cxA` launch failures: a bad flag made codex exit with rc=2 after 0 s and zero tokens. Each was rerun. |
| `ab-ripgrep` (not shipped) | 26 runs | Runs on the three private repositories: 18 narrow, 4 Codex and 4 hooks-only. Counts only, in `ab-ripgrep/scores.public.json`. |
| `hermes-agent/fix-sol` (not shipped) | 7 rows | A Claude (Opus) fix run set, arms A0 and A1m, stopped early. It is not part of any published number. |

The 24 BASE/FIX controls in `tracks/01-fixes/controls.jsonl` are task-validity checks, not agent runs.

## Recomputing the headline numbers

Run these from the bundle root. Python 3 is enough for everything below. Regrading patches or regenerating answer keys requires rebuilt bases; see
`harness/README.md`.

```sh
# Claims bench, tracks 1-7: 51 checks against the published values (counts, resolved,
# mean costs, recall/precision, rename, route_map/tool_map/api_impact, taint, review).
# Prints one OK/MISMATCH line per check and exits 0 if all match.
(cd tracks && python3 verify_tracks.py)

# Track 1: cost ratio vs X0 and GitNexus calls per run, by arm
python3 - <<'EOF'
import json, statistics as st
rows = [r for r in map(json.loads, open("tracks/01-fixes/runs.jsonl")) if not r["excluded"]]
arm = lambda a: [r for r in rows if r["arm"] == a]
cost = lambda a: st.mean(r["cost_usd"] for r in arm(a))
for a, base in [("A1","A0"),("A2","A0"),("A3","A0"),("C1","C0"),("C2","C0"),("H2","H0")]:
    print(a, round(cost(a) / cost(base), 2), round(st.mean(sum(r["gitnexus_calls"].values()) for r in arm(a)), 1))
EOF

# hermes-agent: impact recall/precision/cost/GitNexus calls per arm; fix pass rates, cost, wall time
python3 - <<'EOF'
import json, statistics as st
for f in ["hermes-agent/impact/runs.jsonl", "hermes-agent/fix-sol/runs.jsonl"]:
    rows = [r for r in map(json.loads, open(f)) if not r["excluded"]]
    for a in sorted({r["arm"] for r in rows}):
        rs = [r for r in rows if r["arm"] == a]; o = [r["outcome"] for r in rs]
        if "recall" in o[0]:
            print(a, round(st.mean(x["recall"] for x in o), 3), round(st.mean(x["precision"] for x in o), 3),
                  sum(x["recall"] == 1 for x in o), "of", len(o), "perfect", end=" ")
        else:
            print(a, sum(x["hidden_tests_pass"] for x in o), sum(x["hidden_tests_pass"] and x["regression_clean"] for x in o),
                  "of", len(o), round(st.mean(r["wall_s"] for r in rs), 1), "s", end=" ")
        print("$%.3f" % st.mean(r["cost_usd"] for r in rs), round(st.mean(sum(r["gitnexus_calls"].values()) for r in rs), 2))
t = json.load(open("hermes-agent/impact/toolonly.json"))
print("impact alone:", sum(v["sites"] - len(v["missed"]) for v in t.values()), "of", sum(v["sites"] for v in t.values()),
      sorted({v["epistemic"] for v in t.values()}))
EOF

# A/B public subset: cost comparisons and multi-hop table
python3 -c "import json; s=json.load(open('ab-ripgrep/scores.public.json')); [print(c) for c in s['cost_comparisons']]; [print(m) for m in s['multi_hop_impact_opus_n1']]"
```

Usage shares and hook totals as published are in `tracks/report-data/metrics.json`, as flattened keys under `metrics`
(for example `use.A2.share` and `hooks.total`).
`build_report.py` in `harness/grading/` regenerates `tracks/report-data/*.json` from the run data.

## Known differences between the data and the posts

- **Usage percentages (track 8).** The published figures were computed over every results row. That count includes the
  8 superseded track 1 rows and the hermes-agent runs. Counted one row per run over tracks 1-7
  (`tracks/08-usage/usage-by-arm.json`), three figures change:
  - Opus with the full install: 49% becomes 51% (18 of 35).
  - Direct mode: 93% becomes 100% (12 of 12).
  - Hook totals: 81 contexts, 1338 PreToolUse calls and 64 hints become 75, 1136 and 58.

  The Codex (100%, 97%) and Opus read-only (21%) figures do not change.
- **Codex `tokens.in`.** Everywhere in this bundle, `tokens.in` on Codex rows is uncached input (input minus cached
  input) and `cache_read` is the cached input, so it means the same as on Claude rows. Costs recompute as
  `in x $2 + cache_read x $0.10 + out x $10` per million tokens.
- **Placeholders.** `$BENCH_ROOT` means different things in different directories:
  - in `tracks/`, the claims-bench artifacts directory;
  - in `hermes-agent/`, the benchmark working directory;
  - in `harness/`, the state root. The harness calls the artifacts directory `$BENCH_ARTIFACTS`.

  The task files that the runner reads (`tracks/01-fixes/tasks.json`, `hermes-agent/fix-sol/tasks.json`) now use the
  harness placeholders: the pytest wrappers are `$HARNESS/mining/lcmx_pytest.sh` and
  `$HARNESS/hermes/mining/hermes_pytest.sh`, and `$BUNDLE` (the bundle root) is set automatically. Other `$BENCH_ROOT`
  values in data files under `tracks/` mean the claims-bench data directory, which the harness calls
  `$BENCH_ARTIFACTS`.
- **Spend in `metrics.json`.** `spend.total` ($293.91 over 510 rows) was regenerated after the hermes-agent tracks and
  sums every results file we had: the 391 claims-bench rows (the 367 here plus 24 zero-cost BASE/FIX controls; $242.62,
  the "about $243" in the opening post) and 119 hermes-agent rows ($51.29). Those include the 7 rows of the stopped Opus
  fix set ($7.14), which are not shipped. `spend.scored` uses the same scope.
- **A/B narrow scoring.** #3500 says the narrow A/B questions "were scored against hand-checked answers". The 16 find
  tasks were scored by matching the agent's answer to a hand-picked target symbol; only the callers and impact
  questions have fully hand-verified answer keys (`ab-ripgrep/ground-truth.public.json`).
- **Haiku impact recall.** One H2 answer in track 3 was saved outside its run directory and is scored as empty, as
  in the posts. If it were counted, H2 recall would be 0.97.

## License

Our harness, data and documentation are under the MIT license. Upstream files copied into the bundle keep their
repositories' licenses. See `LICENSE-NOTES.md`.
