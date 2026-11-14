#!/usr/bin/env python3
"""Воспроизводимая сверка сохранности OBSH.91 без запуска кандидатов."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BASE = "d8bbe74198c354bd734d8abff7b4c6f9739bb2d2"


def original(path):
    return subprocess.check_output(["git", "show", f"{BASE}:{path}"], cwd=ROOT)


def digest(data):
    return hashlib.sha256(data).hexdigest()


public = set()
companions = set()
for language in ("", "ru/"):
    path = f"Platform/common/{language}vectors/peer/README.md"
    companion = path.replace("README.md", "README.cases.md")
    old = original(path)
    title, metadata, body = old.split(b"\n\n", 2)
    kept = (ROOT / companion).read_bytes()
    # Граница тела: после первого заголовка и следующего абзаца metadata.
    assert body in kept, f"прежнее тело изменено или потеряно: {path}"
    assert metadata in kept, f"прежняя metadata потеряна: {path}"
    new = (ROOT / path).read_text()
    assert "(judge-only: `README.cases.md`)" in new, path
    for pattern in (r"peer-\d", r"w2c test ca", r"1760000000", r"M11/8", r"ADR-\d"):
        assert not re.search(pattern, new), (path, pattern)
    public.add(path)
    companions.add(companion)
    print(f"PRESERVED {path}: body_bytes={len(body)}, body_sha256={digest(body)}; "
          f"metadata_bytes={len(metadata)}, metadata_sha256={digest(metadata)}; "
          f"оба блока побайтно и целиком в {companion}")

for path in ("Platform/common/export-model-filter.json", "Platform/common/acceptance/judge-input-filter.json"):
    old = json.loads(original(path))
    new = json.loads((ROOT / path).read_text())
    assert {k: v for k, v in old.items() if k != "files"} == {k: v for k, v in new.items() if k != "files"}
    before = {row["path"]: row for row in old["files"]}
    after = {row["path"]: row for row in new["files"]}
    assert len(before) == len(old["files"]) and len(after) == len(new["files"])
    assert set(after) - set(before) == companions
    assert not set(before) - set(after)
    assert [row["path"] for row in new["files"]] == sorted(after, key=lambda p: p.encode())
    for name in set(before) - public:
        assert before[name] == after[name], f"посторонняя запись фильтра изменена: {path}: {name}"
    model = "export-model" in path
    for name in public | companions:
        ru = "/ru/" in name
        if model:
            expected = "judge_only" if ru or name in companions else "model_and_judge"
        else:
            expected = "exclude" if ru or name in companions else "include"
        assert after[name]["disposition"] == expected, (path, name)
    print(f"FILTER {path}: изменения только записей peer README и спутника; "
          "остальные записи и поля фильтра неизменны; порядок UTF-8 и M/J верны")

for path in sorted((ROOT / "Platform/common/vectors/peer").glob("*.tsv")):
    relative = path.relative_to(ROOT).as_posix()
    current = path.read_bytes()
    assert original(relative) == current, f"байты векторов изменены: {relative}"
    print(f"UNCHANGED {relative}: bytes={len(current)}, sha256={digest(current)}")

for name in ("wire.tsv", "consumers.tsv"):
    path = f"Platform/common/vectors/{name}"
    assert original(path) == (ROOT / path).read_bytes(), path

print("PASS: прежние en/ru тела и metadata сохранены побайтно; публичная en-форма в M/J; "
      "случаи en по прежнему exclude в J, judge_only в M; ru вне M/J; TSV не менялись.")
