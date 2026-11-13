"""Compile response-header cases against source OpenAPI and explicit scalar boundary expectations."""
import copy
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import gen_door

HERE = Path(__file__).resolve().parent
GOENV = dict(os.environ, GOPROXY="off", GOFLAGS="-mod=mod", GOWORK="off", GOTOOLCHAIN="local")


class Headers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.source = gen_door.load(gen_door.DEFAULT_SPEC)

    def compiled(self, doc, tests):
        with tempfile.TemporaryDirectory(prefix="normgen-header-") as tmp:
            out = Path(tmp) / "p01-1"
            gen_door.emit(doc, "headers.openapi.yaml", "0" * 64, out)
            (out / "go/apidoor/headers_test.go").write_text(
                'package apidoor\nimport ("encoding/json"; "testing")\n' + tests, encoding="utf-8")
            done = subprocess.run(["go", "test", "./apidoor"], cwd=out / "go", env=GOENV,
                                  capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_actual_write_delay_and_constant_operations(self):
        self.compiled(self.source, r'''
func TestActualDelay(t *testing.T) {
    for _, n := range []int64{-1, 0, 1, 17, 9223372036854775807, -9223372036854775808} {
        a,e:=Refuse(OpWrite,503,"unavailable","busy",nil); if e!=nil {t.Fatal(e)}
        a.RetryAfter=&n
        got,e:=Encode(OpWrite,a); if e!=nil {t.Fatal(n,e)}
        b,_:=json.Marshal(n)
        if got.Header[len(got.Header)-1] != [2]string{"Retry-After",string(b)} {t.Fatal(n,got.Header)}
        a.RetryAfter=nil
        got,e=Encode(OpWrite,a);if e!=nil||len(got.Header)!=1 {t.Fatal(got,e)}
        a,e=Refuse(OpStatus,503,"unavailable","busy",nil);if e!=nil {t.Fatal(e)}
        a.RetryAfter=&n
        got,e=Encode(OpStatus,a)
        if (e==nil)!=(n==1) {t.Fatal("constant operation",n,got,e)}
    }
    one:=int64(1)
    if _,e:=Encode(OpStatus,Answer{Code:299,RetryAfter:&one});e==nil {t.Fatal("undeclared status")}
    if _,e:=Encode(OpCopyHead,Answer{Code:400,RetryAfter:&one});e==nil {t.Fatal("undeclared header on bodyless response")}
}
''')

    def test_refs_required_enum_bounds_and_string_headers(self):
        doc = copy.deepcopy(self.source)
        doc["components"]["schemas"]["Delay"] = {"type": "integer", "minimum": 0, "maximum": 31}
        header = doc["components"]["responses"]["UnavailableOrAmbiguous"]["headers"]["Retry-After"]
        header.update(required=True, schema={"$ref": "#/components/schemas/Delay", "minimum": 1,
                                             "maximum": 30, "enum": [1, 4, 30]})
        # A dynamic string and a constant string use the same operation-specific checker path.
        doc["paths"]["/v1/status"]["get"]["responses"]["503"]["headers"]["X-Token"] = {
            "schema": {"type": "string", "const": "yes"}}
        doc["components"]["responses"]["UnavailableOrAmbiguous"]["headers"]["X-Token"] = {
            "schema": {"type": "string", "pattern": "^yes$"}}
        self.compiled(doc, r'''
func TestConstrainedDelay(t *testing.T) {
    _=json.Number("0")
    a,e:=Refuse(OpWrite,503,"unavailable","busy",nil);if e!=nil {t.Fatal(e)}
    if _,e=Encode(OpWrite,a);e==nil {t.Fatal("required absent")}
    for _,n:=range []int64{-1,0,1,2,4,30,31,32} {
        a.RetryAfter=&n;got,e:=Encode(OpWrite,a)
        if (e==nil)!=(n==1||n==4||n==30) {t.Fatal(n,got,e)}
    }
    n:=int64(4);a.RetryAfter=&n
    for _,v:=range []string{"yes","no","yes\r\nX: bad"} {
        a.XToken=&v;_,e=Encode(OpWrite,a);if (e==nil)!=(v=="yes") {t.Fatal(v,e)}
        b,e:=Refuse(OpStatus,503,"unavailable","busy",nil);if e!=nil {t.Fatal(e)}
        b.XToken=&v;_,e=Encode(OpStatus,b);if (e==nil)!=(v=="yes") {t.Fatal("constant string",v,e)}
    }
    check:=responses[OpWrite][503].headerChecks["Retry-After"]
    for _,v:=range []any{true,"4",float64(4),json.Number("4.0"),json.Number("4e0"),nil} {
        if check(v,"")==nil {t.Fatalf("wrong scalar accepted: %#v",v)}
    }
}
''')

    def test_uint64_header_uses_existing_scalar_range(self):
        doc = copy.deepcopy(self.source)
        doc["components"]["responses"]["UnavailableOrAmbiguous"]["headers"]["X-Wide"] = {
            "schema": {"type": "integer", "minimum": 0, "maximum": 18446744073709551615}}
        self.compiled(doc, r'''
func TestWide(t *testing.T) {
    _=json.Number("0")
    for _,n:=range []uint64{0,9223372036854775808,18446744073709551615} {
        a,e:=Refuse(OpWrite,503,"unavailable","busy",nil);if e!=nil {t.Fatal(e)}
        a.XWide=&n;got,e:=Encode(OpWrite,a);if e!=nil {t.Fatal(e)}
        b,_:=json.Marshal(n);if got.Header[len(got.Header)-1]!=[2]string{"X-Wide",string(b)} {t.Fatal(got.Header)}
    }
}
''')

    def test_all_constant_headers_keep_bool_api(self):
        doc = copy.deepcopy(self.source)
        doc["components"]["responses"]["UnavailableOrAmbiguous"]["headers"]["Retry-After"]["schema"]["const"] = 1
        self.compiled(doc, r'''
func TestConstant(t *testing.T) {
    _=json.Number("0")
    var _ bool = Answer{}.RetryAfter
    a,e:=Refuse(OpWrite,503,"unavailable","busy",nil);if e!=nil {t.Fatal(e)}
    got,e:=Encode(OpWrite,a);if e!=nil||len(got.Header)!=1 {t.Fatal(got,e)}
    a.RetryAfter=true;got,e=Encode(OpWrite,a)
    if e!=nil||got.Header[len(got.Header)-1]!=[2]string{"Retry-After","1"} {t.Fatal(got,e)}
}
''')

    def test_unsupported_scalar_and_mixed_types_refuse(self):
        for schema in ({"type": "object"}, {"type": "array", "items": {"type": "integer"}},
                       {"type": "boolean"}, {"type": "number"}, {"type": ["integer", "null"]},
                       {"type": "integer", "format": "int64"}):
            doc = copy.deepcopy(self.source)
            doc["components"]["responses"]["UnavailableOrAmbiguous"]["headers"]["Retry-After"]["schema"] = schema
            with self.subTest(schema=schema), self.assertRaises(gen_door.GenError):
                gen_door.build_go(gen_door.Spec(doc), "test", "0" * 64)
        doc = copy.deepcopy(self.source)
        doc["components"]["responses"]["UnavailableOrAmbiguous"]["headers"]["Retry-After"]["schema"] = {"type": "string"}
        with self.assertRaisesRegex(gen_door.GenError, "incompatible scalar types"):
            gen_door.build_go(gen_door.Spec(doc), "test", "0" * 64)


if __name__ == "__main__":
    unittest.main()
