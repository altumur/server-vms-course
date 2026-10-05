"""One table of addresses for the course and the product (`testdata/secret_in.tsv`, the boundary's step 4, item 6): what
the vms spec's `source` shows of each, and what refusing it says — by the platform's reading of an address and the
field's `credentials` and `secret_in`, nothing of a camera's in the platform. The product reads the same rows the same
way (`vmsworker/vms/secret_in_test.go`); a row one side masks and the other prints is a password in a log. The course's
rows are its own until the product's table lands — then the file is a copy of the product's, byte for byte."""
from __future__ import annotations

import os

from tests.productdir import SOURCE, product_file

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
    """When the product's committed `main` keeps the table (`testdata/secret_in.tsv`, or
    `vmsworker/testdata/secret_in.tsv`), the course's is a copy of it: the same bytes. A table the product's author is
    still editing in a working tree is not the product's yet (`productdir.py`)."""
    for path in ("vmsworker/testdata/secret_in.tsv", "testdata/secret_in.tsv"):
        theirs = product_file(path)
        if theirs is not None:
            break
    else:
        print("  the product's main keeps no secret_in.tsv (W2C_PRODUCT_DIR): nothing to compare")
        return
    with open(TABLE, "rb") as b:
        assert theirs == b.read(), f"{TABLE} is not the product's {path} byte for byte — copy it"


def test_the_product_is_read_as_its_main_holds_it_and_never_as_a_working_tree_being_edited():
    """What the course holds itself to is the product's committed `main` (`productdir.product_file`): a table or a spec
    the product's author is halfway through editing failed the course's suite, which had read the working tree. Here
    on a made-up checkout: a file changed and not committed is read as committed, a file only in the working tree is
    none, and no checkout at all is none — the tests that compare skip."""
    import subprocess
    import tempfile

    from tests import productdir
    root = tempfile.mkdtemp(prefix="product-")
    git = ["git", "-C", root, "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run(git + ["init", "-q", "-b", "main"], check=True)
    os.makedirs(os.path.join(root, "testdata"))
    with open(os.path.join(root, "testdata", "secret_in.tsv"), "w") as f:
        f.write("committed\n")
    subprocess.run(git + ["add", "testdata/secret_in.tsv"], check=True)
    subprocess.run(git + ["commit", "-q", "-m", "t"], check=True)
    with open(os.path.join(root, "testdata", "secret_in.tsv"), "w") as f:
        f.write("half edited\n")
    with open(os.path.join(root, "testdata", "new.tsv"), "w") as f:
        f.write("not yet\n")
    was = os.environ.get("W2C_PRODUCT_DIR")
    os.environ["W2C_PRODUCT_DIR"] = root
    try:
        assert productdir.product_file("testdata/secret_in.tsv") == b"committed\n"
        assert productdir.product_file("testdata/new.tsv") is None
        assert productdir.product_files("testdata", ".tsv") == ["testdata/secret_in.tsv"]
        os.environ["W2C_PRODUCT_DIR"] = os.path.join(root, "nowhere")
        assert productdir.product_file("testdata/secret_in.tsv") is None and productdir.product_files("testdata") == []
    finally:
        if was is None:
            os.environ.pop("W2C_PRODUCT_DIR", None)
        else:
            os.environ["W2C_PRODUCT_DIR"] = was


LOG_MASK = os.path.join(SOURCE, "tests", "testdata", "log_mask.tsv")


def test_free_text_is_said_with_every_credential_in_it_hidden_as_its_table_says():
    """`secrets.mask_text` — a log line, an error a driver said, a request it logged, a JSON document: no field of any
    spec's (the product's decision, 5 Oct: a function of the platform's own, with its own table). Each row of
    `testdata/log_mask.tsv`, by the platform's own names of a credential alone: `masked` is what is said of `raw`,
    and no row that hides a value shows `hunter2`."""
    from w2cplatform.secrets import NO_RULES, mask_text
    wrong, n = [], 0
    with open(LOG_MASK, encoding="utf-8") as f:
        for i, line in enumerate(f.read().split("\n"), 1):
            if not line or line.startswith("#"):
                continue
            cols = line.split("\t")
            assert len(cols) == 3, f"line {i}: a row is raw, masked, note: {line!r}"
            raw, masked, _ = cols
            n += 1
            got = mask_text(raw, NO_RULES)
            if got != masked:
                wrong.append(f"line {i}: {raw}\n    said as {got}\n    the table: {masked}")
            if "***" in masked and "hunter2" in masked.lower():
                wrong.append(f"line {i}: the table's own mask shows the password: {masked}")
    assert not wrong, f"{len(wrong)} rows of log_mask.tsv go another way:\n  " + "\n  ".join(wrong)
    assert n >= 20, f"the table is too short: {n} rows"


def test_the_platforms_log_lines_go_through_the_mask():
    """`secrets.mask_logs` puts `MaskedLog` on a logger's handlers (the platform's entry points do it for the root's): a
    record whose message holds a credential is said masked, its arguments folded in; any other is left as it was."""
    import io
    import logging

    from w2cplatform.secrets import mask_logs
    out = io.StringIO()
    logger = logging.getLogger("fx-mask-probe")
    logger.propagate = False
    h = logging.StreamHandler(out)
    logger.addHandler(h)
    logger.setLevel(logging.INFO)
    try:
        mask_logs(logger)
        mask_logs(logger)                                # once is enough: no second filter
        assert len(h.filters) == 1
        logger.info("opening %s failed", "rtsp://admin:hunter2@cam/live?token=hunter2")
        logger.info("Authorization: Basic %s", "YWRtaW46aHVudGVyMg==")
        logger.info("nothing to hide: %d", 7)
        said = out.getvalue()
        assert "hunter2" not in said and "YWRtaW46" not in said, said
        assert "rtsp://admin:***@cam/live?token=***" in said and "nothing to hide: 7" in said, said
    finally:
        logger.removeHandler(h)
