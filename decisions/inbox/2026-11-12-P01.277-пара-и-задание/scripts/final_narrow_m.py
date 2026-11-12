"""Finalize only M after P01.277 answered 2026-11-12T20:17:43Z.

The raw pair, full J and J-input are read-only. Existing preliminary M/passport
are retained. No pair/J-input operator is called here.
Usage: spec-python -B final_narrow_m.py <evidence>
"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys

B = Path(sys.argv[1]).resolve()
I = json.loads((B / "IDENTITIES.json").read_text())
sys.path.insert(0, str(B / "archive-C/skills/lesson-spec/scripts"))
sys.path.insert(0, str(B / "operator"))
import b7_export_pair as operator
import export_lists
import m_form


def git(repo, *args):
    return subprocess.check_output(["git", "--git-dir", str(repo), *args])


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


assembled, errors, _ = export_lists.assemble(B / "archive-C")
assert not errors
model = {row["path"]: row["disposition"] for row in assembled["model"]}
check = type("Check", (), {"root": B / "archive-C"})()
lesson = m_form.Lesson(check, "P/01", check.root / "Platform/01-store")
base = m_form.pair_m(check, lesson, model)
assert base is not None
excluded = {"Platform/common/acceptance/testsub-stand.md", "Platform/common/vectors/slot/README.md"}
assert excluded <= base
selected = base - excluded
assert len(selected) == 178
marker = "Platform/COURSE_COMMIT"
assert marker not in base and not (check.root / marker).exists()
selected.add(marker)
raw_repo = Path(I["pair_directory"]) / "M.git"
raw = {}
for row in git(raw_repo, "ls-tree", "-rz", I["raw_M"]).split(b"\0"):
    if row:
        header, path = row.split(b"\t", 1)
        mode, kind, oid = header.decode().split()
        assert kind == "blob"
        raw[path.decode()] = (mode, oid)
assert selected <= raw.keys()
entries = {path: (*raw[path], git(raw_repo, "cat-file", "blob", raw[path][1])) for path in selected}
out = B / "narrow-final"
out.mkdir()
fd = os.open(out, os.O_RDONLY | os.O_DIRECTORY)
try:
    result = operator._emit(fd, "M.git", entries, "model")
finally:
    os.close(fd)
M = result["commit"]
passport = B / "passport" / ("PASSPORT-M-" + M[:12] + ".json")
argv = [sys.executable, "-B", str(B / "operator/m_passport.py"), "--m-git-dir", str(out / "M.git"),
        "--m-commit", M, "--output", str(passport)]
p = subprocess.run(argv, capture_output=True)
(B / "M-FINAL-PASSPORT.out").write_bytes(p.stdout)
(B / "M-FINAL-PASSPORT.err").write_bytes(p.stderr)
dump(B / "M-FINAL-PASSPORT.run.json", {"argv": argv, "exit": p.returncode})
assert p.returncode == 0, p.stderr.decode()
for name in ("IDENTITIES.json", "NARROW-M.json", "PREP-FULL.json", "PREP-FULL.err", "PREP-FULL.run.json"):
    shutil.copyfile(B / name, B / ("PRELIMINARY-" + name))
I.update(M=M, M_git=str(out / "M.git"), M_passport=str(passport), M_passport_sha256=sha(passport))
dump(B / "IDENTITIES.json", I)
dump(B / "NARROW-M.json", {"rule": "exact-C pair_m, two authorized whole-file exclusions, mandatory transport marker",
     "authority": "P01.277 answered 2026-11-12T20:17:43Z; ADR-0133 (93) item 6; P01.280/P01.283",
     "task_at_final_sha256": sha(Path('/home/pilot/cammeta-sessions/tasks/P01.277.yaml')),
     "rule_sha256": sha(check.root / "skills/lesson-spec/scripts/m_form.py"),
     "pair_m_source_count": len(base), "pair_only_exclusions": sorted(excluded),
     "M_source_count": len(selected) - 1, "M_count": len(selected), "M": M, "raw_M": I["raw_M"],
     "raw_M_count": len(raw), "transport_marker": marker,
     "marker_basis": "unchanged pair operator requires marker in both; unchanged m_passport refuses without marker",
     "dependencies": sorted(m_form.dependencies(check, lesson)), "selected": sorted(selected),
     "removed_from_raw_M": sorted(raw.keys() - selected), "J_JI_unchanged": True, "OK": True})
print(json.dumps(I, indent=1))
