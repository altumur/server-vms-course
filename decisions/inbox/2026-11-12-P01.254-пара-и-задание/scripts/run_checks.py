"""Reproduce P01.254 local export verification; no candidate/process probe.

Copy the submitted scripts into <evidence>/scripts next to the accepted operator
copies and exact-C archive. Usage: python3 -B run_checks.py <evidence> <own worktree>
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import time

B, W = map(lambda p: Path(p).resolve(), sys.argv[1:3])
I = json.loads((B / "IDENTITIES.json").read_text())
C, M, J, JIC = (I[k] for k in ("C", "M", "J", "JI"))
P, JI = Path(I["pair_directory"]), Path(I["JI_directory"])


def run(name, argv, expected=0):
    start = time.monotonic()
    p = subprocess.run(argv, cwd=B, capture_output=True)
    (B / (name + ".out")).write_bytes(p.stdout)
    (B / (name + ".err")).write_bytes(p.stderr)
    record = {"argv": argv, "exit": p.returncode, "expected_exit": expected,
              "elapsed_seconds": time.monotonic() - start,
              "stdout_sha256": hashlib.sha256(p.stdout).hexdigest(),
              "stderr_sha256": hashlib.sha256(p.stderr).hexdigest()}
    (B / (name + ".run.json")).write_text(json.dumps(record, indent=1) + "\n")
    assert p.returncode == expected, (name, p.returncode, p.stderr.decode())
    return p.stdout


def py(name, *args):
    return [sys.executable, "-B", str(B / "scripts" / name), *map(str, args)]


def pair():
    run("VERIFY-PAIR", py("verify_pair_p01254.py", B, C, M, J))


def judge_input():
    raw = run("VERIFY-JI-raw", py("verify_ji_p01254.py", W, C, P / "J.git", J,
              JI / "JI.git", JIC, P / "M.git", JI / "FILTER-JI.json"), expected=1)
    (B / "VERIFY-JI-raw.json").write_bytes(raw)
    out = run("VERIFY-JI-classify", py("verify_ji_p01254_classify.py",
              B / "VERIFY-JI-raw.json", JI / "FILTER-JI.json"))
    (B / "VERIFY-JI.json").write_bytes(out)
    out = run("JI-FILTER", py("ji_filter_blob.py", P / "J.git", J))
    (B / "JI-FILTER.json").write_bytes(out)


def passport():
    run("PASSPORT-CONTROLS", py("passport_controls.py"))


with ThreadPoolExecutor(max_workers=3) as pool:
    jobs = [pool.submit(f) for f in (pair, judge_input, passport)]
    for job in jobs:
        job.result()
out = run("VERIFY-ALL", py("verify_assert.py"))
print(out.decode())
