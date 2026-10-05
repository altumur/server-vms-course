"""The cluster's store, as this package names it: М10's `w2cplatform.variables.Variables` contract, and the fake the
older tests and М12 run on.

On a cluster without an orchestrator (the owner's decision of 3 October) the store is `configstore://` — this
server's `configstore` daemon, a member of a raft group over the servers, reached through the unix socket of the
process's role (`w2cplatform/configstorevars.py` the handle, `configstore.py` the daemon, `storemachine.py` what
they agree on). Nothing here speaks to it: a process opens `PLATFORM_STORE` with `open_vars`, and the platform knows
the scheme. Nomad's Variables, which this module spoke to before, went with the orchestrator.

`FakeVariables` stays, and so do the names М12 imports from here (`Variables`, `Conflict`, `Forbidden`): it is the
same contract in memory, one log for every writer, a version that only grows, `cas` and its 409, an optional ACL by
writer — what `storemachine.StoreMachine` does, without the rights file and the API. The module's stand runs the
machine itself behind per-role doors (`tests/cluster/conftest.py`); the fake is for the tests that need a store and nothing
about its doors.
"""
from __future__ import annotations

import threading
from typing import Protocol

from w2cplatform.variables import Conflict, Forbidden   # noqa: F401  the platform's exceptions: one class, so a CAS retry catches ours too
from w2cplatform.variables import refuse_delete, safe_path


class Variables(Protocol):
    def get(self, path: str) -> tuple[dict | None, int]: ...
    def put(self, path: str, items: dict, cas: int | None = None) -> int: ...
    def list(self, prefix: str) -> list[str]: ...
    def delete(self, path: str, cas: int | None = None) -> None: ...


class FakeVariables:
    """One log for the whole cluster, in memory. Optional ACL: a writer id may only put under the prefixes it was
    granted."""

    def __init__(self):
        self._lock = threading.Lock()
        # ONE log for the whole cluster, shared by every writer's view of it: `as_writer` copies this object's
        # attributes, and an int copied is a second counter — two views then hand out the same version, and a
        # stale CAS can match a write it never saw. A list is shared by the copy; an int is not.
        self._log = [1000]
        self._items: dict[str, tuple[dict, int]] = {}
        self.acl: dict[str, list[str]] = {}        # writer -> allowed prefixes
        self.writer: str | None = None            # "who am I" for the ACL check

    def as_writer(self, writer: str, allowed: list[str] | None = None) -> "FakeVariables":
        """The same log seen through one identity — what a role's socket is under the rights file."""
        v = FakeVariables.__new__(FakeVariables)
        v.__dict__ = self.__dict__.copy(); v.writer = writer
        if allowed is not None:
            self.acl[writer] = list(allowed)
        return v

    def _acl(self, path):
        from w2cplatform.rights import refusal       # the platform's one evaluator: `!` denials first
        why = refusal(self.writer, self.acl, path)
        if why:
            raise Forbidden(why)

    def get(self, path):
        safe_path(path)
        with self._lock:
            if path not in self._items:
                return None, 0
            items, idx = self._items[path]
            return dict(items), idx

    def put(self, path, items, cas=None):
        safe_path(path)          # the same key rule as the real store: the fake may not be laxer
        self._acl(path)
        with self._lock:
            _, current = self._items.get(path, (None, 0))
            if cas is not None and cas != current:
                raise Conflict(f"cas={cas} but the version is {current}")
            self._log[0] += 1
            self._items[path] = ({k: str(v) for k, v in items.items()}, self._log[0])
            return self._log[0]

    def list(self, prefix):
        with self._lock:
            return sorted(p for p in self._items if p.startswith(prefix))

    def delete(self, path, cas=None):
        safe_path(path)
        refuse_delete(path, None, {})            # the platform's rule: an epoch is a counter nobody deletes
        self._acl(path)
        with self._lock:
            _, current = self._items.get(path, (None, 0))
            if cas is not None and cas != current:
                raise Conflict(f"cas={cas} but the version is {current}")
            self._items.pop(path, None)
            self._log[0] += 1
