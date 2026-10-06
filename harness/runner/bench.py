#!/usr/bin/env python3
"""GitNexus use-case bench: change tasks with hidden oracles, arms x models, parallel isolated runs.

Usage: bench.py <tasks.json> <out_dir> --arms A0,A2 [--trials 2] [--jobs 6] [--only id,id] [--timeout 2700] [--skip-done] [--no-grade]

Each run gets an APFS clone (cp -c) of the task's base checkout (deps + .gitnexus included), registered in the
BENCH GitNexus home under its own alias (= run dir basename). Claude Bash runs inside Claude's sandbox (writes only
inside the run dir and temp); Codex runs with --sandbox workspace-write. Hidden oracle files are staged only after
the agent exits. Results: <out_dir>/results.jsonl (one row per run) + <out_dir>/runs/<run>/{stream.jsonl,patch.diff,...}.

Published version: every local path is read from the environment (harness/config.example.env, common/benchenv.py);
task files may use the $BENCH_ROOT / $BENCH_ARTIFACTS / ... placeholders documented in common/benchenv.py.
"""
import hashlib, json, os, random, re, shutil, string, subprocess, sys, threading, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "common"))
import benchenv  # noqa: E402

ISO = os.path.join(benchenv.HARNESS, "isolation")
BR = benchenv.opt("BENCH_ROOT", "")  # required to run (checked in main); optional when only parse_claude is imported
# Run clones live under a ".noindex" folder (Spotlight skips it) and are discarded by an O(1) rename into .trash;
# deleting a full clone (deps included) took ~4 min per run under load, longer than most probe runs themselves.
CLONES = os.path.join(BR, "clones.noindex")
NO_GRADE = False


def discard(path):
    if not os.path.exists(path):
        return
    trash = os.path.join(CLONES, ".trash")
    os.makedirs(trash, exist_ok=True)
    try:
        os.rename(path, os.path.join(trash, f"{os.path.basename(path)}-{time.time_ns()}"))
    except OSError:
        shutil.rmtree(path, ignore_errors=True)
HOME_GN = f"{BR}/home"
ADMIN = f"{ISO}/bench-admin.sh"
LAUNCH_RUN = f"{ISO}/launcher-run.sh"   # per-run home via BENCH_GN_HOME; BENCH_GN_RO=1 = read-only MCP (our day-to-day setup)
SHIM_DIR = f"{ISO}/shim"
NOGNX_DIR = f"{ISO}/nognx"  # shadows any user-level `gitnexus` on PATH (ours pointed at our full index estate) for no-GitNexus arms
RUNNER = f"{ISO}/run.cjs"
HOOK = f"{ISO}/hook-logger.sh"
CLAUDE = benchenv.opt("CLAUDE_BIN", "claude")
CODEX = benchenv.opt("CODEX_BIN", "codex")
PKG = benchenv.opt("GITNEXUS_PKG")
# Arms with sys="owner*" append our private global agent instruction file (withheld; see runner/owner-instructions.PLACEHOLDER.md).
OWNER_INSTRUCTIONS = benchenv.opt("OWNER_INSTRUCTIONS_FILE", os.path.join(HERE, "owner-instructions.PLACEHOLDER.md"))
# Arms with skills="owner" (A1, A1f, A1m) copied the gitnexus-* skills from our user-level skills dir (withheld).
OWNER_SKILLS = benchenv.opt("OWNER_SKILLS_DIR")
OPUS, HAIKU, SOL = "claude-opus-5-5", "claude-haiku-4-5-20251001", "gpt-6.1-sol"
SOL_PRICE = {"in": 2.0, "cached": 0.10, "out": 10.0}  # USD / MTok

# Upstream eval/workflow_bench/runner.py prompts, verbatim.
HEADLESS_VERIFY = (" Verification must be observed inside this session: run the typecheck and test commands in the "
                   "foreground to completion and report their actual output — never background them or wait on "
                   "scheduled wakeups.")
BASELINE_PROMPT = ("{task}\n\nImplement the change in this repository and verify it by running the relevant tests. "
                   "Work autonomously without asking questions.")
WORK_DIRECT_PROMPT = ("Use the gitnexus-work skill for: {task}\nHeadless run: proceed without asking. The user explicitly "
                      "declines a separate planning pass — execute in direct mode with the skill's execution discipline."
                      + HEADLESS_VERIFY)
# Hermes large-repo test (2026-10-06): GitNexus's best case, so the GitNexus arm is told to use the graph.
GNX_FIRST_NOTE = ("\n\nThe GitNexus code knowledge graph for this repository is available through the gitnexus MCP tools. "
                  "Use it before editing or answering: run `context` on the symbols involved and `impact` (upstream) on "
                  "every symbol you change or are asked about, and use the results to find all affected call sites. "
                  "You may verify with normal search and file reads.")
GNX_MUST_NOTE = ("\n\nYou MUST use the GitNexus code knowledge graph (the mcp__gitnexus__* tools) for this task. "
                 "Before you search files or answer, call mcp__gitnexus__context and mcp__gitnexus__impact "
                 "(direction \"upstream\") on the target symbol and on every symbol you change. Start your answer from "
                 "those results, then verify each location with file reads or search and add anything the graph missed. "
                 "An answer produced without calling mcp__gitnexus__impact is invalid.")
# Upstream REVIEW_PROMPT / REVIEW_OUTPUT_CONTRACT, verbatim except the output path (inside the run dir here).
REVIEW_OUTPUT_CONTRACT = ("\nWrite {out} as UTF-8 JSON with exactly this shape:\n"
    '{{"schema_version":1,"verdict":"approve|comment|request_changes","findings":[{{\n'
    '"id":"unique stable id","severity":"critical|high|medium|low",\n'
    '"path":"repository-relative changed file","line":1,"end_line":1,\n'
    '"category":"correctness|security|compatibility|performance|tests|other",\n'
    '"scenario":"specific failure scenario","evidence":"concrete code/graph evidence",\n'
    '"recommendation":"bounded fix","blocking":true}}]}}\n'
    "Use an empty findings list with verdict approve when there are no actionable\n"
    "defects. Do not emit Markdown and do not edit any other file.\n")
REVIEW_GNX_PROMPT = ("Use the gitnexus-review skill to review the local uncommitted changes in this repository. {task}\n"
                     "Headless run: proceed without asking; do not post to GitHub or anywhere external.")
REVIEW_PLAIN_PROMPT = ("Review the local uncommitted changes in this repository. {task}\n"
                       "Headless run: proceed without asking; do not post to GitHub or anywhere external.")
NOTE_OFF = "Note for this session: GitNexus is not available here; use normal search (rg/git grep) and file reads.\n\n"

GNX_RO = ["list_repos", "query", "context", "check", "impact", "explain", "pdg_query", "route_map", "tool_map",
          "shape_check", "api_impact", "trace", "detect_changes"]
BUILTIN = ["Read", "Grep", "Glob", "Edit", "Write", "Bash", "Skill"]

# engine, model, mcp (None|ro|rw), skills (deny|none|owner|upstream), prompt, sysprompt (none|owner|owner+block), hooks
ARMS = {
    # Track U: upstream workflow_bench arm definitions (bare-like: no owner instructions, repo files as shipped).
    "U_nomcp":  dict(engine="claude", model=OPUS, mcp=None, skills="deny", prompt="baseline", sys="none", hooks=False),
    "U_mcp":    dict(engine="claude", model=OPUS, mcp="rw", skills="deny", prompt="baseline", sys="none", hooks=False),
    "U_direct": dict(engine="claude", model=OPUS, mcp="rw", skills="repo", prompt="work_direct", sys="none", hooks=False),
    # Review track (upstream review cases): plain review vs upstream's gitnexus-review arm; Codex at high effort (our usual review effort).
    "R_plain": dict(engine="claude", model=OPUS, mcp=None, skills="none", prompt="review_plain", sys="none", hooks=False),
    "R_gnx":   dict(engine="claude", model=OPUS, mcp="rw", skills="upstream", prompt="review_gnx", sys="none", hooks=False),
    "CR0": dict(engine="codex", model=SOL, mcp=None, skills="none", prompt="review_plain", sys="off", hooks=False, effort="high"),
    "CR1": dict(engine="codex", model=SOL, mcp="ro", skills="none", prompt="review_plain", sys="", hooks=False, effort="high"),
    "S_mcp":    dict(engine="claude", model=HAIKU, mcp="rw", skills="deny", prompt="baseline", sys="none", hooks=True),  # harness smoke
    # Track O: our day-to-day environment (A0/A1/C0/C1) vs upstream's full integration (A2/A3/H2/C2).
    "A0": dict(engine="claude", model=OPUS, mcp=None, skills="none", prompt="baseline", sys="owner_off", hooks=False),
    "A1": dict(engine="claude", model=OPUS, mcp="ro", skills="owner", prompt="baseline", sys="owner", hooks=False),
    "A2": dict(engine="claude", model=OPUS, mcp="rw", skills="upstream", prompt="baseline", sys="owner_block", hooks=True),
    "A3": dict(engine="claude", model=OPUS, mcp="rw", skills="upstream", prompt="work_direct", sys="owner_block", hooks=True),
    "H0": dict(engine="claude", model=HAIKU, mcp=None, skills="none", prompt="baseline", sys="owner_off", hooks=False),
    "H2": dict(engine="claude", model=HAIKU, mcp="rw", skills="upstream", prompt="baseline", sys="owner_block", hooks=True),
    "C0": dict(engine="codex", model=SOL, mcp=None, skills="none", prompt="baseline", sys="off", hooks=False),
    "C1": dict(engine="codex", model=SOL, mcp="ro", skills="none", prompt="baseline", sys="", hooks=False),
    "C2": dict(engine="codex", model=SOL, mcp="rw", skills="upstream", prompt="baseline", sys="block", hooks=False),
    # Hermes large-repo test: read-only MCP plus an explicit instruction to use impact/context first.
    "A1f": dict(engine="claude", model=OPUS, mcp="ro", skills="owner", prompt="gnx_first", sys="owner", hooks=False),
    "C1f": dict(engine="codex", model=SOL, mcp="ro", skills="none", prompt="gnx_first", sys="", hooks=False),
    "A1m": dict(engine="claude", model=OPUS, mcp="ro", skills="owner", prompt="gnx_must", sys="owner", hooks=False),
}
REG_LOCK = threading.Lock()


def sh(cmd, cwd=None, timeout=600, env=None):
    p = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str), capture_output=True, text=True, timeout=timeout,
                       env=env, stdin=subprocess.DEVNULL)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def upstream_block(alias):
    """The AGENTS.md/CLAUDE.md block `gitnexus analyze` writes, rendered from upstream's template for this alias."""
    tpl = open(os.path.join(HERE, "upstream-block.md")).read()
    return tpl.replace("{{ALIAS}}", alias)


def install_skills(rundir, kind, engine):
    dst = os.path.join(rundir, ".agents/skills" if engine == "codex" else ".claude/skills")
    if kind == "owner":
        if not OWNER_SKILLS:
            raise SystemExit("arm needs OWNER_SKILLS_DIR (a dir of gitnexus-* skill dirs; ours is withheld, see README)")
        for n in sorted(os.listdir(OWNER_SKILLS)):
            if n.startswith("gitnexus"):
                shutil.copytree(os.path.join(OWNER_SKILLS, n), os.path.join(dst, n), symlinks=False, dirs_exist_ok=True)
    elif kind == "upstream":  # what `gitnexus analyze` installs: <pkg>/skills/<x>.md -> <x>/SKILL.md, dirs copied
        src = os.path.join(benchenv.need("GITNEXUS_PKG"), "skills")
        for n in sorted(os.listdir(src)):
            p = os.path.join(src, n)
            if n.endswith(".md"):
                os.makedirs(os.path.join(dst, n[:-3]), exist_ok=True)
                shutil.copy(p, os.path.join(dst, n[:-3], "SKILL.md"))
            elif os.path.isdir(p):
                shutil.copytree(p, os.path.join(dst, n), dirs_exist_ok=True)
    # A repo that tracks its own copies (the GitNexus repo ships .claude/skills/gitnexus-*) keeps them: restore any
    # tracked file the install overwrote, so the checkout stays clean and the repo's versions win.
    rel_dst = os.path.relpath(dst, rundir)
    if sh(["git", "-C", rundir, "ls-files", "--", rel_dst])[1].strip():
        sh(["git", "-C", rundir, "checkout", "--", rel_dst])
    with open(os.path.join(rundir, ".git/info/exclude"), "a") as f:
        f.write("\n.claude/skills/\n.agents/skills/\n.wfbench-oracle-*/\n.bench-tmp/\n.bench-review/\n")


def parse_claude(stream):
    # A background Bash task can re-invoke the session, so one stream may hold several result events: num_turns is
    # per invocation (summed), total_cost_usd is cumulative (last wins). gnx_cli counts GitNexus CLI use via Bash.
    tools, skills, res, gnx, turns, gnx_cli = {}, [], None, 0, 0, 0
    for line in open(stream, errors="replace"):
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("type") == "assistant":
            for c in (e.get("message") or {}).get("content") or []:
                if c.get("type") == "tool_use":
                    tools[c["name"]] = tools.get(c["name"], 0) + 1
                    if c["name"] == "Skill":
                        skills.append((c.get("input") or {}).get("skill") or (c.get("input") or {}).get("command"))
                    if c["name"].startswith("mcp__gitnexus"):
                        gnx += 1
                    if c["name"] == "Bash" and re.search(
                            r"(?:^|\n|[;&|(`]\s*|\btimeout\s+\d+\s+|\bnpx\s+(?:--yes\s+|-y\s+)?)\s*gitnexus(?:\s|$)|node\s+\S*\.gitnexus/run\.cjs",
                            str((c.get("input") or {}).get("command") or "")):  # command position only, not `cd gitnexus`
                        gnx_cli += 1
        elif e.get("type") == "result":
            res = e
            turns += e.get("num_turns") or 0
    r = res or {}
    u = r.get("usage") or {}
    return dict(cost_usd=r.get("total_cost_usd"), turns=turns or None, is_error=r.get("is_error"),
                subtype=r.get("subtype"), result=(r.get("result") or "")[:3000],
                tok={"in": u.get("input_tokens"), "cache_create": u.get("cache_creation_input_tokens"),
                     "cache_read": u.get("cache_read_input_tokens"), "out": u.get("output_tokens")},
                tools=tools, skills=skills, gnx_calls=gnx, gnx_cli=gnx_cli)


def parse_codex(stream, ans):
    u = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}
    items, mcp, turns = {}, {}, 0
    for line in open(stream, errors="replace"):
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("type") == "turn.completed":
            turns += 1
            for k in u:
                u[k] += (e.get("usage") or {}).get(k, 0) or 0
        if e.get("type") == "item.completed":
            it = e.get("item") or {}
            items[it.get("type")] = items.get(it.get("type"), 0) + 1
            if it.get("type") == "mcp_tool_call":
                n = f"{it.get('server')}.{it.get('tool')}"
                mcp[n] = mcp.get(n, 0) + 1
    fresh = u["input_tokens"] - u["cached_input_tokens"]
    cost = (fresh * SOL_PRICE["in"] + u["cached_input_tokens"] * SOL_PRICE["cached"] + u["output_tokens"] * SOL_PRICE["out"]) / 1e6
    return dict(cost_usd=round(cost, 4), turns=turns, is_error=False, subtype="", tools=items, skills=[],
                result=(open(ans).read() if os.path.exists(ans) else "")[:3000],
                tok={"in": u["input_tokens"], "cache_read": u["cached_input_tokens"], "out": u["output_tokens"]},
                gnx_calls=sum(v for k, v in mcp.items() if k.startswith("gitnexus.")), mcp=mcp)


def release_db(rundir, wait=45):
    """Wait for processes holding this run's graph DB (e.g. a lingering MCP server) to exit; then kill those PIDs."""
    db = os.path.join(rundir, ".gitnexus", "lbug")
    if not os.path.exists(db):
        return []
    for _ in range(wait):
        pids = [x for x in sh(["/usr/sbin/lsof", "-t", db])[1].split() if x.isdigit()]
        if not pids:
            return []
        time.sleep(1)
    for pid in pids:  # exactly the holders of THIS run's DB file, never a substring match
        sh(["kill", pid])
    return pids


def hook_stats(hookdir):
    st = {"calls": 0, "enriched": 0, "fallback": 0, "empty": 0}
    p = os.path.join(hookdir, "hook-calls.log")
    if os.path.exists(p):
        for line in open(p, errors="replace"):
            f = line.rstrip("\n").split("\t")
            ctx = f[5] if len(f) > 5 else ""
            st["calls"] += 1
            st["empty" if not ctx.strip() else ("fallback" if "unavailable" in ctx.lower() else "enriched")] += 1
    return st


def run_one(task, arm, trial, out, timeout):
    a = ARMS[arm]
    name = re.sub(r"[^A-Za-z0-9._-]", "-", f"{task['id']}-{arm}-t{trial}")
    outer = os.path.join(out, "runs", name)
    rundir = os.path.join(CLONES, hashlib.sha1(os.path.abspath(outer).encode()).hexdigest()[:8], name)  # basename = alias
    row = dict(run=name, task=task["id"], track=task.get("track"), cls=task.get("class"), arm=arm, engine=a["engine"],
               model=a["model"], trial=trial)
    if os.path.exists(outer):
        shutil.rmtree(outer)
    os.makedirs(outer)
    discard(rundir)
    os.makedirs(os.path.dirname(rundir), exist_ok=True)
    hookdir = os.path.join(outer, "hooklog")
    os.makedirs(hookdir)
    # Short temp root: tools like tsx put Unix sockets under TMPDIR, and macOS caps socket paths at 104 bytes.
    tmp = os.path.join(os.environ.get("TMPDIR", "/var/tmp"), "gnb", hashlib.sha1(name.encode()).hexdigest()[:10])
    shutil.rmtree(tmp, ignore_errors=True)
    rc, o = sh(["cp", "-cR", task["base"], rundir], timeout=1800)
    if rc:
        row.update(error="clone: " + o[-300:]); return row
    os.makedirs(tmp, exist_ok=True)
    base_sha = sh(["git", "-C", rundir, "rev-parse", "HEAD"])[1].strip()
    if a["skills"] in ("owner", "upstream"):
        install_skills(rundir, a["skills"], a["engine"])
    else:
        with open(os.path.join(rundir, ".git/info/exclude"), "a") as f:
            f.write("\n.wfbench-oracle-*/\n.bench-tmp/\n.bench-review/\n")
    runhome = os.path.join(outer, "gnhome")
    gnx_arm = bool(a["mcp"] or a["hooks"])
    if not gnx_arm:
        # No-GitNexus arms get no index at all: in the GitNexus repo `npx gitnexus` runs the repo's own CLI, and any
        # GitNexus CLI could re-register a present .gitnexus; GITNEXUS_HOME below points at an empty home.
        shutil.rmtree(os.path.join(rundir, ".gitnexus"), ignore_errors=True)
    if os.path.isdir(os.path.join(rundir, ".gitnexus")):
        # One registry per run: list_repos/detect_changes can only ever reach this run's own checkout.
        os.makedirs(runhome)
        for fn in ("gitnexus.json", "meta.json"):  # the APFS copy still names the base checkout as its owner
            mp = os.path.join(rundir, ".gitnexus", fn)
            if os.path.exists(mp):
                md = json.load(open(mp))
                md["repoPath"], md["storagePath"] = rundir, os.path.join(rundir, ".gitnexus")
                with open(mp, "w") as f:
                    json.dump(md, f)
        rc, o = sh([ADMIN, "index", rundir], timeout=600,
                   env={"HOME": os.environ["HOME"], "PATH": "/usr/bin:/bin", "BENCH_GN_HOME": runhome})
        reg = json.load(open(os.path.join(runhome, "registry.json"))) if os.path.exists(os.path.join(runhome, "registry.json")) else []
        if rc or len(reg) != 1 or os.path.realpath(reg[0].get("path", "")) != os.path.realpath(rundir):
            row.update(error=f"index rc={rc} reg={reg} " + o[-300:]); return row
        row["alias"] = reg[0]["name"]
        if a["mcp"] or a["hooks"]:
            with open(os.path.join(rundir, ".gitnexus", "run.cjs"), "w") as rf:  # launcher path filled in at copy time
                rf.write(open(RUNNER).read().replace("__LAUNCH_RUN__", json.dumps(LAUNCH_RUN)))
        elif os.path.exists(os.path.join(rundir, ".gitnexus", "run.cjs")):
            os.remove(os.path.join(rundir, ".gitnexus", "run.cjs"))
    st = sh(["git", "-C", rundir, "status", "--porcelain"])[1].strip()
    if st:
        row.update(error="dirty-before-run: " + st[:300]); return row
    alias = row.get("alias", name)
    if task.get("pre_run_cmd"):  # e.g. apply the PR under review as local uncommitted changes
        prc, po = sh(task["pre_run_cmd"], cwd=rundir, timeout=600)
        if prc:
            row.update(error="pre_run: " + po[-300:]); return row
    review_out = os.path.join(rundir, ".bench-review", "review-output.json")
    if task.get("kind") == "qa":  # question probes: the answer is a JSON file, graded offline against ground truth
        review_out = os.path.join(rundir, ".bench-review", "answer.json")
        os.makedirs(os.path.dirname(review_out), exist_ok=True)
        prompt = task["task"]
    elif task.get("kind") == "review":
        os.makedirs(os.path.dirname(review_out), exist_ok=True)
        tpl = REVIEW_GNX_PROMPT if a["prompt"] == "review_gnx" else REVIEW_PLAIN_PROMPT
        prompt = tpl.format(task=task["task"]) + REVIEW_OUTPUT_CONTRACT.format(out=".bench-review/review-output.json")
    else:
        prompt = (WORK_DIRECT_PROMPT if a["prompt"] == "work_direct" else BASELINE_PROMPT).format(task=task["task"])
    if a["prompt"] == "gnx_first":
        prompt += GNX_FIRST_NOTE
    elif a["prompt"] == "gnx_must":
        prompt += GNX_MUST_NOTE
    path = ":".join(([SHIM_DIR] if a["mcp"] else [NOGNX_DIR]) + task.get("path_prefix", []) + benchenv.path_tail())
    env = {"HOME": os.environ["HOME"], "USER": os.environ["USER"], "LOGNAME": os.environ["USER"], "PATH": path,
           "LANG": "en_US.UTF-8", "TERM": "dumb", "SHELL": "/bin/zsh", "TMPDIR": tmp,
           "XDG_CACHE_HOME": f"{tmp}/xdg", "UV_CACHE_DIR": f"{tmp}/uv", "npm_config_cache": f"{tmp}/npm",
           "HOOKLOG_DIR": hookdir}
    if a["mcp"] or a["hooks"]:
        env.update(GITNEXUS_HOME=runhome, BENCH_GN_HOME=runhome, BENCH_GN_RO="1" if a["mcp"] == "ro" else "")
    else:  # an empty registry for any GitNexus CLI the agent reaches (npx, repo build): never the live estate
        os.makedirs(os.path.join(tmp, "gnx-empty"), exist_ok=True)
        env.update(GITNEXUS_HOME=os.path.join(tmp, "gnx-empty"))
    # npm's global prefix on our machine held a user-level gitnexus wrapper (it forces our full index home), and
    # `npx gitnexus` resolves global bins before downloading. Each run gets its own prefix whose only global
    # `gitnexus` is this arm's entry point: the per-run shim (GitNexus arms) or the not-found stub (others).
    os.makedirs(os.path.join(tmp, "npm-prefix", "bin"), exist_ok=True)
    os.symlink(os.path.join(SHIM_DIR if (a["mcp"] or a["hooks"]) else NOGNX_DIR, "gitnexus"),
               os.path.join(tmp, "npm-prefix", "bin", "gitnexus"))
    env.update(npm_config_prefix=os.path.join(tmp, "npm-prefix"))
    # Per-run placeholders: {TMP} = this run's temp root, {RUNDIR} = its checkout.
    env.update({k: str(v).replace("{TMP}", tmp).replace("{RUNDIR}", rundir) for k, v in task.get("env", {}).items()})
    stream, err, ans = (os.path.join(outer, x) for x in ("stream.jsonl", "stderr.log", "answer.md"))
    sysfile = None
    if a["engine"] == "claude":
        parts = []
        if a["sys"].startswith("owner") and task.get("owner_md", True):
            parts.append(open(OWNER_INSTRUCTIONS).read())
        if a["sys"] == "owner_off":
            parts.append(NOTE_OFF.strip())
        if a["sys"] == "owner_block":
            parts.append(upstream_block(alias))
        if parts:
            sysfile = os.path.join(outer, "sysprompt.md")
            open(sysfile, "w").write("\n\n".join(parts))
        tools = list(BUILTIN)
        if a["mcp"]:
            tools += [f"mcp__gitnexus__{t}" for t in GNX_RO] + (["mcp__gitnexus__rename"] if a["mcp"] == "rw" else [])
        settings = {"sandbox": {"enabled": True, "autoAllowBashIfSandboxed": True, "allowUnsandboxedCommands": False}}
        # The Bash sandbox does not cover the file tools: scope Write/Edit to the run dir (a Haiku run wrote its answer
        # file outside its run dir on 2026-10-05; batches started before 16:25Z ran with unscoped Write/Edit).
        allowed = [f"{t}(./**)" if t in ("Edit", "Write") else t for t in tools]
        if a["hooks"]:
            settings["hooks"] = {
                "PreToolUse": [{"matcher": "Grep|Glob|Bash", "hooks": [{"type": "command", "command": HOOK, "timeout": 20}]}],
                "PostToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": HOOK, "timeout": 20}]}]}
        mcp = ({"mcpServers": {"gitnexus": {"type": "stdio", "command": LAUNCH_RUN, "args": ["mcp"],
                                            "env": {"BENCH_GN_HOME": runhome, "BENCH_GN_RO": env["BENCH_GN_RO"]}}}}
               if a["mcp"] else {"mcpServers": {}})
        cmd = [CLAUDE, "-p", prompt, "--model", a["model"], "--effort", "medium", "--output-format", "stream-json",
               "--verbose", "--no-session-persistence", "--setting-sources", "project,local", "--strict-mcp-config",
               "--mcp-config", json.dumps(mcp), "--settings", json.dumps(settings), "--permission-mode", "dontAsk",
               "--tools", *tools, "--allowedTools", *allowed]
        if a["skills"] == "deny":
            cmd += ["--disallowedTools", "Skill"]
        if sysfile:
            cmd += ["--append-system-prompt-file", sysfile]
    else:
        p = prompt
        if a["sys"] == "off":
            p = NOTE_OFF + p
        elif a["sys"] == "block":
            p = "Repository instructions (from this repo's AGENTS.md):\n\n" + upstream_block(alias) + "\n\n---\n\n" + p
        cmd = [CODEX, "exec", "-m", a["model"], "-c", f"model_reasoning_effort={a.get('effort', 'medium')}", "--sandbox", "workspace-write",
               "--skip-git-repo-check", "--ephemeral", "--json", "-C", rundir, "-o", ans]
        if a["mcp"]:
            # enabled=true explicitly: the Codex home used for the runs may disable the gitnexus server by default.
            cmd[2:2] = ["-c", "mcp_servers.gitnexus.enabled=true", "-c", f'mcp_servers.gitnexus.command="{LAUNCH_RUN}"',
                        "-c", f'mcp_servers.gitnexus.env.BENCH_GN_HOME="{runhome}"',
                        "-c", f'mcp_servers.gitnexus.env.BENCH_GN_RO="{env["BENCH_GN_RO"]}"']
        else:
            cmd[2:2] = ["-c", "mcp_servers.gitnexus.enabled=false"]
        cmd.append(p)
        env["PATH"] = env["PATH"]  # codex resolves itself from PATH
        # Our Codex runs used our global Codex home (its AGENTS.md, skills and memories; withheld). Point
        # CODEX_HOME_FOR_RUNS at a home with only auth/config to approximate a clean setup.
        env["CODEX_HOME"] = benchenv.opt("CODEX_HOME_FOR_RUNS") or os.environ.get("CODEX_HOME", os.path.expanduser("~/.codex"))
    open(os.path.join(outer, "cmd.json"), "w").write(json.dumps({"cmd": cmd[:3] + ["<prompt>"] + cmd[4:] if a["engine"] == "claude" else cmd[:-1] + ["<prompt>"], "env": {k: v for k, v in env.items()}}, indent=1))
    t0 = time.time()
    try:
        with open(stream, "w") as so, open(err, "w") as se:
            rc = subprocess.run(cmd, cwd=rundir, env=env, stdout=so, stderr=se, stdin=subprocess.DEVNULL,
                                timeout=timeout).returncode
    except subprocess.TimeoutExpired:
        rc = "timeout"
    row["wall_s"] = round(time.time() - t0, 1)
    row["rc"] = rc
    row.update(parse_claude(stream) if a["engine"] == "claude" else parse_codex(stream, ans))
    row["hooks"] = hook_stats(hookdir)
    if task.get("kind") in ("review", "qa"):
        row["review_output"] = os.path.exists(review_out)
        if row["review_output"]:
            shutil.copy(review_out, os.path.join(outer, "qa-answer.json" if task["kind"] == "qa" else "review-output.json"))
        row["edited_files"] = len([l for l in sh(["git", "-C", rundir, "status", "--porcelain"])[1].splitlines()])
        if not os.environ.get("BENCH_KEEP"):
            discard(rundir); shutil.rmtree(runhome, ignore_errors=True)
        shutil.rmtree(tmp, ignore_errors=True)
        return row
    # Candidate patch vs the task base (committed + uncommitted + untracked, excluding bench/skill/index files).
    sh(["git", "-C", rundir, "add", "-A"])
    _, patch = sh(["git", "-C", rundir, "diff", "--cached", "--binary", base_sha])
    open(os.path.join(outer, "patch.diff"), "w").write(patch)
    _, ns = sh(["git", "-C", rundir, "diff", "--cached", "--numstat", base_sha])
    files = [l.split("\t") for l in ns.splitlines() if l.count("\t") >= 2]
    row["churn"] = {"files": len(files), "ins": sum(int(f[0]) for f in files if f[0].isdigit()),
                    "del": sum(int(f[1]) for f in files if f[1].isdigit())}
    row["commits"] = int(sh(["git", "-C", rundir, "rev-list", "--count", f"{base_sha}..HEAD"])[1].strip() or 0)
    row["db_holders_killed"] = release_db(rundir)
    if NO_GRADE:  # graded later by regrade.py from the saved patch on a fresh copy
        discard(rundir)
        shutil.rmtree(runhome, ignore_errors=True)
        shutil.rmtree(tmp, ignore_errors=True)
        return row
    # Hidden oracle, staged only now.
    ora = task["oracle"]
    odir = os.path.join(rundir, ".wfbench-oracle-" + "".join(random.choice(string.ascii_lowercase) for _ in range(8)))
    for f in ora["files"]:
        dst = f["dst"].replace("{ORACLE_DIR}", odir)
        dst = dst if os.path.isabs(dst) else os.path.join(rundir, dst)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy(f["src"], dst)
    oenv = dict(env, GITNEXUS_BENCH_ORACLE_ROOT=odir, TMPDIR=tmp, GITNEXUS_HOME=runhome)
    t1 = time.time()
    try:
        orc, oout = sh(ora["cmd"], cwd=rundir, timeout=ora.get("timeout", 900), env=oenv)
    except subprocess.TimeoutExpired:
        orc, oout = "timeout", ""
    row["oracle"] = {"pass": orc == 0, "rc": orc, "secs": round(time.time() - t1, 1)}
    open(os.path.join(outer, "oracle.log"), "w").write(oout[-20000:])
    if task.get("regression"):
        try:
            rrc, rout = sh(task["regression"]["cmd"], cwd=rundir, timeout=task["regression"].get("timeout", 1200), env=oenv)
        except subprocess.TimeoutExpired:
            rrc, rout = "timeout", ""
        row["regression"] = {"pass": rrc == 0, "rc": rrc}
        open(os.path.join(outer, "regression.log"), "w").write(rout[-20000:])
    if not os.environ.get("BENCH_KEEP"):
        discard(rundir)
        shutil.rmtree(runhome, ignore_errors=True)
    shutil.rmtree(tmp, ignore_errors=True)
    return row


def main():
    benchenv.need("BENCH_ROOT")
    tasks_path, out = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])  # runs cd into clones; keep paths absolute
    opt = lambda k, d=None: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
    arms = opt("--arms").split(",")
    trials = int(opt("--trials", "1"))
    jobs = int(opt("--jobs", "4"))
    timeout = int(opt("--timeout", "2700"))
    only = set(opt("--only", "").split(",")) - {""}
    global NO_GRADE
    NO_GRADE = "--no-grade" in sys.argv
    tasks = [t for t in benchenv.load_tasks(tasks_path) if not only or t["id"] in only]
    os.makedirs(os.path.join(out, "runs"), exist_ok=True)
    jobs_list = [(t, arm, k) for k in range(1, trials + 1) for t in tasks for arm in arms]
    if "--skip-done" in sys.argv and os.path.exists(os.path.join(out, "results.jsonl")):
        done = {r["run"] for r in map(json.loads, open(os.path.join(out, "results.jsonl"))) if "error" not in r}
        jobs_list = [j for j in jobs_list if re.sub(r"[^A-Za-z0-9._-]", "-", f"{j[0]['id']}-{j[1]}-t{j[2]}") not in done]
        print(f"skip-done: {len(done)} done, {len(jobs_list)} to run", flush=True)
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=jobs) as ex, open(os.path.join(out, "results.jsonl"), "a") as rf:
        def go(j):
            for attempt in range(4):
                try:
                    row = run_one(*j, out, timeout)
                except Exception as e:  # keep the batch alive; the row records the failure
                    row = dict(run=f"{j[0]['id']}-{j[1]}-t{j[2]}", task=j[0]["id"], arm=j[1], trial=j[2], error=repr(e)[:500])
                # Codex "model is at capacity" kills the turn mid-run: rerun from a fresh clone (run_one resets the run dir).
                st = os.path.join(out, "runs", row["run"], "stream.jsonl")
                if (attempt < 3 and row.get("engine") == "codex" and os.path.exists(st)
                        and "Selected model is at capacity" in open(st, errors="replace").read()):
                    time.sleep(120)
                    continue
                break
            row["capacity_retries"] = attempt
            with lock:
                rf.write(json.dumps(row) + "\n"); rf.flush()
                print(f"{row['run']}: rc={row.get('rc')} err={row.get('error','')[:80]} oracle={row.get('oracle',{}).get('pass')} "
                      f"cost={row.get('cost_usd')} turns={row.get('turns')} wall={row.get('wall_s')} gnx={row.get('gnx_calls')} "
                      f"skills={row.get('skills')} hooks={row.get('hooks')} churn={row.get('churn')}", flush=True)
        list(ex.map(go, jobs_list))


if __name__ == "__main__":
    main()
