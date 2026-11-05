"""Судья части 3б двери урока (gen_door_lesson.py; P/06): тела по схемам — Go Validate против оракула jsonschema.

Запуск: /opt/check-env/lesson-spec/bin/python tools/normgen/test_gen_door_bodies.py [-v]   (jsonschema, referencing, go 1.22)

1. out свежий.
2. Сборка: для каждой схемы тела операции (запрос и ответы) вердикт оракула jsonschema (Draft 2020-12) по исходной схеме
   OpenAPI (внешние $ref — реестр referencing по файлам 05, 08) равен вердикту по схеме сборки bodies.go.
3. Проверка: на значениях судьи (образцы по схеме: допустимые кандидаты и их порча, плюс случайные) вердикт Go
   Validate равен вердикту оракула по сборке, для каждой схемы сборки; есть и допустимые, и недопустимые значения.
4. API: DecodeRequest / CheckResponse / EncodeResponse — объявленные media и коды, строгий JSON, default.
5. Синтетическая сборка судьи: слова, решающие исход (unevaluatedProperties у схем урока равносилен — Unit открыт),
   Go против оракула. 6. Мутанты ручной среды schema_rt.go (unevaluatedProperties, oneOf, integer, minLength в байтах,
   required) — красные на сборке урока или синтетической.
"""
import copy
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

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
LESSON, SLUG = "06-console", "p06"
GOENV = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off", GOTOOLCHAIN="local")
sys.path.insert(0, str(HERE))


def bundle_of(mod):
    s = (Path(mod) / "apidoor/bodies.go").read_text(encoding="utf-8")
    m = re.search(r"^const bundle = (\".*\")$", s, re.M)
    return json.loads(json.loads(m[1]))


def tables_of(mod):
    s = (Path(mod) / "apidoor/bodies.go").read_text(encoding="utf-8")
    req = dict(re.findall(r'^\t(Op\w+): \{("[^}]*)\},$', s[s.index("var requestSchemas"):s.index("var responseSchemas")], re.M))
    return req


class Gen:
    """Образцы значений по схеме сборки: кандидаты допустимых и их порча (вердикт решает оракул, не генератор)."""

    def __init__(self, defs, rnd):
        self.defs, self.rnd = defs, rnd

    def node(self, s):
        seen = 0
        while isinstance(s, dict) and "$ref" in s and seen < 20:
            base = {k: v for k, v in s.items() if k != "$ref"}
            s = dict(self.defs[s["$ref"].split("/")[-1]], **base) if base else self.defs[s["$ref"].split("/")[-1]]
            seen += 1
        return s

    def strings(self, s):
        out = []
        for e in s.get("enum", []):
            if isinstance(e, str):
                out.append(e)
        if isinstance(s.get("const"), str):
            out.append(s["const"])
        lo, hi = s.get("minLength", 0), s.get("maxLength")
        base = ["c1", "testsub", "a", "srv-a", "0123456789abcdef", "abc", "x_y", "UPPER", "a b", "/", ".", "..", "é",
                "0", "1", "2026-11-05T00:00:00Z", "true"]
        for b in base:
            out.append(b)
        if lo:
            out += ["a" * lo, "a" * (lo - 1) if lo > 1 else ""]
        if hi is not None:
            out += ["a" * hi, "a" * (hi + 1)]
        if "pattern" in s:
            out += self.pattern_samples(s["pattern"])
        return out

    def pattern_samples(self, p):
        """Грубые образцы под шаблон: классы символов и повторы — первые символы."""
        q = p.strip("^$")
        q = re.sub(r"^\(\?:(.*)\)$", r"\1", q)
        cand = []
        for rep in ("a", "0", "x", "ab", "a1", "0a"):
            t = re.sub(r"\[[^\]]*\]\{(\d+)(?:,\d*)?\}", lambda m: rep[0] * int(m[1]), q)
            t = re.sub(r"\[[^\]]*\][*+?]?", rep[0], t)
            t = re.sub(r"\\[ds]", "0" if rep[0] == "0" else "a", t)
            t = re.sub(r"[()?*+|^$\\{}\d,]", "", t) if len(t) > 40 else re.sub(r"[()?*+|^$\\]", "", t)
            cand.append(t)
        return [c for c in cand if len(c) < 80]

    def values(self, s, depth=0):
        s = self.node(s)
        if s is True:
            return [None, 1, "a"]
        if s is False:
            return [None]
        out = []
        if "const" in s:
            out.append(s["const"])
        out += list(s.get("enum", []))
        for k in ("anyOf", "oneOf", "allOf"):
            for sub in s.get(k, [])[:4]:
                out += self.values(sub, depth + 1)[:4]
        if "if" in s:
            out += self.values(s["if"], depth + 1)[:2]
            for k in ("then", "else"):
                if k in s:
                    out += self.values(s[k], depth + 1)[:2]
        if "allOf" in s and depth < 4:                 # объект из частей allOf: свойства и обязательные всех частей
            merged = {"properties": {}, "required": []}
            for part in s["allOf"]:
                part = self.node(part)
                if isinstance(part, dict):
                    merged["properties"].update(part.get("properties", {}))
                    merged["required"] += part.get("required", [])
            merged["properties"].update(s.get("properties", {}))
            merged["required"] += s.get("required", [])
            if merged["properties"] or merged["required"]:
                for v in self.values(dict(merged, type="object"), depth + 1)[:6]:
                    out.append(v)
        t = s.get("type")
        types = t if isinstance(t, list) else [t] if t else []
        if not types and not out:
            types = ["object"] if "properties" in s or "required" in s else ["string"]
        for ty in types:
            if ty == "string":
                out += self.strings(s)
            elif ty in ("integer", "number"):
                for k in ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"):
                    if k in s:
                        out += [s[k], s[k] - 1, s[k] + 1]
                out += [0, 1, -1, 1.5, 10 ** 20, 1.0]
            elif ty == "boolean":
                out += [True, False]
            elif ty == "null":
                out.append(None)
            elif ty == "array":
                it = s.get("items", {})
                ivals = self.values(it, depth + 1)[:3] if depth < 4 else [None]
                out += [[], ivals[:1], ivals[:2], ivals[:1] * 2]
            elif ty == "object" or (ty is None and False):
                if depth >= 4:
                    out.append({})
                    continue
                props = s.get("properties", {})
                obj = {}
                for k in s.get("required", []):
                    vs = self.values(props.get(k, {}), depth + 1)
                    obj[k] = vs[0] if vs else "a"
                out.append(obj)
                full = dict(obj)
                for k, ps in list(props.items())[:6]:
                    vs = self.values(ps, depth + 1)
                    if vs:
                        full[k] = vs[0]
                out.append(full)
                if s.get("required"):
                    drop = dict(obj)
                    drop.pop(s["required"][0], None)
                    out.append(drop)
                out.append(dict(obj, zz_extra=1))
                for k, ps in list(props.items())[:8]:     # вложенные значения: каждое свойство — своими образцами
                    for sv in self.values(ps, depth + 1)[:6]:
                        out.append(dict(obj, **{k: sv}))
                for k in list(obj)[:2]:
                    out.append(dict(obj, **{k: 12345}))
        out += [None, "", 0, {}, []] if depth == 0 else []
        uniq, seen = [], set()
        for v in out:
            key = json.dumps(v, sort_keys=True, default=str)
            if key not in seen:
                seen.add(key)
                uniq.append(v)
        return uniq[:80]


DRIVER = r'''package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"

	"%s/apidoor"
)

func main() {
	sc := bufio.NewScanner(os.Stdin)
	sc.Buffer(make([]byte, 1<<22), 1<<22)
	enc := json.NewEncoder(os.Stdout)
	for sc.Scan() {
		var c struct {
			Name  string
			Value json.RawMessage
		}
		if err := json.Unmarshal(sc.Bytes(), &c); err != nil {
			panic(err)
		}
		v, err := apidoor.StrictJSON(c.Value)
		if err != nil {
			panic(fmt.Sprint(err, string(c.Value)))
		}
		var res any
		func() {
			defer func() {
				if r := recover(); r != nil {
					res = fmt.Sprint("panic: ", r)
				}
			}()
			res = apidoor.Validate(c.Name, v) == nil
		}()
		enc.Encode(res)
	}
}
'''


def run_go(mod, cases):
    d = Path(mod) / "cmd/judgebodies"
    d.mkdir(parents=True, exist_ok=True)
    module = (Path(mod) / "go.mod").read_text().split("\n")[0].split()[1]
    (d / "main.go").write_text(DRIVER % module)
    stdin = "".join(json.dumps({"Name": n, "Value": v}, ensure_ascii=False) + "\n" for n, v in cases)
    done = subprocess.run(["go", "run", "./cmd/judgebodies"], cwd=mod, input=stdin, capture_output=True, text=True,
                          env=GOENV)
    if done.returncode:
        raise AssertionError(done.stderr[-2000:])
    return [json.loads(x) for x in done.stdout.split("\n") if x]


def oracle(defs):
    from jsonschema import Draft202012Validator
    root = {"$defs": defs}
    cache = {}

    def check(name, value):
        if name not in cache:
            cache[name] = Draft202012Validator(dict(root, **{"$ref": f"#/$defs/{name}"}))
        return cache[name].is_valid(value)
    return check


def cases_for(defs, rnd):
    g = Gen(defs, rnd)
    out = []
    for name in sorted(defs):
        for v in g.values({"$ref": f"#/$defs/{name}"}):
            out.append((name, v))
    return out


# Синтетическая сборка судьи: схемы, где слово решает исход (у схем урока unevaluatedProperties равносилен — Unit
# объявляет additionalProperties: true), и значения к ним.
SYNTH = {
    "U1": {"allOf": [{"properties": {"a": {}}}], "unevaluatedProperties": False},
    "U2": {"anyOf": [{"properties": {"a": {}}, "required": ["a"]}, {"properties": {"b": {}}, "required": ["b"]}],
           "unevaluatedProperties": False},
    "U3": {"if": {"properties": {"k": {"const": 1}}, "required": ["k"]}, "then": {"properties": {"x": {}}},
           "else": {"properties": {"y": {}}}, "unevaluatedProperties": False},
    "U4": {"properties": {"a": {}}, "patternProperties": {"^p": {}}, "unevaluatedProperties": {"type": "integer"}},
    "U5": {"$ref": "#/$defs/U1", "properties": {"b": {}}, "unevaluatedProperties": False},
    "O1": {"oneOf": [{"type": "integer"}, {"minimum": 2}]},
    "D1": {"type": "object", "dependentRequired": {"a": ["b", "c"]}},
    "N1": {"not": {"anyOf": [{"enum": [".", ".."]}, {"pattern": "/"}]}, "type": "string", "minLength": 2},
    "I1": {"type": "integer", "maximum": 10, "exclusiveMinimum": 0},
    "S1": {"type": "string", "maxLength": 2, "pattern": "^[a-zé]+$"},
    "A1": {"type": "array", "items": {"type": "string"}, "uniqueItems": True, "minItems": 1, "maxItems": 2},
    "P1": {"type": "object", "propertyNames": {"pattern": "^[a-z]+$"}, "minProperties": 1, "maxProperties": 2},
}
SYNTH_VALUES = [{}, {"a": 1}, {"b": 1}, {"a": 1, "b": 2}, {"k": 1, "x": 1}, {"k": 1, "y": 1}, {"k": 2, "y": 1},
                {"k": 2, "x": 1}, {"p1": "s", "z": 1}, {"z": "s"}, {"z": 1.0}, {"a": 1, "c": 1}, 1, 2, 3, 1.0, 2.5,
                0, 10, 10.0, 11, ".", "..", "ab", "a/b", "a", "éé", "ééé", "aa", "AB", ["x"], ["x", "x"], ["x", "y"],
                [], ["x", "y", "z"], [1], {"ab": 1}, {"Ab": 1}, {"a": 1, "b": 1, "c": 1}, None, True, "1"]
SYNTH_CASES = [(n, v) for n in SYNTH for v in SYNTH_VALUES]


def synth_module(src, dst):
    shutil.copytree(src, dst)
    p = Path(dst) / "apidoor/bodies.go"
    text = p.read_text(encoding="utf-8")
    bundle = json.dumps({"$defs": SYNTH}, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    text = re.sub(r"^const bundle = \".*\"$", lambda m: "const bundle = " + json.dumps(bundle), text, count=1, flags=re.M)
    p.write_text(text, encoding="utf-8")
    return dst


class DoorBodies(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("go"):
            raise unittest.SkipTest("go is not in PATH")
        try:
            import jsonschema  # noqa: F401
            import referencing  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("no jsonschema/referencing: /opt/check-env/lesson-spec/bin/python")
        cls.tmp = Path(tempfile.mkdtemp(prefix="door-bodies-"))
        out = cls.tmp / "fresh"
        done = subprocess.run([sys.executable, str(HERE / "gen_door_lesson.py"), "--lesson", LESSON, str(out)],
                              capture_output=True, text=True)
        if done.returncode:
            raise AssertionError(done.stderr)
        cls.fresh = out / "go"
        cls.defs = bundle_of(cls.fresh)["$defs"]
        cls.cases = cases_for(cls.defs, random.Random(36))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_fresh(self):
        for name in ("bodies.go", "schema_rt.go", "routes.go", "routes_rt.go"):
            kept = HERE / "out" / SLUG / "go/apidoor" / name
            self.assertEqual(kept.read_bytes(), (self.fresh / "apidoor" / name).read_bytes(), f"{kept} is stale")

    def test_bundle_equals_source(self):
        """Вердикт по схеме сборки = вердикт по исходной схеме OpenAPI (внешние $ref — файлы уроков)."""
        from jsonschema import Draft202012Validator
        from referencing import Registry, Resource
        from referencing.jsonschema import DRAFT202012
        import yamlsub
        spec = ROOT / "Platform" / LESSON / "spec" / f"{LESSON}.api.openapi.yaml"
        files = [spec] + [ROOT / "Platform" / f for f in ("05-resource/spec/05-resource.api.openapi.yaml",
                                                           "08-domain/spec/08-domain.api.openapi.yaml")]
        reg = Registry()
        for f in sorted((ROOT / "Platform").rglob("*.api.openapi.yaml")):   # все OpenAPI выгрузки: внешние $ref
            try:
                doc = yamlsub.load(f.read_text(encoding="utf-8"), f.name)
            except yamlsub.YamlError:
                continue                                      # вне подмножества загрузчика — не из ссылок урока
            reg = reg.with_resource(f.resolve().as_uri(), Resource(contents=doc, specification=DRAFT202012))
        check = oracle(self.defs)
        compared = 0
        for name, schema in self.defs.items():
            if name[:3] in ("05.", "08."):
                src = files[1 if name.startswith("05.") else 2]
                ref = f"{src.resolve().as_uri()}#/components/schemas/{name[3:]}"
            elif "." in name:
                continue                                      # встроенные схемы тел — их сверяет вердикт операций
            else:
                ref = f"{spec.resolve().as_uri()}#/components/schemas/{name}"
            v = Draft202012Validator({"$ref": ref}, registry=reg)
            for cname, value in self.cases:
                if cname == name:
                    self.assertEqual(v.is_valid(value), check(name, value), f"{name}: {json.dumps(value)[:200]}")
                    compared += 1
        self.assertGreater(compared, 1000)

    def test_validate_against_oracle(self):
        check = oracle(self.defs)
        got = run_go(self.fresh, self.cases)
        self.assertEqual(len(got), len(self.cases))
        bad = [(n, v, g) for (n, v), g in zip(self.cases, got) if g != check(n, v)]
        self.assertEqual(bad[:3], [], f"{len(bad)} of {len(self.cases)} disagree with jsonschema")
        valid = sum(1 for g in got if g is True)
        self.assertGreater(valid, len(got) // 10)
        self.assertGreater(len(got) - valid, len(got) // 10)

    def test_synthetic(self):
        """Семантика проверщика на синтетической сборке: каждое слово решает исход хотя бы раз."""
        mod = synth_module(self.fresh, self.tmp / "synth")
        check = oracle(SYNTH)
        got = run_go(mod, SYNTH_CASES)
        bad = [(n, v, g) for (n, v), g in zip(SYNTH_CASES, got) if g != check(n, v)]
        self.assertEqual(bad[:3], [], f"{len(bad)} of {len(SYNTH_CASES)} disagree")
        for name in SYNTH:
            verdicts = {check(n, v) for n, v in SYNTH_CASES if n == name}
            self.assertEqual(verdicts, {True, False}, f"{name}: the values do not split it")

    def test_api(self):
        prog = r'''package main

import (
	"fmt"

	"%s/apidoor"
)

func main() {
	_, v1 := apidoor.DecodeRequest(apidoor.OpPutByRowsById, "application/json", []byte(`{"a":1,"a":2}`))
	_, v2 := apidoor.DecodeRequest(apidoor.OpPutByRowsById, "text/plain", []byte(`{}`))
	_, v3 := apidoor.DecodeRequest(apidoor.OpGetHealthz, "", nil)
	v4 := apidoor.CheckResponse(apidoor.OpGetHealthz, 299, "application/json", map[string]any{})
	b, v5 := apidoor.EncodeResponse(apidoor.OpGetRoot, 200, "text/html", "<p>")
	fmt.Println(v1 != nil, v2 != nil, v3 == nil, v4 != nil, v5 == nil, string(b))
}
'''
        module = (self.fresh / "go.mod").read_text().split("\n")[0].split()[1]
        d = self.fresh / "cmd/judgeapi"
        d.mkdir(parents=True, exist_ok=True)
        (d / "main.go").write_text(prog % module)
        done = subprocess.run(["go", "run", "./cmd/judgeapi"], cwd=self.fresh, capture_output=True, text=True, env=GOENV)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.strip(), "true true true true true <p>")

    def test_mutants(self):
        check = oracle(self.defs)
        rt = (self.fresh / "apidoor/schema_rt.go").read_text()
        muts = {
            "unevaluated": rt.replace('if up, ok := n["unevaluatedProperties"]; ok {', 'if up, ok := n["zz"]; ok {', 1),
            "oneOf-as-anyOf": rt.replace("if hits != 1 {", "if hits < 1 {", 1),
            "integer": rt.replace("return ok && r.IsInt()", "return ok", 1),
            "minLength-bytes": rt.replace("l := utf8.RuneCountInString(x)", "l := len(x)", 1),
            "required": rt.replace('fail("required " + r.(string))', '_ = r', 1),
        }
        scheck = oracle(SYNTH)
        for name, text in muts.items():
            with self.subTest(mutant=name):
                self.assertNotEqual(text, rt, f"{name}: the mutant does not apply")
                bad = []
                for kind, cases, chk in (("lesson", self.cases, check), ("synth", SYNTH_CASES, scheck)):
                    mod = self.tmp / f"mut-{name}-{kind}"
                    if kind == "synth":
                        synth_module(self.fresh, mod)
                    else:
                        shutil.copytree(self.fresh, mod)
                    (mod / "apidoor/schema_rt.go").write_text(text)
                    try:
                        got = run_go(mod, cases)
                    except AssertionError:
                        bad.append("build")
                        continue
                    bad += [1 for (n, v), g in zip(cases, got) if g != chk(n, v)]
                self.assertTrue(bad, f"{name} survives")


if __name__ == "__main__":
    unittest.main()
