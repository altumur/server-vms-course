"""Exact R4 packet, merge delta, author input, native boundary controls on two snapshots; CT103."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parent; OUT = Path(os.environ['CHECK_OUT'])
HEAD = '4dbe5d20d563e6b22cbec695dcdceb38c0eb59de'; OLD = '4b50e7fbd02ddbe5052765df7e9ce214bf238310'
PIN = 'f1139f29118c196d3bcbd280a48f74403d94feec'; OLDPIN = '82490f29dcc5bd47e98f6b806e9b115d7a930e32'
MANIFEST = '43438c16ff7a9b1996e16d1714447a9f0866b507961defc29b6d2d6873f7d3fa'
AUTHOR = '9585021bc4f4b71ef93f07c3923a90890c5a4c5fce8883940cbaf309cc4ecde1'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def files(root): return {str(p.relative_to(root)):sha(p) for p in root.rglob('*') if p.is_file() and '.git' not in p.relative_to(root).parts}
def extract(archive,target,commit=None):
    target.mkdir()
    with tarfile.open(archive) as stream:
        if commit: assert stream.pax_headers['comment'] == commit
        stream.extractall(target,filter='data')
def blobs(root,listing):
    count=0
    for line in filter(None,listing.read_bytes().split(b'\0')):
        meta,name=line.split(b'\t',1);mode,kind,wanted=meta.split();assert kind==b'blob'
        path=root/name.decode();raw=os.readlink(path).encode() if mode==b'120000' else path.read_bytes()
        assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==wanted.decode(),name
        count+=1
    return count
def normalized(path):
    lines=[line for line in path.read_text().splitlines() if not line.startswith('index ')]
    return [re.sub(r'^@@ -\d+(,\d+)? \+\d+(,\d+)? @@','@@',line) for line in lines]
packet=ROOT/'package';assert sha(packet/'MANIFEST.json')==MANIFEST
manifest=json.loads((packet/'MANIFEST.json').read_text())
for name,wanted in manifest['files'].items():assert sha(packet/name)==wanted,name
assert sha(ROOT/'author-input.tar.gz')==AUTHOR
assert normalized(ROOT/'old-base.patch')==normalized(ROOT/'new-base.patch')
with tempfile.TemporaryDirectory(prefix='rv-p08-r4-') as directory:
    work=Path(directory)
    commits={'runtime':HEAD,'old-runtime':OLD,'specs':PIN,'old-specs':OLDPIN}
    for name,commit in commits.items():extract(ROOT/(name+'.tar'),work/name,commit)
    extract(ROOT/'author-input.tar.gz',work/'author')
    author=work/'author/in';before=files(author)
    verified={name:blobs(work/name,ROOT/(name+'.ls-tree')) for name in commits}
    assert files(work/'runtime')==files(author/'runner') and files(work/'specs')==files(author/'specs')
    for name,wanted in files(packet/'files').items():assert sha(work/'runtime'/name)==wanted,name
    controls={}
    for label,runtime,specs,pin,tree in [('old',work/'old-runtime',work/'old-specs',OLDPIN,'57ea8fde730478c643f842a34855f0b3f080a9b1'),
                                       ('new',work/'runtime',work/'specs',PIN,'eb7adb116cabe734c9e677c9144397ea9539a9cf')]:
        prefix='old-specs' if label=='old' else 'specs'
        def git(*args,input=None):return subprocess.check_output(['git','-C',str(specs),*args],input=input,stderr=subprocess.PIPE).strip()
        git('init','-q')
        names=b''.join(line.split(b'\t',1)[1]+b'\0' for line in filter(None,(ROOT/(prefix+'.ls-tree')).read_bytes().split(b'\0')))
        git('add','-f','--pathspec-from-file=-','--pathspec-file-nul',input=names)
        assert git('write-tree').decode()==tree
        assert git('hash-object','-w','-t','commit','--stdin',input=(ROOT/(prefix+'.commit')).read_bytes()).decode()==pin
        git('update-ref','HEAD',pin)
        os.environ.update(CAMMETA_SPECS=str(specs),ONEOF_EXPORT=str(specs),PYTHONDONTWRITEBYTECODE='1',GIT_OPTIONAL_LOCKS='0')
        out=OUT/label;out.mkdir()
        for script in ('original.py','probe.py'):
            proc=subprocess.run([sys.executable,'-I','-B',str(ROOT/script),str(runtime),str(specs)],
                env=dict(os.environ,CHECK_OUT=str(out)),capture_output=True,text=True,timeout=120)
            (out/(script+'.txt')).write_text(proc.stdout+proc.stderr)
            assert proc.returncode==0,(label,script,proc.stderr[-3000:])
        controls[label]=dict(original=json.loads((out/'exceptions.json').read_text()),raw_identity=json.loads((out/'identity.json').read_text()),
                             boundary=json.loads((out/'boundary-controls.json').read_text()))
    for label in ('old','new'):
        wanted=label=='new';c=controls[label]['boundary']
        assert all(row['safety_pass']==wanted for row in c['names_main_finalize_coverage'].values())
        assert all(row['safety_pass']==wanted for row in c['outside_faults'].values())
        assert c['tls_names']['safety_pass']==wanted
        assert all(row['safety_pass']==wanted for name,row in c['object_commands'].items() if name in ('P/08.3/stand','P/10/stand'))
        assert c['object_commands']['P/09.1/stand']['safety_pass']
        assert controls[label]['original']['safety_pass'] and not controls[label]['raw_identity']['safety_pass']
    os.environ.update(CAMMETA_SPECS=str(work/'specs'),ONEOF_EXPORT=str(work/'specs'))
    tests={}
    for name in ('test_domain_freeze','test_c_domain_pin','test_openapi_refs','test_scenario_control','test_c_domain_stand',
                 'test_c_execution','test_report_identity_secrets','test_diagnostic_secrets','test_c_shared_engines'):
        p=subprocess.run([sys.executable,'-I','-B','-m','unittest','discover','-s','tests','-p',name+'.py'],
            cwd=work/'runtime',capture_output=True,text=True,timeout=180)
        (OUT/(name+'.txt')).write_text(p.stdout+p.stderr);assert p.returncode==0,(name,p.stderr[-3000:])
        tests[name]=int(re.search(r'Ran (\d+) tests?',p.stderr)[1])
    command="import sys,unittest;sys.path.insert(0,'tests');s=unittest.defaultTestLoader.loadTestsFromName('test_tls_stage.StageTests.test_scenario_names_with_sensitive_words_survive_the_report');r=unittest.TextTestRunner().run(s);sys.exit(not r.wasSuccessful())"
    p=subprocess.run([sys.executable,'-I','-B','-c',command],cwd=work/'runtime',capture_output=True,text=True,timeout=60)
    (OUT/'tls-name-test.txt').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr
    assert files(author)==before
    result=dict(verified=True,SUT=0,head=HEAD,previous=OLD,pin=PIN,manifest_sha256=MANIFEST,package_files=len(manifest['files']),
        git_blobs=verified,merge_delta_identical=True,author_input_sha256=AUTHOR,author_input_files=len(before),inputs_unchanged=True,
        tests=tests,total_tests=sum(tests.values()),tls_changed_test=1,controls=controls,
        probe_sha256=sha(ROOT/'probe.py'),original_probe_sha256=sha(ROOT/'original.py'))
    (OUT/'review-evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({key:value for key,value in result.items() if key!='controls'},ensure_ascii=False),flush=True)
