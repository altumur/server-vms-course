#!/usr/bin/env python3
"""Reproduce OBSH.90's preservation and whole-file M/J checks; no candidate runs."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BASE = "94c2d1aa5185c7a6ab9fd4572782e6153704101f"
PACKAGES = ("sealing", "row-check", "door-token", "domain-token")

def original(path):
    return subprocess.check_output(["git", "show", f"{BASE}:{path}"], cwd=ROOT)

def digest(data):
    return hashlib.sha256(data).hexdigest()

public = set()
companions = set()
for package in PACKAGES:
    for language in ("", "ru/"):
        path = f"Platform/common/{language}vectors/{package}/README.md"
        companion = path.replace("README.md", "README.cases.md")
        old = original(path)
        title, metadata, semantic_body = old.split(b"\n\n", 2)
        kept = (ROOT / companion).read_bytes()
        assert semantic_body in kept, f"old semantic body changed or lost: {path}"
        assert metadata in kept, f"old source metadata lost: {path}"
        new = (ROOT / path).read_text()
        assert "(judge-only: `README.cases.md`)" in new, path
        for pattern in (r"token-\d", r"born-empty", r"labels_repeat", r"unique_required_", r"forged_signer", r"three_parts", r"rotate\*", r"k1→k2"):
            assert not re.search(pattern, new), (path, pattern)
        public.add(path)
        companions.add(companion)
        print(f"PRESERVED {path}: old semantic body sha256={digest(semantic_body)}; exact contiguous body and metadata in {companion}")

for path in ("Platform/common/export-model-filter.json", "Platform/common/acceptance/judge-input-filter.json"):
    old = json.loads(original(path))
    new = json.loads((ROOT / path).read_text())
    assert {key: value for key, value in old.items() if key != "files"} == {key: value for key, value in new.items() if key != "files"}
    before = {item["path"]: item for item in old["files"]}
    after = {item["path"]: item for item in new["files"]}
    assert len(before) == len(old["files"]) and len(after) == len(new["files"])
    assert set(after) - set(before) == companions
    assert not set(before) - set(after)
    assert [item["path"] for item in new["files"]] == sorted(after, key=lambda p: p.encode())
    for name in set(before) - public:
        assert before[name] == after[name], f"unrelated filter entry changed: {path}: {name}"
    model = "export-model" in path
    for name in public | companions:
        ru = "/ru/" in name
        expected = ("judge_only" if ru or name in companions else "model_and_judge") if model else ("exclude" if ru else "include")
        assert after[name]["disposition"] == expected, (path, name)
    print(f"FILTER {path}: only 8 README records and 8 companion records; M/J and ru dispositions correct")

for package in PACKAGES:
    for path in sorted((ROOT / f"Platform/common/vectors/{package}").glob("*.tsv")):
        relative = path.relative_to(ROOT).as_posix()
        assert original(relative) == path.read_bytes(), f"vector bytes changed: {relative}"
print("PASS: 8 original semantic bodies and metadata retained byte for byte; all 4 English originals retained in J; 4 public English interfaces in M; vector TSV bytes unchanged.")
