# w2c-cluster.tmpfiles — the directories of a cluster server

**Role in the module.** Lesson 3. Configuration on the data partition: `/data/platform/etc` (= `/etc/w2c`) and `/data/vms/etc` (= `/etc/vms`) — the links are `install.sh`'s. The platform's state is the box's layout (WP-E, `Source/deploy/w2c.tmpfiles`, which `install-obsd.sh` applies too; where both name a directory they say the same): the key ring `etc/secrets` 2710 root:w2c-secrets (the key 0640, `install-obsd.sh`), `etc/tls` 0750 root:configstore (what the store's -api door shows), the store's journal `configstore/` 0700 configstore, the objects 2770 w2c:w2c-store, the events archive `/data/platform/events` 2770 w2c:w2c-events — setgid, every unit writing with `UMask=0007`, so what a client makes is its group's and the resource deletes it. `/run/vms` is the box's `vms.tmpfiles` (root's); the worker's unit makes it its own (`RuntimeDirectory=vms`).

## Notes
- `tests/cluster/test_units.py::test_the_directories_are_the_boxs_layout`; `::test_a_nomad_task_can_read_the_key_and_open_its_socket` (the key ring under Nomad, the twelfth review's major 13).
