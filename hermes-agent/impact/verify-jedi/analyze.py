import json, sys, collections
gt = {g['id'][len('h-impact-'):]: g for g in json.load(open('../gt.json'))}
occ = [json.loads(l) for l in open('jedi-occ-all.jsonl')]
by = collections.defaultdict(list)
for o in occ: by[o['target']].append(o)
for name, os_ in by.items():
    g = gt[name]; gset = {(s['file'], s['line']) for s in g['sites']}
    leaf = name.split('.')[-1]
    hits = [o for o in os_ if o['hit']]
    cand = set()
    print(f"\n===== {name}: occurrences={len(os_)} hits={len(hits)} gt={len(gset)}")
    for o in hits:
        t = o['text']
        isdef = (o['file'], o['line']) == (g['file'], g['line'])
        isimp = t.startswith('from ') or t.startswith('import ') or o['prev'] in ('import', ',') and 'import' in t
        if isdef or isimp: continue
        cand.add((o['file'], o['line']))
    miss = sorted(gset - cand); extra = sorted(cand - gset)
    print(' jedi-candidates', len(cand), ' GT-not-jedi', len(miss), ' jedi-not-GT', len(extra))
    for m in miss:
        os2 = [o for o in os_ if (o['file'], o['line']) == m]
        print('  GT-only', m, [ (o['tok'], o['defs'][:2]) for o in os2], os2[0]['text'] if os2 else 'NO TOKEN ON LINE')
    for e in extra:
        os2 = [o for o in os_ if (o['file'], o['line']) == e]
        print('  JEDI-only', e, os2[0]['text'])
    unres = [o for o in os_ if not o['hit'] and not o['defs']]
    print(' unresolved tokens:', len(unres))
    for o in unres: print('   U', o['file'], o['line'], o['tok'], o['prev'], o['next'], '|', o['text'][:110])
