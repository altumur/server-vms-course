"""Repeat the unchanged review probe on exact old/new archives; CT 103 only."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parent
OUT = Path(os.environ['CHECK_OUT'])
OLD = 'f7e4b38d5e98eae6a1b44e875484b09397f8a905'
NEW = 'b7f2f55efaedbc64c2848ded5538e4bff2792a19'
MANIFEST = '5e1eaba603e449ae3383e54f79e0285080f461b29ced0c30e9399f7845117fe7'
INPUT = 'db5a4c670bbd8ebf50a80517ee7bee9b29a03c72cff723e109b48c79cf71b895'
PROBE = '929678519bfbbf2774bf727fccd9466f6f0eb78a845687c7fd9550f34cbbaae5'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def files(root):
    return {str(p.relative_to(root)): sha(p) for p in root.rglob('*')
            if p.is_file() and '.git' not in p.relative_to(root).parts}
def extract(archive, target, commit=None):
    target.mkdir()
    with tarfile.open(archive) as stream:
        if commit: assert stream.pax_headers['comment'] == commit
        stream.extractall(target, filter='data')
def blobs(root, listing):
    count = 0
    for entry in filter(None, listing.read_bytes().split(b'\0')):
        metadata, name = entry.split(b'\t', 1)
        mode, kind, wanted = metadata.split()
        assert kind == b'blob'
        p = root / name.decode()
        data = os.readlink(p).encode() if mode == b'120000' else p.read_bytes()
        assert hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == wanted.decode(), name
        count += 1
    return count

assert sha(ROOT / 'probe.py') == PROBE
package = ROOT / 'package'
assert sha(package / 'MANIFEST.json') == MANIFEST
manifest = json.loads((package / 'MANIFEST.json').read_text())
assert manifest['commit'] == NEW
for name, wanted in manifest['files'].items(): assert sha(package / name) == wanted, name
assert sha(ROOT / 'author-input.tar.gz') == INPUT
with tempfile.TemporaryDirectory(prefix='rv-store-a-r2-') as directory:
    work = Path(directory)
    extract(ROOT / 'author-input.tar.gz', work / 'author')
    author = work / 'author/in'; specs = author / 'specs'
    before = files(author)
    source = json.loads((author / 'SOURCE-SHA.json').read_text())
    for name, wanted in source.items(): assert sha(author / name) == wanted, name
    os.environ.update(CAMMETA_SPECS=str(specs), ONEOF_EXPORT=str(specs), PYTHONDONTWRITEBYTECODE='1', GIT_OPTIONAL_LOCKS='0')
    git_blobs = dict(specs=blobs(specs, ROOT / 'spec.ls-tree'))
    probes = {}
    for label, commit in [('old', OLD), ('new', NEW)]:
        runtime = work / label
        extract(ROOT / (label+'.tar'), runtime, commit)
        git_blobs[label] = blobs(runtime, ROOT / (label+'.ls-tree'))
        if label == 'new':
            assert files(runtime) == files(author / 'runner')
            for name, wanted in files(package / 'source').items(): assert sha(runtime / name) == wanted, name
        probe_out = OUT / label; probe_out.mkdir()
        proc = subprocess.run([sys.executable, '-I', '-B', str(ROOT / 'probe.py'), str(runtime), str(specs)],
                              env=dict(os.environ, CHECK_OUT=str(probe_out)), capture_output=True, text=True, timeout=60)
        (probe_out / 'probe.txt').write_text(proc.stdout+proc.stderr)
        assert proc.returncode == 0, (label, proc.stdout, proc.stderr)
        probes[label] = json.loads((probe_out / 'controls.json').read_text())
    for name in ('rights_prelude_separate', 'rights_prelude_equal', 'exported_skip_coverage'):
        assert not probes['old'][name]['safety_pass'] and probes['new'][name]['safety_pass'], name
    assert all(probes[label]['opaque_proxy']['safety_pass'] for label in probes)
    tests = {}
    for name in ('test_store_audit', 'test_store_group', 'test_c_process', 'test_c_execution', 'test_assembly',
                 'test_role_readiness', 'test_m11_raw_and_agent_door', 'test_proxy', 'test_diagnostic_secrets'):
        proc = subprocess.run([sys.executable, '-I', '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-p', name+'.py'],
                              cwd=work / 'new', capture_output=True, text=True, timeout=150)
        (OUT / (name+'.txt')).write_text(proc.stdout+proc.stderr)
        assert proc.returncode == 0, (name, proc.stdout[-500:], proc.stderr[-3000:])
        tests[name] = int(re.search(r'Ran (\d+) tests?', proc.stderr)[1])
    assert files(author) == before
    summary = dict(green=True, SUT=0, manifest_sha256=MANIFEST, package_files=len(manifest['files']),
                   author_input_sha256=INPUT, author_input_files=len(before), source_sha_files=len(source),
                   probe_sha256=PROBE, git_blobs=git_blobs, tests=tests, total_tests=sum(tests.values()),
                   controls=probes, inputs_unchanged=True)
    (OUT / 'review-evidence.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k != 'controls'}, ensure_ascii=False), flush=True)
