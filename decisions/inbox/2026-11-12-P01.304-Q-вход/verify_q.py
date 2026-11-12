"""Независимая сверка Q: Git/байты/паспорт; оператор выгрузки не импортируется.

pair_m вызывается отдельно из точного C: это каноническая граница M урока,
а не повторение алгоритма обёртки Q. Никакие пробы из Q не исполняются.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(gd, *args):
    return subprocess.check_output(["git", "--git-dir", str(gd), *args])


def tree(gd, ref):
    result = {}
    for record in git(gd, "ls-tree", "-rz", "--full-tree", ref).split(b"\0"):
        if record:
            meta, path = record.split(b"\t", 1)
            result[path.decode("utf8")] = tuple(meta.decode().split())
    return result


def verify(source_git, source_root, output, operator_path, wrapper, check_run, frozen_pair):
    passport = json.loads((output / "PASSPORT-Q.json").read_text())
    course, commit = passport["source_C"], passport["q_input_commit"]
    qgit = output / "Q.git"
    source = tree(source_git, course)
    actual = tree(qgit, commit)
    raw = git(source_git, "cat-file", "blob", source[passport["filter_path"]][2])
    doc = json.loads(raw)
    paths = [row["path"] for row in doc["files"]]
    selected = set(paths)
    checks = {}
    checks["source_C_exact_commit"] = git(source_git, "rev-parse", course + "^{commit}").decode().strip() == course
    checks["source_tree_bound"] = git(source_git, "rev-parse", course + "^{tree}").decode().strip() == passport["source_tree"]
    checks["source_platform_tree_bound"] = git(source_git, "rev-parse", course + ":Platform").decode().strip() == passport["source_platform_tree"]
    checks["filter_exact_source_bytes"] = (output / "FILTER-Q.json").read_bytes() == raw
    checks["filter_blob_bound"] = source[passport["filter_path"]][2] == passport["filter_blob"]
    checks["filter_sha256_bound"] = hashlib.sha256(raw).hexdigest() == passport["filter_sha256"]
    checks["filter_shape"] = (set(doc) == {"version", "files"} and type(doc["version"]) is int
                              and doc["version"] == 1 and bool(paths)
                              and all(set(r) == {"path", "disposition", "basis"}
                                      and r["disposition"] == "include" and r["basis"].strip()
                                      and r["basis"].isascii() for r in doc["files"]))
    checks["filter_sorted_unique"] = len(paths) == len(selected) and paths == sorted(paths, key=lambda p: p.encode("utf8"))
    checks["all_paths_exist"] = selected <= source.keys()
    checks["Q_paths_equal_inventory"] = set(actual) == selected
    checks["modes_types_blobs_equal_C"] = all(actual[p] == source.get(p) for p in actual)
    checks["regular_blobs_only"] = all(m in {"100644", "100755"} and t == "blob" for m, t, _ in actual.values())
    byte_checks = []
    for path, (_, _, oid) in actual.items():
        byte_checks.append(git(qgit, "cat-file", "blob", oid) == git(source_git, "show", course + ":" + path))
    checks["file_bytes_equal_C"] = all(byte_checks)
    files = [{"path": p, "mode": actual[p][0], "blob": actual[p][2],
              "bytes": len(git(qgit, "cat-file", "blob", actual[p][2])),
              "sha256": hashlib.sha256(git(qgit, "cat-file", "blob", actual[p][2])).hexdigest()}
             for p in sorted(actual, key=lambda p: p.encode("utf8"))]
    checks["file_inventory_bound"] = files == json.loads((output / "FILES.json").read_text())
    foreign = sorted(p for p in actual if re.match(r"Platform/(?:0[2-9]|10)-", p))
    checks["P02_P10_only_explicit_filter_records"] = all(p in selected for p in foreign)
    checks["no_translation_or_nonplatform_or_filter"] = all(
        p.startswith("Platform/") and "ru" not in p.split("/") and not re.search(r"[*?\[]", p)
        and p != passport["filter_path"] and not p.endswith("/forms/export.json")
        and p not in {"Platform/common/export-model-filter.json", "Platform/common/acceptance/judge-input-filter.json"}
        for p in actual)
    procedures = {p for p in source if p.startswith("Platform/") and "/qualification/" in p and "/ru/" not in p}
    mirrors = {p for p in source if p.startswith("Platform/") and "/qualification/" in p and "/ru/" in p}
    checks["all_qualification_procedures_in_Q"] = bool(procedures) and procedures <= actual.keys()
    sys.path.insert(0, str(source_root / "skills/lesson-spec/scripts"))
    import export_lists
    import m_form
    assembled, errors, _ = export_lists.assemble(source_root)
    checks["source_export_lists_valid"] = not errors
    model = {row["path"]: row["disposition"] for row in assembled["model"]}
    check = type("Check", (), {"root": source_root})()
    lesson = m_form.Lesson(check, "P/01", source_root / "Platform/01-store")
    pair = m_form.pair_m(check, lesson, model)
    checks["pair_m_defined"] = pair is not None
    checks["procedures_and_mirrors_outside_pair_m"] = pair is not None and not (procedures | mirrors) & pair
    checks["Q_filter_outside_pair_m"] = pair is not None and passport["filter_path"] not in pair
    checks["procedures_and_mirrors_judge_only_in_M"] = all(model.get(p) == "judge_only" for p in procedures | mirrors)
    judge = {row["path"]: row["disposition"] for row in assembled["judge"]}
    checks["mirrors_excluded_from_J"] = all(judge.get(p) == "exclude" for p in mirrors)
    frozen = json.loads(frozen_pair.read_text())
    frozen_m = tree(frozen["M_git"], frozen["M"])
    checks["procedures_outside_frozen_P01277_M"] = not (procedures | mirrors) & frozen_m.keys()
    checks["Q_tree_bound"] = git(qgit, "rev-parse", commit + "^{tree}").decode().strip() == passport["q_input_tree"]
    checks["Q_single_parentless_commit"] = (git(qgit, "rev-list", "--count", "--all").strip() == b"1"
        and not any(line.startswith(b"parent ") for line in git(qgit, "cat-file", "-p", commit).splitlines()))
    checks["Q_only_expected_ref"] = git(qgit, "for-each-ref", "--format=%(refname) %(objectname)").decode().splitlines() == [passport["ref"] + " " + commit]
    checks["Q_HEAD_bound"] = (git(qgit, "symbolic-ref", "HEAD").decode().strip() == passport["ref"]
                             and git(qgit, "rev-parse", "HEAD").decode().strip() == commit)
    fsck = subprocess.run(["git", "--git-dir", str(qgit), "fsck", "--full", "--strict"], capture_output=True)
    checks["Q_fsck_strict"] = fsck.returncode == 0 and not fsck.stdout and not fsck.stderr
    physical = {line.split()[0] for line in git(qgit, "cat-file", "--batch-all-objects", "--batch-check=%(objectname)").splitlines()}
    reachable = {line.split()[0] for line in git(qgit, "rev-list", "--objects", "--all").splitlines()}
    checks["Q_no_unreachable_objects"] = physical == reachable
    checks["Q_no_alternates_or_hooks"] = not (qgit / "objects/info/alternates").exists() and not (qgit / "hooks").exists()
    checks["operator_unchanged_from_P01277"] = sha(operator_path) == passport["operator_sha256"] == "c046b5ac1abbb8a82b14595f72c340b76e3e8ca6d2953557b93daa02e8b96641"
    checks["wrapper_bound"] = sha(wrapper) == passport["wrapper_sha256"]
    checks["passport_counts_match"] = (passport["files_in_q_input"] == len(actual)
        and passport["files_in_source_platform"] == sum(p.startswith("Platform/") for p in source))
    checks["no_extra_transport_file"] = passport["transport_marker"] is None and "Platform/COURSE_COMMIT" not in actual
    run = json.loads(check_run.read_text())
    checks["check_spec_PASS_on_exact_C"] = run["source_C"] == course and run["exit"] == 0
    for rel in ("skills/lesson-spec/scripts/m_form.py", "skills/lesson-spec/scripts/export_lists.py"):
        checks["exact_C_" + Path(rel).stem] = (source_root / rel).read_bytes() == git(source_git, "show", course + ":" + rel)
    result = {"status": "PASS" if all(checks.values()) else "FAIL", "source_C": course,
              "Q": commit, "Q_tree": passport["q_input_tree"], "checks": checks,
              "counts": {"Q": len(actual), "pair_m_C": len(pair or ()), "Q_objects": len(physical)},
              "P02_P10_files": foreign, "qualification_procedures": sorted(procedures),
              "qualification_mirrors": sorted(mirrors), "pair_m_C": sorted(pair or ()),
              "Q_dependencies_also_in_pair_m_C": sorted(selected & (pair or set())),
              "frozen_P01277_M": frozen["M"],
              "check_spec_run_sha256": sha(check_run), "operator_sha256": sha(operator_path),
              "wrapper_sha256": sha(wrapper), "verifier_sha256": sha(Path(__file__)),
              "pair_m_source_sha256": sha(source_root / "skills/lesson-spec/scripts/m_form.py")}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("source-git-dir", "source-root", "output", "operator", "wrapper", "check-run", "frozen-pair"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    result = verify(args.source_git_dir, args.source_root, args.output, args.operator,
                    args.wrapper, args.check_run, args.frozen_pair)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    sys.exit(0 if result["status"] == "PASS" else 1)
