"""Тесты тестов этапов из сценариев (tools/normgen/gen_stagetests.py; ADR-0125 доп. (3), (4)).

Запуск: python3 tools/normgen/test_gen_stagetests.py [-v]  (go 1.22 в PATH).

- выход out/p01-1/go/stagetests и coreadapter — свежая генерация; опись главы 1.1 — все шаги объявленных сценариев;
- перевод префиксом: шаг-директива отсекает остаток сценария (в описи — исключён с причиной); пустая проекция и
  сценарий вне объявления gate — отказ генератора; форма gate tests:<этап>:<глава>:<сценарии> берётся раньше объявления;
- движок (перенос runner/run.py) на подставном ядре: связывание $имён, тип числа, лишние поля, error у отказа,
  !contains, порядок ключей /v1/list, ASSERT, несвязанное имя в запросе, класс статуса 4xx — исход каждого подтеста.
Внешний судья на коде реализации — scenario_judge.py (раннер на том же коде).
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import gen_stagetests  # noqa: E402
import gen_tests  # noqa: E402

OUT = HERE / "out/p01-1"
STAGES = (ROOT / "Platform/01-store/forms/stages.tsv").read_text(encoding="utf-8")

# Синтетические сценарии: (сценарий, шаг, запрос, ожидание) и ответ подставного ядра на запрос; ожидаемый исход.
CASES = [
    ("s1-bind", "1", 'POST /b1 {"a":1}', '200 {"index":"$a"}', (200, '{"index":"7"}'), "pass"),
    ("s1-bind", "2", "GET /b2", '200 {"index":"$a"}', (200, '{"index":"7"}'), "pass"),
    ("s1-bind", "3", "GET /b3", '200 {"index":"$a"}', (200, '{"index":"8"}'), "fail"),
    ("s2-types", "1", "GET /t1", '200 {"n":1}', (200, '{"n":1.0}'), "fail"),
    ("s2-types", "2", "GET /t2", '200 {"n":1}', (200, '{"n":1}'), "pass"),
    ("s2-types", "3", "GET /t3", '200 {"n":true}', (200, '{"n":1}'), "fail"),
    ("s3-fields", "1", "GET /f1", '200 {"a":"x"}', (200, '{"a":"x","b":1}'), "fail"),
    ("s3-fields", "2", "GET /f2", '409 {"kind":"conflict"}', (409, '{"kind":"conflict","error":"e"}'), "pass"),
    ("s3-fields", "3", "GET /f3", '409 {"kind":"conflict"}', (409, '{"kind":"conflict"}'), "fail"),
    ("s3-fields", "4", "GET /f4", '200 {"a":"x"}', (200, '{"a":"x","a":"x"}'), "fail"),
    ("s4-contains", "1", "GET /c1", '409 {"kind":"k","error":"!contains 42"}', (409, '{"kind":"k","error":"has 42"}'), "fail"),
    ("s4-contains", "2", "GET /c2", '409 {"kind":"k","error":"!contains 42"}', (409, '{"kind":"k","error":"ok"}'), "pass"),
    ("s5-order", "1", "GET /v1/list?prefix=a", '200 {"keys":{"a":"1","b":"2"}}', (200, '{"keys":{"b":"2","a":"1"}}'), "fail"),
    ("s5-order", "2", "GET /v1/list?prefix=b", '200 {"keys":{"a":"1","b":"2"}}', (200, '{"keys":{"a":"1","b":"2"}}'), "pass"),
    ("s6-assert", "1", "GET /p", '200 {"x":"$x","y":"$y"}', (200, '{"x":"1","y":"2"}'), "pass"),
    ("s6-assert", "2", "ASSERT $x != $y", "", None, "pass"),
    ("s6-assert", "3", "ASSERT $x == $y", "", None, "fail"),
    ("s6-assert", "4", "ASSERT $z != $x $y", "", None, "fail"),
    ("s6-assert", "5", "ASSERT $x != $y $x", "", None, "fail"),
    ("s7-unbound", "1", "GET /q/$nope", "200 {}", (200, "{}"), "fail"),
    ("s8-class", "1", "GET /s", "4xx", (404, '{"error":"e"}'), "pass"),
    ("s8-class", "2", "GET /s2", "4xx", (500, '{"error":"e"}'), "fail"),
    ("s9-prefix", "1", "GET /x1", '200 {"a":"1"}', (200, '{"a":"1"}'), "pass"),
    ("s9-prefix", "2", "@restart store", "ok", None, None),
    ("s9-prefix", "3", "GET /x3", '200 {"a":"1"}', (200, '{"a":"1"}'), None),
]

FAKE = '''package coreadapter

type fake struct{}

var replies = map[string]struct {
	code int
	body string
}{
%s}

func Open(cfg Config) (Core, error) { return fake{}, nil }

func (fake) Handle(c Call, method, target string, h map[string]string, b []byte) (int, map[string]string, []byte) {
	r, ok := replies[method+" "+target]
	if !ok {
		return 599, nil, []byte(`{"error":"no reply"}`)
	}
	return r.code, nil, []byte(r.body)
}

func (fake) Close() error { return nil }
'''


def synthetic_root(tmp, rows):
    root = Path(tmp) / "root"
    (root / "Platform/01-store/acceptance/1").mkdir(parents=True)
    (root / "Platform/01-store/forms").mkdir(parents=True)
    (root / "Platform/01-store/forms/stages.tsv").write_text(STAGES, encoding="utf-8")
    lines = ["scenario\tstep\trequest\texpect"] + ["\t".join(r) for r in rows]
    (root / "Platform/01-store/acceptance/1/scenarios.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root


class StageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="normgen-stagetests-")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_out_is_fresh_and_inventory_whole(self):
        files, inventory = gen_stagetests.build(ROOT)
        for rel, text in files.items():
            want = gen_tests.gofmt(text) if rel.endswith(".go") else text
            self.assertEqual((OUT / rel).read_text(encoding="utf-8"), want, f"{rel}: run gen_tests.py")
        scenarios, _, _ = gen_stagetests.read_scenarios(ROOT, "1.1")
        want = sum(len(scenarios[n]) for _, (_, names) in gen_stagetests.STAGE_SCENARIOS.items() for n in names)
        self.assertEqual(len(inventory), want)
        self.assertTrue(all(r[3] == "translated" for r in inventory), "chapter 1.1 runs whole in process")

    def test_prefix_and_projection(self):
        rows = [c[:4] for c in CASES]
        root = synthetic_root(Path(self.tmp.name) / "p", rows)
        files, inventory = gen_stagetests.build(root, declaration={"http": ("1.1", ["s9-prefix"])})
        status = {r[0]: (r[3], r[4]) for r in inventory}
        self.assertEqual(status["1.1/s9-prefix/1"][0], "translated")
        self.assertEqual([status[f"1.1/s9-prefix/{k}"][0] for k in "23"], ["excluded", "excluded"])
        self.assertIn("step 2", status["1.1/s9-prefix/3"][1])
        self.assertIn("[:1]", files["go/stagetests/http_test.go"])
        with self.assertRaises(gen_stagetests.GenError):          # пустая проекция
            gen_stagetests.build(synthetic_root(Path(self.tmp.name) / "e", [("s0", "1", "@restart store", "ok")]),
                                 declaration={"http": ("1.1", ["s0"])})
        with self.assertRaises(gen_stagetests.GenError):          # сценария нет
            gen_stagetests.build(root, declaration={"http": ("1.1", ["s99"])})
        with self.assertRaises(gen_stagetests.GenError):          # вне gate accept:1.1:01-absent
            gen_stagetests.build(root, declaration={"launch": ("1.1", ["s1-bind"])})
        form = STAGES.replace("accept:1.1:01-absent", "tests:launch:1.1:s1-bind")
        files, inventory = gen_stagetests.build(root, stages_text=form, declaration={"launch": ("1.1", ["s9-prefix"])})
        self.assertEqual({r[0].split("/")[1] for r in inventory}, {"s1-bind"})   # форма раньше объявления

    def test_engine_on_fake_core(self):
        rows = [c[:4] for c in CASES]
        root = synthetic_root(Path(self.tmp.name) / "g", rows)
        names = sorted({c[0] for c in CASES})
        files, _ = gen_stagetests.build(root, declaration={"http": ("1.1", names)})
        mod = Path(self.tmp.name) / "mod"
        shutil.copytree(OUT / "go", mod)
        shutil.rmtree(mod / "stagetests")
        for rel, text in files.items():
            if rel.startswith("go/"):
                (mod / rel[3:]).parent.mkdir(parents=True, exist_ok=True)
                (mod / rel[3:]).write_text(text, encoding="utf-8")
        replies = "".join(f'\t{json.dumps(c[2].split(" ")[0] + " " + c[2].split(" ")[1])}: {{{c[4][0]}, {json.dumps(c[4][1])}}},\n'
                          for c in CASES if c[4])
        (mod / "coreadapter/open.go").write_text(FAKE % replies, encoding="utf-8")
        done = subprocess.run(["go", "test", "-count=1", "-json", "./stagetests"], cwd=mod, capture_output=True,
                              text=True)
        got = {}
        for line in done.stdout.splitlines():
            e = json.loads(line)
            if e.get("Action") in ("pass", "fail") and "/" in (e.get("Test") or ""):
                got[e["Test"]] = e["Action"]
        self.assertTrue(got, done.stdout[-2000:] + done.stderr[-2000:])
        for sc, step, req, _, _, want in CASES:
            name = f"TestHttp_{gen_stagetests.camel_name(sc)}/{step}"
            with self.subTest(step=f"{sc}/{step} {req}"):
                self.assertEqual(got.get(name), want, name)


if __name__ == "__main__":
    unittest.main()
