"""ADR-0074: subjects of collected books and the last grant check before delivery.

The index contains identities only. It is written after a book's recipient rows by the
holder; a missing observation never proves a name free. No subsystem-specific meanings.
"""
from __future__ import annotations

import json
import threading

from .bookmerge import _constant, _json, _object

# One holder process serializes collection and guarded identity/grant writes. This is
# not a distributed lock or a claim of a transaction across Variables rows.
MUTATIONS = threading.RLock()


def path(sub, book):
    return f"domain/names/{sub}/{book}"


def declarations():
    from . import declared
    return [(s, b, s.domain.names[b + "/"]) for s in declared.specs()
            for b in s.domain.merged if b + "/" in s.domain.names]


def _parse(raw):
    if not isinstance(raw, str):
        raise ValueError("index value is not JSON text")
    value = json.loads(raw, object_pairs_hook=_object, parse_constant=_constant)
    _json(value)  # reject overflowed numbers and unpaired surrogates as well
    return value


def _names(value):
    if not isinstance(value, list) or any(not isinstance(n, str) or not n for n in value):
        raise ValueError("invalid member names")
    if value != sorted(set(value)):
        raise ValueError("member names are not sorted and unique")
    return tuple(value)


def decode(items, where):
    """Strict index read. No permissive empty default for a missing or damaged index."""
    from .declared import NamesUnavailable
    try:
        if not isinstance(items, dict) or "" not in items:
            raise ValueError("missing index")
        meta = _parse(items[""])
        if not isinstance(meta, dict) or set(meta) != {"missing"}:
            raise ValueError("invalid index marker")
        missing = _names(meta["missing"])
        subjects = {}
        for key, raw in items.items():
            if key == "":
                continue
            if not isinstance(key, str) or not key:
                raise ValueError("invalid subject")
            _json(key)
            doc = _parse(raw)
            if not isinstance(doc, dict) or set(doc) != {"members"}:
                raise ValueError("invalid subject entry")
            subjects[key] = _names(doc["members"])
            if not subjects[key]:
                raise ValueError("subject without an owner")
        return subjects, missing
    except (ValueError, TypeError, OverflowError, RecursionError, UnicodeError):
        # Do not log malformed text: the index must never become an escape for a secret.
        raise NamesUnavailable(where) from None


def index(collected, previous=None):
    """Current subjects plus last known names ONLY of members still explicitly missing.

Lost/removed members are absent from collected.missing and therefore lose their old names.
An unreadable predecessor carries no known names. Fresh results still replace it;
the missing marker independently prevents creation and grant expansion.
"""
    subjects = {k: set(v) for k, v in collected.subjects.items()}
    missing = set(collected.missing)
    if missing and previous is not None:
        from .declared import NamesUnavailable
        try:
            old, _ = decode(previous, "previous book name index")
        except NamesUnavailable:
            old = {}
        for key, owners in old.items():
            retained = missing.intersection(owners)
            if retained:
                subjects.setdefault(key, set()).update(retained)
    return {"": _json({"missing": sorted(missing)}),
            **{k: _json({"members": sorted(v)}) for k, v in sorted(subjects.items())}}


def publish(vars_, spec, book, collected, now):
    """Publish addressed results first, then their index (ADR-0074, 12 October).

No transaction across rows is claimed. Build/validate the index before writing anything;
if an output write fails, the previous index remains. The holder supplies sealed results.
"""
    with MUTATIONS:
        return _publish(vars_, spec, book, collected, now)


def _publish(vars_, spec, book, collected, now):
    where = path(spec.name, book)
    named = book + "/" in spec.domain.names
    previous, idx = vars_.get(where) if named else (None, 0)
    names = index(collected, previous) if named else None
    for member, items in collected.rows.items():
        dest = f"{spec.domain_prefix}{book}/{member}"
        row = delivery(vars_, dest, member, items, now)
        have, rev = vars_.get(dest)
        if have != row:
            vars_.put(dest, row, cas=rev)
    prefix = f"{spec.domain_prefix}{book}/"
    for dest in vars_.list(prefix):
        recipient = dest[len(prefix):]
        if recipient and '/' not in recipient and recipient not in collected.rows:
            vars_.delete(dest)
    if named and previous != names:
        vars_.put(where, names, cas=idx)


def complete(vars_, sub, book):
    from .declared import NamesUnavailable
    where = path(sub, book)
    subjects, missing = decode(vars_.get(where)[0], where)
    if missing:
        raise NamesUnavailable(where, missing)
    return subjects


def available(vars_, spec, book, name):
    """A creator's check before publishing a new subject; not a global reservation.

Two creators can see the same complete index. The next unique collection exposes their
conflict and delivers neither; no per-subsystem hook or distributed lock is introduced.
"""
    from w2cplatform.access import RANK
    from .declared import GRANTS_PREFIX, GrantTooWide, NameTaken, _grants, _person
    from .grants import refuse_name
    refuse_name(name, "subject", also="/")
    rule = spec.domain.names[book + "/"]
    with MUTATIONS:
        subjects = complete(vars_, spec.name, book)
        if name in subjects or _person(vars_, "domain/users/" + name):
            raise NameTaken(f"{name!r} is already a person or a subject of {spec.name}/{book}")
        ceiling = rule.get("grant")
        if ceiling is not None:
            for row in vars_.list(GRANTS_PREFIX):
                if any(subject == name and RANK.get(cap, len(RANK)) > RANK[ceiling]
                       for subject, cap in _grants(vars_.get(row)[0])):
                    raise GrantTooWide(f"{name!r} already has a grant wider than {ceiling!r}")


def _expands(vars_, where, items):
    """A subset, shorter expiry or narrower capability remains revocable during missing reports."""
    from w2cplatform.access import RANK
    from .grants import DOMAIN_GRANTS, _grant
    old = []
    previous = vars_.get(where)[0]
    if previous is not None and not isinstance(previous, dict):
        return True
    for key, value in (previous or {}).items():
        try:
            old.append(_grant(key, value))
        except (ValueError, TypeError, OverflowError):
            pass  # checking a change must not reset the reader's diagnostic state
    def until(g):
        return float("inf") if where == DOMAIN_GRANTS and g.valid_until == 0 else g.valid_until
    for key, value in items.items():
        try:
            g = _grant(key, value)
        except (ValueError, TypeError, OverflowError):
            return True
        if not any(o.subject == g.subject and o.unit == g.unit and o.labels == g.labels and
                   RANK.get(o.capability, -1) >= RANK.get(g.capability, len(RANK)) and
                   until(o) >= until(g) for o in old):
            return True
    return False


def refuse_write(vars_, where, items):
    from w2cplatform.access import RANK
    from .declared import GRANTS_PREFIX, GrantTooWide, NameTaken, NamesUnavailable, _holds, _name_under
    from .grants import grants_from_items
    books = declarations()
    if not books:
        return
    person = _name_under(where, "domain/users/")
    creating = person is not None and not _holds(vars_.get(where)[0])
    grants_row = where.startswith(GRANTS_PREFIX)
    granting = grants_row and _expands(vars_, where, items)
    if not creating and not grants_row:
        return
    for spec, book, rule in books:
        if creating or granting:
            subjects = complete(vars_, spec.name, book)
        else:
            try:
                row = path(spec.name, book)
                subjects, _ = decode(vars_.get(row)[0], row)
            except NamesUnavailable:
                continue  # revocation never waits for a damaged/missing observation
        if creating and person in subjects:
            raise NameTaken(f"{person!r} is a subject of {spec.name}/{book}")
        ceiling = rule.get("grant")
        if grants_row and ceiling is not None:
            for grant in grants_from_items(items, where):
                if grant.subject in subjects and RANK.get(grant.capability, len(RANK)) > RANK[ceiling]:
                    raise GrantTooWide(f"{grant.subject!r} is granted at most {ceiling!r} by {spec.name}/{book}")


def delivery(vars_, row_path, recipient, items, now):
    """Recheck grants at the carry boundary, even if the stored book was collected earlier.

No delivery on absent, expired, malformed or too-wide grants. Scoped grants admit the
account here; the recipient's service still enforces their unit/label scope on use.
"""
    from .grants import grants_from_items
    match = next(((s, b, n) for s, b, n in declarations()
                  if row_path == f"{s.domain_prefix}{b}/{recipient}"), None)
    if match is None or "grant" not in match[2]:
        return items
    spec, book, names = match
    grant_path = f"domain/grants/{recipient}"
    permitted = {g.subject for g in grants_from_items(vars_.get(grant_path)[0], grant_path)
                 if g.capability == names["grant"] and now < g.valid_until}
    out = {"": items[""]} if "" in items else {}
    for key, raw in items.items():
        if not key or key not in permitted:
            continue
        try:
            doc = _parse(raw)
            if not isinstance(doc, dict) or set(doc) != {"entries", "missing"}:
                continue
            _names(doc["missing"])
            entries = doc["entries"]
            if not isinstance(entries, list) or not entries:
                continue
            kept = []
            for e in entries:
                if not isinstance(e, dict) or set(e) != {"member", "item", "value"}:
                    raise ValueError("invalid entry")
                if not all(isinstance(e[k], str) and e[k] for k in ("member", "item")):
                    raise ValueError("invalid origin")
                value, rule = e["value"], spec.domain.merged[book]
                if not isinstance(value, dict) or value.get(rule.key) != key:
                    raise ValueError("invalid value")
                to = value.get(rule.to)
                to = [to] if isinstance(to, str) else to
                if not isinstance(to, list) or any(not isinstance(m, str) or not m for m in to):
                    raise ValueError("invalid recipients")
                if recipient in to:
                    kept.append(e)
            if kept:
                out[key] = _json({"entries": kept, "missing": doc["missing"]})
        except (ValueError, TypeError, OverflowError, RecursionError, UnicodeError):
            continue
    return out
