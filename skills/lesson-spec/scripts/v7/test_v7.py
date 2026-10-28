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
