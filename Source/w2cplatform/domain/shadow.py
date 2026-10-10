"""Lesson 2 — shadow mode: the domain that writes nothing.

The domain computes what the directory WOULD say, observes what the clusters' workers report, and emits a divergence
report. It changes nothing. The taxonomy, per UNIT — a unit on a worker, of any subsystem of the directory:

    lagging       a worker has not yet applied a unit's revision, within grace     not a fault
    stalled       behind past grace, no progress                                   the real "it did not take effect"
    orphaned      placed by the domain, and no cluster's snapshot lists it          fault
    unmanaged     a cluster runs a unit the domain never placed                     in shadow mode: a MEASUREMENT
    conflict      two clusters — or two workers — claim one unit                   always a fault — placement or fencing
    stale_epoch   a worker reports a unit under a superseded epoch                  the fence catching a writer that should have stopped

The one number is `unmanaged == 0`: anything running that the model does not describe is a gap in the model, and
driving it to zero IS the design work. Ordering beats equality: "behind by 4 for 40 minutes" is an outage;
"diverged" is an alert you learn to ignore.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

log = logging.getLogger("shadow")


@dataclass
class WorkerReport:
    """What a worker's heartbeat says: which units it runs, under which epoch each, and which revision of each it has
    applied."""
    worker: str
    cluster: str
    server: str
    units: list[tuple[str, int, int, int]]   # (the unit's ref — the domain's name for it, epoch, revision, observed_revision)
    ts: float


@dataclass
class Finding:
    kind: str
    unit: str | None
    where: str | None
    detail: str


@dataclass
class DivergenceReport:
    findings: list[Finding] = field(default_factory=list)

    def count(self, kind: str) -> int:
        return sum(1 for f in self.findings if f.kind == kind)

    @property
    def unmanaged(self) -> int:
        return self.count("unmanaged")

    @property
    def faults(self) -> list[Finding]:
        return [f for f in self.findings if f.kind in ("stalled", "orphaned", "conflict", "stale_epoch")]

    def summary(self) -> str:
        kinds = ("lagging", "stalled", "orphaned", "unmanaged", "conflict", "stale_epoch")
        return "  ".join(f"{k}={self.count(k)}" for k in kinds)


class Shadow:
    """`placed`: unit ref -> cluster the domain's placement says. `epochs`: (cluster, ref) -> current epoch from that
    cluster's `<sub>/epoch/<id>`, keyed by the ref the snapshot maps it to. `reports`: every worker's heartbeat, every
    cluster. Everything is keyed by the domain's ref: two clusters both have an id 1, and the domain never compares by
    it."""

    def __init__(self, grace_seconds: float = 60.0):
        self.grace = grace_seconds
        self._progress: dict[tuple[str, str], tuple[int, float]] = {}   # (worker, unit) -> (last observed, since when)

    def compare(self, placed: dict, epochs: dict[tuple[str, str], int],
                reports: list[WorkerReport], now: float) -> DivergenceReport:
        rep = DivergenceReport()
        claims: dict[str, list[tuple[str, str]]] = {}
        for r in reports:
            for unit, epoch, revision, observed in r.units:
                current = epochs.get((r.cluster, unit), epoch)
                if epoch < current:
                    rep.findings.append(Finding("stale_epoch", unit, f"{r.cluster}/{r.worker}",
                                                f"reports under epoch {epoch}, current is {current}"))
                    continue                              # a fenced writer's claim counts for nothing
                claims.setdefault(unit, []).append((r.cluster, r.worker))
                key = (r.worker, unit)
                last, since = self._progress.get(key, (None, now))
                if last != observed:
                    self._progress[key] = (observed, now); since = now
                behind = revision - observed
                if behind > 0:
                    age = now - since
                    rep.findings.append(Finding("stalled" if age > self.grace else "lagging", unit, f"{r.cluster}/{r.worker}",
                                                f"behind by {behind} revision(s) for {age:.0f}s"))
        for unit, who in claims.items():
            if len(who) > 1:
                rep.findings.append(Finding("conflict", unit, None, f"claimed by {sorted(who)}"))
            elif unit not in placed:
                rep.findings.append(Finding("unmanaged", unit, f"{who[0][0]}/{who[0][1]}", "running, never placed by the domain"))
            elif placed[unit] != who[0][0]:
                rep.findings.append(Finding("conflict", unit, f"{who[0][0]}/{who[0][1]}", f"placed in {placed[unit]}, running in {who[0][0]}"))
        for unit, cl in placed.items():
            if unit not in claims:
                rep.findings.append(Finding("orphaned", unit, cl, "placed, and no worker in the domain runs it"))
        return rep


def reports_from(fed) -> tuple[list[WorkerReport], dict[tuple[str, str], int], list[str]]:
    """Build the reports and the epoch map from every reachable cluster's heartbeats and `<sub>/epoch/*`, for every
    subsystem of the directory — what the shadow job reads each pass."""
    from w2cplatform.rows import PARSE_ERRORS
    from . import declared
    from .federation import MEMBER_OBJECTS, Unreachable, ref_of
    reports, epochs, down = [], {}, []
    for name, c in fed.clusters.items():
        try:
            for s in declared.directory():
                def name_of(st):
                    return ref_of({**st, "sub": s.name}) or f"{name}/{s.name}/{st['id']}"
                refs = {}
                for w, hb in c.heartbeats(s.name).items():
                    units = []
                    for st in hb.get("status", []):
                        if st.get("phase") != "running":
                            continue
                        # one entry of one worker is that entry's (the ninth review's sweep): an id or an epoch that is
                        # no number raised out of the report for every cluster of the domain, as an epoch row once did
                        try:
                            uid, ref = str(s.parse_id(st["id"])), name_of(st)
                            entry = (ref, int(st.get("epoch", 0)), int(st.get("revision", 0)), int(st.get("observed_revision", 0)))
                        except PARSE_ERRORS as e:
                            MEMBER_OBJECTS.garbled(f"{name}/{s.name}/heartbeats/{w}#{st.get('id')}", e)
                            continue
                        refs[uid] = ref
                        units.append(entry)
                    reports.append(WorkerReport(w, name, hb.get("server", "?"), units, float(hb.get("ts", 0))))
                for path in c.vars.list(f"{s.name}/epoch/"):
                    items, _ = c.vars.get(path)
                    # One epoch row that does not parse is that unit's (the review's sixth pass, the class of
                    # `take_epoch`): read bare, it raised out of the report for EVERY cluster of the domain. Skipped,
                    # the unit has no entry, and `compare` takes its worker's word for the epoch — no finding invented.
                    try:
                        uid = path.rsplit("/", 1)[1]
                        epochs[(name, refs.get(uid, f"{name}/{s.name}/{uid}"))] = int(items["epoch"])
                    except PARSE_ERRORS:
                        log.warning("%s: epoch row %s does not parse: skipped in the shadow report", name, path)
        except Unreachable:
            down.append(name)
    return reports, epochs, down


def exit_criterion(rep: DivergenceReport, consecutive_clean: int, required: int = 3) -> tuple[bool, str]:
    """The written criterion for switching the domain into write mode."""
    if rep.unmanaged:
        return False, f"unmanaged={rep.unmanaged}: the model does not describe everything that runs"
    if rep.faults:
        return False, f"{len(rep.faults)} fault(s) outstanding: {sorted({f.kind for f in rep.faults})}"
    if consecutive_clean < required:
        return False, f"{consecutive_clean}/{required} consecutive clean reports"
    return True, "unmanaged == 0, no faults, stable across reports: the domain may write"
