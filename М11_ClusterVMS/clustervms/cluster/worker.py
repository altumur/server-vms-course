"""The worker as a unit on every server — and it is М10's `VmsWorker`, unchanged.
What a runtime hands a process (WORKER_NAME from the unit, `w-%l-1`; SPARE_FOR
for a spare `w2c-spares.sh` started; SERVER_NAME, LABELS, INSTANCE_ID,
CAPACITY — or, where a site runs an orchestrator, SLOT_INDEX from its own
index) the worker reads from its environment on a box exactly as on a cluster
server; this module keeps the name М11's lessons used and the `env=` calling
convention. Nothing here names a supervisor: see `w2cplatform/runtime.py`.

Nothing here is new behaviour but one line: the loop tells its supervisor it
turns (`notify`, systemd's watchdog). A worker on a cluster is a worker on a box
whose store happens to be replicated (`configstore://`) and whose objects are
read across the servers (`cluster://`).
"""
from __future__ import annotations

import os
import socket

from vms.worker import FakeActuator, VmsWorker, labels_from_environment, slot_from_environment  # noqa: F401


# THE WATCHDOG (the twelfth review, major 14). Lesson 8 promised one — a hung worker gives systemd time to see it
# (`WatchdogSec`) before its cameras move — and there was none: `KeepAlive`/`Restart=always` see a process that ENDED,
# never one that stopped turning, and a hung worker held its cameras the whole fifteen minutes. `sd_notify` without
# libsystemd: one datagram to the socket systemd names in `$NOTIFY_SOCKET` (`@` — the abstract namespace). Nothing to
# say to (launchd, a bench, a test without one): False, and nothing else happens. A socket that refuses is the same: the
# supervisor's business, never a reason for the loop to stop.
def notify(state: bytes = b"WATCHDOG=1", env: dict | None = None) -> bool:
    path = (os.environ if env is None else env).get("NOTIFY_SOCKET", "")
    if not path:
        return False
    if path.startswith("@"):
        path = "\0" + path[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as s:
            s.connect(path)
            s.send(state)
        return True
    except OSError:
        return False


class ClusterWorker(VmsWorker):
    def __init__(self, vars_, objects, actuator=None, env: dict | None = None, **kw):
        super().__init__(None, vars_, objects, actuator or FakeActuator(), env=env, **kw)

    # At the end of every turn of the loop (`VmsWorker.run`), whatever its steps did — a step that RAISED is a loop
    # that turns, and says so; a step that HANGS keeps the loop from coming here, and after `WatchdogSec` systemd ends
    # the process and starts the unit again, which claims its name back.
    def between(self, poll: float, stop, beat: float) -> None:
        notify()
        super().between(poll, stop, beat)
