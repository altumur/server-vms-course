"""Every connection between a member and the domain is opened by the member (`domain/uplink.py`).

The cameras here are NEVER reachable from the domain: none of them is added to the federation by its door.
The domain reads its own cluster's store and nothing else; each camera's agent, on the pass it already makes,
carries rows home and leaves a report. Everything a domain does with its members — the list, "where", a kept
edit and what became of it, the delivery of shared settings, the alarms, the books of Lesson 13 — works from
the reports, and a member's silence is the age of its last one.
"""
import json

from cluster.variables import FakeVariables

from domain.agent import DomainAgent, DomainPublisher
from domain.alarms import Card, DomainAlarms, ReportedDoor, pages
from domain.api import ConsoleAPI
from domain.device import DeviceCluster
from domain.federation import DomainDirectory, Federation, Unreachable
from domain.grants import Grant
from domain.pending import PendingEdits
from domain.readview import ReadView
from domain.shared import SharedSettings
from domain.signer import Signer
from domain.uplink import UPLINK, member_copy, reported_at
from tests.conftest import Clock, make_cluster

NOW = 1_001_000.0


def _site(wall, n=2, nets=None):
    """A domain holder, and cameras the domain cannot open a connection to. Each is in the federation only as
    the copy its own reports make."""
    fed = Federation()
    north, _ = make_cluster("north", domain=True)
    fed.add(north)
    signer = Signer("acme", north.vars, now=wall)
    DomainPublisher(north.vars).publish_keys(signer.tokens.keyset())
    devices, agents, cards = {}, {}, {}
    for i in range(n):
        d = DeviceCluster(f"SN{i}", FakeVariables(), wall=wall, reaches=((nets or ["vlan:a"] * n)[i],))
        d.boot(first_name=f"gate-{i}")
        cards[d.name] = Card()
        fed.add(member_copy(d.name, north.objects, d.reaches, wall=wall))
        devices[d.name] = d
        agents[d.name] = DomainAgent(d.name, north.vars, d.flash, now=wall, console=d, current=d.current,
                                     domain_objects=north.objects, cluster_objects=d.disk,
                                     published=d.local_objects(),
                                     pages=lambda d=d: pages(cards[d.name], wall()))
    return fed, north, signer, devices, agents, cards


def _pass(agents, *skip):
    for name, a in agents.items():
        if name not in skip:
            a.sync()


def test_the_domain_lists_and_finds_cameras_it_has_never_reached():
    wall = Clock(NOW)
    fed, north, _, devices, agents, _ = _site(wall)
    view = ReadView(fed, wall=wall)
    view.refresh()
    assert view.list()["total"] == 0 and not view.list()["complete"]          # nothing reported yet: said, not assumed

    _pass(agents)
    view.refresh()
    rows = view.list()
    assert rows["total"] == 2 and rows["complete"]
    assert {(r["ref"], r["worker_state"]) for r in rows["rows"]} == {("SN0", "live"), ("SN1", "live")}
    ans = DomainDirectory(fed, wall=wall).where("SN1")
    assert (ans.cluster, ans.worker, ans.complete) == ("cam-SN1", "SN1", True)
    assert all(k.startswith(UPLINK + "/") for k in north.objects.list(UPLINK))    # all of it in the domain's own store


def test_a_camera_that_has_not_published_does_not_report():
    """Lesson 10's ordering rule, on the report: before its first publish a camera would report no cameras —
    a complete answer the domain must believe. So it reports nothing, and the domain says it has not heard."""
    wall = Clock(NOW)
    north, _ = make_cluster("north", domain=True)
    d = DeviceCluster("SN9", FakeVariables(), wall=wall)                       # not booted: nothing published
    agent = DomainAgent(d.name, north.vars, d.flash, now=wall, domain_objects=north.objects, published=d.local_objects())
    assert agent.sync() and "has not published" in agent.reported
    assert reported_at(d.name, north.objects) is None
    try:
        member_copy(d.name, north.objects, wall=wall).snapshot()
        assert False
    except Unreachable as e:
        assert "never reported" in str(e)


def test_silence_is_the_age_of_the_last_report():
    wall = Clock(NOW)
    fed, north, _, devices, agents, _ = _site(wall)
    _pass(agents)
    view = ReadView(fed, wall=wall)
    view.refresh()
    wall.advance(60)
    _pass(agents, "cam-SN1")                                                    # SN1 stops reaching the domain
    view.refresh()
    page = view.list()
    assert not page["complete"] and page["clusters"]["cam-SN1"] == "unreachable"
    kept = [r for r in page["rows"] if r["ref"] == "SN1"]
    assert kept and kept[0]["worker_state"] == "unreachable"                    # last known, named as such
    assert "cam-SN1 unreachable" in DomainDirectory(fed, wall=wall).where("SN1").sentence()


def test_an_edit_for_a_camera_the_domain_cannot_reach_is_kept_carried_applied_and_its_outcome_reported():
    """Lesson 9 is the only way an edit reaches such a camera, and it needs nothing new: the forward meets
    silence (there is no door to forward to), the edit is kept beside the camera's grants, the camera's agent
    carries it home on its next pass, its console applies it as the operator — and the outcome goes up in the
    same pass's report, where the domain collects it."""
    wall = Clock(NOW)
    fed, north, _, devices, agents, _ = _site(wall, n=1)
    d = devices["cam-SN0"]
    DomainPublisher(north.vars).publish_grants(d.name, [Grant("anna", "edit", None, wall() + 3600)])
    _pass(agents)
    view = ReadView(fed, wall=wall); view.refresh()
    pending = PendingEdits(north.vars, wall)

    def no_door(name):
        raise Unreachable(f"{name} is reached only by its own agent")

    api = ConsoleAPI(DomainDirectory(fed, wall=wall), no_door, verifier=lambda t: t, pending=pending,
                     last_known=view.last_known)
    out = api.update_camera("SN0", {"name": "main-gate"}, idempotency_key="k1", token="anna")
    assert out["pending"] and d.row()["name"] == "gate-0"                     # kept, not applied
    agents[d.name].sync()                                                      # the camera's next pass
    assert d.row()["name"] == "main-gate"
    pending.collect(fed)                                                       # from the report, not the camera
    assert pending.of(d.name) == {}


def test_shared_settings_delivery_is_read_from_what_members_reported():
    wall = Clock(NOW)
    fed, north, signer, devices, agents, _ = _site(wall, n=3)
    shared = SharedSettings(north.vars, north.objects, signer.tokens, wall=wall)
    shared.edit(lambda s: s.setdefault("defaults", {}).update(events_retention_days=14), base_rev=0, by="anna")
    _pass(agents, "cam-SN2")
    wall.advance(60)
    _pass(agents, "cam-SN2")
    report = shared.delivery(fed)
    assert sorted(report["holding"]) == ["cam-SN0", "cam-SN1"] and report["silent"] == ["cam-SN2"]


def test_alarms_come_from_the_pages_members_report_and_a_silent_ones_from_its_last_report():
    wall = Clock(NOW)
    fed, north, _, devices, agents, cards = _site(wall, n=2)
    cards["cam-SN0"].observe(1, NOW - 1500, "door_forced", alarm=True)
    cards["cam-SN1"].observe(1, NOW - 100, "tamper", alarm=True)
    _pass(agents)
    doors = lambda name: ReportedDoor(name, north.objects, wall=wall)
    out = DomainAlarms(fed, doors, wall).list(since=NOW - 3600)
    assert [(e["member"], e["kind"]) for e in out["events"]] == [("cam-SN1", "tamper"), ("cam-SN0", "door_forced")]
    assert out["complete"]

    wall.advance(60)
    _pass(agents, "cam-SN0")                                                   # SN0 goes quiet
    out = DomainAlarms(fed, doors, wall).list(since=NOW - 3600)
    assert out["members"]["cam-SN0"]["state"] == "last_report"
    assert [(e["member"], e["kind"]) for e in out["events"] if e["member"] == "cam-SN0"] == [("cam-SN0", "silent"), ("cam-SN0", "door_forced")]

def test_the_domain_cannot_write_into_a_member_and_needs_no_door():
    """What the domain wants of a member is a row its agent takes home; the copy refuses writes, and nothing
    in these passes used a camera's door — none was ever handed to the domain."""
    wall = Clock(NOW)
    fed, north, _, devices, agents, _ = _site(wall, n=1)
    _pass(agents)
    c = fed.clusters["cam-SN0"]
    for write in (lambda: c.vars.put("vms/cameras/1", {"name": "x"}), lambda: c.objects.put("vms/snapshot/x", b"{}")):
        try:
            write()
            assert False
        except PermissionError:
            pass
    assert json.loads(c.objects.get("vms/snapshot/SN0"))["cluster"] == "cam-SN0"


def test_a_camera_whose_clock_is_wrong_is_neither_stale_for_ever_nor_never_stale():
    """A camera's clock is not the domain's. Its report's age is counted by the DOMAIN's clock, from when the
    domain first saw it, and the times inside it are moved onto the domain's clock by the difference. A
    camera fifteen minutes slow is live while it reports and silent when it stops, like any other."""
    from domain.uplink import offset_of
    wall = Clock(NOW)
    slow = Clock(NOW - 900)                                                     # the camera's own clock
    north, _ = make_cluster("north", domain=True)
    fed = Federation(); fed.add(north)
    d = DeviceCluster("SN7", FakeVariables(), wall=slow)
    d.boot()
    fed.add(member_copy(d.name, north.objects, wall=wall))
    agent = DomainAgent(d.name, north.vars, d.flash, now=slow, domain_objects=north.objects, published=d.local_objects())
    agent.sync()
    view = ReadView(fed, wall=wall)
    view.refresh()
    [row] = view.rows()
    assert row.worker_state == "live" and row.age < 1                          # not fifteen minutes stale
    assert round(offset_of(fed.clusters[d.name])) == 900                        # and the difference is shown

    for _ in range(3):                                                          # it keeps reporting
        wall.advance(20); slow.advance(20); d.publish(); agent.sync(); view.refresh()
    assert view.rows()[0].worker_state == "live"
    wall.advance(60); slow.advance(60); view.refresh()                          # it stops
    assert view.list()["clusters"][d.name] == "unreachable"


def test_a_cluster_with_no_cameras_yet_reports_that_it_has_none():
    """Feedback AA, on the report. A server room nobody has given a camera yet runs its controller once and
    publishes an empty `unplaced` shard; its agent reports; the domain lists it as a member that answered
    with nothing — complete — and not as one that never reported."""
    from cluster.controller import ClusterController
    wall = Clock(NOW)
    north, _ = make_cluster("north", domain=True)
    south, _ = make_cluster("south")
    fed = Federation(); fed.add(north)
    fed.add(member_copy("south", north.objects, wall=wall))
    ClusterController(south.vars, south.objects, wall=wall, cluster="south").publish_snapshot()
    agent = DomainAgent("south", north.vars, south.vars, now=wall, domain_objects=north.objects, published=south.objects)
    assert agent.sync() and agent.reported.startswith("reported")
    view = ReadView(fed, wall=wall); view.refresh()
    page = view.list()
    assert page["total"] == 0 and page["complete"] and page["clusters"]["south"] == "ok"
