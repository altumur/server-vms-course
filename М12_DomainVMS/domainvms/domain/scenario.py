"""Lesson 12, step 7, and Lesson 16, step 8 — scenarios between cameras, end to end.

A scenario lives in the shared document (Lesson 12):

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
"""
from __future__ import annotations

import json

from .federation import Unreachable
from .ingest import Refused

VALID = 30.0
RATE = 6                               # asks per scenario per minute, the product's default


def _scenarios(settings: dict) -> list[dict]:
    return [sc for sc in settings.get("scenarios", []) if sc.get("enabled", True)]


def _action(then: dict) -> dict:
    return {k: v for k, v in then.items() if k not in ("camera", "within")}


def refusals(settings: dict, crossings) -> list[str]:
    """Scenarios that could never act, each with its reason — checked when the document is WRITTEN (feedback AL),
    so an operator is told, not left with a scenario that silently never fires.

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
    return out


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
            within = float(then.pop("within", VALID))
            if not target or target == self.serial:
                continue                                          # its own automation, not an ask
            if at + within <= now:
                done.append({"target": target, "action": then, "state": "seen after its deadline: not asked"})
                continue
            key, cap = json.dumps(sc, sort_keys=True), int(sc.get("rate_per_minute") or RATE)
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
