"""Unchanged original controls plus independent clean-before-export on r1/r2; CT103."""
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
OLD='8c4db0d7da1d9716876aedd447876625adc2a049'
NEW='fd1af474158189a737a122ae4e2166e842dbe750'
MANIFEST='a2215170882bf4185fcec5cc8a86281fd5d6c66fc5849b080fd0e719a3f6db27'
PROBE='1d3ec87223b0b15a071586e789b265a1a953b9ebc74eaee315bb5f6f85dc1f6d'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def extract(archive,target,commit):
    target.mkdir()
    with tarfile.open(archive) as stream:
        assert stream.pax_headers['comment']==commit;stream.extractall(target,filter='data')
def blobs(root,listing):
    count=0
    for entry in filter(None,listing.read_bytes().split(b'\0')):
        metadata,name=entry.split(b'\t',1);mode,kind,wanted=metadata.split();assert kind==b'blob'
        p=root/name.decode();data=os.readlink(p).encode() if mode==b'120000' else p.read_bytes()
        assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==wanted.decode(),name
        count+=1
    return count
assert sha(ROOT/'probe.py')==PROBE
package=ROOT/'package';assert sha(package/'MANIFEST.json')==MANIFEST
manifest=json.loads((package/'MANIFEST.json').read_text())
for name,wanted in manifest['files'].items():assert sha(package/name)==wanted,name
with tempfile.TemporaryDirectory(prefix='rv-rid-r2-') as directory:
    work=Path(directory);extract(ROOT/'specs.tar',work/'specs','d389cf5e47db0902f8d660f7bb6f917eb1588925')
    os.environ.update(CAMMETA_SPECS=str(work/'specs'),ONEOF_EXPORT=str(work/'specs'),PYTHONDONTWRITEBYTECODE='1')
    controls={};extra={};git_blobs={}
    for label,commit in [('old',OLD),('new',NEW)]:
        runtime=work/label;extract(ROOT/(label+'.tar'),runtime,commit)
        git_blobs[label]=blobs(runtime,ROOT/(label+'.ls-tree'))
        if label=='new':
            for name,wanted in manifest['files'].items():
                if name.startswith('files/'):assert sha(runtime/name[6:])==wanted,name
        out=OUT/label;out.mkdir()
        for filename in ('probe.py','extra.py'):
            proc=subprocess.run([sys.executable,'-I','-B',str(ROOT/filename),str(runtime)],
                                env=dict(os.environ,CHECK_OUT=str(out)),capture_output=True,text=True,timeout=60)
            (out/(filename+'.txt')).write_text(proc.stdout+proc.stderr)
            assert proc.returncode==0,(label,filename,proc.stdout,proc.stderr)
        controls[label]=json.loads((out/'controls.json').read_text())
        extra[label]=json.loads((out/'extra-controls.json').read_text())
    tests={}
    for name in ('test_report_identity_secrets','test_diagnostic_secrets','test_judge_diagnostics'):
        proc=subprocess.run([sys.executable,'-I','-B','-m','unittest','discover','-s','tests','-p',name+'.py'],
                            cwd=work/'new',capture_output=True,text=True,timeout=90)
        (OUT/(name+'.txt')).write_text(proc.stdout+proc.stderr)
        assert proc.returncode==0,(name,proc.stdout,proc.stderr)
        tests[name]=int(re.search(r'Ran (\d+) tests?',proc.stderr)[1])
    result=dict(green=all(r['safety_pass'] for r in controls['new'].values()) and all(r['safety_pass'] for r in extra['new'].values()),
                SUT=0,manifest_sha256=MANIFEST,package_files=len(manifest['files']),git_blobs=git_blobs,
                probe_sha256=PROBE,extra_sha256=sha(ROOT/'extra.py'),tests=tests,controls=controls,extra=extra)
    (OUT/'review-evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False),flush=True);raise SystemExit(not result['green'])
