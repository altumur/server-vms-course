"""Validation of actions against the target camera's own capabilities."""
from w2cplatform.doors import numeric
from w2cplatform.rows import PARSE_ERRORS

# What one camera may ask another — М10B's `cam.preset` and `cam.output`, and nothing else: an ask is a thing
# a camera DOES, over the poll it holds, and the recording of another camera is not one (that is the recorder's
# cluster's automation, М10B Lesson 25). `arg` is the preset's number, or the relay's port.
ACTIONS = {"preset": "the preset's number", "output": "the relay's port"}


def misfit(who: str, can: dict, action: dict) -> str | None:
    """Why a camera that described itself as `can` cannot do `action` ({action, arg}) — None when it can. The
    camera checks its capabilities when the ask arrives (`DeviceCluster.perform`)."""
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


