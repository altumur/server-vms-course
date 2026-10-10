"""The rights file and the code say the same thing, and a test says so.

The store's rights are a file the daemon reads — `deploy/cluster/configstore-rights.json`, installed as
`/etc/w2c/configstore-rights.json` — and the daemon asks it before anything is forwarded or applied, by the socket the
caller came through. The file is GENERATED from the specs of the catalogue (`python3 -m w2cplatform.cluster rights`,
`w2cplatform/cluster/rights.py`): the roles of every subsystem the catalogue holds, the writes from `acl_console`,
`acl_controller`, `acl_worker_role` (the spec's `worker:`) and the create-only object rows, the reads from a list with the
code that makes each read.

The history this file comes from: on Nomad the policies were written by hand in `*-policy.hcl`, and inside two
commits they stopped matching the code three times — the controller's grant named `objects/vms/snapshot` exactly when
the snapshot had become one object per worker; the console got a `blob` route and no grant for it; the rec controller
never had a grant for its own snapshot. All three were invisible, because the suite ran against a store with no
rights at all. The stand now runs every process through its own role's door with THIS file's rights, so a missing
grant is a 403 in the stand; and this checks the file against the code both ways — every write the code makes (the
stand's, every scene, and the doors the scenes do not knock on) is granted, and nothing is granted that the code's
lists do not ask for — and every read the code makes is granted.
"""
import json
import os

from w2cplatform.domain.rights import roles as domain_roles  # noqa: E402
from w2cplatform import catalog
from w2cplatform.cluster.objectstore import is_row
from w2cplatform.cluster.rights import render, roles
from w2cplatform.rights import DELETE_ONLY, split
from vms.config import REC_SPEC, SPEC
from w2cplatform.resource import DOORS
from w2cplatform.storemachine import Rights
from tests.cluster.conftest import HERE, RIGHTS

SPECS = catalog.load_dir(os.path.join(HERE, "vms"))       # the catalogue the installed tree carries (`SPEC_DIR`)

OBJECTS = "objects/"
SOCKETS = "/run/configstore/"


def rights() -> Rights:
    return Rights.load(RIGHTS)


def doc() -> dict:
    with open(RIGHTS, encoding="utf-8") as f:
        return json.load(f)


def test_the_committed_file_is_what_the_spec_generates():
    """`deploy/cluster/configstore-rights.json` is `python3 -m w2cplatform.cluster rights` now — a hand edit, or a spec
    changed without regenerating it, fails here (and `install.sh` refuses to install it)."""
    with open(RIGHTS, encoding="utf-8") as f:
        assert f.read() == render(SPECS, "vms"), \
            "regenerate it: SPEC_DIR=vms python3 -m w2cplatform.cluster rights > deploy/cluster/configstore-rights.json"
    assert Rights.parse(doc()).roles == {r: {a: g[a] for a in ("read", "write", "delete")} for r, g in roles(SPECS, "vms").items()}


def test_each_role_says_its_sockets_group_in_the_products_format():
    """The product's format (its configstore round 2): each role carries its socket's `group` — a VMS subsystem's
    `vms-<role>`, the platform's `w2c-<role>` — which is what a unit joins (`SupplementaryGroups=`). The console is the
    platform's process (ADR 0014), so its group is `w2c-console`; so is every subsystem's controller (ADR 0023): the
    role keeps the spec's name, `<sub>controller`, its group is `w2c-<sub>controller`."""
    r = rights()
    for role in doc()["roles"]:
        platform = role in ("resource", "console", "domain", "domainconsole", "domainagent") or role.endswith("controller")
        assert r.groups[role] == ("w2c-" if platform else "vms-") + role, role
    assert {"console", "vmscontroller", "reccontroller", "vmsworker", "recworker", "resource"} <= set(r.roles)


def _expected_writes() -> dict[str, set[str]]:
    rows = lambda objs: {OBJECTS + p for p in objs if is_row(p)}            # noqa: E731
    out = {"console": {a for s in SPECS for a in s.acl_console()} | {"door/signer", "door/keys"}   # the door key (`door.py`)
           | {p for s in SPECS for p in rows(s.sub.acl_objects_console())}}   # the reaper's end in a mark (ADR-0054)
    for s in SPECS:                                                           # every subsystem of the catalogue: its two roles
        out[f"{s.name}controller"] = set(split(s.acl_controller())[0])          # a `delete:` is no write (ADR-0067)
        out[f"{s.name}worker"] = set(s.acl_worker_role()) | rows(s.sub.acl_objects_worker() + [s.sub.config(p) for p in s.object_rows])
    return {**out,
            "resource": {DOORS + "/*", *[s.sub.request_key("free-*") for s in SPECS if s.requests_free]},   # its ask to free bytes
            # the domain's roles are the platform domain's to say, from the specs (`w2cplatform/domain/rights.py`): the
            # agent's grant on `domain/*` with a denial of every row only the holder writes; no member role
            **{role: set(g["write"]) for role, g in domain_roles(specs=SPECS).items()}}


def _delete_only(role: str) -> set:
    return {p[len(DELETE_ONLY):] for s in SPECS if role == f"{s.name}controller" for p in s.acl_controller()
            if p.startswith(DELETE_ONLY)}


def test_a_controller_deletes_a_unit_row_only_when_its_spec_says_unplaced_delete_after_and_never_writes_one():
    """ADR-0067: `placement.unplaced.delete_after` gives the controller of the spec the DELETE of its unit rows (`delete:`,
    the product's `p.DeleteOnly`) and no write of them; a spec without the key gives neither. The live controller deletes
    a stream nobody holds; the VMS's deletes no camera."""
    r = rights()
    assert r.allows("livecontroller", "delete", "live/streams/7") and not r.allows("livecontroller", "write", "live/streams/7")
    assert not r.allows("vmscontroller", "delete", "vms/cameras/7") and not r.allows("reccontroller", "delete", "rec/recordings/7")


def test_every_write_grant_is_one_the_code_asked_for_and_every_one_it_asked_for_is_there():
    """Both directions against the code's own lists. What `objects/vms/*` would fail — the grant the worker once had,
    whose comment said "its heartbeat" while the pattern said the whole subsystem. And an object that is a FILE now
    (a heartbeat, a shard, a pass report, a blob) is no row, so no grant names it: only the create-only keys are."""
    got = {role: set(g["write"]) for role, g in doc()["roles"].items()}
    assert got == _expected_writes()
    for role, g in doc()["roles"].items():
        marks = {p for p in g["write"] if p.startswith(OBJECTS) and p.endswith("/commands/*")} if role == "console" else set()
        assert set(g["delete"]) == set(g["write"]) - marks | _delete_only(role), role   # a role deletes what it writes — but
        # the console a mark: it writes the end of a request into one (the second writer) and never takes one away (ADR
        # 0054) — and a controller whose spec says `placement.unplaced.delete_after` deletes its unit rows besides (ADR-0067)
        assert all(not p.startswith(OBJECTS) or is_row(p[len(OBJECTS):]) for p in g["write"]), role


def test_nothing_writes_what_it_has_no_business_writing():
    """Direction two by name, the cases each of which once happened: a worker writes its claims and nothing of the
    configuration; the controller places and edits nothing; the console edits and places nothing; the resource
    stays inside its doors; nobody writes an object that is a file."""
    r = rights()
    denied = [("vmsworker", "vms/cameras/7"), ("vmsworker", "vms/placement/7"), ("vmsworker", "vms/workers/w-srv-a-1"),
              ("recworker", "rec/recordings/7"), ("recworker", "vms/epoch/7"),
              ("vmscontroller", "vms/cameras/7"), ("vmscontroller", "vms/epoch/7"), ("vmscontroller", "rec/placement/7"),
              ("console", "vms/placement/7"), ("console", "vms/workers/w-srv-a-1"), ("console", "vms/slots/w-srv-a-1"),
              ("resource", "vms/cameras/7"), ("resource", "platform/schema"),
              ("domainagent", "vms/cameras/7")]
    for role in r.roles:
        denied += [(role, OBJECTS + k) for k in ("vms/heartbeats/w-1", "vms/snapshot/w-1", "vms/controller/pass",
                                                 "platform/resources/srv-a/heartbeat")]
    for role, key in denied:
        assert not r.allows(role, "write", key), f"{role} may write {key}"
    for role in r.roles:
        assert not r.allows(role, "delete", "vms/epoch/7")
        assert (role in ("domain", "domainagent")) == r.allows(role, "delete", "domain/keys"), role


def test_the_console_writes_the_marks_of_requests_and_no_other_object_of_a_worker():
    """ADR 0054: the console's reaper ends a request in its mark — `expired` create-only, `unknown` by the index it read —
    so the console's role writes `objects/<sub>/commands/*` of every spec with `requests:`, and nothing else a worker
    writes (heartbeats, contenders, used); it never deletes a mark — only the holder sweeps one (`Worker.sweep_marks`), a
    mark being «not more than once» (ADR 0013). Create-only and by-index are the code's, not the grant's."""
    r = rights()
    for k in ("vms/commands/r-1", "rec/commands/r-1"):
        assert r.allows("console", "write", OBJECTS + k), k
        assert not r.allows("console", "delete", OBJECTS + k), k                 # only the holder sweeps a mark
    for k in ("vms/heartbeats/w-1", "vms/contenders/7", "vms/used/srv-a", "rec/used/srv-a"):
        assert not r.allows("console", "write", OBJECTS + k), k
    written = [p for p in roles(SPECS, "vms")["console"]["write"] if p.startswith(OBJECTS)]
    assert all(p.endswith("/commands/*") for p in written), written
    assert {p.split("/")[1] for p in written} == {s.name for s in SPECS if s.requests or s.requests_free}, written


def test_the_domain_has_a_role_and_its_keys_are_read_by_that_role_alone():
    """The thirteenth review, major 11: the М12 signer opened `domain.sock`, and no rights file named a role `domain` —
    no daemon opened that socket, the first read was `StoreUnavailable`, the signer went round its restarts. The role
    is the platform's (`w2c-domain`, a group configstore is a member of): the domain's rows and the people's
    (`identity/*`) written, the holder's own cluster read. And the least of DOMAIN-PLATFORM.md's narrowing: the domain's
    keys (`domain/signer`) are read and written by `domain` alone — the agent reads `domain/*` but not them, and writes
    none of what only the holder writes; a member reads nothing of the holder's store (no member role: it carries
    through the domain's door)."""
    r = rights()
    assert r.groups["domain"] == "w2c-domain"
    for action, key in (("read", "domain/signer"), ("write", "domain/signer"), ("write", "identity/users/u1"),
                        ("read", "identity/pointer"), ("write", "domain/vms/crossings"), ("read", "vms/cameras/7"),
                        ("delete", "domain/pending/north")):
        assert r.allows("domain", action, key), (action, key)
    for role in ("domainagent", "domainconsole", "vmsdomain", "console", "vmsworker"):
        for action in ("read", "write", "delete"):
            assert not r.allows(role, action, "domain/signer"), (role, action)
    assert r.allows("domainagent", "read", "domain/keys") and r.allows("domainagent", "write", "domain/grants")
    assert not r.allows("domainagent", "write", "domain/grants/north") and "member" not in r.roles
    assert r.allows("vmsdomain", "write", "domain/vms/primaries/cam-SN1") and not r.allows("vmsdomain", "write", "domain/keys")
    assert not r.allows("domain", "write", "vms/cameras/7")


def test_the_domains_console_has_a_role_of_its_own_with_no_key_and_no_people():
    """ADR-0032: the domain's console is its own process with its own role — `domainconsole`, the platform's group — and
    no part of the domain's keys, read or written; the people's rows (sealed with the ring) are the signer's too. It
    writes what a person decides there with no key: the members, the topology, the grants, an edit kept again; and it
    reads the rest of the domain and the units, for the views it serves."""
    r = rights()
    assert r.groups["domainconsole"] == "w2c-domainconsole"
    for key in ("domain/signer", "domain/signer/backup", "identity/users/u1", "domain/shared", "domain/backup/north",
                "domain/view", "domain/vms/crossings"):
        assert not r.allows("domainconsole", "write", key), key
    for key in ("domain/signer", "domain/signer/backup", "identity/users/u1"):
        assert not r.allows("domainconsole", "read", key), key
    for key in ("domain/members", "domain/topology", "domain/grants/north", "domain/grants/domain", "domain/pending/north"):
        assert r.allows("domainconsole", "write", key), key
    for key in ("domain/keys", "domain/backup/north", "domain/shared", "domain/vms/crossings", "vms/cameras/7"):
        assert r.allows("domainconsole", "read", key), key
    assert not r.allows("domainconsole", "delete", "domain/members")          # the store's rule: the domain's roles alone


# -- what the processes DO: every scene of the stand, and the doors the scenes do not knock on ------------------------
def _doors(s) -> None:
    """A request at the console's door and at the holder's playback door (each asks its gate), what a server reaches
    written from the page, a decommission, and the recorder controller's passes — none of which a scene makes."""
    import urllib.error
    import urllib.request
    from vms.worker import FakeDevice
    from w2cplatform.host import spec_console
    from w2cplatform.spec import SpecController
    s.resources_up()
    con, ctl = s.console("srv-a", "console on srv-a (gate)"), s.controller()
    con.create_camera({"source": "driverpack://acme/10.0.0.50/ch/1"})
    dev = FakeDevice("acme/10.0.0.50", channels=["1"], coverage={"1": (0.0, 100.0)})
    w = s.worker("srv-a", device_factory=lambda k: dev)
    w.heartbeat_once(); ctl.ensure_placed(); w.reconcile_once(); w.heartbeat_once()
    door = w.serve_playback("127.0.0.1", 0)
    rec_con = SpecController(REC_SPEC, con.vars, con.objects, wall=s.wall)
    v = s.door("reccontroller", "reccontroller on srv-b")
    rc = SpecController(REC_SPEC, v, s.objects_on("srv-b", v, "reccontroller on srv-b"), wall=s.wall)
    s.wall.watchers += [rec_con, rc]                      # each judges by what it saw change: it looks as time moves
    srv = spec_console({"vms": con, "rec": rec_con}, "vms").serve("127.0.0.1", 0)
    try:
        for url in (f"http://127.0.0.1:{door.server_address[1]}/playback/1?from=0&to=1",
                    f"http://127.0.0.1:{srv.server_address[1]}/cameras"):
            with urllib.request.urlopen(url) as r:
                r.read()
        # What a server reaches, from the console (feedback DQ): written, removed and written again — so the
        # controllers' passes below read one — at the console's root: one row a server, the platform's
        # (`platform/servers/srv-a`, ADR-0026's addition), read by the camera's controller and the recorder's.
        for method in ("PUT", "DELETE", "PUT"):
            req = urllib.request.Request(f"http://127.0.0.1:{srv.server_address[1]}/servers/srv-a/labels", method=method,
                                         data=b'{"labels": ["vlan:cctv-a"]}' if method == "PUT" else None,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req) as r:
                r.read()
        # A machine gone for good (М10A Lesson 7, step 7): srv-a goes silent, the console writes
        # `platform/decommission/srv-a` — deletes it and writes it again, so a delete is made too — and the
        # controllers' passes below read it, release the slot on that server and write their marks.
        s.wall.advance(100)
        for method, want in (("POST", 202), ("DELETE", 200), ("POST", 202)):
            req = urllib.request.Request(f"http://127.0.0.1:{srv.server_address[1]}/servers/srv-a/decommission",
                                         method=method, data=b'{"why": "the server burnt"}' if method == "POST" else None,
                                         headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req) as r:
                    got = r.status
            except urllib.error.HTTPError as e:
                got = e.code
            assert got == want, (method, got)
    finally:
        door.shutdown(); srv.shutdown()
    rec_con.create({"name": "1", "cam": "1"})
    rc.ensure_placed(); rc.redistribute(); rc.ensure_home(1); rc.unplace_deleted()
    # The pass as the loops run it (`w2cplatform.host.placement_pass`): its report, then the snapshot.
    for c in (ctl, rc):
        c.pass_once(1); c.publish_snapshot()
    assert ctl.slots()[w.name].released and ctl.decommission_marks()       # the row was read, the slot released, the mark written


# The scenes whose point is a write the store refuses: their 403 is the lesson, not the code writing outside its grant.
REFUSED_ON_PURPOSE = ("a_worker_may_not_write_a_camera", "who_may_write_what")
_CALLS: list = []


def code_calls() -> tuple[dict[str, set[tuple[str, str]]], dict[str, set[tuple[str, str, int]]]]:
    """`({role: {("read" | "list", key)}}, {role: {("write" | "delete", key, status)}})`: every read and every write of
    the store each role made — every scene, and `_doors` — by the socket it came through."""
    if _CALLS:
        return _CALLS[0]
    from urllib.parse import parse_qsl, urlsplit
    import tests.cluster.stand as stand
    made, real = [], stand.Stand.__init__
    current = {"scene": ""}

    def init(self, *a, **k):
        real(self, *a, **k)
        made.append((current["scene"], self))
    stand.Stand.__init__ = init
    try:
        for scene in stand.SCENES.values():
            current["scene"] = scene.__name__
            scene()
        current["scene"] = "_doors"
        _doors(stand.Stand())
    finally:
        stand.Stand.__init__ = real
    reads: dict[str, set] = {}
    writes: dict[str, set] = {}
    for scene, s in made:
        for c in s.log.calls:
            if c.kind != "store" or not c.door.startswith(SOCKETS):
                continue
            role = c.door[len(SOCKETS):-len(".sock")]
            if c.write:
                if scene not in REFUSED_ON_PURPOSE:
                    action = "write" if c.op == "put" else "delete"
                    writes.setdefault(role, set()).add((action, c.body["key"], c.status))
            else:
                q = dict(parse_qsl(urlsplit(c.target).query))
                reads.setdefault(role, set()).add(("read", q["key"]) if c.op == "get" else ("list", q.get("prefix", "")))
    _CALLS.append((reads, writes))
    return reads, writes


def test_every_write_the_code_makes_is_granted():
    """THE WRITES AS THE PROCESSES MAKE THEM (the review's ninth pass, major). The checks above compare the file with
    the spec's lists — which are written by hand too: the controller's pass wrote its report, no list named it, and
    every check agreed while the cluster said 403 every five seconds. So every write and delete a process made in the
    stand — every scene, and the passes and doors the scenes do not run — is allowed by that role's rights; and the
    stand refused none of them, except in the scenes whose point is the refusal."""
    _, writes = code_calls()
    assert {"vmsworker", "recworker", "vmscontroller", "reccontroller", "console", "resource"} <= set(writes), sorted(writes)
    r = rights()
    refused, outside = [], []
    for role, made in sorted(writes.items()):
        for action, key, status in sorted(made):
            if status == 403:
                refused.append(f"{role}: {action} {key}")
            if not r.allows(role, action, key):
                outside.append(f"{role}: {action} {key}")
    assert not outside, "the code writes what its rights do not grant:\n" + "\n".join(outside)
    assert not refused, "the stand refused a write the code made:\n" + "\n".join(refused)


def test_every_row_the_code_reads_is_granted():
    """Every get and every listing a process made in the stand is allowed by its role's rights — a get the file does
    not grant is a 403 from the daemon, a listing answers only what the role may read (and so would be silently
    short): both are checked here, by the key and by what lies under the prefix."""
    reads, _ = code_calls()
    assert {"vmsworker", "recworker", "vmscontroller", "reccontroller", "console", "resource"} <= set(reads), sorted(reads)
    r = rights()
    for role, made in sorted(reads.items()):
        for op, key in sorted(made):
            probe = key + "x" if op == "list" else key            # a listing is of a prefix: what lies under it
            assert r.allows(role, "read", probe), f"{role} may not {op} {key}"


def test_the_gate_and_the_schema_are_readable_by_every_process_that_asks_them():
    """The same from the code's constants, for what the stand reaches only in part: the gate asks for the key set and
    every row that marks a member (`TRUST_KEYS`, `DOMAIN_MARKS`) at the console and at the holder's door; a domain's
    image reads the grants by cluster (`domain/grants/<cluster>`); every process checks `platform/schema` first —
    `Worker.__init__` → `check_schema` (WP1's note: every worker role)."""
    from w2cplatform.access import DOMAIN_MARKS, MEMBER_MARK, TRUST_KEYS
    from w2cplatform.contract import SCHEMA_KEY
    r = rights()
    for key in (TRUST_KEYS, *DOMAIN_MARKS, "domain/grants/acme"):
        assert r.allows("console", "read", key), f"console may not read {key}"
    for key in (TRUST_KEYS, MEMBER_MARK):                # the holder's door verifies no token (`Gate.gated`)
        assert r.allows("vmsworker", "read", key), f"vmsworker may not read {key}"
    for role in r.roles:
        assert r.allows(role, "read", SCHEMA_KEY), f"{role} may not read {SCHEMA_KEY}"


def test_the_holder_reads_no_more_of_the_domain_than_its_door_asks():
    """М10's ninth review, minor: the holder's grant once covered every row that marks a member — the grants and
    `domain/break_glass`, the emergency password's hash, among them — while its playback door verifies no token and
    asks only whether the cluster is in a domain (`Gate.gated`: the key set, and `domain/member` while there is none).
    Not wider than the code: of `domain/*` the worker reads exactly those two rows."""
    import tempfile
    from vms.worker import FakeActuator, VmsWorker
    from w2cplatform.access import MEMBER_MARK, TRUST_KEYS
    from w2cplatform.objects import FsObjectStore
    from w2cplatform.variables import FileVariables
    granted = {p for p in doc()["roles"]["vmsworker"]["read"] if p.startswith("domain")}
    assert granted == {TRUST_KEYS, MEMBER_MARK}, sorted(granted)
    root = tempfile.mkdtemp()
    vars_, read = FileVariables(f"{root}/vars"), []
    real = vars_.get
    vars_.get = lambda path: (read.append(path), real(path))[1]
    w = VmsWorker("w-1", vars_, FsObjectStore(f"{root}/objects"), FakeActuator(), resource_root=f"{root}/archive")
    assert w.playback_refusal("1", "", {}, "127.0.0.1") is None        # an open cluster: the door asks nobody
    vars_.put(MEMBER_MARK, {"cluster": "acme"})                       # a member that lost its keys: it asks
    assert w.playback_refusal("1", "", {}, "127.0.0.1")[0] == 503      # …and has no key of its own yet: shut
    made = {p for p in read if p.startswith("domain")}
    assert made == {TRUST_KEYS, MEMBER_MARK}, sorted(made)


def test_the_clusters_key_is_a_credential_of_the_three_units_that_open_a_password_and_no_row():
    """The console seals, the holder and the recorder open (`w2cplatform/sealing.py`). On Nomad the key was a Variable
    that three policies read and a template rendered; here it is a file on every server, and the three units — and no
    other — load it as a systemd credential, readable by their own process only (`%d/platform.key`); and the spares of
    the two that open one, which are their units but the name (the twelfth review, blocker 6). No role of the store
    reads any `secrets/` row: there is none."""
    r = rights()
    for role in r.roles:
        assert not r.allows(role, "read", "secrets/vms"), role
    deploy = os.path.join(os.path.dirname(RIGHTS), "systemd")
    loaders = {f for f in os.listdir(deploy) if f.endswith(".service")
               and "LoadCredential=platform.key:/etc/w2c/secrets/platform.key" in open(os.path.join(deploy, f)).read()}
    assert loaders == {"w2c-console.service", "vms-vmsworker.service", "vms-recworker.service",
                       "vms-vmsworker-spare@.service", "vms-recworker-spare@.service"}


def test_a_key_is_exact_and_a_prefix_says_so():
    """Kept as a named case because it cost a production morning on Nomad: a pattern without a trailing `*` is ONE
    key. The daemon's patterns say the same (`storemachine.Rights`), and a denial (`!`) wins over a grant."""
    r = Rights.parse({"roles": {"c": {"write": ["objects/vms/snapshot/*", "vms/policy", "vms/*", "!vms/epoch/*"]}}})
    assert r.allows("c", "write", "objects/vms/snapshot/w-1") and not r.allows("c", "write", "objects/vms/snapshot")
    assert r.allows("c", "write", "vms/policy") and r.allows("c", "write", "vms/cameras/1")
    assert not r.allows("c", "write", "vms/epoch/1")


def test_a_worker_whose_spec_declares_a_door_for_people_reads_the_clusters_grants_and_no_other_does():
    """«Архитектор» 2026-10-07 (the RTSP accounts, question B): a holder that decides who it shows a unit to — its spec
    declares a door for people (`door: {routes}`: the live gateway, the recorder) — reads the cluster's grants
    (`domain/grants/*`, not secret); a worker with no such door does not. The product's worker reads `*` less its
    denials: the same behaviour. And the secret rows under `domain/` are read by those `secrets.readers` names — the
    domain's console reads neither the accounts nor the books of them; its agent reads the carried book, not the clients."""
    r = rights()
    with_door = {f"{s.name}worker" for s in SPECS if s.door_routes}
    assert {"liveworker", "recworker"} <= with_door
    for s in SPECS:
        assert r.allows(f"{s.name}worker", "read", "domain/grants/room-a") == (f"{s.name}worker" in with_door), s.name
    assert not r.allows("domainconsole", "read", "domain/vms/stream-clients/wall1")
    assert not r.allows("domainconsole", "read", "domain/vms/stream-accounts")
    assert not r.allows("domainagent", "read", "domain/vms/stream-clients/wall1")
    assert r.allows("domainagent", "read", "domain/vms/stream-accounts")
    assert r.allows("domain", "read", "domain/vms/stream-clients/wall1")              # the signer backs up domain.kept


def test_the_recorder_reads_the_books_its_ingest_and_forwarder_read():
    """The scenario «камера — офис — центр», F3: the ingest and the forwarder live in the recorder (ADR-0065's addition of
    2026-10-08), and on configstore the recorder never raised its forwarder — the forwarder's first read, the relay's
    upstream book, was a 403 — and its ingest's every poll read the source book refused. The books they read are the
    rec spec's `worker.reads` (the product's recorder reads them as `*` less its denials): the role `recworker` reads
    them, and the code reads nothing of the domain's books beyond them."""
    import tempfile
    from vms.domainpart.chain import Forwarder
    from vms.domainpart.ingest import should_from_snapshot
    from w2cplatform.objects import FsObjectStore
    from w2cplatform.variables import FileVariables, Forbidden
    r = rights()
    root = tempfile.mkdtemp()
    inner, read = FileVariables(f"{root}/vars"), []

    class AsRecorder:
        def get(self, path):
            read.append(path)
            if not r.allows("recworker", "read", path):
                raise Forbidden(f"recworker may not read {path}")
            return inner.get(path)

        def list(self, prefix):
            return [k for k in inner.list(prefix) if r.allows("recworker", "read", k)]

    class Local:
        def listen(self, fn):
            pass
    objects = FsObjectStore(f"{root}/objects")
    fw = Forwarder("relay-a", Local(), AsRecorder(), dial=lambda url: None, objects=objects)
    fw.book()
    fw.asks_book()
    should_from_snapshot(objects, sources=AsRecorder())("SN-A")
    books = {p for p in read if p.startswith("domain/vms/")}
    assert books == {"domain/vms/upstream", "domain/vms/asks", "domain/vms/sources"}, sorted(books)
    assert set(REC_SPEC.worker_reads) >= books, REC_SPEC.worker_reads
