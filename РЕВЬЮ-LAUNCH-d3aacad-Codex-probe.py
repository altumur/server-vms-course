"""Real c_store/Run.move/child differential. CT103 only; no SUT or raw credentials in output."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(sys.argv[1]) / 'runner'))
import c_store
import cli_evidence as cli
import diagnostic_secrets as ds
from harness import TransportError
import m11stand
import stand

changed = importlib.util.find_spec('launch_environment') is not None
digest = lambda text: hashlib.sha256(text.encode()).hexdigest()
credentials = dict(current='fixture-current-A', cluster='fixture-cluster-B', inherited='fixture-inherit-C', old='fixture-expired-D')
assert len({len(v) for v in credentials.values()}) == 1
results, controls = {}, {}

def token_row(metadata):
    return next(row for row in metadata['environment'] if row['name'] == 'W2C_TOKEN')

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    probe = root / 'child.py'
    probe.write_text("""import hashlib,json,os,sys,time
names={'credential':'W2C_TOKEN','cluster':'CLUSTER','tls':'W2C_TLS_DIR','private':'PYTHONPATH'}
doc={label:{'present':key in os.environ,'length':len(os.environ[key]) if key in os.environ else None,'sha256':hashlib.sha256(os.environ[key].encode()).hexdigest() if key in os.environ else None} for label,key in names.items()}
print(('200 ' if sys.argv[1]=='move' else '')+json.dumps(doc),flush=True)
if sys.argv[1]=='delay':time.sleep(.4)
""")
    config = root / 'config.json'; config.write_text(json.dumps({'parts': {}, 'specs': os.environ['CAMMETA_SPECS']}))
    output = root / 'report.json'
    command = shlex.quote(sys.executable) + ' -I -B ' + shlex.quote(str(probe))
    supplied = {'W2C_TOKEN': credentials['inherited'], 'PYTHONPATH': 'fixture-private-import'}
    cluster_env = {'CLUSTER': 'm1', 'W2C_TOKEN': credentials['cluster'], 'W2C_TLS_DIR': 'fixture-tls-path'}
    records = []

    def engine(args):
        registry = ds.current()
        for label in ('cached', 'fresh', 'expired_refused', 'no_person', 'fresh_refused', 'signer_error'):
            directory = root / label; directory.mkdir()
            run = m11stand.Run(SimpleNamespace(cwd=str(root)), label); run.secrets = registry
            run.person = ('alice', 'fixture-password')
            run.token, run.until = credentials['current'], float('inf')
            calls = []
            marker = TransportError('fixture signer unavailable')
            if label in ('fresh', 'fresh_refused', 'signer_error'):
                run.token, run.until = None, 0
            elif label == 'expired_refused':
                run.token, run.until = credentials['old'], 0
            elif label == 'no_person':
                run.person = None
            def login(*args):
                calls.append(args[:3])
                if label == 'signer_error':
                    raise marker
                if label in ('fresh_refused', 'expired_refused'):
                    return 503, {'error': 'unavailable'}, {}
                return 200, {'token': credentials['current'], 'until': 10**15}, {}
            run.b = SimpleNamespace(clusters={'m1': SimpleNamespace(workdir=str(directory), env=dict(cluster_env), port=1234)},
                recovery='fixture-recovery', private_copy=lambda p: p, recovery_record=lambda *a, **k: None,
                url=lambda p: 'http://fixture.invalid', ac=lambda c: SimpleNamespace(move=command + ' move'),
                proxies={'hold': SimpleNamespace(port=2345)}, http=login)
            with patch.dict(os.environ, supplied, clear=True):
                try:
                    why = run.move('m1', '', '200 {"credential":{"present":"@any"}}')
                except TransportError as error:
                    assert label == 'signer_error' and error is marker
                    why = None
            meta = run.last_command
            if label == 'signer_error':
                assert not meta['started'] and (directory / meta['stdout_file']).read_bytes() == b''
                controls['signer_error_identity_preserved'] = True
                controls['not_started_has_no_present_overlay'] = all(not row['present'] for row in meta['environment'])
                child = None
            else:
                assert why == []
                child = json.loads((directory / meta['stdout_file']).read_text().partition(' ')[2])
                row = token_row(meta)
                expected = credentials['old'] if label == 'expired_refused' else credentials['current']
                should_receive = label in ('cached', 'fresh', 'expired_refused')
                if changed:
                    assert child['credential']['present'] is should_receive
                    assert child['credential']['sha256'] == (digest(expected) if should_receive else None)
                    assert row['present'] is should_receive
                    assert row['length'] == child['credential']['length']
                else:
                    assert not child['credential']['present']
                assert not child['private']['present']
            assert len(calls) == {'cached': 0, 'fresh': 1, 'expired_refused': 2, 'no_person': 0, 'fresh_refused': 1, 'signer_error': 1}[label]
            results[label] = dict(child=child, metadata=meta, login_calls=len(calls))
            records.append((directory / meta['metadata_file'], child))
            registry.evidence.add(directory)

        # A normal CLI and a command-vector must not inherit the person's credential.
        plain = root / 'plain'; plain.mkdir()
        with patch.dict(os.environ, supplied, clear=True):
            p, meta = cli.run(plain, 'join', secrets=registry, code_prefix=False,
                environment=cli.environment({**supplied, **cluster_env}, cluster_env),
                args=[sys.executable, '-I', '-B', str(probe), 'plain'], env={**supplied, **cluster_env}, capture_output=True)
            vector = m11stand.Run(SimpleNamespace(cwd=str(root), view=command + ' vector', json=str(plain / 'vector.json')), 'vector')
            vector.secrets = registry
            why, _ = vector.run_vector('view', str(root / 'unused-input'), '@exit 0')
            assert why == []
        child = json.loads(p.stdout)
        assert not child['credential']['present'] and not child['private']['present']
        results['join'] = dict(child=child, metadata=meta)
        records.append((plain / meta['metadata_file'], child))
        vector_meta = vector.last_command
        controls['vector_post_filter_presence'] = token_row(vector_meta)['present'] is False
        results['vector'] = vector_meta
        registry.evidence.add(plain)

        # Native timeout after the bridge has observed the filtered Popen mapping.
        try:
            cli.run(plain, 'timed', secrets=registry, code_prefix=False,
                environment=cli.environment(supplied, supplied), args=[sys.executable, '-I', '-B', str(probe), 'delay'],
                env=supplied, capture_output=True, timeout=.2)
            raise AssertionError('timeout not raised')
        except subprocess.TimeoutExpired:
            meta = json.loads((plain / 'timed-1.cli.json').read_text())
            assert meta['started'] and meta['exit_code'] is None
            controls['native_timeout_post_filter_presence'] = token_row(meta)['present'] is False

        # A daemon uses a plain role environment and reports exactly what the child received.
        agent = root / 'agent'; agent.mkdir()
        st = stand.Stand.__new__(stand.Stand)
        st.workdir, st.root, st.env, st.agent_tokens = str(agent), 'testsub', dict(cluster_env), str(root / 'tokens')
        st.a, st.procs, st.process_records = SimpleNamespace(cwd=str(root)), [], {}
        st.platform_env = lambda *a, **k: {'W2C_TLS_DIR': 'fixture-tls-path'}
        with patch.dict(os.environ, supplied, clear=True):
            proc, log = st._popen('agent', 'agent#1', command + ' plain')
        assert proc.wait(timeout=10) == 0
        child = json.loads(Path(log).read_text()); assert not child['credential']['present']
        st._write_process_exits()
        record = json.loads((agent / 'process-exits.json').read_text())['processes'][0]
        if changed:
            assert token_row(record)['present'] is False
            results['agent'] = dict(child=child, record=record)
        registry.evidence.add(agent)
        output.write_text(json.dumps({'green': True})); return 0

    with patch.object(c_store, 'arguments', return_value=('extra', [])), \
         patch.dict(sys.modules, {'extra': SimpleNamespace(main=engine)}), \
         patch.dict(os.environ), contextlib.redirect_stderr(io.StringIO()):
        code = c_store.main(['--config', str(config), '--driver', 'store-extra', '--json', str(output)])
    assert code == 0, output.read_text()
    for path, child in records:
        meta = json.loads(path.read_text()); assert cli.valid_metadata(meta)
        if changed and child is not None:
            assert token_row(meta)['present'] == child['credential']['present']
            assert token_row(meta)['length'] == child['credential']['length']
        for value in (*credentials.values(), 'fixture-password', 'fixture-private-import', 'fixture-tls-path'):
            assert value not in path.read_text()
    controls['metadata_matches_after_finalize'] = changed
    controls['same_length_current_credential_reaches_move'] = changed
    controls['other_roles_have_no_credential'] = True

    # Without c_store, supplied is the actual environment; no filter is claimed.
    direct = root / 'direct'; direct.mkdir()
    p, meta = cli.run(direct, 'join', secrets=ds.Secrets(), code_prefix=False,
        environment=cli.environment(supplied), args=[sys.executable, '-I', '-B', str(probe), 'plain'],
        env=supplied, capture_output=True)
    assert json.loads(p.stdout)['credential']['sha256'] == digest(credentials['inherited'])
    assert token_row(meta)['present']
    controls['direct_checker_observes_exact_supplied_env'] = True

Path(sys.argv[2]).write_text(json.dumps(dict(changed=changed, controls=controls, cases=results), indent=2) + '\n')
print(json.dumps(dict(changed=changed, controls=controls)))
if changed:
    assert all(controls.values())
