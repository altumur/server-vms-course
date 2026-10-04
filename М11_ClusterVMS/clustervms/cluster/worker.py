"""The worker as a unit on every server — and it is М10's `VmsWorker`, unchanged.
What a runtime hands a process (WORKER_NAME from the unit, `w-%l-1`; SPARE_FOR
for a spare `w2c-spares.sh` started; SERVER_NAME, LABELS, INSTANCE_ID,
CAPACITY — or, where a site runs an orchestrator, SLOT_INDEX from its own
index) the worker reads from its environment on a box exactly as on a cluster
server; this module keeps the name М11's lessons used and the `env=` calling
convention. Nothing here names a supervisor: see `w2cplatform/runtime.py`.

Nothing here is new behaviour. A worker on a cluster is a worker on a box
whose store happens to be replicated (`configstore://`) and whose objects are
read across the servers (`cluster://`).
"""
from __future__ import annotations

from vms.worker import FakeActuator, VmsWorker, labels_from_environment, slot_from_environment  # noqa: F401


class ClusterWorker(VmsWorker):
    def __init__(self, vars_, objects, actuator=None, env: dict | None = None, **kw):
        super().__init__(None, vars_, objects, actuator or FakeActuator(), env=env, **kw)
