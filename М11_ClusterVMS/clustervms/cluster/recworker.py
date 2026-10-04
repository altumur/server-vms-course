"""The recorder as a unit on every server — and it is М10's `RecWorker`, unchanged.
The unit hands it what it hands a worker (WORKER_NAME → `r-%l-1`, SERVER_NAME
→ the server it runs on, LABELS, CAPACITY, BOX_ID → the machine); it claims
`rec/slots/r-<server>-1` by CAS, takes a volume — a declared one it may serve, by CAS
under `rec/holds/`, or its server's own — reads the assignment the rec
controller wrote, subscribes to each camera's fan-out from whichever worker
holds it (the VMS heartbeat's `live_url`), and writes footage into its volume
through the HOST's obsd, as the stream `<recording>/e<epoch>`.

Its unit (`deploy/systemd/vms-recworker.service`) runs on a server with
disks; whether two recorders on one server both carry recordings is
`rec/policy {servers}` — `distinct` by default, the one subsystem where a
second process on the same disks is no second place to record. When the
server dies, the rec controller moves its recordings to a server whose
resource answers; the footage written before the move stays in the old
server's volume under the old epoch, and the timeline names that volume
unavailable — not lost — until a recorder holds it again.
"""
from __future__ import annotations

from vms.recworker import REC, RecWorker  # noqa: F401
from vms.worker import FakeActuator


class ClusterRecorder(RecWorker):
    def __init__(self, vars_, objects, actuator=None, env: dict | None = None, **kw):
        super().__init__(None, vars_, objects, actuator or FakeActuator(), env=env, **kw)
