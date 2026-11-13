"""Read-only provenance/coverage/budget audit; never executes candidate code."""
from pathlib import Path
import hashlib,json,re,subprocess,sys
W=Path(sys.argv[1]).resolve();B=Path(sys.argv[2]).resolve();B.mkdir(exist_ok=True)
BASE='3ee4ab68be24dbd02b3b52533ad1eada9d38c845'
OLD='30310352523e30aa7e7879d901e44d80e01b118d'
CAND='6d0ad481f43e57ee0ddccc52a8af67890034078e'
P=Path('/home/pilot/owner-receipts/P01.301-court-81-vs-71-20261113T1534Z')
def git(*args):return subprocess.check_output(['git','-C',str(W),*args])
def sha(raw):return hashlib.sha256(raw).hexdigest()
primary={str(p):{'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())} for p in [P/'INDEX.md',P/'court/lm43.txt',P/'soak/runs/c81-recover.out',P/'soak/runs/c81-box2.out',P/'form-mutation/claude81/report.md',P/'form-mutation/claude81/report.json']}
recover=[json.loads(line) for line in (P/'soak/runs/c81-recover.out').read_text().splitlines() if line.startswith('{')]
points=[r for r in recover if r.get('step','').startswith('crash-point-') or r.get('step')=='kill-at-mark-removal']
fail=[r for r in points if r.get('verify',{}).get('rows_ok')==0 and r.get('verify',{}).get('rows_missing')==100]
assert len(points)==62 and [r['point']['seq'] for r in fail]==[55,56,57,58,59]
box=[json.loads(line) for line in (P/'soak/runs/c81-box2.out').read_text().splitlines() if line.startswith('{')]
bad=next(r for r in box if r.get('case')=='checkpoint-two-failures');ok=next(r for r in box if r.get('case')=='checkpoint-control')
assert bad['B_lost'] and bad['version_reissued'] and not ok['B_lost'] and not ok['version_reissued']
assert bad['B']==[200,'170',''] and bad['next_write']==[200,'170'] and ok['next_write']==[200,'171']
report=(W/'decisions/inbox/2026-11-13-P01.332-находки-кандидата-82.md').read_text()
refs=set(re.findall(r'P/(?:\d+\.\d+|AC)-R\d+',report));live=set()
for path in (W/'Platform').rglob('*.norms.md'):
 if '/ru/' not in str(path):live.update(re.findall(r'<!-- req: (P/(?:\d+\.\d+|AC)-R\d+) -->',path.read_text()))
assert refs<=live,refs-live
journals={}
for name in ('history-1.tsv','history-3.tsv','corrections-1.tsv','history.tsv'):
 p='decisions/journal/platform/01-store/'+name;before=git('show',BASE+':'+p);after=(W/p).read_bytes();assert after.startswith(before)
 journals[p]={'prefix_preserved':True,'added_lines':len(after[len(before):].splitlines())}
budgets={}
for lang in ('en','ru'):
 root='Platform/01-store/'+('ru/' if lang=='ru' else '')+'spec/'
 paths=[root+f'01.{k}-store.norms.md' for k in (1,2,3)]
 before=sum(len(git('show',OLD+':'+p)) for p in paths);after=sum((W/p).stat().st_size for p in paths)
 budgets[lang]={'from_C8prime_bytes':before,'to_bytes':after,'delta_bytes':after-before}
q=json.loads((W/'Platform/common/qualification-input-filter.json').read_text());qfiles=q['files'];records=[]
for row in sorted(qfiles,key=lambda r:r['path'].encode()):
 p=W/row['path'];records.append({'path':row['path'],'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())})
qraw=json.dumps(records,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
qresult={'method':'SHA256 of compact UTF-8 JSON list sorted by path bytes; object keys sorted; rows path/bytes/sha256; no final newline in hashed bytes','input_records':records,'sha256':sha(qraw),'count':len(records)}
(B/'Q-INPUT-HASH.json').write_text(json.dumps(qresult,ensure_ascii=False,indent=1)+'\n')
prior=subprocess.check_output(['git','--git-dir=/home/pilot/git/claude81.git','diff','51976fe',CAND,'--','01-store/internal/group/logstore.go']);assert not prior
result={'basis':BASE,'C8prime':OLD,'candidate':CAND,'primary_evidence':primary,'recover':{'points':62,'fail_points':[r['point']['seq'] for r in fail]},'checkpoint':{'control':{'B_lost':False,'version_reissued':False,'next':'171'},'two_failures':{'B_lost':True,'version_reissued':True,'B_version':'170','next':'170'}},'live_report_R_ids':sorted(refs),'journals':journals,'norm_budget':budgets,'Q_input_hash':qresult['sha256'],'logstore_unchanged_from_Opus8':True,'candidate_execution':False,'OK':True}
(B/'TASK-AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=1)+'\n')
print(json.dumps({'report_R_ids':len(refs),'recover_failures':5,'Q_files':len(records),'norm_budget':budgets,'OK':True},ensure_ascii=False))
