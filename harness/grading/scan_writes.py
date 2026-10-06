#!/usr/bin/env python3
"""Isolation audit for Claude's file tools: Claude's Bash sandbox does not cover Write/Edit/MultiEdit/NotebookEdit, so
list every file-tool call whose target lies outside the run's own cwd (from the stream's init event).
Usage: scan_writes.py <runs_dir>[,<runs_dir>...]"""
import json, os, sys

TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}


def main():
    n_runs = n_calls = 0
    for rd in sys.argv[1].split(","):
        runs = os.path.join(rd, "runs")
        if not os.path.isdir(runs):
            continue
        for run in sorted(os.listdir(runs)):
            st = os.path.join(runs, run, "stream.jsonl")
            if not os.path.exists(st):
                continue
            cwd, bad, pend = None, [], {}
            for line in open(st, errors="replace"):
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                if e.get("type") == "system" and e.get("subtype") == "init":
                    cwd = os.path.realpath(e.get("cwd") or "")
                elif e.get("type") == "assistant":
                    for c in (e.get("message") or {}).get("content") or []:
                        if c.get("type") == "tool_use" and c.get("name") in TOOLS:
                            inp = c.get("input") or {}
                            fp = inp.get("file_path") or inp.get("notebook_path") or ""
                            n_calls += 1
                            if cwd and fp and not os.path.realpath(os.path.join(cwd, fp)).startswith(cwd + os.sep):
                                pend[c["id"]] = (c["name"], fp)
                elif e.get("type") == "user":
                    for c in (e.get("message") or {}).get("content") or []:
                        if isinstance(c, dict) and c.get("tool_use_id") in pend:
                            name, fp = pend.pop(c["tool_use_id"])
                            bad.append((name, fp, "ERROR" if c.get("is_error") else "ok"))
            bad += [(n, f, "no-result") for n, f in pend.values()]
            if cwd is None:
                continue
            n_runs += 1
            for name, fp, res in bad:
                print(f"{os.path.basename(rd.rstrip('/'))}/{run}: {name} {fp} [{res}]")
    print(f"# scanned {n_runs} claude runs, {n_calls} file-tool calls", file=sys.stderr)


if __name__ == "__main__":
    main()
