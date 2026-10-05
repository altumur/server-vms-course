"""Lesson 4 — grants are cluster-local, carry an expiry, and expiry IS the
revocation mechanism.

Each cluster holds `subject X may do Y on unit Z until T` in its own
Variables under domain/grants/*, written by the domain agent (the only
writer of domain/* in that cluster) and read by the cluster's console and
subsystems' doors for people. Enforcement is a local read — no lookup, no token exchange —
which is the only way authorization survives the domain being down. A
cluster whose agent cannot reach the domain lets its grants lapse. That
converts an unbounded revocation window into a number the product states.
Workers never see a user, a grant, or a token: the console and the gateway
are the cluster's clients of them, and those two enforce.

Two lifetimes, and they are not independent: the revocation window is the
SHORTER of the token lifetime and the grant lifetime.
"""
from __future__ import annotations

import time
import unicodedata
from dataclasses import dataclass

from w2cplatform.rows import PARSE_ERRORS, Table, finite

from w2cplatform.trust.tokens import PERSON, KeySet, TokenError, verify

GRANT_LIFETIME = 24 * 3600.0     # Lesson 4 makes students pick and defend it; the product states it


@dataclass(frozen=True)
class Grant:
    subject: str
    capability: str          # "view" | "edit" | "admin"
    # The scope: one unit as the platform names it, `<sub>/<id>` (the boundary's step 2 — it was one subsystem's
    # number, and a grant could name nothing else), or None — every unit in this cluster. A grant on a unit takes in
    # the units ABOUT it (`about:` in their spec): the console's gate asks about both (`access.may_on`).
    unit: str | None
    valid_until: float
    # …or the units that carry ALL of these labels (the product's scope, feedback BP): "the ground floor"
    # without a grant per unit. With labels, `unit` is None and means nothing.
    labels: tuple = ()


class ClusterGrants:
    """One cluster's grants, as its console and gateway hold them in memory
    from domain/grants/* (М9's `grants` table, with valid_until, one level up)."""

    def __init__(self, cluster: str, now=time.time):
        self.cluster, self.now = cluster, now
        self.grants: dict[tuple, float] = {}             # (subject, capability, unit, labels) -> valid until

    def grant(self, subject: str, capability: str, unit: str | None, valid_until: float, labels: tuple = ()) -> None:
        self.grants[(subject, capability, unit, tuple(sorted(labels)))] = valid_until

    def revoke(self, subject: str) -> None:
        self.grants = {k: v for k, v in self.grants.items() if k[0] != subject}

    def may(self, subject: str, capability: str, unit, now: float | None = None, labels=()) -> bool:
        now = self.now() if now is None else now
        for (s, c, u, lab), until in self.grants.items():
            if s != subject or c not in (capability, "admin") or now >= until:
                continue
            # A labelled grant covers a unit that carries all of its labels — and never "every unit": asked about no
            # unit in particular (`unit=None`, no labels), it does not match. A grant on a unit covers that unit and
            # nothing else; one with no unit covers every one (`"*"` included).
            if (set(lab) <= set(labels)) if lab else (u in (unit, None)):
                return True
        return False

    def renew_from_domain(self, renewals: list[Grant]) -> None:
        """The agent carried the domain's current grants for this cluster:
        replace, so a grant the domain dropped is not renewed."""
        self.grants = {(g.subject, g.capability, g.unit, tuple(sorted(g.labels))): g.valid_until for g in renewals}

    def access_ends(self, subject: str, token_exp: float) -> float:
        """State in advance: if a revoke cannot reach this cluster, when does
        `subject` lose it? min(token expiry, latest grant expiry)."""
        untils = [u for (s, *_), u in self.grants.items() if s == subject]
        return min(token_exp, max(untils)) if untils else token_exp


# WHAT A NAME MAY HOLD (the review's eighth pass, major; the coordinator's decision). A grant is the item
# `<subject>|<capability>|<unit:<sub>/<id>, labels:a,b, or nothing>`, and the reader split it on `|` into three: a user called `acme|ivan`
# made FOUR, the split raised, and every grant of the row went with it — `domain_may` raised on every `/api/*` of the
# domain's door, for the admin too, and the command that mends the grants raised the same way. `|`, `"` and the
# control characters (a newline above all) are not allowed in a user's name, a grant's subject or a label: refused
# where a user is created (`IdentityStore.create_local`, `create_federated`) and wherever a grant is written (every
# write goes through `grants_to_items`: `publish_grants`, `set_domain_grants`, `python -m w2cplatform.domain.grants`). A label
# may not hold `,` either — the labels of a grant are listed with it.
class BadName(ValueError):
    """A name with a character the domain does not allow in it."""


def name_refused(name, what: str = "name", also: str = "") -> str | None:
    """Why `name` is not a name — None when it is one."""
    if not isinstance(name, str) or not name:
        return f"a {what} is a non-empty string"
    bad = sorted({c for c in name if c in '|"' + also or unicodedata.category(c) in ("Cc", "Zl", "Zp")})
    if bad:
        return f"a {what} may not hold {', '.join(repr(c) for c in bad)}: {name!r}"
    return None


def refuse_name(name, what: str = "name", also: str = "") -> None:
    why = name_refused(name, what, also)
    if why:
        raise BadName(why)


def _item(g: Grant) -> str:
    return f"{g.subject}|{g.capability}|" + ("labels:" + ",".join(sorted(g.labels)) if g.labels else
                                             "" if g.unit is None else UNIT_SCOPE + g.unit)


# …AND A NAME STORED BEFORE THE RULE DOES NOT BLOCK THE ROW (the review's ninth pass, minor). A grant to `say"hi`, written
# before `"` was refused, reads as a grant — `|` is what breaks the reader, `"` does not — and every rewrite of its row
# carried it back here and raised: revoking `mallory` was refused, deleting a user too, and the command that mends the
# grants failed the same way. `was` is the row being replaced: a grant whose item is ALREADY there under a name the rule
# refuses now is left out of the new row — counted once (`grant`, by `<row>#<item>`), logged with why and what to do —
# and the rest is written. A NEW grant under such a name is still refused (`BadName`): the rule is for what is made.
def grants_to_items(grants: list[Grant], was: dict | None = None, where: str = "domain/grants") -> dict:
    """domain/grants/<cluster> as a Variable: one item per grant, the value its expiry. A subject or a label the reader
    could not take back apart is refused here (`BadName`), before anything is written — unless the grant is already in
    `was`, the row this replaces: then it is left out, counted."""
    from w2cplatform.doors import ref_fault
    out = {}
    for g in grants:
        if g.unit is not None and ref_fault(g.unit):                # a scope is a unit as the platform names one
            raise BadName(f"a grant's unit: {ref_fault(g.unit)}")
        why = name_refused(g.subject, "user's name") or next(
            (w for w in (name_refused(label, "label", also=",") for label in g.labels) if w), None)
        if why is None:
            out[_item(g)] = str(g.valid_until)
        elif isinstance(was, dict) and _item(g) in was:
            GRANTS.garbled(f"{where}#{_item(g)}", BadName(f"{why} — stored before the rule; left out of the row as it "
                                                          f"is written again: create the user under an allowed name "
                                                          f"and grant again"))
        else:
            raise BadName(why)
    return out


# …and a row that holds one anyway — written before the rule, by hand, by an older build — is read ITEM BY ITEM: an item
# that does not split into three, whose scope is not `unit:<sub>/<id>`, `labels:…` or nothing, or whose expiry is not a
# finite number, is not a grant
# (`nan` lapsed never: `now >= nan` is false). It is counted once (`grant`, by `<row>#<item>`) and logged once, and the
# other grants of the row are read. Fail shut for that item only: nobody gets a right from it, nobody loses one by it.
GRANTS = Table("grant", "not a grant — the other grants of the row are read", "grant")


UNIT_SCOPE = "unit:"


def _grant(k: str, v) -> Grant:
    from w2cplatform.doors import ref_fault
    subject, cap, scope = k.split("|")
    if scope.startswith("labels:"):
        return Grant(subject, cap, None, finite(v), tuple(l for l in scope[7:].split(",") if l))
    if not scope:
        return Grant(subject, cap, None, finite(v))
    if not scope.startswith(UNIT_SCOPE) or ref_fault(scope[len(UNIT_SCOPE):]):
        raise ValueError(f"a grant's scope is unit:<sub>/<id>, labels:… or nothing, not {scope[:80]!r}")
    return Grant(subject, cap, scope[len(UNIT_SCOPE):], finite(v))


def grants_from_items(items: dict | None, where: str = "domain/grants") -> list[Grant]:
    if items is not None and not isinstance(items, dict):
        GRANTS.garbled(where, TypeError(f"the row is not an object: {type(items).__name__}"))
        return []
    out = []
    for k, v in (items or {}).items():
        g = GRANTS.read(f"{where}#{k}", lambda k=k, v=v: _grant(k, v))
        if g is not None:
            out.append(g)
    return out


# THE DOMAIN'S OWN GRANTS (feedback CA). Who may look at the domain's door and who may change what it decided —
# members, topology, shared settings. The first answer was "an admin of the cluster
# that holds the domain", read from that cluster's carried grants. It does not survive Lesson 15: the holder
# moves from cluster to cluster, and the domain's administrators would change with it — whoever administers
# the member the domain moved to. So the domain keeps its own: `domain/grants/domain`, in the holder's store,
# exported in the backup with everything the domain decided (`term.EXPORTED` has `domain/grants/`). No agent
# carries it: no cluster is called `domain` (`Members` refuses the name).
#
#   whole domain only   no unit, no labels: the domain's door is not a unit's
#   valid_until 0       never lapses — the holder's own grants are not renewed by anybody, so nothing would
#                       renew them; a number is an end, as everywhere else
#   the last admin      a write that leaves no `admin` is refused: the door would close for everybody, and only
#                       a command on the holder could open it again
DOMAIN_SCOPE = "domain"
DOMAIN_GRANTS = f"domain/grants/{DOMAIN_SCOPE}"


def domain_may(vars_, subject: str, capability: str, now: float) -> bool:
    from w2cplatform.access import RANK
    items, _ = vars_.get(DOMAIN_GRANTS)
    for g in grants_from_items(items, DOMAIN_GRANTS):
        if g.subject != subject or g.unit is not None or g.labels:
            continue
        if (g.valid_until == 0 or now < g.valid_until) and RANK.get(g.capability, -1) >= RANK[capability]:
            return True
    return False


class LastAdmin(ValueError):
    """A write that would leave the domain with nobody who may change it."""


def set_domain_grants(vars_, grants: list[Grant], now: float, journal=None, by: str | None = None) -> None:
    """The domain's grants, whole. With a `journal`, the change is a line (feedback CL): who, which rows came and
    which went — the history a row that holds only its last editor loses."""
    items, idx = vars_.get(DOMAIN_GRANTS)
    new = grants_to_items(grants, was=items, where=DOMAIN_GRANTS)      # a name stored before the rule: left out, counted
    if not any(g.capability == "admin" and g.unit is None and not g.labels and (g.valid_until == 0 or now < g.valid_until)
               and _item(g) in new for g in grants):                    # …and an admin left out is no admin
        raise LastAdmin("the domain's grants would name no admin: nobody could change them again but a command on the holder")
    vars_.put(DOMAIN_GRANTS, new, cas=idx)
    if journal is not None:
        was = items or {}
        added, removed = sorted(k for k in new if k not in was), sorted(k for k in was if k not in new)
        if added or removed:
            journal.say("domain.grants.changed", user=by or "?", target=DOMAIN_SCOPE, added=",".join(added), removed=",".join(removed))


def revocation_window(token_lifetime: float, grant_lifetime: float) -> float:
    """The shorter of the two bounds the window. Most people answer the token."""
    return min(token_lifetime, grant_lifetime)


class ClusterAuthoriser:
    """What a cluster's console and doors run: signature against the
    key set the cluster holds (in its Variables, via the domain agent), the
    revocation list it holds, then its grants. Never a network call, never
    a worker."""

    def __init__(self, grants: ClusterGrants, keyset: KeySet, revoked: set[str] = frozenset(), now=time.time):
        self.grants, self.keyset, self.revoked, self.now = grants, keyset, revoked, now

    def update_trust(self, keyset: KeySet, revoked: set[str]) -> None:
        self.keyset, self.revoked = keyset, revoked

    def subject(self, token: str) -> str:
        return verify(token, self.keyset, self.revoked, now=self.now(), kind=PERSON)["sub"]   # a person, never a member (CE)

    def authorise(self, token: str, capability: str, unit: str) -> str:
        try:
            subject = self.subject(token)
        except TokenError as e:
            raise PermissionError(f"token refused: {e}")
        if not self.grants.may(subject, capability, unit):
            raise PermissionError(f"{subject} has no {capability} grant on {unit} in {self.grants.cluster}")
        return subject


# The FIRST administrator of the domain: a command on the holder, as the product has it (feedback CA) — whoever
# can write the holder's store is an administrator already, so the door is not where the first one comes from.
#   PLATFORM_STORE=… python3 -m w2cplatform.domain.grants domain <subject> [view|edit|admin]
if __name__ == "__main__":
    import os
    import sys

    from w2cplatform.variables import open_vars
    if len(sys.argv) not in (3, 4) or sys.argv[1] != DOMAIN_SCOPE:
        sys.exit("usage: python3 -m w2cplatform.domain.grants domain <subject> [view|edit|admin]")
    store = open_vars(os.environ["PLATFORM_STORE"])
    # An item that does not parse is not a grant, and is not written back: this command is how such a row is mended.
    have = [g for g in grants_from_items(store.get(DOMAIN_GRANTS)[0], DOMAIN_GRANTS) if g.subject != sys.argv[2]]
    set_domain_grants(store, have + [Grant(sys.argv[2], sys.argv[3] if len(sys.argv) == 4 else "admin", None, 0.0)],
                      time.time())
    print(f"{sys.argv[2]}: {sys.argv[3] if len(sys.argv) == 4 else 'admin'} on the domain")
