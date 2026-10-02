"""One row of the store that does not parse is that row's trouble: the one reader every table goes through."""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # rows.py — a garbled row: skipped, counted by its key, named
#
# **Role in the module.** Seven passes of the review found the same failure in a new table each time: a row
# read bare — a word where a number goes, after a hand edit, half a write, an older build — raised out of a loop
# over MANY rows, and one row's trouble stopped everybody's pass. Epochs, slots, holds, assignments, then the
# volumes, the keeps, the requests, `platform/space` (the review's seventh pass). Each fix was a reader of its own,
# each counted a little differently — and three of them counted READS, so a row read every pass looked like a
# thousand rows (the seventh pass, minors).
#
# This is the one reader. A table is a `Table`: its name and what not reading a row of it means. `read(key,
# parse, default)` runs `parse()`; what a parse raises — `ValueError` (a `JSONDecodeError` is one), `TypeError`,
# `KeyError`, `AttributeError`, `OverflowError` (`int(float("inf"))`), `RecursionError` (JSON nested ten thousand
# deep: `json.loads` gives up on it, and it fits a Variable — the review's eighth pass) — makes the row garbled: `default` is
# returned, the row is counted ONCE until it parses again (`counts`, by subsystem — the key's first segment),
# logged once with what not reading it means, and its key is in `bad` for whoever names it on a page. A row
# that parses again leaves `bad`; garbled again later, it is counted again — a new spell, not a re-read.
#
# What the DEFAULT is, is the caller's: no candidate (a slot, a hold), the row read last (a volume a recorder
# holds), "everything kept" (a keep), the settings read last (the watermark). Never "no" where "not known" is
# what happened.
#
# ## Public API
# - `PARSE_ERRORS` — what a parse raises when the row is garbled (and nothing else: a store that does not answer
#   raises `OSError`, which is not the row's trouble and is left to the caller).
# - `Table(name, unread, noun="")` — `read(key, parse, default=None)`, `garbled(key, error)`, `parsed(key)`, `counts`,
#   `bad`, `named(prefix)`.
# - `number(key, value, kind, default)` — a number a row or a heartbeat carries, through the table `field`: a word,
#   `nan` or `inf` is `default`, counted once per `<key>#<field>` (the review's seventh pass: `/metrics` of a console
#   failed whole on one field of one heartbeat). `finite(x)` — the same test for a caller that parses itself.
# - `TABLES` — every table made; `counts()` — `{name: {sub: n}}`, the tables of one name summed (a module imported
#   twice — `tests/test_portability.py` rebuilds `sys.modules` — makes a second table of the same name, and a registry
#   keyed by name kept only the last); `garbled_counts(sub)` — `{"<name>s_garbled": n}`, what a heartbeat carries;
#   `forget()` — clears every count (tests).
# - `answer(r, limit)` — the body of another process's door, read up to `ANSWER_MAX` bytes, else `ValueError`.
# ================================================================================================
import logging
import math

log = logging.getLogger(__name__)

PARSE_ERRORS = (ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError)

TABLES: list["Table"] = []


class Table:
    """The rows of one kind: who reads them past one that does not parse, and how many did not."""

    def __init__(self, name: str, unread: str, noun: str = ""):
        self.name = name                  # "slot", "hold", "volume", "keep", … — `<name>s_garbled` in a heartbeat
        self.unread = unread              # what not reading a row of it means, for the log
        self.noun = noun or f"{name} row" # what the log calls one
        self.counts: dict[str, int] = {}  # subsystem -> rows found garbled, each once per spell
        self.bad: set[str] = set()        # keys garbled at their last read
        TABLES.append(self)

    def read(self, key: str, parse, default=None):
        """`parse()` — or, when the row does not parse, `default`: counted once, logged once."""
        try:
            value = parse()
        except PARSE_ERRORS as e:
            self.garbled(key, e)
            return default
        self.parsed(key)
        return value

    def garbled(self, key: str, error) -> None:
        if key in self.bad:
            return                        # the same row, read again: not another row
        self.bad.add(key)
        sub = key.split("/", 1)[0]
        self.counts[sub] = self.counts.get(sub, 0) + 1
        log.error("%s: the %s does not parse (%s); %s", key, self.noun, error, self.unread)

    def parsed(self, key: str) -> None:
        self.bad.discard(key)

    def named(self, prefix: str) -> set[str]:
        """The names under `prefix` whose rows did not parse at their last read."""
        return {k[len(prefix):] for k in self.bad if k.startswith(prefix)}


FIELDS = Table("field", "read as not said", "number in it")


def finite(x) -> float:
    """`float(x)`, and a `ValueError` for `nan` and `inf` — a number that passes every comparison and means nothing:
    `nan < now` is false, so a deadline of `nan` was never past (the review's seventh pass, M3)."""
    v = float(x)
    if not math.isfinite(v):
        raise ValueError(f"{x!r} is not a finite number")
    return v


def number(key: str, value, kind=float, default=0):
    """`value` as a finite number of `kind` — or `default` when it is absent (not counted) or a word, `nan`, `inf`
    (counted once per `key`, which names the object and the field: `<sub>/…#<field>`)."""
    if value is None:
        return default
    return FIELDS.read(key, lambda: kind(finite(value)) if kind is not float else finite(value), default)


def counts() -> dict[str, dict[str, int]]:
    """`{name: {subsystem: rows found garbled}}`, every table of this process, by name."""
    out: dict[str, dict[str, int]] = {}
    for t in TABLES:
        by_sub = out.setdefault(t.name, {})
        for sub, n in t.counts.items():
            by_sub[sub] = by_sub.get(sub, 0) + n
    return out


def garbled_counts(sub: str) -> dict[str, int]:
    """`{"<table>s_garbled": n}` for every table with a garbled row of `sub` in this process."""
    return {f"{name}s_garbled": c[sub] for name, c in counts().items() if c.get(sub)}


def forget() -> None:
    for t in TABLES:
        t.counts.clear()
        t.bad.clear()


# AN ANSWER OF ANOTHER PROCESS'S DOOR IS READ UP TO A BOUND (the review's eighth pass, a sibling the product team found):
# a peer's `/mirrored`, a recorder's `/timeline`, a resource's `/events` and `/events/wait` were read whole whatever
# their size — a door of another build, a proxy's page, a door gone wrong was memory without a ceiling in the reader.
# `answer(r, limit)` reads at most `limit` bytes and raises `ValueError` past it — one of `PARSE_ERRORS`: an answer too
# big to read is an answer that does not parse, and every reader of a door takes it as that door not answering.
ANSWER_MAX = 16 << 20


def answer(r, limit: int = ANSWER_MAX) -> bytes:
    """At most `limit` bytes of `r` (a response), or `ValueError`."""
    data = r.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"the answer is over {limit} bytes: not read")
    return data
