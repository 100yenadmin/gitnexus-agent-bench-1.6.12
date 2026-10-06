# Harness

The code that ran the GitNexus 1.6.12 agent benchmark: the run harness, isolation wrappers, base builders, graders,
ground-truth generators and the two follow-up studies (hermes-agent impact track, GitNexus vs ripgrep A/B). It is the
code we ran, with every machine-specific path, binary location and the embedding-key lookup moved into one config
file. Behaviour is otherwise unchanged; each file that differs in more than paths says so in a "Published version"
comment, and the differences are listed under [Changes from the code we ran](#changes-from-the-code-we-ran).

It was run on macOS with APFS clones (`cp -c`); the clone and `lsof`/`lockf` calls assume macOS.

## Layout

| Dir | What it holds |
| --- | --- |
| `runner/` | `bench.py` (all arms, all claims-bench tracks and the hermes track), `upstream-block.md` (upstream's AGENTS.md block template), `owner-instructions.PLACEHOLDER.md` |
| `isolation/` | GitNexus launchers (per-run, read-only, read-write), `bench-admin.sh` (bench registry), `bench-refresh.sh` (re-analysis), `hook-logger.sh` (wraps upstream's Claude hook), `run.cjs` (stand-in for `.gitnexus/run.cjs`), PATH shims and the not-found stub, `_config.sh` |
| `setup/` | Base builders: Track U / P1-P3 base (GitNexus c4ecf398), PDG variant, P4 taint bases, review-case bases, Track O bases (lcm-x, WorldOS) |
| `grading/` | `regrade.py` (grade of record for change tasks), `report.py`, probe scorers `score_p1/p3/p4/review.py`, contamination audits `scan_gnx.py` / `scan_writes.py`, `costs.py`, `build_report.py` (runs everything, writes report-data/*.json) |
| `ground-truth/` | Answer-key generators: P1 impact (`p1/gt.mjs`, `p1/enumerate.mjs`), P2 rename oracle (`p2/rename_gt_v2.mjs`, `p2/direct/apply_and_check.py`), P3 routes/tools/consumers (`p3/gt.mjs`), P4 MCP client for `explain` (`p4/mcp_call.mjs`) |
| `mining/` | Track O task mining and validation (lcm-x, WorldOS): `validate.py`, `build_tasks.py`, `check_clean.py`, the lcm-x pytest wrappers, task metadata |
| `hermes/` | hermes-agent impact track: scorer, base builders, the pyright ground-truth pipeline (`impact/`), tool-only scoring (`impact/toolonly/`), the jedi cross-check (`impact/verify/`), and task mining (`mining/`) |
| `ab-ripgrep/` | GitNexus vs ripgrep A/B: Claude runner `run.py`, Codex runner `codex_run.py`, scorers, blind-judge packet builders and runners |
| `common/` | `benchenv.py`: config loading and task-file placeholder expansion |

## How the pieces fit

1. **Bases** (`setup/`, `hermes/setup_h_base.sh`). Each task runs on a prepared base checkout under
   `$BENCH_ROOT/tasks/...`: source at the task's base commit, dependencies installed, and a GitNexus index current
   for that commit. GitNexus bases are parentless snapshots (`git archive` of a public commit, with
   `eval/workflow_bench` removed so the hidden oracles are absent). lcm-x, WorldOS and hermes-agent bases are clones
   that hold only ancestors of the base commit (no tags, no remote, reflog expired), and each script checks that the
   fix commit is absent from the object store. Indexes start as an APFS copy of a seed index and are re-analyzed at
   the base commit by `isolation/bench-refresh.sh` in a dedicated bench home. Every SHA is public: GitNexus
   c4ecf398 and the five review commits (in `setup/setup_review_all.sh`), lcm-x and WorldOS base/fix SHAs in the
   mined task files (`mining/tasks-o.json`, built by `mining/build_tasks.py` from `validate.py` output), hermes-agent
   base/fix SHAs in `tasks-h.json`, and the hermes impact base d62fbea7.
2. **Runs** (`runner/bench.py <tasks.json> <out_dir> --arms A0,A2 [--trials N] [--jobs N]`). Per run: APFS clone of
   the base into `$BENCH_ROOT/clones.noindex/`, a private GitNexus home that registers only that clone, arm-specific
   skills, system prompt, MCP config and hooks, a curated environment (own TMPDIR, caches and npm prefix, PATH shims),
   then one headless `claude -p` or `codex exec`. Claude Bash runs in Claude's sandbox and Write/Edit are scoped to the
   run dir; Codex runs with `--sandbox workspace-write`. No-GitNexus arms get no index, an empty GitNexus home, and a
   `gitnexus` that prints "command not found". Hidden oracle files are copied in only after the agent exits. Output:
   `<out_dir>/results.jsonl` (one row per run) and `<out_dir>/runs/<run>/` (stream, patch.diff or answer, hook log).
3. **Grading.** Change tasks (Tracks O, U, P2, hermes fix) are graded of record by `grading/regrade.py`: it applies
   each saved `patch.diff` to a fresh copy of the base, runs the hidden oracle and the regression command, and applies
   a symmetric flaky-test rule (a pytest regression failure counts only if the failed tests also fail when rerun on
   their own, up to 2 reruns, and only when 10 or fewer failed). `regrade_o_final.sh` is the Track O invocation.
   Question tasks write a JSON answer that `score_p1.py` (impact sites, path match within 2 lines, one-to-one),
   `score_p3.py` (route/tool/consumer sets), `score_p4.py` (seeded taint flows and decoys), `score_review.py` (a port
   of upstream's `eval/workflow_bench/review_scoring.py`) and `hermes/score_h_impact.py` score. `build_report.py` runs
   them all, the contamination audits and the spend totals, and writes `report-data/*.json`.
4. **Audits.** `scan_gnx.py` finds every GitNexus CLI call an agent made through its shell and classifies the output
   (LIVE = reached an index estate other than the run's own, STUB = the not-found stub, OK, ERR); LIVE or OK in a
   no-GitNexus arm marks the run contaminated. `scan_writes.py` lists every Claude file-tool write outside the run dir.
   Both need the transcripts, which are not published (see below).

The scorers re-parse `stream.jsonl` (when present) to recompute turns and GitNexus CLI calls. Without the transcripts
they use the values in `results.jsonl`, which were written from the same streams.

## Configuration

Copy `config.example.env` to `config.env` (or set `BENCH_CONFIG`) and fill it in. Python reads it through
`common/benchenv.py` and shell scripts through `isolation/_config.sh`; an already-set environment variable wins.
The main settings:

| Variable | Used for |
| --- | --- |
| `BENCH_ROOT` | State root: `tasks/` (bases), `clones.noindex/` (run clones), `home*/` (GitNexus homes), `refresh-state*/`, `regrade/` |
| `BENCH_ARTIFACTS`, `HERMES_ARTIFACTS`, `AB_ARTIFACTS` | The three studies' data dirs (task files, probes, oracles, run dirs) |
| `GITNEXUS_SRC` | A full clone of abhigyanpatwari/GitNexus (bases, review cases, review labels) |
| `GITNEXUS_PKG`, `NODE_BIN` | gitnexus@1.6.12 package dir and the node that runs it, the hook and the TS ground-truth scripts |
| `CLAUDE_BIN`, `CODEX_BIN`, `UV_BIN` | Agent CLIs and uv |
| `VOYAGE_API_KEY` | Query embeddings (voyage-code-4, 1024 dims). Read only by the shell launchers and `bench-refresh.sh`. |
| `EXTRA_PATH` | PATH entries after the shims in agent and grader environments |
| `SEED_INDEX_*`, `SEED_EMBED_STAMP_DIR` | Seed indexes for the base builders |
| `OWNER_INSTRUCTIONS_FILE`, `OWNER_SKILLS_DIR`, `CODEX_HOME_FOR_RUNS` | Withheld private inputs (below) |

Task files may use `$BENCH_ROOT`, `$TASK_BASE`, `$BENCH_ARTIFACTS`, `$HERMES_ARTIFACTS`, `$HARNESS`, `$GITNEXUS_SRC`,
`$GITNEXUS_PKG`, `$NODE_BIN_DIR`, `$AB_ARTIFACTS` and `$AB_REPOS_ROOT` in any string (paths and commands).
`benchenv.load_tasks` expands exactly these names and leaves every other `$VAR` for the shell. The task files we ran
held absolute local paths in these places; the published task files use the placeholders.

The launchers are the only place the embedding key is used. GitNexus runs under `env -i` with an explicit
environment: the run's home, read-only mode where the arm says so, Voyage embeddings (`GITNEXUS_EMBEDDING_*`) and
`GITNEXUS_VECTOR_MAX_DISTANCE=1.0` (upstream's MCP default of 0.6 dropped most voyage-code-4 matches for plain-English
queries in a probe we ran before the benchmark). Re-indexing commands are refused inside runs.

## Arms (`runner/bench.py`)

All Claude arms run `claude -p --effort medium --permission-mode dontAsk --setting-sources project,local
--strict-mcp-config` with Read, Grep, Glob, Edit, Write, Bash and Skill. MCP arms add the 13 read-only GitNexus tools
(`list_repos, query, context, check, impact, explain, pdg_query, route_map, tool_map, shape_check, api_impact, trace,
detect_changes`), and `rw` arms also add `rename`. Codex arms run `codex exec --sandbox workspace-write --ephemeral`.
Models: Opus = `claude-opus-5-5`, Haiku = `claude-haiku-4-5-20251001`, Sol = `gpt-6.1-sol`.

| Arm | Engine / model / effort | MCP | Skills | Prompt | System prompt / instructions | Hooks |
| --- | --- | --- | --- | --- | --- | --- |
| U_nomcp | Claude Opus, medium | off | Skill tool denied | baseline | none | no |
| U_mcp | Claude Opus, medium | rw | Skill tool denied | baseline | none | no |
| U_direct | Claude Opus, medium | rw | repo's own (as shipped) | work_direct | none | no |
| R_plain | Claude Opus, medium | off | none | review_plain | none | no |
| R_gnx | Claude Opus, medium | rw | upstream | review_gnx | none | no |
| CR0 | Codex Sol, high | off | none | review_plain | NOTE_OFF prepended to the prompt | no |
| CR1 | Codex Sol, high | ro | none | review_plain | none | no |
| S_mcp | Claude Haiku, medium | rw | Skill tool denied | baseline | none | yes (harness smoke only) |
| A0 | Claude Opus, medium | off | none | baseline | instruction file + NOTE_OFF | no |
| A1 | Claude Opus, medium | ro | ours (`OWNER_SKILLS_DIR`) | baseline | instruction file | no |
| A2 | Claude Opus, medium | rw | upstream | baseline | instruction file + upstream AGENTS.md block | yes |
| A3 | Claude Opus, medium | rw | upstream | work_direct | instruction file + upstream AGENTS.md block | yes |
| H0 | Claude Haiku, medium | off | none | baseline | instruction file + NOTE_OFF | no |
| H2 | Claude Haiku, medium | rw | upstream | baseline | instruction file + upstream AGENTS.md block | yes |
| C0 | Codex Sol, medium | off | none | baseline | NOTE_OFF prepended; Codex home's own AGENTS.md | no |
| C1 | Codex Sol, medium | ro | none | baseline | Codex home's own AGENTS.md | no |
| C2 | Codex Sol, medium | rw | upstream (`.agents/skills`) | baseline | upstream AGENTS.md block prepended to the prompt; Codex home's own AGENTS.md | no |
| A1f | Claude Opus, medium | ro | ours | baseline + GNX_FIRST_NOTE | instruction file | no |
| C1f | Codex Sol, medium | ro | none | baseline + GNX_FIRST_NOTE | Codex home's own AGENTS.md | no |
| A1m | Claude Opus, medium | ro | ours | baseline + GNX_MUST_NOTE | instruction file | no |

- "instruction file" = `OWNER_INSTRUCTIONS_FILE`, applied only for tasks with `owner_md: true` (not Track U or the
  review track). "upstream" skills = what `gitnexus analyze` installs from `$GITNEXUS_PKG/skills`. "upstream AGENTS.md
  block" = `runner/upstream-block.md` with the run's alias filled in. Hooks = upstream's Claude hook
  (`hooks/claude/gitnexus-hook.cjs`) on PreToolUse Grep|Glob|Bash and PostToolUse Bash, through `isolation/hook-logger.sh`.
- Prompts are constants in `bench.py`: `BASELINE_PROMPT`, `WORK_DIRECT_PROMPT`, `REVIEW_*` and `HEADLESS_VERIFY` are
  upstream's `eval/workflow_bench/runner.py` prompts, verbatim (the review output path points inside the run dir).
  `NOTE_OFF`, `GNX_FIRST_NOTE` and `GNX_MUST_NOTE` are ours. Question tasks (`kind: qa`) send the task text as is.
- Which arms ran in which track (scored runs per arm, from the run tables): O (12 tasks) = A0, A1, A2, A3, C0, C1, C2,
  H0, H2, 12 each (108); U (4 tasks, each on the standard and the --pdg index) = U_nomcp, U_mcp, U_direct, 8 each scored (24; 4 earlier U_nomcp
  rows are excluded); P1 (10) = A0, A1, A2, C0, C1, C2, H0, H2, 10 each (80); P2 (6) = A0, A1, A2, C0, C2, H0, H2,
  6 each (42); P3 (5) = A0, A2, C0, C2, H0, H2, 5 each (30; one C2 run killed by a Codex capacity error was rerun);
  P4 (1 x 2 trials) = A0, A2, C0, C2, 2 each (8); review (6 cases x 2 trials) = R_plain, R_gnx, CR0, CR1, 12 each
  (48). Total 340. hermes impact (8 targets x 2 trials) = A0, A1f, A1m, C0, C1f, 16 each (80); hermes fix = C0, C1f.

A/B study arms (`ab-ripgrep/run.py`, Opus, medium effort; `codex_run.py`, Sol, medium effort):

| Arm | Setup |
| --- | --- |
| rg | Read/Grep/Glob only, `--setting-sources local`, max 40 turns |
| gnx | rg + GitNexus MCP + a one-paragraph hint naming the repo alias |
| gnxf | gnx + "prefer the gitnexus tools over Grep/Glob" |
| realA / realB / realF | Our real user-level Claude setup (withheld), hooks off, Read/Grep/Glob/Skill/ToolSearch, max 60 turns. realA: no MCP + "no code-graph tools" note; realB: GitNexus MCP; realF: MCP + "use the GitNexus tools first" |
| augH0 / augH2 / augHk | No user settings; instruction file + note as appended system prompt. augH0: no GitNexus; augH2: MCP + upstream hooks; augHk: hooks only |
| cxA / cxB | Codex Sol, medium effort, read-only sandbox, our Codex home. cxA: GitNexus MCP disabled + NOTE_OFF; cxB: MCP on |

`augH2` is defined in `ab-ripgrep/run.py` but no `augH2` runs are in the data.

Blind grading: `build_judge.py` + `run_judges.sh` (Codex Sol at high effort grades the Claude real* answers), and
`judge2.py` (Opus grades the cx* answers; Sol grades the aug* answers). Labels are shuffled deterministically and the
mapping is kept out of the prompt.

## Withheld, and why

- **Our global agent instruction file** (`OWNER_INSTRUCTIONS_FILE`, about 45 KB). It names private repositories,
  internal hosts and people. `runner/owner-instructions.PLACEHOLDER.md` records its sha256 and describes the part that
  matters for the results: it told agents to prefer GitNexus over broad grep on indexed repos.
- **Our gitnexus-* skills** (`OWNER_SKILLS_DIR`, arms A1, A1f, A1m): local versions of nine upstream skills plus one
  local skill about our index setup. They have since been removed.
- **Our Codex home** (`CODEX_HOME_FOR_RUNS`) and our **user-level Claude settings** (A/B real* arms).
- **Transcripts** (`stream.jsonl`), the per-run `sysprompt.md`/`cmd.json`/`stderr.log`, the agents' free-text final
  messages, and the raw grader logs. They contain local paths and private context that agents read during runs. The
  scorers and `build_report.py` still run on the published results and answers. The audits (`scan_gnx.py`,
  `scan_writes.py`) and `ground-truth/p2/direct/apply_and_check.py` need the transcripts, so their published outputs
  (in the data folders) cannot be regenerated from this bundle.
- **Our live index estate.** The setup scripts copied our everyday indexes as seeds and `scan_gnx.py` matched their
  local paths. Both are now configuration (`SEED_INDEX_*`, `LIVE_INDEX_MARKERS`).
- **`report-template.html`** (the report's prose template) is not part of the harness. Without it,
  `build_report.py` writes `report-data/*.json` and `metrics.json` only.

## Rebuilding bases

All bases come from public commits. In order:

1. `setup/setup_track_u.sh`: the GitNexus base (`tasks/gnxu/gnxu-base`, c4ecf398 without `eval/workflow_bench`),
   used by Tracks U, P1, P2 and P3.
2. `setup/setup_pdg_variant.sh tasks/gnxu/gnxu-base gnxu-pdg`: the same base analyzed with `--pdg`.
3. `setup/setup_p4_base.sh` and `setup/setup_p4_named.sh`: the P4 taint bases. They fold the seeded module
   `$BENCH_ARTIFACTS/probes/p4/repo-tools.ts` (or `repo-tools-named.ts`) into the snapshot commit and edit `api.ts`
   inline.
4. `setup/setup_review_all.sh`: the five review bases (upstream review cases, `--pdg`).
5. Track O: `mining/validate.py <repo> <id> <pr>` per mined PR (lcm-x and WorldOS, both public), then
   `mining/build_tasks.py`, `mining/check_clean.py`, and `setup/setup_o_chain.sh <id>...` per repo.
6. hermes-agent: `hermes/mining/validate_h.py` per task, `hermes/mining/build_tasks_h.py`, then
   `hermes/build_h_bases.sh`. The impact base (`tasks/h/impact`) is hermes-agent at d62fbea7. Its answer key comes
   from `hermes/impact/gt.py` (pyright 1.1.414 across Darwin/Linux/Windows), `refs.py` + `lsp_def.py` (completeness
   check), `build_gt.py` (with the manual verdicts in `adjudication.json`), and `verify/jedi_refs.py` (an independent
   check with jedi).

Answer-key generators for the GitNexus probes run against the base checkout without GitNexus: `ground-truth/p1/gt.mjs`
(TypeScript compiler; add a required parameter in memory and record the new type errors), `p2/rename_gt_v2.mjs gt`
(TypeScript's rename engine), and `p3/gt.mjs` (AST and language service).

## Changes from the code we ran

- Paths, binaries and the embedding key come from `config.env` instead of constants and the macOS keychain. Task
  files are read through `benchenv.load_tasks` (placeholder expansion).
- The four read-only launchers that differed only in `GN_HOME` are generated from one template. `bench-refresh.sh`
  evaluates the launcher's pin lines instead of reading them with `sed`, because the pins now reference config
  variables.
- `run.cjs` gets the launcher path filled in when `bench.py` copies it into a run (it was a hardcoded path), and the
  PATH shims find their launcher relative to themselves.
- `ab-ripgrep/run.py` generates the MCP config and the aug-sysprompt files (instruction file + the verbatim notes)
  instead of reading `mcp-gitnexus.json` and the three `aug-sysprompt-*.md` files.
- `hermes/mining/bin/uv` is a forwarding script (it was a symlink to our uv).
- `build_report.py` reads data from `$BENCH_ARTIFACTS`/`$HERMES_ARTIFACTS` and its scorers from this harness. Its
  review-track list named `runs-review-f`, which was never created and was always skipped; it is removed.
- `scan_gnx.py`'s LIVE markers that named our local index directories moved to `LIVE_INDEX_MARKERS`.
- Comments that referred to our internal tooling were reworded. No prompt, arm, scoring rule or threshold changed.

## Checks

Every `.py` here passes `python3 -m py_compile`, every `.sh` passes `bash -n`, and the `.mjs`/`.cjs` files pass
`node --check`. `report.py` (O, U, P2), `score_p1.py`, `score_p3.py`, `score_p4.py`, `score_review.py` and
`hermes/score_h_impact.py` were rerun from this harness on our original run directories, and their output matched the
published `report-data/{O,U,P2,P1,P3,P4,RV,HI}.json` exactly. P1, O and the review track also matched when rerun on a
copy holding only `results.jsonl`, `regrade.jsonl` and the answer files (no transcripts), with task files rewritten to
use `$BENCH_ARTIFACTS`. The launchers, shims, config loader and `bench-refresh.sh` pin evaluation were exercised with a
stub `node`. No agent runs or index builds were run with the published copy.
