#!/usr/bin/env python3
"""Assemble impact/gt.json (P1 gt.json format + `id`, provenance) from the 3-platform pyright GT (gt-final-raw.json),
the residual-reference classification (defs-final.jsonl from refs.py + lsp_def.py) and the manual verdicts in
adjudication.json. A residual is a textual reference that is not a declaration, import, comment/string or pyright site.
Mechanical verdicts: res-other = pyright's go-to-definition resolves it to a different declaration (not this symbol);
res-skip-attr = attribute access `x.name` to a module-level function target in a file that never mentions the target's
module (cannot be that module). res-unresolved / res-TARGET residuals and every string literal whose whole value is the name (`string-exact`) need a manual
verdict in adjudication.json: {"<target>": {"<file>:<line>": ["call"|"not", "note"]}}. Sites with verdict "call" are
added as source=adjudicated. A target is dropped when adjudicated sites > 20% of its sites. adjudication.json["_select"] lists the ids written to gt.json
(the rest stay in gt-summary.json as spares).
Usage: build_gt.py"""
import json, collections, sys
import os as _os, sys as _sys
_HARNESS = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
_sys.path[:0] = [_os.path.join(_HARNESS, "runner"), _os.path.join(_HARNESS, "common")]
import benchenv  # noqa: E402
A = _os.path.join(benchenv.need('HERMES_ARTIFACTS'), 'impact')
raw = json.load(open(f'{A}/gt-final-raw.json'))
adj = json.load(open(f'{A}/adjudication.json'))
rows = [json.loads(l) for l in open(f'{A}/defs-final.jsonl')]
need = collections.defaultdict(dict); stats = collections.defaultdict(collections.Counter)
for r in rows:
    k = r['cls']
    if k == 'residual':
        d = r.get('defs') or []
        k = 'res-TARGET' if [r['tfile'], r['tline']] in d else ('res-other' if d else 'res-unresolved')
    stats[r['target']][k] += 1
    if k in ('res-TARGET', 'res-unresolved', 'string-exact'):
        need[r['target']][f"{r['file']}:{r['line']}"] = r['text'].strip()[:160]
out, summary, missing = [], [], []
for g in raw:
    tgt = f"{g['cls'] + '.' if g['cls'] else ''}{g['name']}"
    gid = 'h-impact-' + (f"{g['cls']}.{g['name']}" if g['cls'] else g['name'])
    sites = [dict(file=s['file'], line=s['line'], code=s['code'], source='pyright', platforms=s['platforms']) for s in g['sites']]
    have = {(s['file'], s['line']) for s in sites}
    verdicts = adj.get(tgt, {})
    selected = gid in adj.get('_select', [gid])
    for key in need[tgt]:
        if key not in verdicts: missing.append((tgt, key, need[tgt][key]))
    n_adj = 0
    for key, (v, note) in sorted(verdicts.items()):
        f, l = key.rsplit(':', 1)
        if v == 'call' and (f, int(l)) not in have:
            sites.append(dict(file=f, line=int(l), code='ADJ', source='adjudicated', note=note)); n_adj += 1
    sites.sort(key=lambda s: (s['file'], s['line']))
    share = n_adj / len(sites) if sites else 0
    keep = share <= 0.2 and 5 <= len(sites) <= 40
    summary.append(dict(id=gid, target=tgt, role=g.get('role'), probe=g['probe'], pyright=len(sites) - n_adj, adjudicated=n_adj,
                        share=round(share, 3), selected=selected, files=len({s['file'] for s in sites}), keep=keep, refs=dict(stats[tgt])))
    if keep and gid in adj.get('_select', [gid]):
        out.append(dict(id=gid, name=g['name'], cls=g['cls'], file=g['file'], line=g['line'], probe=g['probe'], sites=sites))
for s in summary: print(json.dumps(s))
if missing:
    print(f'\n{len(missing)} residuals lack a verdict:', file=sys.stderr)
    for m in missing: print('  ', m, file=sys.stderr)
    sys.exit(1)
json.dump(out, open(f'{A}/gt.json', 'w'), indent=1)
json.dump(summary, open(f'{A}/gt-summary.json', 'w'), indent=1)
print(f'gt.json: {len(out)} targets')
