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
# Окружение навыка одно (scripts/requirements.txt): без стека В7 модуль падает с именем пакета, а не пропускается
# (повторное ревью Claude Н-1).
import cel_expr_python  # noqa: F401,E402
import yaml  # noqa: F401,E402
TREE = None


def setUpModule():
    """Копия Platform/, VMS/ и манифестов курса с пакетом перехода (если курс ещё на диалекте) — одна на модуль."""
    global TREE
    TREE = Path(tempfile.mkdtemp(prefix="v7-tree-"))
    for d in ("Platform", "VMS", "Source/tests/testdata"):
        shutil.copytree(ROOT / d, TREE / d, ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"))
    if (TREE / "Platform/02-installer/spec/02.1-installer.form.yaml").is_file():     # курс ещё на диалекте
        from v7 import transition
        with contextlib.redirect_stdout(io.StringIO()):
            transition.main(["--root", str(TREE)])


def tearDownModule():
    if TREE is not None:
        shutil.rmtree(TREE, ignore_errors=True)


def NEED_TREE(cls):                            # дерево строится всегда (стек — обязательная часть окружения)
    return cls


class TestEnvironment(unittest.TestCase):
    def test_pinned(self):
        """Окружение прогона — закреплённое scripts/requirements.txt; пины стека В7 (v7/requirements.txt) в нём те же."""
        import re
        sys.path.insert(0, str(HERE.parent))
        import check_spec
        self.assertEqual(check_spec.environment(), [])
        pins = lambda p: dict(re.findall(r"(?m)^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;]+)", p.read_text(encoding="utf-8")))  # noqa: E731
        norm = lambda n: re.sub(r"[-_.]+", "-", n).lower()                                               # noqa: E731
        whole = {norm(k): v for k, v in pins(HERE.parent / "requirements.txt").items()}
        for k, v in pins(HERE / "requirements.txt").items():
            self.assertEqual(whole.get(norm(k)), v, k)


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

    def test_scalars_table_is_patterns(self):
        """Таблица скаляров раздела «Форма» — шаблоны `scalars.tsv`, не repr скомпилированных (замечание «Спецификации»);
        строки — те же, что у раздела диалекта."""
        from v7 import textv7
        base = ROOT / "Platform/02-installer/spec/02.1-installer"
        doc = json.loads((HERE / "out/02.1-installer.schema.json").read_text(encoding="utf-8"))
        rel = json.loads((HERE / "out/02.1-installer.relations.json").read_text(encoding="utf-8"))
        built = section.build_form_section(doc, rel, textv7.load_scalars(Path(str(base) + ".scalars.tsv")))
        self.assertNotIn("re.compile", built)
        table = built[built.index("#### Таблица скаляров"):built.index("Пределы:")]
        for ln in (Path(str(base) + ".scalars.tsv")).read_text(encoding="utf-8").split("\n"):
            cols = ln.split("\t")
            if ln and not ln.startswith("#") and cols[0] not in ("kind", "limit"):
                self.assertIn("| %s | `%s` |" % (cols[0], section.cell(cols[1])) if cols[1] else "| %s | `` |" % cols[0],
                              table)
        norms = Path(str(base) + ".norms.md").read_text(encoding="utf-8")
        if "#### Таблица скаляров" in norms and (Path(str(base) + ".form.yaml")).is_file():     # раздел диалекта
            old = norms[norms.index("#### Таблица скаляров"):norms.index("Пределы:", norms.index("#### Таблица скаляров"))]
            self.assertEqual(table, old)

    def test_shown_escapes_invisible(self):
        self.assertEqual(section.shown("a\x00 б"), "a\\u{0000}\\u{2028}б")


def verdicts_of(root):
    acc = root / "Platform/02-installer/acceptance/1"
    return dict(ln.split("\t") for ln in (acc / "verdicts.tsv").read_text(encoding="utf-8").split("\n")
                if ln and not ln.startswith("#"))


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
        self.assertEqual(stats["form_cases"], 684)
        self.assertGreaterEqual(stats["form_rows_held"], 120)

    def test_strict_coverage_implied(self):  # noqa: C901
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
        self.assertTrue(any("without the exception implied" in m for _, m in
                            spec.manifest_check(root, root / "Platform/02-installer/spec/02.1-installer.norms.md", None,
                                                root / "Platform/02-installer/spec/02.1-installer", root /
                                                "Platform/02-installer/acceptance/1", verdicts_of(root), {}, [], False, set())[0]))
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
        self.assertEqual(ch.stats["canonical_vectors"], 159)
        self.assertEqual(ch.stats["canonical_mutants_killed"], ch.stats["canonical_mutants"])
        self.assertEqual(ch.stats["canonical_mutants"], 62)              # и default у корня определения (Б-1)
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
        field = next(ln for ln in lines if ln.startswith("/"))
        lines.append(field.split("\t")[0] + "\tresource\t" + "\t".join(field.split("\t")[2:]))   # С-3: не читатель
        p.write_text("\n".join(lines), encoding="utf-8")
        (root / spec.FAMILY_READ / "03.tsv").unlink()                                       # С-1: нет таблицы урока
        check = check_spec.Check(root, None, False)
        with contextlib.redirect_stdout(io.StringIO()):
            for lesson in sorted((root / "Platform").glob("0*-*/0*.md")):
                check.lesson(lesson.resolve())
            check.outcome_readers()
        mine = [str(e) for e in check.errors if "slots.outcomes.tsv" in str(e)]
        self.assertTrue(any("no outcome of the whole row" in e for e in mine), mine)
        self.assertTrue(any("admin is not a reader" in e for e in mine), mine)
        self.assertTrue(any("names resource, not a reader" in e for e in mine), mine)
        self.assertTrue(any("no table 03.tsv" in str(e) for e in check.errors))
        self.assertTrue(any("no table 08.tsv" in str(e) for e in check.errors))   # без реестра отложенная — красная

    @unittest.skipUnless((ROOT / "Platform/02-installer/spec/02.1-installer.form.yaml").is_file(),
                         "нужны разделы диалекта курса (до пакета п. 2)")
    def test_sections_keep_dialect_meaning(self):
        """Ревью Claude Б-1, Б-2: у каждой строки таблиц разделов диалекта непустые «Урок», «Смысл» и умолчание есть и
        в В7 — пометки места, а нет у места — у цели ссылки; теряется только «класс отказа …» (класс — слой, п. 6)."""
        import re
        marks = [(section.FORM_BEGIN, section.FORM_END), (section.FAMILIES_BEGIN, section.FAMILIES_END),
                 (view.BEGIN, view.END)]

        def rows(text):
            out, head = {}, ""
            for b, e in marks:
                if b not in text:
                    continue
                for ln in text[text.index(b):text.index(e)].split("\n"):
                    if ln.startswith("#### ") or ln.startswith("**`"):
                        head = ln
                    cells = [c.strip() for c in re.split(r"(?<!\\)\|", ln)[1:-1]]
                    if ln.startswith("| `") and len(cells) == 5:
                        out[(b, head if b == section.FAMILIES_BEGIN else "", cells[0])] = cells
            return out
        lost, n = [], 0
        for p in sorted((ROOT / "Platform").glob("*/spec/*.norms.md")):
            a = rows(p.read_text(encoding="utf-8"))
            if not a:
                continue
            b = rows((TREE / p.relative_to(ROOT)).read_text(encoding="utf-8"))
            for k, v in a.items():
                w = b.get(k)
                if w is None:
                    continue
                n += 1
                if "умолчание" in v[2] and "умолчание" not in w[2]:
                    lost.append(("need", p.name, k[2]))
                if v[3] and not w[3]:
                    lost.append(("owner", p.name, k[2]))
                if v[4] and not w[4] and not v[4].startswith("класс отказа"):
                    lost.append(("desc", p.name, k[2]))
        self.assertGreater(n, 1500)
        self.assertEqual(lost, [])

    def test_sections_idempotent(self):
        from v7 import sections
        root = self.copy()
        for norms in sorted((root / "Platform").glob("*/spec/*.norms.md")):
            before = norms.read_bytes()
            sections.rewrite(norms, root)
            self.assertEqual(norms.read_bytes(), before, norms.name)


@NEED_TREE
class TestStack(unittest.TestCase):
    """Ловушки стека В7 и шаги проекции П1–П5 на стандартных файлах дерева (ревью Claude С-2: раньше — через генератор
    диалекта и form_source, после перехода не исполнялись)."""

    @classmethod
    def setUpClass(cls):
        from v7 import stack, vectors
        cls.stack = stack
        cls.fams = {(r["key"], r["kind"]): spec.load_family(TREE, r) for r in spec.read_catalog(TREE)
                    if spec.is_v7_family(r)}
        cls.ld = vectors.loader(TREE)
        cls.man = cls.ld.sch.doc

    def objects(self):
        return [(k, f) for k, f in self.fams.items() if k[1] == "object"]

    def test_empty_key_beside_names_pattern(self):
        """Ключ "" в properties рядом с именем по выражению: propertyNames с исключением "" (ревью Gemini 4.2)."""
        hits = [f for f in self.fams.values() if "common.book_row" in f[2].get("$defs", {})]
        self.assertTrue(hits, "семья с common.book_row")
        defs = hits[0][2]["$defs"]
        book = defs["common.book_row"]
        self.assertEqual(book["propertyNames"]["anyOf"][0], {"enum": [""]})
        rec = self.stack.py_records(self.stack.validator_for(dict(book, **{"$defs": defs})), {"": "x"})
        self.assertFalse([r for r in rec if r[1] == "propertyNames"], rec)
        bare = dict(book, propertyNames=book["propertyNames"]["anyOf"][1])
        rec = self.stack.py_records(self.stack.validator_for(dict(bare, **{"$defs": defs})), {"": "x"})
        self.assertTrue([r for r in rec if r[1] == "propertyNames"], "без исключения ключ \"\" отказан")

    def test_trailing_newline_full_match(self):
        """$ в pattern у Python совпадает перед хвостовым \\n — у стека В7 полный матч (слой 5)."""
        import jsonschema
        s = {"type": "string", "pattern": regex.anchored("[a-z][a-z0-9_-]{0,31}")}
        self.assertTrue(jsonschema.Draft202012Validator(s).is_valid("w-1\n"))      # дефект без слоя
        self.assertFalse(self.stack.validator_for(s).is_valid("w-1\n"))
        self.assertTrue(self.stack.validator_for(s).is_valid("w-1"))

    def test_trailing_newline_manifest(self):
        base = (TREE / "Platform/02-installer/acceptance/1/cases/r38_unit_minimal.subsystem.yaml").read_bytes()
        self.assertEqual(self.ld.judge(base)["verdict"], "ok")
        bad = base.replace(b"worker: {exec: /usr/lib/probe/worker}", b'worker: {exec: "/usr/lib/probe/worker\\n"}')
        self.assertNotEqual(bad, base)
        self.assertEqual(self.ld.judge(bad)["verdict"], "refused")

    def test_outcomes_unit(self):
        """Единица исходов: отказ ниже строки с единицей `поле`/`элемент` делает нечитаемым только её место; у
        читателя — его строки и `*`."""
        O = spec.Outcome
        rows = [O("", "console", "строка нечитаема", 2, "строка", "n"), O("", "admin", "иначе", 2, "строка", "n"),
                O("/a", "*", "поле a пропущено", 1, "поле", "n"), O("/b", "*", "b — строка целиком", 3, "строка", "n")]
        got = lambda paths, r: [o.outcome for o in spec.outcomes_for(rows, paths, r)]   # noqa: E731
        self.assertEqual(got(["/a/x"], "console"), ["поле a пропущено"])
        self.assertEqual(got(["/b/x"], "console"), ["строка нечитаема"])
        self.assertEqual(got(["/b/x"], "admin"), ["иначе"])
        self.assertEqual(got(["/a/x", "/c"], "console"), ["поле a пропущено"])
        self.assertEqual(got([], "console"), [])

    def test_negative_integer_bound(self):
        """Граница целого манифеста (п. 8): −9007199254740992 — отказ, −9007199254740991 — принято, `4.0` — целое."""
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
        v = self.stack.validator_for(dict(free[0], **{"$defs": self.man["$defs"]}))
        self.assertFalse(v.is_valid(-9007199254740992))
        self.assertTrue(v.is_valid(-9007199254740991))
        self.assertTrue(v.is_valid(4.0))

    def test_1e400(self):
        """1e400 — число вне binary64: отказ на своём месте у читателя и у писателя (дельта Б к эталону)."""
        n = 0
        for key, (_, _, doc, _, _) in self.objects():
            for mode in ("reader", "writer"):
                got = self.stack.Family(doc, "object").judge('{"zz_1e400": 1e400}', mode)
                self.assertEqual(got["verdict"], "refused")
                self.assertIn("/zz_1e400", got["paths"], (key, got))
                n += 1
        self.assertGreater(n, 30)

    def test_null_root(self):
        """JSON null вместо объекта семьи — отказ на корне (дельта Б к эталону)."""
        n = 0
        for key, (_, _, doc, _, _) in self.objects():
            for mode in ("reader", "writer"):
                got = self.stack.Family(doc, "object").judge("null", mode)
                self.assertEqual((got["verdict"], got["paths"]), ("refused", [""]), (key, mode))
                n += 1
        self.assertGreater(n, 30)

    # ---- шаги проекции урока 2 (P/02.2-02, -03) на v7.project
    BASE = ("name: probe\nunit:\n  rows: things\n  id: numeric\n  fields:\n%s\nplacement:\n  capacity: {default: 1}\n"
            "worker:\n  exec: /usr/lib/probe/worker\n%s")
    FIELDS = "    label: {}\n    login: {}\n    pass_secret: {bound_to: login}\n    pic: {type: blob}\n    server: {}"

    def view(self, fields=None, tail="", skip=()):
        from v7 import project
        r = self.ld.judge((self.BASE % (fields or self.FIELDS, tail)).encode("utf-8"))
        self.assertEqual(r["verdict"], "ok", r)
        return json.loads(self.stack.jcs(project.canonical(self.ld.sch, r["tree"], skip)))

    def test_step_places(self):
        from v7 import vectors
        places = spec.Places(self.man)
        self.assertEqual([n for n, ptrs in vectors.STEP_PLACES if all(places.place(p) for p in ptrs)],
                         [s[0] for s in view.STEPS])

    def test_sugar(self):
        v = self.view(tail="tables: [a, b]\n")
        self.assertEqual(list(v["tables"]), ["a", "b"])
        self.assertEqual(v["tables"]["a"], {"fields": [], "journal": {"written": "a.written", "deleted": "a.deleted"}})
        f = {x["name"]: x for x in v["unit"]["fields"]}
        self.assertEqual(f["pass_secret"]["bound_to"], ["login"])
        v = self.view("    cam: {type: url, secret_in: [{regex: 'x', in: query}, {param: [p]}]}")
        self.assertEqual(v["unit"]["fields"][0]["secret_in"], [{"decoded": True, "in": ["query"], "regex": "x"},
                                                                {"param": ["p"]}])

    def test_computed(self):
        v = self.view()
        self.assertEqual(v["snapshot"], ["label", "login"])                                  # П1
        self.assertEqual(v["display"]["form"], [{"fields": ["label", "login", "pass_secret", "pic", "server"]}])   # П3
        self.assertTrue(all(x["default"] is None for x in v["unit"]["fields"]))             # П4, и у blob
        self.assertTrue(all(x["type"] == "string" for x in v["unit"]["fields"] if x["name"] != "pic"))   # Б-1
        self.assertEqual(self.view(tail="snapshot: []\n")["snapshot"], [])
        self.assertEqual(self.view(tail="display: {form: [{title: t}]}\n")["display"]["form"], [{"title": "t"}])
        v = self.view(tail="tables:\n  t:\n    journal: {written: w}\n")
        self.assertEqual(v["tables"]["t"]["journal"], {"written": "w", "deleted": "t.deleted"})   # П2
        v = self.view("    n: {type: int, inherit: 1}\n    m: {type: int, default: 2}")
        self.assertEqual([x["default"] for x in v["unit"]["fields"]], [None, 2])
        v = self.view("    cam: {type: url, secret_in: [{regex: 'x', decoded: false}]}")
        self.assertEqual(v["unit"]["fields"][0]["secret_in"], [{"decoded": False, "regex": "x"}])   # П5 — не сказано

    def test_defaults_only_inside_present_parent(self):
        v = self.view()
        self.assertNotIn("requests", v)
        self.assertEqual(v["placement"]["weight"], {"default": 1})
        self.assertEqual(v["lease"], {"unconfirmed_max": "off"})
        self.assertEqual(v["display"]["unit"], "единица")
        self.assertNotIn("section", v["display"])
        self.assertNotIn("suppress", v["events"])

    def test_ordered_keeps_the_author_order(self):
        v = self.view("    zz: {}\n    aa: {}")
        self.assertEqual([x["name"] for x in v["unit"]["fields"]], ["zz", "aa"])
        self.assertEqual(v["snapshot"], ["zz", "aa"])

    def test_skipping_a_step_changes_the_view(self):
        for name, *_ in view.STEPS:
            if name in ("in", "П5"):
                continue
            self.assertNotEqual(self.view(tail="tables: [a]\n"), self.view(tail="tables: [a]\n", skip=(name,)), name)


if __name__ == "__main__":
    unittest.main()
