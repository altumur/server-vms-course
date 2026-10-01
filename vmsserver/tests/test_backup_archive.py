"""Lesson 26 — a backup archive of our own.

Lesson 16 closed a recording's gaps from the DEVICE's archive — whatever a camera keeps on its card, read
through the holder's playback door. The product found that door closed (its DriverPack binding has no
playback calls yet) and a better one open: our own archives. A critical camera is recorded twice — its
primary recording, and a BACKUP recording on a volume of kind `backup`: a second server's disk, or the
card of a camera that runs this platform. The primary closes any hole from the backup — a link that
dropped, the seconds its own recorder took to move — by COPYING the backup's footage, cut to the hole, with
the times it was recorded at. The mechanism is Lesson 16's, over a second kind of source.
"""
import tempfile

from vms import volumes
from vms.config import REC_SPEC, SPEC
from vms.controller import VmsController
from vms.worker import FakeActuator, FakeDevice
from w2cplatform.contract import Heartbeat
from w2cplatform.spec import Refused, SpecController
from tests.conftest import footage, recorder
from tests.test_lesson11_edge import CARD, _box, _holder


def _resource(box, server):
    import json
    box.objects.put(f"platform/resources/{server}/heartbeat",
                    json.dumps({"server": server, "ts": box.wall(), "url": f"http://{server}", "units": {}}).encode())


def _recorder(box, name, server, volume, act=None, opened=True):
    """A recorder PINNED to a declared volume (`$VOLUME`), the volume open — unless another recorder has it
    open already (`opened=False`: a test of placement, where nothing is written)."""
    r = recorder(box, name, server, act, keep_days=1.0, settle=60.0, env={"VOLUME": volume})
    _resource(box, server)
    r.lease_pass(); r.heartbeat_once()
    assert r.store is not None or not opened, r.volume_error or r.archive_error
    return r


def _volume(box, name, kind, server):
    """A declared volume, in a directory of its own: `/data/a` on a box is a temp directory here."""
    url = tempfile.mkdtemp(prefix=f"{name}-")
    volumes.write(box.vars, {"name": name, "kind": kind, "server": server, "url": url, "quota_bytes": 64 << 20})


def _footage(r, unit, spans):
    """A frame every ten seconds, visible."""
    for start, end in spans:
        footage(r.store, unit, r.epochs[unit], start, end, step=10, seal=False)
    r.store.seal()


# The two recorders of `_site` are on srv-a and srv-b, and this test runs both on ONE machine, where the backup's
# archive door is on loopback. On two machines that door would be opened and announced by the server's name; a
# loopback address from another server is not followed (`vms.config.local_only`, feedback BT). The tests that
# fetch across "servers" say so: they stand in for the network, and nothing else.
class _OneMachine:
    def __enter__(self):
        import vms.config as c
        self.c, self.real = c, c.local_only
        c.local_only = lambda url, holder, me: False
    def __exit__(self, *a):
        self.c.local_only = self.real


def _site(when="always", backup_act=None, card=None):
    """Camera 1, held on srv-1. Recorded twice: `1` on srv-a's disks, `1-copy` on srv-b's backup volume."""
    box, ctl, con, con_vars = _box()
    w = _holder(box, lambda k: FakeDevice(k, channels=["1"], coverage={"1": card} if card else None))   # by default a card we cannot read
    con.create_camera({"name": "front", "source": CARD})
    ctl.ensure_placed(); w.reconcile_once(); w.heartbeat_once()
    _volume(box, "disks", "local", "srv-a")
    _volume(box, "copy", "backup", "srv-b")
    con_rec = SpecController(REC_SPEC, con_vars, box.objects, wall=box.wall)
    con_rec.create({"name": "1", "cam": "1", "home": "disks"})
    con_rec.create({"name": "1-copy", "cam": "1", "home": "copy", "when": when})
    primary = _recorder(box, "r-1", "srv-a", "disks")
    backup = _recorder(box, "r-2", "srv-b", "copy", backup_act)
    rec_ctl = SpecController(REC_SPEC, box.vars.as_writer("reccontroller", REC_SPEC.acl_controller()), box.objects, wall=box.wall)
    rec_ctl.ensure_placed()
    for r in (primary, backup):
        r.reconcile_once(); r.heartbeat_once()
    return box, rec_ctl, primary, backup, w


def test_the_primary_closes_its_gap_from_the_backup_recording():
    """The primary's recorder moved, and a hundred seconds are missing from it. The backup recording has
    them. The primary finds the backup in the heartbeats — a recording of the same camera, homed on a backup
    volume, whose recorder says what it holds and serves its archive — and copies exactly the hundred
    seconds, cut out of the backup's volume, with the times they were recorded at. What lands is ours:
    our volume, our epoch, the recording's backfill stream."""
    with _OneMachine():
        box, rec_ctl, primary, backup, _ = _site()
        now = box.wall()
        _footage(backup, "1-copy", ((now - 7200, now - 600),))
        _footage(primary, "1", ((now - 7200, now - 4000), (now - 3900, now - 600)))
        backup.serve_archive(); backup.heartbeat_once()

        src = primary.backup_sources({"id": "1", "cam": "1", "home": "disks"})
        assert [(s["recording"], s["recorder"]) for s in src] == [("1-copy", "r-2")]
        done = primary.backfill(budget=1, now=now, force=True)
        assert [{k: d[k] for k in ("unit", "cam", "from", "to", "source")} for d in done] == [
            {"unit": "1", "cam": "1", "from": now - 4000, "to": now - 3900, "source": "backup:1-copy"}]
        assert done[0]["groups"] > 0 and primary.actuator.fetched == []                         # nothing re-recorded
        primary.store.seal()
        copied = [s for s in primary.store.spans("1") if s.stream.endswith("/backfill")]
        assert [(c.start, c.end) for c in copied] == [(now - 4000, now - 3900)]                 # cut to the hole
        assert copied[0].epoch == primary.epochs["1"]
        assert primary.our_coverage("1") == [(now - 7200, now - 600)]


def test_the_backups_volume_decides_what_is_copied_not_its_summary():
    """The backup's heartbeat says it holds two hours — a summary, start and end. Its volume says there is
    a hole in it too. The primary plans from the summary, copies what the backup's door hands over, and
    remembers what the backup did not have, so the next pass does not ask it again."""
    with _OneMachine():
        box, rec_ctl, primary, backup, _ = _site()
        now = box.wall()
        _footage(backup, "1-copy", ((now - 7200, now - 3960), (now - 3920, now - 600)))        # 40 s missing there too
        _footage(primary, "1", ((now - 7200, now - 4000), (now - 3900, now - 600)))
        backup.serve_archive(); backup.heartbeat_once()

        primary.backfill(budget=1, now=now, force=True)
        primary.store.seal()
        copied = sorted((c.start, c.end) for c in primary.store.spans("1") if c.stream.endswith("/backfill"))
        assert copied == [(now - 4000, now - 3960), (now - 3920, now - 3900)]
        assert primary.nowhere[("1", "backup:1-copy")] == [(now - 3960, now - 3920)]
        assert primary.backfill(budget=1, now=now, force=True) == []


def test_a_backup_fetches_from_nobody():
    """The backup exists to be copied from. A backup that backfilled — from the primary, or from the card —
    would fill ITS holes with footage the primary also has, and the two archives would stop being two
    independent records of what the camera saw: one hole, copied in both directions, is one hole twice."""
    box, rec_ctl, primary, backup, _ = _site(card=(0.0, 2e9, 1))           # …and a card the device CAN serve
    now = box.wall()
    _footage(primary, "1", ((now - 7200, now - 600),))
    _footage(backup, "1-copy", ((now - 7200, now - 4000), (now - 3900, now - 600)))
    primary.serve_archive(); primary.heartbeat_once()
    assert backup.backup_sources({"id": "1-copy", "cam": "1", "home": "copy"}) == []
    assert backup.backfill(budget=5, now=now, force=True) == []


def test_a_backup_volume_holds_its_own_recordings_and_nothing_else():
    """`home` is a preference everywhere else, and for a backup volume that is wrong both ways. The primary
    put onto the backup volume while its own server is down leaves one copy where two were paid for; the
    backup put onto the primary's disk is no copy at all. So a new camera's two recordings, created while
    only srv-b answers, are placed one on srv-b and one nowhere — unplaceable, said out loud — and when srv-a
    comes back the primary lands there. Without the rule the primary goes to srv-b "away from home"."""
    box, ctl, con, con_vars = _box()
    _volume(box, "disks", "local", "srv-a")
    _volume(box, "copy", "backup", "srv-b")
    backup = _recorder(box, "r-2", "srv-b", "copy")
    rec_ctl = SpecController(REC_SPEC, box.vars.as_writer("reccontroller", REC_SPEC.acl_controller()), box.objects, wall=box.wall)
    con_rec = SpecController(REC_SPEC, con_vars, box.objects, wall=box.wall)
    con_rec.create({"name": "2", "cam": "2", "home": "disks"})
    con_rec.create({"name": "2-copy", "cam": "2", "home": "copy"})
    rec_ctl.ensure_placed()
    assert rec_ctl.where("2-copy") == "r-2" and rec_ctl.placement("2") is None

    _recorder(box, "r-1", "srv-a", "disks")
    rec_ctl.ensure_placed()
    assert rec_ctl.where("2") == "r-1"

    con_rec.create({"name": "3-copy", "cam": "3", "home": "copy"})
    box.wall.advance(120); _resource(box, "srv-a")
    _recorder(box, "r-3", "srv-a", "disks", opened=False)             # srv-b silent: only disks answer
    rec_ctl.ensure_placed()
    assert rec_ctl.placement("3-copy") is None                        # the backup waits for ITS volume


def test_the_camera_stands_beside_the_backup_recording():
    """With two recordings, the camera's worker follows one of them (`near: {sub: rec, of: cam}`). Beside
    the primary, the fall of srv-a takes the worker too, and the backup loses its stream at exactly the
    moment it exists for. Beside the backup, the worker survives srv-a, the backup keeps recording, and the
    primary backfills its own move from the backup."""
    box, rec_ctl, primary, backup, w = _site()
    for r in (primary, backup):
        r.heartbeat_once()
    vms = VmsController(box.vars, box.objects, wall=box.wall)
    assert vms.holder_near("1") == ("r-2", "srv-b")


def test_an_offline_backup_stands_in_for_a_failure_and_never_for_a_decision():
    """`when: offline`: the backup records only while the primary SHOULD be written and is not. The primary
    running — hold. The primary gone quiet — a few seconds of grace, because every recording starts that
    way, then the backup records. The primary switched off, or an event recording whose `until` has passed —
    nobody's failure, and standing in for it would make a recording on events a recording always."""
    box, rec_ctl, primary, backup, _ = _site(when="offline")
    row = next(r for r in backup.rows if r["id"] == "1-copy")
    assert not backup.primary_needs_cover(row)

    primary.actuator.stop_all(); primary.reconciler.actual.clear(); primary.heartbeat_once()   # the primary stops writing
    assert not backup.primary_needs_cover(row)                          # …not yet: it may be starting
    box.wall.advance(backup.START_GRACE + 1)
    primary.heartbeat_once()
    assert backup.primary_needs_cover(row)

    con = SpecController(REC_SPEC, box.vars.as_writer("console3", REC_SPEC.acl_console()), box.objects, wall=box.wall)
    con.update("1", {"enabled": False})                                  # the operator switched it off
    assert not backup.primary_needs_cover(row)
    con.update("1", {"enabled": True, "until": box.wall() - 1})          # an event that has ended
    assert not backup.primary_needs_cover(row)


def test_an_offline_backup_runs_on_hold_and_writes_nothing():
    """The backup's pipeline does not wait to be started. It is up, subscribed to the camera, and recording
    into a ring of the last thirty seconds in memory — writing nothing to its volume, which on a card is
    the camera's own flash. The operator sees why it is idle."""
    box, rec_ctl, primary, backup, _ = _site(when="offline")
    assert "1-copy" in backup.actuator.held and backup.holding["1-copy"] is True
    st = next(st for st in backup.status() if st["id"] == "1-copy")
    assert st["phase"] == "standby" and "held in memory" in st["why"]
    box.wall.advance(60); backup.store.seal()
    assert backup.store.spans("1-copy") == []                          # not a frame on the volume


def _primary_stops(box, primary, backup, holder, after: float = 100.0):
    """The backup has been holding for `after` seconds, so its ring is full; then the primary stops."""
    box.wall.advance(after)
    holder.heartbeat_once(); primary.heartbeat_once(); backup.heartbeat_once()
    stopped = box.wall()
    primary.actuator.stop_all(); primary.reconciler.actual.clear(); primary.heartbeat_once()
    backup.reconcile_once()                                            # the backup's next pass sees it quiet
    return stopped


def test_a_released_backup_writes_the_seconds_before_anybody_noticed():
    """The primary stops. Nobody can know at once — every recording starts with a quiet moment — so the
    backup waits its grace, and is released a pass later. Started only then, it would begin eleven seconds
    after the failure, and those are the seconds the failure happened in. Released from its ring, it writes
    them first: from the oldest keyframe the ring still holds, before the primary stopped, named by the time
    the footage was captured."""
    box, rec_ctl, primary, backup, w = _site(when="offline")
    stopped = _primary_stops(box, primary, backup, w)
    box.wall.advance(backup.START_GRACE + 1)
    primary.heartbeat_once()
    backup.reconcile_once()
    released_at = box.wall()

    [(uid, start, end)] = backup.actuator.released
    assert uid == "1-copy" and end == released_at
    assert released_at - backup.PREBUFFER <= start < stopped            # footage from BEFORE the failure
    assert start % backup.actuator.gop == 0                             # from a keyframe, never mid-GOP
    assert backup.holding["1-copy"] is False
    backup.store.seal()
    assert backup.our_coverage("1-copy") == [(start, released_at)]     # on the volume, at its own time


def test_the_backup_goes_back_on_hold_a_minute_after_the_primary_is_back():
    """The primary is written again — by its heartbeat. Its first minutes are not on the volume yet, and will not be
    visible until their block closes; stopping the backup at that word would leave the seam to nobody. So the backup
    keeps writing for a minute, the two archives overlap, and only then is it put back on hold: a restart
    under the same epoch, its sequence finished and kept, the ring filling afresh for next time."""
    box, rec_ctl, primary, backup, w = _site(when="offline")
    _primary_stops(box, primary, backup, w)
    box.wall.advance(backup.START_GRACE + 1)
    primary.heartbeat_once(); backup.reconcile_once()
    epoch = backup.epochs["1-copy"]

    w.heartbeat_once(); primary.reconcile_once(); primary.heartbeat_once()   # the primary's recorder is back
    assert backup.holding["1-copy"] is False                           # released: recording for the primary
    backup.reconcile_once()
    assert backup.holding["1-copy"] is False                           # the primary is back — and the backup still writes
    box.wall.advance(backup.HOLD_AFTER)
    w.heartbeat_once(); primary.heartbeat_once(); backup.heartbeat_once()
    backup.reconcile_once()
    assert backup.holding["1-copy"] is True and "1-copy" in backup.actuator.held
    assert backup.epochs["1-copy"] == epoch                            # the same writer, held again
    assert next(st for st in backup.status() if st["id"] == "1-copy")["phase"] == "standby"


def test_a_primary_switched_off_never_releases_the_ring():
    """The same rule as above, at the gate: an operator's decision is not a failure, and the ring stays
    closed however long the primary is off."""
    box, rec_ctl, primary, backup, w = _site(when="offline")
    con = SpecController(REC_SPEC, box.vars.as_writer("console3", REC_SPEC.acl_console()), box.objects, wall=box.wall)
    con.update("1", {"enabled": False})
    _primary_stops(box, primary, backup, w)
    box.wall.advance(600)
    w.heartbeat_once(); primary.heartbeat_once(); backup.heartbeat_once(); backup.reconcile_once()
    assert backup.actuator.released == [] and backup.holding["1-copy"] is True


def test_a_backup_volume_is_a_box_or_an_address():
    """With a server it is a disk on that box — a camera's card, a second server's disk — and only that box
    serves it. Without one it is an address any box may serve, like a network volume: a second storage
    elsewhere is as independent of the primary's server as a second disk is."""
    volumes.refuse({"name": "copy", "kind": "backup", "url": "s3://copies/site-1", "quota_bytes": 1})   # accepted
    vols = [volumes.Volume("card", "backup", "/data/card", "cam-7", 1), volumes.Volume("cloud", "backup", "s3://c", "", 1)]
    assert volumes.servable(vols, "cam-7") == ["card", "cloud"]
    assert volumes.servable(vols, "srv-a") == ["cloud"]


def _camera_cluster():
    """A camera that is a cluster of its own (М12 Lesson 10): its row, `ref` its serial, and ONE recording
    here — the backup on its card, `when: offline`. Its primary is a row of another cluster, the server room
    that records it (М12 Lesson 13), and nothing of it is in this cluster: no row, no heartbeat."""
    import json
    box, ctl, con, con_vars = _box()
    w = _holder(box, lambda k: FakeDevice(k, channels=["1"]))
    con.create_camera({"name": "gate", "source": CARD, "ref": "SN1"})
    ctl.ensure_placed(); w.reconcile_once(); w.heartbeat_once()
    _volume(box, "card", "edge", "srv-1")
    SpecController(REC_SPEC, con_vars, box.objects, wall=box.wall).create({"name": "1-card", "cam": "1", "home": "card", "when": "offline"})
    card = _recorder(box, "r-1", "srv-1", "card")
    SpecController(REC_SPEC, box.vars.as_writer("reccontroller", REC_SPEC.acl_controller()), box.objects, wall=box.wall).ensure_placed()
    card.reconcile_once(); card.heartbeat_once()

    def carry(should=True, written=True, seen=True, starting=False):   # what the camera's agent does on a pass
        book = {"SN1": json.dumps({"cluster": "room", "recording": "SN1", "should": should, "written": written,
                                   "starting": starting}, sort_keys=True)}
        have, idx = box.vars.get("domain/primaries")
        if have != book:
            box.vars.put("domain/primaries", book, cas=idx)
        if seen:
            box.objects.put("domain/seen", json.dumps({"ts": box.wall()}).encode())
    return box, card, next(r for r in card.rows if r["id"] == "1-card"), carry


def test_a_card_learns_about_its_primary_in_another_cluster_from_the_book_its_agent_carries():
    """The primary is in the server room's cluster, so this cluster's rows and heartbeats say nothing about
    it. Without a book the rule finds no primary and the card never covers — the room down included, the one
    moment it exists for. With the book of primaries the domain writes for this cluster and the agent
    carries home, the card holds while the room writes, covers when the room stops (after the same grace),
    covers when the book cannot be vouched for, and never covers an operator's decision."""
    box, card, row, carry = _camera_cluster()
    assert not card.primary_needs_cover(row)                  # no book: a camera alone, nothing to stand in for

    carry(written=False, starting=True)
    assert not card.primary_needs_cover(row)                  # a recording starting: not yet
    box.wall.advance(card.START_GRACE + 1); carry(written=False, starting=True)
    assert card.primary_needs_cover(row)                      # …it took longer than a start takes
    carry(written=True)
    assert not card.primary_needs_cover(row)                  # the room writes it
    carry(written=False)
    assert card.primary_needs_cover(row)                      # it was written and stopped: at once (feedback AB)

    carry(written=True)
    assert not card.primary_needs_cover(row)
    box.wall.advance(card.CARRIED_LOST_AFTER + 1)             # the agent has not reached the domain since
    assert card.primary_needs_cover(row)                      # nobody can vouch for the book: record

    carry(should=False, written=False)                        # the operator switched the room's recording off
    box.wall.advance(card.START_GRACE + 1); carry(should=False, written=False)
    assert not card.primary_needs_cover(row)


def test_the_book_is_written_to_flash_when_it_changes_and_its_freshness_is_not():
    """On a camera the book is flash. A book carrying the time the domain last looked would change on every
    pass and be rewritten every few seconds for years. So the book holds facts that change when the room's
    recording does, and freshness goes to the object store — RAM on a camera."""
    box, card, row, carry = _camera_cluster()
    carry()
    _, idx = box.vars.get("domain/primaries")
    for _ in range(20):
        box.wall.advance(5); carry()
    assert box.vars.get("domain/primaries")[1] == idx         # twenty passes, no write
    carry(written=False)
    assert box.vars.get("domain/primaries")[1] != idx         # the room stopped: one write


def test_a_primary_that_stops_is_covered_at_once_and_only_a_start_waits():
    """Feedback AB. With no time in the book, "not written" was one state: the card gave a primary that had
    never started and one that had been written and stopped the same twenty seconds. The second is lost
    footage, on top of the time the domain took to notice. The domain knows the difference — a recording
    no recorder of its cluster has named yet is starting — and says it in the book (`starting`), a field
    that changes when a recording starts and when a recorder first reports it."""
    box, card, row, carry = _camera_cluster()
    carry(written=True)
    assert not card.primary_needs_cover(row)
    carry(written=False, starting=False)
    assert card.primary_needs_cover(row)                      # no grace for a stop
    carry(should=False, written=False)
    assert not card.primary_needs_cover(row)                  # a decision is still never covered


def test_a_backup_of_another_servers_camera_finds_its_primary_by_the_domains_name():
    """Two servers as two clusters of one (М11 lesson 1). The backup on the second server names the camera the
    way a recording names a camera of another cluster — `cam: ref:<serial>` — and there is no camera row here
    to find its serial in. It reads the book of primaries by that name: holds while the first server writes,
    covers when it stops."""
    box, card, row, carry = _camera_cluster()
    backup = {**row, "id": "SN1-copy", "cam": "ref:SN1"}
    carry(written=True)
    assert card.carried_primary(backup, box.wall()) is False       # the first server writes it
    carry(written=False, starting=False)
    assert card.carried_primary(backup, box.wall()) is True        # it stopped: cover, at once


def test_what_the_stream_says_comes_before_the_book():
    """The book of primaries is the domain's, and the domain may be what died with the primary: then the book
    says "written" until it goes stale. A standby that can tell from its own stream — the camera came here, the
    card's camera did not hand its stream on — decides by that, at once; when the stream can say nothing, the
    book decides, as before."""
    box, card, row, carry = _camera_cluster()
    carry(written=True)                                       # the book still says the primary writes
    card.stream_says = lambda r: True                         # …but the stream is not being taken
    assert card.primary_needs_cover(row)
    card.stream_says = lambda r: False
    carry(written=False, starting=False)
    assert not card.primary_needs_cover(row)                  # the stream is taken: the book's word is older
    card.stream_says = lambda r: None
    assert card.primary_needs_cover(row)                      # it cannot say: the book decides



def test_a_recorder_says_when_it_cannot_reach_its_source():
    """The pipeline could not open the camera's stream: the recorder says so in its heartbeat, per recording —
    the witness the domain needs to stop sending it to pull and have the camera push (М12 lesson 16)."""
    box, card, row, carry = _camera_cluster()
    card.note_source_unreachable(row["id"], "connection refused")
    st = card.status_extra(row)
    assert st["source_unreachable"] is True and st["why"] == "source unreachable: connection refused"
    card.note_source_unreachable(row["id"], None)
    assert "source_unreachable" not in card.status_extra(row)


# -- memory first: a card that waits for a stream the camera can continue (feedback CB) ---------------------
def test_a_short_break_of_a_pushed_stream_never_touches_the_card():
    """The camera pushes its stream and can continue it after a break. A ten-second drop: the card's gate
    waits `defer_for`, the stream comes back, and nothing was written — no card wear, no backfill."""
    box, card, row, carry = _camera_cluster()
    carry(written=True)
    card.resumes = lambda r: True
    card.stream_says = lambda r: True                          # the break: the primary does not take the stream
    card.gate_pass()
    assert card.holding["1-card"] is True and card.actuator.released == []
    assert "held in memory" in next(s for s in card.status() if s["id"] == "1-card")["why"]
    box.wall.advance(10)
    card.stream_says = lambda r: False                         # back before the card had to write
    assert ("1-card", "back from memory") in card.gate_pass()
    assert card.actuator.released == [] and card.holding["1-card"] is True


def test_a_long_break_releases_the_ring_from_before_the_break():
    box, card, row, carry = _camera_cluster()
    carry(written=True)
    box.wall.advance(100)                                      # the ring is full
    card.resumes = lambda r: True
    card.stream_says = lambda r: True
    broke = box.wall()
    card.gate_pass()
    box.wall.advance(card.defer_for() + 1)
    card.gate_pass()
    [(uid, start, end)] = card.actuator.released
    assert uid == "1-card" and start <= broke - card.DETECTION      # still reaching back past the break
    assert card.holding["1-card"] is False


def test_where_nobody_can_continue_the_stream_the_card_writes_at_once():
    box, card, row, carry = _camera_cluster()
    carry(written=True)
    box.wall.advance(100)                                      # the ring is full
    card.resumes = lambda r: False                             # a camera a server pulls: nothing to continue
    card.stream_says = lambda r: True
    card.gate_pass()
    assert len(card.actuator.released) == 1


def test_a_card_stopped_during_a_break_writes_what_it_held():
    """Inside the deferral the ring is the ONLY copy of the break. Stopping used to drop it."""
    box, card, row, carry = _camera_cluster()
    carry(written=True)
    box.wall.advance(100)
    card.resumes = lambda r: True
    card.stream_says = lambda r: True
    card.gate_pass()
    assert card.actuator.released == []
    card._actuate("stop", row)
    assert len(card.actuator.released) == 1


def test_a_recorder_says_how_far_it_wrote():
    box, card, row, carry = _camera_cluster()
    card.note_written("1-card", 1000.0); card.note_written("1-card", 990.0)   # never backwards
    assert next(s for s in card.status() if s["id"] == "1-card")["written_through"] == 1000.0
