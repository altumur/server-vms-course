# worker.py — `ClusterWorker` is М10's `VmsWorker` as a unit on every server: its name from the unit, the server and labels from the environment

**Role in the module.** Lesson 2. The worker on a cluster is М10's `VmsWorker` unchanged (see `../../../vmsserver/vms/worker.py.md`): what a unit hands a process — `WORKER_NAME` (`w-%l-1`: `w-srv-a-1` on srv-a, product P4), `SPARE_FOR` (a spare started by `w2c-spares.sh`, which takes only an offer of that label set), `SERVER_NAME`, `LABELS`, `CAPACITY`; or, where a site runs an orchestrator, `SLOT_INDEX` — `VmsWorker` already reads from its environment (`w2cplatform/runtime.py`), on a box exactly as on a cluster server. This module keeps the name М11's lessons used and the `env=` calling convention so a test can hand it an environment. The docstring's line: a worker on a cluster is a worker on a box whose store happens to be replicated and whose objects are read across the servers. Used by `__main__.worker` and by `tests/conftest.py`.

## Module-level names
- `FakeActuator`, `VmsWorker`, `labels_from_environment`, `slot_from_environment` — re-exported from `vms.worker` (`noqa: F401`).

## `class ClusterWorker(VmsWorker)`
A `VmsWorker` whose name is always taken from the environment.

### `__init__(self, vars_, objects, actuator=None, env=None, **kw)`
`super().__init__(None, vars_, objects, actuator or FakeActuator(), env=env, **kw)`. `name=None` means "the environment's": the unit's `WORKER_NAME`, claimed by CAS on `vms/slots/<name>` — taken outright when another process holds it (the unit restarted while the old one lived: the old one is fenced at its next renewal); a spare (`SPARE_FOR`) takes an offer row of its label set, or waits holding nothing. `env=None` means `os.environ`; the stand passes `Cluster.env(server, name)` (`SERVER_NAME`, `LABELS`, `INSTANCE_ID` as host and pid, `WORKER_NAME`). `previous_instance`/`previous_hb`/`previous_server` are read from the name's last heartbeat, so a process systemd started again measures its own restart on one clock; a name taken on another server is measured by the reader's own clock (`failover_seconds`).

## Notes
- What the tests prove through this class: the name from the unit and the server's labels in the heartbeat (`test_lesson2_jobs.py::test_the_name_comes_from_the_unit_and_the_labels_from_the_server`); a spare takes an offer and stops (`::test_a_spare_takes_an_offer_then_stops`); two processes with one name resolve at the CAS (`::test_two_processes_with_one_name_resolve_at_the_cas`); the power pull — nothing restarts w-srv-a-1 elsewhere, the controller moves its cameras by assignment to w-srv-b-1 after two silences, which takes the next epoch per camera (`test_lesson4_failover.py::test_the_power_pull`); a restart on one clock, a name taken elsewhere by the reader's (`::test_a_restart_is_measured_on_one_clock_and_a_name_taken_elsewhere_by_the_readers`).
- `__main__.worker` passes `actuator=None` when GStreamer is absent, which lands on `FakeActuator()` here.
