"""Судья части stagetests в режиме портов CALL (gen_cmdtests.py; P/03, P/04; ADR-0125 доп. (5), ADR-0126 доп. (7)).

Запуск: python3 tools/normgen/test_gen_cmdtests_ports.py [-v]   (go 1.22)

1. out свежий; порты пакета — ровно строки таблицы «CALL port» forms/README.md, прочитанной здесь заново; каждый шаг
   швов этапов stages.tsv — тест (опись translated), ни один не потерян.
2. Заглушки адаптера: каждый тест красный, без паники движка.
3. Подставной адаптер (ответы выписаны судьёй из самих швов: «@absent» — поля нет, «$имя» — одна строка на имя;
   генератор и судья реализацию не исполняют): всё зелёное.
4. Мутанты подставного адаптера — красные: поле ответа другое, поле пропало, лишнее поле в «{}», паника порта,
   ошибка порта, «$имя» — разные строки на шагах одного сценария.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
LESSONS = {"03-worker": "p03", "04-controller": "p04", "05-resource": "p05", "06-console": "p06"}
GOENV = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off", GOTOOLCHAIN="local")


def ports(lesson):
    text = (ROOT / "Platform" / lesson / "forms/README.md").read_text(encoding="utf-8")
    return re.findall(r"^\| `([a-z][a-z0-9-]*)` \| ", text, re.M)


def seam_steps(lesson):
    """[(сценарий, шаг, порт, вход, ожидание)] швов, выбранных этапами stages.tsv (своё чтение формы)."""
    les = ROOT / "Platform" / lesson
    rows = [ln.split("\t") for ln in (les / "forms/stages.tsv").read_text(encoding="utf-8").split("\n")
            if ln and not ln.startswith("#")]
    head = rows[0]
    out = []
    for r in rows[1:]:
        gate = dict(zip(head, r))["gate"]
        for g in gate.split(";"):
            m = re.fullmatch(r"\s*tests:([0-9.]+):([^:]+):seams\s*", g)
            if not m:
                continue
            ch = m[1]
            path = les / "acceptance" / (ch.split(".")[1] if "." in ch else "") / "seams.tsv"
            lines = [ln.split("\t") for ln in path.read_text(encoding="utf-8").split("\n") if ln and not ln.startswith("#")]
            names = None if m[2] == "*" else m[2].split(",")
            for sc, st, req, exp in lines:
                if names is None or sc in names:
                    port, _, inp = req[5:].partition(" ")
                    out.append((f"{ch}/{sc}", int(st), port, inp, exp))
    return out


def concrete(exp, binds, sc):
    """Ожидание → ответ: «@absent» — поля нет, «$имя» — строка сценария."""
    if isinstance(exp, dict):
        return {k: concrete(v, binds, sc) for k, v in exp.items() if v != "@absent"}
    if isinstance(exp, list):
        return [concrete(v, binds, sc) for v in exp]
    if isinstance(exp, str) and re.fullmatch(r"\$[A-Za-z_][A-Za-z0-9_]*", exp):
        return binds.setdefault((sc, exp), f"bound-{sc}-{exp[1:]}")
    return exp


def answers(lesson):
    """{(порт, вход): ответ JSON} — выписка из швов; разные ответы на один вход — ошибка судьи (стоп)."""
    out, binds = {}, {}
    for sc, _, port, inp, exp in seam_steps(lesson):
        key = (port, json.dumps(json.loads(inp), sort_keys=True))
        ans = json.dumps(concrete(json.loads(exp), binds, sc), sort_keys=True)
        if key in out and out[key] != ans:
            raise AssertionError(f"{lesson}: two seams give one input of {port} different answers ({sc})")
        out[key] = ans
    return out


def fake_go(lesson, mutate=None):
    lines = ["package lessonadapter", "", "import (", '\t"bytes"', '\t"encoding/json"', '\t"errors"', '\t"fmt"',
             '\t"strings"', ")", "",
             "func canon(in json.RawMessage) string {", "\tvar v any", "\t_ = json.Unmarshal(in, &v)",
             "\treturn canonValue(v)", "}", "",
             "func canonValue(v any) string {", "\tvar buf bytes.Buffer", "\tenc := json.NewEncoder(&buf)",
             "\tenc.SetEscapeHTML(false)", "\t_ = enc.Encode(v)", "\treturn strings.TrimSuffix(buf.String(), \"\\n\")", "}", "",
             "var answers = map[string]string{"]
    ans = answers(lesson)
    for (port, inp), out in ans.items():
        if mutate:
            out = mutate(port, inp, out)
        # Go json.Marshal сортирует ключи отображений — тот же канон, что sort_keys без пробелов
        key = port + "\x00" + json.dumps(json.loads(inp), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        lines.append(f"\t{json.dumps(key, ensure_ascii=False)}: {json.dumps(out, ensure_ascii=False)},")
    lines += ["}", "", "func answer(port string, in json.RawMessage) (json.RawMessage, error) {",
              '\tif a, ok := answers[port+"\\x00"+canon(in)]; ok {',
              '\t\tif a == "PANIC" {', '\t\t\tpanic("mutant")', "\t\t}",
              '\t\tif a == "ERROR" {', '\t\t\treturn nil, errors.New("mutant")', "\t\t}",
              "\t\treturn json.RawMessage(a), nil", "\t}",
              '\treturn nil, fmt.Errorf("no answer for %s %s", port, in)', "}", ""]
    for port in ports(lesson):
        ident = "".join(w[:1].upper() + w[1:] for w in port.split("-"))
        lines.append(f"func {ident}(in json.RawMessage) (json.RawMessage, error) {{ return answer({json.dumps(port)}, in) }}")
    return "\n".join(lines) + "\n"


def go_test(mod):
    done = subprocess.run(["go", "test", "-count=1", "-json", "./stagetests/"], cwd=mod, capture_output=True,
                          text=True, env=GOENV)
    res = {}
    for line in done.stdout.split("\n"):
        if line.startswith("{"):
            ev = json.loads(line)
            if ev.get("Test") and "/" not in ev["Test"] and ev.get("Action") in ("pass", "fail"):
                res[ev["Test"]] = ev["Action"]
    return done, res


class Ports(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("go"):
            raise unittest.SkipTest("go is not in PATH")
        cls.tmp = Path(tempfile.mkdtemp(prefix="judge-ports-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def module(self, lesson, name, fake=None):
        mod = self.tmp / f"{LESSONS[lesson]}-{name}"
        out = self.tmp / f"gen-{LESSONS[lesson]}-{name}"
        done = subprocess.run([sys.executable, str(HERE / "gen_cmdtests.py"), "--lesson", lesson, str(out)],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        shutil.copytree(out / "go", mod)
        if fake is not None:
            for p in (mod / "lessonadapter").glob("*.go"):
                if p.name != "lessonadapter.go":
                    p.unlink()
            (mod / "lessonadapter/fake.go").write_text(fake, encoding="utf-8")
        return mod, out

    def expected_tests(self, lesson):
        return {f"Test{''.join(w[:1].upper() + w[1:] for w in re.split(r'[-_]', stage))}_"
                f"{''.join(w[:1].upper() + w[1:] for w in re.split(r'[-_]', sc.split('/')[1]))}"
                for sc, stage in self.stage_of(lesson)}

    def stage_of(self, lesson):
        les = ROOT / "Platform" / lesson
        rows = [ln.split("\t") for ln in (les / "forms/stages.tsv").read_text(encoding="utf-8").split("\n")
                if ln and not ln.startswith("#")]
        head, out = rows[0], set()
        for r in rows[1:]:
            st = dict(zip(head, r))
            for sc, *_ in seam_steps_for_gate(les, st["gate"]):
                out.add((sc, st["stage"]))
        return out

    def test_fresh_and_projection(self):
        for lesson, slug in LESSONS.items():
            with self.subTest(lesson=lesson):
                _, out = self.module(lesson, "fresh")
                kept = HERE / "out" / slug / "go"
                for p in sorted((out / "go").rglob("*")):
                    if p.is_file() and p.name != "go.mod":
                        rel = p.relative_to(out / "go")
                        self.assertEqual((kept / rel).read_bytes(), p.read_bytes(), f"out/{slug}/go/{rel} is stale")
                stubs = sorted(p.stem for p in (kept / "lessonadapter").glob("*.go") if p.name != "lessonadapter.go")
                self.assertEqual(stubs, sorted(x.replace("-", "_") for x in ports(lesson)))
                inv = (kept / "stagetests/inventory.tsv").read_text(encoding="utf-8")
                for sc, st, *_ in seam_steps(lesson):
                    self.assertIn(f"{sc.split('/')[0]}/seams.tsv/{sc.split('/')[1]}/{st}\t", inv)

    def test_stubs_red(self):
        for lesson in LESSONS:
            with self.subTest(lesson=lesson):
                mod, _ = self.module(lesson, "stubs")
                done, res = go_test(mod)
                self.assertNotIn("panic:", done.stdout)
                self.assertEqual(set(res), self.expected_tests(lesson))
                self.assertEqual({v for v in res.values()}, {"fail"})

    def test_fake_green_and_mutants(self):
        for lesson in LESSONS:
            with self.subTest(lesson=lesson):
                mod, _ = self.module(lesson, "fake", fake_go(lesson))
                done, res = go_test(mod)
                self.assertEqual(done.returncode, 0, done.stdout[-3000:])
                self.assertEqual(set(res), self.expected_tests(lesson))
        lesson = "03-worker"
        first = next(iter(answers(lesson)))

        def change(port, inp, out):                      # поле ответа другое
            v = json.loads(out)
            k = sorted(v)[0]
            v[k] = "mutant"
            return json.dumps(v)

        def drop(port, inp, out):
            v = json.loads(out)
            v.pop(sorted(v)[0])
            return json.dumps(v)

        def extra(port, inp, out):                       # лишний элемент в «[]» или «{}» ответа (ровно пустые)
            v = json.loads(out)

            def fill(x):
                if isinstance(x, dict):
                    for k, y in x.items():
                        if y == {}:
                            x[k] = {"mutant": 1}
                            return True
                        if y == []:
                            x[k] = ["mutant"]
                            return True
                        if fill(y):
                            return True
                if isinstance(x, list):
                    return any(fill(y) for y in x)
                return False
            return json.dumps(v) if fill(v) else out
        self.assertTrue(any(extra(p, i, o) != o for (p, i), o in answers(lesson).items()), "extra: not applicable")

        muts = {"change": change, "drop": drop, "extra-in-empty": extra,
                "panic": lambda p, i, o: "PANIC", "error": lambda p, i, o: "ERROR"}
        for name, fn in muts.items():
            with self.subTest(mutant=name):
                only = (lambda f: (lambda p, i, o: f(p, i, o) if (p, json.dumps(json.loads(i), sort_keys=True)) == first
                                   else o))(fn)
                if name == "extra-in-empty":
                    only = fn
                mod, _ = self.module(lesson, f"mut-{name}", fake_go(lesson, only))
                done, res = go_test(mod)
                self.assertIn("fail", res.values(), f"{name} survives")
                self.assertNotEqual(done.returncode, 0)


def seam_steps_for_gate(les, gate):
    out = []
    for g in gate.split(";"):
        m = re.fullmatch(r"\s*tests:([0-9.]+):([^:]+):seams\s*", g)
        if not m:
            continue
        ch = m[1]
        path = les / "acceptance" / (ch.split(".")[1] if "." in ch else "") / "seams.tsv"
        names = None if m[2] == "*" else m[2].split(",")
        for ln in path.read_text(encoding="utf-8").split("\n"):
            if ln and not ln.startswith("#"):
                sc = ln.split("\t")[0]
                if names is None or sc in names:
                    out.append((f"{ch}/{sc}",))
    return out


if __name__ == "__main__":
    unittest.main()
