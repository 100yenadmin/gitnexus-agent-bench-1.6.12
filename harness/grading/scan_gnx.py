#!/usr/bin/env python3
"""Contamination scan: find every GitNexus CLI call an agent made through Bash/exec (gitnexus, npx gitnexus,
node .gitnexus/run.cjs) and classify its output: LIVE (reached the live estate: lists the 59 live repos or a live
index path), STUB (command not found / missing module), OK (answered from the per-run home) or ERR.
Usage: scan_gnx.py <runs_dir>[,<runs_dir>...]  -> one line per run with any CLI use; LIVE in a no-GitNexus arm = contaminated.
"""
import json, os, re, sys

# gitnexus in COMMAND position (not `cd gitnexus`, not paths): line start, after ; & | ( or `, after `timeout N`, after npx.
CLI = re.compile(r"(?:^|\n|[;&|(`]\s*|\btimeout\s+\d+\s+|\bnpx\s+(?:--yes\s+|-y\s+)?)\s*gitnexus(?:\s|$)|node\s+\S*\.gitnexus/run\.cjs")
# LIVE markers: our full registry listed every indexed repo, and its index paths lived under one local checkout root whose path and
# directory-name fragments we matched here. Set LIVE_INDEX_MARKERS to a regex for your own estate's paths (our value is
# withheld because it names local directories); without it only the repo-count and "Available:" markers apply.
_LIVE_EXTRA = os.environ.get("LIVE_INDEX_MARKERS", "")
LIVE = re.compile(r"Indexed Repositories \((?:[2-9]\d)\)|Available: [A-Za-z]" + (f"|{_LIVE_EXTRA}" if _LIVE_EXTRA else ""))
STUB = re.compile(r"command not found: gitnexus|Cannot find module .*\.gitnexus/run\.cjs|not available in this benchmark")
NOGNX = {"U_nomcp", "A0", "C0", "H0", "R_plain", "CR0"}


def calls_claude(path):
    pend, out = {}, []
    for line in open(path, errors="replace"):
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("type") == "assistant":
            for c in (e.get("message") or {}).get("content") or []:
                if c.get("type") == "tool_use" and c.get("name") == "Bash":
                    cmd = str((c.get("input") or {}).get("command") or "")
                    if CLI.search(cmd):
                        pend[c["id"]] = cmd
        elif e.get("type") == "user":
            for c in (e.get("message") or {}).get("content") or []:
                if isinstance(c, dict) and c.get("type") == "tool_result" and c.get("tool_use_id") in pend:
                    res = c.get("content")
                    res = res if isinstance(res, str) else json.dumps(res)
                    out.append((pend.pop(c["tool_use_id"]), res))
    return out + [(c, "") for c in pend.values()]


def calls_codex(path):
    out = []
    for line in open(path, errors="replace"):
        try:
            e = json.loads(line)
        except Exception:
            continue
        it = e.get("item") or {}
        if it.get("type") == "command_execution" and e.get("type") == "item.completed":
            cmd = str(it.get("command") or "")
            if CLI.search(cmd):
                out.append((cmd, str(it.get("aggregated_output") or "")))
    return out


def classify(res):
    if LIVE.search(res):
        return "LIVE"
    if STUB.search(res):
        return "STUB"
    if re.search(r"error|not found|ENOENT", res, re.I) and len(res) < 400:
        return "ERR"
    return "OK"


def main():
    for rd in sys.argv[1].split(","):
        rows = [json.loads(l) for l in open(os.path.join(rd, "results.jsonl"))]
        for r in rows:
            st = os.path.join(rd, "runs", r["run"], "stream.jsonl")
            if not os.path.exists(st):
                continue
            calls = calls_claude(st) if r.get("engine", "claude") == "claude" else calls_codex(st)
            if not calls:
                continue
            kinds = [classify(res) for _c, res in calls]
            tag = "CONTAMINATED" if r["arm"] in NOGNX and ("LIVE" in kinds or "OK" in kinds) else (
                "live-in-gnx-arm" if "LIVE" in kinds else "")
            print(f"{os.path.basename(rd.rstrip('/'))}/{r['run']:40} {r['arm']:8} calls={len(calls):2} "
                  f"{','.join(sorted(set(kinds))):16} {tag}")
            if tag:
                for (c, res), k in zip(calls, kinds):
                    if k in ("LIVE", "OK"):
                        print(f"      {k}: {c[:110]!r} -> {res[:120]!r}")


if __name__ == "__main__":
    main()
