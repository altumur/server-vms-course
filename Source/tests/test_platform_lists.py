"""The platform's closed lists as a shared table of parity (`testdata/platform_lists.tsv`; ADR-0019, its addition of
2026-10-10, review 15 minor 15): the words of a heartbeat that are the platform's, the roles a secret's readers may
be, and the platform's own secret rows with who reads them (`secret_readers`, ADR-0066's addition of 2026-10-10). The course's code holds exactly the table's sets, and the table is the product's byte for byte when the product's
`main` keeps one — a list that differs is a red test, not a difference found by a review."""
from __future__ import annotations

from tests.frozen_data import frozen_testdata

import os

from tests.productdir import SOURCE, product_file
from w2cplatform import spec
from w2cplatform.secrets import PLATFORM_SECRET_READERS

TABLE = os.path.join(frozen_testdata(), "platform_lists.tsv")
# `secret_readers`: the platform's own secret rows and their readers, a word `<row or prefix>=<role>` each — `<row>=`
# for a row nobody of the platform reads (the product's `PlatformSecretReaders`; ADR-0066's addition of 2026-10-10)
READERS = {f"{row}={r}" for row, roles in PLATFORM_SECRET_READERS.items() for r in (roles or ("",))}
LISTS = {"heartbeat_strings": spec.PLATFORM_HEARTBEAT_STRINGS, "secret_roles": spec.SECRET_ROLES,
         "secret_readers": READERS}


def _rows() -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    with open(TABLE, encoding="utf-8", newline="") as f:
        for i, line in enumerate(f.read().split("\n"), 1):
            if not line or line.startswith("#"):
                continue
            cols = line.split("\t")
            assert len(cols) == 2 and cols[0] in LISTS and cols[1], f"line {i}: a row is list, word: {line!r}"
            assert cols[1] not in out.get(cols[0], set()), f"line {i}: {cols[0]} {cols[1]} twice"
            out.setdefault(cols[0], set()).add(cols[1])
    return out


def test_the_code_holds_the_tables_lists():
    rows = _rows()
    for name, held in LISTS.items():
        assert set(held) == rows.get(name, set()), (f"{name}: the code holds {sorted(held)}, "
                                                    f"platform_lists.tsv {sorted(rows.get(name, set()))}")


def test_the_table_is_the_products_byte_for_byte_when_the_product_keeps_one():
    theirs = product_file("testdata/platform_lists.tsv")
    if theirs is None:
        print("  the product's main keeps no testdata/platform_lists.tsv: the course's copy stands")
        return
    with open(TABLE, "rb") as b:
        assert theirs == b.read(), f"{TABLE} is not the product's testdata/platform_lists.tsv byte for byte"


def test_every_reader_of_the_platforms_secret_rows_is_a_role_a_secret_may_name():
    """A reader in `secret_readers` is one of `secret_roles`, and a row says nobody only with an empty word (`<row>=`)."""
    for row, roles in PLATFORM_SECRET_READERS.items():
        assert row and not set(roles) - set(spec.SECRET_ROLES), (row, roles)
        assert len(set(roles)) == len(roles), (row, roles)
