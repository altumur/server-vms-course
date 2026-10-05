"""The cluster console, standard library — its own job (`system`: one on every server, nothing in front),
its own token (the operator's rows, never placement). The platform's
SpecConsole run from the VMS spec, exactly as М10 runs it — and since the footage
is read at its holders' doors (the boundary's step 6: `/where` hands out the door, the bytes bypass the console), the
cluster adds nothing to it:

    GET /rec/where/<recording>       the recorder that holds it, and its door: the recording's spans from every live
                                     recorder's archive door and an interval as MP4 (`vms/footage.py`)
    GET /events?from&to&unit&…       merged across the live resources' event indexes (the platform's `MergedIndex`); none here
    /rec/spec, /rec/recordings, …    the recorder mounted under its name (`Mount`): the page's Record toggle POSTs here

The rest — the page, /spec, /cameras, /where (one scan of the assignments),
/resources, /servers, /policy, /unplaceable, /metrics, /marks, POST/PUT/DELETE — is
`w2cplatform.console.SpecConsole` reading `vms.subsystem.yaml`. The recorder's
console at `/rec/…` is the same class over `rec.subsystem.yaml`.

The console holds no footage and no event index. Each recorder serves the
volume it holds; each resource job keeps an index over its own tree (its
buckets and the copies it holds of its peers') and answers `GET /events` from
it; the console asks and merges by time, naming what did not answer. Exactly
what М10's console does on one box: one class.
"""
from __future__ import annotations

from http.server import ThreadingHTTPServer

from w2cplatform.console import Mount, SpecConsole, heartbeats   # noqa: F401
from w2cplatform.eventdatabase import MergedIndex          # noqa: F401  (re-exported: the console's view of the event indexes)
from w2cplatform.spec import SpecController

from vms.console import wire_vms

from .controller import ClusterController


# THE SAME CONSOLE MEANS THE SAME GATE (М10's sixth review, found while sweeping every door). This function built the
# two consoles itself and wired nothing of what М10's `make_console` wires: `/timeline/<cam>` and `/export/<cam>` were
# not routes that name a camera here, so in a cluster that asks who is calling a viewer of camera 1 was given camera
# 2's timeline and its footage for any grant at all; a recording's grant was matched on its own placement labels; what
# left through this console was in no journal; and the recorder's mount had neither the archives (`/rec/volumes`,
# `/rec/keeps`) nor the numbers the recorder's scaling check asks for (`rec_recorders_needed`,
# `w2c-spares.sh`, for recorders). One function wires a console of the VMS, whoever builds it: `vms.console.wire_vms`.
def make_console(ctl: ClusterController, worst_failover: float = 0.0, index=None, resource_root: str | None = None,
                 rec_ctl: SpecController | None = None) -> Mount:
    """The VMS at `/` and, when the console fronts it, the recorder at `/rec/…` (the page's Record toggle:
    POST /rec/recordings). Both answer /events from the same merge over the resources' indexes."""
    index = index or MergedIndex(ctl.objects, wall=ctl.wall)
    root = SpecConsole(ctl, marks_root=resource_root, index=index, worst_failover=worst_failover)
    m = Mount(root)
    if rec_ctl is not None:
        m.mount("rec", SpecConsole(rec_ctl, wall=ctl.wall, index=index))   # its tables, requests and numbers: its spec's
    return wire_vms(m, ctl, index)


def metrics_text(ctl: ClusterController, worst_failover: float) -> str:
    return SpecConsole(ctl, worst_failover=worst_failover).metrics_text()


def serve(ctl, host="127.0.0.1", port=8080, worst_failover=0.0, index=None, resource_root=None, rec_ctl=None) -> ThreadingHTTPServer:
    return make_console(ctl, worst_failover, index, resource_root, rec_ctl).serve(host, port)
