"""Frozen package/Git verification and independent old/new controls; CT103 only."""
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
OLD = '5fd65fa25350db1664c7706a4e363675905b949e'
NEW = '2312f8be90924e520b50015c7b5ba9454e8d89cb'
PIN = 'd389cf5e47db0902f8d660f7bb6f917eb1588925'
BD = 'bd3282636f2d5b423b5f07ec4739d82a2bff194e'
MANIFEST = 'dad7f9bfaa69db37a60ad6c20c30129f2415c11821de3785997cf325d10ba9ea'
PROBE = '71de8b25144daf07d019b80b346f7cdca7accd7d17477c35bfac412d37450552'

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
        metadata, name = entry.split(b'\t', 1)
        mode, kind, wanted = metadata.split()
        assert kind == b'blob'
        path = root / name.decode()
        raw = os.readlink(path).encode() if mode == b'120000' else path.read_bytes()
        assert hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == wanted.decode(), name
        count += 1
    return count

package = ROOT / 'package'
assert sha(ROOT / 'probe.py') == PROBE
assert sha(package / 'MANIFEST.json') == MANIFEST
manifest = json.loads((package / 'MANIFEST.json').read_text())
for name, expected in manifest['files'].items():
    assert sha(package / name) == expected, name

with tempfile.TemporaryDirectory(prefix='rv-shell-name-') as directory:
    work = Path(directory)
    git_blobs, controls = {}, {}
    for label, commit in [('specs', PIN), ('bd', BD), ('old', OLD), ('new', NEW)]:
        extract(ROOT / (label + '.tar'), work / label, commit)
        git_blobs[label] = blobs(work / label, ROOT / (label + '.ls-tree'))
    # Inventory reads Git HEAD for optional tables. Rebuild the exact archived
    # pin tree and its original commit object, without fetching or a new history.
    spec_root = work / 'specs'
    subprocess.run(['git', 'init', '--quiet', str(spec_root)], check=True, capture_output=True)
    names = [entry.split(b'\t', 1)[1].decode()
             for entry in filter(None, (ROOT / 'specs.ls-tree').read_bytes().split(b'\0'))]
    subprocess.run(['git', '-C', str(spec_root), '-c', 'core.autocrlf=false', 'add', '-f', '--', *names],
                   check=True, capture_output=True)
    tree = subprocess.run(['git', '-C', str(spec_root), 'write-tree'], check=True,
                          capture_output=True, text=True).stdout.strip()
    assert tree == '028db780ac7ebaec1ac521d52b9c31eabcf34ae2'
    stored = subprocess.run(['git', '-C', str(spec_root), 'hash-object', '-w', '-t', 'commit', '--stdin'],
                            input=(ROOT / 'specs.commit').read_bytes(), check=True, capture_output=True).stdout.decode().strip()
    assert stored == PIN
    subprocess.run(['git', '-C', str(spec_root), 'update-ref', 'HEAD', PIN], check=True, capture_output=True)
    for name, expected in manifest['files'].items():
        if name.startswith('files/'):
            assert sha(work / 'new' / name[6:]) == expected, name
    env = dict(os.environ, CAMMETA_SPECS=str(work / 'specs'), ONEOF_EXPORT=str(work / 'specs'),
               PYTHONDONTWRITEBYTECODE='1')
    for label in ('old', 'new'):
        out = OUT / label
        out.mkdir()
        proc = subprocess.run([sys.executable, '-I', '-B', str(ROOT / 'probe.py'),
                               str(work / label), str(work / 'specs'), str(work / 'bd')],
                              env=dict(env, CHECK_OUT=str(out)), capture_output=True, text=True, timeout=90)
        (out / 'probe.txt').write_text(proc.stdout + proc.stderr)
        assert proc.returncode == 0, (label, proc.stdout, proc.stderr)
        controls[label] = json.loads((out / 'controls.json').read_text())
    assert all(controls['old']['shell'][name]['safety_pass'] is False
               for name in ('quoted-space', 'comment', 'quoted-gt-handler'))
    tests = {}
    for name in ('test_installer_audit_b', 'test_c_installer', 'test_console', 'test_c_shared_engines'):
        # test_console's other classes belong to the excluded historical B pin
        # (portable/runner_modules.py). Only its changed boundary class uses V7.
        filter_args = ['-k', 'Boundaries'] if name == 'test_console' else []
        proc = subprocess.run([sys.executable, '-I', '-B', '-m', 'unittest', 'discover',
                               '-s', 'tests', '-p', name + '.py', *filter_args], cwd=work / 'new', env=env,
                              capture_output=True, text=True, timeout=180)
        (OUT / (name + '.txt')).write_text(proc.stdout + proc.stderr)
        assert proc.returncode == 0, (name, proc.stdout, proc.stderr)
        tests[name + ('.Boundaries' if filter_args else '')] = int(re.search(r'Ran (\d+) tests?', proc.stderr)[1])
    green = all(item['safety_pass'] for group in controls['new'].values() for item in group.values())
    result = dict(green=green, SUT=0, old=OLD, new=NEW, pin=PIN, bd=BD, restored_spec_tree=tree,
                  manifest_sha256=MANIFEST, package_files=len(manifest['files']), git_blobs=git_blobs,
                  probe_sha256=sha(ROOT / 'probe.py'), tests=tests, controls=controls)
    (OUT / 'review-evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(green=green, SUT=0, tests=tests, git_blobs=git_blobs,
                         controls={label: {group: {key: value['safety_pass'] for key, value in items.items()}
                                           for group, items in groups.items()} for label, groups in controls.items()})), flush=True)
    raise SystemExit(not green)
