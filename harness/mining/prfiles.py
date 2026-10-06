import json, subprocess, sys, re, concurrent.futures as cf
repo, tsv, out = sys.argv[1], sys.argv[2], sys.argv[3]
rows = [l.rstrip('\n').split('\t') for l in open(tsv)]
def is_test(p):
    return bool(re.search(r'(^|/)(tests?|test_[^/]*|[^/]*_test\.py|integration_tests)(/|$)', p)) or '/tests/' in p or p.split('/')[-1].startswith('test_')
def fetch(r):
    n = r[0]
    try:
        o = subprocess.run(['gh','api',f'repos/{repo}/pulls/{n}/files','--paginate','--jq','.[] | [.filename,.additions,.deletions,.status] | @tsv'],capture_output=True,text=True,timeout=120).stdout
    except Exception as e:
        return None
    files=[l.split('\t') for l in o.strip().split('\n') if l]
    src=[f for f in files if not is_test(f[0]) and f[0].endswith(('.py','.ts','.js','.mjs','.cs','.swift','.sh')) ]
    tst=[f for f in files if is_test(f[0])]
    return dict(n=int(n),date=r[1],title=r[5],src=[(f[0],int(f[1])+int(f[2])) for f in src],tests=[(f[0],int(f[1])+int(f[2]),f[3]) for f in tst],other=[f[0] for f in files if f not in src and f not in tst])
with cf.ThreadPoolExecutor(8) as ex:
    res=[x for x in ex.map(fetch, rows) if x]
json.dump(res, open(out,'w'), indent=0)
