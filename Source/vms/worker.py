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
(`recworker.py`), a subscriber like any other. It never writes
configuration. systemd (launchd on a Mac, a scheduler where there is one) supervises the process; the
process supervises its pipelines; nothing supervises the loop, because the
loop is the process.

What the environment hands a process, on a box or in an allocation:

    WORKER_NAME / SLOT_INDEX     -> the slot to claim: w-<index>. The index is the preference;
                                    the claim (CAS on vms/slots/w-N) is the proof
    SERVER_NAME (or the hostname) -> `server` in the heartbeat: whose resource its events go to, and the host in `live_url`
    LABELS                        -> `labels` in the heartbeat: what this server can reach; the controller places by them
    INSTANCE_ID                   -> the instance; CAPACITY -> the worker's own number, from М9 Lesson 7's probe

Not one of those names an orchestrator, and that is deliberate: a Quadlet, a
systemd unit or a container's environment each map their own names into these
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
# `w2cplatform.worker.Worker` (the base worker has `claim_slot`, `claim_at_start`, `renew_slot`, `release_slot`,
# `take_epoch`, `renew_leases`, `lease_pass`, `heartbeat`) and is the thing that knows what a camera is. It reads its
# assignment `vms/workers/<me>` and the camera rows it names, runs the platform's reconcile helper over them
# (`w2cplatform/reconcile.py`, ADR 0033 — М9's loop) with an actuator that builds `driverpacksrc ! tee ! …` (`gstvms/actuator.py`;
# `FakeActuator` here without GStreamer), takes an epoch per camera by CAS when it starts one, holds a lease
# per camera, writes events into the camera's bucket on this server's resource, and publishes a heartbeat
# carrying its status. It never writes configuration: its token is `vms/epoch/*`, `vms/slots/*` and
# `vms/devices/*` — the last one what it found a device to be, a discovery and not a decision. systemd (Quadlet
# on a box) supervises the process; the process supervises its pipelines; nothing supervises the loop, because
# the loop is the process. What the environment hands a process is the runtime's neutral names
# (`w2cplatform/runtime.py`): `WORKER_NAME` / `SLOT_INDEX` (the slot preference; the CAS claim on `vms/slots/w-N`
# is the proof), `SPARE_FOR` (a spare: only an offer of its set), `SERVER_NAME` or the hostname (`server`: which
# resource it records into), `LABELS` (what this server can reach; the controller places by them), `INSTANCE_ID`
# (the instance), `CAPACITY` (the worker's own number, from М9 Lesson 7's probe). Run by `__main__.worker`;
# tested in `tests/test_lesson4_worker.py` and used across Lesson 6's tests.
#
# ## Module-level names
# - `log` — logger `vmsworker`.
# - `VMS` — `Subsystem("vms")`, the key layout.
#
# ### `__init__(self, name, vars_, objects, actuator=None, lease_ttl=30.0, lease_margin=5.0,
# clock=time.monotonic, wall=time.time, server=None, capacity=None, instance=None, slot_ttl=45.0,
# resource_root=None, bucket_seconds=600, env=None)` `env` defaults to `os.environ` (tests pass a dict).
# `instance` defaults to `INSTANCE_ID`, else the base class's `box:pid:6hex` (`runtime.instance_on_box`). Calls
# `Worker.__init__` with `name=None` (and the resource tree: the argument, `$RESOURCE_ROOT`, else
# `<PLATFORM_DIR>/events` — `runtime.events_root`, the platform's) and then `claim_at_start(name, env)` (no name:
# the runtime's, by the spec's `slot`, `Worker.given_name`) — so construction *is* the claim, and `self.name` is set afterwards. Then: `capacity`
# from the argument or `$CAPACITY` (50) — "М9 Lesson 7's B + n·I, measured on ITS server"; the actuator
# (`FakeActuator()` if none); an empty `rows`; the reconciler over its gate (`new_reconciler`); `writing_allowed = True`;
# `server` from the argument, `SERVER_NAME`, else the hostname; `labels` (`LABELS`), `alloc` (`INSTANCE_ID`). The
# previous instance's heartbeat under this slot name — what the controller's `failover_seconds` measures from — is
# the platform's to read (`Worker.previous_said`), before the first heartbeat.
# `test_a_replacement_without_a_name_inherits_the_lapsed_slot`: two nameless workers get `w-1`, `w-2`; 46 s of wall
# clock after `w-1` went silent a nameless worker makes `w-3` (within the margin what `w-1` started may still write);
# at 91 s a third nameless worker gets `w-1` back and starts its two cameras with epoch 2.
#
# ## Notes
# - Ordering: the slot is claimed in the constructor, before any assignment is read (the name is the row
#   key); an epoch is taken in `_actuate` before the pipeline starts; the base worker's `lease_pass` checks the
#   slot before the leases.
# - Recovery needs no controller: `test_restart_with_the_controller_stopped` deletes the controller, starts
#   a fresh `w-1` with an empty `actual`, and it starts all three cameras from its assignment with epoch 2
#   each — the old instance is fenced by construction.
# - The exits from a lost lease are the base worker's `lease_pass`: the slot held by another instance (fence
#   everything, first), and a lease lost — a newer epoch issued (the camera reassigned, or a zombie's) or unconfirmed
#   past its ceiling — which stops that one camera (`stop_unit`: dropped from the reconciler, no failure) and goes on.
#   A lease that merely expired because the loop stalled shows up as `may_act` false in `_actuate` and a fresh epoch
#   on the next start.
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
from w2cplatform.contract import NotReadThisPass, SchemaTooNew, Subsystem, check_schema
from w2cplatform.worker import Worker
from w2cplatform.objects import ObjectStore
from w2cplatform.rows import PARSE_ERRORS, finite
from w2cplatform.variables import Variables

from w2cplatform.events import ALARM, OBSERVATION

from w2cplatform.sealing import Sealed, Sealer, open_row
from .config import (DEVICES, LIVE_PORT_BASE, LOOPBACK, PLAYBACK_PORT, RTSP_PORT, SHM_DIR, SPEC, announce_host, channel_key, channel_of, describe, device_of,
                     device_identities, device_row, identity_of, live_shm, live_url, COMMAND_ARG_MAX,
                     playback_url, port_of, row)
from w2cplatform.reconcile import CONVERGED, Reconciler, Want


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
# seconds), False if not; `room(most, wait)` what `take` would give now, waited for like it and NOT taken; `force(n)`
# counts bytes it has whatever the limit says (a piece larger than was asked for: it is in memory already); `give(n)`
# frees them. The holder's playback door (`VmsWorker.playback_pieces`), whose readers are the cluster's processes —
# a person's share of a door is the recording's door's, where a page reads (`vms/footage.py`, `bounded`).
class ByteBudget:
    def __init__(self, limit: int):
        self.limit, self.used = int(limit), 0
        self.cond = threading.Condition()

    # The door sizes a piece by it before the device is asked, and takes the bytes once the device has opened its
    # footage (the thirteenth review, major 19: a hung open held a piece's bytes for as long as the door waited).
    def room(self, most: int, wait: float) -> int:
        deadline = time.monotonic() + wait
        with self.cond:
            while True:
                if not self.used or self.used + most <= self.limit:
                    return int(most)
                left = deadline - time.monotonic()
                if left <= 0:
                    return 0
                self.cond.wait(left)

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
    from vms.obsd import archive_ms, video
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
        from vms.obsd import ObsdError
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


# `LABELS` split on commas, empties dropped — what this server can reach, as the runtime said it.
#
# …in the one alphabet of labels (`spec.LABEL_WORD`; the review's tenth pass): a word outside it is said at start — no
# camera can be given it any more, and no server's row can hold it — and kept, so a camera stored with it before still
# has a server.
def labels_from_environment(env: dict) -> list[str]:
    from w2cplatform.spec import LABEL_WORD
    out = runtime.labels(env)
    bad = [l for l in out if not LABEL_WORD.fullmatch(l)]
    if bad:
        log.warning("LABELS holds %s, which is not a label (letters, digits and _ . : -, starting with a letter or a "
                    "digit): no camera can be given it any more and the console cannot write it for a server; write it "
                    "in those characters", ", ".join(repr(l) for l in bad))
    return out


# `name` is a slot. Given (systemd's `%i`, `SLOT_INDEX` — `runtime.slot`) it is claimed by that name — taken outright,
# even from a holder of this box that has not lapsed, because the unit is the authority on which process is
# current; `None` means the environment's, and failing that "whichever slot is free" — a lapsed one first,
# so a replacement inherits its assignment. "A worker on a cluster is a worker on a box whose stores happen
# to be raft: same class, same heartbeat." It is also the `Store` of its own `Reconciler` (`desired()`).
#
# State beyond the base class: `bucket_seconds`, `observed` (every `(cid, t, kind)` this instance wrote),
# `capacity`, `actuator`, `rows` (the assignment's camera rows, refreshed each pass), `assignment_rev`,
# `reconciler`, `server`, `labels`, `alloc`, `started_at` (monotonic).
class VmsWorker(Worker):
    """`name` is a slot. Given (systemd's %i, `SLOT_INDEX`) it is
    claimed by that name; None means the environment's, and failing that
    "whichever slot is free" — a lapsed one first, so a replacement
    inherits its assignment. A worker on a cluster is a worker on a box
    whose stores happen to be raft: same class, same heartbeat. The
    recorder (`recworker.py`) is this class over another subsystem's rows."""

    SUB = VMS                       # the subsystem whose assignment and rows this worker runs
    REQUEST_TARGET = "the device"   # what a request's refusal calls what was called
    ROWS = "cameras"                # <sub>/<ROWS>/<id>
    parse_row = staticmethod(row)

    def __init__(self, name: str | None, vars_: Variables, objects: ObjectStore, actuator=None,
                 lease_ttl: float = 30.0, lease_margin: float = 5.0, clock=time.monotonic, wall=time.time,
                 server: str | None = None, capacity: int | None = None, instance: str | None = None, slot_ttl: float = 45.0,
                 resource_root: str | None = None, bucket_seconds: int = 600, env: dict | None = None,
                 device_factory=None):
        env = dict(os.environ if env is None else env)
        instance = instance or runtime.instance_on_box(env)   # the box in it: whose a name is (`Worker._may_take_by_name`)
        super().__init__(self.SUB, None, vars_, objects, lease_ttl, lease_margin, clock, wall, instance, slot_ttl,
                         resource_root, env)
        self.sealer = Sealer.from_env(env)                    # opens a device's password for the pipeline, and nothing else does
        self.sealed_errors: dict[str, str] = {}               # camera -> why its password could not be opened
        self.row_errors: dict[str, str] = {}                  # camera -> why its own row is not followed (it does not parse)
        self.server = runtime.server(env, server)             # before the claim: a process on a decommissioned server gets no slot
        # …or, started as a spare (`SPARE_FOR`), an offer of its set — none: nobody, waiting (`Worker.claim_at_start`)
        self.claim_at_start(name, env)                        # no name: the runtime's, by the spec's `slot`
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
        self.observed: list[tuple[int, float, str]] = []
        self._slow_asks: set[int] = set()                # devices whose question did not answer inside `DEVICE_GRACE` (`_ask_devices`)
        self._dev_calls: dict[tuple, dict] = {}          # (question, device) -> its one call not collected yet (`_ask_devices`)
        self._dev_lock = threading.Lock()                # …asked from the loop's thread and from the playback door's
        self._dev_pending: dict[int, int] = {}           # device -> its calls through `_ask_devices` not returned yet
        self._dev_queues: dict = {}                      # device (or ("open", key)) -> its questions not begun yet, in order
        self._dev_runners: set = set()                   # …and the lines a thread is working through now: one per device
        self._dev_heads: dict = {}                       # …and the call each of those lines is in now (`_ask_devices` judges it)
        self._door_reads: dict[int, list] = {}           # device -> the door's reads of its sessions not back yet (`_door_read`)
        self._dev_said: set = set()                      # devices said slow, (question, device) said failing: once a spell
        self._open_failed: dict[str, str] = {}           # device key -> why it did not open, until it opens
        self._said_coverage: dict[tuple, object] = {}    # ("coverage", device, camera) -> what the device said last
        self._said_coverage_at: dict[tuple, float] = {}  # …and when it said it (`wall`)
        self._said_status: dict[tuple, object] = {}      # ("channels" | "in_use", device) -> what the device said last
        self._heard: dict | None = None                  # the heartbeat's one round of answers, while it is being written
        self.capacity = capacity if capacity is not None else int(env.get("CAPACITY", "50"))   # М9 Lesson 7's B + n·I, measured on ITS server
        self.actuator = actuator or FakeActuator()
        self.rows: list[dict] = []
        # One session per DEVICE, not per channel. `device_factory(key)` opens it — a DriverPack session on
        # a box, a `FakeDevice` in the tests, `None` for a source with no archive of its own (a file).
        self.device_factory = device_factory or (lambda key: None)
        self.devices: dict[str, object] = {}
        self.described: dict[str, dict] = {}              # device -> the description this worker last wrote
        self.identities: dict[str, str] = {}              # device -> what it said it is (`identity`), as last written
        self.coincidences: dict[str, tuple] = {}          # device -> (another key whose row says its identity, the identity): said
        self.identity_changes = 0                         # a key whose device said another identity than before (`describe_devices`)
        self.events_refused = 0                           # lines a device posted that could not be written (`drain_bus`)
        self.assignment_rev = 0
        self._pass_now: float | None = None               # a test's own `now` for one pass (`reconcile_once(now)`)
        self.reconciler = self.new_reconciler()
        self.labels = labels_from_environment(env)
        self.alloc = runtime.instance(env) or ""          # published as `alloc` for the readers that already know that name
        self.started_at = clock()

    # -- what the reconciler runs -----------------------------------------------------
    # The platform's helper (`w2cplatform/reconcile.py`, ADR 0033) over this worker's gate, all three verbs: a restart is
    # ONE call (an edit keeps the held epoch and lease — no new writer, no break in `<id>/e<epoch>`, nothing asked of a
    # silent store), never a stop and a start; its delays run on this worker's clock (`now`).
    def new_reconciler(self) -> Reconciler:
        r = Reconciler(lambda uid, want: self._actuate("start", want.body), lambda uid: self._actuate("stop", {"id": uid}),
                       restart=lambda uid, want: self._actuate("restart", want.body))
        r.now = lambda: self.now() if self._pass_now is None else self._pass_now
        return r

    # The rows the reconciler runs: `self.rows`, less what `desired` holds back.
    def desired(self) -> list[dict]:
        """What the reconciler runs. A row with `live: on-demand` is NOT here: its device is
        still held (see `_refresh_devices`) and its archive still served, but no pipeline is
        built for it. Holding the device is what the row buys; the live fan-out is what `live`
        asks for."""
        back = self.held_back()
        return [r for r in self.rows if r.get("live", "always") != "on-demand" and str(r["id"]) not in back]

    # ONE CHANNEL, ONE CAMERA — THE TWIN ONLY THIS WORKER CAN SEE (the owner's decision on the boundary's step 6). The
    # platform refuses a second camera at the same address in its one spelling (`source: {unique: canonical}`), and
    # cannot know that `…/ch/02` and `…/ch/2`, or `…/10.0.0.50:80/…` and `…/10.0.0.50/…`, are one channel: that is how
    # the VMS reads its addresses (`config.device_of`, `channel_key`). Both are one group (`group_by: {cut_at: host}`:
    # the host in one spelling, `ACME`, `:80` and the root's dot aside), so both are here: the first by id is opened, every
    # other is «device busy» in this worker's heartbeat (`status`: `why`, `device_state: busy`) and not opened — two
    # pipelines on one channel are camera 2's picture in camera 1's archive (the review's sixth pass). A host the platform
    # cannot read (`012.0.0.50`) is refused at the door (ADR 0053); a row stored before is in no group, and may be on
    # another worker. `{camera id: the camera whose channel it is already}`.
    #
    # …AND A SOURCE THE VMS CANNOT READ IS NOT OPENED (the review's tenth pass, major, where it was a refusal at the door in
    # the VMS's words, `config.source_refusal`, until the boundary's step 6): a channel written in digits that are not
    # 0–9, a `driverpack://` address with a `?` that could name another host than the one rights were asked of. The
    # platform takes the row (an address by RFC 3986, its port a port); this worker does not dial it, and says why.
    # `{camera id: (state, why)}` — `busy` or `refused`.
    def held_back(self) -> dict[str, tuple[str, str]]:
        from w2cplatform.doors import numeric
        from .config import source_refusal
        seen, out = {}, {}
        for r in sorted(self.rows, key=lambda r: (numeric(str(r["id"])) is None, numeric(str(r["id"])) or 0, str(r["id"]))):
            if not r.get("source"):
                continue
            why = source_refusal(str(r["source"]))
            if why:
                out[str(r["id"])] = ("refused", f"not opened: {why}")
                continue
            key = (device_of(str(r["source"])), channel_key(str(r["source"])))
            if key in seen:
                out[str(r["id"])] = ("busy", f"device busy: camera {seen[key]} is this channel of the device already, "
                                             f"written another way — one channel is one camera: point one of the two "
                                             f"elsewhere, or delete it")
            else:
                seen[key] = str(r["id"])
        return out

    # Read the assignment (`assignment_rev` kept for the heartbeat) and, for each unit it names, the row
    # `vms/cameras/<id>`; rows that are missing or marked `deleted: "true"` are skipped. "A fresh worker
    # knows nothing and reads everything; nothing about what is running is stored." An unassigned worker has
    # no rows and invents nothing (`test_worker_runs_its_assignment…`: the first `reconcile_once` is `[]`).
    def refresh(self) -> None:
        """Read the assignment and the rows it names. A fresh worker knows
        nothing and reads everything; nothing about what is running is stored."""
        a = self.assignment()                         # …which forgets what the lease step let go before it (`lost_to_epoch`)
        self.assignment_rev = a.rev
        rows, errors = [], {}
        for unit in a.units:
            try:
                # The read inside the guard too (the review's twelfth pass, major 18): a torn file is `Garbled` from the
                # store itself, before any parse — read bare, it raised out of here at its unit: a deleted camera 4 went
                # on being recorded and a new camera 5 never started, every pass, for one torn row of another camera.
                items, _ = self.vars.get(self.SUB.config(self.ROWS, unit))
                if not items or items.get("deleted") == "true":
                    continue
                rows.append(self.parse_row(items))
                self.row_parsed(unit)
            except PARSE_ERRORS as e:                    # `Infinity` in an int field too (the tenth round's sweep)
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
        opens = []
        for key in want - set(self.devices):
            opens.append((("open", key), None, lambda key=key: self.device_factory(key)))
        for (_, key), dev in self._ask_devices(opens, until).items():
            if dev is not None:
                self.devices[key] = dev
        closes = []
        for key in set(self.devices) - want:
            dev = self.devices.pop(key)
            self.described.pop(key, None); self.identities.pop(key, None); self.coincidences.pop(key, None)
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
        self._said_coverage_at = {k: v for k, v in self._said_coverage_at.items() if k in self._said_coverage}
        self._said_status = {k: v for k, v in self._said_status.items() if k[1] in held}
        self._slow_asks &= held
        self._open_failed = {k: v for k, v in self._open_failed.items() if k in want and k not in self.devices}
        for key, (other, ident) in list(self.coincidences.items()):
            if not self._still_known_as(other, ident):   # the other row went, or says another device now: said no more
                self.coincidences.pop(key, None)
        self.describe_devices(until)

    # NO CALL INTO A DEVICE WAITS ON THE LOOP'S THREAD (the scaling pass after the eighth review). `perform` was made on a
    # thread of its own in feedback BE; every other call into a device was made bare, on the thread that renews the
    # leases and writes the heartbeat: `capabilities` once a pass for every device, `channels`, `in_use` and every
    # camera's `coverage` once a heartbeat, the session's open and close. A driver that does not answer held the loop
    # for as long as it cared to — for ever, with the fake — and 100 devices of 200 that answer in a tenth of a second
    # were a pass of 10.5 s and a heartbeat of 31 s, measured; at the product's five seconds a call, a heartbeat of
    # 1500 s. Every such call now goes through here, with the commands' rules:
    #
    #   off the loop        the loop waits for the calls of one round TOGETHER, `DEVICE_GRACE` at most — one fifth of a
    #                       second however many hang — and never past `until`, the pass's or the heartbeat's
    #                       `DEVICE_HOLD`
    #   one at a time       a question to a device whose last call has not returned is not asked again: no second
    #                       thread piles onto a hung driver. Its answer, whenever it comes, is the next round's
    #   a slow device       one whose call outlasted a whole `DEVICE_GRACE` is in `_slow_asks`: asked, not waited for,
    #                       until a call into it answers at once
    #   an error            the device's word, not the pass's end: not known this round, said once a spell
    #
    # ONE LINE PER DEVICE, NOT ONE THREAD PER QUESTION (the review's tenth pass, major; a run). "One at a time" was per
    # question: a recorder of 32 channels got `channels`, `in_use` and 32 `coverage` calls at once every heartbeat — 34
    # requests at once into a box that answers one at a time, and at 10 ms an answer it was `slow` in five heartbeats
    # of six, 20 of its cameras without coverage. Now the questions of a round to one device are asked in order on the
    # device's one line (`_dev_run`), and `took` is counted from when a question was BEGUN: one queued behind the
    # device's others is not slow, and its answer is collected by the next round. A question that is slow no longer
    # names the device slow for the commands: `_slow_asks` here, `_slow` there (a relay is waited for in its look again,
    # whatever the device's index takes to list).
    #
    # WHAT IS IN A DEVICE AT ONCE, said as it is (the eleventh review, a minor; a run: "two at most" was untrue — the
    # heartbeat and four door requests were five calls at once). Questions — the heartbeat's, the description's, and the
    # playback door's `coverage` and listing (`recordings`, `playback_pieces`; the product's cross-check found its card
    # poll beside the line too) — go on this one line, one at a time. Beside it: one command (`requests`, one at a time
    # of its own), and the door's READS of the archive (`open_playback`, `read`, `close_playback`) — those are the
    # device's own sessions, as many as its `max_playbacks` lets in (it refuses the next: 503), and a read takes as long
    # as a piece of footage takes, which a question queued behind it must not be judged by.
    #
    # `asks` is `[(key, device, call)]`, the key `(question, id(device), …)` (an open: `("open", device key)`). Returns
    # `{key: answer}` for the calls that answered; a key that is absent is NOT KNOWN — and every caller reads it so:
    # a description not changed, a device said `slow` in the heartbeat, the coverage it said last. `grace`: a door's
    # longer wait (`DOOR_ASK_WAIT`, off the loop) — and a door waits for the same question already on the line rather
    # than taking "not known" at once.
    DEVICE_GRACE = 0.2                                   # the one wait for a round of calls into devices: `PERFORM_GRACE`'s
    DEVICE_HOLD = 0.5                                    # seconds the device calls of one pass, or one heartbeat, may hold it
    DOOR_ASK_WAIT = 5.0                                  # seconds the playback door waits for a question on the device's line

    def _ask_devices(self, asks, until: float | None = None, grace: float | None = None) -> dict:
        start = time.monotonic()
        door = grace is not None
        grace = self.DEVICE_GRACE if grace is None else grace
        until = start + max(self.DEVICE_HOLD, grace) if until is None else until
        out, waiting, lines = {}, [], set()
        for key, dev, fn in asks:
            line = ("open", key[1]) if dev is None else id(dev)
            lines.add(line)
            with self._dev_lock:
                call = self._dev_calls.get(key)
                if call is not None and call["returned"].is_set():
                    del self._dev_calls[key]             # an answer that came after it was given up on: this round's
                    self._collect(key, call, out)
                    continue
                if call is not None:
                    if door:
                        waiting.append((key, call))      # a door waits for the one already asked
                    continue                             # still not back, or not begun: not asked twice
                call = self._dev_calls[key] = {"key": key, "dev": dev, "fn": fn, "returned": threading.Event(),
                                               "since": self.wall()}
                if dev is not None:
                    self._dev_pending[id(dev)] = self._dev_pending.get(id(dev), 0) + 1
                self._dev_queues.setdefault(line, []).append(call)
                begin = line not in self._dev_runners
                self._dev_runners.add(line)
            if begin:
                threading.Thread(target=self._dev_run, args=(line,), name=f"{self.name}-device", daemon=True).start()
            if door or dev is None or id(dev) not in self._slow_asks:
                waiting.append((key, call))
        deadline = min(time.monotonic() + grace, until)
        for key, call in waiting:
            call["returned"].wait(max(0.0, deadline - time.monotonic()))
        # THE HEAD OF EVERY LINE THIS ROUND ASKS IS JUDGED IN THIS ROUND (the eleventh review, a major; a run). A question
        # was judged only in the round that asked it: `in_use` begun just after that round's wait — behind `channels` —
        # and never back was not asked again (rightly) and never looked at again, so the device stayed "healthy",
        # `devices_slow` empty, the log silent, and its 32 `coverage` questions queued behind it for ever: coverage at 0
        # of 32. Now every round looks at what each line it asks is answering now (`_dev_heads`), whoever asked it: out
        # longer than `DEVICE_GRACE`, the device is `slow` (said once; `since` in `device_status`), and each of its cameras
        # keeps the coverage it said last (`_coverage_of`). Not waited for again: it was waited for once.
        with self._dev_lock:
            asked = {id(c) for _, c in waiting}
            heads = [(h["key"], h) for h in (self._dev_heads.get(line) for line in lines) if h is not None and id(h) not in asked]
        for key, call in waiting + heads:
            with self._dev_lock:
                if call["returned"].is_set():
                    if self._dev_calls.get(key) is call:
                        del self._dev_calls[key]
                        self._collect(key, call, out)
                    continue
                begun = call.get("t0")
            if begun is None or time.monotonic() - begun < self.DEVICE_GRACE:
                continue                                 # behind the device's other questions, or begun just now: next round's
            dev = call["dev"]
            if dev is None:                              # an open that has not come back: `opening` in the heartbeat
                if ("opening", key[1]) not in self._dev_said:
                    self._dev_said.add(("opening", key[1]))
                    log.warning("%s: device %s has not opened within %.1f s: its cameras are not commanded and its archive "
                                "is not served until it does; the heartbeat says it is opening", self.name, key[1],
                                self.DEVICE_GRACE)
                continue
            self._slow_asks.add(id(dev))
            if id(dev) not in self._dev_said:
                self._dev_said.add(id(dev))
                log.warning("%s: device %s did not answer `%s` within %.1f s: not waited for until it answers at "
                            "once, and the heartbeat says it is slow", self.name, self._device_name(dev), key[0],
                            self.DEVICE_GRACE)
        return out

    # A device's line: its questions, one after another, on one thread — which ends when the line is empty and is
    # started again by the next question (`_ask_devices`).
    def _dev_run(self, line) -> None:
        while True:
            with self._dev_lock:
                queue = self._dev_queues.get(line)
                if not queue:
                    self._dev_queues.pop(line, None)
                    self._dev_runners.discard(line)
                    return
                call = queue.pop(0)
                call["t0"], call["begun"] = time.monotonic(), self.wall()
                self._dev_heads[line] = call             # what the line is answering now: judged by every round (`_ask_devices`)
            try:
                call["out"] = call["fn"]()
            except Exception as e:                       # noqa: BLE001 — the device's word, whatever it is
                call["error"] = str(e) or type(e).__name__
            call["took"] = time.monotonic() - call["t0"]
            with self._dev_lock:
                if self._dev_heads.get(line) is call:
                    del self._dev_heads[line]
                if call["dev"] is not None:
                    n = self._dev_pending.get(id(call["dev"]), 1) - 1
                    if n > 0:
                        self._dev_pending[id(call["dev"])] = n
                    else:
                        self._dev_pending.pop(id(call["dev"]), None)
                call["returned"].set()

    # One call that came back: its answer into `out`, or its error said (once a spell). A quick answer clears the device's
    # name from `_slow_asks` — unless another question to it has not returned. The commands' `_slow` is theirs
    # (`_performed`): a quick description does not say a relay answers, and a slow index does not say it does not.
    def _collect(self, key: tuple, call: dict, out: dict) -> None:
        dev = call["dev"]
        if dev is not None and call.get("took", 0.0) <= self.DEVICE_GRACE and not self._dev_pending.get(id(dev)):
            self._slow_asks.discard(id(dev))
            self._dev_said.discard(id(dev))
        if dev is None:
            self._dev_said.discard(("opening", key[1]))
        said = (key[0], key[1])
        if "error" in call:
            if key[0] == "open":
                self._open_failed[key[1]] = call["error"]
            if said not in self._dev_said:
                self._dev_said.add(said)
                log.warning("%s: device %s refused `%s` (%s): not known until it answers", self.name,
                            self._device_name(dev) if dev is not None else key[1], key[0], call["error"])
            return
        if key[0] == "open":
            self._open_failed.pop(key[1], None)
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
    # resolves to are two keys here and one recorder, and only the process that opened it can ask the hardware. Every
    # holder reads them back to tell two spellings of one device apart (`config.device_identities`, below).
    #
    # A NAME WHOSE IDENTITY ANOTHER KEY HAS IS SAID, NOT REFUSED (the owner's decisions on the review's ninth pass). The
    # eighth pass made the holder refuse such a name as a second name of a device known already. Two runs of the ninth
    # showed what that cost. An identity is the driver's word, and a serial number is not unique: firmware clones say the
    # same one, and the second clone was refused for good, its status pointing at the other clone's address. And a word
    # is not always said: a recorder that answered two passes without its serial had its row rewritten without one, the
    # other name took the identity meanwhile, and after a restart the holder refused the recorder by its own name — 0 of
    # its 2 cameras recorded. Now:
    #
    #   an empty word unsays nothing   what the device said before — in memory, or in its row when this holder has just
    #                                  started — stands until the device says something else
    #   a coincidence is said          an identity learned now and found under another key (`device_identities`, any
    #                                  vendor) is written all the same, said in the log once, counted (`coincidences`:
    #                                  `identity_coincidences` in the heartbeat, `vms_device_identity_coincidences` on
    #                                  `/metrics`) and named in the status of every camera of the device (`warning`) —
    #                                  two names of one device or two devices with one serial: an operator can tell
    #                                  which, the holder cannot
    #
    # Who may point a camera at a name is the console's question, and it asks it exactly where no identity is known yet:
    # a device no holder has opened is a grant on the whole cluster (`vms/console.py`, `source_cams`); one opened, every
    # camera of every key with its identity. Each pass asks the store whether the other row still says it
    # (`_still_known_as`, `_refresh_devices`), so removing a stale row ends the warning.
    #
    # Asked through `_ask_devices` (the scaling pass): a device that did not answer this pass has its description as it
    # was — not known is not "no relays".
    def describe_devices(self, until: float | None = None) -> int:
        wrote = 0
        idents = self.identities
        known: dict | None = None                        # the device rows' identities, read once a pass when needed
        heard = self._ask_devices([(("capabilities", id(d)), d, d.capabilities) for d in self.devices.values()
                                   if hasattr(d, "capabilities")], until)
        for key, dev in self.devices.items():
            if hasattr(dev, "capabilities") and ("capabilities", id(dev)) not in heard:
                continue                                 # not known this pass: as it was
            caps = heard.get(("capabilities", id(dev)))
            desc, said = describe(caps), identity_of(caps)
            if desc is None:
                continue
            ident = said or idents.get(key, "")          # an empty word does not unsay a known one
            if self.described.get(key) == desc and idents.get(key, "") == ident:
                continue
            path = self.SUB.config(DEVICES, key)
            items, _ = self.vars.get(path)
            if not ident and isinstance(items, dict):
                ident = str(items.get("identity") or "").strip()   # …nor the one its row keeps, when this holder has just started
            was = idents.get(key, "") or (str(items.get("identity") or "").strip() if isinstance(items, dict) else "")
            if said and was and said != was:
                self._changed(key, was, said)
            if ident and idents.get(key, "") != ident:  # learned now: does another key's row say the same?
                if known is None:
                    known = device_identities(self.vars)
                other = next((k for k, i in sorted(known.items()) if i == ident and k != key), None)
                if other is not None:
                    self._coincide(key, other, ident)
                else:
                    self.coincidences.pop(key, None)
            row = device_row(desc, ident)
            if items != row:
                self.vars.put(path, row)
                wrote += 1
            if known is not None and ident:
                known[key] = ident
            self.described[key], idents[key] = desc, ident
        return wrote

    # ANOTHER DEVICE UNDER THE SAME KEY (the product team's sibling of the review's tenth pass): the recorder at an address
    # was replaced, or a name was pointed elsewhere, and the holder went on as if nothing happened — the row took the new
    # serial number without a word, and the cameras recorded another box's channels. Said in the log, counted
    # (`identity_changes` in the heartbeat, `vms_device_identity_changes_total` on `/metrics`); not refused — the device
    # that answers is the one the address names, and only a person knows whether that is what was meant.
    def _changed(self, key: str, was: str, now: str) -> None:
        self.identity_changes += 1
        log.warning("%s: device %s now gives the serial number %s; it gave %s before. Another device answers at this "
                    "address now — replaced, or the name points elsewhere. Its cameras are recorded from the device that "
                    "answers; if that is not the one meant, point them at the right address", self.name, key, now, was)

    def _coincide(self, key: str, other: str, ident: str) -> None:
        if self.coincidences.get(key) == (other, ident):
            return                                       # said once, while it holds
        self.coincidences[key] = (other, ident)
        log.warning("%s: device %s gives the same serial number (%s) as device %s. Either they are one device under two "
                    "names, or two devices with one serial number (firmware clones). Both are recorded. If it is one "
                    "device, point all its cameras at one of the two names and remove the device row of the other "
                    "(vms/devices/...)", self.name, key, ident, other)

    # Whether the device row of `other` still says `ident` — the warning about a coincidence holds while it does.
    def _still_known_as(self, other: str, ident: str) -> bool:
        try:
            items, _ = self.vars.get(self.SUB.config(DEVICES, other))
        except Exception:                                # noqa: BLE001 — a store that does not answer: the warning stands
            return True
        return str((items or {}).get("identity") or "").strip() == ident if isinstance(items, dict) else False

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
    # is fenced (`writing_allowed` false); on `start`, or if no epoch is held for the unit,
    # `take_epoch(unit)` — a new epoch for a new writer — else reuse the held epoch (an edit's restart keeps
    # epoch 1); refuse if `may_act(unit)` is false (no lease, or a lost one); then call the actuator with
    # `epoch` added to the row — the number in the name of every stream a recorder writes (`<rec>/e<epoch>`) and
    # every event bucket a worker does. For `stop`: call the actuator
    # and `release(unit)` (forget epoch and lease). `test_lease_expiry_without_renewal_stops_starts`: after
    # 26 s without renewal `may_act` is false; a later start takes epoch 2.
    def _actuate(self, verb: str, cam: dict) -> bool:
        unit = str(cam["id"])
        if verb in ("start", "restart"):
            if not self.writing_allowed:
                return False
            if verb == "start" or unit not in self.epochs:
                try:
                    # …not one the lease step let go since the assignment was last read (the review's thirteenth pass,
                    # major 6; `n2_pass_stale_assignment`): `take_epoch` refuses it (`NotReadThisPass`), whoever asks —
                    # this gate and the requests alike.
                    cam = dict(cam, epoch=self.take_epoch(unit))   # a new epoch for a new writer
                except (OSError, NotReadThisPass) as e:
                    # The store did not answer for the epoch — or for the assignment, and the unit may be another's now
                    # (`take_epoch`; the product's cross-check): no new number either way, the same answer below.
                    if isinstance(e, OSError):
                        self.store_errors += 1
                    if unit in self.epochs and self.may_write(unit):
                        # A pipeline that fell over while the store is away comes back under the epoch this
                        # worker ALREADY holds (feedback BK). It is the same writer: nobody else could have been
                        # given a number meanwhile by a store that answers nobody. It used to wait for a new
                        # epoch, and the camera was not recorded for as long as the store was silent.
                        log.warning("%s: camera %s restarted under the epoch it holds (%d): no new one now (%s)",
                                    self.name, unit, self.epochs[unit], e)
                        cam = dict(cam, epoch=self.epochs[unit])
                    else:
                        # Never started by this worker: no epoch, no start — for THIS unit, this pass: a failed
                        # start the reconciler retries with its backoff. Raised out of here, it ended the pass
                        # for every unit after it.
                        log.warning("%s: camera %s not started: no epoch for it (%s)", self.name, unit, e)
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
            if not self.may_write(unit):                       # data: a lease that ran out in silence still records
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
    # One pass: `refresh`, `reconciler.once` over the wanted rows, count the pass, log each action. The base class's
    # abstract method; called by `run` and directly by every test.
    #
    # NOT KNOWING IS NOT "NO" (feedback BC). A store that did not answer says nothing about what this worker
    # should be doing: it goes on with the assignment and the rows it read last — what is running keeps running,
    # what fell over is started again, when the store lets it take an epoch. It used to raise out of the pass,
    # and the pass used to be the only place the local work was done.
    def reconcile_once(self, now: float | None = None) -> list[tuple[str, int]]:
        try:
            self.refresh()                            # the assignment read again: what is still mine is the pass's to take
        except OSError as e:
            self.store_errors += 1
            log.warning("%s: the store did not answer (%s); going on with the last assignment read", self.name, e)
        wants = {r["id"]: Want(r["revision"], r) for r in self.desired() if r["enabled"]}
        self._pass_now = now
        try:
            p = self.reconciler.once(wants)
        finally:
            self._pass_now = None
        # The pass as it was done: the stops, then each restart, start or failure in the order the cameras are wanted.
        done = {**{u: "restart" for u in p.restarted}, **{u: "start" for u in p.started}, **{u: "failed" for u in p.failed}}
        actions = [("stop", u) for u in p.stopped] + [(done[u], u) for u in wants if u in done]
        self.passes += 1
        for verb, cid in actions:
            log.info("%s: %s camera %s", self.name, verb, cid)
        return actions

    # An event: the platform's line (`Worker.observe`: under the epoch this worker holds for the camera, into its bucket on
    # this server's resource, through the spec's `events.suppress`, `occurred` kept out of a repeat's identity), with
    # `(cid, t, kind)` kept in `observed` for the tests and diagnostics — a repeat the suppressor swallows too.
    # `test_the_worker_observes_what_it_holds_recording_or_not`: before the first reconcile `observe(1, ...)` is `None`;
    # after it the line lands in `<resource root>/vms/1/e1/…`; camera 2 (not assigned) is `None`; after `fence` a post is
    # dropped; `vms/events` in the store stays empty.
    def observe(self, cid: int, kind: str, **fields) -> str | None:
        """An event: written by this worker, now, into the camera's bucket on
        this server's resource, under the epoch this worker holds for it —
        recording or not. A camera it holds no epoch for is not its to
        observe. Nothing else is told."""
        if self.epochs.get(str(cid)) is None or not self.writing_allowed:
            return None
        self.observed.append((cid, self.wall(), kind))
        return super().observe(cid, kind, **fields)

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

    # The bus, drained: `actuator.pump()` gives `(dead, posted)`; every posted `(cid, kind, fields)` becomes
    # `observe(...)` — a line only if I still hold the epoch; every dead camera becomes
    # `reconciler.forget(cid)` (restart after backoff) plus `observe(cid, "silent")` — "the event with no
    # picture behind it, by definition".
    def pump_once(self) -> None:
        """The bus, drained: what elements posted becomes events — if I still
        hold the epoch — and what died becomes `lost` and a `silent` event."""
        self.drain_bus()
        super().pump_once()                             # …and what somebody asked this device to DO (the platform's requests)

    # …and on every beat between passes (`Worker.beat_once`): the bus too, then the requests.
    def beat(self) -> None:
        self.drain_bus()
        super().beat()

    # -- the platform's life cycle, in the holder's words (`w2cplatform/worker.py`) ------------------------------------
    # A lost lease stops ONE pipeline: `lost` names units the way the lease does — as text — and the reconciler keys by
    # the row's id, which the spec parsed (a number for cameras, a name for recordings): matched, never cast.
    def stop_unit(self, unit) -> None:
        uid = next((k for k in self.reconciler.running() if str(k) == str(unit)), unit)
        self.actuator("stop", {"id": uid})
        self.reconciler.drop(uid)                   # stopped by its lease, not failed: started again, if still mine

    def stop_all_units(self) -> None:
        self.actuator.stop_all()                    # with GStreamer, EOS lets the last access units reach each sink

    def fence_units(self) -> None:
        self.actuator.stop_all()
        self.reconciler.clear()                     # the pipelines were stopped underneath the loop

    def forget_units(self) -> None:
        self.rows, self.assignment_rev = [], 0
        self.reconciler.clear()                     # another name, another assignment: what failed under the old one
        self.reconciler.reset_backoff()             # …waits for nothing here

    def unit_word(self, unit) -> str:
        return f"camera {unit}"

    # A command goes into the DEVICE that carries the camera — one session per device, one call into it at a time — and
    # is performed only by the holder of a camera it holds. What the base compares is the device's KEY (`device_of`),
    # given while the device is open; `perform` calls the session that key names.
    def held_rows(self) -> dict[str, dict]:
        return {str(r["id"]): r for r in self.rows}

    def request_target(self, row: dict):
        key = device_of(row["source"]) if row.get("source") else None
        return key if key in self.devices else None

    def moved_refusal(self, unit: str) -> str:
        return (f"camera {unit} was moved to another device after this command was given: it was not performed — give it "
                f"again if it is still wanted")

    # The bus alone — on the pass, and on every beat between passes (`beat_once`): a device's event waited for the
    # pass, up to `poll` seconds, before it was a line any scenario could see — the part of the road from an event to
    # a device that no histogram measured, because the event's time is stamped when it is drained (the product drains
    # it in its loop of commands too). On the loop's thread either way: the actuator and the reconciler have no other.
    #
    # ONE LINE A DEVICE POSTED THAT CANNOT BE WRITTEN IS THAT LINE (the review's tenth pass): a driver's fields go into
    # `EventLog.append`, which refuses `class` and `v` with a `ValueError`, and a value JSON cannot carry raised a
    # `TypeError` — out of this loop, and what the bus had handed over after that line, any camera's, was gone with
    # every dead camera's `lost`. Now the line is dropped, logged and counted (`events_refused`, on `/metrics` as
    # `vms_device_events_refused_total`); a resource that does not answer (`OSError`) is not the line's, and is left
    # to the loop as before.
    def drain_bus(self) -> None:
        dead, posted = self.actuator.pump()
        for item in posted:
            try:
                cid, kind, fields = item
                self.observe(cid, kind, **fields)
            except PARSE_ERRORS as e:
                self.events_refused += 1
                log.error("%s: a device posted an event that cannot be written (%s: %.200s); dropped — the other events "
                          "are written", self.name, type(e).__name__, e)
        for cid in dead:
            self.reconciler.forget(cid)                 # died, not by command: started again after its delay
            self.observe(cid, "silent")                 # the event with no picture behind it, by definition
        self.flush_suppressed()                         # …storms that ENDED, which no observation will close

    # One command against an open device. Two verbs, because two are what an operator points at; a third
    # belongs here and not in a new place. Unknown verbs raise, which the caller turns into a refusal
    # recorded on the unit — an operator who asked for something this device cannot do gets an answer.
    #
    # …AND AN ARGUMENT IS A NUMBER OR A WORD (the product's cross-check of the eleventh review: an argument had no size).
    # `state` went to the driver as it stood in the row, as long as the row's ceiling let it be; one longer than
    # `ARG_MAX` is that command's refusal, its value not repeated.
    ARG_MAX = COMMAND_ARG_MAX

    def perform(self, device: str, row: dict, it: dict) -> dict:
        action = str(it.get("action", ""))
        long = [f for f in ("port", "state", "pulse_ms", "n") if len(str(it.get(f, ""))) > self.ARG_MAX]
        if long:
            raise ValueError(f"`{long[0]}` is {len(str(it[long[0]]))} characters long: an argument is a number or a word")
        dev = self.devices.get(device)
        if dev is None:
            raise ValueError(f"device {device} is not open now")    # closed between the look and the call
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

    # The read model, per assigned row: `id`, `ref`, `name`, `enabled`, `phase` (`running` if the reconciler
    # runs it; `pending` if disabled; `failed` if it has failures in a row; else `pending`),
    # `position` (`converged | lagging | stalled`), `revision`, `observed_revision` (what is actually
    # running), `epoch` (held, or 0). This list is the heartbeat's `status`; the controller's `read_model`
    # and the console's `/cameras` show it, and `/metrics` counts `phase == running` into
    # `vms_cameras_running`.
    def status(self) -> list[dict]:
        running, st = self.reconciler.running(), self.reconciler.status()
        out, back = [], self.held_back()
        for cam in self.rows:
            cid = cam["id"]
            pos = st[cid].state if cid in st else CONVERGED
            phase = "running" if cid in running else ("pending" if not cam["enabled"] else
                                                      ("failed" if cid in st and st[cid].failures else "pending"))
            lease = self.leases.get(str(cid))
            out.append({"id": cid, "ref": cam.get("ref", ""), "name": cam.get("name", str(cid)), "enabled": cam["enabled"], "phase": phase, "position": pos,
                        "revision": cam["revision"], "observed_revision": running.get(cid, 0),
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
            if str(cid) in back:                           # «device busy», or a source it cannot read: not opened, said why
                out[-1]["device_state"], out[-1]["why"] = back[str(cid)]
            if cam.get("source") and device_of(cam["source"]) in self.coincidences:   # recorded, and said (`describe_devices`)
                other = self.coincidences[device_of(cam["source"])][0]
                out[-1]["warning"] = (f"its device gives the same serial number as {other}: either one device under two "
                                      f"names, or two devices with one serial number. It is recorded. If it is one device, "
                                      f"point all its cameras at one of the two names and remove the other's device row")
        opening = self._opening()
        for cam, st in zip(self.rows, out):                # its device has not opened yet (the review's tenth pass)
            if cam.get("source") and device_of(cam["source"]) in opening:
                st["device_state"] = "opening"
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
    #
    # …and what it said LAST stands in for a question still on the device's line (the review's tenth pass, minor): the
    # door and the heartbeat ask the same questions, one of them found the other's not back and wrote `state: slow` with
    # no channels, while `devices_slow` said nothing was. A device is `slow` when it is (`_slow`, `_slow_asks`); a
    # question still on its way to a device that is not, with nothing said before, is `asking`.
    #
    # …AND A DEVICE THAT HAS NOT OPENED IS LISTED (the same pass, major; a run): a driver that did not come back from
    # `device_factory` left its device out of the heartbeat and out of `/devices`, `devices_slow` empty, the log silent,
    # its cameras `running`, and their relay commands waiting to expire. Now `state: opening` with `since` (the wall
    # time the open was begun), counted (`devices_opening`), said in the log once it outlasts `DEVICE_GRACE`, and named
    # in its cameras' status (`device_state`); one that refused to open is `state: failed` with its words.
    def device_status(self) -> list[dict]:
        known: dict[str, set] = {}
        for r in self.rows:
            if r.get("source"):
                known.setdefault(device_of(r["source"]), set()).add(str(channel_of(r["source"]) or r["id"]))
        devices = sorted(self.devices.items())
        heard = self._heard if self._heard is not None else self._ask_devices(self._status_asks(devices))
        slow = self._slow_devices()
        out = []
        for key, dev in devices:
            have = known.get(key, set())
            st: dict = {"device": key}
            said = {}
            for q in ("channels", "in_use"):
                k = (q, id(dev))
                if not hasattr(dev, q):
                    continue
                if k in heard:
                    said[q] = self._said_status[k] = heard[k]
                elif id(dev) not in slow and k not in self._dev_said and k in self._said_status:
                    said[q] = self._said_status[k]       # on the device's line now: what it said last
            if not hasattr(dev, "channels"):
                st.update(channels=0, known=sorted(have), unimported=[])
            elif "channels" in said:
                chans = [str(c) for c in said["channels"] or []]
                st.update(channels=len(chans), known=sorted(have), unimported=[c for c in chans if c not in have])
            else:
                st["known"] = sorted(have)
            if "in_use" in said:
                st["playbacks"] = said["in_use"]
            st["max_playbacks"] = getattr(dev, "max_playbacks", None)
            missing = [q for q in ("channels", "in_use") if hasattr(dev, q) and q not in said]
            if missing:
                failed = [q for q in missing if (q, id(dev)) in self._dev_said]
                st["state"] = "slow" if id(dev) in slow else ("failed" if failed else "asking")
                if st["state"] != "failed" and (since := self._asking_since(dev)) is not None:
                    st["since"] = since                  # since when the device has not answered (the eleventh review)
            if stuck := self.reads_stuck(dev):           # the playback door's reads it has not come back from: the
                st["reads_stuck"] = stuck                # cameras, and the device slow (the thirteenth review, major 18)
                st.setdefault("state", "slow")
            out.append({**st, **({"can": self.described[key]} if key in self.described else {}),
                        **({"same_serial_as": self.coincidences[key][0]} if key in self.coincidences else {})})
        opening = self._opening()
        for key in sorted(set(known) - set(self.devices)):
            if key in opening:
                out.append({"device": key, "state": "opening", "since": opening[key], "known": sorted(known[key])})
            elif key in self._open_failed:
                out.append({"device": key, "state": "failed", "why": f"it did not open: {self._open_failed[key]}",
                            "known": sorted(known[key])})
        return sorted(out, key=lambda d: d["device"])

    # The devices this holder wants and whose open has not come back: `{key: the wall time the open was begun}`.
    def _opening(self) -> dict[str, float]:
        with self._dev_lock:
            return {k[1]: c["since"] for k, c in self._dev_calls.items()
                    if k[0] == "open" and k[1] not in self.devices and not c["returned"].is_set()}

    # The wall time the question a device is answering now was begun — or, with none begun, the earliest of those waiting
    # on its line; None when nothing is.
    def _asking_since(self, dev) -> float | None:
        with self._dev_lock:
            head = self._dev_heads.get(id(dev))
            if head is not None:
                return head.get("begun")
            waiting = [c["since"] for c in self._dev_calls.values() if c["dev"] is dev and not c["returned"].is_set()]
        return min(waiting) if waiting else None

    def _status_asks(self, devices) -> list:
        return [((q, id(d)), d, getattr(d, q)) for _, d in devices for q in ("channels", "in_use") if hasattr(d, q)]

    # A camera's coverage as its device says it (`status_extra`): from the heartbeat's round, or asked on its own; a
    # device that did not answer has the coverage it said LAST — the summary of an archive that was there a moment ago,
    # beside `state: slow` for its device — and one that never answered has none.
    #
    # …WITH ITS AGE WHEN IT IS NOT FRESH (the review's twelfth pass, minor): the coverage said last went out as if said
    # now. Said again without an answer this round, it carries `said_at` — when the device said it — so whoever reads it
    # (a recorder closing a gap, the page) knows how old the archive's summary is.
    def _coverage_of(self, dev, cid):
        if not hasattr(dev, "coverage"):
            return None
        key = ("coverage", id(dev), str(cid))
        heard = self._heard if self._heard is not None else self._ask_devices([(key, dev, lambda: dev.coverage(cid))])
        if key in heard:
            self._said_coverage[key] = heard[key]
            self._said_coverage_at[key] = self.wall()
            return heard[key]
        return self._aged_coverage(key)

    # What the device said last of a camera's coverage, with `said_at` — or None when it never said.
    def _aged_coverage(self, key):
        said = self._said_coverage.get(key)
        if not isinstance(said, dict) or key not in self._said_coverage_at:
            return said
        return {**said, "said_at": self._said_coverage_at[key]}

    # Where the device's footage is, span by span, clipped to `[t0, t1)`. `None` means this driver cannot
    # list — which is not the same answer as "the device holds nothing here", and the caller must be able
    # to tell the two apart. Costs no playback session: listing is not reading.
    def recordings(self, cam, t0: float, t1: float) -> list[tuple[float, float]] | None:
        row = next((r for r in self.rows if str(r["id"]) == str(cam)), None)
        if row is None:
            raise KeyError(cam)
        dev = self.device_of_row(row)
        # ONE WAIT FOR THE DOOR'S TWO QUESTIONS (the review's twelfth pass, minor): the coverage, then the listing, each
        # up to `DOOR_ASK_WAIT` — a door that promised five seconds waited ten. Both are asked inside the one deadline.
        until = time.monotonic() + self.DOOR_ASK_WAIT
        if dev is None or self._door_coverage(dev, cam, until) is None:
            raise KeyError(cam)
        lister = getattr(dev, "recordings", None)
        if lister is None:
            return None
        return self._door_ask(dev, ("door-recordings", id(dev), str(cam), float(t0), float(t1)), lambda: lister(cam, t0, t1),
                              until)

    # A question the playback door puts to a device, ON THE DEVICE'S LINE (the eleventh review, a minor): `coverage` and
    # the listing went into the device beside the heartbeat's questions, and a recorder that answers one request at a
    # time had five at once. Waited for up to `DOOR_ASK_WAIT`, off the loop; the device's own error is raised as it was;
    # an answer that does not come is a `TimeoutError` — the door's 503, "ask again".
    DOOR_ASKS_PER_DEVICE = 4                             # a door's questions on one device's line at once: the next is 503

    def _door_ask(self, dev, key, fn, until: float | None = None):
        def run():
            try:
                return True, fn()
            except Exception as e:                       # noqa: BLE001 — the device's word, raised to the door below
                return False, e
        with self._dev_lock:                             # what the door gave up on and came back since: nobody asks it again
            for k in [k for k, c in self._dev_calls.items() if str(k[0]).startswith("door-") and c["returned"].is_set()
                      and time.monotonic() - c["t0"] - c.get("took", 0.0) > self.DOOR_ASK_WAIT]:
                del self._dev_calls[k]
            waiting = sum(1 for k, c in self._dev_calls.items() if str(k[0]).startswith("door-") and c["dev"] is dev)
        if waiting >= self.DOOR_ASKS_PER_DEVICE and key not in self._dev_calls:
            raise TimeoutError(f"the device has {waiting} questions of this door on its line already — ask again")
        wait = self.DOOR_ASK_WAIT if until is None else max(0.0, min(self.DOOR_ASK_WAIT, until - time.monotonic()))
        heard = self._ask_devices([(key, dev, run)], grace=wait)
        if key not in heard:
            raise TimeoutError(f"the device has not answered within {self.DOOR_ASK_WAIT:.0f} s — it is busy or does not "
                               f"answer; ask again")
        ok, value = heard[key]
        if not ok:
            raise value
        return value

    # …and what a door asks first: the camera's coverage, by the line — or, when it does not come, what the device said
    # of it last (`_said_coverage`, the heartbeat's): an archive that was there a moment ago is still worth a request.
    def _door_coverage(self, dev, cam, until: float | None = None):
        if not hasattr(dev, "coverage"):
            return None
        try:
            return self._door_ask(dev, ("door-coverage", id(dev), str(cam)), lambda: dev.coverage(cam), until)
        except TimeoutError:
            if ("coverage", id(dev), str(cam)) in self._said_coverage:
                return self._aged_coverage(("coverage", id(dev), str(cam)))
            raise

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
    #   one capability      holds at most `PLAYBACK_PER_CAPABILITY` connections at once (`playback_handler`): one
    #                       process's reads of one camera
    #
    # So what the door holds of pieces is the budget, whoever asks — a connection holds one piece at a time, and lets go
    # of it before it reads the next. A driver whose stream is far above the rate its first piece came at overshoots one
    # piece (counted, `force`), and the next is smaller.
    PLAYBACK_PIECE = 60.0
    PLAYBACK_FIRST = 2.0
    PLAYBACK_PIECE_BYTES = 4 << 20
    PLAYBACK_BUDGET = 64 << 20
    PLAYBACK_BUDGET_WAIT = 5.0
    PLAYBACK_PER_CAPABILITY = 2

    # A piece to a slow reader is at most what it takes in `PLAYBACK_PACE_SECONDS` at the pace it took the last one, and
    # never less than `PLAYBACK_MIN_PIECE` (the review's ninth pass, minor): a reader at 80 kB/s held 4 MiB for fifty
    # seconds, and whoever came after it waited for the budget.
    PLAYBACK_MIN_PIECE = 256 << 10
    PLAYBACK_PACE_SECONDS = 10.0

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

    def playback_capability(self, cap: str, step: int) -> bool:
        """Count a connection on one camera's capability in (`+1`: False when it has its `PLAYBACK_PER_CAPABILITY`) or out."""
        return self._playback_count("_playback_caps", cap, step, self.PLAYBACK_PER_CAPABILITY)

    def playback_budget(self) -> "ByteBudget":
        return self.__dict__.setdefault("_playback_budget", ByteBudget(self.PLAYBACK_BUDGET))

    # Held by the door's budget, and by the bound on one capability's connections (`playback_handler`).
    def playback_pieces(self, cam, t0: float, t1: float):
        row = next((r for r in self.rows if str(r["id"]) == str(cam)), None)
        if row is None:
            raise KeyError(cam)
        dev = self.device_of_row(row)
        if dev is not None and (why := self._door_stuck(dev, cam)):
            raise TimeoutError(why)                      # a device the door already waited for in vain: 503 at once
        cov = self._door_coverage(dev, cam) if dev is not None else None   # by the device's line (the eleventh review)
        if cov is None:
            raise KeyError(cam)
        t0, t1 = max(float(t0), float(cov.get("from", t0))), min(float(t1), float(cov.get("to", t1)))
        budget = self.playback_budget()

        def pieces():
            at, rate, pace, held = t0, None, None, 0
            try:
                while at < t1:
                    budget.give(held)                    # the last piece is the client's now: its bytes are free
                    held = 0
                    want = self.PLAYBACK_PIECE_BYTES
                    if pace is not None:                 # a slow reader: what he takes in `PLAYBACK_PACE_SECONDS`
                        want = max(self.PLAYBACK_MIN_PIECE, min(want, int(pace * self.PLAYBACK_PACE_SECONDS)))
                    full = (f"this door holds {budget.limit} bytes of footage at once, and they are all being sent — "
                            f"retry")
                    # THE BYTES ARE TAKEN ONCE THE DEVICE HAS OPENED ITS FOOTAGE (the thirteenth review, major 19; a
                    # run, `h13_door many`: twenty hung NVRs × eight reads held the door's 64 MiB while it waited for
                    # them to open, and 144 of 160 requests, healthy devices' among them, were "the door is full").
                    # The piece is sized by what the budget would give now (`room`, waited for as a take is), and the
                    # bytes are taken when the device says the footage is open (`_door_read`'s `opened`): a device that
                    # never opens holds none of them.
                    plan = budget.room(want, self.PLAYBACK_BUDGET_WAIT)
                    if not plan:
                        raise OverflowError(full)

                    def admit():
                        nonlocal held
                        held = plan if budget.take(plan, self.PLAYBACK_BUDGET_WAIT) else 0
                        if not held:
                            raise OverflowError(full)
                    # Seconds: `PLAYBACK_FIRST` for the first piece; then as many as the bytes planned come to at the
                    # rate the last piece came at — never more than `PLAYBACK_PIECE`, never less than one.
                    span = min(self.PLAYBACK_FIRST, self.PLAYBACK_PIECE) if rate is None else \
                        max(1.0, min(self.PLAYBACK_PIECE, plan / max(rate, 1.0)))
                    b = min(t1, at + span)
                    got = self._door_read(dev, cam, at, b, admit)   # opened, read and closed before a byte is sent
                    size = sum(len(c) for c in got)
                    budget.force(size - held)            # what the piece really is, whatever was asked
                    held = size
                    rate = size / max(b - at, 1e-3)
                    sent = time.monotonic()
                    yield from got
                    took = time.monotonic() - sent       # how long the client took to take it
                    pace = size / took if took > 1.0 else None
                    at = b
            finally:
                budget.give(held)
        return pieces()

    # A PIECE IS READ OFF THE DOOR'S THREAD, AND WAITED FOR WITH A DEADLINE (the review's twelfth pass, major 8; a run,
    # `h5_door_http`). The door opened, read and closed a device's session on the connection's own thread: eight
    # `/playback` to a recorder that stopped answering never ended, and from the same address `/playback` to a healthy
    # recorder, `/recordings` and `/devices` were 503 — the door's connections were the hung device's, and no socket
    # deadline ends a thread that is inside a call to a device. The door's questions had their line and their wait
    # (`_door_ask`); its reads had neither. Now a piece is read by a thread of its own — open, read, close, the session
    # closed before the piece is handed on, as before — and the door waits for it:
    #
    #   the open            `DOOR_ASK_WAIT`, as long as a question; the device's own refusal (full: `OverflowError`) as it was
    #   each chunk          `PLAYBACK_STALL`: a read that gives nothing for so long is given up — a first piece is the
    #                       door's 503 «ask again», a later one ends the reply short, and the connection is let go
    #   the whole piece     `PLAYBACK_STALL` and the piece's seconds over `PLAYBACK_DEVICE_PACE`: a device that trickles
    #                       a byte just inside the stall deadline is cut all the same — a card played back at the speed
    #                       it was recorded is well inside it
    #   per device          `DOOR_READS_PER_DEVICE` reads not back at once, the next 503
    #   per door            `DOOR_READS` reads not back at once, every device's together — a read given up on whose
    #                       thread is still inside the device counted — the next 503 (the thirteenth review, major 19:
    #                       twenty hung NVRs held the door's threads at eight each, and nothing bounded the sum)
    #   stuck               a CAMERA with a read the door gave up on and that has not come back since is answered 503 at
    #                       once (`_door_stuck`); its device's other cameras are read as before — one channel's hung read
    #                       closed `/playback` to every channel of an NVR (the thirteenth review, major 18). A device
    #                       with such reads on `DOOR_STUCK_CHANNELS` of its cameras is stuck as a whole, and so is one
    #                       whose line has been in a question of the whole device (its channels, its sessions in use)
    #                       longer than `DOOR_ASK_WAIT`; a question of one camera (its coverage, its listing) that hangs
    #                       stops no read — the door falls back on the coverage said last, and a read has its own
    #                       deadlines. What is stuck is said: `reads_stuck` on the device in `/devices` and the
    #                       heartbeat, `door_reads_stuck` beside `devices_slow`.
    #
    # A read given up on is not read further (a streaming driver's chunks are no longer taken), and its session is closed
    # by its own thread whenever the device comes back.
    PLAYBACK_STALL = 10.0                # seconds a device's read may give nothing before the door gives up on it
    PLAYBACK_DEVICE_PACE = 0.5           # seconds of footage a second a device gives at least, over a whole piece
    DOOR_READS_PER_DEVICE = 8            # the door's reads of one device not back at once: the next is 503
    DOOR_READS = 32                      # …of every device together: the next is 503
    DOOR_STUCK_CHANNELS = 2              # cameras of one device with a read given up on: the device is stuck as a whole

    # The cameras of a device whose read this door gave up on and that has not come back: `{camera: since}` (monotonic).
    def _reads_lost(self, dev) -> dict[str, float]:
        lost: dict[str, float] = {}
        with self._dev_lock:
            for j in self._door_reads.get(id(dev), ()):
                if j["lost"]:
                    lost[j["cam"]] = min(lost.get(j["cam"], j["since"]), j["since"])
        return lost

    def _door_stuck(self, dev, cam) -> str | None:
        now = time.monotonic()
        lost = self._reads_lost(dev)
        with self._dev_lock:
            head = self._dev_heads.get(id(dev))
        if str(cam) in lost:
            return (f"the device has not come back from a read of this camera that this door gave up on "
                    f"{now - lost[str(cam)]:.0f} s ago — it is busy or does not answer; ask again")
        if len(lost) >= self.DOOR_STUCK_CHANNELS:
            return (f"the device has not come back from reads of {len(lost)} of its cameras that this door gave up on, "
                    f"the first {now - min(lost.values()):.0f} s ago — it is busy or does not answer; ask again")
        whole = head is not None and str(head["key"][0]) not in ("coverage", "door-coverage", "door-recordings")
        if whole and now - head["t0"] > self.DOOR_ASK_WAIT:
            return (f"the device has not answered a question for {now - head['t0']:.0f} s — it is busy or does not "
                    f"answer; ask again")
        return None

    # The playback door's reads the device has not come back from, said (the thirteenth review, major 18: a device whose
    # reads hung was `state: None` in `/devices`, and the regression was seen by nobody): the cameras of each, and the
    # count over the devices for the heartbeat.
    def reads_stuck(self, dev) -> list[str]:
        return sorted(self._reads_lost(dev))

    def door_reads_stuck(self) -> int:
        with self._dev_lock:
            return sum(1 for jobs in self._door_reads.values() for j in jobs if j["lost"])

    # `opened`: called on the door's thread when the device has opened the footage, before a chunk is taken — the door
    # takes the piece's bytes there (`playback_pieces`); what it raises gives the read up and is raised to the door.
    def _door_read(self, dev, cam, t0: float, t1: float, opened=None) -> list[bytes]:
        import queue
        if why := self._door_stuck(dev, cam):
            raise TimeoutError(why)
        # `given_up`: nobody waits for it any more, not read on; `lost`: given up because the device did not answer in
        # time — what makes its camera stuck. A read let go for the door's own reason (no bytes free) is not lost.
        job = {"since": time.monotonic(), "given_up": False, "lost": False, "q": queue.Queue(), "cam": str(cam)}
        with self._dev_lock:
            jobs = self._door_reads.get(id(dev), [])
            every = sum(len(j) for j in self._door_reads.values())
            if len(jobs) >= self.DOOR_READS_PER_DEVICE:
                raise TimeoutError(f"the device has {len(jobs)} reads of this door under way already — ask again")
            if every >= self.DOOR_READS:
                raise TimeoutError(f"this door has {every} reads of devices under way already — ask again")
            self._door_reads.setdefault(id(dev), []).append(job)

        def run():
            sid, said = None, None
            try:
                sid = dev.open_playback(cam, t0, t1)     # OverflowError when the device is full
                job["q"].put(("open", None))
                got = dev.read(sid)
                if isinstance(got, (bytes, bytearray, memoryview)):
                    job["q"].put(("chunk", bytes(got)))
                else:
                    try:
                        for c in got:
                            if job["given_up"]:
                                break                    # nobody waits for the rest: not read on
                            job["q"].put(("chunk", bytes(c)))
                    finally:
                        getattr(got, "close", lambda: None)()
            except Exception as e:                       # noqa: BLE001 — the device's word, raised at the door below
                said = e
            finally:
                try:
                    if sid is not None:
                        dev.close_playback(sid)          # before the door hands a byte of the piece on
                except Exception as e:                   # noqa: BLE001
                    said = said or e
                with self._dev_lock:
                    jobs = self._door_reads.get(id(dev), [])
                    if job in jobs:
                        jobs.remove(job)
                    if not jobs:
                        self._door_reads.pop(id(dev), None)
                job["q"].put(("end", said))

        threading.Thread(target=run, name=f"{self.name}-read", daemon=True).start()
        until = job["since"] + self.DOOR_ASK_WAIT + self.PLAYBACK_STALL + (t1 - t0) / self.PLAYBACK_DEVICE_PACE
        out, is_open = [], False
        while True:
            wait = min(self.PLAYBACK_STALL if is_open else self.DOOR_ASK_WAIT, until - time.monotonic())
            try:
                kind, value = job["q"].get(timeout=max(0.0, wait))
            except queue.Empty:
                job["given_up"] = job["lost"] = True
                if not is_open:
                    why = f"the device has not opened its footage within {self.DOOR_ASK_WAIT:g} s"
                elif time.monotonic() >= until:
                    why = f"the device gave {t1 - t0:.0f} s of footage slower than {self.PLAYBACK_DEVICE_PACE:g} s a second"
                else:
                    why = f"the device gave nothing for {self.PLAYBACK_STALL:g} s"
                raise TimeoutError(f"{why} — it is busy or does not answer; the playback was cut, ask again") from None
            if kind == "open":
                is_open = True
                if opened is not None:
                    began = time.monotonic()
                    try:
                        opened()                         # the piece's bytes: waited for, then the device read on
                    except BaseException:
                        job["given_up"] = True           # not read on; its session closed by its own thread
                        raise
                    until += time.monotonic() - began
            elif kind == "chunk":
                out.append(value)
            else:
                if value is not None:
                    raise value
                return out

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

    # The platform's heartbeat (`Worker.platform_fields`: `server`, `instance`, `labels`, `capacity`, `headroom`,
    # `conflicts`, `started`, `previous_*`, `fenced` while fenced, `fetched`) to the object `vms/heartbeats/<name>`, with
    # the holder's own beside it (`heartbeat_fields`): `alloc`, `assignment_rev`, `passes`, the counters, `devices` and
    # `heartbeat_extra`. The controller's `capacity_of`, `labels_of`, `server_of`, `headroom`, `failover_seconds` and the
    # console's metrics all read from here.
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
            super().heartbeat_once()
        finally:
            self._heard = None

    def heartbeat_fields(self) -> dict:
        return {"alloc": self.alloc, "assignment_rev": self.assignment_rev, "passes": self.passes,
                "store_errors": self.store_errors + sum(l.store_errors for l in self.leases.values()),
                "pass_failures": self.pass_failures,
                "unconfirmed": len(self.unconfirmed()),       # units recording past their lease, the store silent
                **({"was_fenced": self.was_fenced} if self.was_fenced else {}),
                "devices": self.device_status(), **self.heartbeat_extra()}

    # The devices said slow: those whose last command did not answer inside `PERFORM_GRACE` (the base's `_slow`, by the
    # device's key) and those whose last question did not answer inside `DEVICE_GRACE` (`_slow_asks`, by session).
    def _slow_devices(self) -> set[int]:
        return self._slow_asks | {id(d) for k, d in self.devices.items() if k in self._slow}

    # What the requests family says (`fetched`, the outcomes, the road) is the base's (`Worker.requests_fields`); here,
    # what only a holder of devices can say.
    def heartbeat_extra(self) -> dict:
        # What the beat waits on, said (the review's eighth pass, minor): devices whose last call did not answer — on
        # `/metrics` as `vms_devices_slow` (metrics vms.subsystem.yaml declares, `metrics:`), beside the base's
        # `commands_in_flight`.
        slow = self._slow_devices()
        return {**({"devices_slow": len(slow)} if slow else {}),
                # The playback door's reads a device has not come back from (`_door_read`; the thirteenth review).
                **({"door_reads_stuck": stuck} if (stuck := self.door_reads_stuck()) else {}),
                # Devices whose open has not come back (`device_status`; the tenth pass): `state: opening` each.
                **({"devices_opening": len(opening)} if (opening := self._opening()) else {}),
                # Keys whose device said another identity than before (`_changed`): counted since the process started.
                **({"identity_changes": self.identity_changes} if self.identity_changes else {}),
                # Lines a device posted that could not be written (`drain_bus`; the tenth pass): counted, not raised.
                **({"events_refused": self.events_refused} if self.events_refused else {}),
                # Devices whose identity another key's row says too (`describe_devices`; the ninth pass): said, not refused.
                **({"identity_coincidences": len(self.coincidences)} if self.coincidences else {}),
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
    # ceiling (М10A Lesson 19), and a field that grows with the device does not belong in it. The
    # heartbeat keeps the summary — two numbers, enough to draw a timeline and to know there is something
    # to ask about — and whoever needs the spans pays a request for them.
    #
    # WHO MAY READ THE CARD (the review's fourth pass, blocker 4). `/playback/<cam>` asks — when the cluster is gated,
    # as the console does (`Gate.gated`) — for the capability a process derives from this door's key for this camera
    # (`/playback/<cam>/<capability>`, the recorder and the survey: `playback.process_url`). None, or another camera's:
    # 403, and an `access.denied` line. A page reads a camera's footage at its recording's door, with a door token, and
    # that door says who read (ADR 0015, `vms/footage.py`). The listing and the device list stay as they were: where the footage is, not the
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
            self._playback_journal = Journal(self.resource_root, f"door-{self.name}", self.wall)
        return self._playback_journal

    # `None` when the request may be served; else `(status, reason)`. `rest` is what follows `/playback/<cam>`.
    def playback_refusal(self, cam: str, rest: str, q: dict, addr: str):
        from w2cplatform.access import Denied, Gate
        from . import playback as pb
        if getattr(self, "_playback_gate", None) is None:
            self._playback_gate = Gate(self.vars, self.wall, glass=False)   # whether the cluster asks: no session of its own
        try:
            if not self._playback_gate.gated():
                return None                              # an open cluster: the console it fronts is open too
        except Denied as e:
            return e.status, e.why
        key = getattr(self, "playback_key", None)
        if not key:
            return 503, "this door has no key: it admits nobody in a gated cluster"
        import hmac
        if rest and hmac.compare_digest(rest, pb.capability(key, cam)):
            return None                                  # a process of this cluster, for this camera
        why = "a capability for another camera, or another door" if rest else "no capability: this door is the processes'"
        self.playback_journal().say("access.denied", user="?", capability="playback", target=cam, addr=addr, why=why,
                                    worker=self.name)
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
                    except TimeoutError as e:                    # the device's line did not come to it (`_door_ask`)
                        return self._send(503, {"detail": str(e), "error": "device busy"})
                    if spans is None:
                        return self._send(501, {"detail": "this driver cannot list what the device holds",
                                                "error": "no index"})
                    return self._send(200, {"spans": [{"from": a, "to": b} for a, b in spans]})
                segs = u.path.split("/")                         # "", "playback", <cam>[, <capability>]
                if len(segs) not in (3, 4) or segs[1] != "playback" or not segs[2]:
                    return self._send(404, {"detail": "no such route", "error": "no such path"})
                cam = segs[2]
                refused = gw.playback_refusal(cam, segs[3] if len(segs) == 4 else "", q, str(self.client_address[0]))
                if refused is not None:
                    return self._send(refused[0], {"detail": refused[1], "error": "denied"})
                # One camera's capability holds `PLAYBACK_PER_CAPABILITY` connections at once (`playback_pieces`; the
                # review's seventh pass): eight on one address were eight pieces of one interval.
                held = segs[3] if len(segs) == 4 else ""
                if held and not gw.playback_capability(held, +1):
                    return self._send(503, {"detail": f"this capability is being read {gw.PLAYBACK_PER_CAPABILITY} times "
                                                      f"at once already — one process, one interval", "error": "busy"})
                try:
                    return self._play(cam, q)
                finally:
                    if held:
                        gw.playback_capability(held, -1)

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
                except TimeoutError as e:                        # the device's line did not come to it (`_door_ask`)
                    return self._send(503, {"detail": str(e), "error": "device busy"})
                # A stream, and its end said (`playback_pieces`): to a client that speaks HTTP/1.1, chunks and the last
                # one only when every piece went — a device that failed half way is a reply that ends short, which
                # the client SEES; to an HTTP/1.0 one, the bytes until the connection closes, as before. Written a
                # piece of the wire's size at a time, to a client that keeps the pace (`Paced`).
                # A piece is let go before the next is read — by this loop as by `playback_pieces` — so a connection
                # holds one, as the door's budget counts it.
                out = Paced(self, start_stream(self, 200, "video/mp4"), gw.PLAYBACK_MIN_RATE,
                            gw.PLAYBACK_GRACE)
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
                               asks="for a process's capability for the camera, in a cluster in a domain (`vms/playback.py`); outside one, nobody")
        srv = door_server((host, self.playback_port if port is None else port), self.playback_handler(),
                          self.PLAYBACK_CONNECTIONS, self.PLAYBACK_PER_ADDRESS)
        self.playback_port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        log.info("%s: playback door on %s:%d", self.name, host, self.playback_port)
        return srv
