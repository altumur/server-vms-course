"""Independent before/after control. Run through the CT 103 queue only."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import time
from types import MethodType, SimpleNamespace
from unittest.mock import patch

BASE = 'a8bacaa0901014e39c71e5643aeab67e50219488'
HEAD = 'e5f3bfdbb28b5492cdab0d4432b80330ece9d143'
PIN = 'ee172a0f4b54bc88cf1178e0fb8d73a2be390a27'
MANIFEST = '2dfcad288324d2bdcf0773e1cc523297e2cb7b8ccb6e56563fbd6498a514341b'
INPUT = '0ec8371ed5ca341eb6ec249982f1c4353af57d778f1ec4e52720f5e128a35bce'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(root):
    return {str(p.relative_to(root)): digest(p) for p in root.rglob('*')
            if p.is_file() and '.git' not in p.relative_to(root).parts}


def extract(archive, destination, commit=None):
    destination.mkdir()
    with tarfile.open(archive) as stream:
        if commit:
            assert stream.pax_headers.get('comment') == commit
        stream.extractall(destination, filter='data')


def verify_tree(root, listing):
    entries = listing.read_bytes().split(b'\0')
    count = 0
    for entry in filter(None, entries):
        header, name = entry.split(b'\t', 1)
        mode, kind, wanted = header.split()
        assert kind == b'blob'
        target = root / name.decode()
        raw = os.readlink(target).encode() if mode == b'120000' else target.read_bytes()
        assert hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == wanted.decode()
        count += 1
    return count


def control(runtime, specs, fixed):
    sys.path.insert(0, str(runtime / 'runner'))
    import m11stand
    import stand
    stamp = [fixed]
    clock = SimpleNamespace(time=lambda: stamp[0], gmtime=time.gmtime, strftime=time.strftime)
    with tempfile.TemporaryDirectory(prefix='onappend-model-') as directory:
        root = Path(directory)
        objects, signals = [], []
        clusters = {}
        for name in ('hold', 'm1', 'm2'):
            cluster = SimpleNamespace(data=str(root / name))
            cluster.append_event = MethodType(stand.Stand.append_event, cluster)
            cluster.object_directive = lambda *args, c=name: objects.append((c, args[0])) or None
            cluster.signal = lambda role, sig, c=name: signals.append((c, role, sig)) or False
            clusters[name] = cluster
        run = m11stand.Run(SimpleNamespace(json=None), 'review-onappend')
        run.b = SimpleNamespace(clusters=clusters, offsets={'m1': 100000, 'm2': -100000})
        published = specs / 'Platform/08-domain/acceptance/4/scenarios.tsv'
        requests = [line.split('\t') for line in published.read_text().splitlines()
                    if line.startswith('11-events-view\t4\t') or line.startswith('11-events-view\t5\t')]
        assert len(requests) == 2
        with patch.object(stand, 'time', clock):
            outcomes = [run.step(step, req, expected)[0] for _, step, req, expected in requests]
        paths = sorted(root.rglob('*.events.jsonl'))
        observed = {str(p.relative_to(root)): p.read_text() for p in paths}
        green = outcomes == [[], []] and len(paths) == 2 and not objects and not signals
        if not green:
            assert outcomes == [['the directive failed'], ['the directive failed']]
            assert not paths and len(signals) == 2 and all(r[1] == 'event' for r in signals)
            return {'requested_behavior': 'RED', 'outcomes': outcomes, 'signal_calls': signals,
                    'events': observed}
        bucket = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime(int(fixed) // 600 * 600)) + '.events.jsonl'
        expected_lines = [
            '{"id": "ev-alarm-c2", "t": %.3f, "kind": "jam", "class": "alarm", "of": "testsub/c2"}\n' % fixed,
            '{"id": "ev-tick-c1", "t": %.3f, "kind": "tick", "of": "testsub/c1"}\n' % fixed,
        ]
        for unit, text in zip(('c2', 'c1'), expected_lines):
            assert (root / 'm1/events/testsub' / unit / 'e1' / bucket).read_text() == text
        assert not (root / 'hold').exists() and not (root / 'm2').exists()

        # Append twice to another cluster; preserve existing bytes and Unicode/spacing.
        payload = '{"note": "привет  мир", "t": {now}, "again": "{now}"}  '
        target = root / 'm2/events/testsub/leaf/e2' / bucket
        target.parent.mkdir(parents=True)
        target.write_bytes(b'{"id":"preexisting"}\n')
        with patch.object(stand, 'time', clock):
            for _ in range(2):
                assert run.step('extra', '@on m2 @append event testsub/leaf/e2 ' + payload, 'ok') == ([], None)
        literal = '{"note": "привет  мир", "t": %.3f, "again": "%.3f"}  \n' % (fixed, fixed)
        assert target.read_bytes() == b'{"id":"preexisting"}\n' + literal.encode() * 2
        assert {p: v for p, v in observed.items()} == {
            p: (root / p).read_text() for p in observed}

        # A boundary crossing creates a new current-window file, without changing the old one.
        stamp[0] = (int(fixed) // 600 + 1) * 600 + 0.25
        with patch.object(stand, 'time', clock):
            assert not run.directive('@on m2 @append event testsub/leaf/e2 next {now}', 'ok')
        new_bucket = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime(int(stamp[0]))) + '.events.jsonl'
        assert target.with_name(new_bucket).read_text() == 'next %.3f\n' % stamp[0]
        assert target.read_bytes() == b'{"id":"preexisting"}\n' + literal.encode() * 2

        before_bad = snapshot(root)
        try:
            run.step('missing', '@on m1 @append event testsub/c2/e1', 'ok')
        except ValueError:
            pass
        else:
            raise AssertionError('missing text was accepted')
        assert snapshot(root) == before_bad and not signals and not objects
        for ref in ('testsub/c2/e0', 'testsub/c2/e01', 'testsub//e1', 'testsub/c2/e1/extra'):
            assert run.directive('@on m1 @append event ' + ref + ' text', 'ok')
            assert snapshot(root) == before_bad
        assert not signals and not objects
        return {'requested_behavior': 'GREEN', 'published_steps': 2,
                'clock': fixed, 'events': observed, 'append_preserves_bytes': True,
                'cluster_isolation': True, 'clock_window_rollover': True,
                'missing_text_value_error': True, 'bad_references_no_write': 4,
                'signal_calls': signals, 'object_calls': objects}


def main():
    root = Path(__file__).resolve().parent
    out = Path(os.environ['CHECK_OUT'])
    package = root / 'package'
    assert digest(package / 'MANIFEST.json') == MANIFEST
    manifest = json.loads((package / 'MANIFEST.json').read_text())
    for name, sha in manifest['files'].items():
        assert digest(package / name) == sha, name
    assert digest(root / 'author-input.tar.gz') == INPUT
    with tempfile.TemporaryDirectory(prefix='review-onappend-') as directory:
        work = Path(directory)
        extract(root / 'author-input.tar.gz', work / 'author')
        author = work / 'author/in'
        baseline = snapshot(author)
        verified = {}
        for label, commit in (('before', BASE), ('after', HEAD)):
            extract(root / (label + '.tar'), work / label, commit)
            verified[label] = verify_tree(work / label, root / (label + '.ls-tree'))
        before, after = snapshot(work / 'before'), snapshot(work / 'after')
        assert {p for p in before.keys() | after.keys() if before.get(p) != after.get(p)} == {
            'runner/m11stand.py', 'tests/test_on_append_event.py'}
        assert after == snapshot(author / 'runner')
        assert (work / 'after/SPEC_VERSION').read_text().strip() == PIN
        for name in ('runner/m11stand.py', 'tests/test_on_append_event.py'):
            assert digest(package / 'files' / name) == digest(work / 'after' / name)
        os.environ.update(CAMMETA_SPECS=str(author / 'specs'), PYTHONDONTWRITEBYTECODE='1')
        controls = {}
        for label in ('before', 'after'):
            controls[label] = []
            for now in (1712345678.125, 1712345999.875):
                proc = subprocess.run([sys.executable, '-I', '-B', str(Path(__file__).resolve()),
                                       '--control', str(work / label), str(author / 'specs'), str(now)],
                                      capture_output=True, text=True, timeout=30)
                assert proc.returncode == 0, (label, proc.stdout, proc.stderr)
                controls[label].append(json.loads(proc.stdout))
        assert all(c['requested_behavior'] == 'RED' for c in controls['before'])
        assert all(c['requested_behavior'] == 'GREEN' for c in controls['after'])
        tests = {}
        for name in ('test_on_append_event', 'test_c_domain_stand', 'test_runner'):
            proc = subprocess.run([sys.executable, '-I', '-B', '-m', 'unittest', 'discover',
                                   '-s', 'tests', '-p', name + '.py'], cwd=work / 'after',
                                  capture_output=True, text=True, timeout=90)
            (out / (name + '.txt')).write_text(proc.stdout + proc.stderr)
            assert proc.returncode == 0, (name, proc.stdout, proc.stderr)
            tests[name] = proc.stderr.strip()
        assert snapshot(author) == baseline
        result = {'green': True, 'SUT': 0, 'manifest_sha256': MANIFEST,
                  'package_files': len(manifest['files']), 'author_input_sha256': INPUT,
                  'author_input_files': len(baseline), 'inputs_unchanged': True,
                  'git_blobs': verified, 'controls': controls, 'tests': tests}
        (out / 'review-evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--control':
        print(json.dumps(control(Path(sys.argv[2]), Path(sys.argv[3]), float(sys.argv[4])), ensure_ascii=False))
    else:
        main()
