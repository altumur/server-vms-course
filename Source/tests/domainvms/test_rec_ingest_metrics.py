"""The recorder's own /metrics sums the ingest counters it actually keeps."""
from __future__ import annotations

import urllib.request
from types import SimpleNamespace

from tests.conftest import Box
from vms.recworker import RecWorker


class _Ingest:
    def stats(self):
        return {
            "cam-a": {"repeats_dropped": 5, "absurd_frames": 4, "ahead_losses": 2},
            "cam-b": {"repeats_dropped": 3, "absurd_frames": 1, "ahead_losses": 7},
        }


def test_recorder_metrics_sum_supported_ingest_counters_by_process():
    worker = SimpleNamespace(
        keep_state={},
        reconciler=SimpleNamespace(running=lambda: []),
        volume_wait=False,
        backfilled=0,
        dropped_seconds=0.0,
        ingest=_Ingest(),
    )

    text = RecWorker.metrics_text(worker)

    assert "rec_ingest_repeats_dropped 8" in text
    assert "rec_ingest_absurd_frames 5" in text
    assert "rec_ingest_ahead_losses 9" in text


def test_recorder_archive_door_exposes_metrics_without_a_token():
    box = Box()
    worker = SimpleNamespace(
        store=None,
        wall=box.wall,
        epochs={},
        server="srv-1",
        name="r-1",
        objects=box.objects,
        vars=box.vars,
        resource_root=box.resource_root,
        eyes=None,
        _visible_from=lambda *_: 0.0,
        _kept_of=lambda *_: [],
        _held_since=lambda *_: None,
        verify_keep=lambda *_: True,
        metrics_text=lambda: "# TYPE rec_ingest_repeats_dropped counter\nrec_ingest_repeats_dropped 8\n",
    )
    server = RecWorker.serve_archive(worker, "127.0.0.1", 0)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{server.server_address[1]}/metrics") as reply:
            text = reply.read().decode()
            assert reply.status == 200
            assert reply.headers["Content-Type"].startswith("text/plain")
            assert "rec_ingest_repeats_dropped 8" in text
    finally:
        server.shutdown()
