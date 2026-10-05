"""The archive's engine is a PROCESS: `obsd`, one per host, and this is its client."""
# ================================================================================================
# # obsd.py — a client of the ObjectStorage daemon, protocol version 1
#
# The archive is not written by the recorder. It is written by ObjectStorage — the product's storage
# engine, a C++ library — and the library lives in a process of its own, `obsd`, which the OS supervisor
# starts once per host (launchd, systemd: `obsd.service`). Every recorder and every reader on the
# host talks to it over a unix-domain socket. Why a process and not a library (the product's reasons,
# feedback CF): a fault in the engine takes down `obsd`, not every recorder on the box; the recorder's own
# memory is all the recorder's; and the writer — with the volume's lock — lives in the daemon, so a
# recorder that dies and comes back picks up the writer it left instead of waiting out a stale lock.
#
# The protocol is the daemon's README (`ObjectStorage/mmss/ObjectStorage/obsd/README.md`), and this module
# is that README in Python, nothing more:
#
#   frame      u32 len | u32 id | u16 op | u16 flags | i32 status | u32 jsonLen | json | tail   (little-endian)
#   session    HELLO first, on every connection; a session owns handles; BYE closes them cleanly, and a
#              session that merely VANISHES leaves its writers DETACHED for `OBSD_WRITER_GRACE_S`
#   handles    u64, the top byte its kind: 1 volume, 2 reader, 3 writer
#   samples    the platform's own wire record, big-endian:
#              "SMPL" major subtype flags begin end subLen bodyLen sub body
#   time       the archive's: milliseconds since 1900 (`archive_ms`, `unix_s`)
#
# What the engine IS — a volume that is a ring, blocks fixed at format time, sequences that open on a key
# frame, a reader that sees only closed blocks — is not here. It is in the lessons and in the tests that
# run against a live daemon (`tests/test_obsd.py`), because it is the engine's, and the client only says it.
# ================================================================================================
from __future__ import annotations

import json
import os
import socket
import struct
import threading
import time
import uuid
from dataclasses import dataclass, field

PROTO = 1
EPOCH_OFFSET_MS = 2208988800000          # 1900-01-01 to 1970-01-01, in milliseconds: the archive's clock starts in 1900

OP = {"HELLO": 1, "BYE": 2, "PING": 3, "CANCEL": 4, "STATS": 5,
      "VOLUME_OPEN": 10, "VOLUME_CLOSE": 11, "VOLUME_EXISTS": 12, "VOLUME_FORMAT": 13, "VOLUME_RECOVER": 14,
      "VOLUME_SPACE": 15, "VOLUME_MOUNT_RO": 16, "VOLUME_MOUNT_RW": 17,
      "READER_CLOSE": 20, "READER_INFO": 21, "READER_STATUS": 22, "READER_STREAMS": 23, "READER_TIMELINE": 24,
      "READER_SEQUENCES": 25, "READER_FIND": 26, "READ_SEQUENCE": 27,
      "WRITER_CONFIGURE": 30, "PUT_MEDIA": 31, "FINISH_MEDIA": 32, "WRITER_FLUSH": 33, "WRITER_RESIZE": 34,
      "WRITER_CLOSE": 35, "WRITER_ABANDON": 36}

# The engine's status codes, unchanged from its C interface, and the daemon's own.
STATUS = {0: "OK", 1: "GENERIC_ERROR", 2: "PERMISSION_DENIED", 3: "OPERATION_IN_PROGRESS", 4: "OPERATION_CANCELED",
          5: "IO_ERROR", 6: "INTERNAL_ERROR", 7: "DATA_CORRUPTED", 8: "INVALID_CIPHER_KEY", 9: "ALREADY_FORMATTED",
          10: "PATH_NOT_EMPTY", 11: "NOT_A_VOLUME", 12: "ALREADY_LOCKED", 13: "UNSUPPORTED_FORMAT", 14: "READ_ONLY",
          15: "VOLUME_UNCLEAN", 16: "NO_BLOCK", 17: "INVALID_BLOCK_RANGE", 18: "PARTIAL_CONTENT", 19: "EMPTY_RESULT",
          20: "NO_SPACE", 21: "BLOCK_ALREADY_EXISTS", 22: "UNEXPECTED_BLOCK_ID", 23: "PROTECTED_VOLUME",
          24: "DEVICE_OR_RESOURCE_BUSY", 25: "GENERIC_NETWORK_ERROR", 100: "INVALID_ARGUMENT",
          110: "SEQUENCE_SAMPLE_TIME_INVALID", 111: "SEQUENCE_TIME_INVALID", 112: "SEQUENCE_TYPE_CHANGED",
          113: "SEQUENCE_DUPLICATE_INIT_DATA", 114: "SEQUENCE_LATE_INIT_DATA", 115: "SEQUENCE_MISSING_INIT_DATA",
          116: "SEQUENCE_NEEDS_KEY_SAMPLE", 117: "SEQUENCE_DISCONTINUITY", 118: "SEQUENCE_DURATION_INVALID",
          120: "QUEUE_FULL", 121: "WRITER_STOPPED", 122: "SEQUENCE_TOO_LARGE", 123: "SEQUENCE_LOST",
          130: "WRONG_HANDLE_KIND", 131: "INDEX_REPLAY_PENDING",
          1000: "PROTOCOL_ERROR", 1001: "UNKNOWN_HANDLE", 1002: "PROTO_VERSION", 1003: "SHUTTING_DOWN",
          1004: "UNKNOWN_OP", 1005: "FRAME_TOO_LARGE"}
CODE = {v: k for k, v in STATUS.items()}

HEADER = struct.Struct("<IHHiI")          # id, op, flags, status, jsonLen — after the u32 length
REPLY = 1
SMPL = struct.Struct(">4sIIIQQII")        # magic, major, subtype, flags, begin, end, subLen, bodyLen

# The media types and sample flags, as the engine stores them (the product's `storagewrapper/mediatype`).
MAJOR_VIDEO = 2
SUBTYPE_H264 = ord("H") | ord("2") << 8 | ord("6") << 16 | ord("4") << 24
SUBTYPE_H265 = ord("H") | ord("2") << 8 | ord("6") << 16 | ord("5") << 24
FLAG_NEED_KEY_FRAME = 1 << 0              # this sample needs an earlier key frame to decode
FLAG_NEED_PREVIOUS_FRAME = 1 << 3


# Where the course's daemon listens: `/run/vms-obsd/obsd.sock`, the directory of its own that `obsd.service` gives
# it and only the recorder mounts (the review's third pass) — the product's path (its `vms-obsd.service`; the course's
# was /run/obsd until it took the product's names). Not the daemon's built-in `/run/vms/obsd.sock`, which the client
# kept as its default after the unit moved: a recorder started without `OBSD_SOCKET` (М11's job did not set it)
# looked beside the workers' shared memory and found no daemon there, for ever (the review's fourth pass, blocker 3).
# On macOS the daemon's own default, per user — the product's too.
def default_socket() -> str:
    """Where the daemon listens unless told otherwise: `OBSD_SOCKET`, else where `obsd.service` puts it."""
    if os.environ.get("OBSD_SOCKET"):
        return os.environ["OBSD_SOCKET"]
    import sys
    return f"/tmp/vms-obsd-{os.getuid()}.sock" if sys.platform == "darwin" else "/run/vms-obsd/obsd.sock"


# The name a session says in HELLO when its caller names none: the PROCESS's — `python3 -m vms` is `vms`, a script
# `run.py` is `run` — and not a subsystem's. This client is the VMS's (ADR 0001: the archive's engine is the VMS's, and
# the platform knows none); it used to say "vms" for every caller.
def process_name() -> str:
    """This process's name, as HELLO and a session's token carry it: letters, digits, `.`, `_`, `-`."""
    import sys
    arg0 = sys.argv[0] if sys.argv and sys.argv[0] else ""
    base = os.path.basename(arg0)
    if base == "__main__.py":                                   # `python3 -m <package>`: the package
        base = os.path.basename(os.path.dirname(arg0))
    base = base[:-3] if base.endswith(".py") else base
    return "".join(c if c.isalnum() or c in "._-" else "-" for c in base) or "python"


def archive_ms(unix_s: float) -> int:
    """Unix seconds → the archive's milliseconds since 1900."""
    return int(round(float(unix_s) * 1000)) + EPOCH_OFFSET_MS


def unix_s(archive: int) -> float:
    """The archive's milliseconds since 1900 → unix seconds."""
    return (int(archive) - EPOCH_OFFSET_MS) / 1000.0


class ObsdError(Exception):
    """A reply whose status is not OK: `status` (the number), `name` (`STATUS`), `detail` (the engine's own words)."""

    def __init__(self, status: int, op: str, detail: str = ""):
        self.status, self.op, self.detail = status, op, detail
        self.name = STATUS.get(status, f"STATUS_{status}")
        super().__init__(f"{op}: {self.name}" + (f" — {detail}" if detail else ""))


class Unavailable(ObsdError):
    """The daemon is not there: no socket, or it closed the connection. Not an answer about the volume.

    `sent`: the request went out before the silence or the break — the daemon may have DONE it, and its answer is
    what was lost. A `VOLUME_MOUNT_RW` sent and not answered is a writer that may exist in this session with nobody
    holding its handle (the review's fifth pass, blocker 2); one never sent is nothing at all."""

    def __init__(self, op: str, why: str, sent: bool = False):
        super().__init__(-1, op, why)
        self.name, self.sent = "UNAVAILABLE", sent


class SessionLost(Unavailable):
    """The daemon does not know a handle of this session (`UNKNOWN_HANDLE`) that this client never closed: every
    handle the session had is gone.

    Two ways to get here, and the client need not tell them apart (the engine's session, asked): the daemon was
    restarted, or every connection of the session was gone longer than `OBSD_SESSION_LINGER_MS`. Either way the HELLO
    that reconnected under the same token made a NEW, empty session, and `HELLO` does not say so — its `pid` shows a
    restart only where pids do not repeat, and in a container and after a reboot they do. So the rule is the reply: an
    `UNKNOWN_HANDLE` is the engine lost, and the answer is a remount (the review's third pass, blocker 4). Before
    it, the client reconnected in silence, the old handles answered `UNKNOWN_HANDLE`, and a recorder took that for
    a passing outage and wrote into dead handles until somebody restarted it.

    Raised as well, without asking the daemon, for a handle of a daemon that has restarted since (`Session.call`):
    its number may be another handle's by now.

    A handle this client closed ITSELF answers `UNKNOWN_HANDLE` too — a sample that raced its writer's own close —
    and that is `Closed`, not this: nothing was lost but that handle, and counting it as the engine lost said
    remounts and outages that never happened (the review's fourth pass, a minor)."""

    def __init__(self, op: str, why: str):
        super().__init__(op, why)
        self.status, self.name = CODE["UNKNOWN_HANDLE"], "SESSION_LOST"


class Closed(ObsdError):
    """A handle THIS client closed, used after its close (`UNKNOWN_HANDLE` for a handle in `Session.closed`): a
    sample that raced its writer's own `WRITER_CLOSE`, a question on a volume let go a moment before. Not the engine
    lost — the session and every other handle are where they were."""

    def __init__(self, op: str, handle: int):
        super().__init__(CODE["UNKNOWN_HANDLE"], op, f"handle {handle:#x} was closed by this client")
        self.name = "CLOSED"


@dataclass
class Sample:
    """One frame as the engine stores it. `begin`/`end` are the archive's milliseconds; `sub` the coded header."""
    major: int
    subtype: int
    flags: int
    begin: int
    end: int
    sub: bytes = b""
    body: bytes = b""

    @property
    def key(self) -> bool:
        """Can open a sequence: needs neither an earlier key frame nor the frame before it."""
        return not self.flags & (FLAG_NEED_KEY_FRAME | FLAG_NEED_PREVIOUS_FRAME)

    def encode(self) -> bytes:
        return SMPL.pack(b"SMPL", self.major, self.subtype, self.flags, self.begin, self.end,
                         len(self.sub), len(self.body)) + self.sub + self.body

    @classmethod
    def decode_all(cls, data: bytes) -> list["Sample"]:
        out, at = [], 0
        while at < len(data):
            magic, major, subtype, flags, begin, end, sl, bl = SMPL.unpack_from(data, at)
            if magic != b"SMPL":
                raise ValueError(f"not a sample record at byte {at}")
            at += SMPL.size
            out.append(cls(major, subtype, flags, begin, end, data[at:at + sl], data[at + sl:at + sl + bl]))
            at += sl + bl
        return out


def video(begin: int, end: int, body: bytes, key: bool, width: int = 1920, height: int = 1080,
          subtype: int = SUBTYPE_H264) -> Sample:
    """A coded video frame: the coded header is width and height, two little-endian u32."""
    return Sample(MAJOR_VIDEO, subtype, 0 if key else FLAG_NEED_KEY_FRAME, begin, end,
                  struct.pack("<II", width, height), body)


@dataclass
class Entry:
    """A sequence in the index: where it is (block, offset, size) and when (`start`, `end`, archive ms)."""
    streamId: int
    tag: int
    start: int
    end: int
    blockId: int
    offset: int
    size: int

    def to_json(self) -> dict:
        return dict(self.__dict__)


# What is not sent a second time after the connection broke with the request already out: the daemon may have
# done it, and done twice it is not the same thing (`Session.call`).
NOT_RESENT = frozenset({"PUT_MEDIA", "FINISH_MEDIA", "VOLUME_FORMAT", "VOLUME_MOUNT_RW", "WRITER_CLOSE", "WRITER_RESIZE"})


# The ops a READER sends, and a WRITER's: each kind goes on a connection of its own (`Session.call`).
READ_OPS = frozenset({"VOLUME_MOUNT_RO", "READER_CLOSE", "READER_INFO", "READER_STATUS", "READER_STREAMS",
                      "READER_TIMELINE", "READER_SEQUENCES", "READER_FIND", "READ_SEQUENCE"})
WRITE_OPS = frozenset({"WRITER_CONFIGURE", "PUT_MEDIA", "FINISH_MEDIA", "WRITER_FLUSH", "WRITER_RESIZE", "WRITER_CLOSE",
                       "WRITER_ABANDON"})
# The ops that ISSUE a handle, and the field of the reply it comes in (`Session._issued`).
ISSUES = {"VOLUME_OPEN": "volume", "VOLUME_MOUNT_RO": "reader", "VOLUME_MOUNT_RW": "writer"}
_NUMBER = (1 << 56) - 1                   # a handle without its kind: the daemon's counter


class _Lane:
    """One connection of a session: its socket, its own lock, its own request ids."""

    def __init__(self, name: str):
        self.name = name
        self.sock: socket.socket | None = None
        self.lock = threading.Lock()
        self.id = 0
        self.sent: str | None = None                 # the op whose request went out on this attempt
        self.silent_until = 0.0                      # after a silence: fail at once until then (`Session.call`)


class Session:
    """One session with the daemon. Thread-safe: one request at a time on each of its connections.

    A connection that breaks is opened again under the SAME session token — the daemon keeps a session whose
    connection is gone for `OBSD_SESSION_LINGER_MS`, handles and writers included — and the request is sent
    once more. A daemon that does not answer at all is `Unavailable`, which a recorder treats as "the engine
    is lost": remount, at once (feedback CF). A daemon that answers `UNKNOWN_HANDLE` is `SessionLost`: the
    session the token named is gone — restarted, or past its linger — and every handle with it.

    A daemon that takes the request and says nothing is `Unavailable` too, after `timeout` — and is NOT asked
    again: a broken connection is a reason to resend, a silence is not, and asking twice would double the wait
    of whoever is waiting. A caller that renews leases keeps `timeout` shorter than a lease; the one request the
    protocol allows to take long — `WRITER_CLOSE`, after its flush — waits `long_timeout`.

    And a request that was SENT before the connection broke is resent only if sending it twice is harmless. A
    sample, a finish, a format or a mount may have been done by the daemon before the break; done twice, it is
    a frame written twice or a volume formatted twice. Those raise `Unavailable` instead, and the caller decides.

    THREE CONNECTIONS, NOT ONE (the review's third pass). The protocol lets a session have several, any of them
    using any of its handles. On one connection behind one lock with no deadline, everything waited for
    everything: forty streams' samples queued behind a silent daemon ten seconds each, the pass that renews the
    leases behind them, and a long read held every stream's writing. So the writer's ops, the readers' and the
    rest — the pass: open, format, mount, space — each have a connection of their own, and a connection's lock is
    waited for at most `timeout`: one held by a request that does not come back answers `Unavailable` to the next
    caller instead of queueing it. And a connection that went silent fails at once for `timeout` after — the
    pass's budget: a pass that asks twenty things of a daemon that answers none waits for one of them.

    A SESSION LEFT BEHIND (the review's fourth pass, blocker 1). The silent window has a price: a writer whose close
    is refused in it — or whose close did not come back in time — is still the session's, and the session lives on
    in the connections the readers and the pass keep; every new `VOLUME_MOUNT_RW` of the volume then answers
    `ALREADY_LOCKED`, for as long as the process runs. Such a session is `abandon`ed: every connection dropped and
    none opened again, whoever asks. The daemon then does what it does for a process that died — after
    `OBSD_SESSION_LINGER_MS` the writer is DETACHED, its open sequences finished — and the `successor` session, a
    new token, mounts the volume under the same `owner` and gets that writer back (`reattached`). A close sent before
    the silence and answered late closes the old session's handle and nothing else: a handle never repeats, and a
    new session's writer has a handle of its own."""

    def __init__(self, path: str | None = None, client: str | None = None, token: str | None = None,
                 timeout: float = 35.0, log_level: str = "warning", long_timeout: float = 35.0):
        client = client or process_name()                        # the process's name, not a subsystem's
        self.path, self.client, self.timeout, self.log_level = path or default_socket(), client, timeout, log_level
        self.long_timeout = max(long_timeout, timeout)
        self.token = token or f"{client}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        self._lanes: dict[str, _Lane] = {}
        self._guard = threading.Lock()
        self.server: dict = {}
        self.pid = os.getpid()                       # what HELLO says of this client: the process it is
        self.lost = 0                                # how many times the daemon answered UNKNOWN_HANDLE for a handle it lost
        self.closed: dict[int, None] = {}            # handles this client closed itself, newest last (`Closed`)
        self.abandoned = False                       # left behind for the daemon to detach (`abandon`)
        # WHICH DAEMON a handle belongs to (the review's fifth pass). A restarted daemon numbers its handles from the
        # start again, and `closed` outlived the restart: after a second one a handle of the new daemon answered
        # `UNKNOWN_HANDLE`, its number was in `closed` from before the first, and the engine lost read as `Closed` —
        # `lost` never said, the volume never mounted again. So `closed` is one daemon's, and every handle carries the
        # generation it was opened in: one of an earlier daemon is not written down as closed, and is not sent at all.
        #
        # ONE GENERATION PER DAEMON, FOUND WHERE THE DAEMON SHOWS IT (the review's sixth pass). The generation was
        # counted at every `UNKNOWN_HANDLE` instead, and that was wrong twice. A restart first met by a CLOSE — a
        # seal, a remount — answered `Closed` (the handle had just been written down), nothing was emptied, and the
        # new daemon's handles came back under numbers `closed` still held: the next restart read as `Closed` for
        # ever. And every handle of the dead session, answering late on its own thread, counted one more generation
        # and emptied `closed` again — under handles just opened, whose own closes were then not written down: a
        # sample that raced one was the engine lost, and the volume was mounted once more for nothing. A new daemon is
        # known by its HELLO now — another `pid` (`_greeted`): once, by whichever connection meets it first, before a
        # request reaches it. And where pids repeat (a container's daemon is the same pid every time) `closed` is kept
        # right by the numbers themselves (`_issued`): a daemon counts its handles up for its whole life, so the
        # moment it issues number N, nothing numbered N or higher was ever closed in it.
        self.generation = 0
        self._closed_top = 0                         # the highest number in `closed`
        self._abandons: bool | None = None          # does this daemon take WRITER_ABANDON (`abandons`); None: not asked

    # -- the wire -------------------------------------------------------------------------------------
    def lane(self, name: str) -> _Lane:
        with self._guard:
            ln = self._lanes.get(name)
            if ln is None:
                ln = self._lanes[name] = _Lane(name)
            return ln

    @staticmethod
    def lane_of(op: str) -> str:
        return "read" if op in READ_OPS else "write" if op in WRITE_OPS else "pass"

    def _connect(self, ln: _Lane) -> None:
        if self.abandoned:
            raise Unavailable("connect", "this session was abandoned: its writers are the daemon's to detach")
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        try:
            s.connect(self.path)
        except OSError as e:
            s.close()
            raise Unavailable("connect", f"{self.path}: {e}") from None
        ln.sock = s
        if self.abandoned:                           # abandoned while connecting: no HELLO revives it
            self._drop(ln)
            raise Unavailable("connect", "this session was abandoned: its writers are the daemon's to detach")
        self._greeted(self._exchange(ln, "HELLO", {"proto": [PROTO, PROTO], "client": self.client, "pid": self.pid,
                                                   "session": self.token, "logLevel": self.log_level})[0])

    # A HELLO's answer. Another `pid` than the last one is another daemon: what this session knew of the old one — the
    # handles it closed, the numbers it was issued, what the daemon can do — is forgotten, once, by whichever
    # connection meets it first, and before any request of this session reaches the new daemon.
    def _greeted(self, server: dict) -> None:
        with self._guard:
            was, self.server = self.server.get("pid"), server
            if was is not None and server.get("pid") != was:
                self._new_daemon()

    def _new_daemon(self) -> None:                   # under `_guard`
        self.generation += 1
        self.closed.clear()                          # its numbers were the dead daemon's: this one issues them again
        self._closed_top, self._abandons = 0, None

    # A handle the daemon just issued (`call`, still under the connection's lock). Handles of every kind are numbered
    # by one counter for a daemon's whole life, so whatever `closed` holds under this number or a higher one was
    # closed in a daemon that is gone — one restarted under the same `pid`, which no HELLO shows — and is forgotten
    # before this daemon reaches those numbers again.
    def _issued(self, handle: int) -> None:
        n = handle & _NUMBER
        with self._guard:
            if n <= self._closed_top:
                self.closed = {h: None for h in self.closed if h & _NUMBER < n}
                self._closed_top = max((h & _NUMBER for h in self.closed), default=0)

    def _recv(self, ln: _Lane, n: int) -> bytes:
        buf = bytearray()
        while len(buf) < n:
            if self.abandoned:                       # left behind under this call (`abandon`): not waited for
                raise Unavailable("recv", "this session was abandoned: its writers are the daemon's to detach")
            chunk = ln.sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("obsd closed the connection")
            buf += chunk
        return bytes(buf)

    def _exchange(self, ln: _Lane, op: str, js: dict | None, tail: bytes = b"") -> tuple[dict, bytes]:
        ln.id = (ln.id + 1) & 0xFFFFFFFF
        rid = ln.id
        j = json.dumps(js or {}).encode() if js is not None else b""
        body = HEADER.pack(rid, OP[op], 0, 0, len(j)) + j + tail
        ln.sock.sendall(struct.pack("<I", len(body)) + body)
        ln.sent = op
        while True:
            (n,) = struct.unpack("<I", self._recv(ln, 4))
            frame = self._recv(ln, n)
            got, _op, flags, status, jl = HEADER.unpack_from(frame)
            if got != rid:
                continue                                  # a reply to a request we stopped waiting for
            reply = json.loads(frame[HEADER.size:HEADER.size + jl] or b"{}")
            if status == CODE["UNKNOWN_HANDLE"]:
                h = self._handle_of(js, tail)
                if h is not None and h in self.closed:
                    raise Closed(op, h)                   # ours, closed by us: not the engine lost
                with self._guard:
                    self.lost += 1
                    self._abandons = None                 # maybe a daemon started again under the same `pid`: asked anew
                raise SessionLost(op, str(reply.get("detail", "")) or "no such handle in this session")
            if status != 0:
                raise ObsdError(status, op, str(reply.get("detail", "")))
            return reply, frame[HEADER.size + jl:]

    # The handle a request names: in its JSON, or — a sample, a finish — the u64 its tail begins with.
    @staticmethod
    def _handle_of(js: dict | None, tail: bytes) -> int | None:
        for k in ("writer", "reader", "volume"):
            if js and k in js:
                return int(js[k])
        return struct.unpack_from("<Q", tail)[0] if len(tail) >= 8 else None

    # A handle this client is closing: said BEFORE the close goes out, so that a sample racing it — answered
    # `UNKNOWN_HANDLE` the moment the daemon has done the close — is `Closed`, whichever reply comes back first.
    def closing(self, handle: int, generation: int | None = None) -> None:
        with self._guard:
            if generation is not None and generation != self.generation:
                return                                # a handle of a daemon that is gone: its number is not ours now
            self.closed[handle] = None
            self._closed_top = max(self._closed_top, handle & _NUMBER)
            while len(self.closed) > 4096:
                del self.closed[next(iter(self.closed))]

    # `generation`: of the handle the request names (a `Volume`, a `Reader`, a `Writer` passes its own). A handle of a
    # daemon that has restarted since is not sent: the new daemon numbers its handles from the start, and the number
    # may be another handle of this session by now — a late close of a dead reader would close a live one.
    def call(self, op: str, js: dict | None = None, tail: bytes = b"", long: bool = False,
             timeout: float | None = None, generation: int | None = None) -> tuple[dict, bytes]:
        ln = self.lane(self.lane_of(op))
        wait = timeout if timeout is not None else self.long_timeout if long else self.timeout
        if not ln.lock.acquire(timeout=self.timeout):
            raise Unavailable(op, f"the {ln.name} connection is held by a request unanswered for {self.timeout:g} s")
        try:
            if time.monotonic() < ln.silent_until:
                raise Unavailable(op, f"no answer in {wait:g} s on the {ln.name} connection a moment ago")
            for attempt in (0, 1):
                ln.sent = None
                try:
                    if ln.sock is None:
                        self._connect(ln)
                    if generation is not None and generation != self.generation:
                        raise SessionLost(op, "a handle of a daemon that has restarted since: not sent")
                    ln.sock.settimeout(wait)
                    got = self._exchange(ln, op, js, tail)
                    if op in ISSUES:
                        self._issued(int(got[0][ISSUES[op]]))
                    return got
                except ObsdError:
                    if self.abandoned:
                        self._drop(ln)                   # under this lane's lock: nobody else is using its socket
                    raise
                except socket.timeout:
                    sent = ln.sent == op
                    self._drop(ln)
                    ln.silent_until = time.monotonic() + self.timeout
                    raise Unavailable(op, f"no answer in {wait:g} s", sent=sent) from None
                except (OSError, ConnectionError) as e:
                    sent = ln.sent == op
                    self._drop(ln)
                    if self.abandoned:
                        raise Unavailable(op, "this session was abandoned: its writers are the daemon's to detach",
                                          sent=sent) from None
                    if attempt or (sent and op in NOT_RESENT):
                        raise Unavailable(op, str(e), sent=sent) from None
            raise AssertionError("unreachable")
        finally:
            ln.lock.release()

    @staticmethod
    def _drop(ln: _Lane) -> None:
        if ln.sock is not None:
            try:
                ln.sock.close()
            except OSError:
                pass
        ln.sock = None

    # Every connection dropped — from whichever thread, while other threads may be in the middle of a call on them
    # (the review's fifth pass, a minor). Closing a lane's socket and setting it to None under a call in flight was a
    # race: the caller's next `recv` on None was an `AttributeError` — a 500 from the archive's door instead of a 503
    # — and a socket closed under a blocked `recv` left that call its whole timeout on a daemon that was answering. A
    # lane in use is SHUT DOWN instead: its caller's `recv` returns at once, and the caller drops it under its lock.
    def _drop_all(self) -> None:
        with self._guard:
            lanes = list(self._lanes.values())
        for ln in lanes:
            if ln.lock.acquire(blocking=False):
                try:
                    self._drop(ln)
                finally:
                    ln.lock.release()
                continue
            s = ln.sock
            if s is not None:
                try:
                    s.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def silent(self) -> bool:
        """A connection of this session went unanswered a moment ago, and fails at once for now (`call`)."""
        now = time.monotonic()
        with self._guard:
            return any(now < ln.silent_until for ln in self._lanes.values())

    # -- the session --------------------------------------------------------------------------------
    def ping(self) -> None:
        self.call("PING")

    def stats(self) -> dict:
        return self.call("STATS")[0]

    # DOES THIS DAEMON GIVE A VOLUME UP — `WRITER_ABANDON`, operation 36: the engine's patch 07, the only engine this
    # course supports? Asked with a handle that is nobody's: a daemon that has the operation answers that it does not
    # know the handle, one that does not answers `UNKNOWN_OP`. Asked once per daemon (`_new_daemon` forgets the
    # answer). A daemon that does not answer raises `Unavailable`: not knowing is not "yes".
    def abandons(self) -> bool:
        if self._abandons is None:
            self.closing(0)                          # 0 is never issued: said closed, so its answer is `Closed`, not the session lost
            try:
                self.call("WRITER_ABANDON", {"writer": 0})
                known = True
            except Unavailable:
                raise
            except ObsdError as e:
                known = e.name != "UNKNOWN_OP"
            self._abandons = known
        return self._abandons

    def bye(self) -> None:
        """End the session cleanly: every handle closed, writers included, before the reply."""
        try:
            self.call("BYE")
        finally:
            self._drop_all()

    def vanish(self) -> None:
        """Drop every connection WITHOUT `BYE` — what a process that dies does. Its writers are detached and wait."""
        self._drop_all()

    def abandon(self) -> None:
        """`vanish`, for good: no connection of this session is opened again — a reader on another thread that asks
        next gets `Unavailable` instead of a HELLO that would keep the session, and its writers, alive."""
        self.abandoned = True
        self._drop_all()

    def successor(self) -> "Session":
        """This session abandoned, and a new one with the same settings and a token of its own in its place."""
        self.abandon()
        return Session(self.path, client=self.client, timeout=self.timeout, log_level=self.log_level,
                       long_timeout=self.long_timeout)

    def open_volume(self, uri: str | None = None, params: dict | None = None, max_parallel_reads: int = 0) -> "Volume":
        js = {"uri": uri} if uri else {"params": {k: str(v) for k, v in (params or {}).items()}}
        if max_parallel_reads:
            js["maxParallelReads"] = max_parallel_reads
        handle = int(self.call("VOLUME_OPEN", js)[0]["volume"])
        return Volume(self, handle, self.generation)     # read AFTER the answer: the HELLO before it may have found a new daemon


class _Handle:
    """What a `Volume`, a `Reader` and a `Writer` are: a handle of one daemon. Every request that names it carries the
    generation it was issued in, and is not sent to a daemon started since (`Session.call`)."""

    def _call(self, op: str, js: dict | None = None, tail: bytes = b"", **kw) -> tuple[dict, bytes]:
        return self.session.call(op, js, tail, generation=self.generation, **kw)


@dataclass
class Volume(_Handle):
    session: Session
    handle: int
    generation: int = 0                              # the session's when it was opened (`Session.generation`)

    def exists(self) -> bool:
        return bool(self._call("VOLUME_EXISTS", {"volume": self.handle})[0].get("exists"))

    def format(self, size: int, max_block: int = 0, optimal_read: int = 0, label: str = "",
               check_space: bool = False, lock_refresh: int = 0) -> dict:
        tun = {k: v for k, v in (("maxBlockSize", max_block), ("optimalReadSize", optimal_read),
                                 ("lockRefreshSec", lock_refresh)) if v}
        return self._call("VOLUME_FORMAT", {"volume": self.handle, "size": int(size), "label": label,
                                                   "checkSpace": check_space, **({"tunables": tun} if tun else {})})[0]["info"]

    def recover(self) -> int:
        """0 clean, 1 recovered, 2 error."""
        return int(self._call("VOLUME_RECOVER", {"volume": self.handle})[0].get("result", 0))

    def space(self) -> dict:
        return self._call("VOLUME_SPACE", {"volume": self.handle})[0]

    # A reader or a writer is of its volume's generation: the request went to the daemon the volume is a handle of.
    def mount_ro(self) -> "Reader":
        return Reader(self.session, int(self._call("VOLUME_MOUNT_RO", {"volume": self.handle})[0]["reader"]), self.generation)

    def mount_rw(self, owner: str = "") -> "Writer":
        r = self._call("VOLUME_MOUNT_RW", {"volume": self.handle, "owner": owner})[0]
        return Writer(self.session, int(r["writer"]), bool(r.get("reattached")), generation=self.generation)

    def close(self) -> None:
        self.session.closing(self.handle, self.generation)
        self._call("VOLUME_CLOSE", {"volume": self.handle})


def _tail(writer: int, stream: str, sample: Sample | None = None) -> bytes:
    s = stream.encode()
    return struct.pack("<QH", writer, len(s)) + s + (sample.encode() if sample is not None else b"")


@dataclass
class Writer(_Handle):
    """The volume's one writer on this host. `reattached`: the daemon handed back a writer a vanished session
    of the same `owner` left — nothing recovered, no lock waited for."""
    session: Session
    handle: int
    reattached: bool = False
    put_counts: dict = field(default_factory=dict)
    generation: int = 0

    def configure(self, **settings) -> None:
        self._call("WRITER_CONFIGURE", {"writer": self.handle, "settings": settings})

    def put(self, stream: str, sample: Sample) -> str:
        """One sample. Returns `OK` or `SEQUENCE_LOST` (taken — an EARLIER sequence was refused and lost);
        raises `ObsdError` when it was NOT taken (`SEQUENCE_TOO_LARGE`, `WRITER_STOPPED`, `SEQUENCE_*`)."""
        try:
            self._call("PUT_MEDIA", None, _tail(self.handle, stream, sample))
            status = "OK"
        except ObsdError as e:
            if e.name != "SEQUENCE_LOST":
                self.put_counts[e.name] = self.put_counts.get(e.name, 0) + 1
                raise
            status = e.name
        self.put_counts[status] = self.put_counts.get(status, 0) + 1
        return status

    def finish(self, stream: str) -> bool:
        """Close the stream's open sequence. False: nothing was open."""
        try:
            self._call("FINISH_MEDIA", None, _tail(self.handle, stream))
            return True
        except ObsdError as e:
            if e.name == "EMPTY_RESULT":
                return False
            raise

    def flush(self) -> None:
        self._call("WRITER_FLUSH", {"writer": self.handle})

    def resize(self, size: int) -> None:
        self._call("WRITER_RESIZE", {"writer": self.handle, "size": int(size)})

    def close(self, timeout: float | None = None) -> None:
        """After the flush — up to 30 s. What was written becomes readable: the last block is closed. `timeout`: how
        long to wait for that here, when the caller may not wait the protocol's thirty seconds."""
        self.session.closing(self.handle, self.generation)
        self._call("WRITER_CLOSE", {"writer": self.handle}, long=True, timeout=timeout)

    def abandon(self, timeout: float | None = None) -> None:
        """Give the volume up WITHOUT writing anything more — no queued sequence, no status, no index — the lock
        removed only if it is still this writer's: for a volume that is no longer this client's (the engine's patch
        07, `WRITER_ABANDON`). The volume may need recovering at its next mount."""
        self.session.closing(self.handle, self.generation)
        self._call("WRITER_ABANDON", {"writer": self.handle}, timeout=timeout)


@dataclass
class Reader(_Handle):
    session: Session
    handle: int
    generation: int = 0

    def info(self) -> dict:
        return self._call("READER_INFO", {"reader": self.handle})[0]

    def status(self) -> dict:
        return self._call("READER_STATUS", {"reader": self.handle})[0]["status"]

    def streams(self) -> list[str]:
        return list(self._call("READER_STREAMS", {"reader": self.handle})[0].get("streams", []))

    def timeline(self, stream: str, t0: int, t1: int, min_gap: int = 0, mode: str = "") -> list[dict]:
        """Intervals `{start, end, size, streamId}` of `stream` in `[t0, t1]` (archive ms)."""
        return list(self._call("READER_TIMELINE", {"reader": self.handle, "stream": stream, "from": int(t0),
                                                          "to": int(t1), "minGap": int(min_gap), "mode": mode})[0]
                    .get("intervals", []))

    def sequences(self, stream: str, t0: int, t1: int, page_hint: int = 0) -> list[Entry]:
        js = {"reader": self.handle, "stream": stream, "from": int(t0), "to": int(t1)}
        if page_hint:
            js["pageHint"] = page_hint
        return [Entry(**e) for e in self._call("READER_SEQUENCES", js)[0].get("entries", [])]

    def find(self, stream: str, t: int, backwards: bool = False) -> Entry | None:
        r = self._call("READER_FIND", {"reader": self.handle, "stream": stream, "from": int(t),
                                              "backwards": backwards})[0]
        return Entry(**r["entry"]) if r.get("found") else None

    def read(self, entry: Entry) -> list[Sample]:
        _, tail = self._call("READ_SEQUENCE", {"reader": self.handle, "entry": entry.to_json()})
        return Sample.decode_all(tail)

    def close(self) -> None:
        self.session.closing(self.handle, self.generation)
        self._call("READER_CLOSE", {"reader": self.handle})
