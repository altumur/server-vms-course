"""Exact R2 packet, unchanged old/new Codex probe, related modules and early-reply boundary; CT103."""
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
HEAD = '163c2df6e5708c6640ef48e18843e666884a6431'
BASE = '50ce0b0bacc14eec60f384fef1aa38eb089b34d5'
PIN = '13a30dcbf6a17c7023b518c20bdae96a100058cd'
MANIFEST = '12d5b5bfa5aeff21379e53aa954cc588c9680c7ff2c54e27d351f5750a79b1ec'
AUTHOR = 'ba997b6554f164dcaeba3b937cecc41a6177b8a425fccaf71eee5c859ed52f94'
PROBE = '6e4e111ae7164f8bbd91a158d24c7cb06221e6c939635401375f28cab61cfcbf'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def files(root):
    return {str(p.relative_to(root)): sha(p) for p in root.rglob('*') if p.is_file() and '.git' not in p.relative_to(root).parts}
def extract(path, target, commit=None):
    target.mkdir()
    with tarfile.open(path) as stream:
        if commit: assert stream.pax_headers['comment'] == commit
        stream.extractall(target, filter='data')
def blobs(root, listing):
    count = 0
    for entry in filter(None, listing.read_bytes().split(b'\0')):
        meta, name = entry.split(b'\t', 1); mode, kind, wanted = meta.split(); assert kind == b'blob'
        path = root / name.decode(); raw = os.readlink(path).encode() if mode == b'120000' else path.read_bytes()
        assert hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == wanted.decode(), name
        count += 1
    return count
packet = ROOT / 'package'; assert sha(packet / 'MANIFEST.json') == MANIFEST
manifest = json.loads((packet / 'MANIFEST.json').read_text()); assert manifest['commit'] == HEAD
for name, wanted in manifest['files'].items(): assert sha(packet / name) == wanted, name
assert sha(ROOT / 'author-input.tar.gz') == AUTHOR
assert sha(ROOT / 'probe.py') == PROBE
with tempfile.TemporaryDirectory(prefix='rv-D-r2-') as directory:
    work = Path(directory)
    extract(ROOT / 'author-input.tar.gz', work / 'author')
    extract(ROOT / 'runtime.tar', work / 'runtime', HEAD)
    extract(ROOT / 'old-runtime.tar', work / 'old-runtime', BASE)
    extract(ROOT / 'specs.tar', work / 'specs', PIN)
    runtime, old, specs, author = work / 'runtime', work / 'old-runtime', work / 'specs', work / 'author/in'
    before = files(author)
    source = json.loads((author / 'SOURCE-SHA.json').read_text())
    for name, wanted in source.items(): assert sha(author / name) == wanted, name
    git_blobs = dict(runtime=blobs(runtime, ROOT / 'runtime.ls-tree'), old_runtime=blobs(old, ROOT / 'old-runtime.ls-tree'),
                     specs=blobs(specs, ROOT / 'specs.ls-tree'))
    assert files(runtime) == files(author / 'runner') and files(old) == files(author / 'old')
    assert files(specs) == files(author / 'specs')
    for name, wanted in files(packet / 'source').items(): assert sha(runtime / name) == wanted, name
    old_files, new_files = files(old), files(runtime)
    changed = sorted(name for name in old_files.keys() | new_files.keys() if old_files.get(name) != new_files.get(name))
    assert changed == ['runner/m11stand.py', 'tests/test_scenario_control.py']
    def git(*args, input=None):
        return subprocess.check_output(['git', '-C', str(specs), *args], input=input, stderr=subprocess.PIPE).strip()
    git('init', '-q')
    names = b''.join(entry.split(b'\t', 1)[1] + b'\0' for entry in filter(None, (ROOT / 'specs.ls-tree').read_bytes().split(b'\0')))
    git('add', '-f', '--pathspec-from-file=-', '--pathspec-file-nul', input=names)
    assert git('write-tree').decode() == '5c4a5df9d8f8ec0b52c27fe96369c4007c03f4fa'
    assert git('hash-object', '-w', '-t', 'commit', '--stdin', input=(ROOT / 'specs.commit').read_bytes()).decode() == PIN
    git('update-ref', 'HEAD', PIN)
    os.environ.update(CAMMETA_SPECS=str(specs), ONEOF_EXPORT=str(specs), PYTHONDONTWRITEBYTECODE='1', GIT_OPTIONAL_LOCKS='0')
    controls = {}
    for label, folder in (('old', old), ('new', runtime)):
        out = OUT / label; out.mkdir()
        for script in ('probe.py', 'early.py'):
            proc = subprocess.run([sys.executable, '-I', '-B', str(ROOT / script), str(folder)],
                                  env=dict(os.environ, CHECK_OUT=str(out)), capture_output=True, text=True, timeout=90)
            (out / (script + '.txt')).write_text(proc.stdout + proc.stderr)
            assert proc.returncode == 0, (label, script, proc.stderr[-3000:])
        controls[label] = dict(original=json.loads((out / 'controls.json').read_text()),
                               early=json.loads((out / 'early-refusal.json').read_text()))
    for name in ('http_close_small', 'http_close_large', 'client_half_close'):
        assert not controls['old']['original'][name]['safety_pass'] and controls['new']['original'][name]['safety_pass']
    assert all(controls[label]['original'][name]['safety_pass'] for label in ('old', 'new')
               for name in ('stale_watchdog', 'forgotten_pause'))
    tests = {}
    for name in ('test_scenario_control', 'test_store_group', 'test_proxy', 'test_transport_diagnostics',
                 'test_process_audit_c', 'test_stand_setup', 'test_c_worker', 'test_c_controller', 'test_c_shared_engines',
                 'test_console_resource_start', 'test_cli_environment', 'test_c_process', 'test_c_execution',
                 'test_diagnostic_secrets', 'test_platform', 'test_request_correlation', 'test_vms_stand'):
        proc = subprocess.run([sys.executable, '-I', '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-p', name + '.py'],
                              cwd=runtime, capture_output=True, text=True, timeout=180)
        (OUT / (name + '.txt')).write_text(proc.stdout + proc.stderr)
        assert proc.returncode == 0, (name, proc.stderr[-4000:])
        tests[name] = int(re.search(r'Ran (\d+) tests?', proc.stderr)[1])
    assert files(author) == before
    result = dict(verified=True, SUT=0, head=HEAD, base=BASE, pin=PIN, manifest_sha256=MANIFEST,
                  package_files=len(manifest['files']), git_blobs=git_blobs, source_sha_files=len(source),
                  author_input_sha256=AUTHOR, author_input_files=len(before), changed_files=changed, controls=controls,
                  tests=tests, total_tests=sum(tests.values()), probe_sha256=PROBE, early_probe_sha256=sha(ROOT / 'early.py'),
                  inputs_unchanged=True)
    (OUT / 'review-evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'controls'}, ensure_ascii=False), flush=True)
    print(json.dumps({label: row['early']['safety_pass'] for label, row in controls.items()}), flush=True)
