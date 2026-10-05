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
    """The row the door serves at `/domain/<sub>/<name>`, or None when no spec declares that table."""
    s = spec(sub)
    return f"{s.domain_prefix}{name}" if s is not None and name in s.domain.tables else None


def unit_rows(sub: str) -> bool:
    """`/domain/<sub>/<rows>`: the read view's list of that subsystem's units — a directory spec, by its own row name."""
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



# SUBJECTS BESIDE THE PEOPLE (ADR-0031: a subsystem's worker refused an account under a person's name and a grant to an
# account above `view`, and the platform let a person be made under an account's name and granted an account anything —
# the checks were on one side, in the subsystem's code). A spec says which family of its kept rows are subjects of the
# grants beside the domain's people (`domain.names.<family>/: {exclusive_with: domain/users, grant: <grant>}`), and
# the platform refuses, on every write of the holder's store as its processes open it (`Guarded`: the domain's own,
# `identity.IdentityStore`, `agent.DomainPublisher`, `grants.set_domain_grants`, and a subsystem's worker through
# `runtime.federation_from_env` — without a line of its own):
#   a row of the family under a person's name, and a person under a row's name     `NameTaken`
#   a grant to a row of the family wider than its `grant` (`domain/grants/*`)       `GrantTooWide`
# `domain/users` is the platform's word for its people; the course keeps them as `identity/users/<name>`
# (`identity.IdentityStore._path`).
PEOPLE = {"domain/users": "identity/users/"}
GRANTS_PREFIX = "domain/grants/"         # `agent.GRANTS_PATH`: a row per cluster and the domain's own, `domain/grants/domain`


class Refused(ValueError):
    """A write of the holder's store a spec's `domain.names` forbids."""


class NameTaken(Refused):
    """One name for a person and a subject of a subsystem's family."""


class GrantTooWide(Refused):
    """A grant to a subject of a family wider than the family's `grant`."""


def _holds(items) -> bool:
    """A row that names someone: there, and not the platform's mark of a person deleted (`identity.py`'s tombstone)."""
    return bool(items) and items.get("kind") != "deleted"


def subject_families() -> list[tuple[str, str, str, str | None]]:
    """`(sub, <family prefix 'domain/<sub>/<family>/'>, <the people's prefix>, <grant or None>)` of every loaded spec."""
    return [(s.name, f"{s.domain_prefix}{k}", PEOPLE[rule["exclusive_with"]], rule.get("grant")) for s in specs()
            for k, rule in s.domain.names.items()]


def _name_under(path: str, prefix: str) -> str | None:
    """The last segment of `path` when it is a row right under `prefix`, else None."""
    rest = path[len(prefix):] if path.startswith(prefix) else ""
    return rest if rest and "/" not in rest else None


def _grants(items: dict) -> list[tuple[str, str]]:
    """`(subject, capability)` of a grants row's items, `<subject>|<capability>|<scope>` (`grants._item`)."""
    out = []
    for k in items or {}:
        parts = str(k).rsplit("|", 2)
        if len(parts) == 3:
            out.append((parts[0], parts[1]))
    return out


def refusal(vars_, path: str, items) -> tuple[type, str] | None:
    """Why writing `items` at `path` is refused — `(the refusal's class, its words)` — or None. A delete (no items) or a
    person's tombstone makes no name and is never refused."""
    from w2cplatform.access import RANK
    if not _holds(items):
        return None
    for sub, family, people, ceiling in subject_families():
        rule = f"{sub}'s domain.names.{family.split('/', 2)[2]}"
        name = _name_under(path, family)
        if name is not None:                                        # a row of the family
            if _holds(vars_.get(people + name)[0]):
                return NameTaken, f"{path}: {name!r} is a person of the domain already, {people}{name} ({rule})"
            if ceiling is not None:
                for row in vars_.list(GRANTS_PREFIX):
                    wide = [c for s, c in _grants(vars_.get(row)[0]) if s == name and RANK.get(c, -1) > RANK[ceiling]]
                    if wide:
                        return GrantTooWide, (f"{path}: {row} grants {name!r} {wide[0]}, wider than {ceiling!r} "
                                              f"({rule}.grant)")
        name = _name_under(path, people)
        if name is not None and _holds(vars_.get(family + name)[0]):   # a person
            return NameTaken, f"{path}: {name!r} is {family}{name} already ({rule} exclusive_with domain/users)"
        if ceiling is not None and path.startswith(GRANTS_PREFIX):  # grants
            for subject, cap in _grants(items):
                if RANK.get(cap, len(RANK)) > RANK[ceiling] and _holds(vars_.get(family + subject)[0]):
                    return GrantTooWide, (f"{path}: {subject!r} is {family}{subject}, granted at most {ceiling!r} "
                                          f"({rule}.grant) — not {cap!r}")
    return None


def refuse(vars_, path: str, items) -> None:
    why = refusal(vars_, path, items)
    if why:
        raise why[0](why[1])


class Guarded:
    """A store whose every `put` is asked `refuse` first; everything else is the store's own."""

    def __init__(self, vars_):
        self.inner = vars_

    def put(self, path: str, items: dict, *a, **kw):
        refuse(self.inner, path, items)
        return self.inner.put(path, items, *a, **kw)

    def __getattr__(self, name):
        return getattr(self.inner, name)


def guarded(vars_):
    """`vars_` behind `Guarded` — once: a store already guarded is returned as it is."""
    return vars_ if isinstance(vars_, Guarded) else Guarded(vars_)
