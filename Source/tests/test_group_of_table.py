"""One table of addresses and their groups (`testdata/group_of.tsv`; ADR 0053), the course's and the product's: the group
an address puts its unit in is the HOST it names — the platform's rule (`w2cplatform.spec.url_host`), read by the url
field's `schemes`. The table says its own field and grouping in its header (`# source: {…}`, `# group_by: {…}`), and the
test builds a spec of them alone — nothing of any subsystem's; the product's test reads the same file the same way.
«Паритет» replaces the course's seed with the shared table, and this test reads that one as it reads this.

Columns: the source; its group, or `(none)` (`<none>` is read alike); the fault of a write of it — empty (taken) or
`bad_url` (`canonical.BadUrl`: refused by address — a login, no host or one nobody can tell, a scheme outside the map, a
port that is no number, a `#` of a scheme with a fragment). A readable host is a group all the same: refusing a login is
the field's, grouping is `group_by`'s, and a row written before a rule refused its source is still on the host it names."""
from __future__ import annotations

import copy
import os

import yaml

from tests.productdir import SOURCE

TABLE = os.path.join(SOURCE, "tests", "testdata", "group_of.tsv")
VMS = os.path.join(SOURCE, "vms", "vms.subsystem.yaml")
TESTSUB2 = os.path.join(SOURCE, "tests", "testdata", "testsub2.subsystem.yaml")
NONE = ("(none)", "<none>")


def _table() -> tuple[dict, dict, list]:
    """The header's two declarations, and the rows: (line, source, group or "", fault)."""
    decl, rows = {}, []
    with open(TABLE, encoding="utf-8") as f:
        for i, line in enumerate(f.read().split("\n"), 1):
            if line.startswith("#"):
                key, sep, value = line[1:].strip().partition(":")
                if sep and key in ("source", "group_by") and not rows:
                    assert key not in decl, f"line {i}: `{key}` declared twice"
                    decl[key] = yaml.safe_load(value)
                continue
            if not line:
                continue
            cols = line.split("\t") + ["", ""]
            assert cols[2] in ("", "bad_url") and not any(cols[3:]), f"line {i}: a row is source, group, fault: {line!r}"
            rows.append((i, cols[0], "" if cols[1] in NONE else cols[1], cols[2]))
    assert set(decl) == {"source", "group_by"}, f"the header declares `source` and `group_by`, not {sorted(decl)}"
    return decl["source"], decl["group_by"], rows


def _spec(source: dict, group_by: dict):
    """A spec of the header's field and grouping alone. A field that says no `secret_in` is read by the platform's common
    rules alone (`secret_in: []`) — not by whatever specs this process loaded before (`catalog.secret_rules`)."""
    from w2cplatform.spec import SubsystemSpec
    field = {"secret_in": [], **source} if source.get("type") == "url" else source
    return SubsystemSpec.from_dict({"name": "grouptable", "unit": {"rows": "items", "id": "name", "fields": {
        "name": {"type": "string"}, group_by["field"]: field}},
        "placement": {"capacity": {"from": "capacity", "default": 4}, "group_by": group_by}})


def _fault(spec, raw: str) -> str:
    from w2cplatform.spec import Refused
    try:
        spec.refuse({spec.group_by: raw})
    except Refused as e:
        return getattr(e, "fault", "") or f"a refusal of no kind: {e}"
    return ""


def test_every_address_of_the_table_is_in_the_group_and_has_the_fault_the_table_says():
    """The spec the header declares: each row's group (`SubsystemSpec.group_of`, which the controller's `group_value` and
    the worker's `request_group` ask) and the fault of writing it (`SubsystemSpec.refuse`), answered apart; and that a
    row without a group is taken only where its scheme's `none` says so (ADR 0053)."""
    source, group_by, rows = _table()
    spec = _spec(source, group_by)
    assert spec.group_cut == "host", group_by
    wrong = []
    for i, raw, group, fault in rows:
        got, why = spec.group_of(raw), _fault(spec, raw)
        if got != group:
            wrong.append(f"line {i}: {raw} is in group {got or '(none)'}; the table: {group or '(none)'}")
        if why != fault:
            wrong.append(f"line {i}: {raw}: the fault is {why or '(none)'}; the table: {fault or '(none)'}")
        if not got and not why and spec.group_refusal(raw) is not None:
            wrong.append(f"line {i}: {raw}: taken with no host to tell")
    assert not wrong, f"{len(wrong)} rows of {os.path.basename(TABLE)} go another way:\n  " + "\n  ".join(wrong)
    assert len(rows) >= 55 and sum(bool(r[3]) for r in rows) >= 20 and sum(not r[2] and not r[3] for r in rows) >= 3


def test_the_vms_and_testsub2_read_the_table_alike_where_they_declare_the_same_words():
    """The rule is the platform's and the words are the spec's: the vms spec's source and testsub2's feed group every row
    whose scheme they declare with the table's words as the table says; a scheme they declare otherwise, or not at all,
    is theirs to read (none of the table's business)."""
    from w2cplatform.spec import SubsystemSpec
    source, group_by, rows = _table()
    with open(TESTSUB2, encoding="utf-8") as f:
        two = yaml.safe_load(f)
    two = copy.deepcopy(two)
    two["unit"]["fields"]["feed"]["schemes"] = copy.deepcopy(source["schemes"])
    assert two["placement"]["group_by"] == {"field": "feed", "cut_at": "host"}
    for spec in (SubsystemSpec.load(VMS), SubsystemSpec.from_dict(two)):
        mine = spec.fields[spec.group_by].schemes
        alike = {s for s, words in mine.items() if source["schemes"].get(s) == words}
        assert alike, spec.name
        wrong = [f"line {i}: {raw} is in group {spec.group_of(raw) or '(none)'}; the table: {group or '(none)'}"
                 for i, raw, group, _ in rows if raw.partition("://")[0].lower() in alike and spec.group_of(raw) != group]
        assert not wrong, f"{spec.name}: {len(wrong)} rows go another way:\n  " + "\n  ".join(wrong)
