"""ADR-0032 — the signer holds the keys and performs the operations that need them; the domain's console has no key.

The signer (`signer_service.Holder`) is the one process with the domain's keys, and the holder's whole pass runs there:
every output of the pass — the view, the week of alarms, the backup, the kept edits closed — has that one writer. It has
exactly five operations, and checks each itself, the freeze of a handover included: the shared settings, a handover,
the people with their passwords, the backup sealed by the pass, a move of the domain onto its cluster. The domain's
console (`console.Console`) reads: the members and their publications from the store, what only the signer knows from
the view the signer publishes; it writes what a person decides with no key, and hands the rest to the signer as it
came."""
import ast
import json
import os
import urllib.error
import urllib.request

from w2cplatform.domain.agent import DomainPublisher
from w2cplatform.domain.alarms import AlarmHistory, DomainAlarms, ReportedDoor
from w2cplatform.domain.api import ConsoleAPI
from w2cplatform.domain.console import Console
from w2cplatform.domain.federation import Cluster, DomainDirectory, Federation
from w2cplatform.domain.grants import Grant, set_domain_grants
from w2cplatform.domain.identity import IdentityStore
from w2cplatform.domain.members import Members, fingerprint
from w2cplatform.domain.pending import PendingEdits
from w2cplatform.domain.readview import ReadView
from w2cplatform.domain.signer_service import Holder
from w2cplatform.domain.term import DomainHolder, handover
from w2cplatform.domain.topology import Topology
from w2cplatform.domain.uplink import member_copy
from w2cplatform.trust.signer import Signer
from w2cplatform.trust.tokens import PERSON, RevocationList
from tests.domain.conftest import Clock

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))      # Source/


class Recorded:
    """A store that says what was written through it — each process's writes, told apart."""

    def __init__(self, store, wrote: list):
        self.store, self.wrote = store, wrote

    def get(self, key):
        return self.store.get(key)

    def list(self, prefix):
        return self.store.list(prefix)

    def put(self, key, *a, **kw):
        self.wrote.append(key)
        return self.store.put(key, *a, **kw)

    def delete(self, key):
        self.wrote.append(key)
        return self.store.delete(key)

    def __getattr__(self, name):
        return getattr(self.store, name)


class Lines:
    """A journal that keeps its lines."""

    def __init__(self):
        self.lines = []

    def say(self, kind, cls="observation", **fields):
        self.lines.append((kind, fields))


def _domain():
    """Lesson 14's site — north holds the domain, three cameras report into its store, each with a card — with a signer,
    a term (Lesson 15), and anna an admin of the domain."""
    from tests.domain.test_lesson14_alarms import NOW, _site
    wall = Clock(NOW)
    fed, north, devices, cards, agents, report, reported = _site(wall)
    signer = Signer("acme", north.vars, now=wall)
    DomainPublisher(north.vars).publish_keys(signer.tokens.keyset())
    set_domain_grants(north.vars, [Grant("anna", "admin", None, 0.0), Grant("boris", "view", None, 0.0)], wall())
    return wall, fed, north, devices, cards, report, signer


def _as(fed, north, wrote: list, wall):
    """The domain as one process reads it: the holder's stores through `Recorded`, every member by its reports there."""
    v, o = Recorded(north.vars, wrote), Recorded(north.objects, wrote)
    f = Federation()
    f.add(Cluster("north", v, o, is_domain_holder=True))
    for name in fed.clusters:
        if name != "north":
            f.add(member_copy(name, o, wall=wall))
    return f, v, o


def _signer(fed, north, signer, wall, wrote: list, journal=None) -> Holder:
    f, v, o = _as(fed, north, wrote, wall)
    term = DomainHolder(f, "north", signer, 1, wall, objects=o)
    term.claim()
    return Holder(v, o, signer, ids=IdentityStore(signer, v, o, publish_floor=0, now=wall, journal=journal),
                  revoked=RevocationList(),
                  fed=f, view=ReadView(f, wall=wall), members=Members(v, wall, domain="north"), topology=Topology(v),
                  pending=PendingEdits(v, wall), term=term, journal=journal, console_url="http://console.site:8444",
                  alarms=DomainAlarms(f, lambda m: ReportedDoor(m, o, wall=wall), wall, history=AlarmHistory(o, wall=wall)),
                  wall=wall, backup_every=0)


def _console(fed, north, wall, wrote: list, signer_url=None, journal=None) -> Console:
    f, v, o = _as(fed, north, wrote, wall)
    return Console(DomainDirectory(f), ReadView(f, wall=wall), ConsoleAPI(DomainDirectory(f), lambda n: None,
                   verifier=lambda t: t), refresh_interval=60, holder_objects=o, holder_vars=v,
                   members=Members(v, wall, domain="north", journal=journal), topology=Topology(v),
                   pending=PendingEdits(v, wall), signer_url=signer_url, journal=journal,
                   admin=lambda s: s == "anna",
                   alarms=DomainAlarms(f, lambda m: ReportedDoor(m, o, wall=wall), wall, history=AlarmHistory(o, wall=wall)))


def _call(base, method, path, body=None, token=None):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None, method=method,
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def _serve(holder: Holder):
    from w2cplatform.console import open_doors
    srv = open_doors("127.0.0.1", 0, holder.handler(), unix_env="SG_NO_SUCH_SOCKET", say=False)
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def test_the_domain_console_holds_no_key_material_and_has_no_role_on_the_signers_rows():
    """Its unit loads no ring and joins neither the ring's group nor the tokens socket's; the key file and the signer's
    sockets are not there for it; its store role (`domainconsole`) neither reads nor writes `domain/signer*` nor the
    people; and its code imports nothing that seals, signs or opens a sealed row."""
    from tests.domain.test_lesson3_readview_api_gateway import _units
    from w2cplatform.storemachine import Rights
    u = _units()["w2c-domain-console"]
    assert "LoadCredential" not in u and "SECRETS_KEY" not in u["env"]
    assert u["SupplementaryGroups"][0].split() == ["w2c-domainconsole", "w2c-store", "w2c-events"]
    assert u["env"]["PLATFORM_STORE"] == "configstore:///run/configstore/domainconsole.sock"
    hidden = [p.lstrip("-") for p in u["InaccessiblePaths"][0].split()]
    assert {"/etc/w2c/secrets", "/run/w2c-signer", "/run/w2c-domain"} <= set(hidden)
    r = Rights.load(os.path.join(HERE, "deploy", "cluster", "configstore-rights.json"))
    for action in ("read", "write", "delete"):
        for key in ("domain/signer", "domain/signer/old", "identity/users/anna"):
            assert not r.allows("domainconsole", action, key), (action, key)
    tree = ast.parse(open(os.path.join(HERE, "w2cplatform", "domain", "console.py"), encoding="utf-8").read())
    imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names} | \
               {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    for name in ("Signer", "Sealer", "sign", "seal_row", "seal_items", "open_row", "IdentityStore", "set_password",
                 "TokenIssuer", "DeclaredIssuer", "w2cplatform.trust.signer", "w2cplatform.sealing", "breakglass",
                 "identity", "carry"):
        assert name not in imported, name


def test_each_of_the_five_operations_runs_in_the_signer_and_refuses_while_a_handover_freezes_it():
    """The shared settings, the people with their passwords, a handover, a move and the backup sealed by the pass: each
    asks the freeze HERE — 503 while a handover is under way, nothing written — whatever the console says or does not
    say; and each goes through once the holder is not frozen (a move then says this cluster holds the domain already).
    The backup has no route: the pass seals it."""
    wall, fed, north, devices, cards, report, signer = _domain()
    wrote = []
    h = _signer(fed, north, signer, wall, wrote, Lines())
    h.hand_to = lambda to: (_ for _ in ()).throw(AssertionError("a frozen holder moves nothing"))
    anna = signer.tokens.issue("anna", 900, now=wall(), kind=PERSON)
    h.run_pass()                                                          # the view read every member: backups have keepers
    h.term.frozen_for = "cam-SN1"                                         # a handover is under way
    del wrote[:]
    ops = [lambda: h.shared(anna, {"base_rev": 0, "shared": {"vms": {"retention_days": 3}}}),
           lambda: h.people("POST", "users", anna, {"name": "vera", "password": "a long password"}),
           lambda: h.people("PUT", "break-glass/cam-SN1", anna, {"password": "glass glass glass"}),
           lambda: h.handover(anna, {"to": "cam-SN1"}),
           lambda: h.move({"recovery": signer.backup().decode()})]
    for op in ops:
        st, body = op()
        assert st == 503 and "cam-SN1" in body["detail"], (st, body)
    assert h.backup() is None
    assert wrote == []                                                    # nothing signed, sealed or kept
    h.term.frozen_for = None
    assert ops[0]()[0] != 503                                            # the edit's own rules decide now
    st, body = ops[1]()
    assert st == 200 and h.ids.get("vera").kind == "local"
    st, body = ops[2]()
    assert st == 200 and north.vars.get("domain/break_glass/cam-SN1")[0]["pwhash_secret"] != "glass glass glass"
    assert isinstance(h.backup(), int) and any(k.startswith("backup/rev-") for k in wrote)
    st, body = ops[4]()
    assert st == 409 and "holds the domain at term 1" in body["detail"], body      # nothing to move onto a holder
    assert h.people("POST", "users", None, {"name": "x", "password": "a long password"})[0] == 401
    boris = signer.tokens.issue("boris", 900, now=wall(), kind=PERSON)
    assert h.people("POST", "users", boris, {"name": "x", "password": "a long password"})[0] == 403
    assert h.people("GET", "users", boris, {})[0] == 200                  # view reads them; admin changes them
    assert [k for k, _ in h.journal.lines] == ["domain.user.created", "domain.break_glass.set"]


def test_a_handover_is_the_signers_and_the_console_only_hands_it_on():
    """Lesson 15's site: `POST /domain/handover {to}` at the domain's console goes to the signer as it came, and the
    signer hands the domain over (`term.handover`) — freeze, the last backup to the target, the target's agent takes it,
    the move. Then the old holder is replaced: every operation there is refused (409), at the signer and so at the
    console. No route anywhere signs what it is given."""
    from tests.domain.test_lesson15_domain_of_one import DOMAIN, _objects, _site
    wall = Clock()
    fed, devices, signer, offline, holder, agents = _site(wall)
    set_domain_grants(holder.vars, [Grant("anna", "admin", None, 0.0)], wall())
    lines = Lines()
    h = Holder(holder.vars, devices["cam-SN0"].disk, signer, ids=IdentityStore(signer, holder.vars, devices["cam-SN0"].disk,
               publish_floor=0, now=wall), revoked=RevocationList(), fed=fed, term=holder, journal=lines,
               hand_to=lambda to: handover(holder, to, offline, DOMAIN, _objects(devices), lambda: agents[to].sync(),
                                           wall),
               wall=wall)
    srv, signer_url = _serve(h)
    con = Console(DomainDirectory(fed), ReadView(fed, wall=wall), ConsoleAPI(DomainDirectory(fed), lambda n: None),
                  refresh_interval=60, holder_vars=holder.vars, signer_url=signer_url)
    door = con.serve(port=0)
    base = f"http://127.0.0.1:{door.server_address[1]}"
    anna = signer.tokens.issue("anna", 900, now=wall(), kind=PERSON)
    try:
        assert _call(base, "POST", "/domain/handover", {"to": "cam-SN1"})[0] == 401          # the signer asks who
        assert sorted(_call(signer_url, "GET", "/api/holder")[1]) == ["deposed", "record", "term"]
        st, body = _call(base, "POST", "/domain/handover", {"to": "cam-SN1"}, anna)
        assert st == 200 and body["term"] == 2 and body["stranded"] == [], body
        assert holder.deposed_by["holder"] == "cam-SN1" and lines.lines[-1][0] == "domain.handover"
        said = _call(signer_url, "GET", "/api/holder")[1]
        assert said["deposed"] and said["deposed_by"]["holder"] == "cam-SN1"
        for method, path, body in (("PUT", "/domain/shared", {"base_rev": 0, "shared": {}}),
                                   ("POST", "/domain/users", {"name": "vera", "password": "a long password"}),
                                   ("POST", "/domain/handover", {"to": "cam-SN2"})):
            st, out = _call(base, method, path, body, anna)
            assert st == 409 and "cam-SN1" in out["detail"], (path, st, out)
        for path in ("/api/sign", "/sign/shared", "/sign/term", "/seal/backup", "/api/seal"):
            assert _call(signer_url, "POST", path, {"doc": {}}, anna)[0] == 404, path
            assert _call(base, "POST", path, {"doc": {}}, anna)[0] == 404, path
    finally:
        con.stop(door)
        srv.shutdown()


def test_the_consoles_alarms_read_writes_nothing_and_the_week_is_kept_by_the_signers_pass():
    """`GET /domain/alarms` at the console answers the one list and writes nothing — not the week of history, whose one
    writer is the signer's pass (`DomainAlarms.keep`)."""
    wall, fed, north, devices, cards, report, signer = _domain()
    cards["cam-SN1"].observe(1, wall() - 100, "door_forced", alarm=True)
    report()
    console_wrote, signer_wrote = [], []
    con = _console(fed, north, wall, console_wrote)
    door = con.serve(port=0)
    try:
        st, out = _call(f"http://127.0.0.1:{door.server_address[1]}", "GET", "/domain/alarms")
        assert st == 200 and [e["kind"] for e in out["events"]] == ["door_forced"]
    finally:
        con.stop(door)
    assert console_wrote == [] and north.objects.list("domain/alarm-history/") == []
    _signer(fed, north, signer, wall, signer_wrote).run_pass()
    assert "domain/alarm-history/cam-SN1" in signer_wrote


def test_every_output_of_the_holders_pass_has_one_writer_and_it_is_the_signer():
    """The console's pass and every route it reads write nothing; the signer's pass writes the view, the week of
    alarms, the backup and its pointers. What the console writes at all is a person's decision with no key — admitting
    a member, the topology, the grants — and none of those is an output of the pass."""
    from w2cplatform.console import DOMAIN_VIEW
    from w2cplatform.domain.rights import CONSOLE_WRITES
    from w2cplatform.rights import allowed
    wall, fed, north, devices, cards, report, signer = _domain()
    cards["cam-SN2"].observe(1, wall() - 50, "tamper", alarm=True)
    report()
    console_wrote, signer_wrote = [], []
    h = _signer(fed, north, signer, wall, signer_wrote)
    del signer_wrote[:]
    h.run_pass()
    outputs = set(signer_wrote)
    assert {DOMAIN_VIEW, "domain/alarm-history/cam-SN2"} <= outputs and h.loop.failing == set()
    assert any(k.startswith("backup/rev-") for k in outputs) and any(k.startswith("domain/backup/cam-") for k in outputs)
    srv, signer_url = _serve(h)
    con = _console(fed, north, wall, console_wrote, signer_url=signer_url, journal=Lines())
    con._steps(("following the members", con._follow_members), ("following the topology", con._follow_topology),
               ("the read view's pass", con.view.refresh))
    door = con.serve(port=0)
    base = f"http://127.0.0.1:{door.server_address[1]}"
    try:
        for path in ("/domain", "/domain/alarms", "/domain/backup", "/domain/members", "/domain/grants", "/domain/keys",
                     "/domain/shared", "/domain/topology", "/domain/causes", "/domain/vms/cameras", "/healthz"):
            assert _call(base, "GET", path)[0] == 200, path
        assert console_wrote == []
        view = _call(base, "GET", "/domain")[1]
        assert view["url"] == "http://console.site:8444" and view["term"]["term"] == 1 and "pass_failures" in view
        assert _call(base, "PUT", "/domain/topology", {"base_rev": 0, "centre": "north"}, "anna")[0] == 200
        assert _call(base, "PUT", "/domain/grants/cam-SN1", {"lines": [{"subject": "anna", "cap": "view", "scope": "*"}]},
                     "anna")[0] == 200
        assert _call(base, "PUT", "/domain/grants/cam-SN1", {"lines": []}, "boris")[0] == 403
    finally:
        con.stop(door)
        srv.shutdown()
    assert console_wrote and all(allowed(list(CONSOLE_WRITES), k) for k in console_wrote), console_wrote
    assert not set(console_wrote) & outputs
    assert [k for k, _ in con.journal.lines] == ["domain.topology.changed", "domain.grants.changed"]


def test_a_knocking_member_is_admitted_by_the_key_its_report_presents():
    """The agent's report mark carries the keys it presents; the console names the knocking member with that key's
    fingerprint, and a person who compared it admits the member BY it — its row then holds the key, as one the
    registrar admitted. A fingerprint that is not the presented key's is refused: somebody else knocks under the name."""
    from vms.domainpart.device import DeviceCluster
    from w2cplatform.cluster.variables import FakeVariables
    from w2cplatform.domain.agent import DomainAgent
    from w2cplatform.trust.memberkey import MemberKey
    wall, fed, north, devices, cards, report, signer = _domain()
    members = Members(north.vars, wall, domain="north")
    members.add("cam-SN0", "voucher")                                     # the list is written: strangers knock
    cam, key = DeviceCluster("SN7", FakeVariables(), wall=wall), MemberKey.new()
    cam.boot()
    DomainAgent(cam.name, north.vars, cam.flash, now=wall, domain_objects=north.objects, published=cam.local_objects(),
                key=key).sync()
    knock = {k["name"]: k for k in members.knocking(north.objects)}["cam-SN7"]
    assert knock["key"] == key.pub and knock["fingerprint"] == fingerprint(key.pub) and "seal" not in knock
    try:
        members.accept("cam-SN7", by="anna", domain_objects=north.objects, fingerprint="0" * 16)
        raise AssertionError("another key's fingerprint")
    except Exception as e:                                                # noqa: BLE001
        assert getattr(e, "status", None) == 409
    assert members.accept("cam-SN7", by="anna", domain_objects=north.objects, fingerprint=fingerprint(key.pub))
    row = members.read()["members"]["cam-SN7"]
    assert (row["key"], row["seal"], row["how"]) == (key.pub, key.seal_pub, "accepted by anna")
