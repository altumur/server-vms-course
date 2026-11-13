"""Test P/03/P/04 draft-wire vectors (ADR-0125 addendum 5, item 5). Require fresh output and consumers.tsv roster, with explicit exclusions for undeclared/selected-out rows. Scaffolds fail without panic except family-read. Judge-derived native fixture answers obey absent/new/same and secret-redaction rules. Each rule-specific mutant fails: without, masked secret, sealed values-by-type, whole-table fault, RID stand, subset, events, row, secret leak, turn label, extra writer key, fields, setarray duplicates, raw bytes and stand exit. Fields outside the declared fields list remain accepted so the judge is no broader than the README."""
import lesson as output_lesson
import copy
import importlib
import json
import os
import re
import math
import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
LESSONS = {"03-worker": "p03", "04-controller": "p04", "05-resource": "p05", "06-console": "p06", "08-domain": "p08",
           "09-agent": "p09",
           "10-domain-console": "p10"}
GOENV = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off", GOTOOLCHAIN="local")


def gv(lesson_key):
    sys.path.insert(0, str(HERE))
    os.environ["NORMGEN_LESSON"] = lesson_key
    import lesson
    lesson.CURRENT = lesson.get(lesson_key)
    import gen_vectors
    return importlib.reload(gen_vectors)


def native(compare, value, state):
    """Derive a rule-satisfying response from the expectation."""
    def drop_absent(v):
        if isinstance(v, dict):
            return {k: drop_absent(x) for k, x in v.items() if x != "@absent"}
        if isinstance(v, list):
            return [drop_absent(x) for x in v]
        return v
    if compare in ("subset", "events"):
        return drop_absent(value)
    if compare == "row":
        out = {"result": value["result"]}
        for k in ("word", "field"):
            if k in value and value[k] != "@absent":
                out[k] = value[k]
        if value["result"] == "ok":
            out["row"] = {k: v for k, v in (value.get("row") or {}).items() if v != "@absent"}
        return out
    if compare == "secret":
        out = {"fault": value["fault"], "text": "refused"} if value["fault"] else {"fault": ""}
        if "masked" in value:                          # Console mapping and refusal.
            out["masked"] = value["masked"]
        return out
    if compare == "secret-domain":
        return {"fault": "own-word", "text": "refused"} if value["fault"] else {"fault": ""}
    if compare.startswith("round:"):
        field, prefix = compare[len("round:"):].split(":", 1)
        out = drop_absent(value)
        if value.get("result") == "ok":
            out = dict(out, **{field: [prefix + "a", prefix + "b"]})
        return out
    if compare == "turn":
        out, current = [], None
        for act in value:
            if isinstance(act, dict) and isinstance(act.get("write"), dict) and act["write"].get("holder") in ("@new", "@same"):
                if act["write"]["holder"] == "@new":
                    state["n"] += 1
                    current = f"mark-{state['n']}"
                act = dict(act, write=dict(act["write"], holder=current))
            out.append(act)
        return out
    if compare == "vbt-write":
        if value.get("sealed"):
            return {"status": "ok", "row": "enc:v2:fake", "plaintext": value["plaintext"]}
        if "rowjson" in value:
            return {"status": "ok", "row": json.dumps(value["rowjson"], ensure_ascii=False)}
        return value
    return value


def fake_go(g, mut=None):
    """Fixture lesson adapter maps package-function inputs to responses; mut(decl, no, variant, answer) transforms answers."""
    decls, _ = g.plan(ROOT)
    by_fn = {}
    for d in decls:
        by_fn.setdefault(d["fn"], []).append(d)
    out = ["package vectoradapter", "", "import (", '\t"bytes"', '\t"encoding/json"', '\t"fmt"', '\t"sort"', '\t"strings"', ")", "",
           "func val(s string) any {", "\tvar v any", "\td := json.NewDecoder(bytes.NewBufferString(s))", "\td.UseNumber()", "\t_ = d.Decode(&v)", "\treturn v", "}", "",
           "func key(table, variant string, cells map[string]string) string {", "\tks := []string{}",
           "\tfor k := range cells {", '\t\tks = append(ks, k+"="+cells[k])', "\t}", "\tsort.Strings(ks)",
           '\treturn table + "|" + variant + "|" + strings.Join(ks, "\\x00")', "}", ""]
    state = {"n": 0}
    for fn, ds in by_fn.items():
        entries = []
        for d in ds:
            pdir, path, rows = g.read_table(ROOT, d)
            if "select" in d:
                rows = [(no, r) for no, r in rows if d["select"](r) is True]
            for no, r, variant, fcells, (code, value, raw), fcompare in g.frames_of(d, rows, pdir):
                compare = fcompare or d["compare"]
                ans = {"code": code, "value": native(compare, value, state) if code == 0 else None, "raw": raw}
                if d.get("_form"):
                    import wire_fakes
                    run = next(r for r in d["_runs"] if r.lines[0] == no and r.variant == variant)
                    if raw is None:
                        ans["value"] = wire_fakes.native_value(run)
                if mut:
                    ans = mut(d, no, variant, compare, ans)
                if d["surface"] == "vectors":
                    cells = fcells if fcells is not None else {c: r[c] for c in d["inputs"]}
                    if g.L.key == "06-console" and d["args"] == "input":
                        k, = cells.values()
                    else:
                        k = d["table"] + "|" + variant + "|" + "\x00".join(sorted(f"{a}={b}" for a, b in cells.items()))
                else:
                    if d.get("_form"):
                        data = run.arg
                    else:
                        data = d["input"](r) if callable(d["input"]) else r[d["input"]].encode("utf-8")
                    k = data.decode("utf-8")
                entries.append((k, ans))
        uniq = {}
        for k, a in entries:                           # Identical inputs with identical answers share one map key.
            if k in uniq and uniq[k] != a:
                raise AssertionError(f"{fn}: two rows of one input give different answers: {k[:120]}")
            uniq[k] = a
        entries = list(uniq.items())
        table = ",\n".join(f"\t{g.gstr(k)}: {{Code: {a['code']}, Value: val({g.gstr(json.dumps(a['value'], ensure_ascii=False))})"
                           + (f", Raw: []byte({g.go_bytes(a['raw'])})" if a["raw"] is not None else "") + "}"
                           for k, a in entries)
        out.append(f"var answers{fn} = map[string]Answer{{\n{table},\n}}\n")
        d = ds[0]
        if d["args"] == "cells":
            out.append(f"func {fn}(table string, cells map[string]string, files map[string][]byte) Answer {{\n"
                       f'\treturn answers{fn}[key(table, "", cells)]\n}}\n')
        elif d["args"] == "cells+variant":
            out.append(f"func {fn}(table, variant string, cells map[string]string, files map[string][]byte) Answer {{\n"
                       f"\treturn answers{fn}[key(table, variant, cells)]\n}}\n")
        else:
            out.append(f"func {fn}(input []byte) Answer {{\n\treturn answers{fn}[string(input)]\n}}\n")
    # Positive mutant baselines must also execute all existing Common tests.
    # These are owned response fixtures for the shared adapter APIs; no SUT
    # implementation is inferred from their expected values.
    shared = {
        "crl": ("CRL", "input []byte", "any", "string(input)", "input", "nil"),
        "revoked": ("Revoked", "file []byte", "any", "string(file)", "file", "nil"),
        "store-client": ("StoreClient", "input []byte", "string", "string(input)", "input", '""'),
        "log-mask": ("LogMask", "raw string, fields []byte", "string", 'raw + "\\x00" + string(fields)', "raw", '""'),
    }
    for name, table in g.common_vectors.composition(g.L.key, ROOT, known_only=True):
        if name not in shared:
            continue
        fn, arguments, result_type, key_expr, column, zero = shared[name]
        if fn in by_fn:
            raise AssertionError(f"fixture API collision: {fn}")
        rel, _, rows = g.common_vectors.read(ROOT, name, table)
        fixture = g.common_vectors.fixtures(ROOT, name)
        fields = fixture["fields.yaml"][1].decode() if name == "log-mask" else ""
        values = {}
        for no, row in rows:
            key_value = row[column] + ("\x00" + fields if name == "log-mask" else "")
            value = json.dumps(g.common_vectors.expected(name, row, f"{rel}:{no}"), ensure_ascii=False)
            if key_value in values and values[key_value] != value:
                raise AssertionError(f"conflicting fixture input: {name}:{no}")
            values[key_value] = value
        body = ",\n".join(f"\t{g.gstr(k)}: {g.gstr(v)}" for k, v in values.items())
        out += [f"var common{fn} = map[string]string{{\n{body},\n}}",
                f"func {fn}({arguments}) ({result_type}, error) {{",
                f"\tanswer, ok := common{fn}[{key_expr}]",
                f'\tif !ok {{ return {zero}, fmt.Errorf("undeclared {fn} fixture input") }}',
                "\treturn val(answer)" + (".(string)" if result_type == "string" else "") + ", nil", "}"]
        by_fn[fn] = []
    out += ["var _ = fmt.Errorf"]
    return "\n".join(out), list(by_fn)


class CheckingError(ValueError):
    """Vector preparation/process/report failure, never a semantic mutant kill."""


def vector_test_context(original):
    """Hold names/package from the immutable original, never a mutant's own roster."""
    original = Path(original)
    try:
        names, source = [], []
        for path in sorted((original / "vectortests").glob("*_test.go")):
            if path.is_symlink() or not path.is_file():
                raise CheckingError("nonregular original vector test file")
            raw = path.read_bytes()
            text = raw.decode("utf-8", "strict")
            names += re.findall(r"(?m)^func (Test[A-Za-z0-9_]+)\(t \*testing\.T\)", text)
            source.append((path.name, hashlib.sha256(raw).hexdigest()))
        modules = re.findall(r"(?m)^module ([^\s]+)\s*$", (original / "go.mod").read_text())
        if (not names or len(names) != len(set(names)) or len(modules) != 1 or
                not any(not name.startswith("TestCommon") for name in names)):
            raise CheckingError("nonempty unique original vector roster/package required")
        return tuple(names), modules[0] + "/vectortests", tuple(source)
    except (OSError, UnicodeError) as exc:
        raise CheckingError(f"original vector Source read failed: {exc}") from exc


def _unique_report(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CheckingError("duplicate Go vector report key")
        result[key] = value
    return result


def _report_constant(value):
    raise CheckingError("non-JSON Go vector report constant: " + value)


def _vector_report_context(expected, package):
    if (type(expected) not in (list, tuple) or not expected or
            any(type(v) is not str or not v for v in expected) or len(expected) != len(set(expected)) or type(package) is not str or not package or
            not any(not name.startswith("TestCommon") for name in expected)):
        raise CheckingError("nonempty vector roster/context required")


def vector_report(done, expected, package):
    """Validate every run/terminal and EOF before exposing any semantic failure."""
    _vector_report_context(expected, package)
    try:
        text, stderr = done.stdout, done.stderr
        if type(text) is bytes:
            text = text.decode("utf-8", "strict")
        if type(stderr) is bytes:
            stderr = stderr.decode("utf-8", "strict")
        if type(text) is not str or type(stderr) is not str or stderr:
            raise CheckingError("missing vector process capture or Go command diagnostic")
        text.encode("utf-8", "strict"); stderr.encode("utf-8", "strict")
        if not text.endswith("\n"):
            raise CheckingError("truncated vector Go report: final LF required")
        lines = text.split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        if not lines or any(not line for line in lines):
            raise CheckingError("empty/blank vector Go report")
        events = [json.loads(line, object_pairs_hook=_unique_report, parse_constant=_report_constant) for line in lines]
        json.dumps(events, ensure_ascii=False, allow_nan=False).encode("utf-8", "strict")
    except (UnicodeError, ValueError, TypeError, AttributeError, RecursionError) as exc:
        raise CheckingError("invalid vector Go UTF-8/JSON report") from exc
    allowed = {"Time", "Action", "Package", "Test", "Elapsed", "Output"}
    started, terminal, states, paused = False, None, {}, set()
    outputs = []
    for event in events:
        if (type(event) is not dict or set(event) - allowed or event.get("Package") != package or
                type(event.get("Action")) is not str or terminal is not None or
                ("Test" in event and (type(event["Test"]) is not str or event["Test"] not in expected)) or
                ("Output" in event and type(event["Output"]) is not str) or
                ("Time" in event and type(event["Time"]) is not str) or
                ("Elapsed" in event and (type(event["Elapsed"]) not in (int, float) or
                     not math.isfinite(event["Elapsed"]) or event["Elapsed"] < 0))):
            raise CheckingError("unknown/mistyped/out-of-context vector Go event")
        action, name = event["Action"], event.get("Test")
        if action == "start" and name is None and not started:
            started = True
            continue
        if not started:
            raise CheckingError("vector event before package start")
        if action == "output":
            if "Output" not in event or name is not None and states.get(name) != "run":
                raise CheckingError("vector output outside named execution")
            outputs.append(event.get("Output", ""))
        elif name is not None:
            if action == "run" and name not in states:
                states[name] = "run"
            elif action == "pause" and states.get(name) == "run" and name not in paused:
                paused.add(name)
            elif action == "cont" and states.get(name) == "run" and name in paused:
                paused.remove(name)
            elif action in ("pass", "fail") and states.get(name) == "run" and name not in paused:
                states[name] = action
            else:
                raise CheckingError("duplicate/skipped/unordered vector named event")
        elif action in ("pass", "fail"):
            if set(states) != set(expected) or any(v == "run" for v in states.values()):
                raise CheckingError("partial vector named report")
            terminal = action
        else:
            raise CheckingError("unexpected vector package event")
    failed = any(v == "fail" for v in states.values())
    trace = "".join(outputs) + stderr
    runtime_error = ("[build failed]" in trace or "test timed out" in trace or
        (re.search(r"(?m)^(?:panic:|fatal error:)", trace) is not None and "goroutine " in trace) or
        re.search(r"(?m)^signal:", trace) is not None)
    if (type(getattr(done, "returncode", None)) is not int or done.returncode != (1 if failed else 0) or
            terminal != ("fail" if failed else "pass") or runtime_error):
        raise CheckingError("vector compilation/start/process failure or incomplete package")
    # Common packages keep their own judges, but their complete execution above is mandatory.
    return {name: result for name, result in states.items() if not name.startswith("TestCommon")}


def results(mod, expected, package):
    _vector_report_context(expected, package)
    try:
        done = subprocess.run(["go", "test", "-count=1", "-json", "./vectortests/"], cwd=mod,
                              capture_output=True, text=True, encoding="utf-8", env=GOENV, timeout=300)
    except (OSError, UnicodeError, subprocess.SubprocessError) as exc:
        raise CheckingError(f"vector process failed: {exc}") from exc
    return vector_report(done, expected, package), 0, done


class VectorsLessons(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("go"):
            raise unittest.SkipTest("go is not in PATH")
        cls.tmp = Path(tempfile.mkdtemp(prefix="vectors-lessons-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def module(self, lesson_key, name, fake=None):
        slug = LESSONS[lesson_key]
        mod = self.tmp / f"{slug}-{name}"
        shutil.copytree(output_lesson.output_root() / slug / "go", mod)
        if fake is not None:
            text, fns = fake
            for fn in fns:
                (mod / "vectoradapter" / f"{fn.lower()}.go").unlink()
            (mod / "vectoradapter/fake.go").write_text(text, encoding="utf-8")
        return mod

    def test_fresh_and_composition(self):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        for lesson_key, slug in LESSONS.items():
            with self.subTest(lesson=lesson_key):
                g = gv(lesson_key)
                files, inv = g.build(ROOT)
                for rel, data in files.items():
                    kept = output_lesson.output_root() / slug / rel
                    self.assertTrue(kept.is_file(), f"{kept} is missing")
                    self.assertEqual(kept.read_bytes(), data, f"{kept} is stale: run gen_vectors.py --lesson {lesson_key}")
                decls, known = g.plan(ROOT)
                declared = {(d["package"], d["table"]) for d in decls} | {(f"common/{n}", t) for n, t in known}
                skipped = set(g.SKIP) | set(g.SKIP_LESSON.get(lesson_key, {}))
                self.assertEqual(g.lesson_consumers(ROOT) - declared - skipped, set())

    def test_stubs_red(self):
        for lesson_key in LESSONS:
            with self.subTest(lesson=lesson_key):
                expected, package, _ = vector_test_context(output_lesson.output_root() / LESSONS[lesson_key] / "go")
                res, panics, done = results(self.module(lesson_key, "stubs"), expected, package)
                self.assertEqual(panics, 0, done.stdout[-1500:])
                red = [t for t, a in res.items() if a == "fail" and "FamilyRead" not in t]
                green = [t for t, a in res.items() if a == "pass" and "FamilyRead" not in t]
                self.assertTrue(red)
                self.assertEqual(green, [])

    def test_fake_green(self):
        for lesson_key in LESSONS:
            with self.subTest(lesson=lesson_key):
                g = gv(lesson_key)
                expected, package, _ = vector_test_context(output_lesson.output_root() / LESSONS[lesson_key] / "go")
                res, panics, done = results(self.module(lesson_key, "fake", fake_go(g)), expected, package)
                fails = [t for t, a in res.items() if a == "fail"]
                self.assertEqual(fails, [], done.stdout[-3000:])
                self.assertGreater(len(res), 150)

    def mutant(self, lesson_key, name, mut):
        g = gv(lesson_key)
        expected, package, source_receipt = vector_test_context(
            output_lesson.output_root() / LESSONS[lesson_key] / "go")
        normal = fake_go(g)
        identity = (lesson_key, expected, package, source_receipt, hashlib.sha256(normal[0].encode()).hexdigest())
        if not hasattr(self, "_normal_vector_baselines"):
            self._normal_vector_baselines = set()
        if identity not in self._normal_vector_baselines:
            baseline = self.module(lesson_key, "baseline-" + name, normal)
            before, _, capture = results(baseline, expected, package)
            self.assertEqual(capture.returncode, 0, "normal vector fixture package must pass")
            self.assertEqual([t for t, a in before.items() if a != "pass"], [],
                             "normal complete vector fixture must be positive before mutants: " + capture.stdout[-3000:])
            self._normal_vector_baselines.add(identity)
        res, panics, done = results(self.module(lesson_key, f"mut-{name}", fake_go(g, mut)), expected, package)
        return [t for t, a in res.items() if a == "fail"]

    def test_mutants(self):
        def first(pkg, table, change, compare=None, variant=None):
            hit = {"done": False}

            def mut(d, no, v, cmp, ans):
                if hit["done"] or d["package"] != pkg or d["table"] != table or ans["code"] != 0:
                    return ans
                if (compare and cmp != compare) or (variant is not None and v != variant):
                    return ans
                new = change(copy.deepcopy(ans))
                if new is None:
                    return ans
                hit["done"] = True
                return new
            return mut

        def set_value(f):
            def change(a):
                v = f(a["value"])
                return None if v is None else dict(a, value=v)
            return change

        cases = {
            ("03-worker", "subset-missing"): first("common/domain-token", "cases.tsv",
                                                   set_value(lambda v: {k: x for k, x in v.items() if k != "result"})),
            ("03-worker", "events-field"): first("common/events-merge", "cases.tsv",
                                                 set_value(lambda v: dict(v, events=[dict(e, id="mutant") for e in v["events"]])
                                                           if v.get("events") and "id" in v["events"][0] else None)),
            ("03-worker", "row-extra-word"): first("common/row-check", "cases.tsv",
                                                   set_value(lambda v: dict(v, word="mutant") if v["result"] == "ok" and
                                                             False else (dict(v, result="refused") if v["result"] == "ok" else None))),
            ("03-worker", "secret-leak"): first("common/secret-in", "cases.tsv",
                                                lambda a: None),  # Replaced below; a hidden fragment is required.
            ("03-worker", "vbt-extra"): first("common/values-by-type", "cases.tsv",
                                              set_value(lambda v: dict(v, extra=1) if v.get("status") == "ok" else None),
                                              variant="write"),
            ("03-worker", "setarrays-repeat"): first("common/labels", "cases.tsv",
                                                     set_value(lambda v: v + [v[0]] if isinstance(v, list) and v else None)),
            ("03-worker", "raw-byte"): first("03-worker/creates-key", "cases.tsv",
                                             lambda a: dict(a, raw=a["raw"] + b"x")),
            ("03-worker", "stand-code"): first("common/said-id", "said.tsv", lambda a: dict(a, code=2)),
            ("04-controller", "turn-old-mark"): first("common/turn", "cases.tsv", lambda a: None),
            ("04-controller", "fields-listed"): first("common/slot", "cases.tsv",
                                                      set_value(lambda v: dict(v, state="mutant"))),
        }
        cases.update({
            ("06-console", "without-listed"): first("common/pool", "cases.tsv", set_value(lambda v: dict(v, count=-1))),
            ("06-console", "secret-masked"): first("common/secret-in", "cases.tsv",
                                                   set_value(lambda v: dict(v, masked="mutant"))),
            ("06-console", "vbt-sealed"): first("common/values-by-type", "cases.tsv",
                                                set_value(lambda v: dict(v, row="plain") if str(v.get("row", "")).startswith("enc:v2:")
                                                          else None), variant="write"),
            ("06-console", "whole-table"): first("common/fault", "fault.tsv",
                                                 set_value(lambda v: dict(v, **{sorted(v)[0]: 999}))),
            ("06-console", "stand-raw"): first("06-console/rid", "rid.tsv", set_value(lambda v: {"status": "mutant"})),
        })
        cases.update({
            ("08-domain", "round-same"): first("common/domain-envelopes", "x25519-round.tsv",
                                               set_value(lambda v: dict(v, envelopes=[v["envelopes"][0]] * 2)
                                                         if "envelopes" in v else None)),
            ("08-domain", "secret-domain-empty"): first("common/secret-in", "cases.tsv",
                                                        set_value(lambda v: dict(v, fault="") if v.get("fault") else None)),
        })
        g3 = gv("03-worker")

        def leak(d, no, v, cmp, ans):                      # Refusal text repeats the row's password.
            if leak.done or d["package"] != "common/secret-in" or cmp != "secret":
                return ans
            pdir, path, rows = g3.read_table(ROOT, d)
            r = dict(rows)[no]
            hidden = g3.WIRE["03-worker"] and __import__("wire_draft").secret_hidden(r["raw"], r["masked"])
            if not r["fault"] or not hidden:
                return ans
            leak.done = True
            return dict(ans, value={"fault": r["fault"], "text": "bad " + hidden[0]})       # A complete secret is a leak.
        leak.done = False
        cases[("03-worker", "secret-leak")] = leak

        def old_mark(d, no, v, cmp, ans):                  # Empty label instead of a fresh @new label.
            if old_mark.done or d["package"] != "common/turn":
                return ans
            pdir, path, rows = gv("04-controller").read_table(ROOT, d)
            exp = json.loads(dict(rows)[no]["expect"])
            news = [i for i, a in enumerate(exp) if isinstance(a, dict) and isinstance(a.get("write"), dict)
                    and a["write"].get("holder") == "@new"]
            if not news:
                return ans
            acts = copy.deepcopy(ans["value"])
            acts[news[0]]["write"]["holder"] = ""
            old_mark.done = True
            return dict(ans, value=acts)
        old_mark.done = False
        cases[("04-controller", "turn-old-mark")] = old_mark

        for (lesson_key, name), mut in cases.items():
            with self.subTest(mutant=name):
                fails = self.mutant(lesson_key, name, mut)
                self.assertTrue(getattr(mut, "done", True), f"{name}: the mutant does not apply")
                self.assertEqual(len(fails), 1, f"{name}: red {fails}")

        # Missing fates is accepted: pool P/06 does not judge that field.
        fates_applied = []
        def change_fates(value):
            fates_applied.append(True)
            return dict(value, fates="mutant")
        fates = first("common/pool", "cases.tsv", set_value(change_fates))
        self.assertEqual(self.mutant("06-console", "without-fates", fates), [])
        self.assertTrue(fates_applied, "the ignored-field control must actually change a native answer")
        # A field outside fields:state (P/04 slot takeable) stays accepted; do not broaden the README rule.
        unlisted = first("common/slot", "cases.tsv", set_value(lambda v: dict(v, takeable="mutant") if "takeable" in v else None))
        self.assertEqual(self.mutant("04-controller", "fields-unlisted", unlisted), [])


class VectorReportControls(unittest.TestCase):
    PACKAGE = "owned/vectortests"
    NAMES = ("TestOwned", "TestCommonWitness")

    def events(self, failed=False):
        values = [dict(Action="start", Package=self.PACKAGE)]
        for name in self.NAMES:
            values.append(dict(Action="run", Package=self.PACKAGE, Test=name))
            action = "fail" if failed and name == "TestOwned" else "pass"
            values.append(dict(Action=action, Package=self.PACKAGE, Test=name))
        values.append(dict(Action="fail" if failed else "pass", Package=self.PACKAGE))
        return values

    def done(self, values=None, code=0, stderr=""):
        values = self.events() if values is None else values
        return subprocess.CompletedProcess([], code, "".join(json.dumps(x) + "\n" for x in values), stderr)

    def test_normal_complete_report_validates_common_before_filtering(self):
        self.assertEqual(vector_report(self.done(), self.NAMES, self.PACKAGE), {"TestOwned": "pass"})
        events = self.events()
        events.pop(4)
        with self.assertRaises(CheckingError):
            vector_report(self.done(events), self.NAMES, self.PACKAGE)

    def test_complete_named_semantic_failure_stays_a_failure(self):
        self.assertEqual(vector_report(self.done(self.events(True), 1), self.NAMES, self.PACKAGE),
                         {"TestOwned": "fail"})
        events = self.events(True)
        events.insert(2, dict(Action="output", Package=self.PACKAGE, Test="TestOwned",
                             Output="    fixture_test.go:1: source value says panic: literal\n"))
        self.assertEqual(vector_report(self.done(events, 1), self.NAMES, self.PACKAGE), {"TestOwned": "fail"})

    def test_empty_or_common_only_context_never_starts_go(self):
        from unittest.mock import patch
        for names in ((), ("TestCommonWitness",), ("TestOwned", "TestOwned")):
            with self.subTest(names=names), patch.object(subprocess, "run") as process:
                with self.assertRaises(CheckingError):
                    results(Path("unused"), names, self.PACKAGE)
                process.assert_not_called()

    def test_partial_extra_duplicate_skipped_or_foreign_named_events_are_checking(self):
        normal = self.events()
        mutants = [normal[:-1], normal[:2] + normal[3:],
                   normal[:2] + [normal[1]] + normal[2:],
                   normal[:3] + [normal[2]] + normal[3:],
                   normal + [normal[-1]], normal[1:],
                   [dict(e, Test="TestUnknown") if e.get("Test") == "TestOwned" else e for e in normal],
                   [dict(e, Action="skip") if e.get("Test") == "TestOwned" and e["Action"] == "pass" else e for e in normal],
                   [dict(e, Package="foreign/vectortests") for e in normal],
                   [normal[0], normal[-1]], [normal[0], normal[2], normal[1], *normal[3:]]]
        for events in mutants:
            with self.subTest(events=events), self.assertRaises(CheckingError):
                vector_report(self.done(events), self.NAMES, self.PACKAGE)

    def test_json_utf8_types_duplicates_and_trailing_garbage_are_checking(self):
        raw = self.done().stdout
        mutants = ["", raw + "\n", raw + "garbage", raw[:-5], raw.rstrip("\n"),
                   raw.replace('"Action": "start"', '"Action": true', 1),
                   raw.replace('"Action": "start"', '"Action": "start", "Action": "start"', 1),
                   raw.replace('"Package": "owned/vectortests"', '"Package": NaN', 1),
                   raw.replace('"Action": "start"', '"Action": "start", "Elapsed": true', 1)]
        for text in mutants:
            with self.subTest(text=text), self.assertRaises(CheckingError):
                vector_report(subprocess.CompletedProcess([], 0, text, ""), self.NAMES, self.PACKAGE)
        with self.assertRaises(CheckingError):
            vector_report(subprocess.CompletedProcess([], 0, b"\xff", b""), self.NAMES, self.PACKAGE)

    def test_process_build_signal_timeout_and_panic_are_never_semantic_failures(self):
        from unittest.mock import patch
        for code in (1, 2, -9, True):
            with self.subTest(code=code), self.assertRaises(CheckingError):
                vector_report(self.done(code=code), self.NAMES, self.PACKAGE)
        events = self.events(True)
        events.insert(2, dict(Action="output", Package=self.PACKAGE, Test="TestOwned",
                             Output="panic: subject crashed\n\ngoroutine 9 [running]:\n"))
        with self.assertRaises(CheckingError):
            vector_report(self.done(events, 1), self.NAMES, self.PACKAGE)
        for error in (OSError("no Go"), subprocess.TimeoutExpired(["go"], 1)):
            with patch.object(subprocess, "run", side_effect=error), self.assertRaises(CheckingError):
                results(Path("unused"), self.NAMES, self.PACKAGE)

    def test_original_roster_is_nonempty_and_does_not_follow_a_mutant(self):
        with tempfile.TemporaryDirectory() as temp:
            original = Path(temp) / "original"
            (original / "vectortests").mkdir(parents=True)
            (original / "go.mod").write_text("module owned\n\ngo 1.22\n")
            file = original / "vectortests/cases_test.go"
            file.write_text("package vectortests\nimport \"testing\"\nfunc TestOwned(t *testing.T){}\nfunc TestCommonWitness(t *testing.T){}\n")
            expected, package, identities = vector_test_context(original)
            self.assertEqual(expected, self.NAMES)
            self.assertEqual(package, self.PACKAGE)
            self.assertEqual(len(identities), 1)
            # A valid shorter report never supplies its own expected roster.
            short = [dict(Action="start", Package=package), dict(Action="run", Package=package, Test="TestOwned"),
                     dict(Action="pass", Package=package, Test="TestOwned"), dict(Action="pass", Package=package)]
            with self.assertRaises(CheckingError):
                vector_report(self.done(short), expected, package)
            file.unlink()
            with self.assertRaises(CheckingError):
                vector_test_context(original)

    def test_mutant_checks_a_normal_complete_fixture_before_its_answer(self):
        from unittest.mock import patch
        case = VectorsLessons("test_mutants")
        normal, mutant = self.done(), self.done(self.events(True), 1)
        with patch(__name__ + ".gv", return_value=object()), \
                patch(__name__ + ".fake_go", return_value=("owned fake Source fixture", [])), \
                patch(__name__ + ".vector_test_context", return_value=(self.NAMES, self.PACKAGE, (("file", "hash"),))), \
                patch.object(output_lesson, "output_root", return_value=Path("unused")), \
                patch.object(case, "module", return_value=Path("owned-copy")), \
                patch(__name__ + ".results", side_effect=[({"TestOwned": "pass"}, 0, normal),
                                                         ({"TestOwned": "fail"}, 0, mutant)]) as run:
            self.assertEqual(case.mutant("03-worker", "owned", object()), ["TestOwned"])
            self.assertEqual(run.call_count, 2)

    def test_mutant_process_error_cannot_be_returned_as_a_kill(self):
        from unittest.mock import patch
        case = VectorsLessons("test_mutants")
        with patch(__name__ + ".gv", return_value=object()), \
                patch(__name__ + ".fake_go", return_value=("owned fake Source fixture", [])), \
                patch(__name__ + ".vector_test_context", return_value=(self.NAMES, self.PACKAGE, (("file", "hash"),))), \
                patch.object(output_lesson, "output_root", return_value=Path("unused")), \
                patch.object(case, "module", return_value=Path("owned-copy")), \
                patch(__name__ + ".results", side_effect=[({"TestOwned": "pass"}, 0, self.done()),
                                                         CheckingError("compiler failure")]):
            with self.assertRaises(CheckingError):
                case.mutant("03-worker", "owned", object())


class VectorGoReportControls(unittest.TestCase):
    """Bounded real Go transport controls, separate from Source vector semantics."""

    def test_named_complete_positive_then_semantic_fail_and_build_error(self):
        with tempfile.TemporaryDirectory(prefix="vector-report-go-") as temp:
            root = Path(temp)
            (root / "vectortests").mkdir()
            (root / "go.mod").write_text("module reportcontrol\n\ngo 1.22\n")
            file = root / "vectortests/control_test.go"
            original = ('package vectortests\nimport "testing"\n'
                        'func TestOwned(t *testing.T) {}\n'
                        'func TestCommonWitness(t *testing.T) {}\n')
            file.write_text(original)
            names, package, _ = vector_test_context(root)
            positive, _, capture = results(root, names, package)
            self.assertEqual(capture.returncode, 0)
            self.assertEqual(positive, {"TestOwned": "pass"})
            file.write_text(original.replace('func TestOwned(t *testing.T) {}',
                                            'func TestOwned(t *testing.T) {t.Error("complete semantic mismatch")}'))
            failed, _, capture = results(root, names, package)
            self.assertEqual(capture.returncode, 1)
            self.assertEqual(failed, {"TestOwned": "fail"})
            file.write_text(original + "invalid Go source\n")
            with self.assertRaises(CheckingError):
                results(root, names, package)


class VectorAuditControls(unittest.TestCase):
    def test_original_source_io_utf8_and_unhashable_context_are_checking(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(CheckingError):
                vector_test_context(root)
            (root / "vectortests").mkdir()
            (root / "vectortests/a_test.go").write_bytes(b"\xff")
            with self.assertRaises(CheckingError):
                vector_test_context(root)
        with self.assertRaises(CheckingError):
            _vector_report_context((["unhashable"],), "p/vectortests")

    def test_escaped_surrogate_in_output_is_checking(self):
        fixture = VectorReportControls()
        events = fixture.events()
        events.insert(2, dict(Action="output", Package=fixture.PACKAGE, Test="TestOwned", Output="\ud800"))
        with self.assertRaises(CheckingError):
            vector_report(fixture.done(events), fixture.NAMES, fixture.PACKAGE)

    def test_command_stderr_cannot_be_a_semantic_failure(self):
        fixture = VectorReportControls()
        with self.assertRaises(CheckingError):
            vector_report(fixture.done(fixture.events(True), code=1, stderr="compiler command diagnostic"),
                          fixture.NAMES, fixture.PACKAGE)

    def test_common_failure_prevents_positive_mutant_baseline(self):
        from unittest.mock import patch
        case = VectorsLessons("test_mutants")
        fixture = VectorReportControls()
        with patch(__name__ + ".gv", return_value=object()), \
                patch(__name__ + ".fake_go", return_value=("fixture", [])), \
                patch(__name__ + ".vector_test_context", return_value=(fixture.NAMES, fixture.PACKAGE, (("file", "hash"),))), \
                patch.object(output_lesson, "output_root", return_value=Path("unused")), \
                patch.object(case, "module", return_value=Path("owned-copy")), \
                patch(__name__ + ".results", return_value=({"TestOwned": "pass"}, 0, fixture.done(code=1))) as run:
            with self.assertRaises(AssertionError):
                case.mutant("03-worker", "owned", object())
            self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
