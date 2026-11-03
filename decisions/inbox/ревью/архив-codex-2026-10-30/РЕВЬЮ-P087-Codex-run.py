"""Verify immutable hotfix input, old/new report controls and secrecy regressions on CT103."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile

ROOT=Path(__file__).resolve().parent;OUT=Path(os.environ['CHECK_OUT'])
HEAD='9a90a2d4c16f1546793e61b107b9848fc179d566';OLD='55a6c9e5fef422a4394d519ffbab7f043a55d02a'
PIN='d389cf5e47db0902f8d660f7bb6f917eb1588925'
MANIFEST='32c1db76d5ddb1b597eeebf0bd95a5077c511dc3c82105593c6ad9acde4ebd22'
AUTHOR='02ccdd283319e149954f40747c7bdd9eba4ef1b10aa9e71f40ae00bdb4016749'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def files(root):return {str(p.relative_to(root)):sha(p) for p in root.rglob('*') if p.is_file() and '.git' not in p.relative_to(root).parts}
def extract(archive,target,commit=None):
    target.mkdir()
    with tarfile.open(archive) as stream:
        if commit:assert stream.pax_headers['comment']==commit
        stream.extractall(target,filter='data')
def blobs(root,listing):
    count=0
    for line in filter(None,listing.read_bytes().split(b'\0')):
        meta,name=line.split(b'\t',1);mode,kind,wanted=meta.split();assert kind==b'blob'
        path=root/name.decode();raw=os.readlink(path).encode() if mode==b'120000' else path.read_bytes()
        assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==wanted.decode(),name
        count+=1
    return count
packet=ROOT/'package';assert sha(packet/'MANIFEST.json')==MANIFEST
manifest=json.loads((packet/'MANIFEST.json').read_text())
for name,wanted in manifest['files'].items():assert sha(packet/name)==wanted,name
assert sha(ROOT/'author-input.tar.gz')==AUTHOR
assert (ROOT/'git.patch').read_bytes()==(packet/'change.patch').read_bytes()
with tempfile.TemporaryDirectory(prefix='rv-p087-exact-') as directory:
    work=Path(directory);verified={}
    for name,commit in [('runtime',HEAD),('old-runtime',OLD),('specs',PIN)]:
        extract(ROOT/(name+'.tar'),work/name,commit)
        verified[name]=blobs(work/name,ROOT/(name+'.ls-tree'))
    extract(ROOT/'author-input.tar.gz',work/'author');author=work/'author/in';before=files(author)
    assert files(work/'runtime')==files(author/'runner') and files(work/'specs')==files(author/'specs')
    for name,wanted in files(packet/'files').items():assert sha(work/'runtime'/name)==wanted,name
    old,new=files(work/'old-runtime'),files(work/'runtime')
    delta=sorted(name for name in set(old)|set(new) if old.get(name)!=new.get(name))
    assert delta==['runner/m11stand.py','tests/test_p087_token_names.py']
    specs=work/'specs'
    def git(*args,input=None):return subprocess.check_output(['git','-C',str(specs),*args],input=input,stderr=subprocess.PIPE).strip()
    git('init','-q')
    names=b''.join(line.split(b'\t',1)[1]+b'\0' for line in filter(None,(ROOT/'specs.ls-tree').read_bytes().split(b'\0')))
    git('add','-f','--pathspec-from-file=-','--pathspec-file-nul',input=names)
    assert git('write-tree').decode()=='028db780ac7ebaec1ac521d52b9c31eabcf34ae2'
    assert git('hash-object','-w','-t','commit','--stdin',input=(ROOT/'specs.commit').read_bytes()).decode()==PIN
    git('update-ref','HEAD',PIN)
    os.environ.update(CAMMETA_SPECS=str(specs),ONEOF_EXPORT=str(specs),PYTHONDONTWRITEBYTECODE='1',GIT_OPTIONAL_LOCKS='0')
    controls={}
    for label,runtime in [('old',work/'old-runtime'),('new',work/'runtime')]:
        out=OUT/label;out.mkdir()
        proc=subprocess.run([sys.executable,'-I','-B',str(ROOT/'probe.py'),str(runtime),str(specs),str(packet)],
                            env=dict(os.environ,CHECK_OUT=str(out)),capture_output=True,text=True,timeout=60)
        (out/'probe.txt').write_text(proc.stdout+proc.stderr);assert proc.returncode==0,(label,proc.stderr[-3000:])
        controls[label]=json.loads((out/'controls.json').read_text())
        for mode in ('none','nested','json'):
            assert controls[label][mode]['safety_pass']==(label=='new')
            assert controls[label][mode]['reported_steps']==(27 if label=='new' else 20)
    tests={}
    for name in ('test_p087_token_names','test_report_identity_secrets','test_diagnostic_secrets'):
        proc=subprocess.run([sys.executable,'-I','-B','-m','unittest','discover','-s','tests','-p',name+'.py'],
                            cwd=work/'runtime',capture_output=True,text=True,timeout=120)
        (OUT/(name+'.txt')).write_text(proc.stdout+proc.stderr);assert proc.returncode==0,(name,proc.stderr[-3000:])
        match=re.search(r'Ran (\d+) tests?',proc.stderr);assert match and int(match[1])>0,name
        tests[name]=int(match[1])
    assert files(author)==before
    evidence=dict(verified=True,head=HEAD,base=OLD,pin=PIN,manifest_sha256=MANIFEST,package_files=len(manifest['files']),
                  git_blobs=verified,changed_files=delta,author_input_sha256=AUTHOR,author_input_files=len(before),
                  inputs_unchanged=True,SUT=0,tests=tests,total_tests=sum(tests.values()),controls=controls,
                  probe_sha256=sha(ROOT/'probe.py'))
    (OUT/'review-evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in evidence.items() if k!='controls'},ensure_ascii=False),flush=True)
