"""Prepare representative-only delivery, never execute it.

Uses the accepted P01.180 setup procedure with new immutable identities. Checks
the shell syntax and embedded parameters only. Usage: prepare_delivery.py B W.
"""
from pathlib import Path
import ast
import hashlib
import json
import shutil
import subprocess
import sys

B, W = map(lambda x: Path(x).resolve(), sys.argv[1:3])
I = json.loads((B / "IDENTITIES.json").read_text())
D = W / "decisions/inbox/2026-11-12-P01.254-пара-и-задание/scripts/delivery"
D.mkdir(exist_ok=True)
E = B / "delivery"
E.mkdir(exist_ok=True)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def tree(gd, commit):
    return subprocess.check_output(["git", "--git-dir", str(gd), "rev-parse", commit + "^{tree}"]).decode().strip()


mt = tree(Path(I["pair_directory"]) / "M.git", I["M"])
jt = tree(Path(I["JI_directory"]) / "JI.git", I["JI"])
old = W / "decisions/inbox/2026-11-12-P01.180-пара/scripts/delivery/setup.sh"
setup = old.read_text()
replacements = {
    "P01.180": "P01.254",
    "/home/pilot/run-p01180-pair-20261112": str(B),
    "pair-41a9493fb08c": "pair-" + I["C"][:12],
    "ji-41a9493fb0": "ji-" + I["C"][:12],
    "be48405e645b49985d35efc42b6d61c2f304c4d8": I["M"],
    "6bee0529ff68211f23f7622cd79786b708be95d0": mt,
    "be48405e645b": I["M"][:12],
    "be48405e": I["M"][:8],
    "0b44f9e2e20cda6f4a2ad5dbab58ae93f346bd96cf559bad9a14e38e2c42ef01": I["M_passport_sha256"],
    "9daca227dbc08ce3d4a14c6d47c6ea3f94e55034": I["JI"],
    "8df57f6ee415205c4db08d99013214c7ec27b39d": jt,
    "9daca227": I["JI"][:8],
    "e4f43d403a2a2093e4b3fd72f1cc59c4b00f9a803c807c16684322d8a715766d": I["JI_passport_sha256"],
    "605f12bb9b4664e5e7e9517722fcf5464faf219b": I["J"],
    "605f12bb": I["J"][:8],
}
for old_value, new_value in replacements.items():
    assert old_value in setup, old_value
    setup = setup.replace(old_value, new_value)
# The P01.180 procedure masked pipeline failures and inventory mismatches.
failures = {
    "set -eu\n": "set -euo pipefail\n",
    'diff <(echo "$BEFORE") <(echo "$AFTER") || true; }':
        'diff <(echo "$BEFORE") <(echo "$AFTER") || true; exit 1; }',
    '|| echo "parents_unchanged NO"':
        '|| { echo "parents_unchanged NO"; exit 1; }',
    '|| echo "trial_views_unchanged NO"':
        '|| { echo "trial_views_unchanged NO"; exit 1; }',
}
for old_value, new_value in failures.items():
    assert setup.count(old_value) == 1, old_value
    setup = setup.replace(old_value, new_value)
setup = "# PREPARED ONLY. Execute through the representative/ops103 after their authorization.\n" + setup
assert I["M"] in setup and I["JI"] in setup and I["M_passport_sha256"] in setup
for stale in ("run-p01180", "pair-41a949", "ji-41a949", "be48405e", "9daca227", "605f12bb"):
    assert stale not in setup, stale
for target in (D / "setup.sh", E / "setup.sh"):
    target.write_text(setup)

sources = [("M", str(Path(I["pair_directory"]) / "M.git"), I["M"],
            "/srv/b11-isolation/model-specs/" + I["M"], "model"),
           ("JI", str(Path(I["JI_directory"]) / "JI.git"), I["JI"],
            "/srv/b11-isolation/judge-input/" + I["JI"], "judge-input")]
verify = '''"""P01.254: representative-only post-delivery verification; prepared, not run."""
import hashlib
import json
import os
import stat
import subprocess

SOURCES = __SOURCES__
M_PASSPORT_SHA256 = __M_PASSPORT_SHA256__

def g(d, *args):
    return subprocess.check_output(["git", "-c", "safe.directory=*", "--git-dir", d, *args])

def tree(d, commit):
    result = {}
    for row in g(d, "ls-tree", "-rz", commit).split(b"\\0"):
        if row:
            meta, path = row.split(b"\\t", 1)
            mode, kind, blob = meta.decode().split()
            assert kind == "blob" and mode in ("100644", "100755")
            result[path.decode()] = (mode, blob)
    return result

result = {}
for name, source, commit, destination, ref in SOURCES:
    copied_git = os.path.join(destination, os.path.basename(source))
    expected = tree(source, commit)
    actual_git = tree(copied_git, commit)
    actual_files = set()
    bad = []
    root = os.path.join(destination, "tree")
    for dp, dirs, files in os.walk(root):
        assert not any(os.path.islink(os.path.join(dp, d)) for d in dirs)
        for f in files:
            path = os.path.join(dp, f)
            rel = os.path.relpath(path, root)
            actual_files.add(rel)
            assert stat.S_ISREG(os.lstat(path).st_mode)
            raw = open(path, "rb").read()
            blob = hashlib.sha1(b"blob %d\\0" % len(raw) + raw).hexdigest()
            value = ("100755" if os.stat(path).st_mode & 0o111 else "100644", blob)
            if expected.get(rel) != value:
                bad.append(rel)
    refs = g(copied_git, "for-each-ref", "--format=%(refname)").decode().split()
    physical = {line.split()[0] for line in g(copied_git, "cat-file", "--batch-all-objects", "--batch-check").splitlines()}
    reachable = {line.split()[0] for line in g(copied_git, "rev-list", "--objects", "--all").splitlines()}
    fsck = subprocess.run(["git", "-c", "safe.directory=*", "--git-dir", copied_git, "fsck", "--full", "--strict"], capture_output=True)
    record = {"files": len(expected), "git_tree_equal": expected == actual_git,
              "file_roster_equal": actual_files == set(expected), "bad": bad,
              "refs_equal": refs == ["refs/heads/" + ref],
              "parentless": g(copied_git, "rev-list", "--parents", commit).decode().split() == [commit],
              "all_commits": g(copied_git, "rev-list", "--all").decode().split() == [commit],
              "physical_equals_reachable": physical == reachable,
              "no_hooks_info_logs": not any(os.path.exists(os.path.join(copied_git, x)) for x in ("hooks", "info", "logs")),
              "fsck": fsck.returncode == 0}
    if name == "M":
        record["passport_sha256"] = hashlib.sha256(open(os.path.join(destination, "PASSPORT-M.json"), "rb").read()).hexdigest() == M_PASSPORT_SHA256
    result[name] = record
    assert not bad and all(v for k, v in record.items() if isinstance(v, bool)), (name, record)
print(json.dumps({"OK": True, "views": result}, indent=1))
'''.replace("__SOURCES__", repr(sources)).replace("__M_PASSPORT_SHA256__", repr(I["M_passport_sha256"]))
ast.parse(verify)
for target in (D / "verify.py", E / "verify.py"):
    target.write_text(verify)
syntax = subprocess.run(["bash", "-n", str(D / "setup.sh")], capture_output=True)
assert syntax.returncode == 0, syntax.stderr.decode()
manifest = {"prepared_only": True, "executed": False, "C": I["C"], "M": I["M"], "M_tree": mt,
            "JI": I["JI"], "JI_tree": jt, "M_passport_sha256": I["M_passport_sha256"],
            "JI_passport_sha256": I["JI_passport_sha256"], "bash_n_exit": syntax.returncode,
            "python_ast_parse": True, "embedded_parameters_match_source": True,
            "setup_sha256": sha(D / "setup.sh"), "verify_sha256": sha(D / "verify.py"),
            "procedure_source": str(old), "procedure_source_sha256": sha(old),
            "scope": "syntax and immutable parameter preparation only; stand paths, ACLs and canary not checked"}
for target in (D / "PARAMETERS.json", E / "PARAMETERS.json"):
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n")
print(json.dumps(manifest, indent=1))
