"""Сверка ru↔en (ADR-0120 п. 1 (б)): пара P/01.1 сходится, а каждое расхождение — номер, ссылка, код, слово отказа,
`code`-вставка, таблица, чеклист, кириллица, пометка «производный» — даёт отказ. P/01 — в раскладке ADR-0124 (источник `X`,
перевод `ru/X`), прочие уроки — в прежней (ADR-0121): пары обеих раскладок."""
import unittest
import tempfile
from pathlib import Path

import en_mirror

ROOT = Path(__file__).resolve().parents[3]
RU = ROOT / "Platform/01-store/ru/spec/01.1-store.norms.md"
EN = ROOT / "Platform/01-store/spec/01.1-store.norms.md"
RU3 = ROOT / "Platform/01-store/ru/spec/01.3-store.norms.md"
EN3 = ROOT / "Platform/01-store/spec/01.3-store.norms.md"


# Owned examples of the inline/code/table syntax used before C23b (ec48a8949).
# They are parser witnesses; test_pair_agrees reads the actual published pair.
OWNED_REFUSALS = ((400, "badkey"), (400, "badrequest"), (403, "forbidden"), (409, "conflict"),
                  (409, "expired"), (409, "early"), (412, "guard"), (413, "toolarge"),
                  (503, "unavailable"), (409, "refused"), (503, "ambiguous"))
OWNED_RU = '''# Фикстура синтаксиса

производный от `spec/01.1-store.norms.md`, руками не правится

## N1 Форма

`JSON_DEPTH` = 128 вложенных объектов и массивов.

```yaml
BATCH_WRITES: 64             # предел записей пакета; ровно на пределе — проходит, на один больше — badrequest
```

## N4 Отказы

| Причина | Код | `kind` и поля | Действие |
|---|---|---|---|
''' + "".join(f"| причина | {code} | `{kind}` | действие |\n" for code, kind in OWNED_REFUSALS)
OWNED_EN = '''# Syntax fixture

## N1 Form

`JSON_DEPTH` = 128 nested objects and arrays.

```yaml
BATCH_WRITES: 64             # the limit of batch writes; exactly at the limit — passes, one more — badrequest
```

## N4 Refusals

| Cause | Code | `kind` and fields | Caller |
|---|---|---|---|
''' + "".join(f"| condition | {code} | `{kind}` | action |\n" for code, kind in OWNED_REFUSALS)


class Mirror(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ru = RU.read_text(encoding="utf-8")
        cls.en = EN.read_text(encoding="utf-8")

    def compare(self, ru=None, en=None):
        return en_mirror.compare(self.ru if ru is None else ru, self.en if en is None else en, RU, EN, ROOT)

    def mutated(self, old, new, which="en", *, owned=False):
        ru, en = (OWNED_RU, OWNED_EN) if owned else (self.ru, self.en)
        if owned:
            self.assertEqual(self.compare(ru=ru, en=en), [])
        text = en if which == "en" else ru
        self.assertEqual(text.count(old), 1, old)
        self.assertNotEqual(old, new)
        changed = text.replace(old, new)
        errors = self.compare(ru=changed if which == "ru" else ru, en=changed if which == "en" else en)
        self.assertTrue(errors, f"no refusal for {old!r} → {new!r}")
        return errors

    def test_pair_agrees(self):
        self.assertEqual(self.compare(), [])
        self.assertIn((RU, EN), list(en_mirror.pairs(ROOT)))

    def test_kinds_from_n4(self):
        expected = {"badkey", "badrequest", "forbidden", "conflict", "expired", "early", "guard", "toolarge",
                    "unavailable", "refused", "ambiguous"}
        self.assertEqual(en_mirror.kinds_of(OWNED_RU), expected)
        self.mutated("`early`", "`expired`", owned=True)

    def test_code(self):
        self.mutated("then the door MUST answer `404 {kind: badrequest}`", "then the door MUST answer `405 {kind: badrequest}`")

    def test_refusal_word(self):
        errors = self.mutated("8. If not_before is given and admitted ≤ not_before, return `early`.",
                              "8. If not_before is given and admitted ≤ not_before, return `expired`.")
        self.assertTrue(any("early" in e for e in errors), errors)

    def test_reference(self):
        self.mutated("(C01-ROW-INDEX-LOST-01, the Architect's decision of 2026-10-29).\n",
                     "(the Architect's decision of 2026-10-29).\n")
        self.mutated("it names names and versions, not content (ADR-0021).", "it names names and versions, not content.")
        self.mutated("UTF-8 is not required (N3 «list»).", "UTF-8 is not required (N5 «list»).")

    def test_link(self):
        self.mutated("[P/08.4](../../08-domain/spec/08.4-domain.norms.md)", "[P/08.4](../../08-domain/spec/08.3-domain.norms.md)")

    def test_code_span_dropped(self):
        self.mutated("`JSON_DEPTH` = 128", "JSON_DEPTH = 128", owned=True)

    def test_table_row(self):
        self.mutated("| 40 | batch rights:", "| 39b | x | y |\n| 40 | batch rights:")

    def test_checklist(self):
        self.mutated("- [ ] **P/01.1-31** batch", "- [ ] **P/01.1-32** batch")

    def test_section(self):
        self.mutated("## Implementation decides", "### Implementation decides")

    def test_heading_number(self):
        self.mutated("### N2.1 Request parsing", "### N2.2 Request parsing")

    def test_cyrillic(self):
        errors = self.mutated("The read MUST be linearizable", "The read ДОЛЖЕН be linearizable")
        self.assertTrue(any("Cyrillic" in e for e in errors), errors)
        self.mutated("# A store row. The store", "# Строка хранилища. The store")

    def test_code_block_value(self):                    # ADR-0120 доп. (5) п. 7: значение без смены размеров
        # Owned historical syntax: current source uses the ROW_CEILING reference.
        block = "\n```yaml\nrow:\n    ceiling: 524288          # 512 KiB\n```\n"
        ru, en = OWNED_RU + block, OWNED_EN + block
        self.assertEqual(self.compare(ru=ru, en=en), [])
        before, after = "    ceiling: 524288          # 512 KiB", "    ceiling: 524289          # 512 KiB"
        self.assertEqual(ru.count(before), 1)
        self.assertEqual(en.count(before), 1)
        changed = en.replace(before, after, 1)
        self.assertNotEqual(changed, en)
        self.assertEqual(len(changed), len(en))
        self.assertEqual(changed.count(after), 1)
        self.assertTrue(self.compare(ru=ru, en=changed))
        self.mutated("BATCH_WRITES: 64             # the limit", "BATCH_WRITES: 65             # the limit", owned=True)

    def test_code_block_untranslated_part(self):        # вне комментария — только перевод русской прозы
        self.mutated("      - does not start with \"/\"", "      - does not start with \"\\\\\"")
        self.mutated("BATCH_WRITES: 64             # the limit", "BATCH_LIMIT: 64              # the limit", owned=True)

    def test_code_block_comment_free(self):             # комментарий переводится свободно
        self.assertEqual(self.compare(ru=OWNED_RU, en=OWNED_EN), [])
        before = "# the limit of batch writes;"
        self.assertEqual(OWNED_EN.count(before), 1)
        text = OWNED_EN.replace(before, "# how many writes a batch carries;")
        self.assertNotEqual(text, OWNED_EN)
        self.assertEqual(self.compare(ru=OWNED_RU, en=text), [])

    def test_link_inside_code_span(self):               # «](…)» в регулярке внутри кода — не ссылка
        ru = self.ru + "\nШаблон `[a-z](?:[a-z0-9]{0,61})` — имя.\n"
        en = self.en + "\nThe template `[a-z](?:[a-z0-9]{0,61})` is a name.\n"
        self.assertEqual(self.compare(ru=ru, en=en), [])

    def test_indented_code_block(self):                 # блок кода внутри пункта списка — тоже блок, комментарий переводится
        ru = self.ru + "\n1. Пункт:\n\n   ```yaml\n   limit: 8   # предел пакета\n   ```\n"
        en = self.en + "\n1. Item:\n\n   ```yaml\n   limit: 8   # the batch limit\n   ```\n"
        self.assertEqual(self.compare(ru=ru, en=en), [])
        self.assertTrue(self.compare(ru=ru, en=en.replace("limit: 8 ", "limit: 9 ")))

    def test_table_cell_value(self):
        self.mutated("| 22 | a body over 1048576 bytes", "| 22 | a body over 1048577 bytes")
        self.mutated("| 02 | a creation with", "| 03 | a creation with")

    def test_prose_number(self):
        self.mutated("`JSON_DEPTH` = 128 nested", "`JSON_DEPTH` = 127 nested", owned=True)

    def test_number_notation(self):                     # «0,5» ≡ «0.5», «250 000» ≡ «250,000» ≡ «250000»
        self.assertEqual(en_mirror.numbers("0,5 с, 250 000 записей", "ru"), ["0.5", "250000"])
        self.assertEqual(en_mirror.numbers("0.5 s, 250,000 writes, 250 000", "en"), ["0.5", "250000", "250000"])
        self.assertEqual(en_mirror.numbers("0.25 s", "en"), ["0.25"])
        self.assertNotEqual(en_mirror.numbers("0,6", "ru"), en_mirror.numbers("0.5", "en"))

    def test_escaped_pipe(self):                        # «\\|» inside a code span of a cell does not split it
        self.assertEqual(en_mirror.cells("| a | `x \\| y` | b |"), ["a", "`x \\| y`", "b"])

    def test_mark(self):                                # ADR-0124 доп. (1) п. 8 (1): источник — путём от корня урока
        errors = self.mutated(en_mirror.mark("spec/01.1-store.norms.md"), "производный", which="ru")
        self.assertTrue(any("mark" in e for e in errors), errors)
        self.mutated("производный от `spec/01.1-store.norms.md`", "производный от `spec/01.2-store.norms.md`", which="ru")


class Layouts(unittest.TestCase):
    """ADR-0124 доп. (1) п. 3, 6: пары обеих раскладок; ссылки перевода — в переводы, сверяются как ссылки в источник."""

    def compare3(self, ru=None, en=None):
        r, e = RU3.read_text(encoding="utf-8"), EN3.read_text(encoding="utf-8")
        return en_mirror.compare(r if ru is None else ru, e if en is None else en, RU3, EN3, ROOT)

    def test_pairs_of_both_layouts(self):
        pairs = list(en_mirror.pairs(ROOT))
        self.assertIn((RU3, EN3), pairs)
        self.assertIn((ROOT / "Platform/01-store/ru/lifecycle.md", ROOT / "Platform/01-store/lifecycle.md"), pairs)
        self.assertIn((ROOT / "VMS/ru/README.md", ROOT / "VMS/README.md"), pairs)   # мелкий дом: README модуля
        self.assertIn((ROOT / "Platform/common/ru/NORMATIVE-TERMS.md", ROOT / "Platform/common/NORMATIVE-TERMS.md"), pairs)   # общий канон
        self.assertFalse([p for p in pairs if p[1].parent == ROOT and p[1].name.startswith("ГРАНИЦА")])   # записки — не пары
        for ru, en in pairs:                           # каждая пара — одной из двух раскладок
            self.assertTrue(en.parent.name == "en" and en.name.endswith(".en.md") and ru.name == en.name[:-6] + ".md"
                            or "ru" in ru.relative_to(ROOT).parts and en.name == ru.name, (ru, en))
        self.assertFalse([p for p in pairs if "/01-store/" in str(p[1]) and "/en/" in str(p[1])])
        self.assertFalse([p for p in pairs if p[1].name == "01-store.md"])     # лекция — без пары, только для человека
        self.assertFalse([p for p in pairs if "harness" in p[1].parts])       # машинный текст V/11 — без пары

    def test_translation_links_translation(self):       # ru/…#русский якорь ≡ …#английский якорь по парам заголовков
        self.assertEqual(self.compare3(), [])
        ru = RU3.read_text(encoding="utf-8")
        self.assertIn("(01.1-store.norms.md#n0-словарь-слов)", ru)
        errors = self.compare3(ru=ru.replace("(01.1-store.norms.md#n0-словарь-слов)", "(01.1-store.norms.md#n1-форма)"))
        self.assertTrue(any("link targets differ" in e for e in errors), errors)
        errors = self.compare3(ru=ru.replace("(01.1-store.norms.md#n0-словарь-слов)",
                                             "(../../spec/01.1-store.norms.md#n0-vocabulary)"))
        self.assertEqual(errors, [])                       # перевод МОЖЕТ сослаться и на источник — цель та же

    def test_source_anchor(self):
        self.assertEqual(en_mirror.as_source("Platform/01-store/ru/spec/01.1-store.norms.md#время-в-строке", ROOT),
                         "Platform/01-store/spec/01.1-store.norms.md#time-in-a-row")
        self.assertEqual(en_mirror.as_source("Platform/02-installer/spec/02.1-installer.norms.md#x", ROOT),
                         "Platform/02-installer/spec/02.1-installer.norms.md#x")
        self.assertEqual(en_mirror.as_source("Platform/common/ru/NORMATIVE-TERMS.md", ROOT), "Platform/common/NORMATIVE-TERMS.md")
        self.assertEqual(en_mirror.as_source("VMS/ru/README.md", ROOT), "VMS/README.md")
        self.assertIsNone(en_mirror.home_of(ROOT / "ARCHITECTURE.md", ROOT))         # записка курса — не источник
        self.assertEqual(en_mirror.home_of(ROOT / "Platform/README.md", ROOT), (ROOT / "Platform", Path("README.md")))   # модуль с ru/
        self.assertIsNone(en_mirror.home_of(ROOT / "Platform/module-design.md", ROOT))   # записка без перевода — не источник

    def test_built_block_by_targets(self):              # блок источника и перевода — построчно, глубина путей разная
        ru = RU3.read_text(encoding="utf-8")
        self.assertIn("](../../data/epoch_floor.schema.json)", ru)
        self.assertIn("](../data/epoch_floor.schema.json)", EN3.read_text(encoding="utf-8"))
        errors = self.compare3(ru=ru.replace("](../../data/epoch_floor.schema.json)", "](../../data/epoch_floor.outcomes.tsv)"))
        self.assertTrue(any("built block «families»" in e and "links" in e for e in errors), errors)

    def test_built_block_languages(self):               # ADR-0121 доп. (3) п. 1: источник — английский блок, перевод — русский
        ru, en = RU3.read_text(encoding="utf-8"), EN3.read_text(encoding="utf-8")
        self.assertIn("| Путь отказа | Читатель | Исход |", ru)
        self.assertIn("| Path of refusal | Reader | Outcome |", en)
        self.assertEqual(self.compare3(), [])
        errors = self.compare3(ru=ru.replace("| Путь отказа | Читатель | Исход |", "| Путь отказа | Исход |", 1))
        self.assertTrue(any("built block «families»" in e and "cells" in e for e in errors), errors)
        row = next(ln for ln in ru.splitlines() if ln.startswith("| `/floor`"))
        errors = self.compare3(ru=ru.replace(row, row.replace("| 0 |", "| 7 |", 1)))
        self.assertTrue(any("built block «families»" in e and "numbers" in e for e in errors), errors)

    def test_numbered_steps(self):                     # ADR-0121 доп. (3) М (3): шагов процедуры в паре столько же
        self.assertEqual(en_mirror.steps("1. a\n2. b\n   2a. c\n```yaml\n1. not a step\n```\n"), 3)
        self.assertEqual(en_mirror.steps("```\n1. a\n2. b\n```\n"), 2)
        self.assertEqual(en_mirror.strict("1. а\n", "1. a\n2. b\n"),
                         ["numbered steps: 2, ru 1 — rebuild the translation by the source"])
        self.assertEqual(en_mirror.strict("1. а\n", "1. a\n2. b\n", count_steps=False), [])

    def test_latin_step_and_review_labels(self):        # ADR-0121 доп. (3) п. 3: в источнике — латиница, кириллица — отказ
        en, ru = EN3.read_text(encoding="utf-8"), RU3.read_text(encoding="utf-8")
        self.assertEqual(self.compare3(), [])
        tail = "\nSee step 4а and the audit Г-29.\n"
        errors = self.compare3(en=en + tail, ru=ru + "\nСм. шаг 4a и аудит G-29.\n")
        self.assertTrue(any(e.startswith("Cyrillic outside code") and "4а" in e for e in errors), errors)
        self.assertEqual(self.compare3(en=en + "\nSee step 4a and the audit G-29 (М10/2).\n",
                                       ru=ru + "\nСм. шаг 4a и аудит G-29 (М10/2).\n"), [])

    def test_english_placeholder_labels(self):         # ADR-0121 доп. (3) п. 4: метка источника — английская, перевод — по словарю
        en, ru = EN3.read_text(encoding="utf-8"), RU3.read_text(encoding="utf-8")
        errors = self.compare3(en=en + "\nThe key `domain/users/<имя>`.\n", ru=ru + "\nКлюч `domain/users/<имя>`.\n")
        self.assertTrue(any("a Russian placeholder label in the source: <имя>" in e for e in errors), errors)
        self.assertEqual(self.compare3(en=en + "\nThe key `domain/users/<name>`.\n", ru=ru + "\nКлюч `domain/users/<имя>`.\n"), [])

    def test_latin_section_numbers(self):              # ADR-0121 доп. (5) п. 1: в P/01 номера разделов — N…, Н… — отказ
        en, ru = EN3.read_text(encoding="utf-8"), RU3.read_text(encoding="utf-8")
        self.assertIn("## N0", en)
        errors = self.compare3(en=en + "\nSee Н1.3.\n", ru=ru + "\nСм. N1.3.\n")
        self.assertTrue(any("a Cyrillic section number" in e for e in errors), errors)

    def test_labels_by_dictionary(self):                # метка пары — по словарю Platform/common/ru/placeholders.tsv
        self.assertEqual(en_mirror.as_english_labels("domain/users/<имя> ⟨вариант 2⟩", ROOT), "domain/users/<name> ⟨variant 2⟩")
        self.assertEqual(en_mirror.as_english_labels(".<имя> (имя)", ROOT), ".<name> (name)")
        self.assertEqual(en_mirror.as_english_labels("<неизвестная>", ROOT), "<неизвестная>")


class VmsEnglishSlice(unittest.TestCase):
    """Accepted English slice only; V11 and the old historical map stay explicit."""

    def accepted_pairs(self):
        return [(ru, en) for ru, en in en_mirror.pairs(ROOT)
                if en.relative_to(ROOT).as_posix().startswith("VMS/")
                and not en.relative_to(ROOT).as_posix().startswith("VMS/11-backend/")]

    def test_actual_108_pairs_are_strict_and_clean(self):
        pairs = self.accepted_pairs()
        self.assertEqual(len(pairs), 108)
        for ru, en in pairs:
            with self.subTest(path=en.relative_to(ROOT)):
                name = en.relative_to(ROOT).as_posix()
                self.assertNotIn(name, en_mirror.STEPS_PENDING)
                self.assertFalse(name.startswith(tuple(en_mirror.LABELS_PENDING)))
                self.assertTrue(name.startswith(en_mirror.NUMBERS_DONE))
                self.assertEqual(en_mirror.compare(ru.read_text(), en.read_text(), ru, en, ROOT), [])

    def test_removed_six_step_deferrals_really_refuse_a_changed_step_count(self):
        names = ("02-rec/spec/02.4-rec.norms.md", "05-detjob/spec/05.3-detjob.norms.md",
                 "05-detjob/spec/05.4-detjob.norms.md", "06-detedge/spec/06.2-detedge.norms.md",
                 "07-auto/spec/07.3-auto.norms.md", "12-psim/spec/12.3-psim.norms.md")
        for name in names:
            en = ROOT / "VMS" / name
            ru = en.parents[1] / "ru" / "spec" / en.name
            with self.subTest(path=name):
                before = en_mirror.compare(ru.read_text(), en.read_text(), ru, en, ROOT)
                self.assertEqual(before, [])
                changed = en.read_text() + "\n1. Extra procedure step.\n"
                errors = en_mirror.compare(ru.read_text(), changed, ru, en, ROOT)
                self.assertTrue(any("numbered steps" in e for e in errors), errors)

    def test_latin_labels_and_section_numbers_apply_to_the_actual_slice(self):
        ru, en = self.accepted_pairs()[0]
        r, e = ru.read_text(), en.read_text()
        self.assertEqual(en_mirror.compare(r, e, ru, en, ROOT), [])
        errors = en_mirror.compare(r + "\nSee 4a, G-29.\n", e + "\nSee 4а, Г-29.\n", ru, en, ROOT)
        self.assertTrue(any("Cyrillic outside code" in x for x in errors), errors)
        errors = en_mirror.compare(r + "\n## N99 Extra\n", e + "\n## Н99 Extra\n", ru, en, ROOT)
        self.assertTrue(any("Cyrillic section number" in x for x in errors), errors)

    def test_v11_flags_remain_excluded_not_passed(self):
        name = "VMS/11-backend/spec/11.2-backend.norms.md"
        self.assertIn(name, en_mirror.STEPS_PENDING)
        self.assertTrue(name.startswith(tuple(en_mirror.LABELS_PENDING)))
        self.assertFalse(name.startswith(en_mirror.NUMBERS_DONE))
        self.assertFalse(name.startswith(en_mirror.FULL_ENGLISH_DONE))
        self.assertNotIn("VMS/", en_mirror.NUMBERS_DONE)
        self.assertNotIn("VMS/", en_mirror.FULL_ENGLISH_DONE)


class FullEnglishSource(unittest.TestCase):

    def test_vms_actual_completed_slice_is_clean(self):
        self.assertEqual(en_mirror.full_english_errors(ROOT, en_mirror.VMS_ENGLISH_DONE), [])

    def test_vms_new_hidden_sources_and_yaml_ui_are_checked_without_a_new_locale_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("VMS/01-cam/.new/norms.md", "VMS/common/localization.tsv",
                         "VMS/12-psim/data/schema.json", "VMS/02-rec/rec.subsystem.yaml"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("label: Ж\n")
                self.assertIn(path, [p for p, _ in en_mirror.full_english_errors(root)])
                path.unlink()
            for name in ("VMS/01-cam/ru/README.md", "VMS/11-backend/spec/norms.md"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("Ж\n")
            self.assertEqual(en_mirror.full_english_errors(root), [])

    def test_deferred_vms_map_requires_exact_bytes_and_a_regular_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "VMS/common/id-map.tsv"
            path.parent.mkdir(parents=True)
            data = (ROOT / "VMS/common/id-map.tsv").read_bytes()
            path.write_bytes(data)
            self.assertEqual(en_mirror.full_english_errors(root), [])
            path.write_bytes(data + b"\n")
            self.assertTrue(any("deferred historical bytes differ" in e for _, e in en_mirror.full_english_errors(root)))
            path.unlink()
            outside = root / "outside.tsv"
            outside.write_bytes(data)
            path.symlink_to(outside)
            self.assertTrue(any("without symlinks" in e for _, e in en_mirror.full_english_errors(root)))
    def test_moved_documents_use_only_platform_homes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            expected = []
            for home, name in (("common", "NORMATIVE-TERMS.md"), ("07-console-module", "CONSOLE-MODULE.md")):
                en = root / "Platform" / home / name
                ru = en.parent / "ru" / name
                ru.parent.mkdir(parents=True)
                en.write_text("# Contract\n")
                ru.write_text(f"# Контракт\n\nпроизводный от `{name}`, руками не правится\n")
                expected.append((ru, en))
                relative = ru.relative_to(root).as_posix()
                self.assertEqual(en_mirror.as_source(relative, root), en.relative_to(root).as_posix())
                self.assertEqual(en_mirror.compare(ru.read_text(), en.read_text(), ru, en, root), [])
                en.write_text("# Contract\n\nЖ\n")
            self.assertEqual(set(en_mirror.pairs(root)), set(expected))
            self.assertEqual({p for p, _ in en_mirror.full_english_errors(root)}, {en for _, en in expected})
            self.assertNotIn("NORMATIVE-TERMS.md", en_mirror.FULL_ENGLISH_DONE)
            self.assertNotIn("CONSOLE-MODULE.md", en_mirror.FULL_ENGLISH_DONE)

    def test_quotes_code_and_machine_values_are_not_exempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, text in {"README.md": "`word` «слово»", "data/x.tsv": "key\tзначение",
                               "data/x.json": '{"default":"единица"}', "forms/x.yaml": 'word: "отказ"'}.items():
                p = root / "Platform/demo" / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text)
            errors = en_mirror.full_english_errors(root, ["Platform/demo/"])
            self.assertEqual(len(errors), 4, errors)

    def test_vector_journal_is_source_and_human_journal_is_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ["ru/README.md", "journal/corrections.tsv", "vectors/journal/cases.tsv"]:
                p = root / "Platform/common" / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("русский")
            errors = en_mirror.full_english_errors(root, ["Platform/common/"])
            self.assertEqual([p.relative_to(root).as_posix() for p, _ in errors],
                             ["Platform/common/vectors/journal/cases.tsv"])

    def test_only_localization_ru_column_is_exempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = root / en_mirror.LOCALIZATION
            p.parent.mkdir(parents=True)
            p.write_text("key\ten\tru\nrefresh\tRefresh\tОбновить\n")
            self.assertEqual(en_mirror.full_english_errors(root, [p.relative_to(root)]), [])
            old = root / "Platform/06-console/data/localization.tsv"
            old.parent.mkdir(parents=True)
            old.write_bytes(p.read_bytes())
            self.assertEqual([path for path, _ in en_mirror.full_english_errors(root, [old.relative_to(root)])], [old])
            old.unlink()
            p.write_text("key\ten\tru\nrefresh\tОбновить\tОбновить\n")
            self.assertTrue(en_mirror.full_english_errors(root, [p.relative_to(root)]))
            p.write_text("key\ten\tru\nrefresh\tRefresh\tОбновить\textra\n")
            self.assertTrue(en_mirror.full_english_errors(root, [p.relative_to(root)]))

    def test_unicode_escapes_preserve_payload_but_extended_cyrillic_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = root / "Platform/common/x.json"
            p.parent.mkdir(parents=True)
            p.write_text(r'{"input":"\u044f"}')
            self.assertEqual(en_mirror.full_english_errors(root, ["Platform/common/"]), [])
            p.write_text('{"input":"Ӕ"}')
            self.assertTrue(en_mirror.full_english_errors(root, ["Platform/common/"]))


if __name__ == "__main__":
    unittest.main()
