"""Судья общего пакета договоров (tools/normgen/contracts; ADR-0125 доп. (5), опись генерации п. 1).

Запуск: python3 tools/normgen/test_contracts.py [-v]   (go 1.22)

Пакет contracts — ручная среда «один раз на словарь» по Platform/common/contracts/*.md; адаптеры
contracts/adapters/<функция>.go — функции vectoradapter над ним. Судья — общие векторы: для каждого урока, чьи векторы
(out/pNN/go/vectortests, выход gen_vectors) зовут функцию адаптера, модуль урока собирается с contracts и адаптером
вместо заглушки, и все тесты таблиц этой функции — зелёные (их набор — из самих тестов: вызовы vectoradapter.<Ф>).
Мутант договора (ослабленная проверка) — красный хотя бы у одного урока.
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONTRACTS = HERE / "contracts/go"
ADAPTERS = HERE / "contracts/adapters"
OUT = HERE / "out"
GOENV = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off", GOTOOLCHAIN="local")


def adapter_fns():
    return {re.search(r"^func ([A-Z]\w*)\((?:table string|input \[\]byte|file \[\]byte|raw string)", p.read_text(), re.M)[1]: p
            for p in sorted(ADAPTERS.glob("*.go"))}


def lesson_mods():
    return sorted(p for p in OUT.glob("p*/go") if (p / "vectortests").is_dir())


def tests_calling(mod, fn):
    names = []
    for f in (mod / "vectortests").glob("*_test.go"):
        for chunk in f.read_text().split("\nfunc ")[1:]:
            m = re.match(r"(Test\w+)\(t \*testing\.T\)", chunk)
            if m and f"vectoradapter.{fn}(" in chunk.split("\n}\n")[0]:
                names.append(m[1])
    return names


def build(mod, fn, adapter, contracts_src, tmp):
    dst = tmp / f"{mod.parent.name}-{fn}"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(mod, dst)
    module = (dst / "go.mod").read_text().split("\n")[0].split()[1]
    shutil.copytree(contracts_src, dst / "contracts")
    stub = dst / "vectoradapter" / f"{fn.lower()}.go"
    if stub.exists():
        stub.unlink()
    (dst / "vectoradapter" / f"{fn.lower()}_contracts.go").write_text(
        adapter.read_text().replace('"kitmodule/internal/contracts"', f'"{module}/contracts"'))
    return dst


def run(dst, tests):
    pat = "^(" + "|".join(tests) + ")$"
    done = subprocess.run(["go", "test", "-count=1", "-run", pat, "./vectortests/"], cwd=dst, capture_output=True,
                          text=True, env=GOENV)
    return done


class Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("go"):
            raise unittest.SkipTest("go is not in PATH")
        cls.tmp = Path(tempfile.mkdtemp(prefix="contracts-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_vet(self):
        done = subprocess.run(["gofmt", "-l", str(CONTRACTS), str(ADAPTERS)], capture_output=True, text=True)
        self.assertEqual(done.stdout.strip(), "", "gofmt")

    def test_vectors(self):
        covered = 0
        for fn, adapter in adapter_fns().items():
            for mod in lesson_mods():
                tests = tests_calling(mod, fn)
                if not tests:
                    continue
                with self.subTest(fn=fn, lesson=mod.parent.name):
                    dst = build(mod, fn, adapter, CONTRACTS, self.tmp)
                    done = run(dst, tests)
                    self.assertEqual(done.returncode, 0, done.stdout[-3000:] + done.stderr[-1000:])
                    self.assertEqual(len(re.findall(r"^--- PASS|^ok ", done.stdout, re.M)) >= 1, True)
                    covered += len(tests)
        self.assertGreater(covered, 0)
        print(f"\ncontracts: {covered} vector tests green over {len(adapter_fns())} adapters", flush=True)


class ContractsKit(unittest.TestCase):
    def test_kit_part(self):
        """build_kit --part contracts: пакет internal/contracts и адаптеры над ним вместо заглушек; тесты таблиц — зелёные."""
        import json
        import sys
        if not shutil.which("go"):
            self.skipTest("go is not in PATH")
        with tempfile.TemporaryDirectory(prefix="contracts-kit-") as tmp:
            dst = Path(tmp) / "kit"
            done = subprocess.run([sys.executable, str(HERE / "kit/build_kit.py"), str(dst), "--lesson", "03-worker",
                                   "--part", "families", "--part", "vectors", "--part", "contracts"],
                                  capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            man = json.loads((dst / "kit.manifest.json").read_text())
            paths = {f["path"]: f for f in man["files"]}
            self.assertIn("03-worker/internal/contracts/instance.go", paths)
            fns = adapter_fns()
            for fn in fns:
                f = paths.get(f"03-worker/internal/vectoradapter/{fn.lower()}.go")
                if f:
                    self.assertTrue(f.get("editable"), fn)
                    self.assertTrue(f["source"].startswith("tools/normgen/contracts/adapters/"), f["source"])
            mod = dst / "03-worker"
            (mod / "go.mod").write_text(f"module {man['module']}\n\ngo 1.22\n")
            done = subprocess.run(["go", "test", "-count=1", "-run", "|".join(fns), "./internal/vectortests/"], cwd=mod,
                                  capture_output=True, text=True, env=GOENV)
            self.assertEqual(done.returncode, 0, done.stdout[-2000:])


if __name__ == "__main__":
    unittest.main()
