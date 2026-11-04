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
        self.assertIn((ROOT / "VMS/README.md", ROOT / "VMS/en/README.en.md"), pairs)   # прежняя раскладка: README модуля
        for ru, en in pairs:                           # каждая пара — одной из двух раскладок
            self.assertTrue(en.parent.name == "en" and en.name.endswith(".en.md") and ru.name == en.name[:-6] + ".md"
                            or "ru" in ru.relative_to(ROOT).parts and en.name == ru.name, (ru, en))
        self.assertFalse([p for p in pairs if "/01-store/" in str(p[1]) and "/en/" in str(p[1])])
        self.assertFalse([p for p in pairs if p[1].name == "01-store.md"])     # лекция — без пары, только для человека

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

    def test_built_block_by_targets(self):              # блок источника и перевода — тот же, глубина путей разная
        ru = RU3.read_text(encoding="utf-8")
        self.assertIn("](../../data/epoch_floor.schema.json)", ru)
        self.assertIn("](../data/epoch_floor.schema.json)", EN3.read_text(encoding="utf-8"))
        errors = self.compare3(ru=ru.replace("](../../data/epoch_floor.schema.json)", "](../../data/epoch_floor.outcomes.tsv)"))
        self.assertTrue(any("built blocks differ" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
