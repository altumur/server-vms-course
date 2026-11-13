"""P04.32: read-only check of the committed export lists and the narrow M.

Usage: spec-python -B verify.py <own-course-worktree> <base-commit>
No export is published and no candidate, judge or generation is started.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace


root = Path(sys.argv[1]).resolve()
base = sys.argv[2]
prefix = "Platform/04-controller/"
list_path = prefix + "forms/export.json"


def git(*args):
    return subprocess.check_output(["git", "-C", str(root), *args])


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, root / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


commit = git("rev-parse", "HEAD").decode().strip()
assert not git("diff", "HEAD", "--", "Platform", "skills/lesson-spec/scripts"), "uncommitted spec"
assert not git("ls-files", "--others", "--exclude-standard", "--", "Platform"), "untracked Platform files"
sys.path.insert(0, str(root / "skills/lesson-spec/scripts"))
import export_lists
import m_form

operator_path = "decisions/inbox/2026-11-11-P02.52-операторы/operator/b7_export_pair.py"
operator = load_module("p0252_pair", operator_path)
judge_operator = load_module(
    "p0252_judge", "decisions/inbox/2026-11-11-P02.52-операторы/operator/judge_input_export.py")
git_dir = git("rev-parse", "--absolute-git-dir").decode().strip()
fd = os.open(git_dir, os.O_RDONLY | os.O_DIRECTORY)
try:
    entries = operator._source(fd, commit)
finally:
    os.close(fd)
marker = (commit + "\n").encode()
entries[operator.MARKER] = ("100644", operator._blob_id(marker), marker)
selected = operator._classification(entries)
cases = operator._case_boundary(entries, selected)
assembled, errors, stats = export_lists.assemble(root)
assert not errors, errors
lesson_list = json.loads(entries[list_path][2])
own = {p for p in entries if p.startswith(prefix)}
assert len(own) == 81
results = {}


def base_filter(side):
    common = export_lists.COMMON[side].as_posix()
    doc = json.loads(git("show", f"{base}:{common}"))
    records = list(doc["files"])
    for path in git("ls-tree", "-r", "--name-only", base, "--", "Platform").decode().splitlines():
        if operator.LESSON_LIST.fullmatch(path):
            records.extend(json.loads(git("show", f"{base}:{path}"))[side])
    doc["files"] = sorted(records, key=lambda r: r["path"].encode("utf-8"))
    return doc


for side in ("model", "judge"):
    if side == "model":
        raw, doc, sources = operator._assemble(entries)
    else:
        raw, sources = judge_operator.assemble(git_dir, {p: (mode, oid) for p, (mode, oid, _) in entries.items()})
        doc = json.loads(raw)
    assert doc["files"] == sorted(assembled[side], key=lambda r: r["path"].encode("utf-8")), side
    assert {r["path"] for r in lesson_list[side]} == own, side
    common = export_lists.COMMON[side].as_posix()
    assert not any(r["path"].startswith(prefix) for r in json.loads(entries[common][2])["files"])
    former = base_filter(side)
    without_new_list = dict(doc, files=[r for r in doc["files"] if r["path"] != list_path])
    canonical = lambda value: (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    assert canonical(without_new_list) == canonical(former), side
    assert sum(r["path"].startswith(prefix) for r in former["files"]) == 80
    assert list_path in sources
    results[side] = {"records": len(doc["files"]), "lesson_records": len(lesson_list[side]),
                     "preserved_records": 80, "assembled_sha256": hashlib.sha256(raw).hexdigest()}
    if side == "judge":
        seen, included = judge_operator.parse_filter(raw)
        assert seen == set(entries)
        assert list_path not in included
        results[side]["included"] = len(included)

model = {r["path"]: r["disposition"] for r in assembled["model"]}
check = SimpleNamespace(root=root)
lesson = m_form.Lesson(check, "P/04", root / prefix)
dependencies = m_form.dependencies(check, lesson)
narrow = m_form.pair_m(check, lesson, model)
assert dependencies is not None and narrow is not None
assert all(p in entries for p in dependencies), sorted(dependencies - entries.keys())
public_dependencies = {p for p in dependencies if model[p] == "model_and_judge" and not m_form.q_kind(p)}
assert public_dependencies <= narrow
external = {p for p in narrow if export_lists.LESSON_DIR.fullmatch(p.split("/")[1])
            and not p.startswith(prefix)}
assert external == {p for p in public_dependencies if export_lists.LESSON_DIR.fullmatch(p.split("/")[1])}
narrow_entries = {p: entries[p] for p in narrow | {operator.MARKER}}
assert all(model[p] == "model_and_judge" for p in narrow_entries)
assert not cases & narrow_entries.keys()
assert not any("/ru/" in p or m_form.q_kind(p) for p in narrow_entries)
operator._legacy_model_content_guard(narrow_entries)
manifest = [{"path": p, "mode": mode, "blob": oid, "sha256": hashlib.sha256(raw).hexdigest()}
            for p, (mode, oid, raw) in sorted(narrow_entries.items())]
print(json.dumps({"status": "PASS", "commit": commit, "base": base, "worktree": str(root),
                  "operator": operator_path, "operator_sha256": hashlib.sha256((root / operator_path).read_bytes()).hexdigest(),
                  "stats": stats, "filters": results, "registered_case_tables": len(cases),
                  "narrow_m_files": len(manifest), "lesson_m_files": sum(p.startswith(prefix) for p in narrow),
                  "public_dependencies": sorted(public_dependencies),
                  "non_model_dependencies": sorted(dependencies - public_dependencies),
                  "external_lesson_contracts": sorted(external), "narrow_m_manifest": manifest},
                 ensure_ascii=False, indent=2))
