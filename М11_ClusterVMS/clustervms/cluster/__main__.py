"""python3 -m cluster worker | controller | recorder | reccontroller | console | resource | rights — the processes of
a server, each started by its own unit (`deploy/systemd/`, `deploy/launchd/`); each resource keeps the event index
over its own tree; the recorder is the only writer of footage, through the host's obsd (`vms-obsd.service`, which
is not a Python process). `rights` prints the configstore's rights file generated from the spec (`cluster/rights.py`).

    PLATFORM_STORE                     the store, as a URL: this server's configstore daemon by the role's own socket,
                                       `configstore:///run/configstore/<role>.sock` (the default, by the verb's role);
                                       `CONFIG_URL` is the older name (product P7); `file:///path` on a bench
    OBJECTS                            the object store: `cluster:///data/platform/objects?resource=http://127.0.0.1:8090`
                                       (the default) — this server's objects as files, every server's through the
                                       resource on this one, the create-only keys as rows in the process's own store;
                                       `s3+http://…` on a rented cluster (М12 Lesson 8); `file:///path` on a bench
    WORKER_NAME                        worker, recorder: the name to claim, from the unit (`w-%l-1`, `r-%l-1`: one per
                                       server and role, product P4); `SLOT_INDEX` the older way (`w-<i>`)
    SPARE_FOR                          worker, recorder: a SPARE for this label set, started by `w2c-spares.sh` — it takes
                                       only an offer of the set (`Worker.claim_slot(spare_for=)`), else waits holding nothing
    SERVER_NAME, LABELS                the server, what it can reach (`/etc/w2c/w2c.env`) — neutral names
                                       (`w2cplatform/runtime.py`); a unit or an orchestrator fills them alike
    ARCHIVE                            the platform's events archive on this server (`/etc/w2c/w2c.env`; unset:
                                       `<PLATFORM_DIR>/events`, `runtime.events_root`): the resource's tree, where the
                                       worker and the recorder write their events and register (`Worker.present`)
    ARCHIVE_VOLUME                     recorder: its own volume when nothing is declared (`vms.config.OWN_VOLUME`,
                                       `/data/vms/obsd/volume`: the VMS's, not beside the platform's events)
    OBSD_SOCKET                        recorder: the host's ObjectStorage daemon (its default: where the obsd unit listens)
    ARCHIVE_URL                        recorder: what its heartbeat says the door is — the server's IP, so the console and
                                       a primary backfilling from a backup reach it with no DNS between servers
    ARCHIVE_HOST, ARCHIVE_PORT         recorder: what its archive door binds. The host defaults to the address
                                       ARCHIVE_URL names, else loopback — never every interface: the door has no
                                       authentication, so it opens exactly where the unit said it is reachable
    RESOURCE_URL                       resource: how the console and the other resources reach this server's
    CAPACITY                           worker: cameras it can carry on this server
    COMMANDS_BEAT                      worker: how often it looks at its request rows between passes, seconds (0.25);
                                       0 — only on the pass. Each look is one list of `vms/requests/` in the store
"""
from __future__ import annotations

import logging
import os
import signal
import sys
import threading
import time
from urllib.parse import urlsplit

import cluster  # noqa: F401  — puts М10's vmsserver on sys.path
from w2cplatform import runtime
from w2cplatform.variables import open_vars, store_url

from cluster.objectstore import open_store

# Each verb is one role of the configstore's rights file: the socket its unit's group opens, and what it may do there.
ROLES = {"worker": "vmsworker", "recorder": "recworker", "controller": "vmscontroller", "reccontroller": "reccontroller",
         "console": "console", "resource": "resource"}
OBJECTS = "cluster:///data/platform/objects?resource=http://127.0.0.1:8090"

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(name)s %(levelname)s %(message)s")
stop = threading.Event()
# The platform's events archive on this server — the resource's tree, `/data/platform/events` (WP-E, the box's layout) —
# by the platform's own reader of it, as the box's entry point reads it (`vms/__main__.py`).
archive = runtime.events_root(os.environ)
# The snapshot's cluster name when `/etc/vms/vms.env` says none: the module's cluster, `room-a` — the name its env
# example, its Nomad appendix and М12 give it. It was `cluster-a` here and `room-a` there (the twelfth review's
# «Вопросы»); a server that says nothing now names the cluster as the others do.
CLUSTER = "room-a"


# The process's two stores, opened when it runs and never at import (a test imports this module): the store by its
# role's socket, and the objects — whose create-only keys are rows in THAT store, through the same socket and its
# rights, not a second handle opened from the environment.
def stores(role: str, env=None):
    env = os.environ if env is None else env
    vars_ = open_vars(store_url(env, f"configstore:///run/configstore/{role}.sock"))
    return vars_, open_store(env.get("OBJECTS") or OBJECTS, vars_=vars_)


# A process that holds a slot REGISTERS with its server's resource before it runs (`Worker.present`), as the box's entry
# point does (`vms/__main__._present`): a lock in the resource's tree for as long as the process lives, its name beside
# it. The cluster's entry points did not (the twelfth review's «Вопросы», defect 1): the resource's heartbeat said
# `workers` and `running` empty on every server, so a worker whose process died on a live server was judged `wait` —
# "cannot be told" — for ever, its cameras written by nobody if systemd did not bring it back, and a slot the server no
# longer runs was never released. Built and registered here, and the stand builds its processes through these two
# (`tests/conftest.py`), so what the stand runs is what a unit runs.
def make_worker(vars_, objects, actuator=None, env: dict | None = None, **kw):
    from cluster.worker import ClusterWorker
    w = ClusterWorker(vars_, objects, actuator, env=env, **kw)
    w.present(w.archive_root)                  # its server's resource tree: where its events go too
    return w


def make_recorder(vars_, objects, actuator=None, env: dict | None = None, **kw):
    from cluster.recworker import ClusterRecorder
    r = ClusterRecorder(vars_, objects, actuator, env=env, **kw)
    r.present(r.archive_root)
    return r


def worker() -> None:
    """holds the camera: one connection, one epoch, one fan-out (rtsp://<server>:8554/<cam>), its events into
    the resource on its server. No footage: recording is the recorder's."""
    try:
        from gstvms.actuator import GstActuator
        # Bound to loopback unless the unit opens it (`RTSP_HOST`, М10B Lesson 4) — and in a cluster the unit
        # does: a recorder on another server has to reach it. There is no authentication at this door; what
        # the unit opens, the cluster's network has to keep closed. Its port is the unit's too (`RTSP_PORT`, `auto`
        # for "ask the OS": a spare beside the server's own worker, `vms-vmsworker-spare@.service`), and what the OS
        # gave is what the heartbeat announces (`live_url`), as on a box.
        from vms.config import RTSP_PORT, port_of
        act = GstActuator(rtsp_port=port_of(os.environ.get("RTSP_PORT"), RTSP_PORT),
                          rtsp_address=os.environ.get("RTSP_HOST", "127.0.0.1"))
    except ImportError:
        logging.warning("no GStreamer: the fake actuator holds nothing"); act = None
    w = make_worker(*stores("vmsworker"), act)
    w.rtsp_host = os.environ.get("RTSP_HOST", "127.0.0.1")   # a door announces what it bound
    logging.info("worker %s on %s (instance %s) claimed its slot; labels %s", w.name, w.server, w.instance, w.labels)
    # `beat`: between two passes the worker looks at its request rows every quarter of a second (`COMMANDS_BEAT`;
    # 0 — only on the pass), as on a box (М10B Lesson 25). Here each look is a list of `vms/requests/` through this
    # server's configstore: a read through the log, answered by the leader — never a stale one.
    from vms.worker import commands_beat
    w.run(stop=stop, beat=commands_beat(os.environ))   # SIGTERM from systemd → release_slot(): a stop, not a crash


def recorder() -> None:
    """the only writer of footage: subscribes to the worker's fan-out and writes into the volume it holds, through
    the host's obsd; serves that volume at its archive door."""
    try:
        from gstvms.actuator import GstRecActuator
        act = GstRecActuator()
    except ImportError:
        logging.warning("no GStreamer: the fake actuator records nothing"); act = None
    # Its events into the platform's archive, its own volume where the VMS keeps volumes (`config.OWN_VOLUME`) — said
    # here, as the box's entry point says it, and not left to the recorder's fallback beside the events tree: that is
    # the platform's directory now (WP-E).
    from vms.config import OWN_VOLUME
    env = {**os.environ, "ARCHIVE_VOLUME": os.environ.get("ARCHIVE_VOLUME") or OWN_VOLUME}
    r = make_recorder(*stores("recworker"), act, env=env, archive_root=archive)
    # The door binds where the unit says it is reachable (`ARCHIVE_URL`), else loopback — `0.0.0.0` was the
    # default, and a door with no authentication on every interface is what the review's second pass found.
    announced = urlsplit(os.environ.get("ARCHIVE_URL", "")).hostname
    srv = r.serve_archive(os.environ.get("ARCHIVE_HOST") or announced or "127.0.0.1", int(os.environ.get("ARCHIVE_PORT", "8084")))
    # The unit says how to reach it — an address, no DNS between servers — and the door says on which port it got: a
    # spare recorder asks the OS for one (`ARCHIVE_PORT=0`, `vms-recworker-spare@.service`), and the server's
    # `ARCHIVE_URL` names its own recorder's 8084. Said as the env file says it only when that is the port it has.
    said = os.environ.get("ARCHIVE_URL")
    if said and urlsplit(said).port == srv.server_address[1]:
        r.archive_url = said
    logging.info("recorder %s on %s (instance %s) claimed its slot; labels %s; archive door %s",
                 r.name, r.server, r.instance, r.labels, r.archive_url)
    try:
        r.run(stop=stop)
    finally:
        srv.shutdown()


def reccontroller() -> None:
    """the only writer of rec placement — a unit on every server, safe at two: which recorder writes which camera's
    footage, where the resource answers, one recorder per server by default (rec/policy)."""
    from w2cplatform.spec import SpecController
    from vms.config import REC_SPEC
    ctl = SpecController(REC_SPEC, *stores("reccontroller"), capacity=int(os.environ.get("CAPACITY", "50")))
    while not stop.is_set():
        _placement_pass("rec placement", ctl)
        stop.wait(5)


# Each step of a controller's pass in a try of its own (the review's seventh pass, part 2): they shared one, so a step
# that raised — one row it could not read — skipped every step after it, the snapshot the layer above reads included.
# And said ONCE per spell (the eighth review's minor, closed in the ninth): the trace went into the log on every pass,
# every five seconds for as long as the step kept failing — a refused write did it for days. The trace the first time,
# "works again" when it does (`_failing`, by loop and step), as М12's `domain/steps.py` says it.
_failing: set[tuple[str, str]] = set()


def _steps(what: str, *steps) -> None:
    for i, step in enumerate(steps):
        name = getattr(step, "__name__", "")
        name = f"step {i + 1}" if name in ("", "<lambda>") else name
        try:
            step()
        except Exception:                         # noqa: BLE001
            if (what, name) not in _failing:
                _failing.add((what, name))
                logging.exception("%s: %s failed; the other steps of the pass go on, this one is tried on every pass "
                                  "and said again when it works", what, name)
        else:
            if (what, name) in _failing:
                _failing.discard((what, name))
                logging.warning("%s: %s works again", what, name)


# One pass of a placement controller, the same as the box's loop makes it (`vms/__main__._controller_loop`; the review's
# eighth pass, found by the coordinator): `pass_once` — place, move, bring ONE unit home, each step in a try of its own —
# and the report it writes (`<sub>/controller/pass`), which is where `/metrics` reads `<sub>_units_unplaced`,
# `<sub>_reconcile_pass_seconds`, the last pass and the last success. The cluster's loops called the three steps one by
# one and wrote no report: on a cluster those metrics said 0 and -1 for ever. Then the snapshot, in its own step — the
# recordings' too, as on a box (`rec_snapshot_age_seconds` was -1 here).
#
# Both in ONE pass of reads (`contract.one_pass`; the scaling pass after the eighth review): the snapshot asks every unit's
# row, placement and server, and the placement pass has just read them — a thousand cameras cost the two together some
# 64 000 reads of the store's leader every five seconds, 2 000-odd now (`vmsserver/tests/test_read_budget.py`).
def _placement_pass(what: str, ctl) -> None:
    with ctl.one_pass():
        _steps(what, lambda: ctl.pass_once(1), ctl.publish_snapshot)


def controller() -> None:
    """the only writer of placement — a unit on every server, safe at two (every write a CAS, lesson 10). No HTTP:
    nothing asks it anything."""
    from cluster.controller import ClusterController
    ctl = ClusterController(*stores("vmscontroller"), capacity=int(os.environ.get("CAPACITY", "50")),
                            cluster=os.environ.get("CLUSTER") or CLUSTER)
    while not stop.is_set():
        _placement_pass("placement", ctl)
        stop.wait(5)


def console() -> None:
    """one per server: the page and the API. Its socket writes the
    operator's rows and nothing else; a create is placed by the controller's next
    pass. No event index of its own: /events asks the live resources and merges."""
    from cluster.console import serve
    from cluster.controller import ClusterController
    from w2cplatform.spec import SpecController
    from vms.config import REC_SPEC
    vars_, objects = stores("console")
    ctl = ClusterController(vars_, objects, capacity=int(os.environ.get("CAPACITY", "50")),
                            cluster=os.environ.get("CLUSTER") or CLUSTER)
    rec_ctl = SpecController(REC_SPEC, vars_, objects)
    srv = serve(ctl, os.environ.get("CONSOLE_HOST", "0.0.0.0"), int(os.environ.get("CONSOLE_PORT", "8080")),
                archive_root=archive if os.path.isdir(archive) else None,     # marks go into this server's resource, if it has one
                rec_ctl=rec_ctl)                                               # the recorder at /rec/…: the page's Record toggle
    threading.Thread(target=_console_loop, args=(ctl, rec_ctl), daemon=True).start()
    stop.wait()
    srv.shutdown()


# THE CONSOLE'S LOOP — WHO KEEPS A REQUEST'S `until` IN М11 (the twelfth review, on the author's answer: "REREAD"). A box's
# console runs three loops beside its door (`vms/__main__.console`): what a request asked, turned into work, and a
# recording asked for some minutes ended at its `until` (`_requests_turn`); the requests a holder answered, cleared
# (`clear_requests`, every two seconds); the reaper's slower pass, which takes the day-old ones too. The cluster's console
# ran none of them: a recording on request went on past its end, and the answered requests stood. The same turns here,
# over this console's two subsystems, on every server's console — every write in them a CAS, so two consoles at once
# end a recording once. Each console keeps the `until` it wrote within a turn, and one another console wrote within
# `jobs.Remembered.REREAD` (thirty seconds) — sooner when its end is near.
def console_turn(ctl, rec_ctl, mem, now: float | None = None, reap: bool = False) -> None:
    from vms.__main__ import _reap_turn, _requests_turn
    from vms.jobs import clear_requests
    _steps("console", lambda: _requests_turn(rec_ctl, None, None, mem, now=now),
           *[(lambda c=c: clear_requests(c, sweep=False)) for c in (rec_ctl, ctl)])
    if reap:
        _steps("console reaper", lambda: _reap_turn([], [rec_ctl, ctl], rec_ctl, now=now))


def _console_loop(ctl, rec_ctl, every: float = 2.0, reap_every: float = 30.0) -> None:
    from vms.jobs import Remembered
    mem, reaped = Remembered(), -1e18
    while not stop.is_set():
        reap = time.monotonic() - reaped >= reap_every
        if reap:
            reaped = time.monotonic()
        console_turn(ctl, rec_ctl, mem, reap=reap)
        stop.wait(every)


def resource() -> None:
    """М10's resource process, the platform's unit on every server: the Resource with the VMS registered on it, the event
    index over its own tree, and the door to this server's objects (`/v1/objects`)."""
    from cluster.resource import cluster_resource
    from w2cplatform.resource import serve
    server = runtime.server(os.environ)
    url = os.environ.get("RESOURCE_URL", f"http://{server}:8090")
    res = cluster_resource(archive, server, url, *stores("resource"))
    srv = serve(res, "0.0.0.0", int(os.environ.get("RESOURCE_PORT", "8090")))
    try:                                          # a store away at the start does not end the process (the eighth review)
        res.heartbeat()
    except Exception:                             # noqa: BLE001
        logging.exception("resource heartbeat failed")
    res.start_beat(stop)                          # the beat on its own thread: a hung pass does not silence the server (13th)
    try:                                          # back with an empty disk? pull my buckets from my peers first — and a
        logging.info("restore: %s", res.restore())   # restore that raises does not end the process (the seventh review)
    except Exception:                             # noqa: BLE001
        logging.exception("restore failed — the buckets peers hold of this server stay with them; the process goes on")
    last_policy = 0.0
    while not stop.is_set():
        # Two tasks, two tries, as М10's resource loop has them (`vms/__main__.py`; the review's seventh pass, part 2):
        # they shared one here, so a heartbeat that raised skipped the pass, and a pass that raised was tried again
        # every ten seconds instead of every ten minutes.
        try:
            res.heartbeat()
        except Exception:                         # noqa: BLE001
            logging.exception("resource heartbeat failed")
        try:
            if time.time() - last_policy >= 600:
                last_policy = time.time()         # a pass that raised is tried in ten minutes, not in ten seconds
                logging.info("policy: %s", res.pass_())
        except Exception:                         # noqa: BLE001
            logging.exception("resource pass failed")
        try:                                      # what the restore left with peers, asked for again (the eighth review)
            if res.restore_due():
                logging.info("restore again: %s", res.restore())
        except Exception:                         # noqa: BLE001
            logging.exception("restore failed again; asked again later")
        stop.wait(10)
    srv.shutdown()


if __name__ == "__main__":
    # Only when run, as М10's entry point does (`vms/__main__.py`; the review's sixth pass): installed at import, the
    # handler takes the signals of whatever process imports this module — a test run — and a signal sent to stop
    # that run is swallowed.
    if sys.argv[1:2] == ["rights"]:
        from cluster.rights import main as rights
        sys.exit(rights(sys.argv[2:]))
    for s in (signal.SIGTERM, signal.SIGINT):
        signal.signal(s, lambda *_: stop.set())
    {"worker": worker, "controller": controller, "recorder": recorder, "reccontroller": reccontroller,
     "console": console, "resource": resource}[sys.argv[1]]()
