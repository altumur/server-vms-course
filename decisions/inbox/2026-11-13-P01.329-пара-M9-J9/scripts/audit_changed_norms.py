"""Audit writer-facing M8-prime -> M9 summaries against source and history.

Run: spec-python -B audit_changed_norms.py <own checkout> <C> <M passport> <output>
This audit contains provenance and is not input to the writer.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

W, C, passport, output = Path(sys.argv[1]).resolve(), sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4])
OLD_C = "30310352523e30aa7e7879d901e44d80e01b118d"
HERE = Path(__file__).resolve().parents[1]
JOURNAL = HERE / "CHANGED-NORMS.md"


def git(*args):
    return subprocess.check_output(["git", "-C", str(W), *args])


def read(ref, path):
    return git("show", ref + ":" + path).decode()


def blocks(text):
    anchors = list(re.finditer(r"<!-- req: (\S+) -->", text))
    result = {}
    for i, anchor in enumerate(anchors):
        part = text[anchor.end():anchors[i + 1].start() if i + 1 < len(anchors) else len(text)]
        result[anchor[1]] = re.split(r"(?m)^#{1,6} ", part, 1)[0].strip()
    return result


def history_rows(lesson):
    root = "decisions/journal/platform/" + lesson + "/"
    paths = git("ls-tree", "-r", "--name-only", C, "--", root).decode().splitlines()
    result = []
    for path in paths:
        if not re.fullmatch(r"history(?:-\d+)?\.tsv", Path(path).name):
            continue
        try:
            old = Counter(read(OLD_C, path).splitlines())
        except subprocess.CalledProcessError:
            old = Counter()
        for n, line in enumerate(read(C, path).splitlines(), 1):
            if old[line]:
                old[line] -= 1
                continue
            cells = line.split("\t")
            if len(cells) != 5 or "derived Russian translation" in cells[2]:
                continue
            req, file, source, date, removed = cells
            result.append({"history": path, "line": n, "req_id": req, "file": file,
                           "source": source, "date": date,
                           "removed": removed.replace("\\n", "\n").replace("\\t", "\t")})
    return result


text = JOURNAL.read_text()
listed = set(re.findall(r"^\| (P/\d+(?:\.\d+)?-R\d+) \|", text, re.M))
listed_checks = {req for line in text.splitlines() if line.startswith("|")
                 for req in re.findall(r"P/\d+(?:\.\d+)?-\d+", line.split("|", 2)[1])}
paths = {f["path"] for f in json.loads(passport.read_text())["files"]}
assert "Platform/01-store/spec/01.3-store.norms.md" in paths
changed, proof, changed_checks, check_proof, file_proof, cached = {}, {}, {}, {}, {}, {}
for path in sorted(paths - {"Platform/COURSE_COMMIT"}):
    after = read(C, path)
    try:
        before = read(OLD_C, path)
    except subprocess.CalledProcessError:
        before = ""
    if before == after:
        continue
    lesson, relative = path.split("/", 2)[1:]
    if lesson not in cached:
        cached[lesson] = history_rows(lesson)
    rows = cached[lesson]
    owning = [r for r in rows if r["file"].split("#")[0] == relative]
    assert path.removeprefix("Platform/") in text, ("changed M file not named in journal", path)
    file_proof[path] = {
        "history": [{k: r[k] for k in ("history", "line", "file")} for r in owning],
        "change_commits": git("log", "--format=%H", OLD_C + ".." + C, "--", path).decode().splitlines(),
        "diff_sha256": hashlib.sha256(git("diff", "--no-ext-diff", "--no-renames", OLD_C, C, "--", path)).hexdigest(),
    }
    b, a = blocks(before), blocks(after)
    for req in sorted(b.keys() | a.keys()):
        if b.get(req) == a.get(req):
            continue
        kind = "added" if req not in b else "removed" if req not in a else "changed"
        matching = [r for r in owning if r["req_id"] == req or
                    (r["removed"] not in ("", "-") and r["removed"] in b.get(req, ""))]
        assert matching, ("changed paragraph has no history evidence", req)
        changed[req] = {"file": path, "kind": kind}
        proof[req] = [{k: r[k] for k in ("history", "line", "req_id", "file")} for r in matching]
    def check_lines(value):
        return {req: line for line, req in re.findall(
            r"(?m)^(- \[ \] \*\*(P/\d+(?:\.\d+)?-\d+)\*\*.*)$", value)}
    bchecks, achecks = check_lines(before), check_lines(after)
    for req in sorted(bchecks.keys() | achecks.keys()):
        if bchecks.get(req) == achecks.get(req):
            continue
        matching = [r for r in owning if r["req_id"] == req or
                    (r["removed"] not in ("", "-") and r["removed"] in bchecks.get(req, ""))]
        assert matching, ("changed checklist item has no history evidence", req)
        changed_checks[req] = path
        check_proof[req] = [{k: r[k] for k in ("history", "line", "req_id", "file")} for r in matching]

assert listed == changed.keys(), {"missing": sorted(changed.keys() - listed),
                                  "extra": sorted(listed - changed.keys())}
assert listed_checks == changed_checks.keys(), {"missing_checks": sorted(changed_checks.keys() - listed_checks),
                                               "extra_checks": sorted(listed_checks - changed_checks.keys())}
for forbidden in ("P01.186", "P01.320", "P01.324", "P03.35", "PASSPORT", "VERIFY-ALL", "GUESS"):
    assert forbidden not in text, forbidden
result = {"old_C": OLD_C, "C": C, "passport_sha256": hashlib.sha256(passport.read_bytes()).hexdigest(),
          "journal": str(JOURNAL.relative_to(W)),
          "journal_sha256": hashlib.sha256(JOURNAL.read_bytes()).hexdigest(),
          "changed_paragraphs": changed, "history_evidence": proof,
          "changed_checklist_items": changed_checks, "checklist_history_evidence": check_proof,
          "changed_M_files_evidence": file_proof,
          "files_without_own_added_English_history": [p for p, e in file_proof.items() if not e["history"]],
          "listed_exactly_changed_paragraphs": True,
          "note": "Checks paragraph/file and history coverage; meaning of summaries, checklist and unanchored changes requires reading.",
          "OK": True}
output.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n")
print(json.dumps({"changed": len(changed), "checklist": len(changed_checks), "files": len(file_proof), "OK": True}))
