"""Judge process-input flags (P/03/P/04 environment and positionals, ADR-0125 addendum 5) with an independent form model. Select process from commands; consume positionals in form order and refuse extra words. Environment presence includes empty values; string permits any value, dir/file require nonempty, number requires finite decimal. P/06 command flags accept --x/--x=v and bool true/false; foreign/repeated flags refuse by name. Evaluate required, then bad through cel_expr_python over supplied f/cmd, then literal defaults. Random environments vary sample values and equal/different aliases. Compare Go Parse refusal names or Given/field values with the model; bad/default/wrong-command mutants must fail. Require freshness; run with CEL and Go 1.22."""
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
LESSONS = {"03-worker": "p03", "04-controller": "p04", "05-resource": "p05", "06-console": "p06", "09-agent": "p09"}
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
        flags = {r["flag"]: r for r in rows if r["flag"].startswith("--") and cmd in r["commands"]}
        given, words, k = {}, [], 0
        while k < len(args):                  # P/06 command flags: --x/--x=v; a non-bool without '=' consumes the next word.
            w = args[k]
            k += 1
            if not w.startswith("--"):
                words.append(w)
                continue
            name, eq, value = w.partition("=")
            if name not in flags:
                return {"refused": name}
            if not eq:
                if flags[name]["type"] == "bool":
                    value = "true"
                elif k == len(args):
                    return {"refused": name}
                else:
                    value, k = args[k], k + 1
            if name in given:
                return {"refused": name}
            given[name] = value
        args = words
        if len(args) > len(pos):
            return {"refused": args[len(pos)]}
        given.update(zip(pos, args))
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
            if r["type"] == "bool":
                if raw not in ("true", "false"):
                    return {"refused": r["flag"]}
                f[r["flag"]] = raw == "true"
            elif r["type"] == "number":
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
            if cmd in r["commands"] and r["flag"] not in f and r["default"] != "-" and r["type"] != "bool":
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
    flags = [r["flag"] for r in form.rows if r["flag"].startswith("--")]
    out = []
    if {"RELAY_URL", "RELAY_MEMBER"} <= set(names):
        # The P/09 conditional peer name needs an HTTPS road. Generic random
        # strings cannot exercise that predicate or its comma-list boundary.
        cmd = next(r["commands"][0] for r in form.rows if r["flag"] == "$RELAY_MEMBER")
        env = {r["flag"][1:]: ("1" if r["type"] == "number" else "/data" if r["type"] in ("dir", "file") else "a")
               for r in form.rows if r["flag"].startswith("$") and r["required"] == "true" and cmd in r["commands"]}
        for url in ("http://relay-a", "https://relay-a", "http://relay-a,https://relay-b"):
            for member in (None, "", "relay-member"):
                supplied = dict(env, RELAY_URL=url)
                if member is not None:
                    supplied["RELAY_MEMBER"] = member
                out.append((cmd, [], supplied))
    for _ in range(n):
        cmd = rnd.choice(form.procs + (["nosuch"] if rnd.random() < 0.03 else []))
        args = [rnd.choice(VALUES) for _ in range(rnd.choice([0, 0, 1, 1, 2]))]
        for fl in flags:                               # Command flags with/without '=', duplicates and foreign flags.
            if rnd.random() < 0.6:
                args.insert(rnd.randint(0, len(args)), rnd.choice([fl, fl, fl + "=true", fl + "=false", fl + "=yes", fl + "=1", fl + "=TRUE"]))
        if flags and rnd.random() < 0.05:
            args.append(rnd.choice(["--nosuch", flags[0]]))
        env = {}
        for name in names:
            if rnd.random() < 0.35:
                env[name] = rnd.choice(VALUES)
        if rnd.random() < 0.5:                       # Alias pairs with equal values.
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

    def test_p06_instance_input(self):
        """Absent/empty lets the caller compute the instance; supplied accepted spelling is preserved; no new CLI."""
        given = "box-a:00042:AbCdEf"
        cases = [("console", [], {}), ("console", [], {"INSTANCE_ID": ""}),
                 ("console", [], {"INSTANCE_ID": given}),
                 ("console", [], {"INSTANCE_ID": '\u0443\u0437\u0435\u043b:00042:AbCdEf'}),
                 ("cleanup-window", ["--writers-stopped"], {"INSTANCE_ID": given}),
                 ("console", ["--instance-id=" + given], {})]
        cases = [(cmd, args, dict(env, CONSOLE_ROOT="/tmp/p06-ui") if cmd == "console" else env)
                 for cmd, args, env in cases]
        got = run_driver(self.mods["06-console"], cases)
        self.assertEqual(len(got), len(cases))
        for i in range(5):
            self.assertIsNone(got[i]["refused"], got[i])
        self.assertNotIn("$INSTANCE_ID", got[0]["given"])
        self.assertIn("$INSTANCE_ID", got[1]["given"])
        self.assertNotIn("InstanceID", got[0]["values"])
        self.assertNotIn("InstanceID", got[1]["values"])
        self.assertEqual(got[2]["values"]["InstanceID"], given)
        self.assertEqual(got[3]["values"]["InstanceID"], '\u0443\u0437\u0435\u043b:00042:AbCdEf')
        self.assertNotIn("$INSTANCE_ID", got[4]["given"])
        self.assertNotIn("InstanceID", got[4]["values"])
        self.assertEqual(got[5]["refused"], "--instance-id")

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
                for k, r in enumerate(form.rows):      # Every form check must fire at least once.
                    if r["bad"] and r["flag"].startswith("--"):
                        self.assertIn(r["flag"], outcomes, f"{lesson}: probes never refuse {r['flag']}")
                    elif r["bad"]:                      # Symmetric aliases: refusal names the first, while the condition covers both.
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
                    continue                                # Compilation failure kills the mutant.
                self.assertTrue(disagree(model, cases, got), f"{name} survives")

    def test_mutants_command_flags(self):
        """P/06 input-adjacent command flags: foreign flags, non-bool words, repetition and bad refusals must fail."""
        rnd = random.Random(6)
        lesson = "06-console"
        form = Form(ROOT / "Platform" / lesson / "forms/daemon-flags.tsv")
        model = Model(form)
        cases = probes(form, rnd, 3000)
        src = (self.mods[lesson] / "flags/flags.go").read_text()
        muts = {
            "unknown-accepted": src.replace('return nil, refuse(name, "not a flag of the process")', 'continue', 1),
            "bool-word": src.replace('(raw != "true" && raw != "false")', 'false', 1),
            "twice": src.replace('if _, twice := given[name]; twice {', 'if false {', 1),
            "bad-dropped": src.replace('if in.Given["--writers-stopped"] && isTrue(bad', 'if false && isTrue(bad', 1),
        }
        for name, text in muts.items():
            with self.subTest(mutant=name):
                self.assertNotEqual(text, src, f"{name}: the mutant does not apply")
                mod = self.tmp / f"mut06-{name}"
                shutil.copytree(self.mods[lesson], mod)
                (mod / "flags/flags.go").write_text(text)
                try:
                    got = run_driver(mod, cases)
                except AssertionError:
                    continue
                self.assertTrue(disagree(model, cases, got), f"{name} survives")

    def test_constants(self):
        """Independently read runtime-constants.tsv and compare every flags const/Constants name, value, unit, norm with its row. Verify norm anchors and reject corrupted forms."""
        for lesson, slug in LESSONS.items():
            form = ROOT / "Platform" / lesson / "forms/runtime-constants.tsv"
            got = self.mods[lesson] / "flags/constants.go"
            self.assertEqual(form.is_file(), got.is_file(), lesson)
            if not form.is_file():
                continue
            lines = [ln for ln in form.read_text(encoding="utf-8").split("\n") if ln and not ln.startswith("#")]
            rows = [dict(zip(lines[0].split("\t"), ln.split("\t"))) for ln in lines[1:]]
            norms = "".join(p.read_text(encoding="utf-8")
                            for p in (ROOT / "Platform" / lesson / "spec").glob("*.norms.md"))
            text = got.read_text(encoding="utf-8")
            consts = dict(re.findall(r"^\t(\w+) = ([0-9]+)$", text, re.M))
            table = {m[0]: (int(m[1]), m[2], m[3])
                     for m in re.findall(r'^\t"(\w+)":\s+\{([0-9]+), "(\w+)", "([^"]+)"\},$', text, re.M)}
            self.assertEqual(len(consts), len(rows), lesson)
            self.assertEqual(len(table), len(rows), lesson)
            for r in rows:
                self.assertEqual(consts.get(field("$" + r["name"])), r["value"], r["name"])
                self.assertEqual(table.get(r["name"]), (int(r["value"]), r["unit"], r["norm"]), r["name"])
                self.assertIn(f"<!-- req: {r['norm']} -->", norms, r["name"])
            src = form.read_text(encoding="utf-8")
            first = rows[0]
            row = "\t".join(first[k] for k in ("name", "value", "unit", "norm", "meaning"))
            bad = {"value-zero": row.replace(f"\t{first['value']}\t", "\t0\t", 1),
                   "value-quoted": row.replace(f"\t{first['value']}\t", f'\t"{first["value"]}"\t', 1),
                   "unit": row.replace(f"\t{first['unit']}\t", "\tms\t", 1),
                   "norm": row.replace(f"\t{first['norm']}\t", "\tP/06.1-R999\t", 1),
                   "name": row.replace(first["name"], first["name"].lower(), 1),
                   "repeat": row + "\n" + row}
            for name, new in bad.items():
                with self.subTest(lesson=lesson, form=name):
                    d = self.tmp / f"bad-{name}" / "forms"
                    shutil.copytree(form.parent, d, dirs_exist_ok=True)
                    spec = d.parent / "spec"
                    if not spec.exists():
                        shutil.copytree(form.parent.parent / "spec", spec)
                    (d / "runtime-constants.tsv").write_text(src.replace(row, new, 1), encoding="utf-8")
                    done = subprocess.run([sys.executable, str(HERE / "gen_flags.py"), "--lesson", lesson,
                                           str(d / "daemon-flags.tsv"), str(self.tmp / f"out-{name}")],
                                          capture_output=True, text=True)
                    self.assertNotEqual(done.returncode, 0, f"{name}: accepted")
                    self.assertIn("runtime-constants.tsv", done.stderr, name)


if __name__ == "__main__":
    unittest.main()
