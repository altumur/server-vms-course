#!/usr/bin/env python3
"""Tests of the static as-built extractors and the comparison (ADR-0123).

The synthetic Go module in fixtures/goprobe has known flags, environment
names, constants, refusals, exits and imports; fixtures/spec is committed into
a throw-away git repository that plays the export at the implementation's pin.

Checks: each extractor finds what is known; two runs give the same bytes; the
snapshots fit tools/asbuilt/schemas; no host path leaks; child processes stay
under 1 GiB resident.

Run: python3 tools/asbuilt/test_asbuilt.py
"""

import json
import resource
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import asbuilt  # noqa: E402
import compare  # noqa: E402
import yamlio  # noqa: E402

FIXTURE = HERE / "fixtures" / "goprobe"
SPEC = HERE / "fixtures" / "spec"
LESSON = "07-thing"
GIB = 1 << 30


def git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True,
                   env={"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(cwd), "GIT_CONFIG_NOSYSTEM": "1",
                        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                        "GIT_COMMITTER_EMAIL": "t@t", "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
                        "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z"})


def validate(doc, schema, base, path="$"):
    """Small JSON Schema subset: $ref, type, enum, const, required, properties, additionalProperties, items."""
    if "$ref" in schema:
        ref = schema["$ref"]
        if ref.startswith("#/$defs/"):
            return validate(doc, base["$defs"][ref.split("/")[-1]], base, path)
        sub = json.loads((HERE / "schemas" / ref).read_text())
        return validate(doc, sub, sub, path)
    t = schema.get("type")
    types = t if isinstance(t, list) else [t] if t else []
    pytypes = {"object": dict, "array": list, "string": str, "integer": int, "boolean": bool, "null": type(None)}
    if types and not any(isinstance(doc, pytypes[x]) and not (x == "integer" and isinstance(doc, bool)) for x in types):
        raise AssertionError("%s: %r is not %s" % (path, doc, types))
    if "enum" in schema and doc not in schema["enum"]:
        raise AssertionError("%s: %r not in %s" % (path, doc, schema["enum"]))
    if "const" in schema and doc != schema["const"]:
        raise AssertionError("%s: %r != %r" % (path, doc, schema["const"]))
    if isinstance(doc, dict):
        for k in schema.get("required", []):
            if k not in doc:
                raise AssertionError("%s: missing %s" % (path, k))
        props = schema.get("properties", {})
        for k, v in doc.items():
            if k in props:
                validate(v, props[k], base, path + "." + k)
            elif schema.get("additionalProperties") is False:
                raise AssertionError("%s: unexpected key %s" % (path, k))
    if isinstance(doc, list) and "items" in schema:
        for i, v in enumerate(doc):
            validate(v, schema["items"], base, "%s[%d]" % (path, i))


class AsBuilt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="asbuilt-test-"))
        # The export: fixtures/spec committed at one pin.
        cls.specs = cls.tmp / "specs"
        shutil.copytree(SPEC, cls.specs)
        git(cls.specs, "init", "-q")
        git(cls.specs, "add", "Platform")
        git(cls.specs, "commit", "-q", "-m", "pin")
        cls.pin = subprocess.run(["git", "-C", str(cls.specs), "rev-parse", "HEAD"], capture_output=True,
                                 text=True, check=True).stdout.strip()
        # The subject: a copy of the fixture, so the extractor never sees the course tree.
        cls.root = cls.tmp / "impl"
        shutil.copytree(FIXTURE, cls.root)
        (cls.root / "SPEC_VERSION").write_text(cls.pin[:7] + "\n")
        cls.outs = []
        for i in range(2):
            out = cls.tmp / ("out%d" % i)
            asbuilt.main(["--impl", "probe", "--root", str(cls.root), "--lesson", LESSON,
                          "--spec-repo", str(cls.specs), "--out", str(out)])
            snap = out / "probe" / LESSON
            compare.main(["--snap", str(snap), "--spec-repo", str(cls.specs)])
            cls.outs.append(snap)
        cls.snap = cls.outs[0]
        cls.params = yamlio.load((cls.snap / "params.yaml").read_text())
        cls.refusals = yamlio.load((cls.snap / "refusals.yaml").read_text())
        cls.deps = yamlio.load((cls.snap / "deps.yaml").read_text())
        rows = (cls.snap / "compare.tsv").read_text().splitlines()
        cols = rows[0].split("\t")
        cls.rows = [dict(zip(cols, r.split("\t"))) for r in rows[1:]]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def row(self, unit):
        rs = [r for r in self.rows if r["unit"] == unit]
        self.assertEqual(len(rs), 1, unit)
        return rs[0]

    # ---- determinism, schema, leaks, memory ----

    def test_two_runs_same_bytes(self):
        for name in ("params.yaml", "refusals.yaml", "deps.yaml", "compare.tsv", "compare.md"):
            self.assertEqual((self.outs[0] / name).read_bytes(), (self.outs[1] / name).read_bytes(), name)

    def test_schemas(self):
        for name, doc in (("params", self.params), ("refusals", self.refusals), ("deps", self.deps)):
            schema = json.loads((HERE / "schemas" / (name + ".schema.json")).read_text())
            validate(doc, schema, schema)
        schema = json.loads((HERE / "schemas" / "compare.schema.json").read_text())
        for r in self.rows:
            validate(r, schema, schema)

    def test_header(self):
        h = self.params["header"]
        self.assertEqual(h["spec"], self.pin)
        self.assertEqual(h["source"], "static")
        self.assertEqual(h["implementation"], "probe")
        self.assertEqual(h["module"], "probe")
        self.assertTrue(h["extractor"].startswith(asbuilt.VERSION + "+goextract/"))
        self.assertEqual(self.refusals["header"], h)
        self.assertEqual(self.deps["header"], h)

    def test_no_host_paths(self):
        for p in self.snap.iterdir():
            text = p.read_text()
            self.assertIsNone(asbuilt.LEAK.search(text), p.name)
            self.assertNotIn(str(self.tmp), text, p.name)
            self.assertNotIn("/var/lib/thing", text, p.name)

    def test_memory(self):
        peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        own = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        scale = 1 if sys.platform == "darwin" else 1024
        self.assertLess(peak * scale, GIB, "child peak")
        self.assertLess(own * scale, GIB, "own peak")

    def test_yaml_round_trip(self):
        for name in ("params.yaml", "refusals.yaml", "deps.yaml"):
            text = (self.snap / name).read_text()
            self.assertEqual(yamlio.dump(yamlio.load(text)), text, name)

    # ---- params ----

    def test_flags(self):
        f = {x["name"]: x for x in self.params["flags"]}
        self.assertEqual(sorted(f), ["dir", "legacy", "limit", "root", "verbose", "wait"])
        self.assertEqual({x["set"] for x in f.values()}, {"thingd"})
        self.assertEqual((f["limit"]["type"], f["limit"]["default"]), ("int", "64"))
        self.assertEqual((f["wait"]["type"], f["wait"]["default"], f["wait"]["expr"]), ("duration", "3s", "3 * time.Second"))
        self.assertEqual(f["verbose"]["default"], "false")
        self.assertEqual(f["dir"]["default"], "")
        self.assertTrue(f["root"]["default"].startswith("<path:"))
        self.assertFalse(f["legacy"]["bound"])
        self.assertTrue(f["dir"]["bound"])
        self.assertEqual(f["dir"]["at"], "07-thing/cmd/thingd/main.go:30")

    def test_env_names_only(self):
        env = [(e["name"], e["call"]) for e in self.params["env"]]
        self.assertEqual(env, [("THING_MODE", "os.LookupEnv"), ("THING_TOKEN", "os.Getenv")])

    def test_consts(self):
        c = {x["name"]: x for x in self.params["consts"]}
        self.assertEqual((c["MaxItems"]["value"], c["MaxItems"]["expr"]), ("1024", "1 << 10"))
        self.assertEqual((c["Timeout"]["value"], c["Timeout"]["type"]), ("2s", "time.Duration"))
        self.assertEqual(c["modeEnv"]["value"], "THING_MODE")
        self.assertEqual(c["kindRefused"]["scope"], "lesson")

    def test_help(self):
        (h,) = self.params["help"]
        self.assertEqual((h["package"], h["status"], h["set"], h["exit"]), ("07-thing/cmd/thingd", "ok", "thingd", 2))
        hf = {x["name"]: x for x in h["flags"]}
        self.assertEqual(sorted(hf), ["dir", "legacy", "limit", "root", "verbose", "wait"])
        self.assertEqual(hf["wait"]["default"], "3s")
        self.assertEqual(hf["root"]["default"], self.params and {x["name"]: x for x in self.params["flags"]}["root"]["default"])

    # ---- refusals ----

    def test_http_refusals(self):
        got = sorted((r["code"], r["kind"], r["resolved"], tuple(r["words"]), tuple(r["fields"]), r["func"])
                     for r in self.refusals["http"])
        self.assertEqual(got, [
            (400, "badkey", "literal", ("badkey",), (), "Handle"),
            (403, "forbidden", "wrapper", ("{role} may not read {key}",), (), "Handle"),
            (404, "badrequest", "local-assign", ("badrequest",), (), "Handle"),
            (405, "badrequest", "local-assign", ("badrequest",), (), "Handle"),
            (409, "refused", "literal", ("refused",), (), "Handle"),
            (413, "toolarge", "literal", ("body limit",), ("limit",), "Handle"),
            (413, "toolarge", "literal", ("toolarge",), ("limit", "size"), "Handle"),
            (503, "unavailable", "literal", ("unavailable",), (), "Handle"),
        ])
        (w,) = self.refusals["wrappers"]
        self.assertEqual((w["code"], w["kind"], w["func"], w["words"]), (403, "forbidden", "forbidden", ["{role} may not read {key}"]))

    def test_errors_exits_unresolved(self):
        words = sorted(w for r in self.refusals["errors"] for w in r["words"])
        self.assertEqual(words, ["-dir required", "-limit above {MaxItems}", "empty reason"])
        self.assertEqual([(x["code"], x["func"]) for x in self.refusals["exits"]], [(2, "main")])
        un = sorted((u["what"], u["func"], u["expr"]) for u in self.refusals["unresolved"])
        self.assertEqual(un, [("error", "Check", "errors.New(reason)"), ("refusal", "Dynamic", "fault(code, kind)")])

    def test_tests_are_ignored(self):
        text = "".join((self.snap / n).read_text() for n in ("params.yaml", "refusals.yaml"))
        self.assertNotIn("TEST_ONLY", text)
        self.assertNotIn("teapot", text)

    # ---- deps ----

    def test_deps(self):
        p = {x["path"]: x for x in self.deps["packages"]}
        self.assertEqual(sorted(p), ["probe/07-thing/cmd/thingd", "probe/07-thing/internal/extra",
                                     "probe/07-thing/internal/thing", "probe/08-other/peer", "probe/common/wire"])
        self.assertEqual(p["probe/07-thing/cmd/thingd"]["internal"], ["probe/07-thing/internal/thing", "probe/common/wire"])
        self.assertIn("flag", p["probe/07-thing/cmd/thingd"]["stdlib"])
        self.assertEqual(p["probe/07-thing/internal/extra"]["external"], [{"module": None, "path": "example.com/ext/lib"}])
        self.assertEqual(p["probe/common/wire"]["scope"], "shared")
        self.assertEqual(self.deps["cross_lesson"], [{"from": "probe/07-thing/internal/thing", "to": "probe/08-other/peer"}])

    # ---- comparison ----

    def test_compare_params(self):
        self.assertEqual(self.row("flag:-dir")["status"], "match")
        self.assertEqual(self.row("flag:-wait")["status"], "match")
        self.assertEqual(self.row("flag:-root")["status"], "match")
        r = self.row("flag:-limit")
        self.assertEqual(r["status"], "differs")
        self.assertIn("default differs", r["note"])
        self.assertEqual(self.row("flag:-gone")["status"], "absent")
        for name in ("legacy", "verbose"):
            self.assertEqual(self.row("flag:-" + name)["status"], "extra")
        self.assertEqual(self.row("env:THING_TOKEN")["status"], "match")
        self.assertEqual(self.row("env:THING_MODE")["status"], "extra")
        self.assertEqual(self.row("const:thingd.MaxItems")["status"], "out_of_scope")
        self.assertEqual(self.row("help:-wait")["status"], "match")

    def test_compare_refusals(self):
        self.assertEqual(self.row("pair:400 badkey")["status"], "match")
        self.assertEqual(self.row("pair:403 forbidden")["status"], "match")
        self.assertEqual(self.row("pair:413 toolarge")["status"], "match")
        self.assertEqual(self.row("pair:409 conflict")["status"], "absent")
        for p in ("pair:404 badrequest", "pair:405 badrequest", "pair:409 refused", "pair:503 unavailable"):
            self.assertEqual(self.row(p)["status"], "extra", p)
        r = self.row("fields:413 toolarge RowTooLargeFault")
        self.assertEqual(r["status"], "differs")
        w = self.row("word:<роль> may not read <ключ>")
        self.assertEqual((w["status"], w["fuzzy"]), ("match", "0"))
        d = self.row("reason:P/07.1 Н4 #5/1")
        self.assertEqual((d["status"], d["fuzzy"]), ("match", "1"))
        self.assertIn("main exits 2", d["note"])
        self.assertEqual(self.row("error:empty reason")["status"], "out_of_scope")
        self.assertEqual(self.row("error:-limit above {MaxItems}")["status"], "extra")
        self.assertEqual(self.row("word:body limit")["status"], "extra")

    def test_compare_md(self):
        md = (self.snap / "compare.md").read_text()
        self.assertIn(self.pin[:12], md)
        self.assertIn("| params |", md)

    # ---- word matcher ----

    def test_word_match(self):
        self.assertEqual(compare.word_match("<роль> may not read <ключ>", "{role} may not read {key}"), "exact")
        self.assertEqual(compare.word_match("<роль> may not write|delete <ключ>", "{role} may not {action} {c.Key}"), "fuzzy")
        self.assertEqual(compare.word_match("the last voter", "the last voter: admit requires raft"), "fuzzy")
        self.assertIsNone(compare.word_match("this build has no raft", "invalid -id"))

    def test_mask(self):
        self.assertTrue(asbuilt.mask("/run/configstore").startswith("<path:"))
        self.assertEqual(asbuilt.mask("/v1/rights admin required"), "/v1/rights admin required")
        self.assertEqual(asbuilt.mask("512KiB"), "512KiB")


if __name__ == "__main__":
    unittest.main(verbosity=1)
