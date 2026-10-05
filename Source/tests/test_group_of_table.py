"""One table of sources and their groups (`testdata/group_of.tsv`): the group a camera's source puts it in is the HOST it
names (`placement.group_by: {field: source, cut_at: host, schemes: …}`; «Архитектор», 2026-10-06) — the platform's rule
(`w2cplatform.spec.url_host`), read with the vms spec's declaration of how `driverpack://` and `ipint://` write their host.
The product's `deviceOf` (vmsworker/vms/gate.go) answers the same rows; «Паритет» replaces the file with the table
shared with the product, and this test reads that one as it reads this.

Columns: the source; its group, or `(none)`; `refused` when a write of it is refused — by the field (`refusal`: its
`secret_in` and address rules) or because no host can be told in it (`SubsystemSpec.group_refusal`, ADR 0053). A readable
host is a group all the same: refusing a login is the field's, grouping is `group_by`'s, and a row written before a rule
refused its source is still on the host it names. The only rows without a group and not refused are the `none` ones (a
file). A note may follow."""
from __future__ import annotations

import copy
import os

import yaml

from tests.productdir import SOURCE

TABLE = os.path.join(SOURCE, "tests", "testdata", "group_of.tsv")
VMS = os.path.join(SOURCE, "vms", "vms.subsystem.yaml")
TESTSUB2 = os.path.join(SOURCE, "tests", "testdata", "testsub2.subsystem.yaml")
SCHEMES = {"ipint": {"fragment": "none"}, "driverpack": {"host": "path", "none": ["file"]}}


def _rows():
    with open(TABLE, encoding="utf-8") as f:
        for i, line in enumerate(f.read().split("\n"), 1):
            if not line or line.startswith("#"):
                continue
            cols = line.split("\t")
            assert len(cols) >= 2 and (len(cols) < 3 or cols[2] in ("", "refused")), \
                f"line {i}: a row is address, group, [refused], [note]: {line!r}"
            yield i, cols[0], ("" if cols[1] == "(none)" else cols[1]), len(cols) > 2 and cols[2] == "refused"


def _wrong(spec, refusals: bool) -> list[str]:
    """Each row's group; that a host nobody can tell is refused exactly where the table has no group and a refusal; and —
    `refusals` — that a write of the source is refused exactly where the table says."""
    source = spec.fields[spec.group_by]
    wrong = []
    for i, raw, group, refused in _rows():
        got = spec.group_of(raw)
        if got != group:
            wrong.append(f"line {i}: {raw} is in group {got or '(none)'}; the table: {group or '(none)'}")
        no_host = spec.group_refusal(raw)
        if (no_host is not None) != (refused and not group):
            wrong.append(f"line {i}: {raw}: no host to tell is {'' if no_host else 'not '}refused: {no_host!r}")
        why = source.refusal(raw) or no_host
        if refusals and (why is not None) != refused:
            wrong.append(f"line {i}: {raw} is {'' if refused else 'not '}refused by the table, and a write says {why!r}")
    return wrong


def test_every_source_of_the_table_is_in_the_group_the_table_says_and_refused_where_it_says():
    """The vms spec as shipped: each row's group (`SubsystemSpec.group_of`, which the controller's `group_value` and the
    worker's `request_group` ask), and whether the source field refuses it — the two answered apart."""
    from w2cplatform.spec import SubsystemSpec
    spec = SubsystemSpec.load(VMS)
    assert (spec.group_by, spec.group_cut, spec.group_schemes) == ("source", "host", SCHEMES)
    wrong = _wrong(spec, refusals=True)
    assert not wrong, f"{len(wrong)} rows of {os.path.basename(TABLE)} go another way:\n  " + "\n  ".join(wrong)
    rows = list(_rows())
    assert len(rows) >= 40 and sum(r[3] for r in rows) >= 8 and sum(not r[2] for r in rows) >= 15, len(rows)


def test_the_same_rows_through_a_spec_that_is_not_the_vms_give_the_same_groups():
    """The rule is the platform's and the words are the spec's: testsub2 — a subsystem of the platform's tests — with its
    `feed` taking the table's schemes and its `group_by` declaring them as the vms spec does, groups every row alike."""
    from w2cplatform.spec import SubsystemSpec
    with open(TESTSUB2, encoding="utf-8") as f:
        d = yaml.safe_load(f)
    d = copy.deepcopy(d)
    d["unit"]["fields"]["feed"]["schemes"] = ["driverpack", "ipint", "rtsp", "rtsps", "http", "https", "onvif"]
    d["placement"]["group_by"] = {"field": "feed", "cut_at": "host", "schemes": copy.deepcopy(SCHEMES)}
    spec = SubsystemSpec.from_dict(d)
    wrong = _wrong(spec, refusals=False)
    assert not wrong, f"{len(wrong)} rows go another way through testsub2:\n  " + "\n  ".join(wrong)
    # …and without the declaration the vendor is the host, a file is a host named `file`, and '#' ends the host
    d["placement"]["group_by"] = {"field": "feed", "cut_at": "host"}
    plain = SubsystemSpec.from_dict(d)
    assert plain.group_of("driverpack://acme/10.0.0.50/ch/17") == "acme"
    assert plain.group_of("driverpack://file/clips/a.mp4") == "file"
    assert plain.group_of("ipint://cam7#@nvr50/Acme/N8") == "cam7"
