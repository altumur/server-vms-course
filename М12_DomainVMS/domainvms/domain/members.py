"""Who the domain's members are — written where they are decided, read by every pass.

Until now the list of members was configuration: the environment of the domain's processes (`CLUSTERS`,
`name=report`). A camera that enrolled (Lesson 6) got its certificate and stayed unknown to the domain until
somebody edited that environment and restarted the processes; a camera that left stayed listed. So the
decision is written where it is made: the registrar that admits a box adds it (`Registrar(members=...)`), a
leave removes it, and every pass of the domain — the console's and the books' — reads the record and follows
it without a restart (`apply`): a new member is read from its reports, a departed one is dropped, whatever
report it left behind.

`CLUSTERS` keeps what only configuration can say: how to reach the clusters the domain reads DIRECTLY — its own
and the server rooms. Members that report — cameras, and any cluster the domain cannot dial — are here.

    domain/members   in the domain cluster's Variables: {"doc": {rev, members: {name: {how, serial, since, by}}}}
                     (not the object prefix `domain/members/<member>/` where the reports themselves land)

Three rules the product found (feedback AN):

    the first write carries the configuration   the members the configuration named are written into the list
                                                 as `how: configuration` by its FIRST write — else the first
                                                 admission would make every configured member a stranger
    the domain's own cluster                     is neither admitted nor removed: 400
    who is knocking                              a cluster whose reports are in the domain's store and that is not
                                                 on the list: not read, but named (`knocking`), with when it last
                                                 reported, for a person to accept. Its report could only be
                                                 written with a domain identity, so accepting it admits nobody
                                                 the signer has not already vouched for
"""
from __future__ import annotations

import json
import time

from cluster.variables import Conflict

MEMBERS = "domain/members"


def member_name(serial: str) -> str:
    """The cluster a camera of the platform is: `cam-<serial>` (Lesson 10)."""
    return f"cam-{serial}"


class Members:
    def __init__(self, domain_vars, wall=time.time, configured=None, domain: str | None = None):
        """`configured()`: the reporting members the configuration names — carried into the list by its first
        write. `domain`: the domain's own cluster, which is not a member to admit or remove."""
        self.vars, self.wall = domain_vars, wall
        self.configured, self.domain = configured or (lambda: []), domain

    def read(self) -> dict:
        items, _ = self.vars.get(MEMBERS)
        doc = json.loads(items["doc"]) if items and items.get("doc") else {}
        return {"rev": int(doc.get("rev", 0)), "members": dict(doc.get("members", {}))}

    def names(self) -> list[str]:
        return sorted(self.read()["members"])

    def _refuse_domain(self, name: str) -> None:
        if self.domain and name == self.domain:
            from .api import ApiError
            raise ApiError(400, f"{name} is the domain's own cluster: it is neither admitted nor removed")

    def _change(self, mutate) -> bool:
        for _ in range(10):
            items, idx = self.vars.get(MEMBERS)
            doc = self.read()
            members = dict(doc["members"])
            if doc["rev"] == 0:                          # the first write: the configuration comes along
                for n in self.configured():
                    if n != self.domain:
                        members.setdefault(n, {"how": "configuration", "serial": None, "since": self.wall(), "by": None})
            if not mutate(members):
                return False
            try:
                self.vars.put(MEMBERS, {"doc": json.dumps({"rev": doc["rev"] + 1, "members": members}, sort_keys=True)},
                              cas=idx)
                return True
            except Conflict:
                continue
        raise Conflict("the list of members kept changing underneath the write")

    def add(self, name: str, how: str, serial: str | None = None, by: str | None = None) -> bool:
        """Admitted — by a voucher, or by a person who approved it. Adding one already there changes nothing."""
        self._refuse_domain(name)

        def mutate(m):
            if name in m:
                return False
            m[name] = {"how": how, "serial": serial, "since": self.wall(), "by": by}
            return True
        return self._change(mutate)

    def remove(self, name: str, by: str | None = None) -> bool:
        self._refuse_domain(name)
        return self._change(lambda m: m.pop(name, None) is not None)

    def knocking(self, domain_objects) -> list[dict]:
        """Clusters that report into the domain's store and are not on the list — once the list is written.
        Each with when it last reported (its own clock) and how many reports it has left."""
        from .uplink import REPORTED, UPLINK
        doc = self.read()
        if doc["rev"] == 0:
            return []
        out = []
        for key in domain_objects.list(f"{UPLINK}/"):
            name, _, sub = key[len(UPLINK) + 1:].partition("/")
            if sub != REPORTED or name in doc["members"] or name == self.domain:
                continue
            raw = domain_objects.get(key)
            mark = json.loads(raw) if raw else {}
            out.append({"name": name, "reported": mark.get("ts"), "reports": mark.get("seq")})
        return sorted(out, key=lambda x: x["name"])


def apply(fed, members: Members, domain_objects, topology=None, lost_after: float = 45.0, wall=None) -> dict[str, list]:
    """Make the domain's federation hold exactly the members the record names — besides the clusters it reads
    directly, which configuration keeps. A newcomer is read from its reports (through its relay, if the
    topology says so); one that left is dropped. Never written: the configuration stands."""
    from .uplink import _CopyObjects, member_copy
    doc = members.read()
    if doc["rev"] == 0:
        return {"joined": [], "left": []}
    names = set(doc["members"])
    joined = sorted(n for n in names if n not in fed.clusters)
    for n in joined:
        fed.add(member_copy(n, domain_objects, lost_after=lost_after, wall=wall or time.time,
                            via=topology.via(n) if topology is not None else None))
    left = sorted(n for n, c in list(fed.clusters.items()) if isinstance(c.objects, _CopyObjects) and n not in names)
    for n in left:
        del fed.clusters[n]
    return {"joined": joined, "left": left}
