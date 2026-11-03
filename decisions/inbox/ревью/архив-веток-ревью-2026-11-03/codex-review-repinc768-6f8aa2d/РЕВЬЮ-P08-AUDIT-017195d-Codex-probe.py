"""Native public process names and real preflight-report consumer; CT103 only."""
import contextlib
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(sys.argv[1]) / 'runner'))
import c_execute
import c_process
import c_store
import c_targets
import m11stand
import scenario_control
import stand

SPEC = Path(sys.argv[2])
OUT = Path(os.environ['CHECK_OUT'])
controls = {}


def paused(proc):
    members, error = c_process.group_members([proc.pid])
    assert error is None, error
    return bool(members[proc.pid]) and all(state.startswith('T') for _, state in members[proc.pid])


def settle(proc, want):
    deadline = time.monotonic() + .5
    while time.monotonic() < deadline:
        if paused(proc) is want: return True
        time.sleep(.01)
    return False


with tempfile.TemporaryDirectory(prefix='rv-p08-') as directory:
    root = Path(directory)
    st = stand.Stand.__new__(stand.Stand)
    st.workdir = str(root / 'cluster'); Path(st.workdir).mkdir()
    st.data = st.workdir; st.socket = str(root / 'admin.sock')
    st.procs = []; st.process_records = {}; st.worker_places = {}; st.exited = {}
    st.lock = threading.RLock(); st.grow_thread = None; st.closing = False
    st.freezes = scenario_control.Freezes(); st.store_proxies = {}
    st.a = SimpleNamespace(keep=True); st.diagnostic_secrets = None
    owned = []
    try:
        for role in ('domain-console', 'domain-console', 'domain'):
            proc = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(60)'], start_new_session=True,
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            owned.append(proc)
            # The exact (role,name) tuple used by Bench.start_domain/_popen.
            st.procs.append((role, role, proc)); st._process_record(proc)
        run = m11stand.Run(SimpleNamespace(), 'native-names')
        run.b = SimpleNamespace(clusters={'hold': st})
        aliases = {}
        for public, target in (('domainconsole', owned[1]), ('domainconsole#1', owned[0]), ('domainconsole#2', owned[1])):
            req = '@on hold @freeze ' + public
            preflight = m11stand.on_errors([(1, '1', req, 'ok')])
            frozen = run.directive(req, 'ok')
            stopped = settle(target, True)
            thawed = run.directive('@on hold @thaw ' + public, 'ok')
            resumed = settle(target, False)
            aliases[public] = dict(preflight=preflight, freeze_errors=frozen, stopped=stopped,
                                   thaw_errors=thawed, resumed=resumed)
            scenario_control.finish(st)
        controls['public_domainconsole'] = dict(safety_pass=all(not row['preflight'] and not row['freeze_errors']
                                                and row['stopped'] and not row['thaw_errors'] and row['resumed']
                                                for row in aliases.values()), cases=aliases,
                                                startup_names=[record['copy_name'] for record in st.process_records.values()])
        # Contrast: the internal registered name does resolve, and existing signal dispatch translates the public name.
        direct = run.directive('@on hold @freeze domain-console#1', 'ok')
        stopped = settle(owned[0], True)
        thawed = run.directive('@on hold @thaw domain-console#1', 'ok')
        resumed = settle(owned[0], False)
        calls = []
        with patch.object(st, 'signal', side_effect=lambda target, sig: calls.append(target) or True):
            signal_errors = run.directive('@on hold @sigkill domainconsole#1', 'ok')
        controls['internal_name_and_existing_signal'] = dict(safety_pass=not direct and stopped and not thawed
                                                              and resumed and not signal_errors and calls == ['domain-console#1'],
                                                              mapped_targets=calls)
        row = dict(step='1', line=1, ok=True, why=[], got=None)
        why = run.directive('@on hold @freeze domain#1', 'ok')
        row.update(ok=not why, why=why)
        m11stand.bind_control(run, '@on hold @freeze domain#1', row)
        assert settle(owned[2], True)
        seen = []
        real_observe = st.observe_before_teardown
        def observe():
            seen.append(paused(owned[2])); real_observe()
        st.observe_before_teardown = observe
        bench_root = root / 'bench'; bench_root.mkdir()
        bench = SimpleNamespace(clusters={'hold': st}, proxies={}, sproxies={}, routes=None,
                                tls_client=None, secrets=None, root=str(bench_root))
        m11stand.Bench.close(bench)
        controls['native_domain_end'] = dict(safety_pass=bool(seen) and not any(seen) and not row['ok']
                                               and row.get('classification') == 'data'
                                               and row['why'] == [dict(classification='data', reason='freeze_not_thawed')],
                                               observed_paused=seen, row=row)
    finally:
        st.freezes.close()
        for proc in owned: c_process.finish(proc, [proc.pid], grace=.1, kill_wait=2)

    # Use the actual C bridge and domain main; reject before any stand/implementation can start.
    fixture = root / 'bad-chapter'; fixture.mkdir()
    (fixture / 'scenarios.tsv').write_text('scenario\tstep\trequest\texpect\nfixture\t1\t@on hold @pause domain#1\tok\n')
    parts = {owner: dict(cwd=str(root), keys={'role': 'acc'}, stand={}, adapters={})
             for owner in ('01-store', '02-installer', '03-worker', '04-controller', '05-resource', '06-console',
                           '08-domain', '09-agent', '10-domain-console')}
    keys = ('store', 'console', 'controller', 'worker', 'resource', 'manifest-put', 'rights', 'ring',
            'install-domain', 'first-admin', 'domain', 'agent', 'join', 'token-door', 'domain-console', 'move')
    for part in parts.values():
        part['stand'] = {key: 'NEVER-EXECUTE' for key in keys}
        part['stand'].update(agent='AGENT_TOKEN_DIR={agent_tokens} NEVER-EXECUTE',
                             worker='AGENT_TOKEN_DIR={agent_tokens} NEVER-EXECUTE',
                             **{'token-door': 'unix:{agent_tokens}/{role}.sock'})
    config, output = root / 'config.json', root / 'preflight.json'
    config.write_text(json.dumps(dict(specs=str(SPEC), parts=parts)))
    captured = io.StringIO()
    with patch.object(m11stand.specs, 'acceptance', return_value=str(fixture)), \
         patch.object(m11stand, 'Run', side_effect=AssertionError('preflight started a stand')) as factory, \
         contextlib.redirect_stdout(captured):
        code = c_store.main(['--driver', 'domain-10', '--config', str(config), '--json', str(output)])
    raw = json.loads(output.read_text())
    classified = c_execute.classification(raw, code, False)
    step = raw['scenarios']['fixture'][0]
    controls['preflight_classification'] = dict(safety_pass=code == 1 and classified == 'data' and not factory.called,
                                                 code=code, final_classification=classified,
                                                 report_classification=raw.get('classification'),
                                                 row_classification=step.get('classification'),
                                                 row_executed=step.get('executed'), stand_constructors=factory.call_count,
                                                 row_why=step['why'])
    (OUT / 'preflight-report.json').write_text(json.dumps(raw, ensure_ascii=False, indent=2) + '\n')
    (OUT / 'preflight-stdout.txt').write_text(captured.getvalue())

(OUT / 'controls.json').write_text(json.dumps(controls, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({name: case['safety_pass'] for name, case in controls.items()}), flush=True)
