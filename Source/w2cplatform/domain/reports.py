"""Immutable member reports and pinned readers (ADR-0074, supplement 3).

The caller authenticates the original body before accepting it. A digest checks storage integrity; it
is not authentication. The store must implement atomic put_new/get_at/put_at: no read-then-write fallback.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re

from w2cplatform.canonical import canonical_json, parse_json
from w2cplatform.rows import finite, PARSE_ERRORS
from .federation import Unreachable
from .uplink import MAX_PUBLICATION, REPORTED, base


class StaleReport(ValueError):
    """A member's sequence is not above the committed sequence."""


def _seq(value):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 < value <= 2**53-1:
        raise ValueError('report seq is a positive exact JSON integer')
    return value


def _body(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_PUBLICATION:
        raise ValueError('report exceeds the publication body limit')
    pub = parse_json(raw)
    if not isinstance(pub, dict):
        raise ValueError('report is an object')
    _seq(pub.get('seq'))
    finite(pub.get('sent_at'))
    for part in ('objects', 'rows', 'pages'):
        if not isinstance(pub.get(part), dict):
            raise ValueError('report is missing a complete part')
    for row in pub['rows'].values():
        if not isinstance(row, dict) or not isinstance(row.get('items'), dict) or 'idx' not in row:
            raise ValueError('report has an incomplete row')
    return pub


def _mark(raw):
    mark = parse_json(raw)
    if not isinstance(mark, dict) or set(mark) != {'seq', 'sha256', 'sent_at', 'received_at', 'via'}:
        raise ValueError('report mark is incomplete')
    _seq(mark['seq'])
    if not isinstance(mark['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', mark['sha256']):
        raise ValueError('report digest is invalid')
    finite(mark['sent_at'])
    finite(mark['received_at'])
    if not isinstance(mark['via'], str):
        raise ValueError('report road is not a name')
    return mark


@dataclass(frozen=True)
class Snapshot:
    """One reader's pinned bytes, independent of later publication, pruning or a holder move."""
    member: str
    raw: bytes
    mark: dict

    def document(self):
        return _body(self.raw)                       # fresh projection: a consumer cannot mutate another's view


def read(member, store) -> Snapshot:
    """Read the pointer once, then only the named immutable body. Missing or corrupt is unknown."""
    try:
        mark = _mark(store.get(base(member)+REPORTED))
        raw = store.get(base(member)+'reports/'+str(mark['seq']))
        if raw is None or hashlib.sha256(raw).hexdigest() != mark['sha256']:
            raise ValueError('report body absent or corrupt')
        pub = _body(raw)
        if pub['seq'] != mark['seq'] or pub['sent_at'] != mark['sent_at']:
            raise ValueError('report body and mark disagree')
        return Snapshot(member, raw, mark)
    except PARSE_ERRORS:
        raise Unreachable(f'{member} has no complete report') from None


def accept(member, raw: bytes, store, *, received_at: float, via: str = '') -> Snapshot:
    """Keep authenticated bytes, then atomically advance the pointer. Concurrent or replayed seq never wins.

    The body is durable before the pointer: the object store's atomic creation contract includes durability.
    A crash before the pointer leaves an orphan, never a partially visible publication.
    """
    pub = _body(raw)
    mark = {'seq': pub['seq'], 'sha256': hashlib.sha256(raw).hexdigest(), 'sent_at': pub['sent_at'],
            'received_at': finite(received_at), 'via': via}
    encoded = canonical_json(mark).encode()
    _mark(encoded)
    pointer = base(member)+REPORTED
    before, index = store.get_at(pointer)
    if before is not None and _mark(before)['seq'] >= pub['seq']:
        raise StaleReport('report seq is not above the committed sequence')
    key = base(member)+'reports/'+str(pub['seq'])
    if not store.put_new(key, raw) and store.get(key) != raw:
        raise ValueError('report seq already names different bytes')
    for _ in range(32):
        if store.put_at(pointer, encoded, index):
            return Snapshot(member, raw, mark)
        before, index = store.get_at(pointer)
        if before is not None and _mark(before)['seq'] >= pub['seq']:
            raise StaleReport('report seq is not above the committed sequence')
    raise Unreachable('report pointer stayed busy')


def prune(member, store):
    """Keep the latest two generations at or below the committed pointer. Leave in-flight bodies alone.

    A reader racing removal either already owns pinned bytes or reports explicit incompleteness; it never
    falls through to another generation. Cleanup does not repair a corrupt or missing committed report.
    """
    current = read(member, store).mark['seq']
    prefix = base(member)+'reports/'
    versions = sorted((int(k[len(prefix):]), k) for k in store.list(prefix)
                      if k[len(prefix):].isascii() and k[len(prefix):].isdigit()
                      and int(k[len(prefix):]) <= current)
    for _, key in versions[:-2]:
        store.delete(key)
    return len(versions[:-2])
