"""Opaque HTTP refusal before the request body has been drained; CT103 only."""
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading

sys.path.insert(0, str(Path(sys.argv[1]) / 'runner'))
import harness
import m11stand


def exchange(proxied):
    with tempfile.TemporaryDirectory(prefix='rv-early-') as directory:
        root = Path(directory); target, route = root / 'real.sock', root / 'proxy.sock'
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(target)); server.listen(1); server.settimeout(3)
        seen = {}; body = b'{"kind":"toolarge","error":"body too large","limit":1024}'
        def serve():
            try:
                conn, _ = server.accept()
                with conn:
                    conn.settimeout(3); header = b''
                    while b'\r\n\r\n' not in header:
                        block = conn.recv(4096)
                        if not block: break
                        header += block
                    seen['request_bytes'] = len(header)
                    # A conforming door may reject the declared length without draining the body.
                    reply = b'HTTP/1.1 413 Payload Too Large\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: ' + str(len(body)).encode() + b'\r\n\r\n' + body
                    conn.sendall(reply)
                    seen['response_bytes'] = len(reply)
            except OSError as error: seen['server_error'] = type(error).__name__
        thread = threading.Thread(target=serve, daemon=True); thread.start()
        proxy = m11stand.Proxy(target, capture=False, unix=route) if proxied else None
        reply, error = None, None
        try:
            door = harness.HttpDoor('unix:' + str(route if proxied else target), timeout=3)
            reply = door.request('POST', '/v1/write', b'x' * 1048577)
        except harness.TransportError as caught: error = str(caught)
        finally:
            if proxy: proxy.close()
            server.close(); thread.join(4)
        return dict(ok=reply is not None and reply.status == 413 and reply.body == body,
                    status=reply.status if reply else None, error=error, **seen)


direct = [exchange(False) for _ in range(5)]
proxied = [exchange(True) for _ in range(5)]
result = dict(safety_pass=all(row['ok'] for row in direct + proxied), direct=direct, proxied=proxied)
(Path(os.environ['CHECK_OUT']) / 'early-refusal.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result), flush=True)
