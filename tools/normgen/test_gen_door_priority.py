"""Judge x-route-priority routing (P/05-R057) against an independent OpenAPI model of priority, capture, decode, error. Match literals as raw bytes without whole-path decoding or trailing-slash normalization; filter methods before priority; unmatched method/shape gives bodyless405/404. Invalid captured values use that method's x-path-error without fallback. Probe resource-route seams s30-s37, operation samples, corrupted/random paths and door roles. Method-filter ordering, early decoding, missing UTF-8 checks and whole-remainder decoding mutants must fail. Empty-capture allowance is equivalent under ObjectKey minLength. Run with jsonschema and Go 1.22."""
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
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
LESSON, SLUG = "05-resource", "p05"
GOENV = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off", GOTOOLCHAIN="local")
sys.path.insert(0, str(HERE))
import yamlsub  # noqa: E402


class Model:
    def __init__(self):
        self.spec = ROOT / "Platform" / LESSON / "spec" / f"{LESSON}.api.openapi.yaml"
        self.doc = yamlsub.load(self.spec.read_text(encoding="utf-8"), self.spec.name)
        from jsonschema import Draft202012Validator
        self.V = Draft202012Validator
        self.paths = []
        for path, item in self.doc["paths"].items():
            ms = [m.upper() for m in ("get", "put", "post", "delete", "patch", "head") if m in item]
            params = {}
            for m in ms:
                for p in item.get("parameters", []) + item[m.lower()].get("parameters", []):
                    if p.get("in") == "path":
                        params[p["name"]] = p
            segs = path[1:].split("/") if path != "/" else []
            self.paths.append({"path": path, "segs": segs, "methods": ms, "prio": item["x-route-priority"],
                               "params": params})

    def valid(self, schema, v):
        return self.V(dict(schema, components=self.doc["components"]) if "$ref" in schema else schema,
                      ).is_valid(v) if "$ref" not in schema else \
            self.V({"$ref": schema["$ref"], "components": self.doc["components"]}).is_valid(v)

    def route(self, method, raw):
        if not raw.startswith("/"):
            return {"err": 404, "resp": ""}
        rs = [] if raw == "/" else raw[1:].split("/")
        cands = []
        for p in self.paths:
            vals, ok = {}, True
            for i, s in enumerate(p["segs"]):
                m = re.fullmatch(r"\{(.+)\}", s)
                if m and p["params"][m[1]].get("x-path-capture") == "remainder":
                    if i >= len(rs):
                        ok = False
                    else:
                        vals[m[1]] = "/".join(rs[i:])
                    break
                if i >= len(rs):
                    ok = False
                    break
                if m:
                    vals[m[1]] = rs[i]
                elif rs[i] != s:
                    ok = False
                    break
            else:
                ok = ok and len(rs) == len(p["segs"])
            if ok:
                cands.append((p, vals))
        if not cands:
            return {"err": 404, "resp": ""}
        withm = [(p, v) for p, v in cands if method.upper() in p["methods"]]
        if not withm:
            return {"err": 405, "resp": ""}
        p, vals = min(withm, key=lambda c: c[0]["prio"])
        out = {}
        for name, v in vals.items():
            prm = p["params"][name]
            good = v != ""
            dec = v
            if good and prm.get("x-path-decode") == "percent-segment":
                parts = []
                for seg in v.split("/"):
                    if re.search(r"%(?![0-9A-Fa-f]{2})", seg):
                        good = False
                        break
                    b = re.sub(rb"%([0-9A-Fa-f]{2})", lambda m_: bytes([int(m_[1], 16)]), seg.encode("utf-8"))
                    try:
                        d = b.decode("utf-8")
                    except UnicodeDecodeError:
                        good = False
                        break
                    if "/" in d:
                        good = False
                        break
                    parts.append(d)
                dec = "/".join(parts)
            if good:
                good = self.valid(prm.get("schema", {}), dec)
            if not good:
                pe = (prm.get("x-path-error") or {}).get(method.upper(), {"status": 404, "response_schema": "-"})
                return {"err": pe["status"], "resp": "" if pe["response_schema"] == "-" else pe["response_schema"],
                        "param": name, "path": p["path"]}
            out[name] = dec
        return {"path": p["path"], "method": method.upper(), "params": out}


DRIVER = r'''package main

import (
	"bufio"
	"encoding/json"
	"os"

	"%s/apidoor"
)

func main() {
	sc := bufio.NewScanner(os.Stdin)
	enc := json.NewEncoder(os.Stdout)
	enc.SetEscapeHTML(false)
	for sc.Scan() {
		var c struct{ Method, Path, Role string }
		_ = json.Unmarshal(sc.Bytes(), &c)
		m, err := apidoor.Route(c.Method, c.Path)
		if err != nil {
			r := map[string]any{"err": err.Code, "resp": err.Response}
			if err.Param != "" {
				r["param"] = err.Param
				r["path"] = apidoor.Ops[err.Op].Path
			}
			enc.Encode(r)
			continue
		}
		info := apidoor.Ops[m.Op]
		enc.Encode(map[string]any{"path": info.Path, "method": info.Method, "params": m.Params,
			"admitted": apidoor.Admitted(m.Op, c.Role, func(s string) bool { return s == "testsub" })})
	}
}
'''


def run(mod, probes):
    d = Path(mod) / "cmd/judgeprio"
    d.mkdir(parents=True, exist_ok=True)
    module = (Path(mod) / "go.mod").read_text().split("\n")[0].split()[1]
    (d / "main.go").write_text(DRIVER % module)
    stdin = "".join(json.dumps({"Method": m, "Path": p, "Role": r}) + "\n" for m, p, r in probes)
    done = subprocess.run(["go", "run", "./cmd/judgeprio"], cwd=mod, input=stdin, capture_output=True, text=True, env=GOENV)
    if done.returncode:
        raise AssertionError(done.stderr[-2000:])
    return [json.loads(x) for x in done.stdout.split("\n") if x]


def roles_table():
    rows = [ln.split("\t") for ln in (ROOT / "Platform" / LESSON / "forms/door-roles.tsv").read_text().split("\n")
            if ln and not ln.startswith("#")][1:]
    return {(m, p): r.split(",") for m, p, r, _ in rows}


def admitted(roles, role):
    for r in roles:
        if r == "*" and role:
            return True
        if r == "<sub>worker" and role == "testsubworker":
            return True
        if r == role:
            return True
    return False


def probes(model, rnd):
    seams = [ln.split("\t") for ln in (ROOT / "Platform" / LESSON / "acceptance/seams.tsv").read_text().split("\n")
             if "CALL resource-route" in ln]
    out = []
    for cells in seams:
        inp = json.loads(cells[2].split(" ", 2)[2])
        out.append((inp["method"], inp["path"].split("?")[0], inp.get("role", "console")))
    samples = {"key": "testsub/heartbeats/w-1", "sub": "testsub", "digest": "sha256-" + "0" * 64, "unit": "c1",
               "path": "testsub/c1/e1/20260101T000000Z.events.jsonl", "server": "srv-b"}
    for p in model.paths:
        vals = [samples.get(re.fullmatch(r"\{(.+)\}", s)[1], "x") if s.startswith("{") else s for s in p["segs"]]
        base = "/" + "/".join(vals)
        for m in p["methods"] + ["DELETE", "HEAD"]:
            for role in ("console", "resource", "testsubworker", "otherworker", ""):
                out.append((m, base, role))
        out += [(p["methods"][0], base + "/", "console"), (p["methods"][0], base.replace("/", "//", 1), "console"),
                (p["methods"][0], base + "%2F", "console"), (p["methods"][0], base + "%ZZ", "console"),
                (p["methods"][0], base.replace("testsub", "TestSub"), "console")]
    words = ["v1", "objects", "blobs", "events", "wait", "buckets", "mirror", "mirrored", "testsub", "c1", "", "%2F",
             "%FF", "sha256-" + "a" * 64, "srv-b", "a%20b"]
    for _ in range(400):
        segs = [rnd.choice(words) for _ in range(rnd.randint(0, 6))]
        out.append((rnd.choice(["GET", "PUT", "HEAD", "POST"]), "/" + "/".join(segs), "console"))
    return out


class Priority(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("go"):
            raise unittest.SkipTest("go is not in PATH")
        cls.tmp = Path(tempfile.mkdtemp(prefix="door-prio-"))
        out = cls.tmp / "fresh"
        done = subprocess.run([sys.executable, str(HERE / "gen_door_lesson.py"), "--lesson", LESSON, str(out)],
                              capture_output=True, text=True)
        if done.returncode:
            raise AssertionError(done.stderr)
        cls.fresh = out / "go"
        cls.model = Model()
        cls.roles = roles_table()
        cls.pr = probes(cls.model, random.Random(5))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def expect(self, m, p, role):
        e = self.model.route(m, p)
        if "path" in e and "err" not in e:
            e = dict(e, admitted=admitted(self.roles.get((e["method"], e["path"]), []), role))
        return e

    def test_fresh(self):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        for name in ("routes.go", "routes_rt.go", "bodies.go", "schema_rt.go"):
            kept = output_lesson.output_root() / SLUG / "go/apidoor" / name
            self.assertEqual(kept.read_bytes(), (self.fresh / "apidoor" / name).read_bytes(), f"{kept} is stale")

    def test_seams_and_probes(self):
        got = run(self.fresh, self.pr)
        bad = [(p, self.expect(*p), g) for p, g in zip(self.pr, got) if self.expect(*p) != g]
        self.assertEqual(bad[:3], [], f"{len(bad)} of {len(self.pr)} disagree")
        kinds = {(g.get("err"), bool(g.get("param"))) for g in got}
        for k in ((404, False), (405, False), (400, True), (404, True), (405, True)):
            self.assertIn(k, kinds)
        self.assertEqual({(g["method"], g["path"]) for g in got if "method" in g},
                         {(m, p["path"]) for p in self.model.paths for m in p["methods"]})

    def test_mutants(self):
        rt = (self.fresh / "apidoor/routes_rt.go").read_text()
        muts = {
            "priority-before-method": rt.replace('''		if _, has := byPathMethod[t.path+" "+m]; !has {
			continue
		}''', "", 1),
            "decode-before-match": rt.replace('''	raw := strings.Split(rawPath[1:], "/")''',
                                              '''	dp, _ := unescapeSegment(rawPath)
	raw := strings.Split(dp[1:], "/")''', 1),
            "no-utf8": rt.replace("if ok && !utf8.ValidString(dec) {", "if ok && false && !utf8.ValidString(dec) {", 1),
            "remainder-one-piece": rt.replace('parts := strings.Split(v, "/")', 'parts := []string{v}', 1),
        }
        for name, text in muts.items():
            with self.subTest(mutant=name):
                self.assertNotEqual(text, rt, f"{name}: the mutant does not apply")
                mod = self.tmp / f"mut-{name}"
                shutil.copytree(self.fresh, mod)
                (mod / "apidoor/routes_rt.go").write_text(text)
                try:
                    got = run(mod, self.pr)
                except AssertionError:
                    continue
                bad = [p for p, g in zip(self.pr, got) if self.expect(*p) != g]
                self.assertTrue(bad, f"{name} survives")


if __name__ == "__main__":
    unittest.main()
