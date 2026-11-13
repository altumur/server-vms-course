"""Test data-schema families mode (P/02, famrt2, ADR-0125 addendum 5): freshness and family_judge PASS on02.tsv plus independent V7 cases with nested document mutations. Require FAIL for invalid-name child traversal, missing uniqueItems/JCS/anyOf/x-max-names checks. P/01 flat mode stays in test_gen_families.py."""
import lesson as output_lesson
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
        for ordinal, items in enumerate(SYNTH_ITEMS):
            for mode in ("writer", "reader"):
                text = json.dumps(items)
                expected = fam.judge(json.loads(text), mode)
                cases.append({"case": f"synthetic-{ordinal}-{mode}", "kind": "row", "family": "test/x",
                              "key": "test/x", "mode": mode, "who": ["r"], "text": text,
                              "verdict": expected["verdict"], "paths": expected["paths"],
                              "outcome": [] if mode == "writer" else {"r": []}, "note": "owned synthetic control"})
                want.append(expected)
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


    @staticmethod
    def _role_binding_go_surface(text):
        """Static declaration inventory only; not Go compilation, key binding or runtime proof."""
        import re
        functions = re.findall(r"^func (?:\([^\n]*\) )?[A-Z][A-Za-z0-9_]*\([^\n]*?\)(?: [^{\n]+)? (?=\{)", text, re.M)
        structures = re.findall(r"^type [A-Z][A-Za-z0-9_]* struct \{\n.*?^\}", text, re.M | re.S)
        aliases = re.findall(r"^type [A-Z][A-Za-z0-9_]* (?!struct\b)[^\n]+", text, re.M)
        return sorted(functions), sorted(structures), sorted(aliases)

    def test_role_binding_public_surface(self):
        """RS01 requires the separately frozen Generator input; never execute old subject as a substitute."""
        import re
        runtime = (HERE / "famrt2/go/runtime.go").read_text(encoding="utf-8")
        expected_surface = (['func (f *Family) Judge(key string, items Items, mode Mode) Result ', 'func (f *Family) JudgeItems(items Items, mode Mode) Result ', 'func (f *Family) JudgeText(key string, text []byte, mode Mode) Result ', 'func (f *Family) Matches(key string) bool ', 'func (f *Family) OutcomesFor(paths []string, reader string) []string ', 'func (f *Family) Readers() []string ', 'func (r Result) OK() bool ', 'func ItemsOf(m map[string]string) Items ', 'func ParseItems(text []byte) Items ', 'func Pointer(name string) string '], ['type Family struct {\n\tKey      string // the key template of the catalog\n\tKind     string // row\n\tSchema   string // the schema path\n\tNorm     string\n\tTemplate []Seg\n\tDoc      string // the JSON text of the schema\n\tOutcomes []Outcome\n\tkey      *regexp.Regexp\n\tonce     sync.Once\n\tsch      *schema\n\terr      error\n}', 'type Item struct {\n\tText      string\n\tNotString bool\n}', 'type Outcome struct {\n\tPath     string\n\tReader   string\n\tPriority int\n\tUnit     string\n\t// Wild — the segments «*» of Path (V7, DIALECT § 9): number of the segment → the names of properties of that\n\t// place; «*» matches any one segment except these names (an author name or any item of a list).\n\tWild map[int][]string\n}', 'type Result struct {\n\tVerdict string\n\tPaths   []string\n}', 'type Seg struct {\n\tLit, Placeholder, Grammar string\n}'], ['type Items map[string]Item', 'type Mode int'])
        self.assertEqual(self._role_binding_go_surface(runtime), expected_surface)
        # This checks private source plumbing only, not an oracle inferred from its selector.
        self.assertIn('"domain/deleting/<name>"', runtime)
        self.assertIn('"person_writer"', runtime)
        self.assertIn('"role_writer"', runtime)
        start = runtime.index("func (f *Family) Judge(key string, items Items, mode Mode) Result {")
        end = runtime.index("\n}\n", start)
        keyed = runtime[start:end]
        self.assertIn("f.Matches(key)", keyed)
        self.assertNotIn("return f.JudgeItems(items, mode)", keyed)
        self.assertRegex(keyed, r"return f\.[a-z][A-Za-z0-9_]*\([^\n]*&?key")
        private = re.findall(r"^func (?:\([^\n]*\) )?([a-z][A-Za-z0-9_]*)\([^\n]*\)", runtime, re.M)
        self.assertTrue(private)
        self.assertRegex(runtime, r"\*[ ]*string")
        self.assertIn("panic(", runtime)  # Existing checking-precondition channel; never a semantic kill.

    def test_role_binding_constructors_and_frozen_blocks(self):
        """RS02 static source/constructor guard; no generator import, setup, rendering or Go."""
        import ast
        import hashlib
        expected = [('tools/normgen/test_gen_families_doc.py', 'SYNTH', 'a758b0c8207ac6df17b4737fa6e75e5dc9ef708f6067041c8d2764ff11d346b2'), ('tools/normgen/test_gen_families_doc.py', 'SYNTH_ITEMS', '003697bd95118e64f418ee8319fcb9a1f97c05a3389b247f64937e26c03c5198'), ('tools/normgen/test_gen_families_doc.py', 'synth_mismatches', '7f7bfc8f909522726161727925dc92b6956d4231513d8848b6ee678edf6b2a85'), ('tools/normgen/test_gen_families_doc.py', 'DocMode', 'f87274c53e0d555d5d7a4d9ee7c908015a155bcdca9969e9d4fbbb2aa7c49fbd'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestRegex.test_portable', 'b5ebfcbeeccbfdf207be9db8b9e24591ad0e64c9bcbe40772546d66a7e3aa44d'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestRegex.test_manual_complements', '6ed5db59dfbad4704effca265163a5c7784eb77b3a54079055c0c8d3fbf49e29'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestTraps.test_negative_integer_bound_text', '43d1e800e34d713981de3a0749ed0cf2e04d60ce4dcf1f0a733c3b85786051fc'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestDefects.test_d1_dollar_before_newline', '1d999041921d7ff619a0071364df95004fd7b2f0d46a27097aa063191faada26'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestDefects.test_d2_pattern_properties', 'ca9e0d69fbcf36f86c28b3e7c971ae37d5cb95f130594ee0e80a12409b7b8d13'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestDefects.test_d3_false_schema_path', '134f765fc22fda0108dc5728f5dacad6f842c72da35d287db84f5f1a2ed41d59'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestDefects.test_d4_dyn_overload', 'ebbf5913b99482f645b1829b8fafca7ef10e6106dbeef9b31bbd0830a823f863'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestDefects.test_d5_error_value', 'a19cc5a08f104f1c725730df4012011814161c06460d7389f3e20705080a07c5'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestDefects.test_d6_dyn_range', 'f37905b628693fe80d2658e0a7a81f193e6a7a98edfb6b5cb9be5fd255c38630'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestDefects.test_d7_go_property_names', 'f21877be0fb8f208d5a2c08e490ade31bc370a01f7e3a008d06acc2ed7ac06b1'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestDefects.test_d8_go_double_index', '5d24abbefab2475d9c6e7eb45ea3f3d6c72f7a88ead501191ed5f12a9262f29a'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestDefects.test_d18_map_order', '116ad012e89273482138d8ca32ace7e45270e441c9cc699e30f049b05b300e41'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestDefects.test_d24_two_var_by_name', '59839c27a7d311b322340c800a7107781ae58953c43ed457f7f43f79d52c3e33'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestDefects.test_d22_json_loads', '20ccd34934305bf6d6f0a3dc7b6161c8d140d18c39f27c79f8694fb98f69c24c'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestDefects.test_d23_jsonschema_places', 'e31508089d169fc658723fb0309376777e866238135a68da357ef37638c364da'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestDefects.test_d25_ruamel_rt_overlap', 'aed4d8a0aa09b108e852e66c0c3b46c9e501e92d57de0589d862a5c02d9e8f1a'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestDefects.test_d18_python_map_order', 'a255aeac6172e0e5681b571d7fab5bda59af76498d6f9e68d3507fc98544255f'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestDefects.test_d19_dialect_p1_states', '045b8d3067a56a11d43cd4f07f698fa4d6ad7d6cb091700317740f5f12a518d9'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestRelations.test_python', '7a9145b17e1e553478871e0e4e58b6b7b527100083a5b55a0665861153a14b14'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestRelations.test_go', 'daac8b038606623d3ea6b81baa4523f8b47287fa88686ba773d6db5a00e150df'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestYaml.both', '2efa1c38c7d4ff34f4081cfca77be693fa61db3ec602daa5671de778a477cfd4'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestYaml.setUpClass', 'fc0bb135a8171312741d25bf177e1fc769789e82693879c8eeb1402e8dfe5694'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestYaml.tearDownClass', '18bba3c38a8edc39b54a51759b93f1b7fc2af9c634db838ba0610d36e72ea4f0'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestYaml.go_parses', '9f386e5db19865d6f2b65165a273208ec7258166e4b3eacd6207ff5b9988d933'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestYaml.ruamel_parses', '74de99ce388d73734b7ab7b451c19695fd28518296a608bd5c6de26cfe0e98c2'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestYaml.test_d9_ruamel_big_escape', '2d33644cc1ea930fd7dc3c5553d072b83515203be545a2daa7a208711bbef3aa'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestYaml.test_d10_flow_empty_value', '31ae3244aea7a2fafa982f34bd71d6a217894354f6f79f23498728fba50f814c'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestYaml.test_d20_ruamel_continuation_column0', '802ef23b99d93146b3b13f2da8a35f67416ac59064dd6083f687f85c76460e46'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestYaml.test_d11_comment_after_quote', '1b90f8194adc480296b0331c640f93687972db256ec77f725d59e528da64ffa3'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestYaml.suite_layer1', 'bb22b76a628e785abcf5fa87e20f173d5486eb36f1760d401dc93b345c036b9b'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestYaml.test_flow_dash', '642a3376523119e9fdfcce7f28de7bd6c14f4e58a8c90dab29fe77389ac6bd25'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestYaml.test_d21_ruamel_directives', '1b2dd81a7a791b574de77ece8e389e9cbc8484e5edba98edf1ece1077f7588ce'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestYaml.test_d12_escape_quote', 'ab94439e8d98fc9659a4eca50b44757280764a4cab1104a485de1a037b409797'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestYaml.test_d13_escaped_slash', '82edd49a4785fa587abadf1175dc33f20aacbcf19bc75c743f31a53f10919d56'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestYaml.test_d14_block_header', 'cd843f1023843a0fc25c71d005dd39d56deb60feefc8bbee95ab166b3151d0e8'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestYaml.test_d15_block_leading', '02970e3c1eafadb4221bf4be57e86c4504e5c272dd91738d3abb3d7161d4f6d5'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestYaml.test_d16_trailing_spaces', '7cbfb700d27e43d9de326a99e18a297a715e9c3fdffbffc730110eb1add0264f'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestYaml.test_escape_tab_ok', '205315dc66f3999173560e7c220ebe8d52208562375d8b00403cd0df7c9bc538'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestYaml.test_d17_doc_end', 'c7824676925572c49c9ca78251bd813c5df386132010ddc7dc0b8b110c00a170'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestYaml.test_tab_only_in_comment', '20e4813cf5cff38eab2c6736a71a695261909d8712c45143a0f7f654a97ab835'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestYaml.test_rare_rules', '003fd60b2c06d3684cee9ae8b3f9997575bf40f5d9138bb6a05254908c5b52e5'), ('skills/lesson-spec/scripts/v7/test_v7.py', 'TestYaml.test_style_scalars', '7fda241b2c279750ee93a329f02f28465de28c848bed3288e1a6ce8705caf151')]
        for relative, name, digest in expected:
            path = ROOT / relative
            text = path.read_text(encoding="utf-8")
            lines = text.split("\n")
            tree = ast.parse(text)
            parts = name.split(".")
            node = tree
            for part in parts:
                node = next(n for n in node.body if getattr(n, "name", None) == part or
                            isinstance(n, ast.Assign) and len(n.targets) == 1 and
                            isinstance(n.targets[0], ast.Name) and n.targets[0].id == part)
            first = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
            raw = ("\n".join(lines[first-1:node.end_lineno]) + "\n").encode("utf-8")
            self.assertEqual(hashlib.sha256(raw).hexdigest(), digest, relative + ":" + name)
        constructor_sites = (
            ("skills/lesson-spec/scripts/v7/spec.py", "family_readers", "row['key']"),
            ("skills/lesson-spec/scripts/v7/spec.py", "judge_row", "row['key']"),
            ("skills/lesson-spec/scripts/v7/transition.py", "add_rows", "fam"),
            ("tools/normgen/family_judge.py", "v7_cases", "row['key']"),
            ("skills/lesson-spec/scripts/v7/section.py", "build_families_section", "row['key']"),
        )
        for relative, owner, identity in constructor_sites:
            tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
            function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == owner)
            calls = [n for n in ast.walk(function) if isinstance(n, ast.Call) and
                     (isinstance(n.func, ast.Attribute) and n.func.attr == "Family" or
                      isinstance(n.func, ast.Name) and n.func.id == "SchemaSection")]
            self.assertEqual(len(calls), 1, owner)
            keyword = next((k.value for k in calls[0].keywords if k.arg == "family_template"), None)
            self.assertIsNotNone(keyword, owner)
            self.assertEqual(ast.dump(keyword), ast.dump(ast.parse(identity, mode="eval").body), owner)
        # Separate producer input is mandatory: this is not a reason to execute the unchanged old object.
        generator_tree = ast.parse((HERE / "gen_families.py").read_text(encoding="utf-8"))
        loader = next(n for n in generator_tree.body if isinstance(n, ast.FunctionDef) and n.name == "load_family_doc")
        source_literals = {n.value for n in ast.walk(loader) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        self.assertTrue({"domain/deleting/<name>", "person_writer", "role_writer"} <= source_literals)


@unittest.skipUnless((ROOT / "Platform/common/vectors/family-read/02.tsv").is_file(), "no P/02 family vectors")
class DocMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
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
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        for name in ("families.go", "runtime.go"):
            self.assertEqual((self.mod / "families" / name).read_bytes(),
                             (output_lesson.output_root() / 'p02/go/families' / name).read_bytes(), name)

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
