"""Lesson 4, plugged into a CLUSTER's console: what `w2cplatform/access.py` asks, answered from the cluster's own store.

The platform's gate knows when to ask (the cluster's store holds a key set) and what a route needs. It does not
know how a person is proved — this module does, and it is loaded only in a cluster that is in a domain:

    who(token)    the signature against the key set the agent carried here, the revocation list beside it,
                  the expiry — all offline, all from THIS cluster's Variables (`ClusterTrust`)
    may(...)      the cluster's own grants (`domain/grants`), which carry an expiry and lapse by themselves

Nothing here calls the domain. A cluster cut off from it goes on admitting whoever holds a token that has not
expired and a grant that has not lapsed — and nobody else, for a time the product states (`revocation_window`).
"""
from __future__ import annotations

import time

from w2cplatform.access import RANK, Denied

from .agent import ClusterTrust
from .grants import ClusterGrants
from .tokens import TokenError, verify


class ClusterAccess:
    def __init__(self, cluster_vars, wall=time.time):
        self.trust, self.wall = ClusterTrust(cluster_vars), wall

    def who(self, token: str) -> dict:
        keys = self.trust.keyset()
        if keys is None:
            raise Denied(503, "the key set has gone from this cluster's store: nobody can be checked")
        try:
            return verify(token, keys, self.trust.revoked(), now=self.wall())
        except TokenError as e:
            raise Denied(401, f"token refused: {e}") from None

    def _grants(self) -> ClusterGrants:
        g = ClusterGrants("", now=self.wall)
        g.renew_from_domain(self.trust.grants())
        return g

    # `view` is implied by `edit`, and both by `admin`. A route that names no unit: to LOOK, any grant the
    # subject holds is enough (what it then sees is a separate question, and today it is everything the route
    # lists); to ACT, the grant has to be for the whole cluster.
    def may(self, payload: dict, capability: str, unit: str | None, labels: list) -> bool:
        if payload.get("via") == "break-glass":              # the one local account: admitted, and alarmed by the gate
            return True
        subject, grants, now = str(payload.get("sub", "")), self._grants(), self.wall()
        if unit is None and capability == "view":
            return any(s == subject and now < until for (s, *_), until in grants.grants.items())
        camera = int(unit) if unit is not None and str(unit).isdigit() else unit
        return any(grants.may(subject, c, camera, now, labels=labels) for c, r in RANK.items() if r >= RANK[capability])


def cluster_access(cluster_vars, wall=time.time) -> ClusterAccess:
    return ClusterAccess(cluster_vars, wall)
