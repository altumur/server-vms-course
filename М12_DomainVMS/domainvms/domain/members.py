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

    domain/members   in the domain holder's Variables: {"doc": {rev, members: {name: {how, serial, since, by}}}}
                     (not the object prefix `domain/members/<member>/` where the reports themselves land)

Three rules the product found (feedback AN):

    the first write carries the configuration   the members the configuration named are written into the list
                                                 as `how: configuration` by its FIRST write — else the first
                                                 admission would make every configured member a stranger
    the domain's holder                     is neither admitted nor removed: 400
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
        write. `domain`: the domain's holder, which is not a member to admit or remove."""
        self.vars, self.wall = domain_vars, wall
        self.configured, self.domain = configured or (lambda: []), domain

    def read(self) -> dict:
        items, _ = self.vars.get(MEMBERS)
        doc = json.loads(items["doc"]) if items and items.get("doc") else {}
        return {"rev": int(doc.get("rev", 0)), "members": dict(doc.get("members", {}))}

    def names(self) -> list[str]:
        return sorted(self.read()["members"])

    def settle(self) -> bool:
        """Write the list if nobody ever has — the configuration's members, as the first write carries them
        — so that it is a record and not a property of this holder's processes (Lesson 15, feedback AS)."""
        return self.read()["rev"] == 0 and self._change(lambda members: True)

    def _refuse_domain(self, name: str) -> None:
        from .api import ApiError
        from .grants import DOMAIN_SCOPE
        if self.domain and name == self.domain:
            raise ApiError(400, f"{name} is the domain's holder: it is neither admitted nor removed")
        if name == DOMAIN_SCOPE:                         # `domain/grants/domain` is the domain's own, not a cluster's
            raise ApiError(400, f"no cluster may be called {name!r}: the name is the domain's own scope")

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

    def add(self, name: str, how: str, serial: str | None = None, by: str | None = None, key: str | None = None) -> bool:
        """Admitted — by a voucher, or by a person who approved it. Adding one already there changes nothing.
        `key`: the public key its LDevID was issued for (hex) — what a new holder signs again when the issuing
        certificate that signed it is revoked (Lesson 15, step 9), and the one key it will sign for this member."""
        self._refuse_domain(name)
        if key and key in self._revoked_keys():
            from .api import ApiError
            raise ApiError(409, f"{name}: this key was revoked by the domain's root after a theft — "
                                f"a machine that came home makes a new key and is admitted with it")

        def mutate(m):
            if name in m:
                return False
            m[name] = {"how": how, "serial": serial, "since": self.wall(), "by": by, **({"key": key} if key else {})}
            return True
        return self._change(mutate)

    def _revoked_keys(self) -> set:
        from .agent import KEYS_PATH
        from .tokens import KeySet
        items, _ = self.vars.get(KEYS_PATH)
        return KeySet.from_items(items).revoked_members if items else set()

    def remove(self, name: str, by: str | None = None) -> bool:
        self._refuse_domain(name)
        return self._change(lambda m: m.pop(name, None) is not None)

    # WHICH ROOT A MEMBER PINNED (Lesson 15, feedback BX). A member pins the root of the first key set its agent
    # is given — in the course, and in the product until enrollment brings the root with it (Lesson 6). So the
    # first pass is a window: whoever answers the agent first becomes its root. The domain cannot close that
    # window; it can SEE what came through it. A member that pinned another root still reports here — it refuses
    # this domain's key set and holder record, and says so — and its report carries the root it holds
    # (`domain/root`, `uplink._rows`). The domain names it, and nobody accepts it: such a member is enrolled
    # again, not admitted. Where the domain has no root (Lessons 4–14) there is nothing to compare.
    def own_root(self) -> str | None:
        from .agent import KEYS_PATH
        items, _ = self.vars.get(KEYS_PATH)
        if not items or "doc" not in items:
            return None
        return json.loads(items["doc"]).get("root") or None

    def pinned(self, name: str, domain_objects, own: str | None = None) -> dict:
        """{"root": "this" | "another" | None, "keys_rev": n | None}, from the member's last report."""
        from .agent import KEYS_PATH, ROOT_PATH
        from .uplink import base
        own = self.own_root() if own is None else own

        def row(path):
            raw = domain_objects.get(base(name) + "v/" + path)
            return (json.loads(raw).get("items") or {}) if raw else {}
        pub, keys = row(ROOT_PATH).get("pub"), row(KEYS_PATH)
        rev = json.loads(keys["doc"]).get("rev") if keys.get("doc") else None
        return {"root": None if not (own and pub) else ("this" if pub == own else "another"), "keys_rev": rev}

    def accept(self, name: str, by: str | None, domain_objects=None) -> bool:
        """A person accepts a cluster that is knocking. Refused (409) when its report says it pinned another root:
        accepting it would list a member that takes nothing this domain signs."""
        from .api import ApiError
        if domain_objects is not None and self.pinned(name, domain_objects)["root"] == "another":
            raise ApiError(409, f"{name} pinned another root than this domain's: it refuses this domain's key set. "
                                f"Enroll it again; accepting it would not make it a member")
        return self.add(name, how=f"accepted by {by}", by=by)

    def knocking(self, domain_objects) -> list[dict]:
        """Clusters that report into the domain's store and are not on the list — once the list is written.
        Each with when it last reported (its own clock), how many reports it has left, and which root it
        pinned (`pinned`)."""
        from .uplink import REPORTED, UPLINK
        doc = self.read()
        if doc["rev"] == 0:
            return []
        out, own = [], self.own_root()
        for key in domain_objects.list(f"{UPLINK}/"):
            name, _, sub = key[len(UPLINK) + 1:].partition("/")
            if sub != REPORTED or name in doc["members"] or name == self.domain:
                continue
            raw = domain_objects.get(key)
            mark = json.loads(raw) if raw else {}
            out.append({"name": name, "reported": mark.get("ts"), "reports": mark.get("seq"),
                        **self.pinned(name, domain_objects, own)})
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
