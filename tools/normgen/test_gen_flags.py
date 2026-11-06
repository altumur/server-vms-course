"""Тесты генератора № 3 ADR-0125 (tools/normgen/gen_flags.py) и его судьи tools/normgen/flag_judge.py.

Запуск: /opt/check-env/lesson-spec/bin/python tools/normgen/test_gen_flags.py [-v]
(нужны cel_expr_python для судьи и go 1.22 в PATH; сети не нужно).

- выход out/p01-1/go/flags совпадает с тем, что генератор строит сейчас (не устарел);
- заглушка tools/normgen/flags/stub на сгенерированном пакете проходит все пробы судьи и 400 случайных строк;
- мутанты сгенерированного кода судья роняет (судья не слеп);
- таблица вне формы — отказ генератора (GenError), а не код;
- пакет Б с частью flags собирается и проходит go vet.
"""
import hashlib
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
sys.path.insert(0, str(HERE / "kit"))

import gen_flags  # noqa: E402
from gen_checks import GenError  # noqa: E402

OUT = HERE / "out/p01-1/go"
TABLE = gen_flags.DEFAULT_TABLE.read_text(encoding="utf-8")


def build_stub(module_dir, work):
    sdir = Path(work) / "stub"
    sdir.mkdir(parents=True, exist_ok=True)
    shutil.copy(HERE / "flags/stub/main.go", sdir / "main.go")
    (sdir / "go.mod").write_text("module normgen/flagstub\n\ngo 1.22\n\nrequire normgen/p01-1 v0.0.0\n\n"
                                 f"replace normgen/p01-1 => {module_dir}\n", encoding="utf-8")
    exe = Path(work) / "flagstub"
    done = subprocess.run(["go", "build", "-o", str(exe), "."], cwd=sdir, capture_output=True, text=True)
    if done.returncode:
        raise AssertionError(done.stderr)
    return exe


def judge(exe, *extra):
    done = subprocess.run([sys.executable, str(HERE / "flag_judge.py"), "--cmd", str(exe), "--stub", *extra],
                          capture_output=True, text=True, timeout=900)
    return done.returncode, done.stdout + done.stderr


def mutate(text, old, new):
    assert old in text, old
    return text.replace(old, new, 1)


class GenFlags(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="normgen-flags-")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_out_is_fresh(self):
        for name, text in gen_flags.render().items():
            self.assertEqual((OUT / "flags" / name).read_text(encoding="utf-8"), text, f"{name}: run gen_flags.py")

    def test_judge_on_stub(self):
        exe = build_stub(OUT, self.tmp.name)
        code, out = judge(exe, "--fuzz", "400", "--seed", "7")
        self.assertEqual(code, 0, out[-3000:])
        self.assertRegex(out, r"flags: (\d+)/\1 PASS")

    def test_judge_catches_mutants(self):
        mutants = [
            ("flags.go", "fl.MaxConns = int64(64)", "fl.MaxConns = int64(65)"),            # умолчание
            ("flags.go", "if fl.Given[name] {", "if false {"),                             # повтор флага
            ("flags.go", '!fl.Given["-voters"] &&', 'false &&'),                       # required через CEL
            ("flags.go", "fl.RaftBind = fl.Raft", "fl.RaftBind = \"\""),                   # =-raft
            ("prims.go", "return v4[0] == 127, nil", "return v4[0] == 127 && v4[1] == 0, nil"),  # loopback
            ("flagtypes.go", "n > 65535", "n > 65536"),                                    # тип addr
        ]
        for k, (name, old, new) in enumerate(mutants):
            with self.subTest(mutant=new):
                mod = Path(self.tmp.name) / f"mut{k}"
                shutil.copytree(OUT, mod)
                path = mod / "flags" / name
                path.write_text(mutate(path.read_text(encoding="utf-8"), old, new), encoding="utf-8")
                exe = build_stub(mod, Path(self.tmp.name) / f"mut{k}-work")
                code, out = judge(exe)
                self.assertEqual(code, 1, f"the judge passed the mutant {new!r}")
                self.assertIn("FAIL", out, "a broken probe builder is not a killed mutant")

    def test_table_out_of_form(self):
        cases = [
            ("-dir\tpath\t", "-dir\tpathx\t"),                           # тип вне словаря
            ("1048576\t1MiB", "1MiB\t1MiB"),                             # умолчание вне типа
            ("enum:1|3|5\t1\t", "enum:1|3|5\t2\t"),                      # умолчание не из enum
            ("\tdaemon,recover\t\tP/01.3 N1.3; P/01.3 N2", "\tdaemon,recover,recover\t\tP/01.3 N1.3; P/01.3 N2"),
            ("-raft-bind\taddr\t=-raft", "-raft-bind\taddr\t=-api-conns"),  # =флаг другого типа
            ("!loopback(f[\"-raft\"])", "!islocal(f[\"-raft\"])"),       # функция не объявлена #fn
            ("\"-door\" in f\tdaemon", "f.size() > 1\tdaemon"),          # метод вне подмножества
            ("#var cmd string", "#var command string"),                  # шапка
            ("-upper\tint:0..", "-Upper\tint:0.."),                      # имя флага
        ]
        for old, new in cases:
            with self.subTest(new=new):
                with self.assertRaises(GenError):
                    gen_flags.build(gen_flags.Table(mutate(TABLE, old, new)))
        with self.assertRaises(GenError):                                  # повтор флага
            gen_flags.Table(TABLE + TABLE.splitlines()[-1] + "\n")

    def test_kit_part_flags(self):
        import build_kit
        dst = Path(self.tmp.name) / "kit"
        manifest = build_kit.build(dst, "example.com/attempt/01-store", ["flags"])
        self.assertEqual(manifest["parts"], ["writecheck", "flags"])
        prov = manifest["provenance"]["flags"]
        self.assertEqual(set(prov), {"form", "generator", "generators", "judge", "output", "judged"})
        generators = {f["path"]: f["sha256"] for f in prov["generators"]}
        helper = "tools/normgen/tsv_input.py"
        self.assertEqual(generators[helper], hashlib.sha256((ROOT / helper).read_bytes()).hexdigest())
        forms = {f["path"]: f["sha256"] for f in prov["form"]}
        proof = "Platform/common/data/cell-json-sha256.tsv"
        self.assertEqual(forms[proof], hashlib.sha256((ROOT / proof).read_bytes()).hexdigest())
        self.assertTrue(any(f["path"].endswith("internal/flags/flags.go") and f["origin"] == "generated"
                            for f in manifest["files"]))
        (dst / "01-store/go.mod").write_text("module example.com/attempt/01-store\n\ngo 1.22\n", encoding="utf-8")
        done = subprocess.run(["go", "vet", "./..."], cwd=dst / "01-store", capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("## Part `flags`", (dst / "KIT.md").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((dst / "kit.manifest.json").read_text())["parts"], ["writecheck", "flags"])


if __name__ == "__main__":
    unittest.main()
