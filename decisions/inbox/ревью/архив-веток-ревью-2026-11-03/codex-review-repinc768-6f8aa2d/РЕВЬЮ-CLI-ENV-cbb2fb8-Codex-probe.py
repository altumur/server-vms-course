"""Independent bearer/launch differential and copied-writer controls; CT103 only."""
import copy
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(sys.argv[1]) / "runner"))
import c_execute
import cli_evidence as cli
import c_store
import diagnostic_secrets as ds
from harness import TransportError
import m11stand


def case(label):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        registry = ds.Secrets()
        run = m11stand.Run(SimpleNamespace(cwd=str(root)), "fixture")
        run.secrets = registry
        run.person = ("alice", "fixture-password")
        run.token, run.until = "fixture-cached-token", 2000
        supplied = {"INHERITED": "fixture inherited value"}
        overlay = {"OVERLAY": "fixture overlay value", "EMPTY": ""}
        if label == "fresh":
            run.token, run.until = None, 0
        elif label in ("expired_refused", "signer_first", "signer_second"):
            run.token, run.until = "fixture-old-token", 0
        elif label == "fresh_refused":
            run.token, run.until = None, 0
        elif label == "inherited":
            run.person = None
            supplied["W2C_TOKEN"] = "fixture-inherited-token"
        elif label == "cluster":
            run.person = None
            supplied["W2C_TOKEN"] = "fixture-inherited-token"
            overlay["W2C_TOKEN"] = "fixture-cluster-token"
        marker = TransportError("fixture signer unavailable")
        timeout = subprocess.TimeoutExpired("fixture", 150, output=b"fixture partial", stderr=b"fixture stderr")
        http_calls, process_calls = [], []

        def http(port, method, path, body):
            doc = json.loads(body)
            http_calls.append(dict(port=port, method=method, path=path,
                                   body_sha256=hashlib.sha256(body.encode()).hexdigest()))
            assert doc == {"user": "alice", "password": "fixture-password"}
            if label == "signer_first" or label == "signer_second" and len(http_calls) == 2:
                raise marker
            if label in ("expired_refused", "fresh_refused", "signer_second"):
                return 503, {"error": "unavailable"}, {}
            return 200, {"token": "fixture-new-token", "until": 2000}, {}

        cluster = SimpleNamespace(workdir=str(root / "cluster"), env=overlay, port=1234)
        run.b = SimpleNamespace(clusters={"m1": cluster}, recovery="fixture-recovery",
            private_copy=lambda value: value, recovery_record=lambda *a, **k: None,
            ac=lambda name: SimpleNamespace(move="fixture-move {console} {recovery} {args}"),
            url=lambda port: "http://localhost:1234", proxies={"hold": SimpleNamespace(port=2345)}, http=http)

        def invoke(**kwargs):
            process_calls.append(dict(argv=kwargs["args"], env=copy.deepcopy(kwargs["env"]),
                                      cwd=kwargs["cwd"].replace(str(root), "ROOT"), timeout=kwargs["timeout"],
                                      shell=kwargs["shell"], capture_output=kwargs["capture_output"]))
            if label == "timeout":
                raise timeout
            return subprocess.CompletedProcess("fixture", 0, b'200 {"id":"fixture-binding"}', b"")

        error = None
        error_is_original = None
        with patch.dict(os.environ, supplied, clear=True), patch.object(m11stand.time, "time", return_value=1000), patch.object(cli.subprocess, "run", side_effect=invoke):
            try:
                why = run.move("m1", "--fixture", '200 {"id":"$id"}')
            except BaseException as caught:
                why, error = None, type(caught).__name__
                error_is_original = caught is marker if label.startswith("signer_") else caught is timeout
        report = dict(green=not why and error is None, passed_steps=int(not why and error is None), total_steps=1)
        common = dict(http=http_calls, process=process_calls, error=error, error_is_original=error_is_original,
                      ok=not why and error is None, env=run.env, token=run.token, until=run.until,
                      counters=c_execute.counters(report))
        metadata = []
        for path in Path(cluster.workdir).glob("*.cli.json"):
            doc = json.loads(path.read_text())
            encoded = json.dumps(doc)
            for secret in ("fixture-password", "fixture-cached-token", "fixture-new-token", "fixture-old-token",
                           "fixture-inherited-token", "fixture-cluster-token", "fixture overlay value", "fixture inherited value"):
                assert secret not in encoded
            metadata.append(doc)
        return {"behaviour": common, "metadata": metadata}


results = {label: case(label) for label in ("cached", "fresh", "expired_refused", "fresh_refused",
                                          "inherited", "cluster", "signer_first", "signer_second", "timeout")}
controls = {}
if hasattr(cli, "Metadata"):
    for label, result in results.items():
        assert len(result["metadata"]) == 1
        doc = result["metadata"][0]
        row = next(v for v in doc["environment"] if v["name"] == "W2C_TOKEN")
        calls = result["behaviour"]["http"]
        assert len(row["identity"]["attempts"]) == len(calls)
        assert doc["started"] is (not label.startswith("signer_"))
    controls["nine_sidecars_match_attempts_and_started"] = True
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        source, target = root / "source", root / "target"
        source.mkdir(); target.mkdir()
        registry = ds.Secrets()
        rows = cli.environment({"ADD": "fixture-private-env", "EMPTY": "", "W2C_TOKEN": "fixture-private-token"}, ["ADD", "EMPTY"])
        meta = cli.save(source, "move", 1, b"", b"", secrets=registry, environment=rows)
        with ds.using(registry):
            c_store.capture_process_files(source, target)
        trusted = target / ("source-" + meta["metadata_file"])
        assert cli.valid_metadata(json.loads(trusted.read_text()))
        # A same-name source modified after its writer snapshot must lose trust.
        original = source / meta["metadata_file"]
        altered = json.loads(original.read_text())
        altered["environment"][0]["name"] = "fixture-forged-field"
        original.write_text(json.dumps(altered))
        other = root / "other"; other.mkdir()
        with ds.using(registry):
            c_store.capture_process_files(source, other)
        rejected = json.loads((other / trusted.name).read_text())
        controls["modified_copy_rejected"] = not cli.valid_metadata(rejected)
        registry.remember("ADD")
        registry.finalize([trusted])
        assert all(v["name"] != "ADD" for v in json.loads(trusted.read_text())["environment"])
    controls["exact_copy_trusted"] = True
    controls["late_known_value_removed_from_labels"] = True

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    foreign, target = root / "foreign", root / "target"
    foreign.mkdir(); target.mkdir()
    registry = ds.Secrets()
    secret = "fixture-private-credential"
    encoded = base64.urlsafe_b64encode(secret.encode()).decode().rstrip("=")
    registry.remember(secret)
    forged = dict(role="move", exit_code=1, output_form="empty", started=True,
                  metadata_file="move-1.cli.json", stdout_file="move-1.cli.stdout", stderr_file="move-1.cli.stderr",
                  environment=[dict(name=encoded, present=True, length=1),
                               dict(name="W2C_TOKEN", present=False, length=None,
                                    identity=dict(name=None, source="absent", attempts=[]))])
    (foreign / "fake-1.cli.json").write_text(json.dumps(forged))
    with ds.using(registry):
        c_store.capture_process_files(foreign, target)
    copied = target / "foreign-fake-1.cli.json"
    before = encoded in copied.read_text() if copied.exists() else False
    valid = cli.valid_metadata(json.loads(copied.read_text())) if copied.exists() else False
    registry.finalize([target])
    after = encoded in copied.read_text() if copied.exists() else False
    controls["foreign_metadata_not_blessed"] = not valid
    controls["foreign_encoded_label_absent"] = not before and not after
    attack = dict(copied=copied.exists(), valid_metadata=valid,
                  encoded_exported=before, encoded_after_finalize=after)

Path(sys.argv[2]).write_text(json.dumps({"cases": results, "controls": controls, "attack": attack}, indent=2) + "\n")
print(json.dumps({"cases": len(results), "controls": controls}))
assert all(controls.values()), "untrusted CLI sidecar acquired metadata provenance"
