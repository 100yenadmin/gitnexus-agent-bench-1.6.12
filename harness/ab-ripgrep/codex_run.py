#!/usr/bin/env python3
"""Codex A/B: Sol (medium) with our real Codex setup (global Codex home: AGENTS.md + skills), GitNexus MCP off vs on.
Usage: codex_run.py <out_dir> [--jobs N]. Tasks = tasks-broad.json + tasks-impact.json (x2 trials for impact).
Published version: the task files are read from $AB_ARTIFACTS; codex runs with CODEX_HOME_FOR_RUNS (our runs used our
global Codex home, withheld; its config enabled a gitnexus MCP server pointing at our everyday read-only launcher)."""
import json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "common"))
import benchenv  # noqa: E402
HERE = benchenv.need("AB_ARTIFACTS")
CODEX = benchenv.opt("CODEX_BIN", "codex")
_ENV = dict(os.environ, CODEX_HOME=benchenv.opt("CODEX_HOME_FOR_RUNS") or os.environ.get("CODEX_HOME", os.path.expanduser("~/.codex")))
OUT = sys.argv[1]
JOBS = int(sys.argv[sys.argv.index("--jobs") + 1]) if "--jobs" in sys.argv else 6
NOTE_OFF = "Note for this session: GitNexus is not available here; use normal search (rg/git grep) and file reads.\n\n"
PRICE = {"in": 2.0, "cached": 0.10, "out": 10.0}  # gpt-6.1-sol list price, USD per MTok

tasks = benchenv.load_tasks(os.path.join(HERE, "tasks-broad.json"))
for t in benchenv.load_tasks(os.path.join(HERE, "tasks-impact.json")):
    for k in (1, 2):
        tasks.append(dict(t, id=f"{t['id']}t{k}"))
os.makedirs(OUT, exist_ok=True)


def run(task, arm):
    tag = f"{task['id']}__{arm}"
    ev, ans, err = (os.path.join(OUT, tag + x) for x in (".jsonl", ".txt", ".err"))
    cmd = [CODEX, "exec", "-m", "gpt-6.1-sol", "-c", "model_reasoning_effort=medium", "--sandbox", "read-only",
           "--skip-git-repo-check", "--ephemeral", "--json", "-C", task["cwd"], "-o", ans]
    prompt = task["prompt"]
    if arm == "cxA":
        cmd[2:2] = ["-c", "mcp_servers.gitnexus.enabled=false"]  # after "exec" (index 3 split "-m" from its value)
        prompt = NOTE_OFF + prompt
    t0 = time.time()
    try:
        with open(ev, "w") as so, open(err, "w") as se:
            rc = subprocess.run(cmd + [prompt], stdout=so, stderr=se, stdin=subprocess.DEVNULL, timeout=1800, env=_ENV).returncode
    except subprocess.TimeoutExpired:
        rc = "timeout"
    wall = round(time.time() - t0, 1)
    u = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}
    items, mcp = {}, {}
    for line in open(ev, errors="replace"):
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("type") == "turn.completed":
            for k in u:
                u[k] += (e.get("usage") or {}).get(k, 0) or 0
        if e.get("type") == "item.completed":
            it = e.get("item") or {}
            items[it.get("type")] = items.get(it.get("type"), 0) + 1
            if it.get("type") == "mcp_tool_call":
                name = f"{it.get('server')}.{it.get('tool')}"
                mcp[name] = mcp.get(name, 0) + 1
    fresh = u["input_tokens"] - u["cached_input_tokens"]
    cost = (fresh * PRICE["in"] + u["cached_input_tokens"] * PRICE["cached"] + u["output_tokens"] * PRICE["out"]) / 1e6
    answer = open(ans).read() if os.path.exists(ans) else ""
    return {"id": task["id"], "kind": task["kind"], "alias": task["alias"], "target": task["target"], "arm": arm, "rc": rc,
            "wall_s": wall, "usage": u, "cost_usd": round(cost, 4), "items": items, "mcp": mcp, "answer": answer}


ARMS = sys.argv[sys.argv.index("--arms") + 1].split(",") if "--arms" in sys.argv else ["cxA", "cxB"]
jobs = [(t, arm) for t in tasks for arm in ARMS]
with ThreadPoolExecutor(max_workers=JOBS) as ex, open(os.path.join(OUT, "runs-codex.jsonl"), "a") as out:
    for row in ex.map(lambda j: run(*j), jobs):
        out.write(json.dumps(row) + "\n"); out.flush()
        print(f"{row['id']} {row['arm']}: rc={row['rc']} wall={row['wall_s']}s cost=${row['cost_usd']} "
              f"in={row['usage']['input_tokens']} out={row['usage']['output_tokens']} items={row['items']} mcp={row['mcp']}",
              flush=True)
