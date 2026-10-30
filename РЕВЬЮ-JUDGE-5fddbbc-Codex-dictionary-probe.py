"""Independent public-dictionary origin and late-secret controls, CT103 only."""
import base64
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(sys.argv[1]) / "runner"))
import diagnostic_secrets as ds
import judge_diagnostics as jd
import prepare


def opaque(value):
    assert "value" not in value and "sha256" in value


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    chapter = root / "Platform/09-agent/acceptance/1"
    chapter.mkdir(parents=True)
    (chapter / "scenarios.tsv").write_text('scenario\tstep\trequest\texpect\nother\t1\tGET /x\t503 {"error":"public-tsv"}\n')
    other = root / "Platform/09-agent/acceptance/2"
    other.mkdir()
    (other / "scenarios.tsv").write_text('200 {"error":"outside-chapter"}\n')
    spec = root / "Platform/09-agent/spec"
    spec.mkdir()
    (spec / "09-agent.api.openapi.yaml").write_text('type: string\nenum: [public-enum]\nconst: public-const\ndescription: description-only\n')
    (spec / "notes.json").write_text('{"enum":["non-schema-file"]}')
    registry = ds.Secrets()
    jd.configure(registry, root, chapter)
    jd.allow_expectation(registry, '200 {"id":"$id","word":"public-step"}')
    for word in ("public-tsv", "public-enum", "public-const", "public-step", "id", "$id"):
        assert jd.scalar(word, registry)["value"] == word
        assert jd.name(word, registry) == word
    for word in ("outside-chapter", "description-only", "non-schema-file", "response-enum", "private-binding"):
        opaque(jd.scalar(word, registry))
        opaque(jd.name(word, registry))
    before = set(registry.public_words)
    raw = {"enum": ["response-enum"], "const": "response-const", "id": "private-binding"}
    registry.clean({"got": raw})
    assert registry.public_words == before

    secret = "fixture-private-???a"
    encoded = base64.b64encode(secret.encode()).decode().rstrip("=")
    hexadecimal = "".join(c.upper() if i % 3 == 0 else c for i, c in enumerate(b"fixture-private-credential".hex()))
    for word in (encoded, hexadecimal, "unpublished_closed_word"):
        assert word not in registry.public_words
        opaque(jd.scalar(word, registry))
        opaque(jd.name(word, registry))
        safe = registry.clean({"got": {word: word}})
        assert word not in json.dumps(safe)

    # The second layer must revoke even an admitted public key and value.
    late = "public-step"
    safe = registry.clean({"got": {late: late}})
    assert safe["got"]["keys"] == [late]
    assert safe["got"]["fields"][0]["received"]["value"] == late
    path = root / "report.json"
    prepare.write(path, safe)
    registry.written(path)
    registry.remember(late)
    registry.finalize([path])
    assert late not in path.read_text()

    # A changed on-disk snapshot cannot acquire trusted-writer provenance.
    forged = {"judge_projection": 1, "scope": "value", "type": "string", "value": "unpublished-forged"}
    prepare.write(path, {"got": forged})
    registry.finalize([path])
    assert "unpublished-forged" not in path.read_text()

import specs
real = ds.Secrets()
jd.configure(real, specs.root(), specs.acceptance("P/09.1"))
assert {"unavailable", "denied", "~unknown_issuer"} <= real.public_words
opaque(jd.scalar("fixture-unpublished-export-word", real))
print(json.dumps({"chapter_only": True, "schema_enum_const_only": True,
                  "received_cannot_extend_dictionary": True, "keys_follow_dictionary": True,
                  "unknown_encodings_opaque_before_secret_learn": True,
                  "late_public_secret_removed": True, "tampered_writer_rejected": True,
                  "pinned_export_dictionary": True}))
