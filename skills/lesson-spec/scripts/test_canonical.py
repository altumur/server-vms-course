"""Канонический вид главы 2.2 (ADR-0089, окно 2.2): шаги урока 2, форма и схема вида, раздел, векторы, мутации, puts.tsv."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import jsonschema

from form_source import Loader, SourceError, build_section
from form_source.canonical import (BEGIN, END, STEPS, build_view_section, canonical, ecma, jcs, schema_text,
                                   steps_of, tree_of, unique_names, view_schema)
from form_source.vectors import (ACCEPTANCE, CORPUS, NORMS, SOURCE, VECTORS, Chapter, accepted_inputs,
                                 generate, mutants, probe)

COURSE = Path(__file__).resolve().parents[3]
SUFFIXES = (".form.yaml", ".references.tsv", ".scalars.tsv")
BASE = "name: probe\nunit:\n  rows: things\n  id: numeric\n  fields:\n%s\nplacement:\n  capacity: {default: 1}\n%s"
FIELDS = "    label: {}\n    login: {}\n    pass_secret: {bound_to: login}\n    pic: {type: blob}\n    server: {}"


def course_loader():
    return Loader(*(Path(str(COURSE / SOURCE) + s) for s in SUFFIXES))


LOADER = course_loader()


def view(text, skip=()):
    data = text.encode("utf-8")
    got = LOADER.judge(data)
    if got["verdict"] != "ok":
        raise AssertionError("refused: %s %s %s" % (got["layer"], got["paths"], got["why"]))
    return json.loads(jcs(canonical(LOADER.form, tree_of(data), skip)))


def spec(fields=FIELDS, tail=""):
    return BASE % (fields, tail)


class StepsTests(unittest.TestCase):
    def test_every_step_has_its_places_in_the_lesson_form(self):
        self.assertEqual([s.name for s in steps_of(LOADER.form)], [s.name for s in STEPS])
        self.assertEqual([s.name for s in STEPS], ["tables", "bound_to", "in", "П1", "П2", "П3", "П4", "П5"])

    def test_sugar(self):
        v = view(spec(tail="tables: [a, b]\n"))
        self.assertEqual(list(v["tables"]), ["a", "b"])
        self.assertEqual(v["tables"]["a"], {"fields": [], "journal": {"written": "a.written", "deleted": "a.deleted"}})
        f = {x["name"]: x for x in v["unit"]["fields"]}
        self.assertEqual(f["pass_secret"]["bound_to"], ["login"])
        v = view(spec("    cam: {type: url, secret_in: [{regex: 'x', in: query}, {param: [p]}]}"))
        self.assertEqual(v["unit"]["fields"][0]["secret_in"], [{"decoded": True, "in": ["query"], "regex": "x"},
                                                                {"param": ["p"]}])

    def test_computed(self):
        v = view(spec())
        self.assertEqual(v["snapshot"], ["label", "login"])                                  # П1
        self.assertEqual(v["display"]["form"], [{"fields": ["label", "login", "pass_secret", "pic", "server"]}])   # П3
        self.assertTrue(all(x["default"] is None for x in v["unit"]["fields"]))             # П4, и у blob
        self.assertEqual(view(spec(tail="snapshot: []\n"))["snapshot"], [])
        self.assertEqual(view(spec(tail="display: {form: [{title: t}]}\n"))["display"]["form"], [{"title": "t"}])
        v = view(spec(tail="tables:\n  t:\n    journal: {written: w}\n"))
        self.assertEqual(v["tables"]["t"]["journal"], {"written": "w", "deleted": "t.deleted"})   # П2
        v = view(spec("    n: {type: int, inherit: 1}\n    m: {type: int, default: 2}"))
        self.assertEqual([x["default"] for x in v["unit"]["fields"]], [None, 2])
        v = view(spec("    cam: {type: url, secret_in: [{regex: 'x', decoded: false}]}"))
        self.assertEqual(v["unit"]["fields"][0]["secret_in"], [{"decoded": False, "regex": "x"}])   # П5 — не сказано

    def test_defaults_only_inside_present_parent(self):
        v = view(spec())
        self.assertNotIn("requests", v)
        self.assertEqual(v["placement"]["weight"], {"default": 1})
        self.assertEqual(v["lease"], {"unconfirmed_max": "off"})
        self.assertEqual(v["display"]["unit"], "единица")
        self.assertNotIn("section", v["display"])
        self.assertNotIn("suppress", v["events"])

    def test_ordered_keeps_the_author_order(self):
        v = view(spec("    zz: {}\n    aa: {}"))
        self.assertEqual([x["name"] for x in v["unit"]["fields"]], ["zz", "aa"])
        self.assertEqual(v["snapshot"], ["zz", "aa"])

    def test_skipping_a_step_changes_the_view(self):
        text = spec(tail="tables: [a]\n")
        for s in STEPS:
            if s.name in ("in", "П5"):
                continue
            self.assertNotEqual(view(text), view(text, (s.name,)), s.name)

    def test_steps_do_not_act_without_their_places(self):
        from test_form_source import FORM, REFS, SCALARS
        with tempfile.TemporaryDirectory() as d:
            for name, text in (("s.form.yaml", FORM), ("s.references.tsv", REFS), ("s.scalars.tsv", SCALARS)):
                (Path(d) / name).write_text(text, encoding="utf-8")
            form = Loader(*(Path(d) / ("s" + s) for s in SUFFIXES)).form
            self.assertEqual(steps_of(form), [])


class CorpusTests(unittest.TestCase):
    """Все принятые случаи корпуса 2.1 и спеки курса: проекция без исключений, повтор — те же байты, схема вида."""

    def test_accepted_inputs_project_and_pass_the_schema(self):
        schema = view_schema(LOADER.form)
        jsonschema.Draft202012Validator.check_schema(schema)
        validator = jsonschema.Draft202012Validator(schema)
        inputs = accepted_inputs(COURSE)
        self.assertGreater(len(inputs), 100)
        for case, inp in inputs:
            data = (COURSE / inp).read_bytes()
            self.assertEqual(LOADER.judge(data)["verdict"], "ok", inp)
            a = jcs(canonical(LOADER.form, tree_of(data)))
            self.assertEqual(a, jcs(canonical(LOADER.form, tree_of(data))), inp)
            v = json.loads(a)
            self.assertEqual(list(validator.iter_errors(v)), [], inp)
            self.assertEqual(unique_names(schema, v), [], inp)

    def test_schema_and_section_are_stable_and_leave_the_source_alone(self):
        before = build_section(*(Path(str(COURSE / SOURCE) + s) for s in SUFFIXES))
        self.assertEqual(schema_text(LOADER.form), schema_text(LOADER.form))
        self.assertEqual(build_view_section(LOADER.form), build_view_section(LOADER.form))
        self.assertEqual(before, build_section(*(Path(str(COURSE / SOURCE) + s) for s in SUFFIXES)))
        self.assertEqual([s.name for s in steps_of(LOADER.form)], [s.name for s in STEPS])


class SchemaTests(unittest.TestCase):
    def setUp(self):
        self.schema = view_schema(LOADER.form)
        self.validator = jsonschema.Draft202012Validator(self.schema)
        self.v = view(spec("    cam: {type: url, secret_in: [{regex: 'x'}]}", "tables: [a]\n"))

    def bad(self, change):
        v = json.loads(json.dumps(self.v))
        change(v)
        return list(self.validator.iter_errors(v))

    def test_view_passes(self):
        self.assertEqual(list(self.validator.iter_errors(self.v)), [])

    def test_closed_required_and_one_form(self):
        self.assertTrue(self.bad(lambda v: v.update(extra=1)))                         # закрыт, как форма
        self.assertTrue(self.bad(lambda v: v.pop("snapshot")))                         # П1 — обязателен
        self.assertTrue(self.bad(lambda v: v["placement"].pop("weight")))              # умолчание — обязателен
        self.assertTrue(self.bad(lambda v: v.update(tables=["a"])))                    # сахар tables — одна форма
        self.assertTrue(self.bad(lambda v: v["unit"]["fields"][0].pop("default")))     # П4
        self.assertTrue(self.bad(lambda v: v["unit"]["fields"][0]["secret_in"][0].pop("decoded")))   # П5 при regex
        self.assertTrue(self.bad(lambda v: v["unit"]["fields"][0].pop("name")))
        self.assertTrue(self.bad(lambda v: v["unit"].update(fields={})))               # ordered — список

    def test_unique_name(self):
        v = json.loads(json.dumps(self.v))
        v["unit"]["fields"].append(dict(v["unit"]["fields"][0]))
        self.assertEqual(unique_names(self.schema, v), ["/unit/fields"])

    def test_pattern_is_ecma_with_anchors(self):
        self.assertEqual(ecma(".*_secret"), "^(?:[\\s\\S]*_secret)$")
        self.assertEqual(ecma("[.]\\.x"), "^(?:[.]\\.x)$")
        self.assertEqual(ecma("[]a.]."), "^(?:[]a.][\\s\\S])$")


class SectionTests(unittest.TestCase):
    def test_section(self):
        s = build_view_section(LOADER.form)
        self.assertTrue(s.startswith("### Форма канонического вида (построена из источника)\n"))
        for line in ("| П5 | P/02.2-03 |", "| `snapshot` | список, элемент — строка | есть всегда (шаг П1) |",
                     "порядок автора, `name` без повторов (ordered)", "сахар приведён (`tables`)",
                     "если есть `regex`: обязательны `decoded`."):
            self.assertIn(line, s)
        self.assertNotIn("default_text", s)
        self.assertNotIn("класс отказа", s)


class MutantTests(unittest.TestCase):
    def test_probe_names_the_rule_no_vector_holds(self):
        typed = tree_of(spec("    a: {type: string}").encode())
        untyped = tree_of(spec("    a: {}").encode())
        form = LOADER.form
        built = [jcs(canonical(form, typed)).encode()]
        alive = probe(form, [typed], built)
        self.assertIn("default defs.fieldType", alive)
        self.assertIn("step tables", alive)
        trees = [typed, untyped]
        alive = probe(form, trees, [jcs(canonical(form, t)).encode() for t in trees])
        self.assertNotIn("default defs.fieldType", alive)
        self.assertNotIn("ordered root.unit.fields", [m for m in alive])
        self.assertEqual(schema_text(form), schema_text(course_loader().form))   # проба вернула форму как была
        self.assertGreater(len(mutants(form)), 50)


class LayoutBase(unittest.TestCase):
    """Временная раскладка: источник 2.1 курса, маленький корпус, одна спека курса."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / SOURCE).parent.mkdir(parents=True)
        for s in SUFFIXES:
            shutil.copy(str(COURSE / SOURCE) + s, str(self.root / SOURCE) + s)
        cases = self.root / CORPUS / "cases"
        cases.mkdir(parents=True)
        (self.root / CORPUS / "verdicts.tsv").write_text("# c\none\tok\ntwo\tok\nbad\trefused\n")
        (cases / "one.subsystem.yaml").write_text(spec("    a: {}"))
        (cases / "two.subsystem.yaml").write_text(spec("    a: {type: int}", "tables: [t]\n"))
        (cases / "bad.subsystem.yaml").write_text("name: X\n")
        course = self.root / "Source/tests/testdata"
        course.mkdir(parents=True)
        (course / "sub.subsystem.yaml").write_text(spec())

    def vectors(self):
        generate(self.root)
        (self.root / VECTORS / "README.md").write_text("# Векторы\n")

    def chapter(self, strict=False):
        return Chapter(self.root, strict).run()

    def messages(self, strict=False):
        return [m for _, m in self.chapter(strict).errors]


class GeneratorTests(LayoutBase):
    def test_inputs_and_repeat(self):
        self.assertEqual([c for c, _ in accepted_inputs(self.root)], ["corpus-one", "corpus-two", "course-sub"])
        self.vectors()
        vec = self.root / VECTORS
        first = {p.name: p.read_bytes() for p in (vec / "expect").iterdir()} | {"cases": (vec / "cases.tsv").read_bytes()}
        generate(self.root)
        second = {p.name: p.read_bytes() for p in (vec / "expect").iterdir()} | {"cases": (vec / "cases.tsv").read_bytes()}
        self.assertEqual(first, second)
        self.assertFalse(first["corpus-one.json"].endswith(b"\n"))
        self.assertEqual(json.loads(first["corpus-two.json"])["tables"]["t"]["fields"], [])

    def test_author_rows_kept_and_stale_expect_removed(self):
        self.vectors()
        vec = self.root / VECTORS
        (vec / "inputs").mkdir()
        (vec / "inputs/x.subsystem.yaml").write_text(spec("    b: {}"))
        with open(vec / "cases.tsv", "a") as f:
            f.write("example-x\t%s\t-\tпример\n" % (VECTORS / "inputs/x.subsystem.yaml").as_posix())
        (vec / "expect/old.json").write_text("{}")
        generate(self.root)
        text = (vec / "cases.tsv").read_text()
        self.assertIn("example-x\t%s\texpect/example-x.json\tпример\n" % (VECTORS / "inputs/x.subsystem.yaml").as_posix(), text)
        self.assertFalse((vec / "expect/old.json").exists())
        self.assertTrue((vec / "expect/example-x.json").exists())

    def test_refused_author_input(self):
        self.vectors()
        with open(self.root / VECTORS / "cases.tsv", "a") as f:
            f.write("example-bad\t%s\t-\tx\n" % (CORPUS / "cases/bad.subsystem.yaml").as_posix())
        with self.assertRaises(SourceError):
            generate(self.root)


class ChapterTests(LayoutBase):
    def test_absent(self):
        got = self.chapter()
        self.assertEqual((got.errors, got.stats), ([], {"canonical": "absent"}))

    def test_vectors_pass_and_count(self):
        self.vectors()
        got = self.chapter()
        self.assertEqual(got.errors, [])
        self.assertEqual((got.stats["canonical_views"], got.stats["canonical_vectors"]), (3, 3))
        self.assertLess(got.stats["canonical_mutants_killed"], got.stats["canonical_mutants"])
        self.assertTrue(any("changes no vector" in m for m in self.messages(strict=True)))

    def test_vector_errors(self):
        self.vectors()
        vec = self.root / VECTORS
        (vec / "expect/corpus-one.json").write_bytes(b"{}")
        self.assertTrue(any("differs from the built view" in m for m in self.messages()))
        generate(self.root)
        text = (vec / "cases.tsv").read_text()
        (vec / "cases.tsv").write_text("\n".join(l for l in text.split("\n") if not l.startswith("course-sub")))
        (vec / "expect/course-sub.json").unlink()
        self.assertTrue(any("no vector for the accepted input Source/tests/testdata/sub.subsystem.yaml" in m
                            for m in self.messages()))
        (vec / "notes.txt").write_text("x")
        self.assertTrue(any("unsupported entry" in m for m in self.messages()))

    def test_row_form(self):
        self.vectors()
        vec = self.root / VECTORS
        with open(vec / "cases.tsv", "a") as f:
            f.write("e1\t../x.subsystem.yaml\texpect/e1.json\tx\n")
            f.write("e2\t%s\texpect/zz.json\tx\n" % (CORPUS / "cases/bad.subsystem.yaml").as_posix())
        got = self.messages()
        self.assertTrue(any("is not a spec file under the root" in m for m in got))
        self.assertTrue(any("expect must be expect/e2.json" in m for m in got))
        self.assertTrue(any("refuses the input" in m for m in got))

    def test_section(self):
        norms = self.root / NORMS
        norms.write_text("# 2.2\n")
        got = self.chapter()
        self.assertEqual((got.errors, got.stats["canonical_section"]), ([], "absent"))      # переход
        norms.write_text("# 2.2\n%s\n" % BEGIN)
        self.assertTrue(any("hold the built section once" in m for m in self.messages()))
        section = build_view_section(Chapter(self.root).run().ld.form)
        norms.write_text("# 2.2\n%s\n%s%s\n" % (BEGIN, section, END))
        self.assertEqual(self.messages(), [])
        norms.write_text("# 2.2\n%s\n%s%s\n" % (BEGIN, section.replace("П5", "П6"), END))
        self.assertTrue(any("section differs" in m for m in self.messages()))


class PutsTests(LayoutBase):
    def setUp(self):
        super().setUp()
        self.vectors()
        self.acc = self.root / ACCEPTANCE
        (self.acc / "puts").mkdir(parents=True)
        (self.acc / "puts/first.subsystem.yaml").write_text(spec("    a: {}"))
        (self.acc / "puts/second.subsystem.yaml").write_text(spec("    a: {type: int}", "tables: [t]\n"))

    def puts(self, rows, header="case\tputs\texpect\tcanonical"):
        (self.acc / "puts.tsv").write_text("# p\n%s\n%s" % (header, "".join(r + "\n" for r in rows)))
        got = self.chapter()
        return got.stats.get("canonical_puts"), [m for _, m in got.errors]

    def test_view_column(self):
        n, errors = self.puts(["once\tfirst\t0 1\tcorpus-one", "again\tfirst @view-delete first\t0 2\tcorpus-one",
                               "big\tfirst second\t2 1\tcorpus-one", "two\tsecond\t0 1\tcorpus-two"])
        self.assertEqual((n, errors), (4, []))

    def test_errors(self):
        _, errors = self.puts(["once\tfirst\t0 1\t-", "wrong\tfirst\t0 1\tcorpus-two", "dir\t@view-spoil first\t0 1\tcorpus-one",
                               "nofile\tthird\t0 1\tcorpus-one", "code\tfirst\t1 1\tcorpus-one", "name\tfirst\t0 1\tnosuch"])
        for text in ("the view exists", "is not the view of the last file", "directives", "no file puts/third",
                     "expect is", "is not a case of", "no row of puts.tsv installs it"):
            self.assertTrue(any(text in m for m in errors), (text, errors))

    def test_three_columns_of_2_3(self):
        n, errors = self.puts(["same\tfirst first\t0 1", "two\tsecond\t0 1"], "case\tputs\texpect")
        self.assertEqual((n, errors), (2, []))
        _, errors = self.puts(["same\tfirst @view-delete first\t0 1", "two\tsecond\t0 1"], "case\tputs\texpect")
        self.assertTrue(any("need the canonical column" in m for m in errors), errors)


if __name__ == "__main__":
    unittest.main()
