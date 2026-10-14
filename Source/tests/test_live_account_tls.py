"""C5 actual gateway TLS: role proof, independent human gate, and return hop through the local console."""
import contextlib
import http.client
import json
import select
import ssl
import threading
from http.server import BaseHTTPRequestHandler

from tests.test_console_gate import Tokens
from tests.test_live_accounts import ring
from tests.test_role_client import kits
from tests.vmsconftest import Box
from vms.liveworker import LiveWorker
from w2cplatform import tls
from w2cplatform.console import door_server


@contextlib.contextmanager
def runtime(*, refusal=None):
    """Real CA/CRL/mTLS; the existing Tokens fixture isolates the gateway's independent human gate."""
    with kits() as ca:
        ca.issue('liveworker')
        calls = []
        class Console(BaseHTTPRequestHandler):
            def do_GET(self):
                tls.role_certificate(self.connection.getpeercert(), 'liveworker')
                calls.append((self.path, self.headers.get('Authorization')))
                raw = json.dumps({'users': [{'name': 'anna'}]}).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            def log_message(self, *args): pass
        console = door_server(('127.0.0.1', 0), Console,
                              tls_context=tls.ServerContext(ca.root, role='console'))
        console_thread = threading.Thread(target=console.serve_forever, daemon=True)
        console_thread.start()
        box = Box()
        gateway = LiveWorker('g-1', box.vars, box.objects, clock=box.clock, wall=box.wall,
                             resource_root=box.resource_root, env={
                                 'CONSOLE_URL': f'https://localhost:{console.server_port}',
                                 'W2C_TLS_DIR': ca.root, 'W2C_ROLE': 'liveworker'})
        gateway.sealer = gateway.account_doors.accounts.sealer = ring('local')
        gateway.account_gate.impl = Tokens({'anna': [('admin', None, [])], 'reader': [('view', None, [])]})
        if refusal is not None:
            base = gateway.handler()
            class HeldRefusal(base):
                def _send(self, status, body, raw=False):
                    if status == 403:
                        # The real gate has denied the headers. Put a second TLS record in the kernel before closing;
                        # never read that unauthorized body merely to make an HTTP error arrive intact.
                        refusal['headers_seen'].set()
                        if not refusal['body_sent'].wait(2):
                            refusal['errors'].append('client did not send the held body')
                        elif not select.select([self.connection], [], [], 2)[0]:
                            refusal['errors'].append('request body was not pending at refusal')
                    return super()._send(status, body, raw)
            gateway.handler = lambda: HeldRefusal
        srv = gateway.serve('127.0.0.1', 0)
        try:
            yield ca, box, gateway, srv, calls
        finally:
            srv.shutdown()
            srv.server_close()
            console.shutdown()
            console.server_close()
            console_thread.join(2)


def request(ca, srv, method, path, *, role='console', token='anna', body=None):
    context = tls.Bundle(ca.root, role).client_context() if role else ssl.create_default_context(cafile=ca.root+'/ca.pem')
    conn = http.client.HTTPSConnection('localhost', srv.server_port, context=context, timeout=3)
    headers = {'X-User': 'forged', 'X-Operator': 'forged'}
    if token:
        headers['Authorization'] = 'Bearer '+token
    raw = None if body is None else json.dumps(body).encode()
    try:
        conn.request(method, path, raw, headers)
        response = conn.getresponse()
        data = response.read()
        return response.status, json.loads(data) if response.getheader('Content-Type') == 'application/json' else data
    finally:
        conn.close()


def test_tls_gateway_requires_console_and_an_independent_human_and_returns_the_original_token():
    with runtime() as (ca, box, gateway, srv, calls):
        assert gateway.url == f'https://localhost:{srv.server_port}'
        assert request(ca, srv, 'GET', '/live/accounts', role=None)[0] == 403
        assert request(ca, srv, 'GET', '/live/accounts', role='testsubworker')[0] == 403
        assert request(ca, srv, 'GET', '/live/accounts', token='')[0] == 401
        assert request(ca, srv, 'GET', '/live/accounts', token='unknown')[0] == 401
        status, created = request(ca, srv, 'POST', '/live/accounts', body={'name': 'wall'})
        assert status == 200 and set(created) == {'account', 'password'}
        assert calls == [('/domain/users', 'Bearer anna')]
        stored = box.vars.get('live/accounts/wall')[0]
        assert json.loads(stored['doc'])['by'] == 'anna'
        assert created['password'] not in json.dumps(stored)
        assert request(ca, srv, 'GET', '/live/accounts', token='reader')[1]['accounts'][0]['name'] == 'wall'
        assert request(ca, srv, 'GET', '/metrics', role=None, token='')[0] == 200


def test_tls_gateway_refuses_missing_human_without_waiting_for_a_declared_body():
    with runtime() as (ca, box, gateway, srv, calls):
        conn = http.client.HTTPSConnection('localhost', srv.server_port,
                                         context=tls.Bundle(ca.root, 'console').client_context(), timeout=2)
        try:
            conn.putrequest('POST', '/live/accounts')
            conn.putheader('Content-Length', '1048576')
            conn.endheaders()  # no request body is sent: a human proof must be checked first
            response = conn.getresponse()
            assert response.status == 401 and json.loads(response.read())['error'] == 'denied'
        finally:
            conn.close()
        assert not calls and box.vars.list('live/accounts/') == []


def test_tls_early_refusal_preserves_its_complete_json_even_with_an_unread_body_record():
    refused = {'headers_seen': threading.Event(), 'body_sent': threading.Event(), 'errors': []}
    with runtime(refusal=refused) as (ca, box, gateway, srv, calls):
        failures = []
        # Each iteration places the body in a separate TLS record after the real gate has denied its headers.
        # Repeated connections expose the close-vs-reply loss that a single favorable packet schedule can hide.
        for attempt in range(50):
            refused['headers_seen'].clear()
            refused['body_sent'].clear()
            conn = http.client.HTTPSConnection('localhost', srv.server_port,
                                             context=tls.Bundle(ca.root, 'console').client_context(), timeout=3)
            raw = b'{"disabled":true}'
            try:
                conn.putrequest('PUT', '/live/accounts/wall')
                conn.putheader('Authorization', 'Bearer reader')
                conn.putheader('Content-Length', str(len(raw)))
                conn.endheaders()
                assert refused['headers_seen'].wait(2), 'gateway did not check authorization from headers'
                conn.send(raw)
                refused['body_sent'].set()
                response = conn.getresponse()
                assert response.status == 403
                assert json.loads(response.read()) == {'error': 'denied', 'detail': 'reader may not admin here'}
            except (OSError, http.client.HTTPException, ValueError) as error:
                failures.append((attempt, type(error).__name__, str(error)))
            finally:
                refused['body_sent'].set()
                conn.close()
        assert refused['errors'] == []
        assert failures == [], failures
        assert not calls and box.vars.list('live/accounts/') == []
