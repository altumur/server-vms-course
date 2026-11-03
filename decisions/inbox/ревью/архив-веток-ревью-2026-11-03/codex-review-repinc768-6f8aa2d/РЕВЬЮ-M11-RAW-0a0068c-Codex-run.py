"""r2: invoke the unchanged 87854745c wire controls against two actual Git archives."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
OUT = Path(os.environ['CHECK_OUT'])
source = (ROOT / 'original-probe.py').read_bytes()
assert hashlib.sha1(b'blob ' + str(len(source)).encode() + b'\0' + source).hexdigest() == '3ee8e0268e04c247fa8fde842f7b03e66b5e2992'
spec = importlib.util.spec_from_file_location('original', ROOT / 'original-probe.py')
original = importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)
MANIFEST = '50762f756ba1bbc2b4a38375cc843c8fbd6231ba1e63f332f22997af85bc4c48'
INPUT = 'aef91dc62dacb6e71954f9c92b0839a8db5c1703c6e276005c20d3c103adc242'
package = ROOT / 'package'
assert original.sha(package / 'MANIFEST.json') == MANIFEST
manifest = json.loads((package / 'MANIFEST.json').read_text())
for path, wanted in manifest['files'].items():
    assert original.sha(package / path) == wanted, path
assert original.sha(ROOT / 'author-input.tar.gz') == INPUT
with tempfile.TemporaryDirectory(prefix='review-m11r2-') as directory:
    work = Path(directory)
    original.extract(ROOT / 'author-input.tar.gz', work / 'author')
    author = work / 'author/in'
    before_input = original.files(author)
    blobs = {}
    for label, commit in (('before', '4faf72867250887f13a7c81de4db272bb52b107e'),
                          ('after', '0a0068c1353bf7fa3e9bb2289606536b0ab287df')):
        original.extract(ROOT / (label + '.tar'), work / label, commit)
        blobs[label] = original.blobs(work / label, ROOT / (label + '.ls-tree'))
    assert original.files(work / 'after') == original.files(author / 'runner')
    old, new = original.files(work / 'before'), original.files(work / 'after')
    assert {p for p in old.keys() | new.keys() if old.get(p) != new.get(p)} == {
        'runner/m11stand.py', 'tests/test_m11_raw_and_agent_door.py'}
    os.environ.update(CAMMETA_SPECS=str(author / 'specs'), PYTHONDONTWRITEBYTECODE='1')
    controls = {}
    for label in ('before', 'after'):
        proc = subprocess.run([sys.executable, '-I', '-B', str(ROOT / 'original-probe.py'),
                               '--controls', str(work / label)], capture_output=True, text=True, timeout=40)
        assert proc.returncode == 0, (label, proc.stdout, proc.stderr)
        controls[label] = json.loads(proc.stdout)
    assert {k for k, v in controls['before'].items() if not v['safety_pass']} == {
        'json_literal_marker', 'store_raw'}
    assert all(v['safety_pass'] for v in controls['after'].values()), controls['after']
    tests = {}
    for name in ('test_m11_raw_and_agent_door', 'test_c_domain_stand', 'test_runner'):
        proc = subprocess.run([sys.executable, '-I', '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-p', name + '.py'],
                               cwd=work / 'after', capture_output=True, text=True, timeout=90)
        (OUT / (name + '.txt')).write_text(proc.stdout + proc.stderr)
        assert proc.returncode == 0, (name, proc.stdout, proc.stderr)
        tests[name] = proc.stderr.strip()
    assert original.files(author) == before_input
    result = {'green': True, 'SUT': 0, 'manifest_sha256': MANIFEST, 'package_files': len(manifest['files']),
              'author_input_sha256': INPUT, 'author_input_files': len(before_input), 'git_blobs': blobs,
              'original_probe_blob': '3ee8e0268e04c247fa8fde842f7b03e66b5e2992',
              'controls': controls, 'tests': tests, 'inputs_unchanged': True}
    (OUT / 'review-evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False), flush=True)
