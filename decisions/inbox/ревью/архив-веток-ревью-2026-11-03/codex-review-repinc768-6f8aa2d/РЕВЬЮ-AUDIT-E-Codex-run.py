"""Exact E packet, Git blobs, author input/results and independent old/new controls; CT103."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile

ROOT=Path(__file__).resolve().parent; OUT=Path(os.environ['CHECK_OUT'])
HEAD='f30caad1f183d1e1af332b14c9336e3740fa2dc0'
OLD='4dbe5d20d563e6b22cbec695dcdceb38c0eb59de'
PIN='f1139f29118c196d3bcbd280a48f74403d94feec'
MANIFEST='63aaf07367205c3b7e2a86b8cdc98bfaa650b0cf50f180a8a4c564893cdc46d7'
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
packet=ROOT/'package'; assert sha(packet/'MANIFEST.json')==MANIFEST
manifest=json.loads((packet/'MANIFEST.json').read_text())
for name,wanted in manifest['files'].items():assert sha(packet/name)==wanted,name
assert (ROOT/'git.patch').read_bytes()==(packet/'change-from-main-4dbe5d2.patch').read_bytes()
checks={row['id']:row for row in json.loads((packet/'CHECKS.json').read_text())}
v7='20261030T180032Z-audit-E-final-V7';sut='20261030T180039Z-audit-E-final-Go'
assert sha(ROOT/'author-input.tar.gz')==checks[v7]['input_sha256']
assert sha(ROOT/'author-result.tar.gz')==checks[v7]['result_sha256']
assert sha(ROOT/'sut-result.tar.gz')==checks[sut]['result_sha256']
with tempfile.TemporaryDirectory(prefix='rv-audit-E-') as directory:
    work=Path(directory)
    git_blobs={}
    for name,commit in [('runtime',HEAD),('old-runtime',OLD),('specs',PIN)]:
        extract(ROOT/(name+'.tar'),work/name,commit)
        git_blobs[name]=blobs(work/name,ROOT/(name+'.ls-tree'))
    extract(ROOT/'author-input.tar.gz',work/'author')
    author=work/'author/in'; before=files(author)
    assert files(author/'runner')==files(work/'runtime')
    assert files(author/'specs')==files(work/'specs')
    for name,wanted in json.loads((packet/'reproduce'/v7/'SOURCE-SHA.json').read_text()).items():
        assert sha(author/name)==wanted,name
    for name,wanted in files(packet/'source').items():assert sha(work/'runtime'/name)==wanted,name
    new_files,old_files=files(work/'runtime'),files(work/'old-runtime')
    delta=sorted(k for k in set(new_files)|set(old_files) if new_files.get(k)!=old_files.get(k))
    assert delta==['README.md','runner/l03.py','runner/l09.py','tests/test_audit_e.py'],delta
    result_counts={}
    for label,check,archive in [('v7',v7,'author-result.tar.gz'),('sut',sut,'sut-result.tar.gz')]:
        extract(ROOT/archive,work/label)
        result=work/label/'result'
        rmanifest=json.loads((packet/'evidence'/check/'RESULT-MANIFEST.json').read_text())
        for name,description in rmanifest['files'].items():assert sha(result/name)==description['sha256'],name
        for name,wanted in files(packet/'evidence'/check/'out').items():assert sha(result/'out'/name)==wanted,name
        result_counts[label]=len(rmanifest['files'])
    full=json.loads((work/'v7/result/out/summary.json').read_text())
    assert full['green'] and full['inputs_unchanged'] and (full['modules'],full['tests'],full['skipped'])==(98,1129,8)
    dry=json.loads((work/'sut/result/out/summary.json').read_text())
    assert dry['green'] and dry['inputs_unchanged'] and dry['runner_commit']==HEAD and dry['runner_pin']==PIN
    assert (dry['scenarios'],dry['passed_steps'],dry['total_steps'])==(17,134,134)
    scope=json.loads((packet/'SCOPE.json').read_text()); expected={}
    for entry in scope:
        for number,line in enumerate((work/'specs'/entry['path']).read_text().splitlines(),1):
            cells=line.split('\t')
            if len(cells)>=4 and cells[0] in entry['names']:expected.setdefault(cells[0],[]).append((cells[1],number))
    for number,line in enumerate((work/'specs/Platform/05-resource/acceptance/scenarios.tsv').read_text().splitlines(),1):
        cells=line.split('\t')
        if len(cells)>=4 and cells[0].startswith('23-'):expected.setdefault(cells[0],[]).append((cells[1],number))
    assert len(expected)==17 and sum(map(len,expected.values()))==134
    for qualification in dry['qualifications']:
        name=qualification['scenario']; assert name in expected
        path=qualification['report'].split('/result/',1)[1]
        report=json.loads((work/'sut/result'/path).read_text()); steps=report['scenarios'][name]
        if isinstance(steps,dict):steps=steps['steps']
        assert [(s['step'],s['line']) for s in steps]==expected[name],name
        assert all(s['ok'] is True for s in steps) and qualification['green'] and not qualification['coverage_errors']
    specs=work/'specs'
    def git(*args,input=None):return subprocess.check_output(['git','-C',str(specs),*args],input=input,stderr=subprocess.PIPE).strip()
    git('init','-q')
    names=b''.join(line.split(b'\t',1)[1]+b'\0' for line in filter(None,(ROOT/'specs.ls-tree').read_bytes().split(b'\0')))
    git('add','-f','--pathspec-from-file=-','--pathspec-file-nul',input=names)
    assert git('write-tree').decode()=='eb7adb116cabe734c9e677c9144397ea9539a9cf'
    assert git('hash-object','-w','-t','commit','--stdin',input=(ROOT/'specs.commit').read_bytes()).decode()==PIN
    git('update-ref','HEAD',PIN)
    os.environ.update(CAMMETA_SPECS=str(specs),ONEOF_EXPORT=str(specs),PYTHONDONTWRITEBYTECODE='1',GIT_OPTIONAL_LOCKS='0')
    controls={}
    for label,runtime in [('old',work/'old-runtime'),('new',work/'runtime')]:
        out=OUT/label;out.mkdir()
        proc=subprocess.run([sys.executable,'-I','-B',str(ROOT/'probe.py'),str(runtime),str(specs)],
                            env=dict(os.environ,CHECK_OUT=str(out)),capture_output=True,text=True,timeout=60)
        (out/'probe.txt').write_text(proc.stdout+proc.stderr)
        assert proc.returncode==0,(label,proc.stderr[-3000:])
        controls[label]=json.loads((out/'controls.json').read_text())
        for row in controls[label]['duplicate_controls']:assert row['rejected']==(label=='new' or not row['reordered']),row
        for row in controls[label]['writer_controls']:assert row['correct_order']==(label=='new'),row
    assert controls['old']['legacy_malformed']==controls['new']['legacy_malformed']
    tests={}
    for name in ('test_audit_e','test_c_shared_engines','test_request_correlation','test_transport_diagnostics','test_c_execution'):
        proc=subprocess.run([sys.executable,'-I','-B','-m','unittest','discover','-s','tests','-p',name+'.py'],
                            cwd=work/'runtime',capture_output=True,text=True,timeout=180)
        (OUT/(name+'.txt')).write_text(proc.stdout+proc.stderr);assert proc.returncode==0,(name,proc.stderr[-3000:])
        match=re.search(r'Ran (\d+) tests?',proc.stderr);assert match and int(match[1])>0,name
        tests[name]=int(match[1])
    assert files(author)==before
    evidence=dict(verified=True,head=HEAD,base=OLD,pin=PIN,manifest_sha256=MANIFEST,
                  package_files=len(manifest['files']),git_blobs=git_blobs,changed_files=delta,
                  author_input_files=len(before),author_input_sha256=sha(ROOT/'author-input.tar.gz'),inputs_unchanged=True,
                  archived_result_files=result_counts,author_full_v7=dict(modules=98,tests=1129,skipped=8),
                  author_dry_sut=dict(commit=dry['SUT_commit'],profile_pin=dry['profile_pin'],scenarios=17,steps=134),
                  own_SUT=0,tests=tests,total_tests=sum(tests.values()),controls=controls,
                  probe_sha256=sha(ROOT/'probe.py'))
    (OUT/'review-evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in evidence.items() if k!='controls'},ensure_ascii=False),flush=True)
