"""Lesson 12, step 7, and Lesson 16, step 8 — scenarios between cameras, end to end.

A scenario lives in the shared document (Lesson 12), as `auto`'s document there — `settings.shared.auto.scenarios`,
declared in `auto.subsystem.yaml` (`domain.shared`) with the schema the signer checks it by:

    {"when": {"camera": "SN2", "kind": "motion"},
     "then": {"camera": "SN5", "action": "preset", "arg": 3, "within": 10}}

Two sides read it. The DOMAIN turns each scenario that ties one camera to ANOTHER into a right to ask — the
book of asks (`publish_asks`), built on the domain's pass (`domain/books.py`). The CAMERA whose event it is
reads its own verified copy of the document and, on that event, leaves the ask at an ingest its book names
(`Asker`). A scenario whose action is on the same camera is that camera's own automation (М10B Lesson 25)
and is not an ask.

    within      the ask's deadline, seconds from the event; the default is the product's `valid_until` of a
                request — 30 s. After it the ask dies, answered "expired"
    rate_per_minute  the ceiling, as the product's automation has it (default 6): a scenario that fires more
                often than that in a minute does not ask — a gust through the leaves is one preset, not twenty.
                Kept in the camera's memory; a reboot forgets it, as the product's does
    enabled     false: the scenario is kept and does nothing

The action a scenario names is what the domain writes into the token to ask (`acts`): the ingest refuses any
other, so a camera — or whoever holds its token — can ask for preset 3 and nothing else.

What each camera raises and can be asked to do is its own word — `can` in its heartbeat (М10B Lesson 25: the
holder of a device is the one that knows it). The VMS's domain worker checks every scenario against it on each
pass over the books (`refusals`): the trigger must raise the kind, the target must be able to do the action — one
that cannot is named on every pass, and the camera refuses its ask by the same rule (`misfit`). The signer checks
only what a scenario may BE (the schema): the
platform asks no subsystem's code when the document is written. A camera that has not said is named on every pass
(`unchecked`), and the page builds its form from `catalog`, so an operator picks a kind the gate camera raises and a
preset the yard camera has.
"""
from __future__ import annotations

import json

from w2cplatform.doors import numeric
from w2cplatform.rows import PARSE_ERRORS, Table, finite

from w2cplatform.domain.federation import Unreachable
from .ingest import ASK_DEADLINE_MAX, Refused

VALID = 30.0
RATE = 6                               # asks per scenario per minute, the product's default


# What one camera may ask another — М10B's `vms.preset` and `vms.output`, and nothing else: an ask is a thing
# a camera DOES, over the poll it holds, and the recording of another camera is not one (that is the recorder's
# cluster's automation, М10B Lesson 25). `arg` is the preset's number, or the relay's port.
ACTIONS = {"preset": "the preset's number", "output": "the relay's port"}


def misfit(who: str, can: dict, action: dict) -> str | None:
    """Why a camera that described itself as `can` cannot do `action` ({action, arg}) — None when it can. The
    domain says it when the scenario is written, the camera when the ask arrives (`DeviceCluster.perform`)."""
    name, arg = str(action.get("action", "")), str(action.get("arg", ""))
    if name == "preset":
        n = _count(can, "presets")
        if not can.get("ptz"):
            return f"{who} has no telemetry: it cannot go to a preset"
        if n and not 1 <= (numeric(arg) or 0) <= n:     # `doors.numeric`: `"²".isdigit()` and `int` raised (the tenth pass)
            return f"{who} has {n} preset(s), not {arg}"
        return None
    if name == "output":
        r = _count(can, "relays")
        if not r:
            return f"{who} has no relays"
        if not 1 <= (numeric(arg) or 0) <= r:
            return f"{who} has {r} relay(s), not port {arg}"
        return None
    return f"{who} cannot be asked {name!r}: one camera asks another for {' or '.join(ACTIONS)}"


def _count(can: dict, key: str) -> int:
    """How many presets or relays a camera said it has — 0, "said none", when what it said is not a whole number
    (the review's eighth pass, minor: `int("five")` raised out of the pass over the books)."""
    try:
        return max(0, int(can.get(key) or 0))
    except PARSE_ERRORS:
        return 0


def _within(then: dict) -> float:
    """A scenario's `within`: seconds, finite, more than 0 and at most `ASK_DEADLINE_MAX` — what an ingest takes."""
    w = finite(then.get("within", VALID))
    if not 0 < w <= ASK_DEADLINE_MAX:
        raise ValueError(f"within is {w:g} s; it is more than 0 and at most {ASK_DEADLINE_MAX:.0f}")
    return w


# ONE SCENARIO THAT IS NOT ONE IS THAT SCENARIO'S, COUNTED (the product's cross-check of vmsserver's eleventh review): a
# scenario that is not an object, or whose `when` or `then` is not one, raised `AttributeError` out of every reader of
# the document — the book of asks for every camera (`pairs`), the refusals, a camera's every event — or, read past, was
# gone without a word. Each is skipped now, counted once until it is mended (`SCENARIOS`, in the console's `/healthz`
# beside the other things others wrote that do not parse), logged once; the others are read.
SCENARIOS = Table("scenario", "skipped — the other scenarios are read", "scenario of the shared settings")


WHERE = "settings/shared/auto/scenarios"   # `auto`'s document in the shared settings (`auto.subsystem.yaml`)


def _scenarios(settings: dict) -> list[dict]:
    held = (settings.get("shared") or {}).get("auto") if isinstance(settings.get("shared"), dict) else None
    scs = (held.get("scenarios") if isinstance(held, dict) else None) or []
    if not isinstance(scs, list):
        SCENARIOS.garbled(WHERE, TypeError(f"the scenarios are a list, not {type(scs).__name__}"))
        return []
    SCENARIOS.parsed(WHERE)
    out = []
    for i, sc in enumerate(scs):
        key = f"{WHERE}/{i}"
        if not isinstance(sc, dict) or not all(isinstance(sc.get(k, {}), dict) for k in ("when", "then")):
            SCENARIOS.garbled(key, TypeError("a scenario is an object with a `when` and a `then` that are objects"))
            continue
        SCENARIOS.parsed(key)
        if sc.get("enabled", True):
            out.append(sc)
    return out


def _action(then: dict) -> dict:
    return {k: v for k, v in then.items() if k not in ("camera", "within")}


def refusals(settings: dict, crossings) -> list[str]:
    """Scenarios that could never act, each with its reason — said on every pass over the books (feedback AL: an
    operator is told, not left with a scenario that silently never fires). Not when the document is written: the
    signer that signs it asks no subsystem's code (ADR-0032), and checks a scenario's shape by its schema alone.

    The two ends ask different things. The TARGET must hold a poll: an ask reaches a camera through the poll it
    keeps open to an ingest, every member camera holds one, and a camera that is not a member (a server
    cluster's camera without the platform, a serial nobody has seen) holds none. The TRIGGER only has to be
    known to the domain: its event is read where its cluster reads events — on a member camera by the camera
    itself, on a server cluster's camera by that cluster's automation, over the cluster's merged event log —
    and the book of asks goes to that cluster either way. So a server cluster's camera without the platform can
    be a trigger, and cannot be a target (the product's rule, feedback on notes 10b and 12)."""
    out = []
    for sc in _scenarios(settings):
        a, b = str(sc.get("when", {}).get("camera", "")), str(sc.get("then", {}).get("camera", ""))
        if not a or not b or a == b:
            continue
        if crossings.view.last_known(a) is None:
            out.append(f"camera {a} (trigger) is not known to the domain: its events are read in its own cluster, "
                       f"and no member cluster of this domain has reported it")
        if crossings.polled_at(b) is None:
            out.append(f"camera {b} (target) polls nothing: an ask travels on the poll a member camera holds open "
                       f"to an ingest, and {b} is not a member camera of this domain, or has never reported")
        # …and what each end says it can (Lesson 16, step 8). The trigger's word counts only for a camera of ours:
        # a server cluster's camera is read over its cluster's merged log, where the detectors on it write too,
        # and its holder's `can` knows the device, not the detectors.
        kind, action = str(sc.get("when", {}).get("kind", "")), _action(sc.get("then", {}))
        can_a = crossings.can_of(a) if a in crossings.members() else None
        if can_a is not None and kind not in can_a.get("events", []):
            out.append(f"camera {a} (trigger) does not raise {kind!r} — it raises {', '.join(can_a.get('events', []))}")
        try:
            _within(sc.get("then", {}))
        except PARSE_ERRORS as e:
            out.append(f"the scenario from {a} to {b}: {e}")
        can_b = crossings.can_of(b)
        why = (misfit(f"camera {b} (target)", can_b, action) if can_b is not None else
               None if str(action.get("action", "")) in ACTIONS else misfit(f"camera {b} (target)", {}, action))
        if why:
            out.append(why)
    return list(dict.fromkeys(out))


def unchecked(settings: dict, crossings) -> list[str]:
    """What the domain accepted without being able to vouch for it: an end that has not said what it raises or
    can do. Said on every pass, like a refusal — and gone the pass after the camera describes itself."""
    out, members = [], crossings.members()
    for sc in _scenarios(settings):
        a, b = str(sc.get("when", {}).get("camera", "")), str(sc.get("then", {}).get("camera", ""))
        if not a or not b or a == b:
            continue
        kind, action = str(sc.get("when", {}).get("kind", "")), _action(sc.get("then", {}))
        if a in members and crossings.can_of(a) is None:
            out.append(f"camera {a} (trigger) has not said what it raises: {kind!r} is not checked")
        elif a not in members and crossings.view.last_known(a) is not None:
            out.append(f"camera {a} (trigger) is read over its cluster's merged log: {kind!r} is not checked here")
        if crossings.polled_at(b) is not None and crossings.can_of(b) is None:
            out.append(f"camera {b} (target) has not said what it can do: {action.get('action')!r} is not checked")
    return list(dict.fromkeys(out))


def catalog(crossings) -> dict:
    """What a form needs to offer a scenario between cameras: what one camera may ask another, and per camera
    the domain knows — its cluster, what it said it raises and can do (`can`, None if it has not), and whether it
    can be asked at all (it holds a poll)."""
    cams = {}
    for cluster, rows in sorted(crossings.view.configured.items()):
        for row in rows:
            ref = str(row.get("ref", ""))
            if ref:
                cams[ref] = {"cluster": cluster, "name": row.get("name", ref), "can": crossings.can_of(ref),
                             "asked": crossings.polled_at(ref) is not None}
    return {"actions": dict(ACTIONS), "cameras": cams}


def pairs(settings: dict) -> list[dict]:
    """What the domain's book of asks is built from: every (trigger camera, target camera) a scenario ties, with
    the actions the scenarios between them name."""
    out: dict[tuple, list] = {}
    for sc in _scenarios(settings):
        a, b = str(sc.get("when", {}).get("camera", "")), str(sc.get("then", {}).get("camera", ""))
        if a and b and a != b:
            acts = out.setdefault((a, b), [])
            if _action(sc["then"]) not in acts:
                acts.append(_action(sc["then"]))
    return [{"trigger": a, "target": b, "actions": acts} for (a, b), acts in out.items()]


class Scenarios:
    """The trigger's side — the camera itself, or, for a server cluster's camera, that cluster's automation, with
    the cluster's copy of the document and of the book of asks. `shared` is a `SharedView` — the document its
    agent took and verified; `asker` an `Asker`. `on_event(kind, event)` is called where the camera's analytics raise an event — a hook on the event
    itself, which is why the road is milliseconds. A scenario that reads the merged event log instead (the
    product's automation) adds the log's tail interval: seconds (feedback AK).

    `event`: the row, when there is one. `ts` — when it happened: the deadline counts from THAT, not from when
    the event became visible, and one seen after its deadline asks nothing. `repeats` — the summary a storm's
    suppression writes when its window closes (М10A Lesson 12): it reports on a first row that already fired,
    and firing on it would act twice for one lasting event."""

    def __init__(self, serial: str, shared, asker):
        self.serial, self.shared, self.asker = str(serial), shared, asker
        self.fired: dict[str, list[float]] = {}                   # per scenario: when it asked in the last minute

    def on_event(self, kind: str, event: dict | None = None) -> list[dict]:
        done, now = [], self.asker.clock()
        if event and event.get("repeats"):
            return []                                             # a suppression summary: not an event (AK)
        at = float(event["ts"]) if event and event.get("ts") is not None else now
        for sc in _scenarios(self.shared.settings()):
            when, then = sc.get("when", {}), dict(sc.get("then", {}))
            if str(when.get("camera")) != self.serial or when.get("kind") != kind:
                continue
            target = str(then.pop("camera", ""))
            if not target or target == self.serial:
                continue                                          # its own automation, not an ask
            try:                                                  # past the schema, a `within` out of range is that
                within = _within(then)                            # scenario's trouble, said, not the event's
                then.pop("within", None)
                cap = int(sc.get("rate_per_minute") or RATE)
            except PARSE_ERRORS as e:
                done.append({"target": target, "action": then, "state": f"not asked: {e}"})
                continue
            if at + within <= now:
                done.append({"target": target, "action": then, "state": "seen after its deadline: not asked"})
                continue
            key = json.dumps(sc, sort_keys=True)
            recent = self.fired[key] = [t for t in self.fired.get(key, []) if now - t < 60.0]
            if len(recent) >= cap:
                done.append({"target": target, "action": then, "state": f"over its ceiling of {cap}/min: not asked"})
                continue
            recent.append(now)
            try:
                left = self.asker.ask(target, then, at + within - now)
            except (Refused, Unreachable) as e:
                done.append({"target": target, "action": then, "state": f"not asked: {e}"})
                continue
            if left is None:
                done.append({"target": target, "action": then, "state": "no ingest answered: not asked"})
            else:
                ing, aid = left
                done.append({"target": target, "action": then, "state": "asked", "ingest": ing, "ask": aid,
                             "deadline": at + within})
        return done
