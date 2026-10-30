"""Independent argv/provenance and native proxy controls. CT 103 only, no SUT."""
import contextlib
import io
import json
import os
from pathlib import Path
import shlex
import socket
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
from unittest.mock import patch


def controls(runtime, specs, out):
    sys.path.insert(0, str(runtime / 'runner'))
    import c_execute
    import c_store
    import c_targets
    import store_audit
    from m11stand import Proxy
    result = {}
    with tempfile.TemporaryDirectory(prefix='rights-review-') as directory:
        root = Path(directory)
        observer = root / 'observe.py'
        observer.write_text('import json,pathlib,sys\npathlib.Path(sys.argv[1]).write_text(json.dumps(sys.argv[2:]))\n')
        for variant, flag in (('separate', '-rights '+shlex.quote('/prelude rights')),
                              ('equal', shlex.quote('-rights=/prelude rights'))):
            prelude, observed = root / (variant+'.prelude'), root / (variant+'.argv')
            # The actual final command has no -rights argv flag. Its rights source is implicit.
            command = ('printf "%s\\n" '+flag+' > '+shlex.quote(str(prelude))+' && exec '
                       + shlex.join([sys.executable, '-I', '-B', str(observer), str(observed),
                                     '--implicit-rights', '/actual rights']))
            subprocess.run(command, shell=True, check=True, timeout=5)
            original_argv, original_prelude = json.loads(observed.read_text()), prelude.read_text()
            reason = store_audit.scenario_reason(['@rights store none'], command, None)
            attempts = {}
            for name, value in (('none', None), ('file', '/replacement rights')):
                try:
                    rewritten = store_audit.rights_command(command, value)
                except store_audit.NotExecuted as error:
                    attempts[name] = dict(safety_pass=True, reason=str(error))
                else:
                    subprocess.run(rewritten, shell=True, check=True, timeout=5)
                    attempts[name] = dict(safety_pass=False,
                                          actual_argv_unchanged=json.loads(observed.read_text()) == original_argv,
                                          unrelated_prelude_changed=prelude.read_text() != original_prelude,
                                          actual_argv=json.loads(observed.read_text()), rewritten=rewritten)
            result['rights_prelude_'+variant] = dict(safety_pass=bool(reason) and all(a['safety_pass'] for a in attempts.values()),
                                                     scenario_reason=reason, attempts=attempts)

        # A real bridge invocation with only a legitimately unexecuted scenario: no process is launched.
        # Its raw engine report is valid against the capability plan; exported bytes must stay compatible.
        micro = root / 'specs'; acc = micro / 'Platform/01-store/acceptance/2'; acc.mkdir(parents=True)
        (micro / 'Source/tests/testdata').mkdir(parents=True)
        (micro / 'Platform/02-installer/acceptance/5').mkdir(parents=True)
        normative = c_targets.table(specs / 'Platform/01-store/acceptance/2/scenarios.tsv')[1:]
        rows = [c for _, c in normative if c[0] == '13-rights-file']
        assert len(rows) == 7
        (acc / 'scenarios.tsv').write_text('scenario\tstep\trequest\texpect\n'+'\n'.join('\t'.join(c) for c in rows)+'\n')
        profile = dict(cwd=str(root), keys=dict(role_header='X-Own-Role'), stand={'store': 'unused --implicit-rights'})
        reason = store_audit.scenario_reason([c[2] for c in rows], profile['stand']['store'], None)
        assert reason
        config, report_file = root / 'config.json', root / 'bridge.json'
        config.write_text(json.dumps(dict(specs=str(micro), parts={'01-store': profile})))
        with patch.dict(os.environ), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = c_store.main(['--driver', 'store-rights', '--config', str(config), '--json', str(report_file)])
        exported = json.loads(report_file.read_text())
        (out / 'bridge-report.json').write_text(json.dumps(exported, ensure_ascii=False, indent=2)+'\n')
        target = dict(driver='store-rights', inputs=[c_targets.source(acc / 'scenarios.tsv', micro)],
                      not_executed_scenarios={'13-rights-file': reason})
        covered = c_execute.coverage(target, exported)
        assert code == 1 and exported['green'] is False and exported['classification'] == 'stand'
        assert exported['total_steps'] == exported['passed_steps'] == 0
        assert all(r['ok'] is None and r['not_executed'] is True for r in exported['scenarios']['13-rights-file'])
        result['exported_skip_coverage'] = dict(safety_pass=not covered['errors'], bridge_code=code,
                                               expected_reason=reason, exported_skip=exported['not_executed_scenarios'], coverage=covered)

        listener = socket.socket(); listener.bind(('127.0.0.1', 0)); listener.listen(8); listener.settimeout(.05)
        stopped, connections, errors = threading.Event(), [], []
        def serve_connection(conn):
            with conn:
                try:
                    while data := conn.recv(8192): conn.sendall(data)
                except OSError: pass
        def serve():
            while not stopped.is_set():
                try: conn, _ = listener.accept()
                except socket.timeout: continue
                except OSError: return
                conn.settimeout(3); connections.append(conn)
                threading.Thread(target=serve_connection, args=(conn,), daemon=True).start()
        thread = threading.Thread(target=serve, daemon=True); thread.start()
        proxy = Proxy(listener.getsockname()[1], capture=False)
        remembered = []
        proxy._remember = lambda *args: remembered.append(args)
        def connect(port):
            sock = socket.create_connection(('127.0.0.1', port), timeout=2); sock.settimeout(2); return sock
        def receive(sock, length):
            got = b''
            while len(got) < length:
                part = sock.recv(length-len(got))
                if not part: break
                got += part
            return got
        def closed(sock):
            try: return sock.recv(1) == b''
            except ConnectionResetError: return True
        try:
            payload = b'own opaque data\x00\xff'*5000
            with connect(proxy.port) as first:
                address = first.getsockname(); first.sendall(payload)
                echoed = receive(first, len(payload)) == payload
                proxy.set_cut(True); old_closed = closed(first)
            with connect(proxy.port) as cut: new_closed = closed(cut)
            with connect(listener.getsockname()[1]) as direct:
                direct.sendall(b'api/direct unchanged'); direct_ok = receive(direct, 20) == b'api/direct unchanged'
            proxy.set_cut(False)
            with connect(proxy.port) as mend:
                mend.sendall(b'mend'); mend_ok = receive(mend, 4) == b'mend'
            snapshot = proxy.snapshot(address)
            byte_counts = {e['direction']:e['bytes'] for e in snapshot.get('events', []) if 'bytes' in e}
            # Thread completion is bounded by the socket deadline; wait only on our own events.
            import time
            deadline = time.monotonic()+3
            while len(byte_counts) < 2 and time.monotonic() < deadline:
                time.sleep(.01); snapshot = proxy.snapshot(address)
                byte_counts = {e['direction']:e['bytes'] for e in snapshot.get('events', []) if 'bytes' in e}
            result['opaque_proxy'] = dict(safety_pass=all((echoed,old_closed,new_closed,direct_ok,mend_ok))
                                         and not remembered and len(byte_counts) == 2
                                         and all(v == len(payload) for v in byte_counts.values()),
                                         echoed=echoed,old_closed=old_closed,new_closed=new_closed,direct_ok=direct_ok,
                                         mend_ok=mend_ok,remember_calls=len(remembered),bytes=byte_counts,payload_length=len(payload))
        finally:
            proxy.close(); stopped.set(); listener.close(); thread.join(3)
            for conn in connections: conn.close()
            assert not thread.is_alive() and not errors
    (out / 'controls.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    return result


if __name__ == '__main__':
    print(json.dumps(controls(Path(sys.argv[1]), Path(sys.argv[2]), Path(os.environ['CHECK_OUT'])), ensure_ascii=False))
