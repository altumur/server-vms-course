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
    PLATFORM_DIR  the platform's state: config/, objects/, events/ (`/data/platform`)
    ARCHIVE       the platform's events archive, the resource's tree (`<PLATFORM_DIR>/events`)
    BOX_ID        which machine (systemd's `%m`): two machines with one hostname are two boxes (`box`)

Not one of these names an orchestrator, and that is the whole point of the
module. A systemd unit sets `WORKER_NAME=w-%l-1` (Quadlet on one box `%i`), and
the platform's env file (`/etc/w2c/w2c.env` — on the course's box a link into
`/data/platform/etc`) the server and its labels; an orchestrator, where a site has
one, maps its own (an allocation index, a node's name, a `fieldRef`) into the
same. The loop reads these names and never learns who filled them in — the same rule the package already keeps for the stores
(see `variables.open_vars`).

The index is a PREFERENCE, never proof: whatever a runtime says, the slot is
still taken by CAS (Lesson 7), and a runtime that hands the same index twice
loses the second claim rather than corrupting the first.
"""
from __future__ import annotations

import os
import socket

SLOT_INDEX, SERVER_NAME, LABELS, INSTANCE_ID = "SLOT_INDEX", "SERVER_NAME", "LABELS", "INSTANCE_ID"
WORKER_NAME, SPARE_FOR = "WORKER_NAME", "SPARE_FOR"
PLATFORM_DIR, ARCHIVE = "PLATFORM_DIR", "ARCHIVE"

# THE PLATFORM'S LAYOUT, each default said once (the owner's decisions, 4 October). All the platform's mutable state
# is under one root on the data partition — `config/` (the file store's rows), `objects/` (heartbeats, the snapshot),
# `events/` (the events archive: the resource's, written by its clients of the group `w2c-events`), and in a
# cluster `configstore/` — and its configuration is `/etc/w2c`, which on an A/B box is a LINK to
# `/data/platform/etc`: /etc is on the root slot an OS update replaces. A unit and the code say `/etc/w2c/…`, never
# the link's target. A subsystem's own paths are its own (`vms/config.py`: `/data/vms/…`, `/etc/vms`).
DATA = "/data/platform"                          # PLATFORM_DIR unset
ETC = "/etc/w2c"                                 # → /data/platform/etc: w2c.env, configstore-rights.json, tls/, secrets/
KEY_FILE = ETC + "/secrets/platform.key"         # the cluster's key ring (`sealing.py`): 0640, group `w2c-secrets`


def platform_dir(env: dict) -> str:
    return env.get(PLATFORM_DIR) or DATA


# The events archive: what a process was given, else `$ARCHIVE` (a key of `w2c.env` — the archive is the
# platform's), else `events/` under the platform's root. Every writer of buckets and the resource ask this one
# function, so the box's archive cannot be in two places by two defaults.
def events_root(env: dict, given: str | None = None) -> str:
    return given or env.get(ARCHIVE) or os.path.join(platform_dir(env), "events")


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


# This incarnation. `None` lets the worker fall back to the base class's `box:pid:6hex` (`instance_on_box`),
# which is enough to tell one instance from the next on a box.
def instance(env: dict) -> str | None:
    return env.get(INSTANCE_ID) or None


# THE BOX, NOT ITS HOSTNAME (the review's eighth pass for a recorder's volume; the owner's decision of 4 Oct for every
# name). What "this instance runs on this machine" is read from — whether a hold follows the name at once
# (`RecWorker.hold_follows_name`), whether a live holder's name may be taken at a start (`Worker._may_take_by_name`).
# Two machines installed from one image, two `localhost`s, have one hostname and compute one `w-%l-1`: by the hostname
# they were one box and took each other's name for ever. `BOX_ID` when the runtime says it (systemd's `%m` in a unit,
# Nomad's `${node.unique.id}`), else this machine's id (`/etc/machine-id`, the product's `BoxID`), else the hostname —
# a machine with neither, as before.
BOX_ID = "BOX_ID"
MACHINE_ID_FILES = ("/etc/machine-id", "/var/lib/dbus/machine-id")


def box(env: dict) -> str:
    said = str(env.get(BOX_ID) or "").strip()
    if said:
        return said
    for path in MACHINE_ID_FILES:
        try:
            with open(path, encoding="ascii") as f:
                mid = f.read().strip()
        except (OSError, UnicodeDecodeError):
            continue
        if mid:
            return mid
    return socket.gethostname()


# The box an instance name says it ran on — `box:pid:rnd`, as `instance_on_box` makes it, or the older `host:pid` (the
# product's `OnThisBox` reads both; М11's bench names its incarnations so) — or None for a name that says none: an
# `INSTANCE_ID` or an allocation's id is a scheduler's, and nothing is guessed from it. Since the thirteenth review a name
# that says no box is never this box's (`Worker._on_this_box`): a live holder's name is taken only on its own box.
def box_of(instance: str) -> str | None:
    parts = str(instance or "").rsplit(":", 2)
    if len(parts) == 2 and parts[0] and parts[1].isdigit():
        return parts[0]
    return parts[0] if len(parts) == 3 and parts[0] and parts[1].isdigit() else None


# This incarnation's name, with the box in it: `INSTANCE_ID` as given — prefixed `<box>:<pid>:` when `BOX_ID` is said,
# so an allocation's id gets a box only from the runtime — else `<box>:<pid>:<6 hex>`.
def instance_on_box(env: dict, given: str | None = None) -> str:
    import os
    import uuid
    said, given = str(env.get(BOX_ID) or "").strip(), given or env.get(INSTANCE_ID) or ""
    if given:
        return f"{said}:{os.getpid()}:{given}" if said else given
    return f"{box(env)}:{os.getpid()}:{uuid.uuid4().hex[:6]}"
