"""P01.304: обёртка Q над неизменёнными функциями закреплённого оператора J.

Фильтр Q — опись include, а не полная классификация J. Поэтому build() для J
не вызывается: его запрет проб и требование метки противоречат составу Q.
Перенос blob, режимов и дерева выполняют прежние функции без подмены.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


OPERATOR_SHA256 = "c046b5ac1abbb8a82b14595f72c340b76e3e8ca6d2953557b93daa02e8b96641"
REF = "refs/heads/qualification-input"
Q_FILTER = "Platform/common/qualification-input-filter.json"


def build(source_git, course, operator_path, filter_path, output):
    operator_bytes = operator_path.read_bytes()
    if hashlib.sha256(operator_bytes).hexdigest() != OPERATOR_SHA256:
        raise ValueError("байты оператора отличаются от P01.277")
    spec = importlib.util.spec_from_file_location("p01304_pinned_operator", operator_path)
    op = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(op)
    if not op.HEX40.fullmatch(course):
        raise ValueError("нужен полный C")
    if op.git(source_git, "rev-parse", "--verify", course + "^{commit}").decode().strip() != course:
        raise ValueError("C не является точным коммитом")
    if filter_path != Q_FILTER:
        raise ValueError("P01.304 использует канонический фильтр Q")
    if os.path.lexists(output):
        raise ValueError("выход уже существует")
    platform_tree = op.git(source_git, "rev-parse", course + ":Platform").decode().strip()
    entries = {"Platform/" + p: v for p, v in op.read_tree(source_git, platform_tree).items()}
    filter_blob = entries[filter_path][1]
    raw = op.git(source_git, "cat-file", "blob", filter_blob)
    doc = op.load_json(raw, filter_path)
    if type(doc.get("version")) is not int:
        raise ValueError("version должен быть целым числом")
    op.sorted_records(doc["files"], filter_path)
    seen, included = op.parse_filter(raw)
    if seen != included:
        raise ValueError("Q допускает только include")
    forbidden_filters = {filter_path, "Platform/common/export-model-filter.json", op.FILTER}
    for path in included:
        if (not path.startswith("Platform/") or path not in entries
                or "ru" in path.split("/") or re.search(r"[*?\[]", path)
                or path in forbidden_filters or op.LESSON_LIST.fullmatch(path)):
            raise ValueError("недопустимый путь Q: " + path)
    procedures = {p for p in entries if "/qualification/" in p and "/ru/" not in p}
    if not procedures <= included:
        raise ValueError("в фильтре отсутствуют процедуры Q")
    selected = {p: entries[p] for p in sorted(included, key=lambda x: x.encode("utf8"))}
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=".q-", dir=output.parent))
    bare = str(tmp / "Q.git")
    subprocess.run(["git", "init", "-q", "--bare", "--template=", bare], check=True, env=op.ENV)
    files = []
    for path, (mode, oid) in selected.items():
        data = op.git(source_git, "cat-file", "blob", oid)
        if op.git(bare, "hash-object", "-w", "--stdin", data=data).decode().strip() != oid:
            raise ValueError("blob изменился при переносе: " + path)
        files.append({"path": path, "mode": mode, "blob": oid, "bytes": len(data),
                      "sha256": hashlib.sha256(data).hexdigest()})
    tree = op.mktree(bare, selected)
    commit = op.git(bare, "commit-tree", tree, "-m", "Q-input").decode().strip()
    op.git(bare, "update-ref", REF, commit)
    op.git(bare, "symbolic-ref", "HEAD", REF)
    if op.read_tree(bare, commit) != selected:
        raise ValueError("дерево Q отличается от отбора")
    passport = {"version": 1, "source_C": course,
                "source_tree": op.git(source_git, "rev-parse", course + "^{tree}").decode().strip(),
                "source_platform_tree": platform_tree,
                "filter_path": filter_path, "filter_blob": filter_blob,
                "filter_sha256": hashlib.sha256(raw).hexdigest(), "filter_file": "FILTER-Q.json",
                "q_input_commit": commit, "q_input_tree": tree, "ref": REF,
                "files_in_source_platform": len(entries), "files_in_q_input": len(selected),
                "operator_sha256": OPERATOR_SHA256, "wrapper_sha256": op.sha256_file(__file__),
                "operator_functions": ["git", "read_tree", "load_json", "sorted_records",
                                       "parse_filter", "mktree", "sha256_file"],
                "transport_marker": None}
    (tmp / "FILTER-Q.json").write_bytes(raw)
    for name, value in (("PASSPORT-Q.json", passport), ("FILES.json", files)):
        (tmp / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    os.rename(tmp, output)
    return passport


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-git-dir", required=True)
    parser.add_argument("--course-commit", required=True)
    parser.add_argument("--operator", required=True, type=Path)
    parser.add_argument("--filter-path", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.source_git_dir, args.course_commit, args.operator,
                           args.filter_path, args.output), sort_keys=True))
