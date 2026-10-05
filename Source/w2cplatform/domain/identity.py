"""Lesson 4 — where users live, and creating a user touches no cluster.

    identity/users/<id>   in the domain holder's store, the signer the only writer
                          local: a scrypt hash (`pwhash_secret`, sealed under the platform's ring at rest);
                          federated: an IdP subject and no secret
    identity/pointer      -> identity/rev-N object: the whole set, published object-first
    users/<id>/prefs      per-user UI configuration as an object; last write wins, with a revision

Nothing about a user ever reaches a worker. Authentication ends in a token
naming the subject; what the subject may do is each cluster's grants,
carried by the domain agent and decided by the cluster's console and gateway.
The RPO for users is the publication interval, and it is stated.

Break-glass is the honest residue: one local account, audited on every
use, alarmed on, rotated after — it reintroduces exactly the password
hash the design removed, and the module says so out loud.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import time
from dataclasses import dataclass, field

from w2cplatform.rows import Table
from w2cplatform.trust.signer import Signer
from w2cplatform.trust.tokens import PERSON
from w2cplatform.variables import Conflict, Variables

# One user's record that does not parse is that user's (the review's seventh pass left `identity.users` open): it
# raised out of `users()`, and with it the publication of the whole identity set on the signer's loop and the login of
# every federated user. Skipped, counted once by its path, logged once; the others are read and published.
USERS = Table("user", "left out of the published identity set and of federated logins — the others are read", "user record")

IDENTITY_SET = "identity/pointer"          # what the hashes in the published object are bound to
TOKEN_LIFETIME = 15 * 60.0        # the number the product states; Lesson 4 makes students defend it


class AuthError(Exception):
    pass


def _hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    h = hashlib.scrypt(password.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return salt.hex() + ":" + h.hex()


def _check(password: str, stored: str) -> bool:
    salt, h = stored.split(":")
    return secrets.compare_digest(_hash(password, bytes.fromhex(salt)).split(":")[1], h)


# What a login for a user who does not exist is checked against: the same scrypt, so "no such user" takes as long
# as "wrong password" and the door does not tell a stranger which names are real (the product, feedback BZ).
_NOBODY = _hash(secrets.token_hex(16))


@dataclass
class User:
    id: str
    kind: str                      # "local" | "idp"
    roles: list[str]
    pwhash: str = ""               # local only
    idp_subject: str = ""          # idp only
    created: float = 0.0

    def to_items(self) -> dict:
        return {"id": self.id, "kind": self.kind, "roles": ",".join(self.roles), "pwhash_secret": self.pwhash,
                "idp_subject": self.idp_subject, "created": self.created}

    @classmethod
    def from_items(cls, it: dict) -> "User":
        return cls(it["id"], it["kind"], [r for r in it.get("roles", "").split(",") if r], it.get("pwhash_secret", ""),
                   it.get("idp_subject", ""), float(it.get("created", 0)))


class IdentityStore:
    # WHO CHANGED THE PEOPLE (feedback CL). A record held who edited it last and when; the history was lost. Every
    # change here is a line in the holder's journal — role `domain` — naming the actor the domain's door verified
    # (`by`), the record, and what changed. Never a password: the line says the password changed, and that is all.
    def __init__(self, signer: Signer, vars_: Variables, objects, publish_floor: float = 60.0, now=time.time, journal=None,
                 sealer=None):
        """`sealer`: the platform's ring on the holder — a user's hash is sealed with it in the row (`pwhash_secret`),
        and opened only here, to check a password. With none it lies in the clear, as every secret does then.

        The store is asked through `declared.guarded`: a person is not made under a name a spec holds apart from the
        people (`domain.names.<kept>.exclusive_with: identity/users` — ADR-0031), refused `declared.NameTaken`."""
        from .declared import guarded
        self.signer, self.vars, self.objects, self.now = signer, guarded(vars_), objects, now
        self.sealer = sealer if sealer is not None else getattr(signer, "sealer", None)
        self.floor, self._last_publish, self._dirty = publish_floor, -1e9, False
        self.published_rev, self.publishes = 0, 0
        self.journal = journal

    def _say(self, what: str, uid: str, by: str | None, **fields) -> None:
        if self.journal is not None:
            self.journal.say(what, user=by or "?", target=uid, **fields)

    # -- records ----------------------------------------------------------------
    def _path(self, uid: str) -> str:
        return f"identity/users/{uid}"

    def get(self, uid: str) -> User | None:
        from w2cplatform.sealing import open_row
        items, _ = self.vars.get(self._path(uid))
        return User.from_items(open_row(self.sealer, items, self._path(uid))) if items else None

    def _put(self, u: User) -> None:
        from w2cplatform.sealing import seal_items
        _, idx = self.vars.get(self._path(u.id))
        self.vars.put(self._path(u.id), seal_items(self.sealer, u.to_items(), self._path(u.id)), cas=idx)
        self._dirty = True

    # A user's name is the subject of every token and grant they will hold: `|`, `"` and control characters are refused
    # here, where it is made (the review's eighth pass; `grants.refuse_name`) — a `|` broke every grant of a row.
    def create_local(self, uid: str, password: str, roles: list[str], by: str | None = None) -> User:
        from .grants import refuse_name
        refuse_name(uid, "user's name")
        if self.get(uid) and self.get(uid).kind != "deleted":
            raise ValueError(f"user {uid} exists")
        u = User(uid, "local", roles, pwhash=_hash(password), created=self.now())
        self._put(u)
        self._say("domain.user.created", uid, by, account="local", roles=",".join(roles))
        return u

    def create_federated(self, uid: str, idp_subject: str, roles: list[str], by: str | None = None) -> User:
        """The customer has an IdP: the record holds a subject, not a person, and no secret."""
        from .grants import refuse_name
        refuse_name(uid, "user's name")
        u = User(uid, "idp", roles, idp_subject=idp_subject, created=self.now())
        self._put(u)
        self._say("domain.user.created", uid, by, account="idp", roles=",".join(roles))
        return u

    def set_password(self, uid: str, password: str, by: str | None = None) -> None:
        u = self.get(uid)
        if not u or u.kind != "local":
            raise KeyError(uid)
        u.pwhash = _hash(password)
        self._put(u)
        self._say("domain.user.password", uid, by)       # that it changed — never what to

    def set_roles(self, uid: str, roles: list[str], by: str | None = None) -> None:
        u = self.get(uid)
        if not u:
            raise KeyError(uid)
        was = u.roles
        u.roles = roles
        self._put(u)
        self._say("domain.user.roles", uid, by, roles=",".join(roles), was=",".join(was))

    # A user deleted takes every grant that names them, on every cluster and on the domain (the product, feedback
    # CG). Grants name a SUBJECT, not a record: left behind, they would go to whoever is next created under the
    # same name. The domain's last admin is not deleted (`set_domain_grants` refuses), and nothing is changed then.
    def delete(self, uid: str, by: str | None = None) -> None:
        from .agent import GRANTS_PATH
        from .grants import DOMAIN_GRANTS, grants_from_items, set_domain_grants
        items, _ = self.vars.get(DOMAIN_GRANTS)
        mine = [g for g in grants_from_items(items) if g.subject == uid]
        if mine:
            set_domain_grants(self.vars, [g for g in grants_from_items(items) if g.subject != uid], self.now(),
                              journal=self.journal, by=by)
        for path in self.vars.list(GRANTS_PATH + "/"):
            if path == DOMAIN_GRANTS:
                continue
            row, idx = self.vars.get(path)
            kept = {k: v for k, v in (row or {}).items() if k.rsplit("|", 2)[0] != uid}   # the subject: all but the last two
            if row is not None and kept != row:
                self.vars.put(path, kept, cas=idx)
        _, idx = self.vars.get(self._path(uid))
        self.vars.put(self._path(uid), {"id": uid, "kind": "deleted"}, cas=idx)
        self._dirty = True
        self._say("domain.user.deleted", uid, by, grants_taken=len(mine))

    def users(self) -> list[User]:
        out = []
        from w2cplatform.sealing import open_row
        for p in self.vars.list("identity/users/"):
            items, _ = self.vars.get(p)
            u = USERS.read(p, lambda items=items, p=p: User.from_items(open_row(self.sealer, items, p))
                           if items and items.get("kind") in ("local", "idp") else None)
            if u is not None:
                out.append(u)
        return out

    # -- authentication: ends in a token naming the subject and nothing else ---
    def login(self, uid: str, password: str) -> str:
        u = self.get(uid)
        known = bool(u) and u.kind == "local"
        if not _check(password, u.pwhash if known else _NOBODY) or not known:
            raise AuthError("bad credentials")
        return self.signer.tokens.issue(uid, TOKEN_LIFETIME, now=self.now(), kind=PERSON)

    def login_federated(self, idp_assertion: dict) -> str:
        """The IdP authenticated Alice; the signer issues a DOMAIN token naming
        her, and the clusters never learn the IdP exists."""
        subj = idp_assertion["sub"]
        for u in self.users():
            if u.kind == "idp" and u.idp_subject == subj:
                return self.signer.tokens.issue(u.id, TOKEN_LIFETIME, now=self.now(), kind=PERSON)
        raise AuthError(f"no domain user for IdP subject {subj}")

    # -- publish-then-point: the identity set as one object ------------------------
    def publish(self, force: bool = False) -> bool:
        if not (self._dirty or force):
            return False
        if not force and self.now() - self._last_publish < self.floor:
            return False
        rev = self.published_rev + 1
        # The hashes in the object are sealed under the holder's BACKUP key (`Signer.backup_sealer`): an object is read by
        # whoever reads the holder's objects and is copied with them (the course check of the domain's secrets), and a
        # new holder derives the backup key again — from the root, or from the signer's backup (Lessons 4–7).
        box = self.signer.backup_sealer()
        users = [{**u.to_items(), "pwhash_secret": box.seal("pwhash_secret", u.pwhash, IDENTITY_SET) if u.pwhash else ""}
                 for u in self.users()]
        blob = json.dumps({"format": 2, "revision": rev, "users": users}).encode()
        self.objects.put(f"identity/rev-{rev}", blob)                                     # 1. the object
        _, idx = self.vars.get("identity/pointer")
        self.vars.put("identity/pointer", {"object": f"identity/rev-{rev}", "revision": rev}, cas=idx)   # 2. the pointer
        self.published_rev, self._last_publish, self._dirty, self.publishes = rev, self.now(), False, self.publishes + 1
        return True

    @classmethod
    def restore(cls, signer: Signer, new_vars: Variables, objects, pointer_items: dict, now=time.time) -> "IdentityStore":
        """Moving the domain: the backed-up key (Signer.restore), then the identity object the pointer names — its
        hashes opened with the backup key the restored signer derives, and sealed again with this holder's ring."""
        blob = objects.get(pointer_items["object"])
        if blob is None:
            raise RuntimeError(f"pointer names {pointer_items['object']} but the object store has no such object — refusing to guess")
        d = json.loads(blob)
        st = cls(signer, new_vars, objects, now=now)
        box = signer.backup_sealer()
        for it in d["users"]:
            if it.get("pwhash_secret"):
                it = {**it, "pwhash_secret": box.open("pwhash_secret", it["pwhash_secret"], IDENTITY_SET)}
            st._put(User.from_items(it))
        st.published_rev, st._dirty = int(d["revision"]), False
        _, idx = new_vars.get("identity/pointer")
        new_vars.put("identity/pointer", dict(pointer_items), cas=idx)
        return st

    # -- per-user configuration: an object, last write wins, with a revision --------
    def get_prefs(self, uid: str) -> tuple[dict, int]:
        raw = self.objects.get(f"users/{uid}/prefs")
        if not raw:
            return {}, 0
        d = json.loads(raw)
        return d["prefs"], int(d["revision"])

    def put_prefs(self, uid: str, prefs: dict, base_revision: int) -> int:
        """Returns the new revision; raises Conflict if `base_revision` is
        stale so a second tab is TOLD rather than silently overwritten."""
        _, current = self.get_prefs(uid)
        if base_revision != current:
            raise Conflict(f"prefs revision {current}, you had {base_revision}")
        self.objects.put(f"users/{uid}/prefs", json.dumps({"revision": current + 1, "prefs": prefs}).encode())
        return current + 1


@dataclass
class BreakGlass:
    """One account. Audited on every use, alarmed on, rotated after."""
    signer: Signer
    pwhash: str
    audit: list[dict] = field(default_factory=list)
    alarm: list[str] = field(default_factory=list)
    used_since_rotation: int = 0

    @classmethod
    def create(cls, signer: Signer, password: str) -> "BreakGlass":
        return cls(signer, _hash(password))

    def use(self, password: str, who: str, why: str, now: float) -> str:
        ok = _check(password, self.pwhash)
        self.audit.append({"at": now, "who": who, "why": why, "ok": ok})
        self.alarm.append(f"BREAK-GLASS {'used' if ok else 'ATTEMPTED'} by {who}: {why}")
        if not ok:
            raise AuthError("break-glass: bad password")
        self.used_since_rotation += 1
        return self.signer.tokens.issue("break-glass", TOKEN_LIFETIME, now=now, via="break-glass", who=who, kind=PERSON)

    def rotate(self, new_password: str, by: str | None = None, journal=None) -> None:
        self.pwhash, self.used_since_rotation = _hash(new_password), 0
        if journal is not None:
            journal.say("domain.break_glass.set", user=by or "?")  # that it was set — never what to
