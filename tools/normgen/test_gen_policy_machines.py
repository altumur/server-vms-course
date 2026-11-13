"""Independent judge of P/03 declarative policy generation and packaging.

The approved machine checker is an oracle only in this judge. Production code
does not import it. Trace mutants must fail the original closed tests; random
valid event streams are compared with the independently implemented reference.
"""
import lesson as output_lesson
import copy
import hashlib
import importlib.util
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

import gen_policy_machines as gen
from test_gen_machine import CheckingError, complete_reports, complete_go_tests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
GOENV = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off", GOTOOLCHAIN="local")
FORMS = ROOT / gen.LESSON / "forms"


def oracle():
    path = ROOT / "skills/lesson-spec/scripts/check_machines.py"
    spec = importlib.util.spec_from_file_location("policy_reference", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_module(dst, files=None):
    dst = Path(dst)
    for rel, text in (files or gen.build()).items():
        p = dst / rel[3:]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    for n, data in gen.module_files("normgen/p03").items():
        (dst / n).write_bytes(data)


DRIVER = r'''package main
import("bufio";"encoding/json";"fmt";"os"; p "normgen/p03/workerpolicy")
type event struct { T float64 `json:"t"`; Name string `json:"name"`; Payload json.RawMessage `json:"payload"` }
type request struct { Case int `json:"case"`; Name string `json:"name"`; IR json.RawMessage `json:"ir"`; Input json.RawMessage `json:"input"`; At float64 `json:"at"`; Events []event `json:"events"` }
func main(){s:=bufio.NewScanner(os.Stdin); s.Buffer(make([]byte,4096),8<<20); for s.Scan(){ var q request; if e:=json.Unmarshal(s.Bytes(),&q);e!=nil{panic(e)}; var r *p.Run;var e error
if len(q.IR)>0 {var prog *p.Program;prog,e=p.Compile(q.IR); if e==nil{r,e=prog.New(q.Input,q.At)}}else{r,e=p.Open(q.Name,q.Input,q.At)}
obs:=[]p.Observation{}; if e==nil{obs=append(obs,r.Snapshot()); for _,ev:=range q.Events{var o p.Observation;o,e=r.Step(ev.T,ev.Name,ev.Payload);if e!=nil{break};obs=append(obs,o)}}
msg:="";if e!=nil{msg=e.Error()}; b,_:=json.Marshal(map[string]any{"case":q.Case,"observations":obs,"error":msg});fmt.Println(string(b)) };if e:=s.Err();e!=nil{panic(e)}}
'''


class PolicyMachines(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("go"):
            raise unittest.SkipTest("go not found")
        cls.tmp = tempfile.TemporaryDirectory(prefix="policy-judge-")
        cls.mod = Path(cls.tmp.name)
        write_module(cls.mod)
        (cls.mod / "cmd/driver").mkdir(parents=True)
        (cls.mod / "cmd/driver/main.go").write_text(DRIVER)
        cls.exe = cls.mod / "driver"
        done = subprocess.run(["go", "build", "-o", str(cls.exe), "./cmd/driver"], cwd=cls.mod, env=GOENV,
                              capture_output=True, text=True)
        if done.returncode:
            cls.tmp.cleanup()
            raise AssertionError(done.stdout + done.stderr)
        cls.ref = oracle()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_driver(self, queries):
        done = subprocess.run([str(self.exe)], input="".join(json.dumps(dict(q, case=i)) + "\n" for i, q in enumerate(queries)),
                              capture_output=True, text=True)
        if done.returncode:
            raise CheckingError("policy driver failed: " + done.stderr)
        return complete_reports(done.stdout, len(queries))

    def test_driver_missing_partial_duplicate_and_failed_reports_are_checking_errors(self):
        from unittest.mock import patch
        queries = [{"name": "token-cache", "input": {}, "events": []}] * 2
        samples = [(0, ''), (0, '{"case":0}\n'), (0, '{"case":0}\n{"case":0}\n'),
                   (0, '{"case":0}\n{"case":1}\n{"case":2}\n'), (1, '')]
        for code, text in samples:
            done = subprocess.CompletedProcess([], code, text, "driver failed" if code else "")
            with self.subTest(code=code, text=text), patch.object(subprocess, "run", return_value=done), self.assertRaises(CheckingError):
                self.run_driver(queries)

    def test_driver_lf_reports_preserve_unicode_separators(self):
        from unittest.mock import patch
        for separator in ("\u0085", "\u2028", "\u2029"):
            value = "left" + separator + "right"
            stdout = json.dumps({"case": 0, "observations": [value], "error": ""}, ensure_ascii=False) + "\n"
            done = subprocess.CompletedProcess([], 0, stdout, "")
            with self.subTest(separator=repr(separator)), patch.object(subprocess, "run", return_value=done):
                self.assertEqual(self.run_driver([{"name": "token-cache"}]),
                                 [{"observations": [value], "error": ""}])

    def test_fresh_and_declared_traces(self):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        for rel, text in gen.build().items():
            self.assertEqual((output_lesson.output_root() / 'p03' / rel).read_text(), text, rel)
        for name, data in gen.module_files("normgen/p03").items():
            self.assertEqual((output_lesson.output_root() / 'p03/go' / name).read_bytes(), data)
        done = subprocess.run(["go", "test", "-count=1", "-json", "./workerpolicy"], cwd=self.mod, env=GOENV,
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        cases = [json.loads(s) for s in done.stdout.split("\n") if s]
        self.assertEqual(sum(e.get("Action") == "pass" and e.get("Test", "").count("/") == 1 for e in cases), 2)
        self.assertEqual(sum(len([r for r in (FORMS / (part + ".traces.tsv")).read_text().split("\n")[1:] if r]) for part in gen.PARTS),104)

    def test_oracle_random_events_and_exact_integers(self):
        rng = random.Random(0x503122)
        queries, expected = [], []
        for part in gen.PARTS:
            machine = self.ref.Machine(FORMS / (part + ".machine.yaml"))
            self.assertFalse(machine.errors, machine.errors)
            for _ in range(35):
                run = self.ref.Run(machine, {})
                events, observations = [], [{"state": run.state, "vars": copy.deepcopy(run.vars), "io": []}]
                for i in range(65):
                    kind = rng.choice(list(machine.doc["events"]))
                    payload = {}
                    for key, typ in machine.doc["events"][kind].items():
                        if typ == "bool": value = rng.choice([False, True])
                        elif typ == "double": value = rng.choice([-100.5, 0, 100.5, 90, 100])
                        elif typ == "int": value = rng.choice([-1, 0, 1, 2, 9007199254740993, 2**63-1])
                        else: value = rng.choice(["", "H1", "H2", "J1", "J2", "x;\u2028\U0001f600"])
                        payload[key] = value
                    # Keep receiver facts legal with respect to invariants. Failed
                    # model steps are discarded by replaying the accepted prefix.
                    candidate = copy.copy(run)
                    candidate.vars = copy.deepcopy(run.vars)
                    candidate.violations = []
                    candidate.did = []
                    candidate.external(i+1, kind, payload)
                    if candidate.violations:
                        continue
                    run = candidate
                    events.append({"t": i+1, "name": kind, "payload": payload})
                    ios = []
                    for line in run.did:
                        if line.startswith("io "):
                            name, text = line[3:].split(" ", 1)
                            ios.append([name, json.loads(text)])
                    observations.append({"state": run.state, "vars": copy.deepcopy(run.vars), "io": ios})
                queries.append({"name": part, "input": {}, "events": events})
                expected.append(observations)
        for i, (got, want) in enumerate(zip(self.run_driver(queries), expected)):
            self.assertEqual(got["error"], "", f"stream {i}: {got['error']}")
            self.assertEqual(got["observations"], want, f"stream {i}")

    def test_seven_policy_mutants_are_killed_by_original_traces(self):
        # These are semantic changes, not a mirror of implementation branches.
        mutations = [
            ("contender-writer", "choose-refused-first", "if", "withdrawn"),
            ("contender-writer", "publish-when-due", "if", "!withdrawn"),
            ("contender-writer", "back-only-after-loss", "do", ["mark_acquired()"]),
            ("contender-writer", "lost-once", "do", ["mark_lost()"]),
            ("token-cache", "unknown-key-current-waits", "do", ['request("")']),
            ("token-cache", "persist-after-first-accept", "do", ["promote()"]),
            ("token-cache", "blocked-through-this-day", "if", "day < blocked_day"),
        ]
        original = (self.mod / "workerpolicy/programs.go").read_text()
        try:
            for part, tid, key, value in mutations:
                with self.subTest(machine=part, transition=tid):
                    doc = yaml.safe_load((FORMS / (part + ".machine.yaml")).read_text())
                    next(t for t in doc["transitions"] if t["id"] == tid)[key] = value
                    ir = gen.model(doc)
                    old = gen.load(FORMS / (part + ".machine.yaml"))
                    from gen_checks import go_str
                    patched = original.replace(go_str(json.dumps(old, ensure_ascii=False, separators=(",", ":"))),
                                               go_str(json.dumps(ir, ensure_ascii=False, separators=(",", ":"))))
                    self.assertNotEqual(patched, original)
                    (self.mod / "workerpolicy/programs.go").write_text(patched)
                    done = subprocess.run(["go", "test", "-json", "-count=1", "-run", "TestDeclaredTraces/" + part,
                                           "./workerpolicy"], cwd=self.mod, env=GOENV, capture_output=True, text=True)
                    failed = complete_go_tests(done, {"TestDeclaredTraces", "TestDeclaredTraces/" + part},
                                               "normgen/p03/workerpolicy")
                    self.assertTrue(failed, "policy mutant survives the original declared traces")
        finally:
            (self.mod / "workerpolicy/programs.go").write_text(original)

    def test_invalid_forms_and_unreachable_cel(self):
        original = yaml.safe_load((FORMS / "contender-writer.machine.yaml").read_text())
        patches = [lambda d: d.update(extra={}), lambda d: d["vars"]["since"].update(type="ghost"),
                   lambda d: d["transitions"][0].update(to="ghost"),
                   lambda d: d["transitions"][0].update(do=["publish(1)"]),
                   lambda d: d["actions"]["publish"].update(io=True),
                   lambda d: d["actions"].update(unused={"set": {"since": "not_declared + 1"}}),
                   lambda d: d["transitions"].append({"id": "unreachable", "event": "lost", "from": "quiet", "if": "?"})]
        for patch in patches:
            doc = copy.deepcopy(original)
            patch(doc)
            with self.assertRaises(gen.GenError):
                gen.model(doc)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad.yaml"
            p.write_text("machine: one\nmachine: two\n")
            with self.assertRaises(gen.GenError): gen.load(p)

    def test_strict_payloads_and_clocks(self):
        payloads = ['{"withdrawn":false,"foreign":false,"due":true,"wall":true}',
                    '{"withdrawn":false,"foreign":false,"due":true}',
                    '{"withdrawn":false,"foreign":false,"due":true,"wall":1,"extra":0}']
        queries = [{"name": "contender-writer", "input": {}, "events": []}]
        # raw malformed semantic JSON requires the Go unit test below; the driver
        # transport itself is valid JSON and must not silently normalize it.
        for payload in payloads:
            queries.append({"name": "contender-writer", "input": {}, "events": [{"t": 1, "name": "observe", "payload": json.loads(payload)}]})
        queries += [{"name": "token-cache", "input": {}, "events": [{"t": 1,"name": "demand","payload": {"day": d}}]} for d in [1.0, 2**63, True]]
        queries += [{"name": "token-cache", "input": {}, "events": [{"t": -1,"name":"demand","payload":{"day":1}}]},
                    {"name": "token-cache", "input": {"const":{"UNKNOWN":1}}, "events": []}]
        results = self.run_driver(queries)
        self.assertFalse(results[0]["error"])
        self.assertTrue(all(r["error"] for r in results[1:]), results)

    def test_trace_validation_keeps_first_row_and_unicode(self):
        ir = gen.load(FORMS / "token-cache.machine.yaml")
        handle = 'opaque;"\\\u2028\U0001f600'
        rows = ["# a comment", "trace\tstep\tt\tevent\texpect",
                "unicode\t0\t0\tinput {}\tstate=loading; io=[]",
                "unicode\t1\t1\tloaded " + json.dumps({"opened": True, "handle": handle, "jti": "J"}, ensure_ascii=False)
                + '\tstate=ready; var.current_handle=' + json.dumps(handle, ensure_ascii=False),
                'unicode\t2\t2\tdemand {"day":1}\tio=' + json.dumps([["offer", [handle]]], ensure_ascii=False)]
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "trace.tsv"
            text = "\n".join(rows) + "\n"
            p.write_text(text)
            parsed = gen.trace_rows(p, ir)
            self.assertEqual(len(parsed), 3)
            self.assertEqual(parsed[0]["line"], 3)
            self.assertEqual(parsed[-1]["expect"], rows[-1].split("\t")[-1])
            for old, new in [('unicode\t0\t0', 'unicode\t1\t0'),
                             ('loaded {"opened": true', 'loaded {"extra":0,"opened": true'),
                             ('demand {"day":1}', 'demand {"day":1,"day":2}'),
                             ('io=[["offer",', 'io=[["wait",')]:
                p.write_text(text.replace(old, new))
                with self.assertRaises(gen.GenError):
                    gen.trace_rows(p, ir)

    def test_kit_offline_closed_files_and_editable_sdk(self):
        with tempfile.TemporaryDirectory(prefix="policy-kit-") as tmp:
            dst = Path(tmp) / "kit"
            command = [sys.executable, str(HERE / "kit/build_kit.py"), str(dst), "--lesson", "03-worker",
                       "--module", "example.com/policy/03-worker", "--part", "stagetests", "--part", "slot-capture"]
            done = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            manifest = json.loads((dst / "kit.manifest.json").read_text())
            self.assertEqual(manifest["parts"], ["slot-capture", "stagetests"])
            for entry in manifest["files"]:
                self.assertEqual(hashlib.sha256((dst / entry["path"]).read_bytes()).hexdigest(), entry["sha256"])
                if "/workerpolicy/" in entry["path"] or "/vendor/" in entry["path"]:
                    self.assertFalse(entry.get("editable"), entry["path"])
            sources = {f["path"]: f["sha256"] for f in manifest["provenance"]["stagetests"]["form"]}
            for p in gen.sources():
                self.assertEqual(sources[str(p.relative_to(ROOT))], hashlib.sha256(p.read_bytes()).hexdigest())
            mod = dst / "03-worker"
            self.assertIn("github.com/google/cel-go v0.26.1", (mod / "go.mod").read_text())
            self.assertIn("github.com/google/cel-go v0.26.1", (mod / "vendor/modules.txt").read_text())
            env = dict(GOENV, GOFLAGS="-mod=vendor", GOMODCACHE=str(Path(tmp) / "empty-module-cache"))
            for args in (["vet", "./..."], ["build", "./..."], ["test", "-race", "-count=1", "./internal/workerpolicy", "./internal/slotcapture"]):
                done = subprocess.run(["go", *args], cwd=mod, env=env, capture_output=True, text=True)
                self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            # Closed policy green is separate from actual stage acceptance.
            done = subprocess.run(["go", "test", "-json", "-count=1", "./internal/stagetests"], cwd=mod,
                                  env=env, capture_output=True, text=True)
            self.assertNotEqual(done.returncode, 0)
            self.assertNotIn("panic:", done.stdout + done.stderr)
            events = [json.loads(s) for s in done.stdout.split("\n") if s]
            self.assertEqual(sum(e.get("Action") == "fail" and bool(e.get("Test")) for e in events), 88)
            self.assertFalse(any(e.get("Action") == "skip" for e in events))
            sdk = next(p for p in (mod / "internal/lessonadapter").glob("*.go") if p.name != "lessonadapter.go")
            sdk.write_text(sdk.read_text() + "\n// preserved SDK edit\n")
            mod_file = mod / "go.mod"
            mod_file.write_text(mod_file.read_text() + "\n// preserved module edit\n")
            expected_sdk, expected_mod = sdk.read_bytes(), mod_file.read_bytes()
            runtime = mod / "internal/workerpolicy/run.go"
            runtime.write_text("invalid closed edit\n")
            done = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(sdk.read_bytes(), expected_sdk)
            self.assertEqual(mod_file.read_bytes(), expected_mod)
            self.assertEqual(runtime.read_bytes(), (gen.RUNTIME / "run.go").read_bytes())

    def test_declared_timers_records_and_simultaneous_set(self):
        doc = dict(machine="timer-check", norm="test", states=["live", "done"], initial="live", terminal=["done"],
                   input={"record": "Rec"}, types={"Rec": {"x": "int|string", "ys": "list<int>"}},
                   const={"PERIOD": 2}, vars={"n": {"type": "int", "init": 0},
                       "a": {"type": "int", "init": 9007199254740993}, "b": {"type": "int", "init": 7}},
                   timers={"period": {"every": "PERIOD", "event": "tick", "payload": {"tag": '"period"'}},
                           "delayed": {"after": 0, "after_io": "offer", "event": "ack", "payload": {"tag": "tag"}}},
                   events={"tick": {"tag": "string"}, "ack": {"tag": "string"}, "swap": {}, "finish": {}, "send": {"tag": "string"}},
                   env=[], functions={"same_set": {}},
                   actions={"swap": {"set": {"a": "b", "b": "a"}}, "count": {"set": {"n": "n+1"}},
                            "offer": {"args": {"tag": "string"}, "io": "intent"},
                            "log": {"args": {"tag": "string", "n": "int"}, "io": "intent"}},
                   invariants={"positive": "n>=0", "same": 'same_set(["a","b"],["b","a"])'},
                   transitions=[{"id": "tick", "event": "tick", "do": ["count()", "log(tag,n)"], "stop": True},
                                {"id": "ack", "event": "ack", "do": ["log(tag,n)"]},
                                {"id": "swap", "event": "swap", "do": ["swap()"]},
                                {"id": "send", "event": "send", "do": ["offer(tag)", "offer(tag)"]},
                                {"id": "finish", "event": "finish", "to": "done"}])
        events = [{"t": 0, "name": "swap", "payload": {}}, {"t": 1, "name": "send", "payload": {"tag": "ack;\u2028"}},
                  {"t": 4, "name": "advance"}, {"t": 5, "name": "finish", "payload": {}},
                  {"t": 8, "name": "swap", "payload": {}}]
        inp = {"record": {"x": "9007199254740993", "ys": [0, 9007199254740993, 2**63-1]}}
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "model.machine.yaml"
            p.write_text(yaml.safe_dump(doc, sort_keys=False))
            machine = self.ref.Machine(p)
            self.assertFalse(machine.errors, machine.errors)
            run = self.ref.Run(machine, inp)
            expected = [{"state": run.state, "vars": copy.deepcopy(run.vars), "io": []}]
            for ev in events:
                run.did = []
                run.external(ev["t"], ev["name"], ev.get("payload", {}))
                ios = [[s[3:].split(" ", 1)[0], json.loads(s[3:].split(" ", 1)[1])] for s in run.did if s.startswith("io ")]
                expected.append({"state": run.state, "vars": copy.deepcopy(run.vars), "io": ios})
            self.assertFalse(run.violations)
        ir = gen.model(doc)
        result = self.run_driver([{"ir": ir, "input": inp, "events": events}])[0]
        self.assertFalse(result["error"], result)
        self.assertEqual(result["observations"], expected)
        self.assertEqual(result["observations"][1]["vars"]["b"], 9007199254740993)
        bads = [dict(events=[{"t": 0, "name": "tick", "payload": {"tag": "x"}}]),
                dict(input={"record": {"x": True, "ys": []}}),
                dict(input={"record": {"x": 1, "ys": [1.0]}}),
                dict(input={"record": {"x": 1, "ys": [], "extra": 0}})]
        for patch in bads:
            q = {"ir": ir, "input": inp, "events": []}
            q.update(patch)
            self.assertTrue(self.run_driver([q])[0]["error"], q)
        overflow = copy.deepcopy(doc)
        overflow["vars"]["n"]["init"] = 2**63-1
        result = self.run_driver([{"ir": gen.model(overflow), "input": inp,
                                   "events": [{"t": 0, "name": "advance"}]}])[0]
        self.assertIn("overflow", result["error"])


if __name__ == "__main__":
    unittest.main()
