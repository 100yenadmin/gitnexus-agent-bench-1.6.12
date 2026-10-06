#!/usr/bin/env python3
"""Build the final report mechanically from the run directories.

1. Runs every scorer with --json into report-data/ (report.py for change tasks; score_p1/p3/p4/review for probes).
2. Runs the contamination audit (scan_gnx.py) over every directory that is scored.
3. Sums notional spend per track and engine (results.jsonl cost_usd; Codex rows are priced by the harness).
4. Fills report-template.html: {{key}} -> a metric from the flat metrics dict, {{table:name}} -> a rendered table.
   An unknown key fails loudly so no placeholder ships unfilled.

Usage: build_report.py [--out ../report.html]   (cwd-independent)
Published version: data paths are relative to $BENCH_ARTIFACTS (run dirs, tasks-*.json, probes/, report-template.html,
report-data/), the hermes-agent impact track is read from $HERMES_ARTIFACTS, and the scorers are this harness's own.
"""
import html, json, os, re, subprocess, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))           # harness/grading (code)
HARNESS = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(HARNESS, "runner"), os.path.join(HARNESS, "common")]
import benchenv  # noqa: E402

ART = benchenv.need("BENCH_ARTIFACTS")                     # claims-bench data dir
DATA = os.path.join(ART, "report-data")
PY = sys.executable


def p(*a):
    return os.path.join(ART, *a)


def c(*a):
    return os.path.join(HERE, *a)


def existing(dirs):
    return [d for d in dirs if os.path.exists(p(d, "results.jsonl"))]


# ---- track configuration -------------------------------------------------------------------------------------
U_EXCLUDE = ["runs-u/u-trivial-U_nomcp-t1", "runs-u/u-cbug-U_nomcp-t1", "runs-u/u-feat-U_nomcp-t1",
             "runs-u/u-xmod-U_nomcp-t1"]  # old-isolation no-GitNexus rows: reached the live index (notes 14:25Z)
HB = benchenv.opt("HERMES_ARTIFACTS", os.path.join(ART, "_no_hermes_track"))  # large-repo follow-up (hermes-agent)
TRACKS = {
    "U": dict(kind="change", dirs=["runs-u", "runs-u-nomcp-clean", "runs-u-pdg"], exclude=U_EXCLUDE),
    "O": dict(kind="change", dirs=["runs-o", "runs-o2"], exclude=[]),
    "P2": dict(kind="change", dirs=["runs-p2"], exclude=[]),
    "P1": dict(kind="p1", tasks="tasks-p1.json", dirs=["runs-p1"]),
    "P3": dict(kind="p3", tasks="tasks-p3.json", dirs=["runs-p3", "runs-p3b"],
               exclude=["runs-p3/p3-routes-C2-t1"]),  # killed by Codex "model at capacity"; rerun in runs-p3b
    "P4": dict(kind="p4", tasks="tasks-p4.json", dirs=["runs-p4"]),
    "HI": dict(kind="himpact", scorer=os.path.join(HARNESS, "hermes", "score_h_impact.py"), tasks=os.path.join(HB, "tasks-h-impact.json"),
               dirs=[os.path.join(HB, d) for d in ("runs-h-impact-claude", "runs-h-impact-claude-m", "runs-h-impact-codex")]),
    "HF": dict(kind="change", dirs=[os.path.join(HB, d) for d in ("runs-h-fix-codex",)], exclude=[]),  # Opus fix arms stopped after 7 runs (track closed early)
    "RV": dict(kind="review", tasks="tasks-review.json",
               # (the original list also named "runs-review-f", which was never created; existing() skipped it)
               dirs=["runs-review", "runs-review-b", "runs-review-c", "runs-review-d", "runs-review-e"]),
}
ARM_LABEL = {
    "A0": "Opus, no GitNexus", "A1": "Opus, current setup", "A1f": "Opus, told to use GitNexus first", "A1m": "Opus, required to call GitNexus impact", "A2": "Opus, full upstream", "A3": "Opus, upstream + direct mode",
    "C0": "Sol, no GitNexus", "C1": "Sol, current setup", "C1f": "Sol, told to use GitNexus first", "C2": "Sol, full upstream",
    "H0": "Haiku, no GitNexus", "H2": "Haiku, full upstream",
    "U_nomcp": "No GitNexus", "U_mcp": "MCP (upstream's baseline)", "U_direct": "MCP + skills + direct mode",
    "R_plain": "Opus, plain review", "R_gnx": "Opus, gitnexus-review skill", "CR0": "Sol, plain review", "CR1": "Sol, read-only MCP",
}
ARM_ORDER = ["A0", "A1", "A1f", "A1m", "A2", "A3", "C0", "C1", "C1f", "C2", "H0", "H2", "U_nomcp", "U_mcp", "U_direct", "R_plain", "R_gnx", "CR0", "CR1"]
NOGNX = {"A0", "C0", "H0", "U_nomcp", "R_plain", "CR0"}
CODEX = {"C0", "C1", "C1f", "C2", "CR0", "CR1"}
USAGE = {}


def arm_key(a):
    return ARM_ORDER.index(a) if a in ARM_ORDER else 99


def run_json(cmd, out):
    r = subprocess.run(cmd + ["--json", out], cwd=ART, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"scorer failed: {' '.join(cmd)}\n{r.stderr[-2000:]}")
    return json.load(open(out))


# ---- collect ---------------------------------------------------------------------------------------------------
def collect():
    os.makedirs(DATA, exist_ok=True)
    res = {}
    for name, t in TRACKS.items():
        dirs = existing(t["dirs"])
        if not dirs:
            continue
        out = os.path.join(DATA, f"{name}.json")
        if t["kind"] == "change":
            cmd = [PY, c("report.py"), ",".join(p(d) for d in dirs)]
            if t["exclude"]:
                cmd += ["--exclude", ",".join(t["exclude"])]
        elif t["kind"] == "himpact":
            cmd = [PY, t["scorer"], t["tasks"], ",".join(dirs)]
        else:
            scorer = {"p1": "score_p1.py", "p3": "score_p3.py", "p4": "score_p4.py", "review": "score_review.py"}[t["kind"]]
            cmd = [PY, c(scorer), p(t["tasks"]), ",".join(p(d) for d in dirs)]
            if t.get("exclude"):
                cmd += ["--exclude", ",".join(t["exclude"])]
        res[name] = run_json(cmd, out)
        res[name]["_dirs"] = dirs
    return res


def audit(res):
    dirs = sorted({d for r in res.values() for d in r["_dirs"]})
    out = subprocess.run([PY, c("scan_gnx.py"), ",".join(p(d) for d in dirs)], cwd=ART, capture_output=True, text=True).stdout
    excluded = {e for t in TRACKS.values() for e in t.get("exclude", [])}
    bad = [l.split()[0] for l in out.splitlines() if l.rstrip().endswith("CONTAMINATED")]
    bad_scored = [b for b in bad if b not in excluded]
    live = [l.split()[0] for l in out.splitlines() if "live-in-gnx-arm" in l]
    open(os.path.join(DATA, "scan_gnx.txt"), "w").write(out)
    wr = subprocess.run([PY, c("scan_writes.py"), ",".join(p(d) for d in dirs)], cwd=ART, capture_output=True, text=True)
    open(os.path.join(DATA, "scan_writes.txt"), "w").write(wr.stdout + wr.stderr)
    stray = [l for l in wr.stdout.splitlines() if l.strip()]
    return dict(contaminated_scored=bad_scored, contaminated_excluded=[b for b in bad if b in excluded], live_in_gnx_arm=live,
                stray_writes=stray, file_tool_scan=wr.stderr.strip())


def usage(res):
    """Per arm, over every scored run: how many runs touched GitNexus at all (MCP or CLI), calls per run, and the upstream
    hook's outcomes (enriched = graph context injected; fallback = 'augment unavailable' hint; empty = no output)."""
    from bench import parse_claude
    excluded = {e for t in TRACKS.values() for e in t.get("exclude", [])}
    agg = defaultdict(lambda: defaultdict(int))
    for d in sorted({d for r in res.values() for d in r["_dirs"]}):
        for l in open(p(d, "results.jsonl")):
            r = json.loads(l)
            if f"{d}/{r['run']}" in excluded or "error" in r:
                continue
            st = p(d, "runs", r["run"], "stream.jsonl")
            cli = parse_claude(st)["gnx_cli"] if r.get("engine", "claude") == "claude" and os.path.exists(st) else (r.get("gnx_cli") or 0)
            calls = (r.get("gnx_calls") or 0) + (cli or 0)
            a = agg[r["arm"]]
            a["runs"] += 1; a["used"] += int(calls > 0); a["calls"] += calls
            hl = p(d, "runs", r["run"], "hooklog", "hook-calls.log")
            if os.path.exists(hl):
                for line in open(hl, errors="replace"):
                    f = line.rstrip("\n").split("\t")
                    ev, ctx = (f[2] if len(f) > 2 else ""), (f[5] if len(f) > 5 else "")
                    a["hook_calls"] += 1
                    if re.search(r"\[GitNexus\] \d+ related symbols? found", ctx):
                        a["hook_enriched"] += 1
                    elif "augment is unavailable" in ctx:
                        a["hook_hint"] += 1
                    elif "index is stale" in ctx:
                        a["hook_stale"] += 1
                    elif ctx.strip():
                        a["hook_other"] += 1
                    if ev == "PreToolUse":
                        a["hook_pre"] += 1
    return agg


def spend():
    """Notional spend over EVERY run directory on disk (scored, aborted, smoke), by directory and engine."""
    rows = defaultdict(lambda: dict(runs=0, cost=0.0))
    for root in (ART, HB):
        if not os.path.isdir(root):
            continue
        for d in sorted(os.listdir(root)):
            f = os.path.join(root, d, "results.jsonl")
            if not os.path.isfile(f):
                continue
            for l in open(f):
                try:
                    r = json.loads(l)
                except Exception:
                    continue
                k = (d if root == ART else os.path.join(root, d), r.get("engine", "?"))
                rows[k]["runs"] += 1; rows[k]["cost"] += r.get("cost_usd") or 0
    return rows


# ---- metrics ---------------------------------------------------------------------------------------------------
def fmt_money(x):
    return "–" if x is None else f"${x:,.2f}"


def fmt_pct(x):
    return "–" if x is None else f"{100 * x:.0f}%"


def metrics(res, aud, sp):
    m = {}
    for name, r in res.items():
        if "arms" not in r:
            continue
        for arm, a in r["arms"].items():
            for k, v in a.items():
                if isinstance(v, (int, float)):
                    m[f"{name}.{arm.replace('|', '.')}.{k}"] = v  # P3 keys are "<question>|<arm>"
    if "RV" in res:  # review arms report per-run means; the prose needs totals
        for arm in res["RV"]["arms"]:
            pr = [x for x in res["RV"]["per_run"] if x["arm"] == arm]
            m[f"RV.{arm}.tp_sum"] = sum(x["tp"] for x in pr)
            m[f"RV.{arm}.fp_sum"] = sum(x["fp"] for x in pr)
            m[f"RV.{arm}.labels"] = sum(x["tp"] + x["fn"] for x in pr)
    for arm, a in USAGE.items():
        for k, v in a.items():
            m[f"use.{arm}.{k}"] = v
        m[f"use.{arm}.share"] = a["used"] / a["runs"] if a["runs"] else 0
    hk = [a for arm, a in USAGE.items() if arm in ("A2", "A3", "H2")]
    for k in ("hook_calls", "hook_pre", "hook_enriched", "hook_hint", "hook_stale", "hook_other"):
        m[f"hooks.{k[5:]}"] = sum(a.get(k, 0) for a in hk)
    m["hooks.runs"] = sum(a["runs"] for a in hk)
    for f, pre in (("probes/p3/engine-direct.json", "p3eng"), ("probes/p4/engine-named.json", "p4eng"),
                   ("probes/p2/direct/summary.json", "p2eng")):
        if os.path.exists(p(f)):
            for k, v in json.load(open(p(f))).items():
                if isinstance(v, (int, float)):
                    m[f"{pre}.{k}"] = v
    m["audit.contaminated_scored"] = len(aud["contaminated_scored"])
    m["audit.contaminated_excluded"] = len(aud["contaminated_excluded"])
    m["audit.live_in_gnx_arm"] = len(aud["live_in_gnx_arm"])
    m["audit.stray_writes"] = len(aud["stray_writes"])
    mm = re.search(r"scanned (\d+) claude runs, (\d+) file-tool calls", aud["file_tool_scan"])
    m["audit.file_tool_runs"], m["audit.file_tool_calls"] = (int(mm.group(1)), int(mm.group(2))) if mm else (0, 0)
    tot = sum(v["cost"] for v in sp.values())
    m["spend.total"] = tot
    m["spend.runs"] = sum(v["runs"] for v in sp.values())
    scored_dirs = {d for r in res.values() for d in r["_dirs"]}
    m["spend.scored"] = sum(v["cost"] for (d, _e), v in sp.items() if d in scored_dirs)
    m["spend.scored_runs"] = sum(v["runs"] for (d, _e), v in sp.items() if d in scored_dirs)
    return m


# ---- tables ------------------------------------------------------------------------------------------------------
def tbl(head, rows, cls=""):
    h = "".join(f"<th>{html.escape(x)}</th>" for x in head)
    b = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="tw"><table class="{cls}"><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>'


def turns_cell(arm, v, spec=".0f"):
    """codex exec reports one turn per run, so a Codex turn count carries no information."""
    return "–" if arm in CODEX else format(v, spec)


def gnx_cell(arm, v):
    """No-GitNexus setups have no index; their few attempts hit the not-found stub (scan_gnx.py audits that)."""
    return "–" if arm in NOGNX else f"{v:.1f}"


def arm_cell(a):
    return f'<span class="arm">{html.escape(a)}</span> {html.escape(ARM_LABEL.get(a, a))}'


def change_summary(r):
    rows = []
    for arm in sorted(r["arms"], key=arm_key):
        a = r["arms"][arm]
        rows.append([arm_cell(arm), f'{a["clean"]}/{a["graded"]}', f'{a["resolved"]}/{a["graded"]}', fmt_money(a["cost"]),
                     turns_cell(arm, a["turns"]), f'{a["wall"] / 60:.1f}', gnx_cell(arm, a["gnx"])])
    return tbl(["Setup", "Resolved, no regressions", "Hidden tests pass", "Cost / run", "Turns", "Minutes", "GitNexus calls / run"],
               rows, "num")


def change_grid(r, task_order=None):
    cells = {(c["task"], c["arm"]): c for c in r["cells"]}
    tasks = task_order or sorted({c["task"] for c in r["cells"]})
    arms = sorted({c["arm"] for c in r["cells"]}, key=arm_key)
    rows = []
    for t in tasks:
        row = [f"<code>{html.escape(t)}</code>"]
        for a in arms:
            c = cells.get((t, a))
            if not c or not c["graded"]:
                row.append('<span class="na">–</span>')
                continue
            if c["clean"] == c["graded"]:
                row.append(f'<span class="ok">{"✓" * c["graded"]}</span>')
            elif c["oracle"] > c["clean"]:
                row.append(f'<span class="part" title="hidden tests pass, regression check fails">{c["clean"]}/{c["graded"]}◐</span>')
            elif c["clean"]:
                row.append(f'<span class="part">{c["clean"]}/{c["graded"]}</span>')
            else:
                row.append(f'<span class="bad">{"✗" * c["graded"]}</span>')
        rows.append(row)
    return tbl(["Task"] + [a for a in arms], rows, "grid")


PAIRS = [("A1", "A0"), ("A2", "A0"), ("A3", "A0"), ("C1", "C0"), ("C2", "C0"), ("H2", "H0"),
         ("U_mcp", "U_nomcp"), ("U_direct", "U_nomcp"), ("A1f", "A0"), ("A1m", "A0"), ("C1f", "C0")]


def paired(r):
    """Same task, GitNexus setup vs the same model without it: tasks where only one side resolved (clean), and the
    cost / turns ratio over the tasks both sides ran (ratio of sums)."""
    cells = {(c["task"], c["arm"]): c for c in r["cells"]}
    out = []
    for g, b in PAIRS:
        tasks = sorted({t for (t, a) in cells if a == g} & {t for (t, a) in cells if a == b})
        tasks = [t for t in tasks if cells[(t, g)]["graded"] and cells[(t, b)]["graded"]]
        if not tasks:
            continue
        rate = lambda c: c["clean"] / c["graded"]
        better = sum(rate(cells[(t, g)]) > rate(cells[(t, b)]) for t in tasks)
        worse = sum(rate(cells[(t, g)]) < rate(cells[(t, b)]) for t in tasks)
        cg = sum(cells[(t, g)]["cost"] for t in tasks); cb = sum(cells[(t, b)]["cost"] for t in tasks)
        tg = sum(cells[(t, g)]["turns"] for t in tasks); tb = sum(cells[(t, b)]["turns"] for t in tasks)
        out.append(dict(g=g, b=b, tasks=len(tasks), better=better, worse=worse, same=len(tasks) - better - worse,
                        cost_ratio=cg / cb if cb else None, turns_ratio=tg / tb if tb else None,
                        resolved_g=sum(cells[(t, g)]["clean"] for t in tasks), resolved_b=sum(cells[(t, b)]["clean"] for t in tasks),
                        graded_g=sum(cells[(t, g)]["graded"] for t in tasks), graded_b=sum(cells[(t, b)]["graded"] for t in tasks)))
    return out


def paired_table(r):
    rows = []
    for x in paired(r):
        cr = "–" if x["cost_ratio"] is None else f'{x["cost_ratio"]:.2f}×'
        tr = "–" if x["turns_ratio"] is None or x["g"] in CODEX else f'{x["turns_ratio"]:.2f}×'
        rows.append([f'{arm_cell(x["g"])}<span class="src">vs {html.escape(ARM_LABEL.get(x["b"], x["b"]))}</span>', str(x["tasks"]),
                     f'{x["resolved_g"]}/{x["graded_g"]} vs {x["resolved_b"]}/{x["graded_b"]}',
                     f'<span class="ok">{x["better"]}</span>' if x["better"] else "0",
                     f'<span class="bad">{x["worse"]}</span>' if x["worse"] else "0", str(x["same"]), cr, tr])
    return tbl(["GitNexus setup", "Tasks", "Resolved", "GitNexus better", "GitNexus worse", "Same", "Cost", "Turns"], rows, "num")


def p1_tables(r):
    rows = []
    for arm in sorted(r["arms"], key=arm_key):
        a = r["arms"][arm]
        rows.append([arm_cell(arm), f'{a["R"]:.3f}', f'{a["P"]:.3f}', fmt_pct(a["perfect"]), fmt_money(a["cost"]),
                     turns_cell(arm, a["turns"], ".1f"), gnx_cell(arm, a["gnx"])])
    summary = tbl(["Setup", "Recall", "Precision", "All sites exact", "Cost / question", "Turns", "GitNexus calls"], rows, "num")
    by = defaultdict(dict)
    for x in r["per_run"]:
        by[x["task"]][x["arm"]] = x
    arms = sorted({x["arm"] for x in r["per_run"]}, key=arm_key)
    rows = []
    for t in sorted(by):
        row = [f'<code>{html.escape(t[3:])}</code>', str(next(iter(by[t].values()))["gt"])]
        for a in arms:
            x = by[t].get(a)
            if not x:
                row.append('<span class="na">–</span>'); continue
            ok = x["recall"] == 1 and x["precision"] == 1
            row.append(f'<span class="{"ok" if ok else "bad"}">{x["recall"]:.2f} / {x["precision"]:.2f}</span>' if not ok else '<span class="ok">✓</span>')
        rows.append(row)
    detail = tbl(["Changed symbol", "Sites"] + arms, rows, "grid")
    return summary, detail


def p3_table(r):
    rows = []
    for key in sorted(r["arms"], key=lambda k: (k.split("|")[0], arm_key(k.split("|")[1]))):
        sub, arm = key.split("|")
        a = r["arms"][key]
        rows.append([html.escape(sub), arm_cell(arm), str(int(a["n"])), f'{a["R"]:.2f}', f'{a["P"]:.2f}', fmt_pct(a["perfect"]),
                     fmt_money(a["cost"]), gnx_cell(arm, a["gnx"])])
    return tbl(["Question", "Setup", "Runs", "Recall", "Precision", "Exact", "Cost / run", "GitNexus calls"], rows, "num")


def p4_table(r):
    rows = []
    for arm in sorted(r["arms"], key=arm_key):
        a = r["arms"][arm]
        rows.append([arm_cell(arm), str(int(a["n"])), fmt_pct(a["recall"]), f'{a["d1"] + a["d2"]:.1f}', fmt_money(a["cost"]),
                     gnx_cell(arm, a["gnx"])])
    return tbl(["Setup", "Runs", "Seeded flows found", "Decoys reported / run", "Cost / run", "GitNexus calls"], rows, "num")


def rv_table(r):
    rows = []
    for arm in sorted(r["arms"], key=arm_key):
        a = r["arms"][arm]
        g = lambda k: a.get(k)
        rows.append([arm_cell(arm), str(int(a["n"])), "–" if g("recall") is None else f'{g("recall"):.2f}',
                     "–" if g("wf1") is None else f'{g("wf1"):.2f}', "–" if g("blocker_recall") is None else f'{g("blocker_recall"):.2f}',
                     f'{sum(x["tp"] for x in r["per_run"] if x["arm"] == arm)}/{sum(x["tp"] + x["fn"] for x in r["per_run"] if x["arm"] == arm)}',
                     f'{sum(x["fp"] for x in r["per_run"] if x["arm"] == arm)}',
                     "–" if g("clean_pass") is None else fmt_pct(g("clean_pass")), fmt_money(a["cost"])])
    return tbl(["Setup", "Runs", "Recall", "Weighted F1", "Blocker recall", "Labelled issues found", "False positives",
                "Clean PR approved", "Cost / review"], rows, "num")


def himpact_table(r):
    rows = []
    for arm in sorted(r["arms"], key=arm_key):
        a = r["arms"][arm]
        rows.append([arm_cell(arm), str(int(a["n"])), f'{a["R"]:.3f}', f'{a["P"]:.3f}', fmt_pct(a["perfect"]), fmt_money(a["cost"]),
                     f'{a["wall"]:.0f}', gnx_cell(arm, a["gnx"])])
    return tbl(["Setup", "Runs", "Recall", "Precision", "All sites exact", "Cost / question", "Seconds", "GitNexus calls"], rows, "num")


def toolonly_table(m):
    """impact run directly (upstream, depth 1), scored by caller coverage: a site counts when a returned symbol encloses it."""
    t = json.load(open(os.path.join(HB, "impact", "toolonly", "toolonly.json")))
    rows, sites, covered, returned = [], 0, 0, 0
    for k, v in t.items():
        cov = v["sites"] - len(v["missed"])
        sites += v["sites"]; covered += cov; returned += v["returned"]
        ok = cov == v["sites"]
        rows.append([f'<code>{html.escape(k.replace("h-impact-", ""))}</code>', str(v["sites"]), str(v["returned"]),
                     f'<span class="{"ok" if ok else "bad"}">{cov}</span>', f'{v["symbol_precision"]:.2f}',
                     f'<code>{html.escape(v["epistemic"])}</code>'])
    m["HIT.sites"], m["HIT.covered"], m["HIT.missed"], m["HIT.returned"] = sites, covered, sites - covered, returned
    return tbl(["Target", "Sites", "Symbols", "Covered", "Precision", "impact says"], rows, "num")


def usage_table():
    rows = []
    for arm in sorted(USAGE, key=arm_key):
        if arm in NOGNX:
            continue
        a = USAGE[arm]
        hook = f'{a.get("hook_pre", 0)} / {a.get("hook_enriched", 0)} / {a.get("hook_hint", 0)}' if a.get("hook_calls") else "–"
        rows.append([arm_cell(arm), str(a["runs"]), f'{a["used"]} ({fmt_pct(a["used"] / a["runs"])})', f'{a["calls"] / a["runs"]:.1f}', hook])
    return tbl(["Setup", "Scored runs", "Runs that called GitNexus", "Calls / run", "Search-hook calls / context added / 'use MCP' hint"], rows, "num")


def spend_table(sp, res):
    track_of = {d: n for n, r in res.items() for d in r["_dirs"]}
    agg = defaultdict(lambda: dict(runs=0, cost=0.0))
    for (d, e), v in sp.items():
        k = (track_of.get(d, "not scored"), e)
        agg[k]["runs"] += v["runs"]; agg[k]["cost"] += v["cost"]
    rows = [[html.escape(k[0]), html.escape(k[1]), str(v["runs"]), fmt_money(v["cost"])] for k, v in sorted(agg.items())]
    return tbl(["Track", "Engine", "Runs", "Notional spend"], rows, "num")


# ---- render ------------------------------------------------------------------------------------------------------
def render(res, m, aud, sp, out):
    tables = {}
    for name in ("U", "O", "P2", "HF"):
        if name in res:
            tables[f"{name}.summary"] = change_summary(res[name])
            tables[f"{name}.grid"] = change_grid(res[name])
            tables[f"{name}.paired"] = paired_table(res[name])
            for x in paired(res[name]):
                for k in ("tasks", "better", "worse", "same", "cost_ratio", "turns_ratio", "resolved_g", "resolved_b"):
                    if x[k] is not None:
                        m[f"{name}.pair.{x['g']}.{k}"] = x[k]
    if "P1" in res:
        tables["P1.summary"], tables["P1.detail"] = p1_tables(res["P1"])
    if "P3" in res:
        tables["P3.summary"] = p3_table(res["P3"])
    if "P4" in res:
        tables["P4.summary"] = p4_table(res["P4"])
    if "RV" in res:
        tables["RV.summary"] = rv_table(res["RV"])
    if "HI" in res:
        tables["HI.summary"] = himpact_table(res["HI"])
        tables["HI.toolonly"] = toolonly_table(m)
        a = res["HI"]["arms"]
        for g, b in (("A1f", "A0"), ("A1m", "A0"), ("C1f", "C0")):
            if g in a and b in a:
                m[f"HI.pair.{g}.cost_pct"] = 100 * (a[g]["cost"] / a[b]["cost"] - 1)
                m[f"HI.pair.{g}.wall_pct"] = 100 * (a[g]["wall"] / a[b]["wall"] - 1)
    tables["spend"] = spend_table(sp, res)
    tables["usage"] = usage_table()
    tpl = open(p("report-template.html")).read()

    def sub(mo):
        key, spec = mo.group(1).strip(), (mo.group(2) or "").strip()
        if key.startswith("table:"):
            k = key[6:]
            if k not in tables:
                sys.exit(f"unknown table {k}")
            return tables[k]
        if key not in m:
            sys.exit(f"unknown metric {key}")
        v = m[key]
        if spec == "$":
            return fmt_money(v)
        if spec == "%":
            return fmt_pct(v)
        if spec:
            return format(v, spec)
        return str(v)

    page = re.sub(r"\{\{([^}|]+)(?:\|([^}]*))?\}\}", sub, tpl)
    open(out, "w").write(page)
    json.dump(dict(metrics=m, audit=aud), open(os.path.join(DATA, "metrics.json"), "w"), indent=1, sort_keys=True)


def main():
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else p("..", "report.html")
    global USAGE
    res = collect()
    USAGE = usage(res)
    aud = audit(res)
    sp = spend()
    m = metrics(res, aud, sp)
    if os.path.exists(p("report-template.html")):
        render(res, m, aud, sp, out)
        todo = re.findall(r"TODO-[A-Z0-9-]+", open(out).read())
        print(f"wrote {out}" + (f"  (unfilled: {', '.join(todo)})" if todo else ""))
    else:
        json.dump(dict(metrics=m, audit=aud), open(os.path.join(DATA, "metrics.json"), "w"), indent=1, sort_keys=True)
        print("no template yet; metrics in report-data/metrics.json")
    print(f"contaminated (scored): {len(aud['contaminated_scored'])}  excluded: {len(aud['contaminated_excluded'])}  "
          f"live-in-gnx-arm: {len(aud['live_in_gnx_arm'])}  spend total ${m['spend.total']:.2f} over {m['spend.runs']} runs")


if __name__ == "__main__":
    main()
