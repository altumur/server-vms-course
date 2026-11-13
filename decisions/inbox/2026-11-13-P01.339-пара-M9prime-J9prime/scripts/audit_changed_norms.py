"""Compare both writer-facing delta sections with exact M rosters and history.

Run with spec Python: audit_changed_norms.py <own checkout> <C> <M passport> <output>
This evidence contains provenance; it is outside the writer input.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

W, C, passport, output = Path(sys.argv[1]).resolve(), sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4])
HERE = Path(__file__).resolve().parents[1]
JOURNAL = HERE / "CHANGED-NORMS.md"
BASELINES = (
    ("M9", "dc0645fa329eaf7d52203dac5d4e69eb63cbd989", "2026-11-13-P01.329-пара-M9-J9"),
    ("M8′", "30310352523e30aa7e7879d901e44d80e01b118d", "2026-11-13-P01.299-пара-M8prime-J8prime"),
)


def git(*args):
    return subprocess.check_output(["git", "-C", str(W), *args])


def read(ref, path):
    return git("show", ref + ":" + path).decode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def blocks(value):
    anchors = list(re.finditer(r"<!-- req: (\S+) -->", value))
    result = {}
    for i, anchor in enumerate(anchors):
        assert anchor[1] not in result, ("duplicate anchor", anchor[1])
        part = value[anchor.end():anchors[i + 1].start() if i + 1 < len(anchors) else len(value)]
        result[anchor[1]] = re.split(r"(?m)^#{1,6} ", part, 1)[0].strip()
    return result


def check_lines(value):
    return {req: line for line, req in re.findall(
        r"(?m)^(- \[ \] \*\*(P/\d+(?:\.\d+)?-\d+)\*\*.*)$", value)}


def history_rows(old_c, lesson):
    root = "decisions/journal/platform/" + lesson + "/"
    paths = git("ls-tree", "-r", "--name-only", C, "--", root).decode().splitlines()
    result = []
    for path in paths:
        if not re.fullmatch(r"history(?:-\d+)?\.tsv", Path(path).name):
            continue
        old_file = subprocess.run(["git", "-C", str(W), "show", old_c + ":" + path],
                                  capture_output=True)
        assert old_file.returncode in (0, 128), (path, old_file.stderr)
        old = Counter(old_file.stdout.decode().splitlines()) if old_file.returncode == 0 else Counter()
        for n, line in enumerate(read(C, path).splitlines(), 1):
            if old[line]:
                old[line] -= 1
                continue
            cells = line.split("\t")
            if len(cells) != 5 or re.search(r"translation|производн", cells[2], re.I):
                continue
            req, file, source, date, removed = cells
            result.append({"history": path, "line": n, "req_id": req, "file": file,
                           "source": source, "date": date,
                           "removed": removed.replace("\\n", "\n").replace("\\t", "\t")})
    return result


raw_text = JOURNAL.read_text()
sections = {}
for match in re.finditer(r"(?ms)^## (M9|M8′) → M9′\n(.*?)(?=^## |\Z)", raw_text):
    assert match[1] not in sections
    sections[match[1]] = match[2]
assert set(sections) == {"M9", "M8′"}
new_paths = {f["path"] for f in json.loads(passport.read_text())["files"]}
assert "Platform/01-store/spec/01.3-store.norms.md" in new_paths
results = {}
for label, old_c, old_report in BASELINES:
    text = sections[label]
    old_passport = W / "decisions/inbox" / old_report / "PASSPORT-M.json"
    old_paths = {f["path"] for f in json.loads(old_passport.read_text())["files"]}
    listed = set(re.findall(r"^\| (P/\d+(?:\.\d+)?-R\d+) \|", text, re.M))
    listed_checks = {req for line in text.splitlines() if line.startswith("|")
                     for req in re.findall(r"P/\d+(?:\.\d+)?-\d+", line.split("|", 2)[1])}
    changed, proof, changed_checks, check_proof, file_proof, cached = {}, {}, {}, {}, {}, {}
    for path in sorted((old_paths | new_paths) - {"Platform/COURSE_COMMIT"}):
        before = read(old_c, path) if path in old_paths else ""
        after = read(C, path) if path in new_paths else ""
        if before == after:
            continue
        lesson, relative = path.split("/", 2)[1:]
        if lesson not in cached:
            cached[lesson] = history_rows(old_c, lesson)
        owning = [r for r in cached[lesson] if r["file"].split("#")[0] == relative]
        assert path.removeprefix("Platform/") in text, (label, "changed M file missing", path)
        file_proof[path] = {
            "kind": "added" if path not in old_paths else "removed" if path not in new_paths else "changed",
            "history": [{k: r[k] for k in ("history", "line", "req_id", "file")} for r in owning],
            "change_commits": git("log", "--format=%H", old_c + ".." + C, "--", path).decode().splitlines(),
            "diff_sha256": digest(git("diff", "--no-ext-diff", "--no-renames", old_c, C, "--", path)),
        }
        b, a = blocks(before), blocks(after)
        for req in sorted(b.keys() | a.keys()):
            if b.get(req) == a.get(req):
                continue
            matching = [r for r in owning if r["req_id"] == req or
                        (r["removed"] not in ("", "-") and r["removed"] in b.get(req, ""))]
            assert matching, (label, "paragraph has no history evidence", req)
            changed[req] = {"file": path, "kind": "added" if req not in b else "removed" if req not in a else "changed"}
            proof[req] = [{k: r[k] for k in ("history", "line", "req_id", "file")} for r in matching]
        bchecks, achecks = check_lines(before), check_lines(after)
        for req in sorted(bchecks.keys() | achecks.keys()):
            if bchecks.get(req) == achecks.get(req):
                continue
            matching = [r for r in owning if r["req_id"] == req or
                        (r["removed"] not in ("", "-") and r["removed"] in bchecks.get(req, ""))]
            assert matching, (label, "checklist item has no history evidence", req)
            changed_checks[req] = path
            check_proof[req] = [{k: r[k] for k in ("history", "line", "req_id", "file")} for r in matching]
    assert listed == changed.keys(), {"baseline": label, "missing": sorted(changed.keys() - listed),
                                      "extra": sorted(listed - changed.keys())}
    assert listed_checks == changed_checks.keys(), {"baseline": label,
        "missing_checks": sorted(changed_checks.keys() - listed_checks),
        "extra_checks": sorted(listed_checks - changed_checks.keys())}
    results[label] = {"old_C": old_c, "old_passport_sha256": digest(old_passport.read_bytes()),
        "changed_paragraphs": changed, "history_evidence": proof,
        "changed_checklist_items": changed_checks, "checklist_history_evidence": check_proof,
        "changed_M_files_evidence": file_proof,
        "files_without_own_added_English_history": [p for p, e in file_proof.items() if not e["history"]],
        "listed_exactly_changed_paragraphs": True, "OK": True}

for forbidden in ("P01.", "P02.", "P03.", "PASSPORT", "VERIFY-ALL", "GUESS"):
    assert forbidden not in raw_text, ("provenance in writer-facing journal", forbidden)
result = {"C": C, "passport_sha256": digest(passport.read_bytes()),
          "journal": str(JOURNAL.relative_to(W)), "journal_sha256": digest(JOURNAL.read_bytes()),
          "baselines": results,
          "note": "Exact paragraph/checklist/file coverage and added history evidence; summary meaning and unanchored changes reviewed by reading. The transport marker is excluded.",
          "OK": True}
output.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n")
print(json.dumps({label: {"paragraphs": len(r["changed_paragraphs"]),
                         "checklist": len(r["changed_checklist_items"]),
                         "files": len(r["changed_M_files_evidence"])} for label, r in results.items()},
                 ensure_ascii=False))
