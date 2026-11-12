"""OBSH.45: update eight descriptions from a fixed manifest; retain all local schema deltas.

The former v7.build reads common.form.yaml, removed from the course. Use JSON
string serialization with expected-old guards, retaining the local formatting.
Usage: python refresh_common.py COURSE_ROOT
"""
import copy
import json
import sys
from collections import Counter
from pathlib import Path

root = Path(sys.argv[1]).resolve()

manifest = json.loads(Path(__file__).with_name("replacements.json").read_text())
common = root / "Platform/common/data/common.schema.json"
paths = [common] + sorted(root.glob("Platform/[0-9][0-9]-*/data/*.schema.json"))
pending = []
counts = Counter()
for path in paths:
    raw = path.read_text()
    doc = json.loads(raw)
    before = copy.deepcopy(doc)
    for change in manifest:
        keys = change["pointer"][1:].split("/")
        if keys[1] not in doc.get("$defs", {}):
            continue
        parent = doc
        for key in keys[:-1]:
            parent = parent[key]
        assert parent[keys[-1]] in (change["before"], change["after"]), (path, change["pointer"])
        if parent[keys[-1]] == change["before"]:
            old = json.dumps(change["before"], ensure_ascii=False)
            new = json.dumps(change["after"], ensure_ascii=False)
            assert raw.count(old) == 1, (path, change["pointer"], "non-unique JSON string")
            raw = raw.replace(old, new)
            parent[keys[-1]] = change["after"]
    assert json.loads(raw) == doc, path
    if doc != before:
        pending.append((path, raw))
        counts[path.relative_to(root).parts[1]] += 1

# Validate every source/copy before writing any of them.
for path, text in pending:
    path.write_text(text)

history = root / "decisions/journal/platform/common/history.tsv"
lines = history.read_text().splitlines()
added = 0
for change in manifest:
    for removed in change["removed"]:
        line = "\t".join(("-", "data/common.schema.json#" + change["pointer"],
                          change["source"], change["date"], removed))
        if line not in lines:
            lines.append(line)
            added += 1
history.write_text("\n".join(lines) + "\n")
print(json.dumps({"changed_schemas": len(pending), "by_directory": dict(sorted(counts.items())),
                  "history_rows_added": added}, ensure_ascii=False, indent=2))
