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
# B). A worker's assignment is its units joined by `,` (`contract.Assignment`), and so are a holder's `closed` and a
# heartbeat's ranges: a unit named `1,9` made its worker take `9` and never start `1,9`, and its fetched range
# scanned unit 9's data. And a name that is all digits sorts by its number (`spec._unit_key`): `"7²".isdigit()`
# is true and `int("7²")` raises — every `GET` of that subsystem's list went unanswered. So a unit's name also may not
# hold `,`, nor a digit that is not ASCII 0–9 (superscripts, Arabic-Indic, full width: `isdigit` says yes to all).
# A request's id is not a unit's: a heartbeat says it by its digest when it holds a comma (`requests.said_id`).
LIST_SEPARATOR = ","


def unnamable(name: str, unit: bool = False) -> list[str]:
    import unicodedata
    return sorted({c for c in str(name) if c in '|"' or unicodedata.category(c) in ("Cc", "Zl", "Zp")
                   or (unit and (c == LIST_SEPARATOR or (c.isdigit() and not "0" <= c <= "9")))})


# A REQUEST'S ID (`rid`: the name of `<sub>/requests/<rid>` and of its mark `<sub>/commands/<rid>`) — ONE TABLE FOR THE
# COURSE AND THE PRODUCT («Архитектор», 2026-10-06, ADR 0060; «Паритет»'s `testdata/rid.tsv`): at most `RID_BYTES` bytes
# of UTF-8, not empty, not `.` or `..`; no `/`, `\`, `"`, `'`, and no character of Unicode's Cc, Zl or Zp. It counted
# characters: 150 × «я» passed it and the store refused the 300-byte key with a 500, and `a\u0085b` was a 500 too. One
# function for both who name a request: the console's door (`SpecConsole._file_request`, 400) and a worker's
# (`Worker.file_request`, `RequestRefused`). No prefix means anything: a person's ledger is not in this family (ADR 0060).
RID_BYTES = 200


def rid_fault(rid) -> str | None:
    """Why `rid` is not a request's id, in words — None when it is one."""
    import unicodedata
    rid = str(rid)
    if not rid or rid in (".", ".."):
        return "a request's id is a name, not empty, `.` or `..`"
    try:
        size = len(rid.encode("utf-8"))
    except UnicodeEncodeError:                    # a lone surrogate (`"\ud800"` in JSON): no UTF-8 at all
        return "a request's id is text that UTF-8 can write, and a lone surrogate is none"
    if size > RID_BYTES:
        return f"a request's id is at most {RID_BYTES} bytes of UTF-8, not {size}"
    bad = sorted({c for c in rid if c in "/\\\"'" or unicodedata.category(c) in ("Cc", "Zl", "Zp")})
    if bad:
        return f"a request's id is a name, not a path, and holds no slash, backslash, quote or control character ({bad[0]!r})"
    return None


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
