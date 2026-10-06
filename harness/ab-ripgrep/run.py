#!/usr/bin/env python3
"""A/B: the same headless Claude agent with grep-only tools vs grep + GitNexus MCP.

Usage: run.py <tasks.json> <runs_dir> [--only ID,ID] [--arms rg,gnx] [--jobs N] [--prompt-override TEXT]
Each run writes <runs_dir>/<id>__<arm>.jsonl (stream-json) + .err, and one summary row to runs.jsonl.

Published version: task 'cwd' values may use placeholders (common/benchenv.py, e.g. $AB_REPOS_ROOT).
The MCP config is generated (the original mcp-gitnexus.json pointed at our everyday read-only launcher, which served
one home holding the indexes of all task repos): command = AB_GNX_LAUNCHER (default isolation/launcher-ro.sh), args ["mcp"].
The real*/aug* arms ran with our own user-level setup, which is withheld: real* loaded our user-level Claude settings
(--setting-sources user,...: global instructions, skills, plugins); aug* appended our global instruction file
(OWNER_INSTRUCTIONS_FILE) plus a one-line session note.
"""
import json, os, subprocess, sys, time, argparse
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "common"))
import benchenv  # noqa: E402
GNX_LAUNCHER = benchenv.opt("AB_GNX_LAUNCHER", os.path.join(benchenv.HARNESS, "isolation", "launcher-ro.sh"))
MCP = json.dumps({"mcpServers": {"gitnexus": {"type": "stdio", "command": GNX_LAUNCHER, "args": ["mcp"]}}})
CLAUDE = benchenv.opt("CLAUDE_BIN", "claude")
OWNER_INSTRUCTIONS = benchenv.opt("OWNER_INSTRUCTIONS_FILE",
                                  os.path.join(benchenv.HARNESS, "runner", "owner-instructions.PLACEHOLDER.md"))
ENV = {
    "HOME": os.environ["HOME"], "USER": os.environ["USER"], "LOGNAME": os.environ["USER"],
    "PATH": ":".join(benchenv.path_tail()),
    "LANG": "en_US.UTF-8", "TMPDIR": os.environ.get("TMPDIR", "/var/tmp"), "SHELL": "/bin/zsh", "TERM": "dumb",
}
HINT = ("A GitNexus code-graph index of this repository is available through the `gitnexus` MCP tools: "
        "natural-language and keyword code search (`query`), a symbol's callers/callees (`context`), and change impact "
        "(`impact`). Pass repo=\"{alias}\" on every gitnexus call.")
# Third arm = our standing guidance at the time ("prefer gitnexus code-graph queries over broad grep").
FIRST = (" Prefer the gitnexus tools over Grep/Glob: start with gitnexus (query to find code by description, "
         "context for callers and callees), then use Read/Grep only to confirm or fill gaps.")


REAL_A = ("Note for this session: no code-graph (GitNexus) tools are available here; "
          "answer using Read, Grep and Glob.")


HOOK = os.path.join(benchenv.HARNESS, "isolation", "hook-logger.sh")  # wraps gitnexus-hook.cjs and logs each injected context
# aug-sysprompt-<H0|H2|Hk>.md = our global instruction file + this note (H2: no note). sha256 of the originals are in
# runner/owner-instructions.PLACEHOLDER.md.
AUG_NOTE = {"H0": "Note for this session: no code-graph (GitNexus) tools are available here; answer using Read, Grep and Glob.",
            "H2": None,
            "Hk": "Note for this session: GitNexus code-graph context may be attached automatically to your Grep/Glob searches; "
                  "there are no GitNexus tools to call."}


def aug_sysprompt(kind, runs_dir):
    p = os.path.join(runs_dir, f"aug-sysprompt-{kind}.md")
    if not os.path.exists(p):
        txt = open(OWNER_INSTRUCTIONS).read()
        if AUG_NOTE[kind]:
            txt += "\n\n" + AUG_NOTE[kind] + "\n"
        open(p, "w").write(txt)
    return p
AUG_SETTINGS = json.dumps({"hooks": {
    "PreToolUse": [{"matcher": "Grep|Glob|Bash", "hooks": [{"type": "command", "command": HOOK, "timeout": 20}]}],
    "PostToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": HOOK, "timeout": 20}]}]}})


def cmd_for(task, arm, prompt, runs_dir="."):
    if arm in ("augH0", "augH2", "augHk"):
        # Upstream's recommended "native_augment" integration: MCP + grep auto-enrichment hooks. No user settings
        # (so none of our own hooks run); our global instruction file is carried as an appended system prompt.
        c = [CLAUDE, "-p", prompt, "--model", "claude-opus-5-5", "--effort", "medium",
             "--output-format", "stream-json", "--verbose", "--no-session-persistence",
             "--setting-sources", "project,local", "--strict-mcp-config",
             "--tools", "Read,Grep,Glob,Skill,ToolSearch", "--permission-mode", "default", "--max-turns", "60",
             "--append-system-prompt-file", aug_sysprompt(arm[-2:], runs_dir)]
        if arm == "augH2":
            c += ["--mcp-config", MCP, "--allowedTools", "mcp__gitnexus", "--settings", AUG_SETTINGS]
        if arm == "augHk":  # hooks only: no MCP server in the session, so it cannot hold (lock) the repo DB itself
            c += ["--settings", AUG_SETTINGS]
        return c
    if arm in ("realA", "realB", "realF"):
        # Our REAL setup: user-level CLAUDE.md + skills + plugins (withheld); hooks off (side effects); no subagents.
        c = [CLAUDE, "-p", prompt, "--model", "claude-opus-5-5", "--effort", "medium",
             "--output-format", "stream-json", "--verbose", "--no-session-persistence",
             "--setting-sources", "user,project,local", "--settings", '{"disableAllHooks": true}',
             "--strict-mcp-config", "--tools", "Read,Grep,Glob,Skill,ToolSearch", "--permission-mode", "default",
             "--max-turns", "60"]
        if arm == "realA":
            c += ["--allowedTools", "Skill", "--append-system-prompt", REAL_A]
        else:
            c += ["--mcp-config", MCP, "--allowedTools", "Skill", "mcp__gitnexus"]
            if arm == "realF":  # June-style explicit hint: actually use the graph for this question
                c += ["--append-system-prompt",
                      "For this question, use the GitNexus code-graph tools first (query to find the relevant code, "
                      "context for callers and callees, impact for blast radius) with repo=\"" + task["alias"] + "\", "
                      "then use Read/Grep only to confirm details."]
        return c
    c = [CLAUDE, "-p", prompt, "--model", "claude-opus-5-5", "--effort", "medium",
         "--output-format", "stream-json", "--verbose", "--no-session-persistence",
         "--setting-sources", "local", "--strict-mcp-config", "--tools", "Read,Grep,Glob",
         "--permission-mode", "default", "--max-turns", "40"]
    if arm in ("gnx", "gnxf"):
        hint = HINT.format(alias=task["alias"]) + (FIRST if arm == "gnxf" else "")
        c += ["--mcp-config", MCP, "--allowedTools", "mcp__gitnexus", "--append-system-prompt", hint]
    return c


def parse(stream_path):
    tools, result = {}, None
    with open(stream_path, errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                ev = json.loads(line)
            except Exception:
                continue
            if ev.get("type") == "assistant":
                for b in (ev.get("message") or {}).get("content") or []:
                    if isinstance(b, dict) and b.get("type") == "tool_use":
                        tools[b.get("name")] = tools.get(b.get("name"), 0) + 1
            elif ev.get("type") == "result":
                result = ev
    return tools, result


def run_one(task, arm, runs_dir, prompt=None):
    tag = f"{task['id']}__{arm}"
    sp, ep = os.path.join(runs_dir, tag + ".jsonl"), os.path.join(runs_dir, tag + ".err")
    t0 = time.time()
    try:
        with open(sp, "w") as so, open(ep, "w") as se:
            env = dict(ENV, ENABLE_TOOL_SEARCH="true") if arm.startswith(("real", "aug")) else ENV  # defer MCP schemas like interactive sessions
            if arm in ("augH2", "augHk"):
                env["HOOKLOG_DIR"] = os.path.join(benchenv.opt("AB_ARTIFACTS", runs_dir), "hooklog")
                os.makedirs(env["HOOKLOG_DIR"], exist_ok=True)
                env["GITNEXUS_HOME"] = benchenv.need("AB_AUG_GN_HOME")  # a home registering the task repos' indexes
            rc = subprocess.run(cmd_for(task, arm, prompt or task["prompt"], runs_dir), cwd=task["cwd"], env=env,
                                stdout=so, stderr=se, stdin=subprocess.DEVNULL, timeout=1500).returncode
    except subprocess.TimeoutExpired:
        rc = "timeout"
    wall = round(time.time() - t0, 1)
    tools, res = parse(sp)
    u = (res or {}).get("usage") or {}
    row = {"id": task["id"], "kind": task["kind"], "alias": task["alias"], "target": task["target"], "arm": arm,
           "rc": rc, "wall_s": wall, "is_error": (res or {}).get("is_error"), "subtype": (res or {}).get("subtype"),
           "num_turns": (res or {}).get("num_turns"), "duration_ms": (res or {}).get("duration_ms"),
           "cost_usd": (res or {}).get("total_cost_usd"),
           "in": u.get("input_tokens"), "cache_create": u.get("cache_creation_input_tokens"),
           "cache_read": u.get("cache_read_input_tokens"), "out": u.get("output_tokens"),
           "tools": tools, "answer": (res or {}).get("result")}
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tasks"); ap.add_argument("runs_dir")
    ap.add_argument("--only", default=""); ap.add_argument("--arms", default="rg,gnx")
    ap.add_argument("--jobs", type=int, default=6); ap.add_argument("--prompt-override", default=None)
    ap.add_argument("--summary", default=None)
    a = ap.parse_args()
    tasks = benchenv.load_tasks(a.tasks)
    if a.only:
        keep = set(a.only.split(","))
        tasks = [t for t in tasks if t["id"] in keep]
    arms = a.arms.split(",")
    jobs = [(t, arm) for t in tasks for arm in arms]
    os.makedirs(a.runs_dir, exist_ok=True)
    summary = a.summary or os.path.join(a.runs_dir, "runs.jsonl")
    with ThreadPoolExecutor(max_workers=a.jobs) as ex, open(summary, "a") as out:
        for row in ex.map(lambda j: run_one(j[0], j[1], a.runs_dir, a.prompt_override), jobs):
            out.write(json.dumps(row) + "\n"); out.flush()
            print(f"{row['id']} {row['arm']}: rc={row['rc']} err={row['is_error']} turns={row['num_turns']} "
                  f"wall={row['wall_s']}s cost={row['cost_usd']} tools={row['tools']}", flush=True)


if __name__ == "__main__":
    main()
