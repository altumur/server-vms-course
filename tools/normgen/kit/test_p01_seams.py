"""P01 CALL adapter is YOURS; repeated kit builds preserve it and refresh closed files."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _assert_owned_seam(entry, text):
    """Ownership is a manifest fact; the CALL seam is an actual Go declaration."""
    import re
    if (entry.get("path") != "01-store/internal/coreadapter/seams.go"
            or entry.get("editable") is not True
            or not entry.get("source", "").endswith("/coreadapter/seams.go")):
        raise AssertionError("CALL seam manifest ownership")
    # A bounded declaration scan: literals and comments never provide syntax tokens.
    pattern = re.compile(r'\s+|//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|`[^`]*`|'
                         r"'(?:\\.|[^'\\])*'|[A-Za-z_][A-Za-z_0-9]*|[0-9]+|[^\w\s]", re.S)
    tokens, at, depth = [], 0, {"{": 0, "(": 0, "[": 0}
    while at < len(text):
        match = pattern.match(text, at)
        if match is None:
            raise AssertionError("CALL seam unreadable token")
        raw = match[0]
        if raw.isspace() or raw.startswith(("//", "/*")):
            at = match.end()
            continue
        if raw[0] in ('"', "'", "`"):
            if len(raw) < 2 or raw[-1] != raw[0]:
                raise AssertionError("CALL seam unterminated literal")
            kind = "literal"
        elif text.startswith("/*", at):
            raise AssertionError("CALL seam unterminated comment")
        else:
            kind = "identifier" if re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", raw) else "punctuation"
        tokens.append((kind, raw, tuple(depth.values())))
        if kind == "punctuation":
            if raw in depth:
                depth[raw] += 1
            elif raw in ("}", ")", "]"):
                depth[{"}": "{", ")": "(", "]": "["}[raw]] -= 1
            if any(level < 0 for level in depth.values()):
                raise AssertionError("CALL seam unbalanced declaration")
        at = match.end()
    if any(depth.values()):
        raise AssertionError("CALL seam unbalanced declaration")
    if (tokens[:2] != [("identifier", "package", (0, 0, 0)), ("identifier", "coreadapter", (0, 0, 0))]
            or sum(kind == "identifier" and raw == "package" and level == (0, 0, 0)
                   for kind, raw, level in tokens) != 1):
        raise AssertionError("CALL seam package ownership")
    declarations = [i for i, token in enumerate(tokens[:-1]) if token == ("identifier", "func", (0, 0, 0))
                    and tokens[i + 1][0] == "identifier"]
    signature = "func CallSeam ( c Core , cfg Config , name string , args json . RawMessage ) ( json . RawMessage , error ) {".split()
    expected = [("identifier" if re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", raw) else "punctuation", raw)
                for raw in signature]
    if len(declarations) != 1 or [(kind, raw) for kind, raw, level in tokens[declarations[0]:declarations[0] + len(expected)]] != expected:
        raise AssertionError("CALL seam signature/top-level ownership")


class CosmeticSeamControls(unittest.TestCase):
    """Synthetic manifest/declaration fixtures; no kit build or native process."""
    def fixture(self):
        return ({"path": "01-store/internal/coreadapter/seams.go", "editable": True,
                 "source": "p01-1/go/coreadapter/seams.go"},
                "package coreadapter\nfunc CallSeam(c Core, cfg Config, name string, "
                "args json.RawMessage) (json.RawMessage, error) { return nil, ErrNotImplemented }\n")

    def test_00_no_comment_owned_signature(self):
        _assert_owned_seam(*self.fixture())

    def test_real_seam_accepts_opaque_function_shaped_literals(self):
        entry, text = self.fixture()
        for literal in ('"func Other("', '`func Other() { package foreign }`', "'{'", "'\\''"):
            with self.subTest(literal=literal):
                _assert_owned_seam(entry, text + "const harmless = " + literal + "\n")

    def test_raw_string_function_decoy_is_not_a_seam(self):
        entry, text = self.fixture()
        decoy = "package coreadapter\nconst fake = `" + text.split("\n", 1)[1] + "`\n"
        with self.assertRaisesRegex(AssertionError, "signature/top-level"):
            _assert_owned_seam(entry, decoy)

    def test_local_function_and_package_declarations_do_not_supply_ownership(self):
        entry, text = self.fixture()
        for wrong in ("package coreadapter\nfunc outer() {\n" + text.split("\n", 1)[1] + "}\n",
                      "const fake = `package coreadapter`\n" + text.split("\n", 1)[1],
                      text.replace("package coreadapter", "package foreign")):
            with self.subTest(wrong=wrong), self.assertRaises(AssertionError):
                _assert_owned_seam(entry, wrong)

    def test_manifest_must_own_actual_seam(self):
        entry, text = self.fixture()
        for change in ({"editable": False}, {"path": "foreign/seams.go"}, {"source": "foreign.go"}):
            with self.subTest(change=change), self.assertRaisesRegex(AssertionError, "manifest ownership"):
                _assert_owned_seam(dict(entry, **change), text)

    def test_missing_or_comment_only_signature(self):
        entry, text = self.fixture()
        for wrong in (text.replace("CallSeam", "Other"), "// " + text.replace("\n", "\n// "),
                      text.replace("args json.RawMessage", "args []byte")):
            with self.subTest(text=wrong), self.assertRaises(AssertionError):
                _assert_owned_seam(entry, wrong)

    def test_wrong_framework_ownership(self):
        entry, text = self.fixture()
        for wrong in (text.replace("package coreadapter", "package stagetests"),
                      text + "func Handle() {}\n"):
            with self.subTest(text=wrong), self.assertRaises(AssertionError):
                _assert_owned_seam(entry, wrong)


class P01Seams(unittest.TestCase):
    def test_owned_adapter_survives_rebuild(self):
        with tempfile.TemporaryDirectory(prefix="kit-p01-seams-") as tmp:
            target = Path(tmp) / "kit"
            cmd = [sys.executable, str(HERE / "build_kit.py"), str(target),
                   "--part", "door", "--part", "flags", "--part", "stagetests"]
            env = dict(os.environ, NORMGEN_LESSON="01-store")
            first = subprocess.run(cmd, env=env, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            manifest = json.loads((target / "kit.manifest.json").read_bytes())
            rel = "01-store/internal/coreadapter/seams.go"
            entry = next(f for f in manifest["files"] if f["path"] == rel)
            self.assertIs(entry.get("editable"), True)
            self.assertTrue(entry["source"].endswith("/coreadapter/seams.go"))
            forms = {f["path"] for f in manifest["provenance"]["stagetests"]["form"]}
            self.assertIn("Platform/01-store/acceptance/3/seams.tsv", forms)
            owned = target / rel
            _assert_owned_seam(entry, owned.read_text())
            self.assertIn("ErrNotImplemented", owned.read_text())
            mine = owned.read_bytes() + b"\n// User implementation connects its ordinary native paths here.\n"
            owned.write_bytes(mine)
            closed = [target / "01-store/internal/coreadapter/coreadapter.go",
                      target / "01-store/internal/stagetests/engine_test.go"]
            expected = [p.read_bytes() for p in closed]
            for p in closed:
                p.write_bytes(p.read_bytes() + b"\n// stale closed file\n")
            second = subprocess.run(cmd, env=env, capture_output=True, text=True)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertEqual(owned.read_bytes(), mine)
            self.assertEqual([p.read_bytes() for p in closed], expected)


if __name__ == "__main__":
    unittest.main()
