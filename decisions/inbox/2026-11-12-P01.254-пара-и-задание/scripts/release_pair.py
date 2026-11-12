"""P01.254: local pair/passports/J-input, using unchanged accepted operators.

Run only after CHECK-SPEC-C.exit is 0 and the accepted filter review matrix is
prepared in <evidence>/reviews. No deployment, root operation or pin selection.
Usage: python3 -B release_pair.py <evidence directory>
"""
from pathlib import Path
import datetime
import hashlib
import json
import subprocess
import sys
import time

B = Path(sys.argv[1]).resolve()
C = (B / "C.txt").read_text().strip()


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dump(p, value):
    Path(p).write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n")


def run(name, argv):
    start = time.monotonic()
    p = subprocess.run(argv, cwd=B, capture_output=True)
    (B / (name + ".out")).write_bytes(p.stdout)
    (B / (name + ".err")).write_bytes(p.stderr)
    dump(B / (name + ".run.json"), {"argv": argv, "exit": p.returncode,
         "start_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
         "elapsed_seconds": time.monotonic() - start,
         "stdout_sha256": hashlib.sha256(p.stdout).hexdigest(),
         "stderr_sha256": hashlib.sha256(p.stderr).hexdigest()})
    assert p.returncode == 0, (name, p.returncode, p.stderr.decode())
    return p.stdout


assert (B / "CHECK-SPEC-C.exit").read_text().strip() == "0"
pf = json.loads((B / "PREFLIGHT.json").read_text())
assert pf["C"] == C
assert all(pf[k] == "pass" for k in ("classification", "case_boundary", "lexical_guard"))
delta = json.loads((B / "FILTER-DELTA.json").read_text())
reviews = json.loads((B / "FILTER-REVIEWS.json").read_text())
assert reviews["C"] == C and reviews["all_delta_records_covered"]
assert reviews["delta_sha256"] == sha(B / "FILTER-DELTA.json")
expected = {x["path"] for kind in ("added", "removed", "changed") for x in delta[kind]}
assert {p for row in reviews["deltas"] for p in row["records"]} == expected
for row in reviews["deltas"]:
    a = json.loads((B / row["accepted_receipt"]).read_text())
    assert a["status"] == "accepted"
    assert row["author_provider"] != row["reviewer_provider"]
    assert row["review_sha256"] == sha(B / row["review"])

closure = {"task": "P01.254", "C": C, "scope": "local pair/passports/J-input only",
           "authority": "P01.254 requests the accepted P01.180/P01.251 procedure; delivery and canary belong to the representative",
           "check_exit": 0, "green_check_sha256": sha(B / "CHECK-SPEC-C.out"),
           "preflight_sha256": sha(B / "PREFLIGHT.json"),
           "filter_reviews_sha256": sha(B / "FILTER-REVIEWS.json"),
           "filter_sources": pf["filter_sources"]}
dump(B / "SOURCE-CLOSURE-P01-254.json", closure)
authorization = {"version": 1, "authorization": "ROOT_AFTER_STEP6_GREEN_AND_FILTER_REVIEW",
                 "source_C": C, "filter_blob": pf["assembled_filter_blob"],
                 "wire_blob": pf["wire_blob"], "derived_sha256": pf["derived_sha256"],
                 "source_acceptance_sha256": sha(B / "SOURCE-CLOSURE-P01-254.json"),
                 "green_check_sha256": sha(B / "CHECK-SPEC-C.out"),
                 "different_provider_filter_review_sha256": sha(B / "FILTER-REVIEWS.json"),
                 "filter_author_provider": "Anthropic + OpenAI (per-delta matrix)",
                 "filter_reviewer_provider": "OpenAI + Anthropic (per-delta matrix and inherited P01.251)"}
dump(B / "AUTHORIZATION.json", authorization)
P = B / ("pair-" + C[:12])
assert not P.exists(), "pair may be invoked once; retain any previous failure"
out = run("PAIR", [sys.executable, "-B", str(B / "operator/b7_export_pair.py"),
          "--source-git-dir", str(B / "source.git"), "--course-commit", C,
          "--output", str(P), "--authorization-json", str(B / "AUTHORIZATION.json")])
pair = json.loads(out)
M, J = pair["M"], pair["J"]
(B / "passport").mkdir()
mp = B / "passport" / ("PASSPORT-M-" + M[:12] + ".json")
run("M-PASSPORT", [sys.executable, "-B", str(B / "operator/m_passport.py"),
    "--m-git-dir", str(P / "M.git"), "--m-commit", M, "--output", str(mp)])
sys.path.insert(0, str(B / "operator"))
import judge_input_export as ji
tree = {}
for rec in subprocess.check_output(["git", "--git-dir", str(P / "J.git"), "ls-tree", "-rz", J]).split(b"\0"):
    if rec:
        meta, path = rec.split(b"\t", 1)
        mode, kind, blob = meta.decode().split()
        assert kind == "blob"
        tree[path.decode()] = (mode, blob)
raw, sources = ji.assemble(str(P / "J.git"), tree)
filter_blob = hashlib.sha1(b"blob %d\0" % len(raw) + raw).hexdigest()
JI = B / ("ji-" + C[:12])
assert not JI.exists()
run("JI", [sys.executable, "-B", str(B / "operator/judge_input_export.py"),
    "--j-git-dir", str(P / "J.git"), "--j-commit", J, "--filter-blob", filter_blob,
    "--output", str(JI)])
jic = subprocess.check_output(["git", "--git-dir", str(JI / "JI.git"), "rev-parse", "judge-input"]).decode().strip()
identities = {"C": C, "M": M, "J": J, "JI": jic, "pair_directory": str(P),
              "JI_directory": str(JI), "M_passport": str(mp), "M_passport_sha256": sha(mp),
              "JI_passport_sha256": sha(JI / "PASSPORT-JI.json"),
              "M_filter_blob": pf["assembled_filter_blob"], "JI_filter_blob": filter_blob}
dump(B / "IDENTITIES.json", identities)
print(json.dumps(identities, ensure_ascii=False, indent=1))
