"""One table of addresses for the course and the product (`testdata/secret_in.tsv`, the boundary's step 4, item 6): what
the vms spec's `source` shows of each, and what refusing it says — by the platform's reading of an address and the
field's `credentials` and `secret_in`, nothing of a camera's in the platform. The product reads the same rows the same
way (`vmsworker/vms/secret_in_test.go`); a row one side masks and the other prints is a password in a log. The course's
rows are its own until the product's table lands — then the file is a copy of the product's, byte for byte."""
from __future__ import annotations

import os

from tests.productdir import SOURCE, product_dir

TABLE = os.path.join(SOURCE, "tests", "testdata", "secret_in.tsv")


def _rows():
    with open(TABLE, encoding="utf-8") as f:
        for i, line in enumerate(f.read().split("\n"), 1):
            if not line or line.startswith("#"):
                continue
            cols = line.split("\t")
            assert len(cols) == 4, f"line {i}: a row is raw, masked, fault, note: {line!r}"
            yield i, cols


def test_every_address_of_the_shared_table_is_masked_and_refused_as_the_table_says():
    """Each row: `masked` is what a page shows of `raw` (`hide_in_url` by the field's rules — not by the catalog's, which
    is whatever specs the process happened to load); `fault` is what refusing it as the field's value
    names: nothing (taken), `cred_secret` (a password), `cred_username` (a login and no password), `-` (a text, not
    asked). No refusal repeats the value, and no masked row that holds a password shows it."""
    if not os.path.exists(TABLE):
        print("  no testdata/secret_in.tsv: nothing to read")
        return
    from w2cplatform.secrets import hide_in_url
    from w2cplatform.spec import SubsystemSpec
    source = SubsystemSpec.load(os.path.join(SOURCE, "vms", "vms.subsystem.yaml")).fields["source"]
    wrong, n, refused = [], 0, 0
    for i, (raw, masked, fault, _) in _rows():
        n += 1
        got = hide_in_url(raw, source.rules)
        if got != masked:
            wrong.append(f"line {i}: {raw}\n    masked as {got}\n    the table: {masked}")
        if fault == "-":
            continue
        why = source.refusal(raw)
        if fault == "" and why is not None:
            wrong.append(f"line {i}: {raw} is refused: {why}")
        elif fault and (why is None or fault not in why):
            wrong.append(f"line {i}: {raw}: the refusal names no {fault}: {why!r}")
        elif why and "hunter2" in why.lower():
            wrong.append(f"line {i}: {raw}: the refusal repeats the value: {why!r}")
        if fault == "cred_secret" and "hunter2" in masked.lower():
            wrong.append(f"line {i}: {raw}: the table's own mask shows the password: {masked}")
        refused += bool(fault)
    assert not wrong, f"{len(wrong)} rows of {os.path.basename(TABLE)} go another way:\n  " + "\n  ".join(wrong)
    assert n >= 100 and refused >= 50, f"the table is too short: {n} rows, {refused} refused"


def test_the_shared_table_is_the_products_byte_for_byte_when_the_product_keeps_one():
    """When the product's checkout keeps the table (`testdata/secret_in.tsv`, or `vmsworker/testdata/secret_in.tsv`),
    the course's is a copy of it: the same bytes."""
    root = product_dir()
    theirs = next((p for p in (os.path.join(root, "vmsworker", "testdata", "secret_in.tsv"),
                               os.path.join(root, "testdata", "secret_in.tsv")) if os.path.exists(p)), None) if root else None
    if theirs is None:
        print("  the product keeps no secret_in.tsv (W2C_PRODUCT_DIR): nothing to compare")
        return
    with open(theirs, "rb") as a, open(TABLE, "rb") as b:
        assert a.read() == b.read(), f"{TABLE} is not the product's {theirs} byte for byte — copy it"
