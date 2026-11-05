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
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "contracts"))
import kitside  # noqa: E402
CONTRACTS = HERE / "contracts/go"
ADAPTERS = HERE / "contracts/adapters"
OUT = HERE / "out"
GOENV = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off", GOTOOLCHAIN="local")


def adapter_fns():
    return {re.search(r"^func ([A-Z]\w*)\((?:table|input|file|raw)\b", p.read_text(), re.M)[1]: p
            for p in sorted(ADAPTERS.glob("*.go"))}


def lesson_mods():
    return sorted(p for p in OUT.glob("p*/go") if (p / "vectortests").is_dir())


def tests_calling(mod, fn):
    names = []
    for f in (mod / "vectortests").glob("*_test.go"):
        for chunk in f.read_text().split("\nfunc ")[1:]:
            m = re.match(r"(Test\w+)\(t \*testing\.T\)", chunk)
            if not m:
                continue
            direct = f"vectoradapter.{fn}(" in chunk.split("\n}\n")[0]
            # P/02 wire tests call the actual vector command; select by the adapter's package test prefix.
            via_wire = False
            if (mod / "wirecheck").is_dir():
                import common_vectors
                common = next((n for n, d in common_vectors.DECLS.items() if d["go"] == fn), None)
                prefix = "TestCommon" + common_vectors.camel(common) if common else "Test" + fn + "_"
                via_wire = m[1].startswith(prefix)
            if direct or via_wire:
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
    text = kitside.fill(adapter.read_text(), mod / "vectortests")
    (dst / "vectoradapter" / f"{fn.lower()}_contracts.go").write_text(
        text.replace('"kitmodule/internal/contracts"', f'"{module}/contracts"'))
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


NFKC_MAIN = """package main

import (
	"bufio"
	"encoding/json"
	"os"

	"nfkcjudge/contracts"
)

func main() {
	sc := bufio.NewScanner(os.Stdin)
	sc.Buffer(make([]byte, 1<<20), 1<<20)
	w := bufio.NewWriter(os.Stdout)
	for sc.Scan() {
		var s string
		if json.Unmarshal(sc.Bytes(), &s) != nil {
			os.Exit(2)
		}
		b, _ := json.Marshal(contracts.NFKC(s))
		w.Write(append(b, '\\n'))
	}
	w.Flush()
}
"""


class NFKC(unittest.TestCase):
    """NFKC пакета (адресный договор А4: таблицы Unicode 15.0.0) — свежесть таблиц gen_nfkc.py и равенство
    unicodedata.normalize("NFKC") Python 3.12 (Unicode 15.0.0) на каждой кодовой точке и на случайных цепочках
    из несоединяемых, составных, хангыля и знаков."""

    def test_tables_fresh(self):
        import sys
        sys.path.insert(0, str(HERE / "contracts/gen"))
        import gen_nfkc
        self.assertEqual((CONTRACTS / "nfkc_tables.go").read_text(encoding="utf-8"), gen_nfkc.render(),
                         "run tools/normgen/contracts/gen/gen_nfkc.py")

    def test_equals_unicodedata(self):
        import json
        import random
        import unicodedata
        if not shutil.which("go"):
            self.skipTest("go is not in PATH")
        self.assertEqual(unicodedata.unidata_version, "15.0.0")
        rnd = random.Random(7)
        cps = [c for c in range(0x110000) if not 0xD800 <= c < 0xE000]
        marks = [c for c in cps if unicodedata.combining(chr(c))]
        composed = [c for c in cps if unicodedata.decomposition(chr(c))]
        pools = [marks, composed, cps[:0x3000], range(0x1100, 0x1200), range(0xAC00, 0xAC40)]
        inputs = [chr(c) for c in cps]
        inputs += ["".join(chr(rnd.choice(rnd.choice(pools))) for _ in range(rnd.randint(2, 6)))
                   for _ in range(100000)]
        with tempfile.TemporaryDirectory(prefix="contracts-nfkc-") as tmp:
            mod = Path(tmp)
            (mod / "go.mod").write_text("module nfkcjudge\n\ngo 1.22\n")
            shutil.copytree(CONTRACTS, mod / "contracts")
            (mod / "main.go").write_text(NFKC_MAIN)
            done = subprocess.run(["go", "run", "."], cwd=mod, input="\n".join(json.dumps(s) for s in inputs) + "\n",
                                  capture_output=True, text=True, env=GOENV)
        self.assertEqual(done.returncode, 0, done.stderr[-2000:])
        got = done.stdout.split("\n")[:-1]
        self.assertEqual(len(got), len(inputs))
        bad = [(s, g) for s, g in zip(inputs, got) if json.loads(g) != unicodedata.normalize("NFKC", s)]
        self.assertEqual(bad[:5], [], f"{len(bad)} of {len(inputs)} differ")


if __name__ == "__main__":
    unittest.main()
