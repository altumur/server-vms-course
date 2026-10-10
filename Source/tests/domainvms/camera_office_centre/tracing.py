"""The trace of the camera–office–centre stand: what every process says to every store and every door, as the notes
show it.

The cluster stand's `TraceLog` (`tests/cluster/trace.py`) records a store's requests and answers as the handle sends them;
this one records four more kinds, and prints every value nobody could read the same twice — a signature, a key, a
token, a sealed secret — as a short placeholder, numbered in the order it first appears in one printed trace:

    http     a real HTTP request on loopback, recorded where the client sends it (`urllib.request.urlopen`, wrapped in
             this process) — the agents' `/api/carry`, a person's `/domain/*`, a console handing a request to the
             signer — and the token door's requests on its unix socket (`TokenDoor`'s transport). `who` is whoever the
             scenario said is acting, or the door whose handler made the request
    ingest   a call of an `Ingest` method — the camera's poll and push, the forwarder's at the centre. The course has
             no wire there (Track 2): the line is printed in the PRODUCT's route words (`recproc/ingest.go`), marked
    flash    the camera's store: a `FakeVariables` behind the camera's `Flash`, read and written by its processes —
             printed in the configstore's words, marked as the camera's flash
    note     a line of the scenario's own: who does what, and where the course has a call where the product has a wire

Nothing here changes what the code does: the wrappers call through, and the placeholders are only in what is printed.
"""
from __future__ import annotations

import base64
import contextlib
import io
import json
import os
import random
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from urllib.parse import unquote, urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))          # Source/
if SOURCE not in sys.path:
    sys.path.insert(0, SOURCE)

from tests.cluster.trace import Call, TraceLog, body_shown  # noqa: E402

BASE = 1_757_500_000.0                    # the stand's wall clock at the start of every run


# -- determinism ---------------------------------------------------------------------------------------------------------
class Wall:
    """The stand's one wall clock: every cluster's, every process's — and `time.time` itself, for the code that asks
    the module (the signer's tokens, a member's report mark). It moves only when the scenario says."""

    def __init__(self, t: float = BASE):
        self.t, self.watchers = t, []

    def __call__(self) -> float:
        return self.t

    def advance(self, s: float) -> None:
        for ctl in list(self.watchers):
            try:
                ctl.look()
            except Exception:                 # noqa: BLE001 — a store a scene took away: that controller saw nothing
                pass
        self.t += s


def deterministic(seed: int = 7, wall: Wall | None = None) -> Wall:
    """Every source of chance the code draws from, seeded, and `time.time` on the stand's clock: one run prints what
    the next prints. Keys (Ed25519, X25519), nonces, serial numbers, token ids, salts — all from one generator."""
    import secrets  # noqa: F401 — imported so that its module is the one patched below
    from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
    rng = random.Random(seed)

    def urandom(n: int) -> bytes:
        return bytes(rng.getrandbits(8) for _ in range(n))
    os.urandom = urandom
    random._urandom = urandom                                           # `SystemRandom`, so `secrets` too
    random.seed(seed)
    ed25519.Ed25519PrivateKey.generate = classmethod(lambda cls: ed25519.Ed25519PrivateKey.from_private_bytes(urandom(32)))
    x25519.X25519PrivateKey.generate = classmethod(lambda cls: x25519.X25519PrivateKey.from_private_bytes(urandom(32)))
    wall = wall or Wall()
    time.time = wall                                                    # noqa — the whole process on the stand's clock
    return wall


# -- the calls -------------------------------------------------------------------------------------------------------------
@dataclass
class XCall(Call):
    headers: dict = field(default_factory=dict)
    note: str = ""                       # printed after the `# who → door` line: where the course and the product differ
    ref: object = None                   # an `answer`: the call it answers
    later: bool = False                  # a call whose answer is printed after what it caused (an `answer` of its own)

    @property
    def op(self) -> str:
        """The store's words for a camera's flash too: `get`, `list`, `put`, `delete`."""
        if self.kind in ("store", "flash"):
            if self.target.startswith("/v1/get"):
                return "get"
            if self.target.startswith("/v1/list"):
                return "list"
            if isinstance(self.body, dict):
                return str(self.body.get("op", self.method))
        return self.method


_actor = threading.local()


class _Calls(list):
    """The calls, with nothing appended while the log is muted — the cluster stand's object stores append themselves."""

    def __init__(self, log):
        super().__init__()
        self.log = log

    def append(self, c) -> None:
        if not self.log.quiet:
            super().append(c)


class Log(TraceLog):
    """`TraceLog` with the kinds above, a placeholder for everything random, and `hosts`: loopback addresses printed as the
    stand's names (`127.0.0.1:50123` → `srv:8445`)."""

    def __init__(self, roots: dict | None = None):
        super().__init__(roots=dict(roots or {}))
        self.calls = _Calls(self)                      # the stand's object stores append here directly
        self.hosts: dict[str, str] = {}
        self.quiet = 0                   # > 0: nothing is recorded (a scene's set-up that is not its subject)
        self.blocked = None              # (who, url) -> why the request does not get through, or None (a failure scene)
        self.lock = threading.Lock()

    # who is acting ------------------------------------------------------------------------------------------------------
    @contextlib.contextmanager
    def acting(self, who: str):
        was = getattr(_actor, "who", None)
        _actor.who = who
        try:
            yield
        finally:
            _actor.who = was

    @staticmethod
    def actor(default: str = "?") -> str:
        return getattr(_actor, "who", None) or default

    @contextlib.contextmanager
    def muted(self):
        self.quiet += 1
        try:
            yield
        finally:
            self.quiet -= 1

    def add(self, c: Call) -> Call | None:
        if self.quiet:
            return None
        with self.lock:
            self.calls.append(c)
        return c

    def mark(self) -> int:
        return len(self.calls)

    def answered(self, c, status: int, answer) -> None:
        """`c`'s answer has come: printed with its request when nothing was recorded in between, else where it came —
        after the requests the door made to answer it."""
        if c is None:
            return
        c.status, c.answer = status, answer
        if self.calls and self.calls[-1] is not c and c in self.calls:
            c.later = True
            self.add(XCall(c.who, c.door, c.method, c.target, None, status, answer, kind="answer", ref=c))

    def note(self, text: str) -> None:
        """A line of the scenario's own, printed as a comment."""
        self.add(XCall("", "", "", "", None, 0, None, kind="note", note=text))

    # the store: the cluster stand's wrapper, muted with the rest ---------------------------------------------------------
    def transport(self, who: str, door: str, inner):
        def call(method, target, raw, headers, timeout):
            code, got = inner(method, target, raw, headers, timeout)
            if not self.quiet:
                try:
                    answer = json.loads(got or b"{}")
                except ValueError:
                    answer = got.decode(errors="replace")
                self.add(XCall(who, door, method, target, json.loads(raw) if raw else None, code, answer))
            return code, got
        return call

    # http ---------------------------------------------------------------------------------------------------------------
    def door_name(self, url: str) -> str:
        u = urlsplit(url)
        return self.hosts.get(u.netloc, u.netloc)

    def record_http(self, who: str, method: str, url: str, headers: dict, body, note: str = "") -> XCall | None:
        u = urlsplit(url)
        target = u.path + (f"?{u.query}" if u.query else "")
        shown = {k: v for k, v in headers.items() if k.lower() in SHOWN_HEADERS}
        return self.add(XCall(who, self.door_name(url), method, target, body, 0, None, kind="http", headers=shown,
                              note=note))

    def transport_http(self, who: str, door: str, inner):
        """A unix-socket door's transport (`TokenDoor`), recorded as HTTP."""
        def call(method, target, raw, headers, timeout):
            c = None if self.quiet else self.add(XCall(who, door, method, target, json.loads(raw) if raw else None, 0,
                                                       None, kind="http"))
            code, got = inner(method, target, raw, headers, timeout)
            self.answered(c, code, _parsed(got))
            return code, got
        return call

    # rendering ----------------------------------------------------------------------------------------------------------
    def render(self, since: int = 0, until: int | None = None, who: bool = True, width: int = 110,
               writes: bool = False, kinds: tuple | None = None, brief: bool = False, names=None) -> str:
        """`brief`: the reads of the stores left out — the doors, the calls the course has no wire for, the objects, the
        scenario's lines and every write stay. The placeholders are numbered as in the whole trace."""
        if names is None:
            names = Names()
            if brief:                                    # the placeholders numbered exactly as the whole trace numbers them
                self.render(since, until, who, width, writes, kinds, False, names)
        out = []
        calls = self.calls[since:until]

        def shown(c) -> bool:
            if writes and not c.write:
                return False
            if kinds is not None and c.kind not in kinds and c.kind != "answer":
                return False
            return not (brief and c.kind in ("store", "flash") and not c.write)
        visible = [i for i, c in enumerate(calls) if shown(c)]
        answer_at = {id(c.ref): i for i, c in enumerate(calls) if c.kind == "answer"}
        inline = set()                                  # requests whose answer is printed with them after all
        for k, i in enumerate(visible):
            c = calls[i]
            j = answer_at.get(id(c))
            if getattr(c, "later", False) and j is not None and (k + 1 >= len(visible) or visible[k + 1] == j):
                inline.add(id(c))
        for c in calls:
            if not shown(c):
                names.walk(c.body)                       # numbered as in the whole trace, shown or not
                names.walk(c.answer)
                continue
            if c.kind == "note":
                out += [f"## {names.text(line)}" if line else "##" for line in c.note.split("\n")]
                out.append("")
                continue
            if c.kind == "answer":
                if id(c.ref) in inline:
                    continue
                if who:
                    out.append(f"# {c.who} ← {c.door}: ответ на {c.method} {unquote(c.target)}")
                out += [self._answer(c, width, names), ""]
                continue
            if who:
                out.append(f"# {c.who} → {c.door}")
            if getattr(c, "note", ""):
                out += [f"#   {line}" for line in c.note.split("\n")]
            out += self._lines(c, width, names)
            if getattr(c, "later", False) and id(c) not in inline:
                out += ["→ …", ""]
                continue
            if c.kind != "file":
                out.append(self._answer(c, width, names))
            out.append("")
        return self._clean("\n".join(out).rstrip() + "\n")

    @staticmethod
    def _answer(c: Call, width: int, names: "Names") -> str:
        ans = names.walk(c.answer)
        text = "" if ans is None else " " + json.dumps(ans, ensure_ascii=False,
                                                       indent=2 if len(json.dumps(ans, ensure_ascii=False)) > width else None)
        return f"→ {c.status}{text}"

    def _lines(self, c: Call, width: int, names: "Names") -> list[str]:
        line = f"{c.method} {unquote(c.target)}"
        heads = [f"  {CANONICAL.get(k.lower(), k)}: {names.header(k, v)}"
                 for k, v in (getattr(c, "headers", None) or {}).items()]
        if c.body is None:
            return [line, *heads]
        body = body_shown(c.body) if c.kind in ("store", "flash") else c.body
        body = names.walk(body)
        whole = f"{line} {json.dumps(body, ensure_ascii=False)}"
        if len(whole) <= width or not isinstance(body, dict) or not isinstance(body.get("items"), dict) or not body["items"]:
            if len(whole) > width and isinstance(body, dict) and c.kind in ("http", "ingest"):
                return [line, *heads, json.dumps(body, ensure_ascii=False, indent=2)]
            return [whole, *heads]
        head = {k: v for k, v in body.items() if k != "items"}
        first = json.dumps(head, ensure_ascii=False)[:-1] + ', "items": {'
        rows = [f'  {json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False)}'
                for k, v in body["items"].items()]
        return [f"{line} {first}", *[r + "," for r in rows[:-1]], rows[-1], "}}", *heads]


CANONICAL = {"authorization": "Authorization", "x-w2c-time": "X-W2C-Time", "x-w2c-seal": "X-W2C-Seal",
             "x-w2c-signature": "X-W2C-Signature", "idempotency-key": "Idempotency-Key", "x-operator": "X-Operator",
             "x-camera-clock": "X-Camera-Clock"}
SHOWN_HEADERS = ("authorization", "x-w2c-time", "x-w2c-seal", "x-w2c-signature", "idempotency-key", "x-operator",
                 "x-camera-clock")


def _parsed(raw):
    try:
        return json.loads(raw or b"{}")
    except ValueError:
        return raw.decode(errors="replace") if isinstance(raw, bytes) else raw


# -- placeholders ----------------------------------------------------------------------------------------------------------
HEX = re.compile(r"^[0-9a-f]+$")
TOKEN = re.compile(r"^[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{40,}$")
B64 = re.compile(r"^[A-Za-z0-9+/=_-]{100,}$")


class Names:
    """Placeholders for what is drawn by chance, numbered by first appearance in one printed trace: the same value is the
    same placeholder everywhere in it."""

    def __init__(self):
        self.seen: dict[tuple[str, str], str] = {}
        self.count: dict[str, int] = {}

    def name(self, kind: str, value: str, extra: str = "") -> str:
        key = (kind, value)
        if key not in self.seen:
            self.count[kind] = self.count.get(kind, 0) + 1
            self.seen[key] = f"«{kind} {self.count[kind]}{extra}»"
        return self.seen[key]

    def text(self, line: str) -> str:
        """A line of the scenario's: a long hex in it (a key it prints) is the placeholder the trace uses for it."""
        return re.sub(r"\b[0-9a-f]{32,}\b", lambda m: self.one("key", m.group(0)), line)

    def header(self, k: str, v: str) -> str:
        if k.lower() == "authorization" and v.startswith("Bearer "):
            return "Bearer " + self.one("token", v[7:])
        return self.one(k.lower(), v)

    def one(self, key: str, v: str) -> str:
        if not isinstance(v, str) or not v:
            return v
        if v.startswith("enc:v1:"):
            return self.name("запечатано кольцом", v)
        if v.startswith("x25519:v1:"):
            return self.name("запечатано ключу члена", v)
        if key == "sig" and len(v) >= 40:
            return self.name("подпись", v)
        if v.isdigit() and len(v) >= 20:
            return self.name("серийный номер", v)
        if TOKEN.match(v):
            return self.name("токен", v, _token_says(v))
        if v.startswith("-----BEGIN"):
            return self.name("сертификат", v)
        if HEX.match(v) and len(v) >= 32:
            k = key.lower()
            if len(v) == 128 or "sig" in k:
                return self.name("подпись", v)
            if "sha" in k or "hash" in k:
                return self.name("sha256", v)
            if "secret" in k or "seed" in k:
                return self.name("секрет", v)
            return self.name("ключ", v)
        if key.endswith("_secret") or key in ("pwhash", "hash"):
            return self.name("секрет", v)
        if B64.match(v) and len(v) >= 100:
            try:
                n = len(base64.b64decode(v + "=" * (-len(v) % 4), altchars=b"-_" if ("-" in v or "_" in v) else None))
            except (ValueError, TypeError):
                return v
            return self.name("base64", v, f", {n} байт")
        if v[:1] in "{[" and len(v) > 2:
            try:
                inner = json.loads(v)
            except ValueError:
                return v
            if isinstance(inner, (dict, list)):
                return json.dumps(self.walk(inner), ensure_ascii=False)
        return v

    def walk(self, x, key: str = ""):
        if isinstance(x, dict):
            return {k: self.walk(v, str(k)) for k, v in x.items()}
        if isinstance(x, list):
            return [self.walk(v, key) for v in x]
        if isinstance(x, str):
            return self.one(key, x)
        return x


def _token_says(token: str) -> str:
    """What a token of the domain names, briefly: its kind, subject, audience and what it is for — not its signature."""
    try:
        p = json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "=" * (-len(token.split(".")[1]) % 4)))
    except (ValueError, IndexError):
        return ""
    parts = [str(p.get("kind", "person"))]
    for k in ("sub", "aud", "ref", "for", "to"):
        if k in p:
            parts.append(f"{k}={p[k]}")
    if "exp" in p and "iat" in p:
        parts.append(f"на {p['exp'] - p['iat']:.0f} с")
    return ": " + " ".join(parts)


# -- http, recorded where the client sends it ------------------------------------------------------------------------------
class _Answer(io.BytesIO):
    """A response read whole, handed back as `urlopen` would have: `status`, `read`, a context manager."""

    def __init__(self, status: int, raw: bytes, headers):
        super().__init__(raw)
        self.status, self.code, self.headers = status, status, headers

    def getcode(self):
        return self.status

    def info(self):
        return self.headers


def trace_http(log: Log) -> None:
    """`urllib.request.urlopen`, wrapped: each request recorded before it goes (so a request a door makes while it
    answers another is printed after the one that caused it), its answer after."""
    import urllib.error
    import urllib.request
    real = getattr(urllib.request, "_coc_real_urlopen", None) or urllib.request.urlopen
    urllib.request._coc_real_urlopen = real

    def urlopen(req, data=None, timeout=None, **kw):
        if isinstance(req, str):
            req = urllib.request.Request(req, data=data)
        raw = req.data
        try:
            body = json.loads(raw) if raw else None
        except ValueError:
            body = {"bytes": len(raw)}
        c = log.record_http(log.actor(), req.get_method(), req.full_url, dict(req.header_items()), body)
        why = log.blocked(log.actor(), req.full_url) if log.blocked is not None else None
        if why:                                         # a box off, a road cut: the request never arrives
            log.answered(c, 0, f"no answer: {why}")
            raise urllib.error.URLError(why)
        try:
            r = real(req, timeout=timeout) if timeout is not None else real(req)
            got = r.read()
            log.answered(c, r.status, _parsed(got))
            return _Answer(r.status, got, r.headers)
        except urllib.error.HTTPError as e:
            got = e.read()
            log.answered(c, e.code, _parsed(got))
            raise urllib.error.HTTPError(e.url, e.code, e.msg, e.hdrs, io.BytesIO(got)) from None
        except OSError as e:
            log.answered(c, 0, f"no answer: {type(e).__name__}")
            raise
    urllib.request.urlopen = urlopen


def served_as(log: Log, who: str, handler):
    """A door's handler whose requests ARE `who` acting: a request it makes while answering is printed as its."""
    class H(handler):
        def handle_one_request(self):
            with log.acting(who):
                return super().handle_one_request()
    H.__name__ = handler.__name__
    return H


# -- the ingest: a call, printed as the product's request ------------------------------------------------------------------
# Each `Ingest` method the camera and the forwarder call, and the product's route for it (`recproc/ingest.go`).
INGEST_ROUTES = {
    "poll": ("GET", "/ingest/{ref}/poll"),
    "push": ("POST", "/ingest/{ref}/live"),
    "upload": ("POST", "/ingest/{ref}/range/{rid}"),
    "answer_ask": ("POST", "/ingest/{ref}/answer/{aid}"),
    "ask": ("POST", "/ingest/{target}/ask"),
    "ask_outcome": ("GET", "/ingest/{target}/ask/{aid}"),
    "outcome_wait": ("GET", "/ingest/{target}/ask/{aid}"),
    "pull": ("GET", "/ingest/{ref}/stream"),
    "fetch_range": ("POST", "/ingest/{ref}/fetch"),
    "want": ("RTSP", "rtsp://…/ingest/{ref}"),
}


class TracedIngest:
    """An `Ingest` as one caller reaches it: every call of `INGEST_ROUTES` recorded (kind `ingest`), the rest passed."""

    def __init__(self, log: Log, inner, who: str, door: str):
        self._log, self._inner, self._who, self._door = log, inner, who, door

    def __getattr__(self, name):
        attr = getattr(self._inner, name)
        if name not in INGEST_ROUTES or not callable(attr):
            return attr

        def call(*a, **kw):
            method, route = INGEST_ROUTES[name]
            args = _ingest_args(name, a, kw)
            target = route.format(**{k: args.get(k, "") for k in ("ref", "target", "rid", "aid")})
            shown = {k: v for k, v in args.items() if k not in ("ref", "target", "rid", "aid", "token")}
            headers = {"Authorization": f"Bearer {args['token']}"} if args.get("token") else {}
            note = f"в курсе — вызов Ingest.{name} в процессе; у продукта {method} {target} (recproc/ingest.go)"
            c = self._log.add(XCall(self._who, self._door, method, target, shown or None, 0, None, kind="ingest",
                                    headers=headers, note=note))
            try:
                got = attr(*a, **kw)
            except Exception as e:                      # noqa: BLE001 — recorded, and raised as it was
                self._log.answered(c, 0, f"{type(e).__name__}: {e}")
                raise
            self._log.answered(c, 200, _shown_answer(name, got))
            return got
        return call


_INGEST_PARAMS = {
    "poll": ("token", "ref", "camera_now", "version", "wait"),
    "push": ("token", "ref", "frames", "camera_now", "rtt"),
    "upload": ("token", "ref", "rid", "samples", "camera_now"),
    "answer_ask": ("token", "ref", "aid", "outcome"),
    "ask": ("token", "target", "action", "deadline", "camera_now"),
    "ask_outcome": ("target", "aid"),
    "outcome_wait": ("target", "aid", "wait"),
    "pull": ("token", "ref", "who", "have"),
    "fetch_range": ("ref", "t0", "t1", "wait", "recording"),
    "want": ("ref", "who", "until"),
}


def _ingest_args(name: str, a: tuple, kw: dict) -> dict:
    out = dict(zip(_INGEST_PARAMS[name], a))
    out.update(kw)
    for k in ("frames", "samples"):
        if k in out:
            out[k] = _frames(out[k])
    return {k: v for k, v in out.items() if v is not None}


def _frames(frames) -> str | list:
    """Frames as the trace shows them: how many, from when to when, which are keyframes."""
    try:
        frames = list(frames)
    except TypeError:
        return repr(frames)
    ts = []
    for f in frames:
        if isinstance(f, dict):
            ts.append(f.get("t"))
        elif hasattr(f, "begin"):
            from vms.obsd import unix_s
            ts.append(unix_s(f.begin))
    ts = [t for t in ts if isinstance(t, (int, float))]
    if not frames:
        return []
    if ts:
        return f"{len(frames)} кадров, t {min(ts):.1f}…{max(ts):.1f}"
    return f"{len(frames)} кадров"


def _shown_answer(name: str, got):
    if name in ("pull",):
        return _frames(got)
    if isinstance(got, (dict, list, str, int, float, bool)) or got is None:
        return got
    if isinstance(got, tuple):
        return list(got)
    return repr(got)


# -- the camera's flash ------------------------------------------------------------------------------------------------------
class TracedVars:
    """One process's handle on the camera's flash (a `FakeVariables`): each read and write recorded in the configstore's
    words (kind `flash`). The camera has no configstore daemon; the flash is its one writer's store (М12A Lesson 10)."""

    def __init__(self, log: Log, inner, who: str, door: str):
        self.log, self.inner, self.who, self.door = log, inner, who, door

    def _rec(self, method, target, body, status, answer):
        self.log.add(XCall(self.who, self.door, method, target, body, status, answer, kind="flash"))

    def get(self, path):
        items, idx = self.inner.get(path)
        self._rec("GET", f"/v1/get?key={path}", None, 200, {"items": items, "index": idx if items is not None else ""})
        return items, idx

    def list(self, prefix):
        keys = self.inner.list(prefix)
        self._rec("GET", f"/v1/list?prefix={prefix}", None, 200, {"keys": keys})
        return keys

    def put(self, path, items, cas=None):
        from w2cplatform.variables import Conflict
        body = {"op": "put", "key": path, "cas": "" if cas is None else cas, "items": items}
        try:
            idx = self.inner.put(path, items, cas)
        except Conflict as e:
            self._rec("POST", "/v1/write", body, 409, {"error": str(e)})
            raise
        self._rec("POST", "/v1/write", body, 200, {"index": idx})
        return idx

    def delete(self, path, cas=None):
        idx = self.inner.delete(path, cas) if cas is not None else self.inner.delete(path)
        self._rec("POST", "/v1/write", {"op": "delete", "key": path}, 200, {"index": idx})
        return idx

    def __getattr__(self, name):
        return getattr(self.inner, name)
