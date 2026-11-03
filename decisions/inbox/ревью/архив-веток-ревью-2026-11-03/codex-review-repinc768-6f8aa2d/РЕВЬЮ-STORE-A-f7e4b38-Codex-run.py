"""Review A: verify its exact sources and exercise capability, argv, and transport boundaries."""
import hashlib
import importlib.util
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
HEAD = 'f7e4b38d5e98eae6a1b44e875484b09397f8a905'
MANIFEST = '6432196225660c13f69d565ca43c394059102248c2a2ccca884cb76b1fda18b3'
INPUT = '4b114a2b5e681c0c866d2311f0088aad482ab0d5d01355e31ee326c1b320284f'
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
assert manifest['commit'] == HEAD
for name, wanted in manifest['files'].items(): assert sha(package / name) == wanted, name
assert sha(ROOT / 'author-input.tar.gz') == INPUT
with tempfile.TemporaryDirectory(prefix='rv-store-a-') as directory:
    work = Path(directory)
    extract(ROOT / 'after.tar', work / 'runtime', HEAD)
    extract(ROOT / 'author-input.tar.gz', work / 'author')
    author = work / 'author/in'; runtime = work / 'runtime'; specs = author / 'specs'
    before = files(author)
    source = json.loads((author / 'SOURCE-SHA.json').read_text())
    for name, wanted in source.items(): assert sha(author / name) == wanted, name
    git_blobs = dict(runtime=blobs(runtime, ROOT / 'after.ls-tree'), specs=blobs(specs, ROOT / 'spec.ls-tree'))
    assert files(runtime) == files(author / 'runner')
    for name, wanted in files(package / 'source').items(): assert sha(runtime / name) == wanted, name
    for name, wanted in files(package / 'norms/d942717').items(): assert sha(specs / name) == wanted, name
    os.environ.update(CAMMETA_SPECS=str(specs), ONEOF_EXPORT=str(specs), PYTHONDONTWRITEBYTECODE='1', GIT_OPTIONAL_LOCKS='0')
    tests = {}
    for name in ('test_store_audit', 'test_store_group', 'test_c_process', 'test_c_execution', 'test_assembly',
                 'test_role_readiness', 'test_m11_raw_and_agent_door', 'test_proxy'):
        proc = subprocess.run([sys.executable, '-I', '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-p', name+'.py'],
                              cwd=runtime, capture_output=True, text=True, timeout=150)
        (OUT / (name+'.txt')).write_text(proc.stdout+proc.stderr)
        assert proc.returncode == 0, (name, proc.stdout[-500:], proc.stderr[-3000:])
        tests[name] = int(re.search(r'Ran (\d+) tests?', proc.stderr)[1])
    proc = subprocess.run([sys.executable, '-I', '-B', str(ROOT / 'probe.py'), str(runtime), str(specs)],
                          capture_output=True, text=True, timeout=60)
    (OUT / 'probe.txt').write_text(proc.stdout+proc.stderr)
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    controls = json.loads((OUT / 'controls.json').read_text())
    assert files(author) == before
    summary = dict(green=all(v['safety_pass'] for v in controls.values()), SUT=0, manifest_sha256=MANIFEST,
                   package_files=len(manifest['files']), author_input_sha256=INPUT, author_input_files=len(before),
                   source_sha_files=len(source), git_blobs=git_blobs, tests=tests, total_tests=sum(tests.values()),
                   controls=controls, inputs_unchanged=True)
    (OUT / 'review-evidence.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    raise SystemExit(not summary['green'])
