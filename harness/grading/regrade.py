#!/usr/bin/env python3
"""Deterministic grading from saved patches: apply each run's patch.diff to a fresh APFS copy of its task base
(index rebound + registered in a private home, no live processes), then run the hidden oracle and the regression
command. Usage: regrade.py <tasks.json> <runs_dir> [--jobs 4] [--only-missing] [--only task,task]. Writes <runs_dir>/regrade.jsonl.
"""
import hashlib, json, os, random, shutil, string, subprocess, sys, threading, re, shlex
from concurrent.futures import ThreadPoolExecutor

_H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_H, "common"))
import benchenv  # noqa: E402

ADMIN = os.path.join(_H, "isolation", "bench-admin.sh")
SCRATCH = os.path.join(benchenv.need("BENCH_ROOT"), "regrade")


def sh(cmd, cwd=None, timeout=900, env=None):
    try:
        p = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str), capture_output=True, text=True, timeout=timeout,
                           env=env, stdin=subprocess.DEVNULL)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired as e:
        return "timeout", str(e)[-300:]


def grade(task, row, runs_dir):
    name = row["run"]
    patch = os.path.join(runs_dir, "runs", name, "patch.diff")
    out = {"run": name, "task": row["task"], "arm": row["arm"], "trial": row.get("trial")}
    if not os.path.exists(patch):
        out["error"] = "no patch"; return out
    work = os.path.join(SCRATCH, hashlib.sha1(name.encode()).hexdigest()[:12])
    home, repo = work + "-home", os.path.join(work, "repo")
    shutil.rmtree(work, ignore_errors=True); shutil.rmtree(home, ignore_errors=True)
    os.makedirs(work); os.makedirs(home)
    tmp = os.path.join(os.environ.get("TMPDIR", "/var/tmp"), "gnr", hashlib.sha1(name.encode()).hexdigest()[:10])
    shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
    try:
        rc, o = sh(["cp", "-cR", task["base"], repo], timeout=1800)
        if rc:
            out["error"] = "copy " + o[-200:]; return out
        for fn in ("gitnexus.json", "meta.json"):
            mp = os.path.join(repo, ".gitnexus", fn)
            if os.path.exists(mp):
                md = json.load(open(mp)); md["repoPath"], md["storagePath"] = repo, os.path.join(repo, ".gitnexus")
                json.dump(md, open(mp, "w"))
        if os.path.isdir(os.path.join(repo, ".gitnexus")):
            sh([ADMIN, "index", repo], env={"HOME": os.environ["HOME"], "PATH": "/usr/bin:/bin", "BENCH_GN_HOME": home})
        if os.path.getsize(patch) > 0:
            rc, o = sh(["git", "-C", repo, "apply", "--binary", "--whitespace=nowarn", patch])
            if rc:
                out["error"] = "apply " + o[-300:]; return out
        odir = os.path.join(repo, ".wfbench-oracle-" + "".join(random.choice(string.ascii_lowercase) for _ in range(8)))
        for f in task["oracle"]["files"]:
            dst = f["dst"].replace("{ORACLE_DIR}", odir)
            dst = dst if os.path.isabs(dst) else os.path.join(repo, dst)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy(f["src"], dst)
        env = {"HOME": os.environ["HOME"], "USER": os.environ["USER"], "LOGNAME": os.environ["USER"],
               "PATH": ":".join(task.get("path_prefix", []) + benchenv.path_tail()),
               "LANG": "en_US.UTF-8", "TERM": "dumb", "TMPDIR": tmp, "XDG_CACHE_HOME": f"{tmp}/xdg",
               "UV_CACHE_DIR": f"{tmp}/uv", "npm_config_cache": f"{tmp}/npm", "GITNEXUS_HOME": home,
               "GITNEXUS_BENCH_ORACLE_ROOT": odir}
        # Per-run placeholders: {TMP} = this run's temp root, {RUNDIR} = its checkout.
        env.update({k: str(v).replace("{TMP}", tmp).replace("{RUNDIR}", repo) for k, v in task.get("env", {}).items()})
        orc, oo = sh(task["oracle"]["cmd"], cwd=repo, timeout=task["oracle"].get("timeout", 900), env=env)
        out["oracle"] = orc == 0
        open(os.path.join(runs_dir, "runs", name, "regrade-oracle.log"), "w").write(oo[-20000:])
        if task.get("regression"):
            rrc, ro = sh(task["regression"]["cmd"], cwd=repo, timeout=task["regression"].get("timeout", 1200), env=env)
            out["regression"] = rrc == 0
            open(os.path.join(runs_dir, "runs", name, "regrade-regression.log"), "w").write(ro[-20000:])
            # Flaky-test rule (symmetric across arms): a pytest regression failure counts only if the failed tests also
            # fail when rerun on their own (serially, up to 2 reruns). More than 10 failures = real breakage, no rerun.
            rerun = task["regression"].get("rerun")
            failed = sorted(set(re.findall(r"^(?:FAILED|ERROR) (\S+?)(?: - .*)?$", ro, re.M)))
            if not out["regression"] and rerun and 0 < len(failed) <= 10:
                out["regression_failed_first"] = failed
                for attempt in (1, 2):
                    cmd = rerun.replace("{IDS}", " ".join(shlex.quote(f) for f in failed))
                    xrc, xo = sh(cmd, cwd=repo, timeout=task["regression"].get("timeout", 1200), env=env)
                    open(os.path.join(runs_dir, "runs", name, f"regrade-regression-rerun{attempt}.log"), "w").write(xo[-20000:])
                    if xrc == 0:
                        out["regression"] = True
                        out["regression_flaky"] = failed
                        break
                    failed = sorted(set(re.findall(r"^(?:FAILED|ERROR) (\S+?)(?: - .*)?$", xo, re.M))) or failed
        return out
    finally:
        shutil.rmtree(work, ignore_errors=True); shutil.rmtree(home, ignore_errors=True); shutil.rmtree(tmp, ignore_errors=True)


def main():
    tasks = {t["id"]: t for t in benchenv.load_tasks(sys.argv[1])}
    runs_dir = os.path.abspath(sys.argv[2])  # patch paths are opened from inside scratch clones
    jobs = int(sys.argv[sys.argv.index("--jobs") + 1]) if "--jobs" in sys.argv else 4
    rows = {}
    for l in open(os.path.join(runs_dir, "results.jsonl")):
        r = json.loads(l)
        if r.get("task") in tasks and tasks[r["task"]].get("kind") != "review":
            rows[r["run"]] = r  # last row per run wins
    done = set()
    rg = os.path.join(runs_dir, "regrade.jsonl")
    if "--only-missing" in sys.argv and os.path.exists(rg):
        done = {json.loads(l)["run"] for l in open(rg)}
    only = set(sys.argv[sys.argv.index("--only") + 1].split(",")) if "--only" in sys.argv else None  # task ids
    todo = [r for n, r in sorted(rows.items()) if n not in done and (only is None or r["task"] in only)]
    lock = threading.Lock()
    os.makedirs(SCRATCH, exist_ok=True)
    with ThreadPoolExecutor(max_workers=jobs) as ex, open(rg, "a") as f:
        def go(r):
            res = grade(tasks[r["task"]], r, runs_dir)
            with lock:
                f.write(json.dumps(res) + "\n"); f.flush(); print(json.dumps(res), flush=True)
        list(ex.map(go, todo))


if __name__ == "__main__":
    main()
