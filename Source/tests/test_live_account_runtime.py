"""C5 real gateway HTTP: authenticate before body; local console receives the human token."""
import contextlib
import http.client
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from tests.test_console_gate import Tokens
from tests.test_live_accounts import ring
from tests.vmsconftest import Box
from vms.live_accounts import ACCOUNTS
from vms.liveworker import LiveWorker


@contextlib.contextmanager
def runtime():
    calls = []
    class Console(BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append((self.path, self.headers.get('Authorization')))
            raw = json.dumps({'users': [{'name': 'anna'}]}).encode()
            self.send_response(200)
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        def log_message(self, *args):
            pass
    console = ThreadingHTTPServer(('127.0.0.1', 0), Console)
    threading.Thread(target=console.serve_forever, daemon=True).start()
    box = Box()
    gateway = LiveWorker('g-1', box.vars, box.objects, clock=box.clock, wall=box.wall,
                         resource_root=box.resource_root, env={
                             'CONSOLE_URL': f'http://127.0.0.1:{console.server_port}',
                             'W2C_TLS_DIR': box.resource_root+'/no-kit'})
    gateway.sealer = gateway.account_doors.accounts.sealer = ring('local')
    gateway.account_gate.impl = Tokens({'anna': [('admin', None, [])], 'reader': [('view', None, [])]})
    srv = gateway.serve('127.0.0.1', 0)
    try:
        yield box, gateway, srv, calls
    finally:
        srv.shutdown(); srv.server_close()
        console.shutdown(); console.server_close()


def request(srv, method, path, body=None, token='anna', **headers):
    conn = http.client.HTTPConnection('127.0.0.1', srv.server_port, timeout=3)
    if token:
        headers['Authorization'] = 'Bearer '+token
    if body is not None:
        body = json.dumps(body).encode()
        headers['Content-Type'] = 'application/json'
    try:
        conn.request(method, path, body, headers)
        response = conn.getresponse()
        return response.status, json.loads(response.read())
    finally:
        conn.close()


def test_runtime_uses_original_person_through_local_console_and_never_header_identity():
    with runtime() as (box, gateway, srv, calls):
        status, created = request(srv, 'POST', '/live/accounts', {'name': 'wall'},
                                  **{'X-User': 'forged', 'X-Operator': 'forged'})
        assert status == 200 and set(created) == {'account', 'password'}
        assert calls == [('/domain/users', 'Bearer anna')]
        stored = box.vars.get(ACCOUNTS+'wall')[0]
        assert json.loads(stored['doc'])['by'] == 'anna'
        assert created['password'] not in json.dumps(stored)
        assert request(srv, 'GET', '/live/accounts', token='reader')[1]['accounts'][0]['name'] == 'wall'
        assert request(srv, 'PUT', '/live/accounts/wall', {'disabled': True}, token='reader')[0] == 403
        assert request(srv, 'PUT', '/live/accounts/wall', {'disabled': True}) == (200, {'account': 'wall', 'disabled': True})
        assert request(srv, 'POST', '/live/accounts', {'name': 'anna'})[0] == 409
        assert request(srv, 'GET', '/stream-clients')[0] == 404
        assert request(srv, 'GET', '/clients')[0] == 404


def test_runtime_refuses_missing_token_before_waiting_for_the_declared_body():
    with runtime() as (box, gateway, srv, calls):
        conn = http.client.HTTPConnection('127.0.0.1', srv.server_port, timeout=2)
        try:
            conn.putrequest('POST', '/live/accounts')
            conn.putheader('Content-Length', '1048576')
            conn.endheaders()  # no body ever sent: auth refusal must be immediate
            reply = conn.getresponse()
            assert reply.status == 401
            reply.read()
        finally:
            conn.close()
        assert not calls and box.vars.list(ACCOUNTS) == []
        assert request(srv, 'GET', '/live/accounts', token='unknown')[0] == 401
