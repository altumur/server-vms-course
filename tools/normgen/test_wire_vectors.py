"""Independent probes of the wire.tsv native judge: full response, strict framing, comparisons and assertions.

Inputs and verdicts below are handwritten, not generated from the form's expected values. The judge runs in a separate Go module.
"""
import base64
import copy
import json
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from test_gen_vectors import gv

GOENV = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off", GOTOOLCHAIN="local")
MAIN = '''package main
import ("bufio"; "encoding/base64"; "encoding/json"; "fmt"; "os"; "judge/wirecheck")
func main() {
    s := bufio.NewScanner(os.Stdin); s.Buffer(make([]byte, 4096), 1<<20)
    for s.Scan() {
        var in struct { Code int; Out string; Spec string }
        if err := json.Unmarshal(s.Bytes(), &in); err != nil { panic(err) }
        b, err := base64.StdEncoding.DecodeString(in.Out); if err != nil { panic(err) }
        fmt.Println(wirecheck.Check(in.Code, b, in.Spec) == nil)
    }
    if err := s.Err(); err != nil { panic(err) }
}
'''


class Native(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="wire-native-judge-")
        cls.mod = Path(cls.tmp.name)
        g = gv()
        files, _ = g.build()
        (cls.mod / "wirecheck").mkdir()
        for rel, data in files.items():
            if rel.startswith("go/wirecheck/"):
                (cls.mod / rel[len("go/"):]).write_bytes(data)
        (cls.mod / "go.mod").write_text("module judge\n\ngo 1.22\n")
        (cls.mod / "main.go").write_text(MAIN)
        done = subprocess.run(["go", "build", "-o", str(cls.mod / "judge"), "."], cwd=cls.mod,
                              capture_output=True, text=True, env=GOENV)
        assert done.returncode == 0, done.stderr

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def judge(self, cases, *, value=None, compare="value", native=None, asserts=(), ignore=False, code=0):
        spec = {"code": code, "ignore": ignore, "value": value, "compare": compare,
                "native": native or {"type": "value", "frame": "json"}, "asserts": asserts}
        rows = []
        for output, _ in cases:
            b = output.encode() if isinstance(output, str) else output
            rows.append(json.dumps({"Code": code, "Out": base64.b64encode(b).decode(), "Spec": json.dumps(spec)}))
        done = subprocess.run([str(self.mod / "judge")], input="\n".join(rows)+"\n", capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.splitlines(), [str(valid).lower() for _, valid in cases], done.stderr)

    def test_full_actual_schema_with_partial_expected(self):
        self.judge([('{"layer1":"ok","extra":3}', True), ('{"layer1":"ok"}', False),
                    ('{"layer1":"ok","extra":"3"}', False),
                    ('{"layer1":"ok","extra":3,"foreign":0}', False)],
                   value={"layer1": "ok"}, compare="subset",
                   native={"type": "object", "frame": "json", "schema": {
                       "type": "object", "required": ["layer1", "extra"], "additionalProperties": False,
                       "properties": {"layer1": {"enum": ["ok", "refused"]}, "extra": {"type": "number"}}}})

    def test_strict_json(self):
        self.judge([(' {"x":1} \n', True), ('{"x":1,"x":1}', False), ('{"x":1} rubbish', False),
                    ('{"x":1}{}', False), ('\ufeff{"x":1}', False), ('{"x":NaN}', False),
                    (b'{"x":1,"bad":"\xff"}', False)], value={"x": 1}, compare="subset")

    def test_json_lf(self):
        self.judge([('{"x":1}\n', True), ('{\n "x":1\n}\n', True), (' {"x":1}\n', False),
                    ('{"x":1}', False), ('{"x":1}\n\n', False), ('{"x":1} \n', False)],
                   value={"x": 1}, native={"type": "object", "frame": "json-lf"})

    def test_nonzero_still_checks_stdout_and_ignored_stdout_is_explicit(self):
        self.judge([('"bad"', True), ('12', False), ('garbage', False)], value="bad", code=2,
                   native={"type": "string", "frame": "json"})
        self.judge([('garbage', True)], code=2, ignore=True)

    def test_raw_decoded_string_and_string_domain(self):
        self.judge([('"0012"', True), ('12', False)], value="0012", compare="raw",
                   native={"type": "string", "frame": "json"})
        spec = {"code": 0, "compare": "raw", "native": {"type": "bytes", "frame": "raw"},
                "raw": base64.b64encode(b'\xff\x00').decode()}
        data = json.dumps({"Code": 0, "Out": base64.b64encode(b'\xff\x00').decode(), "Spec": json.dumps(spec)})
        done = subprocess.run([str(self.mod / "judge")], input=data+"\n", capture_output=True, text=True)
        self.assertEqual((done.returncode, done.stdout), (0, "true\n"))

    def test_sets_and_boolean_number(self):
        self.judge([('[2,1,1]', True), ('[1,3]', False)], value=[1, 2], compare="set")
        self.judge([('{"x":[2,1,1]}', True), ('{"x":[1,2],"y":[]}', False)],
                   value={"x": [1, 2]}, compare="object-sets")
        self.judge([('1.0', True), ('true', False)], value=1)
        self.judge([('{}', True), ('{"x":1}', False)], value={}, compare="subset")

    def test_pointer_and_json_inside_a_field(self):
        cases = []
        for value, valid in ((json.dumps({"n": 1}), True), ('{"n":1,"n":1}', False), ({"n": 1}, False)):
            cases.append((json.dumps({"stable": True, "a/b": {"~x": value}}), valid))
        self.judge(cases, value={"stable": True}, compare="subset",
                   asserts=[{"pointer": "/a~1b/~0x", "decode": "json", "compare": "value", "value": {"n": 1}}])

    def test_absent_prefix_and_no_leak(self):
        self.judge([('{"stable":true,"row":"enc:v2:abc"}', True), ('{"stable":true,"row":"bad"}', False),
                    ('{"stable":true,"row":"enc:v2:abc","secret":null}', False)], value={"stable": True},
                   compare="subset", asserts=[{"pointer": "/secret", "test": "absent"},
                                              {"pointer": "/row", "test": "prefix", "value": "enc:v2:"}])
        for whole, valid in ((True, True), (False, False)):
            self.judge([('{"stable":true,"text":"abcd"}', valid),
                        ('{"stable":true,"text":"zzabcdzz"}', False)], value={"stable": True}, compare="subset",
                       asserts=[{"pointer": "/text", "test": "no-leak", "value": ["zzabcdzz"],
                                 "min_bytes": 4, "whole": whole}])


class FormSource(unittest.TestCase):
    def test_input_and_expectation_are_read_from_binding(self):
        import wire
        g = gv()
        bindings = copy.deepcopy(wire.parse(g.ROOT))
        b = next(b for b in bindings if b.key == ("common/loopback", "cases.tsv", "vectors"))
        b.inputs[0]["cells"]["input"] = {"literal": "a new form input"}
        b.expect[0]["value"] = {"literal": "a new form expectation"}
        with patch.object(wire, "parse", return_value=bindings):
            files, _ = g.build()
        frames = [json.loads(v) for p, v in files.items() if p.startswith("vectors/common/loopback/")
                  and p.endswith(".json")]
        self.assertTrue(frames)
        self.assertTrue(all(x["cells"] == {"input": "a new form input"} for x in frames))
        self.assertIn(b'a new form expectation', files["go/vectortests/loopback_cases_test.go"])

    def test_missing_binding_is_not_a_fallback(self):
        import wire
        g = gv()
        bindings = [b for b in wire.parse(g.ROOT) if b.key != ("common/loopback", "cases.tsv", "vectors")]
        with patch.object(wire, "parse", return_value=bindings):
            with self.assertRaisesRegex(g.GenError, "missing adapter binding"):
                g.build()

    def test_unknown_native_schema_keyword_is_refused(self):
        import wire
        g = gv()
        bindings = copy.deepcopy(wire.parse(g.ROOT))
        b = next(b for b in bindings if b.key == ("common/yaml-suite", "expect.tsv", "vectors"))
        b.native["schema"]["foreignKeyword"] = True
        with patch.object(wire, "parse", return_value=bindings):
            with self.assertRaisesRegex(g.GenError, "unsupported native schema"):
                g.build()


if __name__ == "__main__":
    unittest.main()
