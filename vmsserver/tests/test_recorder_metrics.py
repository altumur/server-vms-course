"""What a recorder says about itself, as numbers on the console's `/metrics` (feedback BG).

A fenced recorder and a recorder with nothing assigned both showed "0 running". A volume that would not open, an
archive that went away and a writer that stalled were in the heartbeat and on the page — and there was nothing to
put an alert on. Nobody calls a recorder: the console reads what it published, as it does for everything else.
"""
from w2cplatform.contract import Heartbeat
from w2cplatform.spec import SpecController
from vms.config import REC_SPEC
from vms.console import _recorders
from tests.conftest import Box


def test_a_recorders_troubles_are_numbers_not_only_a_heartbeat():
    box = Box()
    rec = SpecController(REC_SPEC, box.vars.as_writer("console", REC_SPEC.acl_console()), box.objects, wall=box.wall)
    now = box.wall()
    box.objects.put(REC_SPEC.sub.heartbeat_key("r-1"), Heartbeat("r-1", now, [
        {"id": "7", "phase": "running"}, {"id": "8", "phase": "running"}, {"id": "9", "phase": "failed"}],
        {"server": "srv-1", "volume": "vol-a", "volume_error": "", "writer": {"state": "stuck"}, "spool": 12,
         "archive_away_since": now - 360.0, "fenced": False}).to_bytes())
    box.objects.put(REC_SPEC.sub.heartbeat_key("r-2"), Heartbeat("r-2", now, [],
        {"server": "srv-2", "volume": "vol-b", "volume_error": "read-only file system", "writer": {"state": "ok"}, "spool": 0,
         "archive_away_since": 0.0, "fenced": True}).to_bytes())
    text = "\n".join(_recorders(rec))                                # the recorders' part of `rec_metrics`
    for line in ('rec_recordings{worker="r-1",phase="running"} 2', 'rec_recordings{worker="r-1",phase="failed"} 1',
                 'rec_volume_error{worker="r-1"} 0', 'rec_volume_error{worker="r-2"} 1',
                 'rec_archive_away_seconds{worker="r-1"} 360.0', 'rec_archive_away_seconds{worker="r-2"} 0',
                 'rec_writer{worker="r-1",state="stuck"} 1', 'rec_writer{worker="r-2",state="ok"} 1',
                 'rec_spool_segments{worker="r-1"} 12'):
        assert line in text, line
    assert 'rec_recordings{worker="r-2"' not in text                  # nothing assigned: no row, and `rec_worker_fenced` says why
