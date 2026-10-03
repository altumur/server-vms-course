"""The resource process — the platform's resource job (w2cplatform.resource)
with the VMS registered on it. One per server, pinned there for as long as
the server exists; on a box it is `python3 -m vms resource`
(`deploy/w2c-resource.container`), in М11 the `resource` system job. It has
no controller: it has a policy pass on a timer, a heartbeat, its HTTP, and
the event index over its own tree.

Its tree is EVENTS: the camera's buckets under `vms/<cam>/`, a recorder's under
`rec/<name>/`, the alarms', the journal's. Footage is not here any more. It is
in volumes of ObjectStorage, written through the host's `obsd` by the recorder
that holds each one (`vms/archive.py`): a volume is a ring, formatted at its
quota, that gives up its oldest minutes by itself — there is nothing on this
tree to repair, to retain by days or to free under a watermark, and no media
door here. A camera's timeline and its frames are asked of the recorders.

What the VMS adds is the one thing the platform cannot know: which event
buckets somebody said to KEEP (`kept_buckets`, from `rec/keeps/*`).

    platform/resources/<server>/heartbeat   {server, ts, url, usage, units, mirrors} — how the console finds it
    GET <url>/events?from&to&cam&kind&subsystem&unit   the platform's: this resource's EventIndex
    GET <url>/buckets/<sub>/<unit>, /events/<path>, /mirrored/<server>; PUT /mirror/<server>/<path>
"""
from __future__ import annotations

from w2cplatform.eventdatabase import EventIndex
from w2cplatform.resource import Resource
from w2cplatform.rows import PARSE_ERRORS, Table


def vms_resource(root: str, server: str, url: str, vars_, objects, wall=None, peers=None,
                 bucket_seconds: int = 600) -> Resource:
    """The platform's resource for this server, with the event index over its tree and the VMS's keeps."""
    import time
    wall = wall or time.time
    r = Resource(root, server, url, vars_, objects, bucket_seconds, wall, peers)
    r.index = EventIndex(root, server, wall, bucket_seconds)
    r.kept = kept_buckets(vars_)
    return r


# Which event buckets a keep holds (`vms/keeps.py`), for the platform's retention pass. The camera's events
# are in `vms/<cam>/`; whatever a recorder wrote about a recording is in `rec/<name>/`. Read once a pass.
#
# …and every other subsystem's events about the camera too (the review's fourth pass; B10 of the first review). Only
# the `vms` and `rec` trees were held: the detector's alarm at the gate, the scan's hits, the survey's, the scenario
# that opened the door — all inside the keep's interval, all deleted by their own days, and the evidence was the
# footage with nothing saying what happened in it. A unit of those subsystems is not named after a camera, so its
# ROW says which: a detector, a watch and a scan name their `cam`; a scenario names units in its triggers and its
# actions, each of which is a camera or names one. A deleted row is read too — `{days: 0}` after a delete is exactly
# when a keep matters — and a unit whose camera cannot be told (no row, a trigger on any camera, JSON that does not
# parse) is held by EVERY keep: not knowing whose it is is not "nobody's". Every keep whose interval READS — one that does
# not holds its own camera and nothing of these (`keeps.as_far_as_read`; the review's eighth pass).
ANY = None
CAM_FIELD = (("det", "units"), ("survey", "watches"), ("detjob", "jobs"))

# ONE TORN ROW OF A UNIT IS THAT UNIT'S (the review's ninth pass, major). `_rows` read every row bare: one that is not
# JSON in `det/units/55`, `auto/scenarios/s1` or `rec/recordings/r9` raised out of `kept_buckets`, and so out of the
# resource's whole `retain` — `removed=None`, every unit of the server kept 10 of 10, every pass, the copies too; and
# only the log said so. Now each row is read alone (`rows.Table`): one that does not read — not JSON, not a map, a `cam`
# that is not a value — is left out, counted once until it parses again (`unit_rows_garbled` in the resource's
# heartbeat), logged once, and its NAME is handed back: its unit is a unit of no one camera (`ANY`), held by every keep
# that reads — "not knowing whose it is is not nobody's", the rule a missing row already had.
UNIT_ROWS = Table("unit_row", "its unit is held by every keep that reads, as a unit of no one camera, until it is mended",
                  "unit's row")
GARBLED = object()                                   # what `UNIT_ROWS.read` gives for a row that does not read


def _rows(vars_, sub: str, table: str, garbled: set | None = None) -> dict[str, dict]:
    prefix = f"{sub}/{table}/"
    out = {}
    for path in vars_.list(prefix):
        def read(path=path):
            items, _ = vars_.get(path)               # a file store's row that is not even JSON raises in the read itself
            if items and not isinstance(items, dict):
                raise TypeError(f"a row is a map, not {type(items).__name__}")
            if items and not isinstance(items.get("cam", ""), (str, int, type(None))):
                raise TypeError(f"`cam` is a value, not {type(items['cam']).__name__}")
            return items
        items = UNIT_ROWS.read(path, read, GARBLED)
        if items is GARBLED:
            if garbled is not None:
                garbled.add(path[len(prefix):])
            continue
        if items:
            out[path[len(prefix):]] = items          # deleted rows included: their `cam` is what a keep needs
    return out


def cameras_of_units(vars_, unread: set | None = None) -> dict[tuple[str, str], set | None]:
    """`{(subsystem, unit): {cam, …} | ANY}` for the subsystems whose units are about cameras without being named after one.
    A recording whose row does not read goes into `unread`, when the caller gives one: its camera is not known."""
    import json
    out: dict[tuple[str, str], set | None] = {}
    by_sub = {sub: {u: str(it.get("cam", "")) for u, it in _rows(vars_, sub, table).items()} for sub, table in CAM_FIELD}
    for sub, units in by_sub.items():
        for unit, cam in units.items():
            out[(sub, unit)] = {cam} if cam else ANY
    torn: set = set()
    recs = {u: str(it.get("cam") or u) for u, it in _rows(vars_, "rec", "recordings", torn).items()}
    if unread is not None:
        unread |= torn

    def cams_of(sub: str, unit: str) -> set | None:
        if not unit:
            return ANY                                # a trigger on any camera's events
        if sub == "vms":
            return {unit}
        if sub == "det":
            return {by_sub["det"][unit]} if by_sub["det"].get(unit) else ANY
        if sub == "rec":
            return ANY if unit in torn else {recs.get(unit, unit)}   # a torn recording row: whose, not known
        return ANY

    for unit, it in _rows(vars_, "auto", "scenarios").items():
        try:
            when = json.loads(it.get("when") or "[]")
            then = json.loads(it.get("then") or "[]")
            named: set | None = set()
            for t in when:
                c = cams_of(str(t.get("sub", "")), str(t.get("unit") or ""))
                named = ANY if c is ANY or named is ANY else named | c
            for a in then:                            # `vms.output`/`vms.preset` name a camera as `unit`, the others as `cam`
                c = cams_of("vms", str(a.get("cam") or a.get("unit") or ""))
                named = ANY if c is ANY or named is ANY else named | c
            out[("auto", unit)] = named if named else ANY
        except PARSE_ERRORS:                          # `when` nested past what JSON reads too (`RecursionError`): one scenario's, not the retain's (the review's tenth pass)
            out[("auto", unit)] = ANY
    return out


# The store as this hook reads it, with a mark of the pass's progress at every row read and every listing (the
# review's sixth pass): the keeps, and the rows of every subsystem whose units are about a camera, are read one by
# one before anything is swept — a part of the pass that moves the whole time, and said nothing to the pulse.
class _Marked:
    def __init__(self, vars_, progressed):
        self._vars, self._progressed = vars_, progressed

    def get(self, path, *a, **kw):
        out = self._vars.get(path, *a, **kw)
        self._progressed()
        return out

    def list(self, prefix, *a, **kw):
        out = self._vars.list(prefix, *a, **kw)
        self._progressed()
        return out


def kept_buckets(vars_):
    from . import keeps

    def once(progressed=None):
        store = vars_ if progressed is None else _Marked(vars_, progressed)
        # A keep whose row does not parse is held as far as it reads (`keeps.as_far_as_read`; the review's seventh pass:
        # it raised out of here, and the resource's whole `retain` — every unit, every server — swept nothing while it
        # stood). Its camera's buckets only: a unit of no one camera is held by the keeps that read (`sound`), and not
        # by an interval open to the start or the end of time (the review's eighth pass, part 4).
        unread: list = []
        all_ = keeps.declared(store, unread) + unread
        sound = [k for k in all_ if not k.garbled]
        if not all_:
            return lambda sub, unit, start, end: False
        torn: set = set()                            # recordings whose rows do not read: whose camera, not known
        cams = cameras_of_units(store, torn)
        recs = {u: str(it.get("cam") or u) for u, it in _rows(store, "rec", "recordings").items()}

        def kept(sub: str, unit: str, start: float, end: float) -> bool:
            from w2cplatform.events import tree_owner
            sub = tree_owner(sub)[0]                 # a keep holds the alarms' tree as it holds the other
            if sub == "vms":
                return keeps.held(keeps.spans_of_cam(all_, str(unit)), start, end)
            if sub == "rec":                         # named in the keep, or a recording of its camera made since
                named = keeps.spans_of(all_, str(unit), recs.get(str(unit), ""))
                if str(unit) in torn:                # …or, its row torn, a unit of no one camera: every keep that reads
                    named = named + [(k.since, k.until) for k in sound]
                return keeps.held(named, start, end)
            if sub in ("det", "survey", "detjob", "auto"):
                of = cams.get((sub, str(unit)), ANY)
                spans = [(k.since, k.until) for k in sound] if of is ANY else \
                    [sp for cam in of for sp in keeps.spans_of_cam(all_, cam)]
                return keeps.held(spans, start, end)
            return False
        return kept
    return once
