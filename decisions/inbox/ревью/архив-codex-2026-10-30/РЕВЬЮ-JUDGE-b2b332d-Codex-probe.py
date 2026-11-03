"""Independent diagnostic-boundary controls; run only through CT103."""
import base64
import copy
import json
import re
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(sys.argv[1]) / "runner"))
import c_execute
import diagnostic_secrets as ds
import m11stand
import prepare


def serialized_reply(secret, encoded):
    registry = ds.Secrets()
    body = {"token": secret, "error": encoded}
    original = copy.deepcopy(body)
    errors = m11stand.check(503, body, {}, '503 {"error":"unavailable"}', {})
    safe = registry.clean({"why": errors, "got": body})
    assert body == original
    before = encoded in json.dumps(safe)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "report.json"
        prepare.write(path, safe)
        registry.written(path)
        registry.finalize([path])
        after = encoded in path.read_text()
    return {"encoded_value_exported": before, "encoded_value_survives_finalize": after}


def run():
    # Standard base64 without padding is still a reversible closed word.
    secret = "fixture-private-???a"
    standard = base64.b64encode(secret.encode()).decode().rstrip("=")
    assert "/" in standard and re.fullmatch(r"[A-Za-z0-9_.:~/-]{0,64}", standard)
    assert base64.b64decode(standard + "=" * (-len(standard) % 4)).decode() == secret
    standard_result = serialized_reply(secret, standard)

    # Hexadecimal digits have no prescribed letter case.
    secret = "fixture-private-credential"
    hexadecimal = "".join(c.upper() if i % 3 == 0 else c for i, c in enumerate(secret.encode().hex()))
    assert hexadecimal not in (secret.encode().hex(), secret.encode().hex().upper())
    assert bytes.fromhex(hexadecimal).decode() == secret
    hex_result = serialized_reply(secret, hexadecimal)

    registry = ds.Secrets()
    old = registry.clean({"got": {"name": "fixture-late-word"}})
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "report.json"
        prepare.write(path, old)
        registry.written(path)
        registry.remember("fixture-late-word")
        registry.finalize([path])
        assert "fixture-late-word" not in path.read_text()

    for prefix in ("transport:", "instance exited", "store did not open"):
        report = {"green": False, "scenarios": {"f": [{"why": [prefix + " fixture"]}]}}
        assert c_execute.classification(report, 1, False) == "stand"
        assert c_execute.classification(ds.Secrets().clean(report), 1, False) == "stand"

    # A wire response cannot acquire the runner's Projection provenance.
    forged = {"judge_projection": 1, "scope": "mismatch", "kind": "value",
              "field": "body.x", "path": "/x", "expected": "fixture hidden text",
              "received": {"judge_projection": 1, "scope": "value", "type": "null", "value": None}}
    safe = ds.Secrets().clean({"got": forged})
    assert safe["got"] != forged
    assert "fixture hidden text" not in json.dumps(safe)
    return {"standard_base64_unpadded": standard_result, "mixed_case_hex": hex_result,
            "late_refresh": True, "real_transport_preserved": True, "forged_projection_rejected": True}


if __name__ == "__main__":
    result = run()
    Path(sys.argv[2]).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    assert not any(result[k][v] for k in ("standard_base64_unpadded", "mixed_case_hex")
                   for v in result[k]), "known reversible credential reached runner-owned evidence"
