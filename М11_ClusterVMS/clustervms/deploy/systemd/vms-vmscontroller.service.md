# vms-vmscontroller.service — placement of cameras, on every server

**Role in the module.** Lesson 10. `w2c-run.sh controller` as `vms`, joining `vms-vmscontroller`: placement and nothing else; and `w2c-store` (its snapshot is objects on this server), `UMask=0007`, `ProtectSystem=strict`. One on every server, safe at several (every write a CAS); it starts no process — it publishes numbers and offers, and `w2c-spares.sh` starts. Its settings beyond its own lines come from `/etc/w2c/w2c.env` and `/etc/vms/vms.env`, read by `w2c-run.sh` UNDER what the unit says (no `EnvironmentFile=`: systemd would let a file override `Environment=`). `Restart=always`, `RestartSec=2`: a crash is systemd's to restart under the same name, on this server.

## Notes
- `tests/test_units.py`: each unit names its role's socket (`PLATFORM_STORE=configstore:///run/configstore/<role>.sock`), joins the group the rights file gives that role, runs `w2c-run.sh <verb>`, comes after `configstore.service`, as `w2c` (the platform's) or `vms` (the subsystem's).
