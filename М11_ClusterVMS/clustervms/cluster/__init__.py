"""ClusterVMS — М11. М10's platform shape across several servers, with no orchestrator.

Built ON М10's `vmsserver/` (imported, not copied): the same `w2cplatform` contract and the same `vms/` controller,
worker and archive resource. Every server runs the same units (`deploy/systemd/`, `deploy/launchd/`): the platform's
`configstore` daemon — a member of one raft group over the servers (`w2cplatform/configstore.py`) — and its
resource, the VMS's console, controllers and workers. A process opens the store through its role's socket on its own
server (`PLATFORM_STORE=configstore:///run/configstore/<role>.sock`), and nothing in `vms/` can tell it from a box's
files. This package supplies what a cluster adds and nothing else:

    __main__.py     the processes' entry points, one per unit: their stores by role, `python3 -m cluster rights`
    rights.py       the configstore's rights file, generated from the spec (`deploy/configstore-rights.json`)
    variables.py    the `Variables` contract by this package's name, and `FakeVariables` — the older tests', М12's
    objectstore.py  the cluster's objects, `cluster://`: each server's own as files, every server's through the
                    resources (`/v1/objects`), the create-only keys as rows; MinIO / S3 (SigV4 in s3.py) for a
                    rented cluster
    worker.py       the worker as a unit: its name from the unit (`WORKER_NAME=w-%l-1`), labels from the server
    recworker.py    the recorder as a unit: the same, and the volume it holds
    controller.py   the controller on every server: placement under label constraints; the snapshot for М12
    resource.py     the archive resource on every server: its heartbeat, its doors, its event index
    directory.py    where is camera 7 — one scan of vms/workers/*
    console.py      the cluster console, standard library
"""
import os
import sys

_here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for cand in (os.environ.get("VMSSERVER_PATH", ""),
             os.path.join(_here, "vmsserver"),
             os.path.join(os.path.dirname(os.path.dirname(_here)), "vmsserver"),
             os.path.join(os.path.dirname(os.path.dirname(_here)), "М10_ServerVMS", "vmsserver")):
    if cand and os.path.isdir(cand) and cand not in sys.path:
        sys.path.append(cand)          # append, not insert: our own tests/ must win
        break
