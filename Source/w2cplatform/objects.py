"""An object store: large, or frequent, never queried by key. A directory
here, and a directory on every server in М11 (`cluster://`). An object appears
whole or not at all."""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # objects.py — the object store: a directory on one box, a directory on every server in М11
#
# **Role in the module.** Lesson 1's second store. Where `variables.py` holds small rows that must be
# consistent and CAS-able, the object store holds things that are large or written often and are never
# queried by key: worker heartbeats (`<sub>/heartbeats/<worker>`), resource heartbeats
# (`platform/resources/<server>/heartbeat`) and the controller's snapshot, one object per worker under
# `<sub>/snapshot/`. Every one of them is sharded by the writer it describes, and that is why each stays
# small however large the cluster gets: a store may declare a ceiling (`limits.py`), and a shard fits whatever
# ceiling a store declares. Its one
# promise is that an object appears whole or not at all. The `ObjectStore` Protocol is the interface
# `Controller`, `Worker`, `Resource` and `SpecController` type against; `FsObjectStore` is the one-box
# implementation, and М11 keeps it on every server: `ClusterObjectStore` (`w2cplatform/cluster/objectstore.py`) writes into
# this server's directory and reads the others' through their resources (`resource.py`, `/v1/objects`).
#
# ## Module-level names
# None beyond the two classes.
#
# ## Notes
# - The walk in `list` is O(files under root), fine for heartbeats on one box; М11 walks one directory per server
#   and its resource answers the union (`GET /v1/objects?scope=cluster`).
# - `delete` exists, and two callers use it: the blob sweep (Lesson 20), and a worker's sweep of its own marks
#   before a request it answered (`Worker.sweep_marks`, once the answer is past every reader). Everything else in
#   the platform relies on objects NEVER going away — a stale heartbeat simply ages and readers filter by
#   `ts`, and a worker restarting reads the heartbeat its previous instance left to measure its own
#   failover. That is not an accident waiting to be tidied up: sweep the heartbeats and the measurement
#   goes with them. The rule is "an object is deleted only by a caller that can prove nothing refers to it".
# ================================================================================================
from __future__ import annotations

import fcntl
import hashlib
import os
from contextlib import contextmanager
from typing import Protocol

from .events import durable_dir, durably, new_temp
from .limits import NO_CEILING, check

# The directory's lock, taken by EVERY write of the file store (`put`, `put_new`, `put_at`, `delete`): what makes
# `put_at`'s compare and write one step against every other writer of the directory. A `.tmp` name, so no listing
# shows it (`list` skips `.tmp`, as it skips a write in flight).
DIR_LOCK = ".lock.tmp"


# The index a file store writes by (`get_at`/`put_at`): a digest of the bytes; `""` for no object at all.
def bytes_index(data: bytes | None) -> str:
    return "" if data is None else hashlib.sha256(data).hexdigest()


# The directory's lock (`DIR_LOCK`), exclusive, for one write: let go when the descriptor closes. Made under the
# process's umask, as every file of the store is.
@contextmanager
def dir_lock(d: str):
    os.makedirs(d, exist_ok=True)
    fd = os.open(os.path.join(d, DIR_LOCK), os.O_RDWR | os.O_CREAT, 0o666)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


# A `typing.Protocol` with `put(key, data: bytes)`, `get(key) -> bytes | None`, `list(prefix) -> list[str]`.
# Objects are last-writer-wins by design; anything needing ordering goes in Variables — but for two promises asked for
# by name: create-only (`put_new`, a request's mark before its call) and a write BY THE INDEX READ (`get_at`/`put_at`,
# the product's `IndexPutter`): whoever closes a mark it did not begin writes it by the index it read, and a conflict
# means somebody else wrote it meanwhile (ADR-0054). Both object stores have it, and there is no path without it.
class ObjectStore(Protocol):
    # What one object may weigh, in bytes; `NO_CEILING` (0) when the store has none. Declared, not
    # guessed — see `limits.py`. A write over it raises `TooLarge` and leaves the previous object alone.
    max_bytes: int

    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes | None: ...
    def list(self, prefix: str) -> list[str]: ...

    # Removes one object; `True` if it was there. A capability of the STORE — a store can either delete or
    # it cannot — and deliberately not "delete, but only under `blobs/`": that would be policy welded into
    # the seam, and policy lives with the caller that has it (`SpecController.sweep_blobs`) and with the
    # store's rights, which are the only place that can actually enforce it.
    def delete(self, key: str) -> bool: ...

    # The object and the index it stands at (`None` and the index of no object when there is none); and the write that
    # takes only while the object still stands at `index` — `True` when it took, `False` when somebody wrote meanwhile.
    def get_at(self, key: str) -> tuple[bytes | None, object]: ...
    def put_at(self, key: str, data: bytes, index) -> bool: ...


# Implements `ObjectStore` over a directory tree; a key with `/` becomes nested directories.
class FsObjectStore:
    # Stores `root` and creates it. `max_bytes` is what this store says it can hold: a directory has no
    # ceiling worth naming, so the default is `NO_CEILING` — and a test that wants to see a real store's
    # ceiling passes one, which is how the platform's own limits get exercised without a cluster.
    def __init__(self, root: str, max_bytes: int = NO_CEILING):
        self.root = root
        self.max_bytes = max_bytes
        os.makedirs(root, exist_ok=True)

    # Path for a key. Refuses `..` or a leading `/` (raises `ValueError`) so a key cannot leave `root`.
    def _p(self, key: str) -> str:
        if ".." in key or key.startswith("/"):
            raise ValueError(key)
        return os.path.join(self.root, key)

    # Creates parent directories, writes to `<path>.tmp`, then `os.replace` onto the final path. That rename
    # is the "whole or not at all" guarantee: a reader (a controller reading a heartbeat while the worker
    # writes it) sees the old bytes or the new bytes, never a truncated file.
    def put(self, key: str, data: bytes, durable: bool = False) -> None:
        check(key, len(data), self.max_bytes)      # refused before the write: the old object survives intact
        p = self._p(key)
        with self._locked(os.path.dirname(p)):
            self._write(p, data, durable)

    def _locked(self, d: str):
        return dir_lock(d)

    def _write(self, p: str, data: bytes, durable: bool) -> None:
        # A name of its OWN for the file in flight (feedback BD). `<path>.tmp` was shared by every writer of the
        # key: a zombie and its replacement writing one heartbeat wrote into one file, and what was renamed into
        # place was the two of them interleaved — a heartbeat that does not parse, read by a controller's pass.
        fd, tmp = new_temp(os.path.dirname(p), os.path.basename(p) + ".")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                if durable:
                    f.flush(); durably(f)
            os.replace(tmp, p)
            if durable:
                durable_dir(os.path.dirname(p))
        except BaseException:
            try:
                os.remove(tmp)
            except FileNotFoundError:
                pass
            raise

    # The bytes a ROW will name — a detector's mask, whose digest goes into a row written with fsync. Without the
    # barrier the row survives the power going and the file does not, and the detector never starts (the review's
    # second pass). Heartbeats and snapshots do not pay it: the next one replaces them anyway.
    def put_durable(self, key: str, data: bytes) -> None:
        self.put(key, data, durable=True)

    # Creates the object only if there is none; `True` when THIS call made it. The file system's create-or-
    # tell-me-it-exists (`link` onto the final name, which fails on a name that is taken) — the one CAS a
    # store of last-writer-wins objects can offer, and the one a worker's command mark needs: two holders of
    # one device must not both believe they were first (the review's second pass). A store without it gets
    # the command refused (`VmsWorker._mark`).
    #
    # DURABLE, both halves (the review's third pass): the bytes to the medium before the name is made, the
    # directory entry after. The mark is written BEFORE the device is called; a mark the power took with it
    # leaves no trace of a call that happened, and the next holder opens the door a second time.
    def put_new(self, key: str, data: bytes) -> bool:
        check(key, len(data), self.max_bytes)
        p = self._p(key)
        with self._locked(os.path.dirname(p)):
            return self._link_new(p, data)

    # By the index read (`get_at`): the object as it stands and its digest; the write, under the directory's lock, only
    # while the bytes there still have that digest — none at all for `""`. What a closer of a mark writes by (ADR-0054).
    def get_at(self, key: str) -> tuple[bytes | None, str]:
        data = self.get(key)
        return data, bytes_index(data)

    def put_at(self, key: str, data: bytes, index: str) -> bool:
        check(key, len(data), self.max_bytes)
        p = self._p(key)
        with self._locked(os.path.dirname(p)):
            if bytes_index(self.get(key)) != index:
                return False
            self._write(p, data, True)
            return True

    def _link_new(self, p: str, data: bytes) -> bool:
        fd, tmp = new_temp(os.path.dirname(p), os.path.basename(p) + ".")
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
            try:
                os.remove(tmp)
            except FileNotFoundError:
                pass

    # Removes the file; a missing key is not an error, so a sweep that runs twice on the same candidate —
    # two consoles, a retry — does the same thing the second time.
    def delete(self, key: str) -> bool:
        p = self._p(key)
        if not os.path.isdir(os.path.dirname(p)):
            return False                           # no directory, no object: no lock made to say so
        with self._locked(os.path.dirname(p)):
            try:
                os.remove(p)
                return True
            except FileNotFoundError:
                return False

    # Reads the file; a missing key returns `None` rather than raising, so callers such as
    # `Controller.workers_seen` can simply skip it.
    def get(self, key: str) -> bytes | None:
        try:
            with open(self._p(key), "rb") as f:
                return f.read()
        except FileNotFoundError:
            return None

    # `(written, size)` of the object, or `None`: the file's mtime and length. What a server's resource says of each
    # object it holds (`GET /v1/objects`), and what the freshest of several copies is chosen by (`ClusterObjectStore`).
    def stat(self, key: str) -> tuple[float, int] | None:
        try:
            st = os.stat(self._p(key))
        except FileNotFoundError:
            return None
        return st.st_mtime, st.st_size

    # Walks the whole tree, skips `.tmp` files (an in-flight `put`), and returns the sorted keys (paths
    # relative to `root`) that start with `prefix`. `Controller.workers_seen` lists `<sub>/heartbeats/`;
    # `resource.resources_seen` lists `platform/resources/` and keeps the keys ending in `/heartbeat`.
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
