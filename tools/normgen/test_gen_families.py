"""Test gen_families/family_judge freshness, vectors, detected runtime mutants, closed schema vocabulary, typed rows and keys."""
import lesson as output_lesson
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
OUT = output_lesson.output_root() / 'p01-1/go'


class PlaceholderLabels(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="family-labels-")
        self.addCleanup(self.tmp.cleanup)
        self.readme = Path(self.tmp.name) / "README.md"
        self.labels = Path(self.tmp.name) / "placeholders.tsv"
        self.enterContext(patch.object(gen_families, "KEYS_README", self.readme))
        self.enterContext(patch.object(gen_families, "PLACEHOLDER_LABELS", self.labels))
        self.enterContext(patch.object(gen_families, "KEY_GRAMMARS", Path(self.tmp.name) / "absent-keys.tsv"))
        self.enterContext(patch.object(gen_families, "OUTCOME_UNITS", Path(self.tmp.name) / "absent-units.tsv"))

    def grammar(self, rows):
        self.readme.write_text("| Placeholder | Grammar | Example | Norm |\n|---|---|---|---|\n" +
                               "".join(f"| `{label}` | `{expr}` | `1` | norm |\n" for label, expr in rows))

    def test_old_export_without_dictionary(self):
        self.grammar([('<\u0444\u043e\u0440\u043c\u0430>', "^(?:[1-9][0-9]*)$")])
        grammar = gen_families.placeholders()
        self.assertEqual(gen_families.template('canonical/<\u0444\u043e\u0440\u043c\u0430>', grammar)[1],
                         ("", '<\u0444\u043e\u0440\u043c\u0430>', "^(?:[1-9][0-9]*)$"))
        with self.assertRaisesRegex(GenError, "no grammar"):
            gen_families.template("canonical/<form>", grammar)

    def test_dictionary_lookup_preserves_catalogue_key_and_grammar(self):
        self.labels.write_text('ru\ten\n\u0444\u043e\u0440\u043c\u0430\tform\n')
        for label in ('<\u0444\u043e\u0440\u043c\u0430>', "<form>"):
            with self.subTest(readme_label=label):
                self.grammar([(label, "^(?:[1-9][0-9]*)$")])
                grammar = gen_families.placeholders()
                segs = gen_families.template('canonical/<\u0444\u043e\u0440\u043c\u0430>', grammar)
                self.assertEqual(segs, [("canonical/", "", ""), ("", '<\u0444\u043e\u0440\u043c\u0430>', "^(?:[1-9][0-9]*)$")])
                self.assertIsNotNone(gen_families.re.fullmatch(segs[1][2], "12"))
                self.assertIsNone(gen_families.re.fullmatch(segs[1][2], "0"))
                self.assertIsNone(gen_families.re.fullmatch(segs[1][2], "1/2"))
                with self.assertRaisesRegex(GenError, "no grammar"):
                    gen_families.template("canonical/<unknown>", grammar)

    def test_dictionary_is_typed_and_unambiguous(self):
        self.grammar([("<form>", "^(?:[1-9][0-9]*)$")])
        for text in ('en\tru\nform\t\u0444\u043e\u0440\u043c\u0430\n', 'ru\ten\n\u0444\u043e\u0440\u043c\u0430\t\n',
                     'ru\ten\n\u0444\u043e\u0440\u043c\u0430\tform\n\u0444\u043e\u0440\u043c\u0430\tother\n'):
            with self.subTest(dictionary=text):
                self.labels.write_text(text)
                with self.assertRaises(GenError):
                    gen_families.placeholders()

    def test_explicit_typed_grammars_take_priority_over_prose_labels(self):
        self.grammar([('<\u0444\u043e\u0440\u043c\u0430>', "^(?:old)$"), ("<form>", "^(?:new)$")])
        self.labels.write_text('ru\ten\n\u0444\u043e\u0440\u043c\u0430\tform\n')
        self.assertEqual(gen_families.placeholders(), {'<\u0444\u043e\u0440\u043c\u0430>': "^(?:old)$", "<form>": "^(?:new)$"})

    def test_ambiguous_missing_label_is_refused(self):
        self.grammar([('<\u043e\u0434\u0438\u043d>', "^(?:old)$"), ('<\u0434\u0432\u0430>', "^(?:new)$")])
        self.labels.write_text('ru\ten\n\u043e\u0434\u0438\u043d\tmissing\n\u0434\u0432\u0430\tmissing\n')
        with self.assertRaisesRegex(GenError, "conflicting grammars for alias <missing>"):
            gen_families.placeholders()

    def test_conflicting_readme_duplicates_are_refused_before_mapping(self):
        # These two collisions were introduced by translating distinct typed
        # labels to the same English spelling. Neither may use the last row.
        for label in ("<server>", "<key>"):
            for dictionary in (None, "wrong\theader\n"):
                with self.subTest(label=label, dictionary=dictionary):
                    self.grammar([(label, "^(?:[a-z]+)$"), (label, "^(?:[^/]+/[^/]+)$")])
                    self.labels.unlink(missing_ok=True)
                    if dictionary is not None:
                        self.labels.write_text(dictionary)
                    with self.assertRaisesRegex(GenError, f"README.md: conflicting grammars for {label}"):
                        gen_families.placeholders()

    def test_identical_duplicate_rows_and_aliases_are_allowed(self):
        expr = "^(?:[a-z]+)$"
        self.grammar([("<server>", expr), ("<server>", expr), ('<\u0441\u0435\u0440\u0432\u0435\u0440>', expr)])
        self.labels.write_text('ru\ten\n\u0441\u0435\u0440\u0432\u0435\u0440\tserver\n')
        grammar = gen_families.placeholders()
        self.assertEqual(grammar, {"<server>": expr, '<\u0441\u0435\u0440\u0432\u0435\u0440>': expr})
        self.assertEqual(gen_families.template('<\u0441\u0435\u0440\u0432\u0435\u0440>/<server>', grammar),
                         [("", '<\u0441\u0435\u0440\u0432\u0435\u0440>', expr), ("/", "", ""), ("", "<server>", expr)])

    def test_legacy_distinct_types_are_not_merged_without_dictionary(self):
        host = r"^(?:[a-z]+(?:\.[a-z]+)*)$"
        server_name = r"^(?:[a-z]+(?:-[a-z]+)*)$"
        self.grammar([('<\u0441\u0435\u0440\u0432\u0435\u0440>', host), ("<server>", server_name)])
        grammar = gen_families.placeholders()
        self.assertEqual(grammar, {'<\u0441\u0435\u0440\u0432\u0435\u0440>': host, "<server>": server_name})
        self.assertIsNotNone(gen_families.re.fullmatch(grammar['<\u0441\u0435\u0440\u0432\u0435\u0440>'], "srv.example"))
        self.assertIsNone(gen_families.re.fullmatch(grammar["<server>"], "srv.example"))
        self.assertIsNotNone(gen_families.re.fullmatch(grammar["<server>"], "srv-a"))


def module_copy(t):
    """Create an output module containing families only; other packages are not needed by the harness."""
    output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
    dst = Path(t) / "mod"
    (dst / "families").mkdir(parents=True)
    (dst / "go.mod").write_text("module normgen/p01-1\n\ngo 1.22\n", encoding="utf-8")
    for f in (OUT / "families").glob("*.go"):
        shutil.copy(f, dst / "families" / f.name)
    return dst


class CanonicalInputs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="family-canonical-")
        self.addCleanup(self.tmp.cleanup)
        self.keys = Path(self.tmp.name) / "keys.tsv"
        self.units = Path(self.tmp.name) / "units.tsv"
        self.legacy = Path(self.tmp.name) / "legacy.tsv"
        self.enterContext(patch.object(gen_families, "KEY_GRAMMARS", self.keys))
        self.enterContext(patch.object(gen_families, "OUTCOME_UNITS", self.units))
        self.enterContext(patch.object(gen_families, "PLACEHOLDER_LABELS", self.legacy))
        self.enterContext(patch.object(gen_families, "KEYS_README", Path(self.tmp.name) / "not-read.md"))

    def test_direct_typed_registry_never_reads_human_dictionary(self):
        self.keys.write_text("placeholder\tpattern\texample\tnorm\n<host>\t^(?:[A-Za-z.]+)$\tHost.example\tnorm\n"
                             "<server>\t^(?:[a-z-]+)$\tsrv-a\tnorm\n"
                             "<object-key>\t^(?:[^/]+(?:/[^/]+)*)$\ta/b\tnorm\n"
                             "<key>\t^(?:[^/]+)$\tone\tnorm\n")
        self.legacy.write_text("invalid dictionary must not be read")
        got = gen_families.placeholders()
        self.assertEqual(gen_families.grammar_sources(), [self.keys])
        for name, value, want in [("host", "Host.example", True), ("server", "Host.example", False),
                                  ("object-key", "a/b", True), ("key", "a/b", False),
                                  ("object-key", "a//b", False)]:
            with self.subTest(name=name, value=value):
                self.assertEqual(gen_families.re.fullmatch(got[f"<{name}>"], value) is not None, want)
        self.legacy.write_text("another invalid dictionary")
        self.assertEqual(gen_families.placeholders(), got)

    def test_canonical_unit_vocabulary_is_closed(self):
        self.keys.write_text("placeholder\tpattern\texample\tnorm\n<key>\t.+\tx\tnorm\n")
        for values in [("row", "field", "element"), ("row", "field", "item"),
                       ('\u0441\u0442\u0440\u043e\u043a\u0430', '\u043f\u043e\u043b\u0435', '\u044d\u043b\u0435\u043c\u0435\u043d\u0442'), ("row", "field", "field")]:
            with self.subTest(values=values):
                self.units.write_text("unit\tmeaning\n" + "".join(x + "\tmeaning\n" for x in values))
                if values == ("row", "field", "element"):
                    self.assertEqual(gen_families.unit_words(), dict(zip(values, values)))
                else:
                    with self.assertRaisesRegex(GenError, "closed units"):
                        gen_families.unit_words()
        self.units.unlink()
        with self.assertRaisesRegex(GenError, "missing canonical"):
            gen_families.unit_words()
        self.keys.unlink()
        self.assertEqual(gen_families.unit_words(), {"row": '\u0441\u0442\u0440\u043e\u043a\u0430', "field": '\u043f\u043e\u043b\u0435', "element": '\u044d\u043b\u0435\u043c\u0435\u043d\u0442'})


class Fresh(unittest.TestCase):
    def test_out_is_fresh(self):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        for name, text in gen_families.render().items():
            self.assertEqual((OUT / "families" / name).read_text(encoding="utf-8"), text, name)

    def test_kit_files(self):
        files = {name: origin for _, name, _, origin, _ in gen_families.kit_files()}
        self.assertEqual(files, {"families.go": "generated", "runtime.go": "handwritten"})

    def test_no_prose_of_outcomes(self):
        """Exclude outcome prose from generated code; retain only path, reader, priority and unit."""
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        text = (OUT / "families/families.go").read_text(encoding="utf-8")
        self.assertNotIn("fenced", text)
        self.assertNotIn("does not count as a visible door", text)
        self.assertIn('{Path: "/generation_at", Reader: "*", Priority: 1, Unit: "field"}', text)

    def test_provenance(self):
        p = gen_families.provenance()
        paths = [e["path"] for e in p["form"]]
        self.assertIn("Platform/01-store/data/epoch_floor.schema.json", paths)
        self.assertIn("Platform/01-store/data/configstore-doors.layers.tsv", paths)
        self.assertIn("Platform/common/data/key-placeholders.tsv", paths)
        self.assertIn("Platform/common/data/outcome-units.tsv", paths)
        self.assertNotIn("Platform/common/placeholders.tsv", paths)
        self.assertFalse(any("/ru/" in path for path in paths))
        self.assertEqual(p["judge"]["path"], "tools/normgen/family_judge.py")


class Vectors(unittest.TestCase):
    def test_v7_instances(self):
        """Independent judge cases use the course V7 stack as oracle, not the generator."""
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        res = family_judge.judge(OUT, "01", runs=1, v7=True)
        self.assertEqual(res["failures"], [])
        self.assertGreater(res["cases"], 400)

    def test_family_read_01(self):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        res = family_judge.judge(OUT, "01", runs=2)
        self.assertEqual(res["failures"], [])
        self.assertEqual(res["pass"], res["cases"])
        self.assertGreaterEqual(res["cases"], 100)

    def test_mutants_are_killed(self):
        """Every runtime mutant affecting codec, layer3, JSON Schema, key or outcomes must fail at least one vector."""
        # Equivalent on P/01 forms: common.uint53 maximum already enforces the writer's2^53-1 limit;
        # field unit at /generation_at is shadowed by the empty-path row's higher priority (1<2).
        mutants = {
            "reader accepts excessive precision": ("Reader: regexp.MustCompile(`^(0|[1-9][0-9]*)(\\.[0-9]{1,3})?$`)", "Reader: regexp.MustCompile(`^(0|[1-9][0-9]*)(\\.[0-9]+)?$`)"),
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
            gen_families.template('platform/x/<\u043d\u0435\u0442>', gen_families.placeholders())

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
