"""Unpack final M read-only and verify every path, blob and executable mode."""
from pathlib import Path
import hashlib
import json
import stat
import subprocess
import sys
B=Path(sys.argv[1]).resolve()
I=json.loads((B/'IDENTITIES.json').read_text())
passport=Path(I['M_passport']);P=json.loads(passport.read_text())
assert P['C']==I['C'] and P['M']['commit']==I['M']
assert hashlib.sha256(passport.read_bytes()).hexdigest()==I['M_passport_sha256']
root=B/'M'
assert not root.exists(),'never overwrite an earlier export'
root.mkdir()
p=subprocess.Popen(['git','--git-dir',I['M_git'],'archive',I['M']],stdout=subprocess.PIPE)
r=subprocess.run(['tar','-x','-C',str(root)],stdin=p.stdout)
p.stdout.close()
assert p.wait()==r.returncode==0
entries={r['path']:(r['mode'],r['blob']) for r in P['files']}
assert len(entries)==P['count']
assert {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}==entries.keys()
files=[]
for relative,(git_mode,blob) in sorted(entries.items()):
    path=root/relative
    assert stat.S_ISREG(path.lstat().st_mode)
    raw=path.read_bytes()
    assert hashlib.sha1(b'blob %d\0'%len(raw)+raw).hexdigest()==blob
    mode=0o555 if git_mode=='100755' else 0o444
    path.chmod(mode)
    files.append({'path':relative,'git_mode':git_mode,'blob':blob,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'filesystem_mode':oct(mode)})
for path in sorted((p for p in root.rglob('*') if p.is_dir()),reverse=True):path.chmod(0o555)
root.chmod(0o555)
assert all(not p.lstat().st_mode&0o222 for p in (root,*root.rglob('*')))
assert not (root/'.git').exists()
argv=[sys.executable,'-I','-B',str(B/'operator/check_m_passport.py'),str(passport),str(root),I['M']]
r=subprocess.run(argv,capture_output=True)
(B/'UNPACKED-M-passport.out').write_bytes(r.stdout)
(B/'UNPACKED-M-passport.err').write_bytes(r.stderr)
assert r.returncode==0
out={'C':I['C'],'M':I['M'],'directory':str(root),'files_count':len(files),
     'passport':str(passport),'passport_sha256':I['M_passport_sha256'],'passport_check_exit':r.returncode,
     'passport_bound_to_exact_C_M':True,'all_write_bits_cleared':True,'exact_paths_blobs_and_executable_modes':True,
     'no_git_metadata':True,'ancestor_modes':{str(p):oct(stat.S_IMODE(p.stat().st_mode)) for p in reversed(root.parents)},
     'access_limit':'Shared ancestor permissions were not changed; sandbox uid/groups or ops103 setup determines access.',
     'files':files,'OK':True}
(B/'UNPACKED-M.json').write_text(json.dumps(out,ensure_ascii=False,indent=1)+'\n')
print(json.dumps({k:v for k,v in out.items() if k!='files'},ensure_ascii=False,indent=1))
