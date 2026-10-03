"""The scenario as data: what a trigger may say, what an action may ask for,
and the refusal that happens at the door instead of at three in the morning."""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # auto.py — the seventh subsystem's controller, and the whole of the scenario language
#
# **Role in the module.** `auto.subsystem.yaml` says a scenario has a `when`, a `within` and a `then`; the
# platform checks that those are JSON and small, and stops there, because a generic loader that validated a
# trigger would be a generic loader that knows what a trigger is. This file is where the shapes mean
# something: `AutoController.create` refuses a scenario the evaluator could not run, at the moment the
# operator presses the button.
#
# **Why the language is fixed and not an expression.** An expression language is an interpreter: a parser,
# a grammar, precedence, errors at evaluation time, and a page that cannot offer a form because it cannot
# know what the operator will type. A fixed shape is a dozen checks, a form the console can build from the
# catalogue, and every refusal arriving while somebody is still looking at what they wrote. When the shape
# stops fitting, the honest move is another field — not a parser.
#
# **The catalogue is the boundary.** `ACTIONS` names the pairs `(subsystem, action)` this course knows how
# to file a request for, with the fields each one needs. It lives here and not in the platform for the same
# reason the trigger shapes do; it lives here and not in each target subsystem because it is a statement
# about what AUTOMATION may ask for, which is narrower than what those subsystems can do.
#
# **The catalogue is not the device.** `ACTIONS` says preset is a thing automation may ask for; it does not
# say camera 12 has a telemetry, or that it raises `io.input`, or that detector `7` exists. That is a FACT,
# and only the holder of the device knows it: it writes it in `vms/devices/<device>` (`config.describe`).
# `Catalog` reads those rows beside the operator's own (`vms/cameras/*`, `det/units/*`), and a scenario is
# checked against both — the policy (may automation ask for this at all) and the fact (can this unit say
# or do it). A misfit is refused at the door like a missing field; a scenario the fact cannot vouch for yet
# (the device has never been held) is accepted and named on every pass, and so is one that stopped fitting
# after it was written (the camera was replaced by one without a telemetry).
#
# ## Public API
# - `TRIGGER_KEYS`, `ACTIONS` — the language, as data.
# - `Catalog(vars_)` — what the units say and do; `check(fields) -> (misfits, unchecked)`; `reply()` — the
#   whole of it, for the page to build its form from (`GET /auto/catalog`).
# - `refuse_scenario(fields, catalog=None)` — raises `Refused` with a sentence an operator can act on.
# - `AutoController` — `SpecController` over `AUTO_SPEC`, refusing on create and on update.
# - `fires(trigger, event)` — does this event match this trigger. The evaluator's half of the language,
#   here beside the validation so the two cannot drift.
# ================================================================================================
from __future__ import annotations

import time

from w2cplatform.doors import numeric
from w2cplatform.objects import ObjectStore
from w2cplatform.rows import PARSE_ERRORS
from w2cplatform.spec import Refused, SpecController
from w2cplatform.variables import Variables

from .config import AUTO_SPEC, DET_SPEC, DEVICES, HOLDER_EVENTS, SPEC as VMS_SPEC, device_of, parse_device_row

# A trigger names the subsystem whose events it watches and the kind of event, and may narrow it to one
# unit and to fields of the event. Four keys and no more: anything a fifth key would express is either a
# second trigger or a thing the evaluator cannot know.
TRIGGER_KEYS = ("sub", "kind", "unit", "match")

# What automation may ask for. `(subsystem, action)` -> the fields the request needs, and the ones it may
# have. Every one of these becomes a row in `<sub>/requests/<id>`, performed by whoever holds the unit.
ACTIONS = {
    ("vms", "output"): {"need": ("unit", "port"), "may": ("state", "pulse_ms")},
    ("vms", "preset"): {"need": ("unit", "n"), "may": ()},
    ("rec", "record"): {"need": ("cam", "minutes"), "may": ("archive",)},
    # The detectors' two: the stream for minutes from now, or the archive around the moment (`vms/jobs.py`).
    ("det", "detect"): {"need": ("cam", "kind", "minutes"), "may": ("params",)},
    ("det", "scan"): {"need": ("cam", "kind"), "may": ("before", "after", "rec", "params")},
}

# A scenario may not ask for the world. The ceiling is on the SHAPE — how many triggers, how long a window
# — because a scenario with forty triggers and an hour-long window is a query over the whole log run every
# pass, and it would be the operator's own console that got slow.
MAX_TRIGGERS = 4
MAX_WITHIN = 3600
MAX_VALID_FOR = 600          # what a holder accepts: `VmsWorker.MAX_VALID` (a command's deadline is near)
MAX_ACTIONS = 4


def _dicts(v, what: str) -> list[dict]:
    if not isinstance(v, list) or not v:
        raise Refused(f"`{what}` is a non-empty list")
    if len(v) > (MAX_TRIGGERS if what == "when" else MAX_ACTIONS):
        raise Refused(f"`{what}` takes at most {MAX_TRIGGERS if what == 'when' else MAX_ACTIONS} entries")
    for e in v:
        if not isinstance(e, dict):
            raise Refused(f"every entry of `{what}` is an object, not {type(e).__name__}")
    return v


# What the units of this cluster can say and do — the operator's rows for what EXISTS, the holders' rows for
# what it IS. Read from the store on every question: a scenario is written seldom and checked once a pass,
# and a cache here would be a second copy of the rows to keep right.
#
# Two subsystems describe their units, and that is where the check stops. A camera (`vms`) raises what its
# device posts plus what its holder says about every unit (`HOLDER_EVENTS`); a detector (`det`) raises its
# `kind` and nothing else, and its name is `<cam>-<kind>` — the trigger `{sub: det, unit: "7"}` this lesson
# first printed would never have fired, and nothing said so. Any other subsystem's events are not checked,
# and the scenario is told that rather than passed as if they were.
class Catalog:
    def __init__(self, vars_: Variables):
        self.vars = vars_

    def camera(self, unit) -> dict | None:
        it, _ = self.vars.get(VMS_SPEC.sub.config(VMS_SPEC.rows, str(unit)))
        return it if it and it.get("deleted") != "true" else None

    def device(self, cam: dict) -> dict | None:
        if not cam.get("source"):
            return None
        it, _ = self.vars.get(VMS_SPEC.sub.config(DEVICES, device_of(str(cam["source"]))))
        return parse_device_row(it)

    def detectors(self) -> dict[str, dict]:
        out = {}
        for key in self.vars.list(DET_SPEC.sub.config(DET_SPEC.rows, "")):
            it, _ = self.vars.get(key)
            if it and it.get("deleted") != "true":
                out[key.rsplit("/", 1)[1]] = it
        return out

    def recordings_of(self, cam: str, rec: str = "") -> list[str]:
        from .config import REC_SPEC
        out = []
        for key in self.vars.list(REC_SPEC.sub.config(REC_SPEC.rows, "")):
            it, _ = self.vars.get(key)
            if it and it.get("deleted") != "true" and str(it.get("cam", key.rsplit("/", 1)[1])) == cam:
                out.append(key.rsplit("/", 1)[1])
        return [r for r in out if not rec or r == rec]

    def cameras(self) -> dict[str, dict]:
        out = {}
        for key in self.vars.list(VMS_SPEC.sub.config(VMS_SPEC.rows, "")):
            it, _ = self.vars.get(key)
            if it and it.get("deleted") != "true":
                out[key.rsplit("/", 1)[1]] = it
        return out

    # -- one trigger ------------------------------------------------------------------------------
    def _trigger(self, t: dict, misfit: list, unsure: list) -> None:
        sub, kind, unit = str(t.get("sub", "")), str(t.get("kind", "")), str(t.get("unit") or "")
        if sub == VMS_SPEC.name:
            cams = {unit: self.camera(unit)} if unit else self.cameras()
            if unit and cams[unit] is None:
                misfit.append(f"there is no camera {unit}")
                return
            if kind in HOLDER_EVENTS:
                return                                   # every held unit raises these: nothing to ask a device
            descs = {u: self.device(c) for u, c in cams.items()}
            said = {u: d for u, d in descs.items() if d is not None}
            if any(kind in d["events"] for d in said.values()):
                if kind == "io.input" and unit and "port" in (t.get("match") or {}):
                    rays = said[unit]["rays"]
                    if not 1 <= (numeric(t["match"]["port"]) or 0) <= rays:     # `doors.numeric`: `²` raised (the tenth pass)
                        misfit.append(f"camera {unit} has {rays} input(s), not port {t['match']['port']}")
                return
            if len(said) < len(descs):
                who = f"camera {unit}" if unit else "not every camera"
                unsure.append(f"{who} has not said what it raises — its device has not been held yet; "
                              f"{kind!r} is not checked")
                return
            raised = sorted({e for d in said.values() for e in d["events"]})
            misfit.append(f"camera {unit} does not raise {kind!r} — it raises {', '.join(raised)}" if unit else
                          f"no camera raises {kind!r} — the cameras raise {', '.join(raised)}")
        elif sub == DET_SPEC.name:
            dets = self.detectors()
            if unit and unit not in dets:
                on = sorted(n for n, d in dets.items() if str(d.get("cam")) == unit)
                misfit.append(f"there is no detector {unit}" +
                              (f" — a detector is named by its unit: {', '.join(on)} (camera {unit}'s)" if on else ""))
                return
            kinds = {str(dets[unit].get("kind"))} if unit else {str(d.get("kind")) for d in dets.values()}
            if kind not in kinds:
                misfit.append(f"detector {unit} raises {', '.join(sorted(kinds))}, not {kind!r}" if unit else
                              f"no detector raises {kind!r}" + (f" — the detectors raise {', '.join(sorted(kinds))}"
                                                                if kinds else " — there are no detectors"))
        else:
            unsure.append(f"{sub} does not describe what its units raise: {kind!r} is not checked")

    # -- one action -------------------------------------------------------------------------------
    def _action(self, a: dict, misfit: list, unsure: list) -> None:
        sub, name = str(a.get("sub", "")), str(a.get("action", ""))
        if (sub, name) == ("rec", "record"):
            if self.camera(a.get("cam")) is None:
                misfit.append(f"there is no camera {a.get('cam')} to record")
            return
        if sub == DET_SPEC.name:
            cam = str(a.get("cam", ""))
            if self.camera(cam) is None:
                misfit.append(f"there is no camera {cam} to {name}")
            elif name == "scan" and not self.recordings_of(cam, str(a.get("rec") or "")):
                misfit.append(f"nothing records camera {cam}: a scan reads the archive" if not a.get("rec") else
                              f"there is no recording {a.get('rec')} of camera {cam}")
            return
        if sub != VMS_SPEC.name:
            return
        unit = str(a.get("unit", ""))
        cam = self.camera(unit)
        if cam is None:
            misfit.append(f"there is no camera {unit}")
            return
        d = self.device(cam)
        if d is None:
            unsure.append(f"camera {unit} has not said what it can do — its device has not been held yet; "
                          f"vms.{name} is not checked")
            return
        if name == "output":
            port = str(a.get("port", ""))
            if not d["relays"]:
                misfit.append(f"camera {unit} has no relays")
            elif not 1 <= (numeric(port) or 0) <= d["relays"]:
                misfit.append(f"camera {unit} has {d['relays']} relay(s), not port {port}")
        elif name == "preset":
            n = str(a.get("n", ""))
            if not d["ptz"]:
                misfit.append(f"camera {unit} has no telemetry: it cannot go to a preset")
            elif d["presets"] and not 1 <= (numeric(n) or 0) <= d["presets"]:
                misfit.append(f"camera {unit} has {d['presets']} preset(s), not {n}")

    def check(self, fields: dict) -> tuple[list[str], list[str]]:
        """(misfits — refused at the door; unchecked — accepted, and said on every pass)."""
        misfit: list[str] = []
        unsure: list[str] = []
        for t in fields.get("when") or []:
            if isinstance(t, dict):
                self._trigger(t, misfit, unsure)
        for a in fields.get("then") or []:
            if isinstance(a, dict):
                self._action(a, misfit, unsure)
        return list(dict.fromkeys(misfit)), list(dict.fromkeys(unsure))   # one camera named twice is one sentence

    def reply(self) -> dict:
        """Everything a form needs, in one answer: what automation may ask for (`ACTIONS`), and per unit what
        it raises and what it can do. A unit whose device never described itself says `can: null` — the
        page offers it with a free field, which is the honest thing to offer for "unknown"."""
        # ONE CAMERA'S SOURCE IS THAT CAMERA'S (the review's tenth round): a source that does not parse, a device row that
        # does not read, raised out of the whole catalogue — the form had no camera at all to offer. That camera is
        # offered with `can: null`, as one whose device never said, and `unread` says why.
        cams = {}
        for u, c in sorted(self.cameras().items(), key=lambda kv: (len(kv[0]), kv[0])):
            try:
                cams[u] = {"name": str(c.get("name", u)), "can": self.device(c)}
            except PARSE_ERRORS as e:
                cams[u] = {"name": str(c.get("name", u)), "can": None, "unread": f"its device cannot be read ({type(e).__name__})"}
        dets = {n: {"cam": str(d.get("cam", "")), "raises": [str(d.get("kind", ""))]}
                for n, d in sorted(self.detectors().items())}
        return {"actions": {f"{s}.{n}": {"need": list(v["need"]), "may": list(v["may"])} for (s, n), v in sorted(ACTIONS.items())},
                "trigger_keys": list(TRIGGER_KEYS), "holder_events": list(HOLDER_EVENTS),
                "vms": cams, "det": dets}


# The whole language, checked. Every message names the thing that is wrong and what would be right: this
# runs while the operator is still looking at what they typed, which is the only moment the answer is cheap.
#
# With a `catalog`, the scenario is checked against the units too — after the language, for the reason the
# platform's check runs before this one: "camera 12 has no relays" is not a sentence to hand somebody whose
# action has no `sub`.
def refuse_scenario(fields: dict, catalog: Catalog | None = None) -> None:
    for t in _dicts(fields.get("when"), "when"):
        bad = [k for k in t if k not in TRIGGER_KEYS]
        if bad:
            raise Refused(f"a trigger has no key {bad[0]!r} — it takes {', '.join(TRIGGER_KEYS)}")
        if not str(t.get("sub", "")) or not str(t.get("kind", "")):
            raise Refused("a trigger names the subsystem it watches and the kind of event: {sub, kind}")
        if "match" in t and not isinstance(t["match"], dict):
            raise Refused("`match` is an object of field: value, compared against the event's fields")

    when, within = fields.get("when") or [], int(fields.get("within") or 0)
    if len(when) > 1 and within <= 0:
        raise Refused("two triggers need `within`: within how many seconds do they count as together")
    if len(when) == 1 and within:
        raise Refused("`within` is the window between triggers; with one trigger there is nothing to window")
    if within > MAX_WITHIN:
        raise Refused(f"`within` is at most {MAX_WITHIN} seconds")

    for a in _dicts(fields.get("then"), "then"):
        key = (str(a.get("sub", "")), str(a.get("action", "")))
        spec = ACTIONS.get(key)
        if spec is None:
            known = ", ".join(f"{s}.{n}" for s, n in sorted(ACTIONS))
            raise Refused(f"this course files {known} — not {key[0] or '?'}.{key[1] or '?'}")
        allowed = {"sub", "action", *spec["need"], *spec["may"]}
        bad = [k for k in a if k not in allowed]
        if bad:
            raise Refused(f"{key[0]}.{key[1]} has no field {bad[0]!r} — it takes {', '.join(sorted(allowed))}")
        missing = [k for k in spec["need"] if a.get(k) in (None, "")]
        if missing:
            raise Refused(f"{key[0]}.{key[1]} needs {missing[0]!r}")

    valid = int(fields.get("valid_for") or 0)
    if valid and not 5 <= valid <= MAX_VALID_FOR:
        raise Refused(f"`valid_for` is between 5 and {MAX_VALID_FOR} seconds — less is shorter than the road from "
                      f"an event to the device, and the request would expire on its way; more is not a command "
                      f"any longer, and the worker holding the device refuses it")

    rate = int(fields.get("rate_per_minute") or 0)
    if rate and not 1 <= rate <= 600:
        raise Refused("`rate_per_minute` is between 1 and 600 — automation without a ceiling can ring")

    if catalog is not None:
        misfit, _ = catalog.check(fields)
        if misfit:
            raise Refused("; ".join(misfit))


# Does this event set off this trigger? The evaluator's half of the language, and it lives beside the
# validation deliberately: two files would drift, and the drift would look like a scenario that never
# fires — the hardest kind of bug to see, because nothing happens.
#
# An event is what the console's merge hands over, and the key names are ITS, not ours: `subsystem`, not
# `sub` (`eventdatabase.py`, the row built in `query`). A trigger says `sub` because that is what an
# operator writes; the comparison reads what the log actually carries. Getting this wrong is invisible in
# a test with a hand-built event and total on a box: the scenario simply never fires.
#
# Matching is equality on strings and nothing else. No ranges, no negation, no substring: each of those is
# a question about what the operator meant, and the answer belongs in another trigger or in another field.
#
# A line carrying `repeats` is the summary of a window the WRITER suppressed (`Suppressor`, М10A урок 12),
# and it never fires. It is not a new observation: the first line of that window was, and it fired this
# scenario already. Acting on the summary too would open the door a second time for one continuous event —
# and would do it worse the longer the storm ran, because the louder the sensor, the more summaries.
# The summary exists for the operator reading the timeline and for whoever reconstructs the incident.
def fires(trigger: dict, event: dict) -> bool:
    if "repeats" in event:
        return False
    if str(trigger.get("sub", "")) != str(event.get("subsystem", "")):
        return False
    if str(trigger.get("kind", "")) != str(event.get("kind", "")):
        return False
    if trigger.get("unit") not in (None, "") and str(trigger["unit"]) != str(event.get("unit", "")):
        return False
    for k, v in (trigger.get("match") or {}).items():
        if str(event.get(k, "")) != str(v):
            return False
    return True


class AutoController(SpecController):
    """The platform's controller over `auto.subsystem.yaml`, plus the one thing
    the platform cannot do: refuse a scenario that says nothing runnable."""

    def __init__(self, vars_: Variables, objects: ObjectStore, capacity: int = 50, wall=time.time,
                 cluster: str | None = None, catalog: Catalog | None = None):
        super().__init__(AUTO_SPEC, vars_, objects, capacity, wall, cluster)
        self.catalog = catalog if catalog is not None else Catalog(vars_)

    # Both doors, because an edit can break a scenario exactly as a create can — and an edit is the likelier
    # of the two: the scenario that runs the site was written months ago and is being adjusted at speed.
    # The platform's check runs FIRST, and the order is not tidiness: it answers "is this JSON, and does it
    # fit", and everything below assumes the answer is yes. Ask what a trigger means before knowing it
    # parsed and the operator gets a sentence about triggers for a missing brace.
    def create(self, fields: dict, **reserved) -> dict:
        self.spec.refuse(fields)
        refuse_scenario(fields, self.catalog)
        return super().create(fields, **reserved)

    def update(self, uid, fields: dict) -> dict:
        row = self.unit(uid)
        if row is None:
            raise Refused(f"no scenario {uid}")
        self.spec.refuse(fields)                    # the patch: shapes and sizes
        refuse_scenario({**row, **fields}, self.catalog)   # the scenario as it WOULD be, not the half being sent
        return super().update(uid, fields)
