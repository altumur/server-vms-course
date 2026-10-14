"""C5's shared role kit and real HTTP/mTLS client, independent of any product subsystem."""
import contextlib
import os
import shutil
import ssl
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from w2cplatform import tls


def openssl(*args):
    subprocess.run(["openssl", *map(str, args)], check=True, capture_output=True, timeout=15)


class CA:
    def __init__(self, root):
        self.root = root
        os.makedirs(root, exist_ok=True)
        self.config = os.path.join(root, "openssl.cnf")
        with open(os.path.join(root, "index"), "w"):
            pass
        for name in ("serial", "crlnumber"):
            with open(os.path.join(root, name), "w") as f:
                f.write("1000\n")
        with open(self.config, "w") as f:
            f.write(f"[ca]\ndefault_ca=c\n[c]\ndatabase={root}/index\nnew_certs_dir={root}\n"
                    f"certificate={root}/ca.pem\nprivate_key={root}/ca.key\nserial={root}/serial\n"
                    f"crlnumber={root}/crlnumber\ndefault_md=sha256\ndefault_days=30\n"
                    "default_crl_days=30\npolicy=p\nunique_subject=no\n[p]\ncommonName=supplied\n")
        openssl("ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", root + "/ca.key")
        openssl("req", "-new", "-x509", "-key", root + "/ca.key", "-subj", "/CN=role-test-ca-" + os.path.basename(root),
                "-days", "30", "-addext", "basicConstraints=critical,CA:TRUE",
                "-addext", "keyUsage=critical,keyCertSign,cRLSign", "-out", root + "/ca.pem")
        self.crl()

    def crl(self):
        openssl("ca", "-batch", "-config", self.config, "-gencrl", "-out", self.root + "/revoked")

    def issue(self, role, *, dns="localhost", roles=None, cn=None):
        leaf = os.path.join(self.root, role)
        os.makedirs(leaf, exist_ok=True)
        uris = [tls.ROLE_URI + r for r in (roles if roles is not None else [role])]
        ext = os.path.join(leaf, "extensions")
        with open(ext, "w") as f:
            f.write("basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\n"
                    "extendedKeyUsage=serverAuth,clientAuth\nsubjectAltName=DNS:" + dns +
                    "".join(",URI:" + uri for uri in uris) + "\n")
        openssl("ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", leaf + "/server.key")
        openssl("req", "-new", "-key", leaf + "/server.key", "-subj", "/CN=" + (cn or role + "." + dns),
                "-out", leaf + "/request")
        openssl("ca", "-batch", "-config", self.config, "-extfile", ext, "-in", leaf + "/request",
                "-out", leaf + "/server.pem", "-notext")
        return tls.Bundle(self.root, role)

    def revoke(self, role):
        openssl("ca", "-batch", "-config", self.config, "-revoke", self.root + "/" + role + "/server.pem")
        self.crl()


@contextlib.contextmanager
def kits():
    with tempfile.TemporaryDirectory(prefix="role-") as root:
        ca = CA(root)
        ca.issue("console")
        for role in ("testsubworker", "testsub2worker"):
            ca.issue(role)
        yield ca


@contextlib.contextmanager
def server(bundle=None, *, context=None):
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def answer(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            calls.append((self.command, self.path, raw, dict(self.headers)))
            if bundle is not None and self.path.startswith("/accounts"):
                try:
                    tls.role_certificate(self.connection.getpeercert(), "console")
                except ValueError:
                    self.send_response(403)
                    self.end_headers()
                    return
            self.send_response(307 if self.path == "/redirect" else 202)
            self.send_header("Content-Type", "application/json")
            self.send_header("Location", "http://127.0.0.1:1/leak")
            reply = b"x" * ((1 << 20) + 1) if self.path == "/large" else b"{}"
            self.send_header("Content-Length", str(len(reply)))
            self.end_headers()
            self.wfile.write(reply)
        do_GET = do_POST = answer
        def log_message(self, *args): pass
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    if bundle is not None:
        srv.socket = (context or bundle.server_context()).wrap_socket(srv.socket, server_side=True)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield ("https" if bundle is not None else "http") + "://localhost:" + str(srv.server_port), calls
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(2)


def test_role_layout_is_exact_and_never_falls_back_to_the_old_bundle():
    with kits() as ca:
        b = tls.Bundle(ca.root, "console")
        assert b.ca == ca.root + "/ca.pem" and b.crl == ca.root + "/revoked"
        assert b.cert == ca.root + "/console/server.pem" and b.key == ca.root + "/console/server.key"
        assert b.client_context()
        shutil.copy(b.cert, ca.root + "/console.pem")
        os.remove(b.cert)
        with pytest.raises(FileNotFoundError):
            b.client_context()
        for role in ("", "../console", "console/other", "console\n"):
            with pytest.raises(ValueError):
                tls.Bundle(ca.root, role)


def test_real_role_client_proves_both_testsub_worker_roles_and_preserves_the_request():
    with kits() as ca:
        client = tls.RoleClient(ca.root, "console", required_role="console")
        for role in ("testsubworker", "testsub2worker"):
            with server(tls.Bundle(ca.root, role)) as (url, calls):
                headers = {"Authorization": "Bearer person", "Content-Type": "application/custom+json",
                           "Idempotency-Key": "once", "X-Operator": "console"}
                assert client.request("POST", url + "/accounts/alice?mode=one&mode=two", b'{"a":1}',
                                      headers, role=role)[:2] == (202, b"{}")
                assert calls[0][:3] == ("POST", "/accounts/alice?mode=one&mode=two", b'{"a":1}')
                assert all(calls[0][3][key] == value for key, value in headers.items())


def test_role_client_refuses_missing_kit_ip_wrong_role_and_wrong_dns_before_the_request():
    with kits() as ca:
        with server(tls.Bundle(ca.root, "testsubworker")) as (url, calls):
            for client, target, role in (
                    (tls.RoleClient(None, None), url, "testsubworker"),
                    (tls.RoleClient(ca.root, "console"), url.replace("localhost", "127.0.0.1"), "testsubworker"),
                    (tls.RoleClient(ca.root, "console"), url, "testsub2worker"),
                    (tls.RoleClient(ca.root, "testsub2worker", required_role="console"), url, "testsubworker")):
                with pytest.raises((ValueError, OSError)):
                    client.request("GET", target + "/accounts", b"", {}, role=role)
            assert calls == []
        ca.issue("testsubworker", dns="other.test")
        with server(tls.Bundle(ca.root, "testsubworker")) as (url, calls):
            with pytest.raises(ssl.SSLError):
                tls.RoleClient(ca.root, "console").request("GET", url, b"", {}, role="testsubworker")
            assert calls == []


def test_role_client_refuses_foreign_ca_revoked_server_and_revoked_client():
    with kits() as ca, kits() as foreign:
        for root in (foreign.root, ca.root):
            if root == ca.root:
                ca.revoke("console")
            with server(tls.Bundle(ca.root, "testsubworker")) as (url, calls):
                with pytest.raises(OSError):
                    tls.RoleClient(root, "console").request("GET", url + "/accounts", b"", {}, role="testsubworker")
                assert calls == []
    with kits() as ca:
        ca.revoke("testsubworker")
        with server(tls.Bundle(ca.root, "testsubworker")) as (url, calls):
            with pytest.raises(OSError):
                tls.RoleClient(ca.root, "console").request("GET", url + "/accounts", b"", {}, role="testsubworker")
            assert calls == []


def test_certificates_need_one_role_uri_and_exact_cn_without_cn_fallback():
    with kits() as ca:
        for roles, cn in (([], "console.localhost"), (["console", "testsubworker"], None),
                          (["console"], "other.localhost")):
            bundle = ca.issue("console", roles=roles, cn=cn)
            with pytest.raises(ValueError):
                bundle.client_context()
        cert = {"subject": ((("commonName", "console.localhost"),),), "subjectAltName": (("DNS", "localhost"),)}
        with pytest.raises(ValueError):
            tls.role_certificate(cert, "console")


def test_optional_client_certificate_keeps_public_route_but_proves_console_on_process_route():
    with kits() as ca:
        bundle = tls.Bundle(ca.root, "testsubworker")
        context = bundle.server_context(client_optional=True)
        with server(bundle, context=context) as (url, calls):
            anonymous = ssl.create_default_context(cafile=ca.root + "/ca.pem")
            import http.client
            conn = http.client.HTTPSConnection("localhost", int(url.rsplit(":", 1)[1]), context=anonymous)
            try:
                conn.request("GET", "/public")
                assert conn.getresponse().status == 202
                conn.close()
                conn.request("GET", "/accounts")
                assert conn.getresponse().status == 403
            finally:
                conn.close()
            assert tls.RoleClient(ca.root, "console").request("GET", url + "/accounts", b"", {},
                                                               role="testsubworker")[0] == 202
            assert tls.RoleClient(ca.root, "testsub2worker").request("GET", url + "/accounts", b"", {},
                                                                     role="testsubworker")[0] == 403


def test_box_http_never_redirects_a_persons_token_and_https_never_downgrades():
    with server() as (url, calls):
        client = tls.RoleClient(None, None)
        assert client.request("GET", url + "/redirect", b"", {"Authorization": "Bearer person"},
                              role="testsubworker")[0] == 307
        assert len(calls) == 1
        with pytest.raises(ValueError):
            client.request("GET", url.replace("http:", "https:"), b"", {}, role="testsubworker")
    with kits() as ca, server() as (url, calls):
        assert tls.RoleClient(ca.root, "console").request("GET", url, b"", {}, role="testsubworker")[0] == 202
        assert len(calls) == 1


def test_role_server_context_rereads_revocation_and_keeps_the_last_good_list():
    with kits() as ca:
        contexts = tls.ServerContext(ca.root, role="testsubworker", client_optional=True)
        first = contexts.get()
        ca.revoke("console")
        second = contexts.get()
        assert second is not first
        os.remove(ca.root + "/revoked")
        assert contexts.get() is second
        with open(ca.root + "/revoked", "w") as f:
            f.write("incomplete")
        assert contexts.get() is second


def test_http_client_bounds_real_replies_and_reports_malformed_http_as_unavailable():
    import socketserver
    with server() as (url, calls):
        with pytest.raises(ValueError):
            tls.RoleClient(None, None).request("GET", url + "/large", b"", {}, role="testsubworker")
    class Broken(socketserver.BaseRequestHandler):
        def handle(self):
            self.request.recv(4096)
            self.request.sendall(b"not an HTTP response\r\n\r\n")
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Broken)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(OSError):
            tls.RoleClient(None, None).request("GET", "http://127.0.0.1:" + str(srv.server_address[1]), b"", {},
                                               role="testsubworker")
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(2)


def unverified_client_context(bundle):
    """An external TLS endpoint that asks for no certificate; the caller must still refuse its foreign CA."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(bundle.cert, bundle.key)
    return context


def test_revoked_never_adds_foreign_ca_trust_or_forwards_a_persons_bearer_to_it():
    with kits() as ca, kits() as foreign:
        worker = tls.Bundle(foreign.root, "testsubworker")
        with open(ca.root + "/revoked", "rb") as source:
            original = source.read()
        with open(foreign.root + "/ca.pem", "rb") as source:
            foreign_ca = source.read()
        with open(foreign.root + "/revoked", "rb") as source:
            foreign_crl = source.read()
        for appended in (foreign_ca + foreign_crl, b"-----BEGIN PRIVATE KEY-----\nAA==\n-----END PRIVATE KEY-----\n",
                         b"unrelated data\n"):
            with open(ca.root + "/revoked", "wb") as target:
                target.write(original + appended)
            for build in (lambda: tls.Bundle(ca.root, "console").client_context(),
                          lambda: tls.Bundle(ca.root, "testsubworker").server_context(),
                          lambda: tls.Bundle(ca.root, "testsubworker").server_context(client_optional=True)):
                with pytest.raises(ValueError):
                    build()
            with server(worker, context=unverified_client_context(worker)) as (url, calls):
                with pytest.raises(ValueError):
                    tls.RoleClient(ca.root, "console").request("GET", url + "/public", b"",
                        {"Authorization": "Bearer private-person"}, role="testsubworker")
                assert calls == [], "a foreign endpoint received the person's request"


def test_role_loader_uses_the_checked_crl_bytes_if_the_original_file_changes_before_openssl_load():
    from unittest.mock import patch
    with kits() as ca, kits() as foreign:
        worker = tls.Bundle(foreign.root, "testsubworker")
        with open(ca.root + "/revoked", "rb") as source:
            original = source.read()
        mixed = original
        for path in (foreign.root + "/ca.pem", foreign.root + "/revoked"):
            with open(path, "rb") as source:
                mixed += source.read()
        load = ssl.SSLContext.load_verify_locations
        changed = []
        def replace_original(context, cafile=None, capath=None, cadata=None):
            if cafile is not None:
                with open(ca.root + "/revoked", "wb") as target:
                    target.write(mixed)
                changed.append(cafile)
            return load(context, cafile=cafile, capath=capath, cadata=cadata)
        with server(worker, context=unverified_client_context(worker)) as (url, calls):
            with patch.object(ssl.SSLContext, "load_verify_locations", replace_original):
                with pytest.raises(ssl.SSLError):
                    tls.RoleClient(ca.root, "console").request("GET", url + "/public", b"",
                        {"Authorization": "Bearer private-person"}, role="testsubworker")
            assert changed and all(path != ca.root + "/revoked" for path in changed)
            assert calls == [], "reopening the unchecked original file enlarged the CA trust"


def test_bounded_tls_door_handshakes_in_its_request_lane_and_reloads_revocation():
    import http.client
    import socket
    import time
    from unittest.mock import patch
    from w2cplatform import console
    with kits() as ca:
        contexts = tls.ServerContext(ca.root, role="testsubworker", client_optional=True)
        calls = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                calls.append(self.path)
                self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()
            def log_message(self, *args): pass
        srv = console.door_server(("127.0.0.1", 0), Handler, limit=2, per_address=2, tls_context=contexts)
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        stalled = None
        def wait_for(test):
            deadline = time.monotonic() + 2
            while not test():
                assert time.monotonic() < deadline, "bounded TLS lane did not settle"
                threading.Event().wait(0.005)
        url = "https://localhost:" + str(srv.server_port)
        try:
            # A peer that never sends ClientHello must occupy a bounded lane, never the accept loop.
            with patch.object(console, "CONSOLE_HEADER_TIMEOUT", 0.5):
                stalled = socket.create_connection(srv.server_address, timeout=1)
                wait_for(lambda: srv.bounds.used["common"] == 1)
                assert tls.RoleClient(ca.root, "console").request("GET", url + "/healthy", b"", {},
                                                                  role="testsubworker")[0] == 200
                assert calls == ["/healthy"]
                wait_for(lambda: srv.bounds.used["common"] == 0)
            stalled.close()
            stalled = None
            # The next new connection reads the changed list; an already running server refuses the revoked client.
            ca.revoke("console")
            with pytest.raises(OSError):
                tls.RoleClient(ca.root, "console").request("GET", url + "/revoked", b"", {}, role="testsubworker")
            assert calls == ["/healthy"]
            anonymous = ssl.create_default_context(cafile=ca.root + "/ca.pem")
            conn = http.client.HTTPSConnection("localhost", srv.server_port, context=anonymous)
            try:
                conn.request("GET", "/browser")
                assert conn.getresponse().status == 200
            finally:
                conn.close()
            assert calls == ["/healthy", "/browser"]
        finally:
            if stalled is not None:
                stalled.close()
            srv.shutdown()
            srv.server_close()
            thread.join(2)


def test_optional_tls_door_rejects_malformed_presented_roles_before_even_a_public_handler():
    import http.client
    from w2cplatform import console
    with kits() as ca:
        ca.issue("multi", roles=["console", "testsubworker"])
        ca.issue("wrongcn", cn="console.localhost")
        ca.issue("norole", roles=[])
        calls = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                calls.append(self.path)
                self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()
            def log_message(self, *args): pass
        srv = console.door_server(("127.0.0.1", 0), Handler,
            tls_context=tls.ServerContext(ca.root, role="testsubworker", client_optional=True))
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        try:
            for role in ("multi", "wrongcn", "norole", "testsub2worker", None):
                # Raw SSL admits these CA-signed leaves cryptographically. The door must still validate role shape.
                context = ssl.create_default_context(cafile=ca.root + "/ca.pem")
                if role is not None:
                    context.load_cert_chain(ca.root + "/" + role + "/server.pem", ca.root + "/" + role + "/server.key")
                conn = http.client.HTTPSConnection("localhost", srv.server_port, context=context, timeout=2)
                try:
                    if role in ("testsub2worker", None):
                        conn.request("GET", "/" + (role or "browser"))
                        assert conn.getresponse().status == 200
                    else:
                        with pytest.raises((OSError, http.client.HTTPException)):
                            conn.request("GET", "/malformed")
                            conn.getresponse()
                finally:
                    conn.close()
            assert calls == ["/testsub2worker", "/browser"]
        finally:
            srv.shutdown()
            srv.server_close()
            thread.join(2)


def test_worker_bootstrap_uses_the_role_kit_and_keeps_no_kit_on_loopback_without_starting_a_thread():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()
        def log_message(self, *args): pass
    with tempfile.TemporaryDirectory(prefix="worker-no-kit-") as root:
        env = {"W2C_TLS_DIR": root, "W2C_ROLE": "testsubworker"}
        for host, url in (("0.0.0.0", ""), ("127.0.0.1", "https://localhost:9000")):
            with pytest.raises(ValueError):
                tls.worker_door("testsub", host, 0, Handler, env=env, url=url)
        # Other roles' shared CA files do not turn an absent leaf into an incomplete worker kit.
        for name in ("ca.pem", "revoked"):
            with open(os.path.join(root, name), "w") as target:
                target.write("belongs to another role")
        srv, url = tls.worker_door("testsub", "127.0.0.1", 0, Handler, env=env)
        try:
            assert url == "http://127.0.0.1:" + str(srv.server_port) and srv.tls_context is None
            assert not srv.lanes
        finally:
            srv.server_close()
        os.mkdir(root + "/testsubworker")
        with open(root + "/testsubworker/server.key", "w") as target:
            target.write("incomplete")
        with pytest.raises(FileNotFoundError):
            tls.worker_door("testsub", "127.0.0.1", 0, Handler, env=env)
    with kits() as ca:
        env = {"W2C_TLS_DIR": ca.root, "W2C_ROLE": "testsubworker"}
        for url in ("http://localhost:9000", "https://127.0.0.1:9000", "https://other.test:9000",
                    "https://localhost:bad-port"):
            with pytest.raises(ValueError):
                tls.worker_door("testsub", "127.0.0.1", 0, Handler, env=env, url=url)
        with pytest.raises(ValueError):
            tls.worker_door("testsub", "127.0.0.1", 0, Handler,
                            env={**env, "W2C_ROLE": "testsub2worker"})
        srv, url = tls.worker_door("testsub", "127.0.0.1", 0, Handler, env=env)
        assert url == "https://localhost:" + str(srv.server_port) and srv.tls_context is not None
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        try:
            assert tls.RoleClient(ca.root, "console").request("GET", url + "/public", b"", {},
                                                               role="testsubworker")[0] == 200
        finally:
            srv.shutdown()
            srv.server_close()
            thread.join(2)
