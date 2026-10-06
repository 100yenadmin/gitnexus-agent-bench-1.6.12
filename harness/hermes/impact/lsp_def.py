#!/usr/bin/env python3
"""Resolve residual references with pyright's own go-to-definition (pinned pyright 1.1.414 langserver, base checkout,
same venv). For each residual name token: definition -> target decl (same symbol), other decl (different symbol), or
none (pyright cannot resolve the receiver: needs reading). Usage: lsp_def.py refs.jsonl out.jsonl"""
import json, os, subprocess, sys, threading, queue, urllib.parse
import os as _os, sys as _sys
_HARNESS = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
_sys.path[:0] = [_os.path.join(_HARNESS, "runner"), _os.path.join(_HARNESS, "common")]
import benchenv  # noqa: E402
BASE = _os.path.join(benchenv.need('BENCH_ROOT'), 'tasks/h/impact')
LS = _os.path.join(benchenv.opt('PYRIGHT_DIR') or _os.path.join(benchenv.need('BENCH_ROOT'), 'tools/pyright-1.1.414'),
                   'node_modules/pyright/langserver.index.js')
NODE = benchenv.need('NODE_BIN')
uri = lambda p: 'file://' + urllib.parse.quote(os.path.join(BASE, p))
p = subprocess.Popen([NODE, LS, '--stdio'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, cwd=BASE)
resp = {}; cv = threading.Condition(); nid = [0]
def send(msg):
    b = json.dumps(msg).encode(); p.stdin.write(b'Content-Length: %d\r\n\r\n' % len(b) + b); p.stdin.flush()
def reader():
    f = p.stdout
    while True:
        h = {}
        while True:
            l = f.readline()
            if not l: return
            l = l.decode().strip()
            if not l: break
            k, v = l.split(':', 1); h[k.lower()] = v.strip()
        m = json.loads(f.read(int(h['content-length'])))
        if 'method' in m and 'id' in m:   # server -> client request
            if m['method'] == 'workspace/configuration':
                res = []
                for it in m['params']['items']:
                    s = it.get('section')
                    res.append({'pythonPath': f'{BASE}/.venv/bin/python'} if s == 'python' else
                               {'diagnosticMode': 'openFilesOnly', 'autoSearchPaths': True} if s == 'python.analysis' else {})
                send({'jsonrpc': '2.0', 'id': m['id'], 'result': res})
            else:
                send({'jsonrpc': '2.0', 'id': m['id'], 'result': None})
        elif 'id' in m:
            with cv: resp[m['id']] = m; cv.notify_all()
threading.Thread(target=reader, daemon=True).start()
def req(method, params, timeout=300):
    nid[0] += 1; i = nid[0]; send({'jsonrpc': '2.0', 'id': i, 'method': method, 'params': params})
    with cv:
        cv.wait_for(lambda: i in resp, timeout)
        return resp.pop(i, {}).get('result')
req('initialize', {'processId': os.getpid(), 'rootUri': 'file://' + BASE, 'capabilities': {'workspace': {'configuration': True}},
                   'workspaceFolders': [{'uri': 'file://' + BASE, 'name': 'impact'}]})
send({'jsonrpc': '2.0', 'method': 'initialized', 'params': {}})
rows = [json.loads(l) for l in open(sys.argv[1])]
# Prefilter (module-level function targets only): an attribute reference `x.name` can only reach a module function when
# `x` is that module, so attribute residuals in files that never mention the module's last dotted component are
# classified 'res-skip-attr' without an LSP query (e.g. the thousands of dict `.get(` calls for a module function `get`).
import re
_mention = {}
def mentions(f, comp):
    k = (f, comp)
    if k not in _mention:
        _mention[k] = re.search(r'\b' + re.escape(comp) + r'\b', open(f"{BASE}/{f}", encoding='utf-8').read()) is not None
    return _mention[k]
for r in rows:
    if r['cls'] == 'residual' and not r['target_cls'] and r['prev'] == '.':
        comp = r['tfile'][:-3].split('/')[-1]
        if comp == '__init__': comp = r['tfile'].split('/')[-2]
        if not mentions(r['file'], comp): r['cls'] = 'res-skip-attr'
opened = set(); out = open(sys.argv[2], 'w')
for r in rows:
    if r['cls'] != 'residual':
        out.write(json.dumps(r) + '\n'); out.flush(); continue
    if r['file'] not in opened:
        send({'jsonrpc': '2.0', 'method': 'textDocument/didOpen', 'params': {'textDocument': {
            'uri': uri(r['file']), 'languageId': 'python', 'version': 1, 'text': open(f"{BASE}/{r['file']}", encoding='utf-8').read()}}})
        opened.add(r['file'])
    # LSP columns are UTF-16; tokenize columns are code points: convert
    line = open(f"{BASE}/{r['file']}", encoding='utf-8').read().splitlines()[r['line'] - 1]
    col16 = len(line[:r['col']].encode('utf-16-le')) // 2
    res = req('textDocument/definition', {'textDocument': {'uri': uri(r['file'])}, 'position': {'line': r['line'] - 1, 'character': col16 + 1}})
    defs = []
    for d in (res or []):
        u = d.get('uri') or d.get('targetUri'); rg = d.get('range') or d.get('targetSelectionRange')
        path = urllib.parse.unquote(u[len('file://'):]) if u else ''
        defs.append([os.path.relpath(path, BASE) if path.startswith(BASE) else path, rg['start']['line'] + 1])
    r['defs'] = defs
    out.write(json.dumps(r) + '\n'); out.flush()
out.close()
p.kill()
os._exit(0)
