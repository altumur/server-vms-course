"""Сверка ru↔en (ADR-0120 п. 1 (б)): пара P/01.1 сходится, а каждое расхождение — номер, ссылка, код, слово отказа,
`code`-вставка, таблица, чеклист, кириллица, пометка «производный» — даёт отказ. P/01 — в раскладке ADR-0124 (источник `X`,
перевод `ru/X`), прочие уроки — в прежней (ADR-0121): пары обеих раскладок."""
import unittest
from pathlib import Path

import en_mirror

ROOT = Path(__file__).resolve().parents[3]
RU = ROOT / "Platform/01-store/ru/spec/01.1-store.norms.md"
EN = ROOT / "Platform/01-store/spec/01.1-store.norms.md"
RU3 = ROOT / "Platform/01-store/ru/spec/01.3-store.norms.md"
EN3 = ROOT / "Platform/01-store/spec/01.3-store.norms.md"


class Mirror(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ru = RU.read_text(encoding="utf-8")
        cls.en = EN.read_text(encoding="utf-8")

    def compare(self, ru=None, en=None):
        return en_mirror.compare(self.ru if ru is None else ru, self.en if en is None else en, RU, EN, ROOT)

    def mutated(self, old, new, which="en"):
        text = self.en if which == "en" else self.ru
        self.assertEqual(text.count(old), 1, old)
        errors = self.compare(**{which: text.replace(old, new)})
        self.assertTrue(errors, f"no refusal for {old!r} → {new!r}")
        return errors

    def test_pair_agrees(self):
        self.assertEqual(self.compare(), [])
        self.assertIn((RU, EN), list(en_mirror.pairs(ROOT)))

    def test_kinds_from_n4(self):
        self.assertEqual(en_mirror.kinds_of(self.ru), {"badkey", "badrequest", "forbidden", "conflict", "expired",
                                                      "early", "guard", "toolarge", "unavailable", "refused",
                                                      "ambiguous"})

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
        self.mutated("UTF-8 is not required (Н3 «list»).", "UTF-8 is not required (Н5 «list»).")

    def test_link(self):
        self.mutated("[P/08.4](../../08-domain/spec/08.4-domain.norms.md)", "[P/08.4](../../08-domain/spec/08.3-domain.norms.md)")

    def test_code_span_dropped(self):
        self.mutated("`JSON_DEPTH` = 128", "JSON_DEPTH = 128")

    def test_table_row(self):
        self.mutated("| 40 | batch rights:", "| 39b | x | y |\n| 40 | batch rights:")

    def test_checklist(self):
        self.mutated("- [ ] **P/01.1-31** batch", "- [ ] **P/01.1-32** batch")

    def test_section(self):
        self.mutated("## Correspondence to former lessons", "### Correspondence to former lessons")

    def test_heading_number(self):
        self.mutated("### Н2.1 Request parsing", "### Н2.2 Request parsing")

    def test_cyrillic(self):
        errors = self.mutated("The read MUST be linearizable", "The read ДОЛЖЕН be linearizable")
        self.assertTrue(any("Cyrillic" in e for e in errors), errors)
        self.mutated("# A store row. The store", "# Строка хранилища. The store")

    def test_code_block_value(self):                    # ADR-0120 доп. (5) п. 7: значение без смены размеров
        self.mutated("    ceiling: 524288          # 512 KiB", "    ceiling: 524289          # 512 KiB")
        self.mutated("BATCH_WRITES: 64             # the limit", "BATCH_WRITES: 65             # the limit")

    def test_code_block_untranslated_part(self):        # вне комментария — только перевод русской прозы
        self.mutated("      - does not start with \"/\"", "      - does not start with \"\\\\\"")
        self.mutated("BATCH_WRITES: 64             # the limit", "BATCH_LIMIT: 64              # the limit")

    def test_code_block_comment_free(self):             # комментарий переводится свободно
        text = self.en.replace("# the limit of batch writes;", "# how many writes a batch carries;")
        self.assertEqual(self.compare(en=text), [])

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
        self.mutated("`JSON_DEPTH` = 128 nested", "`JSON_DEPTH` = 127 nested")

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
        self.assertIn((ROOT / "ru/НОРМАТИВНЫЕ-СЛОВА.md", ROOT / "НОРМАТИВНЫЕ-СЛОВА.md"), pairs)   # мелкий дом: корень
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
        self.assertIn("(01.1-store.norms.md#н0-словарь-слов)", ru)
        errors = self.compare3(ru=ru.replace("(01.1-store.norms.md#н0-словарь-слов)", "(01.1-store.norms.md#н1-форма)"))
        self.assertTrue(any("link targets differ" in e for e in errors), errors)
        errors = self.compare3(ru=ru.replace("(01.1-store.norms.md#н0-словарь-слов)",
                                             "(../../spec/01.1-store.norms.md#н0-vocabulary)"))
        self.assertEqual(errors, [])                       # перевод МОЖЕТ сослаться и на источник — цель та же

    def test_source_anchor(self):
        self.assertEqual(en_mirror.as_source("Platform/01-store/ru/spec/01.1-store.norms.md#время-в-строке", ROOT),
                         "Platform/01-store/spec/01.1-store.norms.md#time-in-a-row")
        self.assertEqual(en_mirror.as_source("Platform/02-installer/spec/02.1-installer.norms.md#x", ROOT),
                         "Platform/02-installer/spec/02.1-installer.norms.md#x")
        self.assertEqual(en_mirror.as_source("ru/НОРМАТИВНЫЕ-СЛОВА.md", ROOT), "НОРМАТИВНЫЕ-СЛОВА.md")
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

    def test_labels_by_dictionary(self):                # метка пары — по словарю Platform/common/placeholders.tsv
        self.assertEqual(en_mirror.as_english_labels("domain/users/<имя> ⟨вариант 2⟩", ROOT), "domain/users/<name> ⟨variant 2⟩")
        self.assertEqual(en_mirror.as_english_labels(".<имя> (имя)", ROOT), ".<name> (name)")
        self.assertEqual(en_mirror.as_english_labels("<неизвестная>", ROOT), "<неизвестная>")


if __name__ == "__main__":
    unittest.main()
