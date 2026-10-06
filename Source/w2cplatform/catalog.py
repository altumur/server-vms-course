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
# - `register(spec, path)` — a spec this process loaded, and the file it was loaded from. A second spec of one name
#   replaces the first (a test that loads a changed copy); `version` moves, so what was derived from the old one is
#   derived again. `file_of(name)` — the file the name was last loaded from (a copy registered without one keeps it):
#   what lies beside it is the subsystem's (its page `<sub>.shell.html`, `console.page_of`).
# - `load_dir(path)` — every `*.subsystem.yaml` of a directory, in name order; refused when there is none: a process
#   told to run from an empty directory runs nothing, and says so at its start rather than idling. A spec of it whose
#   `near.of`/`near.prefer` neighbour the directory lacks is refused there (`near_known`, ADR 0056).
# - `near_known(spec)` — refuses a spec whose neighbour (`near` with `of` or `prefer`) this catalogue does not hold; the
#   end of `load_dir` and `SpecController`'s start ask it, where the catalogue is whole.
# - `requests_known(spec)` — refuses a spec whose `worker.requests` names a subsystem this catalogue does not hold, its
#   own name, or one that declares no `requests:`; asked where `near_known` is (ADR-0012, ADR-0054).
# - `specs()` / `spec(name)` — what is loaded; with nothing loaded, the directory `SPEC_DIR` names first.
# - `object_rows()` — the objects that are rows of the store (`rows_of` every spec, under its name: its `objects.rows`,
#   and `commands/*` for a spec whose units take requests).
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
_files: dict = {}                # name -> the file it was loaded from
version = 0                      # moves with every register: what is derived from the catalogue is derived again
_derived: dict = {}              # (what, version) -> the value derived


def register(spec, path: str | None = None) -> None:
    global version
    with _lock:
        _loaded[spec.name] = spec
        if path:                 # a copy built in code (a test's changed spec) is still the subsystem whose file it names
            _files[spec.name] = os.path.abspath(path)
        version += 1
        _derived.clear()


def load_dir(path: str) -> list:
    from .spec import SubsystemSpec
    files = sorted(glob.glob(os.path.join(path, "*.subsystem.yaml")))
    if not files:
        raise ValueError(f"{SPEC_DIR}={path}: no <sub>.subsystem.yaml there — the platform runs from the specs it is "
                         f"given and from nothing else")
    loaded = [SubsystemSpec.load(f) for f in files]
    for s in loaded:             # the directory is the catalogue whole: a neighbour it lacks is refused here (ADR 0056)
        near_known(s)
        requests_known(s)        # …and a family its worker files to (ADR-0012, ADR-0054)
    return loaded


def file_of(name: str) -> str | None:
    with _lock:
        return _files.get(name)


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


# The neighbour a spec reads by ITS spec (ADR 0056): `near.of` names a field of theirs, `near.prefer` reads their rows by
# their `rows` and a field's `ref`. A spec whose neighbour this catalogue does not hold is refused, naming it — where the
# catalogue is whole, which is not one file's load (a directory loads in name order, and a follower may come first): the end of
# `load_dir`, and a controller's start (`SpecController`), after its process loaded what it loads. It was a pass's: the
# preference read nothing and placed as if nothing were preferred, in silence (ADR 0012).
def near_known(spec) -> None:
    if spec.near == "none" or not (spec.near_of or spec.near_prefer):
        return
    names = [s.name for s in specs()]
    if spec.near not in names:
        key = "near.prefer" if spec.near_prefer else "near.of"
        raise ValueError(f"spec {spec.name}: {key} reads the spec of {spec.near!r}, and this process loaded none "
                         f"(it loaded {', '.join(names) or 'nothing'}; {SPEC_DIR}) — load {spec.near}'s spec beside it")


# The families a spec's worker files to (`worker: {requests: [<sub>, …]}`, `Worker.file_request`), each a subsystem this
# catalogue holds, not the spec's own, and one that declares `requests:` (ADR-0012, ADR-0054; the fourteenth review,
# minor 9). A typo (`recc`), the subsystem itself, or one with no family loaded as they were: every filing returned True,
# no holder served the row, no reaper ended it (`requests.turn` passes a spec without `requests:`), and rows piled up for
# ever. Asked where the catalogue is whole, as `near_known`: the end of `load_dir`, and a controller's start.
def requests_known(spec) -> None:
    if not spec.worker_requests:
        return
    held = {s.name: s for s in specs()}
    for sub in spec.worker_requests:
        target = held.get(sub)
        why = ("is the spec itself — a worker performs its own units' work, it files to others" if sub == spec.name else
               f"is no subsystem this process loaded (it loaded {', '.join(held) or 'nothing'}; {SPEC_DIR})"
               if target is None else
               "declares no `requests:` — no family there takes a request: none is served, none is ended"
               if not (target.requests or target.requests_free) else None)
        if why:
            raise ValueError(f"spec {spec.name}: worker.requests names {sub!r}, which {why}")


def _derive(what: str, make):
    key = (what, version)
    got = _derived.get(key)
    if got is None:
        got = _derived[key] = make()
    return got


# `objects.rows` of every spec, each under its subsystem's name — the objects kept as rows of the store, not as files
# (`w2cplatform/cluster/objectstore.py`) — and, for a spec whose units take requests (`requests:`), the marks its worker
# writes before it performs one (`commands/*`, `Worker._mark`): create-only ACROSS servers, which only a row is. The
# family is the platform's, and the spec does not have to repeat it: without it a spec that took requests and named no
# rows had its marks as files on each server — two holders on two servers could both perform a request — and on a
# cluster every look that reached a mark raised (`ClusterObjectStore.put_new` refuses a key that is no row).
def rows_of(spec) -> tuple[str, ...]:
    from .contract import COMMANDS
    derived = (f"{COMMANDS}/*",) if spec.requests or spec.requests_free else ()
    return tuple(dict.fromkeys(tuple(spec.object_rows) + derived))


def object_rows() -> tuple[str, ...]:
    return _derive("rows", lambda: tuple(f"{s.name}/{p}" for s in specs() for p in rows_of(s)))


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
