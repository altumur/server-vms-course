"""D6 copy transport observation, not a platform server or a copy-format oracle.

The caller supplies raw response fragments and an independently owned artifact
validator. No socket, candidate command, Source lookup or public profile field.
"""
import hashlib
import os
from pathlib import Path
import re
import tempfile


class CopyProtocolError(ValueError):
    pass


class ObservationLimit(ValueError):
    """The observer cannot qualify this input; not an implementation refusal."""


class MissingBinding(ValueError):
    pass


class ArtifactRejected(CopyProtocolError):
    pass


class CopyRefused(CopyProtocolError):
    def __init__(self, status):
        self.status = status
        super().__init__('copy did not start: HTTP ' + str(status))


TOKEN = re.compile(rb"[!#$%&'*+.^_`|~0-9A-Za-z-]+")


def chunk_size(line):
    match = re.match(rb'[0-9A-Fa-f]+', line)
    if not match:
        raise CopyProtocolError('invalid chunk size')
    offset = match.end()
    while offset < len(line):
        while offset < len(line) and line[offset] in b' \t':
            offset += 1
        if offset == len(line):
            raise CopyProtocolError('trailing whitespace in chunk line')
        if line[offset] != ord(';'):
            raise CopyProtocolError('invalid chunk extension')
        offset += 1
        while offset < len(line) and line[offset] in b' \t':
            offset += 1
        name = TOKEN.match(line, offset)
        if not name:
            raise CopyProtocolError('invalid chunk extension name')
        offset = name.end()
        after_name = offset
        while offset < len(line) and line[offset] in b' \t':
            offset += 1
        if offset == len(line):
            if offset != after_name:
                raise CopyProtocolError('trailing whitespace in chunk extension')
            continue
        if line[offset] == ord(';'):
            continue
        if line[offset] != ord('='):
            raise CopyProtocolError('invalid chunk extension value')
        offset += 1
        while offset < len(line) and line[offset] in b' \t':
            offset += 1
        if offset < len(line) and line[offset] == ord('"'):
            offset += 1
            while offset < len(line) and line[offset] != ord('"'):
                byte = line[offset]
                if byte == ord('\\'):
                    offset += 1
                    if offset == len(line):
                        raise CopyProtocolError('incomplete quoted chunk extension')
                    byte = line[offset]
                if byte < 32 and byte != 9 or byte == 127:
                    raise CopyProtocolError('control byte in chunk extension')
                offset += 1
            if offset == len(line):
                raise CopyProtocolError('incomplete quoted chunk extension')
            offset += 1
        else:
            value = TOKEN.match(line, offset)
            if not value:
                raise CopyProtocolError('invalid chunk extension value')
            offset = value.end()
    return int(match[0], 16)


class Reader:
    def __init__(self, fragments, line_guard):
        if type(line_guard) is not int or line_guard <= 0:
            raise ValueError('line_guard must be a positive observer limit')
        self.fragments = iter(fragments)
        self.buffer = bytearray()
        self.line_guard = line_guard

    def more(self):
        for value in self.fragments:
            if not isinstance(value, bytes):
                raise ObservationLimit('raw fragment must be bytes')
            if value:
                self.buffer.extend(value)
                return True
        return False

    def line(self):
        while True:
            end = self.buffer.find(b'\r\n')
            if end >= 0:
                if end > self.line_guard:
                    raise ObservationLimit('HTTP line exceeds observer guard')
                out = bytes(self.buffer[:end])
                del self.buffer[:end + 2]
                return out
            if len(self.buffer) > self.line_guard:
                raise ObservationLimit('HTTP line exceeds observer guard')
            if not self.more():
                raise CopyProtocolError('incomplete HTTP line')

    def piece(self, limit):
        while not self.buffer:
            if not self.more():
                raise CopyProtocolError('incomplete framed copy body')
        size = min(limit, len(self.buffer), 65536)
        value = bytes(self.buffer[:size])
        del self.buffer[:size]
        return value

    def exact(self, length):
        out = bytearray()
        while len(out) < length:
            out.extend(self.piece(length - len(out)))
        return bytes(out)


def field(line):
    name, separator, value = line.partition(b':')
    if not separator or not TOKEN.fullmatch(name) or b'\r' in value or b'\n' in value:
        raise CopyProtocolError('invalid HTTP header/trailer')
    if any(byte < 32 and byte != 9 or byte == 127 for byte in value):
        raise CopyProtocolError('control byte in HTTP field')
    return name.lower(), value.strip(b' \t')


class CopyBody:
    """A streaming, explicitly framed 200 copy, completed without waiting for EOF.

    Unsupported transfer/content codings and observer limits are qualification
    gaps, not new platform rejection rules. Only already observed bytes after
    completion can be diagnosed; this observer never waits for a second reply.
    """
    def __init__(self, fragments, *, line_guard=65536):
        self.reader = Reader(fragments, line_guard)
        line = self.reader.line()
        match = re.fullmatch(rb'HTTP/1\.[01] ([0-9]{3})(?: [^\r\n]*)?', line)
        if not match:
            raise CopyProtocolError('copy needs an HTTP status line, no private prelude')
        self.status = int(match[1])
        self.headers = {}
        header_bytes = len(line) + 2
        while (line := self.reader.line()):
            header_bytes += len(line) + 2
            if header_bytes > line_guard:
                raise ObservationLimit('response headers exceed observer guard')
            key, value = field(line)
            self.headers.setdefault(key, []).append(value)
        if 100 <= self.status < 200:
            raise ObservationLimit('informational responses need a separately qualified response sequence')
        if self.status != 200:
            # The caller judges the owned Fault separately. A read refusal is
            # never a successful copy or a write's AmbiguousFault.
            raise CopyRefused(self.status)
        media = self.headers.get(b'content-type', [])
        if len(media) != 1 or media[0].split(b';', 1)[0].strip().lower() != b'application/x-ndjson':
            raise CopyProtocolError('copy media must be application/x-ndjson')
        encoding = self.headers.get(b'content-encoding', [])
        if encoding and encoding != [b'identity']:
            raise ObservationLimit('content coding needs a separately qualified decoder')
        length = self.headers.get(b'content-length', [])
        transfer = self.headers.get(b'transfer-encoding', [])
        if length and transfer:
            raise CopyProtocolError('ambiguous transfer-encoding/content-length')
        if transfer:
            tokens = [x.strip().lower() for value in transfer for x in value.split(b',')]
            if tokens != [b'chunked']:
                raise ObservationLimit('transfer coding needs a separately qualified decoder')
            self.framing, self.length = 'chunked', None
        elif length:
            values = [x.strip() for value in length for x in value.split(b',')]
            if not values or any(not re.fullmatch(rb'[0-9]+', x) for x in values):
                raise CopyProtocolError('invalid Content-Length')
            try:
                numbers = [int(x) for x in values]
            except ValueError as error:
                raise ObservationLimit('Content-Length exceeds observer integer capacity') from error
            if len(set(numbers)) != 1:
                raise CopyProtocolError('conflicting Content-Length')
            self.framing, self.length = 'content-length', numbers[0]
        else:
            raise CopyProtocolError('EOF alone cannot complete a successful copy')
        self.complete = False
        self.started = False
        self.bytes = 0
        self.digest = hashlib.sha256()

    def parts(self):
        if self.started:
            raise ValueError('copy body already consumed')
        self.started = True
        remaining = self.length
        while True:
            if self.framing == 'chunked':
                line = self.reader.line()
                remaining = chunk_size(line)
                if remaining == 0:
                    trailer_bytes = 0
                    while (line := self.reader.line()):
                        trailer_bytes += len(line) + 2
                        if trailer_bytes > self.reader.line_guard:
                            raise ObservationLimit('response trailers exceed observer guard')
                        key, _ = field(line)
                        if key in (b'content-length', b'transfer-encoding'):
                            raise CopyProtocolError('framing field in trailer')
                    break
            elif remaining == 0:
                break
            while remaining:
                value = self.reader.piece(remaining)
                remaining -= len(value)
                self.bytes += len(value)
                self.digest.update(value)
                yield value
            if self.framing == 'chunked' and self.reader.exact(2) != b'\r\n':
                raise CopyProtocolError('missing CRLF after chunk')
        if self.reader.buffer:
            raise CopyProtocolError('bytes already observed after completed response')
        self.complete = True


def publish_copy(fragments, destination, *, validate_artifact, line_guard=65536):
    """Validate complete framing AND artifact before replacing a prior copy.

    validate_artifact(path) must return a list of errors; [] means the exact
    owned copy-artifact grammar passed. This function never replaces that
    validator or proves a snapshot's consistency by two sequential GETs.
    """
    if not callable(validate_artifact):
        raise MissingBinding('an independent owned copy artifact validator is required')
    response = CopyBody(fragments, line_guard=line_guard)
    destination = Path(destination)
    fd, name = tempfile.mkstemp(prefix='.' + destination.name + '.', dir=destination.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            os.fchmod(stream.fileno(), 0o600)
            for part in response.parts():
                stream.write(part)
            stream.flush()
            os.fsync(stream.fileno())
        errors = validate_artifact(temporary)
        if not isinstance(errors, list) or any(not isinstance(x, str) for x in errors):
            raise MissingBinding('artifact validator must return a list of errors')
        if errors:
            raise ArtifactRejected('; '.join(errors))
        os.replace(temporary, destination)
        return dict(complete=True, framing=response.framing, bytes=response.bytes,
                    sha256=response.digest.hexdigest(), artifact_validated=True)
    finally:
        temporary.unlink(missing_ok=True)
