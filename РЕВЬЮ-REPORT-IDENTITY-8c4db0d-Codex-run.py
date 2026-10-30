"""Verify frozen packet and compare unchanged provenance controls on two snapshots."""
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
OLD='1a56ad153c056b0f208254d9d554ef837c21c219'
NEW='8c4db0d7da1d9716876aedd447876625adc2a049'
MANIFEST='8c795130a2376d574b35e3df7171b608b5e23a4ec4762d2b2ba4fe749f4f64c5'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def extract(archive,target,commit):
    target.mkdir()
    with tarfile.open(archive) as stream:
        assert stream.pax_headers['comment']==commit
        stream.extractall(target,filter='data')
def blobs(root,listing):
    count=0
    for entry in filter(None,listing.read_bytes().split(b'\0')):
        metadata,name=entry.split(b'\t',1);mode,kind,wanted=metadata.split();assert kind==b'blob'
        p=root/name.decode();data=os.readlink(p).encode() if mode==b'120000' else p.read_bytes()
        assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==wanted.decode(),name
        count+=1
    return count
package=ROOT/'package';assert sha(package/'MANIFEST.json')==MANIFEST
manifest=json.loads((package/'MANIFEST.json').read_text())
for name,wanted in manifest['files'].items():assert sha(package/name)==wanted,name
with tempfile.TemporaryDirectory(prefix='rv-rid-') as directory:
    work=Path(directory);extract(ROOT/'specs.tar',work/'specs','d389cf5e47db0902f8d660f7bb6f917eb1588925')
    os.environ.update(CAMMETA_SPECS=str(work/'specs'),ONEOF_EXPORT=str(work/'specs'),PYTHONDONTWRITEBYTECODE='1')
    controls={};git_blobs={}
    for label,commit in [('old',OLD),('new',NEW)]:
        runtime=work/label;extract(ROOT/(label+'.tar'),runtime,commit)
        git_blobs[label]=blobs(runtime,ROOT/(label+'.ls-tree'))
        if label=='new':
            for name,wanted in manifest['files'].items():
                if name.startswith('files/'):assert sha(runtime/name[6:])==wanted,name
        out=OUT/label;out.mkdir()
        proc=subprocess.run([sys.executable,'-I','-B',str(ROOT/'probe.py'),str(runtime)],
                             env=dict(os.environ,CHECK_OUT=str(out)),capture_output=True,text=True,timeout=60)
        (out/'probe.txt').write_text(proc.stdout+proc.stderr)
        assert proc.returncode==0,(label,proc.stdout,proc.stderr)
        controls[label]=json.loads((out/'controls.json').read_text())
    tests={}
    for name in ('test_report_identity_secrets','test_diagnostic_secrets'):
        proc=subprocess.run([sys.executable,'-I','-B','-m','unittest','discover','-s','tests','-p',name+'.py'],
                            cwd=work/'new',capture_output=True,text=True,timeout=90)
        (OUT/(name+'.txt')).write_text(proc.stdout+proc.stderr)
        assert proc.returncode==0,(name,proc.stdout,proc.stderr)
        tests[name]=int(re.search(r'Ran (\d+) tests?',proc.stderr)[1])
    result=dict(green=all(row['safety_pass'] for row in controls['new'].values()),SUT=0,
                manifest_sha256=MANIFEST,package_files=len(manifest['files']),git_blobs=git_blobs,
                probe_sha256=sha(ROOT/'probe.py'),tests=tests,controls=controls)
    (OUT/'review-evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False),flush=True)
    raise SystemExit(not result['green'])
