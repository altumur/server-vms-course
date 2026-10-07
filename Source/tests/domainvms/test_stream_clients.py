"""The RTSP accounts at the holder — the VMS worker's doors on the domain and the book `stream-accounts` (the product's
`vms/domainpart/streamclients.go` and `publishAccounts`; ADR-0031, the addendum of 2026-10-07; ADR-0024 for who reads the
secrets, ADR-0010 for the books and the kept rows).

A domain of three: srv-b holds it, srv-a and srv-c are members, each with its own ring and admitted with its own key, each
agent carrying through the holder's door. The domain's console is the real one (the people's routes handed to a signer
that answers the list of people from the holder's identity store); the worker's door is the real one, with tokens that
name their person. The declarations are the product's lines added to the course's YAML (`tests/streamspec.py`)."""
import json
import os
import tempfile
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from w2cplatform.console import open_doors
from w2cplatform.domain.agent import DomainAgent, DomainPublisher
from w2cplatform.domain.api import ApiError, ConsoleAPI
from w2cplatform.domain.carry import CarryClient, HolderDoor
from w2cplatform.domain.console import Console
from w2cplatform.domain.declared import GrantTooWide, NameTaken, guarded
from w2cplatform.domain.federation import DomainDirectory, Federation
from w2cplatform.domain.grants import Grant, domain_may, grants_from_items, set_domain_grants
from w2cplatform.domain.identity import IdentityStore
from w2cplatform.domain.members import Members
from w2cplatform.domain.readview import ReadView
from w2cplatform.sealing import is_sealed
from w2cplatform.trust.memberkey import MemberKey
from w2cplatform.trust.signer import Signer
from vms import streamclients as sc
from vms.domainpart.books import Books
from vms.domainpart.crossing import Crossings
from vms.domainpart.streamclients import ConsoleDoor, StreamClientDoors, new_stream_client
from vms.domainpart.worker import door_handler
from tests.domain.conftest import Clock, make_cluster
from tests.streamspec import declared


def ring():
    from w2cplatform.sealing import Sealer, new_key_file
    path = os.path.join(tempfile.mkdtemp(prefix="ring-"), "platform.key")
    new_key_file(path)
    return Sealer.from_file(path)


def _signer_stub(ids):
    """The signer's people's door, as far as these doors ask it: the list of people (`GET /api/people/users`), and no
    term (`/api/holder` 404: no write waits for one)."""
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/api/people/users":
                body, status = {"users": [{"name": u.id} for u in ids.users()]}, 200
            else:
                body, status = {"detail": "no such route"}, 404
            raw = json.dumps(body).encode()
            self.send_response(status); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

        def log_message(self, *a):
            pass
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


class Site:
    def __init__(self):
        self.wall = wall = Clock(1000.0)
        self.fed = fed = Federation()
        self.b, _ = make_cluster("srv-b", domain=True)
        self.a, _ = make_cluster("srv-a")
        self.c, _ = make_cluster("srv-c")
        for x in (self.a, self.b, self.c):
            fed.add(x)
        self.rings = {n: ring() for n in ("srv-a", "srv-b", "srv-c")}
        b = self.b
        self.signer = Signer("acme", b.vars, now=wall, sealer=self.rings["srv-b"])
        DomainPublisher(b.vars).publish_keys(self.signer.tokens.keyset())
        keys = {n: MemberKey.new() for n in ("srv-a", "srv-c")}
        members = Members(b.vars, wall, domain="srv-b")
        for n, k in keys.items():
            members.add(n, "voucher", key=k.pub, seal=k.seal_pub)
        door = HolderDoor(b.vars, b.objects, self.rings["srv-b"], wall)
        self.agents = {n: DomainAgent(n, CarryClient(door, n, keys[n], wall), getattr(self, n[-1]).vars, now=wall,
                                      sealer=self.rings[n], key=keys[n]) for n in ("srv-a", "srv-c")}
        self.agents["srv-b"] = DomainAgent("srv-b", b.vars, b.vars, now=wall, seen_store=b.objects, sealer=self.rings["srv-b"])
        self.crossings = Crossings(b.vars, ReadView(fed, wall=wall), wall, issuer=self.signer.tokens,
                                   sealer=self.rings["srv-b"])
        self.books = Books(self.crossings, b.objects)
        self.ids = IdentityStore(self.signer, b.vars, b.objects, now=wall, sealer=self.rings["srv-b"])
        self.ids.create_local("anna", "a-long-password", [])
        set_domain_grants(b.vars, [Grant("anna", "admin", None, 0.0), Grant("boris", "view", None, 0.0)], wall())
        may = lambda cap: (lambda s: domain_may(b.vars, s, cap, wall()))         # noqa: E731
        self.signer_srv = _signer_stub(self.ids)
        self.console = Console(DomainDirectory(fed), ReadView(fed, wall=wall),
                               ConsoleAPI(DomainDirectory(fed), lambda n: None, verifier=lambda t: t),
                               refresh_interval=60, admin=may("admin"), viewer=may("view"), holder_vars=b.vars,
                               signer_url=f"http://127.0.0.1:{self.signer_srv.server_address[1]}")
        self.console_srv = self.console.serve(port=0)
        self.doors = StreamClientDoors(guarded(b.vars), sealer=self.rings["srv-b"], wall=wall,
                                       console=ConsoleDoor(f"http://127.0.0.1:{self.console_srv.server_address[1]}"))
        self.door = open_doors("127.0.0.1", 0, door_handler(fed, None, verifier=lambda t: t, viewer=may("view"),
                                                             admin=may("admin"), clients=self.doors),
                               unix_env="NO_SUCH_DOOR", say=False)
        self.base = f"http://127.0.0.1:{self.door.server_address[1]}"

    def call(self, method: str, path: str, who: str | None = "anna", body=None):
        req = urllib.request.Request(self.base + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": f"Bearer {who}"} if who else {})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def grant(self, cluster: str, *lines):
        DomainPublisher(self.b.vars).publish_grants(cluster, [Grant(s, cap, None, self.wall() + 86400) for s, cap in lines])

    def carry(self):
        self.books.pass_once()
        for x in self.agents.values():
            x.sync()

    def close(self):
        self.console.stop(self.console_srv)
        for srv in (self.door, self.signer_srv):
            srv.shutdown(); srv.server_close()


def _site():
    return Site()


def test_a_client_is_made_its_password_shown_once_and_sealed_in_the_store():
    """`POST /stream-clients {name}`: the password is in the answer, and nowhere else in the clear — not in the list,
    not in the holder's row (sealed with the holder's ring, bound to the row). A new password is another one; the list
    shows the name, never a password. Looking needs `view` on the domain, making needs `admin`."""
    with declared():
        s = _site()
        try:
            status, made = s.call("POST", "/stream-clients", body={"name": "wall1"})
            assert status == 200 and made["client"] == "wall1" and len(made["password"]) == 32, (status, made)
            row, _ = s.b.vars.get("domain/vms/stream-clients/wall1")
            assert is_sealed(row["password_secret"]) and made["password"] not in json.dumps(row)
            assert json.loads(row["doc"])["name"] == "wall1" and json.loads(row["doc"])["by"] == "anna"
            status, listed = s.call("GET", "/stream-clients", "boris")
            assert status == 200 and listed == {"clients": [json.loads(row["doc"])]}
            assert made["password"] not in json.dumps(listed)
            status, again = s.call("POST", "/stream-clients/wall1/password")
            assert status == 200 and again["client"] == "wall1" and again["password"] != made["password"]
            assert sc.read_stream_client(s.b.vars, "wall1", s.rings["srv-b"])[1] == again["password"]
            assert sc.read_stream_client(s.b.vars, "wall1")[1] == ""          # sealed, and no ring here: no password
            assert s.call("POST", "/stream-clients", "boris", {"name": "wall2"})[0] == 403
            assert s.call("POST", "/stream-clients", None, {"name": "wall2"})[0] == 401
            assert s.call("POST", "/stream-clients/nobody/password")[0] == 404
            assert s.call("PUT", "/stream-clients", body={})[0] == 405
        finally:
            s.close()


def test_a_name_a_person_holds_is_refused_409_and_a_person_is_not_made_under_a_clients_name():
    """One name space, the grants' subjects (ADR-0031). The door asks the domain console whether a person holds the
    name, as the person who asked — 409; a client of that name already — 409; a name that is no name — 400. Without
    the console asked, the holder's store refuses it all the same (`domain.names`, the platform's guard). And the other
    way round: a person under a client's name is the platform's refusal."""
    with declared():
        s = _site()
        try:
            status, said = s.call("POST", "/stream-clients", body={"name": "anna"})
            assert status == 409 and said == {"error": "refused", "detail": "there is a user anna already"}, said
            assert s.b.vars.get("domain/vms/stream-clients/anna")[0] is None
            assert s.call("POST", "/stream-clients", body={"name": "wall1"})[0] == 200
            status, said = s.call("POST", "/stream-clients", body={"name": "wall1"})
            assert status == 409 and said["detail"] == "there is a stream client wall1 already"
            for bad in ("a|b", "", "x/y", "break-glass", 'say"hi'):
                status, said = s.call("POST", "/stream-clients", body={"name": bad})
                assert status == 400 and said["detail"] == f"{json.dumps(bad)} is not a client's name", (bad, said)
            try:
                new_stream_client(guarded(s.b.vars), None, "anna", "tool", s.wall(), s.rings["srv-b"])
                raise AssertionError("the holder's store lets a client be written under a person's name")
            except ApiError as e:
                assert e.status == 409 and "anna" in e.detail
            try:
                s.ids.create_local("wall1", "a-long-password", [])
                raise AssertionError("a person was made under a client's name")
            except NameTaken:
                pass
            try:
                s.grant("srv-a", ("wall1", "edit"))
                raise AssertionError("a client was granted more than view")
            except GrantTooWide:
                pass
        finally:
            s.close()


def test_the_book_of_a_cluster_carries_only_the_clients_its_grants_name_and_no_disabled_one():
    """The books' pass writes `stream-accounts/<cluster>` for every cluster: the clients a line of ITS grants names,
    none disabled — sealed at the holder with its ring; the agent carries it home sealed to the member's key, and keeps
    it sealed with the member's ring as `domain/vms/stream-accounts`, which the member opens with its own ring alone."""
    with declared():
        s = _site()
        try:
            pw = {n: s.call("POST", "/stream-clients", body={"name": n})[1]["password"] for n in ("wall1", "wall2", "wall3")}
            s.grant("srv-a", ("wall1", "view"), ("wall2", "view"), ("anna", "admin"))
            s.grant("srv-c", ("wall3", "view"))
            assert s.call("PUT", "/stream-clients/wall2", body={"disabled": True}) == (200, {"client": "wall2", "disabled": True})
            assert s.call("PUT", "/stream-clients/wall2", body={})[0] == 400
            assert s.call("PUT", "/stream-clients/nobody", body={"disabled": True})[0] == 404
            s.carry()
            assert sc.stream_accounts(s.a.vars, "srv-a", s.rings["srv-a"]) == {"wall1": pw["wall1"]}
            assert sc.stream_accounts(s.c.vars, "srv-c", s.rings["srv-c"]) == {"wall3": pw["wall3"]}
            # the holder hands its own from its records (it holds the keys), and it granted nobody here
            assert sc.stream_accounts(s.b.vars, "srv-b", s.rings["srv-b"]) == {}
            for store, path in ((s.b.vars, "domain/vms/stream-accounts/srv-a"), (s.a.vars, "domain/vms/stream-accounts")):
                items, _ = store.get(path)
                assert is_sealed(items["accounts_secret"]) and pw["wall1"] not in json.dumps(items), path
            assert sc.stream_accounts(s.a.vars, "srv-a", s.rings["srv-c"]) == {}     # another ring opens nothing
            # on again: carried with the next pass
            assert s.call("PUT", "/stream-clients/wall2", body={"disabled": False})[0] == 200
            s.carry()
            assert sc.stream_accounts(s.a.vars, "srv-a", s.rings["srv-a"]) == {"wall1": pw["wall1"], "wall2": pw["wall2"]}
            # a new password reaches the member with its agent's next pass, and the old one is gone
            new = s.call("POST", "/stream-clients/wall1/password")[1]["password"]
            s.carry()
            assert sc.stream_accounts(s.a.vars, "srv-a", s.rings["srv-a"])["wall1"] == new != pw["wall1"]
        finally:
            s.close()


def test_deleting_a_client_drops_every_grant_that_names_it_through_the_domain_console():
    """`DELETE /stream-clients/<name>`: its grants go first, through the domain console's door as the person who asked
    (`PUT /domain/grants/<cluster>`: the grants are the domain's to write), then its row; the next books carry it to
    nobody."""
    with declared():
        s = _site()
        try:
            pw = {n: s.call("POST", "/stream-clients", body={"name": n})[1]["password"] for n in ("wall1", "wall2")}
            s.grant("srv-a", ("wall1", "view"), ("wall2", "view"))
            s.grant("srv-c", ("wall1", "view"))
            s.carry()
            assert set(sc.stream_accounts(s.a.vars, "srv-a", s.rings["srv-a"])) == {"wall1", "wall2"}
            assert s.call("DELETE", "/stream-clients/wall1", "boris")[0] == 403
            status, said = s.call("DELETE", "/stream-clients/wall1")
            assert status == 200 and said == {"client": "wall1", "deleted": True, "grants_changed": ["srv-a", "srv-c"]}, said
            subjects = lambda c: {g.subject for g in grants_from_items(s.b.vars.get(f"domain/grants/{c}")[0])}   # noqa: E731
            assert subjects("srv-a") == {"wall2"} and subjects("srv-c") == set()
            assert domain_may(s.b.vars, "anna", "admin", s.wall())               # the domain's own grants untouched
            assert sc.read_stream_client(s.b.vars, "wall1", s.rings["srv-b"]) == (None, "")
            assert "password_secret" not in s.b.vars.get("domain/vms/stream-clients/wall1")[0]    # the mark: no password
            assert [c.name for c in sc.stream_clients(s.b.vars)] == ["wall2"]
            s.carry()
            assert sc.stream_accounts(s.a.vars, "srv-a", s.rings["srv-a"]) == {"wall2": pw["wall2"]}
            assert sc.stream_accounts(s.c.vars, "srv-c", s.rings["srv-c"]) == {}
            assert s.call("DELETE", "/stream-clients/wall1")[0] == 404
            s.ids.create_local("wall1", "a-long-password", [])                 # the name is free again
        finally:
            s.close()


def test_nothing_declared_nothing_made_and_nothing_carried():
    """The course's YAML as it is, without the product's lines: the doors are not there (404), the pass writes no book
    (`stream-accounts` is not in what it returns), and a member reads no account."""
    s = _site()
    try:
        assert s.call("GET", "/stream-clients")[0] == 404
        assert s.call("POST", "/stream-clients", body={"name": "wall1"})[0] == 404
        s.grant("srv-a", ("wall1", "view"))
        out = s.books.pass_once()
        assert "stream-accounts" not in out
        assert s.b.vars.list("domain/vms/stream-accounts") == []
        assert sc.stream_accounts(s.a.vars, "srv-a", s.rings["srv-a"]) == {}
    finally:
        s.close()
