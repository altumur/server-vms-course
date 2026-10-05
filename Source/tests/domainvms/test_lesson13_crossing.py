"""Lesson 13 — a stream from another cluster.

A server's recorder recording a camera that is a cluster of its own. The recorder is unchanged in what it
does and changed only in where it finds the camera: not in its own cluster's heartbeats, which do not
contain it, but in a source book the domain publishes for its cluster and the cluster's agent carries home
— so the recording goes on with the domain switched off. Data crosses between clusters; work does not.
"""
from cluster.variables import FakeVariables

from w2cplatform.domain.agent import DomainAgent
from w2cplatform.domain.api import ApiError
from vms.domainpart.crossing import Crossings, NotResolvable, plan_backfill, resolve
from vms.domainpart.device import DeviceCluster
from w2cplatform.domain.federation import Federation
from w2cplatform.domain.uplink import member_copy
from w2cplatform.domain.readview import ReadView
from tests.domain.conftest import Clock, Running, make_cluster

SERIAL = "SN4471"


def _site(wall):
    fed = Federation()
    north, north_link = make_cluster("north", domain=True)          # the domain's home
    south, _ = make_cluster("south")                                 # a server room with a recorder
    fed.add(north); fed.add(south)
    room = Running(south, wall)
    room.create(201)
    cam = DeviceCluster(SERIAL, FakeVariables(), wall=wall, address="10.1.0.71")
    cam.coverage = {"from": wall() - 3600, "to": wall()}           # an hour on the card
    cam.boot()
    fed.add(member_copy(cam.name, north.objects, wall=wall))        # the domain reads the camera's reports
    cam_agent = DomainAgent(cam.name, north.vars, cam.flash, now=wall, domain_objects=north.objects,
                            published=cam.local_objects())
    cam_agent.sync()
    view = ReadView(fed, wall=wall)
    view.refresh()
    crossings = Crossings(north.vars, view, wall)
    agent = DomainAgent("south", north.vars, south.vars, now=wall)
    return fed, north_link, south, cam, view, crossings, agent, cam_agent


def test_the_recorder_finds_a_camera_of_another_cluster_in_its_own_clusters_book():
    """The domain decides that south records the camera, publishes south's book from what it last read of
    the camera's cluster, and south's agent carries it home. The recorder resolves `ref:SN4471` against
    south's own Variables. And the camera's store is exactly as it was: nobody wrote into it."""
    wall = Clock()
    fed, north_link, south, cam, view, crossings, agent, cam_agent = _site(wall)
    writes = cam.flash.writes
    assert crossings.record(SERIAL, on="south") == {"camera": SERIAL, "recorded_by": "south", "from": f"cam-{SERIAL}"}
    crossings.publish()
    agent.sync()
    src = resolve(south.vars, f"ref:{SERIAL}", wall())
    assert (src.cluster, src.live_url, src.playback_url) == (f"cam-{SERIAL}", "rtsp://10.1.0.71/live", "http://10.1.0.71/playback")
    assert cam.flash.writes == writes                    # data will cross; nothing was written across
    assert resolve(south.vars, "rtsp://south-cam/201", wall()) is None       # its own sources: found as always


def test_one_camera_one_recording_cluster():
    """A camera serves one live session and one backfill. A second cluster recording it would take them
    from the first — so which cluster records it is the domain's decision, stored, and a second asker is
    refused with the reason, as Lesson 1 refuses a second placement."""
    wall = Clock()
    fed, north_link, south, cam, view, crossings, agent, cam_agent = _site(wall)
    crossings.record(SERIAL, on="south")
    assert crossings.record(SERIAL, on="south")["recorded_by"] == "south"      # asking again is the same answer
    for on, status in (("north", 409), (f"cam-{SERIAL}", 400)):
        try:
            crossings.record(SERIAL, on=on)
            raise AssertionError(f"{on} must be refused")
        except ApiError as e:
            assert e.status == status
    try:
        crossings.record("SN9999", on="south")
        raise AssertionError("an unseen camera cannot be recorded")
    except ApiError as e:
        assert e.status == 404


def test_the_recording_goes_on_with_the_domain_switched_off_and_says_how_old_its_address_is():
    """The thesis, for crossings: the recorder never asks the domain, it asks its own cluster's copy. With
    the domain gone the address is the one last carried, and its age grows — shown, never hidden."""
    wall = Clock()
    fed, north_link, south, cam, view, crossings, agent, cam_agent = _site(wall)
    crossings.record(SERIAL, on="south"); crossings.publish(); agent.sync()
    north_link.up = False
    wall.advance(6 * 3600)
    assert agent.sync() is False
    src = resolve(south.vars, f"ref:{SERIAL}", wall())
    assert src.live_url == "rtsp://10.1.0.71/live" and src.age >= 6 * 3600


def test_a_camera_that_moved_while_the_domain_was_off_is_found_again_when_it_is_back():
    """The failure this design accepts, stated: a camera that changes its address while the domain is off
    is recorded from the old address until the domain is back — the recorder sees a dead URL, reports it,
    and has nothing better. When the domain returns, one pass and one carry and the book is right again."""
    wall = Clock()
    fed, north_link, south, cam, view, crossings, agent, cam_agent = _site(wall)
    crossings.record(SERIAL, on="south"); crossings.publish(); agent.sync()
    north_link.up = False
    cam.address = "10.1.0.99"; cam.publish()                         # a new lease from DHCP
    assert resolve(south.vars, f"ref:{SERIAL}", wall()).live_url == "rtsp://10.1.0.71/live"
    north_link.up = True
    cam_agent.sync()                                                 # the camera reports its new door
    view.refresh(); crossings.publish(); agent.sync()
    assert resolve(south.vars, f"ref:{SERIAL}", wall()).live_url == "rtsp://10.1.0.99/live"


def test_backfill_trusts_the_book_to_plan_and_the_card_to_fetch():
    """The book says the card holds the last hour; south holds all but twenty minutes of it. That is the
    plan. Then the device is asked, and the card — a ring — has overwritten its oldest part since the book
    was carried: what is still there is fetched, what is not is dropped with its reason, not retried."""
    wall = Clock(100_000.0)
    fed, north_link, south, cam, view, crossings, agent, cam_agent = _site(wall)
    crossings.record(SERIAL, on="south"); crossings.publish(); agent.sync()
    now = wall()
    src = resolve(south.vars, f"ref:{SERIAL}", now)
    ours = [(now - 3600, now - 1800), (now - 600, now)]              # a gap from −30 to −10 minutes
    fetch, dropped = plan_backfill(src, ours, now, keep_days=30, settle=60,
                                   ask_device=lambda: {"from": now - 1500, "to": now})
    assert fetch == [(now - 1500, now - 600)]
    assert dropped == [((now - 1800, now - 1500), "no longer on the card")]


def test_a_camera_the_book_does_not_hold_is_said_by_name():
    wall = Clock()
    fed, north_link, south, cam, view, crossings, agent, cam_agent = _site(wall)
    try:
        resolve(south.vars, f"ref:{SERIAL}", wall())
        raise AssertionError("nothing was carried yet")
    except NotResolvable as e:
        assert SERIAL in str(e) and "source book" in str(e)


def test_the_card_learns_from_the_book_of_primaries_whether_the_room_writes_it():
    """The source book the other way round. The backup on the camera's card (`when: offline`, М10B Lesson 26)
    must know whether its primary — a recording of the SERVER ROOM's cluster — is written, and cannot look
    there. So the domain reads the room's rec snapshot (should it be written?) and its recorders' heartbeats
    (is it?) and writes one book per camera cluster; the camera's agent carries it home, and says in RAM when
    it last reached the domain. The book changes when the room's recording does, and only then does it touch
    the camera's flash."""
    import json
    from vms.config import REC_SPEC
    from vms.recworker import DOMAIN_SEEN, PRIMARIES
    from w2cplatform.contract import Heartbeat, Subsystem
    from w2cplatform.spec import SpecController

    wall = Clock()
    fed = Federation()
    north, _ = make_cluster("north", domain=True)
    south, south_link = make_cluster("south")
    fed.add(north); fed.add(south)
    cam = DeviceCluster(SERIAL, FakeVariables(), wall=wall, address="10.1.0.71")
    cam.boot(); fed.add(member_copy(cam.name, north.objects, wall=wall))
    agent = DomainAgent(cam.name, north.vars, cam.flash, now=wall, seen_store=cam.local_objects(),
                        domain_objects=north.objects, published=cam.local_objects())
    agent.sync()                                                      # its first report: now the domain knows it
    view = ReadView(fed, wall=wall); view.refresh()
    crossings = Crossings(north.vars, view, wall)
    crossings.record(SERIAL, on="south")
    rec = SpecController(REC_SPEC, south.vars, south.objects, wall=wall)
    rec.create({"name": SERIAL, "cam": f"ref:{SERIAL}"})              # the room's recording of the camera

    def room(running: bool):                                          # the room's recorder, and its controller
        rec.publish_snapshot()
        st = [{"id": SERIAL, "cam": f"ref:{SERIAL}", "enabled": True, "phase": "running" if running else "pending"}]
        south.objects.put(Subsystem("rec").heartbeat_key("r-0"), Heartbeat("r-0", wall(), st, {}).to_bytes())

    def pass_():
        crossings.publish_primaries(); agent.sync()
        items, _ = cam.flash.get(PRIMARIES)
        return json.loads(items[SERIAL])

    rec.publish_snapshot()                                            # the row, and no recorder has named it yet
    assert pass_() == {"cluster": "south", "recording": SERIAL, "should": True, "written": False, "starting": True}
    room(True)
    assert pass_() == {"cluster": "south", "recording": SERIAL, "should": True, "written": True, "starting": False}
    assert json.loads(cam.ram.get(DOMAIN_SEEN))["ts"] == wall()      # freshness: in RAM
    writes = cam.flash.writes
    for _ in range(10):
        wall.advance(5); room(True); pass_()
    assert cam.flash.writes == writes                                 # ten passes, nothing on flash

    room(False)
    e = pass_()
    assert e["written"] is False and e["starting"] is False and cam.flash.writes == writes + 1   # a stop, not a start (AB)

    rec.update(SERIAL, {"enabled": False}); room(False)
    assert pass_()["should"] is False                                 # the operator's decision: nothing to cover

    rec.update(SERIAL, {"enabled": True}); room(True); pass_()
    south_link.up = False                                             # the room does not answer the domain
    wall.advance(5)
    assert pass_() == {"cluster": "south", "recording": "", "should": True, "written": False, "starting": False}


def test_a_recording_moves_to_another_cluster_and_the_books_follow():
    """Feedback AN. The site is re-wired: the camera is to be recorded by north now. A second cluster is still
    refused — but a MOVE rewrites the decision, and on the next pass south's source book loses the camera (its
    recorder says why and stops), north's gains it. South's book is emptied, not left as it was: it has nothing
    of another cluster any more."""
    import json
    wall = Clock()
    fed, north_link, south, cam, view, crossings, agent, cam_agent = _site(wall)
    north = fed.domain_holder
    crossings.record(SERIAL, on="south"); crossings.publish(); agent.sync()
    try:
        crossings.record(SERIAL, on="north")
        raise AssertionError("a second cluster, without a move")
    except ApiError as e:
        assert e.status == 409
    out = crossings.record(SERIAL, on="north", move=True)
    assert out["recorded_by"] == "north" and out["moved_from"] == "south"
    crossings.publish(); agent.sync()
    assert south.vars.get("domain/vms/sources")[0] == {}
    try:
        resolve(south.vars, f"ref:{SERIAL}", wall())
        raise AssertionError("south records it no more")
    except NotResolvable:
        pass
    assert json.loads(north.vars.get("domain/vms/sources/north")[0][SERIAL])["live_url"] == "rtsp://10.1.0.71/live"
