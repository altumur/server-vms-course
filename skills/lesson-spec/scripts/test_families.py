"""Схемы семей данных (ADR-0088): слова data-form/1, раздел «Семьи данных», исходы, судья с кодеком."""
import tempfile
import unittest
from pathlib import Path

from form_source import SourceError
from form_source.families import (Judge, build_families_section, chapter_families, chapter_prefix, load_family,
                                  outcomes_for, read_catalog, schema_place)
from form_source.source import load_common, load_form, py_pattern

COMMON = """dialect: data-form/1
defs:
  time:
    type: time
    description: время
  uint53:
    type: integer
    minimum: 0
    maximum: 9007199254740991
  hexish:
    type: string
    pattern: '[^\\x{0000}-\\x{001F}]+'
"""

SLOT = """dialect: data-form/1
root:
  type: object
  properties:
    gen:
      ref: common.uint53
      whole: true
      description: поколение
    seen:
      ref: common.time
    tags:
      type: array
      max_items: 2
      items:
        type: string
    doc:
      type: object
      encoding: jcs
      properties:
        n:
          type: integer
      required: [n]
    label:
      type: string
      pattern: '[^\\x{0000}-\\x{001F}]+'
      max_bytes: 4
    name:
      ref: common.hexish
    ratio:
      type: number
      writer:
        maximum: 1
  required: [gen, seen]
"""

OUTCOMES = """# исходы
path\toutcome\tpriority\tunit\tnorm
\tотказ выдачи\t1\tстрока\tP/03.2 Н3
/gen\timport: отказ входа\t0\tстрока\tP/03.2 Н4
/tags\tсписок не читается\t2\tполе\tP/03.2 Н1
"""

CATALOG = ("key\tkind\towner\tops\treaders\twhen\tversion\tschema\tnorm\n"
           "<sub>/slots/<id>\trow\tP/03.2\tput=<sub>worker\t*\t-\t1\t03-worker/data/slot.form.yaml\tP/03.2 Н1\n"
           "<sub>/other\trow\tP/03.1\tput=<sub>worker\t*\t-\t1\t-\tP/03.1 Н1\n")


class FamiliesBase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        data = self.root / "Platform/common/data"
        data.mkdir(parents=True)
        (data / "common.form.yaml").write_text(COMMON, encoding="utf-8")
        (data / "catalog.tsv").write_text(CATALOG, encoding="utf-8")
        self.data = self.root / "Platform/03-worker/data"
        self.data.mkdir(parents=True)
        (self.data / "slot.form.yaml").write_text(SLOT, encoding="utf-8")
        (self.data / "slot.outcomes.tsv").write_text(OUTCOMES, encoding="utf-8")
        self.norms = self.root / "Platform/03-worker/spec/03.2-worker.norms.md"

    def family(self):
        return chapter_families(self.root, "P/03.2")[0]


class DialectWords(FamiliesBase):
    def test_data_words_and_common_refs(self):
        form = self.family().form
        self.assertEqual(form.dialect, "data-form/1")
        self.assertIn("common.time", form.defs)
        self.assertEqual(form.root.properties["name"].ref, "common.hexish")

    def test_words_are_only_in_data_form(self):
        m10 = "dialect: m10-form/1\nroot:\n  type: string\n  max_bytes: 3\ndefs: {}\n"
        with self.assertRaisesRegex(SourceError, "outside the dialect"):
            load_form(m10.encode())
        with self.assertRaisesRegex(SourceError, "type"):
            load_form(b"dialect: m10-form/1\nroot:\n  type: time\ndefs: {}\n")

    def test_bad_data_words(self):
        common = load_common(self.root / "Platform/common/data/common.form.yaml")
        for body, why in (("type: string\n  whole: true", "whole needs type integer"),
                          ("type: integer\n  max_bytes: 3", "max_bytes needs type string"),
                          ("type: string\n  encoding: yaml", "encoding is one of"),
                          ("type: string\n  writer:\n    type: integer", "writer holds only constraints"),
                          ("ref: common.nope", "unknown ref")):
            with self.assertRaisesRegex(SourceError, why):
                load_form(("dialect: data-form/1\nroot:\n  %s\n" % body).encode(), common)

    def test_hex_code_in_pattern(self):
        self.assertEqual(py_pattern("[^\\x{0000}-\\x{1F}]"), "[^\\U00000000-\\U0000001f]")
        with self.assertRaisesRegex(SourceError, "escape"):
            load_form(b"dialect: m10-form/1\nroot:\n  type: string\n  pattern: '\\x{41}'\ndefs: {}\n")


class Catalog(FamiliesBase):
    def test_chapter_and_schema_place(self):
        self.assertEqual(chapter_prefix(self.norms), "P/03.2")
        self.assertEqual(chapter_prefix("spec/02-installer.norms.md"), "P/02")
        rows = read_catalog(self.root)
        self.assertEqual(schema_place(rows[0]), ("03", "slot"))
        for change, why in ((dict(owner="P/04.1"), "not in the lesson of its owner"),
                            (dict(kind="dir"), "only for row, JSON object and JSON file"),
                            (dict(schema="03-worker/slot.form.yaml"), "is not NN-")):
            with self.assertRaisesRegex(SourceError, why):
                schema_place(dict(rows[0], **change))

    def test_missing_files(self):
        (self.data / "slot.outcomes.tsv").unlink()
        with self.assertRaisesRegex(SourceError, "no outcomes file"):
            self.family()
        (self.data / "slot.form.yaml").unlink()
        with self.assertRaisesRegex(SourceError, "is not a file"):
            self.family()


LOCK = """dialect: data-form/1
root:
  type: object
  encoding: json
  properties:
    instance: {type: string}
    pid: {type: integer, minimum: 1, whole: true}
  required: [instance, pid]
"""


class JsonFile(FamiliesBase):
    """Файл с содержимым JSON — семья (ADR-0083 доп. (11), замок присутствия): корень схемы с `encoding` разбирает
    текст файла; файл без JSON схемы не имеет."""

    def setUp(self):
        super().setUp()
        (self.data / "slot.form.yaml").write_text(LOCK, encoding="utf-8")
        (self.data / "slot.outcomes.tsv").write_text("path\toutcome\tpriority\tunit\tnorm\n\tживой процесс без номера"
                                                     "\t0\tстрока\tP/05 Н1.4\n", encoding="utf-8")
        catalog = self.root / "Platform/common/data/catalog.tsv"
        catalog.write_text(catalog.read_text().replace("<sub>/slots/<id>\trow\t", "<root>/<x>.lock\tfile\t"))

    def test_judge_and_section(self):
        fam = self.family()
        self.assertEqual(fam.kind, "file")
        for mode in ("writer", "reader"):
            judge = Judge(fam.form, mode)
            self.assertEqual(judge.judge(b'{"instance":"a","pid":7}', "file")["verdict"], "ok")
            self.assertEqual(judge.judge('{"instance":"a","pid":0}', "file")["paths"], ["/pid"])
            self.assertEqual(judge.judge(b"", "file")["verdict"], "refused")
            self.assertEqual(judge.judge(b"\xff", "file")["verdict"], "refused")
        text = build_families_section(self.norms, self.root, [fam])
        for piece in ("Форма строк и объектов и файлов JSON", "файла — `{key, file}`", "#### `<root>/<x>.lock` — файл",
                      "| `pid` | целое; ≥ 1;", "Исходы нечитаемого файла:", "| файл целиком |"):
            self.assertIn(piece, text)

    def test_file_without_json_has_no_schema(self):
        (self.data / "slot.form.yaml").write_text(LOCK.replace("  encoding: json\n", ""), encoding="utf-8")
        with self.assertRaisesRegex(SourceError, "a file schema is for JSON content"):
            self.family()

    def test_rows_and_objects_keep_their_text(self):
        catalog = self.root / "Platform/common/data/catalog.tsv"
        catalog.write_text(catalog.read_text().replace("<root>/<x>.lock\tfile\t", "<sub>/slots/<id>\tobject\t"))
        text = build_families_section(self.norms, self.root, [self.family()])
        self.assertIn("Форма строк и объектов, которыми", text)
        self.assertNotIn("{key, file}", text)


class Outcomes(FamiliesBase):
    def write(self, text):
        (self.data / "slot.outcomes.tsv").write_text(text, encoding="utf-8")

    def test_outcomes_form(self):
        head = "path\toutcome\tpriority\tunit\tnorm\n\tx\t1\tстрока\tn\n"
        for row, why in (("/nope\tx\t1\tстрока\tn\n", "not a place of the schema"),
                         ("/gen\tx\tone\tстрока\tn\n", "priority"),
                         ("/gen\tx\t1\tузел\tn\n", "unit is one of"),
                         ("/gen\t\t1\tстрока\tn\n", "must be said"),
                         ("\ty\t1\tстрока\tn\n", "repeated")):
            self.write(head + row)
            with self.assertRaisesRegex(SourceError, why):
                self.family()
        self.write("path\toutcome\tpriority\tunit\tnorm\n/gen\tx\t1\tстрока\tn\n")
        with self.assertRaisesRegex(SourceError, "no outcome for the whole"):
            self.family()
        self.write("path\toutcome\tunit\tnorm\n")
        with self.assertRaisesRegex(SourceError, "header"):
            self.family()
        self.write(head + "/tags/0\tx\t1\tэлемент\tn\n/doc/n\tx\t1\tполе\tn\n")
        self.assertEqual(len(self.family().outcomes), 3)

    def test_outcomes_against_the_judge(self):
        fam = self.family()
        judge = Judge(fam.form, "reader")
        good = {"gen": "7", "seen": "12.5"}
        self.assertEqual(judge.judge(good)["verdict"], "ok")
        self.assertEqual(outcomes_for(fam.outcomes, judge.judge(good)["paths"]), [])
        # Пол не целым знаком — /gen; действует исход с наименьшим приоритетом (0), а не строка целиком (1).
        got = judge.judge({"gen": "7.0", "seen": "1"})
        self.assertEqual(got["paths"], ["/gen"])
        self.assertEqual([o.outcome for o in outcomes_for(fam.outcomes, got["paths"])], ["import: отказ входа"])
        # Незнакомый ключ и длинный список — пути вне /gen: строка целиком (1) раньше /tags (2).
        got = judge.judge({"gen": "1", "seen": "1", "tags": "a,b,c", "zz": "1"})
        self.assertEqual(got["paths"], ["/tags", "/zz"])
        self.assertEqual([o.outcome for o in outcomes_for(fam.outcomes, got["paths"])], ["отказ выдачи"])
        got = judge.judge({"seen": "1", "tags": "a,b,c"})
        self.assertEqual([o.priority for o in outcomes_for(fam.outcomes, got["paths"])], [0])

    def test_unit_below_keeps_the_container(self):
        """Единица `элемент` или `поле` (DIALECT § 9): отказ только ниже неё — её исход, даже если строка целиком раньше
        по приоритету; вместе с отказом вне её — строка целиком (пульс: `/status` и "", разбор ревью стадии B 6–7, № 14)."""
        self.write("path\toutcome\tpriority\tunit\tnorm\n\tцеликом\t1\tстрока\tn\n/tags\tэлемент\t2\tэлемент\tn\n"
                   "/gen\tпол\t3\tстрока\tn\n")
        fam = self.family()
        pick = lambda *paths: [o.outcome for o in outcomes_for(fam.outcomes, list(paths))]   # noqa: E731
        self.assertEqual(pick("/tags/3"), ["элемент"])
        self.assertEqual(pick("/tags/3", "/tags/5"), ["элемент"])
        self.assertEqual(pick("/tags/3", "/zz"), ["целиком"])
        self.assertEqual(pick("/gen"), ["целиком"])              # единица «строка» узел не держит
        self.assertEqual(pick(""), ["целиком"])

    def test_star_is_any_name_or_element(self):
        """`*` в пути исхода (DIALECT § 9): любое имя автора (кроме ключей properties) или любой элемент списка; на
        ином месте — ошибка; при выборе исхода совпадает с одним сегментом."""
        (self.data / "slot.form.yaml").write_text("""dialect: data-form/1
root:
  type: object
  properties:
    seq: {type: integer}
    members:
      type: object
      properties:
        fixed: {type: string}
      names:
        key: {type: string}
        value:
          type: object
          properties:
            at: {type: integer}
    tags: {type: array, items: {type: string}}
    free: {type: any}
    doc:
      type: object
      properties:
        x: {type: string}
  names:
    key: {type: string, pattern: 'e-[0-9]+'}
    value: {type: integer}
""", encoding="utf-8")
        head = "path\toutcome\tpriority\tunit\tnorm\n\tвсё\t9\tстрока\tn\n"
        for p in ("/free/*", "/doc/*", "/seq/*", "/*/*"):
            self.write(head + "%s\tx\t1\tэлемент\tn\n" % p)
            with self.subTest(path=p), self.assertRaisesRegex(SourceError, r"segment \* only at names or items"):
                self.family()
        self.write(head + "/members/*\tчлен пропускается\t1\tэлемент\tn\n/members/*/at\tat члена\t0\tполе\tn\n"
                   "/tags/*\tэлемент списка\t1\tэлемент\tn\n/*\tправка\t2\tэлемент\tn\n/seq\tseq\t3\tстрока\tn\n")
        fam = self.family()
        pick = lambda *paths: [o.outcome for o in outcomes_for(fam.outcomes, list(paths))]   # noqa: E731
        self.assertEqual(pick("/members/m1"), ["член пропускается"])
        self.assertEqual(pick("/members/m1/at"), ["at члена"])
        self.assertEqual(pick("/members/~1x/at", "/members/m2"), ["at члена"])
        self.assertEqual(pick("/members/fixed"), ["всё"])        # ключ properties — не имя автора
        self.assertEqual(pick("/members"), ["всё"])              # само отображение — не его элемент
        self.assertEqual(pick("/tags/3"), ["элемент списка"])
        self.assertEqual(pick("/e-1"), ["правка"])
        self.assertEqual(pick("/seq"), ["seq"])                  # /* не берёт ключ properties корня
        self.assertEqual(pick("/doc/x"), ["всё"])
        got = Judge(fam.form, "reader").judge({"seq": "1", "e-1": "z"})
        self.assertEqual(got["paths"], ["/e-1"])
        self.assertEqual(pick(*got["paths"]), ["правка"])
        # Строка таблицы исходов — путь как записан.
        text = build_families_section(self.norms, self.root, [fam])
        self.assertIn("| `/members/*` | член пропускается | 1 | элемент | n |", text)


class Codec(FamiliesBase):
    def judge(self, mode, **row):
        return Judge(self.family().form, mode).judge(dict({"gen": "1", "seen": "1"}, **row))

    def test_writer_strict_reader_tolerant(self):
        for field, text, writer, reader in (
                ("seen", "1.25", "ok", "ok"), ("seen", "1.2345", "refused", "ok"), ("seen", "01", "refused", "refused"),
                ("ratio", "0.5", "ok", "ok"), ("ratio", "0.50", "refused", "ok"), ("ratio", "5e-1", "refused", "ok"),
                ("ratio", "2", "refused", "ok"),                    # writer: maximum 1 — только у писателя
                ("tags", "a,b", "ok", "ok"), ("tags", '["a","b"]', "refused", "ok"), ("tags", "", "ok", "ok"),
                ("doc", '{"n":1}', "ok", "ok"), ('doc', '{ "n": 1 }', "refused", "ok"), ("doc", '{"n":1.0}', "refused", "ok"),
                ("doc", '{"n":1,"n":2}', "refused", "refused"), ("doc", '{"n":NaN}', "refused", "refused"),
                ("label", "abcd", "ok", "ok"), ("label", "abcde", "refused", "refused"), ("label", "a\x01", "refused", "refused")):
            with self.subTest(field=field, text=text):
                self.assertEqual(self.judge("writer", **{field: text})["verdict"], writer)
                self.assertEqual(self.judge("reader", **{field: text})["verdict"], reader)

    def test_tolerant_reader_closed_writer(self):
        """properties + names открывают лишние ключи читателю; writer: {max_items: 0} закрывает их писателю (DIALECT § 2)."""
        form = load_form(b"dialect: data-form/1\nroot:\n  type: object\n  properties:\n    a:\n      type: string\n"
                         b"  names: {key: {type: string}, value: {type: any}}\n  writer: {max_items: 0}\n",
                         load_common(self.root / "Platform/common/data/common.form.yaml"))
        self.assertEqual(Judge(form, "writer").judge({"a": "x"}, "object")["verdict"], "ok")
        self.assertEqual(Judge(form, "writer").judge({"a": "x", "extra": 1}, "object")["verdict"], "refused")
        self.assertEqual(Judge(form, "reader").judge({"a": "x", "extra": 1}, "object")["verdict"], "ok")

    def test_whole_holds_for_the_reader_too(self):
        self.assertEqual(self.judge("reader", gen="1.0")["paths"], ["/gen"])
        self.assertEqual(self.judge("reader", gen="-1")["paths"], ["/gen"])
        self.assertEqual(self.judge("writer", gen="9007199254740992")["paths"], ["/gen"])

    def test_object_kind_reads_json_values(self):
        form = load_form(b"dialect: data-form/1\nroot:\n  type: object\n  properties:\n    n:\n      type: integer\n"
                         b"    at:\n      ref: common.time\n", load_common(self.root / "Platform/common/data/common.form.yaml"))
        self.assertEqual(Judge(form, "reader").judge({"n": 1.0, "at": "2.5"}, "object")["verdict"], "ok")
        self.assertEqual(Judge(form, "writer").judge({"n": 1.0}, "object")["paths"], ["/n"])
        self.assertEqual(Judge(form, "writer").judge({"at": 1.2345}, "object")["paths"], ["/at"])

    def test_object_text_keeps_number_records(self):
        """Текст объекта судья разбирает с записью чисел: время читателя — грамматика записи, целое без whole — точное
        десятичное значение записи, не binary64 (OBS154-RAW-TIME-EXACT-01)."""
        form = load_form(b"dialect: data-form/1\nroot:\n  type: object\n  properties:\n    n:\n      type: integer\n"
                         b"    w:\n      ref: common.uint53\n      whole: true\n    at:\n      ref: common.time\n",
                         load_common(self.root / "Platform/common/data/common.form.yaml"))
        judge = Judge(form, "reader")
        for text, paths in (('{"at": 1.5}', []), ('{"at": 1e0}', ["/at"]), ('{"at": 1e-400}', ["/at"]),
                            ('{"at": -0}', ["/at"]), ('{"at": 1' + "0" * 400 + '}', ["/at"]),
                            ('{"n": 100.0}', []), ('{"n": 100.00000000000000001}', ["/n"]), ('{"n": 1e2}', []),
                            ('{"w": 1}', []), ('{"w": 1.0}', ["/w"]), ('{"w": 1e0}', ["/w"]),
                            ('{"w": -0}', [])):                             # -0 — целый знак (codec.tsv integer)
            with self.subTest(text=text):
                self.assertEqual(judge.judge(text, "object")["paths"], paths)
                self.assertEqual(judge.judge(text.encode("utf-8"), "object")["paths"], paths)
        self.assertEqual(judge.judge({"at": 1.0}, "object")["verdict"], "ok")       # значение без записи — по значению
        self.assertEqual(judge.judge('{"at": 1', "object")["verdict"], "refused")

    def test_json_null_is_judged_not_skipped(self):
        """JSON `null` вместо объекта — значение, его судит корень: отказ, а не «ok» (перепроверка Gemini 2026-10-27, п. 3)."""
        form = load_form(b"dialect: data-form/1\nroot:\n  type: object\n  properties:\n    n:\n      type: integer\n",
                         load_common(self.root / "Platform/common/data/common.form.yaml"))
        for mode in ("writer", "reader"):
            judge = Judge(form, mode)
            for value in ("null", b"null", None):
                with self.subTest(mode=mode, value=value):
                    self.assertEqual(judge.judge(value, "object")["verdict"], "refused")
            self.assertEqual(judge.judge('{"n": 1}', "object")["verdict"], "ok")


class SectionText(FamiliesBase):
    def test_section_is_deterministic_and_projects_the_source(self):
        fams = chapter_families(self.root, "P/03.2")
        a = build_families_section(self.norms, self.root, fams)
        b = build_families_section(self.norms, self.root, chapter_families(self.root, "P/03.2"))
        self.assertEqual(a, b)
        for piece in ("#### `<sub>/slots/<id>` — строка", "[`slot.form.yaml`](../data/slot.form.yaml)",
                      "[кодека](../../common/data/codec.tsv)", "| `gen` | целое; ≥ 0; ≤ 9007199254740991; целый знак и у "
                      "читателя (whole) | обязателен |  | поколение |", "| `seen` | время (P/01.1 Н0 «Время в строке») |",
                      "список, не длиннее 2, элемент — строка", "в `items` — текст JSON, у писателя — JCS (encoding: jcs)",
                      "| `doc.n` | целое | обязателен |", "не длиннее 4 байт UTF-8", "только у писателя: ≤ 1",
                      "| строка целиком | отказ выдачи | 1 | строка | P/03.2 Н3 |", "| `/tags` | список не читается | 2 | поле |"):
            self.assertIn(piece, a)
        self.assertTrue(a.endswith("|\n"))

    def test_names_value_keeps_the_grammar_of_the_name(self):
        """№22 ревью стадии B 3–5: у корня семьи строки отображения нет — грамматика имени и его пояснение идут в
        строку значения; простое имя-строка без пояснения строку не меняет; вложенное — пояснение имени."""
        (self.data / "slot.form.yaml").write_text("""dialect: data-form/1
root:
  type: object
  properties:
    at: {ref: common.time}
    plain:
      type: object
      names:
        key: {type: string, description: имя набора}
        value: {type: string}
  names:
    key:
      type: string
      writer: {pattern: '(room|live)\\.[a-z]+'}
      description: "`room.<sub>` и `live.<sub>`"
    value: {type: string, description: счёт}
""", encoding="utf-8")
        text = build_families_section(self.norms, self.root, chapter_families(self.root, "P/03.2"))
        self.assertIn("| `.<имя>` | имя — строка; только у писателя: целиком `(room\\|live)\\.[a-z]+`; значение — строка "
                      "| необязателен |  | имя: `room.<sub>` и `live.<sub>`; счёт |", text)
        self.assertIn("| `plain.<имя>` | строка | необязателен |  | имя: имя набора |", text)
        (self.data / "slot.form.yaml").write_text("dialect: data-form/1\nroot:\n  type: object\n  properties: {at: {ref: common.time}}\n  names:\n"
                                                  "    key: {type: string}\n    value: {type: any, description: прочее}\n",
                                                  encoding="utf-8")
        text = build_families_section(self.norms, self.root, chapter_families(self.root, "P/03.2"))
        self.assertIn("| `.<имя>` | любое значение | необязателен |  | прочее |", text)

    def test_empty_key_is_labelled(self):
        """Ключ `""` в properties подписан `""` в пути строки таблицы, во вложенных путях и в правилах (не пусто)."""
        (self.data / "slot.form.yaml").write_text("""dialect: data-form/1
root:
  type: object
  properties:
    "":
      type: object
      properties:
        missing: {type: array, items: {type: string}}
      required: [missing]
      description: полнота
    missing: {type: string}
  required: [""]
  names:
    key: {type: string, pattern: '.+'}
    value: {type: string}
""", encoding="utf-8")
        a = build_families_section(self.norms, self.root, chapter_families(self.root, "P/03.2"))
        self.assertEqual(a, build_families_section(self.norms, self.root, chapter_families(self.root, "P/03.2")))
        self.assertIn('| `""` | отображение `{missing}` | обязателен |  | полнота |', a)
        self.assertIn('| `"".missing` | список, элемент — строка | обязателен |', a)
        self.assertIn('| `"".missing[]` | строка |', a)
        self.assertIn("| `missing` | строка | необязателен |", a)
        self.assertNotIn("| `` |", a)

    def test_no_family_no_section(self):
        with self.assertRaisesRegex(SourceError, "owns no family"):
            build_families_section(self.norms, self.root, chapter_families(self.root, "P/03.1"))

    def test_load_family_with_shared_common(self):
        common = load_common(self.root / "Platform/common/data/common.form.yaml")
        row = read_catalog(self.root)[0]
        self.assertEqual(load_family(self.root, row, common).key, "<sub>/slots/<id>")


if __name__ == "__main__":
    unittest.main()
