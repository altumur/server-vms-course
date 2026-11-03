"""Frozen packet audit, native stream controls and relevant common tests; CT103 only."""
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
HEAD = '50ce0b0bacc14eec60f384fef1aa38eb089b34d5'
PIN = '13a30dcbf6a17c7023b518c20bdae96a100058cd'
OLDPIN = '27df7470f2ae66e242078d61d4d58dc5f6983dc5'
MANIFEST = '6229ccd0320a5e7c9fce2cacbfa72fe05ff02b23cf7db2106893697c8d60ad7f'
AUTHOR = 'c2a508afd4cce5afe1ba4ec0d07b591bba619f8c241bf0d90f4ace07ff6eb302'
TREE = '5c4a5df9d8f8ec0b52c27fe96369c4007c03f4fa'


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
        mode, kind, wanted = metadata.split(); assert kind == b'blob'
        path = root / name.decode()
        data = os.readlink(path).encode() if mode == b'120000' else path.read_bytes()
        assert hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == wanted.decode(), name
        count += 1
    return count

package = ROOT / 'package'
assert sha(package / 'MANIFEST.json') == MANIFEST
manifest = json.loads((package / 'MANIFEST.json').read_text())
assert manifest['commit'] == HEAD
for name, wanted in manifest['files'].items(): assert sha(package / name) == wanted, name
assert sha(ROOT / 'author-input.tar.gz') == AUTHOR
with tempfile.TemporaryDirectory(prefix='rv-repin13-D-') as directory:
    work = Path(directory)
    extract(ROOT / 'author-input.tar.gz', work / 'author')
    extract(ROOT / 'runtime.tar', work / 'runtime', HEAD)
    extract(ROOT / 'specs.tar', work / 'specs', PIN)
    extract(ROOT / 'old-specs.tar', work / 'old-specs', OLDPIN)
    author, runtime, specs = work / 'author/in', work / 'runtime', work / 'specs'
    before = files(author)
    source = json.loads((author / 'SOURCE-SHA.json').read_text())
    for name, wanted in source.items(): assert sha(author / name) == wanted, name
    git_blobs = dict(runtime=blobs(runtime, ROOT / 'runtime.ls-tree'), specs=blobs(specs, ROOT / 'specs.ls-tree'),
                     old_specs=blobs(work / 'old-specs', ROOT / 'old-specs.ls-tree'))
    assert files(runtime) == files(author / 'runner')
    assert files(specs) == files(author / 'specs')
    for name, wanted in files(package / 'source').items(): assert sha(runtime / name) == wanted, name
    for name, wanted in files(package / 'normative-delta').items(): assert sha(specs / name) == wanted, name
    old, new = files(work / 'old-specs'), files(specs)
    changed = sorted(name for name in old.keys() | new.keys() if old.get(name) != new.get(name))
    delta = json.loads((package / 'EXPORT-DELTA.json').read_text())
    assert delta['base'] == OLDPIN and delta['pin'] == PIN
    assert changed == sorted(row['path'] for row in delta['files']) and len(changed) == 33
    for row in delta['files']:
        assert old.get(row['path']) == row['before_sha256'] and new.get(row['path']) == row['after_sha256']
    # Restore the exact export commit for inventory tests; no remote refs/parents needed.
    def git(*args, input=None):
        return subprocess.check_output(['git', '-C', str(specs), *args], input=input, stderr=subprocess.PIPE).strip()
    git('init', '-q')
    names = b''.join(entry.split(b'\t', 1)[1] + b'\0' for entry in
                     filter(None, (ROOT / 'specs.ls-tree').read_bytes().split(b'\0')))
    git('add', '-f', '--pathspec-from-file=-', '--pathspec-file-nul', input=names)
    assert git('write-tree').decode() == TREE
    assert git('hash-object', '-w', '-t', 'commit', '--stdin', input=(ROOT / 'specs.commit').read_bytes()).decode() == PIN
    git('update-ref', 'HEAD', PIN)
    os.environ.update(CAMMETA_SPECS=str(specs), ONEOF_EXPORT=str(specs), PYTHONDONTWRITEBYTECODE='1', GIT_OPTIONAL_LOCKS='0')
    proc = subprocess.run([sys.executable, '-I', '-B', str(ROOT / 'probe.py'), str(runtime)],
                          capture_output=True, text=True, timeout=45)
    (OUT / 'probe.txt').write_text(proc.stdout + proc.stderr)
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    controls = json.loads((OUT / 'controls.json').read_text())
    print(json.dumps({name: case['safety_pass'] for name, case in controls.items()}), flush=True)
    tests = {}
    for name in ('test_scenario_control', 'test_store_group', 'test_proxy', 'test_transport_diagnostics',
                 'test_process_audit_c', 'test_stand_setup', 'test_c_worker', 'test_c_controller', 'test_c_shared_engines',
                 'test_console_resource_start', 'test_cli_environment', 'test_c_process', 'test_c_execution',
                 'test_diagnostic_secrets', 'test_platform', 'test_request_correlation', 'test_vms_stand'):
        proc = subprocess.run([sys.executable, '-I', '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-p', name + '.py'],
                              cwd=runtime, capture_output=True, text=True, timeout=180)
        (OUT / (name + '.txt')).write_text(proc.stdout + proc.stderr)
        assert proc.returncode == 0, (name, proc.stdout[-1000:], proc.stderr[-4000:])
        tests[name] = int(re.search(r'Ran (\d+) tests?', proc.stderr)[1])
    assert files(author) == before
    evidence = dict(verified=True, SUT=0, head=HEAD, pin=PIN, manifest_sha256=MANIFEST,
                    package_files=len(manifest['files']), git_blobs=git_blobs, author_input_sha256=AUTHOR,
                    source_sha_files=len(source), author_input_files=len(before), changed_export_files=changed,
                    tests=tests, total_tests=sum(tests.values()), controls=controls,
                    probe_sha256=sha(ROOT / 'probe.py'), inputs_unchanged=True)
    (OUT / 'review-evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: value for key, value in evidence.items() if key not in ('controls', 'changed_export_files')},
                     ensure_ascii=False), flush=True)
