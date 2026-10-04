# w2c-spares.rules — what the spares' user may ask systemd for

**Role in the module.** Lesson 4. A polkit rule, installed by `install.sh --spares` as `/etc/polkit-1/rules.d/50-w2c-spares.rules`. `w2c-spares.sh` ran as root (the product's cross-check, 4 Oct); it runs as `w2c-spares` now (`w2c-cluster.sysusers`, in no group but its own; `User=` in М10's `w2c-spares*.service`), and this rule is all that user may do through systemd: `org.freedesktop.systemd1.manage-units` with the verb `start`, of `vms-vmsworker-spare@<n>.service` or `vms-recworker-spare@<n>.service` — `install.sh`'s `SPARE_UNITS` — with `<n>` from 1 to 99 (the thirteenth review, minor: `@99999999999999999999` was let through; the script's ceilings are single digits by default, and a start past the rule is refused and said). Anything else that user asks is `NO` at once (not an administrator's prompt nobody answers); another user's question is not this rule's (`NOT_HANDLED`).

## Notes
- No `reset-failed`: the script no longer asks it before a start, and an instance systemd refuses is said and the next number tried.
- `tests/test_units.py::test_the_spares_script_runs_as_its_own_user_whom_polkit_lets_start_a_spare_template_and_nothing_else` checks the rule's templates against `SPARE_UNITS` and runs the rule under `node` against a stub `polkit` (skipped where there is no node).
