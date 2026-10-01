"""Lesson 4 — grants are cluster-local, carry an expiry, and expiry IS the
revocation mechanism.

Each cluster holds `subject X may do Y on camera Z until T` in its own
Variables under domain/grants/*, written by the domain agent (the only
writer of domain/* in that cluster) and read by the cluster's console and
live gateway. Enforcement is a local read — no lookup, no token exchange —
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
from dataclasses import dataclass

from .tokens import KeySet, TokenError, verify

GRANT_LIFETIME = 24 * 3600.0     # Lesson 4 makes students pick and defend it; the product states it


@dataclass(frozen=True)
class Grant:
    subject: str
    capability: str          # "view" | "edit" | "admin"
    camera: int | None       # None = every camera in this cluster
    valid_until: float
    # …or the cameras that carry ALL of these labels (the product's scope, feedback BP): "the ground floor"
    # without a grant per camera. With labels, `camera` is None and means nothing.
    labels: tuple = ()


class ClusterGrants:
    """One cluster's grants, as its console and gateway hold them in memory
    from domain/grants/* (М9's `grants` table, with valid_until, one level up)."""

    def __init__(self, cluster: str, now=time.time):
        self.cluster, self.now = cluster, now
        self.grants: dict[tuple, float] = {}             # (subject, capability, camera, labels) -> valid until

    def grant(self, subject: str, capability: str, camera: int | None, valid_until: float, labels: tuple = ()) -> None:
        self.grants[(subject, capability, camera, tuple(sorted(labels)))] = valid_until

    def revoke(self, subject: str) -> None:
        self.grants = {k: v for k, v in self.grants.items() if k[0] != subject}

    def may(self, subject: str, capability: str, camera, now: float | None = None, labels=()) -> bool:
        now = self.now() if now is None else now
        for (s, c, cam, lab), until in self.grants.items():
            if s != subject or c not in (capability, "admin") or now >= until:
                continue
            # A labelled grant covers a camera that carries all of its labels — and never "every camera":
            # asked about no camera in particular (`camera=None`, no labels), it does not match.
            if (set(lab) <= set(labels)) if lab else (cam in (camera, None)):
                return True
        return False

    def renew_from_domain(self, renewals: list[Grant]) -> None:
        """The agent carried the domain's current grants for this cluster:
        replace, so a grant the domain dropped is not renewed."""
        self.grants = {(g.subject, g.capability, g.camera, tuple(sorted(g.labels))): g.valid_until for g in renewals}

    def access_ends(self, subject: str, token_exp: float) -> float:
        """State in advance: if a revoke cannot reach this cluster, when does
        `subject` lose it? min(token expiry, latest grant expiry)."""
        untils = [u for (s, *_), u in self.grants.items() if s == subject]
        return min(token_exp, max(untils)) if untils else token_exp


def grants_to_items(grants: list[Grant]) -> dict:
    """domain/grants/<cluster> as a Variable: one item per grant, the value its expiry."""
    return {f"{g.subject}|{g.capability}|" + ("labels:" + ",".join(sorted(g.labels)) if g.labels else
                                              "" if g.camera is None else str(g.camera)): str(g.valid_until) for g in grants}


def grants_from_items(items: dict | None) -> list[Grant]:
    out = []
    for k, v in (items or {}).items():
        subject, cap, cam = k.split("|")
        if cam.startswith("labels:"):
            out.append(Grant(subject, cap, None, float(v), tuple(l for l in cam[7:].split(",") if l)))
        else:
            out.append(Grant(subject, cap, int(cam) if cam else None, float(v)))
    return out


# THE DOMAIN'S OWN GRANTS (feedback CA). Who may look at the domain's door and who may change what it decided —
# members, topology, scenarios between cameras, shared settings. The first answer was "an admin of the cluster
# that holds the domain", read from that cluster's carried grants. It does not survive Lesson 15: the holder
# moves from cluster to cluster, and the domain's administrators would change with it — whoever administers
# the camera the domain moved to. So the domain keeps its own: `domain/grants/domain`, in the holder's store,
# exported in the backup with everything the domain decided (`term.EXPORTED` has `domain/grants/`). No agent
# carries it: no cluster is called `domain` (`Members` refuses the name).
#
#   whole domain only   no camera, no labels: the domain's door is not a camera's
#   valid_until 0       never lapses — the holder's own grants are not renewed by anybody, so nothing would
#                       renew them; a number is an end, as everywhere else
#   the last admin      a write that leaves no `admin` is refused: the door would close for everybody, and only
#                       a command on the holder could open it again
DOMAIN_SCOPE = "domain"
DOMAIN_GRANTS = f"domain/grants/{DOMAIN_SCOPE}"


def domain_may(vars_, subject: str, capability: str, now: float) -> bool:
    from w2cplatform.access import RANK
    items, _ = vars_.get(DOMAIN_GRANTS)
    for g in grants_from_items(items):
        if g.subject != subject or g.camera is not None or g.labels:
            continue
        if (g.valid_until == 0 or now < g.valid_until) and RANK.get(g.capability, -1) >= RANK[capability]:
            return True
    return False


class LastAdmin(ValueError):
    """A write that would leave the domain with nobody who may change it."""


def set_domain_grants(vars_, grants: list[Grant], now: float) -> None:
    if not any(g.capability == "admin" and g.camera is None and not g.labels and (g.valid_until == 0 or now < g.valid_until)
               for g in grants):
        raise LastAdmin("the domain's grants would name no admin: nobody could change them again but a command on the holder")
    _, idx = vars_.get(DOMAIN_GRANTS)
    vars_.put(DOMAIN_GRANTS, grants_to_items(grants), cas=idx)


def revocation_window(token_lifetime: float, grant_lifetime: float) -> float:
    """The shorter of the two bounds the window. Most people answer the token."""
    return min(token_lifetime, grant_lifetime)


class ClusterAuthoriser:
    """What a cluster's console and live gateway run: signature against the
    key set the cluster holds (in its Variables, via the domain agent), the
    revocation list it holds, then its grants. Never a network call, never
    a worker."""

    def __init__(self, grants: ClusterGrants, keyset: KeySet, revoked: set[str] = frozenset(), now=time.time):
        self.grants, self.keyset, self.revoked, self.now = grants, keyset, revoked, now

    def update_trust(self, keyset: KeySet, revoked: set[str]) -> None:
        self.keyset, self.revoked = keyset, revoked

    def subject(self, token: str) -> str:
        return verify(token, self.keyset, self.revoked, now=self.now())["sub"]

    def authorise(self, token: str, capability: str, camera: int) -> str:
        try:
            subject = self.subject(token)
        except TokenError as e:
            raise PermissionError(f"token refused: {e}")
        if not self.grants.may(subject, capability, camera):
            raise PermissionError(f"{subject} has no {capability} grant on camera {camera} in {self.grants.cluster}")
        return subject


# The FIRST administrator of the domain: a command on the holder, as the product has it (feedback CA) — whoever
# can write the holder's store is an administrator already, so the door is not where the first one comes from.
#   CONFIG_URL=… python3 -m domain.grants domain <subject> [view|edit|admin]
if __name__ == "__main__":
    import os
    import sys

    import cluster as _cluster  # noqa: F401  — registers the `nomad://` scheme
    from w2cplatform.variables import open_vars
    if len(sys.argv) not in (3, 4) or sys.argv[1] != DOMAIN_SCOPE:
        sys.exit("usage: python3 -m domain.grants domain <subject> [view|edit|admin]")
    store = open_vars(os.environ["CONFIG_URL"])
    have = [g for g in grants_from_items(store.get(DOMAIN_GRANTS)[0]) if g.subject != sys.argv[2]]
    set_domain_grants(store, have + [Grant(sys.argv[2], sys.argv[3] if len(sys.argv) == 4 else "admin", None, 0.0)],
                      time.time())
    print(f"{sys.argv[2]}: {sys.argv[3] if len(sys.argv) == 4 else 'admin'} on the domain")
