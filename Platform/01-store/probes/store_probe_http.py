"""Small raw-byte collectors/receivers for the owned production probes.

No process discovery/launch, profile changes or implicit connection to a stand.
The caller owns the already permitted isolated socket. Guards limit this
observer; they are not platform timeouts or body/connection limits.
"""
import base64
import hashlib
import json
import re
import socket
import time
from decimal import Decimal

from copy_stream import CopyProtocolError, Reader, chunk_size, field
from store_fitness import InstrumentationError, MissingBinding, number


class CollectionError(InstrumentationError):
    def __init__(self, message, capture):
        super().__init__(message)
        self.capture = capture


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON field ' + key)
            result[key] = value
        return result
    def constant(value):
        raise ValueError('nonfinite JSON constant ' + value)
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_float=Decimal, parse_constant=constant)


def bytes_from(value):
    if not isinstance(value, str):
        raise InstrumentationError('raw bytes must be supplied as base64 text')
    try:
        return base64.b64decode(value, validate=True)
    except ValueError as exc:
        raise InstrumentationError('invalid raw base64') from exc


def packed(raw):
    return base64.b64encode(raw).decode('ascii')


def response(raw, *, closed, line_guard=65536, body_guard=1048576):
    """Parse one ACTUAL response, preserving duplicate headers and exact body.

    A second response/trailing bytes is an error. EOF-delimited replies need an
    independently observed EOF. Copy success uses the stricter CopyBody owner.
    These observer guards can block qualification, never become SUT Faults.
    """
    if not isinstance(raw, bytes) or type(closed) is not bool:
        raise InstrumentationError('response needs raw bytes and actual EOF observation')
    reader = Reader([raw], line_guard)
    line = reader.line()
    match = re.fullmatch(rb'HTTP/1\.[01] ([0-9]{3})(?: [^\r\n]*)?', line)
    if not match:
        raise CopyProtocolError('invalid HTTP response status line')
    status, headers, total = int(match[1]), {}, len(line) + 2
    while (line := reader.line()):
        total += len(line) + 2
        if total > line_guard:
            raise MissingBinding('response exceeds supplied observer header capacity')
        name, value = field(line)
        headers.setdefault(name.decode('ascii'), []).append(value.decode('latin1'))
    lengths, transfer = headers.get('content-length', []), headers.get('transfer-encoding', [])
    if lengths and transfer:
        raise CopyProtocolError('ambiguous response framing')
    if transfer:
        if [x.strip().lower() for v in transfer for x in v.split(',')] != ['chunked']:
            raise CopyProtocolError('unsupported response transfer coding')
        body = bytearray()
        while True:
            size = chunk_size(reader.line())
            if len(body) + size > body_guard:
                raise MissingBinding('response exceeds supplied observer body capacity')
            if not size:
                while (line := reader.line()):
                    name, _ = field(line)
                    if name in (b'content-length', b'transfer-encoding'):
                        raise CopyProtocolError('framing trailer')
                break
            body.extend(reader.exact(size))
            if reader.exact(2) != b'\r\n':
                raise CopyProtocolError('missing chunk CRLF')
        body = bytes(body)
    elif lengths:
        cells = [s.strip() for v in lengths for s in v.split(',')]
        if any(not re.fullmatch('[0-9]+', x) for x in cells):
            raise CopyProtocolError('invalid response length')
        values = {int(x) for x in cells}
        if len(values) != 1:
            raise CopyProtocolError('conflicting response lengths')
        size = values.pop()
        if size > body_guard:
            raise MissingBinding('response exceeds supplied observer body capacity')
        body = reader.exact(size)
    else:
        if not closed:
            raise CopyProtocolError('unframed response has no observed EOF')
        body = bytes(reader.buffer)
        reader.buffer.clear()
        if len(body) > body_guard:
            raise MissingBinding('response exceeds supplied observer body capacity')
    if reader.buffer:
        raise CopyProtocolError('extra bytes/response after framed reply')
    return dict(status=status, headers=headers, body=body, closed=closed)


def fault_errors(reply, status, kind, *, headers=None, required=None, optional=()):
    errors = []
    if reply['status'] != status:
        errors.append('wrong HTTP status: expected ' + str(status))
    try:
        body = strict_json(reply['body'])
    except (ValueError, UnicodeError):
        return errors + ['refusal body is not strict UTF-8 JSON']
    required = required or {}
    fields = {'kind', 'error', *required}
    if (not isinstance(body, dict) or not fields <= body.keys() or
            not body.keys() <= fields | set(optional) or body.get('kind') != kind or
            not isinstance(body.get('error'), str)):
        errors.append('wrong closed Fault form/kind')
    else:
        for key, value in required.items():
            if type(body[key]) is not type(value) or body[key] != value:
                errors.append('wrong Fault field ' + key)
    for key, value in (headers or {}).items():
        actual = reply['headers'].get(key.lower(), [])
        matches = actual == [value]
        if key.lower() == 'connection' and value.lower() == 'close':
            matches = 'close' in [token.strip().lower() for cell in actual for token in cell.split(',')]
        if not matches:
            errors.append('wrong required response header ' + key)
    return errors


def collect(sock, request, *, observer_seconds, byte_guard, half_close=True):
    """A real raw exchange on an explicitly supplied owned/permitted socket.

    Monotonic client events are ACTUAL; they do not prove server accept, start
    of drain, storage activation, applied-id or a server full-send timestamp.
    A timeout is an observer failure, never a fabricated server-close event.
    """
    timeout = float(number(observer_seconds, positive=True))
    if type(byte_guard) is not int or byte_guard <= 0:
        raise InstrumentationError('collector byte_guard must be positive')
    if not isinstance(request, bytes):
        raise InstrumentationError('collector request must be raw bytes')
    start, chunks, closed, received = time.monotonic_ns(), [], False, 0
    deadline = time.monotonic() + timeout
    first = None
    try:
        sock.settimeout(timeout)
        sock.sendall(request)
        sent = time.monotonic_ns()
        if half_close:
            sock.shutdown(socket.SHUT_WR)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('collector deadline expired before observed EOF')
            sock.settimeout(remaining)
            raw = sock.recv(min(65536, byte_guard + 1 - received))
            if not raw:
                closed = True
                break
            if first is None:
                first = time.monotonic_ns()
            chunks.append(raw)
            received += len(raw)
            if received > byte_guard:
                raise InstrumentationError('collector byte guard exhausted')
    except (TimeoutError, socket.timeout) as exc:
        raw = b''.join(chunks)
        capture = dict(request_b64=packed(request), response_b64=packed(raw), closed=False,
                       client_half_closed=half_close, guard_expired=True,
                       client_events_ns=dict(start=start, sent=locals().get('sent'), first=first,
                                             closed=None, guard_expired=time.monotonic_ns()))
        raise CollectionError('raw receiver did not observe close within its declared guard', capture) from exc
    raw = b''.join(chunks)
    return dict(request_b64=packed(request), response_b64=packed(raw), closed=closed,
                client_half_closed=half_close,
                request_sha256=hashlib.sha256(request).hexdigest(),
                response_sha256=hashlib.sha256(raw).hexdigest(),
                client_events_ns=dict(start=start, sent=sent, first=first,
                                      closed=time.monotonic_ns()),
                qualification='client raw exchange only')
