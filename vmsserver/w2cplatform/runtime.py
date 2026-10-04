"""What a runtime hands a process — and nothing about WHICH runtime.

    <ROLE>_NAME   the slot to claim outright: an operator starting one by hand, a
                  StatefulSet ordinal
    WORKER_NAME   else this — what a unit says, one name per server and role
                  (`Environment=WORKER_NAME=w-%l-1`, the product's P4)
    SLOT_INDEX    else the index, which the process turns into `<prefix>-<n>`
    SPARE_FOR     a SPARE, started by `w2c-spares.sh` for a label set: it takes only
                  an offer of that set (`Worker.claim_slot(spare_for=)`), never a
                  name — and with no offer it waits holding nothing
    SERVER_NAME   whose resource this process writes into, and the host in the URLs
                  it publishes
    LABELS        what this server can reach, comma-separated
    INSTANCE_ID   this incarnation — what failover is measured from

Not one of these names an orchestrator, and that is the whole point of the
module. A systemd unit sets `WORKER_NAME=w-%l-1` (Quadlet on one box `%i`), and
the platform's env file (`/etc/w2c/w2c.env`, on the course's box
`/data/config/w2c.env`) the server and its labels; an orchestrator, where a site has
one, maps its own (an allocation index, a node's name, a `fieldRef`) into the
same. The loop reads these names and never learns who filled them in — the same rule the package already keeps for the stores
(see `variables.open_vars`).

The index is a PREFERENCE, never proof: whatever a runtime says, the slot is
still taken by CAS (Lesson 7), and a runtime that hands the same index twice
loses the second claim rather than corrupting the first.
"""
from __future__ import annotations

import socket

SLOT_INDEX, SERVER_NAME, LABELS, INSTANCE_ID = "SLOT_INDEX", "SERVER_NAME", "LABELS", "INSTANCE_ID"
WORKER_NAME, SPARE_FOR = "WORKER_NAME", "SPARE_FOR"


# The slot to prefer: the role's own name (`RECORDER_NAME`, …), else the unit's `WORKER_NAME`, else
# `<prefix>-<index>`, else None — "whichever is free, a lapsed one first", so a replacement inherits the
# assignment. `WORKER_NAME` is read by every role (the product's P4: each unit says it, `w-%l-1`, `r-%l-1`): the
# role's own name was the course's, and a unit written the product's way named nobody.
def slot(env: dict, name_env: str = WORKER_NAME, prefix: str = "w") -> str | None:
    for name in dict.fromkeys((name_env, WORKER_NAME)):
        if env.get(name):
            return env[name]
    if str(env.get(SLOT_INDEX, "")) != "":
        return f"{prefix}-{int(env[SLOT_INDEX])}"
    return None


# The server this process runs on: what a runtime says, else this host's name. On one box the
# hostname is right and no runtime has to say anything.
def server(env: dict, given: str | None = None) -> str:
    return given or env.get(SERVER_NAME) or socket.gethostname()


def labels(env: dict, default: str = "") -> list[str]:
    return [l for l in env.get(LABELS, default).split(",") if l]


# The label set this process is a spare for, or None — not a spare. Set and empty is the EMPTY set (`SPARE_FOR=`): a
# spare for units that ask for no label, which is a set like any other.
def spare_for(env: dict) -> str | None:
    return str(env[SPARE_FOR]) if SPARE_FOR in env else None


# This incarnation. `None` lets the worker fall back to the base class's `hostname:pid:6hex`,
# which is enough to tell one instance from the next on a box.
def instance(env: dict) -> str | None:
    return env.get(INSTANCE_ID) or None
