"""What a request may NAME, and how much it may ASK for — one place, for every door that turns a URL or a
header into a place on a disk.

Each door used to check for itself, and each a little differently: `".." in rel` on most, nothing at all on
`/buckets/<sub>/<unit>` and `/mirrored/<server>`, and nowhere the one thing that check does not catch — an
ABSOLUTE path. `os.path.join(root, "/etc/hosts")` is `/etc/hosts`: a second slash after a door's prefix read any
file of the machine, a unit's row with its credentials among them (the platform review, 29 September; the
product's doors, feedback BD). A rule written once per door is a rule some door does not have.

    safe_segment(name)   ONE name: not empty, not `.` or `..`, no separator, no NUL. A unit, a server, a subsystem
    safe_rel(rel)        a relative path every segment of which is such a name — so neither `..` nor a leading `/`
    parse_ref(ref)       a UNIT as the platform names one outside its subsystem's routes, `<sub>/<id>`: (sub, id), or
                         None for anything else — a bare id names nothing (`ref_fault` says why, `unit_ref` makes one)
    byte_range(h, size)  a `Range` header cut to the file: the bytes to send, or None for a range no part of
                         which exists (416). The length sent is never the client's number
    MAX_LIMIT            the most rows one answer of `/events` carries, whatever `limit` says: `limit=999999999`
                         is otherwise a request for the whole tree in one JSON

`Range: bytes=0-99999999999` asked `read()` for a hundred gigabytes in one allocation; `bytes=50-40` is a
negative length, which `read()` takes to mean "everything". The suffix form `bytes=-N` is the LAST N bytes; it
used to be read as `0-N`.
"""
from __future__ import annotations

MAX_LIMIT = 10_000


def safe_segment(name: str) -> bool:
    return bool(name) and name not in (".", "..") and "/" not in name and "\\" not in name and "\0" not in name


# The characters a NAME may not hold, beyond what makes it a path (the review's eighth pass): `"` and `|` — a name goes
# whole into a label value on `/metrics` and into `|`-joined fields of heartbeats — and the control, line and paragraph
# separator characters (Unicode Cc, Zl, Zp). The rule the domain keeps for a user's name (`domain/grants.py`). Returns
# the characters found, sorted; empty when the name may stand.
#
# A UNIT'S NAME, `unit=True`, is in lists and is sorted as a number (the review's ninth pass; the product team's sibling
# B). A worker's assignment is its units joined by `,` (`contract.Assignment`), and so are a recorder's `closed` and a
# heartbeat's ranges: a recording named `1,9` made its worker take `9` and never start `1,9`, and its fetched range
# scanned recording 9's camera. And a name that is all digits sorts by its number (`spec._unit_key`): `"7²".isdigit()`
# is true and `int("7²")` raises — every `GET` of that subsystem's list went unanswered. So a unit's name also may not
# hold `,`, nor a digit that is not ASCII 0–9 (superscripts, Arabic-Indic, full width: `isdigit` says yes to all).
# A request's id is not a unit's: a heartbeat says it by its digest when it holds a comma (`requests.said_id`).
LIST_SEPARATOR = ","


def unnamable(name: str, unit: bool = False) -> list[str]:
    import unicodedata
    return sorted({c for c in str(name) if c in '|"' or unicodedata.category(c) in ("Cc", "Zl", "Zp")
                   or (unit and (c == LIST_SEPARATOR or (c.isdigit() and not "0" <= c <= "9")))})


# A UNIT NAMED OUTSIDE ITS OWN SUBSYSTEM'S ROUTES: `<sub>/<id>` — `testsub/c1`, `other/a-b` — one string, wherever the
# platform names a unit: `/events?unit=`, a mark's `unit`, an event line's `of`, a grant's `unit:` scope (the boundary's
# step 2, ГРАНИЦА-ПЛАТФОРМЫ-И-ПОДСИСТЕМЫ.md §2.1). A bare id names nothing — whose `7` would it be? — and the id has no
# `/` of its own: everything after the first one, one segment.
def unit_ref(sub: str, uid) -> str:
    return f"{sub}/{uid}"


def parse_ref(ref) -> tuple[str, str] | None:
    """`(sub, id)` of a reference, None for anything that is not one: a bare id, an empty half, a path."""
    if not isinstance(ref, str):
        return None
    sub, sep, uid = ref.partition("/")
    if not sep or not safe_segment(sub) or not safe_segment(uid) or unnamable(sub) or unnamable(uid):
        return None
    return sub, uid


def ref_fault(ref) -> str | None:
    """Why `ref` is not a reference to a unit, in words — None when it is one."""
    if parse_ref(ref) is not None:
        return None
    return f"a unit is named <sub>/<id> — testsub/7, other/a-b — not {str(ref)[:80]!r}"


# A name as the number it is, or None: ASCII digits only, and only as many as `int` takes (`sys.int_max_str_digits` —
# five thousand nines raise). What every sort and every reader that takes "all digits" for a number asks, so a stored
# name the rule above refuses today (`7²`, `٣`) is read as a name, not as a `ValueError` (the review's ninth pass).
def numeric(name) -> int | None:
    s = str(name)
    if not (s.isascii() and s.isdigit()):
        return None
    try:
        return int(s)
    except ValueError:
        return None


def safe_rel(rel: str) -> bool:
    return bool(rel) and all(safe_segment(s) for s in rel.split("/"))


def byte_range(header: str | None, size: int) -> tuple[int, int] | None:
    """(start, end) inclusive, inside the file. No header, or one that is not a byte range: the whole file."""
    whole = (0, size - 1)
    if not header or not header.startswith("bytes=") or "," in header:
        return whole
    a, sep, b = header[6:].strip().partition("-")
    try:
        if not sep:
            return whole
        if a == "":                                         # bytes=-N: the last N
            n = int(b)
            return None if n <= 0 or size == 0 else (max(0, size - n), size - 1)
        start = int(a)
        end = int(b) if b else size - 1
    except ValueError:
        return whole
    if start < 0 or start >= size or end < start:
        return None
    return start, min(end, size - 1)
