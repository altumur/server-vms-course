"""What a member carries home, and the door it carries it through.

Until now a member's agent read the holder's store: every row of `domain/*`, every member's. The holder's store holds
the signer's keys, every cluster's emergency hash, every member's stream tokens — and the rights that let a member read
its own rows let it read all of them (DOMAIN-PLATFORM.md, «Course check of domain secrets»: the read scope was the
bigger hole). So a member reads NOTHING of the holder's store. It asks the domain's door for what is its own:

    GET /api/carry/<cluster>      signed by the member's key (`trust.memberkey`): `X-W2C-Time`, `X-W2C-Seal` (the X25519
                                  key secrets are sealed to), `X-W2C-Signature` over `carry|<cluster>|<time>|<seal>`.
                                  The holder checks it against the key the member was admitted with (`domain/members`),
                                  and a time within `SKEW` of its own clock
    the answer                    {cluster, rows: {path: items}, objects: {key: base64}} — the rows every member reads
                                  (the key set, the revocations, the holder record, the shared settings' pointer, the
                                  topology, the list of members — what a cluster's console knows a member by when it
                                  asks for the backup this cluster keeps, `term.backup_answer`) and THIS cluster's own (`<path>/<cluster>`: grants, kept edits, the backup
                                  pointer, its LDevID, its emergency hash, every book a spec declares), with the two
                                  documents those pointers name. Every `*_secret` in them — at the top of a row, or of a
                                  JSON object that is one of its values — is opened with the holder's ring and SEALED TO
                                  THE MEMBER'S KEY; the member opens it with its own and keeps it sealed with its own ring
    a relay                       asks for a member it relays (`?for=<member>`, the topology says so): the answer is that
                                  member's, sealed to that member's key — the relay keeps it in memory and gives each
                                  member only its own, by the member's signature (`RelayDoor`)

`answer` is the holder's side, `HolderDoor` the door with its checks, `CarryClient` the member's side, `CarriedVars` and
`CarriedObjects` what the agent's pass reads instead of the holder's stores. An agent handed the holder's store itself
(the tests, and the holder's own agent on its own box) reads it through `answer` too: its own rows and nothing else.
"""
from __future__ import annotations

import base64
import json
import time

from w2cplatform.rows import PARSE_ERRORS
from w2cplatform.secrets import is_secret_field

SKEW = 300.0                            # how far a member's clock may be from the holder's when it asks


class Refused(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


def public_rows() -> list[str]:
    from .agent import KEYS_PATH, REVOKED_PATH
    from .members import MEMBERS
    from .shared import POINTER
    from .term import HOLDER
    from .topology import TOPOLOGY
    return [KEYS_PATH, REVOKED_PATH, HOLDER, POINTER, TOPOLOGY, MEMBERS]


def own_rows(cluster: str) -> list[str]:
    from .agent import GRANTS_PATH, per_cluster
    from .pending import PENDING_PATH
    from .term import BACKUP
    return [f"{GRANTS_PATH}/{cluster}", f"{PENDING_PATH}/{cluster}", f"{BACKUP}/{cluster}",
            *[f"{p}/{cluster}" for p in per_cluster()]]


# -- the secrets in a row, wherever the platform can see them without reading what the row means ------------------------
def _walk(items: dict, fn, ctx: str) -> dict:
    """`items` with `fn(field, value, ctx)` applied to every `*_secret` value: at the top of the row, and anywhere inside
    a value that is a JSON object (`ctx#<key>` — the item it lies in). The structure is walked; what it means is not
    read: a subsystem's book is moved and sealed without the platform knowing what a field of it is for."""
    out = {}
    for k, v in (items or {}).items():
        if is_secret_field(k) and isinstance(v, str) and v:
            out[k] = fn(k, v, ctx)
            continue
        if isinstance(v, str) and v.startswith("{") and "_secret" in v:
            try:
                obj = json.loads(v)
            except PARSE_ERRORS:
                obj = None
            if isinstance(obj, dict):
                touched = []

                def deep(x, where=f"{ctx}#{k}"):
                    if isinstance(x, dict):
                        out_ = {}
                        for f, y in x.items():
                            if is_secret_field(f) and isinstance(y, str) and y:
                                out_[f] = fn(f, y, where)
                                touched.append(f)
                            else:
                                out_[f] = deep(y)
                        return out_
                    if isinstance(x, list):
                        return [deep(y) for y in x]
                    return x
                new = deep(obj)
                if touched:
                    out[k] = json.dumps(new, sort_keys=True)
                    continue
        out[k] = v
    return out


def seal_row(sealer, items: dict, ctx: str) -> dict:
    """Every secret of the row sealed with `sealer` (the platform's ring); as it is with no ring."""
    if sealer is None:
        return dict(items or {})
    return _walk(items, lambda f, v, c: sealer.seal(f, v, c), ctx)


def open_row(sealer, items: dict, ctx: str) -> dict:
    from w2cplatform.sealing import Sealed, is_sealed

    def one(f, v, c):
        if not is_sealed(v):
            return v
        if sealer is None:
            raise Sealed(f"{c}:{f} is sealed and this process has no key (SECRETS_KEY)")
        return sealer.open(f, v, c)
    return _walk(items, one, ctx)


def _member_ctx(path: str, cluster: str) -> str:
    """Where a row of the holder lies in the member's store: `<path>/<cluster>` → `<path>`."""
    return path[: -len(cluster) - 1] if path.endswith(f"/{cluster}") else path


# -- the holder's side -------------------------------------------------------------------------------------------------
def answer(holder_vars, holder_objects, cluster: str, seal_to: str | None = None, sealer=None) -> dict:
    """What `cluster` carries home, from the holder's stores. With `seal_to` (the member's X25519 public key, hex), every
    secret is opened with the holder's ring (`sealer`) and sealed to the member, bound to the row as it will lie in the
    member's store; without it the rows go as they are stored (the holder's own agent, the tests' in-process members)."""
    from w2cplatform.trust.memberkey import seal_to as seal_for
    rows, objects = {}, {}
    for path in public_rows() + own_rows(cluster):
        items, _ = holder_vars.get(path)
        if items is None:
            continue
        if seal_to:
            dest = _member_ctx(path, cluster)
            items = _walk(open_row(sealer, items, path), lambda f, v, c, d=dest: seal_for(seal_to, f, v, d + c[len(path):]),
                          path)
        rows[path] = dict(items)
        obj = items.get("object") if isinstance(items, dict) else None
        if obj and holder_objects is not None and obj not in objects:
            raw = holder_objects.get(obj)
            if raw is not None:
                objects[obj] = base64.b64encode(raw).decode()
    return {"cluster": cluster, "rows": rows, "objects": objects}


def request_message(cluster: str, at: float, seal: str) -> bytes:
    return f"carry|{cluster}|{at:.3f}|{seal}".encode()


class HolderDoor:
    """The door's checks, over the holder's stores: who asks (a member's key, as admitted), when (its clock within
    `SKEW` of ours), for whom (itself, or a member the topology says it relays) — then `answer`, sealed to the member.

    A REFUSED ASK OF A CLUSTER NOT ON THE LIST IS A KNOCK (the three-site scenario, O2; the product's
    `Members.NoteKnock`). An agent that carries through the door and that the door does not know never got as far as a
    report — the pass ends at the refusal — so nobody saw it knock, and `POST /domain/members {name, fingerprint}` had
    nothing to compare. The ask names the key it is signed with (`X-W2C-Key`, `key`); signed by that key and within
    `SKEW`, the door remembers it in the holder's objects (`members.note_knock`) — the person who admits the cluster
    compares that key's fingerprint with the one the box shows. Refused all the same: a knock admits nobody."""

    def __init__(self, holder_vars, holder_objects, sealer=None, wall=time.time):
        self.vars, self.objects, self.sealer, self.wall = holder_vars, holder_objects, sealer, wall

    def carry(self, cluster: str, at: float, seal: str, signature: str, for_member: str | None = None,
              key: str | None = None) -> dict:
        from w2cplatform.trust.memberkey import verify
        from .members import Members, note_knock
        from .topology import Topology
        members = Members(self.vars).read()["members"]
        me = members.get(cluster) or {}
        if not me.get("key"):
            if cluster not in members and key and self.objects is not None and abs(self.wall() - at) <= SKEW \
                    and verify(key, request_message(cluster, at, seal), signature):
                note_knock(self.objects, cluster, key, seal, self.wall())
            raise Refused(403, f"{cluster} is no member with a key: admit it with its key, or register one "
                               f"(`python3 -m w2cplatform.domain.members key {cluster} <pub> <seal_pub>`)")
        if not verify(me["key"], request_message(cluster, at, seal), signature):
            raise Refused(401, f"the ask is not signed by {cluster}'s key")
        if abs(self.wall() - at) > SKEW:
            raise Refused(401, f"the ask is {self.wall() - at:+.0f} s from the holder's clock: more than {SKEW:.0f} s")
        if for_member is None or for_member == cluster:
            if seal != me.get("seal", seal):
                raise Refused(401, f"the ask names a sealing key that is not {cluster}'s")
            return answer(self.vars, self.objects, cluster, seal_to=seal, sealer=self.sealer)
        # …and only for a MEMBER (the three-site scenario, O9): the topology alone was asked, and a member
        # deleted from the list while the topology still placed it behind its office was answered all the same — its
        # public rows, no secret, `key: null` — and the relay then refused the member as one "admitted without a key".
        if for_member not in members:
            raise Refused(404, f"{for_member} is no member of this domain: nothing is carried for it")
        if Topology(self.vars).via(for_member) != cluster:
            raise Refused(403, f"{cluster} does not relay {for_member} (the domain's topology says so)")
        theirs = members[for_member]
        out = answer(self.vars, self.objects, for_member, seal_to=theirs.get("seal") or None, sealer=self.sealer)
        if not theirs.get("seal"):
            # Nobody to seal to: the relay is given no secret of a member it could open, only the rest.
            out["rows"] = {p: _walk(i, lambda f, v, c: "", p) for p, i in out["rows"].items()}
        out["key"] = theirs.get("key")                   # how the relay knows the member's own ask, by its signature
        return out


# -- the member's side -------------------------------------------------------------------------------------------------
class CarryClient:
    """A member's agent's way to its holder: `carry()` asks the door (an in-process `HolderDoor`, or an HTTP base URL
    `http://holder:8445`) and returns the answer with every secret opened by the member's key — ready for the agent to
    keep sealed with its own ring. `carry_for(member)`: a relay's ask for a member it relays (secrets stay that member's)."""

    def __init__(self, door, cluster: str, key, wall=time.time, timeout: float = 10.0):
        self.door, self.cluster, self.key, self.wall, self.timeout = door, cluster, key, wall, timeout

    def _ask(self, for_member: str | None = None) -> dict:
        at = self.wall()
        sig = self.key.sign(request_message(self.cluster, at, self.key.seal_pub))
        if isinstance(self.door, str):
            return _http_ask(self.door, self.cluster, at, self.key.seal_pub, sig, for_member, self.timeout, self.key.pub)
        return self.door.carry(self.cluster, at, self.key.seal_pub, sig, for_member, key=self.key.pub)

    def carry(self) -> dict:
        got = self._ask()
        rows = {p: _walk(i, lambda f, v, c, p=p: self.key.open(f, v, _member_ctx(p, self.cluster) + c[len(p):]), p)
                for p, i in got.get("rows", {}).items()}
        return {**got, "rows": rows}

    def carry_for(self, member: str) -> dict:
        return self._ask(member)

    def answer_for(self, cluster: str, key) -> dict:
        """What the agent's pass asks of its `domain_vars` (`DomainAgent._answer`): this client's own answer."""
        return self.carry()


def open_for(key, answer_: dict, cluster: str) -> dict:
    """An answer a relay kept for `cluster`, opened by `cluster`'s own key."""
    rows = {p: _walk(i, lambda f, v, c, p=p: key.open(f, v, _member_ctx(p, cluster) + c[len(p):]) if v else v, p)
            for p, i in answer_.get("rows", {}).items()}
    return {**answer_, "rows": rows}


def _http_ask(base: str, cluster: str, at: float, seal: str, sig: str, for_member, timeout: float,
              key: str | None = None) -> dict:
    import urllib.error
    import urllib.request
    from .federation import Unreachable
    url = f"{base.rstrip('/')}/api/carry/{cluster}" + (f"?for={for_member}" if for_member else "")
    req = urllib.request.Request(url, headers={"X-W2C-Time": f"{at:.3f}", "X-W2C-Seal": seal, "X-W2C-Signature": sig,
                                               **({"X-W2C-Key": key} if key else {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read()).get("detail", "")
        except PARSE_ERRORS:
            detail = ""
        raise Refused(e.code, detail or f"the door said {e.code}") from None
    except OSError as e:
        raise Unreachable(f"the domain's door {base} did not answer: {e}") from None


class CarriedVars:
    """The rows of one answer, as the agent's pass reads the holder: `get(path)` → `(items, 0)`, `list(prefix)`."""

    def __init__(self, rows: dict):
        self.rows = rows

    def get(self, path: str):
        items = self.rows.get(path)
        return (dict(items), 0) if items is not None else (None, 0)

    def list(self, prefix: str) -> list[str]:
        return sorted(p for p in self.rows if p.startswith(prefix))

    def put(self, path, items, cas=None):
        raise PermissionError("a member writes nothing into the holder's store: it carries")


class CarriedObjects:
    """The documents of one answer to read, and the holder's object store — or the relay's — to report into."""

    def __init__(self, objects: dict, report_to=None):
        self.objects, self.report_to = objects, report_to

    def get(self, key: str):
        raw = self.objects.get(key)
        if raw is not None:
            return base64.b64decode(raw)
        return self.report_to.get(key) if self.report_to is not None and key.startswith("domain/members/") else None

    def list(self, prefix: str) -> list[str]:
        if self.report_to is not None and prefix.startswith("domain/members/"):
            return self.report_to.list(prefix)
        return sorted(k for k in self.objects if k.startswith(prefix))

    def put(self, key, data):
        if self.report_to is None or not key.startswith("domain/members/"):
            raise PermissionError("a member writes only its own report into the holder's objects")
        return self.report_to.put(key, data)

    def delete(self, key):
        if self.report_to is None or not key.startswith("domain/members/"):
            raise PermissionError("a member deletes only from its own report")
        return self.report_to.delete(key)
