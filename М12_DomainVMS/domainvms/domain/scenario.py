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
    enabled     false: the scenario is kept and does nothing
"""
from __future__ import annotations

from .federation import Unreachable
from .ingest import Refused

VALID = 30.0


def _scenarios(settings: dict) -> list[dict]:
    return [sc for sc in settings.get("scenarios", []) if sc.get("enabled", True)]


def pairs(settings: dict) -> list[dict]:
    """What the domain's book of asks is built from: every (trigger camera, target camera) a scenario ties."""
    out, seen = [], set()
    for sc in _scenarios(settings):
        a, b = str(sc.get("when", {}).get("camera", "")), str(sc.get("then", {}).get("camera", ""))
        if a and b and a != b and (a, b) not in seen:
            seen.add((a, b))
            out.append({"trigger": a, "target": b})
    return out


class Scenarios:
    """The camera's side. `shared` is its `SharedView` — the document its agent took and verified; `asker` its
    `Asker`. `on_event(kind)` is called where the camera's analytics raise an event."""

    def __init__(self, serial: str, shared, asker):
        self.serial, self.shared, self.asker = str(serial), shared, asker

    def on_event(self, kind: str) -> list[dict]:
        done = []
        for sc in _scenarios(self.shared.settings()):
            when, then = sc.get("when", {}), dict(sc.get("then", {}))
            if str(when.get("camera")) != self.serial or when.get("kind") != kind:
                continue
            target = str(then.pop("camera", ""))
            within = float(then.pop("within", VALID))
            if not target or target == self.serial:
                continue                                          # its own automation, not an ask
            try:
                left = self.asker.ask(target, then, within)
            except (Refused, Unreachable) as e:
                done.append({"target": target, "action": then, "state": f"not asked: {e}"})
                continue
            if left is None:
                done.append({"target": target, "action": then, "state": "no ingest answered: not asked"})
            else:
                ing, aid = left
                done.append({"target": target, "action": then, "state": "asked", "ingest": ing, "ask": aid})
        return done
