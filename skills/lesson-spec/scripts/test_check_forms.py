"""Мутации форм ADR-0125 P/01: каждая порча формы, прозы или OpenAPI даёт отказ check_forms."""
import re
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
        for ok in ("-dir", "--sha256", "$INSTANCE_ID", "<subsystem>"):
            self.assertTrue(check_forms.FLAG_NAME.fullmatch(ok), ok)
        for bad in ("$instance", "<Sub>", "dir", "---x", "$1X"):
            self.assertFalse(check_forms.FLAG_NAME.fullmatch(bad), bad)

    def test_process_seams(self):                     # швы не по HTTP: RUN, CALL, @file, @read (грамматика stagetests)
        path = self.lesson / "acceptance/1/seams.tsv"
        good = ["# P/02 seams (test)", "# scenario\tstep\trequest\texpect",
                's1-put\t1\t@file $data/in.yaml inputs/cam.yaml\tok',
                's1-put\t2\t@file $run/note "a b"\tok',
                's1-put\t3\tRUN w2cctl manifest put inputs/cam.yaml\texit 0',
                's1-put\t4\tRUN w2cctl manifest put "x y" $id\texit 2; stderr ~"unit.fields"',
                's1-put\t5\tRUN w2cctl show\texit 0; stdout {"n": 1}; stdout-text "ok\\n"; stderr ~"w"',
                's1-put\t6\tCALL parse-manifest {"text":"a: 1"}\t{"verdict":"refused"}',
                's1-put\t7\tCALL parse-manifest {}\t@exit 2',
                's1-put\t8\t@read $data/FORMAT\t{"format":"configstore"}',
                's1-put\t9\t@read $manifest/testsub\t@absent',
                's1-put\t10\t@read $run/log\ttext "done"']
        path.write_text("\n".join(good) + "\n", encoding="utf-8")
        self.assertEqual(check_forms.check_seams(path)[0], [])
        bad = [('RUN w2cctl  put', 'exit 0'), ('RUN w2cctl "unterminated', 'exit 0'), ('RUN w2cctl put', 'exit x'),
               ('RUN w2cctl put', 'exit 0; stderr ~"a"; stdout {}'), ('RUN w2cctl put', 'exit 0; stdout-text plain'),
               ('CALL Parse {}', '{}'), ('CALL parse {not json}', '{}'), ('CALL parse {}', 'refused'),
               ('@file /etc/x inputs/a', 'ok'), ('@file $data/x a.yaml', 'ok'), ('@file $data/x inputs/a', '200'),
               ('@read data/FORMAT', '{}'), ('@read $data/FORMAT', 'text plain')]
        for request, expect in bad:
            path.write_text("\n".join(good[:2] + [f"s1-put\t1\t{request}\t{expect}"]) + "\n", encoding="utf-8")
            self.assertTrue(check_forms.check_seams(path)[0], (request, expect))

    def test_parallel_process_and_operator_commands(self):
        path = self.lesson / "acceptance/1/seams.tsv"
        path.write_text("# t\n# scenario\tstep\trequest\texpect\n"
                        's2\t1\t@parallel 2\tok\n'
                        's2\t2\tCALL parse-manifest {}\teach {"verdict":"ok"}\n'
                        's2\t3\t@parallel 2\tok\n'
                        's2\t4\tRUN w2cctl show\tone exit 0; stdout {"a":1}; rest exit 2; stderr ~"busy"\n', encoding="utf-8")
        self.assertEqual(check_forms.check_seams(path)[0], [])
        forms = self.lesson / "forms"
        forms.mkdir()
        head = "command\tprocess\tprefix\tpositionals\tnorm\n"
        good = 'manifest-put\tw2cctl\t["manifest","put"]\t{"type":"array","items":{"type":"string"},"minItems":1,"maxItems":1}\tP/02.3 Н3\n'
        (forms / "operator-commands.tsv").write_text(head + good, encoding="utf-8")
        self.assertEqual(check_forms.check_operator_commands(forms / "operator-commands.tsv")[0], [])
        for bad in (good + good,                                                     # повтор
                    good.replace('["manifest","put"]', '"manifest put"'),            # prefix не массив
                    good.replace('"minItems":1,"maxItems":1', '"minItems":2,"maxItems":1'),
                    good.replace('{"type":"string"}', '{"type":"integer"}'),
                    good.replace("P/02.3 Н3", " ")):
            (forms / "operator-commands.tsv").write_text(head + bad, encoding="utf-8")
            self.assertTrue(check_forms.check_operator_commands(forms / "operator-commands.tsv")[0], bad)

    def test_single_chapter_lesson(self):              # урок одной главой (P/04): глава 4, acceptance/ без K, P/04-RNNN
        one = self.tmp / "Platform/04-controller"
        (one / "acceptance").mkdir(parents=True)
        (one / "spec").mkdir()
        (one / "acceptance/scenarios.tsv").write_text("# s\n# scenario\tstep\trequest\texpect\n01-a\t1\tGET /x\t200 {}\n", encoding="utf-8")
        (one / "acceptance/seams.tsv").write_text("# s\n# scenario\tstep\trequest\texpect\ns1\t1\t@reopen\tok\n", encoding="utf-8")
        self.assertEqual(check_forms.gate_errors(one, "s", "accept:4:01-a"), [])
        self.assertEqual(check_forms.gate_errors(one, "s", "tests:4:*:seams"), [])
        self.assertTrue(check_forms.gate_errors(one, "s", "accept:4:02-b"))
        (one / "spec/04-controller.norms.md").write_text("<!-- req: P/04-R001 -->\nx\n<!-- req: P/04.1-R002 -->\n", encoding="utf-8")
        errs = check_forms.check_req_anchors(one)[0]
        self.assertEqual(len(errs), 1, errs)                   # P/04.1-R002 не этого файла; P/04-R001 — годен
        self.assertTrue({"slot-capture", "slot-fate", "slot-release"} <= check_forms.KIT_PARTS)

    def test_http_without_kind(self):                  # P/05: тело http без kind — по названной схеме OpenAPI
        lesson = self.tmp / "Platform/05-resource"
        (lesson / "spec").mkdir(parents=True)
        (lesson / "forms").mkdir()
        (lesson / "spec/05-resource.api.openapi.yaml").write_text(
            "openapi: 3.1.0\ncomponents:\n  schemas:\n    ResourceDenied:\n      type: object\n      required: [detail, error]\n"
            "      properties: {detail: {type: string}, error: {const: refused}, role: {type: string}}\n", encoding="utf-8")
        (lesson / "spec/05.1-resource.norms.md").write_text("## Н4 Refusals\n\nThe catalogue is forms/refusals.tsv.\n", encoding="utf-8")
        head = "\t".join(check_forms.REF_COLUMNS + ["word", "response_schema", "cause", "outcome", "diagnostic", "caller"])
        def row(fields, schema):
            return "\t".join(["5.1", "1", "resource_role", "http", "403", "-", fields, "-", "-", "P/05.1 Н4",
                              "refused", schema, "c", "403 refused", "d", "client"])
        path = lesson / "forms/refusals.tsv"
        for fields, schema, ok in (("detail,error,role?", "ResourceDenied", True), ("detail,error", "ResourceDenied", True),
                                   ("detail", "ResourceDenied", False), ("detail,error,x", "ResourceDenied", False),
                                   ("detail,error", "NoSuch", False), ("-", "-", True), ("error", "-", False)):
            path.write_text(head + "\n" + row(fields, schema) + "\n", encoding="utf-8")
            errs = check_forms.check_refusals(path)[0]
            self.assertEqual(not errs, ok, (fields, schema, errs))

        dr = lesson / "forms/door-roles.tsv"
        (lesson / "spec/05-resource.api.openapi.yaml").write_text(
            "openapi: 3.1.0\npaths:\n  /v1/units:\n    get: {}\n    post: {}\ncomponents: {schemas: {}}\n", encoding="utf-8")
        for body, ok in (("GET\t/v1/units\tconsole,<sub>worker\tP/05.1 Н2", True), ("GET\t/v1/units\t*\tP/05.1 Н2", True),
                         ("PUT\t/v1/units\tconsole\tP/05.1 Н2", False), ("GET\t/v1/nope\tconsole\tx", False),
                         ("GET\t/v1/units\tConsole\tx", False), ("GET\t/v1/units\tconsole\t ", False)):
            dr.write_text("method\tpath\troles\tnorm\n" + body + "\n", encoding="utf-8")
            self.assertEqual(not check_forms.check_door_roles(dr)[0], ok, body)


class Wire(unittest.TestCase):                     # провод векторов wire.tsv (wire.md): настоящая форма и мутации
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())          # Platform ссылками, копия — только wire.tsv
        vectors = self.tmp / "Platform/common/vectors"
        vectors.mkdir(parents=True)
        for real, place in ((ROOT / "Platform", self.tmp / "Platform"), (ROOT / "Platform/common", self.tmp / "Platform/common"),
                            (ROOT / "Platform/common/vectors", vectors)):
            for entry in real.iterdir():
                if not (place / entry.name).exists() and entry.name != "wire.tsv":
                    (place / entry.name).symlink_to(entry)
        shutil.copyfile(ROOT / "Platform/common/vectors/wire.tsv", vectors / "wire.tsv")
        (self.tmp / "Source").symlink_to(ROOT / "Source")   # фикстуры canonical от корня выгрузки
        self.path = vectors / "wire.tsv"
        self.good = self.path.read_text(encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def errors(self):
        """Ошибки сверх ошибок настоящей формы (номер строки снят: мутация может сдвинуть строки)."""
        if not hasattr(self, "base"):
            self.base = {self.norm(e) for e in check_forms.check_wire(self.path)[0]} if self.path.read_text(
                encoding="utf-8") == self.good else set()
        return [e for e in check_forms.check_wire(self.path)[0] if self.norm(e) not in self.base]

    @staticmethod
    def norm(message):
        return re.sub(r"^wire\.tsv: row [0-9]+ ", "wire.tsv: ", message)

    def row(self, package, table, surface):
        return next(x for x in self.good.split("\n") if x.startswith(f"{package}\t{table}\t{surface}\t"))

    def mutate(self, old, new, row=None):
        if not hasattr(self, "base"):
            self.errors()
        base = row or self.good
        self.assertEqual(base.count(old), 1, old)
        text = self.good.replace(row, row.replace(old, new)) if row else self.good.replace(old, new)
        self.path.write_text(text, encoding="utf-8")
        return self.errors()

    def test_real_form_clean(self):                  # настоящая форма — без ошибок; красный здесь — дефект данных формы
        errors, stats = check_forms.check_wire(ROOT / "Platform/common/vectors/wire.tsv")
        self.assertEqual(errors, [])
        self.assertGreaterEqual(stats["wire_bindings"], 27)        # форма растёт по урокам (P/05 +2)

    def test_lf_only_lines(self):                   # U+2028 в ячейке — байт ячейки, не конец строки (JCS P/01)
        jcs = self.tmp / "Platform/01-store/vectors/jcs/canonical_json.tsv"
        self.assertIn(" ", jcs.read_text(encoding="utf-8"))
        table = self.tmp / "t.tsv"
        table.write_text("a\tb\nx y\tz w\x85\n", encoding="utf-8")
        self.assertEqual(check_forms.lf_lines(table), ["a\tb", "x y\tz w\x85"])
        errors, rows = check_forms.vector_rows(table, ["a", "b"], False)
        self.assertEqual((errors, len(rows)), ([], 1))

    def test_columns(self):
        row = self.row("common/crl", "cases.tsv", "vectors")
        self.assertTrue(self.mutate(row, row + "\textra"))                       # лишняя колонка
        self.assertTrue(self.mutate(row, row.rsplit("\t", 1)[0]))                # пропущенная колонка
        self.assertTrue(self.mutate("package\ttable\tsurface\theader", "package\tsurface\ttable\theader"))

    def test_triple_repeats(self):
        row = self.row("common/crl", "cases.tsv", "vectors")
        self.assertTrue(any("repeats" in e for e in self.mutate(row, row + "\n" + row)))

    def test_surface(self):
        row = self.row("common/crl", "cases.tsv", "vectors")
        self.assertTrue(self.mutate("\tvectors\t", "\tfunction\t", row))

    def test_compare(self):
        row = self.row("common/crl", "cases.tsv", "vectors")
        self.assertTrue(self.mutate("\tvalue\t", "\tequal\t", row))
        self.assertTrue(self.mutate("\tvalue\t", "\t-\t", row))                  # «-» — только layout
        self.assertTrue(self.mutate("\tvalue\t", '\t"value"\t', row))            # кавычки — не CSV

    def test_column_not_in_header(self):
        row = self.row("common/crl", "cases.tsv", "vectors")
        self.assertTrue(self.mutate('{"column":"expect","decode":"cell"}', '{"column":"wanted","decode":"cell"}', row))
        self.assertTrue(self.mutate('"cells":{"input":{"column":"input"}}', '"cells":{"input":{"column":"inp"}}', row))

    def test_value_constructor(self):
        row = self.row("common/crl", "cases.tsv", "vectors")
        self.assertTrue(self.mutate('{"column":"expect","decode":"cell"}', '{"cell":"expect","decode":"cell"}', row))
        self.assertTrue(self.mutate('{"column":"expect","decode":"cell"}', '{"column":"expect","decode":"yaml"}', row))
        self.assertTrue(self.mutate('{"column":"expect","decode":"cell"}', '{"omit":true}', row))

    def test_when_compiles(self):
        row = self.row("common/crl", "cases.tsv", "vectors")
        self.assertTrue(self.mutate('"variant":"","when":"true","cells"', '"variant":"","when":"row[","cells"', row))
        self.assertTrue(self.mutate('"variant":"","when":"true","cells"', '"variant":"","when":"row","cells"', row))
        self.assertTrue(self.mutate('"variant":"","when":"true","cells"', '"variant":"","when":"x == 1","cells"', row))

    def test_two_expectations(self):
        row = self.row("common/crl", "cases.tsv", "vectors")
        exp = '{"variant":"","when":"true","code":0,"value":{"column":"expect","decode":"cell"}}'
        self.assertTrue(any("2 expectations" in e for e in self.mutate(exp, exp + "," + exp, row)))
        ring = self.row("common/sealing", "ring.tsv", "vectors")             # пересекающиеся when одного variant
        self.assertTrue(any("select one row" in e for e in self.mutate(
            '"when":"row[\\"case\\"].startsWith(\\"rotate\\") && owner', '"when":"owner', ring)))

    def test_fixture_missing(self):
        row = self.row("common/log-mask", "cases.tsv", "vectors")
        self.assertTrue(self.mutate("../secret-in/fields.yaml", "../secret-in/nope.yaml", row))
        self.assertTrue(self.mutate("../secret-in/fields.yaml", "../../../../../etc/hosts", row))
        yaml_row = self.row("common/yaml-suite", "expect.tsv", "vectors")
        self.assertTrue(self.mutate("inputs/{id}.yaml", "inputs/{id}.yml", yaml_row))

    def test_layout_inputs(self):
        row = self.row("common/journal", "modes.tsv", "layout")
        self.assertTrue(self.mutate("\t[]\t{}\t", '\t[{"variant":"","cells":{"path":{"column":"path"}}}]\t{}\t', row))

    def test_header_against_table(self):
        row = self.row("common/crl", "cases.tsv", "vectors")
        self.assertTrue(self.mutate("\tcase,input,expect,note\t", "\tcase,input,note,expect\t", row))
        lm = self.row("common/log-mask", "cases.tsv", "vectors")
        self.assertTrue(self.mutate("\t-,raw,masked,note\t", "\t-,raw,masked\t", lm))

    def test_group_constant(self):               # группа без своего столбца в case — case не постоянен
        row = self.row("02-installer/platform-lists", "cases.tsv", "vectors")
        self.assertTrue(self.mutate('"case":"list"', '"case":"word"', row))

    def test_foreign_owner(self):                    # общий пакет — только потребители consumers.tsv
        crl = self.row("common/store-client", "cases.tsv", "vectors")
        self.assertTrue(any("consumers.tsv" in e for e in self.mutate('"when":"true","cells"', '"when":"owner == \\"07-console-module\\"","cells"', crl)))

    def test_lesson_package_owner(self):             # потребители — строки consumers.tsv ∪ урок-владелец пакета урока
        row = self.row("01-store/rights-evaluator", "expect.tsv", "vectors")
        self.assertTrue(any("not a consumer" in e for e in self.mutate('owner == \\"01-store\\"', 'owner == \\"03-worker\\"', row)))
        self.consumers("06-console/rid\ttemplate.tsv\t03-worker\t", None)    # без строки when с 03-worker — чужой
        self.assertTrue(any("not a consumer" in e and "template.tsv" in e for e in self.errors()))

    def consumers(self, start, new):
        """Строка consumers.tsv, начинающаяся с `start`, заменена на `new` (None — удалена; копия вместо ссылки)."""
        path = self.path.parent / "consumers.tsv"
        text = path.read_text(encoding="utf-8")
        path.unlink()
        lines = text.split("\n")
        hit = [i for i, ln in enumerate(lines) if ln.startswith(start)]
        self.assertEqual(len(hit), 1, start)
        lines[hit[0]:hit[0] + 1] = [] if new is None else [new]
        path.write_text("\n".join(lines), encoding="utf-8")

    def test_consumers_form(self):                  # wire.md: повтор, неизвестный урок, пакет или таблица — ошибка формы
        start = "06-console/rid\ttemplate.tsv\t03-worker\t"
        line = next(ln for ln in (self.path.parent / "consumers.tsv").read_text(encoding="utf-8").split("\n") if ln.startswith(start))
        for new, word in ((line + "\n" + line, "repeats"),
                          (line.replace("\t03-worker\t", "\t99-nope\t"), "lesson '99-nope'"),
                          (line.replace("06-console/rid\t", "rid\t"), "package 'rid'"),
                          (line.replace("06-console/rid\t", "99-nope/rid\t"), "package '99-nope/rid'"),
                          (line.replace("06-console/rid\t", "common/rid\t"), "package 'common/rid'"),
                          (line.replace("\ttemplate.tsv\t", "\tnope.tsv\t"), "table 'nope.tsv'")):
            self.base = set()
            self.consumers(start, new)
            self.assertTrue(any(word in e for e in check_forms.check_wire(self.path)[0]), word)
            (self.path.parent / "consumers.tsv").unlink()
            (self.path.parent / "consumers.tsv").symlink_to(ROOT / "Platform/common/vectors/consumers.tsv")

    def test_assert_tests(self):                  # test: prefix | absent | no-leak (min_bytes ≥ 1 только у no-leak)
        row = self.row("common/family-read", "01.tsv", "vectors")
        old = '{"pointer":"/paths","compare":"set","value":{"column":"paths","decode":"json"}},{"pointer":"/outcome","compare":"value"'
        leak = '{"pointer":"/text","test":"no-leak","value":{"column":"key","decode":"text"},"min_bytes":4},'
        self.assertEqual(self.mutate(old, leak + old, row), [])
        self.assertEqual(self.mutate(old, leak.replace('{"column":"key","decode":"text"}', '{"literal":["s1","s2"]}') + old, row), [])
        self.assertTrue(self.mutate(old, leak.replace('"no-leak"', '"contains"') + old, row))       # test вне списка
        self.assertTrue(self.mutate(old, leak.replace(',"min_bytes":4', '') + old, row))            # no-leak без min_bytes
        self.assertTrue(self.mutate(old, leak.replace('"min_bytes":4', '"min_bytes":0') + old, row))
        self.assertTrue(self.mutate(old, leak.replace('{"column":"key","decode":"text"}', '{"literal":7}') + old, row))
        self.assertEqual(self.mutate(old, leak.replace('{"column":"key","decode":"text"}',
                                                       '{"array":[{"literal":"fixture-password"}]}') + old, row), [])
        self.assertTrue(self.mutate(old, leak.replace('{"column":"key","decode":"text"}', '{"array":[{"literal":7}]}') + old, row))
        self.assertTrue(self.mutate(old, '{"pointer":"/text","test":"absent","min_bytes":4},' + old, row))
        for whole in ("true", "false"):                                                             # whole — только no-leak
            self.assertEqual(self.mutate(old, leak.replace('"min_bytes":4', f'"min_bytes":4,"whole":{whole}') + old, row), [])
        self.assertTrue(self.mutate(old, leak.replace('"min_bytes":4', '"min_bytes":4,"whole":"yes"') + old, row))
        self.assertTrue(self.mutate(old, '{"pointer":"/text","test":"prefix","value":{"literal":"x"},"whole":true},' + old, row))

    def test_layout_any_table(self):              # layout допустим для любой таблицы, правило пустых ячеек прежнее
        crl = self.row("common/crl", "cases.tsv", "vectors")
        layout = "\t".join(["common/crl", "cases.tsv", "layout", "case,input,expect,note", "[]", "{}", "[]", "-", "[]", "-",
                            "common/vectors/crl/README.md"])
        self.assertEqual(self.mutate(crl, crl + "\n" + layout), [])
        fault = self.row("common/fault", "fault.tsv", "layout")   # настоящая привязка: таблица без шапки (P/03, P/06)
        self.assertTrue(self.mutate("\t-,word,status\t", "\t-,word\t", fault))
        self.assertTrue(self.mutate(crl, crl + "\n" + layout.replace("\t[]\t-\tcommon", "\t[]\tvalue\tcommon")))


class SeamFiles(unittest.TestCase):                     # находка spec103: швы урока одной главой (acceptance/seams.tsv)
    def test_flat_and_chapter_seams_found(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            for rel in ("Platform/04-controller/acceptance/seams.tsv", "Platform/01-store/acceptance/1/seams.tsv"):
                (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
                (tmp / rel).write_text("# s\n# scenario\tstep\trequest\texpect\n", encoding="utf-8")
            found = {str(p.relative_to(tmp)) for p in check_forms.seam_files(tmp)}
            self.assertEqual(found, {"Platform/04-controller/acceptance/seams.tsv", "Platform/01-store/acceptance/1/seams.tsv"})
        finally:
            shutil.rmtree(tmp)


class OpenAPIRouting(unittest.TestCase):                # P/05: x-route-priority, x-path-capture/decode/error
    BASE = """openapi: 3.1.0
paths:
  /v1/objects:
    x-route-priority: 50
    get: {responses: {'200': {description: ok}}}
  /v1/objects/{key}:
    x-route-priority: 60
    get:
      parameters:
        - {name: key, in: path, required: true, schema: {type: string}, x-path-capture: remainder, x-path-decode: percent-segment,
           x-path-error: {GET: {status: 400, response_schema: ResourceError}}}
      responses: {'200': {description: ok}, '400': {description: bad}}
components: {schemas: {ResourceError: {type: object}}}
"""

    def run_on(self, text):
        tmp = Path(tempfile.mkdtemp())
        try:
            f = tmp / "05-resource.api.openapi.yaml"
            f.write_text(text, encoding="utf-8")
            return check_forms.check_openapi_routing(f)[0]
        finally:
            shutil.rmtree(tmp)

    def test_clean_and_mutations(self):
        self.assertEqual(self.run_on(self.BASE), [])
        for old, new in (("x-route-priority: 60", "x-route-priority: 50"),        # повтор
                         ("x-route-priority: 60", "x-route-priority: 0"),         # не ≥ 1
                         ("    x-route-priority: 50\n", ""),                       # не у всех
                         ("x-path-capture: remainder", "x-path-capture: rest"),
                         ("x-path-decode: percent-segment", "x-path-decode: raw"),
                         ("{GET: {status: 400", "{PUT: {status: 400"),              # метода нет у пути
                         ("status: 400, response_schema: ResourceError", "status: 404, response_schema: ResourceError"),  # нет в ответах
                         ("response_schema: ResourceError}", "response_schema: NoSuch}"),
                         ("{name: key, in: path", "{name: key, in: query")):
            self.assertTrue(self.run_on(self.BASE.replace(old, new, 1)), (old, new))
        two = self.BASE.replace("/v1/objects/{key}:", "/v1/objects/{key}/{part}:").replace(
            "        - {name: key", "        - {name: part, in: path, required: true, schema: {type: string}, x-path-capture: segment}\n        - {name: key")
        self.assertTrue(self.run_on(two))                                         # remainder не последний


class QueryLexeme(unittest.TestCase):                   # P/05 x-query-lexeme
    def errs(self, schema_type, lex, where="query"):
        return check_forms.query_lexeme_errors("t", {"in": where, "name": "from", "schema": {"type": schema_type}, "x-query-lexeme": lex})

    def test_rules(self):
        num = {"pattern": "^(?:-?[0-9](?:_?[0-9])*)$", "parse": "number", "strip": "_"}
        self.assertEqual(self.errs("number", num), [])
        self.assertEqual(self.errs("integer", {"pattern": "^[0-9]+$", "parse": "integer"}), [])
        self.assertEqual(self.errs("string", {"pattern": "^(?:0|[1-9][0-9]*)$", "parse": "uint64"}), [])
        bad = [("number", dict(num, pattern="[0-9]+")), ("number", dict(num, pattern="^([0-9]$")), ("number", dict(num, parse="float")),
               ("integer", num), ("number", dict(num, strip="-")), ("integer", {"pattern": "^[0-9]+$", "parse": "integer", "strip": "_"}),
               ("string", {"pattern": "^[0-9]+$", "parse": "integer"}), ("number", {"parse": "number"}), ("number", dict(num, extra=1))]
        for st, lex in bad:
            self.assertTrue(self.errs(st, lex), (st, lex))
        self.assertTrue(self.errs("number", num, where="path"))


class RuntimeConstants(unittest.TestCase):              # P/06 runtime-constants.tsv
    def test_rules(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            lesson = tmp / "Platform/06-console"
            (lesson / "spec").mkdir(parents=True)
            (lesson / "forms").mkdir()
            (lesson / "spec/06.1-console.norms.md").write_text("<!-- req: P/06.1-R030 -->\nx\n", encoding="utf-8")
            f = lesson / "forms/runtime-constants.tsv"
            head = "name\tvalue\tunit\tnorm\tmeaning\n"
            good = "CHANGES_TICK\t1\ts\tP/06.1-R030\tthe listing tick\n"
            f.write_text(head + good, encoding="utf-8")
            self.assertEqual(check_forms.check_runtime_constants(f)[0], [])
            for bad in (good + good, good.replace("CHANGES_TICK", "changes_tick"), good.replace("\t1\t", "\t0\t"),
                        good.replace("\t1\t", "\t01\t"), good.replace("\ts\t", "\tms\t"), good.replace("P/06.1-R030", "P/06.1-R999"),
                        good.replace("P/06.1-R030", "P/05.1-R030"), good.replace("the listing tick", " ")):
                f.write_text(head + bad, encoding="utf-8")
                self.assertTrue(check_forms.check_runtime_constants(f)[0], bad)
        finally:
            shutil.rmtree(tmp)


class WireP06(unittest.TestCase):                  # расширения провода P/06 (wire.md «P/06 transport constructors»)
    setUp, tearDown, errors, row, mutate = Wire.setUp, Wire.tearDown, Wire.errors, Wire.row, Wire.mutate
    norm = staticmethod(Wire.norm)

    def test_arg_file_json(self):
        rid = self.row("06-console/rid", "rid.tsv", "stand:rid")
        self.assertTrue(self.mutate('"decode":"raw-json"', '"decode":"yaml"', rid))
        self.assertEqual(self.mutate('"decode":"raw-json"', '"decode":"text"', rid), [])
        self.assertTrue(self.mutate('{"column":"rid","decode":"raw-json"}',
                                    '{"file":{"base":"package","path":"rid.tsv"},"decode":"text"}', rid))
        crl = self.row("common/crl", "cases.tsv", "vectors")                       # json — только у stand
        self.assertTrue(self.mutate('"cells":{"input":{"column":"input"}}', '"arg_file":{"json":{"literal":1}}', crl))

    def test_raw_json_only_in_arg_file(self):
        crl = self.row("common/crl", "cases.tsv", "vectors")
        self.assertTrue(any("raw-json" in e for e in self.mutate('"decode":"cell"', '"decode":"raw-json"', crl)))
        digest = self.row("06-console/request-digest", "digest.tsv", "stand:request-digest")
        self.assertTrue(any("raw-json" in e for e in self.mutate('{"column":"sha256","decode":"text"}',
                                                                 '{"column":"sha256","decode":"raw-json"}', digest)))

    def test_map(self):
        fault = self.row("common/fault", "fault.tsv", "vectors")
        self.assertTrue(any("requires group_by" in e for e in self.mutate('"group_by":[],', '', fault)))
        self.assertTrue(any("map key" in e for e in self.mutate('"map":{"key":"word"', '"map":{"key":"status"', fault)))
        self.assertTrue(self.mutate('"map":{"key":"word"', '"map":{"key":"nope"', fault))
        self.assertTrue(self.mutate('"value":{"column":"status","decode":"json"}}', '"value":{"group":{"column":"status","decode":"json"}}}', fault))
        crl = self.row("common/crl", "cases.tsv", "vectors")
        self.assertTrue(self.mutate('{"column":"expect","decode":"cell"}',
                                    '{"map":{"key":"case","value":{"column":"expect","decode":"cell"}}}', crl))

    def test_input_roles_from_readme(self):          # роли колонок задаёт README: вход может читать колонку ожидания
        digest = self.row("06-console/request-digest", "digest.tsv", "stand:request-digest")
        self.assertEqual(self.mutate('"input":{"column":"input","decode":"text"}', '"input":{"column":"canonical","decode":"text"}',
                                     digest), [])
        crl = self.row("common/crl", "cases.tsv", "vectors")                # cells {} без group_by — вызов на строку
        self.assertEqual(self.mutate('"cells":{"input":{"column":"input"}}', '"cells":{}', crl), [])

    def test_marker_ignore(self):                    # marker.ignore — отказ; assert маркера без test — ignore годен
        ex = self.row("02-installer/exec", "cases.tsv", "stand:exec")
        old = '"value":{"object":{"result":{"literal":"refused"}}}}]'
        self.assertTrue(self.mutate(old, old[:-2] + ',"ignore":["/argv"]}]', ex))
        self.assertEqual(self.mutate(old, old[:-2] + ',"assert":[{"pointer":"/result","value":{"literal":"refused"},'
                                                     '"ignore":["/x"]}]}]', ex), [])
        self.assertTrue(self.mutate(old, old[:-2] + ',"assert":[{"pointer":"/result","test":"prefix","value":{"literal":"r"},'
                                                    '"ignore":["/x"]}]}]', ex))

    def test_ignore(self):
        pool = self.row("common/pool", "cases.tsv", "vectors")
        self.assertEqual(self.errors(), [])
        for bad in ('[""]', '[]', '["/fates","/fates"]', '["/fates","/fates/0"]', '["fates"]', '"/fates"'):
            self.assertTrue(self.mutate('"ignore":["/fates"]', f'"ignore":{bad}', pool), bad)
        self.assertTrue(any("console pool" in e for e in self.mutate('"ignore":["/fates"]', '"ignore":["/other"]', pool)))
        self.assertTrue(any("console pool" in e for e in self.mutate(',"ignore":["/fates"]', '', pool)))   # у 06-console — обязателен
        self.assertEqual(self.mutate('"owner == \\"04-controller\\"","code":0,"value":{"column":"expect","decode":"json"}}',
                                     '"owner == \\"04-controller\\"","code":0,"value":{"column":"expect","decode":"json"},'
                                     '"ignore":["/load"]}', pool), [])                                  # 04-controller — правило не его
        fr = self.row("common/family-read", "01.tsv", "vectors")
        old = '{"pointer":"/paths","compare":"set","value":{"column":"paths","decode":"json"}},{"pointer":"/outcome","compare":"value"'
        self.assertEqual(self.mutate(old, '{"pointer":"/a","value":{"literal":{}},"ignore":["/x","/xy"]},' + old, fr), [])
        self.assertTrue(self.mutate(old, '{"pointer":"/a","test":"absent","ignore":["/x"]},' + old, fr))
        self.assertTrue(self.mutate(old, '{"pointer":"/a","value":{"literal":{}},"ignore":["/x/~1","/x/~1/y"]},' + old, fr))

    def test_cel_json(self):
        ph = self.row("common/password-hash", "cases.tsv", "stand:password-hash")
        self.assertTrue(self.mutate('json(row[\\"input\\"])', 'json(row[\\"input\\"], \\"x\\")', ph))   # арность
        self.assertTrue(self.mutate('json(row[\\"input\\"])', 'json(1)', ph))
        self.assertTrue(any("non-JSON" in e for e in self.mutate('json(row[\\"input\\"])', 'json(row[\\"case\\"])', ph)))

    def test_at(self):                               # at: {"at":{"value":column|literal,"pointer":"/…"},"decode":"json"?}
        pool = self.row("02-installer/workers-script", "cases.tsv", "stand:workers-script")
        col = '{"column":"expect","decode":"json"}'
        at = '{"at":{"value":' + col + ',"pointer":"/start"}}'
        self.assertEqual(self.mutate(col, at, pool), [])                                     # проходящий случай
        self.assertEqual(self.mutate(col, '{"at":{"value":{"literal":{"a":"[1]"}},"pointer":"/a"},"decode":"json"}', pool), [])
        for bad in (at.replace(col, '{"at":{"value":' + col + ',"pointer":"/start"}}'),    # вложенный at
                    at.replace(col, '{"object":{"x":' + col + '}}'),                          # не column и не literal
                    at.replace('"/start"', '""'), at.replace('"/start"', '"start"'), at.replace('"/start"', '"/a~2"'),
                    at[:-1] + ',"decode":"text"}',                                            # внешний decode ≠ json
                    at[:-1] + ',"decode":"json"}',                                            # выбрано не строка
                    at.replace('"/start"', '"/nope"'),                                         # указателя нет в строках
                    '{"at":{"value":{"literal":{"a":1}},"pointer":"/b"}}',
                    '{"at":{"value":' + col + ',"pointer":"/start","extra":1}}'):
            self.assertTrue(self.mutate(col, bad, pool), bad)
        rid = self.row("06-console/rid", "rid.tsv", "stand:rid")                              # at во входе — отказ
        self.assertTrue(self.mutate('{"column":"rid","decode":"raw-json"}',
                                    '{"at":{"value":{"literal":{"a":"x"}},"pointer":"/a"}}', rid))
        crl = self.row("common/crl", "cases.tsv", "vectors")
        self.assertTrue(self.mutate('"cells":{"input":{"column":"input"}}',
                                    '"cells":{"input":{"at":{"value":{"column":"input","decode":"json"},"pointer":"/ca"}}}', crl))

    def test_arg_file_json_closed(self):             # wire.md: в arg_file json — column text|json|raw-json, literal, object, array
        rid = self.row("06-console/rid", "rid.tsv", "stand:rid")
        self.assertTrue(self.mutate('{"column":"rid","decode":"raw-json"}', '{"column":"rid","decode":"cell"}', rid))
        self.assertTrue(self.mutate('"rid":{"column":"rid","decode":"raw-json"}', '"rid":{"omit":true}', rid))
class VersionedDoors(unittest.TestCase):                # P/08 versioned-doors.tsv: настоящая форма и мутации
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.lesson = self.tmp / "Platform/08-domain"
        shutil.copytree(ROOT / "Platform/08-domain/spec", self.lesson / "spec")
        (self.lesson / "forms").mkdir()
        self.path = self.lesson / "forms/versioned-doors.tsv"
        self.good = (ROOT / "Platform/08-domain/forms/versioned-doors.tsv").read_text(encoding="utf-8")
        self.api = next((self.lesson / "spec").glob("*.api.openapi.yaml"))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def errors(self, text):
        self.path.write_text(text, encoding="utf-8")
        return check_forms.check_versioned_doors(self.path)[0]

    def line(self, method, path):
        return next(x for x in self.good.split("\n") if x.startswith(f"{method}\t{path}\t"))

    def cell(self, method, path, column, value):
        line = self.line(method, path)
        cells = line.split("\t")
        cells[check_forms.VDOOR_COLUMNS.index(column)] = value
        return self.good.replace(line + "\n", "\t".join(cells) + "\n")

    def test_real_form_clean(self):
        errors, stats = check_forms.check_versioned_doors(ROOT / "Platform/08-domain/forms/versioned-doors.tsv")
        self.assertEqual(errors, [])
        self.assertEqual(stats["versioned_doors"], 19)
        self.assertEqual(self.errors(self.good), [])

    def test_mutations(self):
        head = "\t".join(check_forms.VDOOR_COLUMNS)
        users = self.line("PUT", "/domain/users/{name}")
        bad = {
            "extra column": self.good.replace(head, head + "\tnote").replace(users, users + "\tx"),
            "missing column": self.good.replace("\tabsent_revision\t", "\t"),
            "source column": self.good.replace(head, head + "\tsource").replace(users, users + "\tx"),
            "unknown operation": self.good.replace(users, users.replace("PUT\t/domain/users/{name}", "PUT\t/domain/nope/{name}")),
            "uncovered operation": self.good.replace(users + "\n", ""),
            "repeat": self.good.replace(users + "\n", users + "\n" + users + "\n"),
            "revision": self.cell("PUT", "/domain/users/{name}", "revision", "version"),
            "etag": self.cell("PUT", "/domain/users/{name}", "etag", "yes"),
            "etag against OpenAPI": self.cell("PUT", "/domain/users/{name}", "etag", "false"),
            "if_match": self.cell("PUT", "/domain/users/{name}", "if_match", "required"),
            "if_match against OpenAPI": self.cell("PUT", "/domain/users/{name}", "if_match", "ignored"),
            "absent_revision": self.cell("PUT", "/domain/users/{name}", "absent_revision", "1"),
            "row kind": self.cell("PUT", "/domain/users/{name}", "row", "domain/users/{name}"),
            "row placeholder": self.cell("PUT", "/domain/users/{name}", "row", "domain/users/<user>"),
            "norm anchor": self.cell("PUT", "/domain/users/{name}", "norm", "P/08.0-R005,P/08.0-R999"),
            "norm foreign lesson": self.cell("PUT", "/domain/users/{name}", "norm", "P/06.1-R030"),
            "norm form": self.cell("PUT", "/domain/users/{name}", "norm", "P/08.0 Н1.9"),
            "norm empty": self.cell("PUT", "/domain/users/{name}", "norm", ""),
            "base-rev without R006": self.cell("PUT", "/domain/topology", "norm", "P/08.0-R005"),
        }
        for what, text in bad.items():
            self.assertNotEqual(text, self.good, what)
            self.assertTrue(self.errors(text), what)

    def test_openapi_side(self):                        # новая операция с If-Match без строки формы — отказ
        text = self.api.read_text(encoding="utf-8")
        self.assertEqual(self.errors(self.good), [])
        self.api.write_text(text.replace("\npaths:\n", "\npaths:\n  /domain/extra:\n    put:\n      parameters:\n"
                                         "        - $ref: '#/components/parameters/IfMatch'\n"
                                         "      responses: {'200': {description: ok}}\n", 1), encoding="utf-8")
        self.assertTrue(self.errors(self.good))



RWB_CATALOG = ("key\tkind\towner\tops\treaders\twhen\tversion\tschema\tnorm\n"
               "<sub>/state/<имя>/<id>\trow\tP/03.6\tguard=<s>worker\t<s>worker\tunit.state\t1\t03-worker/data/state.schema.json\tP/03.6 Н1.7\n"
               "<sub>/epoch/<id>\trow\tP/03.2\tcreate=<s>worker\t<s>worker\t-\t1\t03-worker/data/epoch.schema.json\tP/03.2 Н1.5\n"
               "<sub>/<manifest:unit.rows>/<id>\trow\tP/06.1\tcas=console\tconsole\t-\t1\tmanifest\tP/06.1 Н1.2\n")
RWB_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["born", "revision", "epoch", "value"],
              "properties": {"born": {"type": "string"}, "revision": {"$ref": "#/$defs/common.pos53"},
                             "epoch": {"$ref": "#/$defs/common.pos53"}, "value": {}},
              "$defs": {"common.pos53": {"type": "integer", "minimum": 1}}}
RWB_DECLS = ("#start /sub string\n#start /unit string\n#start /born string\n#start /revision integer\n"
             "#start /epoch integer\n#start /epoch_index string\n#input /name string\n#input /value dyn\n")
RWB_KEY = "{start:/sub}/state/{input:/name}/{start:/unit}"
RWB_GUARD = "{start:/sub}/epoch/{start:/unit}\tstart:/epoch_index"
RWB_NORM = "P/03.6-R018,P/03.6-R029"
RWB_GOOD = ("\t".join(check_forms.RWB_COLUMNS) + "\n" + RWB_DECLS +
            "".join(f"state\t{RWB_KEY}\t/{f}\t{s}\t/{f}\t{RWB_GUARD}\t{RWB_NORM}\n"
                    for f, s in (("born", "start"), ("revision", "start"), ("epoch", "start"), ("value", "input"))))


class RowWriteBindings(unittest.TestCase):              # P/03 row-write-bindings.tsv (P03-GEN-01): фикстура и мутации
    def setUp(self):
        import json
        self.tmp = Path(tempfile.mkdtemp())
        self.lesson = self.tmp / "Platform/03-worker"
        for d in ("forms", "spec", "data"):
            (self.lesson / d).mkdir(parents=True)
        (self.tmp / "Platform/common/data").mkdir(parents=True)
        (self.tmp / "Platform/common/data/catalog.tsv").write_text(RWB_CATALOG, encoding="utf-8")
        (self.lesson / "data/state.schema.json").write_text(json.dumps(RWB_SCHEMA), encoding="utf-8")
        (self.lesson / "spec/03.6-worker.norms.md").write_text(
            "## Н1\n<!-- req: P/03.6-R018 -->\ntext\n<!-- req: P/03.6-R029 -->\ntext\n", encoding="utf-8")
        self.path = self.lesson / "forms/row-write-bindings.tsv"

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def errors(self, text):
        self.path.write_text(text, encoding="utf-8")
        return check_forms.check_row_write_bindings(self.path)[0]

    def row(self, field, text=RWB_GOOD):
        return next(x for x in text.split("\n") if x.startswith("state\t") and x.split("\t")[2] == field)

    def cell(self, field, column, value, text=RWB_GOOD):
        line = self.row(field, text)
        cells = line.split("\t")
        cells[check_forms.RWB_COLUMNS.index(column)] = value
        return text.replace(line + "\n", "\t".join(cells) + "\n")

    def all_cells(self, column, value):
        text = RWB_GOOD
        for f in ("/born", "/revision", "/epoch", "/value"):
            text = self.cell(f, column, value, text)
        return text

    def test_good(self):
        self.path.write_text(RWB_GOOD, encoding="utf-8")
        errors, stats = check_forms.check_row_write_bindings(self.path)
        self.assertEqual(errors, [])
        self.assertEqual(stats["row_write_bindings"], 4)
        const = self.cell("/born", "source", "const")
        self.assertEqual(self.errors(self.cell("/born", "value", '""', const)), [])   # const "" — синтаксис

    def test_real_lessons(self):                        # настоящая форма урока, если она есть в main
        for path in check_forms.row_write_binding_forms(ROOT):
            self.assertEqual(check_forms.check_row_write_bindings(path)[0], [], path)

    def test_mutations(self):
        head = "\t".join(check_forms.RWB_COLUMNS)
        bad = {
            "header extra": RWB_GOOD.replace(head, head + "\tmeaning", 1),
            "header order": RWB_GOOD.replace(head, head.replace("field\tsource", "source\tfield"), 1),
            "header short": RWB_GOOD.replace(head, head.replace("\tnorm", ""), 1),
            "write name": self.all_cells("write", "State"),
            "write field repeats": RWB_GOOD + self.row("/born") + "\n",
            "key differs": self.cell("/epoch", "key", "{start:/sub}/state/{input:/name}/x"),
            "guard_key differs": self.cell("/epoch", "guard_key", "{start:/sub}/epoch/x"),
            "guard_version differs": self.cell("/epoch", "guard_version", "input:/name"),
            "field not pointer": self.cell("/born", "field", "born"),
            "field nested": self.cell("/born", "field", "/born/x"),
            "foreign property": self.cell("/born", "field", "/made"),
            "required not bound": RWB_GOOD.replace(self.row("/epoch") + "\n", ""),
            "source": self.cell("/born", "source", "snapshot"),
            "value no slash": self.cell("/born", "value", "born"),
            "value empty": self.cell("/born", "value", ""),
            "value undeclared": self.cell("/born", "value", "/made"),
            "value of other source": self.cell("/value", "source", "start"),
            "value CEL": self.cell("/revision", "value", "/revision + 1"),
            "const CEL": self.cell("/revision", "value", "start.revision + 1", self.cell("/revision", "source", "const")),
            "const not strict JSON": self.cell("/revision", "value", "NaN", self.cell("/revision", "source", "const")),
            "const type": self.cell("/revision", "value", '"1"', self.cell("/revision", "source", "const")),
            "declaration type": RWB_GOOD.replace("#input /value dyn", "#input /value any"),
            "declaration repeats": RWB_GOOD.replace("#input /value dyn", "#input /value dyn\n#input /value string"),
            "declaration form": RWB_GOOD.replace("#input /value dyn", "#input value dyn"),
            "type against schema": RWB_GOOD.replace("#start /revision integer", "#start /revision string"),
            "key placeholder undeclared": self.all_cells("key", "{start:/sub}/state/{input:/nom}/{start:/unit}"),
            "key placeholder not string": self.all_cells("key", "{start:/sub}/state/{input:/name}/{start:/epoch}"),
            "key placeholder part of segment": self.all_cells("key", "{start:/sub}/state/x{input:/name}/{start:/unit}"),
            "key placeholder name": self.all_cells("key", "{start:/sub}/state/{arg:/name}/{start:/unit}"),
            "key CEL": self.all_cells("key", "start.sub + '/state'"),
            "key foreign family": self.all_cells("key", "{start:/sub}/state"),
            "key family without schema": self.all_cells("key", "{start:/sub}/{input:/name}/{start:/unit}"),
            "guard_key template": self.all_cells("guard_key", "{start:/sub}/epoch/{now}"),
            "guard_version form": self.all_cells("guard_version", "/epoch_index"),
            "guard_version undeclared": self.all_cells("guard_version", "start:/version"),
            "guard_version not string": self.all_cells("guard_version", "start:/epoch"),
            "guard one filled (key)": self.all_cells("guard_version", "-"),
            "guard one filled (version)": self.all_cells("guard_key", "-"),
            "norm empty": self.cell("/born", "norm", ""),
            "norm absent anchor": self.cell("/born", "norm", "P/03.6-R018,P/03.6-R999"),
            "norm foreign lesson": self.cell("/born", "norm", "P/06.1-R030"),
            "norm repeats": self.cell("/born", "norm", "P/03.6-R018,P/03.6-R018"),
            "norm form": self.cell("/born", "norm", "P/03.6 Н1.7"),
        }
        self.assertEqual(self.errors(RWB_GOOD), [])
        self.assertEqual(self.errors(self.all_cells("guard_key", "-").replace("\tstart:/epoch_index\t", "\t-\t")), [])
        for what, text in bad.items():
            self.assertNotEqual(text, RWB_GOOD, what)
            self.assertTrue(self.errors(text), what)


if __name__ == "__main__":
    unittest.main()
