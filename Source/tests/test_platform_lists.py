"""The platform's closed lists as a shared table of parity (`testdata/platform_lists.tsv`; ADR-0019, its addition of
2026-10-10, review 15 minor 15): the words of a heartbeat that are the platform's, and the roles a secret's readers may
be. The course's code holds exactly the table's sets, and the table is the product's byte for byte when the product's
`main` keeps one — a list that differs is a red test, not a difference found by a review."""
from __future__ import annotations

import os

from tests.productdir import SOURCE, product_file
from w2cplatform import spec

TABLE = os.path.join(SOURCE, "tests", "testdata", "platform_lists.tsv")
LISTS = {"heartbeat_strings": spec.PLATFORM_HEARTBEAT_STRINGS, "secret_roles": spec.SECRET_ROLES}


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
