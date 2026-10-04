"""python3 -m vms worker|recorder|gateway|detworker|detjobworker|surveyworker|autoworker|controller|console|resource —
the VMS's processes on a box. The controllers of the other subsystems are the platform's, run from their specs
(`python3 -m w2cplatform controller rec|live|det|detjob|survey|auto`, `w2cplatform/host.py`; the boundary's step 5);
the loops of `controller`, `console` and `resource` here are the platform's too (`host.controller_loop`,
`host.sweep_loop`, `host.every`, `host.run_resource`) — run over the VMS's own controller (a device is one group),
console (its routes) and resource (its keeps) until the boundary's step 6 turns those into declarations.

    PLATFORM_DIR=/data/platform     the platform's state (config/, objects/, events/) — in `w2c.env`, the platform's half
    ARCHIVE=/data/platform/events   the platform's events archive, the resource's tree — `w2c.env` too
    ARCHIVE_VOLUME  MEDIA_DIR=/data/media   the recorder's own volume (`/data/vms/obsd/volume`); the holder's files
    OBSD_SOCKET=/run/vms-obsd/obsd.sock   the host's ObjectStorage daemon — every recorder writes its footage through it
    WORKER_NAME=w-1                  the slot to claim (systemd: %i); unset: NOMAD_ALLOC_INDEX → w-<index>;
                                     neither: the first free slot, a lapsed one first
    CAPACITY=50                      cameras this worker can carry — exported as headroom for the autoscaler
    RECORDER_NAME=r-1                a recorder's slot (systemd: %i); CAPACITY here is recordings — this server's disks and NIC
    CONSOLE_PORT=8080                the console (its own process, its own token: the operator's rows, never placement)
    RESOURCE_PORT=8090  RESOURCE_URL the resource process: heartbeat, the policy pass, the event index served as /events
    GATEWAY_PORT=8082  GATEWAY_URL   a live gateway: WHEP on this port (`auto` — ask the OS, which is what a
                                     SECOND gateway on one box needs); the URL the console proxies to
    RTSP_PORT=8554  PLAYBACK_PORT=8083   the worker's two doors, `auto` likewise: a template that fixes a
                                     number is a door only the first instance on the box can open
    GATEWAY_NAME=g-1                 its slot (systemd: %i); CAPACITY here is viewers
    DET_NAME=d-1                     a detector worker's slot; CAPACITY here is streams; NOMAD_META_labels=gpu says where it is
    COMMANDS_BEAT=0.25               worker: how often it looks at its request rows between passes, in seconds; 0 — only on the pass
    REACH_BUDGET=10                  controller: units it moves in one pass to a server that reaches them (`ensure_reach`);
                                     a group left for a later pass is the alarm `units.over_budget` (`spec.reach_budget`)
    LONG_POLL=0                      autoworker: do not ask the resources to say when a watched event is written; it finds
                                     them on its pass, every PASS_SECONDS, as it did (`w2cplatform/longpoll.py`)
"""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # __main__.py — `python3 -m vms worker | controller | console | resource | …`: the box's processes
#
# **Role in the module.** The entrypoint of the VMS's units (`deploy/*.container` say `Exec=python3 -m vms <verb>`,
# the controllers of the other subsystems `Exec=python3 -m w2cplatform controller <sub>`; the Containerfile's default
# `CMD` is `worker`). It reads the environment, opens the two
# file-backed stores under `$PLATFORM_DIR` with the *right token for the verb*, builds the process's object
# from `worker.py` / `controller.py` / `console.py` / `resource.py` / …, and runs it until SIGTERM/SIGINT. It is
# glue and nothing else: no logic of its own beyond wiring, and each verb's token is deliberately narrower
# than the whole `vms/*` prefix. `tests/test_deploy_units.py` imports this module (without running it) and
# checks that the verbs in the dispatch table are exactly the ones the units invoke.
#
# Environment (from the docstring and the code):
# - `PLATFORM_DIR` (default `/data/platform`, `runtime.platform_dir`) — the platform's state: `<dir>/config` is
#   `FileVariables`, `<dir>/objects` is `FsObjectStore`, `<dir>/events` the events archive.
# - `ARCHIVE` (`runtime.events_root`: `<PLATFORM_DIR>/events`) — the platform's events archive, the resource's tree:
#   every subsystem's buckets, each process a client of it (group `w2c-events`). A recorder with nothing declared
#   formats its server's own volume at `ARCHIVE_VOLUME`, by default `config.OWN_VOLUME` (`/data/vms/obsd/volume`:
#   the archive engine is the VMS's, and so are its volumes).
#   `MEDIA_DIR` is read by `gstvms/uri.py`, not here.
# - `OBSD_SOCKET` — the host's ObjectStorage daemon (`vms/obsd.py`); `OBSD_TIMEOUT` (`10`) how long a
#   recorder waits for one answer from it — shorter than a lease.
# - `WORKER_NAME` — the slot to claim (systemd's `%i`); unset: `NOMAD_ALLOC_INDEX` → `w-<index>`; neither:
#   `None`, which makes `VmsWorker` claim the first free slot, a lapsed one first.
# - `CAPACITY` (default `50`) — cameras this worker can carry; exported as `headroom`. Also passed to the
#   controller and console as the *fallback* for a worker whose heartbeat says nothing.
# - `CONSOLE_HOST` (`127.0.0.1`), `CONSOLE_PORT` (`8080`) — where the console listens
#   (`console.container` sets `0.0.0.0`).
# - `RESOURCE_HOST` (`127.0.0.1`), `RESOURCE_PORT` (`8090`), `RESOURCE_URL` — the resource process's HTTP and the URL
#   its heartbeat advertises (the console asks `/events` there).
# - `LOG_LEVEL` (`INFO`) — `logging.basicConfig` level.
#
# ## Module-level names
# - `root` — `$PLATFORM_DIR`, read once at import.
# - `stop` — the platform's flag (`w2cplatform.host.stop`), set by the SIGTERM/SIGINT handler; every verb loops on
#   it. The handler is installed when the module is RUN (`if __name__ == "__main__"`), never at import: a process that
#   imports the module (the tests do) keeps its own signals.
#
# ### `if __name__ == "__main__"`
# Dispatch table on `sys.argv[1]`: the workers (worker, recorder, gateway, detworker, detjobworker, surveyworker,
# autoworker) and the three processes of the platform that still run a hook of the VMS's (controller, console,
# resource). `test_the_units_run_the_entrypoints_the_package_has` regex-extracts the names and matches them against
# the `Exec=` lines of the Quadlet units — `python3 -m vms <verb>` and `python3 -m w2cplatform controller <sub>`.
#
# ## Notes
# - Three tokens, three processes: `vmsworker` (epochs, slots), `vmscontroller` (placement), `console`
#   (the operator's rows). Together they partition `vms/*`; none of them can do another's job. The mounts in
#   `deploy/` repeat the same split in bytes (`test_who_may_write_where_is_in_the_mounts_too`).
# - `CAPACITY` means two different things depending on the verb: the worker's own number (what it heartbeats
#   and places by) versus the controller's fallback for a worker that has not spoken yet
#   (`test_capacity_is_the_workers_word_not_the_controllers`).
# - `resource` runs the platform's `Resource` as a process on the box exactly as М11 runs it as a job:
#   heartbeat, HTTP, the policy pass (the VMS's hook first, then bucket retention, then the mirror — off on
#   one box), and the `EventIndex` over the tree. The old `retain` verb and its timer are gone: a pass
#   every 600 s from the process's loop is the same pass, and a oneshot could not hold an index's cache.
# ================================================================================================
from __future__ import annotations

import logging
import os
import signal
import sys
import threading

from w2cplatform import host, runtime
from w2cplatform.host import stop
from w2cplatform.objects import FsObjectStore
from w2cplatform.variables import open_vars, store_url

from .controller import VmsController
from .worker import FakeActuator, VmsWorker, commands_beat

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(name)s %(levelname)s %(message)s")
root = runtime.platform_dir(os.environ)
# The store seam: a process is told a URL and nothing else (`w2cplatform.variables.open_vars`). On a box
# this is `file://` — in-process, no daemon, no hop. `PLATFORM_STORE=configstore:///run/configstore/<role>.sock` in a
# cluster (`store_url`), `k8s://…` later; not one of those names appears in the loop.
STORE_URL = store_url(os.environ, "file://" + os.path.join(root, "config"))


# Builds `vmsworker`:
# - Resolves the slot name: `WORKER_NAME`, else `w-$NOMAD_ALLOC_INDEX`, else `None`. (Same rule as
#   `worker.slot_from_environment`, written out again here.)
# - Opens Variables as writer `vmsworker` with `config.WORKER_ACL` — `Subsystem.acl_worker()` for `vms`
#   (epochs, slot, the place it took) plus `vms/devices/*`: a worker says what a device it holds turned out to
#   be (М10B Lesson 25), and can write nothing else. A bug that tried to write a camera row would be a
#   `Forbidden` from the store.
# - Tries `gstvms.actuator.GstActuator()` — `driverpacksrc ! tee`, served as the RTSP fan-out on :8554; on
#   `ImportError` (no `gi`) logs a warning and uses `FakeActuator`, which holds nothing. The worker records
#   nothing either way: recording is the recorder's (`recorder` below).
# - Constructs `VmsWorker(name, vars_, objects, act, capacity=$CAPACITY, archive_root=archive)` — its events
#   go to this server's resource under `vms/<cam>/` — the
#   constructor claims the slot — logs the claimed name and instance, and calls `w.run(stop=stop)`. `run`
#   releases the slot on the way out, so SIGTERM is an orderly stop (scale-in), while a kill leaves the slot
#   to lapse.
def worker() -> None:
    from w2cplatform import runtime
    from .config import WORKER_ACL
    name = runtime.slot(os.environ, "WORKER_NAME", "w")
    vars_ = open_vars(STORE_URL, writer="vmsworker", acl={"vmsworker": WORKER_ACL})
    objects = FsObjectStore(os.path.join(root, "objects"))
    archive = runtime.events_root(os.environ)
    try:
        from gstvms.actuator import GstActuator
        from .config import port_of, RTSP_PORT
        rtsp_host = os.environ.get("RTSP_HOST", "127.0.0.1")     # loopback unless somebody opens it (`vms/config.py`)
        act = GstActuator(rtsp_port=port_of(os.environ.get("RTSP_PORT"), RTSP_PORT), rtsp_address=rtsp_host)
        from .config import opened_beyond_loopback
        opened_beyond_loopback("the RTSP fan-out", rtsp_host, logging.getLogger("vmsworker"))
    except ImportError:
        logging.warning("no GStreamer: the fake actuator holds nothing")
        act = FakeActuator()
    # Devices with an archive of their own — a camera's card, an NVR's disks (Lesson 15). The real factory
    # is a DriverPack session; without it a source has no footage but its live stream, which is the box in
    # this course.
    try:
        from gstvms.devices import open_device as device_factory              # type: ignore
    except ImportError:
        device_factory = None
    w = VmsWorker(name, vars_, objects, act, capacity=int(os.environ.get("CAPACITY", "50")), archive_root=archive,
                  device_factory=device_factory)
    w.rtsp_host = os.environ.get("RTSP_HOST", "127.0.0.1")   # what the fan-out is bound to is what the heartbeat announces
    # The port is the worker's own (`$PLAYBACK_PORT`, `auto` for "ask the OS"), read in its constructor and
    # written back here by whatever the socket actually got.
    srv = w.serve_playback()                             # `$PLAYBACK_HOST`, loopback by default — it was every interface
    logging.info("worker %s (instance %s) claimed its slot; playback on %s", w.name, w.instance, srv.server_address)
    try:
        # `beat`: between two passes it looks at its request rows every quarter of a second (`COMMANDS_BEAT`; 0 —
        # only on the pass). A command is the second half of the road from an event to a device (`VmsWorker.between`).
        _present(w)
        w.run(stop=stop, beat=commands_beat(os.environ))
    finally:
        srv.shutdown()


# Builds `recworker` — the fourth subsystem's worker, the only one placed on top of the archive:
# - the slot: `RECORDER_NAME`, else `r-$NOMAD_ALLOC_INDEX`, else whichever is free; Variables as writer
#   `recworker` with the platform's worker grant for `rec` — epochs, its slot and its hold.
# - its session with the host's ObjectStorage daemon (`OBSD_SOCKET`): every volume it opens is a handle of it.
# - `gstvms.actuator.GstRecActuator()` — `rtspsrc ! h264parse ! appsink` per recording, each access unit a
#   sample into the volume's writer; without GStreamer the fake, which records nothing by itself.
# - its archive door (`ARCHIVE_HOST`, loopback unless said otherwise; `ARCHIVE_PORT`, any): `/timeline` and
#   `/samples` over the volume it holds — what the console draws and plays, and what a primary copies from a
#   backup.
def recorder() -> None:
    from .recworker import RecWorker
    # The platform's grant for a worker of `rec` — epochs, its slot AND its hold. The list here was written by
    # hand before a recorder took volumes, and was never given `rec/holds/*`: on a box with a declared volume
    # this process was refused its own place, by its own token (found with feedback BR).
    from .config import REC_SPEC
    vars_ = open_vars(STORE_URL, writer="recworker", acl={"recworker": REC_SPEC.sub.acl_worker()})
    objects = FsObjectStore(os.path.join(root, "objects"))
    try:
        from gstvms.actuator import GstRecActuator
        act = GstRecActuator()
    except ImportError:
        logging.warning("no GStreamer: the fake actuator records nothing")
        act = FakeActuator()
    # Backfill (Lesson 16): `BACKFILL_WINDOW=22-6` in LOCAL time — night where the camera is, not where the
    # server is — and `BACKFILL_BUDGET` ranges per pass. Unset window: any hour. Budget 0: only what an
    # operator asks for.
    win = os.environ.get("BACKFILL_WINDOW", "")
    window = tuple(int(x) for x in win.split("-")) if "-" in win else None
    # Its events into the platform's archive, its own volume where the VMS keeps volumes (`config.OWN_VOLUME`) — said
    # here, not left to the recorder's fallback beside the events tree, which is the platform's directory now.
    from .config import OWN_VOLUME
    env = {**os.environ, "ARCHIVE_VOLUME": os.environ.get("ARCHIVE_VOLUME") or OWN_VOLUME}
    r = RecWorker(None, vars_, objects, act, capacity=int(os.environ.get("CAPACITY", "50")), env=env,
                  archive_root=runtime.events_root(os.environ),
                  window=window, keep_days=float(os.environ.get("RETENTION_DAYS", "30")))
    r.backfill_budget = int(os.environ.get("BACKFILL_BUDGET", "1"))
    srv = r.serve_archive(os.environ.get("ARCHIVE_HOST", "127.0.0.1"), int(os.environ.get("ARCHIVE_PORT", "0")))
    logging.info("recorder %s (instance %s) claimed its slot; archive door %s", r.name, r.instance, r.archive_url)
    try:
        # No beat between its passes: what a recorder serves from `rec/requests` is a backfill — minutes off a card,
        # on its backfill thread — and a quarter of a second saved on that is nothing. A scenario's `record` is not
        # its to serve at all: the console turns it into a recording (`_requests_loop`).
        _present(r)
        r.run(stop=stop)
    finally:
        srv.shutdown()


# A worker registers with its server's resource before it runs (`Worker.present`): a lock in the resource's tree for as
# long as the process lives. A silent worker whose process the resource names running is HUNG, and keeps its units for
# `HUNG_MOVE_AFTER`; one that is not running is dead, and its units move (`Controller.slot_fate`; the owner, 3 Oct).
def _present(w) -> None:
    w.present(runtime.events_root(os.environ))


# Builds `vmscontroller` and runs the platform's placement loop over it (`host.controller_loop`), every 5 s — the VMS's
# own controller because a device is one group (`VmsController.group_value`: the hook the boundary's step 6 turns into
# a declaration); every other subsystem's controller is the platform's, from its spec (`python3 -m w2cplatform`):
# - Variables as writer `vmscontroller` with `SPEC.acl_controller()` — `vms/workers/*`, `vms/placement/*`,
#   `vms/slots/*`; never a camera's row (see `w2cplatform/spec.py`).
# - `VmsController(vars_, objects, capacity=$CAPACITY)`.
# - Each pass: `ensure_placed()` (deleted rows unplaced first, then every unplaced camera onto the workers
#   it currently sees by their heartbeats), `redistribute()` (only the cameras of a *released* slot —
#   scale-in — move; a merely silent slot is a crash and is left for the scheduler), `publish_snapshot()`
#   (one object per worker under `vms/snapshot/` in the object store) — each in a try of its own, said once a
#   spell (`host.step`). No port, no state: the process can be restarted at any moment, and two of them agree by CAS.
def controller() -> None:
    from .config import SPEC
    vars_ = open_vars(STORE_URL, writer="vmscontroller", acl={"vmscontroller": SPEC.acl_controller()})
    objects = FsObjectStore(os.path.join(root, "objects"))
    host.controller_loop(VmsController(vars_, objects, capacity=int(os.environ.get("CAPACITY", "50"))))


def detworker() -> None:
    """A detector worker: a worker of the `det` subsystem. Its token writes its slot, its epochs and its
    heartbeat; its events go into det/<unit>/e<epoch>/ on this server's resource."""
    from .detworker import DetWorker
    vars_ = open_vars(STORE_URL, writer="detworker", acl={"detworker": ["det/epoch/*", "det/slots/*"]})
    d = DetWorker(None, vars_, FsObjectStore(os.path.join(root, "objects")), capacity=int(os.environ.get("CAPACITY", "8")),
                  archive_root=runtime.events_root(os.environ))
    logging.info("detector %s (instance %s) claimed its slot; models: %s", d.name, d.instance, ",".join(d.models))
    _present(d)
    d.run(stop=stop)


def autoworker() -> None:
    """A scenario evaluator. Its token is the only one in the course that reaches across a subsystem's
    name — `requests_acl("vms", "rec", "det")` — and it reaches exactly one family: bounded work, addressed
    to a unit or turned into one by the console. It cannot write a camera, a recording, a detector or a placement."""
    from w2cplatform.contract import requests_acl
    from .autoworker import AutoWorker
    from .config import AUTO_SPEC
    acl = AUTO_SPEC.sub.acl_worker() + requests_acl("vms", "rec", "det")
    vars_ = open_vars(STORE_URL, writer="autoworker", acl={"autoworker": acl})
    a = AutoWorker(None, vars_, FsObjectStore(os.path.join(root, "objects")),
                   capacity=int(os.environ.get("CAPACITY", "50")),
                   archive_root=runtime.events_root(os.environ))
    logging.info("evaluator %s (instance %s) claimed its slot; may file: %s", a.name, a.instance, ",".join(acl[-3:]))
    # The long poll (`w2cplatform/longpoll.py`): a request held at every resource it asks, answered when an event
    # one of its scenarios watches is written there — the pass begins then, not at the end of its two seconds.
    # `LONG_POLL=0`: nothing is held.
    a.watch_events()
    _present(a)
    a.run(stop=stop)


def detjobworker() -> None:
    """A scan worker: a worker of the `detjob` subsystem. Same box, same models and same GPU as
    `detworker`, a separate process because it carries a separate budget — a retro-search must not be able
    to spend the streams live detection is running on. Its events go into detjob/<job>/e<epoch>/ on this
    server's resource; its progress goes beside them, because its token may not write the row."""
    from .detjobworker import DetJobWorker
    vars_ = open_vars(STORE_URL, writer="detjobworker", acl={"detjobworker": ["detjob/epoch/*", "detjob/slots/*"]})
    j = DetJobWorker(None, vars_, FsObjectStore(os.path.join(root, "objects")),
                     capacity=int(os.environ.get("SCAN_CAPACITY", "2")),
                     archive_root=runtime.events_root(os.environ))
    logging.info("scan worker %s (instance %s) claimed its slot; models: %s", j.name, j.instance, ",".join(j.models))
    _present(j)
    j.run(stop=stop)


def surveyworker() -> None:
    """A survey worker: a worker of the `survey` subsystem. It watches a camera's DEVICE archive — a card,
    an NVR — and copies none of it: what comes out is events. Its budget is its own (`SURVEY_CAPACITY`),
    because a survey must never be able to spend what live detection is running on, and its real limit is
    usually the two playback sessions the device allows rather than the GPU."""
    from .surveyworker import SurveyWorker
    vars_ = open_vars(STORE_URL, writer="surveyworker", acl={"surveyworker": ["survey/epoch/*", "survey/slots/*"]})
    s = SurveyWorker(None, vars_, FsObjectStore(os.path.join(root, "objects")),
                     capacity=int(os.environ.get("SURVEY_CAPACITY", "2")),
                     archive_root=runtime.events_root(os.environ))
    logging.info("survey %s (instance %s) claimed its slot; models: %s", s.name, s.instance, ",".join(s.models))
    _present(s)
    s.run(stop=stop)


def gateway() -> None:
    """A live gateway: a worker of the `live` subsystem. Its token writes its slot and epochs, its heartbeat,
    and `live/streams/*` — so it can delete the fan-out it holds once nobody has watched it for `grace`."""
    from w2cplatform.spec import SpecController
    from .config import LIVE_SPEC
    from .liveworker import LiveWorker
    vars_ = open_vars(STORE_URL, writer="liveworker",
                          acl={"liveworker": ["live/epoch/*", "live/slots/*", "live/streams/*"]})
    objects = FsObjectStore(os.path.join(root, "objects"))
    from .config import port_of
    # `auto` is what lets a second gateway run on this box: it publishes the address it bound (`serve`
    # reads it back into `self.url`), and every viewer reaches it through that, never through a number.
    host, port = os.environ.get("GATEWAY_HOST", "127.0.0.1"), port_of(os.environ.get("GATEWAY_PORT"), 8082)
    peer = None
    try:
        from gstvms.webrtc import GstPeer
        peer = GstPeer
    except ImportError:
        logging.warning("no GStreamer webrtcbin: the fake peer answers SDP and carries no media")
    gw = LiveWorker(None, vars_, objects, ctl=SpecController(LIVE_SPEC, vars_, objects), url=os.environ.get("GATEWAY_URL", f"http://{host}:{port}"),
                     capacity=int(os.environ.get("CAPACITY", "100")), peer_factory=peer,
                     archive_root=runtime.events_root(os.environ))
    srv = gw.serve(host, port)
    logging.info("gateway %s (instance %s) on %s", gw.name, gw.instance, srv.server_address)
    _present(gw)
    gw.run(stop=stop)
    srv.shutdown()


# The screen and the API, as its own process ("count as many as you like"):
# - Variables as writer `console` with `SPEC.acl_console()` — `vms/cameras/*`, `vms/next_id`,
#   `vms/idem/*`, `vms/retention/*`; never placement. It holds a `VmsController` over that token, so a write
#   it must not make (`place`) is a `Forbidden` from the store, not a rule in the console.
# - `$ARCHIVE` for the operator marks it writes into its own bucket. Footage it does not hold: `/timeline/<cam>`
#   and `/export/<cam>` ask the recorders' archive doors, found by their heartbeats.
# - `serve(ctl, archive, $CONSOLE_HOST, $CONSOLE_PORT)` from `vms/console.py` starts the
#   `ThreadingHTTPServer` in a daemon thread; the main thread waits on `stop`, then `srv.shutdown()`.
# Housekeeping the console owns BECAUSE THE ACL SAYS SO. `<sub>/blobs/*` is the console's to write
# (Lesson 27), so it is the console's to collect: the platform's sweep (`host.sweep_loop`), in a loop and a log
# line of its own (Lesson 28) — a sweep that fails inside somebody else's `try` would be reported as somebody else's
# failure, and blobs accumulating with nothing reclaiming them shows up as a disk full a year later.
# The console's second pass, beside the sweep: a job's row follows the worker that finished it. The worker
# cannot write the row (its ACL forbids configuration) and the controller must not (one row, one writer),
# so the console — which already reads these heartbeats — is where the fact lands. See `vms/jobs.py`.
def _reap_loop(controllers, requests=(), rec_ctl=None, det_ctl=None, survey_ctl=None, every: float = 30.0) -> None:
    host.every(lambda: _reap_turn(controllers, requests, rec_ctl, det_ctl, survey_ctl), every)


# One turn of it, in ONE pass of reads (`contract.one_pass`; the scaling pass after the eighth review): `scan_what_arrived`
# read every detector again for every span a recorder closed, `keep_what_fired` every recording for every hit, and
# `reap` and `forget_finished` each every job — some 55 000 reads a turn at a thousand of each. Each key is read once a
# turn now; what a step writes, the next reads back from the store.
def _reap_turn(controllers, requests=(), rec_ctl=None, det_ctl=None, survey_ctl=None, now=None) -> None:
    import time
    from w2cplatform.contract import one_pass
    from .jobs import ask_for_footage, clear_requests, forget_finished, keep_what_fired, reap, scan_what_arrived
    every_ctl = [c for c in (*controllers, *requests, rec_ctl, det_ctl, survey_ctl) if c is not None]
    with one_pass(*every_ctl):
        for c in controllers:
            try:
                moved = reap(c)
                if moved["done"] or moved["failed"]:
                    logging.info("%s: %d done, %d failed", c.spec.name, moved["done"], moved["failed"])
            except Exception:                         # noqa: BLE001
                logging.exception("the job reaper failed in %s — finished jobs will stay open", c.spec.name)
            try:
                gone = forget_finished(c, time.time() if now is None else now)    # finished for days: the row goes, the events stay
                if gone:
                    logging.info("%s: %d finished job(s) forgotten", c.spec.name, gone)
            except Exception:                         # noqa: BLE001
                logging.exception("forgetting finished jobs failed in %s — the list of scans keeps growing", c.spec.name)
        for c in controllers if rec_ctl is not None else ():
            try:
                asked = ask_for_footage(c, rec_ctl)       # a job stuck on footage the DEVICE has: ask the recorder
                if asked:
                    logging.info("%s: asked the recorder for %d range(s)", c.spec.name, asked)
            except Exception:                             # noqa: BLE001
                logging.exception("asking for footage failed in %s — those jobs will wait", c.spec.name)
        for c in controllers if rec_ctl is not None and det_ctl is not None else ():
            try:
                made = scan_what_arrived(rec_ctl, det_ctl, c)   # footage that arrived from a device is a hole in the detections
                if made:
                    logging.info("%s: %d scan(s) queued over footage that just arrived", c.spec.name, made)
            except Exception:                             # noqa: BLE001
                logging.exception("queueing scans over new footage failed in %s — the detections keep the hole", c.spec.name)
        if survey_ctl is not None and rec_ctl is not None:
            try:
                kept = keep_what_fired(survey_ctl, rec_ctl)   # watch everything, copy what a model liked
                if kept:
                    logging.info("%s: asked the recorder to keep %d stretch(es)", survey_ctl.spec.name, kept)
            except Exception:                         # noqa: BLE001
                logging.exception("keeping what fired failed in %s — those minutes stay on the device", survey_ctl.spec.name)
        for c in requests:                            # the same division, one row simpler: fetched, so gone
            try:
                gone = clear_requests(c)              # …and the day-old backfills; the answered ones go in `_clear_loop` too
                if gone:
                    logging.info("%s: %d request(s) fetched and cleared", c.spec.name, gone)
            except Exception:                         # noqa: BLE001
                logging.exception("clearing requests failed in %s — they will be asked for again", c.spec.name)


# The answered requests, cleared in a short cycle of their own (the review's seventh pass, M6): every `CLEAR_EVERY`, the
# rows the workers' heartbeats say they answered — no row is read for it (`clear_requests(sweep=False)`). On the reaper's
# thirty seconds they piled up behind a holder that answers up to sixteen a second, and a holder started again found
# them standing. Apart from `_requests_loop` because that one is automation's way in, and a failure here is not its.
def _clear_loop(requests, every: float | None = None) -> None:
    from .jobs import CLEAR_EVERY
    host.every(lambda: _clear_turn(requests), CLEAR_EVERY if every is None else every)


def _clear_turn(requests) -> None:
    from .jobs import clear_requests
    for c in requests:
        try:
            gone = clear_requests(c, sweep=False)
            if gone:
                logging.debug("%s: %d answered request(s) cleared", c.spec.name, gone)
        except Exception:                             # noqa: BLE001
            logging.exception("clearing answered requests failed in %s — the reaper's pass clears them", c.spec.name)


# The console's third loop: what AUTOMATION asked for, turned into rows — and a short loop, apart from the
# reaper's (the review's second pass). A scenario's request is valid for thirty seconds (`autoworker.py`,
# `valid_for`), and these four calls used to run at the end of the thirty-second loop above: about one firing
# in six reached them after its `valid_until` and was dropped with a warning nobody reads, while the scenario
# had already written `fired`. Two seconds is the evaluator's own pass, so neither side waits on the other;
# what it costs is a listing of two request families and a pass over the rows with an `until`. The drops that
# still happen are on `/metrics` (`jobs.expired`, `vms_requests_expired_total`).
#
# Turning a request into a recording or a detector is a write to CONFIGURATION, and of the three processes only
# this one holds the token for it — a worker writes none, and the controller writes placement. Both ends of
# each family here: the row that starts, and the row whose `until` has passed.
def _requests_loop(rec_ctl=None, det_ctl=None, job_ctl=None, every: float = 2.0) -> None:
    from .jobs import Remembered
    mem = Remembered()
    host.every(lambda: _requests_turn(rec_ctl, det_ctl, job_ctl, mem), every)


# One turn of it: each key read once in it (`contract.one_pass`) — `detect_on_request` read every detector, every
# recording and every job again for each request — and, between turns, only what saves a read (`jobs.Remembered`: the
# backfills seen, the pauses after a store that failed a request, the ends to come). Some 3 000 reads a turn at a
# thousand recordings, detectors and backfills, 33 000 with ten scenarios firing; a few dozen now
# (`tests/test_read_budget.py`).
def _requests_turn(rec_ctl=None, det_ctl=None, job_ctl=None, mem=None, now=None) -> None:
    import time
    from w2cplatform.contract import one_pass
    from .jobs import detect_on_request, expire, expire_recordings, record_on_request
    clock = (lambda: now) if now is not None else time.time
    with one_pass(*[c for c in (rec_ctl, det_ctl, job_ctl) if c is not None]):
        # Each end in a try of its own (the review's seventh pass, M2): the requests and the expiry shared one, so a
        # request the first could not turn into work kept the second from ending anything — a recording asked for
        # ten minutes went on for as long as the request stood.
        if rec_ctl is not None:
            try:
                started = record_on_request(rec_ctl, clock(), mem)
                if started:
                    logging.info("%s: %d recording(s) started on request", rec_ctl.spec.name, started)
            except Exception:                         # noqa: BLE001
                logging.exception("recordings on request failed — a scenario's minutes may not have started")
            try:
                ended = expire_recordings(rec_ctl, clock(), mem)
                if ended:
                    logging.info("%s: %d recording(s) on request ended", rec_ctl.spec.name, ended)
            except Exception:                         # noqa: BLE001
                logging.exception("ending timed recordings failed — a finished one may still be recording")
        if det_ctl is not None and rec_ctl is not None and job_ctl is not None:
            # The detectors' family, the same two ends: a request becomes a detector with an end, or a scan
            # job of `job_ctl`; a detector whose `until` passed is deleted.
            try:
                made = detect_on_request(det_ctl, job_ctl, rec_ctl, clock(), mem)
                if made:
                    logging.info("%s: %d asked for by scenarios", det_ctl.spec.name, made)
            except Exception:                         # noqa: BLE001
                logging.exception("detector requests failed — a scenario's detection may not have started")
            try:
                ended = expire(det_ctl, clock(), mem)
                if ended:
                    logging.info("%s: %d detector(s) on request ended", det_ctl.spec.name, ended)
            except Exception:                         # noqa: BLE001
                logging.exception("ending timed detectors failed — a finished one may still be running")


def console() -> None:
    """The screen and the API: its own process, count as many as you like, a
    token for the operator's rows and nothing else."""
    from .config import SPEC
    from .console import serve
    from w2cplatform.spec import SpecController
    from .auto import AutoController
    from .config import AUTO_SPEC, DET_SPEC, DETJOB_SPEC, LIVE_SPEC, REC_SPEC, SURVEY_SPEC
    from .jobs import DetJobController
    vars_ = open_vars(STORE_URL, writer="console",
                          acl={"console": SPEC.acl_console() + LIVE_SPEC.acl_console() + DET_SPEC.acl_console()
                               + REC_SPEC.acl_console() + DETJOB_SPEC.acl_console()
                               + SURVEY_SPEC.acl_console() + AUTO_SPEC.acl_console()})   # the operator's rows of EVERY subsystem it fronts
    objects = FsObjectStore(os.path.join(root, "objects"))
    ctl = VmsController(vars_, objects, capacity=int(os.environ.get("CAPACITY", "50")))
    archive = runtime.events_root(os.environ)                    # its resource tree: where the operator's marks go
    srv = serve(ctl, archive, os.environ.get("CONSOLE_HOST", "127.0.0.1"), int(os.environ.get("CONSOLE_PORT", "8080")),
                live_ctl=SpecController(LIVE_SPEC, vars_, objects),
                mounts={"det": SpecController(DET_SPEC, vars_, objects), "rec": SpecController(REC_SPEC, vars_, objects),
                        "detjob": DetJobController(vars_, objects),     # a scan's recording is its camera's (`jobs.refuse_job`)
                        "survey": SpecController(SURVEY_SPEC, vars_, objects),
                        # `AutoController` and not the platform's class: a scenario is refused where it is
                        # written, which is here, and the refusal has to be the subsystem's own words.
                        "auto": AutoController(vars_, objects)})
    logging.info("console on %s", srv.server_address)                     # no event index here: /events asks the resource process
    # Rows written before this console had a key: sealed now, not at their next write — a camera nobody edits is
    # never written again (feedback CD). Every subsystem's rows this console writes, and the declared volumes.
    from w2cplatform.sealing import Sealer, seal_stored
    seal_stored(Sealer.from_env(), vars_, [s.sub.config(s.rows, "") for s in
                                           (SPEC, LIVE_SPEC, DET_SPEC, REC_SPEC, DETJOB_SPEC, SURVEY_SPEC, AUTO_SPEC)]
                + ["rec/volumes/"])
    det_ctl, rec_ctl = SpecController(DET_SPEC, vars_, objects), SpecController(REC_SPEC, vars_, objects)
    job_ctl = SpecController(DETJOB_SPEC, vars_, objects)
    survey_ctl = SpecController(SURVEY_SPEC, vars_, objects)
    threading.Thread(target=host.sweep_loop, args=([ctl, det_ctl, rec_ctl, job_ctl, survey_ctl],), daemon=True).start()
    # `[rec_ctl, ctl]`: two families of requests to clear now — footage a person asked for, and commands
    # somebody sent a device (a relay, a preset). Same division as everywhere: the worker performs and
    # says so in its heartbeat, the controller removes the row, because a worker writes no configuration.
    threading.Thread(target=_reap_loop, args=([job_ctl], [rec_ctl, ctl], rec_ctl, det_ctl, survey_ctl), daemon=True).start()
    threading.Thread(target=_clear_loop, args=([rec_ctl, ctl],), daemon=True).start()   # answered requests: every 2 s
    threading.Thread(target=_requests_loop, args=(rec_ctl, det_ctl, job_ctl), daemon=True).start()   # a request lives 30 s: looked at every 2
    stop.wait()
    srv.shutdown()


# The resource process — the platform's resource job on one box, the same as М11's `resource` job:
# - its tree, `$ARCHIVE`: EVENTS — the camera's buckets, a recorder's, the alarms', the journal's. Footage is
#   not here: it is in volumes of ObjectStorage, through the host's `obsd`, each written by the recorder that
#   holds it (`vms/archive.py`). Variables opened with *no* writer and no ACL — the resource only reads rows.
# - `vms_resource(root, hostname, $RESOURCE_URL, vars_, objects)` — the platform's `Resource` with an
#   `EventIndex` over the tree and the VMS's keeps for its bucket retention.
# - `serve(res, $RESOURCE_HOST, $RESOURCE_PORT)` — `/buckets`, `/events`, `/mirrored`, `PUT /mirror`.
# - one heartbeat (`platform/resources/<server>/heartbeat` — how the console finds this process), then
#   `restore()` — and the loop: a heartbeat every 10 s, the policy pass every 600 s (retain buckets by each
#   subsystem's row, the watermark over the tree, the mirror).
def resource() -> None:
    """The resource process: no controller — a policy pass, a heartbeat, its HTTP,
    and the event index over its own tree."""
    import socket
    from w2cplatform.resource import serve
    from .resource import vms_resource
    vars_ = open_vars(STORE_URL)
    objects = FsObjectStore(os.path.join(root, "objects"))
    bind, port = os.environ.get("RESOURCE_HOST", "127.0.0.1"), int(os.environ.get("RESOURCE_PORT", "8090"))
    res = vms_resource(runtime.events_root(os.environ), socket.gethostname(),
                       os.environ.get("RESOURCE_URL", f"http://{bind}:{port}"), vars_, objects)
    host.run_resource(res, serve(res, bind, port))     # the platform's loop: heartbeat, beat, restore, policy pass


if __name__ == "__main__":
    # Only when run: a module imported (the tests) must not take the process's signals. Installed at import, the
    # handler swallowed a SIGTERM or SIGINT sent to the test run itself: the run went on with `stop` set, and the first
    # test to drive the controller's loop ran no pass and failed, alone (the review's fifth pass saw that once). Which
    # signal reached that run is not known — no test of the suite sends one to the runner (the sixth pass:
    # `tests/test_pass_failures.py` has the evidence, `tests/run.py` the guard).
    for s in (signal.SIGTERM, signal.SIGINT):
        signal.signal(s, lambda *_: stop.set())
    {"worker": worker, "recorder": recorder, "gateway": gateway, "detworker": detworker, "detjobworker": detjobworker,
     "surveyworker": surveyworker, "autoworker": autoworker,
     "controller": controller, "console": console, "resource": resource}[sys.argv[1]]()
