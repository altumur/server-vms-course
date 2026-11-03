"""Verify immutable acceptance package, exact Git inputs and old/new driver controls."""
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
OLD = 'dd67722c4c986ab5e76c06ef778d45a3bd033220'
NEW = '55a6c9e5fef422a4394d519ffbab7f043a55d02a'
PIN = 'd389cf5e47db0902f8d660f7bb6f917eb1588925'
MANIFEST = '3898f1224672b8bc7a80384a06aada8b13929137a4f650fb3984bd763597d9f5'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def extract(archive, target, commit):
    target.mkdir()
    with tarfile.open(archive) as stream:
        assert stream.pax_headers['comment'] == commit
        stream.extractall(target, filter='data')

def blobs(root, listing):
    count = 0
    for entry in filter(None, listing.read_bytes().split(b'\0')):
        meta, name = entry.split(b'\t', 1)
        mode, kind, wanted = meta.split()
        path = root / name.decode()
        raw = os.readlink(path).encode() if mode == b'120000' else path.read_bytes()
        assert kind == b'blob' and hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == wanted.decode()
        count += 1
    return count

package = ROOT / 'package'
assert sha(package / 'MANIFEST.json') == MANIFEST
manifest = json.loads((package / 'MANIFEST.json').read_text())
for name, digest in manifest['files'].items():
    assert sha(package / name) == digest, name

with tempfile.TemporaryDirectory(prefix='rv-accept-files-') as directory:
    work = Path(directory)
    git_blobs, controls = {}, {}
    for label, commit in [('specs', PIN), ('old', OLD), ('new', NEW)]:
        extract(ROOT / (label + '.tar'), work / label, commit)
        git_blobs[label] = blobs(work / label, ROOT / (label + '.ls-tree'))
    specs = work / 'specs'
    subprocess.run(['git', 'init', '--quiet', str(specs)], check=True, capture_output=True)
    names = [entry.split(b'\t', 1)[1].decode() for entry in filter(None, (ROOT/'specs.ls-tree').read_bytes().split(b'\0'))]
    subprocess.run(['git', '-C', str(specs), '-c', 'core.autocrlf=false', 'add', '-f', '--', *names], check=True, capture_output=True)
    tree = subprocess.check_output(['git', '-C', str(specs), 'write-tree'], text=True).strip()
    assert tree == '028db780ac7ebaec1ac521d52b9c31eabcf34ae2'
    stored = subprocess.run(['git', '-C', str(specs), 'hash-object', '-w', '-t', 'commit', '--stdin'],
                            input=(ROOT/'specs.commit').read_bytes(), capture_output=True, check=True).stdout.decode().strip()
    assert stored == PIN
    subprocess.run(['git', '-C', str(specs), 'update-ref', 'HEAD', PIN], check=True, capture_output=True)
    for name, digest in manifest['files'].items():
        if name.startswith('files/'):
            assert sha(work / 'new' / name[6:]) == digest, name
    env = dict(os.environ, CAMMETA_SPECS=str(specs), ONEOF_EXPORT=str(specs), PYTHONDONTWRITEBYTECODE='1')
    for label in ('old', 'new'):
        out = OUT / label
        out.mkdir()
        proc = subprocess.run([sys.executable, '-I', '-B', str(ROOT/'probe.py'), str(work/label), str(specs)],
                              env=dict(env, CHECK_OUT=str(out)), capture_output=True, text=True, timeout=90)
        (out/'probe.txt').write_text(proc.stdout+proc.stderr)
        assert proc.returncode == 0, (label, proc.stdout, proc.stderr)
        controls[label] = json.loads((out/'controls.json').read_text())
    assert controls['old']['snapshot'] == controls['new']['snapshot']
    assert not any(controls['old']['controls'].values())
    tests = {}
    for name in ('test_c_domain_stand', 'test_c_pinned_vector_tables', 'test_c_role_packages',
                 'test_c_vector_protocol', 'test_c_value_vectors'):
        # All are in the current V7 module set, not historical B witnesses.
        assert (work/'new/tests'/ (name+'.py')).exists(), name
        proc = subprocess.run([sys.executable, '-I', '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-p', name+'.py'],
                              cwd=work/'new', env=env, capture_output=True, text=True, timeout=120)
        (OUT/(name+'.txt')).write_text(proc.stdout+proc.stderr)
        assert proc.returncode == 0, (name, proc.stdout, proc.stderr)
        tests[name] = int(re.search(r'Ran (\d+) tests?', proc.stderr)[1])
    assert blobs(specs, ROOT/'specs.ls-tree') == git_blobs['specs']
    result = dict(green=controls['new']['green'], SUT=0, old=OLD, new=NEW, pin=PIN,
                  manifest_sha256=MANIFEST, package_files=len(manifest['files']), git_blobs=git_blobs,
                  probe_sha256=sha(ROOT/'probe.py'), tests=tests, controls=controls, inputs_unchanged=True)
    (OUT/'review-evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(green=result['green'], SUT=0, package_files=result['package_files'], git_blobs=git_blobs,
                         tests=tests, pairs=len(controls['new']['snapshot']), rows=controls['new']['accept'],
                         old_controls=controls['old']['controls'], new_controls=controls['new']['controls'])), flush=True)
    raise SystemExit(not result['green'])
