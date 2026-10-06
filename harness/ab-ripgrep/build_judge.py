#!/usr/bin/env python3
"""Build blind grading packets: per question, 4 answers (realA t1/t2, realB t1/t2) under shuffled labels.
Usage: build_judge.py <artifacts_dir>  -> judge/<Q>.prompt.md + judge/<Q>.map.json (mapping is never in the prompt)."""
import hashlib, json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "common"))
import benchenv  # noqa: E402
A = sys.argv[1]
tasks = {t["id"]: t for t in benchenv.load_tasks(os.path.join(A, "tasks-broad.json"))}
rows = {}
for l in [x for f in ("runs-broad.jsonl", "runs-broad-f.jsonl") if os.path.exists(os.path.join(A, "runs", f)) for x in open(os.path.join(A, "runs", f))]:
    r = json.loads(l)
    rows[(r["id"], r["arm"])] = r
os.makedirs(os.path.join(A, "judge"), exist_ok=True)
qids = sorted({t["target"] for t in tasks.values()})
for q in qids:
    cells = [(f"{q}t{t}", arm) for arm in ("realA", "realB", "realF") for t in (1, 2)]
    # deterministic shuffle keyed on the question id
    order = sorted(cells, key=lambda c: hashlib.sha256((q + c[0] + c[1]).encode()).hexdigest())
    labels = "ABCDEF"
    mapping = {labels[i]: {"id": c[0], "arm": c[1]} for i, c in enumerate(order)}
    t0 = tasks[f"{q}t1"]
    question = t0["prompt"].replace(" Answer in at most 400 words. Do not modify any files.", "")
    parts = [
        f"You are grading six anonymous answers to a code-understanding question about the repository at `{t0['cwd']}` "
        "(read it; do not modify anything).\n",
        f"QUESTION: {question}\n",
        "For EACH answer: open the files and line numbers it cites and check its concrete claims and the order of the flow "
        "against the actual source. Then score:\n"
        "- correctness 0-10: 10 = every concrete claim (file, function, line, call order) checks out; deduct for each wrong "
        "or unverifiable claim.\n"
        "- completeness 0-10: 10 = covers every key mechanism or hop a maintainer would expect; deduct for missing ones.\n"
        "List up to 3 concrete errors or omissions per answer. Judge only what is written; do not reward length or style.\n"
        'Output ONLY this JSON, nothing else: {"A":{"correctness":n,"completeness":n,"errors":["..."]},"B":{...},"C":{...},"D":{...},"E":{...},"F":{...}}\n',
    ]
    for lab in labels:
        r = rows.get((mapping[lab]["id"], mapping[lab]["arm"]))
        ans = (r or {}).get("answer") or "(no answer)"
        parts.append(f"\n===== ANSWER {lab} =====\n{ans.strip()}\n")
    open(os.path.join(A, "judge", f"{q}.prompt.md"), "w").write("".join(parts))
    json.dump({"cwd": t0["cwd"], "map": mapping}, open(os.path.join(A, "judge", f"{q}.map.json"), "w"), indent=1)
    print(q, "packet written")
