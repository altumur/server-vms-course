"""A config store with the semantics Nomad Variables promise — a
raft-assigned ModifyIndex, PUT with cas=<index> succeeding only if the index
still matches, a conflict otherwise — on one box, as files.

One JSON file per path under <root>/vars/, one counter file for the index,
one lock. Every write is atomic (write-then-rename) and serialised by the
lock, so two processes on the same box see exactly what two clients of one
raft would: one of them wins the CAS.
"""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # variables.py — a file-backed config store with the semantics of Nomad Variables: ModifyIndex,
# check-and-set, one writer per prefix
#
# **Role in the module.** Lesson 1's config store. It gives one box exactly what a raft-backed Nomad
# Variables store gives a cluster: every path has a `ModifyIndex`, a `put(cas=<index>)` succeeds only if the
# index still matches and raises `Conflict` otherwise, and a writer identity may be confined to a set of
# prefixes (the ACL policy). Everything in the platform that must be consistent — assignments, placement
# rows, epochs, slots, idempotency keys, unit rows — lives here; bulk or frequent data (heartbeats,
# snapshots, media) goes to `objects.py` instead. The store is a directory: one JSON file per path under
# `<root>/vars/`, one counter file for the index, one lock file. Every write is write-then-rename and
# serialised by an `fcntl` lock, so two processes on the same box see exactly what two clients of one raft
# would: one of them wins the CAS. A box keeps it; М11's cluster swaps it for `configstore://`, the same semantics
# replicated by raft over the servers (`storemachine.py`, `configstore.py`), behind the same `Variables` Protocol.
#
# ## Module-level names
# - `Conflict` — exception: the `cas` index passed to `put`/`delete` did not equal the path's current
#   ModifyIndex. Every CAS loop in the platform (`epoch.next_epoch`, `Controller.write`,
#   `Worker.claim_slot`, `IdempotencyKeys.claim`) catches it and re-reads.
# - `Forbidden` — exception: this writer identity is not allowed to write that path. Raised by `put` when an
#   ACL is set; it is how "one writer per prefix" is enforced mechanically rather than by convention. The
#   console test proves a console token cannot write placement by expecting exactly this.
# - `Variables` — `typing.Protocol` with `get`, `put`, `list`: the interface every consumer types against.
#   `FileVariables` implements it here; М11's Nomad client will too. (Note `delete` is not in the Protocol
#   even though `FileVariables` has it; `IdempotencyKeys.prune` uses it.)
#
# ## Notes
# - Atomicity model: rename is atomic on one filesystem; the lock serialises read-check-write; therefore
#   `put(cas=idx)` is a true compare-and-set. `test_two_processes_one_cas_winner` runs four threads, each
#   with its own `FileVariables`, incrementing a counter by CAS and asserts the final value equals the
#   number of successful writes.
# - `test_the_config_store_survives_a_restart_and_refuses_a_stale_cas` shows a second handle on the same
#   directory reads the same items and index, a stale `cas` raises `Conflict`, and `get("nope")` is `(None,
#   0)`.
# - The ACL check is on the handle, not the file: an unrestricted handle over the same directory can still
#   write anything. The confinement is real only when each process gets only its own token — which is what
#   the Quadlet units under `deploy/` arrange.
# ================================================================================================
from __future__ import annotations

import json
import os
import random
import time
from typing import Protocol

from .events import durable_dir, durably
from .limits import NO_CEILING, TooLarge, check


class Conflict(Exception):
    """The cas index did not match the current ModifyIndex."""


class Forbidden(Exception):
    """This writer may not write that path — one writer per prefix."""


# The version of a path, as the store hands it out. OPAQUE: the platform compares it for equality, passes
# it back unmodified, and does nothing else with it — never orders it, never does arithmetic on it. That is
# not fastidiousness, it is what a backend needs. Nomad's `ModifyIndex` is the raft index and is a number;
# Kubernetes' `resourceVersion` is a string, and its API conventions require it: "This value MUST be treated
# as opaque by clients and passed unmodified back to the server" — it is "currently backed by etcd's
# mod_revision", but an application "should *not* rely on the implementation details of the versioning
# system". Typing this `int` would have made a Kubernetes backend bet on that detail.
#
# One value is NOT a version and is the same everywhere: `0` means the path does not exist. `get` returns it
# for a missing path, and `put(cas=0)` therefore means "create only" — the first claimant wins and everyone
# else conflicts (`SpecController.create`, `IdempotencyKeys.claim`).
Index = str | int


class Variables(Protocol):
    # What one path may weigh: the sum of the lengths of every key and every value in it, which is how
    # Nomad measures a Variable. `NO_CEILING` (0) when the store has none. See `limits.py`.
    max_bytes: int

    def get(self, path: str) -> tuple[dict | None, Index]: ...
    def put(self, path: str, items: dict, cas: Index | None = None) -> Index: ...
    def list(self, prefix: str) -> list[str]: ...


# The size a store charges for a path's items: keys and values, as bytes. A row is small — a couple of
# hundred bytes — and that is the point: what makes a row big is one field that should not be in a row.
def items_bytes(items: dict) -> int:
    return sum(len(str(k).encode()) + len(str(v).encode()) for k, v in items.items())


# A key must have exactly ONE spelling, and this is where that is enforced. It is not (only) about escaping
# `<root>/vars/`: the same text becomes a key here, a prefix the ACL is matched against, and — through
# `events.unit_dir` — a directory on a resource's disk. `..` breaks all three differently. Without
# normalisation `vms/a/../b` and `vms/b` are two keys one person reads as one, each with its own
# ModifyIndex, so two writers both win their CAS. With normalisation somewhere downstream (a URL, a tree)
# they collapse into one — but the ACL was matched against the un-normalised string, which is how a token
# for `rec/recordings/*` reaches `vms/cameras/7`. Refused loudly, never repaired: a caller that meant
# `vms/b` should say `vms/b`.
def safe_path(path: str) -> str:
    if not path or path.startswith("/") or ".." in path.split("/"):
        raise ValueError(f"not a key: {path!r}")
    return path


# The store. Holds only paths (`root`, `dir`, `index_file`, `lock_file`) plus an optional writer identity
# and ACL map; it keeps no cache, so any number of instances over the same directory — in one process or
# many — are equivalent.
# -- the seam: which store is behind the contract, said as a URL ------------------------------------
# A process is told `PLATFORM_STORE` (`store_url`; `CONFIG_URL` is its old name, still read) and nothing
# else. `file://` is in-process — on a box there is no daemon, no hop and no second quorum, which is the
# whole reason this is a factory and not a service. Every other scheme is registered by the module that
# implements it, so the platform's loops name no backend and adding Kubernetes later adds a file, not a
# branch here.
#
# This is the same seam Objects already have in М11 (`open_store(OBJECTS)`); Config just never got it, and
# that is why swapping the store meant editing sixteen constructors in three modules and two languages.
_SCHEMES: dict[str, object] = {}


# The platform's own backends, by the module that registers each. `file://` is answered above without a
# lookup because it is what a box with no URL at all gets; `memory://` is the dev box's and the tests'.
# `configstore://` is the cluster's (the owner's decision of 3 October: the cluster without an orchestrator): the
# socket of the store daemon on this server, plain HTTP, standard library only — only the daemon needs the
# raft library (`configstorevars.py` the handle, `configstore.py` the daemon). Anything else — `k8s://` — is a module
# somebody else imports, and this table is not where it goes: that is the difference between a backend the
# platform HAS and a backend it ALLOWS.
# The cluster store's scheme is the product's name, said once (`configstorevars` registers under it).
STORE_SCHEME = "configstore"
_BUILTIN = {"file": "w2cplatform.variables", "memory": "w2cplatform.memvariables",
            STORE_SCHEME: "w2cplatform.configstorevars"}


# Which store a process opens, from its environment: `PLATFORM_STORE` first — the cluster's unit says
# `configstore:///run/configstore/<role>.sock` — then `CONFIG_URL`, the name a box's units and the product's older ones
# still carry (product P7), then `default`. One function, so no process reads the two names in its own order.
def store_url(env=None, default: str | None = None) -> str | None:
    env = os.environ if env is None else env
    return env.get("PLATFORM_STORE") or env.get("CONFIG_URL") or default


def register_scheme(scheme: str, factory) -> None:
    """`factory(url, writer=…, acl=…) -> Variables`. A backend registers itself at import."""
    _SCHEMES[scheme] = factory


def open_vars(url: str, writer: str | None = None, acl: dict[str, list[str]] | None = None):
    """`file:///data/platform/config` · `configstore:///run/configstore/vmsworker.sock` · whatever else registered.

    A bare path is read as `file://` so the box keeps working with no URL at all."""
    if "://" not in url:
        return FileVariables(url, writer, acl)
    scheme, rest = url.split("://", 1)
    if scheme == "file":
        return FileVariables(rest or "/", writer, acl)
    factory = _SCHEMES.get(scheme)
    if factory is None and scheme in _BUILTIN:
        # A backend registers itself when its module is imported, and the platform's own second one is
        # imported here rather than from `__init__` — `import w2cplatform` still pulls in nothing, which is
        # a property the package states about itself and a test checks.
        __import__(_BUILTIN[scheme])
        factory = _SCHEMES.get(scheme)
    if factory is None:
        known = ", ".join(sorted({"file", *_BUILTIN, *_SCHEMES}))
        raise ValueError(f"no Variables backend for {scheme}://  (have: {known})")
    return factory(url, writer=writer, acl=acl)


# Locking the store's `lock` file, on whichever operating system this is running on.
#
# `import fcntl` at the top of this module is what made the platform refuse to start on Windows — not fail
# a call, not behave oddly: the MODULE did not import, so nothing that touches Variables existed at all.
# That is the shape a portability bug takes in Python, and it is why the import lives inside the branch.
#
# THE LOCK HAS A LIMIT (the platform review, "`flock` with no timeout"; feedback BI). `flock(LOCK_EX)` waits
# for as long as it takes, and what waited with it was the loop that renews the leases: a backup tool, a
# stuck neighbour or a debugger holding the lock file froze every process of the box, silently, until it
# let go — and then they all found their leases gone. So the lock is ASKED for, not waited for: taken without
# blocking, asked again every few milliseconds, and after `LOCK_WAIT` seconds the write raises `StoreBusy`.
# That is an `OSError`, which every caller already reads as "the store did not answer" — not as "no"
# (feedback BC): a worker counts it, keeps what it holds and tries again.
#
# The two platforms now behave the same. `msvcrt.locking(LK_LOCK)` had a ten-second limit of its own and
# `flock` had none; `LK_NBLCK` and `LOCK_NB` are the same question. `msvcrt` locks a region from the current
# position, so one byte from zero is the whole of it: the file exists to BE a lock and nobody reads it.
LOCK_WAIT = 10.0


class StoreBusy(OSError):
    """The store's lock was held by somebody else for longer than we wait: not answered, not refused."""


def _try_lock(f) -> bool:
    try:
        import fcntl
    except ImportError:                                   # Windows
        import msvcrt
        f.seek(0)
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except BlockingIOError:
        return False


def _lock_exclusive(f, wait: float | None = None) -> None:
    wait = LOCK_WAIT if wait is None else wait
    deadline = time.monotonic() + wait
    while not _try_lock(f):
        if time.monotonic() >= deadline:
            raise StoreBusy(f"the store's lock has been held by another process for {wait:g} s")
        time.sleep(0.005)


# A PAUSE BEFORE A CAS IS TRIED AGAIN (the review, "CAS retries with no delay and no jitter"). A conflict
# means somebody else wrote between our read and our write. Tried again at once, the same writers meet again
# at once — ten recorders starting after a power cut each lose nine times in a row to the same nine others,
# and a loop with ten tries gives up. A random pause, growing with the number of losses, spreads them out:
# from a fraction of a millisecond to a tenth of a second. Random and not fixed, because two writers that
# wait the same time collide again.
#
# No ceiling of its own on the tries: every loop that calls this already has one.
CAS_PAUSE_MAX = 0.1


def cas_pause(attempt: int, sleep=time.sleep) -> float:
    """Sleep a random time before CAS try number `attempt + 1`; returns what it slept."""
    t = random.uniform(0, min(CAS_PAUSE_MAX, 0.0005 * (2 ** min(attempt, 12))))
    sleep(t)
    return t


# A DELETE IS A WRITE (the review, "`delete` bypasses the ACL"). One rule for every backend, so the file store,
# the memory one and a cluster's cannot disagree about it:
#
#   the ACL        whoever may not write a path may not remove it either. It used to be unchecked: a worker
#                  whose token writes epochs and its slot could delete a camera's row
#   the epoch      nobody deletes `<subsystem>/epoch/<unit>` — not even a handle with no writer at all. The
#                  row is a counter. Deleted, it starts again from 1, and `e1` is already the name of footage
#                  and events somebody else wrote: two writers' files under one name, and a fencing token
#                  that went backwards
#   the domain     nobody but the domain's agent deletes `domain/*` (the review's third pass, Н-M2) — not a handle
#                  with no writer either. Those rows are what makes a console ask who is calling: the key set gone
#                  and the rows that say "a member" gone with it is a console as open as one nobody joined. The
#                  agent itself replaces what it carries and deletes nothing; a store that cannot name its writer
#                  (М11's, where the ACL is the server's) refuses the delete for everybody
DOMAIN_WRITER = "agent"               # the domain agent's identity in a cluster's store (М12, `domain/agent.py`)


def epoch_row(path: str) -> bool:
    parts = path.split("/")
    return len(parts) == 3 and parts[1] == "epoch"


def refuse_delete(path: str, writer: str | None, acl: dict) -> None:
    if epoch_row(path):
        raise Forbidden(f"{path} is an epoch: a counter nobody deletes")
    if path.startswith("domain/") and writer != DOMAIN_WRITER:
        raise Forbidden(f"{path} is the domain's: only its agent removes it")
    if writer is not None and acl:
        allowed = acl.get(writer, [])
        if not any(path == p or (p.endswith("*") and path.startswith(p[:-1])) for p in allowed):
            raise Forbidden(f"{writer} may not delete {path}")


class Corrupt(Exception):
    """The store cannot say what it holds — and says so, instead of starting again."""


# A ROW THE STORE HOLDS AND CANNOT READ IS THAT ROW'S PARSE ERROR (the eleventh review, a minor). Nomad answers every
# Variable as a map of strings; a file of this store can be torn (a hand edit, a disk that lied about a write), hold
# `items` that are not a map, or values that are not strings — and `get` raised whatever `json` or `dict` raised, or
# handed the non-strings on, and the routes that read the drain, a slot, a placement or a worker's row bare fell whole
# with it. A torn file, `items` that are not a map, an index that is no whole number: one error now, a `ValueError`
# naming the row — every reader of rows reads it as that row not parsing (`rows.PARSE_ERRORS`, `rows.Table`). A value
# that is not a string is handed on as its JSON text, a string, as Nomad would hold it: the field's parse error, read
# by the field's reader as a Nomad value that does not parse is. A row that does not read has the version `TORN`: a
# write that means to replace it says so (`put(cas=TORN)`, `Controller.write`), and one that read anything else conflicts.
TORN = "torn"


class Garbled(ValueError):
    """A row the store holds and cannot read: a torn file, items that are not a map, an index that is no number."""

    def __init__(self, key: str, why: str):
        self.key, self.index = key, TORN
        super().__init__(f"the stored row {key} does not read ({why})")


# A KEY IS A FILE NAME HERE (the eleventh review, a minor): a unit's name of 100 000 characters became a file name the
# disk refused — `OSError: File name too long`, answered as "the store did not answer" with the store's local path in
# the reply. A key is at most `KEY_BYTES` bytes as this store spells it on disk — a file name of 255 bytes less
# `.json.tmp`; a `/` and a `%` take three bytes each, a letter outside ASCII two to four. Longer: refused at the write, in
# words (`KeyTooLong`, the store's own limit as `TooLarge` says one: 413 at the console); at a read, no such row — none
# could have been written; a delete finds nothing to remove.
KEY_BYTES = 255 - len(".json.tmp")


class KeyTooLong(TooLarge):
    """A key longer than this store can name a file."""

    def __init__(self, key: str, size: int):
        super().__init__(key if len(key) <= 64 else key[:64] + "…", size, KEY_BYTES,
                         f"a key is at most {KEY_BYTES} bytes here, as a file's name (a / or a % counts three): "
                         f"a shorter name")


class FileVariables:
    # `root` is the store directory; `<root>/vars/` is created. `writer` is this handle's identity (None
    # means unrestricted). `acl` is `{writer: [allowed prefixes]}`; when both `writer` and a non-empty `acl`
    # are present, `put` checks them. Nothing is read at construction; the index counter file is created
    # lazily on the first write.
    #
    # `volatile`: skip the barriers that make a write survive a power cut (below, `put`). For tests only — a
    # barrier costs some fifteen milliseconds on a laptop's disk and a suite makes thousands of writes — and
    # said by the environment (`STORE_VOLATILE=1`, which `tests/run.py` sets and a test's subprocesses inherit),
    # never by a default: a store opened with nothing said is durable.
    def __init__(self, root: str, writer: str | None = None, acl: dict[str, list[str]] | None = None,
                 max_bytes: int = NO_CEILING, volatile: bool | None = None):
        self.volatile = os.environ.get("STORE_VOLATILE") == "1" if volatile is None else volatile
        self.root = root
        self.dir = os.path.join(root, "vars")
        os.makedirs(self.dir, exist_ok=True)
        self.index_file = os.path.join(root, "index")
        self.lock_file = os.path.join(root, "lock")
        self.writer, self.acl = writer, acl or {}
        self.max_bytes = max_bytes          # a directory has no ceiling; a test or an install may say otherwise

    # Returns a new handle on the same directory seen through another identity, allowed only the given
    # prefixes (`'vms/*'`, `'vms/epoch/*'` style: a trailing `*` means prefix match, otherwise exact path).
    # This is what a Nomad ACL policy does for a task's token. The tests build the controller with
    # `as_writer("vmscontroller", SPEC.acl_controller())` and the console with `as_writer("console",
    # SPEC.acl_console())`.
    def as_writer(self, writer: str, allowed: list[str]) -> "FileVariables":
        """The same store seen through another identity, allowed only these
        prefixes ('vms/*', 'vms/epoch/*') — what a Nomad ACL policy does."""
        v = FileVariables(self.root, writer, dict(self.acl), volatile=self.volatile)
        v.acl[writer] = allowed
        return v

    # Maps a variable path to its file: `<root>/vars/<path with / encoded as %2F>.json`. One flat directory,
    # so `list` is a single `listdir`.
    def _file(self, path: str) -> str:
        # `%` is escaped FIRST, or the encoding is not reversible: without it the key `a%2Fb` and the key
        # `a/b` would be the same file, and `list` would report one of them — the same "two keys, one
        # place" bug `safe_path` refuses above, arriving through the encoding instead of through the path.
        name = safe_path(path).replace("%", "%25").replace("/", "%2F")
        if len(name.encode()) > KEY_BYTES:
            raise KeyTooLong(path, len(name.encode()))
        return os.path.join(self.dir, name + ".json")

    # Opens the lock file and takes an exclusive lock on it (`_lock_exclusive`, by OS); the returned file object is used as a
    # context manager, and closing it releases the lock. This serialises every `put`/`delete` across all
    # processes on the box.
    def _locked(self):
        f = open(self.lock_file, "a+")
        _lock_exclusive(f)
        return f

    # Reads the counter file (missing or empty means 1000), increments it, writes it back atomically (tmp +
    # `os.replace`) and returns the new value. Always called under the lock. The starting value 1000 is why
    # the very first write in the tests returns index 1001 — indices never restart from zero after a
    # restart, so a stale CAS from before a restart still conflicts.
    #
    # A counter that cannot be read is an ERROR, not a new beginning (feedback BD). An empty or garbled file
    # used to read as 1000, and so did a missing one beside rows that exist: numbering started again, and a CAS
    # remembered from before could match a row it was never read from. Only a store with no rows at all starts
    # at 1000.
    def _next_index(self) -> int:
        try:
            raw = open(self.index_file).read().strip()
        except FileNotFoundError:
            raw = None
        if raw is None:
            if any(f.endswith(".json") for f in os.listdir(self.dir)):
                raise Corrupt(f"{self.index_file} is missing beside rows that exist: refusing to number again from 1000")
            n = 1000
        else:
            try:
                n = int(raw)
            except ValueError:
                raise Corrupt(f"{self.index_file} does not hold a number ({raw[:20]!r}): refusing to number again from 1000")
        n += 1
        tmp = self.index_file + ".tmp"
        with open(tmp, "w") as f:
            f.write(str(n))
            self._durable(f)
        os.replace(tmp, self.index_file)
        return n

    # The barriers. A row written with `write` + `rename` and nothing else is in the page cache: after a power
    # cut the file can be there, empty, or the old one — and the row is an EPOCH, so the next `next_epoch` hands
    # out a number that was already given (the platform review; the product's store, feedback BD). The file
    # reaches the medium before it is renamed into place, and the directory after.
    def _durable(self, f) -> None:
        if not self.volatile:
            f.flush()
            durably(f)

    def _durable_dirs(self) -> None:
        if not self.volatile:
            durable_dir(self.dir)
            durable_dir(self.root)

    # Reads the path's file and returns `(items, index)`; a missing path is `(None, 0)`. Not locked: a
    # reader sees either the old file or the new one, never a half-written one, because writes rename into
    # place. Items come back as a fresh dict of strings.
    def get(self, path: str) -> tuple[dict | None, int]:
        try:
            with open(self._file(path), "rb") as f:
                raw = f.read()
        except (FileNotFoundError, KeyTooLong):          # a key too long to be a file: nothing could be written there
            return None, 0
        try:
            d = json.loads(raw)
            items, idx = d["items"], d["index"]
            if not isinstance(items, dict) or not all(isinstance(k, str) for k in items):
                raise TypeError("its items are not a map")
            if isinstance(idx, bool) or not isinstance(idx, int):
                raise TypeError("its index is not a whole number")
            # A value that is not a string (a hand edit: `1e999`, `true`, a list) is its JSON text — what Nomad would hold
            # had it been written so: its reader's parse error, the field's, and the rest of the row still says what it says.
            items = {k: v if isinstance(v, str) else json.dumps(v) for k, v in items.items()}
        except (ValueError, TypeError, KeyError, RecursionError) as e:
            raise Garbled(path, f"{type(e).__name__}: {e}") from None
        return items, idx

    # The version a write compares its `cas` with: the row's index, 0 for none — and `TORN` for a row that does not read.
    def _current(self, path: str):
        try:
            return self.get(path)[1]
        except Garbled as e:
            return e.index

    # The write. First the ACL: if this handle has a writer and an ACL, the path must match one of the
    # writer's allowed patterns or `Forbidden` is raised — before taking the lock. Then, under the lock:
    # read the current index; if `cas` was given and differs, raise `Conflict`; otherwise take the next
    # index, dump `{"items": {k: str(v)}, "index": idx}` to a tmp file and rename it over the path's file;
    # return the new index. Two rules to remember: `cas=0` means "create only" (the path must not exist —
    # `SpecController.create` and `IdempotencyKeys.claim` rely on it); and every value is stringified on the
    # way in, which is why callers such as `Assignment.from_items` and `Slot.from_items` parse ints, floats
    # and `"true"`/`"false"` back out.
    def put(self, path: str, items: dict, cas: int | None = None) -> int:
        if self.writer is not None and self.acl:
            allowed = self.acl.get(self.writer, [])
            if not any(path == p or (p.endswith("*") and path.startswith(p[:-1])) for p in allowed):
                raise Forbidden(f"{self.writer} may not write {path}")
        # Checked before the lock and before the write: an oversized row never half-lands, and the value
        # that is already there is still the value that is there.
        check(path, items_bytes(items), self.max_bytes)
        self._file(path)                                # a key too long for a file's name: refused before the lock
        with self._locked():
            current = self._current(path)
            if cas is not None and cas != current:
                raise Conflict(f"{path}: cas={cas} but ModifyIndex={current}")
            idx = self._next_index()
            tmp = self._file(path) + ".tmp"
            with open(tmp, "w") as f:
                json.dump({"items": {k: str(v) for k, v in items.items()}, "index": idx}, f)
                self._durable(f)
            os.replace(tmp, self._file(path))
            self._durable_dirs()
            return idx

    # A delete is a write: the same ACL as `put`, and never an epoch (`refuse_delete`). Then, under the lock:
    # the same CAS check as `put`, remove the file (a missing file is not an error) and burn an index.
    def delete(self, path: str, cas: int | None = None) -> None:
        refuse_delete(path, self.writer, self.acl)
        try:
            self._file(path)
        except KeyTooLong:
            return                                      # nothing could have been written under it
        with self._locked():
            current = self._current(path)
            if cas is not None and cas != current:
                raise Conflict(f"{path}: cas={cas} but ModifyIndex={current}")
            try:
                os.remove(self._file(path))
            except FileNotFoundError:
                pass
            self._next_index()
            self._durable_dirs()                    # the removal, too, survives the power going (the review's second pass)

    # Every stored path that starts with `prefix`, decoded from the filenames and sorted. Callers pass
    # prefixes ending in `/` (`"vms/workers/"`, `"vms/slots/"`, `"vms/idem/"`) to enumerate a row family.
    def list(self, prefix: str) -> list[str]:
        out = []
        for f in os.listdir(self.dir):
            if f.endswith(".json"):
                p = f[:-5].replace("%2F", "/").replace("%25", "%")   # decoded in the reverse order of _file
                if p.startswith(prefix):
                    out.append(p)
        return sorted(out)
