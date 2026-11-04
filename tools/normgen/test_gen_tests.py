"""Сверка генератора № 6 ADR-0125 (tools/normgen/gen_tests.py) — свой судья: покрытие и мутации векторов.

Запуск: python3 tools/normgen/test_gen_tests.py [-v]   (нужен go 1.22 в PATH; сети не нужно; только stdlib).

- tools/normgen/out/p01-1 (части gen_tests) — ровно то, что генератор строит сейчас;
- покрытие: каждая строка-вектор jcs и rights-evaluator — ровно один тест `Test<Этап>_Line<N>` и ровно один вход
  команды векторов с ячейками этой строки и без колонок ожидания; имена — по этапам stages.tsv;
- мутация вектора меняет выход: правка одной строки меняет ровно её тест и её случай; рассогласованный вектор
  (sha256 не от canonical, чужая роль, повтор с другим исходом, NaN) — отказ генератора;
- Go: `go vet` на заглушке адаптера; на подставном адаптере (ответы из самих векторов) все тесты зелёные, на нём же
  тесты из мутированного вектора падают ровно в мутированной строке; адаптеры-мутанты (канон = вход, «всё можно»)
  роняют ровно строки, где это неверно;
- команда векторов: vectorcmd на подставном адаптере под vector_judge.py — все случаи; мутированные случаи — ровно
  один отказ; вход вне провода — внешний код 2;
- память: max RSS теста и дочерних процессов — не больше 1 ГБ.
"""
import hashlib
import json
import os
import re
import resource
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

import gen_tests  # noqa: E402
import vector_judge  # noqa: E402
from gen_checks import go_str  # noqa: E402

OUT = HERE / "out/p01-1"
PARTS = ("go/vectoradapter", "go/vectortests", "go/vectorcmd", "go/cmd/vectors", "go/jsonstrict", "go/writecheck", "vectors")
GOENV = dict(os.environ, GOPROXY="off", GOFLAGS="-mod=mod", GOWORK="off", GOTOOLCHAIN="local")
MAX_RSS = 1 << 30
JCS = "Platform/01-store/vectors/jcs/canonical_json.tsv"
RIGHTS = "Platform/01-store/vectors/rights-evaluator/expect.tsv"


def go(args, cwd, env=None):
    return subprocess.run(["go", *args], cwd=cwd, env=dict(GOENV, **(env or {})), capture_output=True, text=True)


def copy_root(dst):
    """Минимальный корень курса для генератора: векторы P/01 и форма этапов."""
    for rel in ("Platform/01-store/vectors", "Platform/01-store/forms"):
        shutil.copytree(ROOT / rel, Path(dst) / rel)
    return Path(dst)


def edit(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, (path, old)
    path.write_text(text.replace(old, new), encoding="utf-8")


def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def go_funcs(src):
    return re.findall(r"^func (Test\w+)\(t \*testing\.T\) \{\n\t(.*)\n\}$", src, re.M)


def fake_adapter():
    """Подставной адаптер: ответы — из самих векторов (canonical для raw и для canonical; исход строки прав).
    FAKE_MODE=identity — канон равен входу; FAKE_MODE=allow — всё разрешено (адаптеры-мутанты)."""
    jcs, _ = gen_tests.read_jcs(ROOT)
    rights, _, _ = gen_tests.read_rights(ROOT)
    canon = {}
    for _, raw, canonical, _ in jcs:
        canon[raw] = canonical
        canon[canonical] = canonical
    lines = ['package vectoradapter\n\nimport (\n\t"errors"\n\t"os"\n)\n\nvar mode = os.Getenv("FAKE_MODE")\n',
             "var canon = map[string]string{\n"]
    lines += [f"\t{go_str(k)}: {go_str(v)},\n" for k, v in canon.items()]
    lines.append("}\n\nvar rights = map[[3]string]bool{\n")
    lines += [f"\t{{{go_str(r)}, {go_str(a)}, {go_str(k)}}}: {'true' if ok else 'false'},\n"
              for _, r, a, k, ok in rights]
    lines.append('''}

func Canonical(raw []byte) ([]byte, error) {
	if mode == "identity" {
		return raw, nil
	}
	c, ok := canon[string(raw)]
	if !ok {
		return nil, errors.New("fake: unknown text")
	}
	return []byte(c), nil
}

func LoadRights(file []byte) (func(role, action, key string) bool, error) {
	if len(file) == 0 {
		return nil, errors.New("fake: empty rights file")
	}
	if mode == "allow" {
		return func(role, action, key string) bool { return true }, nil
	}
	return func(role, action, key string) bool { return rights[[3]string{role, action, key}] }, nil
}
''')
    return "".join(lines)


VEC_MAIN = '''package main

import (
	"os"

	"normgen/p01-1/vectorcmd"
)

func main() { os.Exit(vectorcmd.Main(os.Args[1:], os.Stdout, os.Stderr)) }
'''


def go_results(stdout):
    """go test -json → {имя теста: pass | fail}."""
    out = {}
    for line in stdout.splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("Test") and ev.get("Action") in ("pass", "fail", "skip"):
            out[ev["Test"]] = ev["Action"]
    return out


class GenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="normgen-tests-")
        cls.files = gen_tests.render(ROOT)
        cls.jcs, _ = gen_tests.read_jcs(ROOT)
        cls.rights, _, _ = gen_tests.read_rights(ROOT)
        # модуль с подставным адаптером и командой векторов
        cls.mod = Path(cls.tmp.name) / "mod"
        (cls.mod / "cmd/vec").mkdir(parents=True)
        (cls.mod / "go.mod").write_text("module normgen/p01-1\n\ngo 1.22\n", encoding="utf-8")
        cls.write_parts(cls.mod, cls.files)
        (cls.mod / "vectoradapter/vectoradapter.go").write_text(fake_adapter(), encoding="utf-8")
        (cls.mod / "cmd/vec/main.go").write_text(VEC_MAIN, encoding="utf-8")
        cls.vec = Path(cls.tmp.name) / "vec.bin"
        done = go(["build", "-o", str(cls.vec), "./cmd/vec"], cls.mod)
        if done.returncode:
            raise AssertionError(f"go build cmd/vec:\n{done.stderr}")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @staticmethod
    def write_parts(mod, files, only_tests=False):
        for rel, data in files.items():
            if not rel.startswith("go/") or (only_tests and not rel.startswith("go/vectortests/")):
                continue
            target = Path(mod) / rel[3:]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        if not only_tests and not (Path(mod) / "checks").exists():   # writecheck (провод write-checks) импортирует checks
            shutil.copytree(HERE / "out/p01-1/go/checks", Path(mod) / "checks")

    def run_tests(self, mod, mode=""):
        done = go(["test", "-count=1", "-json", "./vectortests"], mod, {"FAKE_MODE": mode})
        res = go_results(done.stdout)
        self.assertTrue(res, done.stdout[-2000:] + done.stderr[-2000:])
        return res

    def test_out_up_to_date(self):
        """tools/normgen/out/p01-1 (части gen_tests) — ровно свежая генерация."""
        kept = sorted(str(p.relative_to(OUT)) for part in PARTS for p in (OUT / part).rglob("*") if p.is_file())
        self.assertEqual(kept, sorted(self.files))
        for rel, data in self.files.items():
            self.assertEqual((OUT / rel).read_bytes(), data, f"{rel} is stale: run tools/normgen/gen_tests.py")

    def test_coverage(self):
        """Каждая строка-вектор — ровно один тест и ровно один вход команды; имена — по этапам stages.tsv."""
        self.assertEqual(gen_tests.counts(ROOT), {"jcs": len(self.jcs), "rights-evaluator": len(self.rights)})
        jcs = dict(go_funcs(self.files["go/vectortests/jcs_test.go"].decode()))
        rights = dict(go_funcs(self.files["go/vectortests/rights_eval_test.go"].decode()))
        self.assertEqual(sorted(jcs), sorted(f"TestJcs_Line{r[0]}" for r in self.jcs))
        self.assertEqual(sorted(rights), sorted(f"TestRightsEval_Line{r[0]}" for r in self.rights))
        for no, raw, canonical, digest in self.jcs:
            self.assertEqual(jcs[f"TestJcs_Line{no}"], f"jcsRow(t, {go_str(raw)}, {go_str(canonical)}, {go_str(digest)})")
        for no, role, action, key, ok in self.rights:
            self.assertEqual(rights[f"TestRightsEval_Line{no}"],
                             f"rightsRow(t, {go_str(role)}, {go_str(action)}, {go_str(key)}, {'true' if ok else 'false'})")
        rights_bytes = (ROOT / "Platform/01-store/vectors/rights-evaluator/rights.json").read_bytes()
        for pkg, rows, cells_of in (
                ("01-store/jcs", self.jcs, lambda r: {"raw": r[1]}),
                ("01-store/rights-evaluator", self.rights, lambda r: {"role": r[1], "action": r[2], "key": r[3]})):
            base = f"vectors/{pkg}"
            _, cases = vector_judge.read_cases(OUT / base)
            self.assertEqual([c["case"] for c in cases], [f"line-{r[0]}" for r in rows])
            inputs = sorted(k for k in self.files if k.startswith(base + "/line-"))
            self.assertEqual(inputs, sorted(f"{base}/line-{r[0]}.json" for r in rows))
            for r, c in zip(rows, cases):
                doc = json.loads(self.files[f"{base}/line-{r[0]}.json"])
                self.assertEqual(set(doc), {"format", "package", "table", "case", "variant", "cells", "files"})
                self.assertEqual((doc["format"], doc["package"], doc["case"], doc["variant"]), (1, pkg, f"line-{r[0]}", ""))
                self.assertEqual(doc["cells"], cells_of(r))  # только входные колонки, без ожидания
                if pkg.endswith("jcs"):
                    self.assertEqual(doc["files"], {})
                    self.assertEqual(c["stdout"], {"canonical": r[2], "sha256": r[3]})
                else:
                    self.assertEqual(set(doc["files"]), {"rights.json"})
                    self.assertEqual(vector_judge.b64(doc["files"]["rights.json"], "f"), rights_bytes)
                    self.assertEqual(c["stdout"], "allow" if r[4] else "deny")
                self.assertEqual(c["exit"], 0)

    def test_names_follow_stages(self):
        with tempfile.TemporaryDirectory() as d:
            root = copy_root(d)
            edit(root / gen_tests.STAGES, "\trights_eval\t", "\trights_check\t")
            files = gen_tests.render(root)
            names = [n for n, _ in go_funcs(files["go/vectortests/rights_eval_test.go"].decode())]
            self.assertTrue(names and all(n.startswith("TestRightsCheck_Line") for n in names), names)
            edit(root / gen_tests.STAGES, "vectors:jcs", "tests:jcs")
            with self.assertRaisesRegex(gen_tests.GenError, "no stage with gate vectors:jcs"):
                gen_tests.render(root)

    def mutated(self, d, which):
        """Корень с одной мутированной строкой → (корень, имя теста, case)."""
        root = copy_root(d)
        if which == "jcs":
            no, raw, canonical, digest = self.jcs[0]
            new = canonical.replace("2", "3")
            self.assertNotEqual(new, canonical)
            edit(root / JCS, f"{raw}\t{canonical}\t{digest}", f"{raw}\t{new}\t{sha(new)}")
            return root, f"TestJcs_Line{no}", f"line-{no}"
        no, role, action, key, ok = self.rights[0]
        word = "allow" if ok else "deny"
        edit(root / RIGHTS, f"\n{role}\t{action}\t{key}\t{word}\n",
             f"\n{role}\t{action}\t{key}\t{'deny' if ok else 'allow'}\n")
        return root, f"TestRightsEval_Line{no}", f"line-{no}"

    def test_mutation_changes_output(self):
        """Мутация одной строки меняет ровно её тест и её случай (вход команды тот же)."""
        for which, gofile, pkg in (("jcs", "jcs_test.go", "01-store/jcs"),
                                   ("rights", "rights_eval_test.go", "01-store/rights-evaluator")):
            with tempfile.TemporaryDirectory() as d:
                root, test, case = self.mutated(d, which)
                files = gen_tests.render(root)
                before = dict(go_funcs(self.files[f"go/vectortests/{gofile}"].decode()))
                after = dict(go_funcs(files[f"go/vectortests/{gofile}"].decode()))
                self.assertEqual(sorted(before), sorted(after))
                self.assertEqual([n for n in before if before[n] != after[n]], [test])
                base = f"vectors/{pkg}"
                self.assertEqual(files[f"{base}/{case}.json"], self.files[f"{base}/{case}.json"])
                old = self.files[f"{base}/cases.tsv"].decode().splitlines()
                new = files[f"{base}/cases.tsv"].decode().splitlines()
                diff = [(a, b) for a, b in zip(old, new) if a != b]
                # строка «# source … sha256» таблицы и строка случая — больше ничего
                self.assertEqual(len(diff), 2, diff)
                self.assertTrue(diff[0][0].startswith("# source ") and diff[1][0].startswith(case + "\t"), diff)

    def test_rejects_vectors_out_of_form(self):
        no, raw, canonical, digest = self.jcs[0]
        role_row = "acc\tread\tacc/exact\tallow"
        cases = [
            (JCS, f"{raw}\t{canonical}\t{digest}", f"{raw}\t{canonical} \t{digest}", "not the sha256 of canonical"),
            (JCS, f"{raw}\t{canonical}\t{digest}", f"{raw}\t{canonical}", "2 cells"),
            (JCS, f"{raw}\t{canonical}\t{digest}", f'{{"a":NaN}}\t{canonical}\t{digest}', "NaN is not JSON"),
            (JCS, f"{raw}\t{canonical}\t{digest}", f'{{"a":1,"a":2}}\t{canonical}\t{digest}', "repeated name"),
            (JCS, f"{raw}\t{canonical}\t{digest}", f"{raw}\t{canonical}\t{digest.upper()}", "64 lowercase hex"),
            (RIGHTS, role_row, "nobody\tread\tacc/exact\tallow", "is not in"),
            (RIGHTS, role_row, "acc\tlist\tacc/exact\tallow", "action"),
            (RIGHTS, role_row, "acc\tread\tacc/exact\tmaybe", "allow or deny"),
            (RIGHTS, role_row, f"{role_row}\nacc\tread\tacc/exact\tdeny", "another expect"),
            (RIGHTS, "role\taction\tkey\texpect", "role\taction\tkey\toutcome", "header"),
        ]
        for rel, old, new, msg in cases:
            with self.subTest(msg=msg), tempfile.TemporaryDirectory() as d:
                root = copy_root(d)
                edit(root / rel, old, new)
                with self.assertRaisesRegex(gen_tests.GenError, re.escape(msg)):
                    gen_tests.render(root)

    def test_go_vet_on_stub(self):
        """Заглушка адаптера (out): go vet всего модуля; тесты собираются и падают на «not implemented»."""
        mod = Path(self.tmp.name) / "stub"
        (mod / "cmd/vec").mkdir(parents=True)
        (mod / "go.mod").write_text("module normgen/p01-1\n\ngo 1.22\n", encoding="utf-8")
        self.write_parts(mod, self.files)
        (mod / "cmd/vec/main.go").write_text(VEC_MAIN, encoding="utf-8")
        done = go(["vet", "./..."], mod)
        self.assertEqual(done.returncode, 0, done.stderr)
        res = self.run_tests(mod)
        self.assertEqual(len(res), len(self.jcs) + len(self.rights))
        self.assertEqual(set(res.values()), {"fail"})
        gofmt = subprocess.run(["gofmt", "-l", "."], cwd=mod, capture_output=True, text=True).stdout
        self.assertEqual(gofmt, "")

    def test_go_fake_adapter_green(self):
        res = self.run_tests(self.mod)
        self.assertEqual(len(res), len(self.jcs) + len(self.rights))
        self.assertEqual({n for n, a in res.items() if a != "pass"}, set())
        # судья gate tests: по имени этапа видит только свои тесты
        done = go(["test", "-count=1", "-json", "-run", "^TestJcs_", "./..."], self.mod)
        self.assertEqual(set(go_results(done.stdout)), {f"TestJcs_Line{r[0]}" for r in self.jcs})

    def test_go_mutated_vector_kills_one(self):
        """Тесты из мутированного вектора на адаптере по исходным векторам падают ровно в мутированной строке."""
        for which in ("jcs", "rights"):
            with tempfile.TemporaryDirectory() as d:
                root, test, _ = self.mutated(d, which)
                mod = Path(d) / "mod"
                shutil.copytree(self.mod, mod)
                self.write_parts(mod, gen_tests.render(root), only_tests=True)
                res = self.run_tests(mod)
                self.assertEqual({n for n, a in res.items() if a != "pass"}, {test})

    def test_go_adapter_mutants(self):
        """Адаптер-мутант падает ровно на строках, где он неверен."""
        res = self.run_tests(self.mod, "identity")
        want = {f"TestJcs_Line{r[0]}" for r in self.jcs if r[1] != r[2]}
        self.assertTrue(want)
        self.assertEqual({n for n, a in res.items() if a != "pass" and n.startswith("TestJcs_")}, want)
        res = self.run_tests(self.mod, "allow")
        want = {f"TestRightsEval_Line{r[0]}" for r in self.rights if not r[4]}
        self.assertTrue(want)
        self.assertEqual({n for n, a in res.items() if a != "pass" and n.startswith("TestRightsEval_")}, want)

    def test_vector_command(self):
        """vectorcmd на подставном адаптере под vector_judge: все случаи обоих пакетов; --specs сверяет источники."""
        for pkg, n in (("jcs", len(self.jcs)), ("rights-evaluator", len(self.rights))):
            result, err = vector_judge.judge(pkg, f"{self.vec} {{input}}", specs=str(ROOT))
            self.assertIsNone(err)
            self.assertEqual((result["passed"], result["total"], result["failed"]), (n, n, []))
        with tempfile.TemporaryDirectory() as d:
            root = copy_root(d)
            edit(root / JCS, self.jcs[0][3], "0" * 64)
            _, err = vector_judge.judge("jcs", f"{self.vec} {{input}}", specs=str(root))
            self.assertIn("sha256", err)

    def test_vector_command_mutants(self):
        """Мутированные случаи — ровно один отказ; адаптер-мутант — отказ на своих строках."""
        for which, pkg in (("jcs", "01-store/jcs"), ("rights", "01-store/rights-evaluator")):
            with tempfile.TemporaryDirectory() as d:
                root, _, case = self.mutated(d, which)
                gen_tests.generate(root, Path(d) / "out")
                result, err = vector_judge.judge(pkg, f"{self.vec} {{input}}", cases=str(Path(d) / "out/vectors" / pkg))
                self.assertIsNone(err)
                self.assertEqual([f["case"] for f in result["failed"]], [case])
        os.environ["FAKE_MODE"] = "allow"
        try:
            result, _ = vector_judge.judge("rights-evaluator", f"{self.vec} {{input}}")
        finally:
            del os.environ["FAKE_MODE"]
        self.assertEqual({f["case"] for f in result["failed"]}, {f"line-{r[0]}" for r in self.rights if not r[4]})

    def test_vector_command_wire(self):
        """Вход вне провода — внешний код 2, stdout пуст; верный — конверт {exit_code, stdout_b64, stderr_b64}."""
        good = json.loads(self.files["vectors/01-store/jcs/line-10.json"])
        bad = [
            dict(good, extra=1),
            dict(good, format=2),
            {k: v for k, v in good.items() if k != "variant"},
            dict(good, cells={}),
            dict(good, cells={"raw": good["cells"]["raw"], "canonical": "{}"}),
            dict(good, cells={"raw": 1}),
            dict(good, package="01-store/other"),
            dict(good, variant="write"),
            dict(json.loads(self.files["vectors/01-store/rights-evaluator/line-5.json"]), files={"rights.json": "%%"}),
        ]
        with tempfile.TemporaryDirectory() as d:
            for i, doc in enumerate([good] + bad):
                p = Path(d) / f"{i}.json"
                p.write_text(json.dumps(doc), encoding="utf-8")
                done = subprocess.run([str(self.vec), str(p)], capture_output=True)
                if i == 0:
                    self.assertEqual(done.returncode, 0, done.stderr)
                    env = json.loads(done.stdout)
                    self.assertEqual(set(env), {"exit_code", "stdout_b64", "stderr_b64"})
                    self.assertEqual(env["exit_code"], 0)
                else:
                    self.assertEqual((done.returncode, done.stdout), (2, b""), (doc, done.stderr))

    def test_kit_part(self):
        """build_kit --part tests: пути импорта переписаны, go vet в пустом модуле, манифест — origin generated, часть
        tests; адаптер реализации при повторной сборке не трогается; без части — каталогов tests нет."""
        sys.path.insert(0, str(HERE / "kit"))
        import build_kit
        module = "example.com/w2c/store"
        dst = Path(self.tmp.name) / "kit"
        m = build_kit.build(dst, module, ["tests"])
        store = dst / "01-store"
        (store / "go.mod").write_text(f"module {module}\n\ngo 1.22\n", encoding="utf-8")
        (store / "cmd/store").mkdir(parents=True)
        (store / "cmd/store/main.go").write_text(VEC_MAIN.replace('"normgen/p01-1/', f'"{module}/internal/'),
                                                 encoding="utf-8")
        done = go(["vet", "./..."], store)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(m["parts"], ["writecheck", "tests"])
        tests = [f for f in m["files"] if f["component"] == "tests"]
        self.assertEqual(sorted(f["path"].split("/")[2] for f in tests),
                         ["vectoradapter", "vectorcmd", "vectors", "vectortests", "vectortests", "vectortests"])
        self.assertIn("01-store/cmd/vectors/main.go", [f["path"] for f in tests])   # бинарь векторов (ADR-0126 доп. (5))
        done = go(["build", "-o", str(Path(self.tmp.name) / "kit-vectors"), "./cmd/vectors"], store)
        self.assertEqual(done.returncode, 0, done.stderr)
        for f in tests:
            self.assertEqual(f["origin"], "generated")
            self.assertEqual(f.get("editable", False), "/vectoradapter/" in f["path"])
            self.assertNotIn(b"normgen/p01-1", (dst / f["path"]).read_bytes())
        self.assertIn("TestRightsEval_Line", (dst / "KIT.md").read_text(encoding="utf-8"))
        own = store / "internal/vectoradapter/vectoradapter.go"
        own.write_text(own.read_text(encoding="utf-8") + "\n// mine\n", encoding="utf-8")
        m = build_kit.build(dst, module, ["tests"])
        self.assertTrue(own.read_text(encoding="utf-8").endswith("// mine\n"))
        self.assertNotIn("internal/vectoradapter", [f["path"].rsplit("/", 1)[0][len("01-store/"):] for f in m["files"]])
        other = Path(self.tmp.name) / "kit-plain"
        m = build_kit.build(other, module)
        self.assertEqual(m["parts"], ["writecheck"])
        self.assertFalse((other / "01-store/internal/vectortests").exists())
        with self.assertRaises(build_kit.KitError):
            build_kit.build(other, module, ["door-x"])

    def test_write_checks_binary(self):
        """cmd/vectors на пробах write-checks.probes.tsv — зелёный у vector_judge; мутант провода — красный."""
        mod = Path(self.tmp.name) / "wc"
        shutil.copytree(OUT / "go", mod)
        exe = Path(self.tmp.name) / "wc-vectors"
        done = go(["build", "-o", str(exe), "./cmd/vectors"], mod)
        self.assertEqual(done.returncode, 0, done.stderr)
        judge = [sys.executable, str(HERE / "vector_judge.py"), "--package", "write-checks", "--cmd", f"{exe} {{input}}"]
        done = subprocess.run(judge, capture_output=True, text=True, timeout=600)
        self.assertEqual(done.returncode, 0, done.stdout[-2000:] + done.stderr[-2000:])
        self.assertRegex(done.stdout, r"write-checks: (\d+)/\1 PASS")
        edit(mod / "vectorcmd/vectorcmd.go", '"n": ref.N, "code"', '"n": ref.N + 1, "code"')
        done = go(["build", "-o", str(exe), "./cmd/vectors"], mod)
        self.assertEqual(done.returncode, 0, done.stderr)
        done = subprocess.run(judge, capture_output=True, text=True, timeout=600)
        self.assertEqual(done.returncode, 1, done.stdout[-500:])

    def test_zz_memory(self):
        rss = max(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
        if sys.platform != "darwin":
            rss *= 1024
        self.assertLessEqual(rss, MAX_RSS, f"max RSS {rss >> 20} MiB")


if __name__ == "__main__":
    unittest.main()
