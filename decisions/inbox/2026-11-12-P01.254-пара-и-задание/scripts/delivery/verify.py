"""P01.254: representative-only post-delivery verification; prepared, not run."""
import hashlib
import json
import os
import stat
import subprocess

SOURCES = [('M', '/home/pilot/run-p01254-pair-20261112-r3/pair-298e28fda4b9/M.git', '847ac9d1fb36bd1153450f99ddc4805c2609877e', '/srv/b11-isolation/model-specs/847ac9d1fb36bd1153450f99ddc4805c2609877e', 'model'), ('JI', '/home/pilot/run-p01254-pair-20261112-r3/ji-298e28fda4b9/JI.git', '2fc272022ff073aaa75ce6dac1b953286c0d8b3d', '/srv/b11-isolation/judge-input/2fc272022ff073aaa75ce6dac1b953286c0d8b3d', 'judge-input')]
M_PASSPORT_SHA256 = '6bd5488d483ac38d848cbe21eed7099b91729dec3efa2234b766bd872cf96c8f'

def g(d, *args):
    return subprocess.check_output(["git", "-c", "safe.directory=*", "--git-dir", d, *args])

def tree(d, commit):
    result = {}
    for row in g(d, "ls-tree", "-rz", commit).split(b"\0"):
        if row:
            meta, path = row.split(b"\t", 1)
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
            blob = hashlib.sha1(b"blob %d\0" % len(raw) + raw).hexdigest()
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
