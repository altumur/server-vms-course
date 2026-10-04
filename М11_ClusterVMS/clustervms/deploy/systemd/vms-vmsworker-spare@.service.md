# vms-vmsworker-spare@.service — a spare worker, started by `w2c-spares.sh`

**Role in the module.** Lesson 4. `vms-vmsworker.service` line for line — the same user, groups, socket, key, umask, watchdog, protection — but no name: no `WORKER_NAME`; its label set from a one-line file the script writes before it starts the instance (`EnvironmentFile=/run/w2c-spares/%n.env`, `SPARE_FOR=<set>`; no `-`: a spare whose set is not said does not start, else it would be a worker taking any free name); its fan-out on a port the OS gives (`RTSP_PORT=auto`), 8554 being the server's own worker's. No `[Install]`: never enabled, only its instances started (`systemctl start vms-vmsworker-spare@<n>`). It replaced `systemd-run … w2c-run.sh worker`, a root process without the key or the opened fan-out (the twelfth review, blocker 6). A template and not a list of properties in the script: one file beside the role's, shown by `systemctl cat`, `%d` expanded, held to the role's unit by a test.

## Notes
- `tests/test_units.py::test_a_spare_is_its_roles_unit_line_for_line_but_the_name`; `vmsserver/tests/test_deploy_units.py::test_a_spare_is_started_only_as_its_roles_unit_and_never_as_root_without_one`.
