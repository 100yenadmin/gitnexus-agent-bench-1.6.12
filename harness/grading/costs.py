#!/usr/bin/env python3
"""Notional spend per run directory and engine (Claude: total_cost_usd; Codex: tokens x list price, SOL_PRICE in runner/bench.py).
Usage: costs.py <runs_dir> [...]"""
import json, os, sys
from collections import defaultdict
tot = defaultdict(float); n = defaultdict(int)
for d in sys.argv[1:]:
    p = os.path.join(d, "results.jsonl")
    if not os.path.exists(p):
        continue
    for l in open(p):
        r = json.loads(l); k = (os.path.basename(d.rstrip("/")), r.get("engine", "?"))
        tot[k] += r.get("cost_usd") or 0; n[k] += 1
g = 0.0
for k in sorted(tot):
    print(f"{k[0]:32} {k[1]:7} runs={n[k]:4} ${tot[k]:8.2f}"); g += tot[k]
print(f"{'TOTAL':40} runs={sum(n.values()):4} ${g:8.2f}")
