"""Where the VMS's rows of the domain lie: under the prefix the platform gives the `vms` subsystem (`domain/vms/…`,
`SubsystemSpec.domain_prefix`), by the names its spec declares (`domain.books`, `domain.kept`). Nothing here names a
row the spec does not: a book renamed in the spec and not here fails at import, not in a member's store.

    books (one per member at the holder, `<book>/<member>`; carried home to the member as `<book>`)
        SOURCES_PATH     for each recording cluster: where its cameras of other clusters were last seen (Lesson 13)
        PRIMARIES_PATH   for each camera cluster: who records it, whether written, and where to push (Lessons 13, 16)
        POLL_PATH        for a pushing camera nobody records: the ingest it polls for asks (Lesson 16)
        UPSTREAM_PATH    for each relay: the centre's ingest, per camera (Lesson 17)
        ASKS_PATH        for each camera a scenario makes a trigger: whom it may ask, by which roads (Lesson 16)
    kept at the holder for the whole domain
        CROSSINGS        which cluster records which camera of another
        ROADS            cameras sent to push because a recorder could not pull them: {ref: {on, why, nets}}
"""
from __future__ import annotations

from vms.config import SPEC


def _book(name: str) -> str:
    if name not in SPEC.domain.books:
        raise ValueError(f"vms.subsystem.yaml declares no book {name!r} (domain.books: {list(SPEC.domain.books)})")
    return SPEC.domain_prefix + name


def _kept(name: str) -> str:
    if name not in SPEC.domain.kept:
        raise ValueError(f"vms.subsystem.yaml keeps no row {name!r} (domain.kept: {list(SPEC.domain.kept)})")
    return SPEC.domain_prefix + name


SOURCES_PATH = _book("sources")
PRIMARIES_PATH = _book("primaries")
POLL_PATH = _book("poll")
UPSTREAM_PATH = _book("upstream")
ASKS_PATH = _book("asks")
CROSSINGS = _kept("crossings")
ROADS = _kept("roads")
