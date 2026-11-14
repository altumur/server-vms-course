"""P02.72: unchanged P02.52 compose_pair, exact-C narrow P/02 and read-only M/J.

Run with the spec Python and one prepared, private evidence directory. Source,
operators, green check, preflight and accepted filter reviews must already exist.
Every payload output is new; an unsuccessful output is retained for inspection.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import time

B = Path(sys.argv[1]).resolve()
C = (B / "C.txt").read_text().strip()
assert re.fullmatch(r"[0-9a-f]{40}", C)
sys.path.insert(0, str(B / "operator"))
sys.path.insert(0, str(B / "archive-C/skills/lesson-spec/scripts"))
import b7_export_pair as operator
import export_lists
import m_form


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(name, value):
    (B / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def git(repo, *args):
    return subprocess.check_output(["git", "--git-dir", str(repo), *args])


def run(name, argv):
    start = time.monotonic()
    r = subprocess.run(argv, capture_output=True)
    (B / (name + ".out")).write_bytes(r.stdout)
    (B / (name + ".err")).write_bytes(r.stderr)
    dump(name + ".run.json", {"argv": argv, "exit": r.returncode,
         "seconds": time.monotonic() - start,
         "stdout_sha256": hashlib.sha256(r.stdout).hexdigest(),
         "stderr_sha256": hashlib.sha256(r.stderr).hexdigest()})
    assert r.returncode == 0, (name, r.returncode)
    return r.stdout


def tree(repo, commit, prefix=None):
    out = {}
    args = ["ls-tree", "-rz", commit]
    if prefix:
        args.extend(["--", prefix])
    for row in git(repo, *args).split(b"\0"):
        if row:
            header, path = row.split(b"\t", 1)
            mode, kind, oid = header.decode().split()
            assert kind == "blob" and mode in ("100644", "100755")
            out[path.decode()] = (mode, oid)
    return out


def unpack(side, repo, commit, entries):
    root = B / side
    root.mkdir()
    producer = subprocess.Popen(["git", "--git-dir", str(repo), "archive", commit],
                                stdout=subprocess.PIPE)
    consumer = subprocess.run(["tar", "-x", "-C", str(root)], stdin=producer.stdout)
    producer.stdout.close()
    assert producer.wait() == consumer.returncode == 0
    assert {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()} == entries.keys()
    rows = []
    for rel, (mode, blob) in sorted(entries.items()):
        path = root / rel
        assert stat.S_ISREG(path.lstat().st_mode)
        raw = path.read_bytes()
        assert operator._blob_id(raw) == blob
        filesystem_mode = 0o555 if mode == "100755" else 0o444
        path.chmod(filesystem_mode)
        rows.append({"path": rel, "mode": mode, "blob": blob,
                     "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                     "filesystem_mode": oct(filesystem_mode)})
    for path in sorted((p for p in root.rglob("*") if p.is_dir()), reverse=True):
        path.chmod(0o555)
    root.chmod(0o555)
    assert all(not p.lstat().st_mode & 0o222 for p in (root, *root.rglob("*")))
    dump("UNPACKED-" + side + ".json", {"C": C, "commit": commit,
         "directory": str(root), "count": len(rows), "files": rows,
         "paths_blobs_modes_equal_git": True, "all_write_bits_cleared": True})
    return rows


assert (B / "CHECK-SPEC-C.exit").read_text().strip() == "0"
pf = json.loads((B / "PREFLIGHT.json").read_text())
assert pf["C"] == C and all(pf[k] == "pass" for k in ("classification", "case_boundary", "lexical_guard"))
delta = json.loads((B / "FILTER-DELTA.json").read_text())
reviews = json.loads((B / "FILTER-REVIEWS.json").read_text())
assert reviews["C"] == C and reviews["all_delta_records_covered"]
assert reviews["delta_sha256"] == sha(B / "FILTER-DELTA.json")
assert {r["path"] for k in ("added", "removed", "changed") for r in delta[k]} == {
    p for r in reviews["deltas"] for p in r["records"]}
for row in reviews["deltas"]:
    assert row["author_provider"] != row["reviewer_provider"]
    assert json.loads((B / row["accepted_receipt"]).read_text())["status"] == "accepted"
    assert sha(B / row["review"]) == row["review_sha256"]
composition = json.loads((B / "SOURCE-COMPOSITION.json").read_text())
assert composition["C"] == C and composition["OK"]
closure = {"task": "P02.72", "C": C, "authority": "P02.72: compose_pair as P01.355/P01.360",
           "scope": "P/02 pair, passports, read-only M/J and SPEC_VERSION for P02.27",
           "green_check_sha256": sha(B / "CHECK-SPEC-C.out"),
           "filter_reviews_sha256": sha(B / "FILTER-REVIEWS.json"),
           "source_composition_sha256": sha(B / "SOURCE-COMPOSITION.json")}
dump("SOURCE-CLOSURE.json", closure)
authorization = {"version": 1, "authorization": "ROOT_AFTER_STEP6_GREEN_AND_FILTER_REVIEW",
                 "source_C": C, "filter_blob": pf["assembled_filter_blob"],
                 "wire_blob": pf["wire_blob"], "derived_sha256": pf["derived_sha256"],
                 "source_acceptance_sha256": sha(B / "SOURCE-CLOSURE.json"),
                 "green_check_sha256": sha(B / "CHECK-SPEC-C.out"),
                 "different_provider_filter_review_sha256": sha(B / "FILTER-REVIEWS.json"),
                 "filter_author_provider": reviews["filter_author_provider"],
                 "filter_reviewer_provider": reviews["filter_reviewer_provider"]}
dump("AUTHORIZATION.json", authorization)
P = B / ("pair-" + C[:12])
pair = json.loads(run("PAIR", [sys.executable, "-B", str(B / "operator/b7_export_pair.py"),
    "--source-git-dir", str(B / "source.git"), "--course-commit", C,
    "--output", str(P), "--authorization-json", str(B / "AUTHORIZATION.json")]))
assert pair["C"] == C
raw_M, J = pair["M"], pair["J"]
raw_entries = tree(P / "M.git", raw_M)
assembled, errors, _ = export_lists.assemble(B / "archive-C")
assert not errors
model = {r["path"]: r["disposition"] for r in assembled["model"]}
check = type("Check", (), {"root": B / "archive-C"})()
lesson = m_form.Lesson(check, "P/02", check.root / "Platform/02-installer")
selected = m_form.pair_m(check, lesson, model)
assert selected is not None and selected <= raw_entries.keys()
dependencies = m_form.dependencies(check, lesson)
assert dependencies <= selected
selected |= {operator.MARKER}
N = B / "narrow"
N.mkdir()
entries = {p: (*raw_entries[p], git(P / "M.git", "cat-file", "blob", raw_entries[p][1])) for p in selected}
fd = os.open(N, os.O_RDONLY | os.O_DIRECTORY)
try:
    narrow = operator._emit(fd, "M.git", entries, "model")
finally:
    os.close(fd)
M = narrow["commit"]
me, je = tree(N / "M.git", M), tree(P / "J.git", J)
assert me == {p: raw_entries[p] for p in selected}
assert all(je[p] == entry for p, entry in me.items())
platform = tree(B / "source.git", C, "Platform/")
assert je.keys() == platform.keys() | {operator.MARKER}
assert all(je[p] == entry for p, entry in platform.items())
dump("NARROW-M.json", {"C": C, "M": M, "raw_M": raw_M,
     "rule": "exact-C m_form.pair_m P/02 plus mandatory COURSE_COMMIT",
     "rule_sha256": sha(B / "archive-C/skills/lesson-spec/scripts/m_form.py"),
     "selected": sorted(selected), "dependencies": sorted(dependencies),
     "raw_count": len(raw_entries), "count": len(me)})
run("M-PASSPORT", [sys.executable, "-B", str(B / "operator/m_passport.py"),
    "--m-git-dir", str(N / "M.git"), "--m-commit", M, "--output", str(B / "PASSPORT-M.json")])
object_checks = {}
for side, repo, commit in (("M", N / "M.git", M), ("J", P / "J.git", J)):
    assert git(repo, "rev-list", "--parents", commit).decode().split() == [commit]
    assert git(repo, "for-each-ref", "--format=%(objectname)").decode().split() == [commit]
    assert not git(repo, "remote").strip()
    assert not (repo / "objects/info/alternates").exists()
    physical = set(git(repo, "cat-file", "--batch-all-objects", "--batch-check=%(objectname)").splitlines())
    reachable = set(git(repo, "rev-list", "--objects", "--no-object-names", commit).splitlines())
    assert physical == reachable
    run("FSCK-" + side, ["git", "--git-dir", str(repo), "fsck", "--strict", "--full"])
    object_checks[side] = {"root_commit": True, "single_ref": True,
        "physical_equals_reachable": True, "object_count": len(physical), "fsck_exit": 0}
mr = unpack("M", N / "M.git", M, me)
jr = unpack("J", P / "J.git", J, je)
run("UNPACKED-M-PASSPORT", [sys.executable, "-I", "-B", str(B / "operator/check_m_passport.py"),
    str(B / "PASSPORT-M.json"), str(B / "M"), M])
pins = {}
mod = (B / "M/Platform/common/versions/go.mod").read_text()
sums = (B / "M/Platform/common/versions/go.sum").read_text().splitlines()
for module in ("json", "store-client", "log-mask"):
    name = "servervms.local/common/" + module
    found = re.findall(r"^\s*" + re.escape(name) + r"\s+(v\S+)\s*$", mod, re.M)
    assert len(found) == 1
    version = found[0]
    records = [line for line in sums if line.startswith(name + " " + version + " ") or
               line.startswith(name + " " + version + "/go.mod ")]
    assert len(records) == 2 and all(" h1:" in line for line in records)
    pins[name] = {"version": version, "go_sum": records}
dump("MODULE-PINS.json", {"M": M, "pins": pins, "go_mod_sha256": sha(B / "M/Platform/common/versions/go.mod"),
     "go_sum_sha256": sha(B / "M/Platform/common/versions/go.sum"), "OK": True})
template_path = "decisions/inbox/2026-11-13-P02.27-задание/TASK.md"
template = git(B / "source.git", "show", C + ":" + template_path)
accepted_task = json.loads((B / "reviews/P02.27-accepted.json").read_text())
assert template == git(B / "source.git", "show", accepted_task["commit"] + ":" + template_path)
assert template.count(b"__SPEC_VERSION__") == 1
(B / "TASK-P02.27.template.md").write_bytes(template)
(B / "TASK-P02.27.md").write_bytes(template.replace(b"__SPEC_VERSION__", M.encode()))
(B / "SPEC_VERSION").write_text(M + "\n")
passport = {"format": "P02.72-pair/1", "C": C, "M": M, "J": J, "SPEC_VERSION": M,
    "M_tree": git(N / "M.git", "rev-parse", M + "^{tree}").decode().strip(),
    "J_tree": git(P / "J.git", "rev-parse", J + "^{tree}").decode().strip(),
    "M_count": len(me), "J_count": len(je), "raw_M": raw_M,
    "M_directory": str(B / "M"), "J_directory": str(B / "J"),
    "M_git": str(N / "M.git"), "J_git": str(P / "J.git"),
    "raw_pair_passport": str(P / "PASSPORT-TRUSTED-ONLY.json"),
    "raw_pair_passport_sha256": sha(P / "PASSPORT-TRUSTED-ONLY.json"),
    "M_passport": str(B / "PASSPORT-M.json"), "M_passport_sha256": sha(B / "PASSPORT-M.json"),
    "assembled_filter_blob": pf["assembled_filter_blob"],
    "narrow_selection_sha256": sha(B / "NARROW-M.json"),
    "task_template_source": C + ":" + template_path,
    "task_template_sha256": sha(B / "TASK-P02.27.template.md"),
    "task_filled_sha256": sha(B / "TASK-P02.27.md"),
    "object_checks": object_checks, "M_subset_J_paths_modes_blobs": True,
    "J_equals_full_Platform_C_plus_marker": True,
    "module_pins_verified": True, "read_only_unpacked_directories": True,
    "publication": {"operator_result": pair["status"], "local_pair": str(P),
                    "operator_has_remote_publication": False},
    "OK": True}
dump("PAIR-PASSPORT.json", passport)
checksum_rows = [(r["sha256"], side + "/" + r["path"]) for side, rows in (("M", mr), ("J", jr)) for r in rows]
for path in ("PAIR-PASSPORT.json", "PASSPORT-M.json", "NARROW-M.json", "MODULE-PINS.json",
             "SPEC_VERSION", "TASK-P02.27.template.md", "TASK-P02.27.md", "UNPACKED-M.json", "UNPACKED-J.json"):
    checksum_rows.append((sha(B / path), path))
(B / "SHA256SUMS").write_text("".join(h + "  " + p + "\n" for h, p in sorted(checksum_rows, key=lambda r: r[1])))
print(json.dumps(passport, ensure_ascii=False, indent=2))
