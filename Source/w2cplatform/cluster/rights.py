"""The configstore's rights file, generated from the specs of the catalogue: who may read, write and delete which rows,
by the socket a process came through.

    python3 -m w2cplatform.cluster rights                    # print it      (SPEC_DIR: the specs it is generated from)
    python3 -m w2cplatform.cluster rights --check FILE       # exit 1 when FILE is not what the specs generate now

The daemon opens one socket per role (`/run/configstore/<role>.sock`) owned by the role's group; a unit joins that
group (`SupplementaryGroups=`), so the socket a process could open IS its role, and the daemon asks this file before
anything is forwarded or applied (`w2cplatform/storemachine.py`, `Rights`). The file is installed as
`/etc/w2c/configstore-rights.json` and committed as `deploy/cluster/configstore-rights.json`;
`tests/cluster/test_policies.py` holds it to the code both ways, and to every write and read the module's stand makes.

THE ROLES OF EVERY PROCESS ARE THE SPECS' (§3 row 8 of the boundary note): for each subsystem of the catalogue a
controller (`<sub>controller`, `acl_controller`) and a worker (`<sub>worker`, `acl_worker_role` — its spec's `worker:`
says what it touches beyond its claims), and the platform's own: the console (every spec's `acl_console`), the resource,
the domain's. WRITES come from those lists and, of the objects, only what is still a row: the keys the specs name rows
(`objects.rows`, `objectstore.is_row`). Every other object is a file on its writer's server (`cluster://`), and no grant
names it. A role deletes what it writes; the store refuses the two deletes nobody does whatever the file says (an epoch
row, and `domain/*` but by the domain's own roles). READS are the lists below, each with the code that makes it.
"""
from __future__ import annotations

import json
import os
import sys

from w2cplatform import catalog
from w2cplatform.access import DOMAIN_MARKS, MEMBER_MARK, TRUST_KEYS
from w2cplatform.contract import DECOMMISSION, SCHEMA_KEY
from w2cplatform.door import KEYS_KEY, SIGNER_KEY
from w2cplatform.resource import DOORS, MIRROR_KEY, SPACE_KEY

from .objectstore import ROWS_PREFIX, is_row

OBJECTS = ROWS_PREFIX + "/"    # the rows of the create-only objects, a worker's mark before it acts (`objectstore`)

# Whose each socket is (the product's format): the platform's own roles `w2c-<role>`, a subsystem deployment's
# `<deployment>-<role>` — the directory the specs ship in (`SPEC_DIR`'s name), unless `ROLE_GROUP` says otherwise.
# The console and the domain are the platform's processes (ADR 0014: `python3 -m w2cplatform console`; the owner, 4 Oct:
# "the domain is a platform service"), and so is every subsystem's controller (`python3 -m w2cplatform controller <sub>`,
# ADR 0023): its role keeps the spec's name, `<sub>controller`, and its socket is the platform's, `w2c-<sub>controller`.
PLATFORM = ("resource", "console", "domain", "domainconsole", "domainagent")

# The domain's keys (`domain/signer`: the token key and the issuing key) are read by the domain's own processes alone —
# not by its agent in a member cluster, nor by a member's report, both of which read `domain/*`.
SIGNER_KEYS = "!domain/signer*"


def group(role: str, deployment: str, platform: bool = False) -> str:
    return ("w2c-" if platform or role in PLATFORM else f"{deployment}-") + role


def _rows(objects: list[str]) -> list[str]:
    """Of a list of object prefixes, the ones that are rows in the store: `objects/<key>` for the create-only keys."""
    return [OBJECTS + p for p in objects if is_row(p)]


def _gate() -> list[str]:
    """What the console's gate reads on every request in a cluster that may be a domain's member (М10A Lesson 15): the
    key set and every row that marks a member (`access.TRUST_KEYS`, `DOMAIN_MARKS`), the grants by cluster too."""
    return [TRUST_KEYS, *DOMAIN_MARKS, "domain/grants/*"]


def _worker_objects(spec) -> list[str]:
    """A worker's objects that are rows: its marks before it acts, the places it opened (`catalog.rows_of`)."""
    return _rows(list(dict.fromkeys(spec.sub.acl_objects_worker() + [spec.sub.config(p) for p in catalog.rows_of(spec)])))


# The subsystems a controller of `spec` reads beside its own: what its units are about, what it places near, what a
# field of its rows points at — each a reference the spec declares, read on every pass.
def _referred(spec, names: set[str]) -> list[str]:
    out = {spec.about_sub, spec.near if spec.near != "none" else ""}
    for f in spec.fields.values():
        if f.ref:
            out.add(f.ref.split("/", 1)[0])
    return sorted(s for s in out if s and s != spec.name and s in names)


def roles(specs: list, deployment: str) -> dict[str, dict]:
    """`{role: {group, read, write, delete}}` — the whole file's content, for the specs given; `deployment` names the
    groups of the subsystems' roles (`group`)."""

    def role(name: str, write: list[str], read: list[str], delete: list[str] | None = None, platform: bool = False) -> dict:
        write = list(dict.fromkeys(write))
        return {"group": group(name, deployment, platform), "read": list(dict.fromkeys(read)), "write": write,
                "delete": list(dict.fromkeys(write if delete is None else delete))}

    names = {s.name for s in specs}
    every = [f"{s.name}/*" for s in specs]
    trees = sorted(names | {"console", "audit"})        # whose days a resource reads (`resource.retention_days`)
    out = {
        # The page and the API, one per server: the operator's rows of every subsystem; reads every row of each, the
        # platform's (drain, decommission, the doors /servers shows), the gate's — and every worker's mark before it
        # acts (a create-only row): the reaper reads it to tell a request its holder answered from one nobody performed.
        # And the cluster's door key (`door.py`): it makes it the first time it is asked for a door — the seed, sealed,
        # read by the console alone; the public halves every holder reads. It writes the end of a request into its mark
        # (ADR-0054: the reaper's `expired` create-only, `unknown` into a mark whose holder is gone) — the objects of
        # `acl_objects_console` that are rows.
        "console": role("console", [a for s in specs for a in s.acl_console()]
                        + [r for s in specs for r in _rows(s.sub.acl_objects_console())] + [SIGNER_KEY, KEYS_KEY],
                        [SCHEMA_KEY, *every, "platform/*", *_gate(), *[r for s in specs for r in _worker_objects(s)],
                         SIGNER_KEY, KEYS_KEY],
                        # …and deletes what it writes but a mark: a mark is «not more than once» (ADR 0013), and taking
                        # one away opens a second performing — only the holder sweeps marks (`Worker.sweep_marks`) once
                        # the request's row is gone (ADR 0054: the console writes a mark and never deletes one)
                        delete=[a for s in specs for a in s.acl_console()] + [SIGNER_KEY, KEYS_KEY]),
    }
    for s in specs:
        # Placement, one pass at a time and safe at two: its prefixes; reads its subsystem, the ones it refers to, the
        # platform's rows (decommission, the drain).
        out[f"{s.name}controller"] = role(f"{s.name}controller", s.acl_controller(),
                                          [SCHEMA_KEY, f"{s.name}/*", *[f"{r}/*" for r in _referred(s, names)], "platform/*"],
                                          platform=True)
        # The holder: its claims, what its spec says it writes, its marks; reads its subsystem, what its units are about,
        # whether its server is decommissioned (`Worker._claim_slot`), what a holder's door asks (`Gate.gated`: the key
        # set, and `domain/member` while there is none), the door keys its page door checks a token by (`door/keys`) and
        # what its spec says it reads — never the grants.
        rows = _worker_objects(s)
        out[f"{s.name}worker"] = role(f"{s.name}worker", s.acl_worker_role() + rows,
                                      [SCHEMA_KEY, f"{s.name}/*", *([f"{s.about_sub}/*"] if s.about_sub in names else []),
                                       DECOMMISSION + "*", TRUST_KEYS, MEMBER_MARK, KEYS_KEY, *s.worker_reads, *rows])
    # The platform's resource on every server: where it answers for its objects (`platform/doors/<server>`), and its ask to
    # free bytes, a request row of each subsystem whose spec says it frees (`requests: {free: true}`); reads the others'
    # doors, the mirror and the watermark's knobs, every subsystem's days, what a spec's `holds:` table holds and the rows
    # of every unit ABOUT another (whose its buckets are).
    out["resource"] = role("resource", [DOORS + "/*"] + [s.sub.request_key("free-*") for s in specs if s.requests_free],
                           [SCHEMA_KEY, DOORS + "/*", MIRROR_KEY, SPACE_KEY]
                           + [s.sub.config(s.holds["table"], "*") for s in specs if s.holds]
                           + [s.sub.config(s.rows, "*") for s in specs if s.about_sub]
                           + [s.sub.request_key("free-*") for s in specs if s.requests_free]
                           + [f"{t}/{family}{tail}" for t in trees for family in ("retention", "alarms_retention")
                              for tail in ("", "/*")])
    # The domain's roles — its own processes on the holder, its agent in every cluster with `!` denials on what only the
    # holder writes, a subsystem's worker on the domain — are the platform domain's to say, from the specs
    # (`w2cplatform/domain/rights.py`). A member reads nothing of the holder's store: there is no member role.
    from w2cplatform.domain.rights import roles as domain_roles
    out.update(domain_roles(lambda r: group(r, deployment), SCHEMA_KEY, specs))
    check_secrets(specs, out)
    return out


# WHO READS A SECRET ROW IS WHAT THE SPECS SAY (`secrets: {readers, reads}`, the product's key; `spec._secrets`). Here the
# reads are the grants above, so a declaration is held to them, never the other way: the file is not made while a role
# reads a declared row and is not named (a grant that reaches a seed nobody meant it to — a worker's `<sub>/*` over a
# secret kept under its subsystem's name), or is named and reads nothing of it. A spec's `controller`/`worker` is its
# subsystem's; `console`, `domain`, `domainagent`, `resource` are the one role of that name. A row only `reads` names (no
# spec keeps it secret) is held to the worker's grant alone.
def check_secrets(specs: list, out: dict[str, dict]) -> None:
    from w2cplatform.rights import allowed

    def role(spec, name: str) -> str:
        if name == "domainpart":                                # its worker on the domain (`domain/rights.py`)
            return f"{spec.name}domain"
        return f"{spec.name}{name}" if name in ("controller", "worker") else name

    def reading(row: str) -> set[str]:
        key = row + "_" if row.endswith("/") else row          # a prefix: one row under it stands for every row
        return {r for r, grant in out.items() if allowed(grant["read"], key)}

    declared: dict[str, set[str]] = {}
    for s in specs:
        for row, names in s.secret_readers.items():
            declared.setdefault(row, set()).update(role(s, n) for n in names)
    for s in specs:
        for row in s.secret_reads:
            if row in declared:
                declared[row].add(role(s, "worker"))
    faults = []
    for row, want in sorted(declared.items()):
        have = reading(row)
        if have != want:
            faults.append(f"{row}: the specs name {', '.join(sorted(want))} as its readers, and the rights let "
                          f"{', '.join(sorted(have)) or 'nobody'} read it")
    for s in specs:
        for row in s.secret_reads:
            if row not in declared and role(s, "worker") not in reading(row):
                faults.append(f"{row}: {s.name}'s spec says its worker reads it (secrets.reads), and its rights give it "
                              f"no read — `worker.reads` names what it reads")
    if faults:
        raise ValueError("the secret rows the specs declare are not read as they say (secrets.readers, secrets.reads):\n  "
                         + "\n  ".join(faults))


def specs_of(env: dict | None = None) -> tuple[list, str]:
    """The catalogue the file is generated from — `SPEC_DIR`'s specs, loaded (so the create-only keys are known) — and
    the deployment its roles' groups are named by: `ROLE_GROUP`, else the name of the directory the specs ship in."""
    env = os.environ if env is None else env
    if not env.get(catalog.SPEC_DIR):
        raise ValueError(f"{catalog.SPEC_DIR} is not set: the rights are generated from the specs, and from nothing else")
    return (catalog.load_dir(env[catalog.SPEC_DIR]),
            env.get("ROLE_GROUP") or os.path.basename(os.path.normpath(env[catalog.SPEC_DIR])))


def rights(specs: list, deployment: str) -> dict:
    return {"comment": "generated by `python3 -m w2cplatform.cluster rights` from the specs; installed as "
                       "/etc/w2c/configstore-rights.json — do not edit, regenerate",
            "roles": roles(specs, deployment)}


def render(specs: list, deployment: str) -> str:
    return json.dumps(rights(specs, deployment), indent=1, ensure_ascii=False) + "\n"


def main(argv: list[str], env: dict | None = None) -> int:
    try:
        text = render(*specs_of(env))
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    if argv[:1] == ["--check"] and len(argv) == 2:
        with open(argv[1], encoding="utf-8") as f:
            same = f.read() == text
        print(f"{argv[1]}: {'what the specs generate' if same else 'NOT what the specs generate now: regenerate it'}")
        return 0 if same else 1
    if argv:
        print("python3 -m w2cplatform.cluster rights [--check FILE]", file=sys.stderr)
        return 2
    sys.stdout.write(text)
    return 0
