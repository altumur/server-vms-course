"""Independent runner controls, CT 103 only. No storage implementation or Raft model."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch


def wire(path, body=b'{}', code=200, delay=0):
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(path)); listener.listen(5); listener.settimeout(4)
    errors = []
    def serve():
        try:
            conn, _ = listener.accept()
            with conn:
                conn.settimeout(4)
                request = b''
                while b'\r\n\r\n' not in request:
                    request += conn.recv(65536)
                headers, payload = request.split(b'\r\n\r\n', 1)
                length = next((int(line.split(b':', 1)[1]) for line in headers.split(b'\r\n')[1:]
                               if line.lower().startswith(b'content-length:')), 0)
                while len(payload) < length:
                    payload += conn.recv(65536)
                time.sleep(delay)
                conn.sendall(b'HTTP/1.1 ' + str(code).encode() + b' Reply\r\nContent-Type: application/json\r\nContent-Length: '
                             + str(len(body)).encode() + b'\r\nConnection: close\r\n\r\n' + body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # The short runner deadline can close before this legal reply.
        except BaseException as error:
            errors.append(repr(error))
        finally:
            listener.close()
    thread = threading.Thread(target=serve, daemon=True); thread.start()
    return thread, errors


def controls(runtime, specs, out):
    sys.path.insert(0, str(runtime / 'runner'))
    import c_process
    import c_targets
    import forms
    import harness
    import store_group
    acc = specs / 'Platform/01-store/acceptance/3'
    result = {}
    with tempfile.TemporaryDirectory(prefix='sg-review-', dir='/tmp') as directory:
        root = Path(directory)
        evidence = root / 'evidence'; evidence.mkdir()
        profile = dict(cwd=str(root), keys=dict(store_build='raft', role_header='X-Role'), stand={})
        group = store_group.Group(profile, acc, evidence)
        # Only the HTTP routing is under test here. No certificates/consensus are faked.
        group.kits = SimpleNamespace(directories={'s1': str(root)}, close=lambda: None)
        run = group.directory('s1') / 'run'; run.mkdir()
        try:
            thread, errors = wire(run / 'console.sock')
            try:
                code, _ = group.request('store@s1 GET /v1/get?key=testsub/next_id')
                role_ok = code == 200
            except (OSError, harness.TransportError):
                role_ok = False
                # Use the server for the positive @as control without another fixture.
            code, _ = group.request('@as console store@s1 GET /v1/get?key=testsub/next_id') if not role_ok else (200, b'')
            thread.join(5); assert not errors and not thread.is_alive(), errors
            result['chapter_role'] = dict(safety_pass=role_ok, declared_default='console', actual_default='acc' if not role_ok else 'console',
                                          explicit_as_works=code == 200)
            (run / 'console.sock').unlink()

            thread, errors = wire(run / 'console.sock', delay=2.25)
            began = time.monotonic()
            try:
                code, _ = group.request('store@s1 GET /v1/get?key=testsub/next_id')
                waited = code == 200
            except (OSError, harness.TransportError):
                waited = False
            elapsed = time.monotonic() - began
            thread.join(5); assert not errors and not thread.is_alive(), errors
            result['door_budget'] = dict(safety_pass=waited, response_delay=2.25, elapsed=round(elapsed, 3))
        finally:
            group.close()

        # Read literal published requests/expectations; never loosen their JSON predicates.
        rows = c_targets.table(acc / 'scenarios.tsv')[1:]
        chosen = {(c[0], c[1]): (c[2], c[3]) for _, c in rows}
        setup = chosen[('07-group-size', '1')]
        refused = chosen[('07-group-size', '6')]
        forbidden = chosen[('17-group-members', '10')]
        local_specs = root / 'specs'; local_acc = local_specs / 'Platform/01-store/acceptance/3'
        local_acc.mkdir(parents=True)
        # Schemas are still the exact full export via CAMMETA_SPECS; only scenario selection is a microfixture.
        for name, actual, selected, body in (
                ('admin_refused', 409, refused, {'kind': 'refused'}),
                ('admin_forbidden', 403, forbidden, None)):
            request, expect = selected
            (local_acc / 'scenarios.tsv').write_text('scenario\tstep\trequest\texpect\n'
                + '07-control\t1\t' + setup[0] + '\t' + setup[1] + '\n'
                + '07-control\t2\t' + request + '\t' + expect + '\n')
            raw = json.dumps(body).encode() if body is not None else b''
            class Fixture:
                def __init__(self, *args): pass
                def setup(self, *args): pass
                def request(self, request): return actual, raw
                def close(self): return []
            report = store_group.run(dict(specs=str(local_specs), parts={'01-store': profile}), root / (name+'.json'), factory=Fixture)
            schema_errors = []
            forms.check('P/01.3', 'store', 'POST', '/v1/join', actual, body if body is not None else {}, schema_errors)
            assert schema_errors, 'control payload must violate its published response schema'
            result[name] = dict(safety_pass=not report['green'], runner_green=report['green'],
                                published_request=request, published_expect=expect, schema_errors=[str(v) for v in schema_errors])

        # A shell leader receives TERM and exits while its owned daemon ignores TERM.
        # Stopping must observe the child, not turn a KILL cleanup into a passing TERM step.
        child = root / 'child.py'; ready = root / 'child.ready'
        child.write_text('import os,signal,sys,time\n'
                         'signal.signal(signal.SIGTERM,signal.SIG_IGN)\n'
                         'open(sys.argv[1],"w").write(str(os.getpid()))\n'
                         'while True:time.sleep(0.05)\n')
        command = shlex.join([sys.executable, '-I', '-B', str(child), str(ready)]) + ' & wait'
        proc = subprocess.Popen(command, shell=True, start_new_session=True, stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            limit = time.monotonic()+4
            while not ready.exists() and time.monotonic() < limit: time.sleep(.02)
            assert ready.exists(), 'fixture did not start'
            pid = int(ready.read_text()); os.kill(pid, 0)
            group = store_group.Group(profile, acc, evidence)
            group.members['s1'] = dict(proc=proc, command=command)
            # Observe actual signal delivery without replacing the stop algorithm.
            original = c_process.send_group; signals = []
            def observe(pgid, sig):
                signals.append(int(sig)); return original(pgid, sig)
            with patch.object(c_process, 'send_group', side_effect=observe):
                why = group.stop('s1', signal.SIGTERM)
            result['term_shell_child'] = dict(safety_pass=bool(why), why=why,
                                              cleanup_signals=signals, cleanup_used_sigkill=int(signal.SIGKILL) in signals,
                                              shell_exit=proc.returncode)
            group.close()
        finally:
            c_process.finish(proc, [proc.pid], grace=.1, kill_wait=2)
    (out / 'controls.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    return result


if __name__ == '__main__':
    print(json.dumps(controls(Path(sys.argv[1]), Path(sys.argv[2]), Path(os.environ['CHECK_OUT'])), ensure_ascii=False))
