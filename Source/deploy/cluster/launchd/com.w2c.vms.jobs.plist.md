# com.w2c.vms.jobs.plist — the VMS's housekeeping, on a macOS server

**Role in the module.** The twin of `deploy/cluster/systemd/vms-jobs.service`: `__BOX__/bin/w2c-run.sh vms jobs`, `KeepAlive` and a 2 s `ThrottleInterval` for systemd's `Restart=always`/`RestartSec=2`, the console's socket under `__BOX__/state/run/configstore` (it writes configuration with the console's grant), `JOBS_HOST`/`JOBS_PORT` as the unit's. Logs in `__BOX__/state/logs/com.w2c.vms.jobs.log`. `tests/cluster/test_units.py::test_every_plist_is_its_units_twin`.
