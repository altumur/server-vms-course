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

from form_source import families as fam  # noqa: E402
from v7 import build, gorun, regex, schema, stack  # noqa: E402

ROOT = HERE.parents[3]
HAVE_GO = os.path.exists(gorun.BIN)


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
    """Ловушки поручения (шаг 5)."""

    @classmethod
    def setUpClass(cls):
        cls.fams = {(r["key"], r["kind"]): (r, f, s) for r, f, s in build.all_families(ROOT)}
        cls.man = json.loads((HERE / "out/02.1-installer.schema.json").read_text(encoding="utf-8"))

    def family(self, key, kind):
        r, f, s = self.fams[(key, kind)]
        return f, s

    def test_empty_key_beside_names_pattern(self):
        """Ключ "" в properties рядом с names.key pattern '.+': propertyNames с исключением "" (ревью Gemini 4.2)."""
        hits = [(k, s) for k, (r, f, s) in self.fams.items()
                if '"": ' in json.dumps(s.get("$defs", {}).get("common.book_row", {}))]
        self.assertTrue(hits, "семья с common.book_row")
        book = self.fams[hits[0][0]][2]["$defs"]["common.book_row"]
        self.assertEqual(book["propertyNames"]["anyOf"][0], {"enum": [""]})
        v = stack.validator_for(dict(book, **{"$defs": self.fams[hits[0][0]][2]["$defs"]}))
        rec = stack.py_records(v, {"": "x"})
        self.assertFalse([r for r in rec if r[1] == "propertyNames"], rec)
        bare = dict(book, propertyNames=book["propertyNames"]["anyOf"][1])
        rec = stack.py_records(stack.validator_for(dict(bare, **{"$defs": self.fams[hits[0][0]][2]["$defs"]})),
                               {"": "x"})
        self.assertTrue([r for r in rec if r[1] == "propertyNames"], "без исключения ключ \"\" отказан")

    def test_trailing_newline_full_match(self):
        """$ в pattern у Python совпадает перед хвостовым \\n — у стека В7 полный матч (слой 5)."""
        s = {"type": "string", "pattern": regex.anchored("[a-z][a-z0-9_-]{0,31}")}
        self.assertTrue(jsonschema.Draft202012Validator(s).is_valid("w-1\n"))      # дефект без слоя
        self.assertFalse(stack.validator_for(s).is_valid("w-1\n"))
        self.assertTrue(stack.validator_for(s).is_valid("w-1"))

    def test_trailing_newline_manifest(self):
        m = stack.Manifest(self.man, json.loads((HERE / "out/02.1-installer.relations.json").read_text("utf-8")))
        base = (ROOT / "Platform/02-installer/acceptance/1/cases/r38_unit_minimal.subsystem.yaml").read_bytes()
        self.assertEqual(m.judge(base)["verdict"], "ok")
        bad = base.replace(b"worker: {exec: /usr/lib/probe/worker}", b'worker: {exec: "/usr/lib/probe/worker\\n"}')
        self.assertNotEqual(bad, base)
        self.assertEqual(m.judge(bad)["verdict"], "refused")

    def test_outcomes_unit(self):
        """unit исходов (DIALECT § 9): отказ ниже строки с единицей `поле`/`элемент` делает нечитаемым только её место."""
        O = fam.Outcome
        rows = [O(1, "", "строка нечитаема", 2, "строка", "n"), O(2, "/a", "поле a пропущено", 1, "поле", "n"),
                O(3, "/b", "b — строка целиком", 3, "строка", "n")]
        self.assertEqual([o.no for o in fam.outcomes_for(rows, ["/a/x"])], [2])
        self.assertEqual([o.no for o in fam.outcomes_for(rows, ["/b/x"])], [1])
        self.assertEqual([o.no for o in fam.outcomes_for(rows, ["/a/x", "/c"])], [2])
        self.assertEqual(fam.outcomes_for(rows, []), [])

    def test_negative_integer_bound(self):
        """Граница целого манифеста (п. 8): −9007199254740992 — отказ, −9007199254740991 — принято (схема), у каждого
        целого места без своей границы ниже."""
        found = []

        def rec(x):
            if isinstance(x, dict):
                if x.get("x-integer-place"):
                    found.append(x)
                for v in x.values():
                    rec(v)
            elif isinstance(x, list):
                for v in x:
                    rec(v)
        rec(self.man)
        self.assertGreater(len(found), 10)
        for x in found:
            self.assertGreaterEqual(x["minimum"], -9007199254740991)
            self.assertLessEqual(x["maximum"], 9007199254740991)
        free = [x for x in found if x["minimum"] == -9007199254740991]
        self.assertTrue(free)
        v = stack.validator_for(dict(free[0], **{"$defs": self.man["$defs"]}))
        self.assertFalse(v.is_valid(-9007199254740992))
        self.assertTrue(v.is_valid(-9007199254740991))
        self.assertTrue(v.is_valid(4.0))                      # п. 8: целое по значению

    def test_negative_integer_bound_text(self):
        from form_source.source import textlayer
        _, nums, _ = textlayer.load_text(b"a: -9007199254740992\nb: -9007199254740991\n")
        self.assertEqual([p for p, _ in nums], [["a"]])

    def test_1e400(self):
        """1e400: число JSON вне binary64 — не по грамматике json (codec.tsv): отказ на своём месте. У эталона читатель
        принимает его в месте number, писатель jcs падает (дефекты эталона, строки Б)."""
        n = 0
        for (key, kind), (r, f, s) in self.fams.items():
            if kind != "object":
                continue
            for mode in ("reader", "writer"):
                got = stack.Family(s, kind).judge('{"zz_1e400": 1e400}', mode)
                self.assertEqual(got["verdict"], "refused")
                self.assertIn("/zz_1e400", got["paths"], (key, got))
                n += 1
        self.assertGreater(n, 30)

    def test_null_root(self):
        """JSON null вместо объекта семьи — отказ на корне (у эталона на aee6716ea — принят; дефект эталона, Б)."""
        n = 0
        for (key, kind), (r, f, s) in self.fams.items():
            if kind != "object":
                continue
            for mode in ("reader", "writer"):
                got = stack.Family(s, kind).judge("null", mode)
                self.assertEqual((got["verdict"], got["paths"]), ("refused", [""]), (key, mode))
                n += 1
        self.assertGreater(n, 30)


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

    def test_d4_dyn_overload(self):
        from cel_expr_python import cel
        T = cel.Type
        env = cel.NewEnv(variables={"doc": T.DYN},
                         functions=[cel.FunctionDecl("f", [cel.Overload("f_dyn", T.INT, [T.DYN], impl=lambda x: 1)])])
        self.assertEqual(env.compile("f(doc)").eval(data={"doc": {"a": 1}}).type(), T.ERROR)
        r = stack.PyCel({"env": {"extensions": []}, "rows": [{"no": 1, "cel": 'depth(doc) == 2 ? [] : [{"p": ["x"]}]'}]})
        self.assertEqual(r.run({"a": {"b": 1}}), [])

    def test_d5_error_value(self):
        r = stack.PyCel({"env": {"extensions": []}, "rows": [{"no": 7, "cel": "doc.missing"}]})
        with self.assertRaises(RuntimeError):
            r.run({})

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


if __name__ == "__main__":
    unittest.main()
