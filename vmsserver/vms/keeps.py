"""Footage and events somebody said to keep: `rec/keeps/<id>`, the second of `rec`'s tables."""
# ================================================================================================
# # keeps.py — a keep is an INTERVAL of one camera that the policies leave alone
#
# Retention by days deletes what is old, and the watermark deletes what is in the way. Neither knows that
# ten minutes of camera 7 last Tuesday are evidence (the platform review, blocker 10; feedback BH). A keep
# says so: camera, interval, a note, who set it. While the row stands —
#
#   retention by days     skips the segments and the event buckets that overlap it
#   the watermark         cuts everything else first (`vms/space.py`)
#
# …and that is all it promises. It is NOT "never deleted". A disk is a ring: when it is full and everything
# that is not kept is already on the floor, the oldest KEPT footage goes, oldest first — counted, logged and
# written into the deletions journal under its own reason. The alternative is a recorder that stops
# recording today to protect last month, and nobody chose that. Evidence that has to outlive the disk is
# exported; a keep buys the time to do it.
#
# The product keeps the same table and the same fields, and carries the footage out to a separate archive
# instead of holding it in place: its archive is a ring that cannot spare a range. Ours is a directory with
# a manifest, and can.
#
# THE RECORDINGS ARE WRITTEN INTO THE ROW. An archive knows footage by the recording's name (`7`, `7-cloud`),
# not by the camera; the recording's row says whose it is. Delete the recording and the row is gone — and
# with it the only thing that tied the tree to the camera. So the keep remembers the names it found when it
# was set, and also matches any recording whose row names the camera now.
# ================================================================================================
import json
from dataclasses import dataclass

from w2cplatform.doors import safe_segment
from w2cplatform.spec import Refused

SUB = "rec"
TABLE = "keeps"
# The interval is `from` / `to` in the row and at the door — the names every archive door already uses
# (`/timeline`, `/segment`, a backfill), and the product's (feedback BQ). It was `since` / `until`, and `until`
# on a recording already means something else: how long a recording made on request goes on.
FIELDS = ("cam", "from", "to", "note")
MAX_NOTE = 500


@dataclass(frozen=True)
class Keep:
    id: str
    cam: str
    since: float                  # unix seconds
    until: float
    note: str = ""
    by: str = ""                  # who set it
    at: float = 0.0               # when
    recordings: tuple = ()        # the names of the camera's recordings when it was set

    @classmethod
    def from_items(cls, id_: str, d: dict) -> "Keep":
        return cls(id_, str(d.get("cam", "")), float(d.get("from", d.get("since", 0)) or 0), float(d.get("to", d.get("until", 0)) or 0),   # `since`/`until`: rows written before the rename (feedback BV)
                   str(d.get("note", "")), str(d.get("by", "")), float(d.get("at", 0) or 0),
                   tuple(str(r) for r in _names(d.get("recordings"))))

    def to_items(self) -> dict:
        return {"cam": self.cam, "from": self.since, "to": self.until, "note": self.note, "by": self.by,
                "at": self.at, "recordings": json.dumps(list(self.recordings))}

    def shown(self) -> dict:
        """The row as a console answers it: the recordings as a list."""
        return {"id": self.id, **self.to_items(), "recordings": list(self.recordings)}


# A row's values are strings, so the list is JSON in one of them. A name may hold a comma; it may not hold
# a quote that JSON cannot escape.
def _names(raw) -> list:
    if isinstance(raw, (list, tuple)):
        return list(raw)
    try:
        out = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    return out if isinstance(out, list) else []


def key(id_: str) -> str:
    return f"{SUB}/{TABLE}/{id_}"


def refuse(fields: dict) -> None:
    unknown = [k for k in fields if k not in FIELDS]
    if unknown:
        raise Refused(f"a keep has no field {unknown[0]!r}")
    cam = str(fields.get("cam", "") or "")
    if not cam or not safe_segment(cam):
        raise Refused("a keep names a camera")
    try:
        since, until = float(fields.get("from")), float(fields.get("to"))
    except (TypeError, ValueError):
        raise Refused("a keep is an interval: `from` and `to`, unix seconds") from None
    if not 0 < since < until:
        raise Refused("a keep's interval ends after it starts")
    if len(str(fields.get("note", ""))) > MAX_NOTE:
        raise Refused(f"a note is at most {MAX_NOTE} characters")


# The id is the interval: `<cam>-<since>-<until>`, in whole seconds. A retried POST writes the same row, and
# two people keeping the same ten minutes keep them once.
def write(vars_, fields: dict, recordings: list, by: str, now: float) -> Keep:
    refuse(fields)
    cam, since, until = str(fields["cam"]), float(fields["from"]), float(fields["to"])
    k = Keep(f"{cam}-{int(since)}-{int(until)}", cam, since, until, str(fields.get("note", "")), by, now,
             tuple(sorted(str(r) for r in recordings)))
    _, idx = vars_.get(key(k.id))
    vars_.put(key(k.id), k.to_items(), cas=idx)
    return k


def delete(vars_, id_: str) -> None:
    vars_.delete(key(id_))


def declared(vars_) -> list[Keep]:
    """Every keep. A store that does not answer RAISES, and the caller must let it: "I could not read the
    keeps" is not "there are none", and a policy that reads it so deletes what it was told to leave."""
    out = []
    for path in sorted(vars_.list(f"{SUB}/{TABLE}/")):
        items, _ = vars_.get(path)
        if items:
            out.append(Keep.from_items(path[len(f"{SUB}/{TABLE}/"):], items))
    return out


def spans_of(keeps: list[Keep], recording: str, cam: str = "") -> list[tuple[float, float]]:
    """The intervals kept for one recording: named in the keep, or of the keep's camera."""
    return [(k.since, k.until) for k in keeps if recording in k.recordings or (cam and k.cam == cam)]


def spans_of_cam(keeps: list[Keep], cam: str) -> list[tuple[float, float]]:
    return [(k.since, k.until) for k in keeps if k.cam == cam]


def held(spans: list[tuple[float, float]], start: float, end: float) -> bool:
    return any(a < end and start < b for a, b in spans)
