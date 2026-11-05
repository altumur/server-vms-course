"""Тесты генератора № 5 (gen_families.py) и его судьи (family_judge.py): свежесть выхода, векторы семей, мутанты
среды (судья их ловит), закрытый набор слов схемы, типизированная строка и ключ."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import family_judge
import gen_families
from gen_checks import GenError

HERE = Path(__file__).resolve().parent
OUT = HERE / "out/p01-1/go"


class PlaceholderLabels(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="family-labels-")
        self.addCleanup(self.tmp.cleanup)
        self.readme = Path(self.tmp.name) / "README.md"
        self.labels = Path(self.tmp.name) / "placeholders.tsv"
        self.enterContext(patch.object(gen_families, "KEYS_README", self.readme))
        self.enterContext(patch.object(gen_families, "PLACEHOLDER_LABELS", self.labels))

    def grammar(self, rows):
        self.readme.write_text("| Placeholder | Grammar | Example | Norm |\n|---|---|---|---|\n" +
                               "".join(f"| `{label}` | `{expr}` | `1` | norm |\n" for label, expr in rows))

    def test_old_export_without_dictionary(self):
        self.grammar([("<форма>", "^(?:[1-9][0-9]*)$")])
        grammar = gen_families.placeholders()
        self.assertEqual(gen_families.template("canonical/<форма>", grammar)[1],
                         ("", "<форма>", "^(?:[1-9][0-9]*)$"))
        with self.assertRaisesRegex(GenError, "no grammar"):
            gen_families.template("canonical/<form>", grammar)

    def test_dictionary_lookup_preserves_catalogue_key_and_grammar(self):
        self.labels.write_text("ru\ten\nформа\tform\n")
        for label in ("<форма>", "<form>"):
            with self.subTest(readme_label=label):
                self.grammar([(label, "^(?:[1-9][0-9]*)$")])
                grammar = gen_families.placeholders()
                segs = gen_families.template("canonical/<форма>", grammar)
                self.assertEqual(segs, [("canonical/", "", ""), ("", "<форма>", "^(?:[1-9][0-9]*)$")])
                self.assertIsNotNone(gen_families.re.fullmatch(segs[1][2], "12"))
                self.assertIsNone(gen_families.re.fullmatch(segs[1][2], "0"))
                self.assertIsNone(gen_families.re.fullmatch(segs[1][2], "1/2"))
                with self.assertRaisesRegex(GenError, "no grammar"):
                    gen_families.template("canonical/<unknown>", grammar)

    def test_dictionary_is_typed_and_unambiguous(self):
        self.grammar([("<form>", "^(?:[1-9][0-9]*)$")])
        for text in ("en\tru\nform\tформа\n", "ru\ten\nформа\t\n",
                     "ru\ten\nформа\tform\nформа\tother\n"):
            with self.subTest(dictionary=text):
                self.labels.write_text(text)
                with self.assertRaises(GenError):
                    gen_families.placeholders()

    def test_conflicting_explicit_grammars_are_refused(self):
        self.grammar([("<форма>", "^(?:old)$"), ("<form>", "^(?:new)$")])
        self.labels.write_text("ru\ten\nформа\tform\n")
        with self.assertRaisesRegex(GenError, "conflicting grammars"):
            gen_families.placeholders()


def module_copy(t):
    """Модуль выхода с пакетом families (без прочих пакетов: они не нужны обвесу)."""
    dst = Path(t) / "mod"
    (dst / "families").mkdir(parents=True)
    (dst / "go.mod").write_text("module normgen/p01-1\n\ngo 1.22\n", encoding="utf-8")
    for f in (OUT / "families").glob("*.go"):
        shutil.copy(f, dst / "families" / f.name)
    return dst


class Fresh(unittest.TestCase):
    def test_out_is_fresh(self):
        for name, text in gen_families.render().items():
            self.assertEqual((OUT / "families" / name).read_text(encoding="utf-8"), text, name)

    def test_kit_files(self):
        files = {name: origin for _, name, _, origin, _ in gen_families.kit_files()}
        self.assertEqual(files, {"families.go": "generated", "runtime.go": "handwritten"})

    def test_no_prose_of_outcomes(self):
        """Исход словами (колонка outcome) в пакет не идёт: только путь, читатель, приоритет, единица."""
        text = (OUT / "families/families.go").read_text(encoding="utf-8")
        self.assertNotIn("fenced", text)
        self.assertNotIn("does not count as a visible door", text)
        self.assertIn('{Path: "/generation_at", Reader: "*", Priority: 1, Unit: "поле"}', text)

    def test_provenance(self):
        p = gen_families.provenance()
        paths = [e["path"] for e in p["form"]]
        self.assertIn("Platform/01-store/data/epoch_floor.schema.json", paths)
        self.assertIn("Platform/01-store/data/configstore-doors.layers.tsv", paths)
        self.assertIn("Platform/common/placeholders.tsv", paths)
        self.assertIn(gen_families.sha(gen_families.PLACEHOLDER_LABELS),
                      [e["sha256"] for e in p["form"] if e["path"] == "Platform/common/placeholders.tsv"])
        self.assertEqual(p["judge"]["path"], "tools/normgen/family_judge.py")


class Vectors(unittest.TestCase):
    def test_v7_instances(self):
        """Свои экземпляры судьи, ожидание — стек В7 курса (не генератор)."""
        res = family_judge.judge(OUT, "01", runs=1, v7=True)
        self.assertEqual(res["failures"], [])
        self.assertGreater(res["cases"], 400)

    def test_family_read_01(self):
        res = family_judge.judge(OUT, "01", runs=2)
        self.assertEqual(res["failures"], [])
        self.assertEqual(res["pass"], res["cases"])
        self.assertGreaterEqual(res["cases"], 100)

    def test_mutants_are_killed(self):
        """Каждый мутант среды (слово кодека, слой 3, JSON Schema, ключ, исходы) роняет хотя бы одну строку векторов."""
        # Эквивалентны на формах P/01 (не убиваются никаким экземпляром): предел писателя 2^53 − 1 перекрыт maximum
        # у common.uint53; единица «поле» у /generation_at перекрыта приоритетом (1 < 2 строки пустого пути).
        mutants = {
            "reader time as the writer": ("`^(0|[1-9][0-9]*)(\\.[0-9]+)?$`", "`^(0|[1-9][0-9]*)(\\.[0-9]{1,3})?$`"),
            "minimum ignored": ('p.Min != "" && cmp(v, p.Min) < 0', "false"),
            "whole ignored": ("if w || whole {", "if w {"),
            "closed ignored": ("if f.Closed {", "if false {"),
            "required ignored": ("if !present[k] {", "if false {"),
            "maximum ignored": ('p.Max != "" && cmp(v, p.Max) > 0', "false"),
            "not-string accepted": ("if it.NotString {", "if false {"),
            "key not judged": ("if !f.Matches(key) {", "if false {"),
            "priority ignored": ("keep[i] && o.Priority == low", "keep[i]"),
        }
        for why, (a, b) in mutants.items():
            with self.subTest(why), tempfile.TemporaryDirectory() as t:
                mod = module_copy(t)
                rt = mod / "families/runtime.go"
                src = rt.read_text(encoding="utf-8")
                self.assertEqual(src.count(a), 1, a)
                rt.write_text(src.replace(a, b), encoding="utf-8")
                res = family_judge.judge(mod, "01", runs=1, v7=True)
                self.assertTrue(res["failures"], f"mutant «{why}» survives")


class Closed(unittest.TestCase):
    def schema(self, t, doc):
        p = Path(t) / "x.schema.json"
        p.write_text(json.dumps(doc), encoding="utf-8")
        return gen_families.Schema(p)

    def test_unsupported_word(self):
        with tempfile.TemporaryDirectory() as t:
            s = self.schema(t, {"type": "object", "properties": {"a": {"type": "string", "x-codec": ["string"],
                                                                       "pattern": "^a$"}}})
            with self.assertRaisesRegex(GenError, "pattern"):
                gen_families.prop_of(s, "a", s.doc["properties"]["a"])

    def test_codec_required(self):
        with tempfile.TemporaryDirectory() as t:
            s = self.schema(t, {"type": "object", "properties": {"a": {"type": "string"}}})
            with self.assertRaisesRegex(GenError, "x-codec"):
                gen_families.prop_of(s, "a", s.doc["properties"]["a"])

    def test_integer_needs_bounds(self):
        with tempfile.TemporaryDirectory() as t:
            s = self.schema(t, {"type": "object", "properties": {"a": {"type": "integer", "x-codec": ["integer"]}}})
            with self.assertRaisesRegex(GenError, "int64"):
                gen_families.prop_of(s, "a", s.doc["properties"]["a"])

    def test_layers_must_agree(self):
        with tempfile.TemporaryDirectory() as t:
            s = self.schema(t, {"type": "object", "properties": {"a": {"x-codec": ["time"], "x-time": True}}})
            lt = Path(t) / "x.layers.tsv"
            lt.write_text("place\tlayer\tword\tvalue\n/properties/a\t3\tx-codec\t[\"integer\"]\n", encoding="utf-8")
            with self.assertRaisesRegex(GenError, "x-codec"):
                gen_families.check_layers(s, lt)
            lt.write_text("place\tlayer\tword\tvalue\n/properties/a\t3\tx-codec\t[\"time\"]\n", encoding="utf-8")
            self.assertEqual(gen_families.check_layers(s, lt), 1)

    def test_star_key(self):
        with self.assertRaisesRegex(GenError, "«\\*»"):
            gen_families.template("platform/x/*", gen_families.placeholders())

    def test_unknown_placeholder(self):
        with self.assertRaisesRegex(GenError, "no grammar"):
            gen_families.template("platform/x/<нет>", gen_families.placeholders())

    def test_object_kind(self):
        with self.assertRaisesRegex(GenError, "only row"):
            gen_families.load_family({"key": "k", "kind": "object", "schema": "x", "norm": ""}, {})


TYPED = """package main

import (
	"fmt"

	"normgen/p01-1/families"
)

func main() {
	row, r := families.ReadEpochFloor(map[string]string{"floor": "5", "generation_at": "1.25"}, families.Reader)
	fmt.Println(r.Verdict, row.Floor, row.GenerationAt)
	_, r = families.ReadEpochFloor(map[string]string{"floor": "5.0", "generation_at": "1"}, families.Reader)
	fmt.Println(r.Verdict, r.Paths, families.EpochFloor.OutcomesFor(r.Paths, "<s>worker"))
	_, r = families.ReadEpochFloor(map[string]string{"floor": "5", "generation_at": "x"}, families.Reader)
	fmt.Println(r.Verdict, r.Paths, families.EpochFloor.OutcomesFor(r.Paths, "<s>worker"))
	items, r := families.EpochFloorRow{Floor: 7, GenerationAt: 2.0004}.Items()
	fmt.Println(r.Verdict, items["floor"], items["generation_at"])
	_, r = families.EpochFloorRow{Floor: -1, GenerationAt: 1}.Items()
	fmt.Println(r.Verdict, r.Paths)
	_, r = families.ConfigstoreDoorsRow{SeenAt: -1}.Items()
	fmt.Println(r.Verdict, r.Paths)
	k := families.ConfigstoreDoorsKey("t1")
	fmt.Println(k, families.ConfigstoreDoors.Matches(k), families.ConfigstoreDoors.Matches(families.ConfigstoreDoorsKey("..")))
	fmt.Println(families.EpochFloor.Readers(), families.ByKey("platform/configstore-doors/<id>") == families.ConfigstoreDoors)
}
"""


class Typed(unittest.TestCase):
    def test_read_write_key(self):
        with tempfile.TemporaryDirectory() as t:
            mod = module_copy(t)
            (mod / "cmd").mkdir()
            (mod / "cmd/main.go").write_text(TYPED, encoding="utf-8")
            done = subprocess.run(["go", "run", "./cmd"], cwd=mod, capture_output=True, text=True, timeout=300)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(done.stdout.splitlines(), [
                "ok 5 1.25",
                "refused [/floor] [/floor]",
                "refused [/generation_at] [/generation_at]",
                "ok 7 2",
                "refused [/floor]",
                "refused [/seen_at]",
                "platform/configstore-doors/t1 true false",
                "[<s>worker] true",
            ])


if __name__ == "__main__":
    unittest.main()
