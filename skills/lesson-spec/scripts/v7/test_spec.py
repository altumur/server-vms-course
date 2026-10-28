"""Тесты навыка на стандартных файлах В7 (PLAN-TRANSITION п. 1.4): переносимость выражений, места и исходы по схеме,
разделы норм, проверки check_spec режима В7 на дереве после пакета перехода (v7.transition) — и что каждая проверка
краснеет от своей порчи.

    cd skills/lesson-spec/scripts && <окружение check_spec со стеком В7> python -B -m unittest v7.test_spec

Окружение — как у check_spec со стеком В7 (references/validation.md): PyYAML, jsonschema 4.26.0, ruamel.yaml 0.19.1,
cel-expr-python 0.1.3; без них дерево не строится и тесты на нём пропускаются.
"""
import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from v7 import regex, section, spec, view  # noqa: E402

ROOT = HERE.parents[3]
try:
    import cel_expr_python  # noqa: F401
    import yaml  # noqa: F401
    HAVE_STACK = True
except ImportError:
    HAVE_STACK = False
TREE = None


def setUpModule():
    """Копия Platform/, VMS/ и манифестов курса с пакетом перехода — одна на модуль."""
    global TREE
    if not HAVE_STACK:
        return
    TREE = Path(tempfile.mkdtemp(prefix="v7-tree-"))
    for d in ("Platform", "VMS", "Source/tests/testdata"):
        shutil.copytree(ROOT / d, TREE / d, ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"))
    from v7 import transition
    with contextlib.redirect_stdout(io.StringIO()):
        transition.main(["--root", str(TREE)])


def tearDownModule():
    if TREE is not None:
        shutil.rmtree(TREE, ignore_errors=True)


NEED_TREE = unittest.skipUnless(HAVE_STACK, "нет окружения check_spec со стеком В7")


class TestPortable(unittest.TestCase):
    def test_portable_patterns(self):
        for p in ["^(?:[a-z][a-z0-9_-]{0,31})$", "^(?:[\\s\\S]*_secret)$", "^(?:a|b)$", "^(?:\\.x)$",
                  "^(?:[^/\\\\]+)$", "^(?:[a-z]{1,3}?)$"]:
            self.assertIsNone(regex.check(p), p)

    def test_unportable_patterns(self):
        for p in ["a", "^(?:a.b)$", "^(?:\\s)$", "^(?:(?=a))$", "^(?:(?<n>a))$", "^(?:\\1)$", "^(?:a{2)$",
                  "^(?:[[:alpha:]])$", "^(?:a]b)$", "^(?:\\u0041)$", "^(?:a$b)$", "^(?:[]a])$", "^(?:\\-)$"]:
            self.assertIsNotNone(regex.check(p), p)


class TestSchemaPlaces(unittest.TestCase):
    DOC = {"type": "object", "properties": {"a": {"$ref": "#/$defs/x"}, "l": {"type": "array", "items": {"type": "integer"}}},
           "additionalProperties": False,
           "$defs": {"x": {"type": "object", "properties": {"b": {"type": "string"}},
                           "additionalProperties": {"type": "object", "properties": {"c": {"type": "string"}}}}}}

    def test_self_contained(self):
        self.assertEqual(spec.self_contained(self.DOC), [])
        self.assertTrue(spec.self_contained({"$ref": "common.schema.json#/$defs/x"}))
        self.assertTrue(spec.self_contained({"$ref": "#/$defs/missing"}))

    def test_places(self):
        pl = spec.Places(self.DOC)
        for p in ["/a", "/a/b", "/a/*", "/a/*/c", "/a/zz/c", "/l/*", "/l/0"]:
            self.assertTrue(pl.place(p), p)
        for p in ["/zz", "/a/b/c", "/l/x"]:
            self.assertFalse(pl.place(p), p)
        wild = {}
        pl.place("/a/*/c", wild)
        self.assertEqual(wild, {1: frozenset({"b"})})

    def outcomes(self, rows):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        p = d / "f.outcomes.tsv"
        p.write_text("\t".join(spec.OUTCOME_HEADER) + "\n" + "".join("\t".join(r) + "\n" for r in rows), encoding="utf-8")
        return spec.load_outcomes(p, self.DOC)

    def test_outcomes_reader(self):
        out = self.outcomes([["", "console", "x", "1", "строка", "N"], ["", "<s>worker", "y", "1", "строка", "N"],
                             ["/a/b", "*", "z", "0", "поле", "N"]])
        self.assertEqual(spec.readers_of(out), ["console", "<s>worker"])
        self.assertEqual([o.path for o in spec.outcomes_for(out, ["/a/b"], "console")], ["/a/b"])
        self.assertEqual([o.outcome for o in spec.outcomes_for(out, ["/zz"], "<s>worker")], ["y"])
        for bad in ([["", "*", "x", "1", "строка", "N"]],                                   # пустой путь — не *
                    [["", "console", "x", "1", "строка", "N"], ["", "console", "y", "1", "строка", "N"]],
                    [["", "nobody", "x", "1", "строка", "N"]],                              # не роль
                    [["", "console", "x", "1", "строка", "N"], ["/a/b/c", "*", "x", "1", "поле", "N"]],
                    [["/a/b", "*", "x", "1", "поле", "N"]]):                                # нет пустого пути
            with self.assertRaises(spec.SpecError):
                self.outcomes(bad)

    def test_unique_names(self):
        s = {"type": "array", "x-unique-by": "name", "items": {"type": "object"}}
        self.assertEqual(view.unique_names(s, [{"name": "a"}, {"name": "b"}]), [])
        self.assertEqual(view.unique_names(s, [{"name": "a"}, {"name": "a"}]), [""])

    def test_shown_escapes_invisible(self):
        self.assertEqual(section.shown("a\x00 б"), "a\\u{0000}\\u{2028}б")


@NEED_TREE
class TestTree(unittest.TestCase):
    """check_spec режима В7 на дереве после пакета перехода: чисто, и каждая проверка краснеет от своей порчи."""

    def copy(self):
        """Своё дерево для порчи (копия общего)."""
        d = Path(tempfile.mkdtemp(prefix="v7-tree-mut-"))
        self.addCleanup(shutil.rmtree, d, True)
        shutil.copytree(TREE, d, dirs_exist_ok=True)
        return d

    def manifest(self, root):
        spec_dir = root / "Platform/02-installer/spec"
        acc = root / "Platform/02-installer/acceptance/1"
        verdicts = dict(ln.split("\t") for ln in (acc / "verdicts.tsv").read_text(encoding="utf-8").split("\n")
                        if ln and not ln.startswith("#"))
        classes = dict(ln.split("\t") for ln in (acc / "classes.tsv").read_text(encoding="utf-8").split("\n")
                       if ln and not ln.startswith("#"))
        norms = spec_dir / "02.1-installer.norms.md"
        return spec.manifest_check(root, norms, norms.read_text(encoding="utf-8"), spec_dir / "02.1-installer", acc,
                                   verdicts, classes, sorted((root / "Source/tests/testdata").glob("*.subsystem.yaml")),
                                   strict=False)

    def test_manifest_clean(self):
        errors, stats = self.manifest(TREE)
        self.assertEqual(errors, [])
        self.assertEqual(stats["form_cases"], 680)
        self.assertGreaterEqual(stats["form_rows_held"], 120)

    def test_strict_coverage_implied(self):
        """Строка 18 держится групповой мутацией (x-implied-by [16, 17]); без пометки — красная; пометка без случая
        группы — красная."""
        root = self.copy()
        p = root / "Platform/02-installer/spec/02.1-installer.relations.json"
        rel = json.loads(p.read_text(encoding="utf-8"))
        row = next(r for r in rel["rows"] if r["no"] == 18)
        self.assertEqual(row.get("x-implied-by"), [16, 17])

        def strict():
            spec_dir = root / "Platform/02-installer/spec"
            acc = root / "Platform/02-installer/acceptance/1"
            verdicts = dict(ln.split("\t") for ln in (acc / "verdicts.tsv").read_text(encoding="utf-8").split("\n")
                            if ln and not ln.startswith("#"))
            return spec.manifest_check(root, spec_dir / "02.1-installer.norms.md", None, spec_dir / "02.1-installer",
                                       acc, verdicts, {}, [], strict=True)[0]
        self.assertEqual([m for _, m in strict() if "row 18" in m], [])
        del row["x-implied-by"]
        p.write_text(json.dumps(rel, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        self.assertTrue(any("row 18: no corpus case" in m for _, m in strict()))
        row["x-implied-by"] = [4]                          # строка не из группы: случая группы нет
        p.write_text(json.dumps(rel, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        self.assertTrue(any("row 18: x-implied-by [4]" in m for _, m in strict()))

    def test_manifest_class_is_layer(self):
        root = self.copy()
        p = root / "Platform/02-installer/acceptance/1/classes.tsv"
        text = p.read_text(encoding="utf-8")
        p.write_text(text.replace("\tform\n", "\trelations\n", 1), encoding="utf-8")
        errors, _ = self.manifest(root)
        self.assertTrue(any("class expected relations" in m for _, m in errors), errors[:3])

    def test_manifest_section_built(self):
        root = self.copy()
        p = root / "Platform/02-installer/spec/02.1-installer.norms.md"
        p.write_text(p.read_text(encoding="utf-8").replace("| `name` |", "| `nam` |", 1), encoding="utf-8")
        errors, _ = self.manifest(root)
        self.assertTrue(any("section differs" in m for _, m in errors))

    def test_manifest_layers_table(self):
        root = self.copy()
        p = root / "Platform/02-installer/spec/02.1-installer.layers.tsv"
        p.write_text(p.read_text(encoding="utf-8") + "x\t2\tx-integer-place\ttrue\n", encoding="utf-8")
        errors, _ = self.manifest(root)
        self.assertTrue(any("x-* words" in m for _, m in errors))

    def test_families_clean_and_section(self):
        cat = spec.read_catalog(TREE)
        from v7 import sections
        for norms in sorted((TREE / "Platform").glob("*/spec/*.norms.md")):
            text = norms.read_text(encoding="utf-8")
            if section.FAMILIES_BEGIN not in text:
                continue
            errors, _ = spec.families_check(TREE, norms, text, sections.chapter_prefix(norms), cat)
            self.assertEqual(errors, [], norms.name)

    def test_family_outcome_place(self):
        root = self.copy()
        p = root / "Platform/03-worker/data/slots.outcomes.tsv"
        p.write_text(p.read_text(encoding="utf-8").replace("/gen\t", "/gen/zz\t", 1), encoding="utf-8")
        row = next(r for r in spec.read_catalog(root) if r["schema"].endswith("/slots.schema.json"))
        with self.assertRaisesRegex(spec.SpecError, "not a place"):
            spec.load_family(root, row)

    def test_family_schema_portable_and_self_contained(self):
        root = self.copy()
        p = root / "Platform/03-worker/data/slots.schema.json"
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc["properties"]["x"] = {"type": "string", "pattern": "^(?:a.b)$"}
        p.write_text(json.dumps(doc), encoding="utf-8")
        row = next(r for r in spec.read_catalog(root) if r["schema"].endswith("/slots.schema.json"))
        with self.assertRaisesRegex(spec.SpecError, "pattern"):
            spec.load_family(root, row)
        doc["properties"]["x"] = {"$ref": "common.schema.json#/$defs/common.time"}
        p.write_text(json.dumps(doc), encoding="utf-8")
        with self.assertRaisesRegex(spec.SpecError, "outside the file"):
            spec.load_family(root, row)

    def test_canonical_chapter(self):
        from v7 import vectors
        ch = vectors.Chapter(TREE, strict=True).run()
        self.assertEqual(ch.errors, [])
        self.assertEqual(ch.stats["canonical_vectors"], 157)
        self.assertEqual(ch.stats["canonical_mutants_killed"], ch.stats["canonical_mutants"])
        root = self.copy()
        e = sorted((root / vectors.VECTORS / "expect").glob("corpus-*.json"))[0]
        e.write_bytes(e.read_bytes().replace(b"}", b" }", 1))
        self.assertTrue(any("differs from the built view" in m for _, m in vectors.Chapter(root).run().errors))

    def test_family_read(self):
        cat = spec.read_catalog(TREE)
        errors, stats = spec.family_read(TREE, cat)
        self.assertEqual(errors, [])
        self.assertGreater(stats["family_read_rows"], 4000)
        root = self.copy()
        p = root / spec.FAMILY_READ / "03.tsv"
        lines = p.read_text(encoding="utf-8").split("\n")
        i = next(i for i, ln in enumerate(lines[1:], 1) if "\tok\t[]\t" in ln and "\treader\t" in ln)
        lines[i] = lines[i].replace("\tok\t[]\t", "\trefused\t[\"\"]\t", 1)
        p.write_text("\n".join(lines), encoding="utf-8")
        errors, _ = spec.family_read(root, cat, judge=True)
        self.assertTrue(any("V7 stack gives" in m for _, m in errors), errors[:2])

    def test_outcome_readers(self):
        """Строка пустого пути у каждого читателя (решение владельца 2026-10-28): снять — красное, чужая роль — красное."""
        sys.path.insert(0, str(HERE.parent))
        import check_spec
        root = self.copy()
        p = root / "Platform/03-worker/data/slots.outcomes.tsv"
        lines = p.read_text(encoding="utf-8").split("\n")
        whole = [ln for ln in lines if ln.startswith("\t")]
        self.assertGreater(len(whole), 1)
        lines.remove(whole[0])
        lines.append("\tadmin" + whole[1][len("\t") + len(whole[1].split("\t")[1]):])
        p.write_text("\n".join(lines), encoding="utf-8")
        check = check_spec.Check(root, None, False)
        with contextlib.redirect_stdout(io.StringIO()):
            for lesson in sorted((root / "Platform").glob("0*-*/0*.md")):
                check.lesson(lesson.resolve())
            check.outcome_readers()
        mine = [str(e) for e in check.errors if "slots.outcomes.tsv" in str(e)]
        self.assertTrue(any("no outcome of the whole row" in e for e in mine), mine)
        self.assertTrue(any("admin is not a reader" in e for e in mine), mine)

    def test_sections_idempotent(self):
        from v7 import sections
        root = self.copy()
        for norms in sorted((root / "Platform").glob("*/spec/*.norms.md")):
            before = norms.read_bytes()
            sections.rewrite(norms, root)
            self.assertEqual(norms.read_bytes(), before, norms.name)


if __name__ == "__main__":
    unittest.main()
