"""Таблица проверок P/01.1 (ADR-0120 п. 2 (а)) и её пробы сходятся, а мутации таблицы или проб дают отказ."""
import shutil
import tempfile
import unittest
from pathlib import Path

import check_tables

ROOT = Path(__file__).resolve().parents[3]
TABLE = ROOT / "Platform/01-store/forms/write-checks.tsv"          # раскладка ADR-0124: формы — в forms/
PROBES = TABLE.with_name("write-checks.probes.tsv")


class Checks(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.table, self.probes = self.dir / TABLE.name, self.dir / PROBES.name
        shutil.copy(TABLE, self.table)
        shutil.copy(PROBES, self.probes)

    def edit(self, path, old, new):
        text = path.read_text(encoding="utf-8")
        self.assertEqual(text.count(old), 1, old)
        path.write_text(text.replace(old, new), encoding="utf-8")

    def errors(self):
        return check_tables.check(self.table)[0]

    def refused(self, needle):
        errors = self.errors()
        self.assertTrue(any(needle in e for e in errors), errors)

    def test_agrees(self):
        errors, stats = check_tables.check(TABLE)
        self.assertEqual(errors, [])
        self.assertEqual(stats["check_rows"], 34)

    def test_order_swapped(self):                     # cas раньше items: пробы порядка ловят
        text = self.table.read_text(encoding="utf-8").splitlines()
        i6 = next(k for k, l in enumerate(text) if l.startswith("6\t"))
        a, b = text[i6].split("\t"), text[i6 + 1].split("\t")
        a[0], b[0] = "7", "6"
        text[i6], text[i6 + 1] = "\t".join(b), "\t".join(a)
        self.table.write_text("\n".join(text) + "\n", encoding="utf-8")
        self.refused("the first violated row is")

    def test_row_id(self):                              # ADR-0122 доп. (1) п. 4: адрес строки — постоянный, свой
        self.edit(self.table, "\twc-op\t", "\twc-body_object\t")
        self.refused("id wc-body_object repeats")

    def test_condition_weakened(self):
        self.edit(self.table, "sock != \"admin\"", "sock == \"nobody\"")
        self.refused("n 3, only")

    def test_undeclared_function(self):
        self.edit(self.table, "!key_ok(body.key)\t400", "!key_good(body.key)\t400")
        self.refused("key_good(), not declared by #fn")

    def test_number_in_when(self):
        self.edit(self.table, "weight(body.items) > lim.ROW_CEILING\t", "weight(body.items) > 524288\t")
        self.refused("number literal")

    def test_undeclared_lim(self):
        self.edit(self.table, "weight(body.items) > lim.ROW_CEILING\t", "weight(body.items) > lim.CEILING\t")
        self.refused("lim.CEILING, not declared")

    def test_probe_missing(self):
        self.edit(self.probes, '13\tonly\twriter\t{"op": "put", "key": "acc/a", "items": {"f": "vvvvvvvvv"}}\n', "")
        self.refused("n 13: no probe «only»")

    def test_pair_missing(self):
        self.edit(self.probes, '15\tnopair\twriter\tthe last row of the commands put and delete\n', "")
        self.refused("n 15: no probe «pair»")

    def test_probe_wrong(self):
        self.edit(self.probes, '14\tonly\twriter\t{"op": "delete", "key": "zzz/a"}', '14\tonly\twriter\t{"op": "delete", "key": "acc/a"}')
        self.refused("n 14, only")

    def test_pass_violates(self):
        self.edit(self.probes, '0\tpass\tadmin\t{"op": "floor", "value": 3}', '0\tpass\twriter\t{"op": "floor", "value": 3}')
        self.refused("passing input violates")

    def test_lone_surrogate(self):
        body, lone = check_tables.decode('{"key": "a\\ud800", "items": {"\\udc00": "v"}}')
        self.assertEqual(lone, ["/items", "/key"])
        self.assertEqual(body["key"], "a�")


if __name__ == "__main__":
    unittest.main()
