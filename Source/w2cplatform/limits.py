"""What a store can hold, said by the store.

A store has a ceiling and the platform has to know it — and the number belongs
to the store, not to its caller. The cluster's store (`configstore://`) weighs a
row by every key and every value in it and refuses one past
`storemachine.MAX_VALUE`, at its door and in the raft machine alike; a caller that
guessed a different number would find out in production.

Before this module the number lived in prose. `FsObjectStore` never refuses
anything, so a write that would be rejected in production succeeded in every
test, and the platform found its ceiling the way you find a ceiling in the
dark. The snapshot (Lesson 25) was found that way: one object for a full cluster's
worth of units, 232 KiB, discovered by arithmetic on paper rather than by a
failing test.

So the ceiling becomes a PROPERTY THE STORE DECLARES — `max_bytes`, zero
meaning no ceiling — and a write over it is refused. Refused, and not
truncated: half a row is worse than no row, and a store that silently drops
the tail of an object is a store that lies about `get`.

The seam is the same one `PLATFORM_STORE` and `OBJECTS` already are (Lesson 20).
`file://` has no ceiling, `configstore://` its row ceiling, `cluster://` (a
directory on every server, `w2cplatform/cluster/objectstore.py`) and `s3+https://`
none worth naming — and which one an install has is a fact the code can read
rather than a fact the operator is supposed to remember. The snapshot stays
sharded and the capped stores stay in the tests: a declared ceiling is a clause
of the contract, not a property of one backend.
"""
from __future__ import annotations

NO_CEILING = 0


class TooLarge(Exception):
    """A write over the store's declared ceiling.

    Carries the numbers rather than a sentence about them: the caller that
    knows what it was writing (a snapshot shard, a unit's row) adds the part
    a person needs — how many units that was, and what to do instead."""

    def __init__(self, key: str, size: int, limit: int, detail: str = ""):
        self.key, self.size, self.limit, self.detail = key, size, limit, detail
        super().__init__(f"{key}: {size} bytes over this store's limit of {limit}"
                         + (f" — {detail}" if detail else ""))


def check(key: str, size: int, limit: int, detail: str = "") -> None:
    """Raise `TooLarge` when `limit` is set and `size` is over it."""
    if limit and size > limit:
        raise TooLarge(key, size, limit, detail)
