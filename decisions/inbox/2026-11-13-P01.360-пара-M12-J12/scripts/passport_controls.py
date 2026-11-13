"""Separate passport controls for final M; no product/probe process is run."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys

B = Path(sys.argv[1]).resolve()
I = json.loads((B / "IDENTITIES.json").read_text())
T = B / "passport/controls-final"
T.mkdir()
results = []


def unpack(name, repo, commit):
    out = T / name
    out.mkdir()
    producer = subprocess.Popen(["git", "--git-dir", str(repo), "archive", commit], stdout=subprocess.PIPE)
    consumer = subprocess.run(["tar", "-x", "-C", str(out)], stdin=producer.stdout)
    producer.stdout.close()
    assert producer.wait() == consumer.returncode == 0
    return out


def run(name, root, commit, expected):
    argv = [sys.executable, "-I", "-B", str(B / "operator/check_m_passport.py"), I["M_passport"], str(root), commit]
    result = subprocess.run(argv, capture_output=True)
    (T / (name + ".out")).write_bytes(result.stdout)
    (T / (name + ".err")).write_bytes(result.stderr)
    row = {"name": name, "root": str(root), "argv": argv, "expected_exit": expected,
           "exit": result.returncode, "pass": result.returncode == expected,
           "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
           "stderr_sha256": hashlib.sha256(result.stderr).hexdigest()}
    results.append(row)
    assert row["pass"], row
    print(name, result.returncode)


base = unpack("M-as-is", I["M_git"], I["M"])
j = unpack("full-J", I["J_git"], I["J"])
run("M-as-is", base, I["M"], 0)
run("J-with-M-passport", j, I["M"], 1)
for name in ("byte-change", "missing", "symlink", "extra-J-only", "excluded-common"):
    root = T / name
    shutil.copytree(base, root)
    path = root / "Platform/01-store/forms/code-rules.tsv"
    if name == "byte-change":
        path.write_bytes(path.read_bytes() + b"\nx")
    elif name == "missing":
        path.unlink()
    elif name == "symlink":
        path.unlink()
        path.symlink_to("stages.tsv")
    else:
        relative = "Platform/01-store/forms/extra.scenarios.tsv" if name == "extra-J-only" else \
                   "Platform/common/vectors/slot/README.md"
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((j / relative).read_bytes())
    run(name, root, I["M"], 1)
old_repo = "/home/pilot/P01.299-evidence/r2/narrow/M.git"
old_commit = "bfa66fa76ecfb2c1d9b59c7ac7e2641722493942"
old = unpack("other-M-P01.299", old_repo, old_commit)
run("other-M-tree", old, I["M"], 1)
run("other-M-commit", base, old_commit, 1)
out = {"M": I["M"], "passport": I["M_passport"], "checks": results, "OK": True}
(B / "passport/CONTROLS.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
