"""Lesson 12 — shared settings without a database.

Some settings belong to the system and not to any one unit: the default a unit gets when nobody set one,
the tree the console offers, what one member's event asks of another. With a server room they live in that
cluster's store. With small boxes as members there is no such place
— every member is its own cluster — and the domain has no database, by decision.

The domain already publishes one thing of this shape: the identity set (Lesson 4), as an object named by a
pointer, object first. Shared settings are the same, with two differences that come from where the copy is
READ — on every member, when the domain may be gone:

    signed          the document carries the signer's signature, by the key set every member already holds.
                    A copy is believed by its signature, not by who handed it over — so any copy is as good
                    as the original, and a member that got it from a stale mirror or a wrong door cannot be
                    fooled by it
    ordered         (term, rev): a member never replaces a newer document with an older one, whatever
                    arrives. The term is Lesson 15's — the domain moved — and it outranks the revision
    kept            each member keeps the last verified document in its own durable store. The domain can be
                    gone for a month; the settings are where they are read
    defaults        a shared setting is a DEFAULT, resolved when it is read. It is never copied into rows:
                    that would make the agent a writer of rows, and a change of default a write to five
                    hundred units, each of which might be off
    declared        a subsystem's fields the domain holds a value for are its spec's `domain.shared`; their values
                    are `settings.shared.<sub>.<field>`, and nothing else is taken — not there, not beside it. The
                    platform resolves them (`resolve`: the unit's, the domain's, the spec's `inherit`; `merge: union`
                    adds) and serves them at one door, `GET /domain/shared/<sub>` (`door`), on the cluster's console.
                    An entry of `domain.shared` may be a DOCUMENT the domain holds whole — `{name, type: json,
                    schema}`, no unit's field — and its value is checked by its schema (`refusals`), as a field's
                    with a schema is: one rule over whatever the specs declare, no field known by what it means

    domain/shared            in the domain holder's Variables: {object, rev, term, sha256} — the pointer, and the CAS
    shared/rev-<n>           in the domain holder's objects: the signed document
    domain/shared            in each member's Variables: the pointer to what it holds, written by its agent
    domain/shared            in each member's durable objects: the document itself
    domain/shared-refused    in each member's Variables: a document it would not take, and why
"""
from __future__ import annotations

import hashlib
import json
import time

from w2cplatform.rows import PARSE_ERRORS
from w2cplatform.trust.documents import NotTaken, sign, verify
from w2cplatform.trust.tokens import KeySet, TokenIssuer
from w2cplatform.variables import Conflict

from .federation import MEMBER_OBJECTS, Unreachable

POINTER, OBJECT, REFUSED = "domain/shared", "domain/shared", "domain/shared-refused"


def _order(d: dict) -> tuple[int, int]:
    return int(d.get("term", 0)), int(d.get("rev", 0))


class SharedSettings:
    """The domain's side: edit, sign, publish object-first, point by CAS."""

    def __init__(self, domain_vars, domain_objects, issuer: TokenIssuer, wall=time.time, term=lambda: 1):
        self.vars, self.objects, self.issuer, self.wall, self.term = domain_vars, domain_objects, issuer, wall, term

    def current(self) -> tuple[dict, int]:
        ptr, idx = self.vars.get(POINTER)
        if not ptr:
            return {"rev": 0, "term": self.term(), "settings": {}}, idx
        return json.loads(self.objects.get(ptr["object"])), idx

    # `base_rev` is the revision the editor was looking at. Two editors on one document are Lesson 3's two
    # tabs: the second is told, not overwritten — the CAS on the pointer is what tells them.
    #
    # WHAT THE DOCUMENT MAY HOLD IS THE SPECS', AND NOTHING ELSE IS ASKED (ADR-0010, ADR-0032). The fields and the
    # documents the specs declare, each by its schema (`refusals`) — a 400, the edit wrong by the specs on its own; a
    # revision moved underneath it is a 409, `Conflict`. What a value MEANS — that the units a document names can do
    # what it asks of them — is no check here: the platform asks no subsystem's code; the subsystem says it on its pass.
    def edit(self, mutate, base_rev: int, by: str | None = None) -> int:
        doc, idx = self.current()
        if int(doc["rev"]) != base_rev:
            raise Conflict(f"shared settings are at rev {doc['rev']}; the edit was made against rev {base_rev}")
        settings = json.loads(json.dumps(doc.get("settings", {})))
        mutate(settings)
        wrong = refusals(settings)
        if wrong:
            from .api import ApiError
            raise ApiError(400, "; ".join(wrong))
        new = sign({"rev": int(doc["rev"]) + 1, "term": self.term(), "at": self.wall(), "by": by,
                    "settings": settings}, self.issuer)
        raw = json.dumps(new, ensure_ascii=False, sort_keys=True).encode()
        key = f"shared/rev-{new['rev']}"
        self.objects.put(key, raw)                                                           # 1. the object
        self.vars.put(POINTER, {"object": key, "rev": new["rev"], "term": new["term"],        # 2. the pointer, by CAS
                                "sha256": hashlib.sha256(raw).hexdigest()}, cas=idx)
        return new["rev"]

    # What the console shows beside the settings: which members hold which revision. Read from each
    # member's own copy of the pointer — the agent's report, as Lesson 9's outcomes are.
    def delivery(self, fed) -> dict:
        ptr, _ = self.vars.get(POINTER)
        want = (int(ptr["term"]), int(ptr["rev"])) if ptr else (0, 0)
        out = {"rev": want[1], "holding": [], "behind": {}, "refused": {}, "silent": []}
        for name, c in fed.clusters.items():
            if c.is_domain_holder:
                continue
            try:
                have, _ = c.vars.get(POINTER)
                refused, _ = c.vars.get(REFUSED)
                if refused and (int(refused.get("term", 0)), int(refused.get("rev", 0))) == want:
                    out["refused"][name] = str(refused.get("reason", ""))
                elif have and (int(have["term"]), int(have["rev"])) >= want:
                    out["holding"].append(name)
                else:
                    out["behind"][name] = int(have["rev"]) if have else 0
            except Unreachable:
                out["silent"].append(name)
            except PARSE_ERRORS as e:                       # its copy cannot be read: as one that did not answer (the
                MEMBER_OBJECTS.garbled(f"{name}/{POINTER}", e)   # review's eighth pass), and the other members are read
                out["silent"].append(name)
        out["sentence"] = (f"rev {want[1]} on {len(out['holding'])} of {len(out['holding']) + len(out['behind']) + len(out['refused']) + len(out['silent'])} members"
                           + (f"; not answering: {', '.join(sorted(out['silent']))}" if out["silent"] else "")
                           + (f"; refused by: {', '.join(sorted(out['refused']))}" if out["refused"] else ""))
        return out


# The domain's own read of what it published — for the passes that act on the document (Lesson 16's book of
# asks is built from its scenarios). Its own store, its own document: nothing to verify against.
def published(domain_vars, domain_objects) -> dict:
    ptr, _ = domain_vars.get(POINTER)
    raw = domain_objects.get(ptr["object"]) if ptr else None
    return json.loads(raw).get("settings", {}) if raw else {}


# The agent's side, one pass: carry the document home if it is newer than what the member holds and it
# verifies against the member's OWN key set. Object first, then the pointer — a member that dies between
# the two still points at a document it has.
#
# The same carry takes Lesson 15's backup of the domain's state home, under other names: `src` is the pointer
# in the domain holder, `dst` the member's copy of it, `obj` where the member keeps the document.
def carry(domain_vars, domain_objects, member_vars, member_objects, keys: KeySet | None, now: float,
          src: str = POINTER, dst: str = POINTER, obj: str = OBJECT, refused: str = REFUSED) -> str:
    ptr, _ = domain_vars.get(src)
    if not ptr:
        return "nothing published"
    have, hidx = member_vars.get(dst)
    if have and (int(have["term"]), int(have["rev"])) >= (int(ptr["term"]), int(ptr["rev"])):
        return "up to date" if (int(have["term"]), int(have["rev"])) == (int(ptr["term"]), int(ptr["rev"])) else "holding newer"
    raw = domain_objects.get(ptr["object"])
    try:
        if raw is None:
            raise NotTaken(f"the pointer names {ptr['object']} and there is no such object")
        if hashlib.sha256(raw).hexdigest() != ptr["sha256"]:
            raise NotTaken("the object does not match the pointer's checksum")
        doc = verify(json.loads(raw), keys, now)
        if _order(doc) != (int(ptr["term"]), int(ptr["rev"])):
            raise NotTaken(f"the object is term {doc.get('term')} rev {doc.get('rev')}, the pointer says otherwise")
    except NotTaken as e:
        _, ridx = member_vars.get(refused)
        member_vars.put(refused, {"rev": ptr["rev"], "term": ptr["term"], "reason": str(e), "at": now}, cas=ridx)
        return f"refused: {e}"
    member_objects.put(obj, raw)
    member_vars.put(dst, {"rev": ptr["rev"], "term": ptr["term"], "sha256": ptr["sha256"]}, cas=hidx)
    return f"took rev {ptr['rev']}"


def refusals(settings: dict) -> list[str]:
    """Why the document `settings` would be wrong by the specs — each a reason to refuse the edit whole: anything beside
    `shared`, a subsystem not on the domain, a field it does not share (`domain.shared`), a value its schema refuses — a
    document's (`{name, type: json, schema}`) or a field's that has one. The document carries the declared and nothing
    else, each as its spec says it may be."""
    from w2cplatform.schema import Invalid, check
    from . import declared
    out = [f"settings.{k}: the document holds `shared` and nothing beside it"
           for k in sorted(settings) if k != "shared"]
    shared = settings.get("shared") or {}
    if not isinstance(shared, dict):
        return out + ["settings.shared is {<sub>: {<field>: value}}"]
    for sub, values in shared.items():
        s = declared.spec(sub)
        if s is None or not isinstance(values, dict):
            out.append(f"shared settings for {sub!r}: no subsystem on the domain by that name")
            continue
        stray = sorted(set(values) - set(s.domain.shared))
        if stray:
            out.append(f"shared settings for {sub!r}: {stray} are not in its domain.shared {list(s.domain.shared)}")
        for name, v in values.items():
            f = s.domain.documents.get(name) or s.fields.get(name)
            if name in stray or f is None or f.schema is None:
                continue
            try:
                check(f.schema, v, f"{sub}.{name}")
            except Invalid as e:
                out.append(f"shared settings for {sub!r}: {e}")
            except RecursionError:
                out.append(f"shared settings for {sub!r}: {name} is nested past what is read")
    return out


def resolve(spec, settings: dict, label: str | None, row: dict | None = None) -> dict[str, tuple[object, str]]:
    """`{field: (value, from)}` — a unit's value where it set one; for a field its spec shares and that inherits, the
    domain's value where the unit set none (`merge: union`: the unit's AND the domain's), else the spec's `inherit`.
    A shared field the page groups by is never a unit's value from the domain: what the domain holds there are the
    groups it offers (`door`). `row` None: what a unit that set nothing would get."""
    row = row or {}
    shared = set(spec.domain.shared) - set(spec.domain.documents) if spec.domain else set()
    domain = ((settings.get("shared") or {}).get(spec.name) or {}) if label else {}
    out = {}
    for k in set(row) | {n for n, f in spec.fields.items() if f.inherits}:
        f = spec.fields.get(k)
        mine = row.get(k)
        held = k in shared and k in domain and f is not None and f.inherits
        if held and f.merge == "union" and mine is not None:
            out[k] = (sorted(set(mine) | set(domain[k])), f"unit + {label}")
        elif mine is not None:
            out[k] = (mine, "unit")
        elif held:
            out[k] = (domain[k], label)
        elif f is not None and f.inherits and f.inherit is not None:
            out[k] = (f.inherit, "spec")
    return out


def door(spec, doc: dict | None, row: dict | None = None) -> dict:
    """`GET /domain/shared/<sub>`: the fields its spec shares and nothing else — each inheriting one resolved (for a
    unit, `?unit=<id>`, or for one that set nothing), with where the value came from, its `inherit` and `merge`; the
    field the page groups by as the groups the domain offers (`groups`); a document the domain holds whole as it is."""
    settings = (doc or {}).get("settings", {})
    label = f"domain rev {doc['rev']}" if doc else None
    resolved = resolve(spec, settings, label, row)
    domain = (settings.get("shared") or {}).get(spec.name) or {}
    fields = {}
    for name in spec.domain.shared if spec.domain else ():
        if name in spec.domain.documents:
            fields[name] = {"value": domain.get(name), "from": label if name in domain else None}
            continue
        f = spec.fields[name]
        if f.inherits:
            value, came = resolved.get(name, (None, None))
            fields[name] = {"value": value, "from": came, "inherit": f.inherit,
                            **({"merge": f.merge} if f.merge != "override" else {})}
        else:
            fields[name] = {"groups": domain.get(name) or [], "from": label if name in domain else None}
    return {"sub": spec.name, "rev": doc["rev"] if doc else 0, "fields": fields}


class SharedView:
    """What a member's console reads: the document its agent took, checked again on the way in — a copy on
    flash is still only data — and the defaults resolved against a row."""

    def __init__(self, member_vars, member_objects, wall=time.time):
        self.vars, self.objects, self.wall = member_vars, member_objects, wall

    def document(self) -> dict | None:
        raw = self.objects.get(OBJECT)
        if raw is None:
            return None
        from .agent import ClusterTrust, Untrusted
        try:
            return verify(json.loads(raw), ClusterTrust(self.vars).keyset(), self.wall())
        except (NotTaken, Untrusted, *PARSE_ERRORS):
            return None                                  # nothing this member can check: no document, as unverified

    def settings(self) -> dict:
        doc = self.document()
        return doc["settings"] if doc else {}

    # A field the unit set is the unit's. A field it did not set takes the domain's value, and says
    # so: the console shows WHERE a value came from, because "why does this unit keep 14 days" must have
    # an answer that is not "somebody, somewhere".
    #
    # The chain has three links (feedback AT): the unit's value, the domain's, the spec's `inherit` — the last one
    # resolved here, at the moment of use, and never written. It only works for a field the spec lets be NOT SET
    # (`inherit`, never a `default`) and shares (`domain.shared`). A list the spec merges by `union` (the alarm
    # kinds) is the site's AND the unit's, not one of them. `spec`: the unit's subsystem (`resolve`).
    def effective(self, row: dict, spec) -> dict[str, tuple[object, str]]:
        doc = self.document()
        return resolve(spec, (doc or {}).get("settings", {}), f"domain rev {doc['rev']}" if doc else None, row)
