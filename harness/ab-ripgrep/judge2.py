#!/usr/bin/env python3
"""Blind grading, round 2: per broad question, 4 anonymous answers (2 trials x 2 arms) of ONE author model.
  codex set: cxA vs cxB (Codex Sol, GitNexus MCP off vs on)  -> graded by Claude Opus 5.5 (cross-model)
  aug set:   augH0 vs augHk (Claude Opus, no hooks vs GitNexus hooks only) -> graded by Codex Sol high (cross-model)
Usage: judge2.py <artifacts_dir> [--build-only]. Writes judge-<set>/<Q>.{prompt.md,map.json,out.md,log}."""
import hashlib, json, os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "common"))
import benchenv  # noqa: E402
A = sys.argv[1]
tasks = {t["id"]: t for t in benchenv.load_tasks(os.path.join(A, "tasks-broad.json"))}
SETS = {
    "codex": (os.path.join(A, "runs-codex", "runs-codex.jsonl"), ("cxA", "cxB")),
    "aug": (os.path.join(A, "runs", "runs-aug.jsonl"), ("augH0", "augHk")),
}
SAFE_PATH = ":".join(benchenv.path_tail())
ENV = {"HOME": os.environ["HOME"], "USER": os.environ["USER"], "LOGNAME": os.environ["USER"], "PATH": SAFE_PATH,
       "LANG": "en_US.UTF-8", "TMPDIR": os.environ.get("TMPDIR", "/var/tmp"), "SHELL": "/bin/zsh", "TERM": "dumb"}


def blind(ans):
    """Drop arm-revealing provenance remarks ("GitNexus alias `x` indexes the same checkout ...") from an answer."""
    ans = re.sub(r"\s*\(GitNexus[^)]*\)", "", ans)
    return re.sub(r"[^.\n]*GitNexus[^.\n]*\.?", "", ans)


def build(name):
    src, arms = SETS[name]
    rows = {}
    for l in open(src):
        r = json.loads(l)
        if r.get("rc") == 0 and (r.get("answer") or "").strip():
            rows[(r["id"], r["arm"])] = r  # last valid row wins
    out = os.path.join(A, f"judge-{name}")
    os.makedirs(out, exist_ok=True)
    jobs = []
    for q in sorted({t["target"] for t in tasks.values()}):
        cells = [(f"{q}t{t}", arm) for arm in arms for t in (1, 2)]
        order = sorted(cells, key=lambda c: hashlib.sha256((name + q + c[0] + c[1]).encode()).hexdigest())
        labels = "ABCD"
        mapping = {labels[i]: {"id": c[0], "arm": c[1]} for i, c in enumerate(order)}
        t0 = tasks[f"{q}t1"]
        question = t0["prompt"].replace(" Answer in at most 400 words. Do not modify any files.", "")
        parts = [
            f"You are grading four anonymous answers to a code-understanding question about the repository at `{t0['cwd']}` "
            "(read it; do not modify anything).\n",
            f"QUESTION: {question}\n",
            "For EACH answer: open the files and line numbers it cites and check its concrete claims and the order of the flow "
            "against the actual source. Then score:\n"
            "- correctness 0-10: 10 = every concrete claim (file, function, line, call order) checks out; deduct for each wrong "
            "or unverifiable claim.\n"
            "- completeness 0-10: 10 = covers every key mechanism or hop a maintainer would expect; deduct for missing ones.\n"
            "List up to 3 concrete errors or omissions per answer. Judge only what is written; do not reward length or style.\n"
            'Output ONLY this JSON, nothing else: {"A":{"correctness":n,"completeness":n,"errors":["..."]},"B":{...},"C":{...},"D":{...}}\n',
        ]
        for lab in labels:
            ans = (rows.get((mapping[lab]["id"], mapping[lab]["arm"])) or {}).get("answer") or "(no answer)"
            parts.append(f"\n===== ANSWER {lab} =====\n{blind(ans).strip()}\n")
        p = os.path.join(out, f"{q}.prompt.md")
        open(p, "w").write("".join(parts))
        json.dump({"cwd": t0["cwd"], "map": mapping}, open(os.path.join(out, f"{q}.map.json"), "w"), indent=1)
        jobs.append((name, q, p, t0["cwd"], out))
    return jobs


def grade(job):
    name, q, p, cwd, out = job
    prompt = open(p).read()
    res, log = os.path.join(out, f"{q}.out.md"), os.path.join(out, f"{q}.log")
    if name == "codex":  # Codex-authored answers -> Claude Opus judge
        cmd = [benchenv.opt("CLAUDE_BIN", "claude"), "-p", prompt, "--model", "claude-opus-5-5", "--effort", "high",
               "--output-format", "text", "--no-session-persistence", "--setting-sources", "local",
               "--settings", '{"disableAllHooks": true}', "--strict-mcp-config", "--tools", "Read,Grep,Glob",
               "--permission-mode", "default", "--max-turns", "80"]
        with open(res, "w") as so, open(log, "w") as se:
            rc = subprocess.run(cmd, cwd=cwd, env=ENV, stdout=so, stderr=se, stdin=subprocess.DEVNULL, timeout=2400).returncode
    else:  # Claude-authored answers -> Codex Sol high judge
        cmd = [benchenv.opt("CODEX_BIN", "codex"), "exec", "-m", "gpt-6.1-sol", "-c", "model_reasoning_effort=high", "--sandbox", "read-only",
               "--skip-git-repo-check", "--ephemeral", "-C", cwd, "-o", res, prompt]
        with open(log, "w") as lf:
            rc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, timeout=2400).returncode
    return f"{name}/{q} rc={rc} bytes={os.path.getsize(res) if os.path.exists(res) else 0}"


jobs = build("codex") + build("aug")
print(len(jobs), "packets built", flush=True)
if "--build-only" not in sys.argv:
    with ThreadPoolExecutor(max_workers=10) as ex:
        for line in ex.map(grade, jobs):
            print(line, flush=True)
