"""Two independently frozen R3 series, exact Git snapshots and author inputs; CT103 only."""
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
COMMITS = {'D': 'f1a1af309994023dac4b57973979edddf9ca2cfe', 'D-ce8': 'ce8d1fd60be061ca9288924154f46f37399fed84',
           'D-main': '9dca23bdedbace1ddf83b9af08503230976ddfd6', 'D-old': '50ce0b0bacc14eec60f384fef1aa38eb089b34d5',
           'D-specs': '13a30dcbf6a17c7023b518c20bdae96a100058cd', 'p08': '4b50e7fbd02ddbe5052765df7e9ce214bf238310',
           'p08-old': '6e03664a61d900a61b4e377e5f8a7c19be420e1d', 'p08-specs': '82490f29dcc5bd47e98f6b806e9b115d7a930e32'}
PACKETS = {'D': ('1e32989d383ed8a4b396223faa412968a25f1e552aacedac0d917cd399624d37',
                 '93c176a8a2ae047cd7c73419350f94d16637ad34e33e28543e591a3bcfe8e1fb'),
           'p08': ('4deaa0dc19812cf181719c8aa9ed58fb450d61d67a89e2eaaccf8312f5312311',
                   'a41322ba350f7b8ba21ac92b326d2bacbfff761c4c3e7d7a759cbe3b760e25a6')}
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def files(root): return {str(p.relative_to(root)): sha(p) for p in root.rglob('*') if p.is_file() and '.git' not in p.relative_to(root).parts}
def extract(archive, target, commit=None):
    target.mkdir()
    with tarfile.open(archive) as stream:
        if commit: assert stream.pax_headers['comment'] == commit
        stream.extractall(target, filter='data')
def blobs(root, listing):
    count = 0
    for line in filter(None, listing.read_bytes().split(b'\0')):
        meta, name = line.split(b'\t', 1); mode, kind, wanted = meta.split(); assert kind == b'blob'
        path = root / name.decode(); raw = os.readlink(path).encode() if mode == b'120000' else path.read_bytes()
        assert hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == wanted.decode(), name
        count += 1
    return count
evidence = {'SUT': 0, 'commits': COMMITS, 'series': {}}
with tempfile.TemporaryDirectory(prefix='rv-runner-r3-') as directory:
    work = Path(directory)
    for name, commit in COMMITS.items():
        extract(ROOT / (name + '.tar'), work / name, commit)
        evidence.setdefault('git_blobs', {})[name] = blobs(work / name, ROOT / (name + '.ls-tree'))
    for label, (manifest_sha, author_sha) in PACKETS.items():
        packet = ROOT / (label + '-package'); assert sha(packet / 'MANIFEST.json') == manifest_sha
        manifest = json.loads((packet / 'MANIFEST.json').read_text())
        for name, wanted in manifest['files'].items(): assert sha(packet / name) == wanted, (label, name)
        assert sha(ROOT / (label + '-author.tar.gz')) == author_sha
        extract(ROOT / (label + '-author.tar.gz'), work / (label + '-author'))
        author = work / (label + '-author/in'); before = files(author)
        runtime, specs = work / label, work / (label + '-specs')
        assert files(runtime) == files(author / 'runner') and files(specs) == files(author / 'specs'), label
        if label == 'D':
            merge = json.loads((packet / 'MERGE.json').read_text()); names = merge['main_files_exact']
            merged, main, own = files(runtime), files(work / 'D-main'), files(work / 'D-ce8')
            assert len(names) == 10
            assert all(merged[name] == main[name] for name in names)
            assert {n: s for n, s in merged.items() if n not in names} == {n: s for n, s in own.items() if n not in names}
        else:
            for name, wanted in files(packet / 'files').items(): assert sha(runtime / name) == wanted
        # Reconstruct the exact specs commit in the disposable copy for pin-checking tests.
        def git(*args, input=None): return subprocess.check_output(['git', '-C', str(specs), *args], input=input, stderr=subprocess.PIPE).strip()
        git('init', '-q')
        names = b''.join(line.split(b'\t', 1)[1] + b'\0' for line in filter(None, (ROOT / (label + '-specs.ls-tree')).read_bytes().split(b'\0')))
        git('add', '-f', '--pathspec-from-file=-', '--pathspec-file-nul', input=names)
        assert git('write-tree').decode() == {'D': '5c4a5df9d8f8ec0b52c27fe96369c4007c03f4fa',
                                             'p08': '57ea8fde730478c643f842a34855f0b3f080a9b1'}[label]
        assert git('hash-object', '-w', '-t', 'commit', '--stdin', input=(ROOT / (label + '-specs.commit')).read_bytes()).decode() == COMMITS[label + '-specs']
        git('update-ref', 'HEAD', COMMITS[label + '-specs'])
        os.environ.update(CAMMETA_SPECS=str(specs), ONEOF_EXPORT=str(specs), PYTHONDONTWRITEBYTECODE='1', GIT_OPTIONAL_LOCKS='0')
        controls = {}
        for phase in ('old', 'new'):
            snapshot = work / (label + '-old') if phase == 'old' else runtime
            out = OUT / (label + '-' + phase); out.mkdir()
            scripts = ('EOF.py', 'TCP.py') if label == 'D' else ('exceptions.py',)
            for script in scripts:
                proc = subprocess.run([sys.executable, '-I', '-B', str(ROOT / script), str(snapshot)],
                                      env=dict(os.environ, CHECK_OUT=str(out)), capture_output=True, text=True, timeout=100)
                (out / (script + '.txt')).write_text(proc.stdout + proc.stderr)
                assert proc.returncode == 0, (label, script, proc.stderr)
            if label == 'D':
                controls[phase] = dict(EOF=json.loads((out / 'controls.json').read_text()), TCP=json.loads((out / 'client-controls.json').read_text()))
                assert sum(row['code'] == 413 for row in controls[phase]['TCP'][:3]) == (3 if phase == 'new' else 0)
                assert controls[phase]['TCP'][-1]['code'] is None and controls[phase]['TCP'][-1]['error']
                for name in ('http_close_small', 'http_close_large', 'client_half_close'):
                    assert controls[phase]['EOF'][name]['safety_pass'] == (phase == 'new')
                assert all(controls[phase]['EOF'][name]['safety_pass'] for name in ('stale_watchdog', 'forgotten_pause'))
            else:
                controls[phase] = json.loads((out / 'exceptions.json').read_text())
                controls[phase]['identity'] = json.loads((out / 'identity.json').read_text())
                assert controls[phase]['safety_pass'] == (phase == 'new')
        tests = {}
        modules = ('test_scenario_control', 'test_l04_store', 'test_transport_diagnostics', 'test_request_correlation', 'test_c_shared_engines',
                   'test_console', 'test_report_identity_secrets', 'test_installer_audit_b') if label == 'D' else (
                   'test_domain_freeze', 'test_c_domain_pin', 'test_scenario_control', 'test_c_execution', 'test_c_domain_stand')
        for name in modules:
            command = [sys.executable, '-I', '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-p', name + '.py']
            if name == 'test_console':
                # This legacy module is outside V7; select its actually changed test explicitly.
                command = [sys.executable, '-I', '-B', '-c', "import sys,unittest;sys.path.insert(0,'tests');s=unittest.defaultTestLoader.loadTestsFromName('test_console.Boundaries.test_probe_x_is_loaded_only_in_monitoring_scenarios_from_its_stand');r=unittest.TextTestRunner(verbosity=1).run(s);sys.exit(not r.wasSuccessful())"]
            proc = subprocess.run(command,
                                  cwd=runtime, capture_output=True, text=True, timeout=180)
            (OUT / (label + '-' + name + '.txt')).write_text(proc.stdout + proc.stderr)
            assert proc.returncode == 0, (label, name, proc.stderr[-3000:])
            tests[name] = int(re.search(r'Ran (\d+) tests?', proc.stderr)[1])
        assert files(author) == before
        evidence['series'][label] = dict(manifest_sha256=manifest_sha, package_files=len(manifest['files']),
            author_input_sha256=author_sha, author_input_files=len(before), inputs_unchanged=True, tests=tests,
            total_tests=sum(tests.values()), controls=controls)
    evidence['verified'] = True
    (OUT / 'review-evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: {n: v for n, v in row.items() if n != 'controls'} for k, row in evidence['series'].items()}), flush=True)
