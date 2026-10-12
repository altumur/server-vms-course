"""ADR-0074 observation readers inside ordinary workers.

No placement choice, remote stores, publication or token issuance here. The caller
supplies the primary's member from placement. Former flat books are refused.
"""
from __future__ import annotations
from dataclasses import dataclass
import json


class Unconfirmed(ValueError):
    """A book cannot confirm a new connection or the placed primary's state."""


@dataclass(frozen=True)
class Observation:
    member: str
    item: str
    value: dict


@dataclass(frozen=True)
class Facts:
    entries: tuple[Observation, ...]
    missing: tuple[str, ...]


def _object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise Unconfirmed("duplicate book field")
        out[key] = value
    return out


def _constant(_):
    raise Unconfirmed("non-finite book value")


def _parse(raw):
    try:
        value = json.loads(raw, object_pairs_hook=_object, parse_constant=_constant)
        json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        return value
    except (ValueError, TypeError, OverflowError, RecursionError, UnicodeError):
        raise Unconfirmed("invalid book envelope") from None


def _missing(value):
    if not isinstance(value, list) or any(not isinstance(n, str) or not n for n in value) \
            or len(set(value)) != len(value):
        raise Unconfirmed("invalid book missing members")
    return tuple(sorted(value))


def read(items, ref: str) -> Facts:
    """Read a key with its mandatory completeness marker; errors contain no values."""
    if not isinstance(items, dict) or not isinstance(ref, str) or not ref or "" not in items:
        raise Unconfirmed("book has no completeness marker")
    marker = _parse(items[""])
    if not isinstance(marker, dict) or set(marker) != {"missing"}:
        raise Unconfirmed("invalid book completeness marker")
    missing = _missing(marker["missing"])
    if ref not in items:
        return Facts((), missing)
    envelope = _parse(items[ref])
    if not isinstance(envelope, dict) or set(envelope) != {"entries", "missing"} \
            or _missing(envelope["missing"]) != missing or not isinstance(envelope["entries"], list):
        raise Unconfirmed("inconsistent book envelope")
    entries, seen = [], set()
    for entry in envelope["entries"]:
        if not isinstance(entry, dict) or set(entry) != {"member", "item", "value"}:
            raise Unconfirmed("invalid book origin")
        member, item, value = entry["member"], entry["item"], entry["value"]
        if not isinstance(member, str) or not member or not isinstance(item, str) or not item \
                or not isinstance(value, dict) or value.get("ref") != ref or (member, item) in seen:
            raise Unconfirmed("invalid book observation")
        seen.add((member, item))
        entries.append(Observation(member, item, value))
    return Facts(tuple(sorted(entries, key=lambda e: (e.member, e.item))), missing)


def source(items, ref: str) -> Observation:
    """One confirmed source for a new connection, never a winner from missing."""
    facts = read(items, ref)
    if facts.missing or len(facts.entries) != 1:
        raise Unconfirmed("source is absent, conflicting or incomplete")
    return facts.entries[0]


def primary(items, ref: str, member: str) -> Observation | None:
    """The placed recording, never the first all entry; None applies standby grace."""
    return _primary(read(items, ref), member)


def _primary(facts, member):
    if not isinstance(member, str) or not member:
        raise Unconfirmed("primary placement has no member identity")
    matches = [e for e in facts.entries if e.member == member]
    if member in facts.missing or not matches:
        return None
    if len(matches) != 1:
        raise Unconfirmed("placed recording has conflicting observations")
    value = matches[0].value
    if not isinstance(value.get("recording"), str) or not value["recording"]:
        raise Unconfirmed("recording has no identity")
    if any(type(value.get(field)) is not bool for field in ("enabled", "running")) \
            or "starting" in value and type(value["starting"]) is not bool:
        raise Unconfirmed("recording state is invalid")
    return matches[0]


def copies(items, ref: str, assigned) -> tuple[Observation, ...]:
    """Only explicitly assigned reserve recordings, each with its own origin."""
    facts = read(items, ref)
    return tuple(fact for member in sorted(set(assigned))
                 if (fact := _primary(facts, member)) is not None)
