"""ADR-0074 C2: the domain queues explicit CRUD for admitted members.

The domain never writes a member's unit or invokes its console directly. The
member's agent carries the Edit and calls its own signed console, retaining the
original idempotency key. Authentication and declared domain.edit are checked
before persistence; owned fields and credentials are refused.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .federation import DomainDirectory, Unreachable

FORBIDDEN_FIELDS = ("cluster", "worker", "server", "placement", "epoch", "observed_revision", "phase", "revision")


@dataclass
class ApiError(Exception):
    status: int
    detail: str

    def __str__(self) -> str:
        return f"{self.status}: {self.detail}"


# An address that carries a credential, refused in the cluster's words (`secrets.address_refusal`) and named by its
# field: the domain's `_refuse_secrets`, and a member's own console, which a kept edit reaches without the domain's
# door (Lesson 9). Inside a list or an object too (`secrets.refusal_within`; the thirteenth review, minor): only a
# value that was a string was asked, and a list holding an address with a login in it was 202, kept, and applied on
# the member — the password in the reply, on the member's flash and in what it published.
def refuse_addresses(fields: dict) -> None:
    from w2cplatform.secrets import refusal_within
    found = refusal_within(fields)                       # a field's name that is an address is asked too
    if found:
        raise ApiError(400, f"{found[0]}: {found[1]} — a login and a password are set in the unit's own cluster, in its "
                            f"secret fields; an address is shown, kept, backed up and relayed")


# WHAT A MEMBER ANSWERS IS SAID AS A PAGE SAYS IT (the product's r28-secrets2): the domain handed the member console's
# reply to its caller as it came, and kept it a day as the idempotency copy (`_seen`) — a member of another build, or a
# row stored there before the refusals, put a password in both (a `*_secret`, an address with a login). The member's
# reply is masked the way the cluster masks a row (`mask_secrets`): a `*_secret` as `***`, every address hidden, at
# any depth.
def said(reply):
    from w2cplatform.secrets import mask_secrets
    return mask_secrets([{"": reply}])[0][""]


class ConsoleAPI:
    def __init__(self, directory: DomainDirectory,
                 verifier: Callable[[str], str] | None = None, pending=None, last_known=None):
        """The queue is mandatory for writes. `last_known` resolves an offline unit.

        `verifier(token)` authenticates the person before persistence; the console
        separately requires domain admin. This API never contacts a member console.
        """
        self.directory, self.verifier = directory, verifier
        self.pending, self.last_known = pending, last_known

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

    # A PASSWORD IS NOT THE DOMAIN'S TO CARRY (the product, feedback CD). An edit through the domain for a cluster that
    # is off is KEPT (Lesson 9): in the holder's store, in every backup of it (Lesson 15), in the member's carry answer a
    # relay keeps in memory on its way to the member (`relay.RelayDoor`, Lesson 17), and its fields in the journal. A
    # `*_secret` among them is in the clear in all of those — past the cluster's key, which seals a secret only on the
    # way into the cluster's own store (М10A Lesson 18). So the domain refuses it, kept or forwarded: a password is set
    # in the unit's own cluster.
    #
    # …NOR IN AN ADDRESS (the twelfth review, blocker 9; a run). The rule looked at field NAMES, and an address with a
    # login in its query for a unit whose cluster was off was 202 with the password in the reply, kept in
    # `domain/pending/<cluster>`, and applied when it came back. Every value that is an address goes through the
    # cluster's own rule (`secrets.address_refusal`: a login, a port that is no number, a credential pair in the query
    # or the path), refused before anything is kept or forwarded, in words that name the field and never the value.
    def _refuse_secrets(self, fields: dict) -> None:
        from w2cplatform.secrets import is_secret_field
        bad = sorted(k for k in fields if is_secret_field(k))
        if bad:
            raise ApiError(400, f"{', '.join(bad)}: a password is set in the unit's own cluster — the domain keeps, "
                                f"backs up and relays its edits, and a password would be in the clear in all of those")
        refuse_addresses(fields)

    # …AND ONLY WHAT ITS SPEC LETS THROUGH (ADR-0031: a subsystem's door held the list, and the domain's own route took
    # any field the member's console takes). `domain.edit` of the unit's spec names the fields an edit through the domain
    # may carry; any other is refused here, before the member is asked or the edit is kept, in words that name the
    # fields and the list — and a spec that names none lets nothing through (ADR-0012: no default that passes).
    # The subsystem is the route's (`sub`: the door always names it).
    @staticmethod
    def _refuse_undeclared(sub: str | None, fields: dict) -> None:
        from .declared import edit_fields
        if not sub:
            raise ApiError(400, "the subsystem must be named")
        allowed = edit_fields(sub)
        if not allowed:
            raise ApiError(400, f"{sub}'s spec declares no domain.edit: the domain's door lets no field of its units "
                                f"into an edit — they are edited in their own cluster")
        bad = sorted(k for k in fields if k not in allowed)
        if bad:
            raise ApiError(400, f"{', '.join(bad)}: not the domain's to edit — {sub}'s spec lets an edit through the "
                                f"domain carry {', '.join(allowed)} (domain.edit)")

    def queue(self, method, sub, rows, unit, body, key, cluster, token=None):
        """Every domain CRUD operation is durable before the member's agent applies it."""
        from . import declared
        from .members import Members
        spec = declared.spec(sub)
        if not spec or spec.rows != rows or not spec.rows:
            raise ApiError(404, "no such unit route")
        if not key:
            raise ApiError(400, "Idempotency-Key header is required")
        if not isinstance(body, dict):
            raise ApiError(400, "the body must be an object")
        self._subject(token)
        self._refuse_placement(body)
        self._refuse_secrets(body)
        if method == "PUT":
            self._refuse_undeclared(sub, body)
        if method != "DELETE":
            from w2cplatform.spec import Refused
            from w2cplatform.rows import PARSE_ERRORS
            from w2cplatform.schema import check, Invalid
            try:
                spec.refuse(body)
                for name, value in body.items():
                    field = spec.fields[name]
                    kind = {"int": "integer", "float": "number", "bool": "boolean",
                            "list": "array", "json": None}.get(field.type, "string")
                    if kind:
                        check({"type": kind}, value, name)
                    if field.required and value in (None, "", []):
                        raise Refused(f"{name} is required")
                    if method == "PUT" and field.fixed:
                        raise Refused(f"{name} is fixed at creation")
                if method == "POST":
                    spec.new_row(unit or "new", body)
            except (Refused, Invalid, *PARSE_ERRORS):
                raise ApiError(400, "unit fields do not satisfy their spec") from None
        if method == "POST" and spec.domain and spec.domain.ref and not body.get(spec.domain.ref):
            raise ApiError(400, "the spec's domain.ref field is required")
        if self.pending is None:
            raise ApiError(503, "this domain has no durable edit queue")
        members = Members(self.pending.vars).read()["members"]
        if cluster not in members:
            raise ApiError(404, "the target cluster is not an admitted member")
        path = "/" + sub + "/" + rows + ("/" + str(unit) if unit is not None else "")
        try:
            entry = self.pending.add(cluster, method, path, body, key)
        except ValueError as err:
            raise ApiError(400, str(err)) from None
        return {"kept": entry["id"], "cluster": cluster, "what": entry["what"],
                "note": "kept; the member's agent applies it through its own console"}

    def resolve_unit(self, sub, ref):
        """Resolve a domain reference to its member's local id, with no guessed owner."""
        from . import declared
        from .federation import ref_of
        spec = declared.spec(sub) if sub else None
        if spec is None:
            raise ApiError(400, "the subsystem must be named")
        if self.directory is None or not spec.domain or not spec.domain.ref:
            raise ApiError(400, "cluster is required for a unit without a domain reference")
        answer = self.directory.where(ref)
        if getattr(answer, "contested", None):
            raise ApiError(409, "more than one member reports this domain reference")
        known = self.last_known(ref) if self.last_known is not None else None
        row = None
        if answer.found:
            cluster = answer.cluster
            if getattr(answer, "sub", None) not in (None, sub):
                raise ApiError(404, "the reported unit belongs to another subsystem")
            if callable(getattr(self.directory, "scan", None)):
                scan, _ = self.directory.scan()
                row = next((u for u in scan.get(cluster, {}).get("units", [])
                            if u.get("sub") == sub and ref_of(u) == str(ref)), None)
            elif known and known[0] == cluster:
                row = known[1]
        elif known and known[0] in answer.unreachable:
            cluster, row = known
        else:
            raise ApiError(404 if answer.complete else 503, "the owning member is unknown")
        if row is None or row.get("sub") != sub or ref_of(row) != str(ref) or row.get("id") is None:
            raise ApiError(503, "the member's local unit identity is unknown")
        try:
            local_id = spec.parse_id(row["id"])
        except (TypeError, ValueError, OverflowError):
            raise ApiError(503, "the member's local unit identity is unreadable") from None
        return cluster, local_id

    def update_unit(self, ref, fields, idempotency_key, token=None, sub=None):
        from . import declared
        cluster, local_id = self.resolve_unit(sub, ref)
        return self.queue("PUT", sub, declared.spec(sub).rows, local_id, fields, idempotency_key, cluster, token)

    def create_unit(self, fields, cluster, idempotency_key, token=None, sub=None):
        from . import declared
        spec = declared.spec(sub) if sub else None
        if spec is None:
            raise ApiError(400, "the subsystem must be named")
        return self.queue("POST", sub, spec.rows, None, fields, idempotency_key, cluster, token)
