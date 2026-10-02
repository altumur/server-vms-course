"""python3 -m cluster worker | controller | recorder | reccontroller | console | resource — the jobs
(each resource keeps the event index over its own tree; the recorder is the only writer of footage, through
the host's obsd — the `obsd` system job, which is not a Python process).

    CONFIG_URL                         the store, as a URL: nomad://host:port here, k8s://ns/prefix at a k8s site,
                                       file:///path on a bench. Defaults from NOMAD_ADDR; NOMAD_TOKEN is the task's
                                       own workload identity and is read by the nomad backend alone
    OBJECTS=variables://objects        the object store — heartbeats and the snapshot — as Variables (the default);
                                       s3+http://… when a cluster is large enough to want MinIO; file:///path on a bench
    SLOT_INDEX, SERVER_NAME, LABELS    worker, recorder: the slot to claim (w-<i>, r-<i>), the server, what it can reach —
                                       neutral names (`w2cplatform/runtime.py`); the jobspec maps NOMAD_ALLOC_INDEX,
                                       node.unique.name and meta.labels into them, a k8s manifest the ordinal and a fieldRef
    ARCHIVE                            worker, recorder: where their events go (the resource on their server); the
                                       recorder's own volume goes beside it (`/data/volume`) when nothing is declared
    OBSD_SOCKET                        recorder: the host's ObjectStorage daemon (/run/obsd/obsd.sock, set by the job; also the default)
    ARCHIVE_URL                        recorder: what its heartbeat says the door is — the node's IP, so the console and
                                       a primary backfilling from a backup reach it with no DNS between servers
    ARCHIVE_HOST, ARCHIVE_PORT         recorder: what its archive door binds. The host defaults to the address
                                       ARCHIVE_URL names, else loopback — never every interface: the door has no
                                       authentication, so it opens exactly where the job said it is reachable
    RESOURCE_URL                       resource: how the console reaches this server's events
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
from w2cplatform.variables import open_vars

# The store seam. `nomad://` is registered by `cluster/variables.py`; the default keeps the
# cluster working with no new environment, and a k8s site changes this one variable.
CONFIG_URL = os.environ.get("CONFIG_URL") or "nomad://" + os.environ.get("NOMAD_ADDR", "127.0.0.1:4646").replace("http://", "")

from cluster.objectstore import open_store
from cluster.variables import NomadVariables

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(name)s %(levelname)s %(message)s")
stop = threading.Event()
for s in (signal.SIGTERM, signal.SIGINT):
    signal.signal(s, lambda *_: stop.set())
objects = open_store(os.environ.get("OBJECTS", "variables://objects"))
archive = os.environ.get("ARCHIVE", "/data/archive")


def worker() -> None:
    """holds the camera: one connection, one epoch, one fan-out (rtsp://<server>:8554/<cam>), its events into
    the resource on its server. No footage: recording is the recorder's."""
    from cluster.worker import ClusterWorker
    try:
        from gstvms.actuator import GstActuator
        # Bound to loopback unless the job opens it (`RTSP_HOST`, М10B Lesson 4) — and in a cluster the job
        # does: a recorder on another server has to reach it. There is no authentication at this door; what
        # the job opens, the cluster's network has to keep closed.
        act = GstActuator(rtsp_address=os.environ.get("RTSP_HOST", "127.0.0.1"))
    except ImportError:
        logging.warning("no GStreamer: the fake actuator holds nothing"); act = None
    w = ClusterWorker(open_vars(CONFIG_URL), objects, act)
    w.rtsp_host = os.environ.get("RTSP_HOST", "127.0.0.1")   # a door announces what it bound
    logging.info("worker %s on %s (alloc %s) claimed its slot; labels %s", w.name, w.server, w.alloc, w.labels)
    # `beat`: between two passes the worker looks at its request rows every quarter of a second (`COMMANDS_BEAT`;
    # 0 — only on the pass), as on a box (М10B Lesson 25). Here each look is a list of `vms/requests/` in Nomad's
    # Variables: an ordinary read, answered by the leader — not a blocking query, and not a stale one.
    from vms.worker import commands_beat
    w.run(stop=stop, beat=commands_beat(os.environ))   # SIGTERM from Nomad → release_slot(): scale-in, not a crash


def recorder() -> None:
    """the only writer of footage: subscribes to the worker's fan-out and writes into the volume it holds, through
    the host's obsd; serves that volume at its archive door."""
    from cluster.recworker import ClusterRecorder
    try:
        from gstvms.actuator import GstRecActuator
        act = GstRecActuator()
    except ImportError:
        logging.warning("no GStreamer: the fake actuator records nothing"); act = None
    r = ClusterRecorder(open_vars(CONFIG_URL), objects, act, archive_root=archive)
    # The door binds where the job says it is reachable (`ARCHIVE_URL`), else loopback — `0.0.0.0` was the
    # default, and a door with no authentication on every interface is what the review's second pass found.
    announced = urlsplit(os.environ.get("ARCHIVE_URL", "")).hostname
    srv = r.serve_archive(os.environ.get("ARCHIVE_HOST") or announced or "127.0.0.1", int(os.environ.get("ARCHIVE_PORT", "8084")))
    r.archive_url = os.environ.get("ARCHIVE_URL") or r.archive_url   # the job says how to reach it: an address, no DNS between servers
    logging.info("recorder %s on %s (alloc %s) claimed its slot; labels %s; archive door %s",
                 r.name, r.server, r.alloc, r.labels, r.archive_url)
    try:
        r.run(stop=stop)
    finally:
        srv.shutdown()


def reccontroller() -> None:
    """count = 1, the only writer of rec placement: which recorder writes which camera's footage, where the
    resource answers, one recorder per server by default (rec/policy)."""
    from w2cplatform.spec import SpecController
    from vms.config import REC_SPEC
    ctl = SpecController(REC_SPEC, open_vars(CONFIG_URL), objects, capacity=int(os.environ.get("CAPACITY", "50")))
    while not stop.is_set():
        try:
            ctl.ensure_placed(); ctl.redistribute(); ctl.ensure_home(1); ctl.unplace_deleted()
        except Exception:                         # noqa: BLE001
            logging.exception("rec placement pass failed")
        stop.wait(5)


def controller() -> None:
    """count = 1, the only writer of placement. No HTTP: nothing asks it anything."""
    from cluster.controller import ClusterController
    ctl = ClusterController(open_vars(CONFIG_URL), objects, capacity=int(os.environ.get("CAPACITY", "50")),
                            cluster=os.environ.get("CLUSTER", "cluster-a"))
    while not stop.is_set():
        try:
            ctl.ensure_placed(); ctl.redistribute(); ctl.ensure_home(1); ctl.publish_snapshot()
        except Exception:                         # noqa: BLE001
            logging.exception("placement pass failed")
        stop.wait(5)


def console() -> None:
    """one per server, a system job: the page and the API. Its token writes the
    operator's rows and nothing else; a create is placed by the controller's next
    pass. No event index of its own: /events asks the live resources and merges."""
    from cluster.console import serve
    from cluster.controller import ClusterController
    from w2cplatform.spec import SpecController
    from vms.config import REC_SPEC
    vars_ = open_vars(CONFIG_URL)
    ctl = ClusterController(vars_, objects, capacity=int(os.environ.get("CAPACITY", "50")),
                            cluster=os.environ.get("CLUSTER", "cluster-a"))
    srv = serve(ctl, os.environ.get("CONSOLE_HOST", "0.0.0.0"), int(os.environ.get("CONSOLE_PORT", "8080")),
                archive_root=archive if os.path.isdir(archive) else None,     # marks go into this server's resource, if it has one
                rec_ctl=SpecController(REC_SPEC, vars_, objects))              # the recorder at /rec/…: the page's Record toggle
    stop.wait()
    srv.shutdown()


def resource() -> None:
    """М10's resource process as a job: the platform's Resource with the VMS registered on it, and the event index over its own tree."""
    from cluster.resource import cluster_resource
    from w2cplatform.resource import serve
    server = runtime.server(os.environ)
    url = os.environ.get("RESOURCE_URL", f"http://{server}:8090")
    res = cluster_resource(archive, server, url, open_vars(CONFIG_URL), objects)
    srv = serve(res, "0.0.0.0", int(os.environ.get("RESOURCE_PORT", "8090")))
    res.heartbeat(); logging.info("restore: %s", res.restore())    # back with an empty disk? pull my buckets from my peers first
    last_policy = 0.0
    while not stop.is_set():
        try:
            res.heartbeat()
            if time.time() - last_policy >= 600:
                logging.info("policy: %s", res.pass_()); last_policy = time.time()
        except Exception:                         # noqa: BLE001
            logging.exception("resource pass failed")
        stop.wait(10)
    srv.shutdown()


if __name__ == "__main__":
    {"worker": worker, "controller": controller, "recorder": recorder, "reccontroller": reccontroller,
     "console": console, "resource": resource}[sys.argv[1]]()
