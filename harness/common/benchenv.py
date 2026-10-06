"""Shared configuration for the published harness.

Every machine-specific location the original scripts hardcoded is read from an environment variable here (see
../config.example.env). Task files may use the placeholders below in any string value (paths and commands); they are
expanded when the tasks are loaded, so a task file never has to name a local directory:

    $BENCH_ROOT        state root: tasks/ (base checkouts), clones.noindex/ (per-run clones), home*/ and refresh-state*/
    $TASK_BASE         $BENCH_ROOT/tasks unless set
    $BENCH_ARTIFACTS   claims-bench data dir (tasks-*.json, probes/, oracles-u/, mining/<task>/oracle/, runs-*/)
    $HERMES_ARTIFACTS  hermes-agent impact-track data dir (tasks-h-impact.json, impact/, runs-h-impact-*/)
    $HARNESS           this harness directory (set automatically)
    $BUNDLE            the bundle root, the parent of $HARNESS (set automatically)
    $GITNEXUS_SRC      a GitNexus source checkout at c4ecf398 (v1.6.12); review cases and labels come from its eval/
    $GITNEXUS_PKG      the installed gitnexus npm package (node_modules/gitnexus) at the same version
    $NODE_BIN_DIR      directory holding the `node` used for TypeScript tasks (prepended to PATH via path_prefix)
    $AB_ARTIFACTS      A/B (GitNexus vs ripgrep) data dir (tasks*.json, ground-truth.json, runs/, judge*/)
    $AB_REPOS_ROOT     parent dir of the A/B task repositories (task 'cwd' values)

Only these names are expanded; any other $VAR in a command (e.g. $GITNEXUS_BENCH_ORACLE_ROOT) is left for the shell.
"""
import json, os, re

HARNESS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("HARNESS", HARNESS)
os.environ.setdefault("BUNDLE", os.path.dirname(HARNESS))


def _load_config():
    """harness/config.env (or $BENCH_CONFIG): KEY=VALUE lines, ${OTHER} expanded, the environment wins.
    Same rules as isolation/_config.sh, so the Python and shell sides see the same settings."""
    path = os.environ.get("BENCH_CONFIG") or os.path.join(HARNESS, "config.env")
    if not os.path.isfile(path):
        return
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k) or os.environ.get(k):
            continue
        if k.endswith("_API_KEY"):  # only the GitNexus launchers need the key; keep it out of Python (and agent) envs
            continue
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        os.environ[k] = os.path.expandvars(v)


_load_config()
if os.environ.get("BENCH_ROOT"):
    os.environ.setdefault("TASK_BASE", os.path.join(os.environ["BENCH_ROOT"], "tasks"))
if os.environ.get("NODE_BIN") and not os.environ.get("NODE_BIN_DIR"):
    os.environ["NODE_BIN_DIR"] = os.path.dirname(os.environ["NODE_BIN"])

PLACEHOLDERS = ("BENCH_ROOT", "TASK_BASE", "BENCH_ARTIFACTS", "HERMES_ARTIFACTS", "HARNESS", "BUNDLE", "GITNEXUS_SRC",
                "GITNEXUS_PKG", "NODE_BIN_DIR", "AB_ARTIFACTS", "AB_REPOS_ROOT")
_PH = re.compile(r"\$(?:\{(" + "|".join(PLACEHOLDERS) + r")\}|(" + "|".join(PLACEHOLDERS) + r")\b)")


def need(name):
    """A required setting: fail loudly instead of falling back to a guess."""
    v = os.environ.get(name)
    if not v:
        raise SystemExit(f"benchenv: environment variable {name} is not set (see harness/config.example.env)")
    return v


def opt(name, default=None):
    return os.environ.get(name) or default


def expand(s):
    def sub(m):
        return need(m.group(1) or m.group(2))
    return _PH.sub(sub, s)


def expand_all(obj):
    if isinstance(obj, str):
        return expand(obj)
    if isinstance(obj, list):
        return [expand_all(x) for x in obj]
    if isinstance(obj, dict):
        return {k: expand_all(v) for k, v in obj.items()}
    return obj


def load_tasks(path):
    return expand_all(json.load(open(path)))


def path_tail():
    """PATH entries appended after the per-run shims: EXTRA_PATH (colon list) then the system dirs.
    Our runs had the dirs of the claude, codex and uv launchers and of other command-line tools here."""
    extra = [p for p in opt("EXTRA_PATH", "").split(":") if p]
    return extra + ["/usr/bin", "/bin", "/usr/sbin", "/sbin"]
