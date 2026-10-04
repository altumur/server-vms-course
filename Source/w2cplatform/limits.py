"""What a store can hold, said by the store.

A store has a ceiling and the platform has to know it. This was learned when
the cluster's store was Nomad Variables: Nomad capped a whole Variable — every
key and every value in it — at 64 KiB, and that number was not the platform's
to choose: a constant in the scheduler (`maxVariableSize = 65536`), the request
to make it configurable open since 2022 and answered with "we don't want to
give users a new way to break their clusters". The cluster's store is now its
own daemon (`configstore://`), whose row ceiling is `storemachine.MAX_VALUE`;
the lesson stands — the number belongs to the store, not to its caller.

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

The seam is the same one `CONFIG_URL` and `OBJECTS` already are (Lesson 20).
`file://` has no ceiling, `variables://` has 64 KiB, `s3+https://` has none
worth naming — and which one an install has is now a fact the code can read
rather than a fact the operator is supposed to remember.

М11's objects left Variables: `cluster://` is a directory on every server
(`cluster/objectstore.py`), and it declares no ceiling. A row in the store
still has one if its backend says so, and so does any object store a test or
an install declares — which is why the snapshot stays sharded and the capped
stores stay in the tests: a declared ceiling is a clause of the contract, not
a property of one backend.
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
