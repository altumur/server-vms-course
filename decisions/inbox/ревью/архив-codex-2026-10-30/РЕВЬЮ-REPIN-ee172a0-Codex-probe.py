"""Read-only review of a8bacaa. Execute only through the CT 103 queue."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
from types import SimpleNamespace

BASE = '3427b93f01d4468d5eb2565bec93d9566ab94289'
HEAD = 'a8bacaa0901014e39c71e5643aeab67e50219488'
OLD_PIN = '8d67ccdeddeb044e1d6e75fcd2c071b3cc60df22'
PIN = 'ee172a0f4b54bc88cf1178e0fb8d73a2be390a27'
MANIFEST = 'daf6dba61c7d70ca5af83c160a9c45ac4d3510ac4e1a2c99b4188b22a25914fd'
INPUT = '34fa239b98a8b04aa83a2fb4eb246526efc4ea1645cc0ea119950b4b43272133'
NEW_CASES = {'remove-garbled-rewritten', 'garbled-two-elements'}
CHANGED_TABLES = {'Platform/common/vectors/tombstone/cases.tsv',
                  'Platform/06-console/vectors/metrics/cases.tsv'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text())


def files(root):
    return {p.relative_to(root).as_posix(): sha(p) for p in root.rglob('*')
            if p.is_file() and '.git' not in p.relative_to(root).parts}


def extract(archive, dest, commit=None):
    dest.mkdir()
    with tarfile.open(archive) as stream:
        if commit:
            assert stream.pax_headers.get('comment') == commit, stream.pax_headers
        stream.extractall(dest, filter='data')


def verify_blobs(root, listing):
    count = 0
    for entry in listing.split(b'\0'):
        if not entry:
            continue
        metadata, path = entry.split(b'\t', 1)
        mode, kind, digest = metadata.split()
        assert kind == b'blob', metadata
        target = root / path.decode()
        data = os.readlink(target).encode() if mode == b'120000' else target.read_bytes()
        actual = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        assert actual == digest.decode(), path
        count += 1
    return count


def probe(runtime, old_spec, new_spec):
    sys.path.insert(0, str(runtime / 'runner'))
    import assembly
    import c_targets
    import c_vector_packages as packs
    import c_vector_protocol as wire

    inventories = [c_targets.inventory(s) for s in (old_spec, new_spec)]
    tables = [{v['path']: v for v in inv['tables']} for inv in inventories]
    assert len(tables[0]) == len(tables[1]) == 174
    assert tables[0].keys() == tables[1].keys()
    assert {p for p in tables[0] if tables[0][p]['sha256'] != tables[1][p]['sha256']} == CHANGED_TABLES
    assert [(tables[i]['Platform/common/vectors/tombstone/cases.tsv']['rows'],
             tables[i]['Platform/06-console/vectors/metrics/cases.tsv']['rows'])
            for i in (0, 1)] == [(20, 28), (21, 29)]

    parts = {m: SimpleNamespace(doc={'keys': {'role': 'acc'}, 'stand': {},
                                    'adapters': {}, 'vectors': {}}) for m in assembly.MODULES}
    for target in c_targets.CONNECTED_TARGETS:
        for owner, group, key in (*target.requires, *target.requires_any):
            if group:
                parts[owner].doc[group][key] = 'PLAN-ONLY'
    plans = [c_targets.plan(SimpleNamespace(parts=parts, specs=spec, spec_version=pin),
                           [t.id for t in c_targets.CONNECTED_TARGETS])
             for spec, pin in ((old_spec, OLD_PIN), (new_spec, PIN))]
    assert len(plans[0]) == len(plans[1]) == 230
    structural = lambda p: {k: v for k, v in p.items()
                            if k not in ('inputs', 'execution_cases', 'spec_version')}
    assert [structural(p) for p in plans[0]] == [structural(p) for p in plans[1]]
    assert all(p['status'] == 'ready' for p in plans[1])

    def cases(ps):
        answer = {}
        for plan in ps:
            for original in plan.get('execution_cases', []):
                row = copy.deepcopy(original)
                row.pop('spec_version', None)
                row.pop('table_sha256', None)
                identity = (plan['id'], json.dumps(row, sort_keys=True))
                assert identity not in answer
                answer[identity] = original
        return answer
    before, after = map(cases, plans)
    assert not before.keys() - after.keys()
    added = [after[k] for k in after.keys() - before.keys()]
    assert len(added) == 2 and {c['case'] for c in added} == NEW_CASES
    for row in after.values():
        if 'table_sha256' in row:
            assert row['spec_version'] == PIN
            assert row['table_sha256'] == sha(new_spec / row['source'])

    checks = []
    for driver, owner, case, expected, bad in (
        ('vector-tombstone', '05-resource', 'remove-garbled-rewritten', 'keep', ['remove', None, True]),
        ('vector-metrics', '06-console', 'garbled-two-elements',
         {'lines': ['# TYPE testsub_jam_n gauge', 'testsub_jam_n{worker="w-1"} 0',
                    '# TYPE testsub_jam_age gauge', 'testsub_jam_age{worker="w-1"} 0'], 'garbled': 2},
         [{'lines': ['# TYPE testsub_jam_n gauge', 'testsub_jam_n{worker="w-1"} 0',
                     '# TYPE testsub_jam_age gauge', 'testsub_jam_age{worker="w-1"} 0'], 'garbled': n}
          for n in (0, 1, True, '2')]),
    ):
        selected = [r for r in packs.rows(new_spec, driver, owner) if r['case'] == case]
        assert len(selected) == 1
        row = selected[0]
        assert row['expected'] == expected
        frame = wire.decode_request(wire.encode_request(**{k: row[k]
                    for k in ('package', 'table', 'case', 'variant', 'cells', 'files')}))
        assert frame['cells'] == row['cells']
        assert not ({'expect', 'note', 'expected'} & frame['cells'].keys())
        errors = lambda value, code=0: packs.native_errors(driver, {
            'exit_code': code, 'stdout': json.dumps(value).encode(), 'stderr': b''}, row)
        assert not errors(expected)
        assert errors(expected, 2)
        for wrong in bad:
            assert errors(wrong), (case, wrong)
        checks.append({'case': case, 'owner': owner, 'negative_answers': len(bad) + 1})
    console_cases = packs.rows(new_spec, 'vector-tombstone', '06-console')
    assert all(r['cells']['op'] == 'peers' for r in console_cases)
    assert not NEW_CASES & {r['case'] for r in console_cases}
    return {'tables': 174, 'ready': 230, 'existing_execution_cases': len(before),
            'added_execution_cases': added, 'new_case_checks': checks}


def main():
    r = Path(__file__).resolve().parent
    out = Path(os.environ['CHECK_OUT'])
    package = r / 'package'
    assert sha(package / 'MANIFEST.json') == MANIFEST
    manifest = read_json(package / 'MANIFEST.json')
    for name, digest in manifest['files'].items():
        assert sha(package / name) == digest, name
    assert sha(r / 'author-input.tar.gz') == INPUT
    with tempfile.TemporaryDirectory(prefix='review-ee172-') as temp:
        work = Path(temp)
        extract(r / 'author-input.tar.gz', work / 'author')
        author = work / 'author/in'
        source = read_json(package / 'reproduce/SOURCE-SHA.json')
        for name, digest in source.items():
            assert sha(author / name) == digest, name
        for name, commit in (('runner-before', BASE), ('runner-after', HEAD), ('specs-before', OLD_PIN)):
            extract(r / (name + '.tar'), work / name, commit)
        blobs = {name: verify_blobs(work / name, (r / (name + '.ls-tree')).read_bytes())
                 for name in ('runner-before', 'runner-after', 'specs-before')}
        old, new, oldspec, newspec = (work / 'runner-before', work / 'runner-after',
                                    work / 'specs-before', author / 'specs')
        # Git archive preserves bytes, while later_tables also needs the pinned tree.
        # The author's separately pinned jsdom checkout retains that exact old tree.
        shutil.copytree(author / 'specs-jsdom/.git', oldspec / '.git')
        assert subprocess.check_output(['git', '-C', str(oldspec), 'rev-parse', 'HEAD'],
                                       text=True).strip() == OLD_PIN
        assert files(new) == files(author / 'runner')
        code_before, code_after = files(old), files(new)
        assert {p for p in code_before.keys() | code_after.keys()
                if code_before.get(p) != code_after.get(p)} == {
                    'README.md', 'SPEC_VERSION', 'tests/test_repin_ee172a0.py'}
        oldfiles, newfiles = files(oldspec), files(newspec)
        assert oldfiles.keys() == newfiles.keys()
        export_delta = {p for p in oldfiles if oldfiles[p] != newfiles[p]}
        declared = read_json(package / 'reproduce/EXPORT-DELTA.json')['files']
        assert export_delta == {v['path'] for v in declared} and len(export_delta) == 14
        for v in declared:
            assert oldfiles[v['path']] == v['before_sha256']
            assert newfiles[v['path']] == v['after_sha256']
            assert sha(package / 'export-before' / v['path']) == v['before_sha256']
            assert sha(package / 'export-after' / v['path']) == v['after_sha256']
        os.environ.update(CAMMETA_SPECS=str(newspec), PYTHONDONTWRITEBYTECODE='1')
        probes = {}
        for label, runtime in (('before', old), ('after', new)):
            p = subprocess.run([sys.executable, '-I', '-B', str(Path(__file__).resolve()),
                                '--probe', str(runtime), str(oldspec), str(newspec)],
                               capture_output=True, text=True, timeout=90)
            (out / (label + '-probe.txt')).write_text(p.stdout + p.stderr)
            assert p.returncode == 0, (label, p.stdout, p.stderr)
            probes[label] = json.loads(p.stdout)
        assert probes['before'] == probes['after']
        modules = ['test_repin_ee172a0', 'test_c_resource_vectors', 'test_c_console_vectors',
                   'test_c_vector_protocol', 'test_c_pinned_vector_tables']
        tests = {}
        for module in modules:
            p = subprocess.run([sys.executable, '-I', '-B', '-m', 'unittest', 'discover',
                                '-s', 'tests', '-p', module + '.py'], cwd=new,
                               capture_output=True, text=True, timeout=90)
            (out / (module + '.txt')).write_text(p.stdout + p.stderr)
            assert p.returncode == 0, (module, p.stdout, p.stderr)
            tests[module] = p.stderr.strip()
        for name, digest in source.items():
            assert sha(author / name) == digest, name
        result = {'green': True, 'SUT': 0, 'manifest_sha256': MANIFEST,
                  'package_files_verified': len(manifest['files']), 'source_files_verified': len(source),
                  'author_input_sha256': INPUT, 'inputs_unchanged': True, 'archive_blobs': blobs,
                  'changed_runner_files': ['README.md', 'SPEC_VERSION', 'tests/test_repin_ee172a0.py'],
                  'export_delta_files': sorted(export_delta), 'probes': probes, 'tests': tests}
        (out / 'review-evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--probe':
        print(json.dumps(probe(*(Path(p) for p in sys.argv[2:])), ensure_ascii=False))
    else:
        main()
