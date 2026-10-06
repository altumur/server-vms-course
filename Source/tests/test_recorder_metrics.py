"""What a recorder says about itself, as numbers on the console's `/metrics` (feedback BG).

A fenced recorder and a recorder with nothing assigned both showed "0 running". A volume that would not open, an
archive that went away and a writer that stalled were in the heartbeat and on the page — and there was nothing to
put an alert on. Nobody calls a recorder: the console reads what it published, as it does for everything else.
"""
from w2cplatform.contract import Heartbeat
from w2cplatform.spec import SpecController
from vms.config import REC_SPEC
from w2cplatform.metrics import text as spec_metrics
from tests.vmsconftest import Box


def test_a_recorders_troubles_are_numbers_not_only_a_heartbeat():
    box = Box()
    rec = SpecController(REC_SPEC, box.vars.as_writer("console", REC_SPEC.acl_console()), box.objects, wall=box.wall)
    now = box.wall()
    box.objects.put(REC_SPEC.sub.heartbeat_key("r-1"), Heartbeat("r-1", now, [
        {"id": "7", "phase": "running"}, {"id": "8", "phase": "running"}, {"id": "9", "phase": "failed"}],
        {"server": "srv-1", "volume": "vol-a", "volume_error": "", "writer": {"state": "stuck"},
         "archive_away_since": now - 360.0, "archive_failure": "away", "fenced": False}).to_bytes())
    box.objects.put(REC_SPEC.sub.heartbeat_key("r-2"), Heartbeat("r-2", now, [],
        {"server": "srv-2", "volume": "vol-b", "volume_error": "read-only file system", "writer": {"state": "ok"},
         "archive_away_since": 0.0, "archive_failure": "", "fenced": True}).to_bytes())
    text = spec_metrics(rec)                                # the recorders' part of `rec_metrics`
    for line in ('rec_recordings{worker="r-1",phase="running"} 2', 'rec_recordings{worker="r-1",phase="failed"} 1',
                 'rec_volume_error{worker="r-1"} 0', 'rec_volume_error{worker="r-2"} 1',
                 'rec_archive_away_seconds{worker="r-1"} 360', 'rec_archive_away_seconds{worker="r-2"} 0',
                 'rec_writer{worker="r-1",state="stuck"} 1', 'rec_writer{worker="r-2",state="ok"} 1',
                 'rec_archive_failure{worker="r-1",kind="away"} 1'):
        assert line in text, line
    assert 'rec_archive_failure{worker="r-2"' not in text             # nothing failing: no line
    assert 'rec_recordings{worker="r-2"' not in text                  # nothing assigned: no row, and `rec_worker_fenced` says why


def test_a_recording_the_engine_refuses_is_counted_by_itself_and_its_last_frame_stops():
    """The review's third pass: one camera of thirty whose group of pictures is larger than a block is refused every
    sample — never written at all — and the volume, landing the other twenty-nine, said `ok`. Each recording's sink
    now tallies what the engine answered for ITS samples: the status carries `samples_refused`, `/metrics` the
    counter `rec_samples_refused_total{unit,status}`, and `last_frame_at` is the writer's last TAKE, so the refused
    recording's age grows while frames keep being offered."""
    from vms.obsd import CODE, ObsdError
    from vms.recworker import RecSink
    from vms.worker import fake_samples
    from tests.vmsconftest import recorder
    box = Box()
    rec = SpecController(REC_SPEC, box.vars.as_writer("console", REC_SPEC.acl_console()), box.objects, wall=box.wall)
    r = recorder(box, acl=False)

    class Volume:                                                   # takes 7's frames, refuses every one of 8's
        def put(self, unit, epoch, smp, backfill=False):
            if unit == "8":
                raise ObsdError(CODE["SEQUENCE_TOO_LARGE"], "PUT_MEDIA")
            return "OK"
    sinks = {u: RecSink(Volume(), u, 1, tally=r._tally) for u in ("7", "8")}
    r.rows = [{"id": u, "cam": u, "name": u, "enabled": True, "revision": 1} for u in ("7", "8")]
    from w2cplatform.reconcile import Reconciler, Want
    r.reconciler = Reconciler(lambda k, w: True, lambda k: None)      # both running, as far as the loop knows
    r.reconciler.once({u: Want(1) for u in ("7", "8")})
    t0 = box.wall(); r.writer_pass()
    box.wall.advance(30)
    for sink in sinks.values():
        for smp in fake_samples(t0, t0 + 10):
            try:
                sink.put(smp)
            except ObsdError:
                pass
    st = {row["id"]: r.status_extra(row) for row in r.rows}
    assert st["7"]["last_frame_at"] == t0 + 30 and "samples_refused" not in st["7"]
    assert st["8"].get("last_frame_at") is None and st["8"]["samples_refused"] == {"SEQUENCE_TOO_LARGE": 10}
    box.objects.put(REC_SPEC.sub.heartbeat_key("r-1"), Heartbeat("r-1", box.wall(), [
        {"id": u, "phase": "running", **st[u]} for u in ("7", "8")], {"server": "srv-1"}).to_bytes())
    text = spec_metrics(rec)
    assert 'rec_samples_refused_total{unit="8",status="SEQUENCE_TOO_LARGE"} 10' in text
    assert 'rec_samples_refused_total{unit="7"' not in text
    assert 'rec_last_frame_age_seconds{unit="7"} 0' in text


def test_a_cameras_stream_beyond_its_gaps_is_twelve_numbers_said_or_their_default():
    """The camera's numbers beyond its gaps («Прошивка», «Архитектор» 2026-10-06: the spec's `stream_up` …
    `card_state`). The course's camera recorder says `stream.up`, `stream.owed_s`, `stream.owed_gaps` and `card.state`;
    the leaves it cannot measure — live frames dropped, frames back in time, uploads held and their wait, the clock's
    shift, video on no clock line, live the card skipped, and what the card holds for the centre alone while a relay
    has not sent it up (`stream_owed_up_seconds`: the course does not count the card's relay chain) — stay out of its
    heartbeat, and the declaration's `default` prints them 0 (`card_state`: `recording`). Each by its value (ADR 0055): `12.5`, `0`, never `0.0`. The default
    stands for a leaf of a map that is there: a camera whose stream nobody says (no `stream` map) has no stream line, and
    a server's recorder — no card, no stream — none of the eleven."""
    box = Box()
    rec = SpecController(REC_SPEC, box.vars.as_writer("console", REC_SPEC.acl_console()), box.objects, wall=box.wall)
    now = box.wall()
    box.objects.put(REC_SPEC.sub.heartbeat_key("r-cam"), Heartbeat("r-cam", now, [], {
        "server": "cam-1", "card": {"state": "stalled", "tries": 0, "since": now},
        "stream": {"state": "pushing", "up": True, "lagging": False, "owed_s": 12.5, "owed_gaps": 2}}).to_bytes())
    box.objects.put(REC_SPEC.sub.heartbeat_key("r-mute"), Heartbeat("r-mute", now, [], {
        "server": "cam-2", "card": {"state": "", "tries": 0, "since": now}}).to_bytes())
    box.objects.put(REC_SPEC.sub.heartbeat_key("r-srv"), Heartbeat("r-srv", now, [], {"server": "srv-1"}).to_bytes())
    lines = spec_metrics(rec).splitlines()
    said = {"stream_up": "1", "stream_owed_seconds": "12.5", "stream_owed_gaps": "2"}
    stream = ("stream_up", "stream_owed_seconds", "stream_owed_gaps", "stream_owed_up_seconds",   # (no relay chain: 0)
              "stream_live_drops_total", "stream_frames_back_total",
              "stream_uploads_held", "stream_upload_wait_seconds_total", "camera_clock_shift_seconds",
              "camera_clock_unplaceable_seconds_total")
    for name in stream:
        line = f'rec_{name}{{worker="r-cam"}} {said.get(name, "0")}'
        assert line in lines, line
        assert not any(ln.startswith(f'rec_{name}{{worker="r-mute"}}') for ln in lines), name   # no stream map: no line
    for w, state in (("r-cam", "stalled"), ("r-mute", "recording")):              # r-mute's empty word: the `default`
        assert f'rec_card_live_skipped_seconds_total{{worker="{w}"}} 0' in lines, w
        assert f'rec_card_state{{worker="{w}",state="{state}"}} 1' in lines, w
    assert not any('worker="r-srv"' in ln for ln in lines
                   if ln.split("{")[0][4:] in stream + ("card_live_skipped_seconds_total", "card_state"))   # none of them
    for name in ("stream_up", "stream_owed_seconds", "stream_live_drops_total", "card_live_skipped_seconds_total"):
        assert sum(1 for ln in lines if ln.startswith(f"# TYPE rec_{name} ")) == 1, name
