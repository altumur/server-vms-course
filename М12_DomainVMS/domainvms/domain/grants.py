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
