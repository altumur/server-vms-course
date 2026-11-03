"""Review frozen B inputs and independent boundary controls. CT 103 only."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile

ROOT=Path(__file__).resolve().parent
OUT=Path(os.environ['CHECK_OUT'])
HEAD='1a56ad153c056b0f208254d9d554ef837c21c219'
PIN='d389cf5e47db0902f8d660f7bb6f917eb1588925'
BASEPIN='d94271707b43ab2b9e8ec52a4a14cf7fbd69ac59'
MANIFEST='0c8226bceea341c400b49bbe8c051cd26959015e14602e9c0906ba5784a7bf2c'
INPUT='cc84609a5c63314ea9c0bdc814182f61ad9d9cf6a917385723c37c42958bbb3f'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def files(root):
    return {str(p.relative_to(root)):sha(p) for p in root.rglob('*')
            if p.is_file() and '.git' not in p.relative_to(root).parts}
def extract(archive,target,commit=None):
    target.mkdir()
    with tarfile.open(archive) as stream:
        if commit:assert stream.pax_headers['comment']==commit
        stream.extractall(target,filter='data')
def blobs(root,listing):
    count=0
    for entry in filter(None,listing.read_bytes().split(b'\0')):
        metadata,name=entry.split(b'\t',1);mode,kind,wanted=metadata.split();assert kind==b'blob'
        path=root/name.decode()
        data=os.readlink(path).encode() if mode==b'120000' else path.read_bytes()
        assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==wanted.decode(),name
        count+=1
    return count

package=ROOT/'package'
assert sha(package/'MANIFEST.json')==MANIFEST
manifest=json.loads((package/'MANIFEST.json').read_text());assert manifest['commit']==HEAD
for name,wanted in manifest['files'].items():assert sha(package/name)==wanted,name
assert sha(ROOT/'author-input.tar.gz')==INPUT
with tempfile.TemporaryDirectory(prefix='rv-installer-B-') as directory:
    work=Path(directory)
    extract(ROOT/'author-input.tar.gz',work/'author')
    extract(ROOT/'runtime.tar',work/'runtime',HEAD)
    extract(ROOT/'old-specs.tar',work/'old-specs',BASEPIN)
    author=work/'author/in';runtime=work/'runtime';specs=author/'specs'
    before=files(author)
    source=json.loads((author/'SOURCE-SHA.json').read_text())
    for name,wanted in source.items():assert sha(author/name)==wanted,name
    git_blobs=dict(runtime=blobs(runtime,ROOT/'runtime.ls-tree'),
                   specs=blobs(specs,ROOT/'specs.ls-tree'),old_specs=blobs(work/'old-specs',ROOT/'old-specs.ls-tree'))
    assert files(runtime)==files(author/'runner')
    for name,wanted in files(package/'source').items():assert sha(runtime/name)==wanted,name
    for name,wanted in files(package/'normative-delta').items():assert sha(specs/name)==wanted,name
    old,new=files(work/'old-specs'),files(specs)
    changed=sorted(name for name in old.keys()|new.keys() if old.get(name)!=new.get(name))
    delta=json.loads((package/'EXPORT-DELTA.json').read_text())
    assert delta['base']==BASEPIN and delta['pin']==PIN
    assert changed==sorted(row['path'] for row in delta['files']) and len(changed)==46
    for row in delta['files']:
        assert old.get(row['path'])==row['before_sha256'] and new.get(row['path'])==row['after_sha256']
    # The large new input is a comment-only padding change, not new manifest data.
    base=specs/'Platform/02-installer/acceptance/3/puts/toolarge-base.subsystem.yaml'
    big=base.with_name('toolarge-big.subsystem.yaml')
    assert big.read_bytes().startswith(base.read_bytes())
    padding=big.read_bytes()[len(base.read_bytes()):]
    assert padding.startswith(b'#') and set(padding)<=set(b'#x\n')
    os.environ.update(CAMMETA_SPECS=str(specs),ONEOF_EXPORT=str(specs),PYTHONDONTWRITEBYTECODE='1',GIT_OPTIONAL_LOCKS='0')
    tests={}
    for name in ('test_installer_audit_b','test_c_installer','test_c_exported_manifest','test_c_execution',
                 'test_c_domain_pin','test_diagnostic_secrets','test_c_process','test_runner'):
        proc=subprocess.run([sys.executable,'-I','-B','-m','unittest','discover','-s','tests','-p',name+'.py'],
                            cwd=runtime,capture_output=True,text=True,timeout=180)
        (OUT/(name+'.txt')).write_text(proc.stdout+proc.stderr)
        assert proc.returncode==0,(name,proc.stdout[-500:],proc.stderr[-4000:])
        tests[name]=int(re.search(r'Ran (\d+) tests?',proc.stderr)[1])
    proc=subprocess.run([sys.executable,'-I','-B',str(ROOT/'probe.py'),str(runtime),str(specs)],
                        capture_output=True,text=True,timeout=150)
    (OUT/'probe.txt').write_text(proc.stdout+proc.stderr)
    assert proc.returncode==0,(proc.stdout,proc.stderr)
    controls=json.loads((OUT/'controls.json').read_text())
    assert all(row['safety_pass'] for row in controls.values())
    assert files(author)==before
    summary=dict(green=True,SUT=0,head=HEAD,pin=PIN,manifest_sha256=MANIFEST,package_files=len(manifest['files']),
                 author_input_sha256=INPUT,author_input_files=len(before),source_sha_files=len(source),git_blobs=git_blobs,
                 changed_export_files=changed,padding_bytes=len(padding),tests=tests,total_tests=sum(tests.values()),
                 probe_sha256=sha(ROOT/'probe.py'),controls=controls,inputs_unchanged=True)
    (OUT/'review-evidence.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('controls','changed_export_files')},ensure_ascii=False),flush=True)
