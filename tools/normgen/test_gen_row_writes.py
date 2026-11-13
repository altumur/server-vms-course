"""GEN01: form errors, a compiled pure constructor, V7 oracle and runtime mutants."""
import lesson as output_lesson
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "skills/lesson-spec/scripts"))
import check_forms
from v7 import stack
import gen_families as families
import gen_row_writes as gen
from gen_checks import GenError, go_str

ENV = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off", GOTOOLCHAIN="local")
START = {"sub": "testsub", "unit": "u1", "born": "a" * 32, "revision": 3, "epoch": 8,
         "epoch_index": "9007199254740993"}
SPEC = {"result": {"$ref": "#/$defs/outcome"}}
DEFS = {"outcome": {"type": "object", "required": ["state"], "properties": {"state": {"type": "string"}},
                    "additionalProperties": False}}
INPUT = {"name": "result", "value": {"state": "open"},
         "reread_row": {"born": "b" * 32, "revision": 4}, "current_epoch": 9,
         "current_index": "9223372036854775809"}

HARNESS = r'''package main
import (
 "bufio"; "encoding/json"; "fmt"; "os"
 "rowwritesjudge/families"
)
type request struct {
 Start json.RawMessage
 Schemas, Defs map[string]json.RawMessage
 Input json.RawMessage
 Alias, Repeat, Zero bool
}
func run(raw []byte) (result any) {
 defer func(){ if v:=recover();v!=nil { result=map[string]any{"panic":fmt.Sprint(v)} } }()
 var r request
 if err:=json.Unmarshal(raw,&r);err!=nil { return map[string]any{"harness_error":err.Error()} }
 var snap families.StartSnapshot
 var err error
 if !r.Zero { snap,err=families.CaptureStateStart(r.Start,families.StateSpec{Schemas:r.Schemas,Defs:r.Defs}) }
 if err!=nil { return map[string]any{"error":err.Error(),"phase":"capture"} }
 if r.Alias {
  for i:=range r.Start {r.Start[i]='x'}
  for _,data:=range r.Schemas {for i:=range data {data[i]='x'}}
  for _,data:=range r.Defs {for i:=range data {data[i]='x'}}
  r.Schemas["result"]=json.RawMessage(`{"type":"number"}`)
  r.Defs["outcome"]=json.RawMessage(`{"type":"number"}`)
 }
 out,err:=families.BuildState(snap,r.Input)
 if err!=nil {return map[string]any{"error":err.Error(),"phase":"build"}}
 if r.Repeat {
  out.Items["born"]="changed";if out.Guard!=nil{out.Guard.Index="changed"}
  out,err=families.BuildState(snap,r.Input)
  if err!=nil{return map[string]any{"error":err.Error(),"phase":"repeat"}}
 }
 return out
}
func main(){
 s:=bufio.NewScanner(os.Stdin);s.Buffer(make([]byte,4096),1<<22)
 e:=json.NewEncoder(os.Stdout)
 for s.Scan(){if err:=e.Encode(run(s.Bytes()));err!=nil{panic(err)}}
 if err:=s.Err();err!=nil{panic(err)}
}
'''

BOUNDARY = r'''package families
import ("encoding/json";"reflect";"sync";"testing")
func TestRowWriteJSONBoundary(t *testing.T){
 start:=json.RawMessage(`{"sub":"testsub","unit":"u1","born":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","revision":3,"epoch":8,"epoch_index":"9007199254740993"}`)
 spec:=StateSpec{Schemas:map[string]json.RawMessage{"result":json.RawMessage(`{}`)}}
 snap,err:=CaptureStateStart(start,spec);if err!=nil{t.Fatal(err)}
 bad:=[][]byte{
  []byte(`{"name":"result","value":1} garbage`),
  []byte(`{"name":"result","name":"result","value":1}`),
  []byte(`{"name":"result","value":"\ud800"}`),
  []byte(`{"name":"result","value":"\udc00"}`),
  []byte(`{"name":"result","value":"\ud800\u0041"}`),
  []byte(`{"name":"result","value":NaN}`),
  []byte(`{"name":"result","value":1e400}`),
  append([]byte{0xef,0xbb,0xbf},[]byte(`{"name":"result","value":1}`)...),
  append(append([]byte(`{"name":"result","value":"`),0xff),[]byte(`"}`)...),
 }
 for _,raw:=range bad{
  got,err:=BuildState(snap,raw)
  if err==nil||!reflect.DeepEqual(got,RowWrite{}){t.Fatalf("invalid API JSON produced a partial write: %q %#v %v",raw,got,err)}
 }
 for _,raw:=range []string{`{"name":"result","value":"\ud83d\ude00"}`,`{"name":"result","value":"\\ud800"}`} {
  if _,err:=BuildState(snap,json.RawMessage(raw));err!=nil{t.Fatalf("valid surrogate/literal: %v",err)}
 }
 for _,raw:=range [][]byte{append(append([]byte(nil),start...),[]byte(` garbage`)...),[]byte(`{"sub":"x","sub":"x"}`)} {
  if _,err:=CaptureStateStart(raw,spec);err==nil{t.Fatal("invalid snapshot JSON accepted")}
 }
 invalidKey:=StateSpec{Schemas:spec.Schemas,Defs:map[string]json.RawMessage{string([]byte{0xff}):json.RawMessage(`{}`)}}
 if _,err:=CaptureStateStart(start,invalidKey);err==nil{t.Fatal("invalid Go definition key must not be rewritten by json.Marshal")}
}
func TestRowWriteSnapshotConcurrent(t *testing.T){
 start:=json.RawMessage(`{"sub":"testsub","unit":"u1","born":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","revision":3,"epoch":8,"epoch_index":"9007199254740993"}`)
 spec:=StateSpec{Schemas:map[string]json.RawMessage{"result":json.RawMessage(`{"type":"object","properties":{"s":{"type":"string","pattern":"^[a-z]+$"}}}`)}}
 snap,err:=CaptureStateStart(start,spec);if err!=nil{t.Fatal(err)}
 in:=json.RawMessage(`{"name":"result","value":{"s":"open"}}`)
 var wg sync.WaitGroup
 for i:=0;i<8;i++{wg.Add(1);go func(){defer wg.Done();for j:=0;j<20;j++{
  out,err:=BuildState(snap,in);if err!=nil{t.Error(err);return}
  if out.Guard.Index!="9007199254740993"||out.Items["born"]!="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"{t.Error("snapshot drift")}
  out.Items["born"]="mutated";out.Guard.Index="mutated"
 }}()};wg.Wait()
}
func TestRowWritePointers(t *testing.T){
 raw:=[]byte(`{"a/b":{"~key":[null,{"x":3}]}}`)
 value,err:=rwObject(raw);if err!=nil{t.Fatal(err)}
 v,ok:=rwPointer(value,"/a~1b/~0key/0");if !ok||v!=nil{t.Fatal("explicit null is present")}
 r,err:=rwRawPointer(raw,"/a~1b/~0key/0");if err!=nil||string(r)!="null"{t.Fatal("raw null pointer")}
 for _,p:=range []string{"/missing","/a~1b/~0key/-1","/a~1b/~0key/2","/a~1b/~0key/01"}{
  if _,ok:=rwPointer(value,p);ok{t.Fatalf("missing pointer accepted %s",p)}
  if _,err:=rwRawPointer(raw,p);err==nil{t.Fatalf("missing raw pointer accepted %s",p)}
 }
}
'''


def request(**changes):
    out = copy.deepcopy({"Start": START, "Schemas": SPEC, "Defs": DEFS, "Input": INPUT})
    out.update(changes)
    return out


def expected(start=START, value=None):
    value = {"state": "open"} if value is None else value
    return {"key": f"{start['sub']}/state/result/{start['unit']}",
            "items": {"born": start["born"], "revision": str(start["revision"]), "epoch": str(start["epoch"]),
                      "value": json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))},
            "guard": {"key": f"{start['sub']}/epoch/{start['unit']}", "index": start["epoch_index"]}}


class Producer(unittest.TestCase):
    def test_exact_source_and_fresh_overlay(self):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        model = gen.load()
        self.assertEqual(len(model["declarations"]), 8)
        self.assertEqual(len(model["writes"]), 1)
        write = model["writes"][0]
        self.assertEqual(write["family"], "<sub>/state/<name>/<id>")
        self.assertEqual([(f["field"], f["source"], f["pointer"], f["codec"]) for f in write["fields"]],
                         [("born", "start", "/born", "string"), ("revision", "start", "/revision", "integer"),
                          ("epoch", "start", "/epoch", "integer"), ("value", "input", "/value", "jcs")])
        errors, stats = check_forms.check_row_write_bindings(ROOT / gen.FORM)
        self.assertEqual(errors, [])
        self.assertEqual(stats["row_write_bindings"], 4)
        for name, text in gen.render().items():
            self.assertEqual((output_lesson.output_root() / 'p03/go/families' / name).read_text(), text, "run gen_row_writes.py --lesson 03-worker")

    def test_invalid_forms_and_type_bindings(self):
        original = (ROOT / gen.FORM).read_text()
        variants = {
            "duplicate": original + original.split("\n")[-2] + "\n",
            "missing required": original.replace(next(l + "\n" for l in original.split("\n") if "\t/born\t" in l), ""),
            "foreign field": original.replace("\t/born\t", "\t/foreign\t"),
            "unknown pointer": original.replace("\tstart\t/born\t", "\tstart\t/missing\t"),
            "bad pointer": original.replace("#start /born string", "#start /b~2 string"),
            "key ref type": original.replace("#start /sub string", "#start /sub integer"),
            "wrong value type": original.replace("#start /born string", "#start /born integer"),
            "unknown family": original.replace("/state/", "/foreign/"),
            "split guard": original.replace("\tstart:/epoch_index\t", "\t-\t"),
            "guard type": original.replace("#start /epoch_index string", "#start /epoch_index integer"),
            "unknown source": original.replace("\tstart\t/born\t", "\treread\t/born\t"),
            "different key": original.replace("/state/", "/foreign/", 1),
            "unknown norm": original.replace("P/03.6-R018", "P/03.6-R999"),
            "norm repeat": original.replace("P/03.6-R018", "P/03.6-R018,P/03.6-R018"),
            "bad const": original.replace("\tstart\t/born\t", '\tconst\t{"x":1,"x":2}\t'),
            "const type": original.replace("\tstart\t/born\t", "\tconst\t3\t"),
        }
        with tempfile.TemporaryDirectory(prefix="rowwrites-forms-") as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / "Platform", root / "Platform")
            for name, text in variants.items():
                with self.subTest(name=name):
                    (root / gen.FORM).write_text(text)
                    self.assertTrue(check_forms.check_row_write_bindings(root / gen.FORM)[0])
                    with self.assertRaises(GenError):
                        gen.load(root)

    def test_unsupported_codec_is_a_generation_error(self):
        with tempfile.TemporaryDirectory(prefix="rowwrites-codec-") as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / "Platform", root / "Platform")
            p = root / "Platform/03-worker/data/state.schema.json"
            d = json.loads(p.read_bytes());d["properties"]["born"]["x-codec"] = ["time"]
            p.write_text(json.dumps(d))
            with self.assertRaisesRegex(GenError, "unsupported writer codec"):
                gen.load(root)
            d["properties"]["born"]["x-codec"] = ["string"]
            d["properties"]["value"]["unknown"] = True
            p.write_text(json.dumps(d))
            with self.assertRaisesRegex(GenError, "unsupported family schema word"):
                gen.load(root)


class Runtime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="rowwrites-runtime-")
        cls.root = Path(cls.tmp.name)
        cls.pkg = cls.root / "families";cls.pkg.mkdir()
        with patch.object(families, "DOC_MODE", True), patch.object(families, "RUNTIME", families.RUNTIME_DOC):
            files = families.render("03")
        files.update(gen.render())
        cls.files = files
        for name, text in files.items(): (cls.pkg / name).write_text(text)
        (cls.pkg / "row_boundary_test.go").write_text(BOUNDARY)
        (cls.root / "go.mod").write_text("module rowwritesjudge\n\ngo 1.22\n")
        (cls.root / "main.go").write_text(HARNESS)
        cls.exe = cls.compile(cls.root)
        cls.oracle = stack.Family(json.loads((ROOT / "Platform/03-worker/data/state.schema.json").read_bytes()), "row")

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    @staticmethod
    def compile(root):
        exe = root / "judge"
        done = subprocess.run(["go", "build", "-o", str(exe), "."], cwd=root, env=ENV, capture_output=True, text=True)
        if done.returncode: raise AssertionError("constructor/harness BUILD ERROR (not a killed mutant): " + done.stderr)
        return exe

    def invoke(self, cases, exe=None):
        text = "".join((r if isinstance(r, str) else json.dumps(r, ensure_ascii=True)) + "\n" for r in cases)
        done = subprocess.run([str(exe or self.exe)], input=text, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, "runtime/harness error: " + done.stderr)
        answers = [json.loads(l) for l in done.stdout.split("\n") if l]
        self.assertEqual(len(answers), len(cases), "every oracle case must execute")
        for answer in answers:
            self.assertNotIn("panic", answer)
            self.assertNotIn("harness_error", answer)
        return answers

    def test_state_start_schema_capture_and_no_aliases(self):
        cases = [request(), request(Alias=True), request(Repeat=True)]
        self.assertEqual(self.invoke(cases), [expected()] * len(cases))
        for got in self.invoke(cases):
            self.assertEqual(self.oracle.judge(got["items"], "writer")["verdict"], "ok")
        bad = request(Alias=True);bad["Input"]["value"] = {"state": 7}
        self.assertIn("error", self.invoke([bad])[0], "a new schema after capture must not make the value legal")

    def test_exact_versions_and_integers(self):
        versions = ("9007199254740993", "9223372036854775808", "18446744073709551615", "99999999999999999999", "", "0")
        cases = []
        for version in versions:
            c = request();c["Start"]["epoch_index"] = version
            c["Start"]["revision"] = 9007199254740991
            cases.append(c)
        got = self.invoke(cases)
        self.assertEqual(got, [expected(c["Start"]) for c in cases])
        for value in (0, -1, 9007199254740992, 9223372036854775808, 1.0, True, "3"):
            c = request();c["Start"]["revision"] = value
            self.assertIn("error", self.invoke([c])[0])

    def test_missing_null_empty_and_bad_keys(self):
        cases = [request(Zero=True)]
        for source, field in (("Start", "born"), ("Start", "epoch_index"), ("Input", "value"), ("Input", "name")):
            c = request();del c[source][field];cases.append(c)
        for source, field, value in (("Start", "born", None), ("Start", "born", ""), ("Start", "sub", ""), ("Start", "sub", "a/b"),
                                     ("Start", "unit", ".."), ("Input", "name", "foreign"),
                                     ("Start", "epoch_index", 9007199254740993), ("Start", "epoch_index", "01"),
                                     ("Start", "epoch_index", "1" * 21), ("Start", "born", "wrong")):
            c = request();c[source][field] = value;cases.append(c)
        self.assertTrue(all("error" in a for a in self.invoke(cases)))
        null = request(Schemas={"result": {"type": "null"}}, Defs={});null["Input"]["value"] = None
        got = self.invoke([null])[0]
        self.assertEqual(got["items"]["value"], "null", "required encoded value is not an absent items property")

    def test_strict_json_and_unsupported_schemas(self):
        cases = []
        for schema in ({"unknown": True}, {"$ref": "#/$defs/missing"}, {"$ref": "https://example.invalid/schema"},
                       {"type": 1}, {"type": ["object", 3]}, {"properties": []}, {"pattern": "["},
                       {"minLength": 1.5}, {"allOf": []}, {"required": [1]}, {"required": ["a", "a"]}, {"items": 42}):
            cases.append(request(Schemas={"result": schema}, Defs={}))
        cases.append(request(Schemas={"result": {"$ref": "#/$defs/loop"}}, Defs={"loop": {"$ref": "#/$defs/loop"}}))
        self.assertTrue(all(a.get("phase") == "capture" and "error" in a for a in self.invoke(cases)))

    def test_direct_json_boundary_and_race(self):
        done = subprocess.run(["go", "test", "-race", "-count=1", "./families"], cwd=self.root, env=ENV,
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_unicode_jcs_and_writer_oracle(self):
        cases = []
        values = [{"é": [True, None, '\u043a\u0430\u043c\u0435\u0440\u0430\u2028\x0b'], "a": "😀"}, [1, "x", None], "\\u0436", False, 7]
        for value in values:
            c = request(Schemas={"result": {}}, Defs={});c["Input"]["value"] = value;cases.append(c)
        for c, got in zip(cases, self.invoke(cases)):
            self.assertEqual(got, expected(c["Start"], c["Input"]["value"]))
            self.assertEqual(self.oracle.judge(got["items"], "writer")["verdict"], "ok")
        utf16 = request(Schemas={"result": {}}, Defs={});utf16["Input"]["value"] = {"\ue000": 1, "😀": 2}
        got = self.invoke([utf16])[0]
        self.assertEqual(got["items"]["value"], '{"😀":2,"\ue000":1}')
        self.assertEqual(self.oracle.judge(got["items"], "writer")["verdict"], "ok")

    def test_runtime_mutants_reach_oracle(self):
        baseline = self.invoke([request()])[0]
        self.assertEqual(baseline, expected())
        model = gen.load();original = (self.pkg / "row_writes.go").read_text()
        data = {k: v for k, v in model.items() if k != "sources"}
        cases = [request(), request()]
        cases[1]["Input"]["value"] = {"state": 7}
        cases.append(request());cases[2]["Start"]["born"] = "not-a-born"
        mutations = []
        for field, pointer in (("born", "/reread_row/born"), ("revision", "/reread_row/revision"), ("epoch", "/current_epoch")):
            wrong = copy.deepcopy(data)
            binding = next(f for f in wrong["writes"][0]["fields"] if f["field"] == field)
            binding.update(source="input", pointer=pointer)
            mutations.append((field + " from reread", "row_writes.go", original.replace(
                go_str(json.dumps(data, separators=(",", ":"))), go_str(json.dumps(wrong, separators=(",", ":"))))))
        wrong = copy.deepcopy(data);wrong["writes"][0]["version"] = {"source": "input", "pointer": "/current_index"}
        mutations.append(("guard current version", "row_writes.go", original.replace(
            go_str(json.dumps(data, separators=(",", ":"))), go_str(json.dumps(wrong, separators=(",", ":"))))))
        runtime = self.files["row_write_runtime.go"]
        for name, old, new in (
            ("guard binary64", "Index: version", "Index: func() string { n,_:=strconv.ParseFloat(version,64);return strconv.FormatFloat(n,'f',0,64) }()"),
            ("schema bypass", 'if !sch.judgeText("object", raw, Writer).OK()', 'if false && !sch.judgeText("object", raw, Writer).OK()'),
            ("Writer bypass", 'if !writer.judgeRow(ItemsOf(items), Writer).OK()', 'if false && !writer.judgeRow(ItemsOf(items), Writer).OK()'),
        ):
            self.assertIn(old, runtime);mutations.append((name, "row_write_runtime.go", runtime.replace(old, new, 1)))
        for i, (name, filename, text) in enumerate(mutations):
            with self.subTest(name=name):
                self.assertNotEqual(text, self.files[filename], "mutation must really change compiled code")
                root = self.root / f"mutant-{i}";root.mkdir()
                shutil.copytree(self.pkg, root / "families")
                (root / "go.mod").write_text((self.root / "go.mod").read_text())
                (root / "main.go").write_text(HARNESS)
                (root / "families" / filename).write_text(text)
                exe = self.compile(root)
                actual = self.invoke(cases, exe)
                self.assertTrue(actual[0] != expected() or "error" not in actual[1] or "error" not in actual[2], "mutant survived the oracle")
                print(f"\nrow-write mutant {name}: compiled, {len(cases)} oracle cases executed, killed")


if __name__ == "__main__": unittest.main()
