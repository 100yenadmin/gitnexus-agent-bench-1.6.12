#!/usr/bin/env python3
"""Score hermes impact-track answers against pyright + adjudicated ground truth (impact/gt.json). Same rule as
score_p1.py: a listed location matches a ground-truth site on the same repo-relative path within +-2 lines (one-to-one,
nearest first). Missing/unparseable answers score as empty (counted, not dropped).
Differences from score_p1.py: GT entries are keyed by task id (`id` field) because names repeat (e.g. to_dict), and
paths are normalized to repo-relative form (absolute paths under the task base, leading ./ stripped).
Usage: score_h_impact.py <tasks-h-impact.json> <runs_dir>[,<runs_dir>...] [--json out.json]
       score_h_impact.py --answer <task_id> <answer.json> [tasks.json]   (score one answer file; prints R/P)"""
import json, os, posixpath, re, sys
from collections import defaultdict
import os as _os, sys as _sys
_HARNESS = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path[:0] = [_os.path.join(_HARNESS, "runner"), _os.path.join(_HARNESS, "common")]
import benchenv  # noqa: E402

TOL = 2
DEFAULT_TASKS = os.path.join(benchenv.opt('HERMES_ARTIFACTS', '.'), 'tasks-h-impact.json')
# Task base prefixes stripped from absolute answer paths: the expanded $BENCH_ROOT one, and the literal placeholder
# form (published answers have local paths replaced by $BENCH_ROOT).
_BASES = ['$BENCH_ROOT/tasks/h/impact'] + ([os.path.join(os.environ['BENCH_ROOT'], 'tasks/h/impact')] if os.environ.get('BENCH_ROOT') else [])


def norm(p, base=None):
    p = str(p or '').strip()
    for b in filter(None, [base] + _BASES):
        b = b.rstrip('/') + '/'
        if p.startswith(b):
            p = p[len(b):]
    # bench.py runs each task in an APFS clone at <bench>/clones.noindex/<hash>/<run>/ (verifier fix 2026-10-06):
    # an absolute path inside that run clone is repo-relative after the run dir.
    m = re.match(r'^.*/clones\.noindex/[^/]+/[^/]+/(.+)$', p)
    if m:
        p = m.group(1)
    while p.startswith('./'):
        p = p[2:]
    return posixpath.normpath(p) if p else p


def load(path, base=None):
    try:
        d = json.load(open(path))
    except Exception:
        return None
    out = set()
    for x in (d.get('locations') if isinstance(d, dict) else None) or []:
        try:
            out.add((norm(x.get('path'), base), int(x.get('line'))))
        except Exception:
            continue
    return sorted(out)


def match(ans, gt):
    pairs = sorted((abs(al - gl), ai, gi) for ai, (ap, al) in enumerate(ans) for gi, (gp, gl) in enumerate(gt)
                   if ap == gp and abs(al - gl) <= TOL)
    ua, ug, tp = set(), set(), 0
    for _d, ai, gi in pairs:
        if ai not in ua and gi not in ug:
            ua.add(ai); ug.add(gi); tp += 1
    return tp, [gt[i] for i in range(len(gt)) if i not in ug], [ans[i] for i in range(len(ans)) if i not in ua]


def load_gts(tasks):
    gts = {}
    for t in tasks.values():
        for g in json.load(open(t['gt'])):
            gts[g['id']] = sorted({(s['file'], s['line']) for s in g['sites']})
    return gts


def rp(ans, gt):
    a = ans or []
    tp, missed, extra = match(a, gt)
    R = tp / len(gt) if gt else 1.0
    P = tp / len(a) if a else (1.0 if not gt else 0.0)
    return tp, R, P, missed, extra


def score_one(argv):
    tid, ans_path = argv[0], argv[1]
    tasks = {t['id']: t for t in benchenv.load_tasks(argv[2] if len(argv) > 2 else DEFAULT_TASKS)}
    gt = load_gts(tasks)[tid]
    ans = load(ans_path, tasks[tid].get('base'))
    tp, R, P, missed, extra = rp(ans, gt)
    print(json.dumps(dict(task=tid, gt=len(gt), ans=None if ans is None else len(ans), tp=tp, recall=R, precision=P,
                          missed=missed[:10], extra=extra[:10])))


def main():
    if sys.argv[1] == '--answer':
        return score_one(sys.argv[2:])
    from bench import parse_claude
    tasks = {t['id']: t for t in benchenv.load_tasks(sys.argv[1])}
    gts = load_gts(tasks)
    agg = defaultdict(lambda: defaultdict(list)); per_run = []
    print(f"{'run':44} {'gt':>3} {'ans':>4} {'tp':>3} {'R':>5} {'P':>5} {'cost':>5} {'turns':>5} {'gnx':>4}  missed/extra(e.g.)")
    for rd in sys.argv[2].split(','):
        for l in open(os.path.join(rd, 'results.jsonl')):
            r = json.loads(l)
            if r.get('task') not in tasks:
                continue
            gt = gts[r['task']]
            ans = load(os.path.join(rd, 'runs', r['run'], 'qa-answer.json'), tasks[r['task']].get('base'))
            st = os.path.join(rd, 'runs', r['run'], 'stream.jsonl')
            if r.get('engine') == 'claude' and os.path.exists(st):
                pc = parse_claude(st); r['turns'], r['gnx_cli'] = pc['turns'], pc['gnx_cli']
            a = ans or []
            tp, R, P, missed, extra = rp(ans, gt)
            gnx = (r.get('gnx_calls') or 0) + (r.get('gnx_cli') or 0)
            g = agg[r['arm']]
            g['R'].append(R); g['P'].append(P); g['perfect'].append(int(R == 1 and P == 1)); g['cost'].append(r.get('cost_usd') or 0)
            g['turns'].append(r.get('turns') or 0); g['gnx'].append(gnx); g['missing'].append(int(ans is None)); g['wall'].append(r.get('wall_s') or 0)
            per_run.append(dict(run=r['run'], task=r['task'], arm=r['arm'], gt=len(gt), ans=(len(a) if ans is not None else None), tp=tp,
                                recall=R, precision=P, cost=r.get('cost_usd') or 0, turns=r.get('turns') or 0, wall=r.get('wall_s') or 0, gnx=gnx))
            eg = (f"miss {missed[0][0][-34:]}:{missed[0][1]}" if missed else '') + (f" extra {extra[0][0][-34:]}:{extra[0][1]}" if extra else '')
            print(f"{r['run']:44} {len(gt):3} {len(a) if ans is not None else '-':>4} {tp:3} {R:5.2f} {P:5.2f} {r.get('cost_usd') or 0:5.2f} {r.get('turns') or 0:5} {gnx:4}  {eg}")
    print('\nper arm: mean recall / precision, all-correct rate, missing answers, mean cost / turns / wall / GitNexus calls')
    m = lambda xs: sum(xs) / len(xs) if xs else float('nan')
    for arm, g in sorted(agg.items()):
        print(f"{arm:6} n={len(g['R']):3} recall={m(g['R']):.3f} precision={m(g['P']):.3f} perfect={m(g['perfect']):.2f} "
              f"missing={sum(g['missing'])} cost=${m(g['cost']):.2f} turns={m(g['turns']):.1f} wall={m(g['wall']):.0f}s gnx={m(g['gnx']):.1f}")
    if '--json' in sys.argv:
        json.dump(dict(per_run=per_run, arms={k: dict({x: (sum(v) / len(v) if v else None) for x, v in g.items()}, n=len(next(iter(g.values()))))
                                              for k, g in agg.items()}),
                  open(sys.argv[sys.argv.index('--json') + 1], 'w'), indent=1)


if __name__ == '__main__':
    main()
