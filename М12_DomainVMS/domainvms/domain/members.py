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
    def __init__(self, domain_vars, wall=time.time):
        self.vars, self.wall = domain_vars, wall

    def read(self) -> dict:
        items, _ = self.vars.get(MEMBERS)
        doc = json.loads(items["doc"]) if items and items.get("doc") else {}
        return {"rev": int(doc.get("rev", 0)), "members": dict(doc.get("members", {}))}

    def names(self) -> list[str]:
        return sorted(self.read()["members"])

    def _change(self, mutate) -> bool:
        for _ in range(10):
            items, idx = self.vars.get(MEMBERS)
            doc = self.read()
            members = dict(doc["members"])
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
        def mutate(m):
            if name in m:
                return False
            m[name] = {"how": how, "serial": serial, "since": self.wall(), "by": by}
            return True
        return self._change(mutate)

    def remove(self, name: str, by: str | None = None) -> bool:
        return self._change(lambda m: m.pop(name, None) is not None)


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
