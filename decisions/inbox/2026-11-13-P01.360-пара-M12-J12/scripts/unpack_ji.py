"""Unpack exact J-input into a new read-only tree; verify bytes against Git and passport."""
from pathlib import Path
import hashlib
import json
import stat
import subprocess
import sys
B=Path(sys.argv[1]).resolve()
I=json.loads((B/'IDENTITIES.json').read_text())
passport=Path(I['JI_directory'])/'PASSPORT-JI.json'
P=json.loads(passport.read_text())
assert P['source_C']==I['C'] and P['j_commit']==I['J'] and P['j_input_commit']==I['JI']
assert hashlib.sha256(passport.read_bytes()).hexdigest()==I['JI_passport_sha256']
root=Path(sys.argv[2]).resolve() if len(sys.argv)==3 else B/'JI'
assert not root.exists(), 'never overwrite an earlier export'
root.mkdir()
producer=subprocess.Popen(['git','--git-dir',I['JI_git'],'archive',I['JI']],stdout=subprocess.PIPE)
consumer=subprocess.run(['tar','-x','-C',str(root)],stdin=producer.stdout)
producer.stdout.close()
assert producer.wait()==consumer.returncode==0
entries={}
for row in subprocess.check_output(['git','--git-dir',I['JI_git'],'ls-tree','-rz',I['JI']]).split(b'\0'):
    if row:
        meta,path=row.split(b'\t',1)
        mode,kind,oid=meta.decode().split()
        assert kind=='blob' and mode in ('100644','100755')
        entries[path.decode()]=(mode,oid)
assert len(entries)==P['files_in_j_input']
assert subprocess.check_output(['git','--git-dir',I['JI_git'],'rev-parse',I['JI']+'^{tree}']).decode().strip()==P['j_input_tree']
assert {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}==entries.keys()
files=[]
for relative,(git_mode,blob) in sorted(entries.items()):
    path=root/relative
    assert stat.S_ISREG(path.lstat().st_mode)
    raw=path.read_bytes()
    assert hashlib.sha1(b'blob %d\0'%len(raw)+raw).hexdigest()==blob
    mode=0o555 if git_mode=='100755' else 0o444
    path.chmod(mode)
    files.append({'path':relative,'git_mode':git_mode,'blob':blob,'sha256':hashlib.sha256(raw).hexdigest(),
                  'bytes':len(raw),'filesystem_mode':oct(mode)})
for path in sorted((p for p in root.rglob('*') if p.is_dir()),reverse=True):path.chmod(0o555)
root.chmod(0o555)
assert all(not p.lstat().st_mode&0o222 for p in (root,*root.rglob('*')))
assert not (root/'.git').exists()
out={'C':I['C'],'J':I['J'],'JI':I['JI'],'directory':str(root),'files_count':len(files),
     'passport':str(passport),'passport_sha256':I['JI_passport_sha256'],
     'passport_bound_to_exact_C_J_JI':True,'all_write_bits_cleared':True,
     'exact_paths_blobs_and_executable_modes':True,'no_git_metadata':True,
     'ancestor_modes':{str(p):oct(stat.S_IMODE(p.stat().st_mode)) for p in reversed(root.parents)},
     'access_limit':'/home/pilot is 0750; sandbox access depends on its uid/groups or ops103 setup; shared ancestor permissions were not changed',
     'files':files,'OK':True}
(B/'UNPACKED-JI.json').write_text(json.dumps(out,ensure_ascii=False,indent=1)+'\n')
print(json.dumps({k:v for k,v in out.items() if k!='files'},ensure_ascii=False,indent=1))
