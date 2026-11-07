"""Judge lesson route generation (part 3a, P/06) against an independent OpenAPI model. Require fresh, one-to-one Op coverage and metadata for each method/path. Probe schema-valid parameter samples, short/prefixed variants, unknown segments/catalog names, foreign methods, malformed percent escapes and invalid values. Model literal>catalog-class>free-parameter precedence plus Catalog/schema checks; execute Go Route on a fixture Catalog. Mutants removing prefix variants, all405, parameter patterns or class rank must fail. Run test_gen_door_lesson.py with Go 1.22."""
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
LESSONS = {"06-console": "p06", "08-domain": "p08", "09-agent": "p09", "10-domain-console": "p10"}
GOENV = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off", GOTOOLCHAIN="local")
METHODS = ("get", "put", "post", "delete", "patch", "head", "options", "trace")
CATALOG = {"sub": {"testsub", "testsub2"}, "rows": {"units", "cams"}, "table": {"tallies"}, "pass": {"probe"}}
SAMPLES = ["c1", "0123456789abcdef", "0001", "srv-a", "t1", "a", "member-1", "index.js", "x"]

sys.path.insert(0, str(HERE))
import yamlsub  # noqa: E402


class Model:
    """Independent route model: derive templates and parameter checks directly from OpenAPI."""

    def __init__(self, lesson):
        self.spec = ROOT / "Platform" / lesson / "spec" / f"{lesson}.api.openapi.yaml"
        self.files = {}
        self.doc = self.load(self.spec)
        self.paths = []
        for path, item in self.doc["paths"].items():
            ms = [m.upper() for m in METHODS if m in item]
            if not ms:
                continue
            segs = [] if path == "/" else path[1:].split("/")
            checks = {}
            ops = {}
            for m in METHODS:
                if m not in item:
                    continue
                op = item[m]
                prms = [self.deref(p, self.spec) for p in item.get("parameters", []) + op.get("parameters", [])]
                for p, pbase in prms:                     # Resolve parameter schemas relative to their declaration document.
                    if p["in"] == "path":
                        checks[p["name"]] = self.schema(p["schema"], pbase)
                codes = [str(c) for c in op["responses"]]
                ops[m.upper()] = codes
            urls = [s["url"] for s in item.get("servers") or []]
            pre = "{origin}/{sub}" in urls
            self.paths.append({"path": path, "segs": segs, "checks": checks, "ops": ops, "prefixed": pre,
                               "all405": all("405" in c for c in ops.values())})

    def load(self, p):
        p = Path(p).resolve()
        if p not in self.files:
            self.files[p] = yamlsub.load(p.read_text(encoding="utf-8"), p.name)
        return self.files[p]

    def deref(self, node, base):
        while isinstance(node, dict) and "$ref" in node:
            f, _, ptr = node["$ref"].partition("#")
            base = (Path(base).parent / f).resolve() if f else base
            node = self.load(base)
            for part in ptr.strip("/").split("/"):
                node = node[part]
        return node, base

    def schema(self, node, base):
        node, base = self.deref(node, base)
        return {"min": node.get("minLength", 0), "max": node.get("maxLength"), "pattern": node.get("pattern"),
                "enum": node.get("enum"), "not": node.get("not")}

    @staticmethod
    def ok(c, v):
        if v == "" or len(v) < c["min"] or (c["max"] is not None and len(v) > c["max"]):
            return False
        if c["pattern"] and not re.search(c["pattern"], v):
            return False
        if c["enum"] is not None and v not in [str(e) for e in c["enum"]]:
            return False
        neg = c["not"]
        if neg:
            for it in neg.get("anyOf", [neg]):
                if "enum" in it and v in [str(e) for e in it["enum"]]:
                    return False
                if "pattern" in it and re.search(it["pattern"], v):
                    return False
        return True

    def templates(self):
        for p in self.paths:
            yield p, p["segs"], False
            if p["prefixed"]:
                yield p, ["{sub}"] + p["segs"], True

    @staticmethod
    def rank(seg):
        m = re.fullmatch(r"\{(.+)\}", seg)
        if not m:
            return 2
        return 1 if m[1] in CATALOG else 0

    def route(self, method, path):
        """→ ("op", path, method, params, prefixed) | ("err", code)."""
        if not path.startswith("/"):
            return ("err", 404)
        raw = [] if path == "/" else path[1:].split("/")
        segs = []
        for s in raw:
            if re.search(r"%(?![0-9A-Fa-f]{2})", s):
                return ("err", 404)                    # Malformed percent escape.
            b = re.sub(rb"%([0-9A-Fa-f]{2})", lambda m: bytes([int(m[1], 16)]), s.encode("utf-8"))
            segs.append(b.decode("utf-8", "surrogateescape"))
        hits = []
        for p, tsegs, pre in self.templates():
            if len(tsegs) != len(segs):
                continue
            params, good = {}, True
            for t, v in zip(tsegs, segs):
                m = re.fullmatch(r"\{(.+)\}", t)
                if not m:
                    good = t == v
                elif m[1] == "sub" and pre and t == tsegs[0] and "sub" not in p["checks"]:
                    good = v != ""
                    params["sub"] = v
                else:
                    good = self.ok(p["checks"][m[1]], v)
                    params[m[1]] = v
                if not good:
                    break
            if not good:
                continue
            sub = params.get("sub", "")
            for name, v in params.items():
                if name in ("rows", "table", "pass") and v not in CATALOG[name]:
                    good = False
                if name == "sub" and v not in CATALOG["sub"]:
                    good = False
            if good:
                hits.append((p, tsegs, pre, params))
        if not hits:
            return ("err", 404)

        def key(h):
            return [self.rank(s) for s in h[1]]
        top = max(key(h) for h in hits)
        best = [h for h in hits if key(h) == top]
        if len({h[0]["path"] for h in best}) > 1:
            return ("err", 0)
        p, _, pre, params = best[0]
        m = method.upper()
        if m in p["ops"]:
            return ("op", p["path"], m, params, pre)
        return ("err", 405 if p["all405"] else 404)

    def sample(self, p, name):
        if name in CATALOG:
            return sorted(CATALOG[name])[0]
        c = p["checks"][name]
        if c["enum"]:
            return str(c["enum"][0])
        for s in SAMPLES:
            if self.ok(c, s):
                return s
        return None


DRIVER = r'''package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"

	"%s/apidoor"
)

type cat struct{}

func in(xs []string, v string) bool {
	for _, x := range xs {
		if x == v {
			return true
		}
	}
	return false
}

func (cat) Sub(n string) bool           { return in([]string{"testsub", "testsub2"}, n) }
func (cat) Rows(sub, n string) bool     { return in([]string{"units", "cams"}, n) }
func (cat) Table(sub, n string) bool    { return in([]string{"tallies"}, n) }
func (cat) Pass(sub, n string) bool     { return in([]string{"probe"}, n) }

func main() {
	sc := bufio.NewScanner(os.Stdin)
	enc := json.NewEncoder(os.Stdout)
	for sc.Scan() {
		var c struct {
			ID int
			Method, Path string
		}
		if err := json.Unmarshal(sc.Bytes(), &c); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		m, err := apidoor.Route(c.Method, c.Path, cat{})
		var result map[string]any
		if err != nil {
			result = map[string]any{"err": err.Code}
		} else {
			info := apidoor.Ops[m.Op]
			result = map[string]any{"path": info.Path, "method": info.Method, "params": m.Params, "prefixed": m.Prefixed}
		}
		if err := enc.Encode(map[string]any{"id": c.ID, "result": result}); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	}
	if err := sc.Err(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
'''


class CheckingError(RuntimeError):
    """The checking service failed; this is never a semantic mutant detection."""


def disagree(probes, got, oracle=None):
    """Validate every result before invoking the unchanged semantic oracle."""
    if not isinstance(probes, (list, tuple)) or not probes or any(
            not isinstance(p, (list, tuple)) or len(p) != 2 or
            any(type(v) is not str for v in p) for p in probes):
        raise CheckingError("probes must be a nonempty sequence of Method/Path string pairs")
    if type(got) is not list or len(got) != len(probes):
        raise CheckingError(f"expected {len(probes)} complete results, got {got!r}")
    for i, result in enumerate(got, 1):
        if type(result) is not dict:
            raise CheckingError(f"input {i}: result is not an object: {result!r}")
        if set(result) == {"err"}:
            valid = type(result["err"]) is int
        elif set(result) == {"path", "method", "params", "prefixed"}:
            valid = (type(result["path"]) is str and type(result["method"]) is str and
                     type(result["prefixed"]) is bool and type(result["params"]) is dict and
                     all(type(k) is str and type(v) is str for k, v in result["params"].items()))
        else:
            valid = False
        if not valid:
            raise CheckingError(f"input {i}: incomplete or mistyped result: {result!r}")
    try:
        json.dumps([probes, got], ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (UnicodeError, ValueError, TypeError, RecursionError) as exc:
        raise CheckingError(f"invalid result/input text: {exc}") from exc
    if oracle is None:
        return []
    bad = []
    for probe, result in zip(probes, got):
        try:
            want = oracle(probe)
        except Exception as exc:
            raise CheckingError(f"oracle failed for {probe!r}: {exc}") from exc
        if want != result:
            bad.append((probe, want, result))
    return bad


def read_report(probes, done):
    """Require normal termination and all ordered private-ID frames, then unwrap."""
    if not isinstance(probes, (list, tuple)) or not probes:
        raise CheckingError("a report requires nonempty probes")
    if type(getattr(done, "returncode", None)) is not int or done.returncode != 0:
        raise CheckingError(f"process failed: {done!r}")
    text = done.stdout
    try:
        if isinstance(text, bytes):
            text = text.decode("utf-8")
        if type(text) is not str:
            raise ValueError("stdout is not text")
        text.encode("utf-8")

        def pairs(items):
            result = {}
            for k, v in items:
                if k in result:
                    raise ValueError(f"duplicate JSON name: {k}")
                result[k] = v
            return result

        def constant(value):
            raise ValueError(f"nonfinite JSON constant: {value}")

        frames = text.split("\n")
        if frames[-1] == "":
            frames.pop()                       # One terminal LF is framing, not another result.
        if len(frames) != len(probes):
            raise ValueError(f"expected {len(probes)} frames, got {len(frames)}")
        results = []
        for i, line in enumerate(frames, 1):
            frame = json.loads(line, object_pairs_hook=pairs, parse_constant=constant)
            if (type(frame) is not dict or set(frame) != {"id", "result"} or
                    type(frame["id"]) is not int or frame["id"] != i):
                raise ValueError(f"input {i}: missing, extra or unordered frame identity: {frame!r}")
            results.append(frame["result"])
        disagree(probes, results)               # Validate the complete list before any semantic call.
        return results
    except (UnicodeError, ValueError, TypeError, RecursionError) as exc:
        raise CheckingError(f"invalid process report: {exc}; stdout={done.stdout!r}; stderr={done.stderr!r}") from exc


def run(mod, probes):
    if not isinstance(probes, (list, tuple)) or not probes or any(
            not isinstance(p, (list, tuple)) or len(p) != 2 or
            any(type(v) is not str for v in p) for p in probes):
        raise CheckingError("probes must be a nonempty sequence of Method/Path string pairs")
    try:
        for probe in probes:
            for value in probe:
                value.encode("utf-8")
        wire = "".join(json.dumps({"ID": i, "Method": m, "Path": p}) + "\n"
                       for i, (m, p) in enumerate(probes, 1))
        d = Path(mod) / "cmd/judgeroutes"
        d.mkdir(parents=True, exist_ok=True)
        module = (Path(mod) / "go.mod").read_text().split("\n")[0].split()[1]
        (d / "main.go").write_text(DRIVER % module)
        done = subprocess.run(["go", "run", "./cmd/judgeroutes"], cwd=mod, capture_output=True, text=True, env=GOENV,
                              input=wire)
    except (OSError, UnicodeError, ValueError, TypeError, IndexError, subprocess.SubprocessError) as exc:
        raise CheckingError(f"route checking preparation/process failed in {mod}: {exc}") from exc
    return read_report(probes, done)


def probes(model, rnd):
    out = []
    for p in model.paths:
        for pre in (False, True) if p["prefixed"] else (False,):
            vals = []
            good = True
            for s in p["segs"]:
                m = re.fullmatch(r"\{(.+)\}", s)
                if not m:
                    vals.append(s)
                    continue
                v = model.sample(p, m[1])
                if v is None:
                    good = False
                    break
                vals.append(v)
            if not good:
                continue
            path = "/" + "/".join((["testsub"] if pre else []) + vals)
            for meth in p["ops"]:
                out.append((meth, path))
            out.append(("TRACE", path))                       # Unsupported method.
            bad = path.replace("/" + vals[0], "/zz-unknown", 1) if vals else "/zz-unknown"
            out.append(("GET", bad))
    for p in model.paths:                             # Free-parameter minLength boundary and one character shorter.
        for k, seg in enumerate(p["segs"]):
            m = re.fullmatch(r"\{(.+)\}", seg)
            if not m or m[1] in CATALOG:
                continue
            c = p["checks"][m[1]]
            base = []
            for j, s2 in enumerate(p["segs"]):
                mm = re.fullmatch(r"\{(.+)\}", s2)
                base.append(s2 if not mm else model.sample(p, mm[1]))
            if None in base:
                continue
            for n in (c["min"], c["min"] - 1):
                if n < 1:
                    continue
                vals = list(base)
                vals[k] = "a" * n
                out.append((next(iter(p["ops"])), "/" + "/".join(vals)))
    out += [("GET", "/%zz"), ("GET", "nope"), ("GET", "/testsub/zz/zz/zz/zz/zz"), ("GET", "/zzsub/units")]
    for _ in range(300):
        segs = [rnd.choice(["testsub", "units", "tallies", "probe", "folders", "domain", "at", "c1", "zz", "",
                            "manifest", "where", "servers", "api", "metrics", "%41"]) for _ in range(rnd.randint(0, 5))]
        out.append((rnd.choice(["GET", "PUT", "POST", "DELETE", "PATCH"]), "/" + "/".join(segs)))
    return out


def expected(model, probe):
    r = model.route(*probe)
    if r[0] == "err":
        return {"err": r[1]}
    return {"path": r[1], "method": r[2], "params": r[3], "prefixed": r[4]}


class DoorLessonBase:
    LESSON = SLUG = None

    @classmethod
    def setUpClass(cls):
        if not shutil.which("go"):
            raise unittest.SkipTest("go is not in PATH")
        try:
            cls.tmp = Path(tempfile.mkdtemp(prefix="door-lesson-"))
            out = cls.tmp / "fresh"
            done = subprocess.run([sys.executable, str(HERE / "gen_door_lesson.py"), "--lesson", cls.LESSON, str(out)],
                                  capture_output=True, text=True)
        except (OSError, UnicodeError, subprocess.SubprocessError) as exc:
            raise CheckingError(f"route generation preparation/process failed: {exc}") from exc
        if type(getattr(done, "returncode", None)) is not int or done.returncode != 0:
            raise CheckingError(f"route generation failed: {done!r}")
        cls.fresh = out / "go"
        cls.model = Model(cls.LESSON)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_fresh(self):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        for name in ("routes.go", "routes_rt.go"):
            kept = output_lesson.output_root() / self.SLUG / "go/apidoor" / name
            self.assertEqual(kept.read_bytes(), (self.fresh / "apidoor" / name).read_bytes(), f"{kept} is stale")

    def test_ops(self):
        text = (self.fresh / "apidoor/routes.go").read_text()
        n = sum(len(p["ops"]) for p in self.model.paths)
        self.assertEqual(len(re.findall(r"^\tOp\w+(?:\s+Op = iota \+ 1)?\s+// [A-Z]+ /", text, re.M)), n)
        for p in self.model.paths:
            for m in p["ops"]:
                self.assertIn(f'"{p["path"]} {m}": ', text)

    def test_probes(self):
        rnd = random.Random(6)
        pr = probes(self.model, rnd)
        got = run(self.fresh, pr)
        bad = disagree(pr, got, lambda p: expected(self.model, p))
        self.assertEqual(bad[:3], [], f"{len(bad)} of {len(pr)} probes disagree")
        hit_ops = {(g["path"], g["method"], g["prefixed"]) for g in got if "path" in g}
        want = {(p["path"], m, pre) for p in self.model.paths for m in p["ops"]
                for pre in ((False, True) if p["prefixed"] else (False,))}
        missed = want - hit_ops
        # Allow at most10% probes shadowed by more-specific templates or lacking a sample.
        self.assertLessEqual(len(missed), len(want) // 10, f"probes reach too few operations: {sorted(missed)[:10]}")
        codes = {g.get("err") for g in got}
        self.assertIn(404, codes)
        if any(p["all405"] for p in self.model.paths):
            self.assertIn(405, codes)

    def test_mutants(self):
        rnd = random.Random(7)
        pr = probes(self.model, rnd)
        src = (self.fresh / "apidoor/routes.go").read_text()
        rt = (self.fresh / "apidoor/routes_rt.go").read_text()
        m405 = re.search(r'^\t("[^"]+":\s+)true,$', src[src.index("var all405"):], re.M)
        muts = {
            "prefix-lost": ("routes.go", re.sub(r"(\{path: \"[^\"]+\", segs: \[\]segment\{\{param: \"sub\"\}[^\n]*prefixed: )true",
                                                r"\1false", src, count=1)),
            "all405": ("routes.go", src.replace(f"\t{m405[1]}true,", f"\t{m405[1]}false,", 1) if m405 else src),
            "pattern": ("routes.go", re.sub(r'("(?!sub"|rows"|table"|pass")\w+": paramCheck\{minLen: )1(, maxLen: -1, rx: nil)',
                                            r"\g<1>3\2", src, count=1)),
            "rank": ("routes_rt.go", rt.replace('case s.param == "sub" || s.param == "rows"', 'case s.param == "sub" || s.param == "zz"', 1)),
        }
        prefixed = any(p["prefixed"] for p in self.model.paths)
        shapes = {}
        for p, tsegs, pre in self.model.templates():
            shapes.setdefault(tuple("{}" if re.fullmatch(r"\{.+\}", sg) else sg for sg in tsegs), []).append(tsegs)

        def rows_vs_free(group):                       # rows rank matters when a catalog parameter and a free parameter share a position.
            for i in range(len(group[0])):
                names = {sg for sg in (t[i] for t in group)}
                if "{rows}" in names and any(re.fullmatch(r"\{(.+)\}", n) and n[1:-1] not in CATALOG for n in names):
                    return True
            return False
        classes = any(len(v) > 1 and rows_vs_free(v) for v in shapes.values())
        for name, (f, text) in muts.items():
            if (name == "prefix-lost" and not prefixed) or (name == "rank" and not classes) \
                    or (name == "all405" and m405 is None):
                continue                                   # Inapplicable to lessons without prefixes/catalog classes.
            base = src if f == "routes.go" else rt
            if name == "pattern" and text == base:
                continue                                   # No free parameter with minLength1 and no pattern exists in this lesson.
            with self.subTest(mutant=name):
                if text == base:
                    raise CheckingError(f"{name}: the applicable mutant does not change its target")
                mod = self.tmp / f"mut-{name}"
                try:
                    shutil.copytree(self.fresh, mod)
                    (mod / "apidoor" / f).write_text(text)
                except (OSError, UnicodeError) as exc:
                    raise CheckingError(f"{name}: mutant preparation failed: {exc}") from exc
                got = run(mod, pr)
                bad = disagree(pr, got, lambda p: expected(self.model, p))
                self.assertTrue(bad, f"{name} survives")


class RouteServiceControls(unittest.TestCase):
    """Independent checking-service controls; subprocess responses here are injected."""

    def setUp(self):
        self.inputs = [("GET", "/a"), ("GET", "/b")]
        self.results = [{"err": 404}, {"err": 404}]

    def frames(self, results=None):
        return [{"id": i, "result": v} for i, v in enumerate(self.results if results is None else results, 1)]

    def report(self, frames=None, code=0):
        return subprocess.CompletedProcess(["go", "run"], code,
                                           "".join(json.dumps(f, ensure_ascii=False) + "\n"
                                                   for f in (self.frames() if frames is None else frames)), "")

    def module(self, directory):
        mod = Path(directory) / "go"
        mod.mkdir()
        (mod / "go.mod").write_text("module checking.control\n")
        return mod

    def mutant_case(self, directory):
        fresh = Path(directory) / "fresh"
        (fresh / "apidoor").mkdir(parents=True)
        # Text-only applicability fixture, never compiled or used as a route oracle.
        (fresh / "apidoor/routes.go").write_text(
            'var all405 = map[string]bool{\n\t"/{sub}/": true,\n}\n'
            '{path: "/{sub}/", segs: []segment{{param: "sub"}}, prefixed: true},\n'
            '\t"free": paramCheck{minLen: 1, maxLen: -1, rx: nil},\n')
        (fresh / "apidoor/routes_rt.go").write_text('case s.param == "sub" || s.param == "rows":\n')
        obj = DoorLesson_p06("test_mutants")
        obj.tmp, obj.fresh = Path(directory), fresh
        obj.model = Mock(paths=[{"prefixed": True}])
        obj.model.templates.return_value = [({}, ["{rows}"], False), ({}, ["{free}"], False)]
        return obj

    def test_complete_positive(self):
        success = {"path": "/{name}", "method": "GET", "params": {"name": "a"}, "prefixed": False}
        for value in ({"err": 0}, {"err": 404}, {"err": 405}, success):
            with self.subTest(value=value):
                self.assertEqual(read_report(self.inputs, self.report(self.frames([value, value]))), [value, value])
        with tempfile.TemporaryDirectory() as td:
            mod = self.module(td)
            with patch(__name__ + ".subprocess.run", return_value=self.report()) as proc:
                self.assertEqual(run(mod, self.inputs), self.results)
            sent = [json.loads(line) for line in proc.call_args.kwargs["input"].split("\n") if line]
            self.assertEqual(sent, [{"ID": i, "Method": m, "Path": p}
                                    for i, (m, p) in enumerate(self.inputs, 1)])
            self.assertNotIn("timeout", proc.call_args.kwargs)

    def test_zero_input_before_preparation(self):
        with tempfile.TemporaryDirectory() as td, patch(__name__ + ".subprocess.run") as proc:
            for bad in ([], (), None, [("GET",)], [(True, "/a")]):
                with self.subTest(probes=bad), self.assertRaises(CheckingError):
                    run(Path(td) / "never-created", bad)
            proc.assert_not_called()
            self.assertEqual(list(Path(td).iterdir()), [])
        with self.assertRaises(CheckingError):
            read_report([], self.report([]))

    def test_zero_short_extra_reports(self):
        good = self.frames()
        for frames in ([], good[:1], good + [good[0]]):
            with self.subTest(frames=frames), self.assertRaises(CheckingError):
                read_report(self.inputs, self.report(frames))

    def test_frame_identities(self):
        good = self.frames()
        cases = [good[::-1], [good[0], good[0]], [{"result": self.results[0]}, good[1]]]
        cases += [[dict(good[0], id=v), good[1]] for v in (0, 3, True, 1.0, "1", None)]
        for frames in cases:
            with self.subTest(frames=frames), self.assertRaises(CheckingError):
                read_report(self.inputs, self.report(frames))

    def test_frame_shapes(self):
        for frame in ({"id": 1}, {"id": 1, "result": {"err": 404}, "extra": 1}, [], None):
            with self.subTest(frame=frame), self.assertRaises(CheckingError):
                read_report(self.inputs, self.report([frame, self.frames()[1]]))
        for result in ({}, {"err": 404, "path": "/a"}, {"path": "/a"}, "panic: control"):
            with self.subTest(result=result), self.assertRaises(CheckingError):
                read_report(self.inputs, self.report(self.frames([result, self.results[1]])))

    def test_typed_shapes(self):
        good = {"path": "/a", "method": "GET", "params": {}, "prefixed": False}
        bad = [{"err": True}, {"err": 404.0}, {"err": "404"}]
        bad += [dict(good, **{key: value}) for key, value in
                (("path", None), ("method", 1), ("params", None), ("params", {"x": 1}),
                 ("params", {1: "x"}), ("prefixed", 0))]
        for result in bad:
            with self.subTest(result=result), self.assertRaises(CheckingError):
                disagree(self.inputs, [result, self.results[1]], lambda p: self.results[0])

    def test_valid_wrong_values_are_semantic(self):
        want = {"path": "/a", "method": "GET", "params": {"x": "a"}, "prefixed": False}
        for got in (dict(want, path="/other"), dict(want, method="POST"),
                    dict(want, params={"x": "other"}), dict(want, prefixed=True), {"err": 500}):
            with self.subTest(got=got):
                values = read_report(self.inputs, self.report(self.frames([got, want])))
                self.assertEqual(disagree(self.inputs, values, lambda p: want), [(self.inputs[0], want, got)])

    def test_strict_json(self):
        tail = json.dumps(self.frames()[1]) + "\n"
        texts = ["", "\n\n", "{bad}\n" + tail, '\ufeff' + self.report().stdout,
                 '{"id":1,"id":1,"result":{"err":404}}\n' + tail,
                 '{"id":1,"result":{"err":404,"err":405}}\n' + tail,
                 '{"id":1,"result":{"err":NaN}}\n' + tail,
                 '{"id":1,"result":{"err":Infinity}}\n' + tail,
                 self.report().stdout + "\n", self.report().stdout + "garbage", "\ud800", b"\xff"]
        for text in texts:
            with self.subTest(text=repr(text)), self.assertRaises(CheckingError):
                read_report(self.inputs, subprocess.CompletedProcess([], 0, text, ""))

    def test_preparation_errors(self):
        with tempfile.TemporaryDirectory() as td:
            mod = self.module(td)
            for content in (b"", b"\xff"):
                (mod / "go.mod").write_bytes(content)
                with self.subTest(content=content), self.assertRaises(CheckingError):
                    run(mod, self.inputs)
            (mod / "go.mod").write_text("module checking.control\n")
            with patch.object(Path, "write_text", side_effect=OSError("driver write control")):
                with self.assertRaises(CheckingError):
                    run(mod, self.inputs)
            (mod / "go.mod").unlink()
            with self.assertRaises(CheckingError):
                run(mod, self.inputs)

    def test_start_errors(self):
        with tempfile.TemporaryDirectory() as td:
            mod = self.module(td)
            for failure in (OSError("start control"), UnicodeError("decode control"),
                            subprocess.TimeoutExpired(["go"], 1)):
                with self.subTest(failure=failure), patch(__name__ + ".subprocess.run", side_effect=failure):
                    with self.assertRaises(CheckingError):
                        run(mod, self.inputs)

    def test_compile_nonzero_even_with_complete_output(self):
        for frames in ([], self.frames()[:1], self.frames()):
            done = self.report(frames, code=1)
            done.stderr = "compile control"
            with self.subTest(frames=frames), self.assertRaises(CheckingError):
                read_report(self.inputs, done)
        self.assertFalse(issubclass(CheckingError, AssertionError))

    def test_terminal_errors_are_not_semantic(self):
        with tempfile.TemporaryDirectory() as td:
            mod = self.module(td)
            for error in ("panic: control", "scanner failed", "encoder failed"):
                done = self.report(code=1)
                done.stderr = error
                with self.subTest(error=error), patch(__name__ + ".subprocess.run", return_value=done):
                    with self.assertRaises(CheckingError):
                        run(mod, self.inputs)

    def test_generation_errors(self):
        for failure in (subprocess.CompletedProcess([], 1, "partial", "generation control"), OSError("start control")):
            with tempfile.TemporaryDirectory() as td, patch(__name__ + ".shutil.which", return_value="go"), \
                    patch(__name__ + ".tempfile.mkdtemp", return_value=td):
                kwargs = {"side_effect": failure} if isinstance(failure, Exception) else {"return_value": failure}
                with patch(__name__ + ".subprocess.run", **kwargs), self.assertRaises(CheckingError):
                    DoorLesson_p06.setUpClass()

    def test_complete_before_oracle(self):
        oracle = Mock(return_value={"err": 404})
        for got in ([], [{"err": 405}], [{"err": 405}, {}], self.results + [{"err": 404}]):
            with self.subTest(got=got), self.assertRaises(CheckingError):
                disagree(self.inputs, got, oracle)
        oracle.assert_not_called()
        with patch(__name__ + ".probes", return_value=self.inputs), \
                patch(__name__ + ".run", return_value=[{"err": 405}]), \
                patch(__name__ + ".expected") as expected_call:
            obj = DoorLesson_p06("test_probes")
            obj.model, obj.fresh = Mock(), Path("unused")
            with self.assertRaises(CheckingError):
                obj.test_probes()
            expected_call.assert_not_called()
        with self.assertRaises(CheckingError):
            disagree(self.inputs, self.results, Mock(side_effect=AssertionError("oracle control")))

    def test_mutant_errors_propagate(self):
        for target in ("prefix-lost", "all405", "pattern", "rank"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as td:
                obj = self.mutant_case(td)

                def result(mod, inputs):
                    if mod.name == "mut-" + target:
                        raise CheckingError("process control")
                    return [{"err": 405}, {"err": 404}]

                with patch(__name__ + ".probes", return_value=self.inputs), \
                        patch(__name__ + ".expected", return_value={"err": 404}), \
                        patch(__name__ + ".run", side_effect=result), self.assertRaises(CheckingError):
                    obj.test_mutants()

    def test_correct_mutant_survives(self):
        for target in ("prefix-lost", "all405", "pattern", "rank"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as td:
                obj = self.mutant_case(td)

                def result(mod, inputs):
                    return self.results if mod.name == "mut-" + target else [{"err": 405}, {"err": 404}]

                with patch(__name__ + ".probes", return_value=self.inputs), \
                        patch(__name__ + ".expected", return_value={"err": 404}), \
                        patch(__name__ + ".run", side_effect=result), self.assertRaisesRegex(AssertionError, target + " survives"):
                    obj.test_mutants()

    def test_named_semantic_mismatch(self):
        self.assertEqual(disagree(self.inputs, [{"err": 405}, {"err": 404}], lambda p: {"err": 404}),
                         [(self.inputs[0], {"err": 404}, {"err": 405})])

    def test_mutation_applicability(self):
        with tempfile.TemporaryDirectory() as td:
            obj = self.mutant_case(td)
            with patch(__name__ + ".probes", return_value=self.inputs), \
                    patch(__name__ + ".expected", return_value={"err": 404}), \
                    patch(__name__ + ".run", return_value=[{"err": 405}, {"err": 404}]) as proc:
                obj.test_mutants()
                self.assertEqual([c.args[0].name for c in proc.call_args_list],
                                 ["mut-prefix-lost", "mut-all405", "mut-pattern", "mut-rank"])
            src = obj.fresh / "apidoor/routes.go"
            src.write_text(src.read_text().replace("prefixed: true", "prefixed: false"))
            with patch(__name__ + ".probes", return_value=self.inputs), \
                    patch(__name__ + ".run") as proc, self.assertRaises(CheckingError):
                obj.test_mutants()
            proc.assert_not_called()

    def test_unicode_and_terminal_lf_neighbours(self):
        for char in ("\u0085", "\u2028", "\u2029"):
            value = {"path": "/" + char, "method": "GET", "params": {"name": "a" + char + "b"}, "prefixed": False}
            text = self.report(self.frames([value, value])).stdout
            self.assertIn(char, text)
            for ending in (text, text[:-1]):
                with self.subTest(char=repr(char), final_lf=ending.endswith("\n")):
                    self.assertEqual(read_report(self.inputs, subprocess.CompletedProcess([], 0, ending, "")), [value, value])
        self.assertEqual(read_report(self.inputs, subprocess.CompletedProcess([], 0, self.report().stdout.encode(), "")),
                         self.results)


for _lesson, _slug in LESSONS.items():
    _name = "DoorLesson_" + _slug
    globals()[_name] = type(_name, (DoorLessonBase, unittest.TestCase), {"LESSON": _lesson, "SLUG": _slug})


if __name__ == "__main__":
    unittest.main()
