"""Independent opaque-stream and pause-guard controls; run only through CT103."""
import json
import os
from pathlib import Path
import signal
import socket
import sys
import tempfile
import threading
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(sys.argv[1]) / 'runner'))
import harness
import m11stand
import scenario_control

OUT = Path(os.environ['CHECK_OUT'])


def transfer(use_proxy, half_close, size):
    """A native Unix HTTP peer accepts one request, sends one response and closes."""
    with tempfile.TemporaryDirectory(prefix='rv-unix-') as directory:
        root = Path(directory)
        target, route = root / 'real.sock', root / 'proxy.sock'
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(target)); server.listen(1); server.settimeout(2)
        body = b'x' * size
        state = dict(request_bytes=0, response_bytes=0, server_error=None)

        def serve():
            try:
                conn, _ = server.accept()
                with conn:
                    conn.settimeout(2)
                    request = b''
                    while b'\r\n\r\n' not in request:
                        part = conn.recv(65536)
                        if not part: break
                        request += part
                    state['request_bytes'] = len(request)
                    if not request: return
                    wire = (b'HTTP/1.1 200 OK\r\nContent-Type: application/octet-stream\r\n'
                            b'Connection: close\r\nContent-Length: ' + str(size).encode() + b'\r\n\r\n' + body)
                    conn.sendall(wire)
                    state['response_bytes'] = len(wire)
            except OSError as error:
                state['server_error'] = type(error).__name__

        thread = threading.Thread(target=serve, daemon=True); thread.start()
        proxy = m11stand.Proxy(target, capture=False, unix=route) if use_proxy else None
        door = harness.HttpDoor('unix:' + str(route if use_proxy else target), timeout=2)
        reply, error = None, None
        try:
            if half_close:
                reply = door.raw(b'GET /v1/status HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n',
                                 timeout=2, half_close=True)
            else:
                reply = door.request('GET', '/v1/status')
        except harness.TransportError as caught:
            error = str(caught)
        finally:
            if proxy: proxy.close()
            server.close(); thread.join(timeout=3)
        return dict(ok=reply is not None and reply.status == 200 and reply.body == body,
                    status=reply.status if reply else None, body_bytes=len(reply.body) if reply else None,
                    error=error, **state)


controls = {}
for name, half_close, size in (('http_close_small', False, 1024),
                               ('http_close_large', False, 200000),
                               ('client_half_close', True, 1024)):
    direct = [transfer(False, half_close, size) for _ in range(3)]
    proxied = [transfer(True, half_close, size) for _ in range(3)]
    controls[name] = dict(direct=direct, proxied=proxied,
                          safety_pass=all(case['ok'] for case in direct + proxied))


class Timer:
    def __init__(self, *args, **kwargs): pass
    def start(self): pass
    def cancel(self): pass


signals = []
proc = SimpleNamespace(pid=123456, poll=lambda: None)
with patch.object(scenario_control.threading, 'Timer', Timer), \
     patch.object(scenario_control.c_process, 'send_group', side_effect=lambda pid, sig: signals.append(sig) or []):
    guard = scenario_control.Freezes()
    assert guard.freeze(proc, 'worker') == []
    first = guard.records[-1]
    guard.bind(dict(ok=True, why=[]), '@freeze worker')
    assert guard.thaw(proc) == []
    assert guard.freeze(proc, 'worker') == []
    second = guard.records[-1]
    second_row = dict(ok=True, why=[])
    guard.bind(second_row, '@freeze worker')
    count = len(signals)
    guard._expire(first)
    stale_safe = len(signals) == count and guard.active[proc.pid] is second
    assert guard.thaw(proc) == []
    guard.close()
    controls['stale_watchdog'] = dict(safety_pass=stale_safe and not guard.failures() and second_row['ok'],
                                       signals=[int(value) for value in signals])
    guard = scenario_control.Freezes()
    assert guard.freeze(proc, 'worker') == []
    row = dict(ok=True, why=[])
    guard.bind(row, '@freeze worker')
    guard.close()
    controls['forgotten_pause'] = dict(safety_pass=not row['ok'] and row['classification'] == 'data'
                                      and row['why'] == [dict(classification='data', reason='freeze_not_thawed')]
                                      and not guard.active, row=row)

(OUT / 'controls.json').write_text(json.dumps(controls, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({name: row['safety_pass'] for name, row in controls.items()}), flush=True)
