"""Frozen p08 R2 packet and exact inputs, repeat original public-boundary controls; CT103."""
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
HEAD = '6e03664a61d900a61b4e377e5f8a7c19be420e1d'
OLD = '017195d3919019d62e1e68c0eb1f586e7ce6e4df'
PIN = '9918a61d022f1a061f04cb0e104fe1fb19483620'
MANIFEST = '0cfa5ee1b6bc615f77dd915d3049c8f19293bbb61a72cc3b81da392db6aa19a7'
AUTHOR = 'ac3504b8dac95e1477f7d2a9ebf6d4b41ffbf4dbb8b58a081b5047c8387c0e01'
PROBE = '40388117786d6eeed8fc9009a73711649f3bbdf2a952278b5fc278c72f89a167'
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
        meta, name = entry.split(b'\t', 1); mode, kind, wanted = meta.split(); assert kind == b'blob'
        path = root / name.decode(); raw = os.readlink(path).encode() if mode == b'120000' else path.read_bytes()
        assert hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == wanted.decode(), name
        count += 1
    return count
package = ROOT / 'package'; assert sha(package / 'MANIFEST.json') == MANIFEST
manifest = json.loads((package / 'MANIFEST.json').read_text()); assert manifest['commit'] == HEAD[:7]
for name, wanted in manifest['files'].items(): assert sha(package / name) == wanted, name
assert sha(ROOT / 'author-input.tar.gz') == AUTHOR
assert sha(ROOT / 'probe.py') == PROBE
with tempfile.TemporaryDirectory(prefix='rv-p08-r2-') as directory:
    work = Path(directory)
    for name, commit in [('runtime', HEAD), ('old-runtime', OLD), ('specs', PIN)]:
        extract(ROOT / (name + '.tar'), work / name, commit)
    extract(ROOT / 'author-input.tar.gz', work / 'author')
    runtime, old, specs, author = work / 'runtime', work / 'old-runtime', work / 'specs', work / 'author/in'
    before = files(author)
    verified = {name: blobs(work / name, ROOT / (name + '.ls-tree')) for name in ('runtime', 'old-runtime', 'specs')}
    assert files(runtime) == files(author / 'runner')
    assert files(specs) == files(author / 'specs')
    for name, wanted in files(package / 'files').items(): assert sha(runtime / name) == wanted, name
    def git(*args, input=None):
        return subprocess.check_output(['git', '-C', str(specs), *args], input=input, stderr=subprocess.PIPE).strip()
    git('init', '-q')
    names = b''.join(entry.split(b'\t', 1)[1] + b'\0' for entry in filter(None, (ROOT / 'specs.ls-tree').read_bytes().split(b'\0')))
    git('add', '-f', '--pathspec-from-file=-', '--pathspec-file-nul', input=names)
    assert git('write-tree').decode() == 'fc2095be57d4db3a917630414f08b1fd1b2262f4'
    assert git('hash-object', '-w', '-t', 'commit', '--stdin', input=(ROOT / 'specs.commit').read_bytes()).decode() == PIN
    git('update-ref', 'HEAD', PIN)
    os.environ.update(CAMMETA_SPECS=str(specs), ONEOF_EXPORT=str(specs), PYTHONDONTWRITEBYTECODE='1', GIT_OPTIONAL_LOCKS='0')
    controls = {}
    for label, snapshot in [('old', old), ('new', runtime)]:
        out = OUT / label; out.mkdir()
        for script in ('probe.py', 'relay.py'):
            proc = subprocess.run([sys.executable, '-I', '-B', str(ROOT / script), str(snapshot), str(specs)],
                                  env=dict(os.environ, CHECK_OUT=str(out)), capture_output=True, text=True, timeout=60)
            (out / (script + '.txt')).write_text(proc.stdout + proc.stderr)
            assert proc.returncode == 0, (script, proc.stderr)
        controls[label] = dict(public=json.loads((out / 'controls.json').read_text()),
                               relay=json.loads((out / 'relay-evidence.json').read_text()))
    for label in ('old', 'new'):
        want = label == 'new'
        for name in ('public_domainconsole', 'preflight_classification'):
            assert controls[label]['public'][name]['safety_pass'] is want
        assert controls[label]['relay']['safety_pass'] is want
        assert all(controls[label]['public'][name]['safety_pass'] for name in ('internal_name_and_existing_signal', 'native_domain_end'))
    tests = {}
    for name in ('test_domain_freeze', 'test_c_domain_pin', 'test_openapi_refs', 'test_scenario_control',
                 'test_domain_signals', 'test_c_domain_stand', 'test_domain_agent_copies', 'test_agent_tokens',
                 'test_request_correlation', 'test_proxy'):
        proc = subprocess.run([sys.executable, '-I', '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-p', name + '.py'],
                              cwd=runtime, capture_output=True, text=True, timeout=180)
        (OUT / (name + '.txt')).write_text(proc.stdout + proc.stderr)
        assert proc.returncode == 0, (name, proc.stderr[-3000:])
        tests[name] = int(re.search(r'Ran (\d+) tests?', proc.stderr)[1])
    assert files(author) == before
    evidence = dict(verified=True, SUT=0, head=HEAD, original_head=OLD, pin=PIN, manifest_sha256=MANIFEST,
                    package_files=len(manifest['files']), git_blobs=verified, author_input_sha256=AUTHOR,
                    author_input_files=len(before), tests=tests, total_tests=sum(tests.values()), controls=controls,
                    probe_sha256=PROBE, relay_probe_sha256=sha(ROOT / 'relay.py'), inputs_unchanged=True)
    (OUT / 'review-evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: value for key, value in evidence.items() if key != 'controls'}, ensure_ascii=False), flush=True)
