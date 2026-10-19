"""Построитель источника формы (ADR-0087): сборка, ошибки сборки, загрузчик по решениям свода, раздел урока."""
import tempfile
import unittest
from pathlib import Path

from form_source import Loader, SourceError, build_section, held_rows, jcs_number, prefix_free, template, text_of
from form_source.judge import same, unique

FORM = """dialect: m10-form/1
root:
  type: object
  required:
    - name
  properties:
    name:
      type: string
      pattern: "[a-z]+"
      x-class: name
    fields:
      type: object
      ordered: true
      default: {}
      names:
        key:
          type: string
        value:
          ref: field
    list:
      type: array
      items:
        type: string
    tmpl:
      type: string
defs:
  field:
    type: object
    description: поле
    properties:
      type:
        enum:
          - string
          - int
        default: string
      enum:
        type: array
      size:
        type: integer
    rules:
      - when:
          is:
            type:
              - int
        forbid:
          - enum
"""

REFS = """# path\trelation\tclass\tnorm
path\trelation\tclass\tnorm
list[]\t. in keys(fields)\treference\tt1
tmpl\ttemplate . plain keys(fields) int keys(fields ? type = int) bare\treference\tt2
fields.$f.enum\tunique values(fields.$f.enum[])\tvalue\tt3
"""

SCALARS = """kind\tpattern\tnorm
null\tnull|Null|NULL|~|\tn
true\t[tT][rR][uU][eE]\tb
false\t[fF][aA][lL][sS][eE]\tb
int\t[-+]?[0-9]+\ti
float\t[-+]?(\\.[0-9]+|[0-9]+(\\.[0-9]*)?)([eE][-+]?[0-9]+)?\tf
nonfinite\t[-+]?\\.(inf|Inf|INF)\tf
nonfinite\t\\.(nan|NaN|NAN)\tf
string\t.*\ts
limit\tint_max=9007199254740991\ti
limit\tfloat_max=1.7976931348623157e308\tf
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.write(FORM, REFS, SCALARS)

    def write(self, form=None, refs=None, scalars=None):
        for name, text in (("s.form.yaml", form), ("s.references.tsv", refs), ("s.scalars.tsv", scalars)):
            if text is not None:
                (self.dir / name).write_text(text, encoding="utf-8")

    def paths(self):
        return self.dir / "s.form.yaml", self.dir / "s.references.tsv", self.dir / "s.scalars.tsv"

    def loader(self):
        return Loader(*self.paths())

    def judge(self, text):
        return self.loader().judge(text.encode("utf-8"))


class BuildTests(Base):
    def test_builds(self):
        section = build_section(*self.paths())
        self.assertIn("### Форма (построена из источника)", section)
        self.assertIn("запрещены `enum`", section)
        self.assertIn("порядок автора (ordered)", section)
        self.assertIn("#### Таблица скаляров", section)
        self.assertIn("| 5 | `fields.$f.enum` |", section)   # номер — строка файла

    def test_section_follows_the_source(self):
        before = build_section(*self.paths())
        self.write(FORM.replace("          - int\n        default", "          - int\n          - float\n        default"))
        self.assertNotEqual(before, build_section(*self.paths()))

    def error(self, form=None, refs=None):
        self.write(form, refs)
        with self.assertRaises(SourceError) as ctx:
            self.loader()
        return str(ctx.exception)

    def test_path_not_in_form(self):
        self.assertIn("is not a place of the form", self.error(refs=REFS + "nosuch\t. = x\tvalue\tt\n"))
        self.assertIn("is not a place of the form", self.error(refs=REFS + "tmpl\t. in keys(nosuch)\tvalue\tt\n"))

    def test_rule_key_not_in_mapping(self):
        self.assertIn("rule names key 'nosuch'", self.error(form=FORM.replace("          - enum\n", "          - nosuch\n")))

    def test_pattern_outside_the_subset(self):
        self.assertIn("outside the dialect", self.error(form=FORM.replace('"[a-z]+"', '"\\\\d+"')))
        self.assertIn("repeat", self.error(form=FORM.replace('"[a-z]+"', '"[a-z]{1,1001}"')))

    def test_unquoted_regex(self):
        self.assertIn("quoted string", self.error(refs=REFS + "tmpl\t. ~ a.*\tvalue\tt\n"))
        self.write(refs=REFS + 'tmpl\t. ~ "a.*"\tvalue\tt\n')
        self.loader()

    def test_ordered_value_with_name(self):
        self.assertIn("ordered", self.error(form=FORM.replace("      size:\n", "      name:\n        type: string\n      size:\n")))

    def test_form_is_read_by_the_text_layer(self):
        self.assertIn("text layer", self.error(form=FORM.replace("    - name\n", "    [name,\n     x]\n", 1)))

    def test_tsv_is_not_yaml(self):
        self.assertIn("columns", self.error(refs=REFS + "tmpl . = x\n"))


class LoaderTests(Base):
    def test_ok(self):
        got = self.judge("name: a\nfields:\n  f:\n    type: int\nlist:\n  - f\n")
        self.assertEqual(got["verdict"], "ok", got)

    def test_classes_and_canonical_paths(self):
        got = self.judge("name: A\n")
        self.assertEqual((got["class"], got["paths"]), ("name", [["name"]]))
        got = self.judge("name: a\nzz: 1\naa: 2\n")
        self.assertEqual((got["class"], got["paths"], got["lines"]), ("key", [["aa"], ["zz"]], [2, 3]))

    def test_node_rules_run_with_failures_below(self):
        # Р1: правило поля (forbid enum при type: int) — и при отказе size ниже; пути — каноническим порядком.
        got = self.judge("name: a\nfields:\n  f:\n    type: int\n    size: x\n    enum: [a]\n")
        self.assertEqual((got["class"], got["paths"]), ("value", [["fields", "f", "enum"], ["fields", "f", "size"]]))

    def test_default_in_rule_condition(self):
        # Ф23: умолчание type: string — правило type: int не срабатывает.
        self.assertEqual(self.judge("name: a\nfields:\n  f:\n    enum: [a]\n")["verdict"], "ok")

    def test_relations_and_coverage(self):
        got = self.judge("name: a\nfields:\n  f: {}\nlist:\n  - g\n")
        self.assertEqual((got["class"], got["layer"], got["paths"]), ("reference", "relations", [["list", 0]]))
        self.assertEqual(held_rows([got]), {3})
        got = self.judge("name: a\nfields:\n  f:\n    enum: [1, 1.0]\n")
        self.assertEqual((got["class"], got["paths"]), ("value", [["fields", "f", "enum"]]))

    def test_template_row(self):
        self.assertEqual(self.judge("name: a\nfields:\n  f: {}\ntmpl: \"{f}\"\n")["verdict"], "ok")
        self.assertEqual(self.judge("name: a\nfields:\n  f: {}\ntmpl: \"{f:}\"\n")["class"], "reference")
        self.assertEqual(self.judge("name: a\nfields:\n  f: {}\ntmpl: \"{f{g}\"\n")["class"], "reference")

    def test_text_refusal_path_and_line(self):
        got = self.judge("name: a\nlist: []\nname: b\n")
        self.assertEqual((got["class"], got["paths"], got["lines"]), ("text", [["name"]], [3]))

    def test_number_out_of_range_is_value(self):
        got = self.judge("name: a\nfields:\n  f:\n    size: " + "9" * 4301 + "\n")
        self.assertEqual((got["class"], got["paths"]), ("value", [["fields", "f", "size"]]))


class CanonicalTests(Base):
    """ADR-0089 доп. (1): умолчания внутри присутствующего, ordered — массив в порядке автора, JCS (Р13 — без обёртки)."""

    def canon(self, text):
        from form_source import canonical_bytes
        return canonical_bytes(self.loader(), text.encode("utf-8"))

    def test_defaults_and_order(self):
        self.assertEqual(self.canon("name: a\nfields:\n  z:\n    size: 1\n  a: {}\n"),
                         b'{"fields":[{"name":"z","size":1,"type":"string"},{"name":"a","type":"string"}],"name":"a"}')

    def test_section_default_materializes(self):
        self.assertEqual(self.canon("name: a\n"), b'{"fields":[],"name":"a"}')

    def test_refused_has_no_view(self):
        self.assertIsNone(self.canon("name: A\n"))


class DialectVectors(unittest.TestCase):
    """Ф9 и В3 — векторами построителя, не корпусом (доп. (6)): в форме манифеста они недостижимы."""

    def test_numbers_equal_by_value(self):
        self.assertTrue(same(1, 1.0))
        self.assertFalse(same(True, 1))
        self.assertFalse(unique([1, 1.0]))

    def test_text_is_canonical(self):
        for value, text in ((1.0, "1"), (1.5, "1.5"), (True, "true"), (False, "false"), (1e21, "1e+21"),
                            (0.00000123456789, "0.00000123456789"), (1e-7, "1e-7"), (-0.0, "0"), ("a", "a")):
            self.assertEqual(text_of(value), text, value)
        self.assertEqual(jcs_number(123456789012345680000.0), "123456789012345680000")

    def test_template(self):
        self.assertFalse(template("{a{b}", ["a", "a{b"], [], False))
        self.assertFalse(template("{a:}", ["a"], ["a"], False))
        self.assertFalse(template("{a:str}", ["a"], ["a"], False))
        self.assertTrue(template("{a:int}", [], ["a"], False))
        self.assertTrue(template("x}y", [], [], False))
        self.assertFalse(template("x", [], [], True))

    def test_prefix_free_against_any_element(self):
        self.assertFalse(prefix_free(["a/", "a/b"]))
        self.assertTrue(prefix_free(["a/", "b/", "c"]))


if __name__ == "__main__":
    unittest.main()
