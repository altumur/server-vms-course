"""Judge P/03 slot-capture and P/04 slot-fate/slot-release generators (ADR-0125 addendum 5). Require fresh output, vet and passing closed form tests. Independently reread #var/#const/rows, generate random/boundary inputs including settings, and evaluate conditions/arguments with cel_expr_python. Go Step must match the first state-row and typed arguments; argument integer overflow must error. Form mutants negate conditions, change next/string arguments or swap adjacent rows. Keep only mutants with an oracle-distinguishing input; their generated machine must fail original form tests. Run test_gen_machine.py with CEL and Go 1.22."""
import lesson as output_lesson
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


class CheckingError(RuntimeError):
    """An incomplete or failed check is neither a semantic mismatch nor a kill."""


def complete_reports(text, count):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise CheckingError(f"duplicate report key: {key}")
            result[key] = value
        return result

    try:
        def nonfinite(value):
            raise CheckingError(f"non-JSON number in driver report: {value}")
        rows = [json.loads(line, object_pairs_hook=unique, parse_constant=nonfinite)
                for line in text.splitlines() if line]
    except (ValueError, TypeError) as exc:
        raise CheckingError(f"malformed driver report: {exc}") from exc
    if type(count) is not int or count <= 0 or len(rows) != count:
        raise CheckingError(f"incomplete driver report: {len(rows)}/{count}")
    for i, row in enumerate(rows):
        if type(row) is not dict or type(row.get("case")) is not int or row["case"] != i:
            raise CheckingError(f"missing, duplicate or reordered driver case {i}")
        row.pop("case")
    return rows


def complete_go_tests(done, expected):
    """Require a normal terminal record for every original named Go test."""
    try:
        events = [json.loads(line) for line in done.stdout.splitlines() if line]
    except (ValueError, TypeError) as exc:
        raise CheckingError(f"malformed Go test report: {exc}") from exc
    if not events or any(type(e) is not dict or type(e.get("Action")) is not str or
                         type(e.get("Package")) is not str or not e["Package"] or
                         (e.get("Test") is not None and type(e["Test"]) is not str) for e in events):
        raise CheckingError("empty or malformed Go test report")
    run = [e["Test"] for e in events if e.get("Action") == "run" and e.get("Test")]
    terminal = [e for e in events if e.get("Action") in ("pass", "fail", "skip") and e.get("Test")]
    names = [e["Test"] for e in terminal]
    if (not expected or set(run) != set(expected) or set(names) != set(expected) or
            len(run) != len(set(run)) or len(names) != len(set(names)) or
            any(e["Action"] == "skip" for e in terminal)):
        raise CheckingError("incomplete, extra, duplicate or skipped named Go test")
    package = [e for e in events if not e.get("Test") and e.get("Action") in ("pass", "fail")]
    failed = [e["Test"] for e in terminal if e["Action"] == "fail"]
    combined = done.stdout + done.stderr
    if (len(package) != 1 or package[0]["Action"] != ("fail" if failed else "pass") or
            done.returncode != (1 if failed else 0) or
            any(s in combined for s in ("[build failed]", "panic:", "fatal error:", "signal:", "test timed out"))):
        raise CheckingError("Go compilation/start/runtime error or missing package completion")
    return failed


def shadowed_source_refusal(done):
    if done.returncode == 0:
        return False
    if not done.stdout and re.fullmatch(
            r"gen_machine: Platform/(?:03-worker|04-controller)/forms/[^/\n]+\.tsv: "
            r"n [1-9][0-9]* is never the first match of [a-z_]+ over the enumerated inputs "
            r"\(.+\) — a shadowed row\n?", done.stderr):
        return True
    raise CheckingError("generator failed, not a source-shadow refusal: " + done.stderr)


def camel(name):
    if name.isupper():
        name = name.lower()
    return "".join(w[:1].upper() + w[1:] for w in re.split(r"[-_]", name) if w)


class Form:
    """Independently read machine #var/#const and n, state, condition, action, next rows."""

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
        """Return (row-or-None, [(type, value)] or 'overflow')."""
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
    """Collect numeric literals from conditions/arguments and #const declarations."""
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
    """Return boundary/random judge inputs as [(state, env)]."""
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
        # Settings sometimes equal the compared value to cover their boundaries.
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
			Case  int
			State string
			In    m.In
		}
		if err := json.Unmarshal(sc.Bytes(), &c); err != nil {
			panic(err)
		}
		mv, ok, err := m.Step(m.State(c.State), c.In)
		res := map[string]any{"case": c.Case, "ok": ok, "err": err != nil, "row": mv.Row, "next": string(mv.Next)}
		args := []any{}
		for _, a := range mv.Args {
			args = append(args, tag(a))
		}
		res["args"] = args
		enc.Encode(res)
	}
	if err := sc.Err(); err != nil { panic(err) }
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
    """Format Python numeric repr like Go fmt.Sprint(float64) for comparison."""
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
        lines = "".join(json.dumps({"Case": i, "State": s, "In": {camel(k): v for k, v in env.items()}}) + "\n"
                        for i, (s, env) in enumerate(cases))
        done = go(["run", f"./cmd/judge{self.pkg}"], self.mod, lines)
        if done.returncode:
            raise CheckingError(f"driver: {done.stderr[-2000:]}")
        return complete_reports(done.stdout, len(cases))


def disagreements(oracle, cases, got):
    if not cases or len(cases) != len(got):
        raise CheckingError(f"incomplete independent comparison: {len(got)}/{len(cases)}")
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
    """Return [(name, form text)] row mutants."""
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
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        slug, _ = LESSONS[lesson]
        out = Path(tempfile.mkdtemp(prefix=f"fresh-{slug}-", dir=self.tmp))
        done = gen(lesson, out)
        self.assertEqual(done.returncode, 0, done.stderr)
        kept = output_lesson.output_root() / slug / "go"
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
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        rnd = random.Random(7)
        for lesson, (slug, parts) in LESSONS.items():
            for part in parts:
                form = Form(form_path(ROOT, lesson, part).read_text(encoding="utf-8"))
                oracle = Oracle(form)
                cases = inputs(form, rnd, 1500)
                base = [oracle.run(s, e) for s, e in cases if s in form.states()]
                killed = survived = equivalent = rejected = 0
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
                        # A next-value compiler mutant must preserve the original
                        # procedure interface, rather than rename its callbacks.
                        next_mutant = re.fullmatch(r"n([1-9][0-9]*)-next", name)
                        fp.write_text(form.text if next_mutant else text, encoding="utf-8")
                        out = root / "out"
                        done = gen(lesson, out, root, [part])
                        if done.returncode:
                            if not next_mutant and shadowed_source_refusal(done):
                                rejected += 1
                            else:
                                raise CheckingError("generator failed, not a semantic kill: " + done.stderr)
                            continue
                        pkg = part.replace("-", "")
                        if next_mutant:
                            row = int(next_mutant[1])
                            target = next(r["next"] for r in mform.rows if r["n"] == row)
                            path = out / "go" / pkg / "machine.go"
                            before = path.read_text()
                            pattern = rf"(Move\{{Row: {row},[^\n]*?\bNext: )State[A-Za-z0-9_]+"
                            changed, count = re.subn(pattern, lambda m: m[1] + "State(" + json.dumps(target) + ")", before)
                            if count != 1 or changed == before:
                                raise CheckingError(f"next mutant {name}: not one generated Move.Next")
                            path.write_text(changed)
                        shutil.copy(output_lesson.output_root() / slug / "go" / pkg / "form_test.go", out / "go" / pkg / "form_test.go")
                        done = go(["test", "-json", "-count=1", f"./{pkg}/"], out / "go")
                        failed = complete_go_tests(done, {"TestForm", "TestStates", "TestApply"})
                        if not failed:
                            survived += 1
                        self.assertTrue(failed, f"{part} mutant {name} survives the original form tests")
                        killed += 1
                print(f"\n{part}: semantic kills {killed}, source refusals {rejected}, survived {survived}, equivalent {equivalent}", file=sys.stderr)
                self.assertGreater(killed, len(form.rows), f"{part}: too few mutants")

    def test_kit(self):
        """Build machine kit parts: lesson module compiles, closed tests pass and impl files remain editable. Reject another lesson's machine."""
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
        # The consumer refuses the unavailable part before any form is read.
        # Keep the original source-negative proof on an explicit owned output.
        done = gen("03-worker", self.tmp / "wrong-machine-source", ROOT, ["slot-fate"])
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("no machine form slot-fate.tsv", done.stderr)

    def test_refusals(self):
        """Reject forms with undeclared variables/types, shadowed rows or foreign states."""
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
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


class CheckingControls(unittest.TestCase):
    def test_cardinality_identity_and_json_errors_are_not_comparisons(self):
        good = [{"case": 0, "value": "same"}, {"case": 1, "value": "same"}]
        encode = lambda rows: "".join(json.dumps(r) + "\n" for r in rows)
        self.assertEqual(complete_reports(encode(good), 2), [{"value": "same"}, {"value": "same"}])
        bad = [[], good[:1], good + [{"case": 2}], [good[0], good[0]], list(reversed(good)),
               [{"case": False}, good[1]], [{"case": 0}, {"case": True}],
               [{"case": 0}, {"case": 2}], [{"case": 0}, {}]]
        for rows in bad:
            with self.subTest(rows=rows), self.assertRaises(CheckingError):
                complete_reports(encode(rows), 2)
        for text in ('not json\n', '{"case":0,"case":0}\n'):
            with self.subTest(text=text), self.assertRaises(CheckingError):
                complete_reports(text, 1)

    def test_independent_comparison_rejects_a_missing_tail_before_oracle(self):
        for cases, got in [([("state", {})], []), ([], []), ([('state', {})], [{}, {}])]:
            with self.subTest(counts=(len(cases), len(got))), self.assertRaises(CheckingError):
                disagreements(None, cases, got)

    def test_selector_driver_checks_exit_and_full_report(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(prefix="selector-report-") as folder:
            root = Path(folder)
            (root / "go.mod").write_text("module fixture\n\ngo 1.22\n")
            judge = Judge("03-worker", "slot-capture", root)
            for code, text in [(1, ''), (0, ''), (0, '{"case":0}\n')]:
                done = subprocess.CompletedProcess([], code, text, "failed" if code else "")
                with self.subTest(code=code, text=text), patch(__name__ + ".go", return_value=done), self.assertRaises(CheckingError):
                    judge.step([("admit", {}), ("search", {})])

    def test_only_complete_named_normal_go_failure_is_semantic(self):
        def done(code, events, stderr=""):
            return subprocess.CompletedProcess([], code, "".join(json.dumps(dict(Package="fixture", **e)) + "\n"
                                                                  for e in events), stderr)
        run = {"Action": "run", "Test": "TestOriginal"}
        passed = [run, {"Action": "pass", "Test": "TestOriginal"}, {"Action": "pass"}]
        failed = [run, {"Action": "fail", "Test": "TestOriginal"}, {"Action": "fail"}]
        self.assertEqual(complete_go_tests(done(0, passed), {"TestOriginal"}), [])
        self.assertEqual(complete_go_tests(done(1, failed), {"TestOriginal"}), ["TestOriginal"])
        for report in [done(0, []), done(1, [{"Action": "fail"}]), done(1, failed[:-1]),
                       done(1, [run, run] + failed[1:]), done(1, failed, "panic: not semantic"),
                       done(0, failed), done(1, passed),
                       done(1, failed + [{"Action": "fail", "Test": "extra"}])]:
            with self.subTest(report=report.stdout), self.assertRaises(CheckingError):
                complete_go_tests(report, {"TestOriginal"})

    def test_real_compile_and_missing_source_errors_are_not_kills(self):
        if not shutil.which("go"):
            raise CheckingError("Go is missing for actual checking-error controls")
        with tempfile.TemporaryDirectory(prefix="actual-checking-error-") as folder:
            root = Path(folder)
            (root / "go.mod").write_text("module brokenfixture\n\ngo 1.22\n")
            (root / "broken.go").write_text("package brokenfixture\nfunc broken( {\n")
            done = go(["test", "-json", "./..."], root)
            self.assertNotEqual(done.returncode, 0)
            with self.assertRaises(CheckingError):
                complete_go_tests(done, {"TestOriginal"})
            done = gen("03-worker", root / "out", root, ["slot-capture"])
            self.assertNotEqual(done.returncode, 0)
            with self.assertRaises(CheckingError):
                shadowed_source_refusal(done)


if __name__ == "__main__":
    unittest.main()
