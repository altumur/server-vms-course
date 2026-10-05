# verify-bench.sh — the checks that need a real cluster, in one run on one of its servers

**Role in the module.** Lessons 2 and 5. The suite runs the stand in one process; this runs as root on a server of a real cluster (`install.sh` done on three) and prints PASS/FAIL per item. No Nomad: the questions are the store's and the units'.

## The checks
1. **The store** — `configstore status` through `admin.sock`: three members or more, one leader.
2. **The units** — `configstore`, `w2c-resource`, `w2c-console`, `vms-vmscontroller`, `vms-reccontroller`, `vms-vmsworker`, `vms-recworker`, `vms-obsd` active.
3. **The sockets** — every role of `/etc/w2c/configstore-rights.json` has `/run/configstore/<role>.sock`, mode 660, owned by the role's `group`.
4. **The rights held** — `GET /v1/rights` on `admin.sock` equals the installed file, and the file is what the spec generates (`w2c-run.sh rights --check`).
5. **Rights by the socket**, with `curl --unix-socket`: `vmsworker.sock` writes `vms/slots/*` and is refused `vms/cameras/*` and `vms/placement/*` (403); `console.sock` writes a camera row and is refused placement; `vmscontroller.sock` places. The probe rows are removed through `admin.sock` (slots, cameras and placement are deletable; an epoch row is not, so none is written).
6. **mTLS on the -api door** — a client with no certificate is refused at the handshake (`CONFIGSTORE_API` from `/etc/w2c/w2c.env`).
7. **The objects** — `GET /v1/objects?prefix=vms/heartbeats/&scope=cluster` on the resource here names the servers whose workers' heartbeats it read, and the missing ones.
8. **The mirror** — a peer takes a bucket's copy at `PUT /mirror/…` and lists it at `/mirrored/…`: resource to resource, nothing through a store.

## Notes
- Exit status 0 only if every check passed. The probe in 8 leaves a copy under `.mirror/srv-verify/` on this server, swept by the resource's retention.
