"""The one-box console, standard library — the platform's SpecConsole run from the VMS's specs, and nothing of the
VMS's own any more (the boundary's step 6).

Everything a page asks — the page, /spec, /cameras, /where, /marks, /metrics, the POST/PUT/DELETE of a camera, the
recorder's tables and requests under `/rec/…` — is `w2cplatform.console.SpecConsole` reading the specs. The footage and
the live stream do NOT go through it (the owner's decision 1): `GET /where/<id>` hands out the door of the unit's
holder with a token (`door:` in a spec, `w2cplatform/door.py`), and the page reads the holder itself — a recording's
recorder (`vms/footage.py`), a camera's holder for the device's own archive, a gateway for the stream. The routes that
were here — `/timeline/<cam>`, `/export/<cam>`, `/segment`, `/whep/<cam>` (`vms_routes`, `LiveFront`) — are those doors.
Its own process (`python3 -m vms console`), with its own token: the operator's rows — cameras, next_id, retention — and
never placement.
"""
from __future__ import annotations

import time
from http.server import ThreadingHTTPServer

from w2cplatform.console import PAGE, Mount, SpecConsole, send_file   # noqa: F401  (PAGE, send_file re-exported for М11)
from w2cplatform.eventdatabase import MergedIndex
from w2cplatform.spec import SpecController

from .controller import VmsController


# `SpecConsole`s over the VMS's specs, mounted in one process: the VMS at `/` (the page, /cameras, /where with the
# holder's door), and every other subsystem the console fronts under its name — `/live/…`, `/rec/…`, `/det/…` — each
# with the console's token. With a resource root on this server, operator marks (`POST /marks`) go into the console's
# own event log there. `media` — the page draws a timeline and a player, from the holders' doors.
def make_console(ctl: VmsController, archive_root: str | None, wall=None, live_ctl: SpecController | None = None,
                 mounts: dict[str, SpecController] | None = None, index=None, media: bool | None = None) -> Mount:
    """One console process for the box: the VMS at `/`, and every other subsystem the console fronts under its name."""
    index = index or MergedIndex(ctl.objects, wall=wall or time.time)   # no database here: the resource process's, asked over HTTP
    media = archive_root is not None if media is None else media         # footage to show: the holders' doors
    root = SpecConsole(ctl, marks_root=archive_root, wall=wall, media=media, index=index)
    m = Mount(root)
    if live_ctl is not None:
        m.mount("live", SpecConsole(live_ctl, wall=wall, index=index))
    for name, c in (mounts or {}).items():
        m.mount(name, SpecConsole(c, wall=wall, index=index))          # every mount answers /events from the same merge
    return wire_vms(m, ctl, index)


# WHAT A CONSOLE OF THE VMS NEEDS, WHOEVER BUILDS IT (the review's sixth pass: М11 builds its own, `cluster/console.py`):
# one journal for the process — a mount has no resource root of its own, and "who deleted recording 7" belongs beside
# "who deleted camera 7". (What the VMS's routes needed at the gate — `timeline`, `export`, `whep` as routes that name a
# camera — went with the routes, at the boundary's step 6: the door the console hands out names its unit.)
def wire_vms(m: Mount, ctl, index=None) -> Mount:
    for con in m.mounts.values():
        con.journal = m.root.journal
    return m


# `make_console(...).serve(host, port)`: the server in a daemon thread, returned so the caller can
# `shutdown()` it. `__main__.console` calls it with `$CONSOLE_HOST:$CONSOLE_PORT`; the tests with `port=0`.
def serve(ctl: VmsController, archive_root: str | None, host: str = "127.0.0.1", port: int = 8080, wall=None,
          live_ctl: SpecController | None = None, mounts: dict[str, SpecController] | None = None, index=None) -> ThreadingHTTPServer:
    return make_console(ctl, archive_root, wall, live_ctl, mounts, index).serve(host, port)
