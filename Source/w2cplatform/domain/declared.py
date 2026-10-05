"""What the subsystems this process loaded declare about the domain (`domain:` of each spec, `spec.DomainSection`).

The domain knows the subsystems by their specs and by nothing else: which units are in its directory and by which field
they are named, which objects a member reports, which rows a member carries home and which the holder keeps and backs
up, which tables its door serves, which kinds of token its signer issues. Every list here is read from the catalogue
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
    """Every row a subsystem keeps at the holder for the whole domain: `domain/<sub>/<name>`."""
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
