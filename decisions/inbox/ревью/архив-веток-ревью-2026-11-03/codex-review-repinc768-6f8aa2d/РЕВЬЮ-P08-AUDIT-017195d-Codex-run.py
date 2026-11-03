"""Verify exact p08-audit packet/input and public-boundary controls; CT103 only."""
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
HEAD = '017195d3919019d62e1e68c0eb1f586e7ce6e4df'
PIN = 'a4d0d926c9e5579fe55dca978c5f670e900d51b6'
OLDPIN = '13a30dcbf6a17c7023b518c20bdae96a100058cd'
MANIFEST = '1b5c455e76a2819f884e89cb692967913bf8b836e094b51813a09b7088f1e465'
AUTHOR = '7a868a1e199951783b63c67ad8ff7543024aad8d1dc1d504284628ee7107fb04'
TREE = 'fddff7c5deb3337d0a8106dcae5d3b550d79c6f6'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def files(root):
    return {str(p.relative_to(root)): sha(p) for p in root.rglob('*') if p.is_file() and '.git' not in p.relative_to(root).parts}
def extract(archive, target, commit=None):
    target.mkdir()
    with tarfile.open(archive) as stream:
        if commit: assert stream.pax_headers['comment'] == commit
        stream.extractall(target, filter='data')
def blobs(root, listing):
    count = 0
    for entry in filter(None, listing.read_bytes().split(b'\0')):
        metadata, name = entry.split(b'\t', 1); mode, kind, wanted = metadata.split(); assert kind == b'blob'
        path = root / name.decode(); data = os.readlink(path).encode() if mode == b'120000' else path.read_bytes()
        assert hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == wanted.decode(), name
        count += 1
    return count
package = ROOT / 'package'; assert sha(package / 'MANIFEST.json') == MANIFEST
manifest = json.loads((package / 'MANIFEST.json').read_text()); assert manifest['commit'] == HEAD[:7]
for name, wanted in manifest['files'].items(): assert sha(package / name) == wanted, name
assert sha(ROOT / 'author-input.tar.gz') == AUTHOR
with tempfile.TemporaryDirectory(prefix='rv-p08-audit-') as directory:
    work = Path(directory)
    extract(ROOT / 'author-input.tar.gz', work / 'author')
    extract(ROOT / 'runtime.tar', work / 'runtime', HEAD)
    extract(ROOT / 'specs.tar', work / 'specs', PIN)
    extract(ROOT / 'old-specs.tar', work / 'old-specs', OLDPIN)
    runtime, specs, author = work / 'runtime', work / 'specs', work / 'author/in'
    before = files(author)
    git_blobs = dict(runtime=blobs(runtime, ROOT / 'runtime.ls-tree'), specs=blobs(specs, ROOT / 'specs.ls-tree'))
    assert files(runtime) == files(author / 'runner')
    assert files(specs) == files(author / 'specs')
    for name, wanted in files(package / 'files').items(): assert sha(runtime / name) == wanted, name
    old, new = files(work / 'old-specs'), files(specs)
    changed = sorted(name for name in old.keys() | new.keys() if old.get(name) != new.get(name))
    assert changed == sorted((ROOT / 'export-files.txt').read_text().splitlines()) and len(changed) == 28
    def git(*args, input=None):
        return subprocess.check_output(['git', '-C', str(specs), *args], input=input, stderr=subprocess.PIPE).strip()
    git('init', '-q')
    names = b''.join(entry.split(b'\t', 1)[1] + b'\0' for entry in filter(None, (ROOT / 'specs.ls-tree').read_bytes().split(b'\0')))
    git('add', '-f', '--pathspec-from-file=-', '--pathspec-file-nul', input=names)
    assert git('write-tree').decode() == TREE
    assert git('hash-object', '-w', '-t', 'commit', '--stdin', input=(ROOT / 'specs.commit').read_bytes()).decode() == PIN
    git('update-ref', 'HEAD', PIN)
    os.environ.update(CAMMETA_SPECS=str(specs), ONEOF_EXPORT=str(specs), PYTHONDONTWRITEBYTECODE='1', GIT_OPTIONAL_LOCKS='0')
    proc = subprocess.run([sys.executable, '-I', '-B', str(ROOT / 'probe.py'), str(runtime), str(specs)],
                          capture_output=True, text=True, timeout=45)
    (OUT / 'probe.txt').write_text(proc.stdout + proc.stderr)
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    controls = json.loads((OUT / 'controls.json').read_text())
    print(json.dumps({name: case['safety_pass'] for name, case in controls.items()}), flush=True)
    tests = {}
    for name in (() if '--probe-only' in sys.argv else ('test_domain_freeze', 'test_c_domain_pin', 'test_openapi_refs', 'test_scenario_control',
                 'test_domain_signals', 'test_c_domain_stand', 'test_domain_agent_copies', 'test_agent_tokens',
                 'test_request_correlation', 'test_proxy')):
        proc = subprocess.run([sys.executable, '-I', '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-p', name + '.py'],
                              cwd=runtime, capture_output=True, text=True, timeout=180)
        (OUT / (name + '.txt')).write_text(proc.stdout + proc.stderr)
        assert proc.returncode == 0, (name, proc.stdout[-500:], proc.stderr[-4000:])
        tests[name] = int(re.search(r'Ran (\d+) tests?', proc.stderr)[1])
    assert files(author) == before
    evidence = dict(verified=True, SUT=0, head=HEAD, pin=PIN, manifest_sha256=MANIFEST,
                    package_files=len(manifest['files']), git_blobs=git_blobs, author_input_sha256=AUTHOR,
                    author_input_files=len(before), changed_export_files=changed, tests=tests,
                    total_tests=sum(tests.values()), controls=controls, probe_sha256=sha(ROOT / 'probe.py'), inputs_unchanged=True)
    (OUT / 'review-evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: value for key, value in evidence.items() if key not in ('controls', 'changed_export_files')},
                     ensure_ascii=False), flush=True)
