#!/usr/bin/env python3
"""Tool-only score for GitNexus `impact` (upstream, depth 1) on the 8 Track H impact targets.
A GT site counts as found when the function/method enclosing it (or the file, for module-level sites)
is among impact's depth-1 symbols. Precision = share of returned depth-1 symbols that enclose >=1 GT site.
Run with the base venv's python (ast for current syntax)."""
import ast, json, os, subprocess, sys
import os as _os, sys as _sys
_HARNESS = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
_sys.path[:0] = [_os.path.join(_HARNESS, "runner"), _os.path.join(_HARNESS, "common")]
import benchenv  # noqa: E402
H = benchenv.need("HERMES_ARTIFACTS")
BR = benchenv.need("BENCH_ROOT")
S = f"{BR}/clones.noindex/toolonly-h"
REPO = f"{S}/impact"
gt = json.load(open(f"{H}/impact/gt.json"))
env = dict(os.environ, BENCH_GN_HOME=f"{S}/gnhome", BENCH_GN_RO="1")

def enclosing(path, line, cache={}):
    """Qualified name of the innermost def/class-method enclosing `line` (None = module level)."""
    if path not in cache:
        tree = ast.parse(open(os.path.join(REPO, path)).read())
        spans = []
        def walk(node, prefix):
            for ch in ast.iter_child_nodes(node):
                if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    q = prefix + ch.name
                    spans.append((ch.lineno, ch.end_lineno, q, ch.name))
                    walk(ch, q + ".")
                elif isinstance(ch, ast.ClassDef):
                    walk(ch, prefix + ch.name + ".")
                else:
                    walk(ch, prefix)
        walk(tree, "")
        cache[path] = spans
    best = None
    for a, b, q, n in cache[path]:
        if a <= line <= b and (best is None or a >= best[0]):
            best = (a, b, q, n)
    return best

out = {}
for t in gt:
    name = t["name"].split(".")[-1]
    cmd = [_os.path.join(_HARNESS, "isolation", "launcher-run.sh"), "impact", name, "-r", "impact", "-f", t["file"], "--depth", "1", "--limit", "500"]
    if t.get("cls") or "." in t["name"]:
        cmd += ["--kind", "Method"]
    p = subprocess.run(cmd, cwd=REPO, env=env, capture_output=True, text=True, timeout=600)
    txt = p.stdout[p.stdout.find("{"):]
    try:
        r = json.loads(txt)
    except Exception:
        out[t["id"]] = {"error": (p.stdout + p.stderr)[-400:]}; continue
    syms = (r.get("byDepth") or {}).get("1", [])
    # symbol key: (file, last name segment, qualified tail)
    returned = [(s["filePath"], s["id"].split(":")[-1], s["name"], s["id"].split(":")[0]) for s in syms]
    retset_q = {(f, q) for f, q, n, k in returned}
    retset_n = {(f, n) for f, q, n, k in returned}
    retfiles = {f for f, q, n, k in returned}
    hit, miss, site_syms = 0, [], set()
    for st in t["sites"]:
        enc = enclosing(st["file"], st["line"])
        if enc is None:
            ok = any(f == st["file"] and k == "File" for f, q, n, k in returned)
            key = (st["file"], "<module>")
        else:
            ok = (st["file"], enc[2]) in retset_q or (st["file"], enc[3]) in retset_n
            key = (st["file"], enc[2])
        site_syms.add(key)
        hit += ok
        if not ok: miss.append(f'{st["file"]}:{st["line"]} in {key[1]}')
    good = sum(1 for f, q, n, k in returned
               if any(sf == f and (sq == q or sq.split(".")[-1] == n or (sq == "<module>" and k == "File")) for sf, sq in site_syms))
    gtfiles = {s["file"] for s in t["sites"]}
    out[t["id"]] = dict(sites=len(t["sites"]), site_recall=round(hit / len(t["sites"]), 3), returned=len(returned),
                        symbol_precision=round(good / len(returned), 3) if returned else None,
                        file_recall=round(len(gtfiles & retfiles) / len(gtfiles), 3),
                        file_precision=round(len(gtfiles & retfiles) / len(retfiles), 3) if retfiles else None,
                        impactedCount=r.get("impactedCount"), epistemic=r.get("epistemic"), missed=miss[:12])
json.dump(out, open(f"{H}/impact/toolonly/toolonly.json", "w"), indent=1)
for k, v in out.items():
    print(k, {x: v.get(x) for x in ("sites", "site_recall", "returned", "symbol_precision", "file_recall", "file_precision", "error")})
