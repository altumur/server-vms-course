"""One box in a temp directory: the platform's two stores, the resource's tree, a clock — and, for the
archive, a real obsd on a socket of its own. No GStreamer — the actuator is the fake."""
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
    """The platform on one box, plus the resource's tree (`archive`). The box's own volume goes beside it."""
    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="vmsserver-")
        self.vars = FileVariables(os.path.join(self.root, "config"))
        self.objects = FsObjectStore(os.path.join(self.root, "objects"))
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
OBSD_HINT = ("the archive's tests need obsd, the ObjectStorage daemon, with the patches of `standalone-build/patches/` "
             "(04: a block flushes by its period; 05: a timeline window of any length): build it with `ObjectStorage/standalone-build/build.sh <out>` and set "
             "OBSD_BIN=<out>/build/obsd (or put obsd on PATH)")
OBSD_GRACE_S = 3
OBSD_LINGER_MS = 300


class ObsdDaemon:
    _one = None

    def __init__(self):
        import atexit
        import shutil
        binary = os.environ.get("OBSD_BIN") or shutil.which("obsd")
        if not binary or not os.access(binary, os.X_OK):
            raise RuntimeError(OBSD_HINT)
        self.binary = binary
        self.dir = tempfile.mkdtemp(prefix="obsd-")              # the system's temp dir: a unix socket path is short
        self.socket = os.path.join(self.dir, "run", "obsd.sock")
        if len(self.socket.encode()) > 100:
            raise RuntimeError(f"the socket path {self.socket} is longer than unix sockets allow; set TMPDIR shorter")
        self._start()
        atexit.register(self.stop)

    def _start(self) -> None:
        import subprocess
        import time
        env = dict(os.environ, OBSD_WRITER_GRACE_S=str(OBSD_GRACE_S), OBSD_SESSION_LINGER_MS=str(OBSD_LINGER_MS),
                   OBSD_LOG_LEVEL=os.environ.get("OBSD_LOG_LEVEL", "error"))
        self.log = open(os.path.join(self.dir, "obsd.log"), "a")
        self.proc = subprocess.Popen([self.binary, "--socket", self.socket], env=env, stdout=self.log, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 10
        while not os.path.exists(self.socket):
            if self.proc.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError(f"obsd did not start: see {self.log.name}")
            time.sleep(0.05)

    def stop(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=60)
            except Exception:                                    # noqa: BLE001
                self.proc.kill()

    # The daemon restarted under its clients (the review's third pass, blocker 4): `kill` is a crash — SIGKILL, no
    # writer closed — and otherwise SIGTERM, every writer closed cleanly. The socket stays where it was; every
    # session the daemon knew is gone, and a client that says HELLO again under its token gets a new, empty one.
    def restart(self, kill: bool = True) -> None:
        if kill:
            self.proc.kill()
            self.proc.wait(timeout=10)
        else:
            self.stop()
        try:
            os.unlink(self.socket)
        except FileNotFoundError:
            pass
        self._start()

    @classmethod
    def get(cls) -> "ObsdDaemon":
        if cls._one is None:
            cls._one = cls()
        return cls._one

    @classmethod
    def fresh(cls) -> "ObsdDaemon":
        """A daemon of the test's own, on a socket of its own: what a test that restarts it uses, so that every other
        test's sessions on the shared one are left alone."""
        return cls()


def obsd_session(client: str = "test", token: str | None = None):
    from w2cplatform.obsd import Session
    return Session(ObsdDaemon.get().socket, client=client, token=token)


def obsd_volume(session, size: int = 64 << 20, max_block: int = 4 << 20, optimal_read: int = 512 << 10, label: str = "test"):
    """A fresh volume in a temp directory, formatted: `(volume, path)`."""
    path = tempfile.mkdtemp(prefix="vol-")
    vol = session.open_volume(params={"schema": "file", "path": path})
    vol.format(size, max_block=max_block, optimal_read=optimal_read, label=label)
    return vol, path


# A recorder on the box, with a session of its own on the test daemon, a small volume and a small block: what
# every test that records builds. Its volume, unless one is declared, is `file://<box.root>/volume`.
TEST_QUOTA, TEST_BLOCK, TEST_READ = 64 << 20, 4 << 20, 512 << 10
REC_ACL = ["rec/epoch/*", "rec/slots/*", "rec/holds/*"]


def recorder(box, name: str = "r-1", server: str = "srv-1", actuator=None, acl=None, **kw):
    from vms.recworker import RecWorker
    from vms.worker import FakeActuator
    vars_ = box.vars.as_writer(f"recworker-{name}", acl or REC_ACL) if acl is not False else box.vars
    kw.setdefault("env", {})
    kw.setdefault("default_quota", TEST_QUOTA)
    if kw.get("obsd") is None:
        kw["obsd"] = obsd_session(f"rec-{name}")
    return RecWorker(name, vars_, box.objects, actuator or FakeActuator(), clock=box.clock, wall=box.wall, server=server,
                     archive_root=box.archive, block=TEST_BLOCK, read=TEST_READ, **kw)


def store(name: str = "vol", quota: int = TEST_QUOTA, path: str | None = None, owner: str | None = None):
    """A volume of its own on the test daemon, open for writing: `vms.archive.Archive`."""
    from vms.archive import Archive
    path = path or tempfile.mkdtemp(prefix="vol-")
    return Archive("file://" + path, name, quota, owner or f"rec:{name}-{os.path.basename(path)}",
                   obsd_session(f"store-{name}"), block=TEST_BLOCK, read=TEST_READ).open()


def footage(st, unit, epoch: int, t0: float, t1: float, step: float = 1.0, backfill: bool = False, seal: bool = True):
    """Frames of `[t0, t1)` into a recording's stream, the sequence finished — and, unless told otherwise, the
    writer closed and taken again, so what was written is readable now (a reader sees only closed blocks)."""
    from vms.worker import fake_samples
    for smp in fake_samples(t0, t1, step=step):
        st.put(unit, epoch, smp, backfill)
    st.finish(unit, epoch, backfill)
    if seal:
        st.seal()


def door(box, st, name: str = "r-door", server: str = "srv-1", status: list | None = None):
    """A recorder's archive door over `st`, served, and a heartbeat that announces it — what the console and a
    scan find a recording's footage by. Returns the server; shut it down when done."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from w2cplatform.contract import Heartbeat
    from vms.config import REC_SPEC
    from vms.recworker import archive_routes, send_route
    routes = archive_routes(lambda: st, box.wall)

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            send_route(self, routes(self.path))                 # frames are streamed, as the recorder's own door does

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"

    def announce():                                  # a heartbeat, now: a test that moves the clock says it again
        box.objects.put(REC_SPEC.sub.heartbeat_key(name),
                        Heartbeat(name, box.wall(), status or [], {"server": server, "archive_url": url, "volume": st.name}).to_bytes())
    announce()
    srv.announce, srv.url = announce, url
    return srv
