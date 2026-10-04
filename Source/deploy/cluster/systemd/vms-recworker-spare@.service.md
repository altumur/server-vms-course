# vms-recworker-spare@.service — a spare recorder, started by `w2c-spares.sh`

**Role in the module.** Lesson 4. `vms-recworker.service` line for line — the same user, groups, socket, engine, box, key, umask, watchdog, protection — but no name (it claims whichever `r-<n>` is free and takes a free declared volume by CAS: a recorder needs no offer) and its archive door on a port the OS gives (`ARCHIVE_PORT=0`; `__main__.recorder` then announces the port it got, on the address `ARCHIVE_URL` names). Never enabled; `systemctl start vms-recworker-spare@<n>`. It replaced `systemd-run … w2c-run.sh recorder`, root without the key — a network volume's sealed secret did not open (the twelfth review, blocker 6).

What it depends on it does not start (the thirteenth review, major 12): `Requisite=configstore.service vms-obsd.service` with `After=` — `Wants=` made PID 1 start the engine the administrator had stopped to hand the volumes over (`install-obsd.sh`, `chown -R`) whenever the spares' timer started a spare, past polkit.

## Notes
- `tests/cluster/test_units.py::test_a_spare_is_its_roles_unit_line_for_line_but_the_name`, `::test_a_spare_starts_nothing_it_depends_on_and_a_refused_set_is_not_restarted`.
- No set and no file of its own: a recorder needs no offer. `Type=simple`, `NotifyAccess=main`, `WatchdogSec=360`, as the role's unit.
