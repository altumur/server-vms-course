"""P01.254: separate positive/negative M-passport controls. Own fixtures are retained under evidence/passport/controls/.
No product, model or stand process is run; only the accepted passport checker reads copies of export trees.
"""
from pathlib import Path
import subprocess,json,sys,hashlib,shutil
B=Path(__file__).resolve().parent.parent;C=(B/'C.txt').read_text().strip();P=B/('pair-'+C[:12]);T=B/'passport/controls';T.mkdir()
def g(d,*a):return subprocess.check_output(['git','--git-dir',str(d),*a])
M=g(P/'M.git','rev-parse','model').decode().strip();J=g(P/'J.git','rev-parse','judge').decode().strip();PP=B/'passport'/('PASSPORT-M-'+M[:12]+'.json');CK=B/'operator/check_m_passport.py'
def unpack(name,gd,commit):
 d=T/name;d.mkdir();p=subprocess.Popen(['git','--git-dir',str(gd),'archive',commit],stdout=subprocess.PIPE);q=subprocess.run(['tar','-x','-C',str(d)],stdin=p.stdout);p.stdout.close();assert p.wait()==q.returncode==0;return d
base=unpack('m',P/'M.git',M);jt=unpack('j',P/'J.git',J);res=[]
def run(name,root,sha,expected):
 argv=[sys.executable,'-B','-I',str(CK),str(PP),str(root),sha];p=subprocess.run(argv,capture_output=True)
 (T/(name+'.out')).write_bytes(p.stdout);(T/(name+'.err')).write_bytes(p.stderr)
 r={'name':name,'root':str(root),'argv':argv,'expected':expected,'exit':p.returncode,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()};r['pass']=p.returncode==0 if expected=='green' else p.returncode!=0;res.append(r);print(name,'exit',p.returncode,'PASS' if r['pass'] else 'FAIL');assert r['pass']
run('M-as-is',base,M,'green');run('J-with-M-passport',jt,M,'red')
for name in ['byte-change','missing','symlink','extra-J-only']:
 d=T/name;shutil.copytree(base,d);f=d/'Platform/01-store/forms/code-rules.tsv'
 if name=='byte-change': f.write_bytes(f.read_bytes()+b'\nx')
 elif name=='missing': f.unlink()
 elif name=='symlink': f.unlink();f.symlink_to('stages.tsv')
 else:
  f=d/'Platform/01-store/forms/extra.scenarios.tsv';f.write_bytes(g(P/'J.git','show',J+':Platform/01-store/forms/extra.scenarios.tsv'))
 run(name,d,M,'red')
old=Path('/home/pilot/run-p01251-pair-20261112-r2/pair-2d101991ac6e/M.git');OM='da04d237b656aafc8b30fb382c44406a80642cac';other=unpack('other-M-P01.251',old,OM)
run('other-M-tree',other,M,'red');run('other-M-commit',base,OM,'red')
out={'M':M,'passport':str(PP),'checks':res,'OK':all(r['pass'] for r in res)};(B/'passport/CONTROLS.json').write_text(json.dumps(out,ensure_ascii=False,indent=1)+'\n');assert out['OK']
