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
        self.table, self.probes = self.dir / TABLE.name, self.dir / PROBES.name
        shutil.copy(TABLE, self.table)
        shutil.copy(PROBES, self.probes)

    def tearDown(self):
        shutil.rmtree(self.dir)

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


# ADR-0133 доп. (86) п. 1 (OBSH.48): вход local_admin формы проверок и столбец refusal — необязательные.
SMALL_HEAD = (
    "#var body dyn — the body\n"
    "#var sock string — the effective role\n"
    "{local}"
    "#var lone list<string> — lone surrogates\n"
    "#var lim map<string,int> — the parameters\n")
SMALL_ROWS = (
    "1\twc-body_object\t*\t\t\tbody_object\ttype(body) != map\t400\tbadrequest\t\tN2.1{r1}\n"
    "2\twc-floor_socket\t*\t\t\tfloor_socket\t{when}\t403\tforbidden\t\tN4{r2}\n")
LOCAL = "#var local_admin bool — the request came through the physical local admin.sock, not forwarded\n"
REFUSALS = ("# catalogue\n"
            "chapter\trow\tname\tsurface\tcode\tkind\tfields\theaders\tlog\tnorm\n"
            "1.1\t1\tbody_form\thttp\t400\tbadrequest\t-\t-\t-\tN4\n"
            "1.3\t1\tadmin_only\thttp\t403\tforbidden\t-\t-\t-\tN4\n")


class OptionalInputs(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.table, self.probes = self.dir / "write-checks.tsv", self.dir / "write-checks.probes.tsv"

    def write(self, *, local=True, probe_local=True, refusal=None, refusals=None, when=None):
        head = SMALL_HEAD.format(local=LOCAL if local else "")
        columns = list(check_tables.COLUMNS)
        r1 = r2 = ""
        if refusal is not None:
            columns.append("refusal")
            r1, r2 = (f"\t{v}" for v in refusal)
        when = when or ("!local_admin" if local else "sock != \"admin\"")
        self.table.write_text(head + "\t".join(columns) + "\n" + SMALL_ROWS.format(r1=r1, r2=r2, when=when),
                              encoding="utf-8")
        if probe_local:
            rows = ["n\tcase\tsock\tlocal_admin\tbody",
                    "1\tonly\twriter\ttrue\t[]", "1\tpair\twriter\tfalse\t[]",
                    "2\tonly\tadmin\tfalse\t{}", "2\tnopair\tadmin\t-\tthe last row",
                    "0\tpass\tadmin\ttrue\t{}"]
        else:
            rows = ["n\tcase\tsock\tbody",
                    "1\tonly\tadmin\t[]", "1\tpair\twriter\t[]",
                    "2\tonly\twriter\t{}", "2\tnopair\twriter\tthe last row",
                    "0\tpass\tadmin\t{}"]
        self.probes.write_text("# probes\n" + "\n".join(rows) + "\n", encoding="utf-8")
        if refusals is not None:
            (self.dir / "refusals.tsv").write_text(refusals, encoding="utf-8")

    def errors(self):
        return check_tables.check(self.table)[0]

    @staticmethod
    def validated(path):
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line and not line.startswith("#")]
        return {"path": path, "columns": lines[0].split("\t"), "rows": [line.split("\t") for line in lines[1:]]}

    def refused(self, needle):
        errors = self.errors()
        self.assertTrue(any(needle in e for e in errors), errors)

    def test_local_admin_input_agrees(self):
        self.write()
        errors, stats = check_tables.check(self.table)
        self.assertEqual(errors, [])
        self.assertEqual(stats, {"check_rows": 2, "check_probes": 5})

    def test_local_admin_input_agrees_validated(self):
        self.write(refusal=("body_form", "admin_only"), refusals=REFUSALS)
        self.assertEqual(check_tables.check(self.table, validated=self.validated(self.table),
                                            validated_probes=self.validated(self.probes)),
                         check_tables.check(self.table))
        self.assertEqual(check_tables.check(self.table)[0], [])

    def test_local_admin_value_is_used(self):           # the value of the column reaches CEL: a wrong probe is caught
        self.write()
        self.probes.write_text(self.probes.read_text(encoding="utf-8").replace(
            "2\tonly\tadmin\tfalse\t{}", "2\tonly\tadmin\ttrue\t{}"), encoding="utf-8")
        self.refused("the first violated row is None, not 2")

    def test_local_admin_not_bool(self):
        self.write()
        self.probes.write_text(self.probes.read_text(encoding="utf-8").replace(
            "1\tonly\twriter\ttrue\t[]", "1\tonly\twriter\tyes\t[]"), encoding="utf-8")
        self.refused("local_admin 'yes' — true or false")

    def test_local_admin_declared_without_probe_column(self):
        self.write(probe_local=False)
        self.refused("no column local_admin")

    def test_local_admin_column_without_declaration(self):
        self.write(local=False)
        self.refused("does not declare #var local_admin")

    def test_local_admin_undeclared_in_when(self):      # without #var the name is not a CEL variable
        self.write(local=False, probe_local=False, when="!local_admin")
        self.refused("does not compile")

    def test_local_admin_wrong_type(self):
        self.write()
        self.table.write_text(self.table.read_text(encoding="utf-8").replace(
            "#var local_admin bool", "#var local_admin string"), encoding="utf-8")
        self.refused("#var local_admin string — bool")

    def test_without_new_inputs_as_before(self):
        self.write(local=False, probe_local=False)
        self.assertEqual(check_tables.check(self.table), ([], {"check_rows": 2, "check_probes": 5}))

    def test_refusal_column_names_catalogue_rows(self):
        for cells in (("body_form", "admin_only"), ("body_form", ""), ("-", "admin_only")):
            with self.subTest(cells=cells):
                self.write(refusal=cells, refusals=REFUSALS)
                self.assertEqual(self.errors(), [])

    def test_refusal_column_unknown_name(self):
        self.write(refusal=("body_form", "floor_socket"), refusals=REFUSALS)
        self.refused("n 2: refusal 'floor_socket' is not a name of refusals.tsv")

    def test_refusal_column_without_catalogue(self):
        self.write(refusal=("body_form", "admin_only"))
        self.refused("no refusals.tsv")

    def test_refusal_column_twice_or_misplaced(self):
        self.write(refusal=("body_form", "admin_only"), refusals=REFUSALS)
        text = self.table.read_text(encoding="utf-8").replace("\tnorm\trefusal\n", "\tnorm\trefusal\trefusal\n")
        self.table.write_text(text, encoding="utf-8")
        self.refused("columns must be")


if __name__ == "__main__":
    unittest.main()
