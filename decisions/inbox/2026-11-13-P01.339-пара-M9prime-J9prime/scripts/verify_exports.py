"""Independent Git roster/object verification of the final P01.339 exports.

No candidate, model, stand process or operator is executed. The old independent
JI scanner is retained unchanged; each lexical/routing exception is bounded by
the exact lists accepted in P01.254, rather than a new filename heuristic.
Usage: spec-python -B verify_exports.py <evidence> <own course worktree>
"""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys

B, W = map(lambda p: Path(p).resolve(), sys.argv[1:3])
I = json.loads((B / "IDENTITIES.json").read_text())
C = I["C"]
P = Path(I["pair_directory"])


def git(repo, *args):
    return subprocess.check_output(["git", "--git-dir", str(repo), *args])


def tree(repo, ref, prefix=None):
    result = {}
    args = ["ls-tree", "-rz", ref] + (["--", prefix] if prefix else [])
    for row in git(repo, *args).split(b"\0"):
        if row:
            header, path = row.split(b"\t", 1)
            mode, kind, oid = header.decode().split()
            assert kind == "blob" and mode in {"100644", "100755"}
            result[path.decode()] = (mode, oid)
    return result


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(name, value):
    (B / name).write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n")


source = tree(B / "source.git", C, "Platform")
course = {p: v for p, v in source.items() if p.startswith("Platform/")}
j = tree(I["J_git"], I["J"])
m = tree(I["M_git"], I["M"])
raw_m = tree(P / "M.git", I["raw_M"])
ji = tree(I["JI_git"], I["JI"])
marker = "Platform/COURSE_COMMIT"
assert {p: v for p, v in j.items() if p != marker} == course
assert git(I["J_git"], "show", I["J"] + ":" + marker) == (C + "\n").encode()
assert all(j.get(p) == v for p, v in m.items())
assert m[marker] == j[marker]
sys.path.insert(0, str(B / "archive-C/skills/lesson-spec/scripts"))
import export_lists
import m_form
assembled, errors, _ = export_lists.assemble(B / "archive-C")
assert not errors, errors
fm = json.loads((P / "FILTER-M.json").read_text())
model = {row["path"]: row["disposition"] for row in assembled["model"]}
assert model == {row["path"]: row["disposition"] for row in fm["files"]}
assert raw_m == {p: v for p, v in j.items() if model[p] == "model_and_judge"}
check = type("Check", (), {"root": B / "archive-C"})()
lesson = m_form.Lesson(check, "P/01", check.root / "Platform/01-store")
base = m_form.pair_m(check, lesson, model)
excluded = {"Platform/common/acceptance/testsub-stand.md", "Platform/common/vectors/slot/README.md"}
assert base is not None and not excluded & base
assert set(m) == base | {marker}
deps = m_form.dependencies(check, lesson)
external_deps = {p for p in deps if re.match(r"Platform/\d\d-", p) and not p.startswith("Platform/01-store/")}
non_model_dependencies = {p for p in deps if model.get(p) != "model_and_judge" or m_form.q_kind(p)}
assert deps - m.keys() == non_model_dependencies
assert non_model_dependencies == {"Platform/01-store/qualification/README.md"}
assert all(model[p] == "judge_only" and m_form.q_kind(p) for p in non_model_dependencies)
other = {p for p in m if re.match(r"Platform/\d\d-", p) and not p.startswith("Platform/01-store/")}
assert other == external_deps
assert not any("/ru/" in p for p in m)
assert not any(p.endswith(("/scenarios.tsv", "/seams.tsv")) for p in m)
assert not any(".cases." in Path(p).name or "acceptance/spec/acceptance." in p for p in m)
for path in ("Platform/01-store/forms/group.tsv", "Platform/01-store/acceptance/1/inputs/rights.json",
             "Platform/common/acceptance/forms/stand-manifests.tsv"):
    assert path not in m and path in j and path in ji
assert marker in m and "Platform/README.md" in m and "Platform/lessons.tsv" in m
wire_cases = set()
for path in ("Platform/common/vectors/wire.tsv", "Platform/common/vectors/wire.cases.tsv"):
    lines = [x.split("\t") for x in git(I["J_git"], "show", I["J"] + ":" + path).decode().splitlines()
             if x and not x.startswith("#")]
    for row in lines[1:]:
        lesson_name, package = row[0].split("/", 1)
        wire_cases.add(f"Platform/{lesson_name}/vectors/{package}/{row[1]}")
assert not wire_cases & m.keys()
assert "Platform/common/vectors/wire.tsv" in m and "Platform/common/vectors/wire.cases.tsv" not in m
fj = json.loads((Path(I["JI_directory"]) / "FILTER-JI.json").read_text())
judge = {row["path"]: row["disposition"] for row in assembled["judge"]}
assert judge == {row["path"]: row["disposition"] for row in fj["files"]}
assert set(ji) == {p for p, disposition in judge.items() if disposition == "include"}
assert all(ji[p] == j[p] for p in ji)
assert "Platform/common/contracts/role-certificate.md" in ji
assert sha(Path(I["JI_directory"]) / "PASSPORT-JI.json") == I["JI_passport_sha256"]
assert sha(I["M_passport"]) == I["M_passport_sha256"]
passport = json.loads(Path(I["M_passport"]).read_text())
assert passport["C"] == C and passport["M"]["commit"] == I["M"] and passport["count"] == len(m)
assert {r["path"]: (r["mode"], r["blob"]) for r in passport["files"]} == m
objects = {}
for name, repo, commit, ref in (("raw_M", P / "M.git", I["raw_M"], "model"),
        ("M", Path(I["M_git"]), I["M"], "model"), ("J", Path(I["J_git"]), I["J"], "judge"),
        ("JI", Path(I["JI_git"]), I["JI"], "judge-input")):
    refs = git(repo, "for-each-ref", "--format=%(refname) %(objectname)").decode().splitlines()
    assert refs == ["refs/heads/" + ref + " " + commit]
    assert git(repo, "rev-list", "--parents", commit).decode().split() == [commit]
    assert git(repo, "rev-list", "--all").decode().split() == [commit]
    physical = {r.split()[0] for r in git(repo, "cat-file", "--batch-all-objects", "--batch-check").decode().splitlines()}
    reachable = {r.split()[0] for r in git(repo, "rev-list", "--objects", "--all").decode().splitlines()}
    assert physical == reachable
    assert not (set(p.name for p in repo.iterdir()) - {"objects", "refs", "HEAD", "config", "packed-refs"})
    result = subprocess.run(["git", "--git-dir", str(repo), "fsck", "--full", "--strict"], capture_output=True)
    assert result.returncode == 0, (name, result.stderr.decode())
    objects[name] = {"refs": refs, "parentless": True, "physical_eq_reachable": True,
                     "objects": len(physical), "fsck_exit": result.returncode}
    if name == "M":
        model_blobs = {value[1] for value in m.values()}
        private_blobs = {value[1] for p, value in j.items() if p not in m} - model_blobs
        assert not private_blobs & physical
        objects[name]["J_only_distinct_blobs_absent"] = len(private_blobs)
dump("VERIFY-PAIR.json", {"C": C, "source_roster_exact": True, "filter_equals_check_spec": True,
     "current_pair_m_exact": True, "external_dependencies": sorted(external_deps),
     "excluded_dependencies": [{"path": p, "disposition": model[p], "q_kind": m_form.q_kind(p)} for p in sorted(non_model_dependencies)],
     "M_subset_J": {"M_files": len(m), "J_files": len(j), "matched": len(m)},
     "JI_equals_assembled_filter": True, "passports_exact": True, "object_checks": objects,
     "counts": {"M": len(m), "raw_M": len(raw_m), "J": len(j), "JI": len(ji)}, "OK": True})
argv = [sys.executable, "-B", str(B / "scripts/verify_ji_raw.py"), str(W), C,
        I["J_git"], I["J"], I["JI_git"], I["JI"], I["M_git"], str(Path(I["JI_directory"]) / "FILTER-JI.json")]
result = subprocess.run(argv, capture_output=True)
(B / "VERIFY-JI-raw.json").write_bytes(result.stdout)
(B / "VERIFY-JI-raw.err").write_bytes(result.stderr)
dump("VERIFY-JI-raw.run.json", {"argv": argv, "exit": result.returncode})
assert result.returncode in (0, 1)
raw = json.loads(result.stdout)
baseline_path = Path("/home/pilot/run-p01254-pair-20261112-r3/VERIFY-JI-raw.json")
baseline = json.loads(baseline_path.read_text())
assert all(v for k, v in raw.items() if isinstance(v, bool) and k != "OK")
assert all(set(paths) <= set(baseline["forbidden_hits"][kind]) for kind, paths in raw["forbidden_hits"].items())
assert set(raw["routing_files_missing_in_JI"]) <= set(baseline["routing_files_missing_in_JI"])
assert all(judge[p] == "exclude" for p in raw["routing_files_missing_in_JI"])
assert all(raw["named_inputs_present"].values())
assert raw["objects_physical_eq_reachable"][2]
assert raw["JI_refs"] == ["refs/heads/judge-input"]
dump("VERIFY-JI.json", {"independent_scanner": "unchanged P01.254 verify_ji_p01254.py",
     "scanner_sha256": sha(B / "scripts/verify_ji_raw.py"), "raw_exit": result.returncode,
     "exception_basis": "exact lexical and routing exception paths accepted in P01.254; no new path permitted",
     "baseline_report": str(baseline_path), "baseline_sha256": sha(baseline_path),
     "forbidden_hits": raw["forbidden_hits"], "routing_files_missing_in_JI": raw["routing_files_missing_in_JI"],
     "all_boolean_checks_pass": True, "no_new_exception": True, "counts": raw["counts"], "OK": True})
controls = json.loads((B / "passport/CONTROLS.json").read_text())
assert controls["M"] == I["M"] and controls["OK"] and all(row["pass"] for row in controls["checks"])
out = {"C": C, "M": I["M"], "J": I["J"], "JI": I["JI"], "pair_invariants": True,
       "M_subset_J": {"M_files": len(m), "J_files": len(j), "matched": len(m)},
       "assembled_filters_equal_check_spec": True, "narrow_selection_exact": True,
       "J_input_classified_checks": True, "passport_separate_controls": len(controls["checks"]), "OK": True}
dump("VERIFY-ALL.json", out)
print(json.dumps(out, indent=1))
