# License notes

## Our files: MIT

Except for the files listed under [Upstream files](#upstream-files), everything in this bundle is ours and is released
under the MIT license below. That covers:

- the harness code;
- the task definitions and bug-report statements we wrote;
- the answer keys and their generators;
- the per-run summaries, grades and scores;
- the documentation.

The structured agent answers and review outputs are also covered. Where an answer quotes a short piece of the
repository it was about, that piece keeps the repository's license.

```
MIT License

Copyright (c) 2026 the contributors to this bundle

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Upstream files

These files are copied from, or derived from, public repositories. They keep those repositories' licenses. The
license shown is the one in each repository at the commits used. The SPDX id is the one GitHub reports
(`gh api repos/<repo> -q .license.spdx_id`).

### abhigyanpatwari/GitNexus at `c4ecf398`: PolyForm Noncommercial License 1.0.0

GitHub reports the SPDX id as `NOASSERTION`. The LICENSE file is the PolyForm Noncommercial License 1.0.0,
<https://polyformproject.org/licenses/noncommercial/1.0.0>.

> Required Notice: Copyright Abhigyan Patwari (https://github.com/abhigyanpatwari/GitNexus)

Files:

- **Track 2 oracles.** `tracks/02-workflow-bench/oracles/`: upstream `eval/workflow_bench` hidden oracles and the
  vitest config (three of them repaired), plus `upstream-orig.diff`.
- **Patches against GitNexus source.** Their context lines are GitNexus code:
  - `tracks/02-workflow-bench/patches/`
  - `tracks/04-rename/patches/`
  - the `api.ts` hunks in `tracks/06-taint/seed.patch` and `seed-named.patch`. The seeded `repo-tools.ts` module in
    those patches is ours (MIT).
- **GitNexus tool output on GitNexus source.** It can quote GitNexus code and identifiers:
  - `tracks/04-rename/tool-edit-lists/`
  - `tracks/05-structural/tool-output/`
  - `tracks/06-taint/tool-output/`
- **Harness files.**
  - `harness/runner/upstream-block.md`: the AGENTS.md/CLAUDE.md block template that `gitnexus analyze` writes.
  - `harness/runner/bench.py`: the prompt constants copied verbatim from upstream's
    `eval/workflow_bench/runner.py` (`BASELINE_PROMPT`, `WORK_DIRECT_PROMPT`, `HEADLESS_VERIFY`, `REVIEW_*`). The
    rest of the file is ours.
  - `harness/grading/score_review.py`: a port of upstream's `eval/workflow_bench/review_scoring.py`.

`tracks/07-review/tasks.json` names the upstream review labels and patches by path and sha256. The files themselves
are not copied.

### electricsheephq/lcm-x: MIT

- `tracks/01-fixes/oracle/lcmx-*/`: hidden tests for 7 tasks, 8 files.
- The `lcmx-*` patches: `tracks/01-fixes/patches/` (63) and `tracks/01-fixes/controls/` (14).

### electricsheephq/WorldOS: WorldOS Source-Available Commercial EULA v1.0

GitHub reports the SPDX id as `NOASSERTION`. The file's own identifier is
`LicenseRef-WorldOS-Source-Available-Commercial-1.0`. It is a source-available license, not an OSI open-source
license. See the repository's `LICENSE`. These files are included with the permission of the WorldOS copyright holder, for
reproducing this benchmark only; they remain under that license.

- `tracks/01-fixes/oracle/worldos-*/`: hidden tests for 5 tasks, 8 files.
- The `worldos-*` patches: `tracks/01-fixes/patches/` (45) and `tracks/01-fixes/controls/` (10).

### NousResearch/hermes-agent: MIT

- `hermes-agent/fix-sol/oracle/`: hidden tests for 8 tasks, 11 files.
- `hermes-agent/fix-sol/patches/`: 32 diffs against hermes-agent.
- `hermes-agent/impact/references/`: quoted hermes-agent source lines. Two contributor email addresses are redacted.
- `hermes-agent/impact/pyright/` and `hermes-agent/impact/verify-jedi/`: pyright and jedi output about hermes-agent
  code, including the probe diffs.

### Repositories in the A/B

`ab-ripgrep/` holds only repository names, commit SHAs, file paths, symbol names, line numbers and our own task
prompts for the 13 public repositories. No source text from them is copied.

## Test-fixture strings

Some copied upstream test files contain fake credentials and placeholder identifiers that secret scanners may flag. For
example, `hermes-agent/fix-sol/oracle/hermes-c01/tests/agent/test_anthropic_adapter.py` contains fixture strings shaped
like API keys. These are upstream test data, not real secrets, and the files are kept unchanged because they are
answer keys.
