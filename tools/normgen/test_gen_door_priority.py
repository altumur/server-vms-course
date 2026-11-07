"""Judge x-route-priority routing (P/05-R057) against an independent OpenAPI model of priority, capture, decode, error. Match literals as raw bytes without whole-path decoding or trailing-slash normalization; filter methods before priority; unmatched method/shape gives bodyless405/404. Invalid captured values use that method's x-path-error without fallback. Probe resource-route seams s30-s37, operation samples, corrupted/random paths and door roles. Method-filter ordering, early decoding, missing UTF-8 checks and whole-remainder decoding mutants must fail. Empty-capture allowance is equivalent under ObjectKey minLength. Run with jsonschema and Go 1.22."""
import lesson as output_lesson
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
LESSON, SLUG = "05-resource", "p05"
GOENV = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off", GOTOOLCHAIN="local")
sys.path.insert(0, str(HERE))
import yamlsub  # noqa: E402


class Model:
    def __init__(self):
        self.spec = ROOT / "Platform" / LESSON / "spec" / f"{LESSON}.api.openapi.yaml"
        self.doc = yamlsub.load(self.spec.read_text(encoding="utf-8"), self.spec.name)
        from jsonschema import Draft202012Validator
        self.V = Draft202012Validator
        self.paths = []
        for path, item in self.doc["paths"].items():
            ms = [m.upper() for m in ("get", "put", "post", "delete", "patch", "head") if m in item]
            params = {}
            for m in ms:
                for p in item.get("parameters", []) + item[m.lower()].get("parameters", []):
                    if p.get("in") == "path":
                        params[p["name"]] = p
            segs = path[1:].split("/") if path != "/" else []
            self.paths.append({"path": path, "segs": segs, "methods": ms, "prio": item["x-route-priority"],
                               "params": params})

    def valid(self, schema, v):
        return self.V(dict(schema, components=self.doc["components"]) if "$ref" in schema else schema,
                      ).is_valid(v) if "$ref" not in schema else \
            self.V({"$ref": schema["$ref"], "components": self.doc["components"]}).is_valid(v)

    def route(self, method, raw):
        if not raw.startswith("/"):
            return {"err": 404, "resp": ""}
        rs = [] if raw == "/" else raw[1:].split("/")
        cands = []
        for p in self.paths:
            vals, ok = {}, True
            for i, s in enumerate(p["segs"]):
                m = re.fullmatch(r"\{(.+)\}", s)
                if m and p["params"][m[1]].get("x-path-capture") == "remainder":
                    if i >= len(rs):
                        ok = False
                    else:
                        vals[m[1]] = "/".join(rs[i:])
                    break
                if i >= len(rs):
                    ok = False
                    break
                if m:
                    vals[m[1]] = rs[i]
                elif rs[i] != s:
                    ok = False
                    break
            else:
                ok = ok and len(rs) == len(p["segs"])
            if ok:
                cands.append((p, vals))
        if not cands:
            return {"err": 404, "resp": ""}
        withm = [(p, v) for p, v in cands if method.upper() in p["methods"]]
        if not withm:
            return {"err": 405, "resp": ""}
        p, vals = min(withm, key=lambda c: c[0]["prio"])
        out = {}
        for name, v in vals.items():
            prm = p["params"][name]
            good = v != ""
            dec = v
            if good and prm.get("x-path-decode") == "percent-segment":
                parts = []
                for seg in v.split("/"):
                    if re.search(r"%(?![0-9A-Fa-f]{2})", seg):
                        good = False
                        break
                    b = re.sub(rb"%([0-9A-Fa-f]{2})", lambda m_: bytes([int(m_[1], 16)]), seg.encode("utf-8"))
                    try:
                        d = b.decode("utf-8")
                    except UnicodeDecodeError:
                        good = False
                        break
                    if "/" in d:
                        good = False
                        break
                    parts.append(d)
                dec = "/".join(parts)
            if good:
                good = self.valid(prm.get("schema", {}), dec)
            if not good:
                pe = (prm.get("x-path-error") or {}).get(method.upper(), {"status": 404, "response_schema": "-"})
                return {"err": pe["status"], "resp": "" if pe["response_schema"] == "-" else pe["response_schema"],
                        "param": name, "path": p["path"]}
            out[name] = dec
        return {"path": p["path"], "method": method.upper(), "params": out}


DRIVER = r'''package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"unicode/utf8"

	"%s/apidoor"
)

func main() {
	sc := bufio.NewScanner(os.Stdin)
	enc := json.NewEncoder(os.Stdout)
	enc.SetEscapeHTML(false)
	for sc.Scan() {
		if !utf8.Valid(sc.Bytes()) {
			fmt.Fprintln(os.Stderr, "invalid service UTF-8")
			os.Exit(2)
		}
		var c struct { ID int; Method, Path, Role string }
		if err := json.Unmarshal(sc.Bytes(), &c); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(2)
		}
		if c.ID < 1 {
			fmt.Fprintln(os.Stderr, "missing service identity")
			os.Exit(2)
		}
		m, err := apidoor.Route(c.Method, c.Path)
		if err != nil {
			r := map[string]any{"err": err.Code, "resp": err.Response}
			if err.Param != "" {
				r["param"] = err.Param
				r["path"] = apidoor.Ops[err.Op].Path
			}
			if err := enc.Encode(map[string]any{"id": c.ID, "result": r}); err != nil {
				fmt.Fprintln(os.Stderr, err)
				os.Exit(2)
			}
			continue
		}
		info := apidoor.Ops[m.Op]
		if err := enc.Encode(map[string]any{"id": c.ID, "result": map[string]any{
			"path": info.Path, "method": info.Method, "params": m.Params,
			"admitted": apidoor.Admitted(m.Op, c.Role, func(s string) bool { return s == "testsub" })}}); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(2)
		}
	}
	if err := sc.Err(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
}
'''


class CheckingError(RuntimeError):
    """A service failure is not a semantic disagreement or a killed mutant."""


def response_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise CheckingError(f"duplicate service JSON key: {key}")
        obj[key] = value
    return obj


def response_constant(word):
    raise CheckingError(f"non-JSON service constant: {word}")


def checked_values(cases, values):
    """Check the entire response before any call to the independent oracle."""
    if not cases or type(values) is not list or len(values) != len(cases):
        raise CheckingError("nonempty complete service report required")
    for value in values:
        if type(value) is not dict:
            raise CheckingError("route response must be an object")
        if "err" in value:
            keys = {"err", "resp", "param", "path"} if "param" in value else {"err", "resp"}
            if (set(value) != keys or type(value["err"]) is not int
                    or any(type(value[key]) is not str for key in keys - {"err"})):
                raise CheckingError("invalid route refusal shape")
        elif (set(value) != {"path", "method", "params", "admitted"}
              or type(value["path"]) is not str or type(value["method"]) is not str
              or type(value["admitted"]) is not bool or type(value["params"]) is not dict
              or any(type(k) is not str or type(v) is not str for k, v in value["params"].items())):
            raise CheckingError("invalid route success shape")
        try:
            json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (UnicodeError, ValueError, TypeError) as exc:
            raise CheckingError("invalid service scalar") from exc
    return values


def read_report(cases, done):
    if done.returncode:
        raise CheckingError(f"Go service exited {done.returncode}: {done.stderr[-2000:]}")
    try:
        done.stdout.encode("utf-8")
        lines = done.stdout.split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        if not cases or len(lines) != len(cases) or any(not line for line in lines):
            raise CheckingError("nonempty complete service report required")
        frames = [json.loads(line, object_pairs_hook=response_object, parse_constant=response_constant)
                  for line in lines]
    except (UnicodeError, ValueError, TypeError, RecursionError, AttributeError) as exc:
        raise CheckingError("invalid UTF-8/JSON service report") from exc
    values = []
    for identity, frame in enumerate(frames, 1):
        if (type(frame) is not dict or set(frame) != {"id", "result"}
                or type(frame["id"]) is not int or frame["id"] != identity):
            raise CheckingError(f"service identity/order: expected {identity}")
        values.append(frame["result"])
    return checked_values(cases, values)


def go_process(mod, command, stdin=""):
    try:
        return subprocess.run(["go", "run", command], cwd=mod, input=stdin, capture_output=True,
                              text=True, encoding="utf-8", env=GOENV, timeout=120)
    except (OSError, UnicodeError, subprocess.SubprocessError) as exc:
        raise CheckingError(f"cannot execute Go service: {exc}") from exc


def disagree(cases, got, expected):
    values = checked_values(cases, got)
    return [(case, expected(case), values[i]) for i, case in enumerate(cases) if expected(case) != values[i]]


def run(mod, probes):
    if not probes:
        raise CheckingError("nonempty service input required")
    try:
        d = Path(mod) / "cmd/judgeprio"
        d.mkdir(parents=True, exist_ok=True)
        module = (Path(mod) / "go.mod").read_text(encoding="utf-8").split("\n")[0].split()[1]
        (d / "main.go").write_text(DRIVER % module, encoding="utf-8")
        stdin = "".join(json.dumps({"ID": i, "Method": m, "Path": p, "Role": r}, allow_nan=False) + "\n"
                        for i, (m, p, r) in enumerate(probes, 1))
    except (OSError, UnicodeError, ValueError, TypeError, IndexError) as exc:
        raise CheckingError("cannot prepare route service") from exc
    return read_report(probes, go_process(mod, "./cmd/judgeprio", stdin))


def roles_table():
    rows = [ln.split("\t") for ln in (ROOT / "Platform" / LESSON / "forms/door-roles.tsv").read_text().split("\n")
            if ln and not ln.startswith("#")][1:]
    return {(m, p): r.split(",") for m, p, r, _ in rows}


def admitted(roles, role):
    for r in roles:
        if r == "*" and role:
            return True
        if r == "<sub>worker" and role == "testsubworker":
            return True
        if r == role:
            return True
    return False


def probes(model, rnd):
    seams = [ln.split("\t") for ln in (ROOT / "Platform" / LESSON / "acceptance/seams.tsv").read_text().split("\n")
             if "CALL resource-route" in ln]
    out = []
    for cells in seams:
        inp = json.loads(cells[2].split(" ", 2)[2])
        out.append((inp["method"], inp["path"].split("?")[0], inp.get("role", "console")))
    samples = {"key": "testsub/heartbeats/w-1", "sub": "testsub", "digest": "sha256-" + "0" * 64, "unit": "c1",
               "path": "testsub/c1/e1/20260101T000000Z.events.jsonl", "server": "srv-b"}
    for p in model.paths:
        vals = [samples.get(re.fullmatch(r"\{(.+)\}", s)[1], "x") if s.startswith("{") else s for s in p["segs"]]
        base = "/" + "/".join(vals)
        for m in p["methods"] + ["DELETE", "HEAD"]:
            for role in ("console", "resource", "testsubworker", "otherworker", ""):
                out.append((m, base, role))
        out += [(p["methods"][0], base + "/", "console"), (p["methods"][0], base.replace("/", "//", 1), "console"),
                (p["methods"][0], base + "%2F", "console"), (p["methods"][0], base + "%ZZ", "console"),
                (p["methods"][0], base.replace("testsub", "TestSub"), "console")]
    words = ["v1", "objects", "blobs", "events", "wait", "buckets", "mirror", "mirrored", "testsub", "c1", "", "%2F",
             "%FF", "sha256-" + "a" * 64, "srv-b", "a%20b"]
    for _ in range(400):
        segs = [rnd.choice(words) for _ in range(rnd.randint(0, 6))]
        out.append((rnd.choice(["GET", "PUT", "HEAD", "POST"]), "/" + "/".join(segs), "console"))
    return out


class Priority(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("go"):
            raise unittest.SkipTest("go is not in PATH")
        cls.tmp = Path(tempfile.mkdtemp(prefix="door-prio-"))
        out = cls.tmp / "fresh"
        done = subprocess.run([sys.executable, str(HERE / "gen_door_lesson.py"), "--lesson", LESSON, str(out)],
                              capture_output=True, text=True)
        if done.returncode:
            raise CheckingError(done.stderr)
        cls.fresh = out / "go"
        cls.model = Model()
        cls.roles = roles_table()
        cls.pr = probes(cls.model, random.Random(5))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def expect(self, m, p, role):
        e = self.model.route(m, p)
        if "path" in e and "err" not in e:
            e = dict(e, admitted=admitted(self.roles.get((e["method"], e["path"]), []), role))
        return e

    def test_fresh(self):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        for name in ("routes.go", "routes_rt.go", "bodies.go", "schema_rt.go"):
            kept = output_lesson.output_root() / SLUG / "go/apidoor" / name
            self.assertEqual(kept.read_bytes(), (self.fresh / "apidoor" / name).read_bytes(), f"{kept} is stale")

    def test_seams_and_probes(self):
        got = run(self.fresh, self.pr)
        bad = disagree(self.pr, got, lambda p: self.expect(*p))
        self.assertEqual(bad[:3], [], f"{len(bad)} of {len(self.pr)} disagree")
        kinds = {(g.get("err"), bool(g.get("param"))) for g in got}
        for k in ((404, False), (405, False), (400, True), (404, True), (405, True)):
            self.assertIn(k, kinds)
        self.assertEqual({(g["method"], g["path"]) for g in got if "method" in g},
                         {(m, p["path"]) for p in self.model.paths for m in p["methods"]})

    def test_mutants(self):
        rt = (self.fresh / "apidoor/routes_rt.go").read_text()
        muts = {
            "priority-before-method": rt.replace('''		if _, has := byPathMethod[t.path+" "+m]; !has {
			continue
		}''', "", 1),
            "decode-before-match": rt.replace('''	raw := strings.Split(rawPath[1:], "/")''',
                                              '''	dp, _ := unescapeSegment(rawPath)
	raw := strings.Split(strings.TrimPrefix(dp, "/"), "/")''', 1),
            "no-utf8": rt.replace("if ok && !utf8.ValidString(dec) {", "if ok && false && !utf8.ValidString(dec) {", 1),
            "remainder-one-piece": rt.replace('parts := strings.Split(v, "/")', 'parts := []string{v}', 1),
        }
        for name, text in muts.items():
            with self.subTest(mutant=name):
                self.assertNotEqual(text, rt, f"{name}: the mutant does not apply")
                mod = self.tmp / f"mut-{name}"
                shutil.copytree(self.fresh, mod)
                (mod / "apidoor/routes_rt.go").write_text(text)
                got = run(mod, self.pr)
                bad = disagree(self.pr, got, lambda p: self.expect(*p))
                self.assertTrue(bad, f"{name} survives")


class PriorityServiceControls(unittest.TestCase):
    """Independent controls of the checking service, without running Go."""

    def setUp(self):
        self.cases = [("GET", "/healthz", "console"), ("GET", "/missing", "")]
        self.value = {"err": 404, "resp": ""}

    def report(self, frames):
        return subprocess.CompletedProcess(["go", "run"], 0,
                                           "".join(json.dumps(f) + "\n" for f in frames), "")

    def frames(self):
        return [{"id": i, "result": self.value} for i in range(1, len(self.cases) + 1)]

    def test_complete_equal_values_keep_distinct_input_identities(self):
        self.assertEqual(read_report(self.cases, self.report(self.frames())), [self.value, self.value])
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "go.mod").write_text("module service.control\n")
            with patch(__name__ + ".subprocess.run", return_value=self.report(self.frames())) as proc:
                self.assertEqual(run(td, self.cases), [self.value, self.value])
            sent = [json.loads(line) for line in proc.call_args.kwargs["input"].split("\n") if line]
            self.assertEqual([c["ID"] for c in sent], [1, 2])

    def test_reports_require_nonempty_complete_ordered_identity(self):
        good = self.frames()
        variants = [[], good[:1], good + [good[0]], [good[0], good[0]], good[::-1],
                    [{"id": True, "result": self.value}, good[1]],
                    [{"result": self.value}, good[1]],
                    [dict(good[0], extra=1), good[1]], [[], good[1]],
                    [{"id": 1, "result": "panic: control"}, good[1]]]
        for frames in variants:
            with self.subTest(frames=frames), self.assertRaises(CheckingError):
                read_report(self.cases, self.report(frames))
        for text in ('', '\n', '{bad}\n', '{"id":1,"id":1,"result":true}\n' + json.dumps(good[1]) + '\n',
                     '{"id":1,"result":NaN}\n' + json.dumps(good[1]) + '\n',
                     self.report(good).stdout + '\n', '\ud800'):
            with self.subTest(text=repr(text)), self.assertRaises(CheckingError):
                read_report(self.cases, subprocess.CompletedProcess([], 0, text, ''))

    def test_process_and_preparation_errors_are_checking_errors(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "go.mod").write_text("module service.control\n")
            for failure in (OSError("start"), UnicodeError("UTF-8"), subprocess.TimeoutExpired(["go"], 120)):
                with self.subTest(failure=failure), patch(__name__ + ".subprocess.run", side_effect=failure):
                    with self.assertRaises(CheckingError):
                        run(td, self.cases)
            for stderr in ("compile failed", "panic: control", "scanner failed", "encoder failed"):
                done = subprocess.CompletedProcess([], 1, self.report(self.frames()).stdout, stderr)
                with self.subTest(stderr=stderr), patch(__name__ + ".subprocess.run", return_value=done):
                    with self.assertRaises(CheckingError):
                        run(td, self.cases)
            with patch(__name__ + ".subprocess.run") as proc:
                with self.assertRaises(CheckingError):
                    run(td, [])
                proc.assert_not_called()
            (Path(td) / "go.mod").unlink()
            with self.assertRaises(CheckingError):
                run(td, self.cases)

    def test_complete_report_is_checked_before_the_oracle(self):
        expected = Mock(return_value=self.value)
        for got in ([], [{"err": 403, "resp": ""}], [{"err": 403, "resp": ""}, "bad shape"]):
            with self.subTest(got=got), self.assertRaises(CheckingError):
                disagree(self.cases, got, expected)
        expected.assert_not_called()
        self.assertEqual(disagree(self.cases, [self.value, self.value], lambda c: self.value), [])
        bad = disagree(self.cases, [{"err": 403, "resp": ""}, self.value], lambda c: self.value)
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0][0], self.cases[0])

    def mutant_case(self, directory):
        fresh = Path(directory) / "fresh"
        (fresh / "apidoor").mkdir(parents=True)
        (fresh / "apidoor/routes_rt.go").write_bytes((HERE / "doorrt2/go/routes_priority.go").read_bytes())
        obj = Priority("test_mutants")
        obj.pr = self.cases
        obj.expect = lambda *unused: dict(self.value)
        obj.fresh = fresh
        obj.tmp = Path(directory)
        return obj

    def test_mutant_loop_does_not_absorb_checking_errors(self):
        with tempfile.TemporaryDirectory() as td:
            obj = self.mutant_case(td)
            with patch(__name__ + ".run", side_effect=CheckingError("compile control")):
                with self.assertRaises(CheckingError):
                    obj.test_mutants()

    def test_a_complete_correct_mutant_report_remains_a_survivor(self):
        with tempfile.TemporaryDirectory() as td:
            obj = self.mutant_case(td)
            with patch(__name__ + ".run", side_effect=lambda mod, cases: [dict(self.value) for _ in cases]):
                with self.assertRaisesRegex(AssertionError, "survives"):
                    obj.test_mutants()


if __name__ == "__main__":
    unittest.main()
