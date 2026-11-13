"""Independent exact-roster, source-byte, passport and object checks for P02.68.

Usage: venv-spec/bin/python -B verify_m.py <evidence/r2>
Reads committed source and the final M directory; runs no export operator.
"""
from pathlib import Path
import csv
import hashlib
import io
import json
import re
import stat
import subprocess
import sys

B = Path(sys.argv[1]).resolve()
I = json.loads((B / "IDENTITIES.json").read_text())
C, M, ROOT = I["C"], I["M"], Path(I["directory"])


def git(repo, *args):
    return subprocess.check_output(["git", "--git-dir", str(repo), *args], stderr=subprocess.PIPE)


def tree(repo, ref, prefix=None):
    args = ["ls-tree", "-rz", ref] + (["--", prefix] if prefix else [])
    out = {}
    for line in git(repo, *args).split(b"\0"):
        if line:
            meta, path = line.split(b"\t", 1)
            mode, kind, oid = meta.decode().split()
            assert kind == "blob" and mode in {"100644", "100755"}
            out[path.decode()] = (mode, oid)
    return out


source = tree(B / "source.git", C, "Platform")
j = tree(I["J_git"], I["J"])
raw_m = tree(I["raw_M_git"], I["raw_M"])
m = tree(I["M_git"], M)
marker = "Platform/COURSE_COMMIT"
assert {p: v for p, v in j.items() if p != marker} == source
assert git(I["J_git"], "show", I["J"] + ":" + marker) == (C + "\n").encode()
sys.path.insert(0, str(B / "archive-C/skills/lesson-spec/scripts"))
import export_lists
import m_form
assembled, errors, _ = export_lists.assemble(B / "archive-C")
assert not errors, errors
model = {row["path"]: row["disposition"] for row in assembled["model"]}
assert raw_m == {p: v for p, v in j.items() if model[p] == "model_and_judge"}
check = type("Check", (), {"root": B / "archive-C"})()
lesson = m_form.Lesson(check, "P/02", check.root / "Platform/02-installer")
expected = m_form.pair_m(check, lesson, model) | {marker}
deps = m_form.dependencies(check, lesson)
assert set(m) == expected and deps <= m.keys()
assert all(j[p] == value for p, value in m.items())
external = {p for p in m if re.match(r"Platform/\d\d-", p) and not p.startswith("Platform/02-installer/")}
assert external == {p for p in deps if re.match(r"Platform/\d\d-", p) and not p.startswith("Platform/02-installer/")}
assert not any("/ru/" in p or m_form.q_kind(p) for p in m)
assert all(p.startswith("Platform/") and not p.endswith(("/scenarios.tsv", "/seams.tsv")) for p in m)
passport = json.loads((B / "PASSPORT-M.json").read_text())
assert passport["C"] == C and passport["M"]["commit"] == M and passport["count"] == len(m)
assert {r["path"]: (r["mode"], r["blob"]) for r in passport["files"]} == m
h = hashlib.sha256()
for row in passport["files"]:
    h.update(f"{row['mode']} {row['blob']}\t{row['path']}\n".encode())
assert h.hexdigest() == passport["files_sha256"] == I["files_sha256"]
paths, sums = set(), []
for path in ROOT.rglob("*"):
    st = path.lstat()
    assert not stat.S_ISLNK(st.st_mode) and not st.st_mode & 0o222
    if stat.S_ISDIR(st.st_mode):
        assert stat.S_IMODE(st.st_mode) == 0o555
    else:
        assert stat.S_ISREG(st.st_mode)
        rel = path.relative_to(ROOT).as_posix()
        paths.add(rel)
        mode, oid = m[rel]
        raw = path.read_bytes()
        expected_bytes = (C + "\n").encode() if rel == marker else git(B / "source.git", "cat-file", "blob", source[rel][1])
        assert raw == expected_bytes
        assert hashlib.sha1(b"blob %d\0" % len(raw) + raw).hexdigest() == oid
        assert stat.S_IMODE(st.st_mode) == (0o555 if mode == "100755" else 0o444)
        sums.append((rel, hashlib.sha256(raw).hexdigest()))
assert paths == set(m) and stat.S_IMODE(ROOT.stat().st_mode) == 0o555
assert (B / "SHA256SUMS").read_text() == "".join(d + "  " + p + "\n" for p, d in sorted(sums))
objects = {}
for name, repo, commit, branch in (("M", I["M_git"], M, "model"), ("raw_M", I["raw_M_git"], I["raw_M"], "model"),
                                 ("J", I["J_git"], I["J"], "judge")):
    assert git(repo, "for-each-ref", "--format=%(refname) %(objectname)").decode().splitlines() == ["refs/heads/" + branch + " " + commit]
    assert git(repo, "rev-list", "--parents", commit).decode().split() == [commit]
    physical = {r.split()[0] for r in git(repo, "cat-file", "--batch-all-objects", "--batch-check").decode().splitlines()}
    reachable = {r.split()[0] for r in git(repo, "rev-list", "--objects", "--all").decode().splitlines()}
    assert physical == reachable
    assert not (Path(repo) / "objects/info/alternates").exists()
    result = subprocess.run(["git", "--git-dir", repo, "fsck", "--full", "--strict"], capture_output=True)
    assert result.returncode == 0
    objects[name] = {"parentless": True, "single_ref": True, "physical_equals_reachable": True, "objects": len(physical), "fsck_exit": 0}
    if name == "M":
        private_blobs = {v[1] for p, v in j.items() if p not in m} - {v[1] for v in m.values()}
        assert not private_blobs & physical
        objects[name]["distinct_J_only_blobs_absent"] = len(private_blobs)
rows = list(csv.DictReader(io.StringIO("\n".join(line for line in (ROOT / "Platform/02-installer/forms/code-rules.tsv").read_text().splitlines() if not line.startswith("#"))), delimiter="\t"))
required = {json.loads(row["args"])["module"] for row in rows if row["kind"] == "requires_module" and json.loads(row["args"])["module"].startswith("servervms.local/common/")}
assert required == set(I["shared_module_pins"])
assert all(json.loads(row["args"])["from"] == "Platform/common/versions/go.mod" for row in rows if row["kind"] == "requires_module")
assert "Platform/common/modules.md" in m and "Platform/common/versions/go.mod" in m and "Platform/common/versions/go.sum" in m
go_sum = (ROOT / "Platform/common/versions/go.sum").read_text()
for module, version in I["shared_module_pins"].items():
    assert re.search(r"^" + re.escape(module + " " + version) + r" h1:\S+$", go_sum, re.M)
    assert re.search(r"^" + re.escape(module + " " + version + "/go.mod") + r" h1:\S+$", go_sum, re.M)
out = {"C": C, "M": M, "count": len(m), "directory": str(ROOT), "source_roster_exact": True,
    "assembled_filter_and_narrow_selection_exact": True, "M_subset_J_byte_exact": True,
    "passport_exact": True, "sha256sums_exact": True, "source_bytes_exact": True,
    "filesystem_modes_exact_no_write_bits_no_symlinks": True, "dependencies_complete": len(deps),
    "earlier_lesson_contract_files": sorted(p for p in external if p.startswith("Platform/01-store/")),
    "other_lesson_dependency_files": sorted(external), "shared_module_pins": I["shared_module_pins"],
    "objects": objects, "OK": True}
(B / "VERIFY-M.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
print(json.dumps({k: v for k, v in out.items() if k not in {"earlier_lesson_contract_files", "other_lesson_dependency_files"}}, ensure_ascii=False, indent=1))
