"""M measures: assembled M (model_and_judge of export_lists) and the P/01 reading set
(M files of Platform/01-store + common files linked from «What this lesson takes from common» of Platform/01-store/README.md).
usage: msize.py OUT_PREFIX  (run from the course root)"""
import sys,os,re,json
sys.path.insert(0,'skills/lesson-spec/scripts')
import export_lists
a,e,s=export_lists.assemble('.')
m=sorted(r['path'] for r in a['model'] if r['disposition']=='model_and_judge')
size=lambda p: os.path.getsize(p) if os.path.isfile(p) else 0
out=sys.argv[1]
open(out+'-M.tsv','w').write(''.join(f"{size(p)}\t{p}\n" for p in m))
t=open('Platform/01-store/README.md',encoding='utf-8').read()
sec=re.search(r'^## What this lesson takes from common\n(.*?)(?=^## |\Z)',t,re.S|re.M).group(1)
common=set()
for l in sec.splitlines():
    if not l.startswith('|'): continue
    first=l.split('|')[1]
    for p in re.findall(r'\]\((\.\./common/[^)#]+)',first):
        common.add(os.path.normpath(os.path.join('Platform/01-store',p)))
mset=set(m)
lesson=[p for p in m if p.startswith('Platform/01-store/')]
reading=sorted(set(lesson)|{p for p in common if p in mset})
notm=sorted(p for p in common if p not in mset)
open(out+'-reading.tsv','w').write(''.join(f"{size(p)}\t{p}\n" for p in reading))
print(f"errors={len(e)} M files={len(m)} bytes={sum(map(size,m))}")
print(f"reading P/01: files={len(reading)} bytes={sum(map(size,reading))} (lesson {len(lesson)} {sum(map(size,lesson))}; common {len(reading)-len(lesson)} {sum(size(p) for p in reading if p not in lesson)})")
if notm: print("named in takes-from-common but not model_and_judge:",notm)
