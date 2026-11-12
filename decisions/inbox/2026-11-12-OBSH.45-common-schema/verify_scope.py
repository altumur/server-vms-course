"""Prove the task delta against its exact baseline, including the normative JSON keywords."""
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

root = Path(sys.argv[1]).resolve()
base = sys.argv[2]
manifest = json.loads(Path(__file__).with_name("replacements.json").read_text())
expected = {row["pointer"]: row for row in manifest}
sys.path.insert(0, str(root / "skills/lesson-spec/scripts"))
import m_form
from check_spec import Check

def old_text(path):
    return subprocess.check_output(["git", "show", f"{base}:{path.relative_to(root)}"],
                                   cwd=root).decode("utf-8")

def differences(before, after, pointer=""):
    if before == after:
        return []
    assert type(before) is type(after), pointer
    if isinstance(before, dict):
        assert before.keys() == after.keys(), pointer
        return [item for key in before for item in differences(
            before[key], after[key], pointer + "/" + key.replace("~", "~0").replace("/", "~1"))]
    if isinstance(before, list):
        assert len(before) == len(after), pointer
        return [item for i, (a, b) in enumerate(zip(before, after))
                for item in differences(a, b, pointer + "/" + str(i))]
    return [(pointer, before, after)]

paths = [root / "Platform/common/data/common.schema.json"] + sorted(
    root.glob("Platform/[0-9][0-9]-*/data/*.schema.json"))
schemas, copies, counts = [], 0, Counter()
for path in paths:
    before_raw, after_raw = old_text(path), path.read_text()
    before, after = json.loads(before_raw), json.loads(after_raw)
    delta = differences(before, after)
    expected_raw = before_raw
    for pointer, old, new in delta:
        assert pointer in expected, (path, pointer)
        assert (old, new) == (expected[pointer]["before"], expected[pointer]["after"]), (path, pointer)
        encoded_old, encoded_new = json.dumps(old, ensure_ascii=False), json.dumps(new, ensure_ascii=False)
        assert expected_raw.count(encoded_old) == 1, (path, pointer)
        expected_raw = expected_raw.replace(encoded_old, encoded_new)
    assert expected_raw == after_raw, (path, "unexpected formatting change")
    for row in manifest:
        keys = row["pointer"][1:].split("/")
        if keys[1] not in after.get("$defs", {}):
            continue
        value = after
        for key in keys:
            value = value[key]
        assert value == row["after"], (path, row["pointer"])
    if delta:
        schemas.append({"path": path.relative_to(root).as_posix(), "changed_descriptions": len(delta)})
        counts[path.relative_to(root).parts[1]] += 1
        copies += len(delta)

origin = re.compile(r"ADR-[0-9]{4}|Architect's decision|C08-BACKUP-JSON-99|REC-G01|from M11/")
common = json.loads((root / "Platform/common/data/common.schema.json").read_text())
assert not origin.search(json.dumps(common, ensure_ascii=False))
assert "White_Space property of Unicode 15.0.0" in common["$defs"]["common.person_name"]["description"]

block = re.compile(r"(<!-- (form|families|canonical):begin -->\n).*?(?=<!-- \2:end -->)", re.S)
norms = []
for path in sorted(root.glob("Platform/[0-9][0-9]-*/**/*.norms.md")):
    before, after = old_text(path), path.read_text()
    if before != after:
        assert block.sub(r"\1", before) == block.sub(r"\1", after), path
        norms.append(path.relative_to(root).as_posix())

check = Check(root, scope="platform")
lesson = m_form.Lesson(check, "P/common", root / "Platform/common")
for row in manifest:
    assert m_form.address_problem(check, lesson, "data/common.schema.json#" + row["pointer"], {}) is None

print(json.dumps({"base": base, "schemas": schemas, "by_directory": dict(sorted(counts.items())),
                  "changed_descriptions": copies, "changed_norms": norms,
                  "normative_json_keywords_unchanged": True, "prose_outside_built_blocks_unchanged": True,
                  "schema_formatting_unchanged": True,
                  "history_json_pointers_resolve": True, "white_space_and_unicode_version_preserved": True},
                 ensure_ascii=False, indent=2))
