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


# -- the archive's engine: a live `obsd`, one per test run ------------------------------------------------
#
# The archive is ObjectStorage, and ObjectStorage is a process (`w2cplatform/obsd.py`). The tests do not
# imitate it: they start the real daemon, once, on a socket of their own, with volumes in temp directories —
# never the box's daemon, never its socket. Without the daemon the archive cannot be tested, and the tests
# that need it say how to get it rather than pass for want of it.
#
# Two numbers are shorter than in production, so that a test of them does not wait a minute: how long a
# vanished session's writer waits for its owner, and how long a session with no connection survives.
OBSD_HINT = ("the archive's tests need obsd, the ObjectStorage daemon: build it with "
             "`ObjectStorage/standalone-build/build.sh <out>` and set OBSD_BIN=<out>/build/obsd (or put obsd on PATH)")
OBSD_GRACE_S = 3
OBSD_LINGER_MS = 300


class ObsdDaemon:
    _one = None

    def __init__(self):
        import atexit
        import shutil
        import subprocess
        import time
        binary = os.environ.get("OBSD_BIN") or shutil.which("obsd")
        if not binary or not os.access(binary, os.X_OK):
            raise RuntimeError(OBSD_HINT)
        self.dir = tempfile.mkdtemp(prefix="obsd-")              # the system's temp dir: a unix socket path is short
        self.socket = os.path.join(self.dir, "run", "obsd.sock")
        if len(self.socket.encode()) > 100:
            raise RuntimeError(f"the socket path {self.socket} is longer than unix sockets allow; set TMPDIR shorter")
        env = dict(os.environ, OBSD_WRITER_GRACE_S=str(OBSD_GRACE_S), OBSD_SESSION_LINGER_MS=str(OBSD_LINGER_MS),
                   OBSD_LOG_LEVEL=os.environ.get("OBSD_LOG_LEVEL", "error"))
        self.log = open(os.path.join(self.dir, "obsd.log"), "w")
        self.proc = subprocess.Popen([binary, "--socket", self.socket], env=env, stdout=self.log, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 10
        while not os.path.exists(self.socket):
            if self.proc.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError(f"obsd did not start: see {self.log.name}")
            time.sleep(0.05)
        atexit.register(self.stop)

    def stop(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=60)
            except Exception:                                    # noqa: BLE001
                self.proc.kill()

    @classmethod
    def get(cls) -> "ObsdDaemon":
        if cls._one is None:
            cls._one = cls()
        return cls._one


def obsd_session(client: str = "test", token: str | None = None):
    from w2cplatform.obsd import Session
    return Session(ObsdDaemon.get().socket, client=client, token=token)


def obsd_volume(session, size: int = 64 << 20, max_block: int = 4 << 20, optimal_read: int = 512 << 10, label: str = "test"):
    """A fresh volume in a temp directory, formatted: `(volume, path)`."""
    path = tempfile.mkdtemp(prefix="vol-")
    vol = session.open_volume(params={"schema": "file", "path": path})
    vol.format(size, max_block=max_block, optimal_read=optimal_read, label=label)
    return vol, path
