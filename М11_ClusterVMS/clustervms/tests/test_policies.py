"""The policies and the code say the same thing, and a test says so.

Variables have had an ACL since М10A Lesson 1, and it is derived from the spec:
`acl_controller()`, `acl_console()`, `acl_worker()`. The OBJECT STORE never had
one. On one box that is invisible — `FsObjectStore` has no writer and no prefixes
— and on a cluster the ACL is real, enforced by the scheduler, but written by
hand in `deploy/*-policy.hcl`.

Nothing checked that the hand-written file still matched the code, and inside two
commits it stopped matching three times:

  * the controller's grant named `objects/vms/snapshot` exactly, and the snapshot
    became one object per worker — every shard a 403, every five seconds, logged
    as "placement pass failed";
  * the console got a `blob` route and no grant to write `objects/vms/blobs/*`,
    so the route could not work on a cluster at all;
  * the rec controller never had a grant for its own snapshot, from the day it
    was written.

None of the three is subtle. All three were invisible because the suite runs
against a store with no ACL, and the file with the ACL is not code.

So: the grants are derived from the spec (`acl_objects_*`), and this checks each
policy against them in BOTH directions — everything the code writes is allowed,
and nothing else is.
"""
import os
import re

from vms.config import REC_SPEC, SPEC, WORKER_ACL, WORKER_OBJECTS
from w2cplatform.blobs import digest

DEPLOY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "deploy")
OBJECTS = "objects/"                       # VariablesObjectStore's prefix: an object IS a Variable here

_RULE = re.compile(r'path\s+"([^"]+)"\s*\{\s*capabilities\s*=\s*\[([^\]]*)\]', re.S)


def rules(policy: str) -> list[tuple[str, set[str]]]:
    """`[(path pattern, capabilities)]` in file order, which is the order Nomad reads them."""
    src = open(os.path.join(DEPLOY, policy), encoding="utf-8").read()
    return [(p, {c.strip().strip('"') for c in caps.split(",") if c.strip()}) for p, caps in _RULE.findall(src)]


def matches(pattern: str, key: str) -> bool:
    """Nomad's glob: `*` stands for any run of characters, and a pattern with no
    `*` is an EXACT path. That second half is the whole of the first bug — a
    pattern naming `objects/vms/snapshot` does not match `objects/vms/snapshot/w-1`."""
    return re.fullmatch(re.escape(pattern).replace(r"\*", ".*"), key) is not None


def may_write(policy: str, key: str) -> bool:
    return any("write" in caps for pat, caps in rules(policy) if matches(pat, key))


def write_patterns(policy: str) -> set[str]:
    return {pat for pat, caps in rules(policy) if "write" in caps}


def _keys(prefixes: list[str], sample: str) -> list[str]:
    """A concrete key under each granted prefix — a pattern is checked by what it
    has to match, not by comparing two strings that look alike."""
    return [OBJECTS + (p[:-1] + sample if p.endswith("*") else p) for p in prefixes]   # an exact path is itself


def test_every_object_the_code_writes_is_granted():
    """Direction one, from the code's own lists: a concrete key under each prefix the spec says a process writes."""
    cases = [
        ("vmsworker-policy.hcl", _keys(WORKER_OBJECTS, "w-1")),          # its heartbeat, and the mark it leaves before a command
        ("recworker-policy.hcl", _keys(REC_SPEC.sub.acl_objects_worker(), "r-1")),
        ("vmscontroller-policy.hcl", _keys(SPEC.sub.acl_objects_controller(), "w-1")
                                     + _keys(SPEC.sub.acl_objects_controller(), "unplaced")),
        ("reccontroller-policy.hcl", _keys(REC_SPEC.sub.acl_objects_controller(), "r-1")),
        ("console-policy.hcl", _keys(SPEC.sub.acl_objects_console(), digest(b"a mask"))
                               + _keys(REC_SPEC.sub.acl_objects_console(), digest(b"a mask"))),
    ]
    for policy, keys in cases:
        for key in keys:
            assert may_write(policy, key), f"{policy} does not let it write {key}"


def test_every_row_the_code_writes_is_granted_too():
    """The same direction for Variables, which the first version of this file left
    out — and left out is how `<sub>/sweep` got added to `acl_console()` with no
    line in the policy: the console would have been refused its own bookkeeping the
    first time the blob sweep ran on a cluster. The gap was the same shape as the
    three this file was written for."""
    cases = [
        ("vmsworker-policy.hcl", WORKER_ACL, ["w-1"]),                  # the platform's grant + what a device is
        ("recworker-policy.hcl", REC_SPEC.sub.acl_worker(), ["r-1"]),
        ("vmscontroller-policy.hcl", SPEC.acl_controller(), ["7"]),
        ("reccontroller-policy.hcl", REC_SPEC.acl_controller(), ["7"]),
        ("console-policy.hcl", SPEC.acl_console() + REC_SPEC.acl_console(), ["7"]),
    ]
    for policy, prefixes, samples in cases:
        for pre in prefixes:
            for key in ([pre.rstrip("*") + s for s in samples] if pre.endswith("*") else [pre]):
                assert may_write(policy, key), f"{policy} does not let it write {key}"


def test_nothing_writes_an_object_it_has_no_business_writing():
    """Direction two, and the one that costs something to keep true: a grant wider
    than the code needs is how a worker ends up able to write М12's directory."""
    denied = [
        # a worker writes its own heartbeat and nothing else in the subsystem
        ("vmsworker-policy.hcl", OBJECTS + "vms/snapshot/w-1"),
        ("vmsworker-policy.hcl", OBJECTS + "vms/blobs/" + digest(b"a mask")),
        ("recworker-policy.hcl", OBJECTS + "rec/snapshot/r-1"),
        # the controller publishes the snapshot and touches neither of the others
        ("vmscontroller-policy.hcl", OBJECTS + "vms/heartbeats/w-1"),
        ("vmscontroller-policy.hcl", OBJECTS + "vms/blobs/" + digest(b"a mask")),
        # the console owns the rows and the blobs, never a heartbeat or a shard
        ("console-policy.hcl", OBJECTS + "vms/heartbeats/w-1"),
        ("console-policy.hcl", OBJECTS + "vms/snapshot/w-1"),
        # and the resource stays inside its own prefix
        ("resource-policy.hcl", OBJECTS + "vms/heartbeats/w-1"),
        ("resource-policy.hcl", OBJECTS + "vms/snapshot/w-1"),
    ]
    for policy, key in denied:
        assert not may_write(policy, key), f"{policy} lets it write {key}"


def test_every_write_grant_is_one_the_code_asked_for():
    """The strongest half: no rule in the file that nothing in the code explains.
    This is what `objects/vms/*` would fail — the grant the worker had until now,
    whose comment said "its heartbeat" while the pattern said the whole subsystem."""
    expected = {
        "vmsworker-policy.hcl": set(WORKER_ACL) | {OBJECTS + p for p in WORKER_OBJECTS},
        "recworker-policy.hcl": set(REC_SPEC.sub.acl_worker()) | {OBJECTS + p for p in REC_SPEC.sub.acl_objects_worker()},
        "vmscontroller-policy.hcl": set(SPEC.acl_controller()) | {OBJECTS + p for p in SPEC.sub.acl_objects_controller()},
        "reccontroller-policy.hcl": set(REC_SPEC.acl_controller()) | {OBJECTS + p for p in REC_SPEC.sub.acl_objects_controller()},
        "console-policy.hcl": set(SPEC.acl_console()) | set(REC_SPEC.acl_console())
                              | {OBJECTS + p for p in SPEC.sub.acl_objects_console()}
                              | {OBJECTS + p for p in REC_SPEC.sub.acl_objects_console()},
    }
    for policy, allowed in expected.items():
        unexplained = write_patterns(policy) - allowed
        assert not unexplained, f"{policy} grants write to {sorted(unexplained)}, which no acl_* in the spec asks for"


# -- READS (М10's eighth review, the sweep of the three-cameras notes) -----------------------------------------------
# The file checked writes only, and the stand enforces no read ACL: the console's gate reads `domain/keys` and the rows
# that mark a member on every request, the holder's playback door the same, and every process `platform/schema` when
# it starts — and no policy but the console's let anybody read `platform/*`, and none `domain/*`. On a real Nomad each
# of those is a 403: the gate fails shut, the schema check fails. So the reads are checked against the code too, the way
# the writes are: every read the processes MAKE — the module's stand, every scene, under each process's own name, and
# the doors the scenes do not knock on — is granted by that process's policy; and the cluster's key is read by the
# three jobs that open a device's password and by nobody else.
def may(policy: str, cap: str, key: str) -> bool:
    return any(cap in caps for pat, caps in rules(policy) if matches(pat, key))


ROLES = {"console": "console-policy.hcl", "vmsworker": "vmsworker-policy.hcl", "recworker": "recworker-policy.hcl",
         "resource": "resource-policy.hcl", "vmscontroller": "vmscontroller-policy.hcl",
         "reccontroller": "reccontroller-policy.hcl"}


def _doors(s) -> None:
    """What the scenes do not do: a request at the console's door and at the holder's playback door (each asks its
    gate), and the recorder controller's passes."""
    import urllib.error
    import urllib.request
    from cluster.console import serve
    from cluster.worker import ClusterWorker
    from vms.worker import FakeActuator, FakeDevice
    from w2cplatform.spec import SpecController
    s.resources_up()
    from cluster.controller import ClusterController
    v, o = s.as_process("console (gate)", "console", SPEC.acl_console() + REC_SPEC.acl_console())
    con, ctl = ClusterController(v, o, wall=s.wall), s.controller()
    con.create_camera({"source": "driverpack://acme/10.0.0.50/ch/1"})
    dev = FakeDevice("acme/10.0.0.50", channels=["1"], coverage={"1": (0.0, 100.0)})
    v, o = s.as_process("vmsworker (allocation 0 on srv-a)", "vmsworker-0", WORKER_ACL + [OBJECTS + p for p in WORKER_OBJECTS])
    w = ClusterWorker(v, o, FakeActuator(), env=s.env(0, "srv-a"), clock=s.clock, wall=s.wall, device_factory=lambda k: dev)
    w.heartbeat_once(); ctl.ensure_placed(); w.reconcile_once(); w.heartbeat_once()
    door = w.serve_playback("127.0.0.1", 0)
    rec_con = SpecController(REC_SPEC, con.vars, con.objects, wall=s.wall)
    srv = serve(con, port=0, rec_ctl=rec_con)
    try:
        for url in (f"http://127.0.0.1:{door.server_address[1]}/playback/1?from=0&to=1",
                    f"http://127.0.0.1:{srv.server_address[1]}/cameras"):
            with urllib.request.urlopen(url) as r:
                r.read()
        # What a server reaches, from the console (feedback DQ): the row written, removed and written again — so the
        # controllers' passes below read one — for the camera's subsystem and the recorder's.
        for path in ("/servers/srv-a/labels", "/rec/servers/srv-a/labels"):
            for method in ("PUT", "DELETE", "PUT"):
                req = urllib.request.Request(f"http://127.0.0.1:{srv.server_address[1]}{path}", method=method,
                                             data=b'{"labels": ["vlan:cctv-a"]}' if method == "PUT" else None,
                                             headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req) as r:
                    r.read()
        # A machine gone for good (М10A Lesson 7, step 7): its server goes silent, the console writes
        # `platform/decommission/srv-a` — and deletes it and writes it again, so `DELETE` is exercised too — and the
        # controllers' passes below read it, release the slot on that server and write their marks
        # (`<sub>/decommissioned/srv-a`).
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
    v, o = s.as_process("reccontroller", "reccontroller",
                        REC_SPEC.acl_controller() + [OBJECTS + p for p in REC_SPEC.sub.acl_objects_controller()])
    rc = SpecController(REC_SPEC, v, o, wall=s.wall)
    rc.ensure_placed(); rc.redistribute(); rc.ensure_home(1); rc.unplace_deleted()
    # The pass as the loops run it (`cluster/__main__._placement_pass`): it writes its report (`<sub>/controller/pass`)
    # — the write no policy granted, and no scene made (the review's ninth pass) — and then the snapshot.
    for c in (ctl, rc):
        c.pass_once(1); c.publish_snapshot()
    assert ctl.slots()[w.name].released and ctl.decommission_marks()       # the row was read, the slot released, the mark written


# The scenes whose point is a write the store refuses: their 403 is the lesson, not the code writing outside its grant.
REFUSED_ON_PURPOSE = ("a_worker_may_not_write_a_camera", "who_may_write_what")


def code_calls() -> tuple[dict[str, set[tuple[str, str]]], dict[str, set[tuple[str, str, int]]]]:
    """`({policy: {("read" | "list", path)}}, {policy: {("PUT" | "DELETE", path, status)}})`: every read and every write
    of the store each process made — the module's stand, every scene, under each process's own name, and `_doors`."""
    from urllib.parse import unquote
    import tests.stand as stand
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
            role = c.who.split()[0]
            if c.who == "console" or role not in ROLES:
                continue                                 # `console` alone is the scene's own hand, not a process
            if c.method == "GET":
                if c.url.startswith("/v1/vars?prefix="):
                    op, path = "list", unquote(c.url[len("/v1/vars?prefix="):].split("&", 1)[0])
                else:
                    op, path = "read", unquote(c.url[len("/v1/var/"):].split("?", 1)[0])
                reads.setdefault(ROLES[role], set()).add((op, path))
            elif scene not in REFUSED_ON_PURPOSE:
                path = unquote(c.url[len("/v1/var/"):].split("?", 1)[0])
                writes.setdefault(ROLES[role], set()).add((c.method, path, c.status))
    return reads, writes


def code_reads() -> dict[str, set[tuple[str, str]]]:
    """`{policy: {("read" | "list", path)}}`: every read of the store each process made."""
    return code_calls()[0]


def test_every_write_the_code_makes_is_granted():
    """THE WRITES AS THE PROCESSES MAKE THEM (the review's ninth pass, major). The checks above compared the policy files
    with the spec's `acl_*` lists — which are written by hand too: the controller's pass wrote its report to
    `objects/<sub>/controller/pass`, no list named it, the policy did not grant it, and every check here agreed. On a
    cluster with an ACL that was `Forbidden` every five seconds and `<sub>_units_unplaced` 0 for ever. So: every PUT and
    DELETE a process made in the stand — every scene, and the passes and doors the scenes do not run — is allowed by
    that process's policy; and the stand refused none of them (a 403 there is the stand's grants and the code
    disagreeing, the same drift one level down), except in the scenes whose point is the refusal."""
    _, writes = code_calls()
    assert {"vmsworker-policy.hcl", "recworker-policy.hcl", "vmscontroller-policy.hcl", "reccontroller-policy.hcl",
            "console-policy.hcl", "resource-policy.hcl"} <= set(writes), sorted(writes)
    refused, outside = [], []
    for policy, made in sorted(writes.items()):
        for method, path, status in sorted(made):
            if status == 403:
                refused.append(f"{policy}: {method} {path}")
            if not may(policy, "write", path):
                outside.append(f"{policy}: {method} {path}")
    assert not outside, "the code writes what its policy does not grant:\n" + "\n".join(outside)
    assert not refused, "the stand refused a write the code made:\n" + "\n".join(refused)


def test_every_row_the_code_reads_is_granted():
    """Direction one, for reads: every GET and every listing a process made in the stand is allowed by its policy."""
    reads = code_reads()
    assert set(reads) == set(ROLES.values()), sorted(set(ROLES.values()) - set(reads))   # every process was run
    for policy, made in sorted(reads.items()):
        for op, path in sorted(made):
            key = path + "x" if op == "list" else path   # a listing is of a prefix: what lies under it
            assert may(policy, op, key), f"{policy} does not let it {op} {path}"


def test_the_gate_and_the_schema_are_readable_by_every_process_that_asks_them():
    """The same from the code's constants, for what the stand reaches only in part: the gate asks for the key set and
    every row that marks a member (`TRUST_KEYS`, `DOMAIN_MARKS`) at the console and at the holder's door; a domain's
    image reads the grants by cluster (`domain/grants/<cluster>`); every process checks `platform/schema` first."""
    from w2cplatform.access import DOMAIN_MARKS, MEMBER_MARK, TRUST_KEYS
    from w2cplatform.contract import SCHEMA_KEY
    for key in (TRUST_KEYS, *DOMAIN_MARKS, "domain/grants/acme"):
        assert may("console-policy.hcl", "read", key), f"console-policy.hcl does not let it read {key}"
    for key in (TRUST_KEYS, MEMBER_MARK):                # the holder's door verifies no token (`Gate.gated`)
        assert may("vmsworker-policy.hcl", "read", key), f"vmsworker-policy.hcl does not let it read {key}"
    for policy in set(ROLES.values()):
        assert may(policy, "read", SCHEMA_KEY), f"{policy} does not let it read {SCHEMA_KEY}"


def test_the_holder_reads_no_more_of_the_domain_than_its_door_asks():
    """М10's ninth review, minor: the holder's policy granted every row that marks a member — the grants and
    `domain/break_glass`, the emergency password's hash, among them — while its playback door verifies no token and asks
    only whether the cluster is in a domain (`Gate.gated`: the key set, and `domain/member` while there is none). Not
    wider than the code: the policy's `domain/*` is exactly those two rows, and what the door read in the stand is in
    them."""
    import tempfile
    from vms.worker import FakeActuator, VmsWorker
    from w2cplatform.access import MEMBER_MARK, TRUST_KEYS
    from w2cplatform.objects import FsObjectStore
    from w2cplatform.variables import FileVariables
    granted = {pat for pat, caps in rules("vmsworker-policy.hcl") if pat.startswith("domain") and caps & {"read", "list"}}
    assert granted == {TRUST_KEYS, MEMBER_MARK}, sorted(granted)
    root = tempfile.mkdtemp()
    vars_, read = FileVariables(f"{root}/vars"), []
    real = vars_.get
    vars_.get = lambda path: (read.append(path), real(path))[1]
    w = VmsWorker("w-1", vars_, FsObjectStore(f"{root}/objects"), FakeActuator(), archive_root=f"{root}/archive")
    assert w.playback_refusal("1", "", {}, "127.0.0.1") is None        # an open cluster: the door asks nobody
    vars_.put(MEMBER_MARK, {"cluster": "acme"})                       # a member that lost its keys: it asks
    assert w.playback_refusal("1", "", {}, "127.0.0.1")[0] == 503      # …and has no key of its own yet: shut
    made = {p for p in read if p.startswith("domain")}
    assert made == {TRUST_KEYS, MEMBER_MARK}, sorted(made)


def test_the_clusters_key_is_read_by_the_three_jobs_that_open_a_password_and_nobody_else():
    """`secrets/vms` — the console seals, the holder and the recorder open (`w2cplatform/sealing.py`). The controllers
    had `path "*"` read, which reads it too, against the console's own comment; they read what they read now."""
    for policy in ROLES.values():
        opens = policy in ("console-policy.hcl", "vmsworker-policy.hcl", "recworker-policy.hcl")
        assert may(policy, "read", "secrets/vms") == opens, policy
        assert all(pat != "*" for pat, _ in rules(policy)), f"{policy} still reads everything"


def test_the_exact_path_that_broke_it_stays_broken_as_a_pattern():
    """Kept as a named case because it cost nothing to write and would have cost a
    production morning: Nomad's path is a glob, and a glob without a `*` is exact."""
    assert matches("objects/vms/snapshot/*", "objects/vms/snapshot/w-1")
    assert not matches("objects/vms/snapshot", "objects/vms/snapshot/w-1")
    assert matches("objects/vms/*", "objects/vms/snapshot/w-1")          # why the old worker grant was too wide
