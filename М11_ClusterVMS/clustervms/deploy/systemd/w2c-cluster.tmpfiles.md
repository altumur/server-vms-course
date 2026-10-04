# w2c-cluster.tmpfiles — the directories of a cluster server

**Role in the module.** Lesson 3. Configuration on the data partition: `/data/platform/etc` (= `/etc/w2c`; `secrets/` 0750 root:w2c) and `/data/vms/etc` (= `/etc/vms`) — the links are `install.sh`'s. The platform's state: `/data/platform/configstore` (0700 w2c — the store's journal) and `/data/platform/objects` (2775 w2c:vms); the events tree `/data/archive` (2775 vms:vms) — both written by both users, setgid, with every unit's `UMask=0002`. `/run/vms`: the worker's tee for subscribers on this server.
