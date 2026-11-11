"""Check that every `removed` cell of the rows added by P01.229 is verbatim text of the base sources (exact, or exact
with a line break inside the original — the original LF and indentation are a single space in the cell)."""
import subprocess, re, sys
base = sys.argv[1] if len(sys.argv) > 1 else 'db52c3a18'
def show(rev, p):
    r = subprocess.run(['git', 'show', f'{rev}:{p}'], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ''
files = subprocess.run(['git', 'ls-tree', '-r', '--name-only', base, 'Platform/common/acceptance', 'Platform/01-store', 'Platform/02-installer'], capture_output=True, text=True).stdout.split()
corpus = [show(base, p) for p in files if p.endswith(('.md', '.tsv', '.json')) and '/ru/' not in p]
joined = [re.sub(r'\n[ \t]*', ' ', t) for t in corpus]
journals = ['decisions/journal/platform/common/history.tsv', 'decisions/journal/platform/01-store/history-1.tsv',
            'decisions/journal/platform/01-store/history-3.tsv', 'decisions/journal/platform/01-store/history.tsv',
            'decisions/journal/platform/02-installer/history.tsv', 'decisions/journal/platform/02-installer/history-5.tsv']
bad = exact = wrapped = 0
for f in journals:
    old = set(show(base, f).split('\n'))
    for n, l in enumerate(open(f, encoding='utf-8').read().split('\n'), 1):
        if n == 1 or not l or l in old: continue
        rem = l.split('\t')[4]
        if rem == '-': continue
        if any(rem in t for t in corpus): exact += 1
        elif any(rem in t for t in joined): wrapped += 1
        else: bad += 1; print('NOT VERBATIM', f, n, rem[:160])
print(f'exact={exact} across-line-break={wrapped} not_verbatim={bad}')
