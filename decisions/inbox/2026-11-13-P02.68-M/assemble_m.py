"""P02.68: local M, unchanged P02.52 pair operator, exact-C narrow selection.

Usage: venv-spec/bin/python -B assemble_m.py <own worktree> <C> <fresh evidence> <fresh M>
The caller fetches origin/main first. No candidate or trial process is launched.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time

W, C, B, ROOT = Path(sys.argv[1]).resolve(), sys.argv[2], Path(sys.argv[3]).resolve(), Path(sys.argv[4]).resolve()
BASE = "a494be12d54c2e596467c1508973da3031af2088"
BASE_DOC = "decisions/inbox/2026-11-13-P01.360-пара-M12-J12"
OP_DOC = "decisions/inbox/2026-11-11-P02.52-операторы/operator"
REVIEW = "decisions/inbox/ревью/2026-11-13-P01.365-ревью-записей-фильтра.md"
TASKS = Path("/home/pilot/cammeta-sessions/tasks")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(name, value):
    (B / name).write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n")


def git(repo, *args):
    return subprocess.check_output(["git", "--git-dir", str(repo), *args], stderr=subprocess.PIPE)


def run(name, argv, cwd=None):
    start = time.monotonic()
    result = subprocess.run(argv, cwd=cwd, capture_output=True)
    (B / (name + ".out")).write_bytes(result.stdout)
    (B / (name + ".err")).write_bytes(result.stderr)
    dump(name + ".run.json", {"argv": argv, "cwd": str(cwd or B), "C": C,
         "exit": result.returncode, "seconds": time.monotonic() - start,
         "stdout_sha256": sha(B / (name + ".out")), "stderr_sha256": sha(B / (name + ".err"))})
    assert result.returncode == 0, (name, result.returncode)
    return result.stdout


def tree(repo, ref):
    out = {}
    for row in git(repo, "ls-tree", "-rz", ref).split(b"\0"):
        if row:
            header, path = row.split(b"\t", 1)
            mode, kind, oid = header.decode().split()
            assert kind == "blob" and mode in {"100644", "100755"}
            out[path.decode()] = (mode, oid)
    return out


assert re.fullmatch("[0-9a-f]{40}", C)
assert subprocess.check_output(["git", "-C", str(W), "rev-parse", "origin/main"]).decode().strip() == C
assert subprocess.check_output(["git", "-C", str(W), "branch", "--show-current"]).decode().strip() == "task/P02.68"
assert not B.exists() and not ROOT.exists(), "retain earlier outputs; never overwrite"
B.mkdir(mode=0o700)
(B / "C.txt").write_text(C + "\n")
(B / "TASK-at-source.yaml").write_bytes((TASKS / "P02.68.yaml").read_bytes())
assert REVIEW.encode() in (B / "TASK-at-source.yaml").read_bytes()
subprocess.run(["git", "clone", "--bare", "--no-hardlinks", str(W), str(B / "source.git")], check=True, capture_output=True)
A = B / "archive-C"
A.mkdir()
p = subprocess.Popen(["git", "--git-dir", str(B / "source.git"), "archive", C], stdout=subprocess.PIPE)
r = subprocess.run(["tar", "-x", "-C", str(A)], stdin=p.stdout)
p.stdout.close()
assert p.wait() == r.returncode == 0
(B / "operator").mkdir()
expected = json.loads((A / BASE_DOC / "OPERATOR-UNCHANGED.json").read_text())["files_sha256"]
operators = {}
for name in ("b7_export_pair.py", "judge_input_export.py", "m_passport.py", "check_m_passport.py"):
    old = A / OP_DOC / name if name in {"b7_export_pair.py", "judge_input_export.py"} else Path("/home/pilot/P01.360-evidence/operator") / name
    shutil.copyfile(old, B / "operator" / name)
    assert sha(B / "operator" / name) == expected[name]
    operators[name] = {"source": str(old), "sha256": expected[name], "unchanged": True}
dump("OPERATOR-UNCHANGED.json", {"C": C, "operators": operators, "OK": True})
(B / "scripts").mkdir()
for name in ("preflight.py", "filter_delta.py"):
    raw = (A / BASE_DOC / "scripts" / name).read_bytes()
    if name == "preflight.py":
        raw = raw.replace(b"P01.360", b"P02.68")
    (B / "scripts" / name).write_bytes(raw)
shutil.copyfile(Path(__file__), B / "scripts/assemble_m.py")
run("CHECK-SPEC-C", [sys.executable, "-B", "skills/lesson-spec/scripts/check_spec.py", "--scope", "platform"], A)
for name, args in (("PREFLIGHT", ["preflight.py", C, str(B / "source.git")]),
                   ("FILTER-DELTA", ["filter_delta.py", BASE, C, str(B / "source.git")])):
    raw = run(name, [sys.executable, "-B", str(B / "scripts" / args[0]), *args[1:]], B)
    (B / (name + ".json")).write_bytes(raw)

# The accepted baseline covers unchanged classifications; this explicit review covers
# both new J-only records, without claiming a new or generic blanket authorization.
(B / "reviews").mkdir()
accepted = {}
for name in ("P01.360", "P01.365"):
    raw = (TASKS / "accepted" / (name + ".json")).read_bytes()
    rec = json.loads(raw)
    assert rec["status"] == "accepted"
    subprocess.run(["git", "-C", str(W), "merge-base", "--is-ancestor", rec["commit"], C], check=True)
    (B / "reviews" / (name + "-accepted.json")).write_bytes(raw)
    accepted[name] = rec
shutil.copyfile(A / BASE_DOC / "FILTER-REVIEWS.json", B / "reviews/P01.360-filter-reviews.json")
shutil.copyfile(A / REVIEW, B / "reviews/P01.365-filter-review.md")
delta = json.loads((B / "FILTER-DELTA.json").read_text())
paths = ["Platform/01-store/forms/production/threshold-approvals.json",
         "Platform/01-store/forms/production/threshold-approvals.schema.json"]
assert delta["from"] == BASE and delta["to"] == C
assert delta["added"] == [{"path": p, "M": "judge_only", "JI": "include"} for p in paths]
assert not delta["changed"] and not delta["removed"]
review_raw = (A / REVIEW).read_text()
assert "Claude Opus 5.5" in review_raw and "Codex" in review_raw and all(p in review_raw for p in paths)
reviews = {"C": C, "baseline_C": BASE, "baseline_acceptance": "reviews/P01.360-accepted.json",
    "baseline_acceptance_sha256": sha(B / "reviews/P01.360-accepted.json"),
    "baseline_reviews": "reviews/P01.360-filter-reviews.json", "baseline_reviews_sha256": sha(B / "reviews/P01.360-filter-reviews.json"),
    "delta_sha256": sha(B / "FILTER-DELTA.json"), "filter_author_provider": "codex", "filter_reviewer_provider": "claude",
    "all_delta_records_covered": True, "deltas": [{"records": paths, "author_provider": "codex", "reviewer_provider": "claude",
       "review": "reviews/P01.365-filter-review.md", "review_course_path": REVIEW,
       "review_blob": git(B / "source.git", "rev-parse", C + ":" + REVIEW).decode().strip(),
       "review_sha256": sha(B / "reviews/P01.365-filter-review.md"), "accepted_receipt": "reviews/P01.365-accepted.json",
       "accepted_receipt_sha256": sha(B / "reviews/P01.365-accepted.json")}]}
dump("FILTER-REVIEWS.json", reviews)
pf = json.loads((B / "PREFLIGHT.json").read_text())
assert pf["C"] == C and all(pf[k] == "pass" for k in ("classification", "case_boundary", "lexical_guard"))
closure = {"task": "P02.68", "C": C, "authority": "task P02.68 and answered: local M by unchanged P02.52",
    "task_sha256": sha(B / "TASK-at-source.yaml"), "green_check_sha256": sha(B / "CHECK-SPEC-C.out"),
    "check_exit": 0, "preflight_sha256": sha(B / "PREFLIGHT.json"), "filter_reviews_sha256": sha(B / "FILTER-REVIEWS.json")}
dump("SOURCE-CLOSURE.json", closure)
auth = {"version": 1, "authorization": "ROOT_AFTER_STEP6_GREEN_AND_FILTER_REVIEW", "source_C": C,
    "filter_blob": pf["assembled_filter_blob"], "wire_blob": pf["wire_blob"], "derived_sha256": pf["derived_sha256"],
    "source_acceptance_sha256": sha(B / "SOURCE-CLOSURE.json"), "green_check_sha256": sha(B / "CHECK-SPEC-C.out"),
    "different_provider_filter_review_sha256": sha(B / "FILTER-REVIEWS.json"),
    "filter_author_provider": "codex", "filter_reviewer_provider": "claude"}
dump("AUTHORIZATION.json", auth)
PAIR = B / ("pair-" + C[:12])
pair = json.loads(run("PAIR", [sys.executable, "-B", str(B / "operator/b7_export_pair.py"), "--source-git-dir", str(B / "source.git"),
    "--course-commit", C, "--output", str(PAIR), "--authorization-json", str(B / "AUTHORIZATION.json")], B))
sys.path.insert(0, str(B / "operator"))
sys.path.insert(0, str(A / "skills/lesson-spec/scripts"))
import b7_export_pair as operator
import export_lists
import m_form
assembled, errors, _ = export_lists.assemble(A)
assert not errors, errors
model = {row["path"]: row["disposition"] for row in assembled["model"]}
check = type("Check", (), {"root": A})()
lesson = m_form.Lesson(check, "P/02", A / "Platform/02-installer")
selected = m_form.pair_m(check, lesson, model)
assert selected is not None
deps = m_form.dependencies(check, lesson)
assert not (deps - selected), sorted(deps - selected)
selected |= {operator.MARKER}
raw_entries = tree(PAIR / "M.git", pair["M"])
assert selected <= raw_entries.keys()
N = B / "narrow"
N.mkdir()
entries = {p: (*raw_entries[p], git(PAIR / "M.git", "cat-file", "blob", raw_entries[p][1])) for p in selected}
fd = os.open(N, os.O_RDONLY | os.O_DIRECTORY)
try:
    meta = operator._emit(fd, "M.git", entries, "model")
finally:
    os.close(fd)
M = meta["commit"]
assert tree(N / "M.git", M) == {p: raw_entries[p] for p in selected}
dump("NARROW-M.json", {"C": C, "M": M, "raw_M": pair["M"], "M_count": len(selected),
     "rule": "exact-C m_form.pair_m P/02 plus mandatory COURSE_COMMIT", "rule_sha256": sha(A / "skills/lesson-spec/scripts/m_form.py"),
     "README_blob": git(B / "source.git", "rev-parse", C + ":Platform/02-installer/README.md").decode().strip(),
     "dependencies": sorted(deps), "selected": sorted(selected), "OK": True})
run("M-PASSPORT", [sys.executable, "-B", str(B / "operator/m_passport.py"), "--m-git-dir", str(N / "M.git"),
    "--m-commit", M, "--output", str(B / "PASSPORT-M.json")], B)
passport = json.loads((B / "PASSPORT-M.json").read_text())
ROOT.mkdir()
p = subprocess.Popen(["git", "--git-dir", str(N / "M.git"), "archive", M], stdout=subprocess.PIPE)
r = subprocess.run(["tar", "-x", "-C", str(ROOT)], stdin=p.stdout)
p.stdout.close()
assert p.wait() == r.returncode == 0
want = {row["path"]: row for row in passport["files"]}
assert {p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_file()} == set(want)
files, sums = [], []
for rel, row in sorted(want.items()):
    path = ROOT / rel
    assert stat.S_ISREG(path.lstat().st_mode)
    raw = path.read_bytes()
    assert len(raw) == row["size"] and hashlib.sha1(b"blob %d\0" % len(raw) + raw).hexdigest() == row["blob"]
    mode = 0o555 if row["mode"] == "100755" else 0o444
    path.chmod(mode)
    digest = hashlib.sha256(raw).hexdigest()
    files.append({"path": rel, "git_mode": row["mode"], "blob": row["blob"], "bytes": len(raw), "sha256": digest, "filesystem_mode": oct(mode)})
    sums.append(digest + "  " + rel + "\n")
for path in sorted((p for p in ROOT.rglob("*") if p.is_dir()), reverse=True):
    path.chmod(0o555)
ROOT.chmod(0o555)
assert all(not p.is_symlink() and not p.lstat().st_mode & 0o222 for p in (ROOT, *ROOT.rglob("*")))
(B / "SHA256SUMS").write_text("".join(sums))
run("M-PASSPORT-CHECK", [sys.executable, "-I", "-B", str(B / "operator/check_m_passport.py"), str(B / "PASSPORT-M.json"), str(ROOT), M], B)
run("SHA256SUMS-CHECK", ["sha256sum", "--check", str(B / "SHA256SUMS")], ROOT)
run("FSCK-M", ["git", "--git-dir", str(N / "M.git"), "fsck", "--full", "--strict"], B)
pins = {}
mod = (ROOT / "Platform/common/versions/go.mod").read_text()
for name in ("json", "store-client", "log-mask"):
    found = re.findall(r"^\s*(servervms\.local/common/" + re.escape(name) + r")\s+(v\S+)\s*$", mod, re.M)
    assert len(found) == 1
    pins[found[0][0]] = found[0][1]
dump("UNPACKED-M.json", {"C": C, "M": M, "directory": str(ROOT), "count": len(files), "files": files,
    "passport_sha256": sha(B / "PASSPORT-M.json"), "sha256sums_sha256": sha(B / "SHA256SUMS"),
    "exact_paths_blobs_sizes_modes": True, "all_write_bits_cleared": True, "no_symlinks": True, "OK": True})
identities = {"task": "P02.68", "C": C, "M": M, "M_tree": meta["tree"], "count": len(selected), "raw_M": pair["M"], "J": pair["J"],
    "directory": str(ROOT), "M_git": str(N / "M.git"), "J_git": str(PAIR / "J.git"), "raw_M_git": str(PAIR / "M.git"),
    "passport": str(B / "PASSPORT-M.json"), "passport_sha256": sha(B / "PASSPORT-M.json"), "files_sha256": passport["files_sha256"],
    "sha256sums": str(B / "SHA256SUMS"), "sha256sums_sha256": sha(B / "SHA256SUMS"), "shared_module_pins": pins,
    "filter_review_course_path": REVIEW, "evidence": str(B), "OK": True}
dump("IDENTITIES.json", identities)
print(json.dumps(identities, ensure_ascii=False, indent=1))
