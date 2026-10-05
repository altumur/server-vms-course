"""Lesson 4, at the door of a CLUSTER's console: a real token, the cluster's own key set, its own grants.

The platform's gate (`w2cplatform/access.py`) asks; `domain/access.py` answers — offline, from the cluster's
Variables, where the domain's agent put the key set and the grants. Step 3 of the order agreed with the product
(feedback BP): until this, a cluster's console took `X-User` and everybody was an administrator.
"""
import json
import tempfile
import urllib.error
import urllib.request

from cluster.objectstore import FsObjectStore
from cluster.variables import FakeVariables
from w2cplatform.domain.agent import GRANTS_PATH, KEYS_PATH, REVOKED_PATH
from w2cplatform.domain.grants import Grant, grants_from_items, grants_to_items
from w2cplatform.trust.tokens import RevocationList, TokenError, TokenIssuer, verify
from vms.console import make_console
from vms.controller import VmsController


class Clock:
    def __init__(self, t): self.t = t
    def __call__(self): return self.t
    def advance(self, dt): self.t += dt


def _cluster(clk):
    vars_ = FakeVariables()
    ctl = VmsController(vars_, FsObjectStore(tempfile.mkdtemp(prefix="gate-")), wall=clk)
    srv = make_console(ctl, None, clk).serve("127.0.0.1", 0)
    return vars_, ctl, srv, f"http://127.0.0.1:{srv.server_address[1]}"


def _call(base, method, path, token=None, body=None):
    _call.n = getattr(_call, "n", 0) + 1
    headers = {"Content-Type": "application/json", "Idempotency-Key": f"k{_call.n}", **({"Authorization": f"Bearer {token}"} if token else {})}
    req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def test_a_clusters_console_checks_the_domains_token_against_its_own_store():
    clk = Clock(1_757_500_000.0)
    signer = TokenIssuer("acme")
    vars_, ctl, srv, base = _cluster(clk)
    try:
        assert _call(base, "POST", "/cameras", body={"source": "driverpack://file/1.mp4", "labels": ["ground"]})[0] == 201   # no domain yet: open
        assert _call(base, "POST", "/cameras", body={"source": "driverpack://file/2.mp4"})[0] == 201

        # the cluster joins a domain: its agent carries the key set and the grants into ITS store
        vars_.put(KEYS_PATH, signer.keyset().to_items())
        vars_.put(GRANTS_PATH, grants_to_items([
            Grant("alice", "view", "vms/1", clk() + 86400), Grant("bob", "edit", None, clk() + 86400, ("ground",)),
            Grant("root", "admin", None, clk() + 86400), Grant("late", "admin", None, clk() + 60)]))
        tok = lambda who, life=900: signer.issue(who, life, now=clk(), kind="person")

        assert _call(base, "GET", "/cameras")[0] == 401                                     # the console asks now
        assert _call(base, "GET", "/cameras", TokenIssuer("acme").issue("alice", 900, now=clk(), kind="person"))[0] == 401   # another signer's token
        alice, bob, root = tok("alice"), tok("bob"), tok("root")
        assert _call(base, "GET", "/cameras", alice)[0] == 200
        assert _call(base, "GET", "/where/1", alice)[0] in (200, 404) and _call(base, "GET", "/where/2", alice)[0] == 403
        assert _call(base, "DELETE", "/cameras/1", alice)[0] == 403                         # `view` is not `admin`
        assert _call(base, "GET", "/where/1", bob)[0] in (200, 404)                         # `edit` implies `view`, on what carries the label
        assert _call(base, "GET", "/where/2", bob)[0] == 403
        assert _call(base, "DELETE", "/cameras/2", root)[0] == 200                          # `admin` implies the rest

        # a grant lapses by itself — the revocation that needs no network
        late = tok("late")
        assert _call(base, "GET", "/where/1", late)[0] in (200, 404)
        clk.advance(61)
        assert _call(base, "GET", "/where/1", late)[0] == 403

        # …and a token expires, and one that was revoked is refused though its signature is good
        clk.advance(900)
        assert _call(base, "GET", "/cameras", alice)[0] == 401
        fresh = tok("alice")
        assert _call(base, "GET", "/cameras", fresh)[0] == 200
        from w2cplatform.trust.tokens import verify
        rl = RevocationList(); rl.revoke(verify(fresh, signer.keyset(), now=clk()))
        vars_.put(REVOKED_PATH, rl.to_items())
        assert _call(base, "GET", "/cameras", fresh)[0] == 401
    finally:
        srv.shutdown()


def test_a_labelled_grant_travels_as_a_row_and_never_means_every_camera():
    g = [Grant("bob", "edit", None, 2000.0, ("ground", "east")), Grant("bob", "view", "vms/7", 2000.0), Grant("ann", "admin", None, 2000.0)]
    assert sorted(grants_from_items(grants_to_items(g)), key=str) == sorted(
        [Grant("bob", "edit", None, 2000.0, ("east", "ground")), Grant("bob", "view", "vms/7", 2000.0), Grant("ann", "admin", None, 2000.0)], key=str)
    from w2cplatform.domain.grants import ClusterGrants
    cg = ClusterGrants("south", now=lambda: 1000.0); cg.renew_from_domain(grants_from_items(grants_to_items(g)))
    assert cg.may("bob", "edit", "vms/3", labels=["ground", "east", "roof"]) and not cg.may("bob", "edit", "vms/3", labels=["ground"])
    assert not cg.may("bob", "edit", "vms/3") and not cg.may("bob", "edit", None)      # asked about no camera's labels: it is not "all"
    assert cg.may("bob", "view", "vms/7") and cg.may("ann", "edit", "vms/3")
    assert not cg.may("bob", "view", "7") and not cg.may("bob", "view", "rec/7")       # a unit is `<sub>/<id>`: nothing else is vms/7


def test_a_cluster_in_a_domain_runs_its_console_from_an_image_that_can_check_a_token():
    """The gate loads `w2cplatform.domain.access`; М11's image has not the library it verifies with. A
    console left on that image in a domain answers 503 to everything — shut, and useless. So the domain has an
    image of its own; and the cluster's console job — М11's appendix for a site that runs Nomad (М11's own servers
    run a systemd unit) — takes its installation as a variable."""
    import os
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    image = open(os.path.join(here, "deploy", "domain", "Containerfile")).read()
    assert "FROM localhost/clustervms:latest" in image and "python3-cryptography" in image and "ACCESS_IMPL" not in image
    job = open(os.path.join(here, "deploy", "cluster", "nomad", "console.nomad.hcl")).read()
    assert 'variable "w2c_home"' in job and 'command = "${var.w2c_home}/bin/w2c-run.sh"' in job and 'default = "/opt/w2c"' in job
    import importlib
    from w2cplatform.access import Gate
    assert importlib.import_module("w2cplatform.domain.access").cluster_access                 # what `ACCESS_IMPL` names is there to be loaded
    vars_ = FakeVariables(); vars_.put(KEYS_PATH, TokenIssuer("acme").keyset().to_items())
    assert type(Gate(vars_, lambda: 0.0).access()).__name__ == "ClusterAccess"     # …and with a key set in the store, the gate loads it



def test_a_browser_is_handed_a_cookie_for_a_token_the_console_checked():
    """`/session` — the door in. The page takes the password to the DOMAIN and brings the console only the token;
    the console checks it as the gate would and sets a cookie the page's script cannot read, for as long as the
    token lives. A request that ACTS, rides on the cookie and comes from another site's page is refused."""
    clk = Clock(1_757_500_000.0)
    signer = TokenIssuer("acme")
    vars_, ctl, srv, base = _cluster(clk)

    import itertools
    keys = itertools.count(1)

    def raw(method, path, body=None, headers=None):
        req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None, method=method,
                                     headers={"Content-Type": "application/json", "Idempotency-Key": f"s{next(keys)}", **(headers or {})})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read() or b"null"), r.headers.get("Set-Cookie", "")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}"), e.headers.get("Set-Cookie", "")

    try:
        assert raw("GET", "/session")[1] == {"gated": False, "user": "operator", "login": None}    # no domain: nobody to be
        vars_.put(KEYS_PATH, signer.keyset().to_items())
        vars_.put(GRANTS_PATH, grants_to_items([Grant("alice", "admin", None, clk() + 86400)]))
        assert raw("GET", "/session")[1] == {"gated": True, "user": None, "login": None}           # gated, and not known
        assert raw("POST", "/session", {"token": "not-a-token"})[0] == 401

        token = signer.issue("alice", 900, now=clk(), kind="person")
        code, body, cookie = raw("POST", "/session", {"token": token})
        assert code == 200 and body["user"] == "alice" and body["until"] == clk() + 900
        assert cookie.startswith(f"w2c_token={token}; ") and "HttpOnly" in cookie and "SameSite=Strict" in cookie and "Max-Age=900" in cookie

        me = {"Cookie": f"w2c_token={token}"}
        assert raw("GET", "/session", headers=me)[1]["user"] == "alice"
        assert raw("GET", "/cameras", headers=me)[0] == 200                                         # the cookie is a token, at the gate
        host = base[len("http://"):]
        assert raw("POST", "/cameras", {"source": "driverpack://file/1.mp4"}, {**me, "Origin": f"http://{host}"})[0] == 201
        code, body, _ = raw("POST", "/cameras", {"source": "driverpack://file/2.mp4"}, {**me, "Origin": "http://evil.example"})
        assert code == 403 and "another site" in body["detail"]                                      # steered by somebody else's page
        assert raw("POST", "/cameras", {"source": "driverpack://file/2.mp4"},
                   {"Authorization": f"Bearer {token}", "Origin": "http://evil.example"})[0] == 201   # a bearer is not a browser being steered

        clk.advance(1000)                                                                            # the token ended: the cookie is nobody's
        assert raw("GET", "/session", headers=me)[1]["user"] is None and raw("GET", "/cameras", headers=me)[0] == 401
        code, body, cookie = raw("DELETE", "/session", headers=me)
        assert code == 200 and cookie.startswith("w2c_token=; ") and "Max-Age=0" in cookie
    finally:
        srv.shutdown()


def test_the_emergency_account_opens_a_session_here_with_the_domain_away_and_every_use_is_an_alarm():
    """Lesson 4, step 7, at a cluster's door. The holder is away and every token has run out. The one local
    account: the domain set its password, the agent carried the HASH home, the console checks it here and opens
    a session in its own memory — no token is made, so none can be taken from the store. Every attempt is an
    alarm, the refused ones too; every request under it is one."""
    import itertools
    from w2cplatform.domain.agent import BREAK_GLASS_PATH, per_cluster, DomainPublisher
    from w2cplatform.domain.identity import _hash
    from w2cplatform.eventdatabase import EventIndex
    assert BREAK_GLASS_PATH in per_cluster()                                            # carried home by the agent like the grants
    home = FakeVariables()
    DomainPublisher(home).publish_break_glass("south", _hash("glass-for-south"), 1000.0)
    assert home.get(f"{BREAK_GLASS_PATH}/south")[0]["pwhash"].count(":") == 1          # a hash, never the password

    clk = Clock(1_757_500_000.0)
    vars_ = FakeVariables()
    archive = tempfile.mkdtemp(prefix="glass-")
    ctl = VmsController(vars_, FsObjectStore(tempfile.mkdtemp(prefix="gate-")), wall=clk)
    srv = make_console(ctl, archive, clk).serve("127.0.0.1", 0)
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    keys = itertools.count(1)

    def raw(method, path, body=None, headers=None):
        req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None, method=method,
                                     headers={"Content-Type": "application/json", "Idempotency-Key": f"g{next(keys)}", **(headers or {})})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read() or b"null"), r.headers.get("Set-Cookie", "")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}"), e.headers.get("Set-Cookie", "")

    def alarms():
        return [(e["kind"], e["user"]) for e in EventIndex(archive, "srv-1", wall=clk).query(0, clk() + 1, subsystem="audit", cls="alarm")["events"]]

    try:
        assert raw("POST", "/session", {"glass": {"who": "carol", "why": "uplink down", "password": "x"}})[1]["gated"] is False   # open: nothing to break into
        vars_.put(KEYS_PATH, TokenIssuer("acme").keyset().to_items())
        assert raw("POST", "/session", {"glass": {"who": "carol", "why": "uplink down", "password": "x"}})[0] == 403   # no account for this cluster
        vars_.put(BREAK_GLASS_PATH, home.get(f"{BREAK_GLASS_PATH}/south")[0])            # what the agent carried home
        assert raw("POST", "/session", {"glass": {"who": "", "why": "", "password": "glass-for-south"}})[0] == 400      # who and why are said
        assert raw("POST", "/session", {"glass": {"who": "carol", "why": "uplink down", "password": "wrong"}})[0] == 401
        code, body, cookie = raw("POST", "/session", {"glass": {"who": "carol", "why": "uplink down", "password": "glass-for-south"}})
        assert code == 200 and body["user"] == "break-glass(carol)" and body["until"] == clk() + 900
        assert cookie.startswith("w2c_glass=") and "HttpOnly" in cookie and "SameSite=Strict" in cookie
        me = {"Cookie": cookie.split(";")[0]}
        assert raw("GET", "/session", headers=me)[1]["user"] == "break-glass(carol)"
        assert raw("POST", "/cameras", {"source": "driverpack://file/1.mp4"}, me)[0] == 201                          # it is let in…
        refused = ("access.break_glass.refused", "break-glass(carol)")                                             # no account here, then a wrong password
        assert alarms() == [refused, refused, ("access.break_glass.opened", "break-glass(carol)"),
                            ("access.break_glass", "break-glass(carol)")]                                            # …and every step is said
        assert raw("GET", "/cameras", {"Cookie": "w2c_glass=guessed"})[0] == 401                                      # a session is this process's, not a guess
        clk.advance(901)
        assert raw("GET", "/cameras", headers=me)[0] == 401                                                          # fifteen minutes, like a token
        code, body, cookie = raw("POST", "/session", {"glass": {"who": "carol", "why": "still down", "password": "glass-for-south"}})
        me = {"Cookie": cookie.split(";")[0]}
        assert raw("DELETE", "/session", headers=me)[0] == 200 and raw("GET", "/cameras", headers=me)[0] == 401     # closed: gone from memory
    finally:
        srv.shutdown()


def test_a_token_of_any_shape_but_ours_is_401_before_and_after_its_signature():
    """The review's ninth pass, minor — a run: a token whose header is a list, whose `kid` is a list, or whose part is
    brackets nested past the parser's depth raised out of `tokens.verify` before the signature was looked at — an
    `AttributeError`, a `TypeError`, a `RecursionError` — and the console answered 500 (no answer at all) instead of
    401. And a token whose signature holds and whose `exp` is a word, `NaN` or 10**400, or whose `jti` is a list: no
    signer of ours writes one, and it is refused too. Each is 401 at a cluster's console and at `POST /session`."""
    from w2cplatform.trust.tokens import _b64
    clk = Clock(1_757_500_000.0)
    signer = TokenIssuer("acme")
    vars_, ctl, srv, base = _cluster(clk)
    vars_.put(KEYS_PATH, signer.keyset().to_items())
    vars_.put(GRANTS_PATH, grants_to_items([Grant("root", "admin", None, clk() + 86400)]))
    good = json.dumps({"alg": "EdDSA", "kid": signer.kid}).encode()

    def signed(payload: str) -> str:
        head = _b64(good) + "." + _b64(payload.encode())
        return head + "." + _b64(signer.key.sign(head.encode()))
    now = clk()
    garbage = [
        _b64(b"[1, 2]") + "." + _b64(b"{}") + ".x",                                      # a header that is a list
        _b64(json.dumps({"kid": ["a"]}).encode()) + "." + _b64(b"{}") + ".x",             # a `kid` that is a list
        _b64(good) + "." + _b64(b"[1]") + ".x",                                           # a payload that is a list
        ["a", "list"],                                                                   # not even a string (a body's token)
        signed(json.dumps({"sub": "root", "iat": now, "exp": "ten", "jti": "j1"})),
        signed('{"sub": "root", "iat": %s, "exp": NaN, "jti": "j2"}' % now),
        signed('{"sub": "root", "iat": %s, "exp": 1%s, "jti": "j3"}' % (now, "0" * 400)),
        signed(json.dumps({"sub": "root", "iat": now, "exp": now + 900, "jti": ["j4"]})),
    ]
    try:
        assert _call(base, "GET", "/cameras", signer.issue("root", 900, now=now, kind="person"))[0] == 200   # ours: admitted
        for tok in garbage:
            if isinstance(tok, str):
                code, body = _call(base, "GET", "/cameras", tok)
                assert code == 401, (tok[:40], code, body)
            code, body = _call(base, "POST", "/session", body={"token": tok})
            assert code in (400, 401) and (code == 401 or not isinstance(tok, str)), (tok[:40], code, body)
        for tok in garbage + [_b64(good) + "." + _b64(b"[" * 1_000_000 + b"]" * 1_000_000) + ".x"]:   # past the depth: offline
            try:
                verify(tok, signer.keyset(), now=now)
                raise AssertionError(f"{tok[:40]!r} verified")
            except TokenError:
                pass
    finally:
        srv.shutdown()


def test_the_signers_door_in_answers_a_garbage_body_400_and_a_garbage_token_401():
    """The sweep of the same minor at the signer's own door (`signer_service`, `POST /login`, `POST /revoke`): a body
    that is not an object, a name that is not a string, a token that does not verify were 500 — `/revoke` let the
    token's own error out, which nobody caught. The signer is run as its process is, on a store of files."""
    import os
    import signal
    import socket
    import subprocess
    import sys
    import time
    root = tempfile.mkdtemp(prefix="signer-")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {**os.environ, "DOMAIN_ID": "acme", "PLATFORM_STORE": f"file://{root}/vars", "OBJECT_STORE_URL": f"file://{root}/objects",
           "SIGNER_HOST": "127.0.0.1", "SIGNER_PORT": str(port)}
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    proc = subprocess.Popen([sys.executable, "-m", "w2cplatform.domain.signer_service"], cwd=here, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def post(path: str, raw: bytes) -> int:
        req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=raw, method="POST",
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code
    try:
        for _ in range(100):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    break
            except OSError:
                time.sleep(0.1)
        assert post("/login", b'{"user": "nobody", "password": "x"}') == 401   # the door works: no such user
        for bad in (b"[1]", b"{not json", b'{"user": ["a"], "password": "x"}', b'{"password": "x"}'):
            assert post("/login", bad) == 400, bad
        for bad in (b'{"token": "a.b.c"}', b'{"token": ["a"]}', b"{}", b'{"token": "' + b"x" * 200 + b'"}'):
            assert post("/revoke", bad) == 401, bad
    finally:
        proc.send_signal(signal.SIGTERM)
        proc.wait(10)
