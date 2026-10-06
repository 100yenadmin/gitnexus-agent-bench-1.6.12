# A/B: GitNexus vs ripgrep plus reading (public subset)

This directory holds the public part of an earlier A/B, run on 2026-10-05. It tested GitNexus 1.6.12 as a code-navigation layer for coding agents, against agents that only search with grep/ripgrep and read files.

The full A/B had 163 agent runs on 16 repositories. Three of those repositories are private, so every task, run and score on them is left out here. This subset has **137 runs on 13 public repositories**. All 70 blind-graded answers are included, because every graded question was on a public repository.

All runs were read-only question answering. No run edited code, so there are no patches.

## Setup

- **GitNexus:** the official npm package `gitnexus@1.6.12`, byte-identical to the published tarball. Every repository was indexed with embeddings (`voyage-code-4`, 1024 dimensions).
- **GitNexus MCP server:** started with `gitnexus mcp`, read-only, against a single index home. The environment set `GITNEXUS_VECTOR_MAX_DISTANCE=1.0`, because the default of 0.6 dropped most `voyage-code-4` matches for plain-English queries.
- **Claude arms:** headless `claude -p` (Claude Code 2.1.286) running `claude-opus-5-5` at `--effort medium`, with `--output-format stream-json`, `--strict-mcp-config` and no session persistence.
- **Codex arms:** `codex exec` (Codex CLI 0.160.0) running `gpt-6.1-sol` with `model_reasoning_effort=medium`, `--sandbox read-only` and `--ephemeral`.
- **Working directory:** each repository's checkout at the commit listed in `tasks.public.json` (`commit_sha`). The GitNexus index was built at that same commit.
- **Machine:** macOS.

## Arms

| Arm | Engine | GitNexus | Our instruction file or global config | Tasks |
|---|---|---|---|---|
| `rg` | Claude | none; tools `Read,Grep,Glob` | no (local settings only) | find, callers, impact (n=1) |
| `gnx` | Claude | MCP server plus a neutral hint (below) | no | same |
| `gnxf` | Claude | MCP server plus the hint plus "prefer the gitnexus tools" (below) | no | same |
| `realA` | Claude | none; told it is unavailable | **yes**: our instruction file, skills and plugins | broad (5 questions × 2 trials) |
| `realB` | Claude | MCP server, with only the standing guidance from the instruction file | **yes** | broad |
| `realF` | Claude | MCP server plus "use the GitNexus code-graph tools first" | **yes** | broad |
| `augH0` | Claude | none; told it is unavailable | **yes**: instruction file appended as a system prompt | broad plus impact (× 2 trials) |
| `augHk` | Claude | upstream's grep-enrichment hook only (`hooks/claude/gitnexus-hook.cjs`), no MCP server | **yes** | broad plus impact |
| `cxA` | Codex | GitNexus MCP server disabled; told it is unavailable | **yes**: our global Codex configuration | broad plus impact (× 2 trials) |
| `cxB` | Codex | GitNexus MCP server enabled | **yes** | broad plus impact |

**Disclosure.** The `real*`, `aug*` and `cx*` arms carried our private Claude instruction file or our global Codex configuration. At the time, both told agents to prefer GitNexus:

- The Claude file told agents to prefer GitNexus over grep and whole-file reads on indexed repositories.
- The Codex configuration told agents to use GitNexus first.

Neither file is published. The `rg`, `gnx` and `gnxf` arms used no user-level settings, so they carried neither.

Settings for the `real*` arms:

- Claude's user-level settings, skills and plugins were loaded, and all hooks were disabled.
- MCP tool schemas were deferred (`ENABLE_TOOL_SEARCH=true`), as in interactive sessions.
- Subagents were not available. The tools were `Read,Grep,Glob,Skill,ToolSearch`.

Settings for the `aug*` arms:

- No user-level settings were loaded. The instruction file was appended as a system prompt.
- `augHk` had the upstream hook on `PreToolUse` (`Grep|Glob|Bash`) and `PostToolUse` (`Bash`), wrapped by a logger.
- There was no MCP server in the session, so the session could not lock the graph database.

The exact session notes the harness added:

- `gnx`: "A GitNexus code-graph index of this repository is available through the `gitnexus` MCP tools: natural-language and keyword code search (`query`), a symbol's callers/callees (`context`), and change impact (`impact`). Pass repo="<alias>" on every gitnexus call."
- `gnxf`: the `gnx` hint, then " Prefer the gitnexus tools over Grep/Glob: start with gitnexus (query to find code by description, context for callers and callees), then use Read/Grep only to confirm or fill gaps."
- `realA`: "Note for this session: no code-graph (GitNexus) tools are available here; answer using Read, Grep and Glob."
- `realF`: "For this question, use the GitNexus code-graph tools first (query to find the relevant code, context for callers and callees, impact for blast radius) with repo="<alias>", then use Read/Grep only to confirm details."
- `augH0`: the instruction file ends with "Note for this session: no code-graph (GitNexus) tools are available here; answer using Read, Grep and Glob."
- `augHk`: the instruction file ends with "Note for this session: GitNexus code-graph context may be attached automatically to your Grep/Glob searches; there are no GitNexus tools to call."
- `cxA`: the prompt is prefixed with "Note for this session: GitNexus is not available here; use normal search (rg/git grep) and file reads."

## Tasks

`tasks.public.json` lists 22 public tasks. The prompts are included verbatim.

- **13 find tasks** (P01–P03, P05, P06, P08–P12, P14–P16): find a function from a paraphrased description and answer up to 3 `path :: name` candidates. The scorer matched the target name only. P10 is ambiguous, because two functions fit the description.
- **2 callers tasks** (C01, C02): give the definition plus every direct non-test call site. The answer keys were hand-verified.
- **2 two-hop impact tasks** (I01, I03): list the hop-1 and hop-2 non-test functions affected by a signature change. The answer keys were hand-verified. I01 has a same-named Go function as a trap. I03 has a 12-function fan-out.
- **5 broad questions** (W1–W3 on WorldOS, H1 on hermes-agent, L1 on lossless-claw): open-ended code-understanding questions with a 400-word limit, blind-graded.

The 13 repositories are all public on GitHub (checked with `gh api repos/OWNER/NAME`). Nine of them are forks, and `fork_of` gives the parent. The commit shown is the one the index and checkout were at during the runs. It was recovered from the index registry snapshot and refresh log, and checked to exist on GitHub. The WorldOS checkout was sparse: binary, media, `.jsonl`, `.db` and `.sqlite` files were excluded.

## What was dropped, and why

Three of the 16 repositories in the original A/B are private. Their code, prompts, targets, answer keys and answers cannot be published.

| | Original | Dropped | Public subset |
|---|---|---|---|
| Tasks | 23 narrow + 5 broad | 6 (P04, P07, P13, C03, C04, I02) | 17 narrow + 5 broad |
| Narrow runs (`rg`/`gnx`/`gnxf`) | 69 | 18 | 51 |
| Real-setup broad runs (`realA`/`realB`/`realF`) | 30 | 0 | 30 |
| Codex runs (`cxA`/`cxB`) | 32 | 4 (I02 × 2 trials × 2 arms) | 28 |
| Hooks-only runs (`augH0`/`augHk`) | 32 | 4 (I02 × 2 trials × 2 arms) | 28 |
| **Runs** | **163** | **26** | **137** |
| Blind-graded answers | 70 | 0 | 70 |
| Hook calls logged (`augHk`) | 96 | 8 | 88 |

`runs.public.jsonl` also holds 14 rows with `excluded: true`. These are Codex `cxA` launch failures: the harness passed a bad flag, so codex exited with rc=2 after 0 s and zero tokens. Each cell was rerun after the fix. Two more such failures were on the dropped task. Pilot runs are not part of the 163 and are not included.

## Files

- **`tasks.public.json`:** tasks, public repo slug, fork parent, GitNexus alias, target, commit SHA and prompt.
- **`ground-truth.public.json`:** the answer keys for callers and impact, the find targets with their definition sites, and the scoring rules. The definition sites were located with `git grep` at the run commit after the runs; the scorer used names only.
- **`runs.public.jsonl`:** one row per run in the bundle's shared per-run schema: 137 scored runs plus 14 excluded launch failures. No answer text is included. Field notes:
  - `cost_usd`: for Claude, the CLI's `total_cost_usd`. For Codex, it is notional: tokens × list price ($2/M uncached input, $0.10/M cached input, $10/M output).
  - `tokens.in`: uncached input tokens. For Codex, `cache_read` is the cached input and `cache_create` is null.
  - `turns`: null for Codex.
  - `tool_calls`: Claude tool-use names; for Codex, the `command_execution` and `mcp_tool_call` item counts.
  - `gitnexus_calls`: GitNexus tool names.
  - `hooks`: for `augHk`, hook calls, how many injected context, and lock fallbacks (all 0). They were attributed to runs by session id.
  - `outcome`: the grade of record. Find tasks report `top1`/`in3`. Callers and impact report `recall`, `precision`, `tp`, `gt` and `exact`. Broad questions report the blind judge's `judge_correctness` and `judge_completeness`.
- **`scores.public.json`:** per-arm aggregates on the public subset, cost comparisons against each baseline arm, per-question multi-hop costs, and run counts before and after the drop.
- **`blind-grades.public.json`:** per question, packet, label, arm and trial: the correctness and completeness grades and which model graded them. Judge prompts, answer text and the judges' free-text error notes are not included.
  - `realA/B/F` answers were graded by `gpt-6.1-sol` (high).
  - `cxA/cxB` answers were graded by `claude-opus-5-5` (high). Sentences mentioning GitNexus were removed from these answers before grading.
  - `augH0/augHk` answers were graded by `gpt-6.1-sol` (high).
  - No model graded its own answers.

## Results on the public subset

Accuracy:

| Kind | Arm comparison | Accuracy |
|---|---|---|
| Find (13) | rg / gnx / gnxf | top-1 12/13, 13/13, 12/13 (the only miss is the ambiguous P10) |
| Callers (2) | rg / gnx / gnxf | recall 8/8 and precision 8/8 in every arm |
| Impact, Opus (2) | rg / gnx / gnxf | recall 18/18 in every arm; precision 17/17, 18/18, 18/18 |
| Impact, Codex (2 × 2) | cxA / cxB | recall 36/36 and precision 36/36 in both arms |
| Impact, hooks (2 × 2) | augH0 / augHk | recall 34/36 vs 36/36; precision 32/32 vs 34/34 |
| Broad, blind grade (5 × 2) | realA / realB / realF | correctness 8.3 / 8.2 / 7.6; completeness 7.4 / 7.7 / 7.2 |
| Broad, blind grade | cxA / cxB | correctness 9.1 / 8.6; completeness 7.8 / 8.2 |
| Broad, blind grade | augH0 / augHk | correctness 8.1 / 8.2; completeness 7.6 / 7.4 |

Mean cost per run, GitNexus arm vs its baseline (from `scores.public.json`):

| Kind | Comparison | Change | Runs that called GitNexus tools |
|---|---|---|---|
| Find | gnx vs rg | +25.7% | 1/13 |
| Find | gnxf vs rg | +23.6% | 5/13 |
| Callers | gnx vs rg | +56.6% | 0/2 |
| Callers | gnxf vs rg | −3.3% | 0/2 |
| Broad | realB vs realA | +7.6% | 1/10 |
| Broad | realF vs realA | +21.0% | 10/10 |
| Broad | cxB vs cxA | +40.0% | 10/10 |
| Broad | augHk vs augH0 (hooks only, no tool calls) | −6.8% | 0/10 |
| Impact | gnx vs rg | −31.9% | 1/2 |
| Impact | gnxf vs rg | −25.4% | 2/2 |
| Impact | cxB vs cxA | +47.1% | 4/4 |
| Impact | augHk vs augH0 | +0.2% | 0/4 |

Multi-hop impact with Opus, n=1 per cell:

| Task | gnx vs rg | gnxf vs rg |
|---|---|---|
| I01 | −21.4% (3 `context` calls) | −36.5% (2 `impact` calls) |
| I03 | −42.5% (GitNexus available but not called) | −14.2% (1 `impact` call) |

### Do the published A/B statements hold on this subset?

**Accuracy matched between GitNexus and ripgrep plus reading.** This holds. The narrow tasks are tied apart from the ambiguous P10. Blind grades show no gain from GitNexus. The blind grades are identical to the full A/B, because every graded question is public.

**On find-and-understand tasks, the GitNexus setups cost 20–60% more on average.** This holds for the setups whose agents actually called GitNexus tools: find +24% to +26%, `realF` +21%, and Codex `cxB` +40%. The `gnx` callers cell, at +57%, also falls in this range, but none of its runs called a GitNexus tool, so the extra cost there came only from having the MCP server attached. Three setups fall outside the range:

- `realB` (+8%): GitNexus was used in only 1 of 10 runs.
- `gnxf` callers (−3%, n=2): no GitNexus calls.
- Hooks only (`augHk`, −7%): no tool calls are added.

The full A/B gave find +29% and `gnxf` callers +13%. With the private tasks removed, these are slightly lower.

**Opus was cheaper on 2 of 3 multi-hop questions, at n=1.** The two cheaper questions, I01 and I03, are both public and both in this subset, at −14% to −43%. The third question was on a private repository, so it is not here. On the public data alone, the statement reads "cheaper on 2 of 2". The full 2-of-3 figure can only be checked against the private task.

One caveat: the −42.5% figure (I03, `gnx`) comes from a run that had GitNexus available but never called it. If only runs that called GitNexus are counted, the range is −14% to −37%.

## Caveats

- The narrow tasks have one run per cell. In the broad questions, the same question in the same arm varied by up to 2.5× in cost between trials, so differences of ±30% at these sample sizes can be noise.
- Codex costs are notional list-price estimates. Claude costs come from the CLI and include cache pricing.
- In `claude -p`, the `gnx`/`gnxf` sessions load GitNexus's MCP tool schemas into context up front. Much of the find-task overhead is that context. Interactive sessions and the `real*` arms defer the schemas.
- The find-task descriptions were written by agents that had read the code. All tasks have small fan-out. Deep (3+ hop) impact, cross-repo work and weaker models were not tested.
- Transcripts, final answers, judge prompts, our instruction file and global Codex configuration, and the harness's local wrappers are not included. Transcripts and answers can reproduce private context from our instruction file.
