"""Judge process-input flags (P/03/P/04 environment and positionals, ADR-0125 addendum 5) with an independent form model. Select process from commands; consume positionals in form order and refuse extra words. Environment presence includes empty values; string permits any value, dir/file require nonempty, number requires finite decimal. P/06 command flags accept --x/--x=v and bool true/false; foreign/repeated flags refuse by name. Evaluate required, then bad through cel_expr_python over supplied f/cmd, then literal defaults. Random environments vary sample values and equal/different aliases. Compare Go Parse refusal names or Given/field values with the model; bad/default/wrong-command mutants must fail. Require freshness; run with CEL and Go 1.22."""
import lesson as output_lesson
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
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
	"fmt"
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
			ID   int
			Cmd  string
			Args []string
			Env  map[string]string
		}
		if err := json.Unmarshal(sc.Bytes(), &c); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(2)
		}
		if c.ID < 1 {
			fmt.Fprintln(os.Stderr, "missing service request identity")
			os.Exit(2)
		}
		in, ref := flags.Parse(c.Cmd, c.Args, func(k string) (string, bool) { v, ok := c.Env[k]; return v, ok })
		if ref != nil {
			if err := enc.Encode(map[string]any{"id": c.ID, "refused": ref.Flag}); err != nil {
				fmt.Fprintln(os.Stderr, err)
				os.Exit(2)
			}
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
		if err := enc.Encode(map[string]any{"id": c.ID, "refused": nil, "given": given, "values": values}); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(2)
		}
	}
	if err := sc.Err(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
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


class CheckingError(RuntimeError):
    """A failed check is never evidence that a semantic mutant was killed."""


def response_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise CheckingError(f"duplicate service JSON key: {key}")
        out[key] = value
    return out


def response_constant(word):
    raise CheckingError(f"non-JSON service constant: {word}")


def checked_answers(cases, got):
    """Validate the entire internal report before consulting the semantic oracle."""
    if not cases or type(got) is not list or len(got) != len(cases):
        raise CheckingError("nonempty, complete service response required")
    for identity, answer in enumerate(got, 1):
        if type(answer) is not dict or type(answer.get("id")) is not int or answer["id"] != identity:
            raise CheckingError(f"service response identity/order: expected {identity}")
        if "refused" not in answer or not (answer["refused"] is None or type(answer["refused"]) is str):
            raise CheckingError(f"service response {identity}: invalid refused field")
        keys = {"id", "refused"} if answer["refused"] is not None else {"id", "refused", "given", "values"}
        if set(answer) != keys:
            raise CheckingError(f"service response {identity}: incomplete or extra fields")
        if answer["refused"] is None:
            given, values = answer["given"], answer["values"]
            if (type(given) is not list or any(type(k) is not str for k in given)
                    or given != sorted(set(given)) or type(values) is not dict
                    or any(type(k) is not str or type(v) not in (str, bool, int, float)
                           for k, v in values.items())):
                raise CheckingError(f"service response {identity}: invalid given/values shape")
        try:
            json.dumps(answer, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (UnicodeError, ValueError, TypeError) as exc:
            raise CheckingError(f"service response {identity}: invalid JSON scalar") from exc
    return got


def run_driver(mod, cases):
    if not cases:
        raise CheckingError("nonempty service input required")
    try:
        d = Path(mod) / "cmd/judgeinputs"
        d.mkdir(parents=True, exist_ok=True)
        module = (Path(mod) / "go.mod").read_text(encoding="utf-8").split("\n")[0].split()[1]
        (d / "main.go").write_text(DRIVER % module, encoding="utf-8")
        stdin = "".join(json.dumps({"ID": i, "Cmd": c, "Args": a, "Env": e}, allow_nan=False) + "\n"
                        for i, (c, a, e) in enumerate(cases, 1))
        done = subprocess.run(["go", "run", "./cmd/judgeinputs"], cwd=mod, input=stdin, capture_output=True,
                              text=True, encoding="utf-8", env=GOENV, timeout=120)
    except (OSError, UnicodeError, ValueError, IndexError, subprocess.TimeoutExpired) as exc:
        raise CheckingError(f"service preparation/start/read: {exc}") from exc
    if done.returncode:
        raise CheckingError(f"service Go/exit {done.returncode}: {done.stderr[-2000:]}")
    try:
        if type(done.stdout) is not str or not done.stdout.endswith("\n"):
            raise CheckingError("service response must end with LF")
        lines = done.stdout[:-1].split("\n")
        if any(not line for line in lines):
            raise CheckingError("empty service response record")
        got = [json.loads(line, object_pairs_hook=response_object, parse_constant=response_constant)
               for line in lines]
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise CheckingError(f"service response JSON: {exc}") from exc
    return checked_answers(cases, got)


def disagree(model, cases, got):
    checked_answers(cases, got)
    bad = []
    for (cmd, args, env), g in zip(cases, got):
        want = model.run(cmd, args, env)
        if want["refused"] is not None or g.get("refused") is not None:
            if want["refused"] != g.get("refused"):
                bad.append((cmd, args, env, want, g))
            continue
        values = {k: v for k, v in want["values"].items() if v not in ("", 0.0)}
        if (want["given"] != g["given"] or values != g["values"]
                or any((type(v) is bool) != (type(g["values"].get(k)) is bool) for k, v in values.items())):
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
                raise CheckingError(done.stderr)
            cls.mods[lesson] = out / "go"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_fresh(self):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        for lesson, slug in LESSONS.items():
            for p in sorted((self.mods[lesson] / "flags").iterdir()):
                kept = output_lesson.output_root() / slug / "go/flags" / p.name
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
                got = run_driver(mod, cases)
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
                got = run_driver(mod, cases)
                self.assertTrue(disagree(model, cases, got), f"{name} survives")

    def test_driver_unicode_and_refusal(self):
        """Actual driver preserves scalar strings and distinct identities, including an empty refused command."""
        value = "a\u2028b\u2029c\u044f\U0001f642\nend"
        got = run_driver(self.mods["05-resource"], [("resource", [], {"BUILD": value}), ("", [], {})])
        self.assertEqual([r["id"] for r in got], [1, 2])
        self.assertEqual(got[0]["values"]["Build"], value)
        self.assertEqual(got[1], {"id": 2, "refused": ""})

    def test_driver_scanner_error_is_not_partial_success(self):
        """Scanner failure after a valid prefix is an execution error, not one successful response."""
        mod = self.mods["05-resource"]
        self.assertEqual(len(run_driver(mod, [("resource", [], {"BUILD": "x" * (1 << 17)})])), 1)
        with self.assertRaisesRegex(CheckingError, "service Go/exit"):
            run_driver(mod, [("resource", [], {}), ("resource", [], {"BUILD": "x" * (1 << 20)})])

    def test_driver_encoder_error(self):
        """Compile the actual driver with a closed stdout fixture; ignored Encode errors would exit zero."""
        mod = self.tmp / "encoder-control"
        shutil.copytree(self.mods["05-resource"], mod)
        d = mod / "cmd/judgeinputs"
        d.mkdir(parents=True, exist_ok=True)
        (d / "closed_stdout.go").write_text('''package main
import "os"
func init() {
    f, err := os.CreateTemp("", "judge-closed-stdout-")
    if err != nil { panic(err) }
    name := f.Name()
    f.Close()
    os.Remove(name)
    os.Stdout = f
}
''', encoding="utf-8")
        with self.assertRaisesRegex(CheckingError, "service Go/exit"):
            run_driver(mod, [("resource", [], {})])

    def test_mutant_callers_do_not_swallow_errors(self):
        """Both original mutation loops must propagate checking failures, including a legacy assertion."""
        for method in ("test_mutants", "test_mutants_command_flags"):
            for error in (CheckingError("injected checking error"), AssertionError("injected legacy failure")):
                with self.subTest(method=method, error=type(error).__name__):
                    subject = InputFlags(method)
                    subject.mods = self.mods
                    subject.tmp = self.tmp / f"caller-{method}-{type(error).__name__}"
                    subject.tmp.mkdir()
                    with mock.patch(__name__ + ".run_driver", side_effect=error), \
                            mock.patch(__name__ + ".disagree") as compare:
                        with self.assertRaises(type(error)):
                            getattr(subject, method)()
                        compare.assert_not_called()

    def test_constants(self):
        """Independently read runtime-constants.tsv and compare every flags const/Constants name, value, unit, norm with its row. Verify norm anchors and reject corrupted forms."""
        for lesson, slug in LESSONS.items():
            form = ROOT / "Platform" / lesson / "forms/runtime-constants.tsv"
            got = self.mods[lesson] / "flags/constants.go"
            self.assertEqual(form.is_file(), got.is_file(), lesson)
            if not form.is_file():
                continue
            rows = ConstantSubjectControls.assert_subject(self, ROOT, lesson, got.read_text(encoding="utf-8"))
            src = form.read_text(encoding="utf-8")
            first = rows[0]
            row = "\t".join(first[k] for k in ("name", "value", "unit", "norm", "meaning"))
            bad = {"value-zero": row.replace(f"\t{first['value']}\t", "\t0\t", 1),
                   "value-quoted": row.replace(f"\t{first['value']}\t", f'\t"{first["value"]}"\t', 1),
                   "unit": row.replace(f"\t{first['unit']}\t", "\tunknown\t", 1),
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


class ServiceReports(unittest.TestCase):
    """Independent internal transport controls; these do not simulate a course implementation."""

    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix="flags-service-")
        self.addCleanup(self.work.cleanup)
        self.mod = Path(self.work.name)
        (self.mod / "go.mod").write_text("module judge/service\n\ngo 1.22\n", encoding="utf-8")
        # Equal inputs still require distinct ordinal identities.
        self.cases = [("resource", [], {}), ("resource", [], {})]

    @staticmethod
    def answer(identity, **changes):
        return dict({"id": identity, "refused": None, "given": [], "values": {}}, **changes)

    def responses(self):
        return [self.answer(1), self.answer(2)]

    def invoke(self, text):
        done = subprocess.CompletedProcess([], 0, text, "")
        with mock.patch.object(subprocess, "run", return_value=done):
            return run_driver(self.mod, self.cases)

    def refuse_before_oracle(self, got):
        model = mock.Mock()
        with self.assertRaises(CheckingError):
            disagree(model, self.cases, got)
        model.run.assert_not_called()

    def test_complete_and_unicode_neighbours(self):
        word = "a\u2028b\u2029c\u044f\U0001f642"
        got = [self.answer(1, given=["$BUILD"], values={"Build": word}), {"id": 2, "refused": ""}]
        for escaped in (False, True):
            with self.subTest(escaped=escaped):
                text = "".join(json.dumps(r, ensure_ascii=escaped) + "\n" for r in got)
                self.assertEqual(self.invoke(text), got)
        model = mock.Mock()
        model.run.return_value = {"refused": None, "given": [], "values": {}}
        self.assertEqual(disagree(model, self.cases, self.responses()), [])
        self.assertEqual(model.run.call_count, 2)

    def test_cardinality_before_oracle(self):
        for got in ([], self.responses()[:1], self.responses() + [self.answer(3)]):
            with self.subTest(count=len(got)):
                self.refuse_before_oracle(got)
        for got in (None, {}, tuple(self.responses())):
            with self.subTest(outer=type(got).__name__):
                self.refuse_before_oracle(got)
        with self.assertRaises(CheckingError):
            checked_answers([], [])
        with mock.patch.object(subprocess, "run") as process:
            with self.assertRaises(CheckingError):
                run_driver(self.mod, [])
            process.assert_not_called()

    def test_identity_order_duplicates_and_types(self):
        for identity in (None, True, 1.0, "1", 0, 3):
            with self.subTest(identity=identity):
                self.refuse_before_oracle([self.answer(identity), self.answer(2)])
        missing = self.answer(1)
        del missing["id"]
        for got in ([missing, self.answer(2)], [self.answer(1), self.answer(1)],
                    [self.answer(2), self.answer(1)]):
            self.refuse_before_oracle(got)

    def test_report_shapes(self):
        bad = [None, [], {"id": 1}, self.answer(1, extra=0), self.answer(1, refused=True),
               {"id": 1, "refused": None, "given": []},
               self.answer(1, given="x"), self.answer(1, given=[False]),
               self.answer(1, given=["a", "a"]), self.answer(1, given=["b", "a"]),
               self.answer(1, values=[]), self.answer(1, values={"X": None}),
               self.answer(1, values={"X": []}), self.answer(1, values={"X": {}}),
               self.answer(1, values={"X": float("inf")}), self.answer(1, values={"X": "\ud800"})]
        for n, first in enumerate(bad):
            with self.subTest(shape=n):
                self.refuse_before_oracle([first, self.answer(2)])

    def test_json_and_lf_errors(self):
        good = json.dumps(self.answer(1)) + "\n"
        tail = json.dumps(self.answer(2)) + "\n"
        bad = ["", good + tail.rstrip("\n"), good.rstrip("\n") + tail.rstrip("\n"),
               good + "\n" + tail, good + "{bad\n",
               '{"id":1,"id":1,"refused":null,"given":[],"values":{}}\n' + tail,
               good + '"not an object"\n', good + '{} trailing\n']
        for number in ("NaN", "Infinity", "1e400"):
            bad.append('{"id":1,"refused":null,"given":[],"values":{"X":' + number + '}}\n' + tail)
        for n, text in enumerate(bad):
            with self.subTest(frame=n), self.assertRaises(CheckingError):
                self.invoke(text)

    def test_process_failures(self):
        failures = [OSError("cannot start Go"), subprocess.TimeoutExpired(["go"], 120),
                    UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid transport UTF-8")]
        for error in failures:
            with self.subTest(error=type(error).__name__), \
                    mock.patch.object(subprocess, "run", side_effect=error), self.assertRaises(CheckingError):
                run_driver(self.mod, self.cases)
        for code in (1, 2, -15):
            done = subprocess.CompletedProcess([], code, json.dumps(self.answer(1)) + "\n", "compiler/runtime error")
            with self.subTest(code=code), mock.patch.object(subprocess, "run", return_value=done), \
                    self.assertRaisesRegex(CheckingError, "service Go/exit"):
                run_driver(self.mod, self.cases)

    def test_preparation_errors(self):
        for text in ("", "module", "\ud800"):
            with self.subTest(module=text):
                if text == "\ud800":
                    (self.mod / "go.mod").write_bytes(b"\xff")
                else:
                    (self.mod / "go.mod").write_text(text, encoding="utf-8")
                with self.assertRaises(CheckingError):
                    run_driver(self.mod, self.cases)
        (self.mod / "go.mod").unlink()
        with self.assertRaises(CheckingError):
            run_driver(self.mod, self.cases)

    def test_generation_failure_type(self):
        class Subject(InputFlags):
            pass
        done = subprocess.CompletedProcess([], 1, "", "generation error")
        with mock.patch.object(shutil, "which", return_value="/test/go"), \
                mock.patch.dict(sys.modules, {"cel_expr_python": object()}), \
                mock.patch.object(tempfile, "mkdtemp", return_value=str(self.mod)), \
                mock.patch.object(subprocess, "run", return_value=done) as process:
            with self.assertRaisesRegex(CheckingError, "generation error"):
                Subject.setUpClass()
            self.assertEqual(process.call_args.args[0][:4],
                             [sys.executable, str(HERE / "gen_flags.py"), "--lesson", "03-worker"])

    def test_complete_semantic_mismatch_and_bool_neighbour(self):
        model = mock.Mock()
        model.run.return_value = {"refused": None, "given": [], "values": {"X": 1.0}}
        cases = self.cases[:1]
        self.assertEqual(disagree(model, cases, [self.answer(1, values={"X": 1})]), [])
        for got in (self.answer(1, values={"X": True}), self.answer(1, values={}), {"id": 1, "refused": "wrong"}):
            with self.subTest(answer=got):
                bad = disagree(model, cases, [got])
                self.assertEqual(len(bad), 1)
                self.assertEqual(bad[0][-1]["id"], 1)

    def test_request_identities_and_unchanged_input(self):
        done = subprocess.CompletedProcess([], 0, "".join(json.dumps(r) + "\n" for r in self.responses()), "")
        with mock.patch.object(subprocess, "run", return_value=done) as process:
            run_driver(self.mod, self.cases)
        inputs = [json.loads(line) for line in process.call_args.kwargs["input"].split("\n") if line]
        self.assertEqual([r.pop("ID") for r in inputs], [1, 2])
        self.assertEqual(inputs, [{"Cmd": c, "Args": a, "Env": e} for c, a, e in self.cases])
        self.assertEqual(process.call_args.args[0], ["go", "run", "./cmd/judgeinputs"])



class ConstantSubjectControls(unittest.TestCase):
    """Independent Source form/anchor expectations, including stored ms integers."""

    @staticmethod
    def assert_subject(test, root, lesson, text):
        root = Path(root)
        path = root / "Platform" / lesson / "forms/runtime-constants.tsv"
        lines = [line for line in path.read_text(encoding="utf-8").split("\n")
                 if line and not line.startswith("#")]
        test.assertTrue(lines, "nonempty runtime constant form required")
        head = ["name", "value", "unit", "norm", "meaning"]
        test.assertEqual(lines[0].split("\t"), head)
        cells = [line.split("\t") for line in lines[1:]]
        test.assertTrue(cells, "nonempty runtime constant roster required")
        test.assertTrue(all(len(row) == len(head) for row in cells))
        rows = [dict(zip(head, row)) for row in cells]
        test.assertEqual(len({row["name"] for row in rows}), len(rows), "duplicate source constant")
        norms = "".join(p.read_text(encoding="utf-8")
                        for p in (root / "Platform" / lesson / "spec").glob("*.norms.md"))
        const_matches = re.findall(r"^\t(\w+) = ([0-9]+)$", text, re.M)
        table_matches = re.findall(r'^\t"(\w+)":\s+\{([0-9]+), "(\w+)", "([^"]+)"\},$', text, re.M)
        test.assertEqual(len(const_matches), len(rows), "missing/extra/malformed const")
        test.assertEqual(len(table_matches), len(rows), "missing/extra/malformed metadata")
        consts = dict(const_matches)
        table = {m[0]: (int(m[1]), m[2], m[3]) for m in table_matches}
        test.assertEqual(len(consts), len(rows), "duplicate emitted const")
        test.assertEqual(len(table), len(rows), "duplicate emitted metadata")
        for row in rows:
            name = row["name"]
            test.assertRegex(name, r"^[A-Z][A-Z0-9_]*$")
            test.assertRegex(row["value"], r"^[1-9][0-9]*$")
            test.assertLessEqual(int(row["value"]), 9223372036854775807)
            test.assertIn(row["unit"], ("count", "s", "ms", "bytes"))
            test.assertEqual(consts.get(field("$" + name)), row["value"], name)
            test.assertEqual(table.get(name), (int(row["value"]), row["unit"], row["norm"]), name)
            test.assertIn(f"<!-- req: {row['norm']} -->", norms, name)
        return rows

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.lesson = "03-worker"
        path = self.root / "Platform" / self.lesson
        (path / "forms").mkdir(parents=True)
        (path / "spec").mkdir()
        self.form = path / "forms/runtime-constants.tsv"
        self.norm = path / "spec/test.norms.md"
        self.form.write_text("name\tvalue\tunit\tnorm\tmeaning\nGAP_MS\t317\tms\tP/test\tperiod\n")
        self.norm.write_text("<!-- req: P/test -->\n")
        self.output = '\tGapMs = 317\n\t"GAP_MS": {317, "ms", "P/test"},\n'

    def check(self, text=None):
        return self.assert_subject(self, self.root, self.lesson, self.output if text is None else text)

    def test_stored_ms_integer_and_coherent_source_change(self):
        self.check()
        self.form.write_text(self.form.read_text().replace("317", "319"))
        self.check(self.output.replace("317", "319"))

    def test_output_drift_missing_duplicate_extra_unit_and_scaling(self):
        for text in (self.output.replace("317", "318"), self.output.replace("317", "0.317"),
                     self.output.replace('"ms"', '"s"'), self.output.splitlines()[0] + "\n",
                     self.output + self.output, self.output + '\tExtra = 1\n', ""):
            with self.subTest(text=text), self.assertRaises(AssertionError):
                self.check(text)

    def test_source_only_drift_missing_duplicate_shape_type_unit_overflow_and_anchor(self):
        original = self.form.read_text()
        bad = [original.replace("317", word) for word in
               ("318", "true", "317.0", "0.317", "0317", "0", "9223372036854775808")]
        bad += [original.replace("\tms\t", "\tunknown\t"), original + original.splitlines()[1] + "\n",
                original.splitlines()[0] + "\n", original.replace("period", "period\textra")]
        for text in bad:
            self.form.write_text(text)
            with self.subTest(text=text), self.assertRaises(AssertionError):
                self.check()
        self.form.write_text(original)
        self.norm.write_text("")
        with self.assertRaises(AssertionError):
            self.check()

if __name__ == "__main__":
    unittest.main()
