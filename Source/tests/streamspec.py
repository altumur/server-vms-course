"""The RTSP accounts' declarations (ADR-0031, the addendum of 2026-10-07; ADR-0024) — for the tests of the code that reads
them. The course's YAML carries them in the product's spelling (`vms.subsystem.yaml`: `secrets.readers`, `domain.books`,
`domain.kept`, `domain.names`, `domain.keys`; `live.subsystem.yaml`: `secrets.reads`).

`declared()` puts the course's `vms` and `live` specs, as their YAML says, in this process's catalogue — what the code reads
its declarations from (`w2cplatform.domain.declared`, `catalog.spec`); `undeclared()` the same specs WITHOUT these keys, so
that a test can say what the code does where nothing is declared. On the way out the catalogue holds what it held."""
from __future__ import annotations

import contextlib
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))       # Source/

FAMILY = "domain/vms/stream-"                     # the rows of the accounts: stream-clients/, stream-accounts


def _yaml(name: str) -> dict:
    from w2cplatform import specyaml
    return specyaml.load(os.path.join(HERE, "vms", f"{name}.subsystem.yaml"))


def specs(keys: bool = True):
    """`(vms, live)` as the course's YAML says them — or, `keys=False`, with the accounts' declarations taken out."""
    from w2cplatform.spec import SubsystemSpec
    vms, live = _yaml("vms"), _yaml("live")
    if not keys:
        d = vms["domain"]
        d["books"] = {k: v for k, v in d["books"].items() if k != "stream-accounts"}
        d["kept"] = [k for k in d["kept"] if k != "stream-clients/"]
        d.pop("names", None)
        d["keys"] = [k for k in d["keys"] if not k["id"].startswith("stream-")]
        vms["display"]["keys"] = {k: v for k, v in vms["display"]["keys"].items() if not k.startswith("stream-")}
        vms["secrets"]["readers"] = {r: n for r, n in vms["secrets"]["readers"].items() if not r.startswith(FAMILY)}
        live.pop("secrets", None)
    return SubsystemSpec.from_dict(vms), SubsystemSpec.from_dict(live)


@contextlib.contextmanager
def _registered(keys: bool, in_vms: bool = True, in_live: bool = True):
    import vms.config  # noqa: F401 — the course's specs, loaded: what the catalogue holds again on the way out
    from w2cplatform import catalog
    was = {n: catalog.spec(n) for n in ("vms", "live")}
    v, l_ = specs(keys)
    try:
        if in_vms:
            catalog.register(v)
        if in_live:
            catalog.register(l_)
        yield v, l_
    finally:
        for s in was.values():
            catalog.register(s)


def declared(in_vms=True, in_live=True):
    """The catalogue with the course's specs as they are: the accounts declared."""
    return _registered(True, in_vms, in_live)


def undeclared(in_vms=True, in_live=True):
    """The catalogue with the accounts' declarations taken out of the course's specs."""
    return _registered(False, in_vms, in_live)
