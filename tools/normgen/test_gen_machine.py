"""Судья частей машин (gen_machine.py; slot-capture P/03, slot-fate и slot-release P/04; ADR-0125 доп. (5)).

Запуск: /opt/check-env/lesson-spec/bin/python tools/normgen/test_gen_machine.py [-v]   (нужны cel_expr_python и go 1.22)

1. out свежий: выход каждого урока с машинами равен свежему прогону генератора; go vet и go test пакета — зелёные.
2. Оракул: судья сам читает форму (шапку #var/#const и строки) и сам строит входы — случайные и граничные (литералы и
   #const ± шаг, уставки ЗАГЛАВНЫМИ — тоже случайные), независимо от перебора генератора; условия и аргументы считает
   cel_expr_python; первая совпавшая строка состояния и её аргументы (с типами) должны совпасть с Go Step; переполнение
   int в аргументе (ошибка CEL) — ошибка Step.
3. Мутанты формы: отрицание условия строки, другое next, другой строковый литерал аргумента, обмен соседних строк
   состояния. Мутант берётся, только если оракул находит вход, где его исход иной (не равносилен); выбор перехода
   мутанта с тестами исходной формы (form_test.go) должен быть красным.
"""
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
GEN = HERE / "gen_machine.py"
LESSONS = {"03-worker": ("p03", ["slot-capture"]), "04-controller": ("p04", ["slot-fate", "slot-release"])}
GOENV = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off", GOTOOLCHAIN="local")
INT_MAX = 2 ** 63 - 1
N_RANDOM = 3000


def camel(name):
    if name.isupper():
        name = name.lower()
    return "".join(w[:1].upper() + w[1:] for w in re.split(r"[-_]", name) if w)


class Form:
    """Своё чтение формы судьи: #var, #const, строки (n, state, condition, action, next)."""

    def __init__(self, text):
        self.vars, self.consts, self.rows = {}, {}, []
        for line in text.split("\n"):
            if m := re.fullmatch(r"#var (\w+) (\w+) — (.*)", line):
                self.vars[m[1]] = (m[2], m[3])
            elif m := re.fullmatch(r"#const (\w+) (\w+) = (\S+) — .*", line):
                self.consts[m[1]] = (m[2], m[3])
            elif line and not line.startswith("#") and not line.startswith("n\t"):
                n, state, cond, action, nxt, _ = line.split("\t")
                self.rows.append({"n": int(n), "state": state, "condition": cond, "action": action, "next": nxt})
        self.text = text

    def states(self):
        return list(dict.fromkeys(r["state"] for r in self.rows))


class Oracle:
    def __init__(self, form):
        from cel_expr_python import cel
        self.cel, self.form = cel, form
        T = cel.Type
        types = {"bool": T.BOOL, "int": T.INT, "double": T.DOUBLE, "string": T.STRING}
        variables = {n: types[t] for n, (t, _) in form.vars.items()}
        variables.update({n: types[t] for n, (t, _) in form.consts.items()})
        self.env = cel.NewEnv(variables=variables)
        self.compiled = {}
        for r in form.rows:
            self.compiled[r["n"]] = self.env.compile(r["condition"])
            if r["action"] != "-":
                inner = re.fullmatch(r"[a-z_]+\((.*)\)", r["action"])[1]
                self.compiled[r["n"], "args"] = self.env.compile(f"[{inner}]") if inner else None
        self.const_values = {n: (float(v) if t == "double" else int(v)) for n, (t, v) in form.consts.items()}

    def run(self, state, env):
        """→ (n | None, [(тип, значение)] | "overflow")."""
        data = dict(env, **self.const_values)
        for r in self.form.rows:
            if r["state"] != state:
                continue
            v = self.compiled[r["n"]].eval(data=data)
            if v.type() == self.cel.Type.ERROR:
                raise AssertionError(f"n {r['n']}: condition error {v.value()}")
            if v.plain_value() is True:
                if r["action"] == "-":
                    return r["n"], []
                e = self.compiled.get((r["n"], "args"))
                if e is None:
                    return r["n"], []
                a = e.eval(data=data)
                if a.type() == self.cel.Type.ERROR:
                    return r["n"], "overflow"
                return r["n"], [tagged(x) for x in a.plain_value()]
        return None, []


def tagged(x):
    if isinstance(x, bool):
        return ["bool", x]
    if isinstance(x, int):
        return ["int", str(x)]
    if isinstance(x, float):
        return ["double", repr(float(x))]
    if isinstance(x, str):
        return ["string", x]
    if isinstance(x, dict):
        return ["map", {k: tagged(v) for k, v in sorted(x.items())}]
    raise AssertionError(f"value {x!r}")


def numbers(form):
    """Числа формы: литералы условий и аргументов и #const."""
    out = {float(v) for _, v in form.consts.values()}
    for r in form.rows:
        for lit in re.findall(r"(?<![\w.\"])(\d+(?:\.\d+)?)(?![\w\"])", r["condition"] + " " + r["action"]):
            out.add(float(lit))
    sums = {a + b for a in out for b in out}
    return sorted(out | sums)


def strings(form):
    out = set()
    for r in form.rows:
        out.update(re.findall(r'"([^"\\]*)"', r["condition"] + " " + r["action"]))
    return sorted(out)


def inputs(form, rnd, n):
    """[(state, env)] — граничные и случайные входы судьи."""
    nums, strs = numbers(form), strings(form)
    out = []
    for _ in range(n):
        env = {}
        settings = {}
        for name, (t, doc) in form.vars.items():
            if t == "bool":
                env[name] = rnd.random() < 0.5
            elif t == "string":
                enum = re.match(r"([a-z_]+(?:\|[a-z_]+)+)\b", doc)
                pool = (enum[1].split("|") if enum else strs) + ["", "zz"]
                env[name] = rnd.choice(pool)
            else:
                k = rnd.random()
                base = settings.get("*") or rnd.choice(nums + [0.0])
                if k < 0.6:
                    v = rnd.choice(nums + [0.0]) + rnd.choice([-0.001, 0.0, 0.001, -1, 1])
                elif k < 0.95:
                    v = rnd.uniform(0, 2 * (max(nums) if nums else 10))
                else:
                    v = base
                v = max(v, 0.0)
                if t == "int":
                    v = int(round(v))
                    if rnd.random() < 0.02:
                        v = INT_MAX - rnd.choice([0, 1])
                env[name] = v
        # уставки: иногда равны сравниваемому числу (граница по уставке)
        for name, (t, _) in form.vars.items():
            if name.isupper() and t == "double" and rnd.random() < 0.3:
                for other, (ot, _) in form.vars.items():
                    if ot == "double" and not other.isupper() and rnd.random() < 0.5:
                        env[other] = env[name] + rnd.choice([-0.001, 0.0, 0.001])
        out.append((rnd.choice(form.states() + ["zz-state"] if rnd.random() < 0.01 else form.states()), env))
    return out


DRIVER = r'''package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strconv"

	m "%(module)s/%(pkg)s"
)

func tag(x any) any {
	switch v := x.(type) {
	case bool:
		return []any{"bool", v}
	case int64:
		return []any{"int", strconv.FormatInt(v, 10)}
	case float64:
		return []any{"double", fmt.Sprint(v)}
	case string:
		return []any{"string", v}
	case map[string]any:
		keys := make([]string, 0, len(v))
		for k := range v {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		out := map[string]any{}
		for _, k := range keys {
			out[k] = tag(v[k])
		}
		return []any{"map", out}
	}
	return []any{"?", fmt.Sprintf("%%T", x)}
}

func main() {
	sc := bufio.NewScanner(os.Stdin)
	sc.Buffer(make([]byte, 1<<20), 1<<20)
	enc := json.NewEncoder(os.Stdout)
	for sc.Scan() {
		var c struct {
			State string
			In    m.In
		}
		if err := json.Unmarshal(sc.Bytes(), &c); err != nil {
			panic(err)
		}
		mv, ok, err := m.Step(m.State(c.State), c.In)
		res := map[string]any{"ok": ok, "err": err != nil, "row": mv.Row, "next": string(mv.Next)}
		args := []any{}
		for _, a := range mv.Args {
			args = append(args, tag(a))
		}
		res["args"] = args
		enc.Encode(res)
	}
}
'''


def go(args, cwd, stdin=None):
    return subprocess.run(["go", *args], cwd=cwd, capture_output=True, text=True, env=GOENV, input=stdin)


def gen(lesson, out, root=ROOT, parts=()):
    return subprocess.run([sys.executable, str(GEN), "--lesson", lesson, *parts, "--out", str(out), "--root", str(root)],
                          capture_output=True, text=True)


def form_path(root, lesson, part):
    return Path(root) / "Platform" / lesson / "forms" / f"{part}.tsv"


def go_double(v):
    """repr Python → запись fmt.Sprint(float64) Go для сравнения."""
    x = float(v)
    if x == int(x) and abs(x) < 1e21:
        return str(int(x))
    return repr(x)


def normalize(t):
    if t[0] == "double":
        return ["double", go_double(t[1])]
    if t[0] == "map":
        return ["map", {k: normalize(v) for k, v in t[1].items()}]
    return t


class Judge:
    def __init__(self, lesson, part, mod):
        self.lesson, self.part, self.mod = lesson, part, Path(mod)
        self.pkg = part.replace("-", "")
        self.module = (self.mod / "go.mod").read_text().split("\n")[0].split()[1]

    def step(self, cases):
        d = self.mod / "cmd" / f"judge{self.pkg}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "main.go").write_text(DRIVER % {"module": self.module, "pkg": self.pkg})
        lines = "".join(json.dumps({"State": s, "In": {camel(k): v for k, v in env.items()}}) + "\n"
                        for s, env in cases)
        done = go(["run", f"./cmd/judge{self.pkg}"], self.mod, lines)
        if done.returncode:
            raise AssertionError(f"driver: {done.stderr[-2000:]}")
        return [json.loads(x) for x in done.stdout.split("\n") if x]


def disagreements(oracle, cases, got):
    bad = []
    states = set(oracle.form.states())
    for (state, env), g in zip(cases, got):
        if state not in states:
            if not g["err"]:
                bad.append((state, env, "unknown state without an error", g))
            continue
        n, args = oracle.run(state, env)
        if args == "overflow":
            if not g["err"]:
                bad.append((state, env, f"row {n}: overflow wanted", g))
            continue
        want = {"ok": n is not None, "err": False, "row": n or 0,
                "next": next((r["next"] for r in oracle.form.rows if r["n"] == n), "")}
        if any(g[k] != v for k, v in want.items()) or [normalize(a) for a in args] != g["args"]:
            bad.append((state, env, {**want, "args": [normalize(a) for a in args]}, g))
    return bad


def mutants(form):
    """[(имя, текст формы)] — мутанты строк."""
    head = [ln for ln in form.text.split("\n") if ln.startswith("#") or ln.startswith("n\t")]
    rows = form.rows
    states = sorted({r["state"] for r in rows} | {r["next"] for r in rows})

    def text(rs):
        return "\n".join(head + ["\t".join([str(r["n"]), r["state"], r["condition"], r["action"], r["next"], r.get("norm", "P/00-R000")])
                                 for r in rs]) + "\n"
    norms = {int(ln.split("\t")[0]): ln.split("\t")[5] for ln in form.text.split("\n") if ln and ln[0].isdigit()}
    base = [dict(r, norm=norms[r["n"]]) for r in rows]
    out = []
    for k, r in enumerate(base):
        if r["condition"] != "true":
            out.append((f"n{r['n']}-negate", text(base[:k] + [dict(r, condition=f"!({r['condition']})")] + base[k + 1:])))
        other = next(s for s in states if s != r["next"])
        out.append((f"n{r['n']}-next", text(base[:k] + [dict(r, next=other)] + base[k + 1:])))
        lits = re.findall(r'"([^"\\]+)"', r["action"])
        if lits:
            out.append((f"n{r['n']}-literal", text(base[:k] + [dict(r, action=r["action"].replace(f'"{lits[0]}"', '"mutant"', 1))] + base[k + 1:])))
        if k and base[k - 1]["state"] == r["state"]:
            sw = base[:k - 1] + [dict(r, n=r["n"] - 1), dict(base[k - 1], n=r["n"])] + base[k + 1:]
            out.append((f"n{r['n']}-swap", text(sw)))
    return out


class MachineTests(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        if not shutil.which("go"):
            raise unittest.SkipTest("go is not in PATH")
        try:
            import cel_expr_python  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("no cel_expr_python (the oracle): /opt/check-env/lesson-spec/bin/python")
        cls.tmp = Path(tempfile.mkdtemp(prefix="judge-machine-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def fresh_out(self, lesson):
        slug, _ = LESSONS[lesson]
        out = self.tmp / f"fresh-{slug}"
        done = gen(lesson, out)
        self.assertEqual(done.returncode, 0, done.stderr)
        kept = HERE / "out" / slug / "go"
        for p in sorted((out / "go").rglob("*")):
            if p.is_file() and p.name != "go.mod":
                rel = p.relative_to(out / "go")
                self.assertTrue((kept / rel).is_file(), f"out/{slug}/go/{rel} is missing: run gen_machine.py --lesson {lesson}")
                self.assertEqual((kept / rel).read_bytes(), p.read_bytes(), f"out/{slug}/go/{rel} is stale")
        return out / "go"

    def test_lessons(self):
        for lesson, (slug, parts) in LESSONS.items():
            mod = self.fresh_out(lesson)
            for args in (["vet", "./..."], ["test", "-count=1", "./..."]):
                done = go(args, mod)
                self.assertEqual(done.returncode, 0, f"{lesson}: go {args[0]}: {done.stdout}{done.stderr}")
            for part in parts:
                with self.subTest(part=part):
                    form = Form(form_path(ROOT, lesson, part).read_text(encoding="utf-8"))
                    oracle = Oracle(form)
                    # A new input of one machine must not change another machine's coverage.
                    cases = inputs(form, random.Random(20261105), N_RANDOM)
                    got = Judge(lesson, part, mod).step(cases)
                    self.assertEqual(len(got), len(cases), "the driver dropped cases")
                    bad = disagreements(oracle, cases, got)
                    self.assertEqual(bad[:3], [], f"{part}: {len(bad)} of {len(cases)} disagree with the oracle")
                    hit = {oracle.run(s, e)[0] for s, e in cases if s in form.states()}
                    self.assertTrue({r["n"] for r in form.rows} <= hit, f"{part}: the judge's inputs miss rows "
                                    f"{sorted({r['n'] for r in form.rows} - hit)}")

    def test_capture_exhaustion_priority(self):
        mod = self.tmp / "capture-priority"
        shutil.copytree(self.fresh_out("03-worker"), mod)
        base = {"read_confirmed": True, "exists": True, "gen_readable": True, "row_readable": True, "row_free": True,
                "gen_incrementable": False, "gen": 0, "version": "v7", "wall": 0,
                "me": "box1:1:abcdef", "server": "srv-a"}
        probes = [
            ({}, 7, "generation_exhausted"),
            ({"row_free": False, "permission_matches": True}, 7, "generation_exhausted"),
            ({"row_free": False, "given": True, "first_start_right": True, "same_box": True},
             7, "generation_exhausted"),
            ({"row_readable": False, "age": 50.0}, 7, "generation_exhausted"),
            ({"row_readable": False, "age": 49.999}, 6, "torn_young"),
            ({"row_free": False, "given": True, "first_start_right": True}, 12, "NameOnAnotherBox"),
            ({"row_free": False}, 12, "occupied"),
            ({"gen_readable": False}, 4, "unreadable_gen"),
            ({"exists": False, "gen_incrementable": True}, 5, 1),
            ({"gen_incrementable": True, "gen": 9007199254740990}, 9, 9007199254740991),
        ]
        got = Judge("03-worker", "slot-capture", mod).step(
            [("search", dict(base, **change)) for change, _, _ in probes])
        self.assertEqual(len(got), len(probes))
        for (_, row, value), move in zip(probes, got):
            with self.subTest(row=row, value=value):
                self.assertTrue(move["ok"])
                self.assertFalse(move["err"])
                self.assertEqual(move["row"], row)
                if isinstance(value, str):
                    self.assertEqual(move["next"], "rejected")
                    self.assertEqual(move["args"], [["string", value]])
                else:
                    self.assertEqual(move["next"], "first_write")
                    self.assertEqual(move["args"][1][1]["gen"], ["int", str(value)])

    def test_mutants(self):
        rnd = random.Random(7)
        for lesson, (slug, parts) in LESSONS.items():
            for part in parts:
                form = Form(form_path(ROOT, lesson, part).read_text(encoding="utf-8"))
                oracle = Oracle(form)
                cases = inputs(form, rnd, 1500)
                base = [oracle.run(s, e) for s, e in cases if s in form.states()]
                killed = survived = equivalent = 0
                for name, text in mutants(form):
                    with self.subTest(part=part, mutant=name):
                        mform = Form(text)
                        mo = Oracle(mform)
                        mres = [mo.run(s, e) for s, e in cases if s in form.states()]
                        nxt = {r["n"]: r["next"] for r in form.rows}
                        mnxt = {r["n"]: r["next"] for r in mform.rows}
                        if all(a == b and nxt.get(a[0]) == mnxt.get(b[0]) for a, b in zip(base, mres)):
                            equivalent += 1
                            continue
                        root = self.tmp / f"m-{part}-{name}"
                        fp = form_path(root, lesson, part)
                        fp.parent.mkdir(parents=True)
                        shutil.copy(ROOT / "Platform/lessons.tsv", root / "Platform/lessons.tsv")
                        for other in (ROOT / "Platform" / lesson / "forms").glob("*.tsv"):
                            shutil.copy(other, fp.parent / other.name)
                        fp.write_text(text, encoding="utf-8")
                        out = root / "out"
                        done = gen(lesson, out, root, [part])
                        if done.returncode:            # генератор отверг мутанта (затенённая строка) — убит
                            killed += 1
                            continue
                        pkg = part.replace("-", "")
                        shutil.copy(HERE / "out" / slug / "go" / pkg / "form_test.go", out / "go" / pkg / "form_test.go")
                        done = go(["test", "-count=1", f"./{pkg}/"], out / "go")
                        if done.returncode == 0:
                            survived += 1
                        self.assertNotEqual(done.returncode, 0, f"{part} mutant {name} survives the form tests")
                        killed += 1
                print(f"\n{part}: mutants killed {killed}, survived {survived}, equivalent {equivalent}", file=sys.stderr)
                self.assertGreater(killed, len(form.rows), f"{part}: too few mutants")

    def test_kit(self):
        """build_kit: части машин урока — пакет компилируется под модулем урока, тесты зелёные, impl — editable;
        машина чужого урока — отказ."""
        for lesson, (slug, parts) in LESSONS.items():
            dst = self.tmp / f"kit-{slug}"
            cmd = [sys.executable, str(HERE / "kit/build_kit.py"), str(dst), "--lesson", lesson]
            done = subprocess.run(cmd + sum((["--part", p] for p in parts), []), capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            man = json.loads((dst / "kit.manifest.json").read_text())
            self.assertEqual(sorted(man["parts"]), sorted(parts))
            for f in man["files"]:
                self.assertEqual(bool(f.get("editable")), "impl/" in f["path"], f["path"])
            mod = dst / lesson
            (mod / "go.mod").write_text(f"module {man['module']}\n\ngo 1.22\n")
            done = go(["test", "-count=1", "./..."], mod)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        done = subprocess.run([sys.executable, str(HERE / "kit/build_kit.py"), str(self.tmp / "kit-x"), "--lesson",
                               "03-worker", "--part", "slot-fate"], capture_output=True, text=True)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("no machine form slot-fate.tsv", done.stderr)

    def test_refusals(self):
        """Генератор отвергает форму вне грамматики: необъявленная переменная, тип, затенённая строка, чужое состояние."""
        lesson, part = "04-controller", "slot-release"
        text = form_path(ROOT, lesson, part).read_text(encoding="utf-8")
        bad = {
            "undeclared": text.replace('fate == "release"', 'fate2 == "release"'),
            "type": text.replace('fate == "release"', 'fate == 1'),
            "shadowed": text.replace('reply == "blocked"', 'reply == "conflict"'),
            "state": text.replace("\tP/04-R041\n", "\tP/04-R041\n", 1).replace("\twriting\tP/04-R041", "\tnowhere\tP/04-R041", 1),
            "action": text.replace('result("hung", "")', 'shout("hung")'),
            "args": text.replace('result("hung", "")', 'result("hung")'),
        }
        for name, t in bad.items():
            with self.subTest(refusal=name):
                root = self.tmp / f"r-{name}"
                fp = form_path(root, lesson, part)
                fp.parent.mkdir(parents=True)
                shutil.copy(ROOT / "Platform/lessons.tsv", root / "Platform/lessons.tsv")
                fp.write_text(t, encoding="utf-8")
                done = gen(lesson, root / "out", root, [part])
                self.assertNotEqual(done.returncode, 0, f"{name}: accepted")
                self.assertIn("gen_machine:", done.stderr)


if __name__ == "__main__":
    unittest.main()
