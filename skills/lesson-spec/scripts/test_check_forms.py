"""Мутации форм ADR-0125 P/01: каждая порча формы, прозы или OpenAPI даёт отказ check_forms."""
import shutil
import tempfile
import unittest
from pathlib import Path

import check_forms

ROOT = Path(__file__).resolve().parents[3]
LESSON = ROOT / "Platform/01-store"


class Forms(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.lesson = self.tmp / "Platform/01-store"
        for part in ("forms", "spec", "acceptance", "vectors"):
            shutil.copytree(LESSON / part, self.lesson / part)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def edit(self, rel, old, new):
        path = self.lesson / rel
        text = path.read_text(encoding="utf-8")
        self.assertEqual(text.count(old), 1, old)
        path.write_text(text.replace(old, new), encoding="utf-8")

    def flags(self):
        return check_forms.check_flags(self.lesson / "forms/daemon-flags.tsv")[0]

    def refusals(self):
        return check_forms.check_refusals(self.lesson / "forms/refusals.tsv")[0]

    def test_clean(self):
        self.assertEqual(self.flags(), [])
        self.assertEqual(self.refusals(), [])

    def test_flag_missing(self):
        text = (self.lesson / "forms/daemon-flags.tsv").read_text(encoding="utf-8")
        line = next(x for x in text.split("\n") if x.startswith("-tuning\t"))
        self.edit("forms/daemon-flags.tsv", line + "\n", "")
        self.assertTrue(self.flags())

    def test_flag_default(self):
        self.edit("forms/daemon-flags.tsv", "\t524288\t512KiB\t", "\t524289\t512KiB\t")
        self.assertTrue(self.flags())
        self.edit("forms/daemon-flags.tsv", "\t524289\t512KiB\t", "\t1048576\t1MiB\t")
        self.assertTrue(self.flags())                          # the prose writes 512KiB

    def test_flag_required_and_cel(self):
        self.edit("forms/daemon-flags.tsv", "-isolated\tbool\tfalse\toff\ttrue\t", "-isolated\tbool\tfalse\toff\tfalse\t")
        self.assertTrue(self.flags())
        self.edit("forms/daemon-flags.tsv", '"-join" in f\tP/01.3 Н1.3 join', '"-join" in\tP/01.3 Н1.3 join')
        self.assertTrue(self.flags())

    def test_flag_type_and_commands(self):
        self.edit("forms/daemon-flags.tsv", "-tuning\tenum:default|lan|slow\t", "-tuning\tenum:default|lan|fast\t")
        self.assertTrue(self.flags())
        self.edit("forms/daemon-flags.tsv", "\trecover\t\tP/01.3 Н3 recover", "\tdaemon\t\tP/01.3 Н3 recover")
        self.assertTrue(self.flags())

    def test_two_hyphens_only_from(self):               # --from — имя прозы; иное с двумя дефисами — отказ
        self.edit("forms/daemon-flags.tsv", "--from\tfile\t", "--input\tfile\t")
        self.assertTrue(self.flags())

    def test_stage_kit_parts(self):                     # kit и parts — только части перечня
        self.assertEqual(check_forms.check_stage_parts(self.lesson / "forms/stages.tsv")[0], [])
        self.edit("forms/stages.tsv", "\t-\tdoor,refusals\t", "\t-\tdoor,shell\t")
        self.assertTrue(check_forms.check_stage_parts(self.lesson / "forms/stages.tsv")[0])

    def test_stage_depends(self):                       # depends — только прежние этапы; launch — часть пакета
        self.edit("forms/stages.tsv", "\tlaunch\tlaunch\t1\t", "\tlaunch\tlaunch\t4\t")   # launch — этап 2 (bf64f4058)
        self.assertTrue(any("depends" in e for e in check_forms.check_stage_parts(self.lesson / "forms/stages.tsv")[0]))

    def test_stage_gate(self):                          # gate списком, tests:<глава>:<сценарии>[:seams]
        self.edit("forms/stages.tsv", "s4-parallel-cas:seams", "s9-nothing:seams")
        self.assertTrue(any("s9-nothing" in e for e in check_forms.check_stage_parts(self.lesson / "forms/stages.tsv")[0]))
        self.edit("forms/stages.tsv", "s9-nothing:seams", "s4-parallel-cas:seam")
        self.assertTrue(check_forms.check_stage_parts(self.lesson / "forms/stages.tsv")[0])

    def test_req_anchors(self):                         # ADR-0122 доп. (1) п. 1: номера требований
        self.assertEqual(check_forms.check_req_anchors(self.lesson)[0], [])
        self.edit("spec/01.1-store.norms.md", "<!-- req: P/01.1-R002 -->", "<!-- req: P/01.1-R001 -->")
        self.assertTrue(any("repeats" in e for e in check_forms.check_req_anchors(self.lesson)[0]))
        self.edit("spec/01.1-store.norms.md", "<!-- req: P/01.1-R001 -->\nA common rule", "<!-- req: P/01.2-R002 -->\nA common rule")
        self.assertTrue(any("not of this chapter" in e for e in check_forms.check_req_anchors(self.lesson)[0]))

    def test_req_tombstone(self):
        self.edit("spec/01.1-store.norms.md", "<!-- req: P/01.1-R003 -->", "<!-- removed: P/01.1-R002 by ADR-0122 -->\n<!-- req: P/01.1-R003 -->")
        self.assertTrue(any("reuses a removed" in e for e in check_forms.check_req_anchors(self.lesson)[0]))

    def test_seams(self):                               # ADR-0126 доп. (7) п. 1: закрытая грамматика швов
        path = self.lesson / "acceptance/1/seams.tsv"
        self.assertEqual(check_forms.check_seams(path)[0], [])
        self.edit("acceptance/1/seams.tsv", "@clock +600", "@clock 600s")
        self.assertTrue(check_forms.check_seams(path)[0])
        self.edit("acceptance/1/seams.tsv", "@clock 600s", "@clock +0.987654321")       # доли секунды (P/01.1 Н3, spec103)
        self.assertEqual(check_forms.check_seams(path)[0], [])
        good = path.read_text(encoding="utf-8")
        for bad in ("@clock +.25", "@clock +0.", "@clock +1e3", "@clock +01", "@clock +0.1234567891"):
            path.write_text(good.replace("@clock +0.987654321\t", bad + "\t"), encoding="utf-8")
            self.assertTrue(check_forms.check_seams(path)[0], bad)
        path.write_text(good, encoding="utf-8")
        self.edit("acceptance/1/seams.tsv", "@clock +0.987654321", "@clock +600")
        self.edit("acceptance/1/seams.tsv", "one 200 {", "200 {")
        self.assertTrue(any("after @parallel" in e for e in check_forms.check_seams(path)[0]))

    def test_refusal_code_kind(self):
        self.edit("forms/refusals.tsv", "1.1\t9\tguard_mismatch\thttp\t412\t", "1.1\t9\tguard_mismatch\thttp\t409\t")
        self.assertTrue(self.refusals())

    def test_refusal_rows_cover_prose(self):
        text = (self.lesson / "forms/refusals.tsv").read_text(encoding="utf-8")
        line = next(x for x in text.split("\n") if x.startswith("1.2\t11\t"))
        self.edit("forms/refusals.tsv", line + "\n", "")
        self.assertTrue(self.refusals())

    def test_refusal_openapi(self):
        self.edit("spec/01-store.api.openapi.yaml", "kind: {const: early}", "kind: {const: tooearly}")
        self.assertTrue(self.refusals())

    def test_refusal_fields(self):
        self.edit("forms/refusals.tsv", "\tlimit,key,size\t", "\tlimit,key,size,index\t")
        self.assertTrue(self.refusals())

    def test_write_checks_agree(self):
        self.edit("forms/refusals.tsv", "1.1\t1\tkey_rules\thttp\t400\tbadkey\t", "1.1\t1\tkey_rules\thttp\t400\tbadrequest\t")
        self.assertTrue(self.refusals())


if __name__ == "__main__":
    unittest.main()


class FormsAllLessons(unittest.TestCase):         # ADR-0125 доп. (5): грамматика форм для уроков кроме P/01
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.lesson = self.tmp / "Platform/02-installer"
        shutil.copytree(ROOT / "Platform/02-installer/acceptance", self.lesson / "acceptance")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def gate(self, check):
        return check_forms.gate_errors(self.lesson, "s", check)

    def test_case_gates(self):
        first = next(ln.split("\t")[0] for ln in (self.lesson / "acceptance/1/verdicts.tsv").read_text(encoding="utf-8").splitlines()
                     if ln and not ln.startswith("#"))
        self.assertEqual(self.gate("verdicts:2.1:*"), [])
        self.assertEqual(self.gate(f"verdicts:2.1:{first}"), [])
        self.assertTrue(self.gate("verdicts:2.1:no-such-case"))
        self.assertEqual(self.gate("puts:2.2:first,same_twice"), [])
        self.assertTrue(self.gate("puts:2.2:case"))                # строка заголовка — не случай
        self.assertTrue(self.gate("puts:2.4:*"))                   # нет таблицы главы
        self.assertTrue(self.gate("verdict:2.1:*"))                # вид вне грамматики
        self.assertTrue(self.gate("accept:2.1:*"))                 # accept — только scenarios.tsv

    def test_parts_and_commands(self):
        self.assertTrue({"families", "admin", "core", "rollout-poll"} <= check_forms.KIT_PARTS)
        self.assertTrue(check_forms.COMMAND.fullmatch("manifest-put"))
        self.assertFalse(check_forms.COMMAND.fullmatch("Put"))
