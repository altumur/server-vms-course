"""Test data-schema families mode (P/02, famrt2, ADR-0125 addendum 5): freshness and family_judge PASS on02.tsv plus independent V7 cases with nested document mutations. Require FAIL for invalid-name child traversal, missing uniqueItems/JCS/anyOf/x-max-names checks. P/01 flat mode stays in test_gen_families.py."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
ENV = dict(os.environ, NORMGEN_LESSON="02-installer")


def judge(module_dir, v7=True):
    return subprocess.run([sys.executable, str(HERE / "family_judge.py"), "--module-dir", str(module_dir), "--runs", "1"]
                          + (["--v7"] if v7 else []), capture_output=True, text=True, env=ENV)


SYNTH = {
    "$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False,
    "properties": {
        "doc": {"x-encoding": "jcs", "$ref": "#/$defs/doc"},
        "list": {"x-encoding": "json", "type": "array", "items": {"type": "string", "pattern": "^(?:[a-z]+)$"},
                 "uniqueItems": True, "maxItems": 3},
        "n": {"x-codec": ["integer"], "type": "integer", "minimum": 1, "exclusiveMaximum": 10},
        "t": {"x-codec": ["time"], "x-time": True, "type": "number"},
        "e": {"x-codec": ["string"], "type": "string", "enum": ["a", "b"], "maxLength": 1}},
    "required": ["doc"],
    "$defs": {
        "doc": {"type": "object", "properties": {"kind": {"type": "string"}, "opt": {"anyOf": [{"type": "integer"},
                {"type": "null"}]}, "neg": {"not": {"type": "string"}}},
                "propertyNames": {"pattern": "^(?:[a-z][a-z_]*)$"},
                "additionalProperties": {"type": "object", "required": ["v"], "additionalProperties": False,
                                         "properties": {"v": {"type": "integer", "x-integer": True}}},
                "required": ["kind"], "x-max-names": 2},
        "writer": {"x-max-names": 0}}}

SYNTH_ITEMS = [
    {"doc": '{"kind":"k"}'},
    {"doc": '{"kind":"k","a":{"v":1}}'},
    {"doc": '{"kind":"k","Bad Name":{"v":"x","zz":1}}'},          # An invalid name prevents judging its children.
    {"doc": '{"kind":"k","a":{"zz":1}}'},
    {"doc": '{"kind":"k","a":{"v":1},"b":{"v":2},"c":{"v":3}}'},  # x-max-names
    {"doc": '{"kind":"k","a":{"v":1.0}}'},
    {"doc": '{"kind":"k","opt":"s"}'}, {"doc": '{"kind":"k","opt":null,"neg":1}'}, {"doc": '{"kind":"k","neg":"s"}'},
    {"doc": '{ "kind": "k" }'}, {"doc": '{"kind":"k","kind":"j"}'}, {"doc": '{"kind":"k","a":{"v":1e400}}'},
    {"doc": '{"kind":1}'}, {"doc": "{}"}, {"doc": "[]"}, {"doc": "nope"},
    {"doc": '{"kind":"k"}', "list": '["a","b"]'}, {"doc": '{"kind":"k"}', "list": '["a","a","b"]'},
    {"doc": '{"kind":"k"}', "list": '["a","b","c","d"]'}, {"doc": '{"kind":"k"}', "list": '["A"]'},
    {"doc": '{"kind":"k"}', "n": "1"}, {"doc": '{"kind":"k"}', "n": "10"}, {"doc": '{"kind":"k"}', "n": "0"},
    {"doc": '{"kind":"k"}', "n": "3.0"}, {"doc": '{"kind":"k"}', "n": "1e1"}, {"doc": '{"kind":"k"}', "t": "1.5"},
    {"doc": '{"kind":"k"}', "t": "1.2345"}, {"doc": '{"kind":"k"}', "t": "-1"}, {"doc": '{"kind":"k"}', "e": "a"},
    {"doc": '{"kind":"k"}', "e": "c"}, {"doc": '{"kind":"k"}', "zz": "1"}, {"e": "a"},
]


def synth_mismatches(runtime):
    """Compare a synthetic runtime family with V7 as [(mode, text, response, expectation)]."""
    import json
    sys.path.insert(0, str(ROOT / "skills/lesson-spec/scripts"))
    from v7 import stack
    sys.path.insert(0, str(HERE))
    import gen_families
    units = gen_families.unit_words()
    fam = stack.Family(SYNTH, "row")
    with tempfile.TemporaryDirectory(prefix="famsynth-") as t:
        mod = Path(t) / "go"
        (mod / "families").mkdir(parents=True)
        (mod / "go.mod").write_text("module normgen/p02\n\ngo 1.22\n", encoding="utf-8")
        (mod / "families/runtime.go").write_text(Path(runtime).read_text(encoding="utf-8"), encoding="utf-8")
        (mod / "families/families.go").write_text(
            "package families\n\nconst unitRow = " + json.dumps(units["row"]) + "\n"
            "const unitField = " + json.dumps(units["field"]) + "\n\n"
            "var Synth = &Family{Key: \"test/x\", Kind: \"row\", Template: []Seg{{Lit: "
            "\"test/x\"}}, Outcomes: []Outcome{{Path: \"\", Reader: \"r\", Unit: unitRow}}, Doc: "
            + json.dumps(json.dumps(SYNTH)) + "}\n\nvar All = []*Family{Synth}\n\n"
            "func ByKey(key string) *Family {\n\tfor _, f := range All {\n\t\tif f.Key == key {\n\t\t\treturn f\n"
            "\t\t}\n\t}\n\treturn nil\n}\n", encoding="utf-8")
        sys.path.insert(0, str(HERE))
        import family_judge
        cases, want = [], []
        for items in SYNTH_ITEMS:
            for mode in ("writer", "reader"):
                text = json.dumps(items)
                cases.append({"family": "test/x", "key": "test/x", "mode": mode, "who": ["r"], "text": text})
                want.append(fam.judge(json.loads(text), mode))
        got = family_judge.harness(mod, cases)
        if len(got) != len(cases):
            raise AssertionError(f"synthetic harness executed {len(got)} of {len(cases)} cases")
        return [(c["mode"], c["text"], (g["verdict"], sorted(g["paths"])), (w["verdict"], sorted(w["paths"])))
                for c, g, w in zip(cases, got, want)
                if (g["verdict"], sorted(g["paths"])) != (w["verdict"], sorted(w["paths"]))]


class Synthetic(unittest.TestCase):
    """Independently test every famrt2 keyword using a synthetic family: refusal paths, invalid names without child checks, uniqueItems, anyOf, not, x-max-names, writer JCS and codec, without relying on the lesson corpus."""

    def test_against_v7(self):
        self.assertEqual(synth_mismatches(HERE / "famrt2/go/runtime.go"), [])


@unittest.skipUnless((ROOT / "Platform/common/vectors/family-read/02.tsv").is_file(), "no P/02 family vectors")
class DocMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="famdoc-")
        cls.out = Path(cls.tmp.name) / "out"
        done = subprocess.run([sys.executable, str(HERE / "gen_families.py"), "02", str(cls.out)], capture_output=True,
                              text=True, env=ENV)
        assert done.returncode == 0, done.stderr
        (cls.out / "go/go.mod").write_text("module normgen/p02\n\ngo 1.22\n", encoding="utf-8")
        cls.mod = cls.out / "go"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_out_fresh(self):
        for name in ("families.go", "runtime.go"):
            self.assertEqual((self.mod / "families" / name).read_bytes(),
                             (HERE / "out/p02/go/families" / name).read_bytes(), name)

    def test_judge_pass(self):
        done = judge(self.mod)
        self.assertEqual(done.returncode, 0, done.stdout[-2000:] + done.stderr[-2000:])
        self.assertIn("PASS", done.stdout)

    def mutant(self, old, new):
        t = Path(tempfile.mkdtemp(dir=self.tmp.name))
        shutil.copytree(self.mod, t / "go")
        f = t / "go/families/runtime.go"
        text = f.read_text(encoding="utf-8")
        self.assertIn(old, text)
        f.write_text(text.replace(old, new, 1), encoding="utf-8")
        return judge(t / "go"), f

    def test_mutants_killed(self):
        baseline = judge(self.mod)
        self.assertEqual(baseline.returncode, 0, baseline.stdout[-2000:] + baseline.stderr[-2000:])
        self.assertEqual(synth_mismatches(HERE / "famrt2/go/runtime.go"), [])
        for old, new, why in (
                ("if len(p) > len(b) && samePrefix(p, b) {", "if false && len(p) > len(b) && samePrefix(p, b) {",
                 "children of a bad name"),
                ('\t\tcase "uniqueItems":\n\t\t\tif b, _ := w.(bool); b {', '\t\tcase "uniqueItems":\n\t\t\tif b, _ := w.(bool); b && false {',
                 "uniqueItems"),
                ('if enc == "jcs" && mode == Writer {\n\t\t\tif c, err := jcs(v); err != nil || c != text {',
                 'if enc == "jcs" && mode == Writer && false {\n\t\t\tif c, err := jcs(v); err != nil || c != text {',
                 "writer JCS of an item"),
                ("\t\t\tif !ok {\n\t\t\t\tadd(\"anyOf\", nil)", "\t\t\tif false && !ok {\n\t\t\t\tadd(\"anyOf\", nil)", "anyOf"),
                ('if mn, ok := word(chain, "x-max-names"); ok {', 'if mn, ok := word(chain, "x-max-names"); ok && false {',
                 "x-max-names")):
            done, runtime = self.mutant(old, new)
            self.assertIn(done.returncode, (0, 1), "judge/build errors are not killed mutants: " + done.stderr[-1000:])
            if done.returncode == 1:
                self.assertIn("FAIL ", done.stdout, "the mutant must execute the judge cases")
            mismatches = synth_mismatches(runtime)
            killed = done.returncode == 1 or mismatches
            self.assertTrue(killed, f"mutant survived (corpus and synthetic): {why}\n{done.stdout[-500:]}")
            print(f"\nfamrt2 mutant {why}: corpus exit {done.returncode}, synthetic mismatches {len(mismatches)}")


if __name__ == "__main__":
    unittest.main()
