#!/usr/bin/env python3
"""Fixed ADR-0080/6 probe; artifacts only, never modifies the checked-out Source.

The shared TSV is sent over HTTP to StoreDaemon in another Python process.
FileVariables-only changes are deliberately NOT covered by a fabricated backend.
Existing unit modules run separately against each temporary Source copy.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SOURCE = ROOT / "Source"
SHARED = SOURCE / "tests/testdata/acceptance/М10_Platform/01/scenarios.tsv"
UNIT_MODULES = ["test_variables_contract", "test_storemachine", "test_guard"]
VARIABLE = re.compile(r"^\$([A-Za-z][A-Za-z0-9_]*)$")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def small(value):
    """Keep logs finite without changing any compared values."""
    if isinstance(value, str) and len(value) > 2000:
        return {"bytes": len(value.encode()), "sha256": hashlib.sha256(value.encode()).hexdigest()}
    if isinstance(value, dict):
        return {k: small(v) for k, v in value.items()}
    if isinstance(value, list):
        return [small(v) for v in value]
    return value


def daemon(source, directory, coverage_path):
    """No direct answer() call: the real daemon's real role socket is the API."""
    sys.path.insert(0, str(source))
    called = {}
    targets = {str(source / "w2cplatform" / name) for name in ("variables.py", "storemachine.py")}
    def trace(frame, event, arg):
        if event == "call" and frame.f_code.co_filename in targets:
            key = Path(frame.f_code.co_filename).name + ":" + frame.f_code.co_qualname
            called[key] = called.get(key, 0) + 1
        return None
    sys.settrace(trace)
    threading.settrace(trace)
    from w2cplatform.configstore import LocalBackend, StoreDaemon
    from w2cplatform.storemachine import Rights
    rights = Rights.parse({"roles": {"acceptance": {
        "read": ["acc/*"], "write": ["acc/*"], "delete": ["acc/*"]}}})
    stopped = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    service = StoreDaemon(LocalBackend(), node_id="trial", sockets=str(directory), rights=rights)
    try:
        print(json.dumps({"ready": True, "pid": os.getpid(), "socket": str(directory / "acceptance.sock")}), flush=True)
        stopped.wait()
    finally:
        service.stop()
        sys.settrace(None)
        threading.settrace(None)
        save(coverage_path, called)


class UnixHTTP(http.client.HTTPConnection):
    def __init__(self, path):
        super().__init__("localhost", timeout=10)
        self.path = str(path)

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.path)


def request(path, method, target, body):
    con = UnixHTTP(path)
    try:
        con.putrequest(method, target)
        con.putheader("Content-Type", "application/json")
        con.putheader("Content-Length", str(len(body)))
        con.endheaders()
        try:
            if body:
                con.send(body)
        except (BrokenPipeError, ConnectionResetError):
            # An oversized body is refused on headers. Read its HTTP 413 even
            # when the server closes while the client is still sending bytes.
            pass
        response = con.getresponse()
        return response.status, json.loads(response.read())
    finally:
        con.close()


def substitute(text, bindings):
    text = re.sub(r"@big\((\d+)\)", lambda m: "x" * int(m[1]), text)
    text = re.sub(r'"\$([A-Za-z][A-Za-z0-9_]*)"', lambda m: json.dumps(bindings[m[1]]), text)
    return re.sub(r"\$([A-Za-z][A-Za-z0-9_]*)", lambda m: str(bindings[m[1]]), text)


def compare(expected, actual, bindings, path="body"):
    """$var is universally typed, exactly as the shared README says.

    The body's named fields are compared; error is ignored unless named. Extra
    non-error fields are compared as part of JSON object equality too.
    """
    found = []
    if isinstance(expected, str):
        var = VARIABLE.fullmatch(expected)
        if var:
            name = var[1]
            if name not in bindings:
                bindings[name] = actual
            elif type(actual) is not type(bindings[name]) or actual != bindings[name]:
                found.append((path, expected, actual))
            return found
        if expected.startswith("!contains "):
            if not isinstance(actual, str) or expected[len("!contains "):] in actual:
                found.append((path, expected, actual))
            return found
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key, value in expected.items():
            if key not in actual:
                found.append((path + "." + key, value, {"missing": True}))
            else:
                found.extend(compare(value, actual[key], bindings, path + "." + key))
        for extra in actual.keys() - expected.keys() - {"error"}:
            found.append((path + "." + extra + ".extra", {"absent": True}, actual[extra]))
    elif type(expected) is not type(actual) or expected != actual:
        found.append((path, expected, actual))
    return found


def shape(body):
    """Separate N1 observations; these are NOT literal TSV matcher failures."""
    bad = []
    if isinstance(body, dict) and "index" in body and not isinstance(body["index"], str):
        bad.append("N1.index.string")
    if isinstance(body, dict) and isinstance(body.get("keys"), dict):
        if any(not isinstance(value, str) for value in body["keys"].values()):
            bad.append("N1.list.index.string")
    return bad


def scenarios(source, output):
    records, bindings, previous = [], {}, None
    with tempfile.TemporaryDirectory(prefix="m10-api-", dir="/tmp") as directory:
        directory = Path(directory)
        with (output / "daemon.log").open("w") as err:
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--daemon",
                                        "--source", str(source), "--directory", str(directory),
                                        "--coverage", str(output / "api-calls.json")],
                                       stdout=subprocess.PIPE, stderr=err, text=True)
            try:
                path = directory / "acceptance.sock"
                for _ in range(100):
                    if path.exists():
                        break
                    if process.poll() is not None:
                        raise RuntimeError("daemon did not start; see daemon.log")
                    time.sleep(0.03)
                else:
                    raise TimeoutError("daemon socket was not created")
                # Confirm real readiness before the first request.
                ready = json.loads(process.stdout.readline())
                assert ready["ready"] and ready["pid"] != os.getpid()
                save(output / "daemon.json", ready)
                for number, fields in enumerate(csv.reader(SHARED.read_text().splitlines(), delimiter="\t"), 1):
                    if not fields or fields[0].startswith("#"):
                        continue
                    scenario, step, operation, expected = fields
                    if scenario != previous:
                        bindings, previous = {}, scenario
                    record = {"scenario": scenario, "step": step, "line": number,
                              "operation": operation, "failures": [], "shape": []}
                    try:
                        if operation.startswith("ASSERT "):
                            names = re.findall(r"\$([A-Za-z][A-Za-z0-9_]*)", operation)
                            values = [bindings[n] for n in names]
                            if any(a == b for i, a in enumerate(values) for b in values[i+1:]):
                                record["failures"].append({"facet": "assert.distinct", "values": values})
                        else:
                            expanded = substitute(operation, bindings)
                            method, target, *rest = expanded.split(" ", 2)
                            raw = rest[0].encode() if rest else b""
                            status, body = request(path, method, target, raw)
                            wanted_status, wanted_body = expected.split(" ", 1)
                            record.update(status=status, body=small(body))
                            if status != int(wanted_status):
                                record["failures"].append({"facet": "status", "expected": int(wanted_status), "actual": status})
                            for facet, want, got in compare(json.loads(wanted_body), body, bindings):
                                record["failures"].append({"facet": facet, "expected": small(want), "actual": small(got)})
                            record["shape"] = shape(body)
                    except KeyError as error:
                        record["blocked"] = "unbound variable " + str(error)
                    except Exception as error:
                        record["transport_error"] = type(error).__name__ + ": " + str(error)
                    records.append(record)
            finally:
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()  # only the child this runner created
                    process.wait(timeout=5)
                save(output / "daemon-exit.json", {"pid": process.pid, "exit": process.returncode})
    save(output / "api.json", records)
    return records


def unit(source, output):
    env = dict(os.environ, PYTHONUNBUFFERED="1", OBSD_BIN="/Users/murat/w2c/vms-nightly/exe/obsd")
    env.pop("CONTRACT_URL", None)
    env.pop("W2C_PRODUCT_REF", None)
    with (output / "unit.log").open("w") as log:
        result = subprocess.run([sys.executable, "tests/run.py", *UNIT_MODULES], cwd=source,
                                env=env, stdout=log, stderr=subprocess.STDOUT, timeout=180)
    (output / "unit.exit").write_text(str(result.returncode) + "\n")
    text = (output / "unit.log").read_text()
    totals = re.findall(r"(\d+) passed, (\d+) failed, (\d+) skipped", text)
    return {"exit": result.returncode, "totals": [int(v) for v in totals[-1]] if totals else None,
            "failures": re.findall(r"^(test_\S+.*) \.\.\. FAIL.*$", text, re.MULTILINE),
            "import_failure": "FAIL (does not import)" in text}


def deletion_witness(source, output):
    """Diagnostic only: NOT an existing unit and NOT counted in kill ratios."""
    code = '''import json, tempfile
from w2cplatform.variables import FileVariables, Conflict
with tempfile.TemporaryDirectory() as root:
    v = FileVariables(root, volatile=True)
    first = v.put("acc/witness/c1", {"n":"1"}, cas=0)
    v.delete("acc/witness/c1", cas=first)
    second = v.put("acc/witness/c1", {"n":"2"}, cas=0)
    stale_accepted = False
    try:
        v.put("acc/witness/c1", {"n":"late"}, cas=first)
        stale_accepted = True
    except Conflict:
        pass
    print(json.dumps({"first":first,"recreated":second,"reused":first==second,
                      "stale_cas_accepted":stale_accepted,"row":v.get("acc/witness/c1")[0]}))
'''
    result = subprocess.run([sys.executable, "-c", code], cwd=source, capture_output=True, text=True, check=True)
    save(output / "non-scoring-delete-witness.json", json.loads(result.stdout))


# Exactly 12 preselected semantic faults; every replacement must match once.
MUTANTS = [
    ("S01-cas", "storemachine.py", "elif cas is not None and cas != current:", "elif False:", "stale CAS accepted"),
    ("S02-guard", "storemachine.py", 'if guard is not None and guard["index"] != guarded:', 'if False:', "lost slot guard ignored"),
    ("S03-replay", "storemachine.py", "if op_id and op_id in self.done:", "if False:", "operation replay is submitted again"),
    ("S04-id-content", "storemachine.py", "if was != fingerprint:", "if False:", "operation id accepts different content"),
    ("S05-delete-version", "storemachine.py", 'self.rows.pop(key, None)\n            self.wrote = True\n            res = {"index": self.version(index)}',
     'self.rows.pop(key, None)\n            self.wrote = True\n            res = {"index": current}', "delete returns the old version"),
    ("S06-read-copy", "storemachine.py", 'return {"items": dict(e[0]), "index": e[1]} if e else',
     'return {"items": e[0], "index": e[1]} if e else', "read shares the machine's mutable row"),
    ("S07-limit", "storemachine.py", "MAX_VALUE = 512 << 10", "MAX_VALUE = 256 << 10", "ceiling silently halved"),
    ("S08-acl", "storemachine.py", 'return allowed(self.roles.get(role, {}).get(action, []), key)',
     'return True', "role ACL is bypassed"),
    ("V09-file-cas", "variables.py", 'current = self._current(path)\n            if cas is not None and cas != current:\n                raise Conflict(f"{path}: cas={cas} but ModifyIndex={current}")\n            idx = self._next_index()',
     'current = self._current(path)\n            if False:\n                raise Conflict(f"{path}: cas={cas} but ModifyIndex={current}")\n            idx = self._next_index()', "FileVariables.put ignores CAS"),
    ("V10-guard", "variables.py", 'if guard["index"] != index:', 'if False:', "in-process guard ignores lost ownership"),
    ("V11-key", "variables.py", 'if not path or path.startswith("/") or ".." in path.split("/"):',
     'if not path or path.startswith("/"):', "traversal segments accepted as keys"),
    ("V12-file-delete-version", "variables.py", 'self._next_index()\n            self._durable_dirs()                    # the removal',
     'open(self.index_file, "w").write("1000")\n            self._durable_dirs()                    # the removal', "file deletion resets the version counter"),
]

TARGET_CALLS = {
    **{identity: "storemachine.py:StoreMachine._write" for identity in
       ("S01-cas", "S02-guard", "S03-replay", "S04-id-content", "S05-delete-version")},
    "S06-read-copy": "storemachine.py:StoreMachine.apply",
    "S07-limit": "storemachine.py:<module>",
    "S08-acl": "storemachine.py:Rights.allows",
    "V09-file-cas": "variables.py:FileVariables.put",
    "V10-guard": "variables.py:guard_match",
    "V11-key": "variables.py:safe_path",
    "V12-file-delete-version": "variables.py:FileVariables.delete",
}


def facets(records):
    return {(r["scenario"], r["step"], f["facet"]) for r in records for f in r["failures"]}


def all_runs():
    manifest = {"base": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "python": sys.version, "scenario_sha256": digest(SHARED), "unit_modules": UNIT_MODULES,
                "targets": {n: digest(SOURCE / "w2cplatform" / n) for n in ("variables.py", "storemachine.py")}}
    save(HERE / "inputs.json", manifest)
    results, baseline_facets = [], None
    for mutation in [None, *MUTANTS]:
        identity = mutation[0] if mutation else "baseline"
        output = HERE / identity
        output.mkdir(exist_ok=True)
        print(identity + " start", flush=True)
        with tempfile.TemporaryDirectory(prefix="m10-mut-", dir="/tmp") as root:
            source = Path(root) / "Source"
            shutil.copytree(SOURCE, source, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "node_modules", ".DS_Store"))
            changed = None
            if mutation:
                _, filename, before, after, description = mutation
                changed = source / "w2cplatform" / filename
                text = changed.read_text()
                if text.count(before) != 1:
                    raise AssertionError((identity, "replacement count", text.count(before)))
                changed.write_text(text.replace(before, after, 1))
                ast.parse(changed.read_text())
                import difflib
                diff = "".join(difflib.unified_diff(text.splitlines(True), changed.read_text().splitlines(True),
                                                  fromfile="a/Source/w2cplatform/" + filename,
                                                  tofile="b/Source/w2cplatform/" + filename))
                (output / "mutation.patch").write_text(diff)
            try:
                records = scenarios(source, output)
                units = unit(source, output)
                valid = not units["import_failure"] and not any(r.get("transport_error") for r in records)
                api_bad = facets(records)
                if mutation is None:
                    baseline_facets = api_bad
                    if units["exit"]:
                        raise AssertionError("baseline unit is not green; inspect baseline/unit.log")
                new = sorted(api_bad - (baseline_facets or set()))
                calls = json.loads((output / "api-calls.json").read_text())
                target = TARGET_CALLS.get(identity)
                reached = bool(calls.get(target, 0)) if target else None
                result = {"id": identity, "valid": valid,
                          "target": mutation[1] if mutation else None,
                          "description": mutation[4] if mutation else "unmodified course",
                          "api_scenarios": len({r["scenario"] for r in records}), "api_steps": len(records),
                          "api_failed_steps": sum(bool(r["failures"]) for r in records),
                          "api_failed_scenarios": sorted({r["scenario"] for r in records if r["failures"]}),
                          "api_new_facets": new,
                          "api_killed": bool(new) if mutation else None,
                          "api_target_function": target, "api_function_calls": calls.get(target, 0),
                          "api_target_reached": reached,
                          "api_coverage": "reached; confirmed by api-calls.json" if reached else
                              "not reached by LocalBackend; confirmed by api-calls.json",
                          "unit": units,
                          "unit_killed": bool(units["exit"]) if mutation else None}
                results.append(result)
                save(output / "result.json", result)
                save(HERE / "results.json", results)
                if identity in ("baseline", "V12-file-delete-version"):
                    deletion_witness(source, output)
                print(identity + " " + json.dumps({k: result[k] for k in ("valid", "api_failed_steps", "api_killed", "unit_killed")}), flush=True)
            except Exception as error:
                save(output / "invalid.json", {"error": type(error).__name__ + ": " + str(error)})
                raise
    assert manifest["targets"] == {n: digest(SOURCE / "w2cplatform" / n) for n in manifest["targets"]}
    subprocess.run([sys.executable, str(HERE / "summarize.py")], check=True)
    print("complete: checked-out target sources unchanged", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--daemon", action="store_true")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--coverage", type=Path)
    args = parser.parse_args()
    if args.daemon:
        daemon(args.source, args.directory, args.coverage)
    else:
        all_runs()
