"""P06.22: local read-only M from exact main; run with venv-spec Python -B.

Usage: build_m.py <own worktree> <new evidence directory with CHECK-SPEC-C.run.json>
Uses unchanged P02.52 functions and exact-C pair_m; publishes no M/J pair.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys

W, B = (Path(p).resolve() for p in sys.argv[1:3])
C = (B / "C.txt").read_text().strip()


def git(*args):
    return subprocess.check_output(["git", "-C", str(W), *args])


def dump(name, value):
    (B / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def run(name, args, cwd=None):
    r = subprocess.run(args, cwd=cwd, capture_output=True)
    (B / (name + ".out")).write_bytes(r.stdout)
    (B / (name + ".err")).write_bytes(r.stderr)
    dump(name + ".run.json", {"argv": args, "cwd": str(cwd) if cwd else str(Path.cwd()), "exit": r.returncode,
         "stdout_sha256": sha(r.stdout), "stderr_sha256": sha(r.stderr)})
    assert r.returncode == 0, (name, r.returncode, r.stderr.decode())
    return r.stdout


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


assert git("branch", "--show-current").decode().strip() == "task/P06.22"
assert C == git("rev-parse", "HEAD").decode().strip()
assert subprocess.run(["git", "-C", str(W), "merge-base", "--is-ancestor", "94130b70abaaa07b1479efa4f86e16ebe3c839a9", C]).returncode == 0
assert C == git("rev-parse", "origin/main").decode().strip()
assert not git("diff", C, "--", "Platform", "skills/lesson-spec")
check = json.loads((B / "CHECK-SPEC-C.run.json").read_text())
assert check["C"] == C and check["exit"] == 0
(B / "operator").mkdir()
operator_path = "decisions/inbox/2026-11-11-P02.52-операторы/operator/b7_export_pair.py"
raw = git("show", C + ":" + operator_path)
assert sha(raw) == "326726720e4a1da93acb14f4500b4263913c326af68e1997fb2d9dd41c41482f"
(B / "operator/b7_export_pair.py").write_bytes(raw)
identities = {"b7_export_pair.py": {"source": C + ":" + operator_path,
              "sha256": sha(raw), "byte_equal": True}}
for name, expected in (
    ("m_passport.py", "c19d8f35fc431904f021be8618a70bbde0714c18c9d54b9a7f6e48058f827cdc"),
    ("check_m_passport.py", "4c23afc9fe7d0b68ca10681c01b6beef38faa3d6e57bef37f381ae003f8e6d4c"),
):
    source = Path("/home/pilot/P01.360-evidence/operator") / name
    raw = source.read_bytes()
    assert sha(raw) == expected
    (B / "operator" / name).write_bytes(raw)
    identities[name] = {"source": str(source), "sha256": sha(raw), "byte_equal": True}
dump("OPERATOR-UNCHANGED.json", identities)
shutil.copyfile(__file__, B / "build_m.py")

run("INIT-SOURCE", ["git", "init", "--bare", "--template=", str(B / "source.git")])
run("FETCH-SOURCE", ["git", "--git-dir", str(B / "source.git"), "fetch",
    "--no-tags", "--depth=1", str(W), C])
op = load_module("b7_export_pair", B / "operator/b7_export_pair.py")
fd = op._open_dir(B / "source.git")
try:
    entries = op._source(fd, C)
finally:
    os.close(fd)
entries[op.MARKER] = ("100644", None, (C + "\n").encode())
classification = op._classification(entries)
cases = op._case_boundary(entries, classification)
assert classification[op.DERIVED] == "model_and_judge"
op._legacy_model_content_guard({p: e for p, e in entries.items()
                               if classification[p] == "model_and_judge"})
filter_raw, _, filter_sources = op._assemble(entries)
(B / "FILTER-M.json").write_bytes(filter_raw)

sys.path.insert(0, str(W / "skills/lesson-spec/scripts"))
import export_lists
import m_form

assembled, errors, _ = export_lists.assemble(W)
assert not errors, errors
model = {row["path"]: row["disposition"] for row in assembled["model"]}
assert all(classification[p] == disposition for p, disposition in model.items())
assert set(classification) == model.keys() | {op.MARKER}
ctx = type("Check", (), {"root": W})()
lesson = m_form.Lesson(ctx, "P/06", W / "Platform/06-console")
selected = m_form.pair_m(ctx, lesson, model)
assert selected is not None
deps = m_form.dependencies(ctx, lesson)
assert deps <= selected, sorted(deps - selected)
selected = selected | {op.MARKER}
assert not selected & cases
assert all(classification[p] == "model_and_judge" for p in selected)
retained = {p: entries[p] for p in selected}
fd = op._open_dir(B)
try:
    meta = op._emit(fd, "M.git", retained, "model")
finally:
    os.close(fd)
fd = op._open_dir(B / "M.git")
try:
    op._seal_tree(fd, meta)
finally:
    os.close(fd)
M = meta["commit"]
dump("SELECTION.json", {"C": C, "M": M, "rule": "exact-C m_form.pair_m + COURSE_COMMIT",
    "m_form_sha256": sha((W / "skills/lesson-spec/scripts/m_form.py").read_bytes()),
    "filter_blob": op._blob_id(filter_raw), "filter_sources": filter_sources,
    "dependencies": sorted(deps), "selected": sorted(selected),
    "registered_case_tables_excluded": len(cases), "metadata": meta,
    "operator_functions": ["_source", "_classification", "_case_boundary",
        "_legacy_model_content_guard", "_assemble", "_emit", "_seal_tree"],
    "scope": "local M only for readers under P06.22; no pair release", "OK": True})
run("M-PASSPORT", [sys.executable, "-B", str(B / "operator/m_passport.py"),
    "--m-git-dir", str(B / "M.git"), "--m-commit", M, "--output", str(B / "PASSPORT-M.json")])
passport = json.loads((B / "PASSPORT-M.json").read_text())
assert passport["C"] == C and passport["count"] == len(selected)
source_modes = {}
for record in git("ls-tree", "-rz", C).split(b"\0"):
    if record:
        header, relative = record.split(b"\t", 1)
        mode, kind, oid = header.decode().split()
        source_modes[relative.decode()] = (mode, kind, oid)
for row in passport["files"]:
    if row["path"] == op.MARKER:
        assert row["mode"] == "100644" and row["blob"] == op._blob_id((C + "\n").encode())
    else:
        assert source_modes[row["path"]] == (row["mode"], "blob", row["blob"])
dump("VERIFY-SOURCE-MODES.json", {"C": C, "M": M, "count": len(selected), "source_modes_and_blobs_exact": True, "OK": True})
root = B / "M"
root.mkdir()
producer = subprocess.Popen(["git", "--git-dir", str(B / "M.git"), "archive", M], stdout=subprocess.PIPE)
consumer = subprocess.run(["tar", "-x", "-C", str(root)], stdin=producer.stdout)
producer.stdout.close()
assert producer.wait() == consumer.returncode == 0
expected = {f["path"]: f for f in passport["files"]}
assert {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()} == expected.keys()
checksums = []
for relative, row in sorted(expected.items()):
    path = root / relative
    assert stat.S_ISREG(path.lstat().st_mode)
    raw = path.read_bytes()
    assert op._blob_id(raw) == row["blob"]
    assert raw == ((C + "\n").encode() if relative == op.MARKER else git("show", C + ":" + relative))
    assert len(raw) == row["size"]
    path.chmod(0o555 if row["mode"] == "100755" else 0o444)
    checksums.append(sha(raw) + "  M/" + relative + "\n")
for path in sorted((p for p in root.rglob("*") if p.is_dir()), reverse=True):
    path.chmod(0o555)
root.chmod(0o555)
(B / "SHA256SUMS").write_text("".join(checksums))
for path in (B / "PASSPORT-M.json", B / "SHA256SUMS"):
    path.chmod(0o444)
assert all(not p.is_symlink() and not p.lstat().st_mode & 0o222 for p in (root, *root.rglob("*")))
assert all((root / row["path"]).stat().st_mode & 0o777 == (0o555 if row["mode"] == "100755" else 0o444) for row in passport["files"])
assert all(p.stat().st_mode & 0o777 == 0o555 for p in (root, *[d for d in root.rglob("*") if d.is_dir()]))
run("CHECK-PASSPORT", [sys.executable, "-I", "-B", str(B / "operator/check_m_passport.py"),
    str(B / "PASSPORT-M.json"), str(root), M])
run("CHECK-SHA256SUMS", ["sha256sum", "--check", "SHA256SUMS"], cwd=B)
run("FSCK-M", ["git", "--git-dir", str(B / "M.git"), "fsck", "--full", "--strict"])
out = {"C": C, "M": M, "files": len(selected), "directory": str(root),
       "passport": str(B / "PASSPORT-M.json"), "passport_sha256": sha((B / "PASSPORT-M.json").read_bytes()),
       "files_sha256": passport["files_sha256"], "SHA256SUMS": str(B / "SHA256SUMS"),
       "SHA256SUMS_sha256": sha((B / "SHA256SUMS").read_bytes()),
       "source_bytes_exact": True, "paths_and_modes_exact": True, "all_write_bits_cleared": True,
       "passport_check_exit": 0, "sha256sum_check_exit": 0, "fsck_exit": 0, "OK": True}
dump("VERIFY-M.json", out)
print(json.dumps(out, ensure_ascii=False, indent=2))
