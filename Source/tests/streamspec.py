"""The RTSP accounts' declarations, as the product's specs spell them (ADR-0031, the addendum of 2026-10-07) — for the
tests of the code that reads them, while the course's YAML does not carry them yet (its bytes are «Паритет»'s to lay).

`declared()` loads the course's `vms.subsystem.yaml` and `live.subsystem.yaml`, adds the product's lines for these keys in
Python, builds the specs (`SubsystemSpec.from_dict`) and puts them in this process's catalogue — what the code reads its
declarations from (`w2cplatform.domain.declared`, `catalog.spec`); on the way out the catalogue holds what it held."""
from __future__ import annotations

import contextlib
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))       # Source/

# vms.subsystem.yaml of the product: secrets.readers, domain.books, domain.kept, domain.names, domain.keys
VMS_READERS = {"domain/vms/stream-clients/": ["domainpart"],
               "domain/vms/stream-accounts": ["domainagent", "domainpart", "domain"]}
VMS_BOOK = "stream-accounts"
VMS_KEPT = "stream-clients/"
VMS_NAMES = {"stream-clients/": {"exclusive_with": "domain/users", "grant": "view"}}
VMS_KEYS = [{"id": "stream-clients", "prefix": "domain/vms/stream-clients/"},
            {"id": "stream-accounts", "keys": ["domain/vms/stream-accounts"], "prefix": "domain/vms/stream-accounts/"}]
# live.subsystem.yaml of the product: secrets.reads
LIVE_READS = ["domain/vms/stream-clients/", "domain/vms/stream-accounts"]


def _yaml(name: str) -> dict:
    from w2cplatform import specyaml
    return specyaml.load(os.path.join(HERE, "vms", f"{name}.subsystem.yaml"))


def specs(readers: bool = False):
    """`(vms, live)` built from the course's YAML and the product's lines. `readers`: the product's `secrets.readers` too
    — which the course's rights generator holds to the rights it makes (`cluster.rights.check_secrets`)."""
    from w2cplatform.spec import SubsystemSpec
    vms, live = _yaml("vms"), _yaml("live")
    d = vms["domain"]
    books = d.get("books") or {}
    d["books"] = {**books, VMS_BOOK: {}} if isinstance(books, dict) else [*books, VMS_BOOK]
    d["kept"] = [*(d.get("kept") or []), VMS_KEPT]
    d["names"] = dict(VMS_NAMES)
    d["keys"] = [*(d.get("keys") or []), *VMS_KEYS]
    if readers:
        vms.setdefault("secrets", {}).setdefault("readers", {}).update(VMS_READERS)
    live["secrets"] = {"reads": list(LIVE_READS)}
    return SubsystemSpec.from_dict(vms), SubsystemSpec.from_dict(live)


@contextlib.contextmanager
def declared(in_vms=True, in_live=True):
    """The catalogue with the product's lines in the VMS's spec (`in_vms`) and the gateway's (`in_live`)."""
    import vms.config  # noqa: F401 — the course's specs, loaded: what the catalogue holds again on the way out
    from w2cplatform import catalog
    was = {n: catalog.spec(n) for n in ("vms", "live")}
    v, l_ = specs()
    try:
        if in_vms:
            catalog.register(v)
        if in_live:
            catalog.register(l_)
        yield v, l_
    finally:
        for s in was.values():
            catalog.register(s)
