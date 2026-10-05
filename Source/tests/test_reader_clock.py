"""Freshness on the READER's clock (the product's r29-writers2, checked in the course).

The thirteenth review moved the platform's judges — the controller, the resource, the holder's readers — off the writers'
clocks: a thing is fresh when the judge saw it CHANGE within a window of its own clock (`contract.Eyes`), and the
writer's time is read for a page and for the skew alone. The product found its VMS readers still judging by the writer's
`ts`, and so did the course: the recorders' doors and volumes on the console's page, the volumes' view and its
proposal, the scan's doors, the devices a console calls known, the contenders for a name, the snapshot's age, the
recorder's book of primaries, the event merge's resources. Each is asked here with writers whose clocks are wrong both
ways: a dead one an hour AHEAD must stop counting once it stands still for the window, and a live one an hour (or
100 s) BEHIND that keeps writing must count. The snapshot's age is in `test_garbled_rows.py`."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from w2cplatform.contract import CONTENDER_FRESH, Eyes, Heartbeat, Slot, builds, contenders, judge_clock
from vms.config import REC_SPEC, SPEC
from tests.conftest import Box

AHEAD, BEHIND = 3600.0, -3600.0


def _eyes(box) -> Eyes:
    return Eyes(judge_clock(box.wall), box.wall)


def _beat(box, spec, name: str, skew: float, status=(), **extra) -> None:
    box.objects.put(spec.sub.heartbeat_key(name), Heartbeat(name, box.wall() + skew, list(status), extra).to_bytes())


def test_a_recorder_dead_with_its_clock_ahead_stops_being_a_door_and_one_behind_stays_one():
    """The console's timeline, export and the keeps' copier ask `recorder_doors`; the timeline names the volumes nobody
    serves (`unserved_volumes`). Both read `now - hb.ts`, with no bound ahead: r-ahead, dead, stayed a door for an hour
    and its volume was never named unavailable; r-behind, alive, was no door and its volume "unserved"."""
    from vms.footage import recorder_doors, unserved_volumes
    box, eyes = Box(), None
    eyes = _eyes(box)
    _beat(box, REC_SPEC, "r-ahead", AHEAD, archive_url="http://127.0.0.1:9", volume="va", server="srv-a")
    _beat(box, REC_SPEC, "r-behind", BEHIND, archive_url="http://127.0.0.1:8", volume="vb", server="srv-b")
    recorder_doors(box.objects, box.wall(), eyes=eyes)                       # the first look: both just changed
    for _ in range(3):
        box.wall.advance(20)
        _beat(box, REC_SPEC, "r-behind", BEHIND, archive_url="http://127.0.0.1:8", volume="vb", server="srv-b")
    assert [n for n, _, _ in recorder_doors(box.objects, box.wall(), eyes=eyes)] == ["r-behind"]
    assert [v["volume"] for v in unserved_volumes(box.objects, box.wall(), eyes=eyes)] == ["va"]


def test_a_volume_is_served_by_a_holder_behind_and_no_longer_by_a_dead_one_ahead():
    """`volumes.served` (the console's `/volumes`, `rec_volumes_unserved`) read a hold live while `now <= until` — the
    holder's clock — and a recorder's word by `now - ts`; `volumes.suggest` offered a disk by the same. A hold renewed
    by a recorder an hour behind was "the recorder that held it went silent", and its disk never offered; a dead one an
    hour ahead held its volume for that hour. Now a hold is live while the reader has seen it renewed within a slot's
    term, a recorder's word while its heartbeat changes."""
    from vms import volumes
    box = Box()
    eyes = _eyes(box)
    for name, server in (("va", "srv-a"), ("vb", "srv-b")):
        volumes.write(box.vars, {"name": name, "kind": "local", "server": server, "url": f"/data/{name}", "quota_bytes": 1 << 30})

    def hold(name, holder, skew, by):
        box.vars.put(REC_SPEC.sub.hold_key(name), Slot(name, holder, box.wall() + skew + 45, False, 1, by).to_items())

    def beat_b():
        hold("vb", "inst-b", BEHIND, "r-behind")
        _beat(box, REC_SPEC, "r-behind", BEHIND, volume="vb", server="srv-b", archive="/data/rec-b")

    hold("va", "inst-a", AHEAD, "r-ahead")
    _beat(box, REC_SPEC, "r-ahead", AHEAD, volume="va", server="srv-a", archive="/data/rec-a", volume_error="disk gone")
    beat_b()
    volumes.served(box.vars, REC_SPEC.sub, box.wall(), objects=box.objects, eyes=eyes)    # the first look
    for _ in range(3):
        box.wall.advance(20)
        beat_b()
    rows = {v["name"]: v for v in volumes.served(box.vars, REC_SPEC.sub, box.wall(), objects=box.objects, eyes=eyes)["volumes"]}
    assert rows["vb"]["served_by"] == "inst-b" and rows["vb"]["why"] is None, rows["vb"]
    assert rows["va"]["served_by"] is None and rows["va"]["why"] == "the recorder that held it went silent", rows["va"]
    assert volumes.suggest(box.vars, box.objects, REC_SPEC.sub, box.wall(), eyes=eyes) == []   # both disks declared
    for name in ("va", "vb"):                                         # …and with none declared, the disk of the live one
        volumes.delete(box.vars, name)
    beat_b()
    assert [s["server"] for s in volumes.suggest(box.vars, box.objects, REC_SPEC.sub, box.wall(), eyes=eyes)] == ["srv-b"]


def test_a_scan_asks_the_door_of_a_recorder_behind_and_not_of_a_dead_one_ahead():
    """`scan.recording_read` asked a door live by `is_live` — the recorder's clock against the scan worker's: a recorder
    100 s behind was no door, its minutes unread, the scan waiting and then ending without them."""
    from vms.scan import recording_read

    class Door(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            body = json.dumps({"spans": [{"start": 100.0, "end": 160.0, "epoch": 1, "bytes": 10}]}).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers()
            self.wfile.write(body)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Door)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        box = Box()
        eyes = _eyes(box)
        url = f"http://127.0.0.1:{srv.server_address[1]}"
        _beat(box, REC_SPEC, "r-ahead", AHEAD, archive_url="http://127.0.0.1:9", volume="va")
        _beat(box, REC_SPEC, "r-late", -100.0, archive_url=url, volume="vb")
        recording_read(box.objects, "7", 0, 200, box.wall(), timeout=0.5, eyes=eyes)       # the first look
        box.wall.advance(46)
        _beat(box, REC_SPEC, "r-late", -100.0, archive_url=url, volume="vb")
        got = recording_read(box.objects, "7", 0, 200, box.wall(), timeout=0.5, eyes=eyes)
        assert got.answered and [(s.start, s.end) for s in got.spans] == [(100.0, 160.0)] and got.silent == [], got
    finally:
        srv.shutdown()


def test_a_device_is_known_through_a_holder_behind_and_not_through_a_dead_one_ahead():
    """`config.Devices.held` — what makes a device known, and moving a camera within it a grant on that camera, not on
    the cluster — took the holders live by `ts`: a holder an hour behind made its devices unknown, one dead an hour
    ahead kept a replaced recorder's identity known (the tenth pass's hole, by a clock)."""
    from vms.config import one_device
    box = Box()
    eyes = _eyes(box)
    for dev, ident in (("acme/10.0.0.5", "SN5"), ("acme/10.0.0.6", "SN6")):
        box.vars.put(SPEC.sub.config("devices", dev), {"identity": ident})
    _beat(box, SPEC, "w-ahead", AHEAD, devices=[{"device": "acme/10.0.0.6", "can": True}])
    _beat(box, SPEC, "w-behind", BEHIND, devices=[{"device": "acme/10.0.0.5", "can": True}])
    one_device(box.vars, box.objects, box.wall, eyes).held()                                # the first look
    box.wall.advance(46)
    _beat(box, SPEC, "w-behind", BEHIND, devices=[{"device": "acme/10.0.0.5", "can": True}])
    same = one_device(box.vars, box.objects, box.wall, eyes)
    assert same.known("acme/10.0.0.5") and not same.known("acme/10.0.0.6")


def test_a_contender_is_fresh_while_it_asks_whatever_its_clock_and_not_after():
    """`contract.contenders` read a mark fresh while `now - at <= CONTENDER_FRESH` — the claimant's clock: one an hour
    ahead that stopped asking was a name conflict for an hour, one an hour behind that asks every pass was never one."""
    box = Box()
    eyes = _eyes(box)

    def mark(slot, box_id, skew):
        at = box.wall() + skew
        box.objects.put(SPEC.sub.contender_key(slot, box_id), json.dumps(
            {"name": slot, "box": box_id, "state": "refused", "at": at, "since": at}).encode())

    mark("w-1", "box-ahead", AHEAD)
    mark("w-2", "box-behind", BEHIND)
    contenders(box.objects, SPEC.sub, box.wall(), eyes)                                   # the first look
    for _ in range(int(CONTENDER_FRESH // 10) + 1):
        box.wall.advance(10)
        mark("w-2", "box-behind", BEHIND)
    assert sorted(contenders(box.objects, SPEC.sub, box.wall(), eyes)) == ["w-2"]


def test_a_dead_worker_is_not_kept_fresh_by_two_readers_giving_one_judge_two_tokens():
    """Found beside the product's r29-writers2: `contract.builds` (`/schema`, `set_schema`) gave the controller's eyes a
    heartbeat's bare `ts` under the same key under which `/servers` and the controller give `(ts, crc)` — each read was
    a change to the other, and a dead worker read "fresh" for as long as a page asked both. One token now."""
    from vms.controller import VmsController
    box = Box()
    ctl = VmsController(box.vars, box.objects, wall=box.wall)
    _beat(box, SPEC, "w-1", 0.0)
    key = SPEC.sub.heartbeat_key("w-1")
    hb = Heartbeat.from_bytes(box.objects.get(key))
    for _ in range(12):                                   # a minute of a page asking both, the worker silent
        box.wall.advance(5)
        live = builds(box.objects, box.wall(), eyes=ctl.eyes)["vms/w-1"]["live"]
        ctl.eyes.fresh(key, hb.token, 45.0)
    assert live is False


def test_the_event_merge_asks_a_resource_behind_and_not_a_dead_one_ahead():
    """`MergedIndex` (the console's events, automation's long poll) took a resource live by `now - ts`: one an hour
    behind was "silent" and every window it could have written in incomplete; one dead an hour ahead was asked."""
    from w2cplatform.eventdatabase import MergedIndex
    from tests.conftest import Clock
    box, looks = Box(), Clock()

    def beat(server, skew):
        box.objects.put(f"platform/resources/{server}/heartbeat", json.dumps(
            {"server": server, "ts": box.wall() + skew, "url": f"http://{server}"}).encode())

    m = MergedIndex(box.objects, fetch=lambda url, params: {"events": [], "state": "live"}, wall=box.wall, clock=looks)
    beat("srv-ahead", AHEAD)
    beat("srv-behind", BEHIND)
    m.live(m.seen())                                                                      # the first look
    box.wall.advance(60); looks.advance(60)
    beat("srv-behind", BEHIND)
    assert m.live(m.seen()) == {"srv-behind"}


def test_a_card_stops_trusting_the_book_when_its_agent_stops_whatever_the_agents_clock():
    """The recorder's book of primaries (`RecWorker.carried_primary`) is vouched for by the time the camera's agent last
    reached the domain — the agent's clock. An agent an hour ahead that then lost the domain vouched for the book for
    that hour, and the card did not cover. By the card's own clock now: once the mark stands still past
    `CARRIED_LOST_AFTER`, nobody vouches for the book, and the card records."""
    from tests.test_backup_archive import _camera_cluster
    box, card, row, carry = _camera_cluster()
    carry(written=True, seen=False)
    box.objects.put("domain/seen", json.dumps({"ts": box.wall() + AHEAD}).encode())       # an agent an hour ahead
    assert not card.primary_needs_cover(row)                                              # the room writes it
    box.wall.advance(card.CARRIED_LOST_AFTER + 1); box.clock.advance(card.CARRIED_LOST_AFTER + 1)
    assert card.primary_needs_cover(row)                                                  # the agent stopped: record


def test_the_console_reads_a_worker_behind_as_live_and_its_rows_age_on_the_consoles_clock():
    """`SpecController.read_model` (the console's units and the layer above) said each row's worker `live` or `stale`, and
    its age, by `now - hb.ts`: a worker 100 s behind read `stale` on every row while it ran them. By what the console saw
    change now: live while its heartbeat changes, and stale — aged on the console's clock — once it stands still."""
    from vms.controller import VmsController
    box = Box()
    ctl = VmsController(box.vars, box.objects, wall=box.wall)
    _beat(box, SPEC, "w-late", -100.0, status=[{"id": 1, "phase": "running"}])
    ctl.read_model()                                                                      # the first look
    for _ in range(3):
        box.wall.advance(20)
        _beat(box, SPEC, "w-late", -100.0, status=[{"id": 1, "phase": "running"}])
    [row] = ctl.read_model()
    assert row["worker_state"] == "live" and row["age"] == 0.0, row
    box.wall.advance(60)
    [row] = ctl.read_model()
    assert row["worker_state"] == "stale" and row["age"] == 60.0, row


def test_an_ingest_takes_what_a_recorder_wrote_only_while_it_hears_it():
    """М12's ingest drops every frame not newer than what the cluster's recorder `written_through` says
    (`ingest.written_from_heartbeats`), and read that recorder fresh by `now - hb.ts`: a dead recorder an hour ahead
    said its `written_through` for that hour, one 100 s behind was never heard. By the ingest's own clock now."""
    from vms.domainpart.ingest import written_from_heartbeats
    box = Box()

    def beat(name, skew, through):
        _beat(box, REC_SPEC, name, skew, status=[{"id": f"{name}-r", "cam": "ref:SN1", "written_through": through}])

    written = written_from_heartbeats(box.objects, box.wall)
    beat("r-ahead", AHEAD, box.wall() - 10)
    beat("r-late", -100.0, box.wall() - 50)
    written("SN1")                                                                        # the first look
    box.wall.advance(46)
    beat("r-late", -100.0, box.wall() - 50)
    assert written("SN1") == box.wall() - 50
