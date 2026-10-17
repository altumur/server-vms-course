"""Lesson 12 — shared settings without a database.

Defaults, the folder tree, the scenarios between cameras: settings of the system, not of a camera. The
domain publishes them the way it publishes the identity set — one object, named by a pointer, object
first — signed, so that a copy anywhere is as good as the original, and carried by every member's agent
into that member's own durable store, where the member reads them with the domain gone.
"""

from tests.reporting import sync as report_sync
import json

from w2cplatform.cluster.variables import Conflict, FakeVariables
from w2cplatform.variables import items_bytes

from w2cplatform.domain.agent import DomainAgent, DomainPublisher
from vms.camera_cluster import DeviceCluster
from w2cplatform.domain.federation import Federation
from w2cplatform.domain.uplink import member_copy
from w2cplatform.domain.shared import OBJECT, POINTER, SharedSettings, SharedView, sign
from w2cplatform.trust.signer import Signer
from w2cplatform.trust.tokens import TokenIssuer
from vms.config import SPEC
from tests.domain.conftest import Clock, make_cluster


def _site(wall, n=3):
    fed = Federation()
    north, north_link = make_cluster("north", domain=True)
    fed.add(north)
    signer = Signer("acme", north.vars, now=wall)
    DomainPublisher(north.vars).publish_keys(signer.tokens.keyset())
    devices, agents = [], []
    for i in range(n):
        d = DeviceCluster(f"SN{i}", FakeVariables(), wall=wall)
        d.boot()
        fed.add(member_copy(d.name, north.objects, wall=wall))       # the domain reads its reports, never its door
        devices.append(d)
        agents.append(DomainAgent(d.name, north.vars, d.flash, now=wall, domain_objects=north.objects,
                                  cluster_objects=d.disk, published=d.local_objects()))
    shared = SharedSettings(north.vars, north.objects, signer.tokens, wall=wall)
    return fed, north, north_link, signer, shared, devices, agents


def _alarm_kinds(kind):
    return lambda s: s.setdefault("shared", {}).setdefault("cam", {}).update(alarms=[kind])


def test_published_once_carried_by_every_agent_and_the_console_says_where():
    """One edit, one object, one pointer. Every member's agent takes it on its next pass. The console
    shows delivery the way Lesson 9 shows kept edits — from each member's own report — and names the
    member that is not answering instead of rounding it into the total."""
    wall = Clock()
    fed, north, _, signer, shared, devices, agents = _site(wall)
    rev = shared.edit(_alarm_kinds("io.input"), base_rev=0, by="anna")
    devices[2].power_off()
    for a in agents[:2]:
        report_sync(a)
    d = shared.delivery(fed)
    assert d["holding"] == ["cam-SN0", "cam-SN1"] and d["silent"] == ["cam-SN2"]
    assert d["sentence"] == "rev 1 on 2 of 3 members; not answering: cam-SN2"

    devices[2].boot()
    report_sync(agents[2])
    assert shared.delivery(fed)["holding"] == ["cam-SN0", "cam-SN1", "cam-SN2"]
    assert SharedView(devices[2].flash, devices[2].disk, wall).settings()["shared"]["cam"]["alarms"] == ["io.input"] and rev == 1


def test_a_document_not_signed_by_the_domain_is_refused_and_the_old_one_kept():
    """Whoever can write the domain's store is not thereby the domain. A document signed by another key,
    with a pointer whose checksum matches it perfectly, is refused by every member — against the key set
    ITS agent carried, never one that came with the document — and the member keeps what it had. The
    refusal is reported, with its reason, where the domain reads it."""
    wall = Clock()
    fed, north, _, signer, shared, devices, agents = _site(wall)
    shared.edit(_alarm_kinds("io.input"), base_rev=0)
    for a in agents:
        report_sync(a)

    forged = sign({"rev": 2, "term": 1, "settings": {"shared": {"cam": {"alarms": ["tamper"]}}}}, TokenIssuer("acme"))
    raw = json.dumps(forged, sort_keys=True).encode()
    north.objects.put("shared/rev-2", raw)
    import hashlib
    _, idx = north.vars.get(POINTER)
    north.vars.put(POINTER, {"object": "shared/rev-2", "rev": 2, "term": 1, "sha256": hashlib.sha256(raw).hexdigest()}, cas=idx)
    report_sync(agents[0])
    assert agents[0].shared.startswith("refused") and "does not trust" in agents[0].shared
    assert SharedView(devices[0].flash, devices[0].disk, wall).settings()["shared"]["cam"]["alarms"] == ["io.input"]
    assert "cam-SN0" in shared.delivery(fed)["refused"]


def test_an_older_document_never_replaces_a_newer_one():
    """The pointer can go backwards — a domain restored from yesterday's backup points at yesterday's
    revision. A member that already holds a newer one keeps it: (term, rev) only ever grows on a member,
    whatever the domain says today. Lesson 15 is what makes the domain's own number grow again."""
    wall = Clock()
    fed, north, _, signer, shared, devices, agents = _site(wall, n=1)
    shared.edit(_alarm_kinds("io.input"), base_rev=0)
    ptr_rev1, _ = north.vars.get(POINTER)
    shared.edit(_alarm_kinds("motion"), base_rev=1)
    report_sync(agents[0])
    _, idx = north.vars.get(POINTER)
    north.vars.put(POINTER, ptr_rev1, cas=idx)           # the domain, restored from before rev 2
    report_sync(agents[0])
    assert agents[0].shared == "holding newer"
    assert SharedView(devices[0].flash, devices[0].disk, wall).settings()["shared"]["cam"]["alarms"] == ["motion"]


def test_a_default_is_resolved_when_read_and_never_written_into_a_row():
    """Shared alarm kinds are combined when read, without rewriting camera rows."""
    wall = Clock()
    fed, north, _, signer, shared, devices, agents = _site(wall, n=2)
    devices[1].update_unit(1, {"alarms": ["tamper"]}, None)
    before = [d.row()["revision"] for d in devices]
    shared.edit(_alarm_kinds("io.input"), base_rev=0)
    for a in agents:
        report_sync(a)
    assert [d.row()["revision"] for d in devices] == before
    eff = [SharedView(d.flash, d.disk, wall).effective(d.row(), SPEC)["alarms"] for d in devices]
    assert eff == [(["io.input"], "domain rev 1"), (["io.input", "tamper"], "unit + domain rev 1")]


def test_a_field_with_a_default_can_never_inherit_and_one_that_inherits_is_left_unset():
    """Scalar inheritance is a field contract; a pure example needs no camera setting."""
    from types import SimpleNamespace
    from w2cplatform.spec import Field, SubsystemSpec
    from w2cplatform.domain.shared import resolve
    field = Field("step", type="int", inherit=1, inherits=True)
    spec = SimpleNamespace(name="counter", fields={"step": field}, domain=SimpleNamespace(shared=["step"], documents={}))
    settings = {"shared": {"counter": {"step": 14}}}
    assert resolve(spec, {}, None, {})["step"] == (1, "spec")
    assert resolve(spec, settings, "domain rev 1", {})["step"] == (14, "domain rev 1")
    assert resolve(spec, settings, "domain rev 1", {"step": 30})["step"] == (30, "unit")
    field.default, field.inherits = 1, False
    assert resolve(spec, settings, "domain rev 1", {"step": 1})["step"] == (1, "unit")
    try:
        SubsystemSpec.from_dict({"name": "x", "unit": {"rows": "r", "id": "numeric", "fields": {
            "step": {"type": "int", "default": 1, "inherit": 1}}}})
        raise AssertionError("default and inherit on one field")
    except ValueError as e:
        assert "not both" in str(e)


def test_two_editors_of_the_shared_settings_are_told_not_overwritten():
    wall = Clock()
    fed, north, _, signer, shared, devices, agents = _site(wall, n=1)
    shared.edit(_alarm_kinds("io.input"), base_rev=0, by="anna")
    try:
        shared.edit(_alarm_kinds("tamper"), base_rev=0, by="boris")                     # boris was looking at rev 0
        raise AssertionError("boris must be told")
    except Conflict:
        pass
    assert shared.current()[0]["settings"]["shared"]["cam"]["alarms"] == ["io.input"]


def test_a_five_hundred_camera_tree_does_not_fit_a_variable_and_does_not_need_to():
    """Five hundred folders and five hundred scenarios are some eighty kilobytes: over the 64 KiB a Nomad
    Variable may hold, whole. The document is an object, so its size is the object store's business; the
    Variable is the pointer, and the pointer is a hundred bytes whatever the tree grows to."""
    wall = Clock()
    fed, north, _, signer, shared, devices, agents = _site(wall, n=1)

    def big(s):
        s.setdefault("shared", {}).setdefault("cam", {})["folders"] = [f"Site-{i // 100:02d}/Building-{i // 20 % 5}/Floor-{i // 5 % 4}/Zone-{i:03d}" for i in range(500)]
        s["shared"]["auto"] = {"scenarios": [{"name": f"s{i}", "when": {"camera": f"SN{i}", "kind": "motion"},
                                              "then": {"camera": f"SN{i + 1}", "action": "preset", "arg": 3}}
                                             for i in range(500)]}
    shared.edit(big, base_rev=0)
    assert items_bytes(shared.current()[0]["settings"]) > 65536
    assert items_bytes(north.vars.get(POINTER)[0]) < 200
    report_sync(agents[0])
    assert len(SharedView(devices[0].flash, devices[0].disk, wall).settings()["shared"]["cam"]["folders"]) == 500


def test_with_the_domain_gone_a_camera_that_reboots_still_has_its_defaults():
    """The thesis, for settings: the domain can be switched off and nothing below notices. The document is
    in the camera's durable store, checked again on the way in, and a reboot changes nothing."""
    wall = Clock()
    fed, north, north_link, signer, shared, devices, agents = _site(wall, n=1)
    shared.edit(_alarm_kinds("io.input"), base_rev=0)
    report_sync(agents[0])
    north_link.up = False
    assert report_sync(agents[0]) is False
    devices[0].power_off(); devices[0].boot()
    assert SharedView(devices[0].flash, devices[0].disk, wall).effective(devices[0].row(), SPEC)["alarms"] == (["io.input"], "domain rev 1")
    assert devices[0].disk.get(OBJECT) is not None


def test_the_agent_a_unit_starts_keeps_the_shared_settings_and_the_backup_in_its_clusters_objects():
    """The scenario «камера — офис — центр», O5: `agent.main` — the agent a unit starts — built its `DomainAgent` with no
    `cluster_objects`, and the steps «the shared settings» and «the backup» run only with it: a unit's agent never carried
    home the settings the domain signed (ADR-0032) nor the copy of the domain the holder chose it to keep; only the tests
    gave it one. Its cluster's object store (`OBJECTS`) is where it keeps them."""
    import os
    import signal
    import tempfile
    from w2cplatform.domain import agent as agent_mod
    root = tempfile.mkdtemp()
    env = {"CLUSTER": "relay-b", "PLATFORM_STORE": f"file://{root}/vars", "OBJECTS": f"{root}/objects",
           "DOMAIN_URL": "http://127.0.0.1:9", "SYNC_INTERVAL": "3600"}
    made, saved = [], {k: os.environ.get(k) for k in (*env, "REPORT", "RELAY_URL", "RELAY", "RELAY_MEMBERS", "CLUSTERS")}
    real_run = agent_mod.run
    handlers = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT)}
    try:
        for k in saved:
            os.environ.pop(k, None)
        os.environ.update(env)
        agent_mod.run = lambda agent, interval, stop: made.append(agent)
        agent_mod.main()
    finally:
        agent_mod.run = real_run
        for s, h in handlers.items():
            signal.signal(s, h)
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    (agent,) = made
    assert agent.cluster_objects is not None and agent.cluster_objects is agent.own_objects
    agent.cluster_objects.put("probe", b"x")
    assert os.path.exists(os.path.join(root, "objects", "probe"))
