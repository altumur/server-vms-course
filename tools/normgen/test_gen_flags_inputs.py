"""Судья части flags в режиме входов процесса (gen_flags.py; P/03, P/04 — $ОКРУЖЕНИЕ и <позиционный>; ADR-0125 доп. (5)).

Запуск: /opt/check-env/lesson-spec/bin/python tools/normgen/test_gen_flags_inputs.py [-v]   (cel_expr_python, go 1.22)

Своя модель формы судьи: процесс из колонки commands; позиционные <arg> по порядку формы (лишнее слово — отказ этим
словом); $NAME — присутствие в окружении (пустое значение — тоже дано); тип string — любое значение, dir/file — непустое,
number — конечная десятичная запись; required (true | CEL), затем bad (CEL над f — данные значения — и cmd, оракул
cel_expr_python), затем литеральные умолчания. Пробы — случайные окружения со значениями из словаря судьи (пары
псевдонимов — то равные, то разные); исход Go Parse (отказ — имя входа; иначе Given и значения полей) — равен модели.
Мутанты выхода (обрезанная проверка bad, потерянное умолчание, позиционный не той командой) — красные. out свежий.
"""
import json
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
LESSONS = {"03-worker": "p03", "04-controller": "p04"}
GOENV = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off", GOTOOLCHAIN="local")
NUMBER = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?")
VALUES = ["", "a", "srv-a", "Bad_Name", "srv--a", "900", "1.5", "-3", "1e3", "0x10", "/data/x", "file:///x",
          "Europe/Moscow", "UTC", "bad zone", "w-1"]


def field(name):
    initialisms = {"id": "ID", "api": "API", "tls": "TLS"}
    return "".join(initialisms.get(w, w[:1].upper() + w[1:]) for w in re.split(r"[_-]", name.strip("$<>").lower()))


class Form:
    def __init__(self, path):
        lines = [ln for ln in path.read_text(encoding="utf-8").split("\n") if ln and not ln.startswith("#")]
        cols = lines[0].split("\t")
        self.rows = [dict(zip(cols, ln.split("\t"))) for ln in lines[1:]]
        for r in self.rows:
            r["commands"] = r["commands"].split(",")
        self.procs = list(dict.fromkeys(c for r in self.rows for c in r["commands"]))


class Model:
    def __init__(self, form):
        from cel_expr_python import cel
        self.cel, self.form = cel, form
        T = cel.Type
        cfg = cel.NewEnvConfigFromYaml("name: inputs\nextensions:\n  - name: strings\n")
        self.env = cel.NewEnv(config=cfg, variables={"f": T.Map(T.STRING, T.DYN), "cmd": T.STRING})
        self.exprs = {}
        for k, r in enumerate(form.rows):
            for col in ("required", "bad"):
                if r[col] and r[col] not in ("true", "false"):
                    self.exprs[k, col] = self.env.compile(r[col])

    def cel_true(self, k, col, f, cmd):
        v = self.exprs[k, col].eval(data={"f": f, "cmd": cmd})
        return v.type() != self.cel.Type.ERROR and v.plain_value() is True

    def run(self, cmd, args, environ):
        rows = self.form.rows
        if cmd not in self.form.procs:
            return {"refused": cmd}
        pos = [r["flag"] for r in rows if r["flag"].startswith("<") and cmd in r["commands"]]
        if len(args) > len(pos):
            return {"refused": args[len(pos)]}
        given = dict(zip(pos, args))
        for r in rows:
            if r["flag"].startswith("$") and cmd in r["commands"] and r["flag"][1:] in environ:
                given[r["flag"]] = environ[r["flag"][1:]]
        f, values = {}, {}
        for r in rows:
            if r["flag"] not in given:
                continue
            raw = given[r["flag"]]
            if r["type"] in ("dir", "file", "path") and raw == "":
                return {"refused": r["flag"]}
            if r["type"] == "number":
                if not NUMBER.fullmatch(raw):
                    return {"refused": r["flag"]}
                f[r["flag"]] = float(raw)
            else:
                f[r["flag"]] = raw
            values[field(r["flag"])] = f[r["flag"]]
        for k, r in enumerate(rows):
            if cmd in r["commands"] and r["flag"] not in f and r["required"] != "false":
                if r["required"] == "true" or self.cel_true(k, "required", f, cmd):
                    return {"refused": r["flag"]}
        for k, r in enumerate(rows):
            if r["bad"] and r["flag"] in f and self.cel_true(k, "bad", f, cmd):
                return {"refused": r["flag"]}
        for r in rows:
            if cmd in r["commands"] and r["flag"] not in f and r["default"] != "-":
                values[field(r["flag"])] = float(r["default"]) if r["type"] == "number" else r["default"]
        return {"refused": None, "given": sorted(f), "values": values}


DRIVER = r'''package main

import (
	"bufio"
	"encoding/json"
	"os"
	"reflect"
	"sort"

	"%s/flags"
)

func main() {
	sc := bufio.NewScanner(os.Stdin)
	sc.Buffer(make([]byte, 1<<20), 1<<20)
	enc := json.NewEncoder(os.Stdout)
	for sc.Scan() {
		var c struct {
			Cmd  string
			Args []string
			Env  map[string]string
		}
		if err := json.Unmarshal(sc.Bytes(), &c); err != nil {
			panic(err)
		}
		in, ref := flags.Parse(c.Cmd, c.Args, func(k string) (string, bool) { v, ok := c.Env[k]; return v, ok })
		if ref != nil {
			enc.Encode(map[string]any{"refused": ref.Flag})
			continue
		}
		given := []string{}
		for k := range in.Given {
			given = append(given, k)
		}
		sort.Strings(given)
		values := map[string]any{}
		v := reflect.ValueOf(*in)
		for i := 0; i < v.NumField(); i++ {
			name := v.Type().Field(i).Name
			if name == "Cmd" || name == "Given" || v.Field(i).IsZero() {
				continue
			}
			values[name] = v.Field(i).Interface()
		}
		enc.Encode(map[string]any{"refused": nil, "given": given, "values": values})
	}
}
'''


def probes(form, rnd, n):
    names = [r["flag"][1:] for r in form.rows if r["flag"].startswith("$")]
    out = []
    for _ in range(n):
        cmd = rnd.choice(form.procs + (["nosuch"] if rnd.random() < 0.03 else []))
        args = [rnd.choice(VALUES) for _ in range(rnd.choice([0, 0, 1, 1, 2]))]
        env = {}
        for name in names:
            if rnd.random() < 0.35:
                env[name] = rnd.choice(VALUES)
        if rnd.random() < 0.5:                       # пары псевдонимов: равные значения
            for a, b in (("OBJECTS", "PLATFORM_OBJECTS"), ("RESOURCE_ROOT", "EVENTS")):
                if a in env and rnd.random() < 0.7:
                    env[b] = env[a]
        out.append((cmd, args, env))
    return out


def run_driver(mod, cases):
    d = Path(mod) / "cmd/judgeinputs"
    d.mkdir(parents=True, exist_ok=True)
    module = (Path(mod) / "go.mod").read_text().split("\n")[0].split()[1]
    (d / "main.go").write_text(DRIVER % module)
    stdin = "".join(json.dumps({"Cmd": c, "Args": a, "Env": e}) + "\n" for c, a, e in cases)
    done = subprocess.run(["go", "run", "./cmd/judgeinputs"], cwd=mod, input=stdin, capture_output=True, text=True,
                          env=GOENV)
    if done.returncode:
        raise AssertionError(done.stderr[-2000:])
    return [json.loads(x) for x in done.stdout.split("\n") if x]


def disagree(model, cases, got):
    bad = []
    for (cmd, args, env), g in zip(cases, got):
        want = model.run(cmd, args, env)
        if want["refused"] is not None or g.get("refused") is not None:
            if want["refused"] != g.get("refused"):
                bad.append((cmd, args, env, want, g))
            continue
        if want["given"] != g["given"] or {k: v for k, v in want["values"].items() if v not in ("", 0.0)} != g["values"]:
            bad.append((cmd, args, env, want, g))
    return bad


class InputFlags(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("go"):
            raise unittest.SkipTest("go is not in PATH")
        try:
            import cel_expr_python  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("no cel_expr_python")
        cls.tmp = Path(tempfile.mkdtemp(prefix="judge-inputs-"))
        cls.mods = {}
        for lesson, slug in LESSONS.items():
            out = cls.tmp / slug
            done = subprocess.run([sys.executable, str(HERE / "gen_flags.py"), "--lesson", lesson,
                                   str(ROOT / "Platform" / lesson / "forms/daemon-flags.tsv"), str(out)],
                                  capture_output=True, text=True)
            if done.returncode:
                raise AssertionError(done.stderr)
            cls.mods[lesson] = out / "go"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_fresh(self):
        for lesson, slug in LESSONS.items():
            for p in sorted((self.mods[lesson] / "flags").iterdir()):
                kept = HERE / "out" / slug / "go/flags" / p.name
                self.assertTrue(kept.is_file(), f"{kept} missing")
                self.assertEqual(kept.read_bytes(), p.read_bytes(), f"{kept} is stale: run gen_flags.py --lesson {lesson}")

    def test_oracle(self):
        rnd = random.Random(20261105)
        for lesson in LESSONS:
            with self.subTest(lesson=lesson):
                form = Form(ROOT / "Platform" / lesson / "forms/daemon-flags.tsv")
                model = Model(form)
                cases = probes(form, rnd, 4000)
                got = run_driver(self.mods[lesson], cases)
                self.assertEqual(len(got), len(cases))
                bad = disagree(model, cases, got)
                self.assertEqual(bad[:2], [], f"{lesson}: {len(bad)} of {len(cases)} disagree")
                outcomes = {model.run(*c)["refused"] for c in cases}
                for k, r in enumerate(form.rows):      # каждая проверка формы сработала хоть раз
                    if r["bad"]:                        # симметричные псевдонимы: отказ берёт первый, условие — оба
                        hit = any(model.cel_true(k, "bad", {"$" + n: v for n, v in e.items()}, c)
                                  for c, _, e in cases if r["flag"][1:] in e)
                        self.assertTrue(hit, f"{lesson}: bad of {r['flag']} is never true on the probes")
                    elif r["required"] != "false" or r["type"] in ("dir", "file", "number"):
                        self.assertIn(r["flag"], outcomes, f"{lesson}: probes never refuse {r['flag']}")

    def test_mutants(self):
        rnd = random.Random(3)
        lesson = "04-controller"
        form = Form(ROOT / "Platform" / lesson / "forms/daemon-flags.tsv")
        model = Model(form)
        cases = probes(form, rnd, 3000)
        src = (self.mods[lesson] / "flags/flags.go").read_text()
        muts = {
            "bad-dropped": src.replace('if in.Given["$OBJECTS"] && isTrue(bad', 'if false && in.Given["$OBJECTS"] && isTrue(bad', 1),
            "default-lost": src.replace('in.HungMoveAfter = float64(900)', 'in.HungMoveAfter = float64(0)', 1),
            "positional-cmd": src.replace('positional = append(positional, "<sub>")', '', 1),
            "required-dropped": src.replace('!in.Given["<sub>"] {', '!in.Given["<sub>"] && false {', 1),
        }
        for name, text in muts.items():
            with self.subTest(mutant=name):
                self.assertNotEqual(text, src, f"{name}: the mutant does not apply")
                mod = self.tmp / f"mut-{name}"
                shutil.copytree(self.mods[lesson], mod)
                (mod / "flags/flags.go").write_text(text)
                try:
                    got = run_driver(mod, cases)
                except AssertionError:
                    continue                                # не собрался — убит
                self.assertTrue(disagree(model, cases, got), f"{name} survives")


if __name__ == "__main__":
    unittest.main()
