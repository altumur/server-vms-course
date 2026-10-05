"""What the subsystems this process loaded declare about the domain (`domain:` of each spec, `spec.DomainSection`).

The domain knows the subsystems by their specs and by nothing else: which units are in its directory and by which field
they are named, which objects a member reports, which rows a member carries home and which the holder keeps and backs
up, which tables its door serves, which kinds of token its signer issues and how high they grant, which names may not meet, which fields its door lets
into an edit. Every list here is read from the catalogue
(`w2cplatform.catalog`) at the moment it is asked — a spec loaded later is seen by the next pass.
"""
from __future__ import annotations

from w2cplatform import catalog


def specs() -> list:
    """The loaded specs that are on the domain at all, by name."""
    return [s for s in catalog.specs() if s.domain is not None]


def directory() -> list:
    """The specs whose units are in the domain's directory: a `ref` field names each across clusters."""
    return [s for s in specs() if s.domain.ref]


def spec(name: str):
    for s in specs():
        if s.name == name:
            return s
    return None


def reported_objects() -> tuple[str, ...]:
    """The object prefixes a member reports: every loaded subsystem's heartbeats and snapshot — the shapes every
    cluster publishes — and what a spec adds (`domain.reports`)."""
    out = []
    for s in catalog.specs():
        out += [f"{s.name}/heartbeats/", f"{s.name}/snapshot/"]
        if s.domain is not None:
            out += [f"{s.name}/{r}" for r in s.domain.reports]
    return tuple(out)


def epoch_prefixes() -> tuple[str, ...]:
    """Every loaded subsystem's epochs, which a member's report carries (the shadow compares them)."""
    return tuple(f"{s.name}/epoch/" for s in catalog.specs())


def witnesses() -> tuple[str, ...]:
    """The object families that say a member's unit was heard of by another process than its agent."""
    return tuple(f"{s.name}/{s.domain.witness}/" for s in specs() if s.domain.witness)


def books() -> list[str]:
    """Every book a member carries home: `domain/<sub>/<book>` (the holder keeps one per member, `…/<member>`)."""
    return [f"{s.domain_prefix}{b}" for s in specs() for b in s.domain.books]


def kept() -> list[str]:
    """Every row a subsystem keeps at the holder for the whole domain: `domain/<sub>/<name>`, and every family of them,
    `domain/<sub>/<name>/` — a prefix, as every reader of this list takes it (`term.exported`, `rights.agent_denials`)."""
    return [f"{s.domain_prefix}{k}" for s in specs() for k in s.domain.kept]


def table(sub: str, name: str) -> str | None:
    """The row the door serves at `/api/<sub>/<name>`, or None when no spec declares that table."""
    s = spec(sub)
    return f"{s.domain_prefix}{name}" if s is not None and name in s.domain.tables else None


def unit_rows(sub: str) -> bool:
    """`/api/<sub>/<rows>`: the read view's list of that subsystem's units — a directory spec, by its own row name."""
    return any(s.name == sub for s in directory())


def token_kinds() -> dict[str, dict]:
    """{kind: {lifetime, claims}} of every loaded spec. Two specs declaring one kind is refused: a door takes a kind by
    its name, and two meanings of one name would let one subsystem's token open the other's door."""
    out, whose = {}, {}
    for s in specs():
        for kind, t in s.domain.tokens.items():
            if kind in out:
                raise ValueError(f"the token kind {kind!r} is declared by both {whose[kind]} and {s.name}")
            out[kind], whose[kind] = dict(t), s.name
    return out


def edit_fields(sub: str) -> tuple[str, ...]:
    """The fields the domain's door lets into an edit of a member's unit of `sub` (`domain.edit`); () — not said: the
    member's console decides."""
    s = spec(sub)
    return s.domain.edit if s is not None else ()


# NAMES THAT MAY NOT MEET (ADR-0031: it was a subsystem's worker refusing an account under a person's name, and the
# platform let a person be made under an account's — one check, on one side). A spec says which of its kept rows is a
# name space held apart from a prefix (`domain.names.<kept>.exclusive_with`), and the platform refuses the write of
# EITHER side that would make the two meet: a row of the family (`domain/<sub>/<family>/<name>`) or a name in a kept
# row (its items' keys) against a row `<prefix>/<name>`, and the other way. Asked of every write through `Guarded` —
# the holder's store as the platform's processes open it (`runtime.federation_from_env`, `identity.IdentityStore`) —
# so a subsystem's worker writes its rows and is checked without a line of its own.
class NameTaken(ValueError):
    """A write that would give one name to two name spaces a spec holds apart."""


def _holds(items) -> bool:
    """A row that names someone: there, and not the platform's mark of a person deleted (`identity.py`'s tombstone)."""
    return bool(items) and items.get("kind") != "deleted"


def exclusive() -> list[tuple[str, str, str]]:
    """`(sub, <kept key: a family ends in '/'>, <prefix it is held apart from>)` of every loaded spec."""
    return [(s.name, f"{s.domain_prefix}{k}", rule["exclusive_with"]) for s in specs()
            for k, rule in s.domain.names.items()]


def name_clash(vars_, path: str, items) -> str | None:
    """Why writing `items` at `path` would make two names meet — None when it would not. A delete (no items) or a
    person's tombstone makes no name and is never refused."""
    if not _holds(items):
        return None
    for sub, kept_key, other in exclusive():
        family = kept_key.endswith("/")
        rule = f"{sub}'s domain.names.{kept_key.split('/', 2)[2]} exclusive_with {other}"
        if family and path.startswith(kept_key) and path != kept_key and "/" not in path[len(kept_key):]:
            name = path[len(kept_key):]                             # a row of the family: its name is the last segment
            if _holds(vars_.get(f"{other}/{name}")[0]):
                return f"{path}: {name!r} is already {other}/{name} ({rule})"
        elif not family and path == kept_key:
            for name in sorted(items):                              # a kept row: every name in it
                if _holds(vars_.get(f"{other}/{name}")[0]):
                    return f"{path}: {name!r} is already {other}/{name} ({rule})"
        elif path.startswith(other + "/") and "/" not in path[len(other) + 1:]:
            name = path[len(other) + 1:]                            # the other side: a row of the prefix
            if family and _holds(vars_.get(kept_key + name)[0]):
                return f"{path}: {name!r} is already {kept_key}{name} ({rule})"
            if not family and name in (vars_.get(kept_key)[0] or {}):
                return f"{path}: {name!r} is already a name in {kept_key} ({rule})"
    return None


def refuse_clash(vars_, path: str, items) -> None:
    why = name_clash(vars_, path, items)
    if why:
        raise NameTaken(why)


class Guarded:
    """A store whose every `put` is asked `refuse_clash` first; everything else is the store's own."""

    def __init__(self, vars_):
        self.inner = vars_

    def put(self, path: str, items: dict, *a, **kw):
        refuse_clash(self.inner, path, items)
        return self.inner.put(path, items, *a, **kw)

    def __getattr__(self, name):
        return getattr(self.inner, name)


def guarded(vars_):
    """`vars_` behind `Guarded` — once: a store already guarded is returned as it is."""
    return vars_ if isinstance(vars_, Guarded) else Guarded(vars_)
