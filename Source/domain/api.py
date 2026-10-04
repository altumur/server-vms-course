"""Lesson 3 — the API, and what it refuses.

The domain console's write API is a façade: an edit goes to the directory
("where is camera 7"), then to the OWNING CLUSTER's console — the one in
front of that cluster's controller, the only writer of its vms/* — and that
cluster's grants decide. The domain console owns nothing and never writes
a camera row on its own account; a create goes to the cluster the
placement service chose, and that cluster's controller places it on a
worker (М11 Lesson 10). The domain never names a worker or a server.

    idempotency keys    a retried PUT is the same PUT, not a second edit
    what it refuses     a client may not set placement at either level (cluster, worker, server), nor what
                        a worker observes (phase, observed_revision) or takes (epoch)
    positions/reasons   the read model's `phase` and `position` are passed through untouched
    authentication      Lesson 3 ships it unauthenticated and says so; Lesson 4 adds `verifier`
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from .federation import DomainDirectory, Unreachable

FORBIDDEN_FIELDS = ("cluster", "worker", "server", "placement", "epoch", "observed_revision", "phase", "revision")


class ClusterConsole(Protocol):
    """What the domain can ask of a cluster's console (М11 Lesson 10): the same
    two writes its controller offers, with the caller's subject for its grants."""
    def update_camera(self, camera: int, fields: dict, subject: str | None) -> dict: ...
    def create_camera(self, fields: dict, subject: str | None) -> dict: ...


@dataclass
class ApiError(Exception):
    status: int
    detail: str

    def __str__(self) -> str:
        return f"{self.status}: {self.detail}"


# An address that carries a credential, refused in the cluster's words (`secrets.address_refusal`) and named by its
# field: the domain's `_refuse_secrets`, and a camera's own console (`Device._update`), which a kept edit reaches
# without the domain's door (Lesson 9). Inside a list or an object too (`secrets.refusal_within`; vmsserver's
# thirteenth review, minor): only a value that was a string was asked, and `{"source": ["rtsp://admin:…@…"]}` was
# 202, kept, and applied on the camera — the password in the reply, on the camera's flash and in what it published.
def refuse_addresses(fields: dict) -> None:
    from w2cplatform.secrets import refusal_within
    found = refusal_within(fields)                       # a field's name that is an address is asked too
    if found:
        raise ApiError(400, f"{found[0]}: {found[1]} — a device's login and password are set in the camera's own "
                            f"cluster, in cred_username / cred_secret; an address is shown, kept, backed up and relayed")


# WHAT A MEMBER ANSWERS IS SAID AS A PAGE SAYS IT (the product's r28-secrets2): the domain handed the member console's
# reply to its caller as it came, and kept it a day as the idempotency copy (`_seen`) — a member of another build, or a
# row stored there before the refusals, put a camera's password in both (`cred_secret`, an address with a login). The
# member's reply is masked the way the cluster masks a row (`mask_secrets`): a `*_secret` as `***`, every address
# hidden, at any depth.
def said(reply):
    from w2cplatform.secrets import mask_secrets
    return mask_secrets([{"": reply}])[0][""]


class ConsoleAPI:
    def __init__(self, directory: DomainDirectory, consoles: Callable[[str], ClusterConsole],
                 verifier: Callable[[str], str] | None = None, pending=None, last_known=None):
        """`consoles(cluster)` finds that cluster's console — its Nomad service,
        in production; a dict in tests. `verifier(token) -> subject` is Lesson 4;
        None means unauthenticated, and the API says so on every response.

        `pending` and `last_known` are Lesson 9: somewhere to keep an edit for a cluster
        that is off (`PendingEdits`), and what the domain last saw of the camera
        (`ReadView.last_known`). Without them the API answers as Lesson 3 did — 503,
        could not look — rather than pretend to keep an edit it has nowhere to put."""
        self.directory, self.consoles, self.verifier = directory, consoles, verifier
        self.pending, self.last_known = pending, last_known
        self._seen: dict[str, dict] = {}                      # idempotency key -> response

    def _subject(self, token: str | None) -> str | None:
        if self.verifier is None:
            return None
        if not token:
            raise ApiError(401, "a token is required")
        return self.verifier(token)

    def _refuse_placement(self, fields: dict) -> None:
        bad = [k for k in fields if k in FORBIDDEN_FIELDS]
        if bad:
            raise ApiError(400, f"a client may not set {bad}: the domain places on a cluster and the cluster's "
                                f"controller places on a worker, each with a stored reason; epoch, phase and "
                                f"observed_revision are the worker's; revision is the controller's")

    # A DEVICE'S PASSWORD IS NOT THE DOMAIN'S TO CARRY (the product, feedback CD). An edit through the domain for a
    # cluster that is off is KEPT (Lesson 9): in the holder's store, in every backup of it (Lesson 15), in the
    # books a relay carries (Lesson 17), and its fields in the journal. A `*_secret` among them is in the clear in
    # all of those — past the cluster's key, which seals a secret only on the way into the cluster's own store
    # (М10A Lesson 18). So the domain refuses it, kept or forwarded: a password is set in the camera's cluster.
    #
    # …NOR IN AN ADDRESS (vmsserver's twelfth review, blocker 9; a run). The rule looked at field NAMES, and `{"source":
    # "…?usr=admin&pwd=…"}` for a camera whose cluster was off was 202 with the password in the reply, kept in
    # `domain/pending/<cluster>`, and applied on the camera when it came back. Every value that is an address goes
    # through the cluster's own rule (`secrets.address_refusal`: a login, a port that is no number, a credential pair
    # in the query or the path), refused before anything is kept or forwarded, in words that name the field and never
    # the value.
    def _refuse_secrets(self, fields: dict) -> None:
        from w2cplatform.secrets import is_secret_field
        bad = sorted(k for k in fields if is_secret_field(k))
        if bad:
            raise ApiError(400, f"{', '.join(bad)}: a device's password is set in the camera's own cluster — the domain "
                                f"keeps, backs up and relays its edits, and a password would be in the clear in all of those")
        refuse_addresses(fields)

    def update_camera(self, camera: int, fields: dict, idempotency_key: str, token: str | None = None) -> dict:
        if idempotency_key in self._seen:
            return self._seen[idempotency_key]                # the same PUT, not a second edit
        self._refuse_placement(fields)
        self._refuse_secrets(fields)
        subject = self._subject(token)
        ans = self.directory.where(camera)
        if not ans.found:
            kept = self._keep(camera, fields, subject, ans)
            if kept is not None:
                self._seen[idempotency_key] = kept
                return kept
            raise ApiError(404 if ans.complete else 503, ans.sentence())
        try:
            result = self.consoles(ans.cluster).update_camera(camera, fields, subject)
        except Unreachable:
            # It answered the directory and not the edit — gone between the two, or, with a directory
            # answered from memory (Lesson 11), gone since the last pass. Either way the owner is known,
            # and silent: the same case as Lesson 9's.
            kept = self._keep_for(ans.cluster, camera, fields, subject)
            if kept is None:
                raise ApiError(503, f"{ans.cluster} did not answer the edit")
            self._seen[idempotency_key] = kept
            return kept
        resp = {"camera": camera, "cluster": ans.cluster, "worker": ans.worker, "result": said(result),
                "authenticated": self.verifier is not None}
        self._seen[idempotency_key] = resp
        return resp

    # Lesson 9. The camera was not found because its cluster did not answer — and the domain knows which cluster
    # that was, from what it last saw. Keep the edit for it instead of refusing: per field, against the value
    # last seen. Only then, though: a camera missing from a cluster that DID answer is gone, not waiting, and
    # a complete answer that found nothing is a 404. Accepted is not applied, and the response says which.
    def _keep(self, camera, fields: dict, subject: str | None, ans) -> dict | None:
        if self.pending is None or self.last_known is None or ans.complete:
            return None
        known = self.last_known(camera)
        if known is None or known[0] not in ans.unreachable:
            return None
        return self._keep_for(known[0], camera, fields, subject)

    def _keep_for(self, cluster: str, camera, fields: dict, subject: str | None) -> dict | None:
        if self.pending is None or self.last_known is None:
            return None
        known = self.last_known(camera)
        if known is None or known[0] != cluster:
            return None
        row = known[1]
        entry = self.pending.add(cluster, camera, fields, row, subject)
        return {"camera": camera, "cluster": cluster, "pending": True, "fields": entry["fields"],
                "detail": f"{cluster} is not answering; the edit is kept and will be applied when it is back",
                "authenticated": self.verifier is not None}

    def create_camera(self, fields: dict, cluster: str, idempotency_key: str, token: str | None = None) -> dict:
        """`cluster` comes from the placement service's stored decision, which
        the console reads and forwards — it does not choose. The worker is the
        cluster controller's decision, returned, never sent."""
        if idempotency_key in self._seen:
            return self._seen[idempotency_key]
        self._refuse_placement(fields)
        # The same refusals as an edit's (the product's cross-check of vmsserver's twelfth review): a create is not kept,
        # but it passes the domain's door, its journal and its idempotency copy — a password is set in the cluster.
        self._refuse_secrets(fields)
        subject = self._subject(token)
        result = self.consoles(cluster).create_camera(fields, subject)
        resp = {"cluster": cluster, "result": said(result), "authenticated": self.verifier is not None}
        self._seen[idempotency_key] = resp
        return resp
