"""Static evidence for OBSH.97; never imports or runs candidate code."""
import csv
import io
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = "a8e9c7f694495fc4ce5a746b2ebfabf9f1ceeccf"
sys.path.insert(0, str(ROOT / "skills/lesson-spec/scripts"))
import check_forms
from v7.vectors import loader


def before(path):
    return subprocess.check_output(["git", "show", f"{BASE}:{path}"], cwd=ROOT)


def table(data):
    lines = [s for s in data.decode().splitlines() if s and not s.startswith("#")]
    header = lines[0].split("\t")
    assert all(len(s.split("\t")) == len(header) for s in lines)
    rows = list(csv.DictReader(io.StringIO("\n".join(lines)), delimiter="\t", quoting=csv.QUOTE_NONE))
    assert len({r[header[0]] for r in rows}) == len(rows)
    return header, rows


package = "Platform/common/vectors/row-check/"
cases_path = package + "cases.tsv"
old_header, old_cases = table(before(cases_path))
header, cases = table((ROOT / cases_path).read_bytes())
assert header == old_header[:-1] + ["manifest", "credential_fields", "note"]
assert [{k: r[k] for k in old_header} for r in cases[:len(old_cases)]] == old_cases
assert all(not r["credential_fields"] for r in cases[:len(old_cases)])
new_cases = cases[len(old_cases):]
assert len(new_cases) == 35
for row in cases:
    for column in ("body", "rows"):
        assert isinstance(json.loads(row[column]), dict)
    for column in ("stored", "row", "credential_fields"):
        if row[column]:
            json.loads(row[column])
    assert (ROOT / row["manifest"]).is_file()

state_path = package + "state.tsv"
old_state_bytes = before(state_path)
state_bytes = (ROOT / state_path).read_bytes()
assert state_bytes.startswith(old_state_bytes)
_, old_states = table(old_state_bytes)
_, states = table(state_bytes)
assert len(states) - len(old_states) == 5
for row in states:
    for column in ("name", "unit", "state", "expect"):
        json.loads(row[column])

wire_path = "Platform/common/vectors/wire.cases.tsv"
_, old_wire = table(before(wire_path))
_, wire = table((ROOT / wire_path).read_bytes())
select = lambda rows: next(r for r in rows if r["package"] == "common/row-check")
old_binding, binding = select(old_wire), select(wire)
assert json.loads(binding["expect"])[:len(json.loads(old_binding["expect"]))] == json.loads(old_binding["expect"])
inputs = json.loads(binding["inputs"])
assert inputs == json.loads(old_binding["inputs"])
assert set(inputs[0]["cells"]) == {"unit", "op", "body", "stored", "rows"}
files = json.loads(binding["files"])
assert files["testsub2.subsystem.yaml"] == {"base": "root", "path": "{manifest}"}
errors, stats = check_forms.check_wire(ROOT / wire_path)
assert not errors, errors

fixture_path = package + "fixtures/testsub2.subsystem.yaml"
fixture_result = loader(ROOT).judge((ROOT / fixture_path).read_bytes())
assert fixture_result["verdict"] == "ok", fixture_result
for path in ("Platform/common/data/testsub/testsub.subsystem.yaml",
             "Platform/common/data/testsub/testsub2.subsystem.yaml"):
    assert (ROOT / path).read_bytes() == before(path)

for path, disposition in (
    ("Platform/common/export-model-filter.json", "judge_only"),
    ("Platform/common/acceptance/judge-input-filter.json", "include"),
):
    previous = json.loads(before(path))
    current = json.loads((ROOT / path).read_text())
    added = [r for r in current["files"] if r["path"] == fixture_path]
    assert len(added) == 1 and added[0]["disposition"] == disposition
    assert [r for r in current["files"] if r["path"] != fixture_path] == previous["files"]
    paths = [r["path"] for r in current["files"]]
    assert paths == sorted(set(paths), key=lambda s: s.encode("utf-8"))

print(json.dumps({
    "base": BASE,
    "preserved_case_rows": len(old_cases),
    "preserved_case_columns": len(old_header),
    "new_cases": [r["case"] for r in new_cases],
    "case_counts": dict(Counter(r["expect"] for r in cases)),
    "preserved_state_rows": len(old_states),
    "new_states": [r["case"] for r in states[len(old_states):]],
    "state_counts": {
        "acts": sum(json.loads(r["expect"])["acts"] for r in states),
        "unreadable": sum(json.loads(r["expect"])["unreadable"] for r in states),
        "readable_nonacting": sum(not json.loads(r["expect"])["acts"] and not json.loads(r["expect"])["unreadable"] for r in states),
    },
    "wire": stats,
    "fixture": {k: fixture_result[k] for k in ("verdict", "layer", "paths", "rows")},
    "filters": "only the judge-only fixture added; M/J dispositions and ordering checked",
    "canonical_manifests": "unchanged",
    "result": "PASS static data checks; candidate execution not performed",
}, indent=2, ensure_ascii=False))
