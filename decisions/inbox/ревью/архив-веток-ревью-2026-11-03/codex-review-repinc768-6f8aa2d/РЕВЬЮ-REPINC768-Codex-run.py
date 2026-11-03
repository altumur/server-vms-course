"""Exact pin, inputs and selected qualification reports; no implementation source analysis or SUT run."""
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
HEAD='6f8aa2d45f31cfac180df24da2ab4a30f396ec17';OLD='f30caad1f183d1e1af332b14c9336e3740fa2dc0'
BRIDGE='2431a52af601ffd646d369f5c7fe0bf25b3ed063';PIN='c768d17f8fc56e831b9cc5130e9e88606bd1cce8'
OLDPIN='f1139f29118c196d3bcbd280a48f74403d94feec';BRIDGEPIN='340cf846850d9bf729e635ee04c95105b6c7f604'
MANIFEST='5f799453d24ffa6fd5b246cbe2892ef4bd477c0c3af167aaedcf33783062c3a5'
AUTHOR='1563240c9d54d8945a931b018517cf754c916146c2ca23b71ddd8d59ed626b6d'
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
assert (ROOT/'git.patch').read_bytes()==(packet/'change-from-main-f30caad.patch').read_bytes()
selected_results={}
for check in ('20261030T184850Z-repinc768-V7','20261030T183121Z-repin340-Go','20261030T184857Z-repinc768-Go'):
    rmanifest=json.loads((packet/'evidence'/check/'RESULT-MANIFEST.json').read_text())
    selected=files(packet/'evidence'/check/'out')
    for name,wanted in selected.items():assert wanted==rmanifest['files']['out/'+name]['sha256'],(check,name)
    selected_results[check]=len(selected)
with tempfile.TemporaryDirectory(prefix='rv-repinc768-') as directory:
    work=Path(directory);verified={}
    for name,commit in [('runtime',HEAD),('old-runtime',OLD),('bridge-runtime',BRIDGE),
                        ('specs',PIN),('old-specs',OLDPIN),('bridge-specs',BRIDGEPIN)]:
        extract(ROOT/(name+'.tar'),work/name,commit);verified[name]=blobs(work/name,ROOT/(name+'.ls-tree'))
    extract(ROOT/'author-input.tar.gz',work/'author');author=work/'author/in';before=files(author)
    assert files(work/'runtime')==files(author/'runner') and files(work/'specs')==files(author/'specs')
    for name,wanted in files(packet/'source').items():assert sha(work/'runtime'/name)==wanted,name
    for name,wanted in files(packet/'norms').items():assert sha(work/'specs'/name)==wanted,name
    old,new=files(work/'old-runtime'),files(work/'runtime')
    delta=sorted(k for k in set(old)|set(new) if old.get(k)!=new.get(k))
    assert delta==['README.md','SPEC_VERSION','runner/l09.py','tests/test_stand_0106_audit.py','tests/test_store_audit.py','tests/test_store_group.py']
    bridge=files(work/'bridge-runtime')
    assert sorted(k for k in set(bridge)|set(new) if bridge.get(k)!=new.get(k))==['README.md','SPEC_VERSION']
    export=json.loads((packet/'reproduce/20261030T184850Z-repinc768-V7/EXPORT-DELTA.json').read_text())
    old_spec,new_spec=files(work/'old-specs'),files(work/'specs')
    export_names=sorted(k for k in set(old_spec)|set(new_spec) if old_spec.get(k)!=new_spec.get(k))
    assert export_names==sorted((ROOT/'export-names.txt').read_text().splitlines())==sorted(v['path'] for v in export['files'])
    assert len(export_names)==25
    for item in export['files']:
        assert item['before_sha256']==old_spec.get(item['path']) and item['after_sha256']==new_spec.get(item['path'])
    equality=json.loads((packet/'repin340-to-c768-equality.json').read_text())
    assert len(equality['unchanged_data_sha256'])==2029
    for name,wanted in equality['unchanged_data_sha256'].items():
        assert sha(work/'bridge-specs'/name)==sha(work/'specs'/name)==wanted,name
    changed=equality['changed_data'];assert len(changed)==1 and changed[0]['path']=='Platform/01-store/acceptance/1/scenarios.tsv'
    for row in changed:
        assert sha(work/'bridge-specs'/row['path'])==row['before_sha256'] and sha(work/'specs'/row['path'])==row['after_sha256']
    bridge_spec=files(work/'bridge-specs')
    assert sorted(k for k in set(bridge_spec)|set(new_spec) if bridge_spec.get(k)!=new_spec.get(k))==[
        'COURSE_COMMIT','Platform/01-store/acceptance/1/scenarios.tsv','Platform/01-store/spec/01.1-store.norms.md','Platform/01-store/spec/01.3-store.norms.md']
    specs=work/'specs'
    def git(*args,input=None):return subprocess.check_output(['git','-C',str(specs),*args],input=input,stderr=subprocess.PIPE).strip()
    git('init','-q');names=b''.join(line.split(b'\t',1)[1]+b'\0' for line in filter(None,(ROOT/'specs.ls-tree').read_bytes().split(b'\0')))
    git('add','-f','--pathspec-from-file=-','--pathspec-file-nul',input=names)
    assert git('write-tree').decode()=='706e29b831d8c4383ee7cc18a42cd39dc21df787'
    assert git('hash-object','-w','-t','commit','--stdin',input=(ROOT/'specs.commit').read_bytes()).decode()==PIN
    git('update-ref','HEAD',PIN)
    controls={}
    for label,runtime,spec in [('old',work/'old-runtime',work/'old-specs'),('new',work/'runtime',specs)]:
        out=OUT/label;out.mkdir()
        env=dict(os.environ,CHECK_OUT=str(out),CAMMETA_SPECS=str(spec),ONEOF_EXPORT=str(spec),PYTHONDONTWRITEBYTECODE='1',GIT_OPTIONAL_LOCKS='0')
        proc=subprocess.run([sys.executable,'-I','-B',str(ROOT/'probe.py'),str(runtime),str(spec),str(packet),label],env=env,capture_output=True,text=True,timeout=120)
        (out/'probe.txt').write_text(proc.stdout+proc.stderr);assert proc.returncode==0,(label,proc.stderr[-3000:])
        controls[label]=json.loads((out/'controls.json').read_text())
    os.environ.update(CAMMETA_SPECS=str(specs),ONEOF_EXPORT=str(specs),PYTHONDONTWRITEBYTECODE='1',GIT_OPTIONAL_LOCKS='0')
    tests={}
    for name in ('test_store_audit','test_store_group','test_stand_0106_audit','test_audit_e','test_c_shared_engines','test_c_execution'):
        proc=subprocess.run([sys.executable,'-I','-B','-m','unittest','discover','-s','tests','-p',name+'.py'],cwd=work/'runtime',capture_output=True,text=True,timeout=180)
        (OUT/(name+'.txt')).write_text(proc.stdout+proc.stderr);assert proc.returncode==0,(name,proc.stderr[-3000:])
        match=re.search(r'Ran (\d+) tests?',proc.stderr);assert match and int(match[1])>0,name
        tests[name]=int(match[1])
    assert files(author)==before
    evidence=dict(verified=True,head=HEAD,base=OLD,pin=PIN,manifest_sha256=MANIFEST,package_files=len(manifest['files']),
                  git_blobs=verified,changed_files=delta,export_files=25,reused_equal_data=2029,
                  bridge_code_equal=True,selected_result_files=selected_results,author_input_sha256=AUTHOR,
                  author_input_files=len(before),inputs_unchanged=True,own_SUT=0,tests=tests,total_tests=sum(tests.values()),
                  controls=controls,probe_sha256=sha(ROOT/'probe.py'))
    (OUT/'review-evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in evidence.items() if k!='controls'},ensure_ascii=False),flush=True)
