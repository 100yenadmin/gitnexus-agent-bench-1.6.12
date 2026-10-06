# Placeholder: withheld instruction file

This file stands in for a private file that is not published.

In the benchmark, arms whose system-prompt source is `owner`, `owner_off` or `owner_block` (A0, A1, A2, A3, H0, H2,
A1f, A1m in `runner/bench.py`; `owner_md` defaults to true, and the published task files mark the same tasks with
`user_instruction_file_on_claude_arms: true`) appended our own global agent instruction file to the
Claude system prompt (`--append-system-prompt-file`). The A/B study's `aug*` arms (`ab-ripgrep/run.py`) appended the
same file, followed by a one-line session note. It is the general-purpose instruction file we used across all projects at the time of the runs (2026-10-05/06).
Most of it is unrelated to code navigation, but it included guidance to prefer GitNexus over grep and whole-file reads
on indexed repositories, so the `owner*` arms ran with a standing "prefer GitNexus" instruction. The file is private
and withheld.

Identity of the withheld file (so the runs can be matched to it):

| File | Bytes | sha256 |
| --- | --- | --- |
| global instruction file (used by every `owner*` arm run; all 241 per-run copies start with it) | 45463 | `198dbb4919b703c7edce100d6aeeda90b4c11f8d10cc14d4e8f5a94b458a7a05` |
| A/B `aug-sysprompt-H2.md` (the same file, no note) | 45463 | `198dbb4919b703c7edce100d6aeeda90b4c11f8d10cc14d4e8f5a94b458a7a05` |
| A/B `aug-sysprompt-H0.md` (file + "no code-graph tools" note) | 45573 | `31087a34f66d420f9bf66c76148f42eb8d4b19f79578ebf2f02bb3612c0a5c28` |
| A/B `aug-sysprompt-Hk.md` (file + "context may be attached to searches" note) | 45611 | `a5f4ae1e393ed7a25062e03efd68012085dd3e75472728148a2a80a090464d63` |

The two notes are reproduced verbatim in `ab-ripgrep/run.py` (`AUG_NOTE`). The A0/H0 arms append `NOTE_OFF` and the
A2/A3/H2 arms append upstream's AGENTS.md block (`runner/upstream-block.md`) after the file; both are in
`runner/bench.py`.

To rerun: set `OWNER_INSTRUCTIONS_FILE` to your own instruction file (or leave this placeholder, which then becomes the
appended text). Results will differ from ours to the extent the instructions steer tool choice.

Related withheld inputs:

- `OWNER_SKILLS_DIR` (arms A1, A1f, A1m): at run time this held ten `gitnexus-*` skills: nine with upstream skill names
  (cli, debugging, exploring, guide, impact-analysis, pdg-query, refactoring, review, taint-analysis), in our local
  versions, and one local skill. They have since been removed and are not published.
- `CODEX_HOME_FOR_RUNS` (Codex arms C0-C2, C1f, CR0, CR1, and the A/B cx* arms): runs used our global Codex home,
  with its own global AGENTS.md, skills and memories.
- The A/B `real*` arms loaded our user-level Claude settings (global instructions, skills, plugins).
