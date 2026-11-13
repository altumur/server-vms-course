"""P01.329: local pair, explicit narrow M, passports and judge input; no deployment.

Run with the spec Python: release_pair.py <evidence>. The evidence must contain
the exact-C archive, unchanged accepted operators and successful preflight/check.
The raw pair is retained; the final M has a fresh independent object store.
"""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import time

B = Path(sys.argv[1]).resolve()
C = (B / "C.txt").read_text().strip()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n")


def git(repo, *args):
    return subprocess.check_output(["git", "--git-dir", str(repo), *args])


def run(name, argv):
    start = time.monotonic()
    result = subprocess.run(argv, cwd=B, capture_output=True)
    (B / (name + ".out")).write_bytes(result.stdout)
    (B / (name + ".err")).write_bytes(result.stderr)
    dump(B / (name + ".run.json"), {"argv": argv, "exit": result.returncode,
         "seconds": time.monotonic() - start,
         "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
         "stderr_sha256": hashlib.sha256(result.stderr).hexdigest()})
    assert result.returncode == 0, (name, result.returncode, result.stderr.decode())
    return result.stdout


def tree(repo, ref):
    entries = {}
    for row in git(repo, "ls-tree", "-rz", ref).split(b"\0"):
        if row:
            header, path = row.split(b"\t", 1)
            mode, kind, oid = header.decode().split()
            assert kind == "blob"
            entries[path.decode()] = (mode, oid)
    return entries


assert (B / "CHECK-SPEC-C.exit").read_text().strip() == "0"
pf = json.loads((B / "PREFLIGHT.json").read_text())
assert pf["C"] == C and all(pf[k] == "pass" for k in ("classification", "case_boundary", "lexical_guard"))
delta = json.loads((B / "FILTER-DELTA.json").read_text())
reviews = json.loads((B / "FILTER-REVIEWS.json").read_text())
assert reviews["C"] == C and reviews["all_delta_records_covered"]
assert reviews["delta_sha256"] == sha(B / "FILTER-DELTA.json")
expected = {row["path"] for kind in ("added", "removed", "changed") for row in delta[kind]}
assert {path for row in reviews["deltas"] for path in row["records"]} == expected
for row in reviews["deltas"]:
    accepted = json.loads((B / row["accepted_receipt"]).read_text())
    assert accepted["status"] == "accepted"
    assert row["author_provider"] != row["reviewer_provider"]
    assert row["review_sha256"] == sha(B / row["review"])

composition = json.loads((B / 'SOURCE-COMPOSITION.json').read_text())
assert composition['C'] == C and composition['OK']
assert composition['OBSH.58']['status'] == 'rejected' and composition['OBSH.58']['authorized_by_answered']
closure = {"task": "P01.329", "C": C, "scope": "local pair/narrow M/passports/J-input only",
           "authority": "P01.329 task and answered 2026-11-13T11:48:06Z; local pair now despite OBSH.58 rejected; unchanged operator validates roster; no pin or delivery",
           "check_exit": 0, "green_check_sha256": sha(B / "CHECK-SPEC-C.out"),
           "preflight_sha256": sha(B / "PREFLIGHT.json"),
           "filter_reviews_sha256": sha(B / "FILTER-REVIEWS.json"), "filter_sources": pf["filter_sources"]}
dump(B / "SOURCE-CLOSURE.json", closure)
authorization = {"version": 1, "authorization": "ROOT_AFTER_STEP6_GREEN_AND_FILTER_REVIEW",
                 "source_C": C, "filter_blob": pf["assembled_filter_blob"],
                 "wire_blob": pf["wire_blob"], "derived_sha256": pf["derived_sha256"],
                 "source_acceptance_sha256": sha(B / "SOURCE-CLOSURE.json"),
                 "green_check_sha256": sha(B / "CHECK-SPEC-C.out"),
                 "different_provider_filter_review_sha256": sha(B / "FILTER-REVIEWS.json"),
                 "filter_author_provider": reviews["filter_author_provider"],
                 "filter_reviewer_provider": reviews["filter_reviewer_provider"]}
dump(B / "AUTHORIZATION.json", authorization)
P = B / ("pair-" + C[:12])
if sys.argv[2:] == ["--resume-after-pair"]:
    assert json.loads((B / "PAIR.run.json").read_text())["exit"] == 0
    pair = json.loads((B / "PAIR.out").read_bytes())
    assert pair["C"] == C
else:
    assert not P.exists(), "retain previous output or failure; never overwrite"
    pair = json.loads(run("PAIR", [sys.executable, "-B", str(B / "operator/b7_export_pair.py"),
        "--source-git-dir", str(B / "source.git"), "--course-commit", C,
        "--output", str(P), "--authorization-json", str(B / "AUTHORIZATION.json")]))
raw_M, J = pair["M"], pair["J"]
sys.path.insert(0, str(B / "operator"))
sys.path.insert(0, str(B / "archive-C/skills/lesson-spec/scripts"))
import b7_export_pair as operator
import export_lists
import judge_input_export
import m_form

assembled, errors, _ = export_lists.assemble(B / "archive-C")
assert not errors
model = {row["path"]: row["disposition"] for row in assembled["model"]}
check = type("Check", (), {"root": B / "archive-C"})()
lesson = m_form.Lesson(check, "P/01", check.root / "Platform/01-store")
selected = m_form.pair_m(check, lesson, model)
assert selected is not None
raw_entries = tree(P / "M.git", raw_M)
assert selected <= raw_entries.keys()
# COURSE_COMMIT is transport metadata added by the unchanged pair operator,
# outside the source roster (the assembled filter adds it as a synthetic record).
# The unchanged passport operator requires it.
marker = "Platform/COURSE_COMMIT"
assert not (B / "archive-C" / marker).exists() and marker in raw_entries
selected |= {marker}
N = B / "narrow"
N.mkdir()
entries = {path: (*raw_entries[path], git(P / "M.git", "cat-file", "blob", raw_entries[path][1]))
           for path in selected}
fd = os.open(N, os.O_RDONLY | os.O_DIRECTORY)
try:
    narrow_result = operator._emit(fd, "M.git", entries, "model")
    M = narrow_result["commit"]
finally:
    os.close(fd)
assert tree(N / "M.git", M) == {p: raw_entries[p] for p in selected}
dump(B / "NARROW-M.json", {"rule": "exact-C m_form.pair_m plus mandatory transport marker",
     "rule_sha256": sha(B / "archive-C/skills/lesson-spec/scripts/m_form.py"),
     "README_blob": git(B / "source.git", "rev-parse", C + ":Platform/01-store/README.md").decode().strip(),
     "raw_M": raw_M, "M": M, "raw_M_count": len(raw_entries), "M_source_count": len(selected) - 1,
     "M_count": len(selected), "transport_marker": marker,
     "marker_basis": "b7_export_pair._classification requires marker in both; m_passport.build refuses without marker",
     "dependencies": sorted(m_form.dependencies(check, lesson)),
     "selected": sorted(selected), "removed_from_raw_M": sorted(raw_entries.keys() - selected), "OK": True})
(B / "passport").mkdir()
mp = B / "passport" / ("PASSPORT-M-" + M[:12] + ".json")
run("M-PASSPORT", [sys.executable, "-B", str(B / "operator/m_passport.py"),
    "--m-git-dir", str(N / "M.git"), "--m-commit", M, "--output", str(mp)])
jraw, _ = judge_input_export.assemble(str(P / "J.git"), tree(P / "J.git", J))
filter_blob = hashlib.sha1(b"blob %d\0" % len(jraw) + jraw).hexdigest()
JI = B / ("ji-" + C[:12])
run("JI", [sys.executable, "-B", str(B / "operator/judge_input_export.py"),
    "--j-git-dir", str(P / "J.git"), "--j-commit", J, "--filter-blob", filter_blob, "--output", str(JI)])
JIC = git(JI / "JI.git", "rev-parse", "judge-input").decode().strip()
identities = {"C": C, "raw_M": raw_M, "M": M, "J": J, "JI": JIC,
              "pair_directory": str(P), "M_git": str(N / "M.git"), "J_git": str(P / "J.git"),
              "JI_directory": str(JI), "JI_git": str(JI / "JI.git"),
              "M_passport": str(mp), "M_passport_sha256": sha(mp),
              "JI_passport_sha256": sha(JI / "PASSPORT-JI.json"),
              "raw_M_filter_blob": pf["assembled_filter_blob"], "JI_filter_blob": filter_blob}
dump(B / "IDENTITIES.json", identities)
print(json.dumps(identities, ensure_ascii=False, indent=1))
