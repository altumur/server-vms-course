"""Wiring for the real processes: the environment the units set, turned into Clusters over the config store
(`open_vars`) and the object store. Run by the tests over the units' own lines
(`test_lesson3_readview_api_gateway.py`); everything it wires is exercised elsewhere."""
from __future__ import annotations

import os

from w2cplatform.variables import open_vars

from .federation import Cluster, Federation


def open_objects(url: str):
    """An object store by its URL: a directory on this box (`file://`, or a bare path) by the platform's own
    `FsObjectStore`; any other scheme — `cluster://`, `http(s)://`, `s3+…` — by the cluster's object store
    (`w2cplatform.cluster.objectstore.open_store`), imported only then. A domain process on a box needs nothing of
    the cluster's to open its own directory."""
    if url.startswith("file://") or "://" not in url:
        from w2cplatform.objects import FsObjectStore
        return FsObjectStore(url[len("file://"):] if url.startswith("file://") else url)
    from w2cplatform.cluster.objectstore import open_store
    return open_store(url)


def federation_from_env(var: str = "CLUSTERS") -> Federation:
    """CLUSTERS=north=configstore:///run/configstore/console.sock|cluster:///data/platform/objects,south=report
    The first entry, or DOMAIN_HOLDER, is the domain holder.

    A bare name (`CLUSTERS=north,south=report`) is THIS server's own cluster: its store by the process's own role
    socket (`PLATFORM_STORE`, which its unit names) and its objects by the platform's `OBJECTS` (`w2c.env`) — so one
    line in `w2c.env` serves the domain's console and a subsystem's domain worker, each through its own socket.

    Each half is a URL with a scheme: the config store (`open_vars` — `configstore://`,
    `file://`, whatever a backend registered) and the object store (`open_objects`).
    Neither half names a vendor in code; a cluster on another orchestrator is a
    different scheme in this one string.

    Every store is opened behind `declared.guarded`: a write that would give one name to two name spaces a spec holds
    apart (`domain.names`) is refused whoever writes it — the domain's own processes and a subsystem's worker alike."""
    from .declared import guarded
    fed = Federation()
    domain = os.environ.get("DOMAIN_HOLDER")
    reporting = []
    for i, entry in enumerate(filter(None, os.environ.get(var, "").split(","))):
        if "=" not in entry:                                           # this server's own: the unit's socket
            fed.add(Cluster(entry, guarded(open_vars(os.environ["PLATFORM_STORE"])), open_objects(os.environ["OBJECTS"]),
                            is_domain_holder=(entry == domain) if domain else i == 0))
            continue
        name, rest = entry.split("=", 1)
        if rest == "report" or rest.startswith("report@"):
            reporting.append((name, rest.partition("@")[2] or None))   # reached by nobody: read from its reports
            continue
        config_url, objects = rest.split("|", 1)
        fed.add(Cluster(name, guarded(open_vars(config_url)), open_objects(objects),
                        is_domain_holder=(name == domain) if domain else i == 0))
    if not fed.clusters:
        raise SystemExit(f"{var} is empty: name at least one cluster")
    # Members that report are, from the first pass on, the ones the domain's list names (`domain/members.py`):
    # the registrar adds what it admits, a leave removes. `name=report` here is where the domain starts before
    # anyone has written that list, and what a site without a registrar declares by hand.
    # `name=report`: a member the domain never opens a connection to (`domain/uplink.py`). Its agent leaves
    # reports in the domain holder's object store, and the domain reads it from there — the product's rule
    # for every small box, and a server room's too when the domain cannot route to it.
    from .uplink import member_copy
    # `name=report@relay`: Lesson 17's summary report — the member reports to that relay, which carries one
    # bundle for all its members into the domain holder. Once the operator has written the domain's topology
    # (`domain/topology`), IT says who reports through whom, and each pass follows it (`topology.apply`); the
    # `@relay` here is only where the domain starts before anyone has.
    for name, via in reporting:
        fed.add(member_copy(name, fed.domain_holder.objects, lost_after=float(os.environ.get("LOST_AFTER", "45")), via=via))
    return fed
