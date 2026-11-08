#!/usr/bin/env python3
"""check_anchors.py: every anchor of anchors.tsv must match the bytes of the slice (git show PIN:path, line N contains substring)."""
import subprocess, sys, pathlib
PIN = "862455715be8e155e0c80566d6f60d443a8b2650"
HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE
while not (REPO / ".git").exists():
    REPO = REPO.parent
bad = 0; n = 0
for line in open(HERE / "anchors.tsv", encoding="utf8"):
    if line.startswith("#") or not line.strip():
        continue
    a, path, ln, sub = line.rstrip("\n").split("\t")
    data = subprocess.run(["git", "show", f"{PIN}:{path}"], cwd=REPO, capture_output=True).stdout.decode("utf8")
    lines = data.split("\n")
    n += 1
    if not (1 <= int(ln) <= len(lines)) or sub not in lines[int(ln) - 1]:
        bad += 1
        print("MISMATCH", a, path, ln, repr(sub))
print(f"anchors checked: {n}, mismatches: {bad}")
sys.exit(1 if bad else 0)
