"""Footage and events somebody said to keep: `rec/keeps/<id>`, the second of `rec`'s tables."""
# ================================================================================================
# # keeps.py — a keep is an INTERVAL of one camera somebody said to keep
#
# Footage is in volumes, and a volume is a ring: it gives up its oldest minutes when it is full, whatever they
# are. Ten minutes of camera 7 last Tuesday that are evidence go with the rest (the platform review, blocker
# 10; feedback BH). A keep says so: camera, interval, a note, who set it. While the row stands —
#
#   the footage    is COPIED into an incidents volume by the recorder that holds it (`RecWorker.keep_pass`),
#                  out of whichever recorder's door has it, and stays there after the recording's own ring has
#                  moved on. What was copied is an event with its sha256 (`archive.keep.copied`)
#   the events     retention skips the camera's event buckets that overlap it (`vms/resource.kept_buckets`)
#
# …and that is all it promises. It is NOT "never deleted": the incidents volume is a ring too, only one that
# nothing but keeps writes into. When it is full the oldest kept footage goes — and that is an alarm,
# `archive.keep.lost`, not a quiet cut. Evidence that has to outlive the volume is exported; a keep buys the
# time to do it.
#
# The product keeps the same table and the same fields, and carries the footage out to a separate archive the
# same way: its archive is a ring that cannot spare a range, and so is ours now.
#
# THE RECORDINGS ARE WRITTEN INTO THE ROW. A volume knows footage by the recording's name (`7`, `7-cloud`),
# not by the camera; the recording's row says whose it is. Delete the recording and the row is gone — and
# with it the only thing that tied the streams to the camera. So the keep remembers the names it found when it
# was set, and also matches any recording whose row names the camera now.
# ================================================================================================
import json
import math
from dataclasses import dataclass

from w2cplatform.doors import safe_segment
from w2cplatform.rows import Table, finite
from w2cplatform.spec import Refused

SUB = "rec"
TABLE = "keeps"
# The interval is `from` / `to` in the row and at the door — the names every archive door already uses
# (`/timeline`, `/samples`, `/export`, a backfill), and the product's (feedback BQ). It was `since` / `until`, and `until`
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
        # `finite`: a `nan` bound passes no comparison, so such a keep held nothing while it looked set (the seventh pass)
        return cls(id_, str(d.get("cam", "")), finite(d.get("from", d.get("since", 0)) or 0), finite(d.get("to", d.get("until", 0)) or 0),   # `since`/`until`: rows written before the rename (feedback BV)
                   str(d.get("note", "")), str(d.get("by", "")), finite(d.get("at", 0) or 0),
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


# A KEEP WHOSE ROW DOES NOT PARSE IS THAT KEEP'S TROUBLE (the review's seventh pass, part 2). `from: "yesterday"` in
# one keep raised out of `declared`, and `declared` is under the resource's retention of every unit on every server
# (`vms/resource.kept_buckets`: "not knowing what is kept is not nothing is", so nothing was swept and the disks
# filled), under the incidents recorder's copying of every keep, and under each recorder's door. Now it is skipped
# where keeps are listed, counted once until it parses again (`KEEPS`; `keeps_garbled`), logged once — and handed to
# whoever must not read it as "no keep" through `garbled`: as a keep of its camera WHOLE (`whole`, from 0 to
# infinity), which is what not knowing which minutes means. Retention then keeps that camera's buckets and sweeps the
# rest; nothing is copied for it until it is mended (a whole camera is not a range to copy). A row that does not
# even name a camera holds nothing — a keep without a camera is no keep of anything; it is counted and logged.
KEEPS = Table("keep", "its camera is kept whole and nothing is copied for it, until it is mended")


def declared(vars_, garbled: list | None = None) -> list[Keep]:
    """Every keep whose row parses. A store that does not answer RAISES, and the caller must let it: "I could not read
    the keeps" is not "there are none", and a policy that reads it so deletes what it was told to leave. A row that
    does not parse goes into `garbled`, when the caller gives one, as `whole(...)`."""
    out = []
    for path in sorted(vars_.list(f"{SUB}/{TABLE}/")):
        try:
            items, _ = vars_.get(path)                  # a file store's row that is not even JSON raises in the read itself
        except (ValueError, TypeError, KeyError) as e:
            KEEPS.garbled(path, e)
            continue                                    # no camera to hold: counted, and said in the log
        if items:
            id_ = path[len(f"{SUB}/{TABLE}/"):]
            k = KEEPS.read(path, lambda: Keep.from_items(id_, items))
            if k is not None:
                out.append(k)
            elif garbled is not None and str(items.get("cam", "") or ""):
                garbled.append(whole(id_, items))
    return out


def whole(id_: str, items: dict) -> Keep:
    """A keep nobody can read, as a keep of its camera from the start of time to its end."""
    return Keep(id_, str(items.get("cam", "")), 0.0, math.inf, "its row does not parse", str(items.get("by", "")), 0.0,
                tuple(str(r) for r in _names(items.get("recordings"))))


def spans_of(keeps: list[Keep], recording: str, cam: str = "") -> list[tuple[float, float]]:
    """The intervals kept for one recording: named in the keep, or of the keep's camera."""
    return [(k.since, k.until) for k in keeps if recording in k.recordings or (cam and k.cam == cam)]


def spans_of_cam(keeps: list[Keep], cam: str) -> list[tuple[float, float]]:
    return [(k.since, k.until) for k in keeps if k.cam == cam]


def held(spans: list[tuple[float, float]], start: float, end: float) -> bool:
    return any(a < end and start < b for a, b in spans)
