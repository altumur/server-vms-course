"""Unchanged М10/1 scenarios against a separate Python daemon over its role socket."""
from __future__ import annotations

import argparse
import csv
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse

SOURCE = Path(__file__).resolve().parents[1]
FROZEN_ACCEPTANCE_REF = "a0bd9e53"  # старый Python заморожен, ADR-0080 доп. 16
SHARED = SOURCE / "tests/testdata/acceptance/М10_Platform/01/scenarios.tsv"
BODY_LIMIT = 1048576  # fixed acceptance door setting, М10/1 Н5
ROW_LIMIT = 524288
VARIABLE = re.compile(r"^\$([A-Za-z][A-Za-z0-9_]*)$")


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
    service = StoreDaemon(LocalBackend(), node_id="trial", sockets=str(directory), rights=rights,
                          body_limit=BODY_LIMIT)
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


def verify_limits(call):
    """Check the actual executor's fixed acceptance settings before any scenario runs (М10/1 Н5)."""
    code, body = call("POST", "/v1/write", b"!" * BODY_LIMIT)
    assert code == 400 and body.get("kind") == "badrequest", ("body at boundary", code, body)
    code, body = call("POST", "/v1/write", b"!" * (BODY_LIMIT + 1))
    assert code == 413 and body.get("kind") == "toolarge" and body.get("limit") == BODY_LIMIT, ("body", code, body)
    raw = json.dumps({"op": "put", "key": "acc/preflight/row", "items": {"blob": "x" * (ROW_LIMIT - 3)}}).encode()
    code, body = call("POST", "/v1/write", raw)
    assert code == 413 and body.get("limit") == ROW_LIMIT and body.get("size") == ROW_LIMIT + 1, ("row", code, body)
    return {"body": BODY_LIMIT, "row": ROW_LIMIT, "checked_before_scenarios": True}


def substitute(text, bindings):
    text = re.sub(r"@big\((\d+)\)", lambda m: "x" * int(m[1]), text)
    text = re.sub(r'"\$([A-Za-z][A-Za-z0-9_]*)"', lambda m: json.dumps(bindings[m[1]]), text)
    return re.sub(r"\$([A-Za-z][A-Za-z0-9_]*)", lambda m: str(bindings[m[1]]), text)


def compare(expected, actual, bindings, path="body"):
    """Closed JSON equality, optional error text, and mandatory string version bindings."""
    found = []
    if isinstance(expected, str):
        var = VARIABLE.fullmatch(expected)
        if var:
            name = var[1]
            if not isinstance(actual, str):
                found.append((path + ".string", "JSON string", actual))
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
    """N1 shape checks also cover responses not bound by a TSV variable."""
    bad = []
    if isinstance(body, dict) and "index" in body and not isinstance(body["index"], str):
        bad.append("N1.index.string")
    if isinstance(body, dict) and isinstance(body.get("keys"), dict):
        if any(not isinstance(value, str) for value in body["keys"].values()):
            bad.append("N1.list.index.string")
    return bad


def steps(call):
    records, bindings, previous = [], {}, None
    shared = subprocess.check_output(
        ["git", "show", f"{FROZEN_ACCEPTANCE_REF}:{SHARED.relative_to(SOURCE.parent).as_posix()}"],
        cwd=SOURCE, encoding="utf-8")
    for number, fields in enumerate(csv.reader(shared.splitlines(), delimiter="\t"), 1):
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
                status, body = call(method, target, raw)
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
    return records


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
                call = lambda method, target, raw: request(path, method, target, raw)
                save(output / "limits.json", verify_limits(call))
                records = steps(call)
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


class NativeAPI:
    """Translate notation and Fault envelopes, never CAS/guard/replay decisions.

    The native handle has a writer ACL; get uses that evaluator, list needs no read permission.
    No answer(), StoreMachine or HTTP door is involved in this executor.
    """
    def __init__(self, store, body_limit=BODY_LIMIT):
        self.store, self.body_limit = store, body_limit

    def request(self, method, target, raw):
        code, body = self._request(method, target, raw)
        if code >= 400:
            body.setdefault("error", body["kind"])
        return code, body

    def _request(self, method, target, raw):
        from w2cplatform.storemachine import BadRequest, check_key, parse_command, query_value, wire_command, wire_index
        from w2cplatform.variables import Conflict, GuardFailed, Forbidden, KeyTooLong
        from w2cplatform.limits import TooLarge
        from w2cplatform.configstorevars import StoreAmbiguous, StoreUnavailable
        from w2cplatform.rights import refusal
        path, _, query = target.partition("?")
        def version(value):
            return int(value) if value else 0
        try:
            if method == "GET" and path == "/v1/get":
                key = check_key(query_value(query, "key", required=True).decode("utf-8"))
                if refusal(self.store.writer, self.store.acl, key, "read"):
                    raise Forbidden("read refused")
                items, index = self.store.get(key)
                return 200, {"items": items, "index": wire_index(index)}
            if method == "GET" and path == "/v1/list":
                prefix = query_value(query, "prefix")
                try:
                    text_prefix = prefix.decode("utf-8")
                except UnicodeError:
                    text_prefix = ""
                keys = {}
                for key in self.store.list(text_prefix):
                    if not key.encode("utf-8").startswith(prefix):
                        continue
                    _, index = self.store.get(key)
                    if index != 0:                 # a row deleted after list may be omitted, never given an absent version
                        keys[key] = wire_index(index)
                return 200, {"keys": keys}
            if method != "POST" or path != "/v1/write":
                return 404, {"kind": "badrequest"}
            if len(raw) > self.body_limit:
                return 413, {"kind": "toolarge", "limit": self.body_limit}
            cmd = wire_command(parse_command(raw))
            guard = cmd.get("guard")
            # Native API versions are opaque native values. This is representation conversion only.
            if cmd.get("cas") is not None:
                cmd["cas"] = version(cmd["cas"])
            if guard is not None:
                cmd["guard"] = {"key": guard["key"], "index": version(guard["index"])}
            try:
                receipt = self.store.write(cmd)
            except KeyTooLong as error:
                return 400, {"kind": "badkey", "error": str(error)}
            except ValueError as error:
                return 400, {"kind": "badrequest", "error": str(error)}
            return 200, {"index": wire_index(receipt["index"]), **({"again": True} if receipt["again"] else {})}
        except GuardFailed as error:
            return 412, {"kind": "guard", "key": error.key, "index": wire_index(error.index)}
        except Conflict as error:
            return 409, {"kind": "conflict", "index": wire_index(error.index), "error": str(error)}
        except Forbidden:
            return 403, {"kind": "forbidden"}
        except StoreAmbiguous:
            return 503, {"kind": "ambiguous"}
        except StoreUnavailable:
            return 503, {"kind": "unavailable"}
        except TooLarge as error:
            return 413, {"kind": "toolarge", "key": error.key, "size": error.size, "limit": error.limit}
        except BadRequest as error:
            return 400, {"kind": "badrequest", "error": str(error)}
        except ValueError as error:
            return 400, {"kind": "badkey", "error": str(error)}


def native_scenarios(backend, output):
    from w2cplatform.variables import FileVariables
    from w2cplatform.memvariables import MemVariables
    called = {}
    def trace(frame, event, arg):
        if event == "call" and Path(frame.f_code.co_filename).name in ("variables.py", "memvariables.py"):
            key = Path(frame.f_code.co_filename).name + ":" + frame.f_code.co_qualname
            called[key] = called.get(key, 0) + 1
        return None
    with tempfile.TemporaryDirectory(prefix="m10-native-") as root:
        store = FileVariables(root, max_bytes=ROW_LIMIT, volatile=True) if backend == "file" else MemVariables(max_bytes=ROW_LIMIT)
        handle = store.as_writer("acceptance", ["acc/*"])
        old_trace = sys.gettrace()
        sys.settrace(trace)
        try:
            call = NativeAPI(handle).request
            save(output / "limits.json", verify_limits(call))
            records = steps(call)
        finally:
            sys.settrace(old_trace)
        save(output / "api-calls.json", called)
        save(output / "backend.json", {"backend": backend, "pid": os.getpid(), "door": False,
                                      "disk_files": sorted(str(p.relative_to(root)) for p in Path(root).rglob("*") if p.is_file())})
    save(output / "api.json", records)
    return records


def main():
    args = argparse.ArgumentParser()
    args.add_argument("output", nargs="?", type=Path)
    args.add_argument("--backend", choices=("http", "file", "mem"), default="http")
    args.add_argument("--daemon", action="store_true")
    args.add_argument("--source", type=Path, default=SOURCE)
    args.add_argument("--directory", type=Path)
    args.add_argument("--coverage", type=Path)
    a = args.parse_args()
    if a.daemon:
        daemon(a.source, a.directory, a.coverage)
        return 0
    if a.output is None:
        args.error("output directory required")
    a.output.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(a.source))
    records = scenarios(a.source, a.output) if a.backend == "http" else native_scenarios(a.backend, a.output)
    bad = [r for r in records if r["failures"] or r.get("shape") or r.get("blocked") or r.get("transport_error")]
    print(f"{len(records)-len(bad)}/{len(records)} shared steps passed; {len(bad)} failed")
    for row in bad:
        print(row["scenario"], row["step"], row["failures"], row.get("transport_error", ""))
    return int(bool(bad))


if __name__ == "__main__":
    sys.exit(main())
