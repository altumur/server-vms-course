"""What a request may NAME, and how much it may ASK for — one place, for every door that turns a URL or a
header into a place on a disk.

Each door used to check for itself, and each a little differently: `".." in rel` on most, nothing at all on
`/buckets/<sub>/<unit>` and `/mirrored/<server>`, and nowhere the one thing that check does not catch — an
ABSOLUTE path. `os.path.join(root, "/etc/hosts")` is `/etc/hosts`: a second slash after a door's prefix read any
file of the machine, a unit's row with its credentials among them (the platform review, 29 September; the
product's doors, feedback BD). A rule written once per door is a rule some door does not have.

    safe_segment(name)   ONE name: not empty, not `.` or `..`, no separator, no NUL. A unit, a server, a subsystem
    safe_rel(rel)        a relative path every segment of which is such a name — so neither `..` nor a leading `/`
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
