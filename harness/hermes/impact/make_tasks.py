#!/usr/bin/env python3
"""Emit tasks-h-impact.json (tasks-p1.json schema, P1 question wording adapted to Python/pyright) from impact/gt.json."""
import json
import os as _os, sys as _sys
_HARNESS = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
_sys.path[:0] = [_os.path.join(_HARNESS, "runner"), _os.path.join(_HARNESS, "common")]
import benchenv  # noqa: E402
D = benchenv.need('HERMES_ARTIFACTS')
# Written with placeholders (expanded by benchenv.load_tasks); the original wrote absolute local paths.
BASE = '$BENCH_ROOT/tasks/h/impact'
TEST_RULE = ('test code (any file under a `tests/` or `test/` directory, or named `test_*.py`, `*_test.py` or '
             '`conftest.py`)')
out = []
for g in json.load(open(f'{D}/impact/gt.json')):
    sym = f"{g['cls']}.{g['name']}" if g['cls'] else g['name']
    kind = 'method' if g['cls'] else 'function'
    task = (f"Impact check before a change. We are about to add a new required parameter to `{sym}`, the {kind} declared at "
            f"`{g['file']}:{g['line']}`. Before anyone edits code, list every location in this repository's Python code that "
            f"would have to be updated so the project still type-checks (pyright) and runs after that change: each place that "
            f"calls this exact {kind}, or otherwise uses it in a way that would break (for example passing it, or an object "
            f"that carries it, where a compatible signature is required). Do not include other functions or methods that only "
            f"share its name, the declaration itself, import/export statements, comments, strings, or {TEST_RULE}. "
            f"Do not modify any repository files.\n\n"
            f"Write `.bench-review/answer.json` as UTF-8 JSON with exactly this shape:\n"
            f"{{\"locations\": [{{\"path\": \"<repo-relative path>.py\", \"line\": <1-based line of the call or use>}}]}}\n"
            f"One entry per affected line. Then reply with a one-line summary.")
    out.append(dict(id=g['id'], track='H-IMPACT', **{'class': 'impact'}, kind='qa', base=BASE, owner_md=True,
                    path_prefix=['$NODE_BIN_DIR'], task=task, gt='$HERMES_ARTIFACTS/impact/gt.json'))
json.dump(out, open(f'{D}/tasks-h-impact.json', 'w'), indent=1)
print(len(out), 'tasks')
