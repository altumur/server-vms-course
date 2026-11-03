"""Verify the immutable package/Git input, then test only the affected runner boundaries."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parent
OUT = Path(os.environ['CHECK_OUT'])
COMMIT = 'fdda6a3ffe307a1701e1eb8964690b2b14777732'
MANIFEST = 'fe205606096081cc9ec7d79f4a42b36ebf188fe266b71495bbe00d14d22bff6e'
INPUT = '588b6de8e989b7af25207f52df041cdd0b5834d9f5ab058ea2933c4101bc2521'

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
for name, wanted in manifest['files'].items(): assert sha(package / name) == wanted, name
assert sha(ROOT / 'author-input.tar.gz') == INPUT
with tempfile.TemporaryDirectory(prefix='rv-group-') as directory:
    work = Path(directory)
    extract(ROOT / 'after.tar', work / 'runtime', COMMIT)
    extract(ROOT / 'author-input.tar.gz', work / 'author')
    author = work / 'author/in'; runtime = work / 'runtime'; specs = author / 'specs'
    before = files(author)
    source = json.loads((author / 'SOURCE-SHA.json').read_text())
    for name, wanted in source.items(): assert sha(author / name) == wanted, name
    count = blobs(runtime, ROOT / 'after.ls-tree')
    assert files(runtime) == files(author / 'runner')
    spec_count = blobs(specs, ROOT / 'spec.ls-tree')
    os.environ.update(CAMMETA_SPECS=str(specs), ONEOF_EXPORT=str(specs), PYTHONDONTWRITEBYTECODE='1', GIT_OPTIONAL_LOCKS='0')
    tests = {}
    for name in ('test_store_group', 'test_assembly', 'test_c_execution', 'test_c_process'):
        proc = subprocess.run([sys.executable, '-I', '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-p', name+'.py'],
                              cwd=runtime, capture_output=True, text=True, timeout=150)
        (OUT / (name+'.txt')).write_text(proc.stdout+proc.stderr)
        assert proc.returncode == 0, (name, proc.stdout[-500:], proc.stderr[-3000:])
        tests[name] = proc.stderr.strip().splitlines()[-4:]
    module_spec = importlib.util.spec_from_file_location('controls', ROOT / 'probe.py')
    probe = importlib.util.module_from_spec(module_spec); module_spec.loader.exec_module(probe)
    controls = probe.controls(runtime, specs, OUT)
    assert files(author) == before
    summary = dict(green=all(v['safety_pass'] for v in controls.values()), SUT=0, manifest_sha256=MANIFEST,
                   package_files=len(manifest['files']), author_input_sha256=INPUT, source_sha_files=len(source),
                   author_input_files=len(before), runtime_git_blobs=count, spec_git_blobs=spec_count,
                   tests=tests, controls=controls, inputs_unchanged=True)
    (OUT / 'review-evidence.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    raise SystemExit(not summary['green'])
