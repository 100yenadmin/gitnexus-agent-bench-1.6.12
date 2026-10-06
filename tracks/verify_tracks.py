#!/usr/bin/env python3
"""Recompute the published claims-bench numbers (tracks 1-7) from the files in this directory only.

Run from anywhere:  python3 verify_tracks.py
Exit status 0 when every check matches; each check prints OK or MISMATCH with both values.
Probe answers are re-scored here with the same matching rules as the bench scorers (score_p1/p3/p4.py);
change-task outcomes come from the grade of record (grades.jsonl, produced by regrade.py).
"""
import json, os, posixpath, re, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
FAIL = []


def p(*a):
    return os.path.join(HERE, *a)


def jl(path):
    return [json.loads(l) for l in open(path) if l.strip()]


def ok(name, got, want):
    good = got == want
    print(f"{'OK      ' if good else 'MISMATCH'} {name}: got {got!r}, published {want!r}")
    if not good:
        FAIL.append(name)


def scored(track_dir):
    return [r for r in jl(p(track_dir, "runs.jsonl")) if not r["excluded"]]


def by_arm(rows):
    d = defaultdict(list)
    for r in rows:
        d[r["arm"]].append(r)
    return d


# ---- totals ------------------------------------------------------------------------------------------------------
dirs = ["01-fixes", "02-workflow-bench", "03-impact-ts", "04-rename", "05-structural", "06-taint", "07-review"]
allrows = {d: jl(p(d, "runs.jsonl")) for d in dirs}
ok("graded runs, tracks 1-7", sum(len([r for r in v if not r["excluded"]]) for v in allrows.values()), 340)
ok("Haiku (H0/H2) runs inside tracks 1/3/4/5",
   sum(1 for v in allrows.values() for r in v if not r["excluded"] and r["arm"] in ("H0", "H2")), 66)

# ---- track 1: fixes ----------------------------------------------------------------------------------------------
o = by_arm(scored("01-fixes"))
pub = {"A0": 8, "A1": 7, "A2": 9, "A3": 8, "C0": 11, "C1": 10, "C2": 10, "H0": 7, "H2": 5}
for arm, want in pub.items():
    rs = o[arm]
    ok(f"track 1 {arm} resolved with no regressions (of {len(rs)})", sum(r["outcome"]["resolved_clean"] for r in rs), want)
rd = json.load(open(p("report-data", "O.json")))["arms"]
for arm, rs in sorted(o.items()):
    ok(f"track 1 {arm} mean cost (USD, 4 dp)", round(sum(r["cost_usd"] for r in rs) / len(rs), 4), round(rd[arm]["cost"], 4))
ctl = jl(p("01-fixes", "controls.jsonl"))
ok("track 1 controls: BASE fails hidden tests (of 12)", sum(c["control"] == "BASE" and c["hidden_tests_pass"] is False for c in ctl), 12)
ok("track 1 controls: FIX passes hidden tests and regression (of 12)",
   sum(c["control"] == "FIX" and c["hidden_tests_pass"] is True and c["regression_clean"] is True for c in ctl), 12)

# ---- track 2: upstream workflow_bench ----------------------------------------------------------------------------
u = scored("02-workflow-bench")
for arm in ("U_nomcp", "U_mcp", "U_direct"):
    for variant in ("runs-u-pdg", "base"):
        rs = [r for r in u if r["arm"] == arm and (r["run"].startswith("runs-u-pdg/") == (variant == "runs-u-pdg"))]
        ok(f"track 2 {arm} [{'pdg index' if variant == 'runs-u-pdg' else 'default index'}] resolved (of {len(rs)})",
           sum(r["outcome"]["resolved_clean"] for r in rs), 2)

# ---- track 3: impact (TypeScript) --------------------------------------------------------------------------------
def norm(x):
    x = posixpath.normpath(str(x or "").strip().lstrip("./"))
    i = x.find("gitnexus/src/")
    return x[i:] if i >= 0 else x


def match(ans, gt, tol=2):
    pairs = sorted((abs(al - gl), ai, gi) for ai, (ap, al) in enumerate(ans) for gi, (gp, gl) in enumerate(gt)
                   if ap == gp and abs(al - gl) <= tol)
    ua, ug, tp = set(), set(), 0
    for _d, ai, gi in pairs:
        if ai not in ua and gi not in ug:
            ua.add(ai); ug.add(gi); tp += 1
    return tp


gts = {f"p1-{g['name']}": sorted({(s["file"], s["line"]) for s in g["sites"]}) for g in json.load(open(p("03-impact-ts", "gt.json")))}
agg = defaultdict(lambda: [0.0, 0.0, 0])
bad = 0
for r in scored("03-impact-ts"):
    f = p("03-impact-ts", "answers", r["run"] + ".json")
    ans = []
    if os.path.exists(f):
        s = set()
        for x in json.load(open(f)).get("locations") or []:
            try:
                s.add((norm(x.get("path")), int(x.get("line"))))
            except Exception:
                pass
        ans = sorted(s)
    gt = gts[r["task"]]
    tp = match(ans, gt)
    R = tp / len(gt) if gt else 1.0
    P = tp / len(ans) if ans else (1.0 if not gt else 0.0)
    bad += abs(R - r["outcome"]["recall"]) > 1e-9 or abs(P - r["outcome"]["precision"]) > 1e-9
    a = agg[r["arm"]]; a[0] += R; a[1] += P; a[2] += 1
ok("track 3 answers re-scored == runs.jsonl outcome (mismatching runs)", bad, 0)
rd = json.load(open(p("report-data", "P1.json")))["arms"]
for arm, (R, P, n) in sorted(agg.items()):
    ok(f"track 3 {arm} mean recall / precision (3 dp)", (round(R / n, 3), round(P / n, 3)), (round(rd[arm]["R"], 3), round(rd[arm]["P"], 3)))

# ---- track 4: rename -----------------------------------------------------------------------------------------------
pr = scored("04-rename")
ok("track 4 agent runs resolved with no regressions (of 42)", sum(r["outcome"]["resolved_clean"] for r in pr), 41)
ed = json.load(open(p("04-rename", "tool-edit-lists", "engine-direct.json")))
ok("track 4 rename tool's own edit lists passing the oracle (of 6)", sum(v["passed"] for v in ed.values()), 2)
cnt_bad = 0
for name, v in ed.items():
    lst = json.load(open(p("04-rename", "tool-edit-lists", name + ".json")))["calls"][0]
    cnt_bad += sum(len(c["edits"]) for c in lst["changes"]) != v["edits"]
ok("track 4 bundled edit lists match the edit counts that were applied (mismatching targets)", cnt_bad, 0)

# ---- track 5: structural (agents + tool output) --------------------------------------------------------------------
def tool_json(name):
    s = open(p("05-structural", "tool-output", name)).read()
    return json.loads(s[s.index("\n{", s.index("MCP server starting")) + 1:])


def norm_route(m, path):
    m, path = str(m).upper().strip(), str(path).strip()
    if m == "GET" and ("(?!" in path or path.strip("/") in ("*", "(.*)", ".*") or "spa fallback" in path.lower()):
        return ("GET", "/<SPA fallback regex>")
    return (m, "/" + path.strip("/"))


gt3 = json.load(open(p("05-structural", "gt.json")))
groutes = {norm_route(x["method"], x["path"]) for x in gt3["routes"]}
rm = tool_json("route_map-gnxu-taint.txt")["routes"]
found = {norm_route(e["method"], e["route"]) for e in rm
         if str(e.get("handler", "")).startswith("gitnexus/src/server/") and "repo-tools" not in e["handler"]}
ok("track 5 route_map: ground-truth routes reported with the right method (of 27)", (len(groutes & found), len(groutes)), (21, 27))
tools = {t["name"] for t in tool_json("tool_map-gnxu-taint.txt")["tools"]}
ok("track 5 tool_map: MCP tools found (of 17)", (len(set(gt3["tools"]) & tools), len(gt3["tools"])), (17, 17))
hit = tot = 0
for ep, f in (("/api/file", "api_impact_api_file.txt"), ("/api/query", "api_impact_api_query.txt"), ("/api/repos", "api_impact_api_repos.txt")):
    b = tool_json(f)
    entries = b["routes"] if "routes" in b else [b]
    files = {c.get("file") for e in entries for c in e.get("consumers") or []}
    g = set(gt3["consumers"][ep]["files"])
    hit += len(g & files); tot += len(g)
ok("track 5 api_impact: real consumer files found (of 9)", (hit, tot), (0, 9))
bad = 0
for r in scored("05-structural"):
    f = p("05-structural", "answers", r["run"] + ".json")
    a = json.load(open(f)) if os.path.exists(f) else None
    sub = r["outcome"]["sub"]
    if sub == "routes":
        alls = {pp for m, pp in groutes if m == "ALL"}
        ans = {norm_route(x.get("method"), x.get("path")) for x in (a or {}).get("routes", []) if isinstance(x, dict)}
        ans = {(("ALL", pp) if pp in alls else (m, pp)) for m, pp in ans}
        g = groutes
    elif sub == "tools":
        g = set(gt3["tools"]); ans = {str(x).strip() for x in (a or {}).get("tools", [])}
    else:
        task = r["task"]; ep = {"p3-consumers-repos": "/api/repos", "p3-consumers-file": "/api/file", "p3-consumers-query": "/api/query"}[task]
        g = set(gt3["consumers"][ep]["files"]); ans = set()
        for x in (a or {}).get("files", []):
            x = str(x).strip().lstrip("./"); i = x.find("gitnexus-web/src/")
            ans.add(x[i:] if i >= 0 else "gitnexus-web/src/" + x.split("src/")[-1])
    tp = len(g & ans)
    bad += tp != r["outcome"]["tp"] or len(g) != r["outcome"]["gt"]
ok("track 5 agent answers re-scored == runs.jsonl outcome (mismatching runs)", bad, 0)

# ---- track 6: taint -------------------------------------------------------------------------------------------------
def tool6(name):
    s = open(p("06-taint", "tool-output", name)).read()
    return json.loads(s[s.index("\n{", s.index("MCP server starting")) + 1:])


seeded = "gitnexus/src/server/repo-tools.ts"
inline = [f for f in tool6("explain-seeded.txt")["findings"] + tool6("explain-all.txt")["findings"] if f.get("file") == seeded]
gt4 = json.load(open(p("06-taint", "gt.json")))
ok("track 6 explain on the seeded inline-callback module: seeded flows found (of 3)", (len(inline), len(gt4["flows"])), (0, 3))
named = tool6("explain-named.txt")["findings"]
inter = sorted((f["source"].get("function"), f["sink"].get("function"), f["sinkKind"]) for f in named if f.get("interprocedural"))
print("info     track 6 named-handler variant, interprocedural findings:", inter)
bad = 0
for r in scored("06-taint"):
    flows = json.load(open(p("06-taint", "answers", r["run"] + ".json"))).get("flows") or []
    F, hitset = gt4["file"], set()
    for fl in flows:
        def loc(x):
            try:
                pp = str(x.get("path", "")).strip().lstrip("./"); i = pp.find("gitnexus/src/")
                return (pp[i:] if i >= 0 else pp), int(x.get("line"))
            except Exception:
                return None, None
        sp, sl = loc(fl.get("source") or {}); kp, kl = loc(fl.get("sink") or {})
        m = [g["id"] for g in gt4["flows"] if sp == F and sl is not None and abs(sl - g["source_line"]) <= 2]
        if m:
            hitset.update(m); continue
        if sp == F and sl is not None and abs(sl - gt4["decoys"][0]["source_line"]) <= 2:
            continue
        if kp == F and kl is not None and abs(kl - gt4["decoys"][1]["sink_line"]) <= 2:
            continue
        if kp == F and kl is not None:
            s = [g["id"] for g in gt4["flows"] if abs(kl - g["sink_line"]) <= 2 and g["id"] != "S1"]
            hitset.update(s)
    bad += sorted(hitset) != r["outcome"]["found"]
ok("track 6 agent answers re-scored == runs.jsonl outcome (mismatching runs)", bad, 0)
ok("track 6 agent runs that found all 3 seeded flows (of 8)", sum(len(r["outcome"]["found"]) == 3 for r in scored("06-taint")), 8)

# ---- track 7: review ------------------------------------------------------------------------------------------------
rv = by_arm(scored("07-review"))
for arm, want in (("R_plain", 2), ("R_gnx", 2), ("CR0", 2), ("CR1", 4)):
    rs = rv[arm]
    ok(f"track 7 {arm} labelled defects matched (tp of labels)",
       (sum(r["outcome"]["tp"] for r in rs), sum(r["outcome"]["tp"] + r["outcome"]["fn"] for r in rs)), (want, 42))

print()
print("ALL CHECKS MATCH" if not FAIL else f"{len(FAIL)} MISMATCH(ES): {FAIL}")
sys.exit(1 if FAIL else 0)
