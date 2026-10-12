"""Immutable member reports and pinned readers (ADR-0074, supplement 3).

The caller authenticates the original body before accepting it. A digest checks storage integrity; it
is not authentication. A single holder process serializes each member; every store put is atomic.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
import threading

from w2cplatform.canonical import canonical_json, parse_json
from w2cplatform.rows import finite, PARSE_ERRORS
from .federation import MEMBER_OBJECTS, Unreachable
from .uplink import MAX_PUBLICATION, REPORTED, base


class StaleReport(ValueError):
    """An older publication, or different bytes at the same member time (HTTP 409)."""


# Fixed stripes bound memory and serialize wrappers over the same member's store too.
_LOCKS = tuple(threading.RLock() for _ in range(64))


def lock(member):
    return _LOCKS[hash(member) % len(_LOCKS)]


def _rev(value):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 < value <= 2**53-1:
        raise ValueError('report rev is a positive exact JSON integer')
    return value


def _time(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('report time is a finite JSON number')
    return finite(value)


def _body(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_PUBLICATION:
        raise ValueError('report exceeds the publication body limit')
    try:
        pub = parse_json(raw)
    except PARSE_ERRORS as e:
        raise ValueError('report body is not valid JSON') from e
    if not isinstance(pub, dict):
        raise ValueError('report is an object')
    _time(pub.get('sent_at'))
    for part in ('objects', 'rows', 'pages'):
        if not isinstance(pub.get(part), dict):
            raise ValueError('report is missing a complete part')
    if any(not isinstance(page, str) for page in pub['pages'].values()):
        raise ValueError('report pages are text')
    if pub.get('outcomes') is not None and not isinstance(pub['outcomes'], dict):
        raise ValueError('report outcomes are an object')
    for row in pub['rows'].values():
        if not isinstance(row, dict) or not isinstance(row.get('items'), dict) or 'idx' not in row:
            raise ValueError('report has an incomplete row')
    return pub


def _mark(raw):
    mark = parse_json(raw)
    if not isinstance(mark, dict) or set(mark) != {'rev', 'sha256', 'signature', 'sent_at', 'received_at', 'via'}:
        raise ValueError('report mark is incomplete')
    _rev(mark['rev'])
    if not isinstance(mark['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', mark['sha256']):
        raise ValueError('report digest is invalid')
    _time(mark['sent_at'])
    _time(mark['received_at'])
    if not isinstance(mark['signature'], str):
        raise ValueError('report signature is not a string')
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
        raw = store.get(base(member)+'reports/'+str(mark['rev']))
        if raw is None or hashlib.sha256(raw).hexdigest() != mark['sha256']:
            raise ValueError('report body absent or corrupt')
        pub = _body(raw)
        if pub['sent_at'] != mark['sent_at']:
            raise ValueError('report body and mark disagree')
        MEMBER_OBJECTS.parsed(f"{member}/reported")
        return Snapshot(member, raw, mark)
    except PARSE_ERRORS as e:
        MEMBER_OBJECTS.garbled(f"{member}/reported", e)
        raise Unreachable(f'{member} has no complete report') from None


def pinned(member, store):
    """One whole report (or one failure) for every consumer in this logical pass."""
    from .steps import once
    def load():
        try:
            return read(member, store)
        except Unreachable as e:
            return e
    result = once(('report', id(store), member), load)
    if isinstance(result, Exception):
        raise result
    return result


def accept(member, raw: bytes, store, *, received_at: float, via: str = '', signature: str = '') -> Snapshot:
    """Accept authenticated bytes. Only the pointer makes a generation immutable (ADR-0074).

    A crash before the pointer leaves an unaccepted body; the next reception overwrites it under
    the same process mutex. Equal time and digest is idempotent, including after a holder restart.
    """
    pub = _body(raw)
    digest = hashlib.sha256(raw).hexdigest()
    with lock(member):
        pointer = base(member)+REPORTED
        before = store.get(pointer)
        prev = _mark(before) if before is not None else None
        if prev is not None:
            if pub['sent_at'] < prev['sent_at']:
                raise StaleReport('report sent_at is below the accepted publication')
            if pub['sent_at'] == prev['sent_at']:
                if digest != prev['sha256']:
                    raise StaleReport('different publication at the same sent_at')
                return read(member, store)
        rev = _rev(prev['rev'] + 1 if prev else 1)
        mark = {'rev': rev, 'sha256': digest, 'signature': signature,
                'sent_at': pub['sent_at'], 'received_at': _time(received_at), 'via': via}
        encoded = canonical_json(mark).encode()
        _mark(encoded)
        store.put(base(member)+'reports/'+str(rev), raw)
        store.put(pointer, encoded)
        return Snapshot(member, raw, mark)


def prune(member, store):
    """Keep the latest two accepted generations; remove older bodies and unaccepted orphans."""
    with lock(member):
        raw = store.get(base(member)+REPORTED)
        current = _mark(raw)['rev'] if raw is not None else 0
        prefix = base(member)+'reports/'
        versions = sorted((int(k[len(prefix):]), k) for k in store.list(prefix)
                          if k[len(prefix):].isascii() and k[len(prefix):].isdigit())
        accepted = [pair for pair in versions if pair[0] <= current]
        discard = accepted[:-2] + [pair for pair in versions if pair[0] > current]
        for _, key in discard:
            store.delete(key)
        return len(discard)


def export(store):
    """Copy accepted reports under their member mutex, never an orphan or mixed pointer/body pair."""
    from .uplink import UPLINK
    out = {}
    for path in store.list(UPLINK+'/'):
        if not path.endswith('/'+REPORTED):
            continue
        member = path[len(UPLINK)+1:-len('/'+REPORTED)]
        if not member or '/' in member:
            continue
        with lock(member):
            snap = read(member, store)  # fail closed: do not sign an incomplete backup
            prefix = base(member)+'reports/'
            for rev in range(max(1, snap.mark['rev']-1), snap.mark['rev']+1):
                raw = store.get(prefix+str(rev))
                if raw is not None:
                    out[prefix+str(rev)] = raw.decode('utf-8')
            out[path] = canonical_json(snap.mark)
    return out
