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
from domain.agent import GRANTS_PATH, KEYS_PATH, REVOKED_PATH
from domain.grants import Grant, grants_from_items, grants_to_items
from domain.tokens import RevocationList, TokenIssuer
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
            Grant("alice", "view", 1, clk() + 86400), Grant("bob", "edit", None, clk() + 86400, ("ground",)),
            Grant("root", "admin", None, clk() + 86400), Grant("late", "admin", None, clk() + 60)]))
        tok = lambda who, life=900: signer.issue(who, life, now=clk())

        assert _call(base, "GET", "/cameras")[0] == 401                                     # the console asks now
        assert _call(base, "GET", "/cameras", TokenIssuer("acme").issue("alice", 900, now=clk()))[0] == 401   # another signer's token
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
        from domain.tokens import verify
        rl = RevocationList(); rl.revoke(verify(fresh, signer.keyset(), now=clk()))
        vars_.put(REVOKED_PATH, rl.to_items())
        assert _call(base, "GET", "/cameras", fresh)[0] == 401
    finally:
        srv.shutdown()


def test_a_labelled_grant_travels_as_a_row_and_never_means_every_camera():
    g = [Grant("bob", "edit", None, 2000.0, ("ground", "east")), Grant("bob", "view", 7, 2000.0), Grant("ann", "admin", None, 2000.0)]
    assert sorted(grants_from_items(grants_to_items(g)), key=str) == sorted(
        [Grant("bob", "edit", None, 2000.0, ("east", "ground")), Grant("bob", "view", 7, 2000.0), Grant("ann", "admin", None, 2000.0)], key=str)
    from domain.grants import ClusterGrants
    cg = ClusterGrants("south", now=lambda: 1000.0); cg.renew_from_domain(grants_from_items(grants_to_items(g)))
    assert cg.may("bob", "edit", 3, labels=["ground", "east", "roof"]) and not cg.may("bob", "edit", 3, labels=["ground"])
    assert not cg.may("bob", "edit", 3) and not cg.may("bob", "edit", None)      # asked about no camera's labels: it is not "all"
    assert cg.may("bob", "view", 7) and cg.may("ann", "edit", 3)
