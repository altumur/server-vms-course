"""python3 -m w2cplatform.cluster controller <sub> | console | resource | rights — the platform's processes of a cluster
server, each started by its own unit (`deploy/cluster/systemd/`, `deploy/cluster/launchd/`), from the specs alone
(`SPEC_DIR`, which `w2c-run.sh` sets to the installed tree's specs). `rights` prints the configstore's rights file
generated from those specs (`rights.py`).

The verbs and their loops are the box's (`w2cplatform/host.py`): what a cluster changes is only where the two stores
are — the store by the role's own socket on this server, the objects `cluster://` — and both are the environment's:

    PLATFORM_STORE     the store, as a URL: this server's configstore daemon by the role's socket,
                       `configstore:///run/configstore/<role>.sock` (the default: `<sub>controller`, `console`,
                       `resource`); `file:///path` on a bench
    OBJECTS            the object store: `cluster:///data/platform/objects?resource=http://127.0.0.1:8090` (the default) —
                       this server's objects as files, every server's through the resource on this one, the create-only
                       keys as rows in the process's own store; `s3+http://…` on a rented cluster; `file:///path` on a bench
    SERVER_NAME, LABELS, RESOURCE_ROOT, RESOURCE_URL, CONSOLE_ROOT, …   as on a box (`host.py`, `runtime.py`)

A subsystem's own processes on a cluster are its own entry point's, over the same two variables
(`w2c-run.sh <package> <verb>`).
"""
from __future__ import annotations

import logging
import os
import signal
import sys

from w2cplatform import catalog, host
from w2cplatform.host import stop

OBJECTS = "cluster:///data/platform/objects?resource=http://127.0.0.1:8090"
USAGE = "python3 -m w2cplatform.cluster controller <sub> | console | resource | rights [--check FILE]"


# The environment a verb runs in: the unit's, and where it said nothing, the cluster's two stores — the role's socket on
# this server and the objects across the servers. A test hands its own.
def cluster_env(role: str, env: dict | None = None) -> dict:
    env = dict(os.environ if env is None else env)
    env.setdefault("PLATFORM_STORE", f"configstore:///run/configstore/{role}.sock")
    env.setdefault("OBJECTS", OBJECTS)
    return env


def main(argv: list[str], env: dict | None = None) -> int:
    env = dict(os.environ if env is None else env)
    if argv[:1] == ["rights"]:
        from .rights import main as rights
        return rights(argv[1:], env)
    if not env.get(catalog.SPEC_DIR):
        logging.error("%s is not set: the platform runs from the specs it is given — %s", catalog.SPEC_DIR, USAGE)
        return 2
    catalog.load_dir(env[catalog.SPEC_DIR])
    if argv[:1] == ["controller"] and len(argv) == 2:
        # Its unit gives it no write in the events tree: its decisions are in its log, not this server's journal.
        host.controller(argv[1], cluster_env(f"{argv[1]}controller", env), journal=False)
        return 0
    if argv == ["resource"]:
        host.resource(cluster_env("resource", env))
        return 0
    if argv == ["console"]:
        try:
            host.console(cluster_env("console", env))
        except ValueError as e:
            logging.error("%s", e)
            return 2
        return 0
    logging.error("%s", USAGE)
    return 2


if __name__ == "__main__":
    # Only when run: a module imported (the tests) must not take the process's signals (the review's sixth pass).
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(name)s %(levelname)s %(message)s")
    from w2cplatform.secrets import mask_logs
    mask_logs()                    # a log line holds no credential: an address, a driver's error (`secrets.mask_text`)
    for s in (signal.SIGTERM, signal.SIGINT):
        signal.signal(s, lambda *_: stop.set())
    sys.exit(main(sys.argv[1:]))
