"""Review closure: unchanged b027f8f69 probe on two verified Git snapshots, CT 103 only."""
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
BEFORE = 'fdda6a3ffe307a1701e1eb8964690b2b14777732'
AFTER = '1a31a041944fb38305aab9550bbad88149b2ffe0'
MAIN = '0a0068c1353bf7fa3e9bb2289606536b0ab287df'
MANIFEST = '3fe30fd4a73a55cdd8c0bcf101083dd6955bb5f190deb3b8ff5c7931a1104ed4'
INPUT = '5d6e13a45de1df687018ddc48ecbed4efc5dcf6a6c15b5ba86957b51f1aab434'
PROBE = 'db7dd18cd2936f83c48482b2ee6a567b68f5fb3c8e6b275eef242efcb54789ba'

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

package = ROOT / 'package'
assert sha(package / 'MANIFEST.json') == MANIFEST
manifest = json.loads((package / 'MANIFEST.json').read_text())
assert manifest['commit'] == AFTER and manifest['previous'] == BEFORE and manifest['base'] == MAIN
for name, wanted in manifest['files'].items(): assert sha(package / name) == wanted, name
assert sha(ROOT / 'author-input.tar.gz') == INPUT
assert sha(ROOT / 'probe.py') == PROBE
assert sha(package / 'reproduce/Codex-probe.py') == PROBE
assert sha(package / 'prior-MANIFEST.json') == 'fe205606096081cc9ec7d79f4a42b36ebf188fe266b71495bbe00d14d22bff6e'
with tempfile.TemporaryDirectory(prefix='rv-group-r3-') as directory:
    work = Path(directory)
    extract(ROOT / 'author-input.tar.gz', work / 'author')
    author = work / 'author/in'; specs = author / 'specs'
    before_inputs = files(author)
    source = json.loads((author / 'SOURCE-SHA.json').read_text())
    for name, wanted in source.items(): assert sha(author / name) == wanted, name
    git_blobs = {}
    for label, commit in (('before', BEFORE), ('after', AFTER), ('main', MAIN)):
        extract(ROOT / (label + '.tar'), work / label, commit)
        git_blobs[label] = blobs(work / label, ROOT / (label + '.ls-tree'))
    git_blobs['specs'] = blobs(specs, ROOT / 'spec.ls-tree')
    runtime = work / 'after'
    assert files(runtime) == files(author / 'runner')
    old, new = files(work / 'before'), files(runtime)
    changed = {p for p in old.keys() | new.keys() if old.get(p) != new.get(p)}
    assert changed == {'runner/harness.py', 'runner/m11stand.py', 'tests/test_m11_raw_and_agent_door.py',
                       'runner/store_group.py', 'tests/test_store_group.py'}, changed
    for name, wanted in files(work / 'main').items(): assert new[name] == wanted, name
    for name, wanted in files(package / 'source').items(): assert new[name] == wanted, name
    for source_name, export_name in {
        'README-common.md': 'Platform/common/acceptance/README.md',
        'README-1.3.md': 'Platform/01-store/acceptance/3/README.md',
        'rights.json': 'Platform/01-store/acceptance/2/inputs/rights.json',
        '01-store.api.openapi.yaml': 'Platform/01-store/spec/01-store.api.openapi.yaml',
    }.items(): assert sha(package / 'norms' / source_name) == sha(specs / export_name)
    os.environ.update(CAMMETA_SPECS=str(specs), ONEOF_EXPORT=str(specs), PYTHONDONTWRITEBYTECODE='1', GIT_OPTIONAL_LOCKS='0')
    controls = {}
    for label in ('before', 'after'):
        dest = OUT / label; dest.mkdir()
        proc = subprocess.run([sys.executable, '-I', '-B', str(ROOT / 'probe.py'), str(work / label), str(specs)],
                              env=dict(os.environ, CHECK_OUT=str(dest)), capture_output=True, text=True, timeout=90)
        (dest / 'probe.txt').write_text(proc.stdout+proc.stderr)
        assert proc.returncode == 0, (label, proc.stdout, proc.stderr)
        controls[label] = json.loads((dest / 'controls.json').read_text())
    expected = {'chapter_role', 'door_budget', 'admin_refused', 'admin_forbidden', 'term_shell_child'}
    assert set(controls['before']) == set(controls['after']) == expected
    assert all(not v['safety_pass'] for v in controls['before'].values()), controls['before']
    assert all(v['safety_pass'] for v in controls['after'].values()), controls['after']
    tests = {}
    for name in ('test_store_group', 'test_assembly', 'test_c_execution', 'test_c_process', 'test_m11_raw_and_agent_door'):
        proc = subprocess.run([sys.executable, '-I', '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-p', name+'.py'],
                              cwd=runtime, capture_output=True, text=True, timeout=150)
        (OUT / (name+'.txt')).write_text(proc.stdout+proc.stderr)
        assert proc.returncode == 0, (name, proc.stdout[-500:], proc.stderr[-3000:])
        tests[name] = int(re.search(r'Ran (\d+) tests?', proc.stderr)[1])
    assert files(author) == before_inputs
    summary = dict(green=True, SUT=0, manifest_sha256=MANIFEST, package_files=len(manifest['files']),
                   author_input_sha256=INPUT, source_sha_files=len(source), author_input_files=len(before_inputs),
                   git_blobs=git_blobs, probe_sha256=PROBE, changed_runtime_files=sorted(changed),
                   main_files_unchanged=3, controls=controls, tests=tests, total_tests=sum(tests.values()),
                   inputs_unchanged=True)
    (OUT / 'review-evidence.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(summary, ensure_ascii=False), flush=True)
