"""Independent pre-parse SHA gate and closed environment-name controls, CT103 only."""
import base64
import copy
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(sys.argv[1]) / "runner"))
import c_store
import cli_evidence as cli
import diagnostic_secrets as ds

rejected = {"sidecar_rejected": "sidecar rejected: sha mismatch"}
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    registry = ds.Secrets()
    dictionary = cli.ENVIRONMENT_NAMES
    secret = "fixture-private-credential"
    encoded = base64.urlsafe_b64encode(secret.encode()).decode().rstrip("=")
    added = ["CLUSTER", "W2C_WALL_OFFSET", "W2C_TLS_DIR", encoded, "PRIVATE_CUSTOM"]
    rows = cli.environment({"CLUSTER": "fixture private value", "W2C_WALL_OFFSET": "", encoded: "hidden"}, added)
    assert rows.unlisted == 2
    keyed = {row["name"]: row for row in rows}
    assert set(keyed) == {"CLUSTER", "W2C_WALL_OFFSET", "W2C_TLS_DIR", "W2C_TOKEN"}
    assert keyed["W2C_WALL_OFFSET"]["present"] and keyed["W2C_WALL_OFFSET"]["length"] == 0
    assert not keyed["W2C_TLS_DIR"]["present"] and keyed["W2C_TLS_DIR"]["length"] is None
    assert encoded not in json.dumps(rows) and "PRIVATE_CUSTOM" not in json.dumps(rows)
    assert cli.ENVIRONMENT_NAMES == dictionary
    genuine = root / "genuine"
    meta = cli.save(genuine, "move", 1, b"", b"", secrets=registry, environment=rows)
    path = genuine / meta["metadata_file"]
    assert json.loads(path.read_text())["unlisted"] == 2
    registry.remember("CLUSTER")
    for _ in range(2):
        registry.finalize([path])
        doc = json.loads(path.read_text())
        assert cli.valid_metadata(doc) and doc["unlisted"] == 3
        assert "CLUSTER" not in {row["name"] for row in doc["environment"]}

    # Each input is syntactically valid CLI metadata with only fixed names.
    # No JSON parser, credential learner or boundary-B handler may inspect it on SHA mismatch.
    for modified in (False, True):
        source = root / ("modified" if modified else "foreign")
        target = root / ("modified-copy" if modified else "foreign-copy")
        source.mkdir(); target.mkdir()
        meta = cli.save(source, "move", 1, b"", b"", secrets=registry,
                        environment=cli.environment({}, []))
        path = source / meta["metadata_file"]
        payload = json.loads(path.read_text())
        payload["exit_code"] = 2
        assert cli.valid_metadata(payload)
        path.write_text(json.dumps(payload))
        if not modified:
            registry.own_files.pop(path.resolve())
        copied = target / (source.name + "-" + path.name)
        registry.register_log(path)
        registry.register_log(copied)
        # Ignore genuine B streams here; test the sidecar gate directly, then the copier separately.
        with patch.object(ds.json, "loads", side_effect=AssertionError("foreign sidecar parsed")), \
             patch.object(registry, "learn", side_effect=AssertionError("foreign sidecar learned")), \
             patch.object(registry, "log", side_effect=AssertionError("sidecar sent to B")):
            registry.file(path)
            for _ in range(2):
                registry.finalize([path])
        assert json.loads(path.read_text()) == rejected
        assert path.resolve() not in registry.own_files
        with ds.using(registry):
            c_store.capture_process_files(source, target)
        for _ in range(2):
            registry.finalize([copied])
        assert json.loads(copied.read_text()) == rejected
        assert copied.resolve() not in registry.own_files

    # An untrusted malformed file is rejected by the same gate without decoding.
    binary = root / "binary-1.cli.json"
    binary.write_bytes(b"\xff\x00fixture native bytes")
    with patch.object(ds.json, "loads", side_effect=AssertionError("malformed sidecar parsed")):
        registry.finalize([binary])
    assert json.loads(binary.read_text()) == rejected
    assert binary.resolve() not in registry.own_files

print(json.dumps({"fixed_names_only": True, "unknown_names_count_only": True,
                  "empty_and_absent_distinct": True, "unlisted_stable_after_late_redaction": True,
                  "valid_foreign_and_modified_rejected_before_parse_learn_log": True,
                  "repeated_finalize_never_promotes": True, "copied_rejection_stays_untrusted": True,
                  "malformed_sidecar_not_decoded": True}))
