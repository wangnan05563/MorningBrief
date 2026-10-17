import os, re, json, collections

ROOT = r'D:\code\otherProjects\20_News'
rows = [l.rstrip('\n').split('\t') for l in open('rows.tsv', encoding='utf-8')
        if len(l.rstrip('\n').split('\t')) >= 6]
TOK = re.compile(r'([\w./\\-]+\.(?:vue|js|ts|py|json|md|wxml|wxss|scss|css|yml|yaml))(?::([\d,\-]+))?')

# index basenames
by_name = collections.defaultdict(list)
for dp, dn, fn in os.walk(ROOT):
    if any(x in dp for x in ('node_modules', '.git', 'dist', '_validate', '__pycache__', '.venv', 'release')):
        continue
    for f in fn:
        by_name[f].append(os.path.join(dp, f))

cache = {}


def resolve(p):
    p = p.replace('\\', '/')
    cand = os.path.join(ROOT, p)
    if os.path.isfile(cand):
        return cand, 'exact'
    base = os.path.basename(p)
    hits = by_name.get(base, [])
    if len(hits) == 1:
        return hits[0], 'basename'
    if len(hits) > 1:
        # prefer path suffix match
        suffix = '/' + '/'.join(p.split('/')[-3:])
        m = [h for h in hits if h.replace('\\', '/').endswith(suffix)]
        if len(m) == 1:
            return m[0], 'suffix'
        return None, f'ambiguous({len(hits)})'
    return None, 'missing'


stat = collections.Counter()
bad = []
line_oob = []
for r in rows:
    ok = True
    ms = TOK.findall(r[4])
    if not ms:
        stat['no_token'] += 1
        bad.append((r[0], 'no_token', r[4][:60]))
        continue
    for p, ln in ms:
        key = p
        if key not in cache:
            cache[key] = resolve(p)
        f, how = cache[key]
        stat[how] += 1
        if not f:
            ok = False
            bad.append((r[0], how, p))
            continue
        if ln:
            try:
                n = sum(1 for _ in open(f, encoding='utf-8', errors='replace'))
            except Exception:
                n = 0
            nums = [int(x) for x in re.findall(r'\d+', ln)]
            if nums and max(nums) > n:
                line_oob.append((r[0], p, ln, n))
    if not ok:
        stat['rows_with_bad'] += 1

print('files unique', len(cache), dict(stat))
print('line out-of-range count', len(line_oob))
for x in line_oob[:15]:
    print('  OOB', x)
print('bad refs', len(bad))
for x in bad[:15]:
    print('  BAD', x)
json.dump({'bad': bad, 'oob': line_oob}, open('evidence_check.json', 'w', encoding='utf-8'), ensure_ascii=False)
