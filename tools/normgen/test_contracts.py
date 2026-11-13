"""Judge for shared contracts (tools/normgen/contracts; ADR-0125 addendum (5), generation inventory item 1).

Run: python3 tools/normgen/test_contracts.py [-v]   (go 1.22)

The contracts package is a handwritten runtime shared by a vocabulary, based on Platform/common/contracts/*.md.
contracts/adapters/<function>.go exposes its vectoradapter functions. Shared vectors are the judge: for each lesson
whose vectors (out/pNN/go/vectortests, produced by gen_vectors) call an adapter function, build the lesson module
with contracts and that adapter replacing the stub. Every test for the function's tables must pass; the test set
is read from vectoradapter.<Function> calls in the tests. A contract mutant that weakens validation must fail
in at least one lesson.
"""
import lesson as output_lesson
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "contracts"))
import kitside  # noqa: E402
CONTRACTS = HERE / "contracts/go"
ADAPTERS = HERE / "contracts/adapters"
OUT = output_lesson.output_root()
GOENV = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off", GOTOOLCHAIN="local")


def adapter_fns():
    return {re.search(r"^func ([A-Z]\w*)\((?:table|input|file|raw)\b", p.read_text(), re.M)[1]: p
            for p in sorted(ADAPTERS.glob("*.go"))}


def lesson_mods():
    output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
    ready = output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
    modules = [ready[slug] / "go" for slug in output_lesson.PROFILES]
    missing = [str(path) for path in modules if not (path / "vectortests").is_dir()]
    if missing:
        raise AssertionError(f"missing prepared vector profiles: {missing}")
    return modules


def tests_calling(mod, fn):
    if mod.parent.name == "p06":
        return p06_tests_calling(mod, fn)
    names = []
    for f in (mod / "vectortests").glob("*_test.go"):
        for chunk in f.read_text().split("\nfunc ")[1:]:
            m = re.match(r"(Test\w+)\(t \*testing\.T\)", chunk)
            if not m:
                continue
            direct = f"vectoradapter.{fn}(" in chunk.split("\n}\n")[0]
            # P/02 wire tests call the actual vector command; select by the adapter's package test prefix.
            via_wire = False
            if (mod / "wirecheck").is_dir():
                import common_vectors
                common = next((n for n, d in common_vectors.DECLS.items() if d["go"] == fn), None)
                prefix = "TestCommon" + common_vectors.camel(common) if common else "Test" + fn + "_"
                via_wire = m[1].startswith(prefix)
            if direct or via_wire:
                names.append(m[1])
    return names


def p06_tests_calling(mod, fn):
    """Canonical P/06: vectors and stand siblings have separate API functions and test prefixes."""
    import common_vectors
    import wire
    from wire_api_p06 import API_P06
    runs, _ = wire.expand(HERE.parent.parent, "06-console")
    active = {r.binding.key for r in runs}
    prefixes = []
    for package, table, surface, name, _ in API_P06:
        if name != fn or (package, table, surface) not in active:
            continue
        prefix = "Test" + common_vectors.camel(package.split("/", 1)[1]) + "_" + common_vectors.camel(table[:-4])
        if surface.startswith("stand:") and (package, table, "vectors") in active:
            prefix += "_Stand"
        prefixes.extend((prefix + "_Line", prefix + "_Lists"))
    for name, d in common_vectors.DECLS.items():
        if d["go"] == fn:
            prefixes.append("TestCommon" + common_vectors.camel(name) + "_")
    return [name for f in (mod / "vectortests").glob("*_test.go")
            for name in re.findall(r"^func (Test\w+)\(t \*testing\.T\)", f.read_text(), re.M)
            if any(name.startswith(prefix) for prefix in prefixes)]


def build(mod, fn, adapter, contracts_src, tmp):
    dst = tmp / f"{mod.parent.name}-{fn}"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(mod, dst)
    module = (dst / "go.mod").read_text().split("\n")[0].split()[1]
    # Preparation includes contracts; replace only this owned module copy so
    # a contract mutant cannot inherit leftover files from the prepared runtime.
    shutil.rmtree(dst / "contracts", ignore_errors=True)
    shutil.copytree(contracts_src, dst / "contracts")
    stub = dst / "vectoradapter" / f"{fn.lower()}.go"
    if stub.exists():
        stub.unlink()
    text = kitside.fill(adapter.read_text(), mod / "vectortests")
    (dst / "vectoradapter" / f"{fn.lower()}_contracts.go").write_text(
        text.replace('"kitmodule/internal/contracts', f'"{module}/contracts'))
    return dst


def run(dst, tests):
    pat = "^(" + "|".join(tests) + ")$"
    done = subprocess.run(["go", "test", "-count=1", "-run", pat, "./vectortests/"], cwd=dst, capture_output=True,
                          text=True, env=GOENV)
    return done


class Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("go"):
            raise unittest.SkipTest("go is not in PATH")
        cls.tmp = Path(tempfile.mkdtemp(prefix="contracts-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_vet(self):
        done = subprocess.run(["gofmt", "-l", str(CONTRACTS), str(ADAPTERS)], capture_output=True, text=True)
        self.assertEqual(done.stdout.strip(), "", "gofmt")

    def test_heartbeat_fresh(self):
        sys.path.insert(0, str(HERE / "contracts/gen"))
        import gen_heartbeat
        for name, text in gen_heartbeat.render().items():
            self.assertEqual((CONTRACTS / "heartbeat" / name).read_text(encoding="utf-8"), text,
                             "run tools/normgen/contracts/gen/gen_heartbeat.py")

    def test_common_heartbeat_sources(self):
        sys.path.insert(0, str(HERE / "contracts/gen"))
        import gen_heartbeat
        root = HERE.parent.parent
        paths = set(gen_heartbeat.sources())
        self.assertIn(root / "Platform/common/data/key-placeholders.tsv", paths)
        self.assertIn(root / "Platform/common/data/outcome-units.tsv", paths)
        self.assertIn(root / "Platform/common/data/cell-json-sha256.tsv", paths)
        self.assertIn(HERE / "tsv_input.py", paths)
        self.assertFalse(any("/common/ru/" in p.as_posix() for p in paths))
        generated = gen_heartbeat.render()["families.go"]
        self.assertIn('const unitField = "field"', generated)
        self.assertTrue('Key: "<sub>/heartbeats/<name>"' in generated, "worker heartbeat selector")
        self.assertTrue('Key: "platform/resources/<server>/heartbeat"' in generated, "resource heartbeat selector")
        self.assertEqual(generated.count('&Family{Key:'), 2)

    def test_vectors(self):
        covered = 0
        for fn, adapter in adapter_fns().items():
            for mod in lesson_mods():
                tests = tests_calling(mod, fn)
                if not tests:
                    continue
                with self.subTest(fn=fn, lesson=mod.parent.name):
                    dst = build(mod, fn, adapter, CONTRACTS, self.tmp)
                    done = run(dst, tests)
                    self.assertEqual(done.returncode, 0, done.stdout[-3000:] + done.stderr[-1000:])
                    self.assertEqual(len(re.findall(r"^--- PASS|^ok ", done.stdout, re.M)) >= 1, True)
                    covered += len(tests)
        self.assertGreater(covered, 0)
        print(f"\ncontracts: {covered} vector tests green over {len(adapter_fns())} adapters", flush=True)


class ContractsKit(unittest.TestCase):
    def test_record_events_kit(self):
        if not shutil.which("go"):
            self.skipTest("go is not in PATH")
        import json
        with tempfile.TemporaryDirectory(prefix="record-events-kit-") as tmp:
            dst = Path(tmp) / "kit"
            done = subprocess.run([sys.executable, str(HERE / "kit/build_kit.py"), str(dst), "--lesson", "06-console",
                                   "--part", "families", "--part", "vectors", "--part", "contracts"],
                                  capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            man = json.loads((dst / "kit.manifest.json").read_text())
            mod = dst / "06-console"
            (mod / "go.mod").write_text(f"module {man['module']}\n\ngo 1.22\n")
            done = subprocess.run(["go", "test", "-count=1", "-run", "^Test(Record|EventsMerge)_",
                                   "./internal/vectortests/"], cwd=mod, capture_output=True, text=True, env=GOENV)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_heartbeat_kit(self):
        """A foreign-family reader in a controller kit: nested files, import rewriting, and actual vector calls."""
        if not shutil.which("go"):
            self.skipTest("go is not in PATH")
        with tempfile.TemporaryDirectory(prefix="heartbeat-kit-") as tmp:
            dst = Path(tmp) / "kit"
            done = subprocess.run([sys.executable, str(HERE / "kit/build_kit.py"), str(dst), "--lesson", "04-controller",
                                   "--part", "families", "--part", "vectors", "--part", "contracts"],
                                  capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            import json
            man = json.loads((dst / "kit.manifest.json").read_text())
            paths = {f["path"]: f for f in man["files"]}
            for name in ("families.go", "runtime.go", "read.go"):
                self.assertIn(f"04-controller/internal/contracts/heartbeat/{name}", paths)
            self.assertIn("ReadWorker", (dst / "KIT.md").read_text())
            mod = dst / "04-controller"
            (mod / "go.mod").write_text(f"module {man['module']}\n\ngo 1.22\n")
            done = subprocess.run(["go", "test", "-count=1", "-run", "^TestHeartbeatRead_", "./internal/vectortests/"],
                                  cwd=mod, capture_output=True, text=True, env=GOENV)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_kit_part(self):
        """build_kit --part contracts: internal/contracts and its adapters replace stubs; table tests must pass."""
        import json
        import sys
        if not shutil.which("go"):
            self.skipTest("go is not in PATH")
        with tempfile.TemporaryDirectory(prefix="contracts-kit-") as tmp:
            dst = Path(tmp) / "kit"
            done = subprocess.run([sys.executable, str(HERE / "kit/build_kit.py"), str(dst), "--lesson", "03-worker",
                                   "--part", "families", "--part", "vectors", "--part", "contracts"],
                                  capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            man = json.loads((dst / "kit.manifest.json").read_text())
            paths = {f["path"]: f for f in man["files"]}
            self.assertIn("03-worker/internal/contracts/instance.go", paths)
            fns = adapter_fns()
            for fn in fns:
                f = paths.get(f"03-worker/internal/vectoradapter/{fn.lower()}.go")
                if f:
                    self.assertTrue(f.get("editable"), fn)
                    self.assertTrue(f["source"].startswith("tools/normgen/contracts/adapters/"), f["source"])
            mod = dst / "03-worker"
            (mod / "go.mod").write_text(f"module {man['module']}\n\ngo 1.22\n")
            done = subprocess.run(["go", "test", "-count=1", "-run", "|".join(fns), "./internal/vectortests/"], cwd=mod,
                                  capture_output=True, text=True, env=GOENV)
            self.assertEqual(done.returncode, 0, done.stdout[-2000:])


NFKC_MAIN = """package main

import (
	"bufio"
	"encoding/json"
	"os"

	"nfkcjudge/contracts"
)

func main() {
	sc := bufio.NewScanner(os.Stdin)
	sc.Buffer(make([]byte, 1<<20), 1<<20)
	w := bufio.NewWriter(os.Stdout)
	for sc.Scan() {
		var s string
		if json.Unmarshal(sc.Bytes(), &s) != nil {
			os.Exit(2)
		}
		b, _ := json.Marshal(contracts.NFKC(s))
		w.Write(append(b, '\\n'))
	}
	w.Flush()
}
"""


class Heartbeat(unittest.TestCase):
    def test_mixed_outcomes(self):
        """Field priority 0 must not hide a whole-object error or a status error at another path."""
        if not shutil.which("go"):
            self.skipTest("go is not in PATH")
        src = r'''package heartbeat
import ("testing"; "strings"; "sync")
func TestMixed(t *testing.T) {
    worker := `{"worker":"w-1","ts":100,"status":[{"id":"c1","phase":"running","epoch":1,"revision":1,"observed_revision":1}],"server":"srv-a","instance":"box-a:1:aaaaaa","build":7}`
    key := "testsub/heartbeats/w-1"
    whole := strings.Replace(worker, `,"instance":"box-a:1:aaaaaa"`, "", 1)
    if got := ReadWorker(key, []byte(whole)); got.Rows != "unreadable" || got.Others != "unreadable" || len(got.Fields) != 0 { t.Fatalf("whole: %#v", got) }
    element := strings.Replace(worker, `,"phase":"running"`, "", 1)
    got := ReadWorker(key, []byte(element))
    rows, ok := got.Rows.(RowItems)
    if !ok || len(rows.Skip) != 1 || rows.Skip[0] != 0 || got.Others != "unreadable" || len(got.Fields) != 0 { t.Fatalf("element: %#v", got) }
    resource := `{"ts":100,"url":"http://127.0.0.1:8090","schema":1,"build":5,"usage":0,"usage_at":100,"space":{"total":1000,"free":900,"used":100,"full":0.1},"volumes":{},"units":{},"mirrors":{},"short":0,"door":{"addr":"127.0.0.1:8090","mode":"loopback"},"waits":{"waiting":0,"held":0,"full":0,"replaced":0,"max":16},"restore":{},"mirror":{"skipped":0,"failed":0,"peer_errors":0,"lines_garbled":0}}`
    validResource := strings.Replace(resource, `{`, `{"server":"srv-a",`, 1)
    if got := ReadResource("platform/resources/srv-a/heartbeat", []byte(validResource)); !got.Readable || len(got.Fields) != 1 || got.Fields[0] != "build" { t.Fatalf("resource baseline: %#v", got) }
    if got := ReadResource("platform/resources/srv-a/heartbeat", []byte(resource)); got.Readable { t.Fatalf("resource without server: %#v", got) }
    var wg sync.WaitGroup
    for i := 0; i < 8; i++ { wg.Add(1); go func() { defer wg.Done(); for j := 0; j < 10; j++ { ReadWorker(key, []byte(worker)); ReadResource("platform/resources/srv-a/heartbeat", []byte(resource)) } }() }
    wg.Wait()
}
'''
        with tempfile.TemporaryDirectory(prefix="heartbeat-mixed-") as tmp:
            dst = Path(tmp)
            (dst / "go.mod").write_text("module heartbeatjudge\n\ngo 1.22\n")
            shutil.copytree(CONTRACTS, dst / "contracts")
            (dst / "contracts/heartbeat/mixed_test.go").write_text(src)
            done = subprocess.run(["go", "test", "-race", "-count=1", "./contracts/heartbeat/"], cwd=dst,
                                  capture_output=True, text=True, env=GOENV)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_mutant(self):
        """The common vectors reject a reader that ignores whole-object outcomes."""
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        if not shutil.which("go"):
            self.skipTest("go is not in PATH")
        mod = OUT / "p04/go"
        with tempfile.TemporaryDirectory(prefix="heartbeat-mutant-") as tmp:
            dst = build(mod, "HeartbeatRead", ADAPTERS / "heartbeatread.go", CONTRACTS, Path(tmp))
            path = dst / "contracts/heartbeat/read.go"
            text = path.read_text()
            self.assertIn('if active[""] {', text)
            path.write_text(text.replace('if active[""] {', 'if false {', 1))
            done = run(dst, tests_calling(mod, "HeartbeatRead"))
            self.assertNotEqual(done.returncode, 0)
            self.assertIn("--- FAIL: TestHeartbeatRead_", done.stdout, done.stdout + done.stderr)
            self.assertNotIn("panic:", done.stdout)


class RecordEvents(unittest.TestCase):
    def test_mutants(self):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        if not shutil.which("go"):
            self.skipTest("go is not in PATH")
        mutations = [("Record", "p08", "record.go", "!ed25519.Verify(", "false && !ed25519.Verify("),
                     ("EventsMerge", "p06", "eventsmerge.go", "if former.Cmp(epoch) < 0 {", "if former.Cmp(epoch) > 0 {"),
                     ("EventsMerge", "p05", "eventsmerge.go", "t >= q.To", "t > q.To")]
        with tempfile.TemporaryDirectory(prefix="record-events-mutants-") as tmp:
            for fn, lesson, name, old, new in mutations:
                with self.subTest(fn=fn, lesson=lesson):
                    mod = OUT / lesson / "go"
                    dst = build(mod, fn, ADAPTERS / f"{fn.lower()}.go", CONTRACTS, Path(tmp))
                    path = dst / "contracts" / name
                    text = path.read_text()
                    self.assertIn(old, text)
                    path.write_text(text.replace(old, new, 1))
                    done = run(dst, tests_calling(mod, fn))
                    self.assertNotEqual(done.returncode, 0)
                    self.assertIn(f"--- FAIL: Test{fn}_", done.stdout, done.stdout + done.stderr)
                    self.assertNotIn("panic:", done.stdout)

    def test_canonical_golden(self):
        """The actual contracts signer uses every RFC 8785 golden row, including 1e21 and UTF-16 ordering."""
        if not shutil.which("go"):
            self.skipTest("go is not in PATH")
        import hashlib
        source = HERE.parents[1] / "Platform/01-store/vectors/jcs/canonical_json.tsv"
        vectors = [line.split("\t") for line in source.read_text().split("\n") if line and not line.startswith("#")]
        main = r'''package main
import ("bufio"; "encoding/json"; "fmt"; "os"; "strings"; "canonicaljudge/contracts")
func main() {
    sc := bufio.NewScanner(os.Stdin)
    sc.Buffer(make([]byte, 1<<20), 1<<20)
    for sc.Scan() {
        dec := json.NewDecoder(strings.NewReader(sc.Text())); dec.UseNumber()
        var v any
        if dec.Decode(&v) != nil { os.Exit(2) }
        fmt.Println(contracts.CanonicalJSON(v))
    }
    if sc.Err() != nil { os.Exit(2) }
}
'''
        with tempfile.TemporaryDirectory(prefix="contracts-jcs-") as tmp:
            dst = Path(tmp)
            (dst / "go.mod").write_text("module canonicaljudge\n\ngo 1.22\n")
            shutil.copytree(CONTRACTS, dst / "contracts")
            (dst / "main.go").write_text(main)
            done = subprocess.run(["go", "run", "."], input="\n".join(v[0] for v in vectors) + "\n", cwd=dst,
                                  capture_output=True, text=True, env=GOENV)
            self.assertEqual(done.returncode, 0, done.stderr)
            got = done.stdout.split("\n")[:-1]
            self.assertEqual(got, [v[1] for v in vectors])
            self.assertEqual([hashlib.sha256(v.encode()).hexdigest() for v in got], [v[2] for v in vectors])

    def test_boundaries(self):
        if not shutil.which("go"):
            self.skipTest("go is not in PATH")
        src = r'''package contracts
import ("bytes"; "crypto/ed25519"; "encoding/base64"; "encoding/hex"; "encoding/json"; "fmt"; "testing")
func TestSignedJCS(t *testing.T) {
    key := ed25519.NewKeyFromSeed(bytes.Repeat([]byte{1},32))
    pub := hex.EncodeToString(key.Public().(ed25519.PublicKey)); kid := pub[:16]
    keys := map[string]any{"domain":"acme","issuing":[]any{kid},"revoked_issuing":[]any{}}
    doc := map[string]any{"domain":"acme","term":json.Number("1"),"holder":"m1","url":"http://x","at":json.Number("1e21"),"issuer":pub}
    // Expected signing bytes are independent of the contracts encoder.
    signed := fmt.Sprintf(`{"at":1e+21,"domain":"acme","holder":"m1","issuer":"%s","term":1,"url":"http://x"}`,pub)
    doc["kid"],doc["sig"] = kid,base64.RawURLEncoding.EncodeToString(ed25519.Sign(key,[]byte(signed)))
    text,_ := json.Marshal(doc); row := map[string]any{"doc":string(text)}
    if got:=Record(keys,row,TermRecord); got.Result!="ok" { t.Fatalf("signed JCS: %#v",got) }
    if got:=Record(keys,row,BackupRecord); got.Reason!="not_a_record" { t.Fatalf("foreign kind: %#v",got) }
    for _,bad := range []string{string(text)+"?",`{"x":1,"x":2}`,`{"x":"\ud800"}`,`{"x":"`+string([]byte{0xff})+`"}`} {
        if got:=Record(keys,map[string]any{"doc":bad},TermRecord); got.Reason!="not_a_record" { t.Fatalf("malformed text: %#v",got) }
    }
    for _,valid := range []string{`{"x":"\\ud800"}`,`{"x":"\ud83d\ude00"}`} {
        if _,ok:=strictJSONObject([]byte(valid)); !ok { t.Fatalf("valid Unicode rejected: %s",valid) }
    }
    doc["at"]=json.Number("1e309"); text,_=json.Marshal(doc)
    if got:=Record(keys,map[string]any{"doc":string(text)},TermRecord); got.Reason!="not_a_record" { t.Fatalf("overflow: %#v",got) }
}
func TestTakeOrder(t *testing.T) {
    makeRow := func(seed byte, term string) (map[string]any,string) {
        key:=ed25519.NewKeyFromSeed(bytes.Repeat([]byte{seed},32)); pub:=hex.EncodeToString(key.Public().(ed25519.PublicKey))
        doc:=map[string]any{"domain":"acme","term":json.Number(term),"rev":json.Number("3"),"part":"3232","members":map[string]any{},"issuer":pub}
        sig:=ed25519.Sign(key,[]byte(CanonicalJSON(doc))); doc["kid"],doc["sig"]=pub[:16],base64.RawURLEncoding.EncodeToString(sig)
        text,_:=json.Marshal(doc); return map[string]any{"doc":string(text)},pub[:16]
    }
    row,kid:=makeRow(1,"2"); have,old:=makeRow(2,"2")
    keys:=map[string]any{"domain":"acme","issuing":[]any{kid},"revoked_issuing":[]any{old}}
    if got:=TakeMemberRecord(keys,row,"3232",have); got.Result!="same" { t.Fatalf("equality precedes revoked bound: %#v",got) }
    row,_=makeRow(1,"1")
    if got:=TakeMemberRecord(keys,row,"3232",have); got.Result!="take" { t.Fatalf("revoked greater bound: %#v",got) }
}
func TestEventsEdges(t *testing.T) {
    row:=`{"id":"a","subsystem":"testsub","unit":"testsub/c9","of":"testsub/c1","epoch":1,"t":10,"occurred":1,"kind":"tick","server":"srv-b","bucket":"testsub/c9/e1/x","class":"observation"}`
    input:=`{"participant":"console","grant":["unit:testsub/c9"],"units":{"testsub/c1":"@unreadable"},"epochs":{"testsub":{"c9":1}},"resources":{"srv-a":{"events":[`+row+`,{"id":"broken"}],"state":"live","truncated":0,"partial":true,"lines_garbled":2},"srv-b":"silent"}}`
    out,err:=MergeEvents([]byte(input))
    if err!=nil || len(out["events"].([]map[string]any))!=1 || out["withheld"]!=nil || out["partial"]!=true || out["lines_garbled"]!=json.Number("3") || out["state"]!="live; srv-b unreachable; srv-b from mirror" { t.Fatalf("merge edges: %#v %v",out,err) }
    resource:=`{"events":[`+row+`],"query":{"by":"occurred","from":1,"to":5,"late":5}}`
    cut,err:=FilterResourceEvents([]byte(resource))
    if err!=nil || len(cut["events"].([]map[string]any))!=1 { t.Fatalf("late equality: %#v %v",cut,err) }
    negativeFrom:=`{"events":[`+row+`],"query":{"from":-1,"to":20}}`
    cut,err=FilterResourceEvents([]byte(negativeFrom))
    if err!=nil || len(cut["events"].([]map[string]any))!=1 { t.Fatalf("negative from (P/05-R022): %#v %v",cut,err) }
    negativeWindow:=`{"events":[`+row+`],"query":{"from":-10,"to":-1}}`
    cut,err=FilterResourceEvents([]byte(negativeWindow))
    if err!=nil || len(cut["events"].([]map[string]any))!=0 { t.Fatalf("negative to (P/05-R022): %#v %v",cut,err) }
    fractionalLate:=`{"events":[],"query":{"by":"occurred","late":100.00000000000000001}}`
    if _,err:=FilterResourceEvents([]byte(fractionalLate)); err==nil { t.Fatal("fractional late rounded into an integer") }
    hidden:=`{"participant":"console","grant":[],"epochs":{"testsub":"did not answer"},"resources":{"srv-a":{"events":[`+row+`],"state":"live","truncated":0}}}`
    out,err=MergeEvents([]byte(hidden))
    if err!=nil || out["complete"]!=false || len(out["events"].([]map[string]any))!=0 || out["incomplete"].(map[string]string)["testsub/epoch"]!="did not answer" { t.Fatalf("hidden failed epoch: %#v %v",out,err) }
    large:=`{"participant":"console","resources":{"srv-a":{"events":[],"state":"live","truncated":9007199254740992},"srv-b":{"events":[],"state":"live","truncated":1}}}`
    out,err=MergeEvents([]byte(large))
    if err!=nil || out["truncated"]!=json.Number("9007199254740993") { t.Fatalf("exact counter: %#v %v",out,err) }
}
'''
        with tempfile.TemporaryDirectory(prefix="record-events-boundaries-") as tmp:
            dst = Path(tmp)
            (dst / "go.mod").write_text("module boundaries\n\ngo 1.22\n")
            shutil.copytree(CONTRACTS, dst / "contracts")
            (dst / "contracts/boundaries_test.go").write_text(src)
            done = subprocess.run(["go", "test", "-count=1", "./contracts/"], cwd=dst,
                                  capture_output=True, text=True, env=GOENV)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


class NFKC(unittest.TestCase):
    """Package NFKC (address contract A4, Unicode 15.0.0 tables): gen_nfkc.py table freshness and equality with
    Python 3.12 unicodedata.normalize("NFKC") (Unicode 15.0.0), for every code point and random sequences of
    noncombining characters, composites, Hangul and marks."""

    def test_tables_fresh(self):
        import sys
        sys.path.insert(0, str(HERE / "contracts/gen"))
        import gen_nfkc
        self.assertEqual((CONTRACTS / "nfkc_tables.go").read_text(encoding="utf-8"), gen_nfkc.render(),
                         "run tools/normgen/contracts/gen/gen_nfkc.py")

    def test_equals_unicodedata(self):
        import json
        import random
        import unicodedata
        if not shutil.which("go"):
            self.skipTest("go is not in PATH")
        self.assertEqual(unicodedata.unidata_version, "15.0.0")
        rnd = random.Random(7)
        cps = [c for c in range(0x110000) if not 0xD800 <= c < 0xE000]
        marks = [c for c in cps if unicodedata.combining(chr(c))]
        composed = [c for c in cps if unicodedata.decomposition(chr(c))]
        pools = [marks, composed, cps[:0x3000], range(0x1100, 0x1200), range(0xAC00, 0xAC40)]
        inputs = [chr(c) for c in cps]
        inputs += ["".join(chr(rnd.choice(rnd.choice(pools))) for _ in range(rnd.randint(2, 6)))
                   for _ in range(100000)]
        with tempfile.TemporaryDirectory(prefix="contracts-nfkc-") as tmp:
            mod = Path(tmp)
            (mod / "go.mod").write_text("module nfkcjudge\n\ngo 1.22\n")
            shutil.copytree(CONTRACTS, mod / "contracts")
            (mod / "main.go").write_text(NFKC_MAIN)
            done = subprocess.run(["go", "run", "."], cwd=mod, input="\n".join(json.dumps(s) for s in inputs) + "\n",
                                  capture_output=True, text=True, env=GOENV)
        self.assertEqual(done.returncode, 0, done.stderr[-2000:])
        got = done.stdout.split("\n")[:-1]
        self.assertEqual(len(got), len(inputs))
        bad = [(s, g) for s, g in zip(inputs, got) if json.loads(g) != unicodedata.normalize("NFKC", s)]
        self.assertEqual(bad[:5], [], f"{len(bad)} of {len(inputs)} differ")


if __name__ == "__main__":
    unittest.main()
