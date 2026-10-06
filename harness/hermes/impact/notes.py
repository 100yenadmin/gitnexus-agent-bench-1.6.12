#!/usr/bin/env python3
"""Write adjudication-notes.md: per symbol, the completeness-check tallies and every manual verdict."""
import json
import os as _os, sys as _sys
_HARNESS = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
_sys.path[:0] = [_os.path.join(_HARNESS, "runner"), _os.path.join(_HARNESS, "common")]
import benchenv  # noqa: E402
A = _os.path.join(benchenv.need('HERMES_ARTIFACTS'), 'impact')
summ = json.load(open(f'{A}/gt-summary.json')); adj = json.load(open(f'{A}/adjudication.json'))
raw = {f"{g['cls'] + '.' if g['cls'] else ''}{g['name']}": g for g in json.load(open(f'{A}/gt-final-raw.json'))}
L = ['# Hermes impact track: completeness check and adjudication', '',
     'Reference classes (refs.py + lsp_def.py, every NAME token / alias / string / comment equal to the name in the 2383 in-scope files):',
     'gt = on a pyright site line; def = a declaration of any same-named symbol; import; comment; string (prose) / string-exact (whole literal == name, read);',
     'res-other = pyright go-to-definition resolves to a different declaration; res-skip-attr = `x.name` to a module function in a file that never names its module;',
     'res-unresolved / res-TARGET = read by hand (verdicts below).', '']
for s in summ:
    g = raw[s['target']]
    plat = [f"{x['file']}:{x['line']} ({'/'.join(x['platforms'])})" for x in g['sites'] if len(x['platforms']) < 3]
    L.append(f"## {s['target']} ({g['file']}:{g['line']}) - {'SELECTED' if s['selected'] else 'spare'}")
    L.append(f"- role {s['role']}; probe {s['probe']}; sites {s['pyright'] + s['adjudicated']} = {s['pyright']} pyright + {s['adjudicated']} adjudicated "
             f"(share {s['share']:.0%}, limit 20%); {s['files']} files")
    L.append(f"- platform-only pyright sites: {', '.join(plat) if plat else 'none'}")
    L.append(f"- reference tallies: {', '.join(f'{k} {v}' for k, v in sorted(s['refs'].items()))}")
    for key, (v, note) in sorted(adj.get(s['target'], {}).items()):
        L.append(f"  - `{key}` **{v}**: {note}")
    L.append('')
open(f'{A}/adjudication-notes.md', 'w').write('\n'.join(L) + '\n')
print(len(L), 'lines')
