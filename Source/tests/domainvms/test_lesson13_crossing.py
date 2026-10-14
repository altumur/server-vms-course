"""Assigned recording observations cross clusters; work and ownership stay local."""
import json

from tests.reporting import sync
from tests.domain.conftest import Clock, make_cluster
from tests.domainvms.recording_domain import RecordingDomain
from vms.domainpart.device import DeviceCluster
from vms.domainpart.inputs import BookInputs
from vms.recording_books import primary, source
from vms.recording_sources import NotResolvable, plan_backfill, resolve
from w2cplatform.cluster.variables import FakeVariables
from w2cplatform.domain.agent import DomainAgent, DomainPublisher
from w2cplatform.domain.api import ApiError
from w2cplatform.domain.federation import Federation
from w2cplatform.domain.readview import ReadView
from w2cplatform.domain.uplink import member_copy
from w2cplatform.trust.signer import Signer

SERIAL = "SN4471"


def _site(wall):
    fed = Federation()
    north, link = make_cluster("north", domain=True)
    south, _ = make_cluster("south")
    fed.add(north); fed.add(south)
    signer = Signer("acme", north.vars, now=wall)
    DomainPublisher(north.vars).publish_keys(signer.tokens.keyset())
    cam = DeviceCluster(SERIAL, FakeVariables(), wall=wall, address="10.1.0.71")
    cam.boot()
    fed.add(member_copy(cam.name, north.objects, wall=wall))
    ca = DomainAgent(cam.name, north.vars, cam.flash, now=wall,
        domain_objects=north.objects, published=cam.local_objects())
    sa = DomainAgent("south", north.vars, south.vars, now=wall)
    view = ReadView(fed, wall=wall)
    inputs = BookInputs(north.vars, view, wall)
    books = RecordingDomain(inputs, signer, agents=[ca, sa], devices=[cam])
    return fed, link, south, cam, books, sa, ca


def test_the_recorder_reads_a_source_from_the_assigned_origin_and_its_typed_envelope():
    wall = Clock()
    _, _, south, cam, books, _, _ = _site(wall)
    books.assign(SERIAL, "south"); books.collect()
    got = source(south.vars.get("domain/cam/sources")[0], SERIAL)
    assert got.member == cam.name and got.value["to"] == ["south"]
    assert (resolve(south.vars, "ref:" + SERIAL, wall()).cluster,
            got.value["live_url"]) == (cam.name, "rtsp://10.1.0.71/live")
    assert resolve(south.vars, "rtsp://local/201", wall()) is None
    assert "token" not in json.dumps(got.value)


def test_assignment_validates_members_and_reassignment_has_one_authoritative_revision():
    wall = Clock()
    _, _, _, _, books, _, _ = _site(wall)
    first = books.assign(SERIAL, "south")
    assert books.assign(SERIAL, "south") == first
    try:
        books.assign(SERIAL, "unknown")
    except ApiError as e:
        assert e.status == 400
    else:
        raise AssertionError("unadmitted receiver was accepted")
    moved = books.assign(SERIAL, "north")
    assert moved["rev"] > first["rev"] and moved["cluster"] == "north"


def test_carried_source_survives_a_domain_outage_and_reports_its_age():
    wall = Clock()
    _, link, south, _, books, sa, _ = _site(wall)
    books.assign(SERIAL, "south"); books.collect()
    link.up = False; wall.advance(6 * 3600)
    assert sync(sa) is False
    src = resolve(south.vars, "ref:" + SERIAL, wall())
    assert src.live_url == "rtsp://10.1.0.71/live" and src.age >= 6 * 3600


def test_address_changes_are_visible_after_a_new_complete_signed_publication():
    wall = Clock()
    _, link, south, cam, books, _, _ = _site(wall)
    books.assign(SERIAL, "south"); books.collect()
    link.up = False
    cam.address = "10.1.0.99"; cam.publish()
    assert resolve(south.vars, "ref:" + SERIAL, wall()).live_url == "rtsp://10.1.0.71/live"
    link.up = True; wall.advance(1); books.collect()
    assert resolve(south.vars, "ref:" + SERIAL, wall()).live_url == "rtsp://10.1.0.99/live"


def test_card_coverage_is_a_recording_contribution_and_backfill_checks_the_actual_card():
    wall = Clock(100_000.0)
    _, _, south, cam, books, _, _ = _site(wall)
    books.assign(SERIAL, "south"); books.collect()
    books.observe(cam.name, [{"id": "card", "cam": "ref:" + SERIAL, "enabled": True}],
        [{"id": "card", "phase": "running", "coverage": {
            "from": wall() - 3600, "to": wall(), "fragments": 1}}], kind="edge")
    books.collect()
    src = resolve(south.vars, "ref:" + SERIAL, wall())
    fetch, dropped = plan_backfill(src, [(wall()-3600, wall()-1800), (wall()-600, wall())],
        wall(), 30, 60, lambda: {"from": wall()-1500, "to": wall()})
    assert fetch == [(wall()-1500, wall()-600)]
    assert dropped == [((wall()-1800, wall()-1500), "no longer on the card")]


def test_a_source_without_assignment_cannot_be_used_for_a_new_connection():
    wall = Clock()
    _, _, south, _, books, _, _ = _site(wall)
    books.collect()
    try:
        resolve(south.vars, "ref:" + SERIAL, wall())
    except NotResolvable:
        pass
    else:
        raise AssertionError("an unassigned source opened")


def test_primary_enabled_and_running_are_explicit_observations_not_a_starting_field():
    wall = Clock()
    _, _, _, cam, books, _, _ = _site(wall)
    books.assign(SERIAL, "south"); books.collect()
    for enabled, running in ((True, False), (True, True), (False, False)):
        books.observe("south", [{"id": SERIAL, "cam": "ref:"+SERIAL, "enabled": enabled}],
            [{"id": SERIAL, "phase": "running" if running else "pending"}])
        books.collect()
        got = primary(cam.flash.get("domain/rec/primaries")[0], SERIAL, "south")
        assert (got.value["enabled"], got.value["running"]) == (enabled, running)
        assert "starting" not in got.value


def test_a_publisher_change_is_not_observed_until_its_signed_report_is_collected():
    wall = Clock()
    _, _, _, cam, books, sa, _ = _site(wall)
    books.assign(SERIAL, "south"); books.collect()
    row = {"id": SERIAL, "cam": "ref:"+SERIAL, "enabled": True}
    books.observe("south", [row], [{"id": SERIAL, "phase": "pending"}]); books.collect()
    books.observe("south", [row], [{"id": SERIAL, "phase": "running"}])
    assert not primary(cam.flash.get("domain/rec/primaries")[0], SERIAL, "south").value["running"]
    books.collect()
    assert primary(cam.flash.get("domain/rec/primaries")[0], SERIAL, "south").value["running"]


def test_reassignment_withdraws_old_recipients_and_old_books_confer_no_connection_right():
    wall = Clock()
    fed, _, south, cam, books, _, _ = _site(wall)
    books.assign(SERIAL, "south"); books.collect()
    books.assign(SERIAL, "north"); books.collect()
    assert set(south.vars.get("domain/cam/sources")[0]) == {""}
    try:
        resolve(south.vars, "ref:" + SERIAL, wall())
    except NotResolvable:
        pass
    else:
        raise AssertionError("former receiver still has a source")
    row = fed.domain_holder.vars.get("domain/cam/sources/north")[0]
    assert source(row, SERIAL).member == cam.name
