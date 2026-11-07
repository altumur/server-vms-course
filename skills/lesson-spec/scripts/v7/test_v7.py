"""Тесты генератора и стека В7: ловушки (поручение, шаг 5) и дефекты закреплённых версий (DEFECTS.tsv, ADR-0092 п. 9).

    cd skills/lesson-spec/scripts && <venv>/bin/python -B -m unittest v7.test_v7

Тесты Go (D7, D8, ловушки на Go) — если собран раннер (V7CHECK, gorun.BIN); иначе пропуск.
"""
import json
import os
import random
import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import jsonschema  # noqa: E402

from v7 import gorun, regex, schema, stack  # noqa: E402

ROOT = HERE.parents[3]
HAVE_GO = os.path.exists(gorun.BIN)
# Окружение навыка одно (scripts/requirements.txt): без cel-expr-python модуль падает с именем, а не пропускает
# тесты CEL (повторное ревью Claude Н-1).
import cel_expr_python  # noqa: F401,E402


def NEED_CEL(f):
    return f
# Генератор «диалект → стандарт» после перехода — за меткой (ADR-0092 п. 12): его ловушки — только на курсе с диалектом.
NEED_DIALECT = unittest.skipUnless((ROOT / "Platform/02-installer/spec/02.1-installer.form.yaml").is_file(),
                                   "форма диалекта снята переходом на В7 (эталон — метка dialect-reference-dc94d0fd1)")


def paths(validator, instance):
    return sorted(stack.pointer(p) for p in stack.norm(stack.py_records(validator, instance), instance))


class TestRegex(unittest.TestCase):
    def test_portable(self):
        self.assertEqual(regex.anchored("a.b"), "^(?:a[\\s\\S]b)$")
        self.assertEqual(regex.anchored("[]a]"), "^(?:[\\]a])$")
        self.assertEqual(regex.anchored("\\-\\#x"), "^(?:-#x)$")
        self.assertEqual(regex.anchored("[a\\-z]"), "^(?:[a\\-z])$")
        self.assertEqual(regex.anchored("\\x{2028}"), "^(?: )$")
        self.assertEqual(regex.anchored("\\{x\\}"), "^(?:\\{x\\})$")

    def test_manual_complements(self):
        """Дополнение MANUAL совпадает ровно с тем, что выражение диалекта не берёт целиком (эталон: re.fullmatch, S)."""
        rnd = random.Random(20261027)
        alphabet = "aZ_9-.\n/é_secret"
        for p, comp in regex.MANUAL.items():
            cases = ["", "_secret", "a_secret", "x_secret\n", "secret", "a" * 64, "a" * 65, "_" + "b" * 63, "9a"]
            cases += ["".join(rnd.choice(alphabet) for _ in range(rnd.randint(0, 70))) for _ in range(20000)]
            for s in cases:
                inside = re.fullmatch(p, s, re.S) is not None
                outside = re.fullmatch(comp, s) is not None
                self.assertNotEqual(inside, outside, (p, s))


class TestTraps(unittest.TestCase):
    """Ловушки поручения (шаг 5). Ловушки стека В7 на стандартных файлах — v7/test_spec.py TestStack (ревью Claude С-2);
    здесь — только слой 1 эталона диалекта."""

    @NEED_DIALECT
    def test_negative_integer_bound_text(self):
        from form_source.source import textlayer
        _, nums, _ = textlayer.load_text(b"a: -9007199254740992\nb: -9007199254740991\n")
        self.assertEqual([p for p, _ in nums], [["a"]])


class TestDefects(unittest.TestCase):
    """DEFECTS.tsv: красный без обхода, зелёный с ним."""

    def test_d1_dollar_before_newline(self):
        s = {"pattern": "^(?:w)$"}
        self.assertTrue(jsonschema.Draft202012Validator(s).is_valid("w\n"))
        self.assertFalse(stack.validator_for(s).is_valid("w\n"))
        # PY-JS-01: \d — класс Unicode, `.` без \n; обход — переносимое подмножество их не пускает (check_spec)
        self.assertTrue(jsonschema.Draft202012Validator({"pattern": "^(?:\\d)$"}).is_valid("\u0661"))
        self.assertFalse(jsonschema.Draft202012Validator({"pattern": "^(?:.)$"}).is_valid("\n"))
        self.assertTrue(regex.check("^(?:\\d)$") and regex.check("^(?:.)$"))
        self.assertIsNone(regex.check("^(?:[0-9][\\s\\S])$"))

    def test_d2_pattern_properties(self):
        s = {"patternProperties": {"^(?:[\\s\\S]*_secret)$": {"type": "string"}}}
        self.assertTrue(jsonschema.Draft202012Validator(s).is_valid({"a_secret\n": 1}) is False)
        s2 = {"patternProperties": {"^(?:a)$": {"type": "string"}}}
        self.assertFalse(jsonschema.Draft202012Validator(s2).is_valid({"a\n": 1}))     # дефект: имя "a\n" взято
        self.assertTrue(stack.validator_for(s2).is_valid({"a\n": 1}))

    def test_d3_false_schema_path(self):
        inst = {"o": {"k": 1}}
        bad = {"properties": {"o": {"properties": {"k": False}}}}
        self.assertEqual(paths(jsonschema.Draft202012Validator(bad), inst), ["/o"])     # дефект: имя ключа потеряно
        good = {"properties": {"o": {"properties": {"k": schema.NEVER}}}}
        self.assertEqual(paths(stack.validator_for(good), inst), ["/o/k"])

    @NEED_CEL
    def test_d4_dyn_overload(self):
        from cel_expr_python import cel
        T = cel.Type
        env = cel.NewEnv(variables={"doc": T.DYN},
                         functions=[cel.FunctionDecl("f", [cel.Overload("f_dyn", T.INT, [T.DYN], impl=lambda x: 1)])])
        self.assertEqual(env.compile("f(doc)").eval(data={"doc": {"a": 1}}).type(), T.ERROR)
        r = stack.PyCel({"env": {"extensions": []}, "rows": [{"no": 1, "cel": 'depth(doc) == 2 ? [] : [{"p": ["x"]}]'}]})
        self.assertEqual(r.run({"a": {"b": 1}}), [])

    @NEED_CEL
    def test_d5_error_value(self):
        r = stack.PyCel({"env": {"extensions": []}, "rows": [{"no": 7, "cel": "doc.missing"}]})
        with self.assertRaises(RuntimeError):
            r.run({})

    @NEED_CEL
    def test_d6_dyn_range(self):
        from cel_expr_python import cel
        env = cel.NewEnv(variables={"doc": cel.Type.DYN})
        with self.assertRaises(Exception):
            env.compile('doc["a"].exists(x, x == 1)')
        self.assertTrue(env.compile('dyn(doc["a"]).exists(x, x == 1)').eval(data={"doc": {"a": [1]}}).value())

    @unittest.skipUnless(HAVE_GO, "раннер Go не собран")
    def test_d7_go_property_names(self):
        go = gorun.Go()
        try:
            s = {"properties": {"o": {"propertyNames": {"pattern": "^(?:[a-z]+)$"}}}}
            recs = go.call({"op": "schema_inline", "schema": s, "instance": {"o": {"Bad": 1}}})["records"]
            self.assertEqual([(r["path"], r["kw"], r["extra"]) for r in recs], [(["o"], "propertyNames", "Bad")])
            raw = go.call({"op": "schema_inline", "schema": s, "instance": {"o": {"Bad": 1}}, "raw": True})["records"]
            self.assertEqual([r["path"] or [] for r in raw], [[]])     # без слоя 4: место — корень отдельной проверки
        finally:
            go.close()

    @unittest.skipUnless(HAVE_GO, "раннер Go не собран")
    def test_d8_go_double_index(self):
        go = gorun.Go()
        try:
            with self.assertRaises(gorun.GoError):
                go.call({"op": "cel_eval", "expr": 'double(doc["a"]) <= 2.0', "doc": {"a": 1}})
            self.assertTrue(go.call({"op": "cel_eval", "expr": 'double(dyn(doc["a"])) <= 2.0', "doc": {"a": 1}})["value"])
        finally:
            go.close()

    @unittest.skipUnless(HAVE_GO, "раннер Go не собран")
    def test_d18_map_order(self):
        go = gorun.Go()
        try:
            doc = {"r": {"probe/a/": 1, "probe/a/b/": 1, "x/": 1, "y": 1}}
            by_index = ('dyn(doc.r).filter(k, true).all(i, a, !(a.endsWith("/") && dyn(doc.r).filter(k, true)'
                        '.exists(j, b, j != i && b != a && b.startsWith(a))))')
            got = {go.call({"op": "cel_eval", "expr": by_index, "doc": doc})["value"] for _ in range(60)}
            self.assertEqual(got, {False, True})               # дефект: исход зависит от порядка перебора
            fixed = ('dyn(doc.r).filter(k, true).all(a, !(a.endsWith("/") && dyn(doc.r).filter(k, true)'
                     '.exists(b, b != a && b.startsWith(a))))')
            got = {go.call({"op": "cel_eval", "expr": fixed, "doc": doc})["value"] for _ in range(60)}
            self.assertEqual(got, {False})
        finally:
            go.close()


    @NEED_CEL
    def test_d24_two_var_by_name(self):
        """D24 (PY-CEL-02): two-var-comprehensions — только по имени в конфигурации окружения (модуля в ext нет); без
        него transformList не собирается; несуществующее имя принимается молча — PyCel сверяет имена со своим перечнем."""
        from cel_expr_python import cel

        def env(names):
            y = "name: r\n" + ("extensions:\n" + "".join("  - name: %s\n" % n for n in names) if names else "")
            return cel.NewEnv(config=cel.NewEnvConfigFromYaml(y), variables={"doc": cel.Type.DYN})
        expr = "[1, 2].transformList(i, v, v * 2)"
        self.assertFalse(hasattr(getattr(cel, "ext", None), "two_var_comprehensions"))
        with self.assertRaises(Exception):
            env([]).compile(expr)
        self.assertEqual(env(["two-var-comprehensions"]).compile(expr).eval(data={"doc": {}}).plain_value(), [2, 4])
        env(["no-such-extension"])                                           # дефект: принято молча
        with self.assertRaisesRegex(ValueError, "unknown CEL extension no-such-extension"):
            stack.PyCel({"env": {"extensions": [{"name": "no-such-extension"}]}, "rows": []})

    def test_d22_json_loads(self):
        """D22 (PY-JSON-01): json CPython 3.12 — `1e400` → inf, NaN/Infinity приняты, повтор ключа — последний; стек
        (strict_json: parse_float/parse_int — лексема, parse_constant и повтор — отказ) отказывает."""
        self.assertEqual(json.loads("1e400"), float("inf"))
        self.assertTrue(json.loads("NaN") != json.loads("NaN") and json.loads("Infinity") == float("inf"))
        self.assertEqual(json.loads('{"a": 1, "a": 2}'), {"a": 2})
        for t in ("NaN", "Infinity", "-Infinity", '{"a": 1, "a": 2}'):
            with self.assertRaises(stack.Bad, msg=t):
                stack.strict_json(t)
        with self.assertRaises(stack.Bad):
            stack.strict_json("1e400", finite=True)
        self.assertEqual(stack.strict_json("1e0").lex, "1e0")                 # точная лексема, не 1.0

    def test_d23_jsonschema_places(self):
        """D23 (PY-JS-02): jsonschema 4.26.0 — место `required`, `additionalProperties: false`, `uniqueItems` —
        объект или список; стек (слой 4, LAYERS § 6) — недостающее поле, лишний ключ, элемент, равный более раннему."""
        s = {"type": "object", "required": ["a"], "additionalProperties": False,
             "properties": {"b": {"type": "array", "uniqueItems": True}}}
        inst = {"b": [1, 1], "x": 0}
        raw = sorted("/" + "/".join(map(str, e.absolute_path)) for e in jsonschema.Draft202012Validator(s).iter_errors(inst))
        self.assertEqual(raw, ["/", "/", "/b"])                              # дефект: родитель и список
        self.assertEqual(stack.Family(s, "object").judge(inst)["paths"], ["/a", "/b/1", "/x"])

    def test_d25_ruamel_rt_overlap(self):
        """D25 (PY-RY-08): ruamel typ=rt — NotImplementedError «overlap in comment» на P94K (suite ok); стек разбирает
        typ=safe — вход принят."""
        from ruamel.yaml import YAML
        from v7 import textv7
        data = (ROOT / "Platform/common/vectors/yaml-suite/inputs/P94K.yaml").read_bytes()
        with self.assertRaises(NotImplementedError):
            YAML(typ="rt").load(data.decode())
        YAML(typ="safe", pure=True).load(data.decode())
        textv7.load_text_map(data)

    @NEED_CEL
    def test_d18_python_map_order(self):
        """D18 и у cel-expr-python (cel-cpp, PY-CEL-03): порядок перебора отображения меняется от процесса к процессу."""
        import subprocess
        code = ("from cel_expr_python import cel;"
                "e = cel.NewEnv(variables={'doc': cel.Type.DYN});"
                "print(e.compile('{\"z\": 1, \"a\": 2, \"m\": 3}.map(k, k)').eval(data={'doc': {}}).plain_value())")
        orders = {subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout
                  for _ in range(8)}
        self.assertGreater(len(orders), 1, orders)

    def test_d19_dialect_p1_states(self):
        """D19 — дефект эталона по метке: П1 без `state.<имя>` (ADR-0091 п. 3; V7-P022-SNAPSHOT-STATE-01). Эталон метки
        (form_source и форма P/02.1 из `git archive`) даёт `snapshot` без состояний, стек В7 — с ними, кроме `cursor`;
        SUT `dialect` узнаёт ровно это расхождение (sut.p1_states)."""
        import subprocess
        import tempfile
        from v7 import project, textv7
        from v7.sut import sut
        data = (b"name: probe\nunit:\n  rows: counters\n  id: name\n  fields:\n    name: {type: string, required: true}\n"
                b"  state:\n    result: {type: object, properties: {state: {type: string}}}\n"
                b"    cursor: {type: object, properties: {at: {type: int}}}\n"
                b"placement:\n  capacity: {default: 4}\nworker: {exec: /usr/lib/probe/worker}\n")
        with tempfile.TemporaryDirectory() as d:
            tar = subprocess.run(["git", "-C", str(ROOT), "archive", sut.TAG, "skills/lesson-spec/scripts",
                                  "Platform/02-installer/spec"], capture_output=True, check=True).stdout
            subprocess.run(["tar", "-x", "-C", d], input=tar, check=True)
            (Path(d) / "in.yaml").write_bytes(data)
            code = ("import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1] + '/skills/lesson-spec/scripts');"
                    "from form_source import Loader, canonical as can;"
                    "b = Path(sys.argv[1] + '/Platform/02-installer/spec/02.1-installer');"
                    "ld = Loader(*(Path(str(b) + s) for s in ('.form.yaml', '.references.tsv', '.scalars.tsv')));"
                    "sys.stdout.buffer.write(can.canonical_bytes(ld, Path(sys.argv[1] + '/in.yaml').read_bytes()))")
            run = subprocess.run([sys.executable, "-I", "-c", code, d], capture_output=True)
            self.assertEqual(run.returncode, 0, run.stderr.decode("utf-8", "replace")[-800:])
            old = run.stdout
        base = ROOT / "Platform/02-installer/spec/02.1-installer"
        textv7.use_scalars(Path(str(base) + ".scalars.tsv"))
        m = stack.Manifest(json.loads(Path(str(base) + ".schema.json").read_text(encoding="utf-8")),
                           json.loads(Path(str(base) + ".relations.json").read_text(encoding="utf-8")))
        r = m.judge(data)
        new = stack.jcs(project.canonical(m.sch, r["tree"])).encode("utf-8")
        self.assertEqual(json.loads(old)["snapshot"], ["name"])                           # дефект: без состояний
        self.assertEqual(json.loads(new)["snapshot"], ["name", "state.result"])           # исправлено: без cursor
        self.assertTrue(sut.p1_states(new, old))
        self.assertFalse(sut.p1_states(new, new.replace(b'"name"]', b'"name","x"]')))


    @staticmethod
    def _role_binding_document():
        """Approved bounded fixture only; not adoption of a later Source/profile revision."""
        return json.loads(r'''{"$schema":"https://json-schema.org/draft/2020-12/schema","type":"object","properties":{},"propertyNames":{"type":"string"},"additionalProperties":{"description":"fields of the mark: `at`, `done` (N1.1 domain/deleting); the reader does not refuse by them: at absent or unreadable \u2014 there is no term","x-codec":["any"]},"$defs":{"common.time":{"description":"time N0 P/01.1 \u00abTime in a row\u00bb","type":["string","number"],"x-time":true},"common.person_name":{"description":"the person's name (P/08.4 N1.1 name): 1\u201364 characters without whitespace, control characters (U+0000\u2013U+001F, U+007F) and : | ( ) \" /; not exactly break-glass; whitespace \u2014 the White_Space property of Unicode 15.0.0, written out as characters (the Architect's decision of 2026-10-20 on the questions of assembling lesson 8, item 3); \u00abnot a subject of the name index\u00bb \u2014 a check of the door (chapter 8.5 N1.7), not the form","type":"string","not":{"enum":["break-glass"]},"pattern":"^(?:[^\u0000- \u007f\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000:|()\"/]{1,64})$"},"writer":{"x-max-names":0},"person_writer":{"type":"object","properties":{"at":{"$ref":"#/$defs/common.time","x-codec":["time"]},"done":{"type":"boolean","x-codec":["boolean"]}},"required":["at"],"additionalProperties":false},"role_writer":{"type":"object","const":{}}}}''')

    def _role_binding_family(self, doc=None, identity="domain/deleting/<name>"):
        return stack.Family(self._role_binding_document() if doc is None else doc, "row", family_template=identity)

    def _role_binding_template(self):
        from v7 import spec
        table, errors = spec.placeholder_table(ROOT)
        self.assertEqual(errors, [])
        return spec.KeyTemplate("domain/deleting/<name>", table)

    def test_role_binding_person_valid(self):
        fam = self._role_binding_family()
        for done in (None, "true", "false"):
            items = {"at": "1.25"}
            if done is not None:
                items["done"] = done
            with self.subTest(done=done):
                got = fam.judge(items, "writer", key="domain/deleting/alice")
                self.assertEqual((got["verdict"], got["paths"]), ("ok", []))
                self.assertIs(type(got["value"]["at"]), float)
                self.assertEqual(got["value"]["at"], 1.25)
                if done is not None:
                    self.assertIs(got["value"]["done"], done == "true")

    def test_role_binding_person_empty(self):
        got = self._role_binding_family().judge({}, "writer", key="domain/deleting/alice")
        self.assertEqual((got["verdict"], got["paths"], got["value"]), ("refused", ["/at"], {}))

    def test_role_binding_role_empty(self):
        got = self._role_binding_family().judge({}, "writer", key="domain/deleting/role:editors")
        self.assertEqual((got["verdict"], got["paths"], got["value"]), ("ok", [], {}))

    def test_role_binding_role_nonempty(self):
        fam = self._role_binding_family()
        for items in ({"at": "1.25"}, {"done": "true"}, {"at": "bad"}, {"extra": "x"},
                      {"at": 1.25}, {"done": False}, {"extra": {}}, {"at": "1.25", "done": "false"}):
            with self.subTest(items=items):
                got = fam.judge(items, "writer", key="domain/deleting/role:editors")
                self.assertEqual(got["verdict"], "refused")
                self.assertTrue(got["paths"], "no decoding/field erasure may accept a nonempty role mark")

    def test_role_binding_person_bad_at(self):
        fam = self._role_binding_family()
        for value in ("bad", "1.2345", "-1", "1e0", "NaN", "Infinity", "", 1.25, True, None, []):
            with self.subTest(value=value):
                got = fam.judge({"at": value}, "writer", key="domain/deleting/alice")
                self.assertEqual(got["verdict"], "refused")
                self.assertIn("/at", got["paths"])
        self.assertEqual(fam.judge({}, "writer", key="domain/deleting/alice")["paths"], ["/at"])

    def test_role_binding_person_bad_done(self):
        fam = self._role_binding_family()
        for value in ("True", "1", "", "null", "falsex", True, 1, None, {}):
            with self.subTest(value=value):
                got = fam.judge({"at": "1.25", "done": value}, "writer", key="domain/deleting/alice")
                self.assertEqual(got["verdict"], "refused")
                self.assertIn("/done", got["paths"])

    def test_role_binding_person_extra(self):
        fam = self._role_binding_family()
        for value in ("x", True, 1, {}):
            got = fam.judge({"at": "1.25", "extra": value}, "writer", key="domain/deleting/alice")
            self.assertEqual(got["verdict"], "refused")
            self.assertIn("/extra", got["paths"])

    def test_role_binding_key_before_value(self):
        from unittest.mock import patch
        from v7 import spec
        fam, template = self._role_binding_family(), self._role_binding_template()
        class Poison:
            def __deepcopy__(self, memo):
                raise AssertionError("key must be checked before examining/copying value")
        for key in ("elsewhere/alice", "domain/deleting/", "domain/deleting/role:",
                    "domain/deleting/a b", "domain/deleting/role:a:b", "domain/deleting/a/b",
                    "domain/deleting/.", "domain/deleting/.."):
            with self.subTest(key=key):
                got = fam.judge(Poison(), "writer", key=key)
                self.assertEqual((got["verdict"], got["paths"]), ("refused", [""]))
                with patch.object(spec, "family_value", side_effect=AssertionError("premature value parser")) as parse:
                    got = spec.judge_family(fam, template, key, "row", Poison(), "writer")
                    self.assertEqual((got["verdict"], got["paths"]), ("refused", [""]))
                    parse.assert_not_called()

    def test_role_binding_missing_context(self):
        from unittest.mock import patch
        from v7 import spec
        doc = self._role_binding_document()
        for identity in (None, "other/<name>"):
            fam = self._role_binding_family(doc, identity)
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                fam.judge({}, "writer", key="domain/deleting/role:editors")
        fam, template = self._role_binding_family(), self._role_binding_template()
        for key in (None, True, 1):
            with self.subTest(key=key), self.assertRaises(ValueError):
                fam.judge({}, "writer", key=key)
            with self.subTest(wrapper=key), self.assertRaises(spec.SpecError):
                spec.judge_family(fam, template, key, "row", "{}", "writer")
        with self.assertRaises(ValueError):
            fam.judge({}, "writer")
        wrong = self._role_binding_family(doc, "other/<name>")
        with patch.object(spec, "family_value", side_effect=AssertionError("identity must precede value")), \
                self.assertRaises(spec.SpecError):
            spec.judge_family(wrong, template, "domain/deleting/alice", "row", "{}", "writer")

    def test_role_binding_alternating_contexts(self):
        doc = self._role_binding_document()
        before = json.dumps(doc, ensure_ascii=True, sort_keys=True)
        fam = self._role_binding_family(doc)
        writer, schema, validator = fam.writer, fam.sch, fam.sch.v
        attributes = set(fam.__dict__)
        for order in (("person", "role"), ("role", "person")):
            for chosen in order:
                items = {"at": "1.25", "done": "true"} if chosen == "person" else {}
                key = "domain/deleting/alice" if chosen == "person" else "domain/deleting/role:editors"
                input_before = json.dumps(items, sort_keys=True)
                self.assertEqual(fam.judge(items, "writer", key=key)["verdict"], "ok")
                self.assertEqual(json.dumps(items, sort_keys=True), input_before)
                self.assertEqual(fam.judge({"at": "garbled"}, "reader", key=key)["value"], {"at": "garbled"})
                self.assertEqual(fam.judge({}, "reader")["verdict"], "ok")
                self.assertEqual(json.dumps(doc, ensure_ascii=True, sort_keys=True), before)
                self.assertIs(fam.writer, writer)
                self.assertIs(fam.sch, schema)
                self.assertIs(fam.sch.v, validator)
                self.assertIs(fam.sch.doc, doc)
                self.assertEqual(set(fam.__dict__), attributes)

    def test_role_binding_local_ref_base(self):
        doc = self._role_binding_document()
        doc["$defs"]["common.time"]["maximum"] = 2
        fam = self._role_binding_family(doc)
        self.assertEqual(fam.judge({"at": "1.25"}, "writer", key="domain/deleting/alice")["verdict"], "ok")
        got = fam.judge({"at": "3"}, "writer", key="domain/deleting/alice")
        self.assertEqual(got["verdict"], "refused")
        self.assertIn("/at", got["paths"], "local ref must resolve from original complete document")
        # Isolate x-time from the initial time codec: the original referenced annotation still applies.
        doc = self._role_binding_document()
        doc["$defs"]["person_writer"]["properties"]["at"]["x-codec"] = ["any"]
        fam = self._role_binding_family(doc)
        got = fam.judge({"at": "1.2345"}, "writer", key="domain/deleting/alice")
        self.assertEqual(got["verdict"], "refused")
        self.assertIn("/at", got["paths"])

    def test_role_binding_root_and_common(self):
        doc = self._role_binding_document()
        doc["$defs"]["person_writer"]["additionalProperties"] = True
        fam = self._role_binding_family(doc)
        self.assertEqual(fam.judge({"at": "1.25", "done": "false"}, "writer", key="domain/deleting/alice")["verdict"], "ok")
        got = fam.judge({"at": "1.25", "extra": "x"}, "writer", key="domain/deleting/alice")
        self.assertEqual(got["verdict"], "refused")
        self.assertIn("", got["paths"], "common x-max-names0 survives profile selection")
        doc = self._role_binding_document()
        doc["propertyNames"] = {"pattern": "^(?:at)$"}
        got = self._role_binding_family(doc).judge({"at": "1.25", "done": "true"}, "writer", key="domain/deleting/alice")
        self.assertEqual(got["verdict"], "refused")
        self.assertIn("/done", got["paths"])

    def test_role_binding_reader_unchanged(self):
        doc = self._role_binding_document()
        ordinary, contextual = stack.Family(doc, "row"), self._role_binding_family(doc)
        for items in ({}, {"at": "garbled"}, {"done": "not-bool"}, {"at": 1}, {"extra": "x"}):
            for key in (None, "domain/deleting/alice", "domain/deleting/role:editors"):
                with self.subTest(items=items, key=key):
                    self.assertEqual(contextual.judge(items, "reader", key=key), ordinary.judge(items, "reader"))
        manual = [({}, "ok", [], {}), ({"at": "garbled"}, "ok", [], {"at": "garbled"}),
                  ({"done": "not-bool"}, "ok", [], {"done": "not-bool"}),
                  ({"at": 1}, "refused", ["/at"], {}), ({"extra": "x"}, "ok", [], {"extra": "x"})]
        for items, verdict, paths_, value in manual:
            got = contextual.judge(items, "reader")
            self.assertEqual((got["verdict"], got["paths"], got["value"]), (verdict, paths_, value))

    def test_role_binding_incomplete_source(self):
        from unittest.mock import patch
        for removed in (("person_writer",), ("role_writer",), ("person_writer", "role_writer"),
                        ("writer",), ("common.time",), ("common.person_name",)):
            doc = self._role_binding_document()
            for name in removed:
                del doc["$defs"][name]
            fam = self._role_binding_family(doc)
            with self.subTest(removed=removed), patch.object(fam, "decode", side_effect=AssertionError("no codec before source")), \
                    self.assertRaises(ValueError):
                fam.judge({"at": "1.25"}, "writer", key="domain/deleting/alice")
        for name in ("person_writer", "role_writer"):
            for wrong in (None, True, "profile", []):
                doc = self._role_binding_document()
                doc["$defs"][name] = wrong
                with self.subTest(name=name, wrong=wrong), self.assertRaises(ValueError):
                    self._role_binding_family(doc).judge({}, "writer", key="domain/deleting/role:editors")
        with self.assertRaises(ValueError):
            stack.Family(self._role_binding_document(), "row").judge({}, "writer", key="domain/deleting/role:editors")

    def test_role_binding_existing_name_grammar(self):
        fam = self._role_binding_family()
        for name in ("alice", "\u00e9", "\u0438\u043c\u044f", "a" * 64):
            self.assertEqual(fam.judge({"at": "1.25"}, "writer", key="domain/deleting/" + name)["verdict"], "ok")
            self.assertEqual(fam.judge({}, "writer", key="domain/deleting/role:" + name)["verdict"], "ok")
        class Poison:
            def __deepcopy__(self, memo):
                raise AssertionError("invalid source name must precede value")
        for name in ("", "a" * 65, "break-glass", "a b", "a:b", "a|b", "a(b", "a)b", 'a"b', "a/b", "a\x00b",
                     "a\x7fb", "a\u0085b", "a\u2028b", "a\u3000b"):
            for prefix in ("domain/deleting/", "domain/deleting/role:"):
                with self.subTest(name=name, prefix=prefix):
                    got = fam.judge(Poison(), "writer", key=prefix + name)
                    self.assertEqual((got["verdict"], got["paths"]), ("refused", [""]))

    def test_role_binding_noncontext_unchanged(self):
        row = {"type": "object", "properties": {"n": {"type": "integer", "x-codec": ["integer"]}},
               "additionalProperties": False, "$defs": {"writer": {"x-max-names": 0}}}
        for identity in (None, "ordinary/<name>"):
            fam = stack.Family(row, "row", family_template=identity)
            got = fam.judge({"n": "2"}, "writer")
            self.assertEqual((got["verdict"], got["value"]), ("ok", {"n": 2}))
            self.assertEqual(fam.judge({"n": "2"}, "writer", key="ordinary/a"), got)
            self.assertEqual(fam.judge({"n": "2.5"}, "writer")["verdict"], "refused")
        obj = stack.Family({"type": "object", "required": ["n"]}, "object")
        self.assertEqual(obj.judge('{"n":1}', "writer")["value"], {"n": 1})
        self.assertEqual(obj.judge('{}', "writer")["paths"], ["/n"])
        file = stack.Family({"type": "string", "minLength": 1}, "file")
        self.assertEqual(file.judge(b"ok", "writer")["value"], "ok")
        self.assertEqual(file.judge(b"", "writer")["verdict"], "refused")


class TestRelations(unittest.TestCase):
    """Слой связей: равенство диалекта — числа по значению (`1 = 1.0`, свод Ф9), bool не число (DIALECT § 6); формой
    манифеста недостижимо (ADR-0087 доп. (6)) — проверено на среде CEL связей обоих языков (решение по набору Б, r10)."""

    EXPRS = {'doc.a == doc.b': True, 'doc.a in [doc.b]': True, 'doc.t == doc.a': False, 'doc.t in [1, 1.0]': False,
             '[doc.a] == [doc.b]': True, '{"k": doc.a} == {"k": doc.b}': True, 'doc.s == doc.a': False}
    DOC = {"a": 1, "b": 1.0, "t": True, "s": "1"}

    @NEED_CEL
    def test_python(self):
        rows = [{"no": i, "cel": "(%s) ? [] : [{\"p\": [\"x\"]}]" % e} for i, e in enumerate(self.EXPRS)]
        r = stack.PyCel({"env": {"extensions": [{"name": "strings"}, {"name": "two-var-comprehensions"}]},
                         "rows": rows}).run(self.DOC)
        got = {list(self.EXPRS)[no]: False for no, _ in r}
        self.assertEqual({e: got.get(e, True) for e in self.EXPRS}, self.EXPRS)

    @unittest.skipUnless(HAVE_GO, "раннер Go не собран")
    def test_go(self):
        go = gorun.Go()
        try:
            for e, want in self.EXPRS.items():
                self.assertEqual(go.call({"op": "cel_eval", "expr": e, "doc": self.DOC})["value"], want, e)
        finally:
            go.close()


class TestYaml(unittest.TestCase):
    """Слой 1 (п. 2) на обоих языках: дефекты парсеров D9–D17, D20, D21 — красный без своей проверки (парсер один), зелёный со
    слоем; на Go — если собран раннер."""

    def both(self, data):
        from v7 import textv7
        out = []
        mods = [textv7] + ([self.go.text] if HAVE_GO else [])
        for m in mods:
            try:
                m.load_text_map(data)
                out.append("ok")
            except m.TextRefused as exc:
                out.append("refused:" + exc.rule)
        return out

    @classmethod
    def setUpClass(cls):
        cls.go = gorun.Go() if HAVE_GO else None

    @classmethod
    def tearDownClass(cls):
        if cls.go:
            cls.go.close()

    def go_parses(self, data):
        r = self.go.call({"op": "yaml_docs", "data": __import__("base64").b64encode(data).decode()})
        return "parse_error" not in r

    def ruamel_parses(self, data):
        from ruamel.yaml import YAML
        y = YAML(typ="safe", pure=True)
        try:
            list(y.parse(data.decode()))
            return True
        except Exception:                        # noqa: BLE001
            return False

    def test_d9_ruamel_big_escape(self):
        d = b'a: "\\UFFFFFFFF"\n'
        self.assertTrue(all(x.startswith("refused") for x in self.both(d)))

    def test_d10_flow_empty_value(self):
        d = b"lease: {unconfirmed_max:}\n"
        self.assertEqual(set(self.both(d)), {"refused:flow"})

    def test_d20_ruamel_continuation_column0(self):
        """D20 (линия Python PY-RY-01): ruamel.yaml принимает строки продолжения потока и кавычек на колонке 0 и с TAB в
        начале (yaml-test-suite 9C9N, QB6E, DK95/01, Y79Y/003 — suite error); слой 1 отказывает своими правилами
        (rare-95, tab) — как пакет yaml-suite."""
        self.suite_layer1((("9C9N", "rare-95"), ("QB6E", "rare-95"), ("DK95/01", "tab"), ("Y79Y/003", "tab")))

    def test_d11_comment_after_quote(self):
        d = b'key: "value"# c\n'
        self.assertTrue(self.ruamel_parses(d))                        # дефект парсера
        self.assertEqual(set(self.both(d)), {"refused:lexis"})
        self.suite_layer1((("SU5Z", "comment-tight"), ("9JBA", "comment-tight"), ("CVW2", "root")))   # PY-RY-02

    def suite_layer1(self, cases, parses=True):
        """Входы yaml-test-suite пакета yaml-suite: ruamel принимает (parses) или падает не YAMLError-ом; слой 1 отказывает
        правилом rule."""
        from v7 import textv7, thin_rules
        inputs = ROOT / "Platform/common/vectors/yaml-suite/inputs"
        for tid, rule in cases:
            data = (inputs / (tid + ".yaml")).read_bytes()
            self.assertEqual(self.ruamel_parses(data), parses, tid)
            with self.assertRaises(textv7.TextRefused, msg=tid) as cm:
                textv7.load_text_map(data)
            self.assertEqual(thin_rules.rule_of(cm.exception), rule, tid)

    def test_flow_dash(self):
        """V7-FLOW-DASH-01 (26-е правило): одиночный `-` простым скаляром в потоке — отказ text на обоих языках, раньше
        корня (G5U8, YJV2); `"-"`, `-x` в потоке и `-` в блоке — не правило."""
        for d in (b"a: [-, x]\n", b"a: [-]\n", b"a: {b: [x, -]}\n", b"- [-, -]\n", b"[-]\n"):
            self.assertEqual(set(self.both(d)), {"refused:flow-dash"}, d)
        for d in (b'a: ["-", x]\n', b"a: [-x, x]\n", b"a:\n  - -\n"):
            self.assertEqual(set(self.both(d)), {"ok"}, d)
        self.suite_layer1((("G5U8", "flow-dash"), ("YJV2", "flow-dash")))

    def test_d21_ruamel_directives(self):
        """D21 (PY-RY-03): директива после содержимого принята; `%YAML 1.3`, `...` в конце — падение разбора; слой 1 —
        directive и doc-end по байтам."""
        self.suite_layer1((("9HCY", "directive"), ("EB22", "directive"), ("RHX7", "directive"),
                           ("MUS6/01", "directive")))
        self.suite_layer1((("BEC7", "directive"), ("HWV9", "doc-end"), ("M7A3", "doc-end"), ("QT73", "doc-end")),
                          parses=False)

    @unittest.skipUnless(HAVE_GO, "раннер Go не собран")
    def test_d12_escape_quote(self):
        d = b"double: \"quoted \\' scalar\"\n"
        self.assertTrue(self.go_parses(d))
        self.assertEqual(set(self.both(d)), {"refused:lexis"})

    @unittest.skipUnless(HAVE_GO, "раннер Go не собран")
    def test_d13_escaped_slash(self):
        d = b'a: "x\\/y"\n'
        self.assertFalse(self.go_parses(d))                            # дефект парсера
        self.assertEqual(self.both(d), ["ok", "ok"])
        self.assertEqual(self.go.text.load_text_map(d)[0], {"a": "x/y"})

    @unittest.skipUnless(HAVE_GO, "раннер Go не собран")
    def test_d14_block_header(self):
        d = b"block: ># comment\n  scalar\n"
        self.assertTrue(self.go_parses(d))
        self.assertTrue(all(x.startswith("refused") for x in self.both(d)))

    @unittest.skipUnless(HAVE_GO, "раннер Go не собран")
    def test_d15_block_leading(self):
        d = b"empty block scalar: >\n \n  \n   \n # comment\n"
        self.assertTrue(self.go_parses(d))
        self.assertTrue(all(x.startswith("refused") for x in self.both(d)))

    def test_d16_trailing_spaces(self):
        """Обход D16: последняя строка без LF получает LF до разбора — значение блочного скаляра по YAML 1.2.2."""
        from v7 import textv7
        d = b"foo: |\n  x\n   "
        from ruamel.yaml import YAML
        self.assertEqual(YAML(typ="safe", pure=True).load(d.decode()), {"foo": "x\n "})     # дефект парсера
        self.assertEqual(textv7.load_text_map(d)[0], {"foo": "x\n \n"})
        if HAVE_GO:
            self.assertEqual(self.go.text.load_text_map(d)[0], {"foo": "x\n \n"})
        self.assertEqual(set(self.both(b"a: b\n  ")), {"ok"})                                # не отказ

    def test_escape_tab_ok(self):
        """`\\<TAB>` в двойных кавычках — экранирование (YAML 1.2.2, Н1.1), не литеральный TAB (п. 4)."""
        from v7 import textv7
        d = b'a: "x\\\ty"\n'
        self.assertEqual(textv7.load_text_map(d)[0], {"a": "x\ty"})
        if HAVE_GO:
            self.assertEqual(self.go.text.load_text_map(d)[0], {"a": "x\ty"})
        self.assertEqual(set(self.both(b'a: "x\ty"\n')), {"refused:tab"})

    @unittest.skipUnless(HAVE_GO, "раннер Go не собран")
    def test_d17_doc_end(self):
        d = b"a: b\n...\n"
        self.assertTrue(self.go_parses(d))
        self.assertEqual(set(self.both(d)), {"refused:document"})

    def test_tab_only_in_comment(self):
        self.assertEqual(set(self.both(b"a: b # x\ty\n")), {"ok"})
        self.assertEqual(set(self.both(b'a: "x\ty"\n')), {"refused:tab"})
        self.assertEqual(set(self.both(b"a: |\n  x\ty\n")), {"refused:tab"})

    def test_rare_rules(self):
        for d in (b"a: [b,\n  c]\n", b'a: "b\n  c"\n', b"a: |2\n   x\n", b"? a\n: b\n", b"%YAML 1.2\n---\na: b\n"):
            self.assertTrue(all(x.startswith("refused") for x in self.both(d)), d)

    def test_style_scalars(self):
        from v7 import textv7
        t = textv7.load_text_map(b'a: "true"\nb: true\nc: TRUE\nd: 0x10\ne: ~\n')[0]
        self.assertEqual(t, {"a": "true", "b": True, "c": True, "d": "0x10", "e": None})
        if HAVE_GO:
            self.assertEqual(self.go.text.load_text_map(b'a: "true"\nb: true\nc: TRUE\nd: 0x10\ne: ~\n')[0], t)


if __name__ == "__main__":
    unittest.main()
