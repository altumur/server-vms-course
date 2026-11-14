import json,re,subprocess,sys
from pathlib import Path
B=Path(sys.argv[1]).resolve();C=(B/'C.txt').read_text().strip();O='0fbe6e55ceb0b07e4a70727e813934a2f06edb1b'
I=json.loads((B/'IDENTITIES.json').read_text())
old=json.loads(Path('decisions/inbox/2026-11-13-P01.332-пара-M8doubleprime-J8doubleprime/PASSPORT-M.json').read_text())
new=json.loads(Path(I['M_passport']).read_text())
old_files={r['path']:(r['mode'],r['blob']) for r in old['files']}
new_files={r['path']:(r['mode'],r['blob']) for r in new['files']}
paths=[p for p in sorted(old_files.keys()|new_files.keys()) if old_files.get(p)!=new_files.get(p) and p!='Platform/COURSE_COMMIT']
(B/'CHANGED-M-PATHS.json').write_text(json.dumps(paths,indent=1)+'\n')
def read(ref,path):
 r=subprocess.run(['git','show',ref+':'+path],capture_output=True)
 return r.stdout.decode() if r.returncode==0 else ''
def blocks(v):
 a=list(re.finditer(r'<!-- req: (\S+) -->',v))
 def clean(s):
  s=re.sub(r'(?m)^<!-- removed: .*? -->\s*$', '',s)
  return re.sub(r'(?m)^---+\s*$', '',s).strip()
 return {m[1]:clean(re.split(r'(?m)^#{1,6} ',v[m.end():a[i+1].start() if i+1<len(a) else len(v)],1)[0]) for i,m in enumerate(a)}
def checks(v):return {req:l for l,req in re.findall(r'(?m)^(- \[ \] \*\*(P/(?:\d+(?:\.\d+)?|AC)-\d+)\*\*.*)$',v)}
files={};rs={};cs={}
for p in paths:
 before,after=read(O,p),read(C,p);files[p]={'before':before,'after':after}
 a,z=blocks(before),blocks(after)
 for req in sorted(a.keys()|z.keys()):
  if a.get(req)!=z.get(req):rs[req]={'path':p,'before':a.get(req,''),'after':z.get(req,'')}
 a,z=checks(before),checks(after)
 for req in sorted(a.keys()|z.keys()):
  if a.get(req)!=z.get(req):cs[req]={'path':p,'before':a.get(req,''),'after':z.get(req,'')}
(B/'CHANGED-NORMS-DETAILS.json').write_text(json.dumps({'files':files,'paragraphs':rs,'checks':cs},ensure_ascii=False,indent=1)+'\n')
for r,v in rs.items():print(r,v['path'],str(len(v['before']))+'->'+str(len(v['after'])))
print('CHECKLIST',list(cs));print('paragraphs',len(rs),'checklist',len(cs),'files',len(files))
