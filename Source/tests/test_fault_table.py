"""The closed vocabulary of `fault` (`testdata/fault.tsv`; «Архитектор» with «Паритет», 2026-10-06): the word a door's
refusal says to a machine and a test, and the HTTP status it comes with — one table for the course and the product, byte
for byte. The course's side of it: `canonical.FAULTS` holds exactly its words, each refusal that carries a word answers
the table's status through the doors' one function (`console.refused_status`), and the other shared tables
(`requests_body.tsv`, `group_of.tsv`) say no word it does not hold."""
from __future__ import annotations

import os

from tests.productdir import SOURCE, product_file

DATA = os.path.join(SOURCE, "tests", "testdata")
TABLE = os.path.join(DATA, "fault.tsv")


def _rows() -> dict[str, int]:
    """word → status, in the table's order."""
    out: dict[str, int] = {}
    with open(TABLE, encoding="utf-8", newline="") as f:
        for i, line in enumerate(f.read().split("\n"), 1):
            if not line or line.startswith("#"):
                continue
            cols = line.split("\t")
            assert len(cols) == 2 and cols[1] in ("400", "409"), f"line {i}: a row is word, status (400|409): {line!r}"
            assert cols[0] not in out, f"line {i}: {cols[0]} twice"
            out[cols[0]] = int(cols[1])
    return out


def _carriers() -> dict[str, list]:
    """Every refusal of the platform that says a word (a `canonical.Fault`, a `spec.Refused` with `fault`), by its word."""
    from w2cplatform import canonical, spec

    def subclasses(c):
        for s in c.__subclasses__():
            yield s
            yield from subclasses(s)
    out: dict[str, list] = {}
    for base in (canonical.Fault, spec.Refused):
        for c in subclasses(base):
            word = getattr(c, "fault", "")
            if word:
                out.setdefault(word, []).append(c)
    return out


def test_the_vocabulary_is_canonical_faults_and_each_word_comes_with_the_tables_status():
    """`canonical.FAULTS` is the table's words, in its order; a refusal saying a word answers its status at every door
    (`refused_status`: 400 the body alone is wrong, 409 it depends on the rows that stand, ADR 0031) — the refusals
    the door's code raises with the word set on an instance (`Refused` with `fault` not_json / not_number / too_long)
    are 400 by the same function."""
    from w2cplatform import canonical
    from w2cplatform.console import refused_status
    from w2cplatform.spec import Refused
    table = _rows()
    assert tuple(table) == canonical.FAULTS, f"fault.tsv says {list(table)}; canonical.FAULTS {list(canonical.FAULTS)}"
    carriers = _carriers()
    assert set(carriers) <= set(table), f"refusals say words fault.tsv does not hold: {sorted(set(carriers) - set(table))}"
    wrong = [f"{c.__module__}.{c.__name__} says {word}: {refused_status(c('x'))}, the table {table[word]}"
             for word, cs in carriers.items() for c in cs if refused_status(c("x")) != table[word]]
    for word in ("not_json", "not_number", "too_long"):                  # set on an instance (`SubsystemSpec.refuse`)
        r = Refused("x")
        r.fault = word
        if refused_status(r) != table[word]:
            wrong.append(f"a Refused with fault {word}: {refused_status(r)}, the table {table[word]}")
    assert not wrong, "\n".join(wrong)
    assert {w for w, s in table.items() if s == 409} <= set(carriers), "every 409 word is said by a refusal class"


def test_the_shared_tables_say_their_faults_only_in_its_words():
    """`requests_body.tsv` (column 4) and `group_of.tsv` (column 3) take their `fault` from fault.tsv alone."""
    words = set(_rows())
    wrong = []
    for name, col in (("requests_body.tsv", 3), ("group_of.tsv", 2)):
        with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
            for i, line in enumerate(f.read().split("\n"), 1):
                if not line or line.startswith("#"):
                    continue
                cols = line.split("\t")
                fault = cols[col] if len(cols) > col else ""
                if fault and fault not in words:
                    wrong.append(f"{name} line {i}: {fault!r} is no word of fault.tsv")
    assert not wrong, "\n".join(wrong)


def test_the_table_is_the_products_byte_for_byte_when_the_product_keeps_one():
    """When the product's committed `main` keeps `testdata/fault.tsv`, the course's is a copy of it: the same bytes."""
    theirs = product_file("testdata/fault.tsv")
    if theirs is None:
        print("  the product's main keeps no testdata/fault.tsv: the course's copy stands")
        return
    with open(TABLE, "rb") as b:
        assert theirs == b.read(), f"{TABLE} is not the product's testdata/fault.tsv byte for byte"
