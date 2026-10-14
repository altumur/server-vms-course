"""ADR-0074 observation readers inside ordinary workers.

No placement choice, remote stores, publication or token issuance here. The caller
supplies the primary's member from placement. Former flat books are refused.
"""
from __future__ import annotations
from dataclasses import dataclass
import json
import math

SOURCES_PATH = "domain/cam/sources"
PRIMARIES_PATH = "domain/rec/primaries"


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


def read(items, ref: str, *, value_key="ref") -> Facts:
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
                or not isinstance(value, dict) or value.get(value_key) != ref or (member, item) in seen:
            raise Unconfirmed("invalid book observation")
        seen.add((member, item))
        entries.append(Observation(member, item, value))
    return Facts(tuple(sorted(entries, key=lambda e: (e.member, e.item))), missing)


def source(items, ref: str) -> Observation:
    """One confirmed source for a new connection, never a winner from missing."""
    facts = read(items, ref)
    if facts.missing or len(facts.entries) != 1:
        raise Unconfirmed("source is absent, conflicting or incomplete")
    source_value(facts.entries[0].value)
    return facts.entries[0]


def primary(items, ref: str, member: str) -> Observation | None:
    """The placed recording, never the first all entry; None applies standby grace."""
    return _primary(read(items, ref), member, "primary")


def _primary(facts, member, role):
    if not isinstance(member, str) or not member:
        raise Unconfirmed("primary placement has no member identity")
    own = [e for e in facts.entries if e.member == member]
    if any(e.value.get("role") not in ("primary", "backup", "card") for e in own):
        raise Unconfirmed("recording role is invalid")
    matches = [e for e in own if e.value["role"] == role]
    if member in facts.missing or not matches:
        return None
    if len(matches) != 1:
        raise Unconfirmed("placed recording has conflicting observations")
    value = matches[0].value
    if not isinstance(value.get("recording"), str) or not value["recording"]:
        raise Unconfirmed("recording has no identity")
    if any(type(value.get(field)) is not bool for field in ("enabled", "running")):
        raise Unconfirmed("recording state is invalid")
    recording_value(value)
    return matches[0]


def copies(items, ref: str, assigned) -> tuple[Observation, ...]:
    """Only explicitly assigned reserve recordings, each with its own origin."""
    facts = read(items, ref)
    return tuple(fact for member in sorted(set(assigned))
                 if (fact := _primary(facts, member, "backup")) is not None)


def _fields(value, required, optional):
    if not isinstance(value, dict) or not required <= value.keys() or value.keys() - required - optional:
        raise Unconfirmed("invalid C2 fields")
    if any(value[k] is None for k in value):
        raise Unconfirmed("null C2 field")
    _missing(value["to"])
    if not value["to"] or not isinstance(value["ref"], str) or not value["ref"]:
        raise Unconfirmed("invalid C2 subject or recipients")
    for field in ("push", "polls"):
        if field in value and value[field] is not True:
            raise Unconfirmed("false optional C2 field must be absent")


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def source_value(value):
    _fields(value, {"ref", "to", "live_url", "server", "as_of"}, {"codec", "push", "polls"})
    if any(not isinstance(value[k], str) for k in ("live_url", "server")) or not _number(value["as_of"]):
        raise Unconfirmed("invalid C2 source")
    if "codec" in value and (not isinstance(value["codec"], str) or not value["codec"]):
        raise Unconfirmed("invalid C2 codec")
    return value


def recording_value(value):
    _fields(value, {"ref", "to", "recording", "role", "enabled", "running"},
            {"coverage", "peer_url", "ingest", "ingest_cluster", "push"})
    if not isinstance(value["recording"], str) or not value["recording"] \
            or value["role"] not in ("primary", "backup", "card") \
            or any(type(value[k]) is not bool for k in ("enabled", "running")):
        raise Unconfirmed("invalid C2 recording")
    if "coverage" in value:
        cov = value["coverage"]
        if not isinstance(cov, dict) or set(cov) != {"from", "to", "fragments"} \
                or any(not _number(cov[k]) for k in ("from", "to")) or type(cov["fragments"]) is not int:
            raise Unconfirmed("invalid C2 coverage")
    if "peer_url" in value and (not isinstance(value["peer_url"], str) or not value["peer_url"]):
        raise Unconfirmed("invalid C2 peer address")
    if "ingest" in value and (not isinstance(value["ingest"], list) or not value["ingest"]
                             or any(not isinstance(u, str) or not u for u in value["ingest"])):
        raise Unconfirmed("invalid C2 ingest addresses")
    if "ingest_cluster" in value and (not isinstance(value["ingest_cluster"], str) or not value["ingest_cluster"] or "ingest" not in value):
        raise Unconfirmed("invalid C3b ingest member")
    if value.get("push") and "ingest" not in value:
        raise Unconfirmed("C2 push requires ingest addresses")
    return value
