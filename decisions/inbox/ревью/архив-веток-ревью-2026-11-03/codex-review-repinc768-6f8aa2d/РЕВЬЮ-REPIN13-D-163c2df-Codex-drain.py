"""Early response with bounded drain required by P/01.1 N2.1; CT103 only."""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tarfile
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parent
OUT = Path(os.environ['CHECK_OUT'])


def worker(runtime):
    sys.path.insert(0, str(runtime / 'runner'))
    import harness
    import m11stand
    def exchange(proxied):
        with tempfile.TemporaryDirectory(prefix='rv-drain-') as directory:
            root = Path(directory)
            target, route = root / 'real.sock', root / 'proxy.sock'
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind(str(target)); server.listen(1); server.settimeout(5)
            seen = {}
            body = b'{"kind":"toolarge","error":"body too large","limit":1024}'
            request_length = 1048577
            def serve():
                try:
                    conn, _ = server.accept()
                    with conn:
                        conn.settimeout(5); header = b''
                        while b'\r\n\r\n' not in header:
                            block = conn.recv(4096)
                            if not block: raise AssertionError('missing headers')
                            header += block
                        _, already = header.split(b'\r\n\r\n', 1)
                        reply = b'HTTP/1.1 413 Payload Too Large\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: ' + str(len(body)).encode() + b'\r\n\r\n' + body
                        conn.sendall(reply)
                        seen['response_bytes'] = len(reply)
                        # Declared drain limits: 2 MiB and 5 s; actual declared body fits.
                        drained = len(already); deadline = time.monotonic() + 5
                        while drained < min(request_length, 2 * 1024 * 1024):
                            conn.settimeout(max(.001, deadline - time.monotonic()))
                            block = conn.recv(min(65536, request_length - drained))
                            if not block:
                                seen['request_eof'] = True
                                break
                            drained += len(block)
                        seen['drained'] = drained
                except BaseException as error:
                    seen['server_error'] = repr(error)
            thread = threading.Thread(target=serve, daemon=True); thread.start()
            proxy = m11stand.Proxy(target, capture=False, unix=route) if proxied else None
            reply, error = None, None
            try:
                door = harness.HttpDoor('unix:' + str(route if proxied else target), timeout=5)
                reply = door.request('POST', '/v1/write', b'x' * request_length)
                thread.join(6)
            except harness.TransportError as caught: error = str(caught)
            finally:
                if proxy: proxy.close()
                server.close(); thread.join(6)
            return dict(ok=reply is not None and reply.status == 413 and reply.body == body
                        and (seen.get('drained') == request_length or seen.get('request_eof'))
                        and 'server_error' not in seen,
                        status=reply.status if reply else None, error=error, **seen)
    direct = [exchange(False) for _ in range(3)]
    proxied = [exchange(True) for _ in range(3)]
    result = dict(safety_pass=all(row['ok'] for row in direct + proxied), direct=direct, proxied=proxied)
    print(json.dumps(result), flush=True)
    assert result['safety_pass'], result


if len(sys.argv) > 1:
    worker(Path(sys.argv[1]))
else:
    commits = dict(old='50ce0b0bacc14eec60f384fef1aa38eb089b34d5', new='163c2df6e5708c6640ef48e18843e666884a6431')
    result = dict(SUT=0, drain_bytes=2097152, drain_seconds=5, request_bytes=1048577,
                  probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), controls={})
    with tempfile.TemporaryDirectory(prefix='rv-drain-check-') as directory:
        specs = Path(directory) / 'specs'; specs.mkdir()
        with tarfile.open(ROOT / 'specs.tar') as stream:
            assert stream.pax_headers['comment'] == '13a30dcbf6a17c7023b518c20bdae96a100058cd'
            stream.extractall(specs, filter='data')
        for label, archive in [('old', 'old-runtime.tar'), ('new', 'runtime.tar')]:
            target = Path(directory) / label; target.mkdir()
            with tarfile.open(ROOT / archive) as stream:
                assert stream.pax_headers['comment'] == commits[label]
                stream.extractall(target, filter='data')
            proc = subprocess.run([sys.executable, '-I', '-B', str(Path(__file__).resolve()), str(target)],
                                  env=dict(os.environ, CAMMETA_SPECS=str(specs), ONEOF_EXPORT=str(specs)),
                                  capture_output=True, text=True, timeout=60)
            (OUT / (label + '.txt')).write_text(proc.stdout + proc.stderr)
            assert proc.returncode == 0, proc.stderr
            result['controls'][label] = json.loads(proc.stdout)
    (OUT / 'drain-evidence.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)
