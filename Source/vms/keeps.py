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
#   the events     retention skips the camera's event buckets that overlap it — its spec's `holds:`, which every
#                  resource reads itself (`w2cplatform/holds.py`; the boundary's step 6)
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

from w2cplatform.doors import safe_segment, unnamable
from w2cplatform.rows import PARSE_ERRORS, Table, finite, number
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
    garbled: bool = False         # its interval did not parse whole: held as far as it reads (`as_far_as_read`)

    # Only the INTERVAL can make a keep unreadable (the review's eighth pass, part 4): `at` — when it was set — is
    # metadata, and `at: "yesterday"` made the whole keep garbled, its camera held from the start of time to its end.
    # A word there is read as not said (0), counted once as a field (`rows.number`), and the keep holds what it says.
    @classmethod
    def from_items(cls, id_: str, d: dict) -> "Keep":
        # `finite`: a `nan` bound passes no comparison, so such a keep held nothing while it looked set (the seventh pass)
        return cls(id_, str(d.get("cam", "")), finite(d.get("from", d.get("since", 0)) or 0), finite(d.get("to", d.get("until", 0)) or 0),   # `since`/`until`: rows written before the rename (feedback BV)
                   str(d.get("note", "")), str(d.get("by", "")), number(f"{key(id_)}#at", d.get("at") or None, float, 0.0),
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
    text = str(raw or "").strip()
    if not text.startswith("["):                     # the spec's list field: its names joined by `,` (`Field.to_item`)
        return [x for x in text.split(",") if x]
    try:
        out = json.loads(text)
    except PARSE_ERRORS:                             # nested past what JSON reads too: the list unread, the keep stands (the tenth round)
        return []
    return out if isinstance(out, list) else []


def key(id_: str) -> str:
    return f"{SUB}/{TABLE}/{id_}"


# SET BY THE PLATFORM'S RULES (the boundary's step 6): what a keep row may be — a camera, an interval, a note of at
# most 500 characters, named by its camera and its interval, stamped with who and when — is `tables.keeps` in
# rec.subsystem.yaml, and the platform's console writes it (`tables.write_row`); a keep holds at most a week of events on
# the resources (`holds.longest`). The rules were here (`refuse`), called by the VMS's route on the console. This is the
# same write for the VMS's own code and its tests. Whose recordings it
# holds is its camera's now, and the names of its recordings when it was set if whoever set it said them (`recordings`).
def write(vars_, fields: dict, recordings: list | None = None, by: str = "", now: float = 0.0) -> Keep:
    from w2cplatform.tables import write_row
    from .config import REC_SPEC
    if recordings and "recordings" not in fields:
        fields = {**fields, "recordings": sorted(str(r) for r in recordings)}
    name, items = write_row(REC_SPEC, TABLE, vars_, fields, by, now)
    return Keep.from_items(name, items)


def delete(vars_, id_: str) -> None:
    from w2cplatform.tables import delete_row
    from .config import REC_SPEC
    delete_row(REC_SPEC, TABLE, vars_, id_)


KEEPS = Table("keep", "its camera is kept as far as its interval reads, units of no one camera are not held by it, and "
                      "nothing is copied for it, until it is mended")


def declared(vars_, garbled: list | None = None) -> list[Keep]:
    """Every keep whose row parses. A store that does not answer RAISES, and the caller must let it: "I could not read
    the keeps" is not "there are none", and a policy that reads it so deletes what it was told to leave. A row that
    does not parse goes into `garbled`, when the caller gives one, as `as_far_as_read(...)`."""
    out = []
    for path in sorted(vars_.list(f"{SUB}/{TABLE}/")):
        try:
            items, _ = vars_.get(path)                  # a file store's row that is not even JSON raises in the read itself
        except PARSE_ERRORS as e:                       # …a row nested past what JSON reads too (`RecursionError`)
            KEEPS.garbled(path, e)
            continue                                    # no camera to hold: counted, and said in the log
        if isinstance(items, dict) and items:
            id_ = path[len(f"{SUB}/{TABLE}/"):]
            k = KEEPS.read(path, lambda: Keep.from_items(id_, items))
            if k is not None:
                out.append(k)
            elif garbled is not None and str(items.get("cam", "") or ""):
                garbled.append(as_far_as_read(id_, items))
    return out


def as_far_as_read(id_: str, items: dict) -> Keep:
    """A keep whose interval does not parse whole: its camera, from the bound that parses — or the start of time — to the
    bound that parses — or its end."""
    def bound(names, default):
        try:
            return finite(next((items[n] for n in names if n in items), default) or 0)
        except PARSE_ERRORS:
            return default
    since, until = bound(("from", "since"), 0.0), bound(("to", "until"), math.inf)
    if not since < until:
        since, until = 0.0, math.inf                    # the two that parse contradict each other: not known which is wrong
    return Keep(id_, str(items.get("cam", "")), since, until, "its row does not parse", str(items.get("by", "")), 0.0,
                tuple(str(r) for r in _names(items.get("recordings"))), garbled=True)


def spans_of(keeps: list[Keep], recording: str, cam: str = "") -> list[tuple[float, float]]:
    """The intervals kept for one recording: named in the keep, or of the keep's camera."""
    return [(k.since, k.until) for k in keeps if recording in k.recordings or (cam and k.cam == cam)]


def spans_of_cam(keeps: list[Keep], cam: str) -> list[tuple[float, float]]:
    return [(k.since, k.until) for k in keeps if k.cam == cam]


def held(spans: list[tuple[float, float]], start: float, end: float) -> bool:
    return any(a < end and start < b for a, b in spans)
