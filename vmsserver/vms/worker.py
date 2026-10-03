"""vmsworker — DriverPack as the worker: the process that HOLDS a camera.

One process, N pipelines, its own loop. It reads its assignment
(vms/workers/<me>) and the camera rows it names, runs М9's reconcile loop
over them with the actuator that builds `driverpacksrc ! tee` and serves the
tee as an RTSP fan-out (`rtsp://<server>:8554/<cam>`, in the heartbeat as
`live_url`) — one connection to the camera, N subscribers: the recorder
(the fourth subsystem, on a server with an archive), live gateways,
detectors, on any server. It takes an epoch per camera by CAS when it
starts one, holds a lease per camera, writes what it observes into the
camera's bucket on ITS server's resource, and publishes a heartbeat
carrying its status. It records nothing: recording is the recorder's
(`recorder.py`), a subscriber like any other. It never writes
configuration. Nomad (or systemd, on one box) supervises the process; the
process supervises its pipelines; nothing supervises the loop, because the
loop is the process.

What the environment hands a process, on a box or in an allocation:

    WORKER_NAME / SLOT_INDEX     -> the slot to claim: w-<index>. The index is the preference;
                                    the claim (CAS on vms/slots/w-N) is the proof
    SERVER_NAME (or the hostname) -> `server` in the heartbeat: whose resource its events go to, and the host in `live_url`
    LABELS                        -> `labels` in the heartbeat: what this server can reach; the controller places by them
    INSTANCE_ID                   -> the instance; CAPACITY -> the worker's own number, from М9 Lesson 7's probe

Not one of those names an orchestrator, and that is deliberate: a Quadlet, a
Nomad jobspec and a Kubernetes manifest each map their own names into these
five (`w2cplatform/runtime.py`), and the loop never learns which did.
"""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # worker.py — vmsworker: DriverPack as the worker — N pipelines against an assignment, an epoch per
# camera,
# a lease, a heartbeat with server, labels and capacity
#
# **Role in the module.** Lesson 4. One process, N pipelines, its own loop. `VmsWorker` extends
# `w2cplatform.contract.Worker` (see `contract.py` for `claim_slot`, `renew_slot`, `release_slot`,
# `take_epoch`, `renew_leases`, `heartbeat`) and is the thing that knows what a camera is. It reads its
# assignment `vms/workers/<me>` and the camera rows it names, runs М9's `Reconciler` over them
# (`reconciler.py`) with an actuator that builds `driverpacksrc ! tee ! …` (`gstvms/actuator.py`;
# `FakeActuator` here without GStreamer), takes an epoch per camera by CAS when it starts one, holds a lease
# per camera, writes events into the camera's bucket on this server's resource, and publishes a heartbeat
# carrying its status. It never writes configuration: its token is `vms/epoch/*`, `vms/slots/*` and
# `vms/devices/*` — the last one what it found a device to be, a discovery and not a decision. Nomad or
# systemd supervises the process; the process supervises its pipelines; nothing supervises the loop, because
# the loop is the process. The docstring names what the environment hands a process: `WORKER_NAME` /
# `NOMAD_ALLOC_INDEX` (the slot preference; the CAS claim on `vms/slots/w-N` is the proof),
# `NOMAD_NODE_NAME` or the hostname (`server`: which resource it records into), `NOMAD_META_labels`
# (`labels`: what this server can reach; the controller places by them), `NOMAD_ALLOC_ID` (the instance),
# `CAPACITY` (the worker's own number, from М9 Lesson 7's probe). Run by `__main__.worker`; tested in
# `tests/test_lesson4_worker.py` and used across Lesson 6's tests.
#
# ## Module-level names
# - `log` — logger `vmsworker`.
# - `VMS` — `Subsystem("vms")`, the key layout.
#
# ### `__init__(self, name, vars_, objects, actuator=None, lease_ttl=30.0, lease_margin=5.0,
# clock=time.monotonic, wall=time.time, server=None, capacity=None, instance=None, slot_ttl=45.0,
# archive_root=None, bucket_seconds=600, env=None)` `env` defaults to `os.environ` (tests pass a dict).
# `instance` defaults to `NOMAD_ALLOC_ID`, else the base class's `hostname:pid:6hex`. Calls
# `Worker.__init__` with `name=None` and then `claim_slot(prefer=name or slot_from_environment(env))` — so
# construction *is* the claim, and `self.name` is set afterwards. Then: `archive_root` from the argument or
# `$ARCHIVE` (`/data/archive`); `capacity` from the argument or `$CAPACITY` (50) — "М9 Lesson 7's B + n·I,
# measured on ITS server"; the actuator (`FakeActuator()` if none); an empty `rows`; the `Reconciler(self,
# self._actuate)`; `recording_allowed = True`; `server` from the argument, `NOMAD_NODE_NAME`,
# `NOMAD_NODE_ID`, else the hostname; `labels`, `alloc`; the two start clocks. Finally it reads the previous
# heartbeat object of this slot name: if one exists and was written by a different instance, `previous_hb`
# is its `ts` and `previous_instance` its instance — the controller's `failover_seconds` computes `started −
# previous_hb` from these, measured from what the workers wrote.
# `test_a_replacement_without_a_name_inherits_the_lapsed_slot`: two nameless workers get `w-1`, `w-2`; after
# `w-1` lapses (46 s of wall clock) a third nameless worker gets `w-1` back and starts its two cameras with
# epoch 2.
#
# ## Notes
# - Ordering: the slot is claimed in the constructor, before any assignment is read (the name is the row
#   key); an epoch is taken in `_actuate` before the pipeline starts; `lease_pass` checks the slot before
#   the leases.
# - Recovery needs no controller: `test_restart_with_the_controller_stopped` deletes the controller, starts
#   a fresh `w-1` with an empty `actual`, and it starts all three cameras from its assignment with epoch 2
#   each — the old instance is fenced by construction.
# - Three exits from a lost lease, all in `lease_pass`: reassignment (stop that one, continue), zombie
#   (fence everything), and slot taken (fence everything, first). A lease that merely expired because the
#   loop stalled shows up as `may_write` false in `_actuate` and a fresh epoch on the next start.
# - `observe` returns the bucket path, which the tests read back with `read_bucket`; the worker keeps
#   `observed` only for tests and diagnostics.
# ================================================================================================
from __future__ import annotations

import logging
import os
import socket
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from w2cplatform import runtime
from w2cplatform.console import STREAM_GRACE, STREAM_MIN_RATE, Deadlined, Paced, SendMixin, door_server, start_stream
from w2cplatform.contract import SchemaTooNew, Subsystem, Worker, check_schema
from w2cplatform.objects import ObjectStore
from w2cplatform.rows import finite
from w2cplatform.variables import Variables

from w2cplatform.events import ALARM, OBSERVATION, EventLog, Suppressor

from w2cplatform.sealing import Sealed, Sealer, open_row
from .config import (DEVICES, LIVE_PORT_BASE, LOOPBACK, PLAYBACK_PORT, RTSP_PORT, SHM_DIR, SPEC, announce_host, channel_of, describe, device_of,
                     device_identities, device_row, identity_of, live_shm, live_url, said_id,
                     playback_url, port_of, row)
from .reconciler import CONVERGED, Reconciler

# `UNCONFIRMED_MAX`: how long a holder goes on RECORDING past a lease's end while the store is silent.
#
#   unset      no ceiling. One box: the store is a directory on the same disk — away for one process, away for
#              all of them, and nobody can be given the next epoch. There is nobody to protect the camera from,
#              and `ttl − margin` was costing footage to guard against something that cannot happen
#   a number   seconds. A cluster: the store is on the network, and a worker cut off from it may still be
#              holding the camera's session while its successor cannot connect. Longer than `lost_after`, or
#              the recording stops before anybody has been given the camera (М11 sets it)
#   off        none at all: a lease that was not confirmed in time stops its camera, as before feedback BK
def unconfirmed_max(env) -> float | None:
    raw = str(env.get("UNCONFIRMED_MAX", "") or "").strip().lower()
    if not raw:
        return None
    return 0.0 if raw == "off" else float(raw)


# `COMMANDS_BEAT`: how often a holder looks at its request rows BETWEEN passes, in seconds (`VmsWorker.between`).
# A quarter of a second unless the environment says — the product's holder does the same (`commandsBeat`, 250 ms);
# `0` is "only on the pass", the loop as it was. What the process hands `run(beat=…)`.
COMMANDS_BEAT = 0.25


def commands_beat(env) -> float:
    raw = str(env.get("COMMANDS_BEAT", "") or "").strip()
    return float(raw) if raw else COMMANDS_BEAT


log = logging.getLogger("vmsworker")
VMS = Subsystem("vms")


# Bytes a door may hold at once, across its connections: `take(n, wait)` — True once `n` are free (within `wait`
# seconds), False if not; `force(n)` counts bytes it has whatever the limit says (a piece larger than was asked for: it
# is in memory already); `give(n)` frees them. The holder's playback door (`VmsWorker.playback_pieces`).
class ByteBudget:
    def __init__(self, limit: int):
        self.limit, self.used = int(limit), 0
        self.cond = threading.Condition()

    def take(self, n: int, wait: float) -> bool:
        deadline = time.monotonic() + wait
        with self.cond:
            while self.used and self.used + n > self.limit:   # nothing held: one piece goes, whatever its size
                left = deadline - time.monotonic()
                if left <= 0:
                    return False
                self.cond.wait(left)
            self.used += n
            return True

    def force(self, n: int) -> None:
        with self.cond:
            self.used += n
            if n < 0:
                self.cond.notify_all()

    def give(self, n: int) -> None:
        if n:
            with self.cond:
                self.used -= n
                self.cond.notify_all()


# М9 Lesson 6's `print()` with a memory — the actuator without GStreamer, and the one `__main__` falls back
# to. It mirrors `GstActuator`'s surface: callable, `pump()`, `stop_all()`, plus test hooks. State:
# `failing` (a set of camera ids, or a predicate, whose start fails), `calls` (every `(verb, id)`),
# `running` (ids started and not stopped), `epochs` (`{id: epoch}` as passed in the row at start), `dead`
# and `posted` (what tests push in to simulate a bus).
# What DriverPack connects to, without DriverPack: N channels, an archive of its own, a session budget.
# A camera with an SD card is a device with one channel; an NVR is a device with thirty-two. The real one
# is a DriverPack session; this one is what the tests hold.
class FakeDevice:
    """A held device: its channels, its own footage, and how many playbacks it allows at once."""

    def __init__(self, key: str, channels=(), coverage=None, max_playbacks: int = 2, bps: int = 1, index=None,
                 rays: int = 0, relays: int = 0, ptz: bool = False, presets: int = 0, events=(), identity: str = ""):
        self.key, self._channels = key, [str(c) for c in channels]
        self.identity = identity                                 # what the hardware says it is: a serial number, a MAC
        self._coverage = {str(k): v for k, v in (coverage or {}).items()}   # camera -> (from, to[, fragments])
        self._index = {str(k): [(float(a), float(b)) for a, b in v] for k, v in (index or {}).items()}
        self.max_playbacks, self.bps = max_playbacks, bps
        self.open: dict[str, tuple] = {}
        self.fetched: list[tuple] = []
        self.rays, self.relays, self.ptz = rays, relays, ptz or presets > 0     # what the `.rep` file would have said
        self.presets = presets                                   # how many the telemetry knows; 0 — it did not say
        self.events = tuple(events)                              # what its own analytics post: "motion", "tamper"
        self.did: list[tuple] = []                               # every command performed, in order

    def channels(self) -> list[str]:
        return list(self._channels)

    # What the device can DO, beside what it can show. Two of the eleven part-kinds DriverPack describes
    # (`ioDevice` with its `rayCount`/`relayCount`, and `telemetry`), because those are the two an
    # operator points at: open the door, look at the gate. Both are momentary — there is nothing to hold
    # open, nothing to fence over time — which is why they are requests and not units.
    #
    # And what it can SAY on its own: the analytics the device runs itself and posts on the bus (`events`).
    # The worker adds what it says about every unit it holds — `describe` below.
    def capabilities(self) -> dict:
        return {"rays": self.rays, "relays": self.relays, "ptz": self.ptz, "presets": self.presets,
                "events": list(self.events), **({"identity": self.identity} if self.identity else {})}

    def output(self, port: int, state: str, ms: int = 0) -> None:
        if not 1 <= int(port) <= self.relays:
            raise ValueError(f"{self.key} has {self.relays} relay(s), not {port}")
        self.did.append(("output", int(port), state, int(ms)))

    def preset(self, n: int) -> None:
        if not self.ptz:
            raise ValueError(f"{self.key} has no telemetry")
        if self.presets and not 1 <= int(n) <= self.presets:
            raise ValueError(f"{self.key} has {self.presets} preset(s), not {n}")
        self.did.append(("preset", int(n), "", 0))

    # The summary the holder puts in its heartbeat — not the index. Drawing a timeline must not
    # cost a session, and on a device that allows two of them, it must not cost a request either.
    def coverage(self, cam) -> dict | None:
        c = self._coverage.get(str(cam))
        return None if c is None else {"from": c[0], "to": c[1], "fragments": c[2] if len(c) > 2 else 0}

    # The INDEX: what the device actually holds, span by span. A card recording continuously has one span
    # and its summary says everything; an NVR recording on motion has hundreds, and between its `from` and
    # its `to` there is mostly nothing. Without this a scan is promised minutes that do not exist.
    #
    # Absent here means "this driver cannot list" — not "the device holds nothing". The two are different
    # answers and the caller has to be able to tell them apart, so it is `None` rather than `[]`.
    def recordings(self, cam, t0: float, t1: float) -> list[tuple[float, float]] | None:
        spans = self._index.get(str(cam))
        if spans is None:
            return None
        return [(max(a, t0), min(b, t1)) for a, b in spans if b > t0 and a < t1]

    def in_use(self) -> int:
        return len(self.open)

    def open_playback(self, cam, t0: float, t1: float) -> str:
        if len(self.open) >= self.max_playbacks:
            raise OverflowError(f"device {self.key}: {self.max_playbacks} playback sessions, all in use")
        sid = f"{cam}:{t0}:{len(self.fetched)}:{len(self.open)}"
        self.open[sid] = (str(cam), t0, t1)
        return sid

    def read(self, sid: str) -> bytes:
        cam, t0, t1 = self.open[sid]
        self.fetched.append((cam, t0, t1))
        return b"\x00" * max(1, int((t1 - t0) * self.bps))

    def close_playback(self, sid: str) -> None:
        self.open.pop(sid, None)

    def close(self) -> None:
        self.open.clear()


# Frames a fake pipeline writes: one sample per `step` seconds, a key frame first and then every `gop` seconds —
# enough for the engine to cut sequences, index them and hand them back, and few enough that an hour of footage is
# three thousand six hundred samples, not ninety thousand. Shaped like H.264 in Annex-B: a key frame carries a
# parameter set pair and an IDR slice, the others a slice — so an export of fake footage is an MP4 (`fmp4.py`).
FAKE_SPS = b"\x00\x00\x00\x01\x67\x42\x00\x1f\xe9\x01\x40\x7b\x20"
FAKE_PPS = b"\x00\x00\x00\x01\x68\xce\x38\x80"


def fake_samples(t0: float, t1: float, step: float = 1.0, gop: float = 2.0, size: int = 256) -> list:
    from w2cplatform.obsd import archive_ms, video
    out, t, since_key = [], float(t0), None
    while t < t1 - 1e-9:
        end = min(t + step, t1)
        key = since_key is None or t - since_key >= gop - 1e-9
        if key:
            since_key = t
        body = (FAKE_SPS + FAKE_PPS + b"\x00\x00\x00\x01\x65" if key else b"\x00\x00\x00\x01\x41") + b"\x80" * size
        out.append(video(archive_ms(t), archive_ms(end), body, key, 1280, 720))
        t = end
    return out


class FakeActuator:
    """М9 Lesson 6's print(), with a memory. `failing` is a set of camera ids
    (or a predicate) whose start fails. A recording's pipeline is handed a SINK — the volume's writer under the
    recording's stream — and `feed` is what a test calls to have it write frames, as a camera would."""

    def __init__(self, failing=frozenset()):
        self.failing = failing
        self.calls: list[tuple[str, int]] = []
        self.running: set[int] = set()
        self.epochs: dict[int, int] = {}
        self.dead: list[int] = []
        self.posted: list[tuple[int, str, dict]] = []
        self.fetched: list[tuple] = []                   # what `record_range` was asked for
        self.available = None                            # (source, t0, t1) -> spans the source really holds; None: all
        self.range_error = ""                            # set by a real actuator whose range pipeline failed
        # The prebuffer (Lesson 26): pipelines running ON HOLD — recording into a ring of the last
        # `ring_seconds` and writing nothing — and what each release wrote. `gop` is the keyframe interval:
        # a release starts at the first keyframe still in the ring, never mid-GOP.
        self.held: dict = {}                             # id -> {"since", "ring", "epoch", "sink"}
        self.released: list[tuple] = []                  # (id, start, end) of every ring written out
        self.gop = 2.0
        self.started: dict[int, dict] = {}
        # What each pipeline handed its sink, in bytes, cumulative — the writer watch's "offered" (Lesson
        # 10). A real actuator counts it at the sink's pad; the tests set it. None: not measured.
        self.offered_bytes: dict = {}

    def offered(self, cid):
        return self.offered_bytes.get(cid)

    # Records the call. `stop` always succeeds and removes the id. A start/restart on a failing id fails
    # (and clears `running`); otherwise the id is running and `cam["epoch"]` is remembered — the tests read
    # `act.epochs` to see which epoch the worker handed the pipeline.
    def __call__(self, verb: str, cam: dict) -> bool:
        cid = cam["id"]
        self.calls.append((verb, cid))
        if verb == "stop":
            self.running.discard(cid)
            self.held.pop(cid, None)
            return True
        if verb == "release":
            return self._release(cid, float(cam["now"]))
        fails = self.failing(cid) if callable(self.failing) else cid in self.failing
        if fails:
            self.running.discard(cid)
            return False
        self.running.add(cid)
        self.epochs[cid] = cam.get("epoch", 0)
        self.started[cid] = cam                     # what the pipeline was built from: the row plus what `enrich` added
        if cam.get("hold"):
            self.held[cid] = {"since": float(cam.get("now", 0)), "ring": float(cam.get("ring_seconds", 0)),
                              "epoch": cam.get("epoch", 0), "sink": cam.get("sink")}
        else:
            self.held.pop(cid, None)
        return True

    # Open the ring: what it holds is written first — from the oldest keyframe still in it, which is at most
    # `ring` seconds ago and never before the pipeline started — with the times it was CAPTURED, then live
    # footage follows. The real one removes a pad probe; this writes the frames.
    def _release(self, cid, now: float) -> bool:
        import math
        h = self.held.pop(cid, None)
        if h is None:
            return False
        oldest = max(now - h["ring"], h["since"])
        start = math.ceil(oldest / self.gop) * self.gop       # the ring may begin mid-GOP; the copy may not
        if start < now and h["sink"] is not None:
            for smp in fake_samples(start, now, gop=self.gop):
                h["sink"].put(smp)
            h["sink"].finish()
            self.released.append((cid, start, now))
        return True

    # What a camera would do to a running recording: `[t0, t1)` of frames through its sink, the sequence
    # finished at the end. Returns what the engine said of each, `{status: count}`.
    def feed(self, cid, t0: float, t1: float, step: float = 1.0) -> dict:
        from w2cplatform.obsd import ObsdError
        sink = (self.started.get(cid) or {}).get("sink")
        if sink is None or cid not in self.running:
            raise RuntimeError(f"recording {cid} is not running here: nothing to feed")
        said: dict = {}
        for smp in fake_samples(t0, t1, step=step, gop=self.gop):
            try:
                st = sink.put(smp)
            except ObsdError as e:
                st = e.name
            said[st] = said.get(st, 0) + 1
        sink.finish()
        return said

    # Returns and clears `dead` and `posted`; dead ids leave `running`. Same contract as `GstActuator.pump`.
    def pump(self) -> tuple[list[int], list[tuple[int, str, dict]]]:
        """(dead, posted). Tests push into `dead` and `posted` directly."""
        dead, self.dead = self.dead, []
        posted, self.posted = self.posted, []
        for cid in dead:
            self.running.discard(cid)
        return dead, posted

    # What an element would post on the bus: appends to `posted`.
    def post(self, cid: int, kind: str, **fields) -> None:
        """What an element would post on the bus."""
        self.posted.append((cid, kind, fields))

    # Fetch a range out of a device's own archive: its frames, with the times they were recorded at, as a real
    # actuator gets them from the holder's playback door. The recorder writes them into its volume.
    #
    # `available(source, t0, t1) -> [(a, b)]`, when a test sets it, is what the source ACTUALLY holds of the
    # range — a card with a hole in it (Lesson 16, and the feedback's point P: a summary cannot say where the
    # holes are). Only those spans come back. Unset, the source has everything it is asked for.
    def record_range(self, cam, source: str, t0: float, t1: float) -> list:
        spans = [(t0, t1)] if self.available is None else [(max(a, t0), min(b, t1)) for a, b in self.available(source, t0, t1)
                                                          if b > t0 and a < t1]
        out = []
        for lo, hi in spans:
            out += fake_samples(lo, hi, gop=self.gop)
            self.fetched.append((str(cam), lo, hi, source))
        return out

    def stop_all(self) -> None:
        self.running.clear()


# The live branch's RTP port for a camera on its worker's server: deterministic, so a gateway needs only the
# heartbeat (server + this) to subscribe, and nobody keeps a port table.
#
# `base` is the PROCESS's, not a constant (`RTP_BASE`, default 20000). Ids are unique inside a cluster, so
# two workers of one cluster on one box never collide. Two CLUSTERS on one box do: a cluster of one camera
# (М12 Lesson 10) calls its camera 1, and so does every other — on a real camera each has its own loopback,
# on a bench they all send RTP to 20001 and a picture turns up in someone else's window with no error.
def live_port(cid, base: int | None = None) -> int:
    from .config import LIVE_PORT_BASE
    base = LIVE_PORT_BASE if base is None else base
    try:                                         # a port is a number, and this is the only place an id must be one:
        return base + int(cid)                   # a named unit gets the base port and the fan-out has none to publish
    except ValueError:
        return base


# `WORKER_NAME` if set; else `w-<NOMAD_ALLOC_INDEX>`; else `None` — claim whatever is free, a lapsed slot
# first. The recorder uses the same rule with `RECORDER_NAME` and `r-`.
def slot_from_environment(env: dict, name_env: str = "WORKER_NAME", prefix: str = "w") -> str | None:
    return runtime.slot(env, name_env, prefix)   # None: claim whatever is free — a lapsed slot first


# `LABELS` split on commas, empties dropped — what this server can reach, as the runtime said it.
def labels_from_environment(env: dict) -> list[str]:
    return runtime.labels(env)


# `name` is a slot. Given (systemd's `%i`, Nomad's alloc index) it is claimed by that name — taken outright,
# even from a holder that has not lapsed, because the scheduler is the authority on which process is
# current; `None` means the environment's, and failing that "whichever slot is free" — a lapsed one first,
# so a replacement inherits its assignment. "A worker on a cluster is a worker on a box whose stores happen
# to be raft: same class, same heartbeat." It is also the `Store` of its own `Reconciler` (`desired()`).
#
# State beyond the base class: `archive_root` (this server's resource), `bucket_seconds`, `observed` (every
# `(cid, t, kind)` this instance wrote), `capacity`, `actuator`, `rows` (the assignment's camera rows,
# refreshed each pass), `assignment_rev`, `reconciler`, `recording_allowed` / `fenced_reason` (the
# instance-wide fence), `server`, `labels`, `alloc`, `started_at` (monotonic) and `_started_wall`, `passes`,
# `previous_hb` / `previous_instance` (what failover is measured from).
class VmsWorker(Worker):
    """`name` is a slot. Given (systemd's %i, Nomad's alloc index) it is
    claimed by that name; None means the environment's, and failing that
    "whichever slot is free" — a lapsed one first, so a replacement
    inherits its assignment. A worker on a cluster is a worker on a box
    whose stores happen to be raft: same class, same heartbeat. The
    recorder (`recorder.py`) is this class over another subsystem's rows."""

    SUB = VMS                       # the subsystem whose assignment and rows this worker runs
    ROWS = "cameras"                # <sub>/<ROWS>/<id>
    SLOT_PREFIX, NAME_ENV = "w", "WORKER_NAME"
    parse_row = staticmethod(row)

    def __init__(self, name: str | None, vars_: Variables, objects: ObjectStore, actuator=None,
                 lease_ttl: float = 30.0, lease_margin: float = 5.0, clock=time.monotonic, wall=time.time,
                 server: str | None = None, capacity: int | None = None, instance: str | None = None, slot_ttl: float = 45.0,
                 archive_root: str | None = None, bucket_seconds: int = 600, env: dict | None = None,
                 device_factory=None):
        env = dict(os.environ if env is None else env)
        instance = instance or runtime.instance(env)
        super().__init__(self.SUB, None, vars_, objects, lease_ttl, lease_margin, clock, wall, instance, slot_ttl)
        self.unconfirmed_max = unconfirmed_max(env)           # a holder writes DATA: it records through a silent store
        self.sealer = Sealer.from_env(env)                    # opens a device's password for the pipeline, and nothing else does
        self.sealed_errors: dict[str, str] = {}               # camera -> why its password could not be opened
        self.epoch_errors: dict[str, str] = {}                # camera -> why its epoch could not be taken (a garbled row)
        self.row_errors: dict[str, str] = {}                  # camera -> why its own row is not followed (it does not parse)
        self.claim_slot(prefer=name if name is not None else slot_from_environment(env, self.NAME_ENV, self.SLOT_PREFIX))
        self.archive_root = archive_root or env.get("ARCHIVE", "/data/archive")   # this server's resource: where its events go
        self.shm_dir = env.get("SHM_DIR", SHM_DIR)                                 # the tee's shared-memory branch, for subscribers on this server
        # THIS instance's two doors. Defaults are what they always were, so a box with one worker is
        # unchanged; `auto` asks the OS, which is what makes a SECOND worker on the same box possible at
        # all. Both numbers are published, never assumed: a subscriber reads the address out of the
        # heartbeat (`live_url`, `playback_url`), and it has done since Lesson 4.
        self.rtsp_port = port_of(env.get("RTSP_PORT"), RTSP_PORT)
        # What the two doors are BOUND to — and therefore what the heartbeat says their address is (`announce_host`).
        self.rtsp_host = env.get("RTSP_HOST")            # the fan-out is the actuator's to bind; the process says to what
        self.playback_host = env.get("PLAYBACK_HOST")    # set by `serve_playback`, which binds it
        self.playback_port = port_of(env.get("PLAYBACK_PORT"), PLAYBACK_PORT)
        self.rtp_base = int(env.get("RTP_BASE") or LIVE_PORT_BASE)                 # the live branch's ports: `live_port`, per cluster on a shared bench
        self.bucket_seconds = bucket_seconds
        # What this subsystem declared about repeats (`events.suppress`), held for as long as this worker
        # holds its units. The counters live HERE and nowhere else: this process is the only one that sees
        # the stream before it is a file, and the only one holding the epoch that makes the file writable.
        self.suppressor = Suppressor(SPEC.suppress)
        self.observed: list[tuple[int, float, str]] = []
        # Request ids this worker has served — performed, refused or expired, all three being answers.
        # The heartbeat carries them and the console's `clear_requests` removes the rows: a worker
        # writes no configuration, so it cannot delete what it has done, only say that it did it.
        self.fetched: list[str] = []
        # What became of the commands this worker was asked to perform, counted since it started: done, refused
        # by the device, or arrived after their moment. The last is the one to watch — a share of `expired` that
        # grows is the road from an event to this worker getting longer than the requests live (М10B Lesson 25).
        self.commands = {"performed": 0, "refused": 0, "expired": 0, "unknown": 0}
        # The road to the device, counted since this process started, over `ROAD_BUCKETS` (`_measure`): from the
        # request's `at` — the event's moment — to the call (`road`: two clocks), from the row's filing to the call
        # (`request_road`: two clocks), each by who asked; and from this worker's first sight of the row to the call
        # (`wait`: one clock, its own).
        self.road = {"auto": self._histogram(), "operator": self._histogram()}           # the event's moment -> the call
        self.request_road = {"auto": self._histogram(), "operator": self._histogram()}   # the row's filing -> the call
        self.wait = {"buckets": [0] * len(self.ROAD_BUCKETS), "sum": 0.0, "count": 0}
        self._first_seen: dict[str, float] = {}          # request -> when a pass of this worker first saw its row, by the clock
        self._requests_read: dict[str, tuple] = {}       # request -> (the unit it names, its fields if ours): read once (M5)
        self._marks_looked: set[str] = set()             # requests whose mark was read at their first sight (`_confirm`)
        self._appeared: dict[str, float] = {}            # request -> the wall time of the last listing that did not have it
        self._listed: tuple[float, set] | None = None    # (when, which requests) of the previous listing
        self._slow: set[int] = set()                     # devices whose last call did not answer inside `PERFORM_GRACE`
        self._dev_calls: dict[tuple, dict] = {}          # (question, device) -> its one call not collected yet (`_ask_devices`)
        self._dev_lock = threading.Lock()                # …asked from the loop's thread and from the playback door's
        self._dev_pending: dict[int, int] = {}           # device -> its calls through `_ask_devices` not returned yet
        self._dev_said: set = set()                      # devices said slow, (question, device) said failing: once a spell
        self._said_coverage: dict[tuple, object] = {}    # ("coverage", device, camera) -> what the device said last
        self._heard: dict | None = None                  # the heartbeat's one round of answers, while it is being written
        self.reanswered = 0                              # requests answered before by this slot, said again (`_answered_before`)
        self._beat_failed = False                        # the look at the requests between passes is failing: said once (`beat_once`)
        self._marks_swept = -1e18                        # when the marks of requests that are gone were last cleared
        self._marks_owed: dict[str, bytes] = {}          # request -> its answered mark, not yet taken by the store (`_confirm`)
        self.capacity = capacity if capacity is not None else int(env.get("CAPACITY", "50"))   # М9 Lesson 7's B + n·I, measured on ITS server
        self.actuator = actuator or FakeActuator()
        self.rows: list[dict] = []
        # One session per DEVICE, not per channel. `device_factory(key)` opens it — a DriverPack session on
        # a box, a `FakeDevice` in the tests, `None` for a source with no archive of its own (a file).
        self.device_factory = device_factory or (lambda key: None)
        self.devices: dict[str, object] = {}
        self.described: dict[str, dict] = {}              # device -> the description this worker last wrote
        self.identities: dict[str, str] = {}              # device -> what it said it is (`identity`), as last written
        self.second_names: dict[str, tuple] = {}          # device -> (the name it is known by already, its identity): refused
        self.assignment_rev = 0
        self.reconciler = Reconciler(self, self._actuate)
        self.recording_allowed = True
        self.fenced_reason: str | None = None
        self.was_fenced: str | None = None               # why it was fenced last, once it has rejoined
        self.conflicts_carried = 0                       # epoch conflicts it met as a zombie, under the name it lost (`rejoin`)
        self._performing: dict[int, dict] = {}           # device -> the one command in flight into it
        self.store_errors = 0                            # passes and renewals the store did not answer
        self.pass_failures = 0                           # parts of the loop that raised, since the process started
        self.server = runtime.server(env, server)
        self.labels = labels_from_environment(env)
        self.alloc = runtime.instance(env) or ""          # published as `alloc` for the readers that already know that name
        self.started_at = clock()
        self._started_wall = self.wall()
        self.passes = 0
        # the previous instance of this slot, if it left a heartbeat: what failover is measured from
        self.previous_hb, self.previous_instance = 0.0, ""
        # A heartbeat that does not parse is one object's trouble (the review's second pass, M6) — here too: read
        # bare, it raised out of the constructor, and the process went into a restart loop over the very object its
        # first heartbeat would have replaced. Unparsed, there is no failover to measure; that is all it costs.
        raw = objects.get(self.sub.heartbeat_key(self.name))
        if raw:
            from w2cplatform.contract import parse_heartbeat
            old = parse_heartbeat(self.sub.heartbeat_key(self.name), raw)
            if old is not None and old.extra.get("instance") != self.instance:
                self.previous_hb, self.previous_instance = old.ts, old.extra.get("instance", "")

    # -- the store, as the reconciler sees it ------------------------------------
    # The reconciler's store: `self.rows`.
    def desired(self) -> list[dict]:
        """What the reconciler runs. A row with `live: on-demand` is NOT here: its device is
        still held (see `_refresh_devices`) and its archive still served, but no pipeline is
        built for it. Holding the device is what the row buys; the live fan-out is what `live`
        asks for."""
        return [r for r in self.rows if r.get("live", "always") != "on-demand"]

    # Read the assignment (`assignment_rev` kept for the heartbeat) and, for each unit it names, the row
    # `vms/cameras/<id>`; rows that are missing or marked `deleted: "true"` are skipped. "A fresh worker
    # knows nothing and reads everything; nothing about what is running is stored." An unassigned worker has
    # no rows and invents nothing (`test_worker_runs_its_assignment…`: the first `reconcile_once` is `[]`).
    def refresh(self) -> None:
        """Read the assignment and the rows it names. A fresh worker knows
        nothing and reads everything; nothing about what is running is stored."""
        a = self.assignment()
        self.assignment_rev = a.rev
        rows, errors = [], {}
        for unit in a.units:
            items, _ = self.vars.get(self.SUB.config(self.ROWS, unit))
            if items and items.get("deleted") != "true":
                try:
                    rows.append(self.parse_row(items))
                    self.row_parsed(unit)
                except (ValueError, KeyError, TypeError) as e:
                    # One row that does not parse is that unit's (`Worker.row_garbled`; the sixth pass, the follow-up),
                    # and it is not a unit taken away: what runs under the row read last keeps running, and a unit
                    # never read whole is not started. Raised out of here, it froze the whole worker at the rows of
                    # the pass before.
                    errors[unit] = self.row_garbled(unit, e)
                    last = next((r for r in self.rows if str(r["id"]) == unit), None)
                    if last is not None:
                        rows.append(last)
        self.rows, self.row_errors = rows, errors
        self._refresh_devices()

    # One connection per device, however many of its channels are assigned: an NVR with thirty-two cameras
    # is one session, not thirty-two — the same argument as "one connection to the camera" (Lesson 4), a
    # level up. A device no row names any more is closed.
    #
    # Opened and closed through `_ask_devices`, inside the pass's `DEVICE_HOLD` (the scaling pass): a session that does
    # not open within `DEVICE_GRACE` is not waited for — the device is held from the pass its open comes back in; one
    # that raises (a `ConnectionRefusedError` is an `OSError`, and went out of `refresh` as "the store did not answer"
    # and ended the pass) is that device's, said once and opened again on the next pass.
    def _refresh_devices(self) -> None:
        until = time.monotonic() + self.DEVICE_HOLD
        want = {device_of(r["source"]) for r in self.rows if r.get("source")}   # a recorder's rows name none
        self.second_names = {k: v for k, v in self.second_names.items() if k in want}
        opens = []
        for key in want - set(self.devices):
            if key in self.second_names and self._still_known_as(*self.second_names[key]):
                continue                                 # refused, and the other name still stands: not opened again
            self.second_names.pop(key, None)
            opens.append((("open", key), None, lambda key=key: self.device_factory(key)))
        for (_, key), dev in self._ask_devices(opens, until).items():
            if dev is not None:
                self.devices[key] = dev
        closes = []
        for key in set(self.devices) - want:
            dev = self.devices.pop(key)
            self.described.pop(key, None); self.identities.pop(key, None)
            if hasattr(dev, "close"):
                closes.append((("close", id(dev)), dev, dev.close))
        with self._dev_lock:                             # opens that came back after their device stopped being wanted
            late = [(k, c) for k, c in self._dev_calls.items() if k[0] == "open" and k[1] not in want and c["returned"].is_set()]
            for k, c in late:
                del self._dev_calls[k]
        closes += [(("close", id(c["out"])), c["out"], c["out"].close) for _, c in late
                   if c.get("out") is not None and hasattr(c["out"], "close")]
        self._ask_devices(closes, until)
        held = {id(d) for d in self.devices.values()}
        with self._dev_lock:                             # what a device that is not held any more said: not kept
            for k in [k for k, c in self._dev_calls.items() if k[0] != "open" and k[1] not in held and c["returned"].is_set()]:
                del self._dev_calls[k]
        self._said_coverage = {k: v for k, v in self._said_coverage.items() if k[1] in held}
        self.describe_devices(until)

    # NO CALL INTO A DEVICE WAITS ON THE LOOP'S THREAD (the scaling pass after the eighth review). `perform` was made on a
    # thread of its own in feedback BE; every other call into a device was made bare, on the thread that renews the
    # leases and writes the heartbeat: `capabilities` once a pass for every device, `channels`, `in_use` and every
    # camera's `coverage` once a heartbeat, the session's open and close. A driver that does not answer held the loop
    # for as long as it cared to — for ever, with the fake — and 100 devices of 200 that answer in a tenth of a second
    # were a pass of 10.5 s and a heartbeat of 31 s, measured; at the product's five seconds a call, a heartbeat of
    # 1500 s. Every such call now goes through here, with the commands' rules:
    #
    #   its own thread      the loop waits for the calls of one round TOGETHER, `DEVICE_GRACE` at most — one fifth of a
    #                       second however many hang — and never past `until`, the pass's or the heartbeat's
    #                       `DEVICE_HOLD`
    #   one at a time       a question to a device whose last call has not returned is not asked again: no second
    #                       thread piles onto a hung driver. Its answer, whenever it comes, is the next round's
    #   a slow device       one whose call outlasted a whole `DEVICE_GRACE` is in `_slow` — the same set the commands
    #                       use: asked, not waited for, until a call into it answers at once
    #   an error            the device's word, not the pass's end: not known this round, said once a spell
    #
    # `asks` is `[(key, device, call)]`, the key `(question, id(device), …)` (an open: `("open", device key)`). Returns
    # `{key: answer}` for the calls that answered; a key that is absent is NOT KNOWN — and every caller reads it so:
    # a description not changed, a device said `slow` in the heartbeat, the coverage it said last.
    DEVICE_GRACE = 0.2                                   # the one wait for a round of calls into devices: `PERFORM_GRACE`'s
    DEVICE_HOLD = 0.5                                    # seconds the device calls of one pass, or one heartbeat, may hold it

    def _ask_devices(self, asks, until: float | None = None) -> dict:
        start = time.monotonic()
        until = start + self.DEVICE_HOLD if until is None else until
        out, waiting = {}, []
        for key, dev, fn in asks:
            with self._dev_lock:
                call = self._dev_calls.get(key)
                if call is not None and call["returned"].is_set():
                    del self._dev_calls[key]             # an answer that came after it was given up on: this round's
                    self._collect(key, call, out)
                    continue
                if call is not None:
                    continue                             # still not back: not asked twice
                call = self._dev_calls[key] = {"dev": dev, "returned": threading.Event(), "t0": time.monotonic()}
                if dev is not None:
                    self._dev_pending[id(dev)] = self._dev_pending.get(id(dev), 0) + 1

            def run(call=call, fn=fn):
                t0 = time.monotonic()
                try:
                    call["out"] = fn()
                except Exception as e:                   # noqa: BLE001 — the device's word, whatever it is
                    call["error"] = str(e) or type(e).__name__
                call["took"] = time.monotonic() - t0
                with self._dev_lock:
                    if call["dev"] is not None:
                        n = self._dev_pending.get(id(call["dev"]), 1) - 1
                        if n > 0:
                            self._dev_pending[id(call["dev"])] = n
                        else:
                            self._dev_pending.pop(id(call["dev"]), None)
                    call["returned"].set()

            threading.Thread(target=run, name=f"{self.name}-device", daemon=True).start()
            if dev is None or id(dev) not in self._slow:
                waiting.append((key, call))
        deadline = min(time.monotonic() + self.DEVICE_GRACE, until)
        for key, call in waiting:
            call["returned"].wait(max(0.0, deadline - time.monotonic()))
        for key, call in waiting:
            with self._dev_lock:
                if call["returned"].is_set():
                    if self._dev_calls.get(key) is call:
                        del self._dev_calls[key]
                        self._collect(key, call, out)
                    continue
            dev = call["dev"]
            if dev is not None and time.monotonic() - call["t0"] >= self.DEVICE_GRACE:
                self._slow.add(id(dev))
                if id(dev) not in self._dev_said:
                    self._dev_said.add(id(dev))
                    log.warning("%s: device %s did not answer `%s` within %.1f s: not waited for until it answers at "
                                "once, and the heartbeat says it is slow", self.name, self._device_name(dev), key[0],
                                self.DEVICE_GRACE)
        return out

    # One call that came back: its answer into `out`, or its error said (once a spell). A quick answer clears the device's
    # name from `_slow`, as a quick command does (`_performed`) — unless another call into it has not returned: a device
    # hung on a command and quick to describe itself is still a device a call is hanging in.
    def _collect(self, key: tuple, call: dict, out: dict) -> None:
        dev = call["dev"]
        if dev is not None and call.get("took", 0.0) <= self.DEVICE_GRACE and not self._dev_pending.get(id(dev)):
            ahead = self._performing.get(id(dev))
            if ahead is None or ahead["returned"].is_set():
                self._slow.discard(id(dev))
                self._dev_said.discard(id(dev))
        said = (key[0], key[1])
        if "error" in call:
            if said not in self._dev_said:
                self._dev_said.add(said)
                log.warning("%s: device %s refused `%s` (%s): not known until it answers", self.name,
                            self._device_name(dev) if dev is not None else key[1], key[0], call["error"])
            return
        self._dev_said.discard(said)
        out[key] = call.get("out")

    def _device_name(self, dev) -> str:
        return next((k for k, d in self.devices.items() if d is dev), str(getattr(dev, "key", "?")))

    # What each held device is, written where automation reads it: `vms/devices/<device>` (`config.py` says
    # why a row). Only when the answer differs from what is stored — the first pass after a start compares
    # with the store, every later one with memory, so a worker that holds a camera for a year writes its row
    # once. A device that described nothing is left alone: silence is "unknown", and a row saying "no relays"
    # would be a lie that refuses scenarios.
    #
    # …and WHICH DEVICE it is, in its own word (`identity`; the review's eighth pass): a DNS name and the address it
    # resolves to are two keys here and one recorder, and only the process that opened it can ask the hardware. The
    # console reads it back to tell the two spellings apart (`config.one_device`).
    #
    # A SECOND NAME OF A DEVICE ALREADY KNOWN IS REFUSED (the owner's decision on the review's eighth pass). A name no
    # holder had opened was its key alone, and a camera moved onto it — `nvr50.local`, the recorder another camera holds
    # as `10.0.0.50` — passed the console with rights on its old device and on the new key's cameras, which were none;
    # the holder opened it on its next pass and the camera showed the recorder's channel. Now the identity the device
    # gives is looked up among the device rows (`device_identities`) when this holder first learns it: under ANOTHER key
    # of the same vendor, this name is a second one — its row is not written (two rows with one identity, and a restarted
    # holder of the first name would find the second and refuse the device by its own name), the device is closed, no
    # camera of it is started (`_actuate`), its status says what name the device goes by (`status`), and it is said in
    # the log once. A name never seen opens as before: that is how identities are learned. Each pass asks the store
    # whether the other name still stands (`_still_known_as`), so removing its stale row lets this one open.
    #
    # Asked through `_ask_devices` (the scaling pass): a device that did not answer this pass has its description as it
    # was — not known is not "no relays".
    def describe_devices(self, until: float | None = None) -> int:
        wrote = 0
        idents = self.identities
        known: dict | None = None                        # the device rows' identities, read once a pass when needed
        refused: list[tuple[str, str, str]] = []
        heard = self._ask_devices([(("capabilities", id(d)), d, d.capabilities) for d in self.devices.values()
                                   if hasattr(d, "capabilities")], until)
        for key, dev in self.devices.items():
            if hasattr(dev, "capabilities") and ("capabilities", id(dev)) not in heard:
                continue                                 # not known this pass: as it was
            caps = heard.get(("capabilities", id(dev)))
            desc, ident = describe(caps), identity_of(caps)
            if desc is None or (self.described.get(key) == desc and idents.get(key, "") == ident):
                continue
            if ident and idents.get(key, "") != ident:  # learned now: is it a device known by another name?
                if known is None:
                    known = device_identities(self.vars)
                other = next((k for k, i in sorted(known.items())
                              if i == ident and k != key and k.split("/", 1)[0] == key.split("/", 1)[0]), None)
                if other is not None:
                    refused.append((key, other, ident))
                    continue
            path, row = self.SUB.config(DEVICES, key), device_row(desc, ident)
            items, _ = self.vars.get(path)
            if items != row:
                self.vars.put(path, row)
                wrote += 1
            if known is not None and ident:
                known[key] = ident
            self.described[key], idents[key] = desc, ident
        for key, other, ident in refused:
            dev = self.devices.pop(key)
            self.described.pop(key, None); idents.pop(key, None)
            if hasattr(dev, "close"):
                self._ask_devices([(("close", id(dev)), dev, dev.close)], until)
            if self.second_names.get(key) != (other, ident):
                log.error("%s: device %s is not opened: it is the same device as %s, which is already in use under that "
                          "name. Point its cameras at %s, or, if nothing uses that name any more, remove its device "
                          "row", self.name, key, other, other)
            self.second_names[key] = (other, ident)
        return wrote

    # Whether the device row of `other` still says `ident` — the refusal of a second name holds while it does.
    def _still_known_as(self, other: str, ident: str) -> bool:
        try:
            items, _ = self.vars.get(self.SUB.config(DEVICES, other))
        except Exception:                                # noqa: BLE001 — a store that does not answer: the refusal stands
            return True
        return str((items or {}).get("identity") or "").strip() == ident

    # The same description, per unit, as it is carried in the heartbeat (`can`). The row is for this
    # cluster's automation; the heartbeat is how the description leaves the cluster — a domain reads
    # heartbeats and never another cluster's rows (М12, Lesson 16).
    def can_of(self, cam: dict) -> dict | None:
        dev = self.device_of_row(cam)
        return self.described.get(device_of(cam["source"])) if dev is not None else None

    # The device a camera is a channel of, and the device object if it is held.
    def device_of_row(self, cam: dict):
        return self.devices.get(device_of(cam["source"])) if cam.get("source") else None

    # -- the gate ---------------------------------------------------------------
    # The gate between the reconciler and the real actuator. For `start`/`restart`: refuse if the instance
    # is fenced (`recording_allowed` false); on `start`, or if no epoch is held for the unit,
    # `take_epoch(unit)` — a new epoch for a new writer — else reuse the held epoch (an edit's restart keeps
    # epoch 1); refuse if `may_write(unit)` is false (no lease, or a lost one); then call the actuator with
    # `epoch` added to the row — the number in the name of every stream a recorder writes (`<rec>/e<epoch>`) and
    # every event bucket a worker does. For `stop`: call the actuator
    # and `release(unit)` (forget epoch and lease). `test_lease_expiry_without_renewal_stops_starts`: after
    # 26 s without renewal `may_write` is false; a later start takes epoch 2.
    def _actuate(self, verb: str, cam: dict) -> bool:
        unit = str(cam["id"])
        if verb in ("start", "restart"):
            if not self.recording_allowed:
                return False
            if cam.get("source") and device_of(cam["source"]) in self.second_names:
                return False                                    # a second name of a device known already (`describe_devices`)
            if verb == "start" or unit not in self.epochs:
                try:
                    cam = dict(cam, epoch=self.take_epoch(unit))   # a new epoch for a new writer
                except OSError as e:
                    self.store_errors += 1
                    if unit in self.epochs and self.may_record(unit):
                        # A pipeline that fell over while the store is away comes back under the epoch this
                        # worker ALREADY holds (feedback BK). It is the same writer: nobody else could have been
                        # given a number meanwhile by a store that answers nobody. It used to wait for a new
                        # epoch, and the camera was not recorded for as long as the store was silent.
                        log.warning("%s: camera %s restarted under the epoch it holds (%d): the store did not answer "
                                    "for a new one (%s)", self.name, unit, self.epochs[unit], e)
                        cam = dict(cam, epoch=self.epochs[unit])
                    else:
                        # Never started by this worker: no epoch, no start — for THIS unit, this pass: a failed
                        # start the reconciler retries with its backoff. Raised out of here, it ended the pass
                        # for every unit after it.
                        log.warning("%s: camera %s not started: the store did not answer for its epoch (%s)", self.name, unit, e)
                        return False
                except Exception as e:                          # noqa: BLE001
                    # …and a row `vms/epoch/<unit>` that does not parse is THIS camera's trouble too (the review's fifth
                    # pass, the class det and survey were mended for in the fourth): the `ValueError` went out through the
                    # reconciler and ended the pass — the cameras after this one were not started, and one taken away
                    # was not stopped, every pass. A failed start now, retried with the reconciler's backoff, and why
                    # in the camera's status.
                    log.error("%s: camera %s not started: its epoch could not be taken (%s)", self.name, unit, e)
                    self.epoch_errors[unit] = str(e)
                    return False
                self.epoch_errors.pop(unit, None)
            else:
                cam = dict(cam, epoch=self.epochs[unit])
            if not self.may_record(unit):                       # data: a lease that ran out in silence still records
                return False
            cam = self.enrich(cam)                              # what the pipeline needs beyond the row: the fan-out here, the source for a recorder
            if cam is None:
                return False                                    # not startable now (a recorder whose camera nobody holds): the reconciler retries
            # The device's password, opened at the last moment and only for the pipeline (`w2cplatform/sealing.py`):
            # the row in the store, in this process's memory and in its heartbeat stays sealed.
            try:
                cam = open_row(self.sealer, cam, self.SUB.config(self.ROWS, str(cam["id"])))
            except Sealed as e:
                log.error("%s: camera %s not started: %s", self.name, unit, e)
                self.sealed_errors[unit] = str(e)               # in its status, not only in this log (feedback CD)
                return False
            self.sealed_errors.pop(unit, None)
            return self.actuator(verb, cam)
        ok = self.actuator("stop", cam)
        self.release(unit)
        return ok

    # What the pipeline needs beyond the row. The worker's tee: its RTSP fan-out (`live_url`) and the loopback
    # port the fan-out server listens on. `None` means "cannot start now".
    #
    # A device with no picture (`kind: io` — a door controller, a relay board) gets none of it, and that
    # absence is the whole of its special treatment. There is no fan-out to publish, so nothing is
    # published; the recorder looks for a holder with a `live_url` and does not find one, the gateway the
    # same, the page the same. One field decided in one place, and no second branch anywhere else.
    def enrich(self, cam: dict) -> dict | None:
        if cam.get("kind") == "io":
            return dict(cam)
        return dict(cam, live_url=live_url(announce_host(self.rtsp_host, self.server), cam["id"], self.fanout_port()), live_port=live_port(cam["id"], self.rtp_base),
                    live_shm=live_shm(cam["id"], self.shm_dir))

    # Seconds since start on the monotonic clock — the reconciler's `now` for backoff.
    def now(self) -> float:
        return self.clock() - self.started_at

    # -- the passes ---------------------------------------------------------------
    # One pass: `refresh`, `reconciler.reconcile(now)`, count the pass, log each action. The base class's
    # abstract method; called by `run` and directly by every test.
    #
    # NOT KNOWING IS NOT "NO" (feedback BC). A store that did not answer says nothing about what this worker
    # should be doing: it goes on with the assignment and the rows it read last — what is running keeps running,
    # what fell over is started again, when the store lets it take an epoch. It used to raise out of the pass,
    # and the pass used to be the only place the local work was done.
    def reconcile_once(self, now: float | None = None) -> list[tuple[str, int]]:
        try:
            self.refresh()
        except OSError as e:
            self.store_errors += 1
            log.warning("%s: the store did not answer (%s); going on with the last assignment read", self.name, e)
        actions = self.reconciler.reconcile(self.now() if now is None else now)
        self.passes += 1
        for verb, cid in actions:
            log.info("%s: %s camera %s", self.name, verb, cid)
        return actions

    # Renew the slot and every lease, and decide what a lost lease means. First `renew_slot()`: if the slot
    # is held by another instance now, `fence("slot w-N is held by another instance now")` and return every
    # held unit — the zombie is fenced at the slot *before* any epoch is looked at
    # (`test_the_zombie_is_fenced_at_the_slot_first`: the replacement's `slot.gen == 2`). Then
    # `renew_leases()`; each lost unit's pipeline is stopped, it is dropped from `reconciler.actual` and
    # released, and the rest go on recording (`test_a_reassignment_is_not_a_zombie`: released, not fenced,
    # `recording_allowed` still true). Returns the lost units. `test_the_zombie_on_one_box`: A's `lease_pass`
    # returns `["1"]`, A is fenced with "slot w-1" in the reason, its epoch lease also reports a conflict, and
    # it may start nothing (`("failed", 1)`); B is fine.
    #
    # Since feedback BC, three rules, and the second replaces "a lost lease on a camera still mine: I am the
    # zombie, fence the instance":
    #
    #   the slot says who I am    only a slot row READ, naming another holder, fences the instance. A store that
    #                             did not answer is not that row: "still me", counted (`store_errors`). The slot
    #                             is a name; the right to write is the leases', and they run out by themselves
    #   a lease is one camera's   lost however it was lost — the camera went to another worker, it is in two
    #                             assignments for the seconds a controller takes to mend that, or the store did
    #                             not confirm the lease in time — ONE pipeline stops and its epoch is given up.
    #                             If the camera is still mine the reconciler starts it again, with its backoff,
    #                             under a new epoch. The slot was renewed a line above: there is no other
    #                             instance of me, and fifty cameras are not stopped for one
    #   a fence is not for ever   `rejoin`, below
    #
    # And since feedback BK the second rule has an exception, which is the whole of that decision: a lease that
    # ran out while the store was SILENT is not lost. The pipeline goes on under the epoch it has — DATA, which
    # a stale epoch cannot harm — and ACTIONS wait (`requests` asks the strict `may_write`). When the store
    # answers again: the same epoch, and nothing was stopped; another, and the camera stops as it always did.
    # `UNCONFIRMED_MAX` is the ceiling on that, in seconds past the lease's end; unset is none, `off` is the old
    # behaviour.
    def lease_pass(self) -> list[str]:
        """Renew the slot and every lease. Another holder on my slot: the instance
        fences. A lost lease: that one camera stops and gives its epoch up."""
        try:
            mine = self.renew_slot()
        except OSError as e:
            self.store_errors += 1
            log.warning("%s: the store did not answer for the slot (%s); still %s", self.name, e, self.name)
            mine = True
        except SchemaTooNew as e:
            # The store was raised past this build while it ran (the review's second pass, m4): the rows it
            # would read next are not what it thinks they are. Fenced, as a build older than the store does
            # not start — and it stays fenced (`rejoin` checks the same thing) until somebody restarts it new.
            self.schema_seen = None                   # what it read is not the store's layout any more (`rejoin`)
            self.fence(str(e))
            # Fenced with its slot in hand, it renews nothing: the row lapses and another process takes the name. From
            # the lease step that reads another holder there it is nobody, and says nothing under the name (the
            # review's sixth pass, beside `rejoin`) — until then the name is its own, and its heartbeat says `fenced`.
            self.name_taken()
            return list(self.epochs)
        if not mine:
            # NOBODY FROM THIS LINE (the review's sixth pass), as `keep_slot` makes every other worker: the name is the
            # other instance's, and so are its assignment and its heartbeat. It was fenced and kept the name — and a
            # heartbeat `fenced: true` went out over the legitimate one until `rejoin` took another slot, for as long
            # as that claim failed.
            self.give_up_name()
            self.fence(f"slot {self.name} is held by another instance now")
            return list(self.epochs)
        waiting = {u: l.epoch for u, l in self.leases.items() if l.unconfirmed() > 0}
        lost = self.renew_leases()
        for unit, epoch in waiting.items():
            lease = self.leases.get(unit)
            if unit not in lost and lease is not None and lease.silent_since is None:
                log.warning("%s: the store confirms epoch %d of camera %s again; nothing was stopped", self.name, epoch, unit)
        for unit in lost:
            lease = self.leases.get(unit)
            why = ("a newer epoch was issued for it" if lease is not None and lease.fenced
                   else f"unconfirmed for longer than UNCONFIRMED_MAX ({lease.unconfirmed_max:g} s)"
                   if lease is not None and lease.silent_since is not None and lease.unconfirmed_max
                   else "the store did not confirm the lease in time")
            log.warning("%s: camera %s stopped: %s", self.name, unit, why)
            # `lost` names units the way the lease does — as text. The reconciler keys by the row's id,
            # which the spec parsed (a number for cameras, a name for recordings): match it, never cast.
            uid = next((k for k in self.reconciler.actual if str(k) == unit), unit)
            self.actuator("stop", {"id": uid})
            self.reconciler.actual.pop(uid, None)
            self.release(unit)
        return lost

    # A fenced instance used to stay fenced: alive, renewing nothing, heartbeating `fenced: true` — which
    # placement does not read — and recording nothing until somebody restarted it by hand; a supervisor does not
    # restart a process that has not died (the product's Go worker, feedback BC). Fenced, it is nobody: the
    # slot it had belongs to the instance that took it. So on its next pass it takes a FREE slot and starts
    # from nothing — no epochs, no rows, whatever that slot's assignment says. Returns the new name, or None
    # while there is no slot to take.
    def rejoin(self) -> str | None:
        if self.recording_allowed:
            return self.name
        # A store raised past this build: nobody to rejoin as (the review's second pass, m4). With the version it last
        # read whole (the review's fourth pass): `rejoin` asked bare, and a row that does not parse is "never read" to a
        # bare check — a worker fenced for any other reason never came back while one field was garbled, though
        # `renew_slot` keeps running on the same row with what it read. A worker fenced FOR the schema has no version
        # to keep (`lease_pass` forgets it): a garbled row is not proof the store came back to its layout.
        try:
            self.schema_seen = check_schema(self.vars, getattr(self, "schema_seen", None))
        except SchemaTooNew:
            return None
        except OSError:
            return None                               # not known: a fenced instance can wait a pass
        was = self.name
        # What the epochs said of the zombie goes with it to its next name. The leases that counted the conflicts are
        # let go on the next line, and under the name it lost it says nothing now — the number `vms_epoch_conflicts`
        # is there to show (М11 Lesson 9) would be shown by nobody (the sixth pass, the follow-up).
        self.conflicts_carried += super().conflicts()
        self.release_all()
        self.rows, self.assignment_rev = [], 0
        self.reconciler.clear()
        # The claim can fail — the store blinks, every candidate is taken under it — and it used to leave the instance
        # with no slot and the OLD name: an `OSError` went out of here, `renew_slot` with no slot said "still me", and
        # the heartbeat went on under a name another instance holds (the review's sixth pass; the fifth's blocker 3,
        # on this path). The name is given up first and the claim is `keep_slot`'s (`_seek_slot`): nobody until it
        # has a slot, and every pass tries again.
        self.give_up_name()
        if not self._seek_slot():
            return None
        name = self.name
        log.warning("%s: was fenced as %s (%s); rejoined as %s", self.instance, was, self.fenced_reason, name)
        self.recording_allowed, self.was_fenced, self.fenced_reason = True, self.fenced_reason, None
        return name

    def conflicts(self) -> int:
        return super().conflicts() + self.conflicts_carried

    # A fenced instance is nobody: the stand-in renews nothing for it — not the slot row that may still name it (a store
    # raised past this build fences it with its slot in hand), not its leases (feedback DD).
    def may_stand_in(self) -> bool:
        return self.recording_allowed

    # Once: log at error, set `recording_allowed = False` and `fenced_reason`, `actuator.stop_all()`,
    # `reconciler.clear()` — the pipelines were stopped underneath the loop. Idempotent (a second call
    # returns immediately). After this `_actuate` refuses every start and `observe` writes nothing; the heartbeat
    # says `fenced: true` while the name is still this instance's (a store raised past its build), and nothing at
    # all once the name is another's (`lease_pass` gives it up before it calls this: `seeking`).
    def fence(self, why: str) -> None:
        if not self.recording_allowed:
            return
        log.error("%s: FENCED (%s). Stopping every pipeline.", self.name, why)
        self.recording_allowed, self.fenced_reason = False, why
        self.actuator.stop_all()
        self.reconciler.clear()

    # An event: written by this worker, now (`wall()`), into the camera's bucket on this server's resource
    # under the epoch this worker holds for it — recording or not. `None` if no epoch is held for the camera
    # (not mine to observe) or the instance is fenced. Records `(cid, t, kind)` in `observed` and returns
    # the bucket path from `event_log(archive_root, cid, epoch, bucket_seconds).append(...)`. Nothing else
    # is told — no store write, no controller. `test_the_worker_observes_what_it_holds_recording_or_not`:
    # before the first reconcile `observe(1, ...)` is `None`; after it the line lands in
    # `<archive>/vms/1/e1/…`; camera 2 (not assigned) is `None`; after `fence` a post is dropped;
    # `vms/events` in the store stays empty.
    def observe(self, cid: int, kind: str, **fields) -> str | None:
        """An event: written by this worker, now, into the camera's bucket on
        this server's resource, under the epoch this worker holds for it —
        recording or not. A camera it holds no epoch for is not its to
        observe. Nothing else is told."""
        epoch = self.epochs.get(str(cid))
        if epoch is None or not self.recording_allowed:
            return None
        t = self.wall()
        # `t` is when the bus was drained; `occurred` is when the DEVICE says it happened, where the path that
        # posted the line knows it (the review's second pass, M11) — a driver that reads the device's clock passes
        # it in the fields; one that does not passes nothing, and no second time is invented. It is kept out of
        # the suppressor's identity: a repeat is the same thing, whatever the device's clock said each time.
        occurred = fields.pop("occurred", None)
        if occurred is not None:
            try:
                occurred = float(occurred)
            except (TypeError, ValueError):
                log.warning("%s: camera %s posted %s with occurred=%r, not a time; dropped", self.name, cid, kind, occurred)
                occurred = None
        self.observed.append((cid, t, kind))
        # Suppression stands between the observation and the file, and it is the LAST thing before the
        # write for a reason: everything above this line — the epoch, the fence, `observed` — is about
        # whether this worker may speak about this unit at all, and that answer does not change because
        # the same thing happened twice. What comes back is what belongs in the log: usually this line,
        # sometimes nothing, sometimes the summary of a window that just closed and then this line.
        lines = self.suppressor.lines(t, str(cid), kind, fields)
        if lines and occurred is not None:                      # the observation itself is the last line; a summary before it has its own times
            lt, lk, lf = lines[-1]
            lines[-1] = (lt, lk, {**lf, "occurred": occurred})
        return self._write(cid, epoch, lines, self.class_of(cid, kind))

    # The traffic class of one line: `alarm` when this DEVICE lists this kind among its alarms, else
    # `observation`. The platform fixes the two words and refuses anything else (`events.py`); which of a
    # device's kinds belong to which is the operator's, on the row, because it is a fact about the wiring —
    # the same `io.input` is a door forced on one camera and a technician's cabinet on the next.
    #
    # A camera this worker holds no row for reads as observation rather than refusing: the epoch says the
    # unit is mine, the row may be a pass behind, and downgrading a line beats dropping it.
    def class_of(self, cid: int, kind: str) -> str:
        row = next((r for r in self.rows if str(r.get("id")) == str(cid)), None)
        alarms = (row or {}).get("alarms") or ""
        names = alarms if isinstance(alarms, (list, tuple)) else str(alarms).split(",")
        return ALARM if kind in [str(n).strip() for n in names if str(n).strip()] else OBSERVATION

    # Writes the lines a suppressor handed back, and answers with the path of the LAST one — the caller
    # asked "where did my observation go", and the summary that may precede it is not its answer. `None`
    # when nothing was written, which is what a suppressed repeat is.
    def _write(self, cid: int, epoch: int, lines, cls: str = OBSERVATION) -> str | None:
        log_ = EventLog(self.archive_root, self.SUB.name, str(cid), epoch, self.bucket_seconds)
        path = None
        for t, kind, fields in lines:
            path = log_.append(t, kind, cls, **fields)
        return path

    # Windows that closed with nobody left to close them — the storm stopped, so no observation came to
    # carry the summary out. Called once a pass: without it a burst that ENDS is a burst nobody ever
    # counted, and the log says the quiet minute and the swallowed thousand with the same silence.
    #
    # A summary needs the epoch its window was opened under, and this worker may have lost the unit since.
    # Then the line is dropped rather than written under a fresh epoch: the events it counted belong to
    # the run that observed them, and moving them forward would put a predecessor's storm in a successor's
    # bucket. Being fenced drops them for the same reason, one that this whole file already obeys.
    def flush_suppressed(self) -> int:
        if not self.recording_allowed:
            return 0
        written = 0
        for unit, t, kind, fields in self.suppressor.flush(self.wall()):
            epoch = self.epochs.get(str(unit))
            if epoch is None:
                continue
            self._write(int(unit), epoch, [(t, kind, fields)], self.class_of(int(unit), kind))
            written += 1
        return written

    # The bus, drained: `actuator.pump()` gives `(dead, posted)`; every posted `(cid, kind, fields)` becomes
    # `observe(...)` — a line only if I still hold the epoch; every dead camera becomes
    # `reconciler.lost(cid, now)` (restart after backoff) plus `observe(cid, "silent")` — "the event with no
    # picture behind it, by definition".
    def pump_once(self) -> None:
        """The bus, drained: what elements posted becomes events — if I still
        hold the epoch — and what died becomes `lost` and a `silent` event."""
        self.drain_bus()
        try:
            self.serve_requests()                       # …and what somebody asked this device to DO
        except OSError as e:                            # the requests are rows in the store: no store, none this pass
            self.store_errors += 1
            log.warning("%s: the store did not answer for the requests (%s)", self.name, e)

    # The bus alone — on the pass, and on every beat between passes (`beat_once`): a device's event waited for the
    # pass, up to `poll` seconds, before it was a line any scenario could see — the part of the road from an event to
    # a device that no histogram measured, because the event's time is stamped when it is drained (the product drains
    # it in its loop of commands too). On the loop's thread either way: the actuator and the reconciler have no other.
    def drain_bus(self) -> None:
        dead, posted = self.actuator.pump()
        for cid, kind, fields in posted:
            self.observe(cid, kind, **fields)
        for cid in dead:
            self.reconciler.lost(cid, self.now())
            self.observe(cid, "silent")                 # the event with no picture behind it, by definition
        self.flush_suppressed()                         # …storms that ENDED, which no observation will close

    # Where the requests are served: here, on the loop's thread — a pulse and a preset take a moment. A recorder's
    # request is an hour off a camera's card and takes minutes: it serves them on its backfill thread
    # (`RecWorker.serve_requests`), so the leases and the heartbeat are not kept waiting (the review's second pass).
    def serve_requests(self) -> None:
        self.requests()

    # -- commands: `<sub>/requests/<id>`, done by whoever holds the device ------------------------------
    # The other half of what a device is. Until now a holder only OBSERVED: one connection, a fan-out,
    # events. A device also acts — a relay to pulse, a preset to go to — and the command has to travel the
    # same connection, because there is only one: a second process opening the device to click a relay is
    # the thing this subsystem is built not to do.
    #
    # So a command is a ROW, in the family the platform already has for "bounded work somebody asked for",
    # and the worker holding the unit performs it. Not a unit of its own: a pulse has no duration to hold,
    # no epoch to fence, nothing to reconcile — it happens and it is over. `RecWorker.requests` is the
    # same method for the same reason, one subsystem over.
    #
    # `valid_until` is the one field a recording's request does not need. Footage fetched an hour late is
    # still the footage; a door opened an hour late is an incident. A request that arrives after its
    # moment is EXPIRED, reported as such and cleared — never performed, never silently dropped.
    #
    # NOTHING LONG WHERE THE LEASES ARE RENEWED (feedback BE). `perform` is a call into a driver, and a driver's
    # call has no timeout of ours: a camera whose network went away with its session still held kept this
    # method — and with it the loop, the slot, the leases and the heartbeat of every camera of this worker —
    # for as long as the vendor's SDK cared to wait. So the call is made on a thread of its own:
    #
    #   PERFORM_GRACE     the loop waits this long for it: a device that answers at once is answered at once
    #   PERFORM_TIMEOUT   after this the request is answered `the device did not answer`, and cleared
    #   one at a time     while a call into a device has not returned, no second call is made into it — the next
    #                     requests wait their turn, or expire by their own `valid_until`
    #
    # And a worker that may no longer write for the unit does not act on it either: a fenced instance, or one
    # whose lease on the unit is lost, leaves the request for whoever holds the device now.
    #
    # A COMMAND HAS A DEADLINE, AND IT IS NEAR (feedback BI). `valid_until` was optional: a row without one
    # waited for its device for ever, and was performed the day the device came back. Without it a command is
    # refused; with one more than `MAX_VALID` away it is refused too — "open the door some time in the next
    # week" is not a command.
    #
    # AT MOST ONCE (the platform review, "a command with no fence check"). The answer to a request is said in
    # the heartbeat, seconds after the device was called. A worker that died in between left a request that
    # looked untouched, and whoever took the device next performed it again: a door pulsed twice, the second
    # time a minute later, with nobody at it. So before the device is called the worker says it is about to —
    # a MARK, `<subsystem>/commands/<id>` in the object store, the one place a worker may write besides its
    # own rows. A request that carries another instance's mark is not performed: it is answered `unknown: an
    # earlier instance … began it`, and a person decides. For a door, "perhaps twice" is worse than "perhaps
    # not at all".
    #
    # The mark is written only when the call is about to be made — the device is open and free — so a request
    # that waits for its device carries none. Marks of requests that no longer exist are cleared every
    # `MARK_SWEEP` seconds, by whichever worker gets there.
    #
    # And the mark is written CREATE-ONLY, and the unit is under a lease first (the review's second pass). Two
    # holders of one device in the same second — the seconds a controller takes to mend a double assignment —
    # both read "no mark" and both wrote one; now the store says which of them made it, and the other answers
    # `unknown`. A unit held with no lease (`live: on-demand`: the device is on the line, nothing recorded) took
    # no epoch and so had no fence: it takes one here, before its first command, so that a second holder fences
    # the first the way it would for a stream.
    #
    # LOOKED AT FOUR TIMES A SECOND (2 October 2026). A request used to wait for this worker's pass — two seconds
    # at worst, one on average, of a road whose whole length a person at a door feels. Between passes the loop now
    # looks at the request rows every `COMMANDS_BEAT` (`run`, `beat_once`): this same method, with every rule
    # above — the lease, the deadline, the mark, one call at a time. Nobody tells the worker anything: the row is
    # the request and the look is the worker's own, the same on a box and in a cluster. What it costs is one
    # listing of `<sub>/requests/` per worker per beat, and a read of each row ONCE, when it first appears (the
    # review's seventh pass, M5): every row of the cluster was read on every beat — another holder's, one answered
    # already — and twenty holders over two hundred standing rows were 16 000 reads of the store a second. The unit a
    # row names is remembered by its key (`_requests_read`), and the checks that need no row — answered, in flight —
    # come before any read. A request row is written once (the console files it create-only; a scenario's id is its
    # event's, the same row each time), so what was read is what stands.
    #
    # AND THE ROAD IS MEASURED HERE, where it ends (`_measure`). Two kinds of histogram, because there are two clocks:
    #
    #   wait   from this worker's first sight of the row to the call into the device — its own monotonic clock,
    #          so the number is this link's and nobody's skew
    #   road   from the request's `at` — the moment of the event that caused it, by the clock of whoever wrote
    #          the event — to the call, by this worker's wall clock. The whole road, and only as true as the two
    #          clocks agree: a negative one is counted (`skewed`) and taken as zero
    #
    # The evaluator's buckets (`AutoWorker.LATENCY_BUCKETS`), and three finer ones under a second: the road is a
    # fraction of a second now, and a histogram whose first bucket is one second would not show it.
    #
    # WHAT THE NUMBERS MEAN, SAID PRECISELY (the review's seventh pass, minor). `vms_request_to_device_seconds` was the
    # holder's first sight of the row, not its filing — and after a restart every standing row was "first seen" at
    # its call, a zero. And the road mixed automation's requests with an operator's clicks, whose `at` is the click.
    # Now three histograms, two of them split by who asked (`by`: `auto` for a scenario's row, `operator` for the rest):
    #
    #   road      from the event (`at`) to the call                            two clocks: the event's writer's, ours
    #   request   from the row's filing (`filed`; an operator's row: `at`) to the call   two clocks: the filer's, ours
    #   wait      from this worker's first sight of the row to the call        one clock, its own
    #
    # and a clock skew is counted in both directions where it can be seen. AHEAD: the writer's moment is after ours —
    # a road below zero, taken as zero. BEHIND: the row says it was filed before this worker's previous listing of
    # the requests, which did not have it — by more than `SKEW_SLACK`; only a request can be caught so (an event
    # happened before anybody filed for it, and nothing here bounds how long before).
    #
    # HUNG DEVICES DO NOT HOLD THE LOOP (the review's seventh pass, M7). The loop waited `PERFORM_GRACE` for every call,
    # and `budget` counted only what was answered — so a hung device cost a fifth of a second and nothing of the budget:
    # 100 of 200 devices hung for 30 s held the loop's thread 24.7 s, a fast command waited 7 s and the lease went
    # 13.9 s unrenewed; about 120 hung was past the lease. Three bounds now, the design number being a holder that keeps
    # its leases with every one of its devices hung (`HUNG_DEVICES`, 200):
    #
    #   REQUESTS_HOLD       the most one `requests` call holds the loop's thread, reading and waiting together; what
    #                       is left is the next look's, a beat away. The calls a look began are waited for TOGETHER,
    #                       `PERFORM_GRACE` at most: one fifth of a second however many of them hang
    #   budget              requests acted on per look — a call STARTED counts, answered or not; refusals, expiries too
    #   a slow device       one whose last call did not answer inside `PERFORM_GRACE` is not waited for at all: its
    #                       answer is collected by the next look (`_performed`), and a quick answer clears the name
    #
    # The budget is `COMMANDS_PER_LOOK`: every device of a holder of the design's size, commanded at once, is called in
    # one look — the design's burst (`COMMANDS_BURST`) many times over. What bounds a look on a slow store is
    # `REQUESTS_HOLD`, which cuts it first; the rest is a beat away. The sustained rate (`COMMANDS_SUSTAINED`) is what
    # the rows must not pile up at — the answers leave in the heartbeat (`FETCHED_BYTES`) and the console clears them
    # every `jobs.CLEAR_EVERY` (`clear_requests`).
    PERFORM_GRACE, PERFORM_TIMEOUT = 0.2, 10.0
    MAX_VALID, MARK_SWEEP = 600.0, 30.0
    ROAD_BUCKETS = (0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 300.0)
    COMMANDS_SUSTAINED, COMMANDS_BURST = 2.0, 16    # commands a second per holder: the design numbers of 2 October 2026
    HUNG_DEVICES = 200                              # devices hung at once a holder keeps its leases through (the test's)
    COMMANDS_PER_LOOK = HUNG_DEVICES                # every device of such a holder, commanded at once, called in one look
    REQUESTS_HOLD = 0.5                             # seconds one `requests` call may hold the loop's thread
    FETCHED_BYTES = 8192                            # the answered ids one heartbeat carries, oldest first
    FETCHED_COUNT = COMMANDS_BURST * 10             # …at most so many: the burst, for the ten seconds between two heartbeats
    SKEW_SLACK = 1.0                                # a filing this much before our previous listing: the writer's clock is behind

    @staticmethod
    def _histogram() -> dict:
        return {"buckets": [0] * len(VmsWorker.ROAD_BUCKETS), "sum": 0.0, "count": 0, "ahead": 0, "behind": 0}

    def _measure(self, rid: str, it: dict) -> None:
        def count(h: dict, seconds: float) -> None:
            h["sum"] += seconds
            h["count"] += 1
            for i, le in enumerate(self.ROAD_BUCKETS):
                if seconds <= le:
                    h["buckets"][i] += 1

        def two_clocks(h: dict, since, behind_of: float | None = None) -> None:
            try:
                at = float(since)
            except (TypeError, ValueError):
                return                                   # a row that does not say when: not counted here
            if at != at or at in (float("inf"), float("-inf")):
                return
            seconds = self.wall() - at
            if seconds < 0:
                h["ahead"] += 1                          # the writer's clock is ahead of this one: said, not hidden
            elif behind_of is not None and at < behind_of - self.SKEW_SLACK:
                h["behind"] += 1                         # filed "before" a listing that did not have it: its clock is behind
            count(h, max(0.0, seconds))

        count(self.wait, max(0.0, self.clock() - self._first_seen.pop(rid, self.clock())))
        by = "auto" if str(it.get("by", "")).startswith("auto/") else "operator"
        two_clocks(self.road[by], it.get("at"))
        filed = it.get("filed") if it.get("filed") not in (None, "") else (it.get("at") if by == "operator" else None)
        two_clocks(self.request_road[by], filed, self._appeared.pop(rid, None))

    def command_key(self, rid: str) -> str:
        return f"{self.SUB.name}/commands/{rid}"

    def began_by(self, rid: str) -> str | None:
        """The instance that said it was about to perform this request, or None."""
        mark = self.mark_of(rid)
        return None if mark is None else (str(mark.get("instance", "")) or "?")

    def mark_of(self, rid: str) -> dict | None:
        """The mark of this request as it stands, or None. Raises if the store does not answer."""
        raw = self.objects.get(self.command_key(rid))
        if raw is None:
            return None
        try:
            mark = json.loads(raw)
        except ValueError:
            return {"instance": "?"}                     # a mark that does not parse is still a mark
        return mark if isinstance(mark, dict) else {"instance": "?"}

    def sweep_marks(self) -> int:
        if self.clock() - self._marks_swept < self.MARK_SWEEP:
            return 0
        self._marks_swept = self.clock()
        prefix = f"{self.SUB.name}/commands/"
        marks = self.objects.list(prefix)                # the marks FIRST: a mark is written after its request,
        if not marks:                                    # so a mark listed here whose row is gone below is over
            return 0
        rows = {k.rsplit("/", 1)[1] for k in self.vars.list(self.SUB.requests_prefix())}
        gone = [k for k in marks if k.rsplit("/", 1)[1] not in rows]
        for k in gone:
            self.objects.delete(k)
        return len(gone)

    def requests(self, budget: int = COMMANDS_PER_LOOK, now: float | None = None) -> list[dict]:
        now = self.wall() if now is None else now
        held_from = time.monotonic()                     # the waits below are real seconds: so is their bound
        mine = {str(r["id"]): r for r in self.rows}
        done: list[dict] = self._performed()             # what calls already in flight have come to
        base, again, from_calls, begun = len(done), 0, 0, []   # what this look acted on: answers given, calls begun
        self.sweep_marks()
        listed_at = self.wall()
        keys = sorted(self.vars.list(self.SUB.requests_prefix()))
        # An answered request is remembered for as long as its ROW stands — the heartbeat carries it until the
        # controller clears the row — and not after: `fetched` grew by one id per command for the life of the
        # process (the review's third pass, minor). A retry after the row is gone is the console's to recognise,
        # by its key (`vms/console.py`).
        present = {k.rsplit("/", 1)[1] for k in keys}
        self.fetched = [r for r in self.fetched if r in present]
        self._first_seen = {r: t for r, t in self._first_seen.items() if r in present}
        self._requests_read = {r: v for r, v in self._requests_read.items() if r in present}
        self._marks_looked &= present
        if self._marks_owed:
            self._confirm_owed(present)                  # answers the store did not take the first time (`_confirm`)
        # When each row first appeared, as "after our previous listing" — what a filing that says otherwise is checked
        # against (`_measure`, `behind`). The first listing of a process knows of no before.
        self._appeared = {r: t for r, t in self._appeared.items() if r in present}
        if self._listed is not None:
            for r in present - self._listed[1]:
                self._appeared.setdefault(r, self._listed[0])
        self._listed = (listed_at, present)
        answered = set(self.fetched)
        in_flight = {c["rid"] for c in self._performing.values()}
        self._slow &= {id(d) for d in self.devices.values()}
        for key in keys:
            if len(done) - base - again - from_calls + len(begun) >= budget:
                break                                    # this look has acted on its share: the rest is the next look's
            if time.monotonic() - held_from >= self.REQUESTS_HOLD:
                break                                    # …or held the loop as long as one look may
            rid = key.rsplit("/", 1)[1]
            if rid in answered or rid in in_flight:
                continue                                 # one we have answered, or one in flight: not even read
            got = self._requests_read.get(rid)           # (the unit it names, its fields if the unit is ours)
            if got is None or (got[0] in mine and got[1] is None):
                it, _ = self.vars.get(key)
                if not it:
                    continue
                unit_of = str(it.get("unit", ""))
                got = self._requests_read[rid] = (unit_of, it if unit_of in mine else None)
            row = mine.get(got[0])
            if row is None:
                continue                                 # another worker's device: its row was read once, when it appeared
            it = got[1]
            self._first_seen.setdefault(rid, self.clock())   # what `wait` is measured from (`_measure`)
            unit = str(row["id"])
            if not self.recording_allowed or (unit in self.leases and not self.may_write(unit)):
                continue                                 # not mine to act on now: fenced, or the lease is lost
            # ANSWERED BEFORE, BY THIS NAME (the review's seventh pass, M6). A holder started again on standing rows
            # it had performed under its previous instance found that instance's mark on each, and answered
            # `unknown` with a `command.failed` — a scenario may fire on that — or `expired`; 53 and 16 of 69 in the
            # review's run. The answer is in the mark now (`_confirm`): a mark that says how the call went is that
            # call's answer, said again so the row is cleared, and nothing else — no event, no counter of outcomes.
            # Looked at once per row, at its first sight, before the deadline: performed is not expired.
            unmarked = False                             # read just now, and no mark: not read again before the call
            if rid not in self._marks_looked:
                mark = self.mark_of(rid)                 # raises if the store does not answer: not known is not "nobody"
                self._marks_looked.add(rid)
                unmarked = mark is None
                if mark is not None and mark.get("outcome"):
                    self._answered_before(rid, row, mark, done)
                    again += 1                           # a read, not a call: not of the budget
                    continue
            # ONE ROW'S TROUBLE IS THAT ROW'S (the review's sixth pass). Two things here were read or taken bare, and
            # either raised out of `requests` — out of every `pump_once`, for as long as the row stood — so no command
            # to ANY device of this holder was performed behind it: a `valid_until` that is not a number (which never
            # reaches the check that expires it), and, below, the epoch of a unit held without a lease, when its row
            # `<sub>/epoch/<unit>` does not parse. Each is a refusal now, answered like the others here.
            #
            # …and `nan`, `inf` are not a time either (the review's seventh pass, M3): `float("nan")` passed all three
            # checks below — every comparison with it is false — and a holder that came up three hours later performed
            # the command. `finite` refuses them with the words.
            try:
                until = finite(it.get("valid_until", 0) or 0)
            except (TypeError, ValueError):
                self._refused(rid, row, it, f"`valid_until` is not a time: {it.get('valid_until')!r}", done)
                continue
            if not until:
                self._refused(rid, row, it, "a command carries a deadline (`valid_until`): without one it would wait "
                                            "for its device for ever", done)
                continue
            if until - now > self.MAX_VALID:
                self._refused(rid, row, it, f"`valid_until` is more than {self.MAX_VALID:.0f} s away: that is not a command", done)
                continue
            if now > until:
                self.fetched.append(rid)                 # say so, so it is cleared rather than asked again
                done.append({"request": rid, "unit": row["id"], "expired": True})
                self.commands["expired"] += 1
                log.warning("%s: request %s expired unperformed (%.0fs late)", self.name, rid, now - until)
                continue
            # RIGHTS ARE THE DEVICE'S THE COMMAND WAS FILED FOR (the review's eighth pass, minor). The console asks for them on
            # every camera of the device (`command_cams`) and writes that device into the row (`device`); a command
            # waits up to `MAX_VALID`, and a camera moved onto a recorder's channel meanwhile would have the recorder
            # pulse a relay nobody with a right on it chose. Performed only on the device it was filed for. A row with
            # no `device` — a scenario's (asked again when its camera moves: `vms/console.py`, `source_cams`) or an
            # older console's — is performed as before.
            filed_for = str(it.get("device") or "")
            if filed_for and filed_for != device_of(str(row.get("source") or "")):
                self._refused(rid, row, it, f"camera {unit} was moved to another device after this command was given: it "
                                            f"was not performed — give it again if it is still wanted", done)
                continue
            dev = self.device_of_row(row)
            if dev is None:
                continue                                 # the device is not open yet: ask again next pass
            if id(dev) in self._performing:
                # A call this look began into the same device, not yet back: waited for — inside its own
                # `PERFORM_GRACE` and the look's `REQUESTS_HOLD` — so that two commands to a device that answers at once
                # go in one look, as they always did; a device that does not answer is not waited for twice.
                ahead = self._performing[id(dev)]
                if id(dev) not in self._slow and any(c is ahead for c, _ in begun):
                    left = min(ahead["t0"] + self.PERFORM_GRACE, held_from + self.REQUESTS_HOLD) - time.monotonic()
                    if left > 0:
                        ahead["returned"].wait(left)
                    if ahead["returned"].is_set():
                        got_back = self._performed()
                        from_calls += len(got_back)
                        done += got_back
                    elif time.monotonic() - ahead["t0"] >= self.PERFORM_GRACE:
                        self._slow.add(id(dev))
                if id(dev) in self._performing:
                    continue                             # a call into this device has not returned: wait your turn
            if unit not in self.leases:
                try:
                    self.take_epoch(unit)                # a device commanded is a unit fenced: its epoch, before the first command
                except OSError:
                    raise                                # the store did not answer: not known, for every request — `pump_once` says so
                except Exception as e:                   # noqa: BLE001 — a garbled epoch row, or no slot: this command's refusal
                    self.epoch_errors[unit] = str(e)     # …and in the unit's status, as a start refused for it is (`_actuate`)
                    self._refused(rid, row, it, f"its unit's epoch could not be taken: {e}", done)
                    log.error("%s: request %s not performed: the epoch of %s could not be taken (%s)", self.name, rid, unit, e)
                    continue
                self.epoch_errors.pop(unit, None)
            if not self.may_write(unit):
                continue                                 # taken and lost already, or not confirmed: whoever holds it now acts
            mark = None if unmarked else self.mark_of(rid)   # raises if the store does not answer: not known is not "nobody"
            if mark is not None and mark.get("outcome"):
                self._answered_before(rid, row, mark, done)      # answered meanwhile — by another holder of the device
                again += 1
                continue
            before = None if mark is None else (str(mark.get("instance", "")) or "?")
            made = self._mark(rid, unit, now) if before is None else False
            if made is None:
                self._refused(rid, row, it, self.CANNOT_MARK, done)
                continue
            if before is None and not made:
                before = self.began_by(rid) or "?"       # somebody made the mark between our read and our write
            if before is not None:
                why = f"unknown: an earlier instance ({before}) began it, and whether the device acted is not known"
                self.fetched.append(rid)
                done.append({"request": rid, "unit": row["id"], "error": why})
                self.commands["unknown"] += 1
                self.observe(row["id"], "command.failed", action=str(it.get("action", "")), error=why)
                log.warning("%s: request %s not performed — %s", self.name, rid, why)
                continue
            call = {"rid": rid, "row": row, "it": it, "at": self.clock(), "returned": threading.Event(), "answered": False,
                    "t0": time.monotonic()}

            def run(call=call, dev=dev):
                t0 = time.monotonic()
                try:
                    call["out"] = self.perform(dev, call["row"], call["it"])
                except Exception as e:                   # noqa: BLE001 — the device's word, whatever it is
                    call["error"] = str(e)
                call["took"] = time.monotonic() - t0
                call["returned"].set()

            self._performing[id(dev)] = call
            in_flight.add(rid)
            self._measure(rid, it)                       # the road ends here: the call into the device
            threading.Thread(target=run, daemon=True).start()
            begun.append((call, id(dev)))
        # The calls this look began, waited for TOGETHER — a device that answers at once is answered in this look — for
        # `PERFORM_GRACE` at most, and never past what is left of `REQUESTS_HOLD`. One after another, each hung device
        # was a fifth of a second of the loop's; now a look waits one fifth however many hang. A device that did not
        # answer last time is not waited for at all, and a call that outlasts a whole `PERFORM_GRACE` names its device
        # so; its answer, whenever it comes, is collected by a later look (`_performed`).
        if begun:
            deadline = min(time.monotonic() + self.PERFORM_GRACE, held_from + self.REQUESTS_HOLD)
            for call, dev_id in begun:
                if dev_id not in self._slow and deadline > time.monotonic():
                    call["returned"].wait(max(0.0, deadline - time.monotonic()))
            for call, dev_id in begun:
                if not call["returned"].is_set() and time.monotonic() - call["t0"] >= self.PERFORM_GRACE:
                    self._slow.add(dev_id)
            done += self._performed()
        return done

    # A request this holder's slot had answered before — its mark says how the call went (`_confirm`) — answered again,
    # so that the row is cleared: into `fetched`, and nowhere else. No event (it was written when the call came back),
    # no outcome counted twice; `reanswered` says how many, in the heartbeat.
    def _answered_before(self, rid: str, row: dict, mark: dict, done: list) -> None:
        self.fetched.append(rid)
        self.reanswered += 1
        done.append({"request": rid, "unit": row["id"], "answered": str(mark.get("outcome")),
                     "by": str(mark.get("slot") or mark.get("instance") or "?")})
        log.info("%s: request %s was answered before (%s, by %s): said again, not performed", self.name, rid,
                 mark.get("outcome"), mark.get("slot") or mark.get("instance"))

    # The answer, written into the mark once the device has said it — the mark is this holder's to write (the one place
    # a worker writes besides its own rows), and it is what an instance started after this one reads instead of
    # "an earlier instance began it" (`requests`). A call that did not answer leaves its mark as it was: whether the
    # device acted is not known, and `unknown` is then the truth. A store that does not take the write costs the
    # same: the next instance says `unknown`, as it did before; the answer already given stands.
    #
    # …AND AN ANSWER THE STORE DID NOT TAKE IS OWED, NOT DROPPED (the review's eighth pass, minor; 5 of 5): one failed write
    # and a restart in the ten seconds after was a false `command.failed` — the next instance found the bare mark and
    # said `unknown`. The mark is kept (`_marks_owed`) and written again at every look until the store takes it, or the
    # request's row is gone (`requests`); what stays open is a restart while the store is still not taking it.
    MARKS_OWED_PER_LOOK = 16

    def _confirm(self, rid: str, row: dict, outcome: str, it: dict) -> None:
        mark = json.dumps({"instance": self.instance, "slot": self.name, "unit": str(row["id"]), "outcome": outcome,
                           "action": str(it.get("action", "")), "at": self.wall()}).encode()
        try:
            self.objects.put(self.command_key(rid), mark)
            self._marks_owed.pop(rid, None)
        except Exception as e:                           # noqa: BLE001
            self.store_errors += 1
            self._marks_owed[rid] = mark
            log.warning("%s: the answer to request %s could not be written into its mark (%s); written again at the next "
                        "look", self.name, rid, e)

    def _confirm_owed(self, present: set) -> int:
        self._marks_owed = {r: m for r, m in self._marks_owed.items() if r in present}   # a row gone: its mark is swept
        wrote = 0
        for rid, mark in list(self._marks_owed.items())[:self.MARKS_OWED_PER_LOOK]:
            try:
                self.objects.put(self.command_key(rid), mark)
            except Exception:                            # noqa: BLE001 — still not taking it: the next look
                self.store_errors += 1
                break
            del self._marks_owed[rid]
            wrote += 1
        return wrote

    # The mark, create-only: `True` when this instance made it, `False` when somebody else did — the store says so
    # (`put_new`: a directory's `link`, М11's Variables by CAS on index 0). A store WITHOUT create-only answers
    # `None`, and the command is refused (the review's third pass). Reading the mark back after a last-writer-wins
    # write was the old fallback, and it is no fence: A puts, A reads its own name, B puts, B reads its own name —
    # two holders in the same two seconds both pulse the door. For a door, "not performed, and a person is told
    # why" is better than "perhaps twice".
    CANNOT_MARK = ("this object store cannot write a command's mark create-only (no `put_new`): two holders of the "
                   "device could both perform it, so neither does")

    def _mark(self, rid: str, unit: str, now: float) -> bool | None:
        put_new = getattr(self.objects, "put_new", None)
        if put_new is None:
            return None
        return bool(put_new(self.command_key(rid), json.dumps({"instance": self.instance, "slot": self.name, "unit": unit,
                                                               "at": now}).encode()))

    # What the calls in flight have come to: performed, refused by the device, or — after `PERFORM_TIMEOUT` —
    # not answered. A call that timed out is answered ONCE and stays in flight until the driver returns: the
    # device is busy for as long as the driver says it is, whatever we told the requester.
    def _performed(self) -> list[dict]:
        done = []
        for key, call in list(self._performing.items()):
            rid, row, it = call["rid"], call["row"], call["it"]
            if call["returned"].is_set():
                del self._performing[key]
                if call.get("took", 0.0) <= self.PERFORM_GRACE and not self._dev_pending.get(key):
                    self._slow.discard(key)              # it answered at once, nothing else hangs in it (`_collect`)
                if call["answered"]:
                    continue                             # it came back after we had said it did not answer
                if "error" in call:
                    self._refused(rid, row, it, call["error"], done)
                    self._confirm(rid, row, "refused", it)
                else:
                    self.fetched.append(rid)
                    done.append({"request": rid, "unit": row["id"], **call["out"]})
                    self.commands["performed"] += 1
                    self._confirm(rid, row, "performed", it)
                    self.observe(row["id"], "command", **call["out"])    # what was done to a device is an event about it
            elif not call["answered"] and self.clock() - call["at"] >= self.PERFORM_TIMEOUT:
                call["answered"] = True
                self._refused(rid, row, it, "the device did not answer", done)
        return done

    def _refused(self, rid: str, row: dict, it: dict, why: str, done: list) -> None:
        self.fetched.append(rid)                         # a refusal is an answer: do not ask for ever
        done.append({"request": rid, "unit": row["id"], "error": why})
        self.commands["refused"] += 1
        self.observe(row["id"], "command.failed", action=str(it.get("action", "")), error=why)

    # One command against an open device. Two verbs, because two are what an operator points at; a third
    # belongs here and not in a new place. Unknown verbs raise, which the caller turns into a refusal
    # recorded on the unit — an operator who asked for something this device cannot do gets an answer.
    def perform(self, dev, row: dict, it: dict) -> dict:
        action = str(it.get("action", ""))
        if action == "output":
            port, state, ms = int(it.get("port", 0)), str(it.get("state", "pulse")), int(it.get("pulse_ms", 0) or 0)
            if not hasattr(dev, "output"):
                raise ValueError("this device has no outputs")
            dev.output(port, state, ms)
            return {"action": action, "port": port, "state": state}
        if action == "preset":
            n = int(it.get("n", 0))
            if not hasattr(dev, "preset"):
                raise ValueError("this device has no telemetry")
            dev.preset(n)
            return {"action": action, "n": n}
        raise ValueError(f"unknown action {action!r}")

    # The read model, per assigned row: `id`, `ref`, `name`, `enabled`, `phase` (`running` if in
    # `reconciler.actual`; `pending` if disabled; `failed` if in `reconciler.failures`; else `pending`),
    # `position` (`converged | lagging | stalled`), `revision`, `observed_revision` (what is actually
    # running), `epoch` (held, or 0). This list is the heartbeat's `status`; the controller's `read_model`
    # and the console's `/cameras` show it, and `/metrics` counts `phase == running` into
    # `vms_cameras_running`.
    def status(self) -> list[dict]:
        st = self.reconciler.status()
        out = []
        for cam in self.rows:
            cid = cam["id"]
            pos, lag = st.get(cid, (CONVERGED, 0))
            phase = "running" if cid in self.reconciler.actual else ("pending" if not cam["enabled"] else
                                                                     ("failed" if cid in self.reconciler.failures else "pending"))
            lease = self.leases.get(str(cid))
            out.append({"id": cid, "ref": cam.get("ref", ""), "name": cam.get("name", str(cid)), "enabled": cam["enabled"], "phase": phase, "position": pos,
                        "revision": cam["revision"], "observed_revision": self.reconciler.actual.get(cid, {}).get("revision", 0),
                        "epoch": self.epochs.get(str(cid), 0),
                        # recording under an epoch the store has not confirmed: said, not hidden
                        **({"lease": "unconfirmed", "unconfirmed_s": round(lease.unconfirmed(), 1)}
                           if lease is not None and lease.unconfirmed() > 0 else {}),
                        **self.status_extra(cam)})
            if str(cid) in self.sealed_errors and phase != "running":
                out[-1]["why"] = f"its password cannot be opened: {self.sealed_errors[str(cid)]}"
            elif str(cid) in self.epoch_errors and phase != "running":
                out[-1]["why"] = f"its epoch could not be taken: {self.epoch_errors[str(cid)]}"
            elif str(cid) in self.row_errors:              # running or not: it is not following its row
                out[-1]["why"] = f"{self.row_errors[str(cid)]}; going on with the row read last"
            if cam.get("source") and device_of(cam["source"]) in self.second_names:   # running or not: its source is refused
                other = self.second_names[device_of(cam["source"])][0]
                out[-1]["why"] = (f"its device is already known as {other}: this name is not opened. Point the camera at "
                                  f"{other}, or, if nothing uses that name any more, remove its device row")
        for cam, st in zip(self.rows, out):                # `held`: the device is on the line, no stream is built
            if cam.get("live", "always") == "on-demand" and st["phase"] != "running":
                st["phase"] = "held" if self.device_of_row(cam) is not None else "pending"
        return out

    # What each held device is, and what it has that we have not imported. Discovery is an OBSERVATION and
    # goes where observations go: this worker's token writes `vms/epoch/*`, `vms/slots/*` and what a device
    # is (`vms/devices/*`), never `vms/cameras/*`. The operator imports channels from the page, with their
    # own token.
    #
    # Its two questions to each device are asked through `_ask_devices` (the scaling pass) — in the heartbeat's one round
    # (`heartbeat_once`), or on their own for the playback door's `/devices`. A device that did not answer them is
    # NAMED, not waited for: `state: slow` — its last call did not answer within `DEVICE_GRACE`, or has not returned —
    # or `state: failed` with the device's words, and what was not answered is left out rather than said as 0.
    def device_status(self) -> list[dict]:
        known: dict[str, set] = {}
        for r in self.rows:
            if r.get("source"):
                known.setdefault(device_of(r["source"]), set()).add(str(channel_of(r["source"]) or r["id"]))
        devices = sorted(self.devices.items())
        heard = self._heard if self._heard is not None else self._ask_devices(self._status_asks(devices))
        out = []
        for key, dev in devices:
            have = known.get(key, set())
            st: dict = {"device": key}
            if not hasattr(dev, "channels"):
                st.update(channels=0, known=sorted(have), unimported=[])
            elif ("channels", id(dev)) in heard:
                chans = [str(c) for c in heard[("channels", id(dev))] or []]
                st.update(channels=len(chans), known=sorted(have), unimported=[c for c in chans if c not in have])
            else:
                st["known"] = sorted(have)
            if ("in_use", id(dev)) in heard:
                st["playbacks"] = heard[("in_use", id(dev))]
            st["max_playbacks"] = getattr(dev, "max_playbacks", None)
            if "channels" not in st or "playbacks" not in st:
                failed = [q for q in ("channels", "in_use") if (q, id(dev)) in self._dev_said]
                st["state"] = "failed" if failed and id(dev) not in self._slow else "slow"
            out.append({**st, **({"can": self.described[key]} if key in self.described else {})})
        return out

    def _status_asks(self, devices) -> list:
        return [((q, id(d)), d, getattr(d, q)) for _, d in devices for q in ("channels", "in_use") if hasattr(d, q)]

    # A camera's coverage as its device says it (`status_extra`): from the heartbeat's round, or asked on its own; a
    # device that did not answer has the coverage it said LAST — the summary of an archive that was there a moment ago,
    # beside `state: slow` for its device — and one that never answered has none.
    def _coverage_of(self, dev, cid):
        if not hasattr(dev, "coverage"):
            return None
        key = ("coverage", id(dev), str(cid))
        heard = self._heard if self._heard is not None else self._ask_devices([(key, dev, lambda: dev.coverage(cid))])
        if key in heard:
            self._said_coverage[key] = heard[key]
        return self._said_coverage.get(key)

    # Where the device's footage is, span by span, clipped to `[t0, t1)`. `None` means this driver cannot
    # list — which is not the same answer as "the device holds nothing here", and the caller must be able
    # to tell the two apart. Costs no playback session: listing is not reading.
    def recordings(self, cam, t0: float, t1: float) -> list[tuple[float, float]] | None:
        row = next((r for r in self.rows if str(r["id"]) == str(cam)), None)
        if row is None:
            raise KeyError(cam)
        dev = self.device_of_row(row)
        if dev is None or dev.coverage(cam) is None:
            raise KeyError(cam)
        lister = getattr(dev, "recordings", None)
        return None if lister is None else lister(cam, t0, t1)

    # A range out of the device's own archive. The ceiling belongs to the hardware, not to this worker:
    # capacity here is still cameras, and an exhausted device is a 503 — the same admission control the
    # gateway does for viewers (Lesson 13), one floor down. On a camera, this competes with live for the
    # one uplink; on an NVR it usually does not.
    def playback(self, cam, t0: float, t1: float) -> bytes:
        return b"".join(self.playback_pieces(cam, t0, t1))

    # …A PIECE AT A TIME (the review's fifth pass, major). The door read the whole range in one `read` and wrote it in
    # one buffer: a thousand seconds of a 100 kB/s card was 100 MB in the holder — the process holding every camera
    # of its server — and a signed day of a card was enough to take it down. What a device's `read` gives is the
    # driver's to say, and the code here has only one driver, the fake: `read(session) -> bytes`, the whole range at
    # once. So the door never asks it for more than `PLAYBACK_PIECE` seconds: the range is cut to the device's
    # coverage, then read piece by piece — a session opened for each and closed before the next, so the door still
    # holds one of the device's sessions, not one per piece — and each piece goes out as it comes. A driver whose
    # `read` yields chunks (a stream: what a DriverPack session reading a card would be) is passed on chunk by chunk.
    # The first piece is read before anything is sent (the door takes it with `next`), so "no such archive" (404) and
    # "the device is full" (503) are still answers; a device that fails later ends the reply short, and the client
    # sees it (`playback_handler`).
    #
    # …AND THE DEVICE'S SESSION IS CLOSED BEFORE THE PIECE IS HANDED ON (the review's sixth pass, major). The piece was
    # yielded with the session still open, so the session was held for as long as the client took to read that piece:
    # two slow connections — from one address — held both playback sessions of a recorder that has two, and the
    # recorder closing a gap got 503. A session is now open only while the DEVICE is read: the piece is taken whole
    # (a driver that streams is read to the end of the piece — it is one piece, `PLAYBACK_PIECE` seconds, either
    # way), the session closed, and only then does the piece go to whoever is waiting for it.
    #
    # …AND A PIECE IS SIZED IN BYTES, AND THE DOOR'S PIECES HAVE A BUDGET (the review's seventh pass, major; a run: a
    # viewer with `view` on one camera, eight connections on one signed address, a camera of 8 Mbit/s — the holder went
    # from 45 to 503 MB, and from four addresses it would have been 1.9 GB). A piece of sixty seconds is a number of
    # bytes only the camera's bitrate says, and the door held one per connection. So:
    #
    #   bytes, not seconds  the first piece asks for `PLAYBACK_FIRST` seconds; every next one for as many seconds as
    #                       `PLAYBACK_PIECE_BYTES` came to at the rate the last one came at — never more than
    #                       `PLAYBACK_PIECE` seconds, never less than one
    #   a budget            the pieces the door holds across all its connections are at most `PLAYBACK_BUDGET` bytes:
    #                       a piece is read only when its bytes are free (`ByteBudget`), waiting `PLAYBACK_BUDGET_WAIT`
    #                       for them; past that the first piece is 503 and a later one ends the reply short — said, as a
    #                       device that failed half way is. A piece's bytes are the door's until the client has taken it
    #   one signature       holds at most `PLAYBACK_PER_SIGNATURE` connections at once (`playback_handler`): a signed
    #                       address is one viewer's, for one interval
    #
    # So what the door holds of pieces is the budget, whoever asks — a connection holds one piece at a time, and lets go
    # of it before it reads the next. A driver whose stream is far above the rate its first piece came at overshoots one
    # piece (counted, `force`), and the next is smaller.
    PLAYBACK_PIECE = 60.0
    PLAYBACK_FIRST = 2.0
    PLAYBACK_PIECE_BYTES = 4 << 20
    PLAYBACK_BUDGET = 64 << 20
    PLAYBACK_BUDGET_WAIT = 5.0
    PLAYBACK_PER_SIGNATURE = 2

    # …AND ONE PERSON HOLDS A SHARE OF IT, NOT ALL OF IT (the review's eighth pass, major; a run). The bound was per signed
    # address, and every `/segment` with another `from` is another signature: a viewer with `view` on one camera took
    # sixteen, opened them from two addresses and read at 80 kB/s — above `Paced`'s floor — and in fifteen seconds the
    # door's 64 MiB were his; everybody else's playback was 503, or ended at its next piece. So a signed viewer — the
    # name the console signed (`check_signed`), never a `v` that nobody checked, and in an open cluster nobody — holds
    # `PLAYBACK_PER_PERSON` connections at once whatever he was signed: a connection holds one piece at a time, so a
    # person holds `PLAYBACK_PER_PERSON × PLAYBACK_PIECE_BYTES` of the budget (16 of 64 MiB at the defaults), and three
    # quarters of it are other people's. A process of the cluster (a capability per camera) is held by the signature
    # bound alone, as before.
    PLAYBACK_PER_PERSON = 4

    def _playback_count(self, table: str, key: str, step: int, limit: int) -> bool:
        counts = self.__dict__.setdefault(table, {})            # one, whichever connection asks first
        with self.__dict__.setdefault("_playback_sigs_lock", threading.Lock()):
            n = counts.get(key, 0)
            if step > 0 and n >= limit:
                return False
            if n + step > 0:
                counts[key] = n + step
            else:
                counts.pop(key, None)
            return True

    def playback_signature(self, sig: str, step: int) -> bool:
        """Count a connection on a signed address in (`+1`: False when it has its `PLAYBACK_PER_SIGNATURE`) or out."""
        return self._playback_count("_playback_sigs", sig, step, self.PLAYBACK_PER_SIGNATURE)

    def playback_person(self, who: str, step: int) -> bool:
        """Count a connection of a signed viewer in (`+1`: False when he has his `PLAYBACK_PER_PERSON`) or out."""
        return self._playback_count("_playback_people", who, step, self.PLAYBACK_PER_PERSON)

    def playback_budget(self) -> "ByteBudget":
        return self.__dict__.setdefault("_playback_budget", ByteBudget(self.PLAYBACK_BUDGET))

    def playback_pieces(self, cam, t0: float, t1: float):
        row = next((r for r in self.rows if str(r["id"]) == str(cam)), None)
        if row is None:
            raise KeyError(cam)
        dev = self.device_of_row(row)
        cov = dev.coverage(cam) if dev is not None else None
        if cov is None:
            raise KeyError(cam)
        t0, t1 = max(float(t0), float(cov.get("from", t0))), min(float(t1), float(cov.get("to", t1)))
        budget = self.playback_budget()

        def pieces():
            at, span, held = t0, min(self.PLAYBACK_FIRST, self.PLAYBACK_PIECE), 0
            try:
                while at < t1:
                    budget.give(held)                    # the last piece is the client's now: its bytes are free
                    held = 0
                    want = self.PLAYBACK_PIECE_BYTES
                    if not budget.take(want, self.PLAYBACK_BUDGET_WAIT):
                        raise OverflowError(f"this door holds {budget.limit} bytes of footage at once, and they are "
                                            f"all being sent — retry")
                    held = want
                    b = min(t1, at + span)
                    sid = dev.open_playback(cam, at, b)  # OverflowError when the device is full
                    try:
                        got = dev.read(sid)
                        got = [bytes(got)] if isinstance(got, (bytes, bytearray, memoryview)) else [bytes(c) for c in got]
                    finally:
                        dev.close_playback(sid)          # before a byte of the piece is sent
                    size = sum(len(c) for c in got)
                    budget.force(size - held)            # what the piece really is, whatever was asked
                    held = size
                    rate = size / max(b - at, 1e-3)
                    span = max(1.0, min(self.PLAYBACK_PIECE, self.PLAYBACK_PIECE_BYTES / max(rate, 1.0)))
                    yield from got
                    at = b
            finally:
                budget.give(held)
        return pieces()

    # What the heartbeat says per unit beyond the platform's fields: the worker publishes `live_url` — where a
    # recorder, a gateway or a detector subscribes; never a viewer.
    # Which port the fan-out is really on. The actuator owns that server, so the actuator is asked; a fake
    # one has no door and the configured number stands. Asking rather than assuming is the same rule as
    # everywhere here: the process that opened the thing is the one that knows.
    def fanout_port(self) -> int:
        return int(getattr(self.actuator, "rtsp_port", 0) or self.rtsp_port)

    def status_extra(self, cam: dict) -> dict:
        """What the heartbeat says per camera beyond the platform's fields. Two kinds of output:
        `live_url`/`live_shm` — the stream now; `playback_url` + `coverage` — the archive the DEVICE
        wrote, which we did not. A subscriber needs nothing but this object, for either."""
        can = self.can_of(cam)
        if cam.get("kind") == "io":
            # Nothing to subscribe to, and saying so is the point: a subscriber reads this object and
            # nothing else, so an address published here would be an address somebody dials.
            return {"kind": "io", **({"can": can} if can else {})}
        out = {"live_url": live_url(announce_host(self.rtsp_host, self.server), cam["id"], self.fanout_port()),
               "live_shm": live_shm(cam["id"], self.shm_dir), **({"can": can} if can else {})}
        dev = self.device_of_row(cam)
        cov = self._coverage_of(dev, cam["id"]) if dev is not None else None
        if cov is not None:
            out["playback_url"] = playback_url(announce_host(self.playback_host, self.server), cam["id"], self.playback_port)
            out["coverage"] = cov                         # the SUMMARY: from, to, fragments — never the index
            # …and WHERE to ask for the index, which is not the same thing as carrying it. The heartbeat is
            # one object under a ceiling; thirty days of motion recording is thousands of spans. A door,
            # not a field (М10A Lesson 26 made the same choice for a mask).
            out["index_url"] = playback_url(announce_host(self.playback_host, self.server), cam["id"], self.playback_port).replace("/playback/", "/recordings/")
        return out

    # `max(0, capacity − len(rows))`: cameras this worker could still take. "Not CPU — a worker at 40 % CPU
    # with no assignment left is full." What the autoscaler reads via the controller's `headroom()` and
    # `/metrics`.
    def headroom(self) -> int:
        """What the autoscaler reads: cameras this worker could still take.
        Not CPU — a worker at 40 % CPU with no assignment left is full."""
        return max(0, self.capacity - len(self.rows))

    # `Worker.heartbeat(status, …)` to the object `vms/<name>/heartbeat` with the extras the platform reads
    # by name: `server`, `instance`, `alloc`, `labels` (comma-joined), `assignment_rev`, `fenced`,
    # `conflicts`, `passes`, `capacity`, `headroom`, `started`, `previous_hb`, `previous_instance`, `archive`
    # (the resource root it records into — on a cluster the value of Nomad's `meta.archive`, via `$ARCHIVE`). The
    # controller's `capacity_of`, `labels_of`, `server_of`, `headroom`, `failover_seconds` and the console's
    # metrics all read from here.
    #
    # The devices are asked ONCE for the whole heartbeat, in one round (`_ask_devices`, the scaling pass): every device's
    # `channels` and `in_use`, every camera's `coverage` — one fifth of a second at most however many hang, where it was
    # each call in turn on the loop's thread. What did not answer is said so (`device_status`), not waited for.
    def heartbeat_once(self) -> None:
        devices = sorted(self.devices.items())
        asks = self._status_asks(devices)
        for cam in self.rows:
            dev = self.device_of_row(cam)
            if cam.get("kind") != "io" and dev is not None and hasattr(dev, "coverage"):
                asks.append((("coverage", id(dev), str(cam["id"])), dev, lambda dev=dev, cid=cam["id"]: dev.coverage(cid)))
        self._heard = self._ask_devices(asks)
        try:
            self._heartbeat_now()
        finally:
            self._heard = None

    def _heartbeat_now(self) -> None:
        self.heartbeat(self.status(), server=self.server, instance=self.instance, alloc=self.alloc,
                       labels=",".join(self.labels), assignment_rev=self.assignment_rev,
                       fenced=not self.recording_allowed, conflicts=self.conflicts(), passes=self.passes,
                       store_errors=self.store_errors + sum(l.store_errors for l in self.leases.values()),
                       pass_failures=self.pass_failures,
                       unconfirmed=len(self.unconfirmed()),          # units recording past their lease, the store silent
                       **({"was_fenced": self.was_fenced} if self.was_fenced else {}),
                       capacity=self.capacity, headroom=self.headroom(), started=self._started_wall,
                       previous_hb=self.previous_hb, previous_instance=self.previous_instance,
                       devices=self.device_status(),
                       # `archive`: the resource tree its events go to — Nomad's meta.archive, through $ARCHIVE. A
                       # recorder says its own volume there instead (`RecWorker.heartbeat_extra`).
                       **{"archive": self.archive_root, **self.heartbeat_extra()})

    # What a subclass adds to the heartbeat. `fetched` for everyone — the requests this worker has
    # answered, which is how the rows get cleared — and a subsystem with one more fact about itself says
    # it by extending this, not by rewriting the heartbeat.
    #
    # EVERY ANSWER, OLDEST FIRST, UNDER A CEILING (the review's seventh pass, M6). It was the last 32 ids, once every ten
    # seconds: about three answers a second could be cleared, while the beat lets a holder answer sixteen. At three
    # commands a second the standing rows went 45 → 174 and on without a bound. Now as many as fit in `FETCHED_BYTES`
    # (a heartbeat is one object under the store's ceiling), oldest first: what is cleared leaves `fetched` with its
    # row, and the next heartbeat carries the next ones — a cursor that is the list itself.
    #
    # …AND BY COUNT, NOT BY THE LENGTH OF A NAME (the review's eighth pass, minor; a run): the ceiling was bytes, so a
    # heartbeat cleared `FETCHED_BYTES / (len(id) + 1)` — forty ids of an operator's 200 characters, four commands a
    # second, and the rows grew past it (30 a second: 1108 standing in 90 s). A long id, or one with a comma or a control
    # character in it, is said by its digest (`config.said_id`, which the console's `clear_requests` matches the same
    # way): every answer costs at most 41 bytes, and a heartbeat carries `FETCHED_COUNT` of them — 16 a second cleared,
    # the burst the beat allows, whatever the names. Faster than that for long is past the design (2 a second).
    def fetched_said(self) -> str:
        out, size = [], 0
        for rid in self.fetched[:self.FETCHED_COUNT]:
            said = said_id(rid)
            size += len(said) + 1
            if size > self.FETCHED_BYTES:
                break
            out.append(said)
        return ",".join(out)

    def heartbeat_extra(self) -> dict:
        return {"fetched": self.fetched_said(),
                **({"command_counts": dict(self.commands)} if any(self.commands.values()) else {}),
                **({"commands_reanswered": self.reanswered} if self.reanswered else {}),
                # What the beat waits on, said (the review's eighth pass, minor): devices whose last call did not answer
                # inside `PERFORM_GRACE` (`_slow`) and calls into devices not back yet — on `/metrics` as `vms_devices_slow`
                # and `vms_commands_in_flight` (`vms/console.py`, `beat_lines`).
                **({"devices_slow": len(self._slow)} if self._slow else {}),
                **({"commands_in_flight": len(self._performing)} if self._performing else {}),
                # The road to the device, as histograms since this process started (`_measure`).
                **({"command_road": self.road, "command_request": self.request_road, "command_wait": self.wait}
                   if self.wait["count"] else {}),
                # The playback door's key, once the door is open (`vms/playback.py`): what the console signs a viewer's
                # address with, and what a process derives its capability from. Here and not in a camera's status:
                # statuses are the read model the page shows.
                **({"playback_key": self.playback_key} if getattr(self, "playback_key", None) else {})}

    # -- the playback door ---------------------------------------------------------------------------
    # The holder's second surface, and the reason it is HTTP and not the RTSP fan-out: a browser has to
    # seek inside what it gets, and the recorder fetches ranges through the same door (Lesson 16). The
    # console proxies to it; nothing about a device leaves this process except bytes and the summary.
    #
    #   GET /playback/<cam>?from&to      the device's own footage for that range
    #   GET /recordings/<cam>?from&to    WHERE that footage is: the device's own index, span by span
    #   GET /devices                     what is held, and what channels are not imported yet
    #
    # The index is fetched and not heartbeated, and that is a decision rather than a detail. Thirty days of
    # motion recording on thirty-two channels is thousands of spans; the heartbeat is ONE object under a
    # ceiling (М10A Lesson 25 and 26), and a field that grows with the device does not belong in it. The
    # heartbeat keeps the summary — two numbers, enough to draw a timeline and to know there is something
    # to ask about — and whoever needs the spans pays a request for them.
    #
    # WHO MAY READ THE CARD (the review's fourth pass, blocker 4). `/playback/<cam>` asks — when the cluster is gated,
    # as the console does (`Gate.gated`) — for one of two things: the console's signature over this camera, these
    # minutes, an expiry and the viewer (`?…&exp&v&sig`, what `GET /segment` hands a browser), or the capability a
    # process derives from this door's key for this camera (`/playback/<cam>/<capability>`, the recorder and the
    # survey: `playback.process_url`). Neither: 403, and an `access.denied` line. A viewer's read is a line too,
    # `archive.read` with `source=device` — the console said it handed the address out; this says it was used,
    # by whom and from where. The listing and the device list stay as they were: where the footage is, not the
    # footage — a door between processes until mutual TLS. (The review's sixth pass asked for a signature on
    # `/devices` and `/recordings/<cam>` too; authentication between processes is put off to the mutual-TLS step by
    # the owner's decision. Until then whoever reaches this door on the network reads, unasked: the devices held,
    # their channels, how many playback sessions each has in use, and the spans every camera's card holds.)
    #
    # WHAT THE CONSOLE'S DOOR HAS, THIS ONE HAS (the same pass, major). The protections were the console's alone:
    # three hundred slow connections here were three hundred and two threads in the holder — the process holding
    # every camera of its server. The server is the console's (`door_server`: `PLAYBACK_CONNECTIONS` at once,
    # `PLAYBACK_PER_ADDRESS` to one address, the next answered 503 on the spot), the handler reads its request line
    # and headers under a deadline (`Deadlined`), and the footage goes out in pieces to a client that takes them
    # (`Paced`: `STREAM_PIECE` a write, `STREAM_MIN_RATE` on average) — with the device's session already closed.
    PLAYBACK_TIMEOUT = 30.0          # a client that sends or reads nothing for this long lets its thread go
    PLAYBACK_CONNECTIONS = 32        # connections the door serves at once: a holder's threads are its cameras' too
    PLAYBACK_PER_ADDRESS = 8         # …of which one address holds this many: a browser, a recorder, a survey
    PLAYBACK_MIN_RATE = STREAM_MIN_RATE   # bytes a second a client takes on average, over the time spent writing to it
    PLAYBACK_GRACE = STREAM_GRACE         # …counted once that time is past this many seconds
    PLAYBACK_SNDBUF = 256 << 10           # the kernel's send buffer a connection gets: a LAN's bandwidth × delay, not 4 MB

    def playback_journal(self):
        from w2cplatform.journal import Journal
        if getattr(self, "_playback_journal", None) is None:
            self._playback_journal = Journal(self.archive_root, f"door-{self.name}", self.wall)
        return self._playback_journal

    # `None` when the request may be served; else `(status, reason)`. `rest` is what follows `/playback/<cam>`. `seen`,
    # when given, is told who the signed viewer is (`who`) — only once the signature over that name was checked.
    def playback_refusal(self, cam: str, rest: str, q: dict, addr: str, seen: dict | None = None):
        from w2cplatform.access import Denied, Gate
        from . import playback as pb
        if getattr(self, "_playback_gate", None) is None:
            self._playback_gate = Gate(self.vars, self.wall)
        try:
            if not self._playback_gate.gated():
                return None                              # an open cluster: the console it fronts is open too
        except Denied as e:
            return e.status, e.why
        key = getattr(self, "playback_key", None)
        if not key:
            return 503, "this door has no key: it admits nobody in a gated cluster"
        import hmac
        if rest:
            if hmac.compare_digest(rest, pb.capability(key, cam)):
                return None                              # a process of this cluster, for this camera
            why = "a capability for another camera, or another door"
        else:
            try:
                who = pb.check_signed(key, cam, q, self.wall())
                if seen is not None:
                    seen["who"] = who
                self.playback_journal().say("archive.read", user=who, source="device", target=cam, addr=addr,
                                            **{"from": q.get("from"), "to": q.get("to"), "worker": self.name})
                return None
            except PermissionError as e:
                why = str(e)
        self.playback_journal().say("access.denied", user=str(q.get("v") or "?"), capability="playback", target=cam,
                                    addr=addr, why=why, worker=self.name)
        return 403, why

    def playback_handler(self):
        gw = self

        class H(SendMixin, Deadlined, BaseHTTPRequestHandler):
            timeout = gw.PLAYBACK_TIMEOUT

            def log_message(self, *a): pass

            # The kernel's share of a connection, capped (`PLAYBACK_SNDBUF`; the review's eighth pass): left to itself
            # the send buffer grows to megabytes under a reader that is slow — and each connection cut for its pace
            # left that much footage in the kernel for as long as the socket lingered, outside the door's budget.
            def setup(self):
                super().setup()
                try:
                    self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, gw.PLAYBACK_SNDBUF)
                except OSError:
                    pass

            def do_GET(self):
                u = urlsplit(self.path); q = {k: v[0] for k, v in parse_qs(u.query).items()}
                if u.path == "/devices":
                    return self._send(200, gw.device_status())
                if u.path.startswith("/recordings/"):
                    try:
                        spans = gw.recordings(u.path.rsplit("/", 1)[1], float(q.get("from", 0)), float(q.get("to", 1e12)))
                    except KeyError:                             # no such camera here, or no archive of its own: said
                        return self._send(404, {"detail": "this camera has no archive of its own here",
                                                "error": "no device archive"})
                    except ValueError:
                        return self._send(400, {"detail": "from and to are unix seconds", "error": "bad range"})
                    if spans is None:
                        return self._send(501, {"detail": "this driver cannot list what the device holds",
                                                "error": "no index"})
                    return self._send(200, {"spans": [{"from": a, "to": b} for a, b in spans]})
                segs = u.path.split("/")                         # "", "playback", <cam>[, <capability>]
                if len(segs) not in (3, 4) or segs[1] != "playback" or not segs[2]:
                    return self._send(404, {"detail": "no such route", "error": "no such path"})
                cam = segs[2]
                seen: dict = {}
                refused = gw.playback_refusal(cam, segs[3] if len(segs) == 4 else "", q, str(self.client_address[0]), seen)
                if refused is not None:
                    return self._send(refused[0], {"detail": refused[1], "error": "denied"})
                # One signed address — or one camera's capability — holds `PLAYBACK_PER_SIGNATURE` connections at once
                # (`playback_pieces`): eight on one address were eight pieces of one viewer's interval. And one VIEWER —
                # the name the console signed, never a `v` nobody checked — holds `PLAYBACK_PER_PERSON` across every
                # address he was signed (the review's eighth pass, major).
                held = q.get("sig") or (segs[3] if len(segs) == 4 else "")
                who = seen.get("who")
                if held and not gw.playback_signature(held, +1):
                    return self._send(503, {"detail": f"this address is being read {gw.PLAYBACK_PER_SIGNATURE} times "
                                                      f"at once already — one viewer, one interval", "error": "busy"})
                if who is not None and not gw.playback_person(who, +1):
                    if held:
                        gw.playback_signature(held, -1)
                    return self._send(503, {"detail": f"{who} is reading {gw.PLAYBACK_PER_PERSON} pieces of footage at "
                                                      f"once already — close one first", "error": "busy"})
                try:
                    return self._play(cam, q)
                finally:
                    if held:
                        gw.playback_signature(held, -1)
                    if who is not None:
                        gw.playback_person(who, -1)

            def _play(self, cam, q):
                try:
                    pieces = gw.playback_pieces(cam, float(q.get("from", 0)), float(q.get("to", 1e12)))
                    first = next(pieces, None)                   # the first piece read before the reply is chosen
                except KeyError:
                    return self._send(404, {"detail": "this camera has no archive of its own here",
                                            "error": "no device archive"})
                except ValueError:
                    return self._send(400, {"detail": "from and to are unix seconds", "error": "bad range"})
                except OverflowError as e:                       # the device's ceiling, not ours
                    return self._send(503, {"detail": str(e), "error": str(e)})
                # A stream, and its end said (`playback_pieces`): to a client that speaks HTTP/1.1, chunks and the last
                # one only when every piece went — a device that failed half way is a reply that ends short, which
                # the client SEES; to an HTTP/1.0 one, the bytes until the connection closes, as before. Written a
                # piece of the wire's size at a time, to a client that keeps the pace (`Paced`).
                # A piece is let go before the next is read — by this loop as by `playback_pieces` — so a connection
                # holds one, as the door's budget counts it.
                out = Paced(self, start_stream(self, 200, "video/mp4"), gw.PLAYBACK_MIN_RATE, gw.PLAYBACK_GRACE)
                piece, first = first, None
                try:
                    while piece is not None:
                        if piece:
                            out.write(piece)
                        piece = None
                        piece = next(pieces, None)
                    out.end()
                except (OSError, OverflowError, KeyError) as e:  # the client went or fell behind, or the device failed after the first byte
                    log.warning("%s: playback of camera %s ended short: %s", gw.name, cam, e)
                finally:
                    pieces.close()

        return H

    # …and the door is opened here, which is the only place that knows what the OS actually gave. With
    # `port=0` the number is invented by the kernel, so it is read back and kept: from this moment
    # `playback_url` says the truth, and a second worker on the same box is an ordinary thing rather than
    # a crash loop every two seconds.
    def serve_playback(self, host: str | None = None, port: int | None = None) -> ThreadingHTTPServer:
        from .config import opened_beyond_loopback
        from .playback import new_key
        self.playback_key = getattr(self, "playback_key", None) or new_key()   # the door's own, announced in the heartbeat
        host = (self.playback_host or LOOPBACK) if host is None else host
        self.playback_host = host                        # what it is bound to is what the heartbeat announces
        opened_beyond_loopback(f"{self.name}: the door to the devices' own archives", host, log,
                               asks="for an address the console signed, in a cluster in a domain (`vms/playback.py`); outside one, nobody")
        srv = door_server((host, self.playback_port if port is None else port), self.playback_handler(),
                          self.PLAYBACK_CONNECTIONS, self.PLAYBACK_PER_ADDRESS)
        self.playback_port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        log.info("%s: playback door on %s:%d", self.name, host, self.playback_port)
        return srv

    # The loop as a process. Every `poll` seconds: `reconcile_once`, `pump_once`, `lease_pass` every `max(1,
    # (lease_ttl − lease_margin)/3)` s (≈8.3 s by default, well inside the 25 s the lease allows),
    # `heartbeat_once` every 10 s; any exception is logged and the loop continues. Each of those is a `guarded`
    # step, and the stand-in (`Worker.start_stand_in`) renews the slot and leases for one that hangs. On `stop`:
    # `actuator.stop_all()` (with GStreamer, EOS lets the last access units reach each sink —
    # `vmsworker@.container` gives it `StopTimeout=20`), a last heartbeat, then `release_slot()` — "an
    # orderly stop says so; a crash says nothing", which is what lets the controller tell scale-in
    # (redistribute) from a crash (leave it to the scheduler).
    #
    # `beat` is `COMMANDS_BEAT`, in seconds: between two passes the loop looks at its request rows that often
    # (`between`). 0 — only on the pass, which is what a caller that does not say gets, and what the loop always did;
    # the process says a quarter of a second (`commands_beat`).
    def run(self, poll: float = 2.0, stop=None, beat: float = 0.0) -> None:
        """One box: the loop as a process. Nomad or systemd restarts it."""
        import threading
        stop = stop or threading.Event()
        lease_every = max(1.0, (self.lease_ttl - self.lease_margin) / 3)
        # Said out loud rather than left to the clock: the first heartbeat goes NOW. `time.monotonic()`
        # counts from boot, so `clock() - 0 >= 10` happens to be true here on the first pass — and Go's
        # monotonic counts from process start, where it is false, which left a Go worker invisible to the
        # controller for ten seconds. The two loops now do the same thing for a reason instead of by luck.
        # Every step below is `guarded`, and the stand-in renews for one that hangs (feedback DD): a pass, a pump, a
        # recorder's call into obsd. It ends with the loop.
        stand_in = self.start_stand_in()
        with self.guarded("heartbeat"):
            self.heartbeat_once()
        last_lease, last_hb = 0.0, self.clock()
        while not stop.is_set():
            # The WORK, and whatever it raises stays in here. Two tries, not one: what is LOCAL — draining the
            # pipelines' buses, the devices' events — does not wait for the pass over the store to succeed
            # (feedback BC). They shared a `try`, so a store that was away skipped the pump on every pass: a
            # device's alarms piled up in memory, a pipeline that fell over was not noticed.
            try:
                with self.guarded("pass"):
                    if not self.recording_allowed:
                        self.rejoin()                      # a fence is not for ever: a free slot, from nothing
                    self.reconcile_once()
            except Exception:                              # noqa: BLE001
                self.pass_failures += 1                    # …and counted: a loop that raises every pass is alive and says so
                log.exception("%s: pass failed; will retry", self.name)
            try:
                with self.guarded("pump"):
                    self.pump_once()
            except Exception:                              # noqa: BLE001
                self.pass_failures += 1
                log.exception("%s: pump failed; will retry", self.name)
            # STAYING ALIVE, in a try of its own and never inside the one above. These two used to share
            # it, so anything the work raised skipped them — every pass, for as long as it kept raising.
            # A recorder whose archive went away stopped renewing its leases (fenced at 30 s) and stopped
            # heartbeating (called dead at 45 s), and an outage it could have waited out ended the recording
            # instead. A pass that failed is a pass to retry; the process that ran it still holds
            # its units, and saying so is not something a failure elsewhere gets to switch off.
            #
            # …and the two in a try EACH (the review's seventh pass, part 2, blocker 1). The comment above promised it
            # and the code had one `try` for both: one volume row with a word for its size raised out of the
            # recorder's lease step, and the heartbeat after it never went — every recorder of the cluster dead to the
            # controller at 45 s, the holds of network volumes unconfirmed, the engine's fence refusing every frame. A
            # lease step that raised is retried on the next turn (`last_lease` stays); the heartbeat goes regardless.
            try:
                if self.clock() - last_lease >= lease_every:
                    with self.guarded("lease"):
                        self.lease_pass()
                    last_lease = self.clock()
            except Exception:                              # noqa: BLE001
                self.pass_failures += 1
                log.exception("%s: the lease step failed; will retry, and the heartbeat goes all the same", self.name)
            try:
                if self.clock() - last_hb >= 10.0:
                    with self.guarded("heartbeat"):
                        self.heartbeat_once()
                    last_hb = self.clock()
            except Exception:                              # noqa: BLE001
                log.exception("%s: heartbeat failed; will retry", self.name)
            self.between(poll, stop, beat)                 # `stop.wait(poll)`, with a look at the requests every `beat`
        stand_in.set()
        self.before_stop_all()
        self.actuator.stop_all()
        self.heartbeat_once()
        self.release_slot()                           # an orderly stop says so; a crash says nothing
        self.after_stop()

    # BETWEEN TWO PASSES: THE REQUESTS, EVERY BEAT (2 October 2026). The wait between passes is `poll` seconds, and a
    # command filed a moment after a pass waited all of it: the second half of the road from an event to a device,
    # a second on average. The loop now wakes every `beat` seconds inside that wait and does what `pump_once` does —
    # `beat_once`: the bus drained (a device's event is a line within a beat, not at the next pass) and the look at the
    # request rows. Not a pass: the assignment is not read again, nothing is reconciled. And not a new way in: the
    # same `drain_bus`, the same `requests`, the same rows, the same rules.
    #
    # The lease step and the heartbeat stay where they were — once per turn of the loop, by the clock: a beat brings
    # neither forward. A beat that hangs on the store is a `guarded` step like any other, and the stand-in renews
    # for it.
    #
    # By the real clock, not `self.clock`: `stop.wait` waits real seconds, and the beats divide THAT wait.
    def between(self, poll: float, stop, beat: float) -> None:
        if beat <= 0 or beat >= poll:
            stop.wait(poll)
            return
        end = time.monotonic() + poll
        while not stop.wait(max(0.0, min(beat, end - time.monotonic()))):
            if end - time.monotonic() <= 0.001:
                return                                # the pass is due, and it looks at the requests itself
            self.beat_once()

    # One look at the requests between passes. A store that does not answer is waited out as on a pass — and said
    # ONCE per outage, counted once: four warnings a second for as long as the store is away would be the log, and
    # the pass says it every two seconds anyway (`pump_once`).
    def beat_once(self) -> None:
        try:
            with self.guarded("beat"):
                self.drain_bus()
                self.serve_requests()
        except Exception as e:                        # noqa: BLE001 — a beat that raised is a beat to make again
            if not self._beat_failed:
                self._beat_failed = True
                if isinstance(e, OSError):
                    self.store_errors += 1
                    log.warning("%s: the store did not answer for the requests between passes (%s); "
                                "looking again every beat, saying so once", self.name, e)
                else:
                    self.pass_failures += 1
                    log.exception("%s: the look at the requests between passes failed; will retry", self.name)
            return
        if self._beat_failed:
            self._beat_failed = False
            log.warning("%s: the requests are read between passes again", self.name)

    # What a subsystem's worker does before its pipelines are stopped on an ORDERLY stop: nothing here. A recorder
    # writes the rings it holds through a break first (`RecWorker.before_stop_all`).
    def before_stop_all(self) -> None:
        pass

    # What a subsystem's worker lets go of on an ORDERLY stop, after the slot: nothing here. A recorder: its
    # place (`RecWorker.after_stop`).
    def after_stop(self) -> None:
        pass
