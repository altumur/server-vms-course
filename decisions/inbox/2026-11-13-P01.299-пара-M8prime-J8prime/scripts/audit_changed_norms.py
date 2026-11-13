"""Check history coverage of the writer-facing journal; no judge inputs or reports.

Usage: spec-python -B audit_changed_norms.py <own source checkout> <C> <output.json>
The output contains provenance for the reviewer and is not an input to the writer.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

W, C, output = Path(sys.argv[1]).resolve(), sys.argv[2], Path(sys.argv[3])
OLD_C = "70c969fe200a8d785a8b86f698f938d24310cf2c"
JOURNAL = Path(__file__).resolve().parents[1] / "CHANGED-NORMS.md"


def git(*args):
    return subprocess.check_output(["git", "-C", str(W), *args])


def read(ref, path):
    return git("show", ref + ":" + path).decode()


def blocks(text):
    anchors = list(re.finditer(r"<!-- req: (\S+) -->", text))
    result = {}
    for i, anchor in enumerate(anchors):
        part = text[anchor.end():anchors[i + 1].start() if i + 1 < len(anchors) else len(text)]
        # Text after the next heading belongs to that section, not to the last R-id.
        result[anchor[1]] = re.split(r"(?m)^#{1,6} ", part, 1)[0].strip()
    return result


text = JOURNAL.read_text()
listed = set(re.findall(r"^\| (P/01\.[13]-R\d+) \|", text, re.M))
changed, proof, explicit_history = {}, {}, set()
for chapter in (1, 3):
    norms = f"Platform/01-store/spec/01.{chapter}-store.norms.md"
    history = f"decisions/journal/platform/01-store/history-{chapter}.tsv"
    before, after = blocks(read(OLD_C, norms)), blocks(read(C, norms))
    old_rows = Counter(read(OLD_C, history).splitlines())
    rows = []
    for n, line in enumerate(read(C, history).splitlines(), 1):
        if old_rows[line]:
            old_rows[line] -= 1
            continue
        cells = line.split("\t")
        if len(cells) != 5 or cells[0] == "req_id":
            continue
        req, file, source, date, removed = cells
        if "derived Russian translation" in source:
            continue
        rows.append((n, req, file, removed.replace("\\n", "\n")))
        if req.startswith("P/01."):
            explicit_history.add(req)
    for req in sorted(before.keys() | after.keys()):
        if before.get(req) == after.get(req):
            continue
        assert req in before and req in after, ("unexpected added/removed P/01 R-id", req)
        changed[req] = norms
        matching = [{"history": history, "line": n, "req_id": rid, "file": file}
                    for n, rid, file, removed in rows
                    if file.split("#")[0] == norms.split("Platform/01-store/")[1]
                    and (rid == req or (removed and removed in before[req]))]
        assert matching, ("changed paragraph has no history evidence", req)
        proof[req] = matching

assert listed == changed.keys(), {"missing": sorted(changed.keys() - listed),
                                  "extra": sorted(listed - changed.keys())}
assert explicit_history <= listed, sorted(explicit_history - listed)
# The deliverable describes visible specification changes, not review diagnoses.
for forbidden in ("P01.186", "P01.236", "P01.297", "P01.305", "P01.306", "P01.307", "P01.308",
                  "GUESS", "PASSPORT", "VERIFY-ALL", "PREFLIGHT", "owner-receipts"):
    assert forbidden not in text, forbidden
result = {"old_C": OLD_C, "C": C, "journal": str(JOURNAL.relative_to(W)),
          "journal_sha256": hashlib.sha256(JOURNAL.read_bytes()).hexdigest(),
          "changed_P01_paragraphs": changed, "history_explicit_ids": sorted(explicit_history),
          "history_evidence": proof, "listed_exactly_changed_P01_paragraphs": True,
          "note": "Checks id/history coverage, not semantic equality of the summaries or external dependency rewrites.",
          "OK": True}
output.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n")
print(json.dumps({"C": C, "changed": len(changed), "history_explicit": len(explicit_history), "OK": True}))
