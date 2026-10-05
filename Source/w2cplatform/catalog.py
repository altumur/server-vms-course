"""The subsystems this process knows: the specs it loaded, and nothing else (ГРАНИЦА-ПЛАТФОРМЫ-И-ПОДСИСТЕМЫ.md §1, §2.3).

    SPEC_DIR    a directory of `<sub>.subsystem.yaml`: what a process of the platform's own (`python3 -m w2cplatform`)
                runs from, and what any process reads when it has loaded no spec by itself

Whatever the platform used to know by name — which objects are rows of the store, which words of an address carry a
login — it reads here, from the specs this process holds: one a subsystem loaded (`SubsystemSpec.load` puts it in),
or the directory `SPEC_DIR` names. A spec built from a dict in code (`SubsystemSpec.from_dict`: a test's, a probe's)
is nobody's catalogue.
"""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # catalog.py — the loaded specs, by name
#
# **Role in the module.** The boundary's step 4: a string a subsystem needs the platform to treat in some way is a key
# of its spec, and the platform's code asks the catalogue for it. Step 5: the platform's own entry point loads a
# directory of specs and runs its processes for each (`host.py`).
#
# - `register(spec)` — a spec this process loaded. A second spec of one name replaces the first (a test that loads a
#   changed copy); `version` moves, so what was derived from the old one is derived again.
# - `load_dir(path)` — every `*.subsystem.yaml` of a directory, in name order; refused when there is none: a process
#   told to run from an empty directory runs nothing, and says so at its start rather than idling.
# - `specs()` / `spec(name)` — what is loaded; with nothing loaded, the directory `SPEC_DIR` names first.
# - `object_rows()` — the objects that are rows of the store (`objects.rows` of every spec, under its name).
# - `door_objects()` — the files a resource's door gives the other servers (`objects.door`, `domain.reports`).
# - `heartbeat_strings(sub)` — the fields of a subsystem's heartbeats that are strings (`heartbeat.strings`).
# - `secret_rules()` — how an address carries a login (`secret_in` of every url field of every spec, together).
# ================================================================================================
from __future__ import annotations

import glob
import os
import threading

SPEC_DIR = "SPEC_DIR"

_lock = threading.Lock()
_loaded: dict = {}               # name -> SubsystemSpec
version = 0                      # moves with every register: what is derived from the catalogue is derived again
_derived: dict = {}              # (what, version) -> the value derived


def register(spec) -> None:
    global version
    with _lock:
        _loaded[spec.name] = spec
        version += 1
        _derived.clear()


def load_dir(path: str) -> list:
    from .spec import SubsystemSpec
    files = sorted(glob.glob(os.path.join(path, "*.subsystem.yaml")))
    if not files:
        raise ValueError(f"{SPEC_DIR}={path}: no <sub>.subsystem.yaml there — the platform runs from the specs it is "
                         f"given and from nothing else")
    return [SubsystemSpec.load(f) for f in files]


def specs(env: dict | None = None) -> list:
    if not _loaded:
        path = (os.environ if env is None else env).get(SPEC_DIR)
        if path:
            load_dir(path)
    with _lock:
        return [_loaded[n] for n in sorted(_loaded)]


def spec(name: str, env: dict | None = None):
    for s in specs(env):
        if s.name == name:
            return s
    raise ValueError(f"no subsystem {name!r} among the specs this process loaded "
                     f"({', '.join(s.name for s in specs(env)) or 'none'}; {SPEC_DIR})")


def _derive(what: str, make):
    key = (what, version)
    got = _derived.get(key)
    if got is None:
        got = _derived[key] = make()
    return got


# `objects.rows` of every spec, each under its subsystem's name: `<sub>/commands/*` — the objects kept as rows of the
# store, not as files (`w2cplatform/cluster/objectstore.py`).
def object_rows() -> tuple[str, ...]:
    return _derive("rows", lambda: tuple(f"{s.name}/{p}" for s in specs() for p in s.object_rows))


# A key by a pattern of the specs' objects: segment by segment, `*` one segment, a last `*` the rest (one at least).
def matches(pattern: str, key: str) -> bool:
    p, k = pattern.split("/"), key.split("/")
    for i, seg in enumerate(p):
        if i == len(p) - 1 and seg == "*":
            return len(k) > i and all(k[i:])
        if i >= len(k) or not k[i] or seg not in ("*", k[i]):
            return False
    return len(k) == len(p)


# The files of every spec a resource's door gives the other servers, each under its subsystem's name (`resource.
# door_readable`): its `objects.door`, and what its domain section says a member reports and who witnesses a unit
# (`domain.reports`, `domain.witness`) — the member's agent reads them on whichever server it runs.
def door_objects() -> tuple[str, ...]:
    def make():
        out = []
        for s in specs():
            out += [f"{s.name}/{p}" for p in s.object_door]
            if s.domain is not None:
                out += [f"{s.name}/{r}*" if r.endswith("/") else f"{s.name}/{r}" for r in s.domain.reports]
                out += [f"{s.name}/{s.domain.witness}/*"] if s.domain.witness else []
        return tuple(dict.fromkeys(out))
    return _derive("door", make)


# `heartbeat.strings` of the subsystem `sub`: the fields of its heartbeats a reader takes as strings, or the heartbeat
# is garbled (`contract.parse_heartbeat`). A subsystem no spec here names has none but the platform's.
def heartbeat_strings(sub: str) -> tuple[str, ...]:
    return _derive("heartbeat_strings", lambda: {s.name: s.heartbeat_strings for s in specs()}).get(sub, ())


# The `secret_in` of every url field of every spec, as one set of rules: what hides an address wherever one is said
# (`secrets.hide_in_url`), and what a door that is no spec's field asks (`secrets.address_refusal`).
def secret_rules():
    from .secrets import NO_RULES
    def make():
        out = NO_RULES
        for s in specs():
            for f in s.fields.values():
                if f.rules is not None:
                    out = out | f.rules
        return out
    return _derive("secrets", make)
