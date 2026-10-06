"""The cluster's object store — М10's `w2cplatform.objects.ObjectStore`
contract: worker heartbeats, resource heartbeats, the controllers' snapshot
shards and pass reports, the masks and models a row names by digest.

On this cluster the implementation is `ClusterObjectStore`, `cluster://`:
each server keeps its objects as files in its own directory, and its resource
answers for them over HTTP (`w2cplatform/resource.py`, `/v1/objects`). A put
is a local file — every object has ONE writer, and almost every one is written
again within a pass, so no consensus is needed to hold it. A read is the local
file when it is a blob (any copy that hashes to its name is the object),
otherwise the freshest copy among every server's, asked of the local
resource with `scope=cluster` — for a key the doors give out
(`resource.door_readable`: the platform's families, a spec's `objects.door`);
any other key is this server's file alone, read from its directory. A listing
is the union of every server's, cached for a second. No ceiling:
`max_bytes = 0` — files on a disk.

Two kinds of object are not files. A key a subsystem's spec names a ROW
(`objects: {rows: […]}`, `catalog.object_rows`) — one that must be created ONCE
across the cluster (a worker's mark before it acts, `put_new`), or read where
the place it names is gone — is a row `objects/<key>` in the replicated store,
through `VariablesObjectStore`: a directory's `link` is create-only on one
server, and two holders of one thing sit on two. And a blob is copied by the resource
to the next live peers on the events mirror's ring (`Resource.mirror_blobs`),
and deleted by the sweep on every server that answers.

A subsystem, the platform and the domain do not know which store they hold. The
other adapters stay for what they are for: `s3+http://…` (`s3.py`) for a
rented cluster (М12 Lesson 8), `http://` for a plain object endpoint, a
directory for the tests. A subsystem's bulk data never goes to any of these.
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Protocol

from w2cplatform.limits import check
from w2cplatform.rows import answer
from w2cplatform.variables import Conflict

log = logging.getLogger(__name__)


class ObjectStore(Protocol):
    max_bytes: int                      # what one object may weigh here; 0 means no ceiling (М10A Lesson 26)

    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes | None: ...
    def list(self, prefix: str) -> list[str]: ...


# The heaviest object a READ takes (the review's eighth pass, a sibling of the peers' answers): `get` read the whole body
# whatever its size, so a store or a proxy gone wrong was memory without a ceiling in every reader of heartbeats and
# snapshots. Objects here are heartbeats and snapshot shards — kilobytes; past this the read is refused with a
# `ValueError` (`rows.answer`), never truncated: half an object is worse than none.
GET_MAX = 64 << 20


class HttpObjectStore:
    max_bytes = 0                       # no ceiling worth naming
    def __init__(self, base_url: str, timeout: float = 10.0):
        self.base = base_url.rstrip("/")
        self.timeout = timeout

    def put(self, key: str, data: bytes) -> None:
        req = urllib.request.Request(f"{self.base}/{key}", data=data, method="PUT")
        req.add_header("Content-Type", "application/octet-stream")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            if r.status not in (200, 201, 204):
                raise IOError(f"PUT {key}: {r.status}")

    def get(self, key: str) -> bytes | None:
        try:
            with urllib.request.urlopen(f"{self.base}/{key}", timeout=self.timeout) as r:
                return answer(r, GET_MAX)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise

    def list(self, prefix: str) -> list[str]:
        raise NotImplementedError("plain HTTP has no listing; use s3+http:// for the heartbeat prefix")


class FsObjectStore:
    max_bytes = 0                       # no ceiling worth naming
    def __init__(self, root: str):
        self.root = root
        os.makedirs(root, exist_ok=True)

    # Every write under the directory's lock, as М10's (`objects.dir_lock`): what makes `put_at` one step.
    def put(self, key: str, data: bytes) -> None:
        from w2cplatform.objects import dir_lock
        p = os.path.join(self.root, key)
        with dir_lock(os.path.dirname(p)):
            with open(p + ".tmp", "wb") as f:
                f.write(data)
            os.replace(p + ".tmp", p)              # an object appears whole or not at all

    # By the index read, as М10's: the bytes' digest, compared and written under the directory's lock (ADR-0054).
    def get_at(self, key: str) -> tuple[bytes | None, str]:
        from w2cplatform.objects import bytes_index
        data = self.get(key)
        return data, bytes_index(data)

    def put_at(self, key: str, data: bytes, index: str) -> bool:
        from w2cplatform.objects import bytes_index, dir_lock
        p = os.path.join(self.root, key)
        with dir_lock(os.path.dirname(p)):
            if bytes_index(self.get(key)) != index:
                return False
            with open(p + ".tmp", "wb") as f:
                f.write(data)
            os.replace(p + ".tmp", p)
            return True

    # Create-only, as М10's `FsObjectStore.put_new` does it: `link` onto a name that is taken fails. Without it a
    # worker on a bench store refuses its actions (`Worker` marks an action before it acts; the platform review's third pass).
    def put_new(self, key: str, data: bytes) -> bool:
        from w2cplatform.objects import dir_lock
        p = os.path.join(self.root, key)
        with dir_lock(os.path.dirname(p)):
            return self._link_new(p, data)

    def _link_new(self, p: str, data: bytes) -> bool:
        import tempfile
        from w2cplatform.events import durable_dir, durably
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p), prefix=os.path.basename(p) + ".", suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush(); durably(f)
            try:
                os.link(tmp, p)
            except FileExistsError:
                return False
            durable_dir(os.path.dirname(p))
            return True
        finally:
            os.remove(tmp)

    # Removes the object under the directory's lock, as М10's `FsObjectStore.delete` does (ADR-0054: a delete between a
    # `get_at` and its `put_at` is one step or the other, never inside). A missing key is `False`, not an error — a
    # sweep that meets one candidate twice does the same thing twice; no directory, no lock made to say so. Without it a
    # worker on `OBJECTS=file://` raised `AttributeError` at every `MARK_SWEEP` (the review's fourteenth pass, minor 19).
    def delete(self, key: str) -> bool:
        from w2cplatform.objects import dir_lock
        p = os.path.join(self.root, key)
        if not os.path.isdir(os.path.dirname(p)):
            return False
        with dir_lock(os.path.dirname(p)):
            try:
                os.remove(p)
                return True
            except FileNotFoundError:
                return False

    def get(self, key: str) -> bytes | None:
        p = os.path.join(self.root, key)
        if not os.path.exists(p):
            return None
        with open(p, "rb") as f:
            return f.read()

    def list(self, prefix: str) -> list[str]:
        out = []
        for d, _, files in os.walk(self.root):
            for f in files:
                if f.endswith(".tmp"):
                    continue
                key = os.path.relpath(os.path.join(d, f), self.root)
                if key.startswith(prefix):
                    out.append(key)
        return sorted(out)


# Where the create-only objects are rows in the store: `objects/<key>`. The name the class gave every object when every
# object was a row (М11's first shape); the create-only keys are all that is left there, and the rights file grants
# them under it (`cluster/rights.py`).
ROWS_PREFIX = "objects"


class VariablesObjectStore:
    """Objects as rows: `<prefix>/<key>` -> {data: <utf-8 text>}. Keys are the
    platform's (`<sub>/commands/r-7`); the store is whatever Variables the caller
    holds, with the rights that come with its door.

    Its job on the cluster is NARROWED to the keys the specs name rows
    (`objects.rows`) — `ClusterObjectStore` sends those here (`row_patterns`)
    and everything else to files. The class itself still holds any key: a test,
    or the module's stand, may run every object through one store."""

    def __init__(self, vars_, prefix: str = ROWS_PREFIX):
        self.vars, self.prefix = vars_, prefix.strip("/")
        # An object here IS a Variable, so it inherits the Variable's ceiling — and says so, rather than
        # letting a caller find it out in production. The `data` key and its value are what gets charged.
        self.max_bytes = max(0, getattr(vars_, "max_bytes", 0) - len("data"))

    def _path(self, key: str) -> str:
        if ".." in key or key.startswith("/"):
            raise ValueError(key)
        return f"{self.prefix}/{key}"

    def put(self, key: str, data: bytes) -> None:
        check(key, len(data), self.max_bytes)
        self.vars.put(self._path(key), {"data": data.decode("utf-8")})       # no cas: the last heartbeat wins, as it should

    def get(self, key: str) -> bytes | None:
        return self.get_at(key)[0]

    # By the index read (the product's `IndexPutter` on `RowObjects`): the row's own index, and the write by CAS on it —
    # 0, no row, is create-only. `False` when somebody wrote the row meanwhile (ADR-0054: a closer re-reads).
    def get_at(self, key: str) -> tuple[bytes | None, int]:
        items, idx = self.vars.get(self._path(key))
        return (items["data"].encode("utf-8") if items and "data" in items else None), idx

    def put_at(self, key: str, data: bytes, index: int) -> bool:
        check(key, len(data), self.max_bytes)
        try:
            self.vars.put(self._path(key), {"data": data.decode("utf-8")}, cas=index)
        except Conflict:
            return False
        return True

    def list(self, prefix: str) -> list[str]:
        base = f"{self.prefix}/"
        return sorted(p[len(base):] for p in self.vars.list(base + prefix))

    # Creates the object only if there is none; `True` when THIS call made it. A Variable written with `cas=0`
    # succeeds only where no Variable is — raft's create-only, and the one a worker's command mark needs: two
    # holders of one thing in the same two seconds must not both believe they were first (the platform review's
    # third pass). The heartbeat's `put` stays last-writer-wins, as it should; this is the other promise, asked
    # for by name. Raft has it on disk before it answers — nothing to fsync here.
    def put_new(self, key: str, data: bytes) -> bool:
        check(key, len(data), self.max_bytes)
        try:
            self.vars.put(self._path(key), {"data": data.decode("utf-8")}, cas=0)
        except Conflict:
            return False
        return True

    def delete(self, key: str) -> None:
        self.vars.delete(self._path(key))


# -- the cluster's objects: files on every server -------------------------------------------------------------------

# The keys that are ROWS of the store and not files, by glob over segments (`*` is one segment; a last `*` is the rest):
# each loaded spec's `objects.rows` under its name (`catalog.object_rows`; the boundary's step 4 — this was a constant
# here, `*/commands/*`, one subsystem's family in the platform's code). A directory's `link` is create-only on ONE
# server, and two holders of one thing are on two (the platform review's third pass, on a cluster); and a mark of a
# place read when the place is gone must not be a file on the server that went with it.
def row_patterns() -> tuple[str, ...]:
    from w2cplatform.catalog import object_rows
    return object_rows()


LIST_FRESH = 1.0                 # seconds a listing of every server is used again before it is asked again
DOOR_TIMEOUT = 10.0              # what the resource on this server has to answer: its own reads of peers take ≤ 5 s


def _match(pattern: list[str], key: list[str]) -> bool:
    for i, p in enumerate(pattern):
        if i == len(pattern) - 1 and p == "*":
            return len(key) > i and all(key[i:])
        if i >= len(key) or (p != "*" and p != key[i]) or not key[i]:
            return False
    return len(key) == len(pattern)


def is_row(key: str) -> bool:
    """A key a loaded spec names in `objects.rows`: a row in the replicated store, never a file."""
    return any(_match(p.split("/"), key.split("/")) for p in row_patterns())


# Whether some key under `prefix` could be a row — so a listing of it asks the store too. `<sub>/` could
# (`<sub>/commands/…`), `<sub>/heartbeats/` could not.
def _may_hold_rows(prefix: str) -> bool:
    *whole, part = prefix.split("/")
    for pattern in (p.split("/") for p in row_patterns()):
        ok = True
        for i, seg in enumerate(whole):
            if i >= len(pattern):
                ok = pattern[-1] == "*"
                break
            if pattern[i] != "*" and pattern[i] != seg:
                ok = False
                break
        else:
            i = len(whole)
            ok = i >= len(pattern) and pattern[-1] == "*" or i < len(pattern) and (pattern[i] == "*" or pattern[i].startswith(part))
        if ok:
            return True
    return False


class ObjectsUnavailable(OSError):
    """The resource on this server did not answer: the cluster's objects cannot be read from here now. An `OSError`,
    which every caller already reads as "the store did not answer" — never as "there is nothing" (a controller that
    took a silent door for an empty listing would call every worker of the other servers dead)."""


def _store_from_env():
    from w2cplatform import variables as v
    store_url = getattr(v, "store_url", None)
    url = store_url(os.environ) if store_url is not None else os.environ.get("PLATFORM_STORE")
    if not url:
        raise ValueError("a create-only object is a row in the store, and no store was named: "
                         "PLATFORM_STORE=configstore:///run/configstore/<role>.sock")
    return v.open_vars(url)


class ClusterObjectStore:
    """`cluster:///data/platform/objects?resource=http://127.0.0.1:8090` — this server's objects as files under `root`,
    every server's through the resource on this one (`/v1/objects`), the create-only keys as rows in the store."""

    max_bytes = 0                       # files on a disk: no ceiling worth naming

    def __init__(self, root: str, resource: str = "http://127.0.0.1:8090", vars_=None, timeout: float = DOOR_TIMEOUT,
                 wall=time.time, clock=time.monotonic, list_fresh: float = LIST_FRESH):
        from w2cplatform.objects import FsObjectStore as Files
        self.local = Files(root)        # this server's files: what the resource serves as `scope=local`
        self.resource = resource.rstrip("/")
        self.timeout, self.wall, self.clock, self.list_fresh = timeout, wall, clock, list_fresh
        self._vars, self._rows = vars_, None
        self._listed: dict[str, tuple[float, set[str]]] = {}   # prefix -> (by `clock`, keys) — `list`
        self.missing: list[str] = []    # the servers the last answer of the resource named as not answering
        self._where: dict[str, str] = {}                         # key -> the server whose copy was listed last
        self._heard: dict[str, tuple[str, bytes]] = {}           # key -> (server, the bytes read from it last)

    # The rows of the create-only keys, opened on first use: from the handle the process gave, else from its environment.
    @property
    def rows(self) -> VariablesObjectStore:
        if self._rows is None:
            self._rows = VariablesObjectStore(self._vars if self._vars is not None else _store_from_env())
        return self._rows

    # -- the door on this server -----------------------------------------------------------------------------------
    def _door(self, method: str, path: str, query: dict) -> tuple[int, bytes, dict]:
        url = f"{self.resource}{path}?{urllib.parse.urlencode(query)}"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method=method), timeout=self.timeout) as r:
                return r.status, answer(r, GET_MAX), dict(r.headers)
        except urllib.error.HTTPError as e:
            body = e.read()
            if e.code == 404:
                return 404, body, dict(e.headers)
            raise ObjectsUnavailable(f"the resource on this server refused {method} {path} ({e.code}: "
                                     f"{body[:200].decode(errors='replace')})") from None
        except (OSError, ValueError) as e:
            raise ObjectsUnavailable(f"the resource on this server does not answer at {self.resource} ({e}): the "
                                     f"cluster's objects cannot be read from here until it does") from None

    def _said_missing(self, missing) -> None:
        missing = sorted(missing or [])
        if missing != self.missing:
            if missing:
                log.warning("objects: %s did not answer — their objects are left out of what is read here", ", ".join(missing))
            else:
                log.info("objects: every server answers again")
        self.missing = missing

    # -- the contract --------------------------------------------------------------------------------------------------
    # A local file — the one writer of the key is on this server — with the writer's clock as `written`: the copy a
    # reader takes when the key is on several servers (a controller that moved, a worker's name taken up elsewhere) is
    # the one written last. A create-only key is a row whatever writes it.
    def put(self, key: str, data: bytes) -> None:
        if is_row(key):
            self.rows.put(key, data)
        else:
            self._file(self.local.put, key, data)
        self._seen(key, True)

    # The same, through the medium before the name (a blob a row is about to name: `SpecController.put_blob`).
    def put_durable(self, key: str, data: bytes) -> None:
        if is_row(key):
            self.rows.put(key, data)
        else:
            self._file(self.local.put_durable, key, data)
        self._seen(key, True)

    def _file(self, write, key: str, data: bytes) -> None:
        write(key, data)
        t = self.wall()
        os.utime(self.local._p(key), (t, t))

    # Create-only across the cluster: a row written with `cas=0` (`VariablesObjectStore.put_new`) — `True` when THIS
    # call made it. Only for a key a spec names a row (`objects.rows`): create-only on files is create-only on one server, and a key
    # asked for here and read from files elsewhere would be two objects under one name.
    def put_new(self, key: str, data: bytes) -> bool:
        if not is_row(key):
            raise ValueError(f"{key}: a create-only object is a row of the store, one of "
                             f"{', '.join(row_patterns()) or 'none: no spec loaded here names one'} — its subsystem's "
                             f"spec names it in `objects.rows`, so every reader looks for it in the store")
        made = self.rows.put_new(key, data)
        self._seen(key, True)
        return made

    # By the index read: the row's (`VariablesObjectStore.get_at`/`put_at`) — for a key a spec names a row only, as
    # `put_new`: a file has one writer, and its index on one server is nobody's on another.
    def get_at(self, key: str) -> tuple[bytes | None, int]:
        self._row_only(key, "a write by the index read")
        return self.rows.get_at(key)

    def put_at(self, key: str, data: bytes, index: int) -> bool:
        self._row_only(key, "a write by the index read")
        took = self.rows.put_at(key, data, index)
        self._seen(key, True)
        return took

    @staticmethod
    def _row_only(key: str, what: str) -> None:
        if not is_row(key):
            raise ValueError(f"{key}: {what} is of a row of the store, one of "
                             f"{', '.join(row_patterns()) or 'none: no spec loaded here names one'} — its subsystem's "
                             f"spec names it in `objects.rows`")

    # A blob from this server's file when it hashes to its name; anything else — and a blob whose copy here does not —
    # the freshest copy among every server's, asked of the resource here (`scope=cluster`). `None` when nobody that
    # answered has it; `ObjectsUnavailable` when the resource here does not answer.
    def get(self, key: str) -> bytes | None:
        from w2cplatform.blobs import BlobMismatch, verify
        from w2cplatform.resource import door_readable, is_blob_key
        if is_row(key):
            return self.rows.get(key)
        if not door_readable(key):                       # a file no door gives out: this server's, read here alone
            return self.local.get(key)
        if is_blob_key(key):
            data = self.local.get(key)
            if data is not None:
                try:
                    return verify(key.rsplit("/", 1)[1], data)
                except BlobMismatch as e:
                    log.error("objects: this server's copy of %s is not the blob (%s): read from another server", key, e)
        status, body, headers = self._door("GET", "/v1/objects/" + urllib.parse.quote(key), {"scope": "cluster"})
        missing = [s for s in headers.get("X-Missing", "").split(",") if s]
        self._said_missing(missing)
        if status != 404:
            if not is_blob_key(key):
                self._heard[key] = (str(headers.get("X-Server", "")), body)
            return body
        last = self._heard.get(key)
        if last is not None and last[0] in missing:
            return last[1]                  # its server does not answer: what it said last (`_remembered`)
        self._heard.pop(key, None)
        return None

    # Every server's keys under `prefix` (the resource's `scope=cluster`), with the create-only rows when the prefix
    # could hold any — asked again after `list_fresh` seconds; what this process wrote or deleted meanwhile is in it.
    def list(self, prefix: str) -> list[str]:
        from w2cplatform.resource import door_covers, door_may_hold, door_readable
        cached = self._listed.get(prefix)
        if cached is not None and self.clock() - cached[0] < self.list_fresh:
            return sorted(cached[1])
        keys = set()
        if door_may_hold(prefix):                        # what the doors give out: every server's
            status, body, _ = self._door("GET", "/v1/objects", {"prefix": prefix, "scope": "cluster"})
            try:
                said = json.loads(body)
                keys = set(said["objects"])
            except (ValueError, TypeError, KeyError) as e:
                raise ObjectsUnavailable(f"the resource on this server answered a listing that is not one ({e})") from None
            self._said_missing(said.get("missing"))
            keys |= self._remembered(prefix, said["objects"], said.get("missing") or [])
        if not door_covers(prefix):                      # …and this server's files no door gives out
            keys |= {k for k in self.local.list(prefix) if not door_readable(k) and not is_row(k)}
        if _may_hold_rows(prefix) and (self._vars is not None or self._rows is not None
                                              or os.environ.get("PLATFORM_STORE")):
            keys |= {k for k in self.rows.list(prefix) if is_row(k)}
        self._listed[prefix] = (self.clock(), keys)
        return sorted(keys)

    # A create-only row, by the store. A blob on EVERY server that answers (the sweep, `SpecController.sweep_blobs`):
    # `True` if any had it; a server that did not answer keeps its copy and the next sweep finds it. Anything else is
    # this server's file only — its one writer is here.
    def delete(self, key: str) -> bool:
        from w2cplatform.resource import is_blob_key
        self._seen(key, False)
        if is_row(key):
            self.rows.delete(key)
            return True
        if is_blob_key(key):
            status, body, _ = self._door("DELETE", "/v1/objects/" + urllib.parse.quote(key), {"scope": "cluster"})
            said = json.loads(body) if status == 200 else {}
            self._said_missing(said.get("missing"))
            return any((said.get("deleted") or {}).values())
        return self.local.delete(key)

    # A SERVER THAT DOES NOT ANSWER IS NOT A SERVER THAT NEVER WAS (found by the module's stand, the power pull with the
    # dead server's doors down). Its objects are files on it, and with it gone they left every listing: the last
    # heartbeat of its worker and of its resource with them — and a controller that cannot read a worker's heartbeat
    # cannot tell which server it ran on, so it waited for ever (`Controller.slot_fate`: "never said which server"), and
    # a resource it cannot read is "unknown", which is not "silent": the dead server's units never moved. So a reader
    # keeps what it last listed and read of each server, and while the resource here names that server missing, the
    # keys it last listed are in the listing and their last bytes are what `get` answers — ageing by their own `ts`,
    # which is how the controller sees the two silences. A reader started after the server went never heard it, and
    # says nothing of it (the operator's decommission is for that). A server that answers again answers for itself.
    def _remembered(self, prefix: str, listed: dict, missing: list[str]) -> set[str]:
        for key, entry in listed.items():
            server = entry.get("server") if isinstance(entry, dict) else None
            if isinstance(server, str):
                self._where[key] = server
        gone = set(missing)
        for key in [k for k, s in self._where.items() if k.startswith(prefix) and k not in listed and s not in gone]:
            self._where.pop(key, None)                    # its server answered without it: deleted, or moved
            self._heard.pop(key, None)
        return {k for k, s in self._where.items() if k.startswith(prefix) and s in gone}

    def _seen(self, key: str, present: bool) -> None:
        for prefix, (_, keys) in self._listed.items():
            if key.startswith(prefix):
                (keys.add if present else keys.discard)(key)


def open_store(url: str, vars_=None) -> ObjectStore:
    """cluster:///path?resource=http://127.0.0.1:8090 (this server's files, every server's through its resource; the
    create-only keys in the store `vars_`, else the one the environment names) · file:///path · http(s)://host/bucket
    (anonymous) · s3+http(s)://host/bucket?region=r (SigV4, credentials from AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
    — on a server, from a row)."""
    if url.startswith("cluster://"):
        from urllib.parse import parse_qs, urlsplit
        u = urlsplit(url)
        resource = parse_qs(u.query).get("resource", ["http://127.0.0.1:8090"])[0]
        return ClusterObjectStore(u.path or "/data/platform/objects", resource, vars_)
    if url.startswith(("s3+http://", "s3+https://")):
        from urllib.parse import parse_qs, urlsplit
        from .s3 import S3ObjectStore
        u = urlsplit(url[3:])
        region = parse_qs(u.query).get("region", ["us-east-1"])[0]
        return S3ObjectStore(f"{u.scheme}://{u.netloc}", u.path.strip("/"), region)
    if url.startswith(("http://", "https://")):
        return HttpObjectStore(url)
    if url.startswith("file://"):
        return FsObjectStore(url[len("file://"):])
    return FsObjectStore(url)
