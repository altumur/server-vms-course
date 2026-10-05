"""The platform across several servers, with no orchestrator (М11_Cluster).

The same contract, spec controller, worker runtime, resource and console as on one box: every server runs the same
units (`deploy/cluster/systemd/`, `deploy/cluster/launchd/`) — the platform's `configstore` daemon, a member of one raft
group over the servers (`w2cplatform/configstore.py`), its resource, its console and a controller per subsystem — and a
subsystem's own workers beside them. A process opens the store through its role's socket on its own server
(`PLATFORM_STORE=configstore:///run/configstore/<role>.sock`) and its objects as `cluster://` (`OBJECTS`), and nothing
in its loop can tell them from a box's files. This package supplies what a cluster adds and nothing else, and knows the
subsystems by their specs only:

    __main__.py     the platform's processes, one per unit: `controller <sub>`, `console`, `resource`, `rights`
    rights.py       the configstore's rights file, generated from the catalogue of specs
    variables.py    the `Variables` contract by this package's name, and `FakeVariables`
    objectstore.py  the cluster's objects, `cluster://`: each server's own as files, every server's through the
                    resources (`/v1/objects`), the create-only keys as rows; MinIO / S3 (SigV4 in s3.py) for a
                    rented cluster
    directory.py    where is unit N of a subsystem — one scan of `<sub>/workers/*`
"""
