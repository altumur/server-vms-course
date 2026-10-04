"""The configstore's rights file, generated from the spec: who may read, write and delete which rows, by the socket a
process came through.

    python3 -m cluster rights                    # print it
    python3 -m cluster rights --check FILE       # exit 1 when FILE is not what the spec generates now

The daemon opens one socket per role (`/run/configstore/<role>.sock`) owned by the role's group; a unit joins that
group (`SupplementaryGroups=`), so the socket a process could open IS its role, and the daemon asks this file before
anything is forwarded or applied (`w2cplatform/storemachine.py`, `Rights`). The file is installed as
`/etc/w2c/configstore-rights.json` and committed as `deploy/cluster/configstore-rights.json`; `tests/cluster/test_policies.py` holds
it to the code both ways, and to every write and read the module's stand makes.

WRITES come from the code's own lists — `acl_console`, `acl_controller`, `acl_worker`, `WORKER_ACL` — and, of the
objects, only what is still a row: the create-only keys (`objectstore.CREATE_ONLY`, a worker's mark before a device
command). Every other object is a file on its writer's server now (`cluster://`), and no grant names it. A role
deletes what it writes; the store refuses the two deletes nobody does whatever the file says (an epoch row, and
`domain/*` but by the domain's own roles). READS are the list below, each with the code that makes it.
"""
from __future__ import annotations

import json
import sys

from cluster.objectstore import ROWS_PREFIX, is_create_only
from vms.config import (AUTO_SPEC, DET_SPEC, DETJOB_SPEC, LIVE_SPEC, REC_SPEC, SPEC, SURVEY_SPEC, WORKER_ACL,
                        WORKER_OBJECTS)
from vms.recworker import PRIMARIES
from w2cplatform.access import DOMAIN_MARKS, MEMBER_MARK, TRUST_KEYS
from w2cplatform.contract import DECOMMISSION, SCHEMA_KEY
from w2cplatform.resource import DOORS, MIRROR_KEY, SPACE_KEY

OBJECTS = ROWS_PREFIX + "/"    # the rows of the create-only objects, a worker's mark before a device command (`objectstore`)

# Whose each socket is (the product's format): a subsystem's role `vms-<role>`, the platform's own `w2c-<role>` — the
# domain is the platform's (the owner, 4 Oct: "the domain is a platform service").
PLATFORM = ("resource", "domain", "domainagent", "member")

# The domain's keys (`domain/signer`: the token key and the issuing key, М12 `signer.py`) are read by the domain's own
# processes alone — not by its agent in a member cluster, nor by a member's report, both of which read `domain/*`.
# The thirteenth review, major 11 asked for the role; this is the least of the narrowing DOMAIN-PLATFORM.md lists, the
# rest (each member its own rows, the agent's other holder-only keys) is the round that splits М12.
SIGNER_KEYS = "!domain/signer*"


def group(role: str) -> str:
    return ("w2c-" if role in PLATFORM else "vms-") + role


def _rows(objects: list[str]) -> list[str]:
    """Of a list of object prefixes, the ones that are rows in the store: `objects/<key>` for the create-only keys."""
    return [OBJECTS + p for p in objects if is_create_only(p)]


# The subsystems whose buckets a resource may hold — and so whose days it reads (`resource.retention_days`): every
# spec of the VMS, the console's marks, the audit journal. A rights file says keys and prefixes, not `*/retention`,
# so the names are said.
TREES = sorted({s.name for s in (SPEC, LIVE_SPEC, DET_SPEC, REC_SPEC, DETJOB_SPEC, AUTO_SPEC, SURVEY_SPEC)}
               | {"console", "audit"})


def _gate() -> list[str]:
    """What the console's gate reads on every request in a cluster that may be a domain's member (М10A Lesson 15): the
    key set and every row that marks a member (`access.TRUST_KEYS`, `DOMAIN_MARKS`), the grants by cluster too."""
    return [TRUST_KEYS, *DOMAIN_MARKS, "domain/grants/*"]


def roles() -> dict[str, dict]:
    """`{role: {group, read, write, delete}}` — the whole file's content."""
    def role(name: str, write: list[str], read: list[str], delete: list[str] | None = None) -> dict:
        write = list(dict.fromkeys(write))
        return {"group": group(name), "read": list(dict.fromkeys(read)), "write": write,
                "delete": list(dict.fromkeys(write if delete is None else delete))}

    worker_rows = _rows(WORKER_OBJECTS)                                   # the marks before a device command
    rec_rows = _rows(REC_SPEC.sub.acl_objects_worker())                  # none: a recorder commands no device
    out = {
        # The page and the API, one per server: the operator's rows of both subsystems; reads every row of both, the
        # platform's (drain, decommission, the doors /servers shows), and the gate's. And a holder's mark before a
        # device command (`objects/vms/commands/<id>`, a create-only row): the console's reaper reads it to tell a
        # command the holder answered from one nobody performed (`vms/jobs.py`, `_end_command`) — the thirteenth
        # review, major 20: `Forbidden` on every turn, and the command stood.
        "console": role("console", SPEC.acl_console() + REC_SPEC.acl_console(),
                        [SCHEMA_KEY, "vms/*", "rec/*", "platform/*", *_gate(), *worker_rows, *rec_rows]),
        # Placement, one pass at a time and safe at two: its prefixes; reads its subsystem, the other's epochs
        # (`near`, a camera's backup), the platform's rows (decommission, the drain).
        "vmscontroller": role("vmscontroller", SPEC.acl_controller(), [SCHEMA_KEY, "vms/*", "rec/*", "platform/*"]),
        "reccontroller": role("reccontroller", REC_SPEC.acl_controller(), [SCHEMA_KEY, "rec/*", "vms/*", "platform/*"]),
        # The holder: its epochs, slot, holds and devices, and its marks; reads its subsystem, whether its server is
        # decommissioned (`Worker._claim_slot`), and what its playback door asks (`Gate.gated`: the key set, and
        # `domain/member` while there is none) — never the grants or the emergency password's hash.
        "vmsworker": role("vmsworker", WORKER_ACL + worker_rows,
                          [SCHEMA_KEY, "vms/*", DECOMMISSION + "*", TRUST_KEYS, MEMBER_MARK, *worker_rows]),
        # The recorder: its epochs, slot and the volume it holds; reads both subsystems (the workers' rows: what it
        # records; its own), whether its server is decommissioned, and where a camera's primary is (М12).
        "recworker": role("recworker", REC_SPEC.sub.acl_worker() + rec_rows,
                          [SCHEMA_KEY, "rec/*", "vms/*", DECOMMISSION + "*", PRIMARIES, *rec_rows]),
        # The platform's resource on every server: where it answers for its objects (`platform/doors/<server>`); reads
        # the others' doors, the mirror and the watermark's knobs, every subsystem's days, and what a keep holds.
        "resource": role("resource", [DOORS + "/*"],
                         [SCHEMA_KEY, DOORS + "/*", MIRROR_KEY, SPACE_KEY, "rec/recordings/*", "rec/keeps/*"]
                         + [f"{t}/{family}{tail}" for t in TREES for family in ("retention", "alarms_retention")
                            for tail in ("", "/*")]),
        # М12, in a member cluster's store: the domain's agent writes the domain's rows and the relay's, and is the one
        # role of the cluster that deletes `domain/*` (`storemachine.DOMAIN_ROLES`); a member's report reads them —
        # neither the domain's keys (`SIGNER_KEYS`).
        "domainagent": role("domainagent", ["domain/*", "relay/*", SIGNER_KEYS],
                            [SCHEMA_KEY, "domain/*", "relay/*", SIGNER_KEYS]),
        "member": role("member", [], [SCHEMA_KEY, "domain/*", "relay/*", SIGNER_KEYS]),
        # М12, in the DOMAIN HOLDER's store (the thirteenth review, major 11: the signer opened `domain.sock`, which no
        # rights file named, so no daemon opened it — `StoreUnavailable` at its first read and a loop of restarts). The
        # domain's own processes on the holder: the signer (its keys, the key set, the revocations, the people
        # `identity/*`, the books its pass writes) and the domain's console (pending edits, topology, crossings,
        # members) — both by `CLUSTERS`' own line for the holder's cluster, whose snapshot and heartbeats they read too.
        # With the agent, the one role that deletes `domain/*` (`storemachine.DOMAIN_ROLES`).
        "domain": role("domain", ["domain/*", "identity/*"],
                       [SCHEMA_KEY, "domain/*", "identity/*", "relay/*", "vms/*", "rec/*", "platform/*"]),
    }
    return out


def rights() -> dict:
    return {"comment": "generated by `python3 -m cluster rights` from the spec (М11); installed as "
                       "/etc/w2c/configstore-rights.json — do not edit, regenerate",
            "roles": roles()}


def render() -> str:
    return json.dumps(rights(), indent=1, ensure_ascii=False) + "\n"


def main(argv: list[str]) -> int:
    if argv[:1] == ["--check"] and len(argv) == 2:
        with open(argv[1], encoding="utf-8") as f:
            same = f.read() == render()
        print(f"{argv[1]}: {'what the spec generates' if same else 'NOT what the spec generates now: regenerate it'}")
        return 0 if same else 1
    if argv:
        print("python3 -m cluster rights [--check FILE]", file=sys.stderr)
        return 2
    sys.stdout.write(render())
    return 0
