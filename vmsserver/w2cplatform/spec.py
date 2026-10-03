"""The controller as data. A subsystem gives the platform a spec — one YAML
file — and the platform runs the controller from it:

    name          the prefix: <name>/*
    unit          the rows: where they live (<name>/<rows>/<id>), how an id is made (numeric | <field>),
                  the operator's fields with types and defaults, and derived rows (a second row the
                  platform keeps beside the unit — the VMS's <name>/retention/<id> that the resource reads)
    placement     capacity and headroom as heartbeat fields; a constraint and a tie-break BY NAME from
                  the catalogue below — never an expression; `requires: resource` when a worker must
                  run where a resource answers (not placed on, moved off, while it is silent); the
                  rebalance dead band
    snapshot      the fields that leave the cluster, as one object for the layer above

The catalogue is deliberately short. `labels-subset`: a unit's `labels` must
be a subset of what the worker's server reports. `most-free-capacity`: the
worker with the most capacity − load wins. A subsystem that needs another
rule registers a function under a name (`register_constraint`), which is the
same door the resource opens for its hooks — code, named, not YAML pretending
to be code.

What is NOT in a spec: anything about what a unit does. That is the worker,
and the worker is the subsystem.
"""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # spec.py — the controller as data: SubsystemSpec from `<sub>.subsystem.yaml`, and SpecController, the one
# controller every subsystem runs
#
# **Role in the module.** Lesson 6. A subsystem gives the platform one YAML file and the platform runs its
# controller from it. The spec says: `name` (the prefix `<name>/*`); `unit` (where rows live —
# `<name>/<rows>/<id>` — how an id is made — `numeric` or a field name — the operator's fields with types
# and defaults, and derived rows kept beside the unit, such as the VMS's `vms/retention/<id>` that the
# resource reads); `placement` (which heartbeat fields carry capacity and headroom, a constraint and a
# tie-break chosen *by name* from a short catalogue — never an expression — `requires: resource` when the
# worker's server must have a resource that answers, and the rebalance dead band);
# `snapshot` (the fields that leave the cluster); `console` (the name of the running gauge). What is not in
# a spec: anything about what a unit does — that is the worker, and the worker is the subsystem.
# `SpecController` extends `contract.Controller` and adds units, placement, redistribution, rebalance, the
# read model and the snapshot. `vms/controller.py` is this class with the VMS's spec and VMS names for the
# methods; `vms/config.py` exposes `row()`/`items()`; `console.py` runs over the same spec.
# `tests/test_lesson8_live.py` and `tests/test_lesson9_det.py` run two more subsystems through it from their own YAML.
#
# ## Module-level names
# - `PLATFORM_FIELDS = ("worker", "placement", "epoch", "revision", "observed_revision", "phase", "id")` —
#   never the operator's. `SubsystemSpec.refuse` rejects any of them in a create/update body: placement is
#   decided and stored by the controller with a reason; revision, epoch and phase are not the operator's.
# - `SpecController.POLICY_DEFAULTS` / `POLICY_CHOICES` — the administrator's knobs, one row `<name>/policy`
#   written by the console (`acl_console` includes it) and read by the controller on every pass: `servers`
#   is `shared` (default: every worker carries units, two on one server included — a box is that; a dead
#   server's slot is the scheduler's to reschedule onto a neighbour) or `distinct` (one worker per server
#   carries units, `idle_by_policy` names the rest; a server whose worker and resource are both silent is
#   gone, `gone_servers`, and its units move). The jobspec says `spread`, so both are possible without
#   touching Nomad.
# - `CONSTRAINTS` — the catalogue: `"none"` (always eligible) and `"labels-subset"` (`_labels_subset`).
#   `requires: resource` is not a constraint on the unit but on the worker's server: `resource_state` reads
#   `platform/resources/<server>/heartbeat` — `live`, `silent`, or `unknown` (never seen) — and `_pool`
#   drops workers whose resource is silent; `redistribute` moves their units off with the reason
#   `resource on <server> silent`. Nomad's `meta.archive` puts a worker where disks are declared; this is
#   whether the resource there still answers. `unknown` passes: silent is a fact, unknown is not one.
#   Extended only by `register_constraint`.
#
# ## Notes
# - Every write is `Controller.write` (CAS loop) or a create-only `put(cas=0)`; nothing is cached between passes,
#   so the process can be killed anywhere. Within one pass each key is read once (`contract.one_pass`). One
#   exception, on purpose: the servers' labels last read (`server_labels`) are kept, so a store that does not answer
#   moves nothing — a process that never read them moves nothing either.
# - What a server reaches (feedback DQ): `<name>/servers/<server> {labels}`, the console's row, over the labels its
#   workers report (`labels_of`, `node_labels_of`); `ensure_reach` moves a placed unit its server no longer reaches,
#   or unplaces it with the reason, `REACH_BUDGET` a pass.
# - The order inside `place` — placement row, then assignment — is what makes two instances agree: the row
#   is the lock.
# - `capacity_of`/`labels_of`/`server_of` call `workers_seen(max_age=1e12)` each time: outside a pass one
#   object-store listing per call, inside one (`pass_once`, the snapshot) the heartbeats read once for the pass.
# ================================================================================================
from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field

from urllib.parse import urlsplit

from .doors import numeric, unnamable
from .secrets import is_secret_field
from .blobs import digest as blob_digest, is_digest, verify
from .contract import ASSIGNMENTS, ASSIGNMENTS_GARBLED, CONTROLLER_PASS, DRAIN_KEY, SLOTS_GARBLED, UNPLACED, Controller, Subsystem, is_live, one_pass, slot_number
from .events import Suppress
from .limits import TooLarge
from .objects import ObjectStore
from .rows import PARSE_ERRORS, Table, finite
from .variables import Conflict, Variables

PLATFORM_FIELDS = ("worker", "placement", "epoch", "revision", "observed_revision", "phase", "id")   # never the operator's
# The most a single `json` field may be. Not the row's ceiling (Lesson 19) — this one keeps ONE field
# from eating it, because a field that can hold a document will be given one.
JSON_CEILING = 4000


# A write the spec does not allow: a platform field, an unknown field, a missing required field, an id for a
# numeric-id subsystem, a duplicate id. The console turns it into HTTP 400.
log = logging.getLogger(__name__)


class Moved(Exception):
    """A move the controller decided on a row that has changed since: somebody else moved the unit first."""


class Refused(Exception):
    pass


# The counter of numeric ids, `<name>/next_id`, through the one reader of rows (`SpecController._next_id`).
NEXT_IDS = Table("next_id", "the next id is one past the largest one there is, and the row is written whole")
# A unit stored under a name `create` refuses today (`doors.unnamable`, `unit`; the review's ninth pass): served as it
# stands — but a name with `,` is in no assignment (`contract.Assignment.to_items`), so nobody runs it.
UNIT_NAMES = Table("unit_name", "it is served as it stands, a name with a comma is assigned to nobody; create it again "
                                "under a name without the character", "unit's name")
# A server's labels from the console (`<sub>/servers/<server>`, feedback DQ): one that does not parse — a word that is not
# a label, no `labels` at all, a key the listing shows and a read does not find — keeps what was last read of that
# server; never read, the server reaches no label until it is (the review's tenth pass) — and nothing moves off it
# (`SpecController.server_labels`).
SERVER_LABELS = Table("server_labels", "the server keeps the labels last read of it — if none were read, it takes no unit "
                      "that needs a label — and nothing moves off it", "server's labels")
# What a label may be: the camera's own alphabet (`vlan:cctv-a`, `site.b`), and nothing that is a separator in the row
# (a comma) or in a path. The product's rule (`labelWord`). ONE alphabet (the review's tenth pass, major): a camera's
# `labels` (any subsystem's under `labels-subset`, at creation and for a label new to a row), a server's row, the
# node's `LABELS` (`runtime.labels` says the words outside it). A camera stored before with `склад` or `zone 1` is
# read as it stands and is not moved for a label no server's row can say (`UNIT_LABELS`).
LABEL_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:\-]{0,63}")
UNIT_LABELS = Table("unit_label", "the unit stays where it is: no server's row can say it reaches that label — write the "
                    "label again in letters, digits and _ . : -", "unit's label")
# A server's name: what a host's name may be (letters, digits, `.`, `-`, `_`; 253 at most) — `*`, `srv%2Fa`, a newline,
# three hundred characters were rows nobody's server would ever read (the review's tenth pass, minor).
SERVER_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.\-]{0,252}")
REACH_BUDGET = 10                 # moves `ensure_reach` makes in one pass: a server's labels edited moves its units over a few


def parse_labels(text) -> frozenset:
    """A row's `labels` — comma-joined label words — as a set; `ValueError` for a word that is not a label."""
    out = frozenset(l.strip() for l in str(text).split(",") if l.strip())
    bad = [l for l in out if not LABEL_WORD.fullmatch(l)]
    if bad:
        raise ValueError(f"{bad[0]!r} is not a label")
    return out


def server_name(server: str) -> str:
    """A server's name as a row's key: not a path, no character a list or a log would split on — a host's name."""
    server = str(server or "")
    if not SERVER_WORD.fullmatch(server) or server in (".", "..") or unnamable(server, unit=True):
        shown = server if len(server) <= 80 else server[:80] + "…"
        raise Refused(f"{shown!r} is not a server's name: letters, digits and . - _ (up to 253)")
    return server


def label_refusal(labels, old=()) -> str | None:
    """Why a unit's `labels` may not stand — a label new to the row outside `LABEL_WORD` — or None. One stored before is
    left as it is (`old`): refusing it would make every other edit of that unit's row a 400."""
    bad = [l for l in (labels or []) if str(l) not in set(map(str, old or ())) and not LABEL_WORD.fullmatch(str(l))]
    return (f"a label is letters, digits and _ . : - (up to 64), starting with a letter or a digit, not {bad[0]!r}"
            if bad else None)


# A stored placement decision: `unit` (int for numeric ids, str otherwise), `worker`, `reason` (a sentence
# naming the free capacity, the labels reached and the server), `at` (wall time), `rev`. Lives at
# `<name>/placement/<id>`.
@dataclass
class Placement:
    unit: object                  # the unit's id: an int for numeric ids, a str otherwise
    worker: str
    reason: str
    at: float
    rev: int


# One operator field from the spec: `name`, `type` (`string | int | float | bool | list | url | blob`),
# `default`, `required`. A `blob` holds a DIGEST (`sha256-<hex>`); the bytes live in the object store under
# `<name>/blobs/<digest>` and the platform never looks inside them — see `blobs.py`.
#
# `inherit` instead of `default` (М12 Lesson 12, feedback AT): the field may be left NOT SET, and a value
# somebody above sets — a domain's shared default — is then the value. A `default` cannot do that: it is
# written into the row when the row is created and supplied again when the row is read, so "set" and "not set"
# are the same row, and an inherited value never applies. An inheriting field has no default at all: a new row
# does not carry it, a read gives `None`, and the value in `inherit` is only the LAST link of the chain, taken
# at the moment of use by whoever resolves it (`SharedView.effective` in М12; the resource's own fallback for
# retention). `merge` says what a set value does to an inherited one: `override` (the default) replaces it,
# `union` adds to it — a list of alarm kinds the site declares, plus the camera's own.
@dataclass
class Field:
    name: str
    type: str = "string"          # string | int | float | bool | list | url | blob | json
    default: object = None
    required: bool = False
    inherit: object = None        # the fallback of an inheriting field; see `inherits`
    inherits: bool = False
    merge: str = "override"       # override | union — for an inheriting field

    # Convert an item string or JSON value to the typed value; `None` gives the default. Bools accept a real
    # bool or the string `"true"`; lists accept a list or a comma-separated string.
    def parse(self, v):
        if self.inherits and (v is None or v == ""):
            return None                                  # not set: the value is whatever is inherited
        if v is None:
            return self.default_value()
        if self.type == "int":
            return int(v)
        if self.type == "float":
            return float(v)
        if self.type == "bool":
            return v if isinstance(v, bool) else str(v).lower() == "true"
        if self.type == "list":
            return list(v) if isinstance(v, (list, tuple)) else [x for x in str(v).split(",") if x]
        # A small structured value, stored as compact JSON and handed back parsed. The fifth subsystem
        # needed it and none of the four before it did, which is the bar: a scenario's triggers are a
        # LIST OF SHAPES, and flattening that into fields would either cap it at one trigger or invent
        # `when_1_sub`, `when_2_sub` — a schema pretending not to be one.
        #
        # What the platform checks is exactly what it can: valid JSON, and small. What the shapes MEAN is
        # the subsystem's, checked in its own controller before the row is written, the way `vms/volumes`
        # checks a volume. A generic loader that tried to validate a trigger would be a generic loader
        # that knows what a trigger is.
        if self.type == "json":
            import json as _json
            return _json.loads(v) if isinstance(v, (str, bytes)) else v
        return str(v)

    # The declared default, else the type's zero (`0`, `0.0`, `False`, `[]`, `""`).
    def default_value(self):
        if self.inherits:
            return None
        if self.default is not None:
            return self.default
        return {"int": 0, "float": 0.0, "bool": False, "list": [], "json": None}.get(self.type, "")

    # The Variables form: bools as `"true"/"false"`, lists comma-joined, else `str`.
    def to_item(self, v) -> str:
        if self.type == "bool":
            return "true" if v else "false"
        if self.type == "list":
            return ",".join(v)
        if self.type == "json":
            import json as _json
            return _json.dumps(v, separators=(",", ":"), ensure_ascii=False) if not isinstance(v, str) else v
        return str(v)


# A second row the platform keeps beside the unit: `row` (a path template under the prefix with `{id}`, e.g.
# `retention/{id}`), `items` (`{item name: field name}` — which unit field feeds each item), `on_delete`
# (what the row becomes when the unit is deleted; `None` leaves it alone). The VMS's derived row makes
# `events_retention_days` visible to the resource as `vms/retention/<id> {days}` and sets `{days: 0}` on
# delete so the buckets go at the next pass.
@dataclass
class Derived:
    row: str                      # under the subsystem's prefix, with {id}
    items: dict                   # item -> field
    on_delete: dict | None = None # what the row becomes when the unit is deleted (None: left alone)


# `events.suppress` parsed into `{kind: Suppress}`. `by` left out means every field of the line, which is
# the reading that cannot lose an observation — see `Suppressor` in `events.py`. Read leniently HERE and
# refused in `from_dict`: parsing says what was written, the checks say whether it may be used, and keeping
# the two apart is what lets a refusal name the number it objects to.
def suppress_rules(events: dict) -> dict[str, Suppress]:
    out: dict[str, Suppress] = {}
    for kind, rule in (events.get("suppress") or {}).items():
        rule = rule or {}
        by = rule.get("by")
        out[str(kind)] = Suppress(str(kind), float(rule.get("window", 0) or 0),
                                  tuple(str(b) for b in by) if by is not None else None)
    return out


# The parsed YAML. Fields: `name`; `rows` (`"units"`; the VMS says `cameras`); `id` (`"numeric"` or a field
# name); `fields`; `derived`; `capacity_from` / `capacity_fallback` (heartbeat key for a worker's capacity,
# and the number for a worker that said nothing); `headroom_from`; `constraint`; `tie_break` (only
# `most-free-capacity` exists); `dead_band`; `snapshot` (field names); `running_gauge` (`units_running` by
# default; `cameras_running` for the VMS).
@dataclass
class SubsystemSpec:
    name: str
    rows: str = "units"
    id: str = "numeric"           # numeric, or the field whose value is the id
    fields: dict[str, Field] = field(default_factory=dict)
    derived: list[Derived] = field(default_factory=list)
    capacity_from: str = "capacity"
    capacity_fallback: int = 50
    headroom_from: str = "headroom"
    constraint: str = "none"
    requires: str = "none"        # "resource": a worker is eligible only while its server's resource is not silent
    servers: str = "shared"       # the default of the `servers` policy knob: shared | distinct (the console may change it)
    tie_break: str = "most-free-capacity"
    near: str = "none"            # a subsystem whose worker holding the same unit id this one prefers to be beside (an affinity, never a filter)
    # WHICH unit of that subsystem. `id` — the same unit id, which is what `near: <sub>` means and all the
    # VMS needed while the camera and its recording were the same string. A subsystem whose units are named
    # for something else has to say so: a detector's unit is `7-linecross`, no recorder ever reports that id,
    # and `near: rec` on it would match nothing — an affinity that reads as followed and is not. So
    # `near: {sub: rec, by: cam}` — follow the recorder holding the recording my `cam` field names.
    near_by: str = "id"
    # `near: {sub: rec, of: cam}` — WHAT OF THEIRS the value is matched against. `by` says which value of
    # MINE to look for (my id, or a field of my row); `of` says where in THEIR status to look for it (their
    # unit id by default, or a field they report). The two are independent, and the second arrived when
    # recordings stopped being named by their camera: "the recorder running a recording whose `cam` is
    # camera 7" holds whether the operator called it `7`, `7-cloud` or `gate-lobby`, while "the recorder
    # running unit `7`" was only ever true by coincidence — and silently false when the coincidence ended.
    #
    #   vms:    near: {sub: rec, of: cam}            my id (7)        vs their `cam`     — whoever records me
    #   det:    near: {sub: rec, by: cam, of: cam}   my field `cam`   vs their `cam`     — likewise, for a pair
    #   detjob: near: {sub: rec, by: rec}            my field `rec`   vs their id        — I name the recording
    #
    # The field is read from the heartbeat STATUS (`status_extra` puts it there), not from the other
    # subsystem's rows, which this controller has no business reading. Several of their units may answer —
    # two recordings of one camera — and then the affinity takes the smallest of their ids, so two passes
    # over the same heartbeats reach the same server. Being beside one of them is the point; the other
    # reads the same fan-out over the network.
    near_of: str = ""
    # `home: <field>` — the server named in that field of the unit's own row is where it prefers to run;
    # `home: near` — wherever the subsystem this one follows is. A PREFERENCE and not a label: a label is a
    # filter, and a unit whose home is down would become unplaceable — the one thing it must not be,
    # because the home being down is exactly when the work has to continue somewhere else. It is topology,
    # not taste: the recording's home is the disk it is written to. Coming home is then not a procedure but
    # a consequence, bounded by `ensure_home`.
    home: str = ""
    # `spread_by: <field>` — units sharing a value of that field go on DIFFERENT servers. Unlike `near` this
    # is a FILTER, not a preference: the whole point of a second copy is that it is not where the first one
    # is, and a second copy on the same server is not a second copy. Unplaceable while no other server
    # qualifies, and that is the honest answer — `/unplaceable` says so rather than quietly co-locating.
    spread_by: str = ""
    # `group_by: <name>` — the mirror image, and the one the VMS needed first: units sharing a value go on
    # the SAME worker. Also a FILTER, for a reason that is not about preference at all — a device is ONE
    # connection. Sixteen channels of one recorder are sixteen units, and placing them on four workers
    # opens four sessions to a box that licenses two; the subsystem then fails in the device's words
    # ("too many sessions"), which is the hardest kind of failure to trace back to a placement decision.
    #
    # What the value is, the platform does not know: `group_value(row)` reads the field of this name by
    # default, and a subsystem whose grouping is not a plain field overrides it — the VMS parses the
    # device out of `driverpack://<device>/<channel>`, which no generic loader could do.
    #
    # Where it hurts, and it does: the worker holding the group is not chosen for its room. A group that
    # outgrows its worker becomes unplaceable rather than spilling over, because spilling over is the
    # thing being prevented. The operator raises that worker's capacity or moves the group — `/unplaceable`
    # names the device, so the answer is on the screen rather than in a session count on a camera.
    group_by: str = ""
    # `place_by: <field>` — WHAT the policy and the home are counted in: the heartbeat field that names the
    # place a worker occupies. `server` by default, and for everything whose unit of storage is a server
    # that is the truth. A recorder's is not: a box with three disks runs three recorders, one per volume,
    # and `servers: distinct` has to mean one per DISK — two recorders on one volume are no second place to
    # record, while two on one server with different disks are exactly that.
    #
    # Only the policy and `home` follow this field. Reachability (`requires: resource`), draining and
    # `spread_by` stay on the server, because those are about a machine: a volume has no address, cannot be
    # drained on its own, and two copies on two disks of one server survive nothing the operator was buying
    # insurance against.
    place_by: str = "server"
    # `retire_when: {field: state, in: [done, failed]}` — a unit whose row says one of those values is
    # FINISHED, and finished work is not placed. The first subsystem to need it is `detjob`, whose unit
    # ends; everything before it ran until an operator said stop.
    #
    # Not `enabled`. That field is read by workers, never here: a disabled camera keeps its assignment and
    # its line in the console's list, and a unit that has to STAY VISIBLE while doing nothing is a
    # different thing from one that is over. Saying which field and which values, per subsystem, is the
    # difference between the two — and it is the row that says it, not a heartbeat: un-placing a finished
    # unit makes its worker drop it, which makes the heartbeat stop mentioning it, which would erase the
    # only evidence it was ever finished. It would then be placed again, and start over, for ever.
    retire_field: str = ""
    retire_values: tuple = ()
    dead_band: float = 0.10
    snapshot: list[str] = field(default_factory=list)
    # `tables: [volumes]` — row families this subsystem's CONSOLE owns besides its units. Not units: nothing
    # is placed on them, they have no epoch and no worker; they are the administrator's lists, like `policy`
    # but plural and named. `rec` declares `volumes`, the archives an operator may write recordings into.
    #
    # The platform learns the NAME and nothing else: the ACL gains `<name>/<table>/*`, and what a row of
    # that table means, which fields it has and which routes serve it are the subsystem's, in its own
    # console code. That is the line: a generic grant is a platform matter, a volume is not.
    tables: tuple[str, ...] = ()
    running_gauge: str = "units_running"     # the console's gauge for units in phase "running" (console: {running: …})
    # `events: {older_epochs: fenced | earlier-run}` — what it MEANS that a unit's events were written
    # under an epoch that is not the current one.
    #
    # `fenced` (the default, and right for everything that runs until stopped): a writer that lost the
    # race and kept writing. The page strikes those events through, because they are a zombie's.
    #
    # `earlier-run`: the same mechanism, the opposite meaning. A unit whose work ENDS takes a new epoch
    # every time the operator runs it again, so an older epoch is a finished earlier result — a run to
    # compare against, not a loser to strike through. Marking it `fenced` would tell an operator that the
    # search they ran last week was never valid.
    older_epochs: str = "fenced"
    # `events: {suppress: {<kind>: {window: <seconds>, by: [<field>, …]}}}` — which of this subsystem's
    # event kinds collapse when they repeat, and what counts as a repeat.
    #
    # A storm is normal, not a fault, and the only place a repeat costs nothing to recognise is the writer
    # (`Suppressor`, `events.py`). The subsystem declares it because the timescale belongs to the event:
    # a door contact bounces in milliseconds, a motion detector re-reports for as long as the scene moves,
    # a link flaps for as long as the cable is bad. The platform holds none of those numbers.
    #
    # `by` defaults to every field of the line, which is the reading that cannot lose an observation: two
    # lines collapse only when they are identical. A subsystem narrows it when a field drifts for a reason
    # that is not a new observation.
    suppress: dict[str, "Suppress"] = field(default_factory=dict)

    # Builds the spec from the YAML dict, tolerating absent sections. Field defaults are parsed to their
    # type once here (strings kept as strings so `"cam{id}"` survives). `snapshot` defaults to every field.
    @classmethod
    def from_dict(cls, d: dict) -> "SubsystemSpec":
        unit, pl = d.get("unit", {}), d.get("placement", {})
        fields = {n: Field(n, f.get("type", "string"), f.get("default"), bool(f.get("required", False)),
                           f.get("inherit"), "inherit" in f, f.get("merge", "override"))
                  for n, f in (unit.get("fields") or {}).items()}
        for f in fields.values():
            if f.inherits and f.default is not None:
                raise ValueError(f"field {f.name}: `default` and `inherit` — a field is either filled in when the row "
                                 f"is created or left for somebody above to set, not both")
            if f.merge not in ("override", "union"):
                raise ValueError(f"field {f.name}: merge is override or union, not {f.merge!r}")
            if f.default is not None:
                f.default = f.parse(f.default) if f.type != "string" else str(f.default)
            if f.inherits and f.inherit is not None:
                f.inherit = Field(f.name, f.type).parse(f.inherit) if f.type != "string" else str(f.inherit)
        derived = [Derived(x["row"], dict(x.get("items", {})), x.get("on_delete")) for x in unit.get("derived", [])]
        # `snapshot:` LEFT OUT means "every field that may go" — a convenience, not a decision.
        # `snapshot: []` means "no field of the row leaves the cluster", which is a decision. The two were
        # one thing here for as long as this read `list(d.get("snapshot", [])) or [every field]`: an empty
        # list is falsy, so a spec declaring "publish nothing" published everything, and its author would
        # have learned that from М12 rather than from the file they wrote.
        #
        # An empty list is not an empty object. `id`, `revision`, `worker` and `server` are structural and
        # go either way, because "which unit is where" is the snapshot's other job and the layer above is
        # built on it. What `[]` buys is that nothing an OPERATOR typed leaves the cluster.
        #
        # `snapshot:` with nothing after it is neither, so it is refused rather than guessed: the author
        # meant one of the two and the file does not say which.
        if "snapshot" in d and d["snapshot"] is None:
            raise ValueError(f"spec {d['name']}: `snapshot:` with nothing after it says neither — write "
                             f"`snapshot: []` for no fields, or leave the key out for every field")
        declared = d.get("snapshot")
        cap = pl.get("capacity", {}) or {}
        spec = cls(name=d["name"], rows=unit.get("rows", "units"), id=str(unit.get("id", "numeric")), fields=fields,
                   derived=derived, capacity_from=cap.get("from", "capacity"), capacity_fallback=int(cap.get("fallback", 50)),
                   headroom_from=(pl.get("headroom", {}) or {}).get("from", "headroom"),
                   constraint=pl.get("constraint", "none"), requires=str(pl.get("requires", "none")), servers=str(pl.get("servers", "shared")), tie_break=pl.get("tie_break", "most-free-capacity"),
                   near=str((pl.get("near") or {}).get("sub", "none") if isinstance(pl.get("near"), dict) else pl.get("near", "none")),
                   near_by=str((pl.get("near") or {}).get("by", "id") if isinstance(pl.get("near"), dict) else "id"),
                   near_of=str((pl.get("near") or {}).get("of", "") if isinstance(pl.get("near"), dict) else ""),
                   spread_by=str(pl.get("spread_by", "") or ""),
                   group_by=str(pl.get("group_by", "") or ""),
                   place_by=str(pl.get("place_by", "server") or "server"),
                   home=str(pl.get("home", "") or ""),
                   retire_field=str((pl.get("retire_when") or {}).get("field", "") or ""),
                   retire_values=tuple(str(v) for v in ((pl.get("retire_when") or {}).get("in") or [])),
                   dead_band=float((pl.get("rebalance", {}) or {}).get("dead_band", 0.10)),
                   snapshot=(list(declared) if declared is not None else
                             [n for n, f in fields.items() if not is_secret_field(n) and f.type != "blob"]),
                   tables=tuple(str(t) for t in (d.get("tables") or [])),
                   running_gauge=str((d.get("console", {}) or {}).get("running", "units_running")),
                   older_epochs=str((d.get("events", {}) or {}).get("older_epochs", "fenced")),
                   suppress=suppress_rules(d.get("events", {}) or {}))
        # A secret in the snapshot is a secret leaving the cluster: `vms/snapshot/*` is what М12's directory
        # reads. Refused at LOAD time, not watched for at review time — and only when it is named, because
        # the default ("every field") is a convenience and not a decision.
        # A table's name becomes a key family and an ACL prefix, so it is a name and not a path, and it may
        # not be the unit rows under another spelling — two writers on one family with different rules.
        for t in spec.tables:
            if not t or "/" in t or t in (spec.rows, "policy", "slots", "holds", "epoch", "idem", "requests", "servers"):
                raise ValueError(f"spec {spec.name}: `tables:` takes a fresh row family name, not {t!r}")
        leaks = [n for n in spec.snapshot if is_secret_field(n)]
        if leaks:
            raise ValueError(f"spec {spec.name}: a secret may not be in the snapshot: {leaks} — "
                             f"the snapshot is what leaves the cluster")
        # A blob is the one field that is certainly too big for the snapshot, and the snapshot is one
        # object per worker with a ceiling over it. Refused at LOAD time for the same reason a secret is:
        # by the time someone notices the snapshot stopped publishing, М12 has been stale for a while.
        heavy = [n for n, f in fields.items() if f.type == "blob" and n in spec.snapshot]
        if heavy:
            raise ValueError(f"spec {spec.name}: a blob may not be in the snapshot: {heavy} — the snapshot "
                             f"is one object per worker under a ceiling, and a blob is what does not fit "
                             f"in a row in the first place")
        unknown_snap = [n for n in spec.snapshot if n not in fields]
        if unknown_snap:
            raise ValueError(f"spec {spec.name}: snapshot names no field: {unknown_snap}")
        if spec.older_epochs not in ("fenced", "earlier-run"):
            raise ValueError(f"spec {spec.name}: events.older_epochs is fenced or earlier-run, "
                             f"not {spec.older_epochs!r} — the page draws one of the two")
        # Suppression drops observations, so its declaration is refused at LOAD time rather than read
        # leniently. A window of zero is the shape a typo takes (`window: 0`, a missing key, a string
        # that did not parse), and reading it as "no suppression" would leave a subsystem believing it
        # had some. The fields naming what repeats are names, never a path or the reserved words the
        # summary line itself carries.
        for r in spec.suppress.values():
            if r.window <= 0:
                raise ValueError(f"spec {spec.name}: events.suppress.{r.kind}.window is seconds and must be "
                                 f"positive, not {r.window!r} — a kind with no window is a kind not listed here")
            if r.by is not None and not r.by:
                raise ValueError(f"spec {spec.name}: events.suppress.{r.kind}.by is empty — every line of "
                                 f"{r.kind} would then be the same thing. Leave `by` out for every field, "
                                 f"or name the fields that decide sameness")
            for b in r.by or ():
                if not b or "/" in b or b in ("repeats", "since", "until"):
                    raise ValueError(f"spec {spec.name}: events.suppress.{r.kind}.by names {b!r} — a field "
                                     f"name, and not one the summary line writes itself")
        if spec.retire_field and spec.retire_field not in fields:
            raise ValueError(f"spec {spec.name}: retire_when names no field: {spec.retire_field!r}")
        if bool(spec.retire_field) != bool(spec.retire_values):
            raise ValueError(f"spec {spec.name}: retire_when needs both a field and a non-empty `in` — "
                             f"a predicate that matches nothing retires nothing, silently")
        if spec.near_by != "id" and spec.near_by not in fields:
            raise ValueError(f"spec {spec.name}: near.by names no field: {spec.near_by!r}")
        if spec.near_by != "id" and spec.near == "none":
            raise ValueError(f"spec {spec.name}: near.by needs a near to follow")
        if spec.group_by and spec.group_by == spec.spread_by:
            raise ValueError(f"spec {spec.name}: `group_by` and `spread_by` name the same field "
                             f"({spec.group_by!r}): together they say units must be on one worker and on "
                             f"different servers")
        if spec.near_of and spec.near == "none":
            raise ValueError(f"spec {spec.name}: near.of needs a near to follow")
        # `of` names a field of the OTHER subsystem's status, which this loader cannot see — nothing to
        # check here. A name that matches nothing behaves like an affinity that finds no holder: units are
        # placed by the filters alone, `_pick` says so in its reason, and nobody is refused.
        if spec.home == "near" and spec.near == "none":
            raise ValueError(f"spec {spec.name}: home: near needs a near to follow")
        if spec.home and spec.home != "near" and spec.home not in fields:
            raise ValueError(f"spec {spec.name}: home names no field: {spec.home!r}")
        return spec

    # `yaml.safe_load` then `from_dict`. PyYAML is imported lazily so the rest of the platform has no
    # dependency on it.
    @classmethod
    def load(cls, path: str) -> "SubsystemSpec":
        import yaml
        with open(path) as f:
            return cls.from_dict(yaml.safe_load(f))

    # `Subsystem(name)` — the key layout from `contract.py`.
    @property
    def sub(self) -> Subsystem:
        return Subsystem(self.name)

    # -- who writes what: two tokens, one prefix each ------------------------------------
    # The operator's rows: `<name>/<rows>/*`, `<name>/next_id`, `<name>/idem/*` (a retried POST answered the
    # same by any instance), `<name>/policy` (the administrator's knobs) and the first segment of every
    # derived row (`<name>/retention/*`). Never placement. This is the console process's token.
    def acl_console(self) -> list[str]:
        """The operator's rows: what a console (one per server, any of them) may write — never placement."""
        out = [f"{self.name}/{self.rows}/*", f"{self.name}/next_id", f"{self.name}/idem/*",   # idem: a retried POST answered the same by ANY instance
               f"{self.name}/policy",                                                         # the administrator's knobs: servers distinct | shared
               f"{self.name}/sweep",                                                          # what the blob sweep marked, and when
               f"{self.name}/requests/*",                                                     # bounded work an operator asked a worker for, outside its ordinary pass
               f"{self.name}/servers/*",                                                      # what a server reaches, as the administrator says it (feedback DQ)
               DRAIN_KEY]                                                                     # "this machine is about to stop": the operator's, and the same row for every subsystem
        for d in self.derived:
            out.append(f"{self.name}/{d.row.split('/')[0]}/*")
        out += [f"{self.name}/{t}/*" for t in self.tables]              # the administrator's lists: `rec/volumes/*`
        return out

    # Placement: `<name>/workers/*`, `<name>/placement/*`, `<name>/slots/*` — never a unit's row. The
    # controller process's token (count = 1). Together the two ACLs split the old `<name>/*` so that the
    # console cannot place and the controller cannot edit; `test_the_console_over_http` proves
    # `con.place(1)` raises `Forbidden`.
    def acl_controller(self) -> list[str]:
        """Placement: what the controller (count = 1) may write — never a unit's row."""
        return [f"{self.name}/workers/*", f"{self.name}/placement/*", f"{self.name}/slots/*"]

    # Whether ids are numbers; convert a string id accordingly.
    @property
    def numeric(self) -> bool:
        return self.id == "numeric"

    def parse_id(self, v):
        return int(v) if self.numeric else str(v)

    # -- rows <-> items --------------------------------------------------------------
    # Variables items to a typed row: `id`, every spec field (default if absent), `revision` (default 1).
    def row(self, items: dict) -> dict:
        r = {"id": self.parse_id(items["id"])}
        for n, f in self.fields.items():
            r[n] = f.parse(items.get(n)) if n in items else f.default_value()
        r["revision"] = int(items.get("revision", 1))
        return r

    # The inverse, all strings.
    def items(self, row: dict) -> dict:
        out = {"id": str(row["id"]), "revision": str(row.get("revision", 1))}
        for n, f in self.fields.items():
            v = row.get(n, f.default_value())
            if f.inherits and v is None:
                continue                                 # not set is ABSENT — never a stored "None"
            out[n] = f.to_item(v)
        return out

    # Raise `Refused` for any `PLATFORM_FIELDS` key or any key not in the spec. Called first by `create` and
    # `update`.
    def refuse(self, fields: dict) -> None:
        bad = [k for k in fields if k in PLATFORM_FIELDS]
        if bad:
            raise Refused(f"a client may not set {bad}: placement is decided and stored by the controller with a "
                          f"reason; revision, epoch and phase are not the operator's")
        unknown = [k for k in fields if k not in self.fields]
        if unknown:
            raise Refused(f"unknown field(s) {unknown}")
        # A secret arrives in the clear and is sealed HERE, on its way into the store. A value that already looks
        # sealed is a copy from another row — camera 7's ciphertext under camera 8, for the holder to open for
        # whoever reads 8 — or a typo that would stop the holder's pass (the review's second pass, blocker 3 and a
        # major): refused at the door. Nothing a client types is `enc:v1:…`.
        from .sealing import is_sealed, is_secret_field
        pasted = [k for k, v in fields.items() if is_secret_field(k) and is_sealed(v)]
        if pasted:
            raise Refused(f"{pasted}: a secret is given in the clear and sealed by this console; a sealed value is not taken")
        # A `url` field may not carry a userinfo. `rtsp://root:hunter2@10.0.0.5/…` is how a password
        # reaches a row that is in the SNAPSHOT — out of the cluster, into М12's directory, and onto the
        # screen of every console, past a mask that only looks at `*_secret`. The credential fields are
        # where it goes instead, and saying so is better than moving it quietly: an operator who pasted a
        # URL from a browser learns that this system keeps the two apart.
        # A `blob` field holds the digest of the bytes, never the bytes. Without this, the obvious thing
        # for a client to do — paste the lump into the row — is also the thing that puts a row over the
        # store's ceiling, and the refusal it gets says "too big" rather than what to do instead.
        for name, f in self.fields.items():
            if f.type == "blob" and fields.get(name) and not is_digest(fields[name]):
                raise Refused(f"{name} takes a digest, not the bytes ({len(str(fields[name]))} of them): "
                              f"PUT the bytes to /{self.rows}/<id>/{name} and the row gets the digest back")
        for name, f in self.fields.items():
            # A `json` field that is not JSON is a 400 to whoever typed it, not a 500 from the store on
            # the next read. The ceiling is the row's own (Lesson 19's limit) — this one keeps a single
            # field from eating it: a scenario is a handful of triggers, not a document.
            if f.type == "json" and fields.get(name) is not None:
                import json as _json
                raw = fields[name]
                try:
                    text = raw if isinstance(raw, str) else _json.dumps(raw)
                    _json.loads(text)
                except (TypeError, ValueError) as e:
                    raise Refused(f"{name} is not JSON: {e}")
                if len(text) > JSON_CEILING:
                    raise Refused(f"{name} is {len(text)} bytes of JSON; the ceiling is {JSON_CEILING}")
            if f.type == "url" and fields.get(name):
                # …and a url `urlsplit` cannot read, or whose port is no port, is a 400 with the words (the product
                # team's sibling of the tenth pass): `rtsp://[10.0.0.5/x` raised `ValueError` out of here — a 500 — and
                # `…:8²/…` was taken, to stand in every reader of the row.
                try:
                    u = urlsplit(str(fields[name]))
                    u.port
                except ValueError as e:
                    raise Refused(f"{name} is not an address: {e}")
                if u.username or u.password or "@" in u.netloc:
                    raise Refused(f"{name} may not carry a login: put it in cred_username / cred_secret — "
                                  f"a url field is in the snapshot, and the snapshot leaves the cluster")

    # A fresh row: each required field must be present and truthy (`"a vms unit needs a source"`), others
    # get their default; a string value containing `{id}` has it substituted (the VMS's `name: "cam{id}"`);
    # `revision` is 1.
    def new_row(self, uid, fields: dict) -> dict:
        r = {"id": uid}
        for n, f in self.fields.items():
            if f.required and not fields.get(n):
                raise Refused(f"a {self.name} unit needs a {n}")
            v = fields.get(n)
            r[n] = f.parse(v) if v is not None else f.default_value()
            if isinstance(r[n], str) and "{id}" in r[n]:
                r[n] = r[n].replace("{id}", str(uid))
        r["revision"] = 1
        return r


# -- the catalogue --------------------------------------------------------------------
# The unit's `labels` must be a subset of what the worker's server reports.
def _labels_subset(row: dict, worker_labels: set[str]) -> bool:
    return set(row.get("labels") or []) <= worker_labels


CONSTRAINTS = {"none": lambda row, labels: True, "labels-subset": _labels_subset}


# A subsystem's own rule, as code under a name — never as YAML. The same door the resource opens for its
# hooks.
def register_constraint(name: str, fn) -> None:
    """A subsystem's own rule, as code under a name — never as YAML."""
    CONSTRAINTS[name] = fn


# Two more doors of the same kind, for rules a constraint cannot state because they need more than the row
# and the worker's labels. Keyed by the SPEC's name; the platform calls them and knows nothing of what they
# mean.
#
# `admit(ctl, row, worker) -> bool` — may this unit be placed on this worker at all. A FILTER: it runs in
# `eligible`, beside the labels and `spread_by`, so it beats `home` and `near` the way they do. The VMS
# registers one for `rec`: a backup volume holds only the recordings homed on it, and they go nowhere else.
#
# `near_rank(ctl, their_id, memo) -> sortable` — when `near` finds SEVERAL units of the followed subsystem (two
# recordings of one camera), which one to stand beside. Smallest first; ties by their id, so two passes
# agree. The VMS registers one for `vms`: beside the BACKUP recording, which is the one that must survive
# the primary's server. `memo` is a dict that lives as long as one look at the heartbeats (`NearIndex`): what the
# rank reads to answer — the VMS's, which volumes are backups — it reads once there, not once per unit placed (the
# scaling pass). Each of their ids is ranked once per look.
#
# `refuse(ctl, uid, old, new)` — may this row be WRITTEN: raises `Refused`. Called by `create` and `update` with the
# row as it was (None for a create) and as it will be, before anything is stored — for a rule about what a field
# POINTS AT, which the spec's types cannot state and which must hold for every writer of rows, a scenario's request
# turned into a row as much as an operator's edit (the review's sixth pass: a recording's `home` on another camera's
# card; a camera's `source` on a channel another camera already is). The gate asks who may; this says what may be.
ADMIT: dict[str, object] = {}
NEAR_RANK: dict[str, object] = {}
REFUSE: dict[str, object] = {}


def register_admit(spec_name: str, fn) -> None:
    ADMIT[spec_name] = fn


def register_refuse(spec_name: str, fn) -> None:
    REFUSE[spec_name] = fn


def register_near_rank(spec_name: str, fn) -> None:
    NEAR_RANK[spec_name] = fn


# ONE LOOK AT THE FOLLOWED SUBSYSTEM (the scaling pass): `SpecController.near_index`. Its live workers' `running` entries,
# by the value `near` matches — their unit id, or the field `near.of` names — in the order the heartbeats were read:
# `[(their unit id, worker, server)]`. And what ranking them has read (`memo`, `ranks`), for as long as the look lives.
class NearIndex:
    def __init__(self, by: dict[str, list[tuple[str, str, str]]]):
        self.by, self.memo, self.ranks = by, {}, {}


# Sort key: numeric ids before others, numbers by value.
GARBLED_ROW = object()     # what `SpecController._parsed` says of a row that does not parse: there, and unreadable


#
# By `doors.numeric`, never `isdigit` + `int` (the review's ninth pass): `"7²".isdigit()` is true and `int` raises — a
# name the API took, and every list of its subsystem (`units`, `/where`, a drain's order) went unanswered with it.
def _unit_key(u: str):
    n = numeric(u)
    return (0, n) if n is not None else (1, str(u))


# The `rev` a placement row gets when it is written again. One that does not parse counts from nothing: the row is
# being rewritten whole, and a word in `rev` must not stop the write that mends it.
# The sweep's list — `<sub>/sweep {at, digests}` — as `(digests, at)`; one that does not parse is NO list (the sixth
# pass, the follow-up). `put_blob` reads it on every upload, to take its digest off it: a row with half a list in it
# raised there, and no blob of the subsystem could be stored. Nothing is deleted on the word of a list nobody can
# read: the sweep reads it as empty and marks afresh — a new list, a new grace.
def _sweep_list(items) -> tuple[list, float]:
    import json
    try:
        marked = json.loads((items or {}).get("digests", "[]"))
        at = float((items or {}).get("at", 0))
    except PARSE_ERRORS:                              # `[` ten thousand deep too (`RecursionError`, the ninth review's sweep)
        return [], 0.0
    return (marked, at) if isinstance(marked, list) else ([], 0.0)


def _next_rev(it) -> int:
    try:
        return int((it or {}).get("rev", 0)) + 1
    except (ValueError, TypeError):
        return 1


# The only writer of `<name>/*`, from a spec. Holds nothing; two instances are harmless; never on the
# recovery path. The VMS is one spec; live and det are others — same code.
class SpecController(Controller):
    """The only writer of <name>/*, from a spec. Holds nothing; two instances
    are harmless; never on the recovery path. The VMS is one spec; live and
    det are others — same code."""

    # `capacity` is only the fallback for a worker whose heartbeat says nothing (defaults to the spec's).
    # `cluster` is the name the snapshot carries (`$CLUSTER`, else `cluster-a`); one box is a cluster of
    # one.
    def __init__(self, spec: SubsystemSpec, vars_: Variables, objects: ObjectStore, capacity: int | None = None,
                 wall=time.time, cluster: str | None = None):
        super().__init__(spec.sub, vars_, objects, wall)
        self.spec = spec
        self.capacity = capacity if capacity is not None else spec.capacity_fallback   # the FALLBACK for a worker whose heartbeat says nothing
        self.cluster = cluster or os.environ.get("CLUSTER", "cluster-a")               # the name the snapshot carries; one box is a cluster of one
        self.rows_garbled = 0                                                            # rows the last `units()` could not parse (the review's second pass, M7)
        self._garbled_rows: set[str] = set()
        # What `failover_seconds` saw, by this process's clock: per worker the instance, its `ts` and when that last moved;
        # the gaps it saw between two instances; the largest it measured; and how many it could not measure.
        self._hb_moved: dict[str, tuple] = {}
        self._failover_seen: dict[str, float] = {}
        self.failover_worst, self.failovers_unmeasured = 0.0, 0
        self._pass_failing: set[str] = set()             # the steps of `pass_once` whose last run raised: said once each
        self._server_rows_last: dict | None = None       # the servers' labels last read from the console's rows (`server_labels`)
        self._server_rows_unread: set[str] = set()       # …and the servers whose row is there and did not read on that read
        self.last_reach_moves = 0                        # what the last `ensure_reach` moved or unplaced (the pass report)
        # The key that seals `*_secret` fields on the way into the store (`sealing.py`) — the console's process
        # has it (`SECRETS_KEY`); a process without it writes secrets in the clear, and says so once.
        from .sealing import Sealer
        self.sealer = Sealer.from_env()

    # The row as it goes into the store: `*_secret` values sealed, when this process holds the key.
    def _sealed(self, items: dict, uid) -> dict:
        from .sealing import seal_items
        return seal_items(self.sealer, items, self._row_key(uid))

    # `<name>/<rows>/<id>`.
    def _row_key(self, uid) -> str:
        return self.sub.config(self.spec.rows, str(uid))

    # -- what the workers say --------------------------------------------------------
    # The worker's own number from its latest heartbeat (`extra[capacity_from]`, any age), else the
    # fallback. `test_capacity_is_the_workers_word_not_the_controllers`: workers saying 2 and 6 are placed
    # by 2 and 6; an unknown worker gets 50.
    #
    # A NUMBER THAT IS A WORD (the sixth pass, the follow-up). A heartbeat that does not parse is skipped where it
    # is read (`parse_heartbeat`); one that parses and carries a word where a number is read here raised here — and
    # `capacity_of` is asked of every candidate while ANY unit is placed, so one worker's field stopped every
    # placement. Such a field is read as "it has not said" (`_number`): the fallback, no headroom, no failover time.
    def capacity_of(self, worker: str) -> int:
        hb = self._said(worker)
        said = self._number(worker, hb, self.spec.capacity_from, int) if hb else None
        return self.capacity if said is None else said

    # What a worker last said, any age — the four questions above and `place_of` ask it per candidate and per unit placed.
    # Inside a pass it is one dict built once (`_per_pass`; the scaling pass), not a walk of every heartbeat per question.
    def _said(self, worker: str):
        return self._per_pass(self.sub.heartbeats_prefix(), lambda: self.workers_seen(max_age=1e12), "any_age").get(worker)

    # Through `rows.number` (the review's ninth pass, the sibling of `failover_seconds`): its own `(ValueError, TypeError)`
    # let `int(inf)` — `headroom: Infinity`, which JSON reads — raise `OverflowError` out of `headroom()`, and every
    # placement with it; and `inf` passed as a number.
    def _number(self, worker: str, hb, field: str, kind=float):
        """A numeric field of a worker's heartbeat, or None if it is absent or not a finite number (counted once)."""
        from .rows import number
        if field not in hb.extra:
            return None
        return number(f"{self.sub.heartbeat_key(worker)}#{field}", hb.extra[field], kind, None)

    # What this worker's server reaches, as placement reads it: the administrator's row for the server when there is
    # one (`server_labels`, feedback DQ), the worker's own word otherwise (`node_labels_of`).
    def labels_of(self, worker: str) -> set[str]:
        rows = self.server_labels()
        server = self.server_of(worker)
        if rows is not None and server in rows:
            return set(rows[server])
        if server in self._server_rows_unread:
            return set()                               # its row did not read, and never has: it reaches no label known
        return self.node_labels_of(worker)

    # The `labels` string of its heartbeat, split on commas — the node's `LABELS` (`meta.labels` in a Nomad client's
    # `client.hcl`), read by the worker when it starts: the first value of a new box and the fallback of every other.
    def node_labels_of(self, worker: str) -> set[str]:
        hb = self._said(worker)
        return set(l for l in str(hb.extra.get("labels", "")).split(",") if l) if hb else set()

    # -- what a server reaches, from the console (feedback DQ) ----------------------------------------------------
    # A camera's labels say which network segments its address answers on; a server's say which ones the machine is
    # plugged into. The server's half came from the node alone: `LABELS`, filled from `meta.labels` in `client.hcl`,
    # read by a worker when it starts. Changing it was a file on the machine and a restart, for a fact the operator
    # learns in the console, beside the cameras that carry the same labels — and a label decided only the NEXT
    # placement: a camera stayed on a server that no longer reached its VLAN, recorded by nobody, and nothing said so.
    #
    # So a server may have a row, `<sub>/servers/<server> {labels: "a,b"}`, written by the console (`PUT`/`DELETE
    # /servers/<server>/labels`, admin on the whole cluster). Where it exists it IS the server's labels — empty too,
    # which says "this machine reaches nothing"; where it does not, the node's answer. Placement reads the rows once a
    # pass (`_per_pass`), and `ensure_reach` moves what a server no longer reaches.
    #
    # A STORE THAT DOES NOT ANSWER MOVES NOTHING. The rows last read are kept (`_server_rows_last`): a hiccup must not
    # turn every server back to its node's labels for one pass and move the cameras the administrator placed by his.
    # A process that has never read them says None — and `ensure_reach` then moves nothing.
    #
    # …AND A ROW THAT DID NOT READ IS NOT KNOWN, NOT "NO ROW" (the review's tenth pass, major; a run). A row that did not
    # parse kept what was last read of that server, else its NODE's: after a restart of the controller there was no
    # last read, the node's `client.hcl` was the stale `vlan:b` the row had been written to correct, and `ensure_reach`
    # took 12 cameras of 12 off the server in two passes, "srv-a no longer reaches vlan:a". And a listing that left
    # the row out for one pass was "no row": the node's labels again, 5 cameras of 5 moved, and they did not come back.
    # Now each server's row is read BY ITS KEY — the listed ones, the servers this subsystem's workers run on, and the
    # ones read before — so a listing that misses a row costs nothing; and a server whose row is there and did not read
    # (garbled, no `labels`, a read that failed, a listed key the read does not find) is UNREAD this pass
    # (`_server_rows_unread`): it keeps the labels last read of it, and with none it reaches no label (`labels_of`) —
    # nothing that needs one is placed there — and `ensure_reach` moves nothing off it. One such row is that server's
    # alone: the others are read.
    def server_labels(self) -> dict[str, frozenset] | None:
        """`{server: labels}` from the console's rows — None while this process has never read them."""
        prefix = self.sub.servers_prefix()

        def read():
            last = self._server_rows_last or {}
            try:
                listed = {k[len(prefix):] for k in self.vars.list(prefix)}
            except Exception as e:                     # noqa: BLE001 — a store that does not answer: the rows last read
                self._failed("server_labels", f"the servers' labels could not be read ({e}); the last read are kept")
                return self._server_rows_last
            rows, unread = {}, set()
            for server in sorted(listed | self._worker_servers() | set(last)):
                key = prefix + server
                try:
                    it, _ = self.vars.get(key)
                except Exception as e:                 # noqa: BLE001 — that server's row, not every server's
                    SERVER_LABELS.garbled(key, f"it could not be read: {e}")
                    it = ()
                if it is None and server not in listed:
                    continue                           # no row: the node's labels answer
                if it is None:
                    SERVER_LABELS.garbled(key, "the listing names it and a read finds nothing")
                # a row with no `labels` is garbled, not "reaches nothing" — that is `labels: ""`
                got = SERVER_LABELS.read(key, lambda: parse_labels(it["labels"])) if isinstance(it, dict) else None
                if got is not None:
                    rows[server] = got
                    continue
                unread.add(server)
                if server in last:
                    rows[server] = last[server]
            self._works("server_labels")
            self._server_rows_last, self._server_rows_unread = rows, unread
            return rows
        return self._per_pass(prefix, read, "server_labels", rows=True)

    # The servers this subsystem's workers say they run on, whatever their age — each one's row is read by its key.
    def _worker_servers(self) -> set[str]:
        seen = self._per_pass(self.sub.heartbeats_prefix(), lambda: self.workers_seen(max_age=1e12), "any_age")
        return {s for hb in seen.values() if isinstance(s := hb.extra.get("server"), str) and SERVER_WORD.fullmatch(s)}

    # Whether a server's row is there and did not read on the last read (`server_labels`): what it reaches is not known.
    def labels_unread(self, server: str) -> bool:
        self.server_labels()
        return server in self._server_rows_unread

    # Where a server's labels come from now: `console` (its row) or `node` (its workers' heartbeats).
    def labels_source(self, server: str) -> str:
        rows = self.server_labels()
        return "console" if rows is not None and server in rows else "node"

    # The servers anybody has announced: this subsystem's workers (any age), the resources, the rows there are. A label
    # row is written only for one of these (the review's tenth pass, minor: a typo was 200 and a row nobody reads).
    def servers_known(self) -> set[str]:
        from .resource import resources_seen
        out = set(self._worker_servers()) | set(self.server_labels() or {}) | set(self._server_rows_unread)
        try:
            out |= {s for s in resources_seen(self.objects) if isinstance(s, str)}
        except Exception:                              # noqa: BLE001 — the resources not listed: the workers' word
            pass
        return out

    # The console's two writes. The row is written whole — a set of labels, not an edit of one — and the controller
    # reads it on its next pass. Refused: a server that is no name, a label that is not one (`LABEL_WORD`).
    #
    # …and only strings (the review's tenth pass, minor: `[null]`, `[true]`, `[1]` were the labels `None`, `True`, `1`),
    # and only for a server somebody has announced (`servers_known`): a typo wrote a row no server reads, and said 200.
    def set_server_labels(self, server: str, labels) -> list[str]:
        server = server_name(server)
        if not isinstance(labels, (list, tuple)) or not all(isinstance(l, str) for l in labels):
            raise Refused('the labels are {"labels": ["vlan:cctv-a", …]}, each a string; [] for none')
        if server not in self.servers_known():
            raise Refused(f"no server {server} is known here: no worker and no resource of it has reported, and it has "
                          f"no row — check the name")
        out = sorted({str(l).strip() for l in labels})
        bad = [l for l in out if not LABEL_WORD.fullmatch(l)]
        if bad:
            raise Refused(f"a label is letters, digits and _ . : - (up to 64), not {bad[0]!r}")
        self.vars.put(self.sub.server_key(server), {"labels": ",".join(out)})
        return out

    def clear_server_labels(self, server: str) -> bool:
        """The row goes; the node's labels answer again. False when there was none."""
        key = self.sub.server_key(server_name(server))
        if self.vars.get(key)[0] is None:
            return False
        self.vars.delete(key)
        return True

    # What would move if `server` reached `labels` (None: its node's) — asked by the page before it writes, with the
    # same constraint the pass asks: the units placed on that server's workers that would no longer pass it.
    def would_move(self, server: str, labels) -> list:
        rule = CONSTRAINTS[self.spec.constraint]
        out = []
        with one_pass(self):
            for row in self.units():
                pl = self.placement(row["id"])
                if pl is None or self.server_of(pl.worker) != server or self.retired(row):
                    continue
                has = self.node_labels_of(pl.worker) if labels is None else set(labels)
                if not rule(row, has):
                    out.append(row["id"])
        return out

    # The heartbeat's `server`, `"?"` if unknown. Goes into placement reasons and the snapshot.
    def server_of(self, worker: str) -> str:
        hb = self._said(worker)
        return hb.extra.get("server", "?") if hb else "?"

    # The place this worker occupies, in the units the spec counts in: its server, or its volume when the
    # subsystem says `place_by: volume`. `"?"` when the worker has not said — and an unknown place never
    # matches a home, so a unit with a home waits rather than landing somewhere at random.
    def place_of(self, worker: str) -> str:
        if self.spec.place_by == "server":
            return self.server_of(worker)
        hb = self._said(worker)
        if hb is None:
            return "?"
        # Three cases, and the difference between the last two is the point.
        #
        # The field NAMES a place — the ordinary one: that is where this worker is.
        #
        # The field is ABSENT: one volume named after the server. That is the truth for every box with one
        # disk, it is what a worker written before the field existed means, and where it is NOT the truth
        # it errs the safe way — three recorders on three disks that nobody told apart read as three on
        # one place, and `distinct` idles two of them rather than letting two think they own the same disk.
        #
        # The field is PRESENT AND EMPTY: the worker says it is on NO place — a spare, running and holding
        # nothing, waiting for a place to become free. Reading that as its server would be the worst
        # answer available: the spare would share a place with the recorder that actually owns the disk,
        # and `distinct` would idle one of the two at random.
        if self.spec.place_by in hb.extra:
            return str(hb.extra[self.spec.place_by])
        return str(hb.extra.get("server", "?"))

    # Sum of `extra[headroom_from]` over workers seen in the last 45 s — what the autoscaler reads via
    # `/metrics`. Stale until the workers heartbeat again after a placement.
    def headroom(self) -> int:
        return sum(self._number(w, hb, self.spec.headroom_from, int) or 0 for w, hb in self.workers_seen().items())

    # -- units ------------------------------------------------------------------------
    # For numeric ids, bump `<name>/next_id {n}` by CAS and return it; otherwise `Refused` (the unit is
    # named by its field).
    #
    # A COUNTER THAT DOES NOT PARSE (the review's seventh pass, a minor): `n: "seven"` raised here, and not one unit of
    # the subsystem could be created until somebody mended the row by hand. It is counted once (`NEXT_IDS`, through the
    # one reader of rows) and the next number is one past the LARGEST id under `<name>/<rows>/` — the deleted rows
    # included, which stay as marks, so a number once given is not given again — and the CAS writes the row whole.
    def _next_id(self):
        if self.spec.numeric:
            key = self.sub.config("next_id")

            def bump(it):
                n = NEXT_IDS.read(key, lambda: int(finite(it.get("n", 0) or 0)))
                return {"n": (self._largest_id() if n is None else n) + 1}
            new = self.write(key, bump)
            return int(new["n"])
        raise Refused(f"a {self.spec.name} unit is named by its {self.spec.id}")

    def _largest_id(self) -> int:
        prefix = self.sub.config(self.spec.rows, "")
        ids = [k[len(prefix):] for k in self.vars.list(prefix)]
        return max([n for i in ids if (n := numeric(i)) is not None] + [0])     # `doors.numeric`: not `isdigit` + `int`

    # Keep every derived row in step: on create/update write `{item: to_item(row[field])}` only if it
    # differs; on delete write `on_delete` if set and the row exists.
    def _derived(self, row: dict | None, uid, deleted: bool = False) -> None:
        for d in self.spec.derived:
            path = self.sub.config(*d.row.replace("{id}", str(uid)).split("/"))
            if deleted:
                if d.on_delete is not None:
                    # Written whether or not the row was there. "If the row exists" was the rule, and it stopped
                    # being right the day a field could be left to INHERIT (М12 Lesson 12): such a unit has no
                    # derived row at all, so deleting it wrote nothing, and what the row governs lived on by the
                    # subsystem's default — a deleted camera's events, for a year (found with feedback BO).
                    self.write(path, lambda it, v=d.on_delete: {k: str(x) for k, x in v.items()})
                continue
            # A field left to inherit gives no item: the derived row then says nothing, and its reader goes on
            # down its own chain — the resource's retention falls back to the subsystem's, then to a year.
            want = {k: self.spec.fields[f].to_item(row[f]) for k, f in d.items.items() if row.get(f) is not None}
            self.write(path, lambda it, want=want: None if it == want else want)

    # `refuse`, choose the id (numeric: `_next_id`; else the field's value, which must be present and not
    # already exist), build the row with `new_row`, write it with `cas=0` (create-only), write derived rows,
    # return the row. Placement is not done here — the controller's pass does it; the console reports
    # `worker: None`.
    #
    # `uid` and `reserve` are the console's (`IdempotencyKeys`): the id is RESERVED in the request's claim before the
    # row is written (`reserve(uid)`), so a retry that takes over a stale claim creates under the same id — or finds
    # the unit created and answers with it. "The reply was lost" and "the write was never made" look the same from
    # outside; the reserved id tells them apart (the review's second pass; the product's `CreateAs`, feedback CS).
    def create(self, fields: dict, uid=None, reserve=None) -> dict:
        self.spec.refuse(fields)
        self._refuse_labels(fields, ())
        if uid is not None:
            old = self.unit(uid)
            if old is not None:
                return old                                              # created by the attempt whose reply was lost: the row is the answer
        if self.spec.numeric:
            uid = self._next_id() if uid is None else self.spec.parse_id(uid)
        else:
            uid = str(fields.get(self.spec.id) or "")
            if not uid:
                raise Refused(f"a {self.spec.name} unit needs a {self.spec.id}")
            # A named unit's id comes VERBATIM from the operator's body, and from here it becomes three
            # things: the key `<sub>/<rows>/<id>`, the prefix an ACL is matched against, and a directory on
            # a resource's disk (`events.unit_dir`). So it is a name, not a path: no separators, and not a
            # relative one. `variables.safe_path` refuses the same shapes one layer down — this one is a
            # 400 to the person who typed it rather than a 500 from the store.
            if "/" in uid or uid in (".", ".."):
                raise Refused(f"a {self.spec.name} {self.spec.id} is a name, not a path: {uid!r}")
            # …and a name that goes into other text whole (the review's eighth pass, part 4, and its question about `|`,
            # `"` and the newline): a label value on `/metrics` (escaped there too, for the names already stored —
            # `console.label`), a `|`-joined field of a heartbeat (`closed`, `hits`), a log line. Refused here, the rule
            # the domain keeps for a user's name (`domain/grants.py`, `name_refused`): no `"`, no `|`, no control
            # character or line or paragraph separator (Unicode Cc, Zl, Zp).
            # …and a unit's name is in lists and sorted as a number (the ninth pass, sibling B of the product team): no
            # `,` — an assignment is its units joined by one — and no digit but ASCII 0–9 (`doors.unnamable`, `unit`).
            bad = unnamable(uid, unit=True)
            if bad:
                raise Refused(f"a {self.spec.name} {self.spec.id} may not hold {', '.join(repr(c) for c in bad)}: {uid!r}")
        if reserve is not None:
            reserve(uid)                                                # into the claim, before the row exists
        if self.spec.name in REFUSE:                                   # the subsystem's own rule about what the row points at
            REFUSE[self.spec.name](self, uid, None, self.spec.new_row(uid, fields))
        if not self.spec.numeric:
            old, idx = self.vars.get(self._row_key(uid))
            if old and old.get("deleted") != "true":
                raise Refused(f"{self.spec.name} unit {uid} exists")
            # A NAME STAYS ITS CAMERA'S (the review's fifth pass, major). A unit's name is also the name of what it left
            # behind — a recording's tree in its volumes, a detector's events — and readers find those by the name.
            # Deleted as camera 1's «1-cloud» and created again as camera 2's, the recording handed camera 1's
            # footage to whoever may view camera 2 (`GET /export/2` played it). The tombstone keeps `cam`: the name
            # comes back for the same camera, and for another it is refused — whatever was written under it is still
            # there, and nothing here can know when the last of it is gone, so "reuse once the archive is empty" is
            # not a rule this controller could keep.
            if old and "cam" in old and "cam" in fields and str(self.spec.fields["cam"].parse(fields["cam"])) != str(old["cam"]):
                raise Refused(f"the name {uid} was cam {old['cam']}'s, and what was written under it still is: create "
                              f"cam {fields['cam']}'s under another name")
            if old:                                                 # a named unit deleted earlier comes back under its name:
                r = self.spec.new_row(uid, fields)                  # a fresh row, one revision on from the old one, by CAS on it
                r["revision"] = int(old.get("revision", 0)) + 1
                self.vars.put(self._row_key(uid), self._sealed(self.spec.items(r), uid), cas=idx)
                self._derived(r, uid)
                return r
        r = self.spec.new_row(uid, fields)
        self.vars.put(self._row_key(uid), self._sealed(self.spec.items(r), uid), cas=0)
        self._derived(r, uid)
        return r

    # The labels a unit is placed by, in the one alphabet (`LABEL_WORD`; the review's tenth pass): a camera with `склад`
    # was placed by the node's word and taken off its server as soon as an administrator gave that server a row, which
    # cannot hold the word.
    def _refuse_labels(self, fields: dict, old) -> None:
        if self.spec.constraint != "labels-subset" or "labels" not in fields or "labels" not in self.spec.fields:
            return
        why = label_refusal(self.spec.fields["labels"].parse(fields["labels"]), old)
        if why:
            raise Refused(why)

    # `refuse`, then read-modify-write the row: `KeyError` if missing or marked deleted; parse each field
    # into the row; bump `revision` (the trigger from М9 Lesson 5, now in the controller — the worker
    # restarts what it runs on a new revision); write. Derived rows are refreshed only if one of their
    # source fields changed.
    #
    # THE UNIT A ROW IS ABOUT IS FIXED AT ITS CREATION (the review's fourth pass, major). A recording, a detector, a
    # stream is ABOUT a camera — `cam`, the field the console's gate reads to know whose grant to check — and the gate
    # checks the camera the row names NOW. `PUT /rec/recordings/1 {"cam": "2"}` with `admin` on camera 1 passed on
    # camera 1 and moved the recording to camera 2: the recorder wrote camera 2 into a tree camera 1's viewers read; a
    # detector took its alarms and scenarios along. Rights on both cameras would make the move legal for somebody who
    # holds both, and it would still be one camera's history going on as another's; so `cam` does not change. The
    # same value is no change — the page sends the whole form.
    def update(self, uid, fields: dict) -> dict:
        self.spec.refuse(fields)
        def mutate(it):
            if not it or it.get("deleted") == "true":
                raise KeyError(uid)
            r = self.spec.row(it)
            if "cam" in fields and "cam" in r and str(self.spec.fields["cam"].parse(fields["cam"])) != str(r["cam"]):
                raise Refused(f"`cam` is fixed when the unit is created: {uid} is about {r['cam']} — create one for "
                              f"{fields['cam']} under another name (this one stays {r['cam']}'s, deleted or not)")
            was = dict(r)
            for k, v in fields.items():
                r[k] = self.spec.fields[k].parse(v)
            if "labels" in fields and self.spec.constraint == "labels-subset":
                why = label_refusal(r.get("labels"), was.get("labels") or ())
                if why:
                    raise Refused(why)
            if self.spec.name in REFUSE:             # the subsystem's own rule about what the row points at, old and new
                REFUSE[self.spec.name](self, uid, was, r)
            r["revision"] += 1                       # the trigger from М9 Lesson 5, in the controller
            return self._sealed(self.spec.items(r), uid)
        r = self.spec.row(self.write(self._row_key(uid), mutate))
        if any(f in fields for d in self.spec.derived for f in d.items.values()):
            self._derived(r, uid)
        return r

    # The operator's half: the row is marked `deleted: "true"` (not removed) and derived rows get their
    # `on_delete`. Its placement is the controller's half, taken back on the next pass by `unplace_deleted`
    # — a console's token cannot touch an assignment, and does not need to.
    def delete(self, uid) -> None:
        """The operator's half: the row is marked. Its placement is the controller's
        half, taken back on the next pass (`unplace_deleted`) — a console's token
        cannot touch an assignment, and does not need to."""
        self.write(self._row_key(uid), lambda it: {**it, "deleted": "true"} if it else None)
        self._derived(None, uid, deleted=True)

    # The controller's half of a delete: for every `placement/<id>` row with a worker whose unit no longer
    # exists, remove the unit from that worker's assignment and rewrite the placement as `{worker: "",
    # reason: "deleted", at, rev+1}`. Runs first in `ensure_placed` and `redistribute`. The console test:
    # after `DELETE /cameras/1` the placement still says `w-1` until `unplace_deleted()` returns `[1]`.
    def unplace_deleted(self) -> list:
        """The controller's half of a delete: every placement whose unit is gone
        loses its assignment and its row says so. Runs first in every pass."""
        gone = []
        for p in self.vars.list(self.sub.config("placement") + "/"):
            uid = self._placed_id(p)
            it, _ = self.vars.get(p)
            if uid is None or not it or not it.get("worker") or self._parsed(uid) is not None:
                continue                                  # a row that does not parse EXISTS: it is not unplaced as deleted
            self.assign_remove(it["worker"], str(uid))
            self.write(p, lambda it: {"worker": "", "reason": "deleted", "at": self.wall(), "rev": _next_rev(it)})
            gone.append(uid)
        return gone

    # The unit a row under `<sub>/placement/` is about, or None when its name is no unit's id — a stray row there
    # raised out of the two passes that walk the placements, and so out of `ensure_placed` and `redistribute`, for
    # every unit (the sixth pass, the follow-up). Skipped, and said once.
    def _placed_id(self, path: str):
        try:
            return self.spec.parse_id(path.rsplit("/", 1)[1])
        except (ValueError, TypeError):
            if path not in self._garbled_rows:
                self._garbled_rows.add(path)
                log.warning("%s: %s is named after no unit; skipped", self.sub.name, path)
            return None

    # Whether this row says the work is over — `retire_when` in the spec, and nothing at all for the
    # subsystems that never end.
    def retired(self, row: dict | None) -> bool:
        if not self.spec.retire_field or row is None:
            return False
        return str(row.get(self.spec.retire_field, "")) in self.spec.retire_values

    # The other half of `retire_when`: a unit that FINISHED while placed gives its assignment back, so the
    # worker drops it and the budget it was holding is free again. Without this the predicate below only
    # stops the next placement, and a cluster's whole capacity ends up held by work that is over.
    #
    # The reason says which value did it, because "done" and "failed" are a very different message to the
    # person reading `/where/<id>`.
    def unplace_retired(self) -> list:
        """Every placement whose unit's row says the work is over loses its assignment."""
        done = []
        for p in self.vars.list(self.sub.config("placement") + "/"):
            uid = self._placed_id(p)
            it, _ = self.vars.get(p)
            row = self._parsed(uid) if uid is not None else GARBLED_ROW
            if not it or not it.get("worker") or row is GARBLED_ROW or not self.retired(row):
                continue                                  # whether a row that does not parse is over, nobody can say
            state = str(row.get(self.spec.retire_field, ""))
            self.assign_remove(it["worker"], str(uid))
            self.write(p, lambda i: {"worker": "", "reason": state, "at": self.wall(), "rev": _next_rev(i)})
            done.append(uid)
        return done

    # The row, or `None` if absent or deleted.
    def unit(self, uid) -> dict | None:
        it, _ = self.vars.get(self._row_key(uid))
        return self.spec.row(it) if it and it.get("deleted") != "true" else None

    # The same for the controller's loops over units ALREADY PLACED (the review's third pass): a row that does not
    # parse is `GARBLED_ROW` — logged once, counted by `units()` in `rows_garbled` like every other — instead of an
    # exception out of `unplace_deleted`, which ran first in `ensure_placed` and `redistribute`: one hand-edited
    # field on a placed camera, and no new camera was placed and no unit of a silent server moved, every pass.
    def _parsed(self, uid):
        try:
            return self.unit(uid)
        except PARSE_ERRORS as e:                     # a `json` field ten thousand deep too (the ninth review's sweep)
            p = self._row_key(uid)
            if p not in self._garbled_rows:
                self._garbled_rows.add(p)
                log.warning("%s: row %s does not parse (%s); skipped", self.sub.name, p, e)
            return GARBLED_ROW

    # Every live row under `<name>/<rows>/`, sorted by `_unit_key`. A row that does not parse — a field edited by
    # hand, a build that wrote another layout — is ONE unit nobody serves, not the end of every caller's pass
    # (the review's second pass, M7): skipped, counted in `rows_garbled` (the pass report; `<sub>_rows_garbled`),
    # logged once per row until it parses again.
    #
    # Whatever a parse raises (`PARSE_ERRORS`: a row nested past what JSON reads, a number past a float, a row that is
    # not a map), and the read of a file store's row that is not JSON at all (the review's ninth pass, beside `7²`). A
    # row whose NAME a unit could not be created under today (`doors.unnamable`, `unit`: a `,`, a digit not ASCII) is
    # served as it stands, and counted and named once (`UNIT_NAMES`): somebody is to create it again under another name.
    def units(self) -> list[dict]:
        out, garbled = [], 0
        for p in self.vars.list(self.sub.config(self.spec.rows) + "/"):
            try:
                it, _ = self.vars.get(p)
                if not it or it.get("deleted") == "true":
                    continue
                out.append(self.spec.row(it))
            except PARSE_ERRORS as e:
                garbled += 1
                if p not in self._garbled_rows:
                    self._garbled_rows.add(p)
                    log.warning("%s: row %s does not parse (%s); skipped", self.sub.name, p, e)
                continue
            self._garbled_rows.discard(p)
            if (bad := unnamable(out[-1]["id"], unit=True)):
                UNIT_NAMES.garbled(p, f"its name holds {', '.join(repr(c) for c in bad)}")
            else:
                UNIT_NAMES.parsed(p)
        self.rows_garbled = garbled
        return sorted(out, key=lambda r: _unit_key(str(r["id"])))

    # -- placement ---------------------------------------------------------------------
    # The stored decision, `None` if no row or the worker is empty (unplaced).
    #
    # WHAT THE ROW DECIDES IS `worker` (the sixth pass, the follow-up); `reason`, `at` and `rev` are for a person.
    # All four were parsed bare, and the row of ONE unit is read while others are placed (`together`, `apart`), by
    # `unplaced()`, by `ensure_home`: an `at` with a word in it stopped them all. The decision is read as it stands;
    # what does not parse beside it is 0, and the row is said once.
    def placement(self, uid) -> Placement | None:
        key = self.sub.config("placement", str(uid))
        it, _ = self.vars.get(key)
        if not it or not it.get("worker"):
            return None
        return self._placement(uid, it)

    def _placement(self, uid, it: dict) -> Placement:
        key = self.sub.config("placement", str(uid))
        try:
            at, rev = float(it["at"]), int(it["rev"])
            self._garbled_rows.discard(key)
        except (ValueError, KeyError, TypeError):
            at, rev = 0.0, 0
            if key not in self._garbled_rows:
                self._garbled_rows.add(key)
                log.warning("%s: placement row %s does not parse beyond its worker (%r); read as placed on %s",
                            self.sub.name, key, it, it["worker"])
        return Placement(self.spec.parse_id(uid), it["worker"], str(it.get("reason", "")), at, rev)

    # Assigned units on that worker — from the assignment row, not from the heartbeat.
    def load(self, worker: str) -> int:
        return len(self.assignment(worker).units)

    # Workers passing the spec's constraint against their labels.
    def eligible(self, row: dict, workers: list[str]) -> list[str]:
        rule = CONSTRAINTS[self.spec.constraint]
        out = [w for w in workers if rule(row, self.labels_of(w))]
        out = [w for w in out if self.server_of(w) not in self.servers_taken(row)]
        admit = ADMIT.get(self.spec.name)
        if admit is not None:
            out = [w for w in out if admit(self, row, w)]
        with_group = self.worker_with_group(row, out)
        return [w for w in out if w == with_group] if with_group else out

    # The worker already carrying a unit of this row's group, if there is one and it is still in the pool.
    #
    # "Still in the pool" is the whole of the care needed here. A placement on a worker that is gone,
    # draining or idle by policy must NOT pin the group to it: that worker's units are on their way out,
    # and honouring its placement would make every unit of the group unplaceable at exactly the moment
    # the group has to move. Read from the live pool and the group re-forms wherever its first unit lands.
    #
    # Ties go to the smallest worker name so two passes agree — after a partial move two peers can sit on
    # two workers, and picking "whichever came first" would walk the group between them.
    def worker_with_group(self, row: dict, pool: list[str]) -> str | None:
        if not self.spec.group_by:
            return None
        value = self.group_value(row)
        if not value:
            return None
        mine, found = str(row["id"]), []
        for other in self._rows_by("group", self.group_value).get(value, ()):
            if str(other["id"]) == mine:
                continue
            pl = self.placement(other["id"])
            if pl is not None and pl.worker in pool:
                found.append(pl.worker)
        return sorted(found)[0] if found else None

    # What `group_by` names, for this row. A field by default; a subsystem that knows better overrides —
    # `VmsController` returns the device out of the source URL, because the row has no device field and
    # a generic loader has no business parsing a scheme it has never heard of.
    def group_value(self, row: dict) -> str:
        return str(row.get(self.spec.group_by, "") or "")

    # Every live row by one value of it — the group, the spread field — built once a pass (`_per_pass`). Asked for every
    # unit waiting to be placed, it was every row read and parsed again for each: 500 cameras waiting of 600 cost a pass
    # 670 000 reads and ten seconds (the scaling pass; `tests/test_read_budget.py`). Rows in `units()` order.
    def _rows_by(self, name: str, value_of) -> dict[str, list[dict]]:
        def read():
            out: dict[str, list[dict]] = {}
            for r in self.units():
                out.setdefault(value_of(r), []).append(r)
            return out
        return self._per_pass(self.sub.config(self.spec.rows) + "/", read, name, rows=True)

    # The servers already carrying a unit that shares this row's `spread_by` value — where this one may
    # therefore NOT go. Empty when the subsystem does not ask to spread, which is every subsystem today.
    #
    # Read the whole rule in one sentence: two recordings of one camera exist to survive one server, so
    # putting them on one server is not a compromise, it is the failure the operator was buying insurance
    # against. `near` pulls a recorder towards the camera's holder and would otherwise pull BOTH copies to
    # the same place — the preference loses to the filter, and the reason says which.
    def servers_taken(self, row: dict) -> set[str]:
        field = self.spec.spread_by
        if not field:
            return set()
        value = row.get(field)
        if value in (None, ""):
            return set()
        mine, taken = str(row["id"]), set()
        for other in self._rows_by(f"spread:{field}", lambda r: str(r.get(field))).get(str(value), ()):
            if str(other["id"]) == mine:
                continue
            pl = self.placement(other["id"])
            if pl is not None:
                taken.add(self.server_of(pl.worker))
        return taken

    # -- the administrator's knobs: one row, `<name>/policy`, written by the console ---------------
    # `servers`: `shared` (default) — every worker is a place to put units, two on one server included (a
    # box IS several workers on one server); a dead server's slot is Nomad's to reschedule onto a neighbour
    # (Lesson 4's power pull), and the controller waits for it. `distinct` — one worker per server carries
    # units; a second worker Nomad put on the same server idles by policy, and a server whose worker and
    # resource both fall silent is gone (`gone_servers`) — its units move. The jobspec says `spread`, so
    # both are possible without touching Nomad; the administrator chooses on the console.
    POLICY_CHOICES = {"servers": ("distinct", "shared")}

    @property
    def POLICY_DEFAULTS(self) -> dict:                                   # the spec's `placement.servers` is the default; the row overrides
        return {"servers": self.spec.servers}

    def policy(self) -> dict:
        items, _ = self.vars.get(self.sub.config("policy"))
        out = dict(self.POLICY_DEFAULTS)
        for k, v in (items or {}).items():
            if k in self.POLICY_CHOICES and v in self.POLICY_CHOICES[k]:
                out[k] = v
        return out

    def set_policy(self, changes: dict) -> dict:
        for k, v in changes.items():
            if k not in self.POLICY_CHOICES or v not in self.POLICY_CHOICES[k]:
                raise Refused(f"policy {k} must be one of {', '.join(self.POLICY_CHOICES.get(k, ()))}")
        self.write(self.sub.config("policy"), lambda it: {**(it or {}), **{k: str(v) for k, v in changes.items()}})
        return self.policy()

    # Under `servers: distinct`, the workers that a server's OTHER workers must yield to: for each server,
    # the worker with units (the most, ties to the first name), else the first by name; the rest idle by
    # policy. Under `shared`, nobody.
    def idle_by_policy(self, workers) -> list[str]:
        if self.policy()["servers"] != "distinct":
            return []
        by_place: dict[str, list[str]] = {}
        for w in sorted(workers, key=slot_number):
            by_place.setdefault(self.place_of(w), []).append(w)
        idle = []
        for server, ws in by_place.items():
            if server == "?" or len(ws) < 2:
                continue
            keep = max(ws, key=lambda w: (self.load(w), -slot_number(w)))
            idle += [w for w in ws if w != keep]
        return idle

    # -- what the worker's server must have: a resource, when the spec says so ---------------------
    # The state of the resource on a server, from `platform/resources/<server>/heartbeat`: `"live"` (younger
    # than `lost_after`), `"silent"` (older), `"unknown"` (never heartbeaten — a box before its resource
    # process starts, a bench). Nomad's `meta.archive` constraint puts a worker where disks are declared;
    # this is the live fact: whether the resource there still answers.
    def resource_state(self, server: str, lost_after: float = 45.0) -> str:
        from .resource import RESOURCES, resources_seen            # the platform's own reader of the resource heartbeats
        hb = self._per_pass(RESOURCES + "/", lambda: resources_seen(self.objects)).get(server)   # asked per worker, read once a pass
        if hb is None:
            return "unknown"
        return "live" if is_live("platform", float(hb["ts"]), self.wall(), lost_after) else "silent"

    # Workers whose server's resource is silent, when the spec requires one: not placed on, and (in
    # `redistribute`) moved off. A worker on a server whose resource was never seen passes — "silent" is
    # a fact, "unknown" is not one.
    # Live workers that say they hold no place, in a subsystem that places by one — spares. Not a fault in
    # itself; it is one when such a worker still has units assigned (`redistribute`).
    def placeless(self, workers) -> list[str]:
        if self.spec.place_by == "server":
            return []
        return [w for w in workers if self.place_of(w) == ""]

    def without_resource(self, workers) -> list[str]:
        if self.spec.requires != "resource":
            return []
        return [w for w in workers if self.resource_state(self.server_of(w)) == "silent"]

    # A server that is gone, not a process that crashed: the slot has lapsed and stayed lapsed for another
    # `lost_after` — Nomad's chance to reschedule it onto a spare server, in which case the replacement
    # claims the name and inherits the assignment (Lesson 4) — AND the resource on the slot's last known
    # server is silent. One silence is a crash and is left alone; two independent silences from the same
    # server are a fact about the server. Only when the spec requires a resource.
    def gone_servers(self, lost_after: float = 45.0) -> dict[str, str]:
        """Lapsed slots whose server's resource is silent too: {slot: server}."""
        if self.spec.requires != "resource" or self.policy()["servers"] != "distinct":
            return {}                                                    # shared: a dead server's slot is Nomad's to reschedule onto a neighbour
        now = self.wall(); out = {}
        for name, slot in self.slots().items():
            if slot.lapsed(now) and now > slot.until + lost_after and self.assignment(name).units:
                server = self.server_of(name)
                if server != "?" and self.resource_state(server, lost_after) == "silent":
                    out[name] = server
        return out

    # The given list, or the workers seen heartbeating in the last 45 s; minus those whose resource is
    # silent when the spec requires one; sorted.
    # Who may receive units now. Three exclusions, and the third is the one a catalogue teaches: a worker
    # that RELEASED its slot said it is leaving, and a service catalogue's answer to that is deregistration —
    # gone from the list at once, not in `lost_after` seconds when its heartbeat finally ages out. We have
    # the fact (`Slot.released`) and used it only to move units OFF such a worker (`redistribute`); without
    # this line the very next `place()` could put a new one back ON it, and the pass after that would move
    # it off again. A departure that still collects work is churn at every scale-in and every update.
    # Workers on the server being drained: not placed on, and (in `redistribute`) moved off. The third
    # kind of "not here" beside a released slot and a silent resource — and the only one the operator says
    # BEFORE it is true, which is the whole point of an upgrade.
    def on_draining(self, workers) -> list[str]:
        server = self.draining()
        return [w for w in workers if server and self.server_of(w) == server] if server else []

    def _pool(self, workers):
        pool = sorted(workers if workers is not None else self.workers_seen())
        leaving = {n for n, s in self.slots().items() if s.released}
        gone = set(self.without_resource(pool)) | set(self.idle_by_policy(pool)) | leaving | set(self.on_draining(pool))
        return [w for w in pool if w not in gone]

    # The dry run. Which units nothing else could serve if this server went away — asked BEFORE it does,
    # with the machinery that will answer for real afterwards (`eligible` over the pool minus that server).
    # Fifty cameras leaving a machine have to land somewhere, and "somewhere" is a fact about headroom and
    # labels, not a hope. An upgrade script reads this and stops; the alternative is reading `/unplaceable`
    # after the reboot.
    def would_strand(self, server: str, workers: list[str] | None = None) -> list[str]:
        """Unit ids that nothing left could serve if `server` stopped now."""
        with one_pass(self):
            return self._would_strand(server, workers)

    def _would_strand(self, server: str, workers: list[str] | None) -> list[str]:
        pool = [w for w in self._pool(workers) if self.server_of(w) != server]
        out = []
        for row in self.units():
            uid = row["id"]
            pl = self.placement(uid)
            if pl is not None and self.server_of(pl.worker) != server:
                continue                                   # it is not on that server: not its business
            if not self.eligible(row, pool):
                out.append(str(uid))
        return out

    # `near: <sub>`: the worker of that subsystem whose heartbeat status lists this unit's id in phase
    # `running` — `(worker, server)` — or None. The recorder says `near: vms`: the camera's holder.
    #
    # `near.of` names the field of THEIR status entry the value is matched against, instead of their unit
    # id: how a camera finds the recorder running a recording OF it without knowing what the operator named
    # that recording. Ties (two recordings of one camera) go to the smallest of their ids, so two passes
    # over the same heartbeats reach the same server.
    #
    # FROM ONE LOOK, HANDED IN (the scaling pass). Each call read every heartbeat of the followed subsystem and walked
    # every entry in them — and `ensure_home` asks for every unit, `_pick` for every unit it places: a thousand cameras
    # beside the recordings of twenty recorders read the store 25 500 times, and walked every recorder's status a
    # thousand times. A caller asking for many units takes one look first — `near_index`, from the heartbeats it has
    # read already, if it has — and hands it in as `near`; a unit asked about alone takes a look of its own.
    def near_index(self, beats: dict | None = None) -> NearIndex:
        """The followed subsystem's live `running` entries, by the value `near` matches. `beats`: its heartbeats as
        `console.heartbeats` returns them, when the caller has read them; else they are read here, once."""
        if self.spec.near == "none":
            return NearIndex({})
        if beats is None:
            # Inside a pass the look is the pass's (`_per_pass`): its heartbeats read once, the index built once — and a
            # step that did not hand one in (`_pick` from `place`, `home_for`) gets the same one.
            from .console import heartbeats                        # the read model's scan, without the age filter
            prefix = f"{self.spec.near}/heartbeats/"
            beats = self._per_pass(prefix, lambda: heartbeats(self.objects, self.spec.near + "/"))
            return self._per_pass(prefix, lambda: self._near_index(beats), "near_index")
        return self._near_index(beats)

    def _near_index(self, beats: dict) -> NearIndex:
        by: dict[str, list[tuple[str, str, str]]] = {}
        field, now = self.spec.near_of, self.wall()
        for w, hb in beats.items():
            if not is_live(self.spec.near, hb.ts, now, 45.0):
                continue
            for st in hb.status:
                if st.get("phase") == "running":
                    key = st.get(field) if field else st.get("id")
                    by.setdefault(str(key), []).append((str(st.get("id")), w, hb.extra.get("server", "?")))
        return NearIndex(by)

    def holder_near(self, uid, near: NearIndex | None = None) -> tuple[str, str] | None:
        if self.spec.near == "none":
            return None
        want = self.near_id(uid)                                   # `by`: which value of mine to look for
        if not want:
            return None
        near = self.near_index() if near is None else near
        found = near.by.get(want)                                  # (their unit id, worker, server)
        if not found:
            return None
        if not self.spec.near_of or len(found) == 1:
            return found[0][1], found[0][2]                        # their unit is mine, or one of theirs: nothing to rank
        rank = NEAR_RANK.get(self.spec.name)

        def ranked(f):
            if rank is None:
                return 0, f
            if f[0] not in near.ranks:
                near.ranks[f[0]] = rank(self, f[0], near.memo)
            return near.ranks[f[0]], f
        _, w, server = sorted(found, key=ranked)[0]
        return w, server

    # Whose unit of the followed subsystem this one wants to be beside: its own id by default, or the
    # string in the field `near.by` names. The row is read for the second form only — a subsystem whose
    # units share the other's naming pays nothing for the ones that do not.
    def near_id(self, uid) -> str:
        if self.spec.near_by == "id":
            return str(uid)
        row = self.unit(uid)
        return str(row.get(self.spec.near_by, "") or "") if row else ""

    # Where this unit belongs, for `ensure_home`. `home` is either the name of a field on the row — the
    # server an operator named — or the literal `near`, meaning "wherever the thing I follow is".
    #
    # The second form is what makes one subsystem come home BEHIND another. `near` alone is applied once,
    # when a unit is placed: a camera whose worker was moved while a server was down keeps being held
    # there for ever, because reading its fan-out over RTSP works and nothing is broken.
    #
    # Exactly one of a following pair may say `home: near`, and that is not a detail. Two subsystems that
    # each follow the other have no anchor: every pass moves each towards where the other was, and they
    # swap places instead of meeting. The anchor is the one with a real home — for the VMS, the recording,
    # because it writes to a disk and a disk does not move.
    def home_for(self, row: dict, near: NearIndex | None = None) -> str:
        if self.spec.home == "near":
            near = self.holder_near(row["id"], near) if self.spec.near != "none" else None
            return near[1] if near and near[1] != "?" else ""
        return str(row.get(self.spec.home, "") or "") if self.spec.home else ""

    # The same, addressed by id — what `_pick` needs before a unit is placed anywhere.
    def home_of(self, uid) -> str:
        if not self.spec.home or self.spec.home == "near":
            return ""                                     # the `near` form is resolved by `_pick`, which has the holder
        row = self.unit(uid)
        return str(row.get(self.spec.home, "") or "") if row else ""

    # The pick, with the two affinities in order — home first, then `near` — over a pool the FILTERS have
    # already cut (`eligible`: the constraint and `spread_by`). `(worker, free, note)`, and the note says
    # which it was: "at home on srv-a", "beside w-1 holding it", "away from home srv-a" — so the reason
    # tells the operator both where the recording reads its source from and whether it is where it belongs.
    #
    # Home before near, because they disagree exactly when a server is down: `near` would pin a recorder to
    # whichever server picked up the camera, and nothing would ever come back.
    def _pick(self, pool: list[str], uid, near: NearIndex | None = None) -> tuple[str | None, int, str]:
        near = self.holder_near(uid, near)
        home = near[1] if self.spec.home == "near" and near else self.home_of(uid)
        follows = self.spec.home == "near"
        if home:
            best, free = self._best([w for w in pool if self.place_of(w) == home])
            if best is not None:
                return best, free, (f", beside {near[0]} holding it" if follows else f", at home on {home}")
        if near is not None and not follows:
            beside = [w for w in pool if self.server_of(w) == near[1]]
            best, free = self._best(beside)
            if best is not None:
                return best, free, f", beside {near[0]} holding it" + (f" (home {home} has no room)" if home else "")
        best, free = self._best(pool)
        note = ""
        if best is not None and near is not None and self.server_of(best) != near[1]:
            note = f", away from {near[0]} on {near[1]} (no room there)"
        if best is not None and home and not follows and self.place_of(best) != home:
            note += f"; away from home {home}"
        return best, free, note

    # `most-free-capacity`: the worker with the largest `capacity_of − load`, strictly positive; ties go to
    # the first in sorted order.
    def _best(self, pool: list[str]) -> tuple[str | None, int]:
        best, free = None, 0
        for w in pool:                                        # most-free-capacity: the one tie-break in the catalogue
            f = self.capacity_of(w) - self.load(w)
            if f > free:
                best, free = w, f
        return best, free

    # Place one unit. An existing placement is returned untouched — adding a worker moves nothing. A missing
    # unit is `None`. Otherwise pick `_best` among the eligible pool; `None` if nothing has free capacity
    # ("the system is full" — or nothing that can reach it; never "w-1 is full"). The reason names the free
    # capacity, the pool size, the labels reached (under `labels-subset`) and the server. Then the row first
    # (CAS decides who won: if another instance placed it meanwhile, the mutator returns `None` and the
    # other's row is used), then `assign_add` on the winner's worker. `test_two_controllers_agree_by_cas`:
    # two threads placing 40 cameras with opposite preferences end with every camera exactly once across
    # `w-1`/`w-2`.
    def place(self, uid, workers: list[str] | None = None) -> Placement | None:
        """Place ONE unit on the worker with the most free capacity among those
        seen heartbeating (or given) that satisfy the constraint. An existing
        placement is returned untouched: adding a worker moves nothing."""
        have = self.placement(uid)
        if have:
            return have
        row = self.unit(uid)
        if row is None or self.retired(row):
            return None                                 # finished work is not placed, and not "unplaceable" either
        pool = self.eligible(row, self._pool(workers))
        best, free, near = self._pick(pool, uid, self.near_index())      # the pass's one look (`near_index`), not one per unit
        if best is None:
            return None                                 # "the system is full" — or nothing that can reach it; never "w-1 is full"
        reason = f"most free capacity ({free}) among {len(pool)} worker(s)"
        if self.spec.constraint == "labels-subset" and row.get("labels"):
            reason += f" reaching {','.join(sorted(row['labels']))}"
        reason += f"; on {self.server_of(best)}"
        if self.spec.requires == "resource":
            reason += f", whose resource is {self.resource_state(self.server_of(best))}"
        reason += near
        pl = Placement(self.spec.parse_id(uid), best, reason, self.wall(), 0)
        # the row first (CAS decides who won), then the assignment
        def mutate(it):
            if it and it.get("worker"):
                return None                             # the other instance placed it while we thought
            return {"worker": pl.worker, "reason": pl.reason, "at": pl.at, "rev": _next_rev(it)}
        written = self.write(self.sub.config("placement", str(uid)), mutate)
        pl = self._placement(uid, written)             # ours, or the other instance's — which may be the garbled one
        self.assign_add(pl.worker, str(uid))
        return pl

    # The pass: `unplace_deleted`, then `place` every unit; returns what is placed.
    # `test_placement_is_stored_with_a_reason_and_adding_a_worker_moves_nothing`: six cameras split 3/3 by
    # capacity 3; the seventh waits; a third worker arriving takes only the seventh.
    # THE PASS, as one call that measures itself and says so where anybody can read it (feedback BG). The
    # controller has no port, and its pass used to be three calls in a loop in `__main__`: a pass that raised
    # every time, a unit with nowhere to go, an assignment the rows contradicted — none of it was a number
    # anywhere. `snapshot_age` stayed fresh while the cameras were not recorded. The report goes to the object
    # store (`<sub>/controller/pass`), like a heartbeat, and the console exports it:
    #
    #   ts, last_success   when the pass last ran, and when it last ran WITHOUT raising. Both: a pass that does
    #                      not run is a controller that stopped; one that runs and never succeeds is a controller
    #                      that is up and failing — and a fresh snapshot hid exactly that
    #   seconds, failures  how long it took; how many passes have raised since the store was new
    #   unplaced           units that should be somewhere and are nowhere
    #   diverged           assignments this pass had to bring back to what the placement rows say
    #   garbled            rows that do not parse — units nobody serves until somebody mends the row
    #   reach_moves        units moved, or unplaced, because their server no longer reaches them (`ensure_reach`)
    #
    # The steps each in a `try` of their own (the review's second pass, M7): they shared one, so a
    # `redistribute` that raised on one released slot kept `ensure_home` from ever running, every pass. Four since
    # `ensure_reach` (feedback DQ), in the product's order: placed, reach, redistribute, home.
    PASS_KEY = CONTROLLER_PASS                        # granted by `acl_objects_controller` (the review's ninth pass)

    # …and each key read ONCE in it (`contract.one_pass`; the scaling pass after the eighth review): its three steps and
    # the report re-read the rows, the placements and the heartbeats per step and per unit — some 41 000 reads at a
    # thousand cameras on twenty workers, 2 000-odd now (`tests/test_read_budget.py`). The loop that also publishes the
    # snapshot opens the pass around both (`vms/__main__._controller_loop`), and the snapshot reads nothing again.
    def pass_once(self, home_budget: int = 1) -> dict:
        with one_pass(self):
            return self._pass_once(home_budget)

    def _pass_once(self, home_budget: int) -> dict:
        import json
        started, now = time.monotonic(), self.wall()
        prev = self.pass_report() or {}
        try:
            failures = int(prev.get("failures", 0))
        except PARSE_ERRORS:                          # `1e400` too: `int(inf)` raised out of the pass, every pass (the ninth review's sweep)
            failures = 0                              # a count that is a word: counted from here
        rep = {"ts": now, "ok": True, "error": "", "failures": failures,
               "last_success": prev.get("last_success")}
        self.last_diverged = 0
        errors = []
        self.last_reach_moves = 0
        for step, run in (("ensure_placed", self.ensure_placed),                   # deleted rows unplaced; new units onto the workers it sees
                          ("ensure_reach", self.ensure_reach),                     # a unit its server no longer reaches: moved, or unplaced with why
                          ("redistribute", self.redistribute),                     # units of a RELEASED slot (scale-in) onto the rest
                          ("ensure_home", lambda: self.ensure_home(home_budget))): # a unit back to the server its row names, if it is back
            try:
                run()
            except Exception as e:                    # noqa: BLE001
                errors.append(f"{step}: {e}")
                self._failed(step, f"placement pass failed at {step}")
            else:
                self._works(step)
        if errors:
            rep.update(ok=False, error="; ".join(errors), failures=rep["failures"] + 1)
        else:
            rep["last_success"] = now
        rep["seconds"] = round(time.monotonic() - started, 3)
        rep["diverged"] = self.last_diverged
        rep["reach_moves"] = self.last_reach_moves     # units moved or unplaced because their server no longer reaches them
        # …and since the store was new, a counter (the review's tenth pass, minor): the gauge of the last pass showed a
        # third of the moves to a scrape every 15 s
        from .rows import number
        rep["reach_moves_total"] = number(f"{self.sub.name}/{self.PASS_KEY}#reach_moves_total",
                                          prev.get("reach_moves_total", 0), int, 0) + self.last_reach_moves
        try:
            rep["unplaced"] = len(self.unplaced())
            rep["garbled"] = self.rows_garbled
            for name, counts in (("slots_garbled", SLOTS_GARBLED), ("assignments_garbled", ASSIGNMENTS_GARBLED)):
                if counts.get(self.sub.name):         # rows of the contract this process could not read (`contract.py`):
                    rep[name] = counts[self.sub.name] # said when there are any, as a worker's heartbeat says them
            self.objects.put(f"{self.sub.name}/{self.PASS_KEY}", json.dumps(rep).encode())
        except Exception:                             # noqa: BLE001 — a report that cannot be written is an old report, which says so
            self._failed("report", "the pass could not report on itself")
        else:
            self._works("report")
        return rep

    # A STEP THAT FAILS EVERY PASS IS SAID ONCE (the eighth review's minor, closed in the ninth): `log.exception` on every
    # pass put the same trace in the log every five seconds — a policy that refused the report did it for days — and
    # buried the first one, the one that says why. The trace once per spell, as `domain/steps.py` has it for М12's
    # loops; "works again" when the step succeeds; the count of failed passes is the report's `failures`.
    def _failed(self, step: str, what: str) -> None:
        if step not in self._pass_failing:
            self._pass_failing.add(step)
            log.exception("%s: %s; tried again on every pass, said again when it works", self.sub.name, what)

    def _works(self, step: str) -> None:
        if step in self._pass_failing:
            self._pass_failing.discard(step)
            log.warning("%s: %s works again", self.sub.name, step)

    # The last pass's report, or None — and None for one that does not parse (the sixth pass, the follow-up):
    # `pass_once` reads it first, and "it does not raise" is what the loop calling it relies on. Half a write under
    # this key raised out of the pass and out of the loop, the process ended, started, and ended again on the same
    # object — which only a pass that finishes writes over.
    def pass_report(self) -> dict | None:
        import json
        raw = self.objects.get(f"{self.sub.name}/{self.PASS_KEY}")
        if not raw:
            return None
        try:
            rep = json.loads(raw)
        except PARSE_ERRORS:
            log.warning("%s: the last pass's report does not parse; this pass writes it again", self.sub.name)
            return None
        return rep if isinstance(rep, dict) else None

    def unplaced(self) -> list:
        """Units that should be somewhere and are nowhere — whatever the reason; `/unplaceable` says which cannot be."""
        return [r["id"] for r in self.units() if not self.retired(r) and self.placement(r["id"]) is None]

    def ensure_placed(self, workers: list[str] | None = None) -> list[Placement]:
        self.unplace_deleted()
        self.unplace_retired()
        self.last_diverged = len(self.sync_assignments())
        out = []
        for r in self.units():
            # One unit that cannot be placed — a row that does not parse after a field changed its type, a
            # store that refused one write — is one unit waiting, not a pass that stops at it and places
            # nothing after it, every pass (feedback BC).
            try:
                pl = self.place(r["id"], workers)
            except Exception:                           # noqa: BLE001
                log.exception("%s: unit %s not placed this pass", self.sub.name, r.get("id"))
                continue
            if pl:
                out.append(pl)
        return out

    # The placement rows are the DECISION; the assignments carry it out. They are two writes, and a pass can
    # stop between them: a controller killed after the row and before `assign_add` left a unit whose row
    # named a worker that never heard of it — not placed again ("an existing placement is returned
    # untouched"), not in `/unplaceable`, running nowhere, for ever (the platform review; the product lost
    # a unit the same way to ten CAS conflicts in a row, feedback BC). So every pass starts by making the
    # assignments say what the rows say: the unit is added to the worker its row names and taken from any
    # other that lists it. A unit with no placement row is not touched — placing it is `place`'s job.
    def sync_assignments(self) -> list[tuple]:
        fixed = []
        assignments = self.assignments()
        for p in self.vars.list(self.sub.config("placement") + "/"):
            unit = p.rsplit("/", 1)[1]
            it, _ = self.vars.get(p)
            if not it or not it.get("worker"):
                continue
            want = it["worker"]
            for w, a in assignments.items():
                if w != want and unit in a.units:
                    self.assign_remove(w, unit)
                    fixed.append((unit, w, None))
            if unit not in (assignments[want].units if want in assignments else ()):
                self.assign_add(want, unit)
                fixed.append((unit, None, want))
        return fixed

    # Units with no placement that no live worker's labels can serve — the console's honest answer, with the
    # labels named and the live worker count.
    def unplaceable(self) -> list[dict]:
        """Units nothing live can serve — the console's honest answer, with the labels named."""
        with one_pass(self):                          # `eligible` per unit asked the heartbeats per worker, again per unit
            return self._unplaceable()

    def _unplaceable(self) -> list[dict]:
        live = self._pool(None)
        out = []
        for r in self.units():
            if self.placement(r["id"]) is None and not self.retired(r) and not self.eligible(r, live):
                u = {"id": r["id"], "labels": r.get("labels", []), "workers_live": len(live)}
                why = self.unplaced_reason(r["id"])
                if why and why != "deleted":           # what took its place away — a server that stopped reaching it
                    u["why"] = why
                out.append(u)
        return out

    # The placed worker.
    def where(self, uid) -> str | None:
        pl = self.placement(uid)
        return pl.worker if pl else None

    # The one two-writer operation: remove the unit from every assignment that lists it other than `to`
    # (wherever it is listed, not only where the row says), rewrite the placement row, `assign_add` on `to`.
    # The destination takes the next epoch when it starts; the source's lease fences on renewal and it
    # stops. Called by an operator's hand (no door of the console calls it), or by the controller's own steps through
    # `move_from` — a released slot's units (`redistribute`), a unit back home (`ensure_home`), one its server no
    # longer reaches (`ensure_reach`) — each with its reason in the row; never by a rebalance nobody asked for (the
    # review's tenth pass: "never automatic" was untrue since those steps).
    #
    # The order is the row, then the removals, then the addition (feedback BC): the row is the decision, and
    # `sync_assignments` finishes a move a crash cut short — from either side of it. `expect`: the worker the
    # caller saw the unit on. The OPERATOR's move has none — "from wherever it is". A move the CONTROLLER decided
    # names it (`move_from`), and the same CAS that writes the row checks the row still says so: two
    # controllers, overlapping for the seconds of a deploy, each moved the unit where it thought best, and the
    # unit ended in two assignments — which a worker reads as "I am a zombie".
    def move(self, uid, to: str, reason: str, expect: str | None = None) -> Placement:
        """The one two-writer operation: the destination takes the next epoch when
        it starts; the source's lease fences on renewal and it stops. The operator's,
        or a controller step's through `move_from`, with the reason in the row."""
        def mutate(it):
            if expect is not None and (it or {}).get("worker") != expect:
                raise Moved(f"{uid} is on {(it or {}).get('worker') or 'nobody'}, not on {expect}: somebody moved it first")
            return {"worker": to, "reason": reason, "at": self.wall(), "rev": _next_rev(it)}
        new = self.write(self.sub.config("placement", str(uid)), mutate)
        for w, a in self.assignments().items():                     # wherever it is listed, and not only where the row says
            if str(uid) in a.units and w != to:
                self.assign_remove(w, str(uid))
        self.assign_add(to, str(uid))
        return Placement(self.spec.parse_id(uid), to, reason, float(new["at"]), int(new["rev"]))

    def move_from(self, uid, frm: str, to: str, reason: str) -> Placement | None:
        """The controller's own move: only if the row still names `frm`. None if somebody moved it first."""
        try:
            return self.move(uid, to, reason, expect=frm)
        except Moved as e:
            log.info("%s: %s", self.sub.name, e)
            return None

    # The controller's one unasked move: for each released slot (scale-in, or `retire`) that still lists
    # units, move each to the live worker with the most free capacity; stop when the system is full (the
    # unit waits, listed where it was). A merely lapsed slot is not touched: that is a crash, and its
    # process returns under the same name. Two more cases when the spec requires a resource: a live worker
    # whose server's resource went silent (it has nowhere to write), and a slot that lapsed AND whose
    # server's resource is silent — the server is gone, and with one worker per server (`distinct_hosts`)
    # nobody will claim that slot until the server returns; its units go to the workers that are here. `test_scale_in_releases_a_slot_and_the_controller_redistributes`:
    # a silent `w-3` moves nothing; after `release_slot()` its two cameras go to `w-1`/`w-2` with reason
    # `slot w-3 released; …`.
    def redistribute(self, workers: list[str] | None = None) -> list[tuple]:
        """The controller's one unasked move: a slot that was RELEASED — the
        scheduler scaled in, or an operator retired it — still lists units. Move
        them to the workers that are here. A slot that merely lapsed is not
        touched: that is a crash, and its process returns under the same name."""
        self.unplace_deleted()
        moves = []
        seen = sorted(workers if workers is not None else self.workers_seen())
        # a released slot — and, when the spec requires a resource, a live worker whose server's resource
        # went silent: it heartbeats, but it has nowhere to write; its units go to workers that do
        gone_for = {g: f"slot {g} released" for g in self.released_slots()}
        for w in self.without_resource(seen):
            if self.assignment(w).units:
                gone_for.setdefault(w, f"resource on {self.server_of(w)} silent")
        # …and a live worker that holds NO PLACE where the subsystem places by one (feedback BN): a recorder
        # that lost its volume — two restarted, the other took it — is alive, keeps its slot and cannot write
        # a byte, and the recordings assigned to it used to stay there, recorded by nobody, for as long as it
        # lived. It says so itself (`place` empty in its heartbeat); its units go to a worker that has a place.
        for w in self.placeless(seen):
            if self.assignment(w).units:
                gone_for.setdefault(w, f"{w} holds no {self.spec.place_by} now")
        for w in self.on_draining(seen):                               # an operator said this machine is about to stop
            if self.assignment(w).units:
                gone_for.setdefault(w, f"server {self.server_of(w)} draining")
        for w, server in self.gone_servers().items():                  # the server is gone: its slot lapsed and its resource silent
            gone_for.setdefault(w, f"server {server} gone: slot {w} lapsed and its resource silent")
        idx = None                                    # one look at what is followed, taken when a unit is moved
        for gone, why in gone_for.items():
            live = [w for w in self._pool(workers) if w != gone]
            for unit in sorted(self.assignment(gone).units, key=_unit_key):
                try:
                    uid = self.spec.parse_id(unit)
                except PARSE_ERRORS as e:
                    # A name in the row that is no unit's id (`read_assignment` reads the list as it stands): that name's
                    # trouble, counted — it raised out of the whole step, and no unit of any leaving slot moved (the
                    # review's seventh pass, the walk over every row read).
                    ASSIGNMENTS.garbled(f"{self.sub.assignment(gone)}#{unit}", e)
                    continue
                row = self._parsed(uid)
                if row is GARBLED_ROW:
                    continue                            # its filters cannot be read: it waits where it is, the others move
                pool = self.eligible(row, live) if row else live
                idx = self.near_index() if idx is None else idx
                best, free, near = self._pick(pool, uid, idx)
                if best is None:
                    # THIS unit waits, listed where it was — and the next one is looked at: each has filters of
                    # its own, and a `break` here let one unit with a rare label, first in the list, hold every
                    # other unit of a dead worker for ever (the platform review; feedback BC).
                    continue
                if self.move_from(uid, gone, best, f"{why}; most free capacity ({free}); on {self.server_of(best)}{near}"):
                    moves.append((uid, gone, best))
        return moves

    # Units placed away from the home their row names, moved back — at most `budget` a pass, because every
    # move is a new epoch and a seam in the recording. It is the other half of `home`: the preference in
    # `_pick` decides where a unit goes when it is placed, and this is what happens to one already placed
    # somewhere else when its home comes back.
    #
    # `eligible` runs first, so the filters still beat the preference: a unit whose home is barred by
    # `spread_by` or by its labels stays where it is. A home with no live worker, or no room, is not an
    # error and says nothing — the unit is where it can be, which is the point of a preference.
    def ensure_home(self, budget: int = 1, workers: list[str] | None = None) -> list[tuple]:
        """Units away from the home their row names — or, with `near` and no `home`, away
        from the server holding what they follow — moved back, `budget` a pass."""
        if budget <= 0 or not self.spec.home:
            return []
        moves, pool = [], self._pool(workers)
        idx = None                                    # one look for every unit that follows, taken at the first
        for row in self.units():
            if len(moves) >= budget:
                break
            if idx is None and self.spec.home == "near":
                idx = self.near_index()
            uid, home = row["id"], self.home_for(row, idx)
            pl = self.placement(uid)
            if not home or pl is None or self.place_of(pl.worker) == home:
                continue
            best, free = self._best([w for w in self.eligible(row, pool) if self.place_of(w) == home])
            if best is None:
                continue                                  # home is not back, or has no room: stay put, quietly
            why = f"it follows {self.spec.near} onto" if self.spec.home == "near" else "home is"
            if self.move_from(uid, pl.worker, best, f"{why} {home}; most free capacity ({free}); on {home}"):
                moves.append((uid, pl.worker, best))
        return moves

    # WHAT MAKES A LABEL AN EDIT AND NOT A NOTE (feedback DQ). A placed unit whose worker no longer passes the constraint
    # — its server's labels, or its own, changed after it was placed — moves to a live worker that does; when none does,
    # it gives its place back with the reason, and `/unplaceable` lists it. Without this a label decided only the NEXT
    # placement: a camera stayed on a server that had stopped reaching it, and nothing said so.
    #
    # Only the constraint is asked again — `spread_by` and the subsystem's `admit` decided the place once and are not
    # this step's, though the target is chosen through `eligible`, which asks them — and only of a unit on a LIVE worker
    # of the pool: the units of a worker that is gone, leaving or draining are `redistribute`'s. At most `budget` a pass:
    # every move is a new epoch and a seam in the recording, and an edit that strips a server of its VLAN moves its
    # cameras over a few passes, not in one. A pass that has never read the servers' rows (`server_labels` is None: the
    # store did not answer) moves nothing; nor does one off a server whose row did not read this pass (the tenth pass).
    #
    # THE GROUP MOVES WHOLE, OR NOT THIS PASS (the review's tenth pass, minor): an administrator of one camera of a
    # four-channel recorder changed its `labels`, and the channel went alone to another holder — two sessions to one
    # recorder, for good. A unit with a group (`group_by`: the VMS's device) moves with every unit of its group on its
    # worker, onto a worker that takes them all, in one pass — past the budget when the group is the pass's first move;
    # with no such worker, the units whose server no longer reaches them give their place back and the rest stay: an
    # unplaced channel holds no session.
    #
    # …and A LABEL NO ROW CAN SAY IS NOT A REASON TO MOVE (the same pass, major): a camera stored with `склад` before the
    # one alphabet was placed by a node's word; a server's row cannot hold the word, so the camera stays where it is,
    # counted once (`UNIT_LABELS`). Each move and each place given back is a line in the log with its reason; the pass
    # report counts them (`reach_moves`, and `reach_moves_total` since the store was new).
    def ensure_reach(self, budget: int = REACH_BUDGET, workers: list[str] | None = None) -> list[tuple]:
        """Units whose worker no longer passes the constraint, moved to one that does — or unplaced, with the reason."""
        self.last_reach_moves = 0
        rule = CONSTRAINTS[self.spec.constraint]
        if budget <= 0 or self.spec.constraint == "none" or self.server_labels() is None:
            return []
        unread = set(self._server_rows_unread)
        pool = self._pool(workers)
        live, moves, idx, done = set(pool), [], None, set()
        for row in self.units():
            if len(moves) >= budget:
                break
            uid = row["id"]
            if str(uid) in done:
                continue
            pl = self.placement(uid)
            if pl is None or pl.worker not in live or self.retired(row):
                continue
            server = self.server_of(pl.worker)
            if server in unread:
                continue                                  # what its server reaches is not known this pass: it stays
            has = self.labels_of(pl.worker)
            if rule(row, has):
                continue
            why = self._why_off(row, server, has)
            if why is None:
                continue                                  # a label no server's row can say: it stays, counted
            group = self._reach_group(row, pl.worker)
            if len(group) > 1 and moves and len(moves) + len(group) > budget:
                break                                     # the group goes whole, next pass
            done |= {str(m["id"]) for m in group}
            idx = self.near_index() if idx is None else idx
            others = [w for w in pool if w != pl.worker]
            fits = None
            for m in group:
                e = set(self.eligible(m, others))
                fits = e if fits is None else fits & e
            best, free, near = self._pick([w for w in others if w in fits], uid, idx)
            if best is not None and free < len(group):
                best = None                               # no worker takes the whole group
            if best is None:
                for m in group:
                    if m is row or not rule(m, has):
                        mwhy = why if m is row else (self._why_off(m, server, has) or why)
                        if self.unplace_from(m["id"], pl.worker, f"{mwhy}; nothing live reaches it"):
                            moves.append((m["id"], pl.worker, None))
                            log.warning("%s: %s gave its place on %s back: %s; nothing live reaches it", self.sub.name,
                                        m["id"], pl.worker, mwhy)
                continue
            for m in group:
                reason = (f"{why}; most free capacity ({free}); on {self.server_of(best)}{near}" if m is row else
                          f"with {uid}, one {self.spec.group_by}: {why}; on {self.server_of(best)}")
                if not self.move_from(m["id"], pl.worker, best, reason):
                    break                                 # somebody moved it first: the rest of the group waits for the next pass
                moves.append((m["id"], pl.worker, best))
                log.warning("%s: %s moved from %s to %s: %s", self.sub.name, m["id"], pl.worker, best, reason)
        self.last_reach_moves = len(moves)
        return moves

    # Why a unit is off its server — the labels it needs that the server does not reach — or None when one of them is a
    # word no server's row can hold (`LABEL_WORD`): then it is not moved for it (counted once, `UNIT_LABELS`).
    def _why_off(self, row: dict, server: str, has: set) -> str | None:
        if self.spec.constraint != "labels-subset":
            return f"{server} no longer meets {self.spec.constraint}"
        lost = sorted(set(map(str, row.get("labels") or [])) - set(has))
        key = f"{self._row_key(row['id'])}#labels"
        bad = [l for l in lost if not LABEL_WORD.fullmatch(l)]
        if bad:
            UNIT_LABELS.garbled(key, f"{bad[0]!r} is not a label")
            return None
        UNIT_LABELS.parsed(key)
        return f"{server} no longer reaches {','.join(lost)}"

    # The units of `row`'s group placed on `worker` — `row` first — or `[row]` when the spec groups nothing or the row
    # has no group.
    def _reach_group(self, row: dict, worker: str) -> list[dict]:
        value = self.group_value(row) if self.spec.group_by else ""
        if not value:
            return [row]
        out = [row]
        for other in self._rows_by("group", self.group_value).get(value, ()):
            if str(other["id"]) == str(row["id"]) or self.retired(other):
                continue
            pl = self.placement(other["id"])
            if pl is not None and pl.worker == worker:
                out.append(other)
        return out

    # A unit's place given back — the row says nowhere, and why — only while the row still names `frm`, in the same CAS
    # that writes it (`move`'s rule); then the assignment follows. The next pass places it again if anything live can.
    def unplace_from(self, uid, frm: str, reason: str) -> bool:
        def mutate(it):
            if (it or {}).get("worker") != frm:
                raise Moved(f"{uid} is on {(it or {}).get('worker') or 'nobody'}, not on {frm}: somebody moved it first")
            return {"worker": "", "reason": reason, "at": self.wall(), "rev": _next_rev(it)}
        try:
            self.write(self.sub.config("placement", str(uid)), mutate)
        except Moved as e:
            log.info("%s: %s", self.sub.name, e)
            return False
        self.assign_remove(frm, str(uid))
        return True

    # Why a unit is nowhere, when its placement row says so — a reach lost, a unit finished, deleted — else None.
    def unplaced_reason(self, uid) -> str | None:
        it, _ = self.vars.get(self.sub.config("placement", str(uid)))
        return str(it.get("reason") or "") or None if it and not it.get("worker") else None

    # Up to `budget` moves: each step takes the most and least loaded workers by `load/capacity`, stops if
    # their spread is under the dead band or the low one is full, and moves the lowest-numbered unit of the
    # high one. Only when asked. `test_rebalance_is_explicit_budgeted…`: budget 0 moves nothing; budget 3
    # moves three from `w-1` to `w-2`; a further budget of 5 moves one more and then stops inside the 10 %
    # band.
    def rebalance(self, budget: int, dead_band: float | None = None, workers: list[str] | None = None) -> list[tuple]:
        dead_band = self.spec.dead_band if dead_band is None else dead_band
        workers = self._pool(workers)
        moves = []
        for _ in range(budget):
            if len(workers) < 2:
                break
            loads = {w: self.load(w) / self.capacity_of(w) for w in workers}
            hi, lo = max(workers, key=loads.get), min(workers, key=loads.get)
            if loads[hi] - loads[lo] < dead_band:
                break
            cands = sorted(self.assignment(hi).units, key=_unit_key)
            if not cands or self.load(lo) + 1 > self.capacity_of(lo):
                break
            uid = self.spec.parse_id(cands[0])
            if not self.move_from(uid, hi, lo, f"rebalance from {hi} (spread {(loads[hi] - loads[lo]) * 100:.0f}%)"):
                break                                     # the picture changed under this pass: the next one looks again
            moves.append((uid, hi, lo))
        return moves

    # -- what the console and the layer above read -------------------------------------------
    # What the console lists: every `status` entry from every worker's latest heartbeat (any age), tagged
    # with `worker`, `server`, `age` and `worker_state` (`live` or `stale`), sorted by unit id.
    # `test_the_failure_arithmetic`: with the controller gone the read model still answers from heartbeats;
    # with the worker gone 100 s the rows say `stale`, age 100.
    def read_model(self, lost_after: float = 45.0) -> list[dict]:
        now = self.wall()
        rows = []
        for w, hb in self.workers_seen(max_age=1e12).items():
            age = now - hb.ts
            state = "live" if age <= lost_after else "stale"
            for s in hb.status:
                if "id" not in s:
                    continue                            # an entry that names no unit says nothing about one (the seventh pass)
                rows.append({**s, "worker": w, "server": hb.extra.get("server", "?"), "age": round(age, 1), "worker_state": state})
        return sorted(rows, key=lambda r: _unit_key(str(r["id"])))

    # -- blobs: a field too big for a row ------------------------------------------------------------
    # The bytes of one `blob` field. Written FIRST, before the row that names them: a crash between the
    # two leaves an object nobody points at (harmless, collectable), where the other order would leave a
    # row pointing at nothing — a unit that cannot start. The same order М12's identity store publishes in.
    #
    # The key is the digest, so this is idempotent by construction: writing the same bytes twice writes
    # the same object twice, and two units with the same mask share one object.
    def put_blob(self, data: bytes) -> str:
        """Store the bytes; return the digest to put in the row."""
        import json
        d = blob_digest(data)
        # These exact bytes may be sitting on the sweep's list right now — the same mask uploaded again
        # for a second unit, while the copy the first unit stopped naming is marked for collection.
        # Taking it off the list makes the sweep's own CAS fail, and a sweep that loses that CAS deletes
        # nothing at all. The alternative is a lock, for a window two store calls wide.
        key = self.sub.sweep_key()

        def off_the_list(it):
            marked = _sweep_list(it)[0]
            return {**it, "digests": json.dumps([x for x in marked if x != d])} if d in marked else None

        self.write(key, off_the_list)                 # by CAS, tried again on a conflict: the sweeper writes this row too
        # On the platter before the row names it (`FsObjectStore.put_durable`); a store without the barrier puts as it can.
        getattr(self.objects, "put_durable", self.objects.put)(self.sub.blob_key(d), data)
        return d

    # What a worker calls with the digest it read from its row. `None` when the object is not there, which
    # is a real state — the row travelled and the object did not — and the caller must not start on it.
    #
    # The bytes are CHECKED against the digest before they are handed over. Not belt-and-braces: the key
    # says what the bytes are, and nothing but this makes that true. An ACL says who may write the key,
    # which is a different claim and a weaker one — it cannot survive a store shared more widely than
    # intended, an object copied between stores, or a bad disk. `verify` survives all three.
    def blob(self, d: str, check_digest: bool = True) -> bytes | None:
        data = self.objects.get(self.sub.blob_key(d))
        if data is None or not check_digest:
            return data
        return verify(d, data)

    # Every digest any row currently names: what the sweep keeps (`sweep_blobs`, below).
    def blobs_referenced(self) -> set[str]:
        names = [n for n, f in self.spec.fields.items() if f.type == "blob"]
        return {r[n] for r in self.units() for n in names if is_digest(r.get(n) or "")}

    # -- the sweep: collecting blobs nothing names any more ------------------------------------------
    # Nothing else in the platform deletes an object, and this is the one thing that has to. A blob key is
    # the digest of its bytes, so every edit of a `blob` field makes a NEW permanent object: unlike a
    # heartbeat, whose key is reused by the next instance of the slot, blobs grow with the number of edits
    # over the system's lifetime and nothing ever reclaims them.
    #
    # The obvious implementation is wrong, and it is worth being precise about why. "Delete every blob no
    # row names" races with `put_blob`: the object is written BEFORE the row that names it (Lesson 26), so
    # a sweep landing between those two writes sees an unreferenced blob and deletes the bytes a row is
    # about to point at. The unit then cannot start, and the operator's upload silently did nothing.
    #
    # So noticing and deleting are put in DIFFERENT PASSES:
    #
    #   mark   nothing is deleted. The digests that no row names are written to `<name>/sweep` with the
    #          time. A blob created after this moment is not on the list, which is where the grace period
    #          comes from — no timestamps on objects required, and `variables://` has none to offer.
    #   sweep  one pass later, and only after `grace`: the marked digests are checked AGAIN, the decision is
    #          written by CAS on the index just read — the doomed digests, `state: deleting` — and only then
    #          are the objects removed, each one read back from the row the moment before.
    #
    # The order of those last two is the whole safety argument. Writing the decision first means a lost CAS —
    # anyone touched the row since the mark — costs nothing: not one object has been deleted yet. Deleting
    # first would mean acting on a decision that something has already contradicted.
    #
    # And the decision STAYS on the row while the bytes go (the review's second pass, m5). It used to be
    # cleared first, so a `put_blob` of a marked digest in the seconds the deletes took found an empty list,
    # took nothing off it, and its bytes were removed under a row about to name them. Now it finds the digest
    # there, as before the decision, and takes it off; the sweeper re-reads the row before each delete and
    # leaves what is gone from it alone. The row is cleared at the end, by CAS; a clear that loses — somebody
    # took a digest off meanwhile — leaves the rest listed for the next pass, which checks them again.
    #
    # That left one window, two store calls wide (the review's third pass): the sweeper reads "still doomed",
    # `put_blob` takes the digest off and writes the object, and the sweeper's delete removes it. It is closed by
    # reading the bytes before the delete and the row AFTER it: a digest that left the list in between is one
    # somebody is uploading, and its object is put back — the same bytes, by construction (the key is their
    # digest), so the restore and the upload write one object, in whichever order they land. Still on the list
    # after the delete means `put_blob` has not taken it off yet, and its own write comes after ours.
    #
    # `limit` is not a nicety either: `<name>/sweep` is a row, and a row has the store's ceiling over it
    # (Lesson 26). The sweep is subject to the rule it was written under.
    SWEEP_LIMIT = 64
    SWEEP_GRACE = 300.0

    def sweep_blobs(self, limit: int = SWEEP_LIMIT, grace: float = SWEEP_GRACE) -> dict:
        """One pass: marks, or sweeps, or waits. `{marked, deleted, waiting}`."""
        import json
        names = [n for n, f in self.spec.fields.items() if f.type == "blob"]
        if not names:
            return {"marked": 0, "deleted": 0, "waiting": 0}
        key, now = self.sub.sweep_key(), self.wall()
        items, idx = self.vars.get(key)
        marked, at = _sweep_list(items)

        if not marked:                                   # -- mark: notice, write it down, delete nothing
            referenced = self.blobs_referenced()
            prefix = self.sub.blobs_prefix()
            orphans = sorted(k[len(prefix):] for k in self.objects.list(prefix)
                             if k[len(prefix):] not in referenced)[:limit]
            if orphans:
                self.vars.put(key, {"at": str(now), "digests": json.dumps(orphans)}, cas=idx)
            return {"marked": len(orphans), "deleted": 0, "waiting": 0}

        if now - at < grace:
            return {"marked": 0, "deleted": 0, "waiting": len(marked)}

        # -- sweep: check again, write the decision down, and only then remove the bytes
        referenced = self.blobs_referenced()
        # Only digests: an entry of the list that is none is no blob's name — `blob_key` raised on it, every sweep, and the
        # list was never cleared: nothing of the subsystem was reclaimed again (the review's seventh pass).
        doomed = [d for d in marked if isinstance(d, str) and is_digest(d) and d not in referenced]
        self.vars.put(key, {"at": str(now), "digests": json.dumps(doomed), "state": "deleting"}, cas=idx)   # Conflict here deletes nothing
        deleted = 0
        for d in doomed:
            items, idx = self.vars.get(key)                                 # still doomed? `put_blob` takes a digest off this list
            if d not in _sweep_list(items)[0]:
                continue
            data = self.objects.get(self.sub.blob_key(d))
            if data is None or not self.objects.delete(self.sub.blob_key(d)):
                continue
            items, idx = self.vars.get(key)                                 # …and after: taken off meanwhile is being uploaded
            if d not in _sweep_list(items)[0]:
                getattr(self.objects, "put_durable", self.objects.put)(self.sub.blob_key(d), data)
                continue
            deleted += 1
        try:
            self.vars.put(key, {"at": str(now), "digests": "[]"}, cas=idx)
        except Conflict:
            pass                                                            # a digest left the list under us: the rest wait for the next pass
        return {"marked": 0, "deleted": deleted, "waiting": 0}

    # Units and placement for the layer above, ONE OBJECT PER WORKER: `<name>/snapshot/<worker>` holding
    # `{cluster, worker, ts, <rows>: [{id, <snapshot fields>, revision, worker, server}]}`, plus
    # `<name>/snapshot/unplaced` for the units nobody holds. A copy with an age — never the rows
    # themselves, which do not leave raft.
    #
    # The shape is the heartbeat's, and that is the point. Every other object in the platform is already
    # sharded by its writer — one heartbeat per worker, one resource heartbeat per server — and stays small
    # whatever the cluster does. The snapshot was the exception: one object for every unit in the cluster,
    # under a store with a ceiling. See `Subsystem.snapshot_key` for the arithmetic that made this a defect
    # rather than a preference.
    def snapshot_shards(self) -> dict[str, dict]:
        """The snapshot as one object per worker, keyed by shard name."""
        with one_pass(self):                          # `server_of` per unit read every heartbeat per unit (the scaling pass)
            return self._snapshot_shards()

    def _snapshot_shards(self) -> dict[str, dict]:
        keep = ["id"] + [f for f in self.spec.snapshot if f != "id"] + ["revision"]
        now, out = self.wall(), {}
        for r in self.units():
            w = self.where(r["id"])
            self.sub.snapshot_key(w)              # refuses a worker named `unplaced` before it shadows the shard
            sh = out.setdefault(w or UNPLACED, {"cluster": self.cluster, "worker": w, "ts": now, self.spec.rows: []})
            sh[self.spec.rows].append({**{k: r[k] for k in keep if k in r}, "worker": w,
                                       "server": self.server_of(w or "")})
        return out

    # The shards merged back, for a reader inside this process. What М12 does over the wire is the same
    # merge, out of `objects.list(snapshot_prefix())` — see `Cluster.snapshot` there.
    def snapshot(self) -> dict:
        """Every shard merged: what the layer above ends up seeing."""
        shards = self.snapshot_shards()
        units = [u for sh in shards.values() for u in sh[self.spec.rows]]
        return {"cluster": self.cluster, "ts": self.wall(), self.spec.rows: units}

    # How old the published snapshot is, in seconds — `None` when nothing has been published.
    #
    # Read from the STORE, not kept in this process: the controller has no port to serve it from, it is
    # restarted freely, and two of them may be running. Whoever can read the objects can answer this, which
    # is what makes it a number a console can put on `/metrics`.
    #
    # The age of the whole is the age of the STALEST shard, the same rule М12's reader uses: a directory is
    # only as fresh as its oldest part, and taking the newest would report an RPO better than the real one —
    # which is exactly the direction a number like this must never be wrong in.
    #
    # A `ts` FROM THE FUTURE IS NOT FRESH (the review's ninth pass, minor): a controller whose clock ran an hour ahead
    # and then stopped wrote shards an hour ahead — `max(0, now − ts)` read them as age 0 for that hour, the copy above
    # "fresh" while nothing published it. A shard further ahead than `FUTURE_TOLERANCE` (the heartbeats' rule) has no
    # age anybody can vouch for: the oldest there can be, counted once (`fields_garbled`), and its lead goes into the
    # subsystem's `heartbeat_skew_seconds_max`, where a clock running ahead is already measured.
    def snapshot_age(self, now: float | None = None) -> float | None:
        import json
        from .contract import FUTURE_TOLERANCE, SKEW_MAX
        from .rows import FIELDS
        now = self.wall() if now is None else now
        oldest = None
        prefix = self.sub.snapshot_prefix()
        for key in self.objects.list(prefix):
            raw = self.objects.get(key)
            if not raw:
                continue
            try:
                ts = finite(json.loads(raw).get("ts", 0))   # `nan` passes every `min` and read as fresh (the review's eighth pass)
            except PARSE_ERRORS:
                ts = 0.0                              # a shard that does not parse has no age: the oldest there can be
            if ts - now > FUTURE_TOLERANCE:
                SKEW_MAX[self.sub.name] = max(SKEW_MAX.get(self.sub.name, 0.0), ts - now)
                FIELDS.garbled(f"{key}#ts", ValueError(f"{ts - now:.0f} s ahead of this clock: no age anybody can vouch for"))
                ts = 0.0
            else:
                FIELDS.parsed(f"{key}#ts")
            oldest = ts if oldest is None else min(oldest, ts)
        if oldest is None:
            return None
        return max(0.0, now - oldest)

    # Writes one object per worker under `<name>/snapshot/`.
    def publish_snapshot(self) -> None:
        with one_pass(self):
            self._publish_snapshot()

    def _publish_snapshot(self) -> None:
        import json
        shards = self.snapshot_shards()
        prefix = self.sub.snapshot_prefix()
        # A worker that is GONE — scaled in, or its units moved away — keeps its last shard forever: nothing
        # in the platform deletes an object. Its units would go on being reported to М12 from a worker that
        # no longer exists. So every shard already in the store that this pass did not fill is written EMPTY.
        for key in self.objects.list(prefix):
            shards.setdefault(key[len(prefix):], {"cluster": self.cluster, "worker": None, "ts": self.wall(),
                                                  self.spec.rows: []})
        # A cluster with no units at all — a camera's cluster before its camera, a recording cluster before
        # its first recording — would publish NOTHING, and "published that there are none" would read as
        # "never published" (feedback AA). М12's member that has not published does not report (Lesson 10),
        # so such a cluster stayed "never reported" for ever. An empty `unplaced` shard is the statement.
        if not shards:
            shards[UNPLACED] = {"cluster": self.cluster, "worker": None, "ts": self.wall(), self.spec.rows: []}
        for name, shard in shards.items():
            try:
                self.objects.put(prefix + name, json.dumps(shard).encode())
            except TooLarge as e:
                # The store refuses with bytes; the caller knows what those bytes WERE. A shard is one
                # worker's assignment, so an oversized shard is not a shape problem any more — it is a
                # store too small to hold what a single worker carries, and `OBJECTS` is what names it.
                raise TooLarge(e.key, e.size, e.limit,
                               f"{len(shard[self.spec.rows])} units on {name}; the snapshot is already one "
                               f"object per worker, so the store is the thing to change (OBJECTS=…)") from e

    # Per worker: the gap between the last heartbeat of the previous instance and this instance's start.
    #
    # ON ONE CLOCK (the review's ninth pass, minor; the product's sibling D). `started − previous_hb` subtracted the clock
    # of the box the replacement runs on from the clock of the box the instance before it ran on: on two machines their
    # disagreement was IN the number — ten minutes of drift, a ten-minute failover, or a negative one. Two ways now,
    # each on one clock:
    #
    #   the same server   the instance before ran where this one runs (`previous_server` = `server`, written by the
    #                     replacement from the heartbeat it found): `started − previous_hb`, both by that box's clock
    #   another server    what THIS reader saw, by its own clock: when the heartbeat under that name last moved, and
    #                     when another instance was first there — as late as the reader looks (the console reads it on
    #                     every scrape, the stand when a scene says so)
    #
    # Neither — another server, and this reader did not see the instance before alive — is not measured: no number made
    # of two clocks. Nor is a negative gap (one clock that stepped back). Both are counted (`failovers_unmeasured`, on
    # `/metrics`). Every number through `rows.number`: `previous_hb: -inf` made `worst` infinite and the alert burn for
    # ever. `failover_worst` is the largest this process has measured: the largest of the LAST ones forgot a failover as
    # soon as the same worker had a shorter one.
    def failover_seconds(self) -> dict[str, float]:
        """Per worker: the gap between the heartbeat before its current instance started and that instance's start —
        on one clock, or not at all."""
        from .rows import FIELDS, number
        now, out, unmeasured = self.wall(), {}, 0
        for w, hb in self.workers_seen(max_age=1e12).items():
            hk = self.sub.heartbeat_key(w)
            instance = str(hb.extra.get("instance", ""))
            was = self._hb_moved.get(w)                   # (instance, ts, when this reader saw it move)
            if was is not None and was[0] != instance:
                self._failover_seen[w] = round(now - was[2], 1)   # another instance, seen by this reader: its clock only
            if was is None or was[:2] != (instance, hb.ts):
                self._hb_moved[w] = (instance, hb.ts, now)
            prev = number(f"{hk}#previous_hb", hb.extra.get("previous_hb"), float, None)
            if not prev:
                continue                                  # no instance before this one under that name: no failover
            server = hb.extra.get("server")
            if server is not None and hb.extra.get("previous_server") == server:
                started = number(f"{hk}#started", hb.extra.get("started"), float, None) if "started" in hb.extra else hb.ts
                gap = None if started is None else round(started - prev, 1)
            else:
                gap = self._failover_seen.get(w)
            if gap is not None and gap < 0:
                FIELDS.garbled(f"{hk}#previous_hb", ValueError(f"{gap} s before this instance started: a clock stepped back"))
                gap = None
            if gap is None:
                unmeasured += 1
                continue
            out[w] = gap
            self.failover_worst = max(self.failover_worst, gap)
        self.failovers_unmeasured = unmeasured
        return out
