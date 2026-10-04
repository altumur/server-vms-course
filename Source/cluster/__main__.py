"""python3 -m cluster worker | controller | recorder | reccontroller | console | resource | rights — the processes of
a server, each started by its own unit (`deploy/cluster/systemd/`, `deploy/cluster/launchd/`); each resource keeps the event index
over its own tree; the recorder is the only writer of footage, through the host's obsd (`vms-obsd.service`, which
is not a Python process). `rights` prints the configstore's rights file generated from the spec (`cluster/rights.py`).

The loops are the platform's (`w2cplatform/host.py`, the boundary's step 5): `host.controller_loop` for both
controllers, `host.step` for a console's turns, `host.run_resource` for the resource — what the box runs, over this
cluster's stores (the configstore by the role's socket, the objects `cluster://`). The recordings' controller is the
platform's from the spec alone (`SPEC_DIR`, which `w2c-run.sh` sets to the installed tree's specs).

    PLATFORM_STORE                     the store, as a URL: this server's configstore daemon by the role's own socket,
                                       `configstore:///run/configstore/<role>.sock` (the default, by the verb's role);
                                       `file:///path` on a bench
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
    REACH_BUDGET                       controller: units one pass moves to a server that reaches them (`ensure_reach`,
                                       10); a group left for the next pass is the alarm `units.over_budget`
"""
from __future__ import annotations

import logging
import os
import signal
import sys
import threading
import time
from urllib.parse import urlsplit

from w2cplatform import catalog, host, runtime
from w2cplatform.host import stop
from w2cplatform.variables import open_vars, store_url

from cluster.objectstore import open_store

# Each verb is one role of the configstore's rights file: the socket its unit's group opens, and what it may do there.
ROLES = {"worker": "vmsworker", "recorder": "recworker", "controller": "vmscontroller", "reccontroller": "reccontroller",
         "console": "console", "resource": "resource"}
OBJECTS = "cluster:///data/platform/objects?resource=http://127.0.0.1:8090"

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(name)s %(levelname)s %(message)s")
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
# (`tests/cluster/conftest.py`), so what the stand runs is what a unit runs.
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
    footage, where the resource answers, one recorder per server by default (rec/policy). The platform's controller
    from the spec the catalogue holds, in the platform's loop."""
    from w2cplatform.spec import SpecController
    ctl = SpecController(catalog.spec("rec"), *stores("reccontroller"), capacity=int(os.environ.get("CAPACITY", "50")))
    host.controller_loop(ctl, journal=False)       # its unit writes nothing of the events tree: the log, as before


def controller() -> None:
    """the only writer of placement — a unit on every server, safe at two (every write a CAS, lesson 10). No HTTP:
    nothing asks it anything."""
    from cluster.controller import ClusterController
    ctl = ClusterController(*stores("vmscontroller"), capacity=int(os.environ.get("CAPACITY", "50")),
                            cluster=os.environ.get("CLUSTER") or CLUSTER)
    host.controller_loop(ctl, journal=False)      # each step in a try of its own, said once a spell (`host.step`)


def console() -> None:
    """one per server: the page and the API. Its socket writes the
    operator's rows and nothing else; a create is placed by the controller's next
    pass. No event index of its own: /events asks the live resources and merges."""
    from cluster.console import serve
    from cluster.controller import ClusterController
    from w2cplatform.spec import SpecController
    vars_, objects = stores("console")
    ctl = ClusterController(vars_, objects, capacity=int(os.environ.get("CAPACITY", "50")),
                            cluster=os.environ.get("CLUSTER") or CLUSTER)
    rec_ctl = SpecController(catalog.spec("rec"), vars_, objects)
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
    host.step(ctl, "console", "requests", lambda: _requests_turn(rec_ctl, None, None, mem, now=now))
    for c in (rec_ctl, ctl):
        host.step(ctl, "console", f"clearing {c.spec.name}'s requests", lambda c=c: clear_requests(c, sweep=False))
    if reap:
        host.step(ctl, "console reaper", "reap", lambda: _reap_turn([], [rec_ctl, ctl], rec_ctl, now=now))


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
    host.run_resource(res, serve(res, "0.0.0.0", int(os.environ.get("RESOURCE_PORT", "8090"))))   # the platform's loop


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
