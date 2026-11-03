"""Two unchanged independent probes on r2/r3 Git snapshots; CT103 only."""
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
OLD = 'fd1af474158189a737a122ae4e2166e842dbe750'
NEW = 'dd67722c4c986ab5e76c06ef778d45a3bd033220'
SPEC = 'd389cf5e47db0902f8d660f7bb6f917eb1588925'
MANIFEST = '7b1206878afcfb93ecd67ae168ee631817e45d7988ba5405785e575c50abcd63'
PROBES = {
    'probe.py': '1d3ec87223b0b15a071586e789b265a1a953b9ebc74eaee315bb5f6f85dc1f6d',
    'extra.py': '820c476f3c26a546930657f5bd58f915aacb3455e8bb212d43387537d1334cc6',
}


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
        data = os.readlink(path).encode() if mode == b'120000' else path.read_bytes()
        assert hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == wanted.decode(), name
        count += 1
    return count


for filename, wanted in PROBES.items():
    assert sha(ROOT / filename) == wanted, filename
package = ROOT / 'package'
assert sha(package / 'MANIFEST.json') == MANIFEST
manifest = json.loads((package / 'MANIFEST.json').read_text())
for name, wanted in manifest['files'].items():
    assert sha(package / name) == wanted, name

with tempfile.TemporaryDirectory(prefix='rv-rid-r3-') as directory:
    work = Path(directory)
    extract(ROOT / 'specs.tar', work / 'specs', SPEC)
    spec_blobs = blobs(work / 'specs', ROOT / 'specs.ls-tree')
    os.environ.update(CAMMETA_SPECS=str(work / 'specs'), ONEOF_EXPORT=str(work / 'specs'),
                      PYTHONDONTWRITEBYTECODE='1')
    controls, extra, git_blobs = {}, {}, {}
    for label, commit in [('old', OLD), ('new', NEW)]:
        runtime = work / label
        extract(ROOT / (label + '.tar'), runtime, commit)
        git_blobs[label] = blobs(runtime, ROOT / (label + '.ls-tree'))
        if label == 'new':
            for name, wanted in manifest['files'].items():
                if name.startswith('files/'):
                    assert sha(runtime / name[6:]) == wanted, name
        out = OUT / label
        out.mkdir()
        for filename in PROBES:
            proc = subprocess.run([sys.executable, '-I', '-B', str(ROOT / filename), str(runtime)],
                                  env=dict(os.environ, CHECK_OUT=str(out)), capture_output=True,
                                  text=True, timeout=60)
            (out / (filename + '.txt')).write_text(proc.stdout + proc.stderr)
            assert proc.returncode == 0, (label, filename, proc.stdout, proc.stderr)
        controls[label] = json.loads((out / 'controls.json').read_text())
        extra[label] = json.loads((out / 'extra-controls.json').read_text())

    # Preserve the r2 counterexample: objects and the exporter lifecycle fail,
    # while report identities, JSON strings and ordinary short secrets pass.
    assert all(not value['safety_pass'] for value in extra['old'].values())
    assert all(value['safety_pass'] == (not key.endswith('-object'))
               for key, value in controls['old'].items())
    tests = {}
    for name in ('test_report_identity_secrets', 'test_diagnostic_secrets', 'test_judge_diagnostics'):
        proc = subprocess.run([sys.executable, '-I', '-B', '-m', 'unittest', 'discover',
                               '-s', 'tests', '-p', name + '.py'], cwd=work / 'new',
                              capture_output=True, text=True, timeout=90)
        (OUT / (name + '.txt')).write_text(proc.stdout + proc.stderr)
        assert proc.returncode == 0, (name, proc.stdout, proc.stderr)
        tests[name] = int(re.search(r'Ran (\d+) tests?', proc.stderr)[1])
    result = dict(green=all(value['safety_pass'] for value in controls['new'].values())
                       and all(value['safety_pass'] for value in extra['new'].values()),
                  SUT=0, old=OLD, new=NEW, spec=SPEC, manifest_sha256=MANIFEST,
                  package_files=len(manifest['files']), git_blobs=git_blobs, spec_blobs=spec_blobs,
                  probe_sha256=PROBES, tests=tests, controls=controls, extra=extra)
    (OUT / 'review-evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(green=result['green'], SUT=0, package_files=result['package_files'],
                         git_blobs=git_blobs, spec_blobs=spec_blobs, tests=tests,
                         controls={label: {key: val['safety_pass'] for key, val in values.items()}
                                   for label, values in controls.items()},
                         extra={label: {key: val['safety_pass'] for key, val in values.items()}
                                for label, values in extra.items()})), flush=True)
    raise SystemExit(not result['green'])
