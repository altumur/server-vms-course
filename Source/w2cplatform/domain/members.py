"""Who the domain's members are — written where they are decided, read by every pass.

Until now the list of members was configuration: the environment of the domain's processes (`CLUSTERS`,
`name=report`). A box that enrolled (Lesson 6) got its certificate and stayed unknown to the domain until
somebody edited that environment and restarted the processes; a box that left stayed listed. So the
decision is written where it is made: the registrar that admits a box adds it (`Registrar(members=...)`), a
leave removes it, and every pass of the domain — the console's and the books' — reads the record and follows
it without a restart (`apply`): a new member is read from its reports, a departed one is dropped, whatever
report it left behind.

`CLUSTERS` keeps what only configuration can say: how to reach the clusters the domain reads DIRECTLY — its own
and the server rooms. Members that report — small boxes, and any cluster the domain cannot dial — are here.

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

from w2cplatform.rows import PARSE_ERRORS
from w2cplatform.variables import Conflict

MEMBERS = "domain/members"


class Members:
    def __init__(self, domain_vars, wall=time.time, configured=None, domain: str | None = None, journal=None):
        self.journal = journal                        # who admitted whom, with the key the person saw (feedback CL, CJ)
        """`configured()`: the reporting members the configuration names — carried into the list by its first
        write. `domain`: the domain's holder, which is not a member to admit or remove."""
        self.vars, self.wall = domain_vars, wall
        self.configured, self.domain = configured or (lambda: []), domain

    # A list that does not parse (М10's seventh review: `Members.read` is the first step of the signer's books, of the
    # domain's member pages and of following the members) is read as NOT WRITTEN — `rev 0`, nobody joins, nobody is
    # dropped — and says so (`unreadable`), logged once. It is never written over by `settle` or a change: the list is
    # a record, and a record nobody can read is mended by a person, not replaced by the configuration.
    def read(self) -> dict:
        from .federation import MEMBER_OBJECTS
        items, _ = self.vars.get(MEMBERS)
        try:
            doc = json.loads(items["doc"]) if items and items.get("doc") else {}
            out = {"rev": int(doc.get("rev", 0)), "members": dict(doc.get("members", {}))}
        except PARSE_ERRORS as e:
            MEMBER_OBJECTS.garbled(MEMBERS, e)
            return {"rev": 0, "members": {}, "unreadable": str(e)}
        MEMBER_OBJECTS.parsed(MEMBERS)
        return out

    def names(self) -> list[str]:
        return sorted(self.read()["members"])

    def settle(self) -> bool:
        """Write the list if nobody ever has — the configuration's members, as the first write carries them
        — so that it is a record and not a property of this holder's processes (Lesson 15, feedback AS)."""
        doc = self.read()
        return doc["rev"] == 0 and not doc.get("unreadable") and self._change(lambda members: True)

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
            if doc.get("unreadable"):
                raise Conflict(f"the list of members ({MEMBERS}) does not parse ({doc['unreadable']}): mend it first — "
                               f"a change written over it would drop every member it names")
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

    def add(self, name: str, how: str, serial: str | None = None, by: str | None = None, key: str | None = None,
            seal: str | None = None) -> bool:
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
            m[name] = {"how": how, "serial": serial, "since": self.wall(), "by": by, **({"key": key} if key else {}),
                       **({"seal": seal} if seal else {})}
            return True
        done = self._change(mutate)
        if done and self.journal is not None:
            self.journal.say("domain.member.admitted", user=by or how, target=name, how=how, **({"key": key} if key else {}))
        return done

    def _revoked_keys(self) -> set:
        from .agent import KEYS_PATH
        from .api import ApiError
        from w2cplatform.trust.tokens import KeySet
        items, _ = self.vars.get(KEYS_PATH)
        try:
            return KeySet.from_items(items).revoked_members if items else set()
        except PARSE_ERRORS as e:                        # not known is not "none revoked": the admission waits (the review's eighth pass)
            raise ApiError(503, f"the domain's key set does not parse ({e}): whether this key was revoked after a theft "
                                f"cannot be checked, so nobody is admitted with a key until it is mended") from None

    # A member admitted without a key — one the configuration named — asks the domain's door with none, and is answered
    # nothing (`carry.HolderDoor`). Its key is registered here, by a person on the holder, as its agent printed it at its
    # first start: the signing key and the sealing key, once. A key it has is never replaced this way.
    def set_key(self, name: str, key: str, seal: str, by: str | None = None) -> bool:
        if key in self._revoked_keys():
            from .api import ApiError
            raise ApiError(409, f"{name}: this key was revoked by the domain's root after a theft")

        def mutate(m):
            row = m.get(name)
            if row is None or row.get("key"):
                return False
            m[name] = {**row, "key": key, "seal": seal}
            return True
        done = self._change(mutate)
        if done and self.journal is not None:
            self.journal.say("domain.member.key", user=by or "?", target=name, key=key)
        return done

    def remove(self, name: str, by: str | None = None) -> bool:
        self._refuse_domain(name)
        done = self._change(lambda m: m.pop(name, None) is not None)
        if done and self.journal is not None:
            self.journal.say("domain.member.left", user=by or "?", target=name)
        return done

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
        try:
            return json.loads(items["doc"]).get("root") or None
        except PARSE_ERRORS:
            return None                                  # a root nobody can read is no root to compare with (the seventh review)

    def pinned(self, name: str, domain_objects, own: str | None = None) -> dict:
        """{"root": "this" | "another" | None, "keys_rev": n | None}, from the member's last report."""
        from .agent import KEYS_PATH, ROOT_PATH
        from .uplink import base
        own = self.own_root() if own is None else own

        def row(path):
            raw = domain_objects.get(base(name) + "v/" + path)
            try:
                got = (json.loads(raw).get("items") or {}) if raw else {}
            except PARSE_ERRORS:
                got = {}                                 # that report's row does not parse: it says nothing (the seventh review)
            return got if isinstance(got, dict) else {}
        pub, keys = row(ROOT_PATH).get("pub"), row(KEYS_PATH)
        try:
            rev = json.loads(keys["doc"]).get("rev") if keys.get("doc") else None
        except PARSE_ERRORS:
            rev = None
        return {"root": None if not (own and pub) else ("this" if pub == own else "another"), "keys_rev": rev}

    # ADMITTED BY THE KEY IT PRESENTS (ADR-0032). A knocking member's report mark carries the keys its agent presents
    # (`uplink.report`); the person who accepts it has compared the key's fingerprint with the one the box itself
    # shows, and the page sends what it showed (`fingerprint`). Accepted, the member is listed WITH that key — its door
    # opens to it from the next ask (`carry.HolderDoor`) — and a fingerprint that is not the key the mark holds now is
    # refused: somebody else is knocking under that name. A mark with no key admits the member without one, as the
    # configuration's members are listed, and its key is registered on the holder later (`set_key`).
    def accept(self, name: str, by: str | None, domain_objects=None, fingerprint: str | None = None) -> bool:
        """A person accepts a cluster that is knocking. Refused (409) when its report says it pinned another root:
        accepting it would list a member that takes nothing this domain signs."""
        from .api import ApiError
        presented = self.presented(name, domain_objects) if domain_objects is not None else {}
        if domain_objects is not None and self.pinned(name, domain_objects)["root"] == "another":
            raise ApiError(409, f"{name} pinned another root than this domain's: it refuses this domain's key set. "
                                f"Enroll it again; accepting it would not make it a member")
        if fingerprint is not None and fingerprint != presented.get("fingerprint"):
            raise ApiError(409, f"{name} presents another key than the one whose fingerprint was compared "
                                f"({presented.get('fingerprint') or 'none'}, not {fingerprint}): look again before admitting it")
        return self.add(name, how=f"accepted by {by}", by=by, key=presented.get("key"), seal=presented.get("seal"))

    @staticmethod
    def presented(name: str, domain_objects) -> dict:
        """The keys `name` presents on its last report mark: {key, seal, fingerprint} — {} when it presents none."""
        from .federation import published
        from .uplink import REPORTED, base
        mark = published(name, base(name) + REPORTED, domain_objects.get(base(name) + REPORTED)) or {}
        key, seal = mark.get("key"), mark.get("seal")
        if not isinstance(key, str) or not isinstance(seal, str):
            return {}
        try:
            return {"key": key, "seal": seal, "fingerprint": fingerprint(key)}
        except ValueError:
            return {}                                    # a key that is no hex is no key to admit by

    def knocking(self, domain_objects) -> list[dict]:
        """Clusters that report into the domain's store and are not on the list — once the list is written.
        Each with when it last reported (`last`, its own clock), how many reports it has left (`times`), the key it
        presents with its fingerprint, and which root it pinned (`pinned`) — the product's words."""
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
            from .federation import published
            mark = published(name, key, raw) or {}        # a mark nobody can read: knocking, with no time (the seventh review)
            shown = {k: v for k, v in self.presented(name, domain_objects).items() if k != "seal"}
            out.append({"name": name, "last": mark.get("ts"), "times": mark.get("seq"), **shown,
                        **self.pinned(name, domain_objects, own)})
        return sorted(out, key=lambda x: x["name"])


def fingerprint(key_hex: str) -> str:
    """A member's public key as a person compares it with the one its box shows: the first eight bytes of its
    SHA-256, in hex — the product's `trust.Fingerprint`."""
    import hashlib
    return hashlib.sha256(bytes.fromhex(key_hex)).hexdigest()[:16]


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


# On the holder: `PLATFORM_STORE=… python3 -m w2cplatform.domain.members key <member> <pub> <seal_pub>` — the keys its
# agent printed at its first start. ON A FRESH DOMAIN TOO (the scenario «камера — офис — центр», O1): the list of members
# is written by its first change, and that first write carries the members the configuration names (`CLUSTERS`, as the
# domain's processes read it: `runtime.names_from_env`) — the command built the list with no configuration, nobody had
# written it yet, and a member of `CLUSTERS` was "not registered — no such member". The product lists the members of
# `CLUSTERS` from the start (`Membership.Configured`).
def main(argv: list[str], env=None) -> int:
    import os
    import sys

    from w2cplatform.variables import open_vars
    from .runtime import names_from_env
    env = os.environ if env is None else env
    if len(argv) != 4 or argv[0] != "key":
        print("usage: python3 -m w2cplatform.domain.members key <member> <pub> <seal_pub>", file=sys.stderr)
        return 2
    holder, reporting = names_from_env(env=env)
    m = Members(open_vars(env["PLATFORM_STORE"]), configured=lambda: reporting, domain=holder)
    done = m.set_key(argv[1], argv[2], argv[3], by="the holder's operator")
    print(f"{argv[1]}: {'key registered' if done else 'not registered — no such member, or it has a key'}")
    return 0 if done else 1


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
