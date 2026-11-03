"""Independent pinned rows, exact public fixture bytes and real profile entrypoint."""
import base64
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(sys.argv[1]) / 'runner'))
import c_domain_packages
import c_package_vectors as cli
import c_targets
import c_vector_packages as packages
import c_vector_protocol as wire

specs = Path(sys.argv[2])
out = Path(os.environ['CHECK_OUT'])
readme = (specs / 'Platform/common/vectors/accept/README.md').read_text()
declared = re.findall(r'\| `(testsub2?)` \| .*? \| `([0-9a-f]{64})` \|', readme)
assert len(declared) == 2
wanted = {name + '.subsystem.yaml': digest for name, digest in declared}
raws = {name: (specs / 'Source/tests/testdata' / name).read_bytes() for name in wanted}
assert all(hashlib.sha256(raws[name]).hexdigest() == digest for name, digest in wanted.items())
snapshot, accept, controls = {}, {}, {}
def typed(value):
    if isinstance(value, dict):
        return ['dict', [[typed(k), typed(v)] for k, v in sorted(value.items())]]
    if isinstance(value, (list, tuple)):
        return [type(value).__name__, [typed(v) for v in value]]
    return [type(value).__name__, repr(value)]

# Compare every pair dispatched through the changed domain adapter, not only accept.
for driver, definition in packages.DEFINITIONS.items():
    owners = definition['owners'] if driver in packages.DOMAIN_DRIVERS else (
        tuple(o for o in definition['owners'] if o in ('08-domain', '09-agent', '10-domain-console'))
        if driver in packages.CONSOLE_DRIVERS else ())
    for owner in owners:
        rows = packages.rows(specs, driver, owner)
        stripped = [{k: v for k, v in row.items() if k != 'files'} for row in rows]
        key = driver + ':' + owner
        snapshot[key] = dict(rows=len(rows), sha256=hashlib.sha256(json.dumps(typed(stripped)).encode()).hexdigest())
        if driver != 'vector-accept':
            assert all(row['files'] == {} for row in rows), key
            continue
        assert len(rows) == 62
        frames = [wire.decode_request(wire.encode_request(**{k: row[k] for k in
                   ('package', 'table', 'case', 'variant', 'cells', 'files')})) for row in rows]
        exact = all(set(frame['files']) == set(wanted) and
                    all(base64.b64decode(frame['files'][name], validate=True) == raw for name, raw in raws.items())
                    for frame in frames)
        assert all(frame['cells'] == row['cells'] and set(frame) == wire.REQUEST_FIELDS
                   for row, frame in zip(rows, frames))
        rows[0]['files'].clear()
        isolated = set(rows[1]['files']) == set(wanted)
        accept[owner] = dict(rows=len(rows), exact_files=exact, independent_row_maps=isolated)
        controls['all_frames_' + owner] = exact and isolated

sources = packages.sources(packages.DEFINITIONS['vector-accept'], specs)
sealed = all('Source/tests/testdata/' + name in sources for name in wanted)
controls['fixtures_in_sources'] = sealed
parts = {owner: SimpleNamespace(doc=dict(keys={}, vectors={'common/accept': 'PLAN-ONLY'}))
         for owner in ('08-domain', '09-agent')}
plans = c_targets.plan(SimpleNamespace(specs=specs, spec_version=(Path(sys.argv[1])/'SPEC_VERSION').read_text().strip(),
                                       parts=parts), ['P/08/vectors-accept', 'P/09/vectors-accept'])
assert len(plans) == 2
for plan in plans:
    supplied = {item['path']: item['sha256'] for item in plan['inputs']}
    controls['plan_' + plan['id']] = (len(plan['execution_cases']) == 62 and
        all(supplied.get('Source/tests/testdata/' + name) == digest for name, digest in wanted.items()))

with tempfile.TemporaryDirectory(prefix="rv-accept '") as directory:
    root = Path(directory)
    helper = root / 'profile.py'
    helper.write_text('''import base64,hashlib,json,sys
p=json.loads(open(sys.argv[1]).read())
assert set(p)=={'format','package','table','case','variant','cells','files'}
assert p['package']=='common/accept'
wanted=''' + repr(wanted) + '''
assert set(p['files'])==set(wanted)
assert all(hashlib.sha256(base64.b64decode(p['files'][n],validate=True)).hexdigest()==h for n,h in wanted.items())
print(json.dumps(dict(exit_code=2,stdout_b64='',stderr_b64='')))
''')
    command = shlex.join([sys.executable, '-I', '-B', str(helper)]) + ' {input}'
    for owner in ('08-domain', '09-agent'):
        selected = next(row for row in packages.rows(specs, 'vector-accept', owner) if row['expected_exit_code'] == 2)
        config = root / (owner + '.config.json')
        config.write_text(json.dumps(dict(specs=str(specs), spec_version=(Path(sys.argv[1])/'SPEC_VERSION').read_text().strip(),
            parts={name: dict(cwd=str(root), vectors={'common/accept': command if name == owner else 'exit 91'})
                   for name in ('08-domain', '09-agent')})))
        report = root / (owner + '.json')
        # One published @exit 2 row isolates the profile transport; the helper
        # verifies input, then returns that native code without computing accept.
        with patch.object(packages, 'rows', return_value=[selected]), contextlib.redirect_stdout(io.StringIO()):
            code = cli.main(['--config', str(config), '--owner', owner, '--driver', 'vector-accept', '--json', str(report)])
        got = json.loads(report.read_text())
        payload = wire.decode_request((root / (owner + '-processes/case-0001/input.json')).read_bytes())
        assert payload['case'] == selected['case'] and payload['cells'] == selected['cells']
        controls['native_profile_' + owner] = code == 0 and got['green'] and got['cases'] == [1, 1]

    # Missing/empty/non-UTF8 public fixture must be rejected before any command.
    broken = root / 'broken'
    folder = broken / 'Platform/common/vectors/accept'
    folder.mkdir(parents=True)
    shutil.copyfile(specs / 'Platform/common/vectors/accept/cases.tsv', folder / 'cases.tsv')
    data = broken / 'Source/tests/testdata'
    data.mkdir(parents=True)
    (data / 'testsub.subsystem.yaml').write_bytes(raws['testsub.subsystem.yaml'])
    for mode, raw in [('missing', None), ('empty', b' \r\n'), ('non_utf8', b'\xff')]:
        path = data / 'testsub2.subsystem.yaml'
        if raw is not None:
            path.write_bytes(raw)
        rejected = False
        try:
            packages.rows(broken, 'vector-accept', '08-domain')
        except c_targets.DataError:
            rejected = True
        controls['bad_fixture_' + mode] = rejected

result = dict(green=all(controls.values()), snapshot=snapshot, accept=accept,
              fixture_sha256=wanted, sources=list(sources), controls=controls)
(out / 'controls.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(dict(green=result['green'], adapter_pairs=len(snapshot), controls=controls)))
