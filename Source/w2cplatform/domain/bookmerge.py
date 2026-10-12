"""Deterministic collection of member rows (ADR-0074), without storage or subsystem code.

The caller supplies authenticated, complete report snapshots for admitted members. None means a member
in its grace window has no usable report; lost members are excluded by the domain view. This module does
not establish freshness, confer writing rights, publish rows or open/reseal secrets. Those remain the
responsibility of the report reader and delivery boundary. The result is a separate row per recipient.
"""
from __future__ import annotations

from dataclasses import dataclass
import json

from w2cplatform.spec import BookMerge


@dataclass
class Collected:
    rows: dict[str, dict[str, str]]
    # Only identities and reasons, never a contribution's value or a parse exception containing it.
    diagnostics: tuple[tuple[str, str, str, str], ...]  # member, item, key (when known), reason
    subjects: dict[str, tuple[str, ...]]  # before recipient projection and unique conflicts
    missing: tuple[str, ...]


def _object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate object field")
        out[key] = value
    return out


def _constant(_):
    raise ValueError("non-finite value")


def _json(value) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    raw.encode("utf-8")                  # lone surrogates are not a value the transport can carry
    return raw


def _rows(rule, report):
    if not isinstance(report, dict):
        raise ValueError("invalid report")
    if not rule.source.endswith("/"):
        return [("", report.get(rule.source, {}))]
    out = []
    for path, row in report.items():
        if not isinstance(path, str):
            raise ValueError("invalid report path")
        if not path.startswith(rule.source):
            continue
        writer = path[len(rule.source):]
        if not writer or "/" in writer or writer in (".", ".."):
            raise ValueError("invalid writer identity")
        out.append((writer, row))
    return sorted(out)


def collect(rule: BookMerge, reports: dict, members, *, lost=()) -> Collected:
    """Collect a book from complete row snapshots, projecting each entry only to its named recipients.

reports[member] is {local_path: {item: JSON object text}}, or None (unknown, never an empty report).
members is the admitted roster; lost is the view's subset past lost_after. Unknown report senders are
ignored. Each call replaces its entire previous result, so a withdrawn row cannot linger in the book.
Grant checks and resealing must precede publication; this function's output alone authorizes no delivery.
"""
    admitted = set(members)
    active = admitted - set(lost)
    missing, diagnostics, candidates, subjects = set(), [], {}, {}
    for member in sorted(active):
        report = reports.get(member)
        if report is None:
            missing.add(member)
            continue
        pending, seen = [], set()
        try:
            for writer, row in _rows(rule, report):
                if not isinstance(row, dict):
                    raise ValueError("invalid input row")
                for item, raw in sorted(row.items()):
                    if not isinstance(item, str) or not item or not isinstance(raw, str):
                        raise ValueError("invalid input item")
                    value = json.loads(raw, object_pairs_hook=_object, parse_constant=_constant)
                    if not isinstance(value, dict):
                        raise ValueError("not an object")
                    key = value.get(rule.key)
                    if not isinstance(key, str) or not key:
                        raise ValueError("invalid key")
                    if rule.pick == "unique" and key in seen:
                        raise ValueError("duplicate key in member")
                    seen.add(key)
                    # Reject overflowed JSON numbers even for a contribution with no admitted destination.
                    _json(value)
                    to = value.get(rule.to)
                    if isinstance(to, str):
                        to = [to]
                    if not isinstance(to, list) or any(not isinstance(m, str) or not m for m in to):
                        raise ValueError("invalid recipients")
                    # One unknown destination invalidates the contribution, not just that destination.
                    # Do not echo a purported recipient: it may contain data from an invalid payload.
                    if set(to) - admitted:
                        diagnostics.append((member, f"{writer}/{item}" if writer else item, key, "unknown recipient"))
                        continue
                    entry = {"member": member, "item": f"{writer}/{item}" if writer else item, "value": value}
                    pending.append((key, entry, set(to)))
        except (ValueError, TypeError, OverflowError, RecursionError, UnicodeError):
            missing.add(member)
            diagnostics.append((member, "", "", "invalid input"))
            continue                          # discard every contribution of this member for this book
        for key in seen:
            subjects.setdefault(key, set()).add(member)
        for key, entry, to in pending:
            candidates.setdefault(key, []).append((entry, to))

    absent = sorted(missing)
    rows = {m: {"": _json({"missing": absent})} for m in sorted(admitted)}
    for key in sorted(candidates):
        entries = sorted(candidates[key], key=lambda e: (e[0]["member"].encode(), e[0]["item"].encode()))
        if rule.pick == "unique" and len(entries) != 1:
            diagnostics.extend((e["member"], e["item"], key, "conflicting key") for e, _ in entries)
            continue
        for recipient in rows:
            selected = [entry for entry, to in entries if recipient in to]
            if selected:
                rows[recipient][key] = _json({"entries": selected, "missing": absent})
    return Collected(rows, tuple(sorted(diagnostics)),
                     {k: tuple(sorted(v)) for k, v in sorted(subjects.items())}, tuple(absent))
