"""The one-box console, standard library — the platform's SpecConsole run from the VMS's specs, and nothing of the
VMS's own any more (the boundary's step 6).

Everything a page asks — the page, /spec, /cameras, /where, /marks, /metrics, the POST/PUT/DELETE of a camera, the
recorder's tables and requests under `/rec/…` — is `w2cplatform.console.SpecConsole` reading the specs. The footage and
the live stream do NOT go through it (the owner's decision 1): `GET /where/<id>` hands out the door of the unit's
holder with a token (`door:` in a spec, `w2cplatform/door.py`), and the page reads the holder itself — a recording's
recorder (`vms/footage.py`), a camera's holder for the device's own archive, a gateway for the stream. The routes that
were here — `/timeline/<cam>`, `/export/<cam>`, `/segment`, `/whep/<cam>` (`vms_routes`, `LiveFront`) — are those doors.
The deployed console is the platform's verb, `python3 -m w2cplatform console` with `CONSOLE_ROOT=vms` (`host.py`); this
module builds the same `Mount` for the tests and the lessons, from the VMS's specs: its own token, the operator's rows —
cameras, next_id, retention — and never placement.
"""
from __future__ import annotations

from http.server import ThreadingHTTPServer

from w2cplatform.console import Mount
from w2cplatform.host import spec_console
from w2cplatform.spec import SpecController

from .controller import VmsController


# `SpecConsole`s over the VMS's specs, mounted in one process (`host.spec_console`, the platform's): the VMS at `/` (the
# page, /cameras, /where with the holder's door), and every other subsystem the console fronts under its name —
# `/live/…`, `/rec/…`, `/det/…` — each with the console's token, one journal and one index for all of them. With a
# resource root on this server, operator marks (`POST /marks`) go into the console's own event log there.
def make_console(ctl: VmsController, resource_root: str | None, wall=None, live_ctl: SpecController | None = None,
                 mounts: dict[str, SpecController] | None = None, index=None) -> Mount:
    """One console process for the box: the VMS at `/`, and every other subsystem the console fronts under its name."""
    ctls = {ctl.spec.name: ctl, **({"live": live_ctl} if live_ctl is not None else {}), **(mounts or {})}
    return spec_console(ctls, ctl.spec.name, resource_root, index, wall)


# `make_console(...).serve(host, port)`: the server in a daemon thread, returned so the caller can
# `shutdown()` it. `__main__.console` calls it with `$CONSOLE_HOST:$CONSOLE_PORT`; the tests with `port=0`.
def serve(ctl: VmsController, resource_root: str | None, host: str = "127.0.0.1", port: int = 8080, wall=None,
          live_ctl: SpecController | None = None, mounts: dict[str, SpecController] | None = None, index=None) -> ThreadingHTTPServer:
    return make_console(ctl, resource_root, wall, live_ctl, mounts, index).serve(host, port)
