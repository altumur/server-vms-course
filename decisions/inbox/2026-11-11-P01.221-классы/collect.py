#!/usr/bin/env python3
"""Read saved evidence; never execute a candidate, build, probe or judge."""
import collections
import csv
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
RECEIPTS = Path("/home/pilot/owner-receipts")
K = RECEIPTS / "P01.163-court-kimi-20261111"
SRC = RECEIPTS / "P01.222-kimi-src-20261111"
PAIR = Path("/home/pilot/run-p0226-pair-20261111")
PINS = {
    "J": ("49e622795ca96b2e73904f1da5d203f2d103b2d5", PAIR / "ji-4694190a17/JI.git"),
    "M": ("bf8462085c08c5cd5f6b4cce3ca3580ebd74ffae", PAIR / "pair-4694190a178f/M.git"),
}
ENGINE = Path("/srv/minimax-loop/runs/p01-engine-8719b2141670/work")
ENGINE_SHA = "ef7dcf9b3138b6c8259633252db288be91f77621"
hashes = {}


def read(path):
    data = path.read_bytes()
    hashes[str(path)] = hashlib.sha256(data).hexdigest()
    return data


def spec(side, path):
    sha, repo = PINS[side]
    data = subprocess.check_output(["git", "--git-dir=" + str(repo), "show", sha + ":" + path])
    hashes[side + ":" + path] = hashlib.sha256(data).hexdigest()
    return data.decode()


def scenario_rows(chapter):
    path = f"Platform/01-store/acceptance/{chapter}/scenarios.tsv"
    lines = spec("J", path).split("\n")
    result = {}
    for line, text in enumerate(lines, 1):
        if not text or text.startswith("#"):
            continue
        scenario, step, request, expect = text.split("\t")
        if chapter == 1:
            request = json.loads(request)
        result[line] = dict(scenario=scenario, step=step, request=request, expect=expect)
    return result


expected_lines = {
    "P_01_1_door": [3, 266, 267, 268, 269, 270, 281, 282],
    "P_01_2_rights": [3, 7, 9],
    "P_01_3_daemon": [23, 25, 26, 27, 28, 29, 34, 35],
}
summary = {}
rows = []
for chapter, target in enumerate(expected_lines, 1):
    reports = [
        json.loads(read(K / "out-diag/Kfinal" / target / "engine.json")),
        json.loads(read(RECEIPTS / "P01.159-court-attempt6-20261111/out-diag/attempt6" / target / "engine.json")),
        json.loads(read(RECEIPTS / "P01.188-court-claude-20261111/out-diag/claude" / target / "engine.json")),
    ]
    step_maps = [{(s["table"], s["line"]): s for s in r["steps"]} for r in reports]
    assert step_maps[1] == step_maps[2], target
    assert step_maps[0].keys() == step_maps[1].keys(), target
    inputs = scenario_rows(chapter)
    unique = []
    common = []
    for key, step in step_maps[0].items():
        if step["result"] != "red":
            continue
        others = [m[key]["result"] for m in step_maps[1:]]
        if others == ["red", "red"]:
            common.append(step["line"])
            continue
        assert others == ["GREEN", "GREEN"], (target, step, others)
        n = step["line"]
        unique.append(n)
        source = inputs[n]
        assert source["scenario"] == step["scenario"]
        if chapter == 1:
            cls = "K1" if n == 3 else "K2"
        elif chapter == 2:
            cls = "K1"
        else:
            cls = "K4" if n >= 34 else "K3"
        rows.append([
            reports[0]["target"], step["table"], n, step["scenario"], source["step"],
            source["request"], source["expect"], step["class"], step["reason"],
            *others, cls, "кандидат", "не сохранён", "CLASS-" + cls + ".md",
        ])
    assert unique == expected_lines[target], (target, unique)
    summary[reports[0]["target"]] = {
        "own_red_lines": unique, "common_red_lines": common,
        "other_candidates_steps_equal": True,
        "Kfinal_red": len(unique) + len(common),
    }
assert len(rows) == 19
with (HERE / "red-steps.tsv").open("w") as f:
    writer = csv.writer(f, delimiter="\t", lineterminator="\n")
    writer.writerow(["target", "table", "line", "scenario", "step", "request", "expect",
                     "reported_class", "reported_reason", "MiniMax", "Opus", "review_class",
                     "outcome", "observed_HTTP", "package"])
    writer.writerows(rows)

norms = {}
for p in ["Platform/common/acceptance/PROFILE.md", "Platform/common/acceptance/README.md",
          "Platform/01-store/spec/01.1-store.norms.md",
          "Platform/01-store/spec/01.2-store.norms.md",
          "Platform/01-store/spec/01.3-store.norms.md"]:
    norms[p] = spec("M", p)
for p in ["Platform/common/acceptance/PROFILE.md", "Platform/common/acceptance/README.md"]:
    assert spec("J", p) == norms[p]
spec("J", "Platform/common/acceptance/forms/targets.routing.tsv")
spec("J", "Platform/01-store/acceptance/2/inputs/rights.json")

# LF is the JSONL delimiter. str.splitlines would also split literal Unicode
# separators inside tool output and incorrectly report damaged JSON records.
messages = [json.loads(line) for line in read(SRC / "kimi-run.jsonl").decode().split("\n") if line]
reads = {}
for response_line in [12, 14, 16, 35]:
    response = messages[response_line - 1]
    request = messages[response_line - 2]
    assert response["role"] == "tool"
    call = next(c for c in request["tool_calls"] if c["id"] == response["tool_call_id"])
    args = json.loads(call["function"]["arguments"])
    path = args["path"].split("/specs/", 1)[1]
    # Read tool prefixes each physical source line by '<number>\t'.
    unnumbered = "\n".join(line.split("\t", 1)[1]
                           for line in response["content"].split("\n") if "\t" in line)
    assert unnumbered == norms[path].removesuffix("\n"), path
    reads[path] = {
        "request_line": response_line - 1, "response_line": response_line,
        "tool_call_id": call["id"], "entire_pinned_file_in_response": True,
        "response_sha256": hashlib.sha256(response["content"].encode()).hexdigest(),
    }
profile_writes = []
for n, message in enumerate(messages, 1):
    for call in message.get("tool_calls", []):
        if call["function"]["name"] != "Write":
            continue
        args = json.loads(call["function"]["arguments"])
        if args.get("path", "").endswith("/01-store/acceptance.yaml"):
            assert args["content"].encode() == read(SRC / "Kfinal/01-store/acceptance.yaml")
            profile_writes.append({"line": n, "tool_call_id": call["id"]})
assert len(profile_writes) == 1

read(SRC / "TASK.md")
read(SRC / "SHA256SUMS")
source_paths = [
    "internal/storecore/fingerprint.go", "internal/storecore/apply.go",
    "internal/storecore/storecore_test.go", "internal/jcs/jcs.go",
    "internal/door/write.go", "internal/door/answers.go", "internal/door/door.go",
    "internal/door/door_test.go", "internal/group/group.go", "internal/group/group_test.go",
    "internal/daemon/backend.go", "internal/daemon/daemon.go",
    "internal/daemon/daemon_test.go",
]
source_comparison = {}
for p in source_paths:
    old = SRC / "K150/01-store" / p
    current = read(SRC / "Kfinal/01-store" / p)
    source_comparison[p] = {"K150_exists": old.exists(),
                            "same_bytes": read(old) == current if old.exists() else False}
for snapshot in ["K150", "Kfinal"]:
    for name in ["NOTES.md", "PLAN.md", "GUESSES.md", "SPEC_VERSION"]:
        read(SRC / snapshot / name)
assert not (SRC / "K150/01-store/acceptance.yaml").exists()
assert not (SRC / "K150/assembly.yaml").exists()
assert not (SRC / "Kfinal/assembly.yaml").exists()

for p in ["internal/engine/scenario_verdict.go", "internal/engine/run_stand.go",
          "internal/engine/run_directives.go", "cmd/judge/main.go"]:
    data = read(ENGINE / "engine" / p)
    archived = subprocess.check_output([
        "git", "-c", "safe.directory=" + str(ENGINE), "-C", str(ENGINE),
        "show", ENGINE_SHA + ":engine/" + p,
    ])
    assert data == archived, p
for p in ["PRE.md", "RESULT.md", "all163-diag.sh", "summary-official.json"]:
    read(K / p)
official_logs = sorted((K / "out/K150").glob("*/engine.log"))
assert len(official_logs) == 12
for path in official_logs:
    log = read(path).decode()
    assert "assembly.yaml: no such file or directory" in log
    assert not path.with_name("engine.json").exists()

result = {
    "engine": ENGINE_SHA, "pins": {k: v[0] for k, v in PINS.items()},
    "targets": summary, "own_red_total": len(rows),
    "class_counts": dict(collections.Counter(r[11] for r in rows)),
    "HTTP_observations_saved": False,
    "model_reads": reads, "journal_records": len(messages), "profile_writes": profile_writes,
    "K150_profile_exists": False, "K150_assembly_exists": False, "Kfinal_assembly_exists": False,
    "K150_official_no_report": len(official_logs),
    "source_comparison": source_comparison, "input_sha256": hashes,
}
(HERE / "evidence.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({k: result[k] for k in ["own_red_total", "class_counts", "journal_records"]}))
