"""Where is unit N of a subsystem — answered from the cluster in one scan.

`<sub>/workers/*` is the assignment, written by the controller into one store
and read by every worker from the same store; scanning it is the cluster
directory, and it is *consistent* because it is one store. A layer that
aggregates several clusters cannot be — which is why the question is answered here.
"""
from __future__ import annotations

import time

from w2cplatform.contract import ASSIGNMENTS, read_assignment, stored


class Directory:
    def __init__(self, vars_, sub: str, ttl: float = 5.0, clock=time.monotonic):
        self.vars, self.ttl, self.clock, self.prefix = vars_, ttl, clock, f"{sub}/workers/"
        self._cache: dict[str, list[str]] = {}
        self._at = -1e9
        self.scans = 0

    def scan(self, force: bool = False) -> dict[str, list[str]]:
        if force or self.clock() - self._at >= self.ttl:
            out = {}
            for path in self.vars.list(self.prefix):
                worker = path[len(self.prefix):]
                items, _ = stored(self.vars, path, ASSIGNMENTS)        # …nor one the store cannot read at all
                out[worker] = read_assignment(path, worker, items).units   # one garbled `rev` is not the end of the scan
            self._cache, self._at, self.scans = out, self.clock(), self.scans + 1
        return self._cache

    def where(self, unit) -> str | None:
        hits = [w for w, units in self.scan().items() if str(unit) in units]
        return hits[0] if len(hits) == 1 else (None if not hits else "+".join(sorted(hits)))   # a reassignment window shows as both

    def holdings(self, worker: str) -> list[str]:
        return sorted(self.scan().get(worker, []))
