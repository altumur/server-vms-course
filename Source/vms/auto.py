"""The scenario as data: what a trigger may say, what an action may ask for, and the refusal the evaluator says
of a scenario it cannot run."""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # auto.py — the scenario language: its catalogue, the check against the devices, the match
#
# **Role in the module.** `auto.subsystem.yaml` says a scenario has a `when`, a `within` and a `then`, and since the
# boundary's step 6 it says what their SHAPE may be — JSON Schema on each field (the owner's decision 3) — which the
# platform checks at the door for every writer, in the schema's words. It was a controller of the VMS's own here
# (`AutoController`, `refuse_scenario`), and a hook in the platform's console is what the boundary takes away. What no
# schema of one field can say is this file's, and the evaluator's to act on: two triggers need `within` and one
# refuses it (`refusal`), and what a scenario asks of a device the device can do (`Catalog.check`). A scenario that
# fails either is REFUSED by its evaluator — not fired, `refused` with why in its heartbeat (`AutoWorker`).
#
# **Why the language is fixed and not an expression.** An expression language is an interpreter: a parser,
# a grammar, precedence, errors at evaluation time, and a page that cannot offer a form because it cannot
# know what the operator will type. A fixed shape is a schema, a form a page can build from it, and every refusal of
# the shape arriving while somebody is still looking at what they wrote. When the shape stops fitting, the honest
# move is another field — not a parser.
#
# **The catalogue is the boundary.** `ACTIONS` names the pairs `(subsystem, action)` this course knows how
# to file a request for, with the fields each one needs — the same five the spec's schema of `then` allows. It is
# a statement about what AUTOMATION may ask for, which is narrower than what those subsystems can do.
#
# **The catalogue is not the device.** `ACTIONS` says preset is a thing automation may ask for; it does not
# say camera 12 has a telemetry, or that it raises `io.input`, or that detector `7` exists. That is a FACT,
# and only the holder of the device knows it: it writes it in `vms/devices/<device>` (`config.describe`).
# `Catalog` reads those rows beside the operator's own (`vms/cameras/*`, `det/units/*`), and the evaluator checks a
# scenario against both on its pass. A misfit is refused there; a scenario the fact cannot vouch for yet (the device
# has never been held) runs and is named on every pass.
#
# ## Public API
# - `TRIGGER_KEYS`, `ACTIONS` — the language, as data.
# - `Catalog(vars_)` — what the units say and do; `check(fields) -> (misfits, unchecked)`; `reply()` — the whole of it.
# - `refusal(fields, catalog=None) -> [why]` — what the evaluator refuses a scenario for, `[]` when it may run.
# - `fires(trigger, event)` — does this event match this trigger. The evaluator's half of the language,
#   here beside the validation so the two cannot drift.
# ================================================================================================
from __future__ import annotations

from w2cplatform.doors import numeric, unit_ref
from w2cplatform.rows import PARSE_ERRORS, Table
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

# A scenario may not ask for the world. The ceiling is on the SHAPE — how many triggers, how long a window — because a
# scenario with forty triggers and an hour-long window is a query over the whole log run every pass, and it would be
# the operator's own console that got slow. The numbers are the spec's schema's (`auto.subsystem.yaml`: `maxItems`,
# `maximum`); these say them for the code that reads a scenario, and `test_auto_spec` holds the two to one another.
MAX_TRIGGERS = 4
MAX_WITHIN = 3600
MAX_VALID_FOR = 600          # what a holder accepts: `VmsWorker.MAX_VALID` (a command's deadline is near)
MAX_ACTIONS = 4


# What the units of this cluster can say and do — the operator's rows for what EXISTS, the holders' rows for
# what it IS. Read from the store on every question: a scenario is written seldom and checked once a pass,
# and a cache here would be a second copy of the rows to keep right.
#
# Two subsystems describe their units, and that is where the check stops. A camera (`vms`) raises what its
# device posts plus what its holder says about every unit (`HOLDER_EVENTS`); a detector (`det`) raises its
# `kind` and nothing else, and its name is `<cam>-<kind>` — the trigger `{sub: det, unit: "7"}` this lesson
# first printed would never have fired, and nothing said so. Any other subsystem's events are not checked,
# and the scenario is told that rather than passed as if they were.
#
# ONE ROW AT A TIME (the review's twelfth pass, major 20; and the product's cross-check: one unreadable row withdrew every
# scenario). The rows were read bare: one torn camera file raised out of `GET /auto/catalog` (the connection dropped),
# out of every `POST /auto/scenarios` (500), and out of the evaluator's check of EVERY scenario it holds, each pass.
# Each row is read through `_row` now: one the store cannot read, or that is not a map, is left out — counted once in
# `CATALOG` — and named (`unread`): a scenario that names it is not refused for it, it is "not checked" and says so;
# the catalogue offers the camera with `can: null` and the reason.
CATALOG = Table("catalog", "left out of the automation catalogue until it reads again", "row")


class Catalog:
    def __init__(self, vars_: Variables):
        self.vars = vars_
        self.unread: dict[str, str] = {}             # key -> why, for the rows the last reads could not read

    def _row(self, key: str) -> dict | None:
        try:
            it, _ = self.vars.get(key)
            if it is not None and not isinstance(it, dict):
                raise TypeError(f"not a map but {type(it).__name__}")
        except PARSE_ERRORS as e:                    # `Garbled` from the store is a `ValueError` too
            CATALOG.garbled(key, e)
            self.unread[key] = f"its row cannot be read ({type(e).__name__})"
            return None
        CATALOG.parsed(key)
        self.unread.pop(key, None)
        return it if it and it.get("deleted") != "true" else None

    def camera(self, unit) -> dict | None:
        return self._row(VMS_SPEC.sub.config(VMS_SPEC.rows, str(unit)))

    # Whether this camera's row is there and cannot be read — after `camera` said None.
    def camera_unread(self, unit) -> str:
        return self.unread.get(VMS_SPEC.sub.config(VMS_SPEC.rows, str(unit)), "")

    def device(self, cam: dict) -> dict | None:
        if not cam.get("source"):
            return None
        it, _ = self.vars.get(VMS_SPEC.sub.config(DEVICES, device_of(str(cam["source"]))))
        return parse_device_row(it)

    # …and asked from a check: a device row or a source that does not read is that camera's "not said yet".
    def _device_or_none(self, cam: dict) -> dict | None:
        try:
            return self.device(cam)
        except PARSE_ERRORS:
            return None

    def _rows(self, prefix: str) -> dict[str, dict]:
        out = {}
        for key in self.vars.list(prefix):
            it = self._row(key)
            if it is not None:
                out[key.rsplit("/", 1)[1]] = it
        return out

    def detectors(self) -> dict[str, dict]:
        return self._rows(DET_SPEC.sub.config(DET_SPEC.rows, ""))

    def recordings_of(self, cam: str, rec: str = "") -> list[str]:
        from .config import REC_SPEC
        out = [k for k, it in self._rows(REC_SPEC.sub.config(REC_SPEC.rows, "")).items() if str(it.get("cam", k)) == cam]
        return [r for r in out if not rec or r == rec]

    def cameras(self) -> dict[str, dict]:
        return self._rows(VMS_SPEC.sub.config(VMS_SPEC.rows, ""))

    # The cameras whose rows are there and cannot be read, by id — what `cameras()` left out.
    def cameras_unread(self) -> dict[str, str]:
        prefix = VMS_SPEC.sub.config(VMS_SPEC.rows, "")
        return {k[len(prefix):]: why for k, why in self.unread.items() if k.startswith(prefix)}

    # -- one trigger ------------------------------------------------------------------------------
    def _trigger(self, t: dict, misfit: list, unsure: list) -> None:
        sub, kind, unit = str(t.get("sub", "")), str(t.get("kind", "")), str(t.get("unit") or "")
        if sub == VMS_SPEC.name:
            cams = {unit: self.camera(unit)} if unit else self.cameras()
            if unit and cams[unit] is None:
                if self.camera_unread(unit):
                    unsure.append(f"camera {unit}: {self.camera_unread(unit)} — {kind!r} is not checked")
                else:
                    misfit.append(f"there is no camera {unit}")
                return
            if kind in HOLDER_EVENTS:
                return                                   # every held unit raises these: nothing to ask a device
            if not unit and self.cameras_unread():
                unsure.append(f"camera(s) {', '.join(sorted(self.cameras_unread()))} cannot be read: what they raise "
                              f"is not checked")
            descs = {u: self._device_or_none(c) for u, c in cams.items()}
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
                if self.camera_unread(a.get("cam")):
                    unsure.append(f"camera {a.get('cam')}: {self.camera_unread(a.get('cam'))} — rec.record is not checked")
                else:
                    misfit.append(f"there is no camera {a.get('cam')} to record")
            return
        if sub == DET_SPEC.name:
            cam = str(a.get("cam", ""))
            if self.camera(cam) is None:
                if self.camera_unread(cam):
                    unsure.append(f"camera {cam}: {self.camera_unread(cam)} — det.{name} is not checked")
                else:
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
            if self.camera_unread(unit):
                unsure.append(f"camera {unit}: {self.camera_unread(unit)} — vms.{name} is not checked")
            else:
                misfit.append(f"there is no camera {unit}")
            return
        d = self._device_or_none(cam)
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
        for u, why in self.cameras_unread().items():  # a row that does not read: offered, with why (major 20)
            cams[u] = {"name": u, "can": None, "unread": why}
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
# WHAT A SCENARIO MAY BE IS ITS SPEC'S, WHAT IT MAY DO IS ITS EVALUATOR'S (the boundary's step 6, the owner's decision 3).
# The shape — which keys a trigger takes, the five actions and what each needs, the bounds of `within`, `valid_for`,
# `rate_per_minute` — is JSON Schema in `auto.subsystem.yaml`, checked by the platform at the door for every writer. It
# was `refuse_scenario`, run by a controller of the VMS's own (`AutoController`) before the row was written. What no
# schema of one field can say is said here, and the evaluator refuses the scenario with it in its heartbeat
# (`AutoWorker.reconcile_once`): two triggers need `within`, one refuses it; and what the scenario asks of a device the
# device can do (`Catalog.check`, its misfits).
def refusal(fields: dict, catalog: Catalog | None = None) -> list[str]:
    """Why the evaluator does not run this scenario — `[]` when it may."""
    out = []
    when, within = fields.get("when") or [], int(fields.get("within") or 0)
    if isinstance(when, list) and len(when) > 1 and within <= 0:
        out.append("two triggers need `within`: within how many seconds do they count as together")
    if isinstance(when, list) and len(when) == 1 and within:
        out.append("`within` is the window between triggers; with one trigger there is nothing to window")
    if catalog is not None:
        out += catalog.check(fields)[0]
    return out


def fires(trigger: dict, event: dict) -> bool:
    if "repeats" in event:
        return False
    if str(trigger.get("sub", "")) != str(event.get("subsystem", "")):
        return False
    if str(trigger.get("kind", "")) != str(event.get("kind", "")):
        return False
    if trigger.get("unit") not in (None, "") and unit_ref(trigger.get("sub", ""), trigger["unit"]) != str(event.get("unit", "")):
        return False                                     # the trigger's unit, inside its subsystem; the line's is `<sub>/<id>`
    for k, v in (trigger.get("match") or {}).items():
        if str(event.get(k, "")) != str(v):
            return False
    return True
