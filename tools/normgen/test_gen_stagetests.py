"""Test stage-test generation (ADR-0125 addenda3/4, ADR-0126 addendum 7). Require fresh stagetests/coreadapter and complete selected-step inventory. Gate tests selections precede transitional declarations. Stand directives and later-stage refusals truncate prefixes; reject empty projections, missing scenarios, scenario/seam duplicate names and new bindings in each/rest. Check fixture-core engine binding, number kinds, extra fields, error, !contains, list ordering, ASSERT, unbound names, status classes and clock/reopen/parallel seams. scenario_judge compares runner execution on identical implementation code. Go 1.22 required."""
import lesson as output_lesson
import re
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import gen_stagetests  # noqa: E402
import gen_tests  # noqa: E402

OUT = output_lesson.output_root() / 'p01-1'
STAGES = (ROOT / "Platform/01-store/forms/stages.kit.tsv").read_text(encoding="utf-8")
REFUSALS = (ROOT / "Platform/01-store/forms/refusals.tsv").read_text(encoding="utf-8")

# (scenario, step, request, expectation, fixture response(status, body) or None, subtest outcome or None if excluded).
SCEN = [
    ("s1-bind", "1", 'POST /b1 {"a":1}', '200 {"index":"$a"}', (200, '{"index":"7"}'), "pass"),
    ("s1-bind", "2", "GET /b2", '200 {"index":"$a"}', (200, '{"index":"7"}'), "pass"),
    ("s1-bind", "3", "GET /b3", '200 {"index":"$a"}', (200, '{"index":"8"}'), "fail"),
    ("s2-types", "1", "GET /t1", '200 {"n":1}', (200, '{"n":1.0}'), "fail"),
    ("s2-types", "2", "GET /t2", '200 {"n":1}', (200, '{"n":1}'), "pass"),
    ("s2-types", "3", "GET /t3", '200 {"n":true}', (200, '{"n":1}'), "fail"),
    ("s3-fields", "1", "GET /f1", '200 {"a":"x"}', (200, '{"a":"x","b":1}'), "fail"),
    ("s3-fields", "2", "GET /f2", '409 {"kind":"conflict"}', (409, '{"kind":"conflict","error":"e"}'), "pass"),
    ("s3-fields", "3", "GET /f3", '409 {"kind":"conflict"}', (409, '{"kind":"conflict"}'), "fail"),
    ("s3-fields", "4", "GET /f4", '200 {"a":"x"}', (200, '{"a":"x","a":"x"}'), "fail"),
    ("s4-contains", "1", "GET /c1", '409 {"kind":"k","error":"!contains 42"}', (409, '{"kind":"k","error":"has 42"}'), "fail"),
    ("s4-contains", "2", "GET /c2", '409 {"kind":"k","error":"!contains 42"}', (409, '{"kind":"k","error":"ok"}'), "pass"),
    ("s5-order", "1", "GET /v1/list?prefix=a", '200 {"keys":{"a":"1","b":"2"}}', (200, '{"keys":{"b":"2","a":"1"}}'), "fail"),
    ("s5-order", "2", "GET /v1/list?prefix=b", '200 {"keys":{"a":"1","b":"2"}}', (200, '{"keys":{"a":"1","b":"2"}}'), "pass"),
    ("s6-assert", "1", "GET /p", '200 {"x":"$x","y":"$y"}', (200, '{"x":"1","y":"2"}'), "pass"),
    ("s6-assert", "2", "ASSERT $x != $y", "", None, "pass"),
    ("s6-assert", "3", "ASSERT $x == $y", "", None, "fail"),
    ("s6-assert", "4", "ASSERT $z != $x $y", "", None, "fail"),
    ("s6-assert", "5", "ASSERT $x != $y $x", "", None, "fail"),
    ("s7-unbound", "1", "GET /q/$nope", "200 {}", (200, "{}"), "fail"),
    ("s8-class", "1", "GET /s", "4xx", (404, '{"error":"e"}'), "pass"),
    ("s8-class", "2", "GET /s2", "4xx", (500, '{"error":"e"}'), "fail"),
    ("s9-prefix", "1", "GET /x1", '200 {"a":"1"}', (200, '{"a":"1"}'), "pass"),
    ("s9-prefix", "2", "@restart store", "ok", None, None),
    ("s9-prefix", "3", "GET /x3", '200 {"a":"1"}', (200, '{"a":"1"}'), None),
    ("s10-late", "1", "GET /l1", '200 {"a":"1"}', (200, '{"a":"1"}'), "pass"),
    ("s10-late", "2", "GET /l2", '403 {"kind":"forbidden"}', (403, '{"kind":"forbidden","error":"e"}'), None),
]
SEAMS = [
    ("m1-clock", "1", "GET /now", '200 {"now":"2000000000"}', None, "pass"),
    ("m1-clock", "2", "@clock +60", "ok", None, "pass"),
    ("m1-clock", "3", "GET /now", '200 {"now":"2000000060"}', None, "pass"),
    ("m1-clock", "4", "@clock -10", "ok", None, "pass"),
    ("m1-clock", "5", "GET /now", '200 {"now":"2000000050"}', None, "pass"),
    ("m1-clock", "6", "GET /now", '200 {"now":"2000000000"}', None, "fail"),
    ("m2-reopen", "1", "GET /opens", '200 {"n":"1"}', None, "pass"),
    ("m2-reopen", "2", "@clock +5", "ok", None, "pass"),
    ("m2-reopen", "3", "@reopen", "ok", None, "pass"),
    ("m2-reopen", "4", "GET /opens", '200 {"n":"2"}', None, "pass"),
    ("m2-reopen", "5", "GET /now", '200 {"now":"2000000005"}', None, "pass"),
    ("m4-frac", "1", "@clock +0.25", "ok", None, "pass"),
    ("m4-frac", "2", "GET /nowns", '200 {"now":"2000000000250000000"}', None, "pass"),
    ("m4-frac", "3", "@clock +100.25", "ok", None, "pass"),
    ("m4-frac", "4", "GET /nowns", '200 {"now":"2000000100500000000"}', None, "pass"),
    ("m4-frac", "5", "@reopen", "ok", None, "pass"),
    ("m4-frac", "6", "@clock -100.125", "ok", None, "pass"),
    ("m4-frac", "7", "GET /nowns", '200 {"now":"2000000000375000000"}', None, "pass"),
    ("m4-frac", "8", "@clock +0.000000001", "ok", None, "pass"),
    ("m4-frac", "9", "GET /nowns", '200 {"now":"2000000000375000000"}', None, "fail"),
    ("m3-par", "1", "@parallel 4", "ok", None, "pass"),
    ("m3-par", "2", "POST /race1 {}", 'one 200 {"index":"$b"}; rest 409 {"kind":"conflict","index":"$b"}', None, "pass"),
    ("m3-par", "3", "GET /five", '200 {"index":"$b"}', None, "pass"),
    ("m3-par", "4", "@parallel 3", "ok", None, "pass"),
    ("m3-par", "5", "GET /same", 'each 200 {"a":"1"}', None, "pass"),
    ("m3-par", "6", "@parallel 3", "ok", None, "pass"),
    ("m3-par", "7", "POST /race2 {}", 'each 200 {"index":"5"}', None, "fail"),
    ("m3-par", "8", "@parallel 2", "ok", None, "pass"),
    ("m3-par", "9", "GET /same", 'one 200 {"a":"1"}; rest 409 {"kind":"conflict"}', None, "fail"),
]

FAKE = '''package stagetests

import (
	"fmt"
	"strings"
	"sync"

	"normgen/p01-1/apidoor"
	"normgen/p01-1/coreadapter"
)

type fakeCore struct{ coreadapter.NotInStage }

func (fakeCore) Get(coreadapter.Ctx, apidoor.GetQuery) apidoor.Answer   { return apidoor.Answer{} }
func (fakeCore) List(coreadapter.Ctx, apidoor.ListQuery) apidoor.Answer { return apidoor.Answer{} }
func (fakeCore) Write(coreadapter.Ctx, []byte) apidoor.Answer           { return apidoor.Answer{} }
func (fakeCore) QueryRefused(coreadapter.Ctx, apidoor.Op, *apidoor.QueryError) apidoor.Answer {
	return apidoor.Answer{}
}
func (fakeCore) Context(c coreadapter.Call, h map[string]string) coreadapter.Ctx { return nil }
func (fakeCore) Close()                                                        {}

var (
	mu    sync.Mutex
	opens = map[string]int{}
	races = map[string]int{}
)

var replies = map[string]struct {
	code int
	body string
}{
%s}

func init() {
	openCore = func(cfg coreadapter.Config) (coreadapter.Core, error) {
		mu.Lock()
		opens[cfg.DataDir]++
		mu.Unlock()
		return fakeCore{}, nil
	}
	handleCall = func(c coreadapter.Core, cfg coreadapter.Config, call coreadapter.Call, method, target string,
		h map[string]string, b []byte) (int, map[string]string, []byte) {
		switch {
		case target == "/now":
			return 200, nil, []byte(fmt.Sprintf(`{"now":"%%d"}`, cfg.Now().Unix()))
		case target == "/nowns":
			return 200, nil, []byte(fmt.Sprintf(`{"now":"%%d"}`, cfg.Now().UnixNano()))
		case target == "/opens":
			mu.Lock()
			defer mu.Unlock()
			return 200, nil, []byte(fmt.Sprintf(`{"n":"%%d"}`, opens[cfg.DataDir]))
		case target == "/five":
			return 200, nil, []byte(`{"index":"5"}`)
		case target == "/same":
			return 200, nil, []byte(`{"a":"1"}`)
		case strings.HasPrefix(target, "/race"):
			mu.Lock()
			races[cfg.DataDir+target]++
			n := races[cfg.DataDir+target]
			mu.Unlock()
			if n == 1 {
				return 200, nil, []byte(`{"index":"5"}`)
			}
			return 409, nil, []byte(`{"kind":"conflict","index":"5","error":"e"}`)
		}
		r, ok := replies[method+" "+target]
		if !ok {
			return 599, nil, []byte(`{"error":"no reply"}`)
		}
		return r.code, nil, []byte(r.body)
	}
}
'''

CALL_PROBES = r'''package stagetests
import (
    "encoding/json"
    "errors"
    "os"
    "testing"
    "time"
    "normgen/p01-1/coreadapter"
)
func TestCALLContract(t *testing.T) {
    prior:=callSeam
    defer func(){callSeam=prior}()
    sc:=&scenario{core:fakeCore{}, cfg:coreadapter.Config{DataDir:t.TempDir(),Now:func()time.Time{return time.Unix(7,123)}},env:map[string]any{}}
    type probe struct{ want,actual string; pass bool }
    cases:=[]probe{
        {`{"n":1}`,`{"n":1.0,"extra":true}`,true},
        {`{"n":1e3}`,`{"n":1000.000}`,true},
        {`{"n":9007199254740993}`,`{"n":9007199254740993.0}`,true},
        {`{"n":9007199254740993}`,`{"n":9007199254740992.0}`,false},
        {`{"n":1}`,`{"n":true}`,false},
        {`{"n":true}`,`{"n":1}`,false},
        {`{"o":{"a":1}}`,`{"o":{"a":1.0,"b":2},"extra":true}`,true},
        {`{"o":{}}`,`{"o":{"b":2}}`,false},
        {`{}`,`{"a":1}`,false},
        {`{"xs":[1,2]}`,`{"xs":[1.0,2.0]}`,true},
        {`{"xs":[1,2]}`,`{"xs":[2,1]}`,false},
        {`{"xs":[1,2]}`,`{"xs":[1,2,3]}`,false},
        {`{"x":"@absent"}`,`{"other":1}`,true},
        {`{"x":"@absent"}`,`{"x":null}`,false},
        {`{"s":"$empty"}`,`{"s":""}`,true},
        {`{"s":"$empty"}`,`{"s":"changed"}`,false},
        {`{"s":"$1"}`,`{"s":"$1"}`,true},
        {`{"s":"$1"}`,`{"s":"literal"}`,false},
    }
    input:=`{"raw": 9007199254740993, "fraction":1e+2}`
    received:=0
    for i,p:=range cases {
        callSeam=func(c coreadapter.Core,cfg coreadapter.Config,name string,args json.RawMessage)(json.RawMessage,error){
            if c!=sc.core || cfg.DataDir!=sc.cfg.DataDir || cfg.Now().UnixNano()!=7000000123 || name!="store-start-flags" || string(args)!=input {t.Fatal("ABI/context/raw arguments changed")}
            if err:=os.WriteFile(cfg.DataDir+"/adapter-observed",[]byte(name),0600);err!=nil {t.Fatal(err)}
            received++
            return json.RawMessage(p.actual),nil
        }
        errs:=sc.runStep(step{request:"CALL store-start-flags "+input,expect:p.want})
        if (len(errs)==0)!=p.pass {t.Fatalf("probe %d: pass=%v, errors=%v",i,p.pass,errs)}
    }
    if received!=len(cases) {t.Fatal("adapter was not invoked for every case")}
    // HTTP keeps its former type-sensitive comparison, apart from CALL.
    one,_:=decode([]byte(`{"n":1}`)); decimal,_:=decode([]byte(`{"n":1.0}`))
    if len(checkResponse(200,decimal,`200 {"n":1}`,map[string]any{},"GET","/probe"))==0 {t.Fatal("CALL changed HTTP number types")}
    if len(checkResponse(200,one,`200 {"n":1}`,map[string]any{},"GET","/probe"))!=0 {t.Fatal("old HTTP positive control failed")}
}

func TestCALLFailurePaths(t *testing.T) {
    prior:=callSeam
    defer func(){callSeam=prior}()
    sc:=&scenario{core:fakeCore{},cfg:coreadapter.Config{DataDir:t.TempDir()},env:map[string]any{}}
    st:=step{request:`CALL store-copy-floor {"input":"test-only"}`,expect:`{"complete":true}`}
    for name,fn:=range map[string]func(coreadapter.Core,coreadapter.Config,string,json.RawMessage)(json.RawMessage,error){
        "stub":coreadapter.CallSeam,
        "error":func(coreadapter.Core,coreadapter.Config,string,json.RawMessage)(json.RawMessage,error){return []byte(`{"complete":true}`),errors.New("I/O failed")},
        "panic":func(coreadapter.Core,coreadapter.Config,string,json.RawMessage)(json.RawMessage,error){panic("I/O panic")},
        "notexecuted":func(coreadapter.Core,coreadapter.Config,string,json.RawMessage)(json.RawMessage,error){return nil,nil},
    } {
        callSeam=fn
        if errs:=sc.runStep(st);len(errs)==0 {t.Fatal(name,"passed")}
    }
    called:=false
    callSeam=func(coreadapter.Core,coreadapter.Config,string,json.RawMessage)(json.RawMessage,error){called=true;return []byte(`{"complete":true}`),nil}
    bad:=st;bad.request=`CALL invented-port {}`
    if errs:=sc.runStep(bad);len(errs)==0 || called {t.Fatal("unknown port was executed or passed")}
    for _,raw:=range [][]byte{
        []byte(`{"complete":true,"complete":true}`),[]byte(`{"complete":true} {}`),[]byte(`{"complete":true} }`),
        []byte("\xef\xbb\xbf{\"complete\":true}"),[]byte(`{"complete":NaN}`),[]byte{'"',0xff,'"'},
    } {
        callSeam=func(coreadapter.Core,coreadapter.Config,string,json.RawMessage)(json.RawMessage,error){return raw,nil}
        if errs:=sc.runStep(st);len(errs)==0 {t.Fatalf("non-strict actual passed: %q",raw)}
        called=false
        callSeam=func(coreadapter.Core,coreadapter.Config,string,json.RawMessage)(json.RawMessage,error){called=true;return []byte(`{"complete":true}`),nil}
        bad=st;bad.request="CALL store-copy-floor "+string(raw)
        if errs:=sc.runStep(bad);len(errs)==0 || called {t.Fatalf("non-strict input executed/passed: %q",raw)}
        bad=st;bad.expect=string(raw)
        if errs:=sc.runStep(bad);len(errs)==0 || called {t.Fatalf("non-strict expectation executed/passed: %q",raw)}
    }
}

func TestCALLHeldObservation(t *testing.T) {
    prior:=callSeam
    defer func(){callSeam=prior}()
    sc:=&scenario{core:fakeCore{},cfg:coreadapter.Config{DataDir:t.TempDir()},env:map[string]any{}}
    // Exercise the declared seam. Fixture observations are authored independently
    // of its expectation, never copied from that expectation into the adapter.
    st:=seams1_3["s11-import-held-reads"][0]
    input:=`{"input":"backup_into_live_group","interrupt_after_target_rows":1}`
    fields:=[]string{"leader_read_unavailable","follower_read_unavailable","write_unavailable","complete"}
    observation:=func()map[string]any{return map[string]any{
        "leader_read_unavailable":true,"follower_read_unavailable":true,
        "write_unavailable":true,"complete":true,
    }}
    encode:=func(value any)json.RawMessage{raw,err:=json.Marshal(value);if err!=nil{t.Fatal(err)};return raw}
    actual:=encode(observation())
    called:=false
    install:=func(){callSeam=func(c coreadapter.Core,cfg coreadapter.Config,name string,args json.RawMessage)(json.RawMessage,error){
        called=true
        if c!=sc.core || cfg.DataDir!=sc.cfg.DataDir || name!="store-import-held" || string(args)!=input {t.Fatal("held ABI/context/raw input changed")}
        return actual,nil
    }}
    install()
    if errs:=sc.runStep(st);len(errs)!=0 || !called {t.Fatal("independent held positive failed",errs)}
    // JSON-schema integer semantics: equal mathematical integers may use an
    // exponent or fractional token. The untouched raw input still reaches YOURS.
    for _,number:=range []string{"1.0","1e0","1.000e+0"} {
        input=`{"input":"backup_into_live_group","interrupt_after_target_rows":`+number+`}`
        alt:=st;alt.request="CALL store-import-held "+input
        if errs:=sc.runStep(alt);len(errs)!=0 {t.Fatal(number,errs)}
    }
    input=`{"input":"backup_into_live_group","interrupt_after_target_rows":1}`
    for _,key:=range fields {
        for _,bad:=range []any{false,nil,1,"true",[]any{true},map[string]any{}} {
            value:=observation();value[key]=bad;actual=encode(value)
            if errs:=sc.runStep(st);len(errs)==0 {t.Fatalf("held %s=%v passed",key,bad)}
        }
        value:=observation();delete(value,key);actual=encode(value)
        if errs:=sc.runStep(st);len(errs)==0 {t.Fatal("held missing field passed",key)}
    }
    value:=observation();value["extra"]=true
    for _,raw:=range []json.RawMessage{encode(value),[]byte(`{}`),[]byte(`[]`),[]byte(`true`),nil,[]byte(`not JSON`),[]byte(`{"complete":true} {}`)} {
        actual=raw
        if errs:=sc.runStep(st);len(errs)==0 {t.Fatalf("held invalid/extra/empty actual passed: %q",raw)}
    }
    actual=encode(observation())
    for _,raw:=range []string{
        `{}`,`[]`,`{"input":"other","interrupt_after_target_rows":1}`,
        `{"input":"backup_into_live_group","interrupt_after_target_rows":true}`,
        `{"input":"backup_into_live_group","interrupt_after_target_rows":"1"}`,
        `{"input":"backup_into_live_group","interrupt_after_target_rows":1.5}`,
        `{"input":"backup_into_live_group","interrupt_after_target_rows":0}`,
        `{"input":"backup_into_live_group","interrupt_after_target_rows":2}`,
        `{"input":"backup_into_live_group","interrupt_after_target_rows":1,"extra":true}`,
    } {
        called=false;bad:=st;bad.request="CALL store-import-held "+raw
        if errs:=sc.runStep(bad);len(errs)==0 || called {t.Fatal("held invalid input executed/passed",raw,errs)}
    }
    for _,raw:=range []string{`{}`,`{"leader_read_unavailable":true,"follower_read_unavailable":true,"write_unavailable":true,"complete":1}`,string(encode(value))} {
        called=false;bad:=st;bad.expect=raw
        if errs:=sc.runStep(bad);len(errs)==0 || called {t.Fatal("held invalid expectation executed/passed",raw,errs)}
    }
    for name,fn:=range map[string]func(coreadapter.Core,coreadapter.Config,string,json.RawMessage)(json.RawMessage,error){
        "stub":coreadapter.CallSeam,
        "error":func(coreadapter.Core,coreadapter.Config,string,json.RawMessage)(json.RawMessage,error){return actual,errors.New("held I/O failed")},
        "panic":func(coreadapter.Core,coreadapter.Config,string,json.RawMessage)(json.RawMessage,error){panic("held I/O panic")},
        "notexecuted":func(coreadapter.Core,coreadapter.Config,string,json.RawMessage)(json.RawMessage,error){return nil,nil},
    } {
        callSeam=fn
        if errs:=sc.runStep(st);len(errs)==0 {t.Fatal("held",name,"passed")}
    }
}
'''


def synthetic_root(tmp, scen, seams=None):
    root = Path(tmp) / "root"
    acc = root / "Platform/01-store/acceptance/1"
    acc.mkdir(parents=True)
    (root / "Platform/01-store/forms").mkdir(parents=True)
    (root / "Platform/01-store/forms/stages.kit.tsv").write_text(STAGES, encoding="utf-8")
    (root / "Platform/01-store/forms/refusals.tsv").write_text(REFUSALS, encoding="utf-8")
    # The adapter reads the declared API even when these grammar probes use
    # synthetic scenarios. Supply that input rather than a producer fallback.
    relative_api = "Platform/01-store/spec/01-store.api.openapi.yaml"
    api = root / relative_api
    api.parent.mkdir(parents=True)
    api.write_bytes((ROOT / relative_api).read_bytes())
    head = ["scenario\tstep\trequest\texpect"]
    (acc / "scenarios.tsv").write_text("\n".join(head + ["\t".join(r) for r in scen]) + "\n", encoding="utf-8")
    if seams is not None:
        (acc / "seams.tsv").write_text("\n".join(head + ["\t".join(r) for r in seams]) + "\n", encoding="utf-8")
    return root


def with_gate(gate):
    lines = []
    for line in STAGES.split("\n"):
        cells = line.split("\t")
        if len(cells) > 4 and cells[1] == "store_core":
            cells[4] = gate
        elif len(cells) > 4 and cells[0] != "n":       # Other stages have no tests gates because their scenarios are absent from the synthetic source.
            cells[4] = ";".join(p for p in cells[4].split(";") if not p.strip().startswith("tests:")) or "build"
        lines.append("\t".join(cells))
    return "\n".join(lines)


class StageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="normgen-stagetests-")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def sub(self, name):
        return Path(self.tmp.name) / name

    def test_out_is_fresh_and_inventory_whole(self):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        files, inventory = gen_stagetests.build(ROOT)
        for rel, text in files.items():
            want = gen_tests.gofmt(text) if rel.endswith(".go") else text
            self.assertEqual((OUT / rel).read_text(encoding="utf-8"), want, f"{rel}: run gen_tests.py")
        scenarios, _, _ = gen_stagetests.read_table(ROOT, "1.1", "scenarios.tsv")
        want = sum(len(scenarios[n]) for _, items in gen_stagetests.TRANSITIONAL.items() for _, ns, _ in items for n in ns)
        if "tests:1.1:" not in STAGES:                     # Transitional declaration until tests:<chapter> enters the form.
            self.assertEqual(len(inventory), want)
        self.assertTrue(all(len(r) == 6 for r in inventory))
        for chapter in ("1.1", "1.3"):
            seams, _, _ = gen_stagetests.read_table(ROOT, chapter, "seams.tsv")
            selected = [r for r in inventory if r[0].startswith(chapter + "/seams.tsv/")]
            listed = {r[0].split("/")[2] for r in selected}
            if seams:                                    # Every declared seam scenario appears step-for-step in inventory.
                self.assertEqual(listed, set(seams))
                self.assertEqual(len(selected), sum(len(seams[n]) for n in listed))
        stages = {r[1] for r in inventory}
        for line in STAGES.split("\n"):
            cells = line.split("\t")
            if len(cells) > 4 and "tests:" in cells[4]:
                self.assertIn(cells[1], stages, "a stage with tests: has its projection")

    def test_selection_prefix_and_refusals(self):
        root = synthetic_root(self.sub("p"), [c[:4] for c in SCEN], [c[:4] for c in SEAMS])
        files, inv = gen_stagetests.build(root, stages_text=with_gate("tests:1.1:s9-prefix,s10-late;tests:1.1:m3-par:seams"),
                                          transitional={})
        status = {r[0]: r for r in inv}
        self.assertEqual(status["1.1/scenarios.tsv/s9-prefix/1"][3], "translated")
        self.assertEqual([status[f"1.1/scenarios.tsv/s9-prefix/{k}"][3] for k in "23"], ["excluded", "excluded"])
        self.assertIn("step 2", status["1.1/scenarios.tsv/s9-prefix/3"][5])
        self.assertEqual(status["1.1/scenarios.tsv/s10-late/2"][3], "excluded")     # Rights-related403 belongs to the rights stage.
        self.assertIn("later stage", status["1.1/scenarios.tsv/s10-late/2"][5])
        self.assertEqual(status["1.1/seams.tsv/m3-par/2"][4], "yes")                 # @parallel tests require -race.
        self.assertEqual(status["1.1/scenarios.tsv/s9-prefix/1"][4], "no")
        self.assertIn("TestStoreCore_S9Prefix", files["go/stagetests/store_core_test.go"])

    def test_required_call_seams_and_strict_form(self):
        _, inventory = gen_stagetests.build(ROOT)
        required = {"s7-loopback-api-no-tls", "s8-loopback-join-needs-tls", "s9-public-api-needs-tls",
                    "s10-import-floor-resume", "s11-import-held-reads"}
        calls = [r for r in inventory if r[0].startswith("1.3/seams.tsv/")]
        self.assertEqual({r[0].split("/")[2] for r in calls}, required)
        self.assertEqual(len(calls), 5)       # OBSH.67 makes the declared held seam part of kit stage 11.
        self.assertTrue(all(r[3] == "translated" and r[2] != "-" for r in calls), calls)
        for request, expect in (("CALL unknown-port {}", "{}"), ('CALL store-copy-floor {"x":1,"x":2}', "{}"),
                                ("CALL store-copy-floor NaN", "{}"), ("CALL store-copy-floor {} {}", "{}"),
                                ("CALL store-copy-floor {}", '{"x":1,"x":2}'), ("CALL store-copy-floor {}", "{} }")):
            with self.subTest(request=request, expect=expect), self.assertRaises(gen_stagetests.GenError):
                gen_stagetests.step_blocker("1.3", ("1", request, expect, 1), True, {}, 9)

    def test_held_closed_source_forms(self):
        args = {"input": "backup_into_live_group", "interrupt_after_target_rows": 1}
        result = {key: True for key in ("leader_read_unavailable", "follower_read_unavailable",
                                       "write_unavailable", "complete")}

        def check(input_text, expect):
            return gen_stagetests.step_blocker("1.3", ("1", "CALL store-import-held " + input_text, expect, 1),
                                              True, {}, 11)

        for number in ("1", "1.0", "1e0"):
            self.assertIsNone(check('{"input":"backup_into_live_group","interrupt_after_target_rows":' + number + '}',
                                    json.dumps(result)))
        invalid_inputs = [[], {}, dict(args, extra=True), dict(args, input="other")]
        invalid_inputs += [dict(args, interrupt_after_target_rows=value) for value in (True, "1", 0, 2, 1.5, None)]
        invalid_inputs += [{key: value for key, value in args.items() if key != missing} for missing in args]
        for value in invalid_inputs:
            with self.subTest(input=value), self.assertRaises(gen_stagetests.GenError):
                check(json.dumps(value), json.dumps(result))
        invalid_results = [[], {}, dict(result, extra=True)]
        for key in result:
            invalid_results += [dict(result, **{key: value}) for value in (1, "true", None, {}, [])]
            invalid_results.append({k: v for k, v in result.items() if k != key})
            # Form validation must not synthesize a true observation: false is a
            # valid boolean, whose value the runtime compares with the seam.
            self.assertIsNone(check(json.dumps(args), json.dumps(dict(result, **{key: False}))))
        for value in invalid_results:
            with self.subTest(result=value), self.assertRaises(gen_stagetests.GenError):
                check(json.dumps(args), json.dumps(value))
        huge_exponent = '1e999999999999999999999999'
        for port in ('store-start-flags', 'store-copy-floor'):
            # The existing ports retain their strict-JSON parser and generic
            # matcher contract. Decimal is confined to the new held source ABI.
            request = 'CALL ' + port + ' {"number":' + huge_exponent + '}'
            self.assertIsNone(gen_stagetests.step_blocker("1.3", ("1", request, '{}', 1), True, {}, 11))
        with self.assertRaises(gen_stagetests.GenError):
            check('{"input":"backup_into_live_group","interrupt_after_target_rows":' + huge_exponent + '}',
                  json.dumps(result))

    def test_call_engine_contract_and_default_stub_failure(self):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        mod = self.sub("callmod")
        shutil.copytree(OUT / "go", mod)
        (mod / "stagetests/fake_test.go").write_text(FAKE % "", encoding="utf-8")
        (mod / "stagetests/call_contract_test.go").write_text(CALL_PROBES, encoding="utf-8")
        done = subprocess.run(["go", "test", "-count=1", "-race", "-run", "^TestCALL", "./stagetests"],
                              cwd=mod, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        done = subprocess.run(["go", "test", "-count=1", "-json", "-run", "^(TestDaemon(Doors|Copy)_|TestGroup_S11ImportHeldReads$)", "./stagetests"],
                              cwd=mod, capture_output=True, text=True)
        roots = {}
        for raw in done.stdout.splitlines():
            event = json.loads(raw)
            name = event.get("Test", "")
            if name and "/" not in name and event.get("Action") in ("pass", "fail", "skip"):
                roots[name] = event["Action"]
        self.assertEqual(set(roots), {"TestDaemonDoors_S7LoopbackApiNoTls", "TestDaemonDoors_S8LoopbackJoinNeedsTls",
                                     "TestDaemonDoors_S9PublicApiNeedsTls", "TestDaemonCopy_S10ImportFloorResume",
                                     "TestGroup_S11ImportHeldReads"}, done.stdout + done.stderr)
        self.assertEqual(set(roots.values()), {"fail"}, done.stdout + done.stderr)
        self.assertIn("not implemented", done.stdout)

    def test_bad_selection_and_parallel_forms(self):
        root = synthetic_root(self.sub("bad-selection"), [c[:4] for c in SCEN], [c[:4] for c in SEAMS])
        bad = [
            ("tests:1.1:s99", {}),                                            # Missing scenario.
            ("tests:1.1:s9-prefix,s9-prefix", {}),                            # Duplicate.
            ("tests:store_core:1.1:s1-bind", {}),                             # Kind outside addendum 7, item 2.
            ("tests:1.1:s9-prefix; tests:1.1:m3-par:seams", {}),              # Whitespace after ';' violates the form header.
            ("tests:1.1:s9-prefix;", {}),                                     # Empty element.
        ]
        for gate, tr in bad:
            with self.subTest(gate=gate), self.assertRaises(gen_stagetests.GenError):
                gen_stagetests.build(root, stages_text=with_gate(gate), transitional=tr)
        empty = synthetic_root(self.sub("e"), [("s0", "1", "@restart store", "ok")])
        with self.assertRaises(gen_stagetests.GenError):                   # Empty projection.
            gen_stagetests.build(empty, stages_text=with_gate("tests:1.1:s0"), transitional={})
        clash = synthetic_root(self.sub("c"), [("m1-clock", "1", "GET /x", "200 {}")], [c[:4] for c in SEAMS])
        with self.assertRaises(gen_stagetests.GenError):                   # Same name in two files.
            gen_stagetests.build(clash, stages_text=with_gate("tests:1.1:m1-clock:seams"), transitional={})
        for seams in ([("p1", "1", "@parallel 2", "ok"), ("p1", "2", "GET /x", 'each 200 {"i":"$new"}')],
                      [("p1", "1", "@parallel 2", "ok"), ("p1", "2", "GET /x", 'one 200 {}; rest 200 {"i":"$new"}')],
                      [("p1", "1", "GET /x", 'each 200 {}')],
                      [("p1", "1", "@parallel 2", "ok")],
                      [("p1", "1", "@clock +5", "200 {}")]):
            r = synthetic_root(self.sub(f"b{len(list(self.sub('.').glob('b*')))}"), [("s", "1", "GET /x", "200 {}")], seams)
            with self.subTest(seams=seams), self.assertRaises(gen_stagetests.GenError):
                gen_stagetests.build(r, stages_text=with_gate("tests:1.1:p1:seams"), transitional={})

    def test_synthetic_fixture_supplies_exact_current_api(self):
        relative = "Platform/01-store/spec/01-store.api.openapi.yaml"
        original = (ROOT / relative).read_bytes()
        root = synthetic_root(self.sub("api-closure"), [("g1", "1", "GET /v1/get?key=acc/g/x", "200 {}")])
        self.assertEqual((root / relative).read_bytes(), original)
        _, rows = gen_stagetests.build(root, stages_text=with_gate("tests:1.1:g1"), transitional={})
        self.assertEqual({r[0].split("/", 2)[2]: r[3] for r in rows}["g1/1"], "translated")
        self.assertEqual((ROOT / relative).read_bytes(), original)
        self.assertEqual((root / relative).read_bytes(), original)

    def test_synthetic_fixture_missing_or_malformed_api_is_refused(self):
        relative = "Platform/01-store/spec/01-store.api.openapi.yaml"
        original = (ROOT / relative).read_bytes()
        root = synthetic_root(self.sub("api-required"), [("g1", "1", "GET /v1/get?key=acc/g/x", "200 {}")])
        _, rows = gen_stagetests.build(root, stages_text=with_gate("tests:1.1:g1"), transitional={})
        self.assertEqual({r[0].split("/", 2)[2]: r[3] for r in rows}["g1/1"], "translated")
        api = root / relative
        api.unlink()
        with self.assertRaisesRegex(gen_stagetests.GenError, "stage adapter API"):
            gen_stagetests.build(root, stages_text=with_gate("tests:1.1:g1"), transitional={})
        api.write_bytes(b"openapi: [unterminated\n")
        with self.assertRaisesRegex(gen_stagetests.GenError, "stage adapter API"):
            gen_stagetests.build(root, stages_text=with_gate("tests:1.1:g1"), transitional={})
        self.assertEqual((ROOT / relative).read_bytes(), original)

    def test_at_is_data(self):
        """Treat @ in keys/values/bodies as data unless grammar and position declare a directive (Codex C5)."""
        scen = [
            ("a1", "1", 'POST /v1/write {"op":"put","key":"acc/a1/x@y","items":{"mail":"a@b.example"}}', '200 {"index":"$a"}'),
            ("a1", "2", "GET /v1/get?key=acc/a1/x@y", '200 {"items":{"mail":"a@b.example"},"index":"$a"}'),
            ("a1", "3", 'POST /v1/write {"op":"put","key":"acc/a1/@big(3)@z","items":{"@":"@"}}', '200 {"index":"$b"}'),
            ("a1", "4", "GET /v1/get?key=acc/a1/x@y", '200 {"items":{"at":"@time"},"index":"$a"}'),
            ("a1", "5", "GET /v1/get?key=acc/a1/x@y", '200 {"index":"$a"}'),
            ("a2", "1", "GET /v1/get?key=acc/a2/c", '@oneof 200 {"index":""} | 503 {"kind":"unavailable"}'),
            ("a3", "1", "GET /v1/get?key=acc/a3/c", '200 {"items":"@any","index":""}'),
            ("a3", "2", "GET /v1/get?key=acc/a3/c", '200 {"items":null,"index":""}'),
        ]
        root = synthetic_root(self.sub("at"), scen)
        _, inv = gen_stagetests.build(root, stages_text=with_gate("tests:1.1:a1,a3"), transitional={})
        status = {r[0].split("/", 2)[2]: r for r in inv}
        for k in ("a1/1", "a1/2", "a1/3"):
            self.assertEqual(status[k][3], "translated", k)
        self.assertEqual(status["a1/4"][3], "excluded")
        self.assertIn("@time", status["a1/4"][5])
        self.assertEqual(status["a1/5"][3], "excluded")                      # Suffix after a directive.
        self.assertEqual(status["a3/1"][3], "excluded")
        self.assertIn("@any", status["a3/1"][5])
        with self.assertRaises(gen_stagetests.GenError):                     # @oneof as the first step yields an empty projection.
            gen_stagetests.build(root, stages_text=with_gate("tests:1.1:a2"), transitional={})

    def test_engine_on_fake_core(self):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        root = synthetic_root(self.sub("g"), [c[:4] for c in SCEN], [c[:4] for c in SEAMS])
        names = ",".join(sorted({c[0] for c in SCEN}))
        seams = ",".join(sorted({c[0] for c in SEAMS}))
        files, _ = gen_stagetests.build(root, stages_text=with_gate(f"tests:1.1:{names};tests:1.1:{seams}:seams"),
                                        transitional={})
        mod = self.sub("mod")
        shutil.copytree(OUT / "go", mod)
        shutil.rmtree(mod / "stagetests")
        for rel, text in files.items():
            if rel.startswith("go/"):
                (mod / rel[3:]).parent.mkdir(parents=True, exist_ok=True)
                (mod / rel[3:]).write_text(text, encoding="utf-8")
        replies = "".join(f'\t{json.dumps(c[2].split(" ")[0] + " " + c[2].split(" ")[1])}: {{{c[4][0]}, {json.dumps(c[4][1])}}},\n'
                          for c in SCEN if c[4])
        (mod / "stagetests/fake_test.go").write_text(FAKE % replies, encoding="utf-8")
        done = subprocess.run(["go", "test", "-count=1", "-race", "-json", "./stagetests"], cwd=mod, capture_output=True,
                              text=True)
        got = {}
        for line in done.stdout.splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("Action") in ("pass", "fail") and "/" in (e.get("Test") or ""):
                got[e["Test"]] = e["Action"]
        self.assertTrue(got, done.stdout[-2000:] + done.stderr[-2000:])
        self.assertNotIn("DATA RACE", done.stdout)
        for sc, step, req, _, _, want in SCEN + SEAMS:
            name = f"TestStoreCore_{gen_stagetests.camel_name(sc)}/{step}"
            with self.subTest(step=f"{sc}/{step} {req}"):
                self.assertEqual(got.get(name), want, name)


if __name__ == "__main__":
    unittest.main()
