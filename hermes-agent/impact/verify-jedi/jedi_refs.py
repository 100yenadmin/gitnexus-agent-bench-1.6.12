#!/usr/bin/env python3
"""Independent verifier: token-scan every scope file for the target name and any import aliases of it,
then classify each occurrence with jedi goto(follow_imports=True). Output JSONL of occurrences."""
import io, json, os, re, sys, tokenize
import jedi

B = sys.argv[1]; scope = [l.strip() for l in open(sys.argv[2]) if l.strip()]
targets = json.loads(sys.argv[3])   # list of {name, file, line, cls}
out = open(sys.argv[4], 'w')
try:
    env = jedi.create_environment(os.path.join(B, '.venv'), safe=False)
    env._get_subprocess()
except Exception as e:
    print('env fallback', e, file=sys.stderr); env = None
proj = jedi.Project(B, environment_path=None)
src = {}
for f in scope:
    try: src[f] = open(os.path.join(B, f), encoding='utf-8').read()
    except Exception: src[f] = ''

def name_tokens(code, names):
    res = []
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(code).readline))
    except Exception as e:
        return None
    for i, t in enumerate(toks):
        if t.type == tokenize.NAME and t.string in names:
            prev = toks[i-1].string if i else ''
            nxt = toks[i+1].string if i+1 < len(toks) else ''
            res.append((t.start[0], t.start[1], t.string, prev, nxt))
    return res

for tg in targets:
    name = tg['name']; leaf = name.split('.')[-1]
    # aliases: "import ... leaf as X" anywhere in scope
    aliases = set()
    pat = re.compile(r'\b' + re.escape(leaf) + r'\s+as\s+([A-Za-z_]\w*)')
    for f, c in src.items():
        for m in pat.finditer(c): aliases.add(m.group(1))
    names = {leaf} | aliases
    tfile = os.path.join(B, tg['file'])
    for f, c in src.items():
        if not any(n in c for n in names): continue
        toks = name_tokens(c, names)
        if toks is None:
            out.write(json.dumps({'target': name, 'file': f, 'error': 'tokenize'}) + '\n'); continue
        if not toks: continue
        s = jedi.Script(c, path=os.path.join(B, f), project=proj, environment=env)
        lines = c.splitlines()
        for (ln, col, tok, prev, nxt) in toks:
            try:
                defs = s.goto(ln, col, follow_imports=True)
            except Exception as e:
                defs = []; err = repr(e)[:100]
            else:
                err = None
            dl = [(str(d.module_path) if d.module_path else None, d.line, d.type) for d in defs]
            hit = any(p and os.path.realpath(p) == os.path.realpath(tfile) and l == tg['line'] for p, l, _ in dl)
            out.write(json.dumps({'target': name, 'file': f, 'line': ln, 'col': col, 'tok': tok, 'prev': prev, 'next': nxt,
                                  'hit': hit, 'defs': [(os.path.relpath(p, B) if p and p.startswith(B) else p, l, t) for p, l, t in dl],
                                  'err': err, 'text': lines[ln-1].strip()[:160]}) + '\n')
        out.flush()
    print('done', name, sorted(aliases), file=sys.stderr)
