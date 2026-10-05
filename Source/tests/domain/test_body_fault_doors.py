"""A body that is no JSON is the same refusal at the domain's doors as at the cluster's (the architect with «Паритет»,
2026-10-06; product 5223aba): the domain's console, its signer and the signer's token door read a body through
`canonical.parse_json`, and bytes that are not UTF-8, a lone surrogate, or a number past a float64 are 400 with the
shared table's `fault` (`not_json`, `not_number`) beside the door's own `detail`. The cluster's console and the store:
`tests/test_body_fault_doors.py`."""
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

BAD = [(b'{"a": "\xff"}', "not_json"), (b'{"a": "\\ud800"}', "not_json"), (b'{"a": 1e400}', "not_number")]


def _post(url: str, raw: bytes, who: str | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(url, data=raw, method="POST",
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": f"Bearer {who}"} if who else {})})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def test_the_domains_console_refuses_a_body_that_is_no_json_with_its_fault():
    """`POST /domain/members` as the domain's admin: 400, `fault`, the console's `detail` kept; a list is 400 with none."""
    from w2cplatform.domain.api import ConsoleAPI
    from w2cplatform.domain.console import Console
    from w2cplatform.domain.federation import DomainDirectory
    from w2cplatform.domain.grants import Grant, domain_may, set_domain_grants
    from w2cplatform.domain.members import Members
    from w2cplatform.domain.readview import ReadView
    from tests.domain.conftest import Clock
    from tests.domain.test_lesson15_root import _site
    wall = Clock()
    fed, devices, root, holder, agents, _ = _site(wall)
    set_domain_grants(holder.vars, [Grant("anna", "admin", None, 0.0)], wall())
    may = lambda cap: (lambda s: domain_may(holder.vars, s, cap, wall()))         # noqa: E731
    con = Console(DomainDirectory(fed), ReadView(fed, wall=wall), ConsoleAPI(DomainDirectory(fed), lambda n: None,
                  verifier=lambda t: t), refresh_interval=60, members=Members(holder.vars, wall),
                  admin=may("admin"), viewer=may("view"), holder_objects=devices["cam-SN0"].disk_door())
    srv = con.serve(port=0)
    url = f"http://127.0.0.1:{srv.server_address[1]}/domain/members"
    try:
        for raw, fault in BAD:
            st, out = _post(url, raw, "anna")
            assert (st, out.get("fault")) == (400, fault) and "does not parse" in out.get("detail", ""), (raw, st, out)
        st, out = _post(url, b"[1]", "anna")
        assert st == 400 and "fault" not in out, out
    finally:
        con.stop(srv)


def test_the_signers_token_door_refuses_a_body_that_is_no_json_with_its_fault():
    """`POST /tokens/<kind>` (`tokendoor.handler`): 400 with `fault` before the issuer is asked anything."""
    import threading
    from http.server import ThreadingHTTPServer

    from w2cplatform.domain import tokendoor

    class Issuer:
        kid, kinds = "k1", {}

        def issue(self, *a, **kw):
            raise AssertionError("asked to issue")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), tokendoor.handler(Issuer()))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        for raw, fault in BAD:
            st, out = _post(f"http://127.0.0.1:{srv.server_address[1]}/tokens/book", raw)
            assert (st, out.get("fault")) == (400, fault) and out.get("detail", "").startswith("the body is {sub, claims}"), \
                (raw, st, out)
        st, out = _post(f"http://127.0.0.1:{srv.server_address[1]}/tokens/book", b'{"sub": 7}')
        assert st == 400 and "fault" not in out, out
    finally:
        srv.shutdown()


def test_the_signers_door_refuses_a_body_that_is_no_json_with_its_fault():
    """`POST /api/login` at the signer, run as its process is (on a store of files): 400 with `fault`, its `detail` kept."""
    root = tempfile.mkdtemp(prefix="signer-")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {**os.environ, "DOMAIN_ID": "acme", "PLATFORM_STORE": f"file://{root}/vars", "OBJECTS": f"file://{root}/objects",
           "SIGNER_HOST": "127.0.0.1", "SIGNER_PORT": str(port)}
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    proc = subprocess.Popen([sys.executable, "-m", "w2cplatform.domain.signer_service"], cwd=here, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    break
            except OSError:
                time.sleep(0.1)
        assert _post(f"http://127.0.0.1:{port}/api/login", b'{"user": "nobody", "password": "x"}')[0] == 401
        for raw, fault in BAD:
            st, out = _post(f"http://127.0.0.1:{port}/api/login", raw)
            assert (st, out.get("fault"), out.get("detail")) == (400, fault, "the body is a JSON object"), (raw, st, out)
        st, out = _post(f"http://127.0.0.1:{port}/api/login", b"[1]")
        assert st == 400 and "fault" not in out, out
    finally:
        proc.send_signal(signal.SIGTERM)
        proc.wait(10)
