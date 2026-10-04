# configstore.service — this server's member of the cluster's replicated config store

**Role in the module.** Lesson 2. `w2c-run.sh configstore`: the daemon (`w2cplatform/configstore.py`) as its own user `configstore` (WP-E: the journal its alone, 0700), a member of the raft group over the servers, a unix socket per role of the rights file under `/run/configstore` (`RuntimeDirectory=configstore`), each 0660 and owned by the role's group — so `configstore` is a member of every one (`w2c-cluster.sysusers`) — `admin.sock` root's, and the -api door with mutual TLS (`/etc/w2c/tls`). Its flags from `/etc/w2c/w2c.env` (`CONFIGSTORE_RAFT`, `CONFIGSTORE_API`, `CONFIGSTORE_JOIN`). Every other unit comes after it. Its journal is `/data/platform/configstore`, the one path it writes (`ProtectSystem=strict`).

## Notes
- `tests/cluster/test_units.py`: each unit names its role's socket (`PLATFORM_STORE=configstore:///run/configstore/<role>.sock`), joins the group the rights file gives that role, runs `w2c-run.sh <verb>`, comes after `configstore.service`, as `w2c` (the platform's) or `vms` (the subsystem's).
