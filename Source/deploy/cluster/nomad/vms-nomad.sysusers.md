# vms-nomad.sysusers — the groups the `vms` user needs where Nomad runs the VMS's jobs

**Role in the module.** The appendix «форма поставки». A unit gives its process its role's groups (`SupplementaryGroups=`); a `raw_exec` task runs as `user = "vms"` with that user's groups. So on a Nomad node `vms` is a member of what its tasks open: `vms-console`, `vms-vmsworker`, `vms-recworker` (the store's sockets), `vms-obsd` (the engine), `w2c-events`, `w2c-store` and `w2c-secrets` (the box's layout). The key ring was 0750 root:w2c and `vms` not in `w2c`: `Sealer.from_file` raised and every task went round its restarts (the twelfth review, major 13); the ring is 2710 root:w2c-secrets now and the key 0640 to that group. The cost, said: on such a node the roles are one user.

## Notes
- `tests/cluster/test_units.py::test_a_nomad_task_can_read_the_key_and_open_its_socket`.
