"""Тесты генератора № 4 ADR-0125 (tools/normgen/gen_refusals.py) и его судьи tools/normgen/refusal_judge.py.

Запуск: python3 tools/normgen/test_gen_refusals.py [-v]  (go 1.22 в PATH; сети не нужно).

- выход out/p01-1/go/refusals совпадает с тем, что генератор строит сейчас;
- судья проходит на сгенерированном пакете и падает на мутантах (код, поле, заголовок, имя);
- таблица вне формы — отказ генератора (GenError);
- пакет Б с частями door и refusals собирается и проходит go vet; Check, LogLine, Exit ведут себя по каталогу.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "kit"))

import gen_refusals  # noqa: E402
from gen_checks import GenError  # noqa: E402

OUT = HERE / "out/p01-1/go"
TABLE = gen_refusals.DEFAULT_TABLE.read_text(encoding="utf-8")


def judge(module_dir):
    done = subprocess.run([sys.executable, str(HERE / "refusal_judge.py"), "--module-dir", str(module_dir)],
                          capture_output=True, text=True, timeout=600)
    return done.returncode, done.stdout + done.stderr


def mutate(text, old, new):
    assert old in text, old
    return text.replace(old, new, 1)


BEHAVIOUR = '''package refusals

import (
	"strings"
	"testing"
)

func TestBehaviour(t *testing.T) {
	if CasMismatch.Check(map[string]any{"index": "1"}) != nil || CasMismatch.Check(map[string]any{"index": "1", "key": "k"}) != nil {
		t.Fatal("cas_mismatch: index and optional key")
	}
	if CasMismatch.Check(map[string]any{}) == nil || CasMismatch.Check(map[string]any{"index": "1", "size": 3}) == nil {
		t.Fatal("cas_mismatch: no index or an extra field passes")
	}
	if Weight.Check(map[string]any{"limit": int64(1), "key": "k", "size": 2.5}) == nil {
		t.Fatal("a float passes")
	}
	line, err := StartFlags.LogLine(map[string]string{"flag": "-x"})
	if err != nil || !strings.Contains(line, `flag="-x"`) {
		t.Fatal(line, err)
	}
	if _, err := StartFlags.LogLine(map[string]string{}); err == nil {
		t.Fatal("a log naming nothing passes")
	}
	if _, err := StartFlags.LogLine(map[string]string{"dir": "/d"}); err == nil {
		t.Fatal("a value outside the log passes")
	}
	if l, _ := BoxNoRaft.LogLine(nil); !strings.Contains(l, "this build has no raft") {
		t.Fatal(l)
	}
	var logged string
	if BoxAdmit.Exit(func(s string) { logged = s }, nil) == 0 || logged == "" {
		t.Fatal("exit !0")
	}
	if StartFlags.Code != 2 || ByName("connection_limit") != ConnectionLimit || !ConnectionLimit.RetryAfter || ByName("nope") != nil {
		t.Fatal("catalogue")
	}
}
'''


class GenRefusals(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="normgen-refusals-")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_out_is_fresh(self):
        for name, text in gen_refusals.render().items():
            self.assertEqual((OUT / "refusals" / name).read_text(encoding="utf-8"), text, "run gen_refusals.py")

    def test_judge_passes(self):
        code, out = judge(OUT)
        self.assertEqual(code, 0, out[-3000:])
        self.assertRegex(out, r"refusals: (\d+)/\1 PASS")

    def test_judge_catches_mutants(self):
        mutants = [
            ('Name: "cas_mismatch", Surface: "http", Code: 409', 'Name: "cas_mismatch", Surface: "http", Code: 410'),
            ('Fields: []Field{{"index", false}, {"key", true}}', 'Fields: []Field{{"index", false}}'),
            ('Headers: [][2]string{{"Retry-After", "1"}}, RetryAfter: true',
             'Headers: [][2]string{{"Retry-After", "1"}}, RetryAfter: false'),
            ('"guard_mismatch", Surface: "http", Code: 412, Kind: "guard"',
             '"guard_mismatch", Surface: "http", Code: 412, Kind: "guards"'),
            ('Name: "start_flags", Surface: "start", Code: 2', 'Name: "start_flags", Surface: "start", Code: 1'),
        ]
        for k, (old, new) in enumerate(mutants):
            with self.subTest(mutant=new):
                mod = Path(self.tmp.name) / f"mut{k}"
                shutil.copytree(OUT, mod)
                path = mod / "refusals/refusals.go"
                path.write_text(mutate(path.read_text(encoding="utf-8"), old, new), encoding="utf-8")
                code, out = judge(mod)
                self.assertEqual(code, 1, f"the judge passed the mutant {new!r}: {out[-500:]}")

    def test_table_out_of_form(self):
        cases = [
            ("1.1\t1\tkey_rules\thttp\t400", "1.1\t1\tkey_rules\thttp\t4000"),
            ("1.1\t1\tkey_rules\thttp", "1.1\t1\tKeyRules\thttp"),
            ("1.1\t2\tbody_form\thttp", "1.1\t2\tkey_rules\thttp"),
            ("\tstart\texit 2\t-\t-\t-\trights file", "\tstart\texit 3\t-\t-\t-\trights file"),
            ("\tstart\texit 2\t-\t-\t-\trights file", "\tstart\texit 2\tbadkey\t-\t-\trights file"),
            ("\thttp\t409\tconflict\tindex,key?", "\thttp\t409\tconflict\tindex,index"),
            ("Retry-After: 1\t-\tP/01.1 Н4; P/01.3", "Retry-After 1\t-\tP/01.1 Н4; P/01.3"),
            ("key_rules\thttp\t400", "key_rules\tgate\t400"),
        ]
        for old, new in cases:
            with self.subTest(new=new):
                with self.assertRaises(GenError):
                    gen_refusals.Table(mutate(TABLE, old, new))

    def test_kit_part_refusals(self):
        import build_kit
        dst = Path(self.tmp.name) / "kit"
        manifest = build_kit.build(dst, "example.com/attempt/01-store", ["door", "refusals"])
        self.assertEqual(manifest["parts"], ["writecheck", "door", "refusals"])
        self.assertEqual(set(manifest["provenance"]["refusals"]), {"form", "generator", "judge"})
        mod = dst / "01-store"
        (mod / "go.mod").write_text("module example.com/attempt/01-store\n\ngo 1.22\n", encoding="utf-8")
        (mod / "internal/refusals/behaviour_test.go").write_text(BEHAVIOUR, encoding="utf-8")
        for cmd in (["go", "vet", "./..."], ["go", "test", "./internal/refusals/"]):
            done = subprocess.run(cmd, cwd=mod, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("## Part `refusals`", (dst / "KIT.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
