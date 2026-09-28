"""One box in a temp directory: the platform's two stores, a spool and an
archive, a clock. No GStreamer — the actuator is the fake."""
from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from w2cplatform.objects import FsObjectStore  # noqa: E402
from w2cplatform.variables import FileVariables  # noqa: E402


class Clock:
    def __init__(self, t=1000.0): self.t = t
    def __call__(self): return self.t
    def advance(self, s): self.t += s


class Box:
    """The platform on one box, plus the two directories the archive resource needs."""
    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="vmsserver-")
        self.vars = FileVariables(os.path.join(self.root, "config"))
        self.objects = FsObjectStore(os.path.join(self.root, "objects"))
        self.spool = os.path.join(self.root, "spool")
        self.archive = os.path.join(self.root, "archive")
        self.clock, self.wall = Clock(), Clock(1_757_500_000.0)


def published_snapshot(objects, sub: str, rows: str = "cameras") -> dict:
    """The snapshot as a READER sees it: list `<sub>/snapshot/`, get each shard, merge.
    One object per worker is the published shape, so a test that reads one key is
    testing a shape the platform no longer has."""
    out = []
    for key in objects.list(f"{sub}/snapshot/"):
        raw = objects.get(key)
        if raw:
            out.extend(json.loads(raw).get(rows, []))
    return {rows: out}


def door_site(box) -> None:
    """What a scenario about the front door needs to EXIST before it is written (М10B Lesson 25): the door
    controller (camera 12 — one contact, two relays, no picture), the lobby camera 7 (a telemetry with five
    presets, its own motion analytics) and a motion detector on 7. The device rows are what their holder
    would have written on its first pass (`VmsWorker.describe_devices`)."""
    box.vars.put("vms/cameras/12", {"id": "12", "name": "front door", "source": "driverpack://acme/10.0.0.90/ch/1",
                                    "kind": "io"})
    box.vars.put("vms/devices/acme/10.0.0.90", {"events": "command,command.failed,io.input,silent", "rays": "1",
                                                "relays": "2", "ptz": "false", "presets": "0"})
    box.vars.put("vms/cameras/7", {"id": "7", "name": "lobby", "source": "driverpack://acme/10.0.0.77/ch/1"})
    box.vars.put("vms/devices/acme/10.0.0.77", {"events": "command,command.failed,motion,silent", "rays": "0",
                                                "relays": "0", "ptz": "true", "presets": "5"})
    box.vars.put("det/units/7-motion", {"name": "7-motion", "cam": "7", "kind": "motion", "enabled": "true"})


def cam(i, revision=1, enabled=True, **kw):
    return {"id": i, "name": f"cam{i}", "source": f"driverpack://file/cam{i}.mp4", "enabled": enabled,
            "priority": 100, "revision": revision, **kw}


class FakeStore:
    def __init__(self, rows): self.rows = rows
    def desired(self): return self.rows
