"""One table of addresses for the course and the product (`testdata/secret_in.tsv`, the boundary's step 4, item 6): what
a url field of the VMS's specs shows of each, and what refusing it says — by the platform's reading of an address and the
field's `credentials` and `secret_in`, nothing of a camera's or a volume's in the platform. The product reads the same
rows the same way (`vmsworker/vms/secret_in_test.go`); a row one side masks and the other prints is a password in a log.
The file is a copy of the product's (its committed main, `testdata/secret_in.tsv`), byte for byte; so is the free
text's, `testdata/log_mask.tsv`, read by the platform's `secrets.mask_text`.

A row names its field (ADR-0053, addendum of 2026-10-06: a volume's url has words of its own): five columns,
tab-separated — `field, raw, masked, fault, note`. `field` is `<sub>.<field>` for a unit's (`vms.source`) or
`<sub>.<table>.<field>` for a table's (`rec.volumes.url`), of `Source/vms/<sub>.subsystem.yaml`; a name that is no url
field there is the row's error, never a row skipped."""
from __future__ import annotations

import contextlib
import os

from tests.productdir import SOURCE, product_file

TABLE = os.path.join(SOURCE, "tests", "testdata", "secret_in.tsv")
SPECS = os.path.join(SOURCE, "vms")
COLUMNS = ("field", "raw", "masked", "fault", "note")


@contextlib.contextmanager
def _deployment():
    """The catalogue for a while holds the VMS's specs alone (`Source/vms/*.subsystem.yaml`), as a deployment's process
    holds them: an address nested in a field's is read by every loaded spec's rule (ADR-0053, `nested`), and a spec
    another test loaded is no deployment's. Yields them by name."""
    from w2cplatform import catalog
    specs = {s.name: s for s in catalog.load_dir(SPECS)}
    with catalog._lock:
        saved = dict(catalog._loaded)
        catalog._loaded.clear()
        catalog._loaded.update(specs)
        catalog.version += 1
        catalog._derived.clear()
    try:
        yield specs
    finally:
        with catalog._lock:
            catalog._loaded.clear()
            catalog._loaded.update(saved)
            catalog.version += 1
            catalog._derived.clear()


def _field(specs: dict, name: str):
    """The url field a row names — `<sub>.<field>` or `<sub>.<table>.<field>` — or the words why there is none."""
    parts = name.split(".")
    spec = specs.get(parts[0]) if len(parts) in (2, 3) else None
    if spec is None:
        return None, f"names no field of a spec of {os.path.relpath(SPECS, SOURCE)}/ (<sub>.<field> or <sub>.<table>.<field>)"
    if len(parts) == 3 and parts[1] not in spec.table_specs:
        return None, f"names no table {parts[1]!r} of {parts[0]}"
    fields = spec.fields if len(parts) == 2 else spec.table_specs[parts[1]].fields
    f = fields.get(parts[-1])
    if f is None or f.type != "url":
        return None, f"names no url field {parts[-1]!r} of {'.'.join(parts[:-1])}"
    return f, None


def _check(path: str) -> tuple[list[str], int, int]:
    """Every row of the table at `path` against the field it names: `(wrong, rows, refused)`. Each row: `masked` is what
    a page shows of `raw` (`hide_in_url` by the field's rule, an address nested in it by the deployment's specs);
    `fault` is what refusing it as the field's value names: nothing (taken), the field's secret (`cred_secret`,
    `access_secret`: a password), its login (`cred_username`, `access_key`: a login and no password), `-` (a text, not
    asked). No refusal repeats the value, and no masked row refused for a password shows it."""
    from w2cplatform.secrets import hide_in_url
    wrong, n, refused = [], 0, 0
    with open(path, encoding="utf-8") as f, _deployment() as specs:
        for i, line in enumerate(f.read().split("\n"), 1):
            if not line or line.startswith("#"):
                continue
            cols = line.split("\t")
            if len(cols) != len(COLUMNS):
                wrong.append(f"line {i}: a row is {', '.join(COLUMNS)}, tab-separated: {line!r}")
                continue
            name, raw, masked, fault, _ = cols
            n += 1
            fld, why_not = _field(specs, name)
            if fld is None:
                wrong.append(f"line {i}: {name!r} {why_not}")
                continue
            got = hide_in_url(raw, fld.rules)
            if got != masked:
                wrong.append(f"line {i}: {name} {raw}\n    masked as {got}\n    the table: {masked}")
            if fault == "-":
                continue
            why = fld.refusal(raw)
            if fault == "" and why is not None:
                wrong.append(f"line {i}: {name} {raw} is refused: {why}")
            elif fault and (why is None or fault not in why):
                wrong.append(f"line {i}: {name} {raw}: the refusal names no {fault}: {why!r}")
            elif why and "hunter2" in why.lower():
                wrong.append(f"line {i}: {name} {raw}: the refusal repeats the value: {why!r}")
            if fault and fault == fld.credentials.get("secret") and "hunter2" in masked.lower():
                wrong.append(f"line {i}: {name} {raw}: the table's own mask shows the password: {masked}")
            refused += bool(fault)
    return wrong, n, refused


def test_every_address_of_the_shared_table_is_masked_and_refused_as_the_table_says():
    """The shared table, every row against the field it names (`_check`); at least a hundred rows, fifty refused."""
    if not os.path.exists(TABLE):
        print("  no testdata/secret_in.tsv: nothing to read")
        return
    wrong, n, refused = _check(TABLE)
    assert not wrong, f"{len(wrong)} rows of {os.path.basename(TABLE)} go another way:\n  " + "\n  ".join(wrong)
    assert n >= 100 and refused >= 50, f"the table is too short: {n} rows, {refused} refused"


def test_the_tables_reader_asks_each_row_of_the_field_it_names_and_an_unknown_name_is_the_rows_error():
    """The reader on a table of its own: rows of `vms.source` and of `rec.volumes.url`, each by its field's rule and
    `credentials` — the VMS's `session=` refused at a camera and taken at a volume, an `@` with no `://` refused at a
    volume (ADR-0053) — and rows naming a field no spec has, a table no spec has, a field that is no url, or a row of
    four columns: each the row's error, never skipped."""
    import tempfile
    rows = [
        ("vms.source", "rtsp://10.0.0.5/live?usr=admin&pwd=Hunter2", "rtsp://10.0.0.5/live?usr=admin&pwd=***", "cred_secret"),
        ("vms.source", "rtsp://admin@10.0.0.5/live", "rtsp://admin@10.0.0.5/live", "cred_username"),
        ("vms.source", "rtsp://10.0.0.5/live?session=Hunter2", "rtsp://10.0.0.5/live?session=***", "cred_secret"),
        ("vms.source", "rtsp://10.0.0.5/Streaming/Channels/101", "rtsp://10.0.0.5/Streaming/Channels/101", ""),
        ("rec.volumes.url", "s3://h/eu/bucket?session=abc", "s3://h/eu/bucket?session=abc", ""),
        ("rec.volumes.url", "https://acct.blob.example/c?sv=1&sig=Hunter2", "https://acct.blob.example/c?sv=1&sig=***", "access_secret"),
        ("rec.volumes.url", "AKIA:Hunter2@s3.example.com/eu", "AKIA:***@s3.example.com/eu", "access_secret"),
        ("rec.volumes.url", "/mnt/a@b", "/mnt/a@b", "access_key"),
        ("rec.volumes.url", "/mnt/a%40b", "/mnt/a%40b", ""),
    ]
    bad = [("vms.nosuch", "rtsp://h/x", "rtsp://h/x", ""), ("rec.nosuch.url", "s3://h/b", "s3://h/b", ""),
           ("nosuch.source", "rtsp://h/x", "rtsp://h/x", ""), ("rec.volumes.kind", "local", "local", "")]
    lines = ["# a table of the reader's own", *("\t".join([*r, "a note"]) for r in rows + bad), "vms.source\trtsp://h/x\trtsp://h/x\t"]
    with tempfile.NamedTemporaryFile("w", suffix=".tsv", encoding="utf-8", delete=False) as f:
        f.write("\n".join(lines) + "\n")
    try:
        wrong, n, refused = _check(f.name)
    finally:
        os.unlink(f.name)
    assert (n, refused) == (len(rows) + len(bad), 6), (n, refused, wrong)
    assert len(wrong) == len(bad) + 1, "\n".join(wrong)
    for (name, *_), said in zip(bad, wrong):
        assert repr(name) in said, (name, said)
    assert "a row is field, raw, masked, fault, note" in wrong[-1], wrong[-1]


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
    spec's (the product's decision, 5 Oct: a function of the platform's own, with its own table — the product's file,
    byte for byte). Each row of `testdata/log_mask.tsv`, as a process that loaded the VMS's spec masks it (the names
    its `secret_in` adds — `sig`, `psd` — beside the platform's own): `masked` is what is said of `raw`, and no row
    that hides a value shows `hunter2`."""
    from w2cplatform.secrets import mask_text
    from w2cplatform.spec import SubsystemSpec
    rules = SubsystemSpec.load(os.path.join(SOURCE, "vms", "vms.subsystem.yaml")).fields["source"].rules
    wrong, n = [], 0
    with open(LOG_MASK, encoding="utf-8") as f:
        for i, line in enumerate(f.read().split("\n"), 1):
            if not line or line.startswith("#"):
                continue
            cols = line.split("\t")
            assert len(cols) == 3, f"line {i}: a row is raw, masked, note: {line!r}"
            raw, masked, _ = cols
            n += 1
            got = mask_text(raw, rules)
            if got != masked:
                wrong.append(f"line {i}: {raw}\n    said as {got}\n    the table: {masked}")
            if "***" in masked and "hunter2" in masked.lower():
                wrong.append(f"line {i}: the table's own mask shows the password: {masked}")
    assert not wrong, f"{len(wrong)} rows of log_mask.tsv go another way:\n  " + "\n  ".join(wrong)
    assert n >= 19, f"the table is too short: {n} rows"


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
