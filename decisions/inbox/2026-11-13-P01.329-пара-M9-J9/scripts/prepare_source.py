"""Exact-C archive and unchanged P02.52 operators for P01.329; no pin or delivery."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import time

B, W = (Path(x).resolve() for x in sys.argv[1:3])
C = sys.argv[3]
assert len(C) == 40 and all(x in '0123456789abcdef' for x in C)
assert subprocess.check_output(['git','-C',str(W),'rev-parse',C]).decode().strip() == C
T = Path('/home/pilot/cammeta-sessions/tasks')
task = (T/'P01.329.yaml').read_bytes()
assert b'answered:' in task and 'Нет, не ждать'.encode() in task
B.mkdir()
(B/'C.txt').write_text(C+'\n')
(B/'TASK-at-source.yaml').write_bytes(task)
(B/'reviews').mkdir()
rows=[]
for name in ('P01.298','P01.324','OBSH.56','OBSH.61','P01.320','P03.35'):
    raw=(T/'accepted'/(name+'.json')).read_bytes()
    r=json.loads(raw)
    assert r['status']=='accepted',name
    subprocess.run(['git','-C',str(W),'merge-base','--is-ancestor',r['commit'],C],check=True)
    (B/'reviews'/(name+'-accepted.json')).write_bytes(raw)
    rows.append({'task':name,'status':r['status'],'commit':r['commit'],'utc':r['utc'],'accepted_sha256':hashlib.sha256(raw).hexdigest(),'ancestor_C':True})
r58=(T/'accepted/OBSH.58.json').read_bytes()
assert json.loads(r58)['status']=='rejected'
(B/'reviews/OBSH.58-rejected.json').write_bytes(r58)
subprocess.run(['git','clone','--bare','--no-hardlinks',str(W),str(B/'source.git')],check=True,capture_output=True)
(B/'archive-C').mkdir()
p=subprocess.Popen(['git','--git-dir',str(B/'source.git'),'archive',C],stdout=subprocess.PIPE)
r=subprocess.run(['tar','-x','-C',str(B/'archive-C')],stdin=p.stdout)
p.stdout.close()
assert p.wait()==r.returncode==0
(B/'operator').mkdir()
hashes={}
for name in ('b7_export_pair.py','m_passport.py','check_m_passport.py','judge_input_export.py','test_b7_export_pair.py','test_judge_input_export.py'):
    old=Path('/home/pilot/P01.299-evidence/r2/operator')/name
    new=B/'operator'/name
    shutil.copyfile(old,new)
    prior=Path('/home/pilot/P01.277-evidence/operator')/name
    assert old.read_bytes()==new.read_bytes()==prior.read_bytes()
    hashes[name]=hashlib.sha256(new.read_bytes()).hexdigest()
(B/'OPERATOR-UNCHANGED.json').write_text(json.dumps({'source':'/home/pilot/P01.299-evidence/r2/operator','also_equal':'/home/pilot/P01.277-evidence/operator','files_sha256':hashes,'unchanged':True},indent=1)+'\n')
(B/'scripts').mkdir()
for old in Path(__file__).resolve().parent.glob('*.py'):
    shutil.copyfile(old,B/'scripts'/old.name)
composition={'C':C,'dependencies':rows,'OBSH.58':{'status':'rejected','receipt':'reviews/OBSH.58-rejected.json','sha256':hashlib.sha256(r58).hexdigest(),'authorized_by_answered':True,'answered_utc':'2026-11-13T11:48:06Z','scope':'operator itself validates roster; check_spec without .git defect does not block this pair'},'task_sha256':hashlib.sha256(task).hexdigest(),'latest_fetched_main_at_source':C,'OK':True}
(B/'SOURCE-COMPOSITION.json').write_text(json.dumps(composition,ensure_ascii=False,indent=1)+'\n')
argv=[sys.executable,'-B','skills/lesson-spec/scripts/check_spec.py','--scope','platform']
start=time.monotonic();r=subprocess.run(argv,cwd=B/'archive-C',capture_output=True)
for ext,raw in [('out',r.stdout),('err',r.stderr)]: (B/('CHECK-SPEC-C.'+ext)).write_bytes(raw)
(B/'CHECK-SPEC-C.exit').write_text(str(r.returncode)+'\n')
(B/'CHECK-SPEC-C.run.json').write_text(json.dumps({'argv':argv,'cwd':str(B/'archive-C'),'C':C,'exit':r.returncode,'seconds':time.monotonic()-start,'roster_limitation':'OBSH.58 rejected: archive has no .git; unchanged export operator preflight checks exact roster per answered'},indent=1)+'\n')
assert r.returncode==0
for name,args in [('PREFLIGHT',['preflight.py',C,str(B/'source.git')]),('FILTER-DELTA',['filter_delta.py','30310352523e30aa7e7879d901e44d80e01b118d',C,str(B/'source.git')])]:
    argv=[sys.executable,'-B',str(B/'scripts'/args[0]),*args[1:]]
    r=subprocess.run(argv,capture_output=True)
    (B/(name+'.json')).write_bytes(r.stdout);(B/(name+'.err')).write_bytes(r.stderr)
    (B/(name+'.run.json')).write_text(json.dumps({'argv':argv,'exit':r.returncode},indent=1)+'\n')
    assert r.returncode==0,(name,r.stderr.decode())
print(json.dumps({'C':C,'evidence':str(B),'check_exit':0,'preflight_exit':0},indent=1))
