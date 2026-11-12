"""Reproduce task/control/local prep inputs with the final M identity.

Writes only the own evidence/report paths; existing matching files are checked.
The deployed specs/passport paths are changed only in task-prep-final.json.
Usage: python3 -B prepare_inputs.py <evidence> <report directory>
"""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

B, D = map(lambda p: Path(p).resolve(), sys.argv[1:3])
I = json.loads((B / "IDENTITIES.json").read_text())
M = I["M"]
root = Path(__file__).resolve().parents[4]
baseline = root / "decisions/inbox/2026-11-12-P01.254-пара-и-задание/task-attempt7.json"
task = json.loads(baseline.read_text())
task.update(name="p01-b-raft-" + M[:12], specs_sha=M, specs="/srv/b11-isolation/model-specs/" + M + "/tree")
task["seed_files"]["SPEC_VERSION"] = M + "\n"
task["stages"]["m_passport"] = {"path": "/srv/b11-isolation/model-specs/" + M + "/PASSPORT-M.json",
                                  "sha256": I["M_passport_sha256"]}
task["miniswe_plan_steps"] = 60
task["miniswe_plan_idle_steps"] = 8
task["stages"]["mech"]["test"] = "go test -race -count=1 ./..."


def write_or_check(path, raw):
    if path.exists():
        assert path.read_bytes() == raw, str(path)
    else:
        path.write_bytes(raw)


write_or_check(D / "task-attempt7.json", (json.dumps(task, ensure_ascii=False, indent=2) + "\n").encode())
source = Path("/home/pilot/owner-receipts/P01.184-control-task-20261112/TASK.md")
control = source.read_text()
old = "847ac9d1fb36bd1153450f99ddc4805c2609877e"
assert control.count(old) == 1
control = control.replace(old, M)
write_or_check(D / "CONTROL-TASK-attempt7.md", control.encode())
assert all((B / "M-tree-final" / path).is_file() for path in task["head_files"])
local = json.loads(json.dumps(task))
local["specs"] = str(B / "M-tree-final")
local["stages"]["m_passport"]["path"] = I["M_passport"]
write_or_check(B / "task-prep-final.json", (json.dumps(local, indent=1) + "\n").encode())


def differences(a, b, prefix=""):
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(a.keys() | b.keys()):
            out.extend(differences(a.get(key), b.get(key), prefix + "." + key if prefix else key))
    elif a != b:
        out.append({"field": prefix, "before": a, "after": b})
    return out


delta = differences(json.loads(baseline.read_text()), task)
local_delta = differences(task, local)
assert {row["field"] for row in local_delta} == {"specs", "stages.m_passport.path"}
out = {"M": M, "task_sha256": hashlib.sha256((D / "task-attempt7.json").read_bytes()).hexdigest(),
       "control_sha256": hashlib.sha256((D / "CONTROL-TASK-attempt7.md").read_bytes()).hexdigest(),
       "control_source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
       "control_changes": ["SPEC_VERSION only; all 14 reading paths remain present"],
       "task_delta_against_P01.254": delta, "local_prep_delta": local_delta, "OK": True}
(B / "TASK-CHECK.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
print(json.dumps({"OK": True, "task_changed_fields": len(delta), "control_changes": out["control_changes"]}))
