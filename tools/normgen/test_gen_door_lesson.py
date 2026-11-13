"""Judge lesson route generation (part 3a, P/06) against an independent OpenAPI model. Require fresh, one-to-one Op coverage and metadata for each method/path. Probe schema-valid parameter samples, short/prefixed variants, unknown segments/catalog names, foreign methods, malformed percent escapes and invalid values. Model literal>catalog-class>free-parameter precedence plus Catalog/schema checks; execute Go Route on a fixture Catalog. Mutants removing prefix variants, all405, parameter patterns or class rank must fail. Run test_gen_door_lesson.py with Go 1.22."""
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
from unittest.mock import Mock, patch
import copy
import hashlib
import stat
from urllib.parse import unquote_to_bytes

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
LESSONS = {"06-console": "p06", "08-domain": "p08", "09-agent": "p09", "10-domain-console": "p10"}
GOENV = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off", GOTOOLCHAIN="local")
METHODS = ("get", "put", "post", "delete", "patch", "head", "options", "trace")
CATALOG = {"sub": {"testsub", "testsub2"}, "rows": {"units", "cams"}, "table": {"tallies"}, "pass": {"probe"}}
SAMPLES = ["c1", "0123456789abcdef", "0001", "srv-a", "t1", "a", "member-1", "index.js", "x"]

sys.path.insert(0, str(HERE))
import yamlsub  # noqa: E402


class Model:
    """Independent route model: derive templates and parameter checks directly from OpenAPI."""

    def __init__(self, lesson):
        from test_gen_door_bodies import SourceSchemaReader, CheckingError as SourceError
        self.spec = ROOT / "Platform" / lesson / "spec" / f"{lesson}.api.openapi.yaml"
        self.files = {}
        self.context = _given_contexts()[0] if lesson == "06-console" else None
        try:
            self.reader = SourceSchemaReader(ROOT, self.spec)
            self.doc = self.reader.document(self.spec)
            self.declarations = self.reader.operation_declarations()
            self.paths = []
            by_path = {}
            for record in self.declarations:
                path, item, operation = record["route"], record["item"], record["operation"]
                if path not in by_path:
                    urls = [v["url"] for v in operation.get("servers", item.get("servers", self.doc.get("servers", [])))]
                    p = dict(path=path, segs=[] if path == "/" else path[1:].split("/"),
                             checks={}, ops={}, prefixed="{origin}/{sub}" in urls,
                             all405=True, component=record["component"], records={})
                    by_path[path] = p
                    self.paths.append(p)
                p = by_path[path]
                p["records"][record["method"].upper()] = record
                record["path_checks"] = {}
                for node, base, pointer in record["parameters"]:
                    prm, file = self.reader.parameter(node, base, (record["symbol"], path, record["method"]),
                                                      (base, pointer))
                    if prm["in"] == "path":
                        check = self.schema(prm["schema"], file)
                        p["checks"][prm["name"]] = check
                        record["path_checks"][prm["name"]] = check
                p["ops"][record["method"].upper()] = [str(v) for v in operation["responses"]]
                p["all405"] = p["all405"] and "405" in p["ops"][record["method"].upper()]
            self.routes = _source_route_instances(self) if self.context else None
        except SourceError as exc:
            raise CheckingError(f"independent source reader failed: {exc}") from exc

    def load(self, p):
        p = Path(p).resolve()
        if p not in self.files:
            self.files[p] = self.reader.document(p)
        return self.files[p]

    def deref(self, node, base):
        # A value occurring at several aliases keeps every guarded declaration coordinate.
        locations = self.reader._locations(node, base, "parameter")
        values = [self.reader.resolve_object(p, ptr, "parameter") for p, ptr in locations]
        value, file, _ = values[0]
        if any(v != value or p != file for v, p, _ in values):
            raise CheckingError("ambiguous source Parameter declaration")
        return value, file

    def schema(self, node, base):
        value = self.reader.schema_type_node(node, base)
        if type(value) is not dict:
            raise CheckingError("path parameter is not a string Schema Object")
        coordinates = self.reader._locations(node, base, "schema")
        return {"min": value.get("minLength", 0), "max": value.get("maxLength"),
                "pattern": value.get("pattern"), "enum": value.get("enum"), "not": value.get("not"),
                "validator": self.reader.validators(coordinates)}

    @staticmethod
    def ok(c, v):
        if v == "" or len(v) < c["min"] or (c["max"] is not None and len(v) > c["max"]):
            return False
        if c["pattern"] and not re.search(c["pattern"], v):
            return False
        if c["enum"] is not None and v not in [str(e) for e in c["enum"]]:
            return False
        neg = c["not"]
        if neg:
            for it in neg.get("anyOf", [neg]):
                if "enum" in it and v in [str(e) for e in it["enum"]]:
                    return False
                if "pattern" in it and re.search(it["pattern"], v):
                    return False
        return True

    def templates(self):
        # Preserve logical templates for the original probes/mutant applicability machinery.
        for p in self.paths:
            yield p, p["segs"], False
            if p["prefixed"]:
                yield p, ["{sub}"] + p["segs"], True

    @staticmethod
    def rank(seg):
        if isinstance(seg, tuple):
            return seg[1]                 # independently carried source/catalogue/free provenance
        m = re.fullmatch(r"\{(.+)\}", seg)
        return 2 if not m else 1 if m[1] in CATALOG else 0

    def route(self, method, path):
        """Independent pathname selection; pass and forwarding tails retain their raw remainder."""
        if type(method) is not str or type(path) is not str or not path.startswith("/"):
            return ("err", 404)
        pathname = path.partition("?")[0]
        raw = [] if pathname == "/" else pathname[1:].split("/")
        try:
            if any(re.search(r"%(?![0-9A-Fa-f]{2})", s) for s in raw):
                return ("err", 404)
            segs = [unquote_to_bytes(s).decode("utf-8", "surrogateescape") for s in raw]
        except (ValueError, UnicodeError):
            return ("err", 404)
        if self.context:
            return _route_in_context(self, method.upper(), raw, segs)
        hits = []
        for p, tsegs, pre in self.templates():
            if len(tsegs) != len(segs):
                continue
            params, good = {}, True
            for i, (t, v) in enumerate(zip(tsegs, segs)):
                m = re.fullmatch(r"\{(.+)\}", t)
                if not m:
                    good = t == v
                elif m[1] == "sub" and pre and i == 0 and "sub" not in p["checks"]:
                    good = v in CATALOG["sub"]
                    params["sub"] = v
                else:
                    check = p["checks"][m[1]]
                    good = check["validator"].is_valid(v) and (m[1] not in CATALOG or v in CATALOG[m[1]])
                    params[m[1]] = v
                if not good:
                    break
            if good:
                hits.append((p, tsegs, pre, params))
        if not hits:
            return ("err", 404)
        ranks = lambda h: [self.rank(s) for s in h[1]]
        best = [h for h in hits if ranks(h) == max(map(ranks, hits))]
        if len({h[0]["path"] for h in best}) != 1:
            return ("err", 0)
        p, _, pre, params = best[0]
        m = method.upper()
        return ("op", p["path"], m, params, pre) if m in p["ops"] else ("err", 405 if p["all405"] else 404)

    def sample(self, p, name):
        if self.context:
            views = self.context["views"]
            root = next(v for v in views if v["name"] == self.context["root"])
            values = {"sub": [self.context["root"]], "rows": [root["unit"]["rows"]],
                      "table": sorted({k for v in views for k in v.get("tables", {})}),
                      "pass": sorted({k for v in views for k in (v.get("door", {}).get("pass", [])
                               if type(v.get("door", {}).get("pass", [])) is list else
                               v["door"]["pass"].get("routes", []))}),
                      "file": [k for v in views for k in v.get("console", {}).get("files", [])]}
            if name in values:
                return values[name][0] if values[name] else None
        elif name in CATALOG:
            return sorted(CATALOG[name])[0]
        c = p["checks"][name]
        choices = ([str(v) for v in c["enum"]] if c["enum"] else []) + SAMPLES
        choices += ["a" * max(1, c["min"])]
        return next((v for v in choices if c["validator"].is_valid(v)), None)


DRIVER = r'''package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"

	"%s/apidoor"
)

type cat struct{}

func in(xs []string, v string) bool {
	for _, x := range xs {
		if x == v {
			return true
		}
	}
	return false
}

func (cat) Sub(n string) bool           { return in([]string{"testsub", "testsub2"}, n) }
func (cat) Rows(sub, n string) bool     { return in([]string{"units", "cams"}, n) }
func (cat) Table(sub, n string) bool    { return in([]string{"tallies"}, n) }
func (cat) Pass(sub, n string) bool     { return in([]string{"probe"}, n) }

func main() {
	sc := bufio.NewScanner(os.Stdin)
	enc := json.NewEncoder(os.Stdout)
	for sc.Scan() {
		var c struct {
			ID int
			Method, Path string
		}
		if err := json.Unmarshal(sc.Bytes(), &c); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		m, err := apidoor.Route(c.Method, c.Path, cat{})
		var result map[string]any
		if err != nil {
			result = map[string]any{"err": err.Code}
		} else {
			info := apidoor.Ops[m.Op]
			result = map[string]any{"path": info.Path, "method": info.Method, "params": m.Params, "prefixed": m.Prefixed}
		}
		if err := enc.Encode(map[string]any{"id": c.ID, "result": result}); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	}
	if err := sc.Err(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
'''


class CheckingError(RuntimeError):
    """The checking service failed; this is never a semantic mutant detection."""


def disagree(probes, got, oracle=None):
    """Validate every result before invoking the unchanged semantic oracle."""
    if not isinstance(probes, (list, tuple)) or not probes or any(
            not isinstance(p, (list, tuple)) or len(p) != 2 or
            any(type(v) is not str for v in p) for p in probes):
        raise CheckingError("probes must be a nonempty sequence of Method/Path string pairs")
    if type(got) is not list or len(got) != len(probes):
        raise CheckingError(f"expected {len(probes)} complete results, got {got!r}")
    for i, result in enumerate(got, 1):
        if type(result) is not dict:
            raise CheckingError(f"input {i}: result is not an object: {result!r}")
        if set(result) == {"err"}:
            valid = type(result["err"]) is int
        elif set(result) == {"path", "method", "params", "prefixed"}:
            valid = (type(result["path"]) is str and type(result["method"]) is str and
                     type(result["prefixed"]) is bool and type(result["params"]) is dict and
                     all(type(k) is str and type(v) is str for k, v in result["params"].items()))
        else:
            valid = False
        if not valid:
            raise CheckingError(f"input {i}: incomplete or mistyped result: {result!r}")
    try:
        json.dumps([probes, got], ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (UnicodeError, ValueError, TypeError, RecursionError) as exc:
        raise CheckingError(f"invalid result/input text: {exc}") from exc
    if oracle is None:
        return []
    bad = []
    for probe, result in zip(probes, got):
        try:
            want = oracle(probe)
        except Exception as exc:
            raise CheckingError(f"oracle failed for {probe!r}: {exc}") from exc
        if want != result:
            bad.append((probe, want, result))
    return bad


def read_report(probes, done):
    """Require normal termination and all ordered private-ID frames, then unwrap."""
    if not isinstance(probes, (list, tuple)) or not probes:
        raise CheckingError("a report requires nonempty probes")
    if type(getattr(done, "returncode", None)) is not int or done.returncode != 0:
        raise CheckingError(f"process failed: {done!r}")
    text = done.stdout
    try:
        if isinstance(text, bytes):
            text = text.decode("utf-8")
        if type(text) is not str:
            raise ValueError("stdout is not text")
        text.encode("utf-8")

        def pairs(items):
            result = {}
            for k, v in items:
                if k in result:
                    raise ValueError(f"duplicate JSON name: {k}")
                result[k] = v
            return result

        def constant(value):
            raise ValueError(f"nonfinite JSON constant: {value}")

        frames = text.split("\n")
        if frames[-1] == "":
            frames.pop()                       # One terminal LF is framing, not another result.
        if len(frames) != len(probes):
            raise ValueError(f"expected {len(probes)} frames, got {len(frames)}")
        results = []
        for i, line in enumerate(frames, 1):
            frame = json.loads(line, object_pairs_hook=pairs, parse_constant=constant)
            if (type(frame) is not dict or set(frame) != {"id", "result"} or
                    type(frame["id"]) is not int or frame["id"] != i):
                raise ValueError(f"input {i}: missing, extra or unordered frame identity: {frame!r}")
            results.append(frame["result"])
        disagree(probes, results)               # Validate the complete list before any semantic call.
        return results
    except (UnicodeError, ValueError, TypeError, RecursionError) as exc:
        raise CheckingError(f"invalid process report: {exc}; stdout={done.stdout!r}; stderr={done.stderr!r}") from exc


def run(mod, probes):
    if not isinstance(probes, (list, tuple)) or not probes or any(
            not isinstance(p, (list, tuple)) or len(p) != 2 or
            any(type(v) is not str for v in p) for p in probes):
        raise CheckingError("probes must be a nonempty sequence of Method/Path string pairs")
    try:
        for probe in probes:
            for value in probe:
                value.encode("utf-8")
        wire = "".join(json.dumps({"ID": i, "Method": m, "Path": p}) + "\n"
                       for i, (m, p) in enumerate(probes, 1))
        d = Path(mod) / "cmd/judgeroutes"
        d.mkdir(parents=True, exist_ok=True)
        module = (Path(mod) / "go.mod").read_text().split("\n")[0].split()[1]
        (d / "main.go").write_text(DRIVER % module)
        done = subprocess.run(["go", "run", "./cmd/judgeroutes"], cwd=mod, capture_output=True, text=True, env=GOENV,
                              input=wire)
    except (OSError, UnicodeError, ValueError, TypeError, IndexError, subprocess.SubprocessError) as exc:
        raise CheckingError(f"route checking preparation/process failed in {mod}: {exc}") from exc
    return read_report(probes, done)


_S08_FROZEN = [('tools/normgen/test_gen_door_lesson.py', 'Model.ok', 'd30ff78ba38cd35e4704e96b4c4a471983dcd93f58bdd3bd1b31a5cb3e4fa564'), ('tools/normgen/test_gen_door_lesson.py', 'disagree', 'e332c31849a603cf3267e7f26766f78087508602934d6a78bd97e5912d43134a'), ('tools/normgen/test_gen_door_lesson.py', 'read_report', 'cb491146085c53d1c54dbbbb205eb8739a50de31fa37d5a52a4cadab00f64653'), ('tools/normgen/test_gen_door_lesson.py', 'run', '765f0a9c0955d8fbd66d5fa678b5fc889dda8d1cbf862d78bb79423d962f3719'), ('tools/normgen/test_gen_door_lesson.py', 'probes', 'ba1cbe48467a83537190e53471f3083d9ad99c5ecb56ad04525706d599e054b4'), ('tools/normgen/test_gen_door_lesson.py', 'expected', '8a7c489e4c7f64ccd774eeafc8363b10a6709322c5b4c82b11c1e6726ba3f436'), ('tools/normgen/test_gen_door_lesson.py', 'DoorLessonBase.tearDownClass', '8d5eaa86110ac5b69b246e646fa16610d1cb4ff1e0e709b303fa64e2ea627c73'), ('tools/normgen/test_gen_door_lesson.py', 'DoorLessonBase.test_fresh', '0def318142f4126edad897de20f31b2e7be0ad5d53e9cbbb2e1085d8523fa9c3'), ('tools/normgen/test_gen_door_lesson.py', 'DoorLessonBase.test_ops', '7513d4f9b2c01407ab78e75b2fad4fcbe47dfb2e62377e027b403b7a88929f44'), ('tools/normgen/test_gen_door_lesson.py', 'RouteServiceControls.setUp', '243d4b1de620f93e8726636f5b37c2cf3808b1f12cf2ab763512c590a3dcea90'), ('tools/normgen/test_gen_door_lesson.py', 'RouteServiceControls.frames', 'c51e647f03a714a6e297a06b38b47c4d86483587f8b7301c105e7064de6b2872'), ('tools/normgen/test_gen_door_lesson.py', 'RouteServiceControls.report', '45bcc4fe9ba187a14a1dec38c13efffae2200c02adfde8e9309ce3bb7dfd8330'), ('tools/normgen/test_gen_door_lesson.py', 'RouteServiceControls.module', '2cefa7609ef259b4241571b1f563a32414de56e4896749e3db9c490793c163a6'), ('tools/normgen/test_gen_door_lesson.py', 'RouteServiceControls.test_complete_positive', '69a1adb7188c3d5624a8331348ef9020df6cb11515e36e7f186ae4bfae9dba83'), ('tools/normgen/test_gen_door_lesson.py', 'RouteServiceControls.test_zero_input_before_preparation', 'b981d674c0993fbd745976f83b1d359f11ea2ddfae7591660c5698fdd91b52cf'), ('tools/normgen/test_gen_door_lesson.py', 'RouteServiceControls.test_zero_short_extra_reports', 'edc73043908283bd93981e7b9c0ade08caa858ae3429327addae364c695d173d'), ('tools/normgen/test_gen_door_lesson.py', 'RouteServiceControls.test_frame_identities', '1e04b3b22392d226483547d9b9295bdb7e5fa5cc28e397491f2f1e2730025c3c'), ('tools/normgen/test_gen_door_lesson.py', 'RouteServiceControls.test_frame_shapes', 'e30c793ec298e6acb71a2e9423139f19d3a90577ca5c87437f232b93f18aaa46'), ('tools/normgen/test_gen_door_lesson.py', 'RouteServiceControls.test_typed_shapes', '69d57e83743ff63f93a3ff42741e6286862cd317225c5178af7827d4eeeb5b52'), ('tools/normgen/test_gen_door_lesson.py', 'RouteServiceControls.test_valid_wrong_values_are_semantic', 'e67ee9781a8f7c571481e5aa0cf068e9c56a28828acadeda396fce160d8ca4ff'), ('tools/normgen/test_gen_door_lesson.py', 'RouteServiceControls.test_strict_json', '08d8b9e2641378dfd976f1ebdf16d26819c95cfcb60ba1d5d3b30d23e38f40a7'), ('tools/normgen/test_gen_door_lesson.py', 'RouteServiceControls.test_preparation_errors', 'c06720649b14a9b970f6d3e58d381070bb222c9e60a2fd80df67e9a77186efce'), ('tools/normgen/test_gen_door_lesson.py', 'RouteServiceControls.test_start_errors', 'b276fb771296e054dedf32ad53e48b55c67d414695879b2d6edac4c00dfc1047'), ('tools/normgen/test_gen_door_lesson.py', 'RouteServiceControls.test_compile_nonzero_even_with_complete_output', 'bc051dd1578f9e0b7b894694ff3debda3f1b46e362b17a8c85645c40dfebe0f8'), ('tools/normgen/test_gen_door_lesson.py', 'RouteServiceControls.test_terminal_errors_are_not_semantic', '62234b0db2ea9a63b36042554ee343c28665f2fd16f1f46ea56d2ffc7e900f83'), ('tools/normgen/test_gen_door_lesson.py', 'RouteServiceControls.test_generation_errors', '77db9cfcb9e71e70d4aeeab95de73baa628ba476bcf48517bed196ae20651d2e'), ('tools/normgen/test_gen_door_lesson.py', 'RouteServiceControls.test_mutant_errors_propagate', '2dd0a81f1b0002b36ffa2c9a22824b4b1bcdc5e1c49b31cf7b89ca51c272bf73'), ('tools/normgen/test_gen_door_lesson.py', 'RouteServiceControls.test_correct_mutant_survives', '2b36bac03767f6e28c4e74ef15a10871ba86636f8af930e29a2e33eff7c276de'), ('tools/normgen/test_gen_door_lesson.py', 'RouteServiceControls.test_named_semantic_mismatch', '38858b50a03a5d4e6d120b32ab82bdeb10a026b2d78db354d5127a464f7c2dcb'), ('tools/normgen/test_gen_door_lesson.py', 'RouteServiceControls.test_mutation_applicability', 'a8428bc4a8af3f09e285a9ebb5276774a244cc3ccf78868904ed9ed1e1bedf5e'), ('tools/normgen/test_gen_door_lesson.py', 'RouteServiceControls.test_unicode_and_terminal_lf_neighbours', 'd2d17b21cfa730eebc9ebf7c34643196d581ddd22f80f4a4bb53b6b511fdca29'), ('tools/normgen/test_gen_door_lesson.py', 'SchemaPositionControls.setUp', 'a08776372f2c76ab4234953a60b000b0a508a5c3d66fefd4dce09d42166e5eb9'), ('tools/normgen/test_gen_door_lesson.py', 'SchemaPositionControls.test_00_schema_map_array_and_escaped_pointer_neighbours', 'd88e1ac61b649ba6716602321b77393cf76534a397b9298ad48547ac021654c9'), ('tools/normgen/test_gen_door_lesson.py', 'SchemaPositionControls.test_01_bad_array_indices_escapes_and_fragments_are_errors', 'e0cfd45e125fac2d9e1c4df6b2dc5a59f19c0bcff026277eaaf6c9cdb214d75a'), ('tools/normgen/test_gen_door_lesson.py', 'SchemaPositionControls.test_02_literal_ref_values_are_data_even_when_the_uri_is_unsafe', 'e8f4c5c32d5e6d6dce5c0d9c16a1611ead840b786e2e1ff79ff1eb33a9ca9f53'), ('tools/normgen/test_gen_door_lesson.py', 'SchemaPositionControls.test_03_schema_of_a_property_named_ref_is_still_traversed', '9e6c18982b501b3b02ed5487ecdbb1e3788d1efe5832424d2e0bd5ffdd5a592e'), ('tools/normgen/test_gen_door_lesson.py', 'SchemaPositionControls.test_04_schema_ref_siblings_keep_their_own_constraints', 'd0f012514e622bb700d169ef038487a9c57f12fd75513a2d813e859d182f23d1'), ('tools/normgen/test_gen_door_lesson.py', 'SchemaPositionControls.test_05_schema_shaped_literal_data_is_not_a_schema_target', '85959f3eaecff2252da6f33a1c259ed3ec8a34ba39e49f48b1569e16f63da8e0'), ('tools/normgen/test_gen_door_lesson.py', 'SchemaPositionControls.test_06_json_cannot_replace_parameter_response_or_pathitem', '3535e8090b1146ff3cf6e1afcb2345b236aa617cdbe300865f11698e8b7dccb9'), ('tools/normgen/test_gen_door_lesson.py', 'SchemaPositionControls.test_07_openapi_object_kind_and_whole_document_are_preserved', '2438ec0e227077bfdbb7b5ca0282857bb11ef475f4703f3468ab753f0cf4eabc'), ('tools/normgen/test_gen_door_lesson.py', 'SchemaPositionControls.test_08_local_parameter_reference_and_json_schema_parameter', '638e20e81c05571bbbe2e6dccf79465c77b2a18ffb82da05b303c299f5a69684'), ('tools/normgen/test_gen_door_lesson.py', 'SchemaPositionControls.test_09_parameter_aliases_keep_both_operation_declarations', '21a31f8748e60f0ae8554c9ce16039fd71ea70cf6aa09fabd8bb6b275c03afa4'), ('tools/normgen/test_gen_door_lesson.py', 'SchemaPositionControls.test_10_missing_parameter_context_cannot_guess_a_source', '8af45e00b5ba752432b1ba9b0d81d95eaba4b96bd1462a512df64d1d834e5ab3'), ('tools/normgen/test_gen_door_lesson.py', 'SchemaPositionControls.test_11_extensions_are_opaque_until_a_typed_reference_enters_them', 'cc618ed3a0173d90c6663c5eab7490602f9cd5b6e667f63959c2b8d4cae5cb67'), ('tools/normgen/test_gen_door_lesson.py', 'SchemaPositionControls.test_12_equal_nonalias_values_do_not_share_late_permissions', 'a052af1b013317fc1d792902a1e6171fee4a8c67f1856db96a379f866a282d8b'), ('tools/normgen/test_gen_door_lesson.py', 'SchemaPositionControls.test_13_independent_schema_errors_are_not_false_verdicts', 'b5f36d918307eb7138c1e49410c8dcfa36babd4ae5acc6dc099ce8ad33d75da9'), ('tools/normgen/test_gen_door_bodies.py', 'bundle_of', '8db3f43ea61522c367ecb36dcb65ee80397041a99801d325d6e16a9ed36c7913'), ('tools/normgen/test_gen_door_bodies.py', 'tables_of', '5ace0b6d5dbd23762aae9b31c1e32049684e1e7c7877ccbec440bcdb77779913'), ('tools/normgen/test_gen_door_bodies.py', 'Gen.__init__', '052c893a67f821371c804d5918ba0631ff7ae34f949c1ce45d2327f8a43d6864'), ('tools/normgen/test_gen_door_bodies.py', 'Gen.node', '69b19c2977d4e341664ef3e3abd1312e7ab89c70367375d98c1c5f1b342559b1'), ('tools/normgen/test_gen_door_bodies.py', 'Gen.strings', '13c0bb438192967ea00caabd189f67e57702129b5070f0a59990d8e7a5204abd'), ('tools/normgen/test_gen_door_bodies.py', 'Gen.pattern_samples', 'c4980773cacbb59bbfb128355eb3f12786ab4f43f5aedeadff99647a34ef8221'), ('tools/normgen/test_gen_door_bodies.py', 'Gen.values', '65202fbcc93c17fca9bf6608fff8ae183713385bedd3e4e0b19513e098b9aee5'), ('tools/normgen/test_gen_door_bodies.py', 'response_object', 'd1e241d8f495b5d0649845731259a2381ece976779c5f1df3919125a4606c067'), ('tools/normgen/test_gen_door_bodies.py', 'response_constant', '065f123bf5639066d98614357058c68bf24a5b9dab5ecb8aee39f26e8161dce9'), ('tools/normgen/test_gen_door_bodies.py', 'checked_values', '88d175a13a52247cdf7ce2844cd39214826f41f130af8be21d56ce04d58368ac'), ('tools/normgen/test_gen_door_bodies.py', 'read_report', 'b4f5fa0d454c7c1f59e9f1927c5ac671687d2f67584faafa77221aaadf1df1bc'), ('tools/normgen/test_gen_door_bodies.py', 'go_process', 'f3c0e8e0f0e08180159b0325bdfeaa9fa6e76fffcc8382a43c34b72859cfd2a1'), ('tools/normgen/test_gen_door_bodies.py', 'disagree', '61b1ee0795c020b267f56474278a9205b7f2448fd428fa2ec9b5348a2be2cdf7'), ('tools/normgen/test_gen_door_bodies.py', 'run_go', 'a9ad04b8395fb093f0cf1170afec957cc8d4eb8151b66a6e5033f9ddf1d0c59f'), ('tools/normgen/test_gen_door_bodies.py', 'oracle', 'ea203d89f7935b8b226acc863269699d6557d1b70b5ffd8156a8f69dca66fe15'), ('tools/normgen/test_gen_door_bodies.py', 'cases_for', '8dd99fd435f7f6e4fe6b5041179b3876f00dbfd2c484affd8f6854fee5affd53'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReader.__init__', '3ee444d3aa324331d26ae46d875b6797e73d6eb4899ed5c2d9a556c798c086aa'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReader.escape', '79cd3c02d29cc2d7a031e51460c691d7168a0af4795b0f3146302c3c30dc68c3'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReader.fragment', 'a371552c315c6a968cdddbfdd77d94cd65b090a557a9eea50b74d39f3876baa1'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReader.physical', '24468af12453b3da75229cfd227152c9a162db9f5a4b8161774fdfaf932759d3'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReader.owner', 'df0ee85ee7ad5f64c1fe417cccfab37d2bfc6c554778c787a0460cb318a21ec5'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReader.is_json', '8d5fcf5f23cd79945ef14a313b6104172aadc46492e42ae05f42da693c4c69f2'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReader._json_pairs', 'af6e2d306f2c8a38067fd340d65834395270f13b781e9dd1a783c14f8b8e37b8'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReader._constant', 'ee428586fb18afc9c887a452bad240765a70945414a1dd824f5a744659cd37a5'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReader._json_tree', 'e9d0c4f9a2ca48a67dff5a2e5686bd024e1125fd91f6fbb9117afc4b9de7559a'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReader.document', '8207901d03b8375b34e2693c42295b282ec6b8360fb22da6923a829777cd103b'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReader._index', '087d9d97d4c42b02a87945f732f2effcb5bb5d8ad3efb82a10612fc1af08353f'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReader.value', '510c0a472b390b53da57421c8c704d2c93be3ad36994808341d5100b1e880686'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReader.at', 'f0e751c401b5bfb6595b78c1b16867d3a9dbc6d41590f1b5aca52d0ec471625a'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReader._late', '499029179a8d4fef6acfb1d8ae8149d1aaefcacb24280069493f786d2c486fb7'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReader._reference', 'f4080cea6695b0584fbf86e7ae7c91c7d82453d58bebd84fa8eb785f6f136369'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReader._walk', '9dc231e1530db96753b26539e745d832972c3e47b514672617bc887db12b0553'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReader._check_schema', 'e898f10ee2802794b49c19b19a88b630c221871fb6ba9e4b81f49e9c991079b4'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReader.uri', '0edb5200fe6bd7b4129ae5027fca3783e9cd9073d5661573bfc5f5c2bcb10136'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReader.validator_at', 'd5449f798ac3bca87b37b05d55beeb1a2b301ad05a2f462a2281d17fff25c1e1'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReader._locations', 'bec3ce82178bddc85dc081f41b7a5490216281ae554b6f86dc0e7c26ae308a9a'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReader.resolve_object', 'e73e59cc3ba1fd35e7b800dc4f2e983c4cf5eb6e3c5ec8bb964913e2fa80eec7'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReader.schema_type_node', '2b5bfba7bcf2afa9ac7c4781a5a51cb7d3fc38367170eaa6c500ce7af93a893f'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReader.parameter_validator', '4681bde317733cea1e1024134f55adbb67691cac1fdb278297b62ffbd4622ace'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReader.validators', 'dbbb7df1a48481cfc00de1c99a7ab6f85da54e6fb8fbd4b9f10a284a2607d61a'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReader.canonical', 'ff12c99b7e7f4948c7c44d4c378df4ca75bfd50acd25fdb013e52406228ce907'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReader.bundle_origins', '6bdc3284c97a231219ced7ea6b8d8bc168c94b78d62ce2a60007ef8966a40714'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReader.compare', '56383840167be9ecb03432206bc8a76e2c4204c1ee6e69a22e261bbeba8d08b7'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReader.literal_table', '1557a382d5b269fb066dfb787edcdf925ddbe148cb740a97a0bfac23ed72459a'), ('tools/normgen/test_gen_door_bodies.py', 'synth_module', '64ae86253f1b6bf57f26669f75be849f8cad3c43efe37c7d9a046775230e2fa0'), ('tools/normgen/test_gen_door_bodies.py', 'DoorBodiesBase.setUpClass', 'ed892c5250d188f88505bfbb9e9aa096fa6236d40d3125ad8ef67c6b8d6fe73b'), ('tools/normgen/test_gen_door_bodies.py', 'DoorBodiesBase.tearDownClass', '8d5eaa86110ac5b69b246e646fa16610d1cb4ff1e0e709b303fa64e2ea627c73'), ('tools/normgen/test_gen_door_bodies.py', 'DoorBodiesBase.test_fresh', '6f3dc13378496cac3eac49ccef22b73cb557f84dbaa43aa0844f2647fc01eaa7'), ('tools/normgen/test_gen_door_bodies.py', 'DoorBodiesBase.test_bundle_equals_source', 'e29e57de500f40cd14e9e82f96d7e9e32f1406d199c6ecbac1fc67454b0cd978'), ('tools/normgen/test_gen_door_bodies.py', 'DoorBodiesBase.test_validate_against_oracle', 'b02e5db2587916d8a758baae56aea98949577740de732e23d0d1b3a75cb2cdaa'), ('tools/normgen/test_gen_door_bodies.py', 'DoorBodiesBase.test_synthetic', 'd2b233e7ea6355391a1bd66c7de9886ccb8a9872f7bded86481b9c806de939d2'), ('tools/normgen/test_gen_door_bodies.py', 'DoorBodiesBase.test_api', 'e76aef33a1ff16967ec25a842ca540df41523d8cca77a301dc93a515c780c82a'), ('tools/normgen/test_gen_door_bodies.py', 'DoorBodiesBase.test_mutants', '177bc38a47a3ec1465aaa5f8d71ed0a3e2e053eaec64252fc715e23cfdddfaab'), ('tools/normgen/test_gen_door_bodies.py', 'BodyServiceControls.setUp', '37bcb7bf356ed51d6454bd0d87beeb5e3069f66f9c6fc6f30ede6c7f400a14b0'), ('tools/normgen/test_gen_door_bodies.py', 'BodyServiceControls.report', 'e3a3be0c3b53b960bab71546c1accadc1230e57290306ba3171bf7d6ea0fa0d4'), ('tools/normgen/test_gen_door_bodies.py', 'BodyServiceControls.frames', 'ba5a70d83498634c35c3178f555e6cc9beedc90f2024075d5177e69e0dfafe6b'), ('tools/normgen/test_gen_door_bodies.py', 'BodyServiceControls.test_complete_equal_values_keep_distinct_input_identities', 'b26db0270bf07d88bed449cec9c48126812aa484843aa93b1126ea527a48d876'), ('tools/normgen/test_gen_door_bodies.py', 'BodyServiceControls.test_reports_require_nonempty_complete_ordered_identity', '9a10744d9b4d618d1cc3b596c9698685ce45ecb3c24caec2dadec7a17afaf1ab'), ('tools/normgen/test_gen_door_bodies.py', 'BodyServiceControls.test_process_and_preparation_errors_are_checking_errors', 'da84666ce1f5dbcc405eaff9581131dbca56cec10577f44df8e0f162e804e0d1'), ('tools/normgen/test_gen_door_bodies.py', 'BodyServiceControls.test_complete_report_is_checked_before_the_oracle', '549836272bf4455e1ba46968e86f634cb07a87d26e76abf21dde5f64dbd2e764'), ('tools/normgen/test_gen_door_bodies.py', 'BodyServiceControls.mutant_case', '2c67dbcb8f006484196a5de00f9a6c2e9bd4cffac71f226cccea8ec820020765'), ('tools/normgen/test_gen_door_bodies.py', 'BodyServiceControls.test_mutant_loop_does_not_absorb_checking_errors', '377e109d7fa3bb10946fe92a864ce525a3534d2c48ec1e90316c521e63203001'), ('tools/normgen/test_gen_door_bodies.py', 'BodyServiceControls.test_a_complete_correct_mutant_report_remains_a_survivor', 'd1866bcfa04d9a7743225bc475512d7f10a5d019a3b5c0b6fa0510ac1d88930e'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReaderControls.setUp', '43c4e3b70754207a0bad316052b3094aab9249eb1bd4440e15f16f349959c0a3'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReaderControls.write', '2563171e8aa5e88f808f0cd835fdc99bd1651e4aec18570e177e9029cfffc14d'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReaderControls.api', '22c13256041e07c9da199c2b6751c6533e7e701136e4c8d218609c34953c894c'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReaderControls.schema', '683d9ad93dfacb25764d07809cbf59fbc1ef2c1e46ab5b466fb2bd4bba4bf9a4'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReaderControls.reader', '81ae5c93b9d3f023c656f436ae986b138b14fce261e182a7b3ca5ad8b242124c'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReaderControls.late', '216340f60c8e1de28e666bd2bcd6c1e1630dad7f0cac1840f25c331f4feb6d74'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReaderControls.test_00_actual_four_positions_without_document_or_cache_injection', '6227003eaf3108176c198aa8f59c3ff87ddec3fc2252087a8bebfecac0259b72'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReaderControls.test_01_actual_p10_reference_bearing_aliases_keep_each_coordinate', 'ce1bfc62d9844095b2caa16bbd3bcc69ca50958dd62d4ef5fc34ade0204bf44b'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReaderControls.test_02_root_json_and_transitive_local_source', '4b7694bc2aab331f91e0ce4df6c439526581e3d00977afb41453bf4f6accd73d'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReaderControls.test_03_boolean_schemas_are_not_scalar_errors', '2b24cb97d17090646f872d126e1caa2fc3fd667a2398f4d1b86205a6f88c1d89'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReaderControls.test_04_early_p10_to_current_p09_pointer', '620e1a890b74ebf8065c68d8806df420de9ba85383f849a66c6d48dd7b3f1cd3'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReaderControls.test_05_exact_late_door_before_negative_neighbours', '407b3678435bfc679f4f2eb12a0484e997514fa515e4de4578e62f5f1b2498d5'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReaderControls.test_06_missing_chapter_and_wrong_declared_target', '88d0be27c46d30d7fea3ba07ac47ac0f86541e4c4cca9b1e424382f9d9e86ba8'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReaderControls.test_07_alias_under_door_and_components_does_not_inherit_permission', '53f0d0748248e926d4a11054529c719af27b975fe850446c9a83b359d9047e85'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReaderControls.test_08_real_cache_fill_does_not_authorize_later_declaration', '3c23dfb62c008df9b057733edfb4aed3b4e1c31daa544212b0dff09bb4d3b7cd'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReaderControls.test_09_standalone_json_has_no_inherited_late_door', '56c9e9ede4b94f067e659563e25cf2a7505d030d1584d79a91514b8c693dfb13'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReaderControls.test_10_legal_reference_aliases_preserve_both_source_positions', 'ebba288eab0c14519cee2ce4093581ee3eef47fb02263429ca24a1b46ca57d58'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReaderControls.test_11_cyclic_alias_structure_is_a_checking_error', '447b57369ae49f9e4c6709dcc75183f16136a02755eb9bf18b99e96d8e35cabc'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReaderControls.test_12_common_cannot_read_a_lesson', '5968e2398a6e32c7ce9b2fc525a81898f83d4a1f6f4ada38bc43b0b2db620f68'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReaderControls.test_13_relative_base_is_the_actual_declaration_resource', '17e117c6cf2015e99addea60f92a4a5ca83c7d579d639a30d868d79a69f4b38c'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReaderControls.test_14_network_absolute_query_and_missing_resources_are_errors', 'a21b524631bea6b8a6b65d9363ffc8fdc7f6d17cb6cf20b00e9d01a300ffa78c'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReaderControls.test_15_physical_boundary_and_real_owner_follow_symlinks', 'ac4322b89509df643798cadbbadfaa75069978574079007f08b16e44110a6fb4'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReaderControls.test_16_cross_file_cycle_differs_from_local_recursion', '546eb1094bcec4d0de18916d0cf8abf2091bb4d6c5cf3e35cd7c60162a1c90f9'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReaderControls.test_17_malformed_duplicate_nonfinite_and_scalar_json', 'ad8a656210f5c4fdd2f1308ed4f09bf146a755af87c9f3ed2462f9f1289e1ce2'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReaderControls.test_18_schema_dialect_and_base_are_not_silently_changed', '78df18f87a7a3c88fe1952aea7ebe89868278d43b882bf5f59737bf3dfbf371a'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReaderControls.test_19_source_cache_is_not_healed_after_input_changes', 'cab982fec0d61a8ca991476b8b054912c041d8043a5c8942630b44b21a2711d3'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReaderControls.test_20_actual_dotted_definition_is_covered_not_skipped', 'bbb43a3a9f96a7bff2af09363f4f70ca2afb82d2ca4b11b601d00cf8138cbbcc'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReaderControls.test_21_unmapped_ambiguous_and_empty_comparisons_are_errors', '4ba3bbbb3fced759716775c069acf2a029dfdf6f35c4fae3f07698e5f4305a43'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReaderControls.test_22_proven_alias_origins_retain_every_coordinate', '67cdeffc37ba205d479c06a0fa457b7437b89409e6d59fd603962064d05bcc26'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReaderControls.test_23_actual_metadata_tables_are_strict_and_are_not_the_oracle', 'e3c140a12cf04f1670205ebed8f3c41613734d212cc7aae406ddb80499c629ff'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReaderControls.test_24_binding_table_completeness_and_source_operation_identity', '2bb1fac29f67fc313efc755839af28a5deea7327f39ea322f59975bc21629042'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReaderControls.test_25_ref_sibling_constraints_belong_to_the_declaration_not_its_target', '2fa2df47f9735aa971f839de2fa529533b2209dfe2f53fd7cd2ddb64035a8dcb')]

_S08_MUTABLE = [('tools/normgen/test_gen_door_lesson.py', 'Model.__init__', '03d887a970132a1162f594f80871a6e3f0c45985598304f70d52359b05188888'), ('tools/normgen/test_gen_door_lesson.py', 'Model.load', '84cb83bc144793b426def6ec8ca857241c54c724add0a9dd3732a240a2069894'), ('tools/normgen/test_gen_door_lesson.py', 'Model.deref', '3e0a8fe90ebda7fb2a5594a43100c85042f72698b5354be8906bbe5607ac2e13'), ('tools/normgen/test_gen_door_lesson.py', 'Model.schema', '0a17d328639806050d0b476d7adfbda370e3955ac9904230edbe2c5b92851c9b'), ('tools/normgen/test_gen_door_lesson.py', 'Model.templates', '73874cea37770e773f903f29a7952dc4bf19816ec0d83a114bb784f56405b63e'), ('tools/normgen/test_gen_door_lesson.py', 'Model.rank', '64b47c61e51d8ab9f131828543324d83cb8cb8b517f6695a38647f2cfeb8f366'), ('tools/normgen/test_gen_door_lesson.py', 'Model.route', '75ca2e24631985cb302dad2605da09e33bbe69050982ac23f4235874ed1edb32'), ('tools/normgen/test_gen_door_lesson.py', 'Model.sample', '6a86ee41a0f0b0fdc0651b0208241723ce1cd4c941193de83915ad3987e3d0fc'), ('tools/normgen/test_gen_door_lesson.py', 'DoorLessonBase.setUpClass', '69dab29887583afc0d6e4a8e25ef6dd75594f134e1b588ed6e8cd4f78dd805c1'), ('tools/normgen/test_gen_door_lesson.py', 'DoorLessonBase.test_probes', '9178e1587389b8caad3b99a2e81aff5ab73aec92986fdb4bbef194f319d1f3ad'), ('tools/normgen/test_gen_door_lesson.py', 'DoorLessonBase.test_mutants', 'ea4907714ff217943f701b4cb51444166594cd8157e9d94dd2f4ff34e50d44c4'), ('tools/normgen/test_gen_door_lesson.py', 'RouteServiceControls.mutant_case', '17de7ca2cc0f35be2ad8f098d1ca721e022dfc7e501d7769227c3ed25dc0f0e5'), ('tools/normgen/test_gen_door_lesson.py', 'RouteServiceControls.test_complete_before_oracle', '7cc5cf9aafeb5856fa0d43fa5df146a4f20dcdf6977d6b7936305a51879bbcc7'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReader.output_bindings', 'd8178c39f26b04be8580af5f4796e86d7949f75e747bd2eb7bf9b06292528e07'), ('tools/normgen/test_gen_door_bodies.py', 'SourceSchemaReader.parameter', '26e713c338fd16c76d5eda0bbdcbf7cc5b1284f45acaadbb3048764c909232aa'), ('tools/normgen/test_gen_door_bodies.py', 'DoorBodiesBase.test_params', 'fed7e0e4554ec805407f9d0338b7144104daa68ffa070303b258e82942f5cf69')]
_S08_OLD_ASSIGNMENTS = [('tools/normgen/test_gen_door_lesson.py', 'HERE', '65eefe4da79587f39b6d92c49700f89186d9cc4fcd1165a730bcdbb58aa5fc02'), ('tools/normgen/test_gen_door_lesson.py', 'ROOT', '3ca87edaf167e2bfa28b5b8acad00a2a832fe57538e31569eba9c5f979ab407a'), ('tools/normgen/test_gen_door_lesson.py', 'LESSONS', '7b57216c88f150296a6db8bbdf9e907addce45b7dec65c5e8ca8927578962f7e'), ('tools/normgen/test_gen_door_lesson.py', 'GOENV', '51cf862cec7861a3727427f4cccbea71714acd827999b8178d9150b756950ffe'), ('tools/normgen/test_gen_door_lesson.py', 'METHODS', '67a560fc62ce72bccf32ae38c22b13accc5a62d7c3fe789857e0d0779bca3420'), ('tools/normgen/test_gen_door_lesson.py', 'CATALOG', 'cfb964e78086e627b2e05b72e756ac59b9d0f890cf7d7bff46dfb0bae9c49ca1'), ('tools/normgen/test_gen_door_lesson.py', 'SAMPLES', '5b096ae7a70db627c3a548d5beb9f2f1b1f02b7112135e1e7772a24a703506c5'), ('tools/normgen/test_gen_door_lesson.py', 'DRIVER', 'c667f606c538ce358b806e69237ff6d5974e6fa3a305fc8852d88de3ac08171a'), ('tools/normgen/test_gen_door_bodies.py', 'HERE', '65eefe4da79587f39b6d92c49700f89186d9cc4fcd1165a730bcdbb58aa5fc02'), ('tools/normgen/test_gen_door_bodies.py', 'ROOT', '3ca87edaf167e2bfa28b5b8acad00a2a832fe57538e31569eba9c5f979ab407a'), ('tools/normgen/test_gen_door_bodies.py', 'LESSONS', 'e9fb07f8c10e06675d7c1036d9e3a7c9a503dd1a201bfe4358040889133ca238'), ('tools/normgen/test_gen_door_bodies.py', 'GOENV', '51cf862cec7861a3727427f4cccbea71714acd827999b8178d9150b756950ffe'), ('tools/normgen/test_gen_door_bodies.py', 'DRIVER', '95fc8ed802a12acd75afd88e47eb28eff65d986cc76e224ad47ea466eb9344fc'), ('tools/normgen/test_gen_door_bodies.py', 'SYNTH', 'a0cf019123e3f558bea3fae5143e69e5d0f9dfe9918f98b24a3fd15032b758d5'), ('tools/normgen/test_gen_door_bodies.py', 'SYNTH_VALUES', '38b760b4e3c8a28b27f57b04e5478f5acb860fca3e8b603b7ea199cca865aa13'), ('tools/normgen/test_gen_door_bodies.py', 'SYNTH_CASES', '7fdb40729bea70c40ff54aa94bb737e97eb68231121483f9307ea720ca06035c')]
_S08_PARAM_SLICES = ['                    for raw in ("1", "0", "-3", "1.5", "1e3", "abc", "true", "", "local", "cluster", "newest", "t",\n                                "bytes=0-9", "sha256-" + "0" * 64, "x" * 200, "1_000", "1__0", "1e400", "1e-400", ".5", "5.",\n                                "007", "18446744073709551615", "18446744073709551616", "-0", "+1", "30", "30.1", "0.0"):\n                        cases.append((op, prm["in"], prm["name"], raw, sch, Path(base).resolve(), bool(prm.get("required")),\n                                      prm.get("x-query-lexeme")))\n', '        def want(c):\n            op, place, name, raw, sch, base, req, lex = c\n            t = node(sch, base).get("type") if isinstance(node(sch, base), dict) else None\n            v = raw\n            if lex:                                       # Independent x-query-lexeme model from P/05 forms/README.\n                if not re.fullmatch(lex["pattern"], raw):\n                    return False\n                text = raw.replace(lex.get("strip", "") or "\\x00", "") if lex.get("strip") else raw\n                if lex["parse"] == "number":\n                    f = float(text)\n                    if f in (float("inf"), float("-inf")):\n                        return False\n                    v = f\n                elif lex["parse"] == "integer":\n                    v = int(text)\n                else:\n                    n = int(text)\n                    if not 0 <= n <= 2 ** 64 - 1:\n                        return False\n                    v = raw\n            elif t in ("number", "integer") and re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\\.[0-9]+)?(?:[eE][+-]?[0-9]+)?", raw):\n                from decimal import Decimal              # Match Go big.Rat exactly:1e-400 is not an integer.\n                v = Decimal(raw) if any(ch in raw for ch in ".eE") else int(raw)\n                if isinstance(v, Decimal) and v == v.to_integral_value():\n                    v = int(v)                           # A mathematically integral value such as1e3 is integer per Draft 2020-12.\n            elif t == "boolean" and raw in ("true", "false"):\n                v = raw == "true"\n', '        prog = ["package main", "", "import (", \'\\t"encoding/json"\', \'\\t"fmt"\', \'\\t"os"\',\n                f\'\\t"{(self.fresh / "go.mod").read_text().split()[1]}/apidoor"\', ")", "", "func main() {",\n                "\\tenc := json.NewEncoder(os.Stdout)"]\n        for identity, (op, place, name, raw, *_) in enumerate(cases, 1):\n            nm = name.lower() if place == "header" else name      # Header names are case-insensitive.\n            prog.append(f\'\\t{{ _, _, v := apidoor.CheckParam(apidoor.{op}, {json.dumps(place)}, {json.dumps(nm)}, \'\n                        f\'[]string{{{json.dumps(raw)}}}); if err := enc.Encode(map[string]any{{"id": {identity}, \'\n                        \'"result": v == nil}); err != nil { fmt.Fprintln(os.Stderr, err); os.Exit(2) } }\')\n        prog.append("}")\n        try:\n            d = self.fresh / "cmd/judgeparams"\n            d.mkdir(parents=True, exist_ok=True)\n            (d / "main.go").write_text("\\n".join(prog) + "\\n", encoding="utf-8")\n        except (OSError, UnicodeError) as exc:\n            raise CheckingError("cannot prepare parameter service") from exc\n        got = read_report(cases, go_process(self.fresh, "./cmd/judgeparams"))\n        bad = disagree(cases, got, want)\n        self.assertEqual(bad[:3], [], f"{len(bad)} of {len(cases)} parameter verdicts disagree")\n']

_S08_PARTIAL = [('DoorLessonBase.test_probes', '9178e1587389b8caad3b99a2e81aff5ab73aec92986fdb4bbef194f319d1f3ad'), ('DoorLessonBase.test_mutants', 'ea4907714ff217943f701b4cb51444166594cd8157e9d94dd2f4ff34e50d44c4'), ('RouteServiceControls.mutant_case', '17de7ca2cc0f35be2ad8f098d1ca721e022dfc7e501d7769227c3ed25dc0f0e5'), ('RouteServiceControls.test_complete_before_oracle', '7cc5cf9aafeb5856fa0d43fa5df146a4f20dcdf6977d6b7936305a51879bbcc7')]

def _assert_s08_preservation():
    import ast
    present = {}
    for relative in {v[0] for v in _S08_FROZEN}:
        text = (ROOT / relative).read_text(encoding="utf-8")
        lines = text.splitlines(keepends=True)
        def walk(node, prefix=""):
            for child in getattr(node, "body", []):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    start = min([child.lineno] + [d.lineno for d in child.decorator_list]) - 1
                    present[relative, prefix + child.name] = _sha("".join(lines[start:child.end_lineno]).encode())
                elif isinstance(child, ast.ClassDef):
                    walk(child, prefix + child.name + ".")
        tree = ast.parse(text)
        walk(tree)
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                present[relative, node.targets[0].id] = _sha("".join(lines[node.lineno-1:node.end_lineno]).encode())
    if len(_S08_MUTABLE) != 16 or len({(p, n) for p, n, d in _S08_MUTABLE}) != 16:
        raise CheckingError("canonical mutable16 inventory changed")
    for relative, name, before_digest in _S08_MUTABLE:
        if (relative, name) not in present or not re.fullmatch("[0-9a-f]{64}", before_digest):
            raise CheckingError("missing canonical mutable block")
    body = (ROOT / "tools/normgen/test_gen_door_bodies.py").read_text(encoding="utf-8")
    if any(body.count(part) != 1 for part in _S08_PARAM_SLICES):
        raise CheckingError("old parameter/coercion/service source changed")
    lesson_text = (ROOT / "tools/normgen/test_gen_door_lesson.py").read_text(encoding="utf-8")
    lesson_lines = lesson_text.splitlines(keepends=True)
    methods = {cls.name + "." + fn.name: fn for cls in ast.parse(lesson_text).body if isinstance(cls, ast.ClassDef)
               for fn in cls.body if isinstance(fn, ast.FunctionDef)}
    for name, digest in _S08_PARTIAL:
        node = methods[name]
        raw = "".join(lesson_lines[node.lineno-1:node.end_lineno])
        if name == "DoorLessonBase.test_mutants":
            addition = "        if self.model.context:\n            return _test_source_route_mutants(self)\n"
            if raw.count(addition) != 1:
                raise CheckingError("active Source mutation delegate missing/duplicated")
            raw = raw.replace(addition, "")
        if name == "DoorLessonBase.test_probes":
            for addition in (
                    "        pr = _source_complete_probes(self.model, pr)\n",
                    "        want = _source_applicable_want(self.model, want)\n",
                    '        if self.model.context:\n            self.assertFalse(missed, f"mandatory source route coverage GAP: {sorted(missed)}")\n'):
                if raw.count(addition) != 1:
                    raise CheckingError("source coverage plumbing missing/duplicated")
                raw = raw.replace(addition, "")
        raw = raw.replace("self._route_executor(self.fresh, pr)", "run(self.fresh, pr)")
        raw = raw.replace("self._route_executor(mod, pr)", "run(mod, pr)")
        raw = "".join(line for line in raw.splitlines(keepends=True)
                      if "obj._route_executor = lambda mod, pr: run(mod, pr)" not in line and
                      "obj.model.context = None  #" not in line)
        if _sha(raw.encode()) != digest:
            raise CheckingError("plumbing-only semantic/fixture block changed: " + name)
    for relative, name, digest in _S08_FROZEN + _S08_OLD_ASSIGNMENTS:
        if present.get((relative, name)) != digest:
            raise CheckingError("frozen old service/oracle block changed: " + name)

# Private S08 instrumentation observes existing APIs. These templates are never a routing oracle.
_S08_CONTEXT = "p06-5-manual-pair:43750c8e:root=testsub"
_S08_TEST = "TestReview103S08Observation"
_S08_PACKAGE = "normgen/p06/apidoor"
_S08_VIEWS = (
    ("course-testsub.json", "357f87568ec750317624b872c69aa9826a0e196a94143f7de91a2a988b2a7447"),
    ("course-testsub2.json", "a72a6d2b8786b7d3ddb27a6d83ea62c223e6a2018b606366d30bd6e7ea0078c6"),
)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _unique_json(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise CheckingError(f"duplicate private JSON key: {key}")
        value[key] = item
    return value


def _reject_constant(value):
    raise CheckingError(f"nonfinite private JSON: {value}")


def _finite_float(value):
    parsed = float(value)
    if not float("-inf") < parsed < float("inf"):
        raise CheckingError("nonfinite private JSON number")
    return parsed


def _strict_json(raw):
    try:
        value = json.loads(raw, object_pairs_hook=_unique_json, parse_constant=_reject_constant, parse_float=_finite_float)
        def check(v):
            if type(v) is str:
                v.encode("utf-8", "strict")
            elif type(v) is dict:
                for key, item in v.items():
                    check(key)
                    check(item)
            elif type(v) is list:
                for item in v:
                    check(item)
        check(value)
        return value
    except (UnicodeError, TypeError, ValueError, RecursionError) as exc:
        raise CheckingError(f"invalid private JSON: {exc}") from exc


def _ndjson(raw):
    try:
        text = raw.decode("utf-8", "strict") if type(raw) is bytes else raw
        if type(text) is not str or not text:
            raise CheckingError("missing NDJSON")
        lines = text.split("\n")
        if lines[-1] == "":
            lines.pop()
        if not lines or any(not line for line in lines):
            raise CheckingError("blank NDJSON frame")
        return [_strict_json(line) for line in lines]
    except UnicodeError as exc:
        raise CheckingError("NDJSON is not UTF8") from exc


def _text(raw):
    try:
        if type(raw) is bytes:
            return raw.decode("utf-8", "strict")
        if type(raw) is str:
            raw.encode("utf-8", "strict")
            return raw
    except UnicodeError as exc:
        raise CheckingError("process output is not UTF8") from exc
    raise CheckingError("process output is not text")


def _accounting_dependency_digest(raw):
    import ast
    text = raw.decode("utf-8")
    selected = [n for n in ast.parse(text).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
                and n.name in ("CheckingError", "complete_go_tests")]
    if [n.name for n in selected] != ["CheckingError", "complete_go_tests"]:
        raise CheckingError("missing/duplicate service-accounting dependency")
    return _sha("\n".join(ast.get_source_segment(text, n) for n in selected).encode())


def _complete_observer_go_test(done, package=_S08_PACKAGE, test=_S08_TEST):
    """Service accounting only; no semantic comparison on an incomplete process."""
    if type(getattr(done, "returncode", None)) is not int or done.returncode != 0:
        raise CheckingError("observer did not terminate normally with exit0")
    stdout, stderr = _text(getattr(done, "stdout", None)), _text(getattr(done, "stderr", None))
    if stderr:
        raise CheckingError("observer wrote diagnostic stderr")
    events = _ndjson(stdout)
    state = 0
    allowed = {"Time", "Action", "Package", "Test", "Elapsed", "Output"}
    for e in events:
        if (type(e) is not dict or set(e) - allowed or e.get("Package") != package or
                type(e.get("Action")) is not str or
                ("Time" in e and type(e["Time"]) is not str) or
                ("Test" in e and (type(e["Test"]) is not str or e["Test"] != test)) or
                ("Output" in e and type(e["Output"]) is not str) or
                ("Elapsed" in e and (type(e["Elapsed"]) not in (int, float) or
                 not float("-inf") < e["Elapsed"] < float("inf") or e["Elapsed"] < 0))):
            raise CheckingError("invalid/foreign observer lifecycle event")
        action, named = e["Action"], "Test" in e
        if action == "output":
            if state not in (1, 2, 3) or (named and state != 2):
                raise CheckingError("observer output outside its lifecycle")
        elif (action, named, state) == ("start", False, 0):
            state = 1
        elif (action, named, state) == ("run", True, 1):
            state = 2
        elif (action, named, state) == ("pass", True, 2):
            state = 3
        elif (action, named, state) == ("pass", False, 3):
            state = 4
        else:
            raise CheckingError("unordered/failed/duplicate observer lifecycle")
    if state != 4:
        raise CheckingError("observer has no complete singleton terminal")
    dependency = HERE / "test_gen_machine.py"
    if _accounting_dependency_digest(_regular_bytes(dependency)) != "560bec0b2856fe79fbeeeec2025cec5cebe484451ceaa919ce00b265af5d5d14":
        raise CheckingError("accepted service-accounting dependency changed")
    from test_gen_machine import complete_go_tests, CheckingError as AccountingError
    normal = subprocess.CompletedProcess([], 0, stdout, stderr)
    try:
        failed = complete_go_tests(normal, [test], package)
    except AccountingError as exc:
        raise CheckingError(f"observer accounting: {exc}") from exc
    if failed:
        raise CheckingError("observer returned a failing named test")


def _requests(inputs):
    if type(inputs) is not list or not inputs:
        raise CheckingError("observer requires positive nonempty input batch")
    for p in inputs:
        if type(p) not in (tuple, list) or len(p) != 2 or any(type(v) is not str for v in p):
            raise CheckingError("observer input Method/Path is not a string pair")
        for v in p:
            _text(v)
    return [{"ID": i, "Method": m, "Path": p} for i, (m, p) in enumerate(inputs, 1)]


def _exact(value, fields):
    if type(value) is not dict or set(value) != set(fields):
        raise CheckingError("private record has missing/extra keys")


def _typed(value, typ):
    if type(value) is not typ:
        raise CheckingError(f"private value must have exact type {typ.__name__}")
    if typ is str:
        _text(value)


def _strings(values, nullable=False):
    if nullable and values is None:
        return
    _typed(values, list)
    for value in values:
        _typed(value, str)


def _param(value):
    _exact(value, ("name", "in", "required"))
    _typed(value["name"], str)
    _typed(value["in"], str)
    _typed(value["required"], bool)


def _list_records(values, checker):
    _typed(values, list)
    for value in values:
        checker(value)


def _op_record(value):
    _exact(value, ("op", "method", "path", "prefixed", "params", "responses", "request_media", "request_required"))
    _typed(value["op"], int)
    _typed(value["method"], str)
    _typed(value["path"], str)
    _typed(value["prefixed"], bool)
    _typed(value["request_required"], bool)
    _strings(value["request_media"])
    _list_records(value["params"], _param)
    _typed(value["responses"], list)
    for response in value["responses"]:
        _exact(response, ("code", "media", "headers"))
        _typed(response["code"], str)
        _strings(response["media"])
        _strings(response["headers"])
    _typed(value["responses"], list)


def _private_op(value):
    _exact(value, ("op", "path", "component", "source", "base", "servers", "segments", "checks",
                   "item_parameters", "operation_parameters", "security"))
    _typed(value["op"], int)
    for key in ("path", "component", "source", "base", "security"):
        _typed(value[key], str)
    _strict_json(value["security"])
    _typed(value["servers"], list)
    for server in value["servers"]:
        _exact(server, ("mounted", "subs"))
        _typed(server["mounted"], bool)
        _strings(server["subs"], nullable=True)
    _typed(value["servers"], list)
    _typed(value["segments"], list)
    for segment in value["segments"]:
        _exact(segment, ("literal", "parameter"))
        for v in segment.values():
            _typed(v, str)
    _typed(value["segments"], list)
    _typed(value["checks"], list)
    for check in value["checks"]:
        _exact(check, ("name", "min", "max", "pattern", "enum", "not_enum", "not_patterns"))
        _typed(check["name"], str)
        _typed(check["min"], int)
        _typed(check["max"], int)
        if check["pattern"] is not None:
            _typed(check["pattern"], str)
        _strings(check["enum"], True)
        _strings(check["not_enum"], True)
        _strings(check["not_patterns"])
    _typed(value["checks"], list)
    _list_records(value["item_parameters"], _param)
    _list_records(value["operation_parameters"], _param)


def _counted(record, name):
    _typed(record[name], list)
    count = record[name + "_count"]
    if type(count) is not int or count < 0 or count != len(record[name]):
        raise CheckingError("private metadata counter/list mismatch")


def _frame_shapes(frames, inputs, run_id, context_id, symbols, package, test):
    n = len(_requests(inputs))
    if (type(run_id) is not str or not re.fullmatch("[0-9a-f]{32}", run_id) or
            type(context_id) is not str or not context_id or type(symbols) is not list or not symbols or
            any(type(s) is not str for s in symbols) or len(set(symbols)) != len(symbols)):
        raise CheckingError("invalid trusted observer identities")
    if type(frames) is not list or len(frames) != n + 2:
        raise CheckingError("private frame cardinality")
    for i, f in enumerate(frames):
        if (type(f) is not dict or type(f.get("id")) is not int or f["id"] != i or
                f.get("run") != run_id or f.get("context") != context_id):
            raise CheckingError("private frame identity/order/context mismatch")
    meta, end = frames[0], frames[-1]
    _exact(meta, ("kind", "id", "run", "context", "package", "test", "ops_count", "ops",
                  "symbols_count", "symbols", "provenance"))
    if meta["kind"] != "meta" or meta["package"] != package or meta["test"] != test:
        raise CheckingError("private meta owner mismatch")
    _counted(meta, "ops")
    _counted(meta, "symbols")
    _list_records(meta["ops"], _op_record)
    if [v["op"] for v in meta["ops"]] != sorted({v["op"] for v in meta["ops"]}):
        raise CheckingError("Ops map snapshot is not sorted unique keys")
    for symbol in meta["symbols"]:
        _exact(symbol, ("name", "op"))
        _typed(symbol["name"], str)
        _typed(symbol["op"], int)
    if [v["name"] for v in meta["symbols"]] != symbols:
        raise CheckingError("private symbol witness cardinality/order")
    provenance = meta["provenance"]
    _exact(provenance, ("operations_count", "operations", "references_count", "references",
                        "documents_count", "documents"))
    for name in ("operations", "references", "documents"):
        _counted(provenance, name)
    _list_records(provenance["operations"], _private_op)
    _strings(provenance["references"])
    for document in provenance["documents"]:
        _exact(document, ("path", "sha256"))
        _typed(document["path"], str)
        if type(document["sha256"]) is not str or not re.fullmatch("[0-9a-f]{64}", document["sha256"]):
            raise CheckingError("private source document digest malformed")
    for f in frames[1:-1]:
        _exact(f, ("kind", "id", "run", "context", "result", "op", "sub", "reason"))
        if f["kind"] != "route":
            raise CheckingError("expected route record")
        r = f["result"]
        if type(r) is not dict:
            raise CheckingError("invalid private route result")
        if "err" in r:
            _exact(r, ("err",))
            _typed(r["err"], int)
            if f["op"] is not None or f["sub"] is not None or type(f["reason"]) is not str:
                raise CheckingError("error route has success payload")
        else:
            _exact(r, ("path", "method", "params", "prefixed"))
            _typed(r["path"], str)
            _typed(r["method"], str)
            _typed(r["prefixed"], bool)
            _typed(r["params"], dict)
            if any(type(k) is not str or type(v) is not str for k, v in r["params"].items()):
                raise CheckingError("invalid private params")
            _typed(f["op"], int)
            _typed(f["sub"], str)
            if f["reason"] is not None:
                raise CheckingError("success route has error reason")
    _exact(end, ("kind", "id", "run", "context", "meta", "routes", "boolean_calls", "snapshot_unchanged"))
    if (end["kind"] != "end" or type(end["meta"]) is not int or end["meta"] != 1 or
            type(end["routes"]) is not int or end["routes"] != n or
            type(end["boolean_calls"]) is not int or end["boolean_calls"] < 0):
        raise CheckingError("private terminal counters")
    _typed(end["snapshot_unchanged"], bool)
    return frames


def _regular_bytes(path, *, mode=None):
    """Do not follow aliases, wait on FIFOs, or accept a replay as a fresh report."""
    path = Path(path)
    try:
        for parent in [path, *path.parents]:
            if parent.is_symlink():
                raise CheckingError("symlink in private path")
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or (mode is not None and stat.S_IMODE(before.st_mode) != mode):
            raise CheckingError("private path is not the required regular file")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as f:
            actual = os.fstat(f.fileno())
            if (before.st_dev, before.st_ino) != (actual.st_dev, actual.st_ino):
                raise CheckingError("private file replaced before read")
            raw = f.read()
            after = os.fstat(f.fileno())
        if (actual.st_size, actual.st_mtime_ns, actual.st_ctime_ns) != (
                after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise CheckingError("private file changed during read")
        return raw
    except (OSError, UnicodeError) as exc:
        raise CheckingError(f"cannot read private file: {exc}") from exc


def _tree_receipt(root):
    root = Path(root)
    if any(p.is_symlink() for p in [root, *root.parents]) or not root.is_dir():
        raise CheckingError("owned snapshot root is not a real directory")
    result = {}
    for p in sorted(root.rglob("*")):
        mode = p.lstat().st_mode
        key = p.relative_to(root).as_posix()
        if stat.S_ISDIR(mode):
            result[key] = ("dir", stat.S_IMODE(mode))
        elif stat.S_ISREG(mode):
            raw = _regular_bytes(p)
            result[key] = ("file", stat.S_IMODE(mode), len(raw), _sha(raw))
        else:
            raise CheckingError("snapshot contains an alias/nonregular file")
    return result


def _verify_tree(root, receipt):
    if _tree_receipt(root) != receipt:
        raise CheckingError("immutable module/observer snapshot changed")


def _new_path(path):
    path = Path(path)
    if path.exists() or path.is_symlink():
        raise CheckingError("private destination already exists/replay")
    for p in path.parents:
        if p.is_symlink():
            raise CheckingError("private destination parent alias")
    return path


def _copy_owned(source, destination):
    if Path(destination).resolve().is_relative_to(Path(source).resolve()):
        raise CheckingError("private clone destination is inside its source")
    before = _tree_receipt(source)
    _new_path(destination)
    try:
        shutil.copytree(source, destination)
    except OSError as exc:
        raise CheckingError("cannot clone immutable generated module") from exc
    _verify_tree(source, before)
    _verify_tree(destination, before)
    return before


def _read_observation_frames(path, inputs, run_id, context_id, symbols,
                             package=_S08_PACKAGE, test=_S08_TEST):
    return _frame_shapes(_ndjson(_regular_bytes(path, mode=0o600)), inputs, run_id,
                         context_id, symbols, package, test)


def _validate_context(context):
    _exact(context, ("id", "root", "raw", "views", "digests"))
    if type(context["id"]) is not str or not context["id"] or type(context["root"]) is not str or not context["root"]:
        raise CheckingError("missing explicit GIVEN root/context")
    if (type(context["raw"]) is not list or not context["raw"] or type(context["views"]) is not list or
            type(context["digests"]) is not list or
            not len(context["raw"]) == len(context["views"]) == len(context["digests"])):
        raise CheckingError("incomplete GIVEN view bytes")
    names = []
    for raw, view, digest in zip(context["raw"], context["views"], context["digests"]):
        if type(raw) is not bytes or _sha(raw) != digest or _strict_json(raw) != view:
            raise CheckingError("GIVEN complete view bytes changed")
        if type(view) is not dict or type(view.get("name")) is not str or not view["name"]:
            raise CheckingError("GIVEN view has no declared name")
        names.append(view["name"])
    if len(set(names)) != len(names) or context["root"] not in names:
        raise CheckingError("GIVEN root is not a unique catalogue member")
    return context


def _given_contexts():
    raw = [_regular_bytes(ROOT / "Platform/02-installer/vectors/canonical/expect" / name)
           for name, digest in _S08_VIEWS]
    if [_sha(v) for v in raw] != [digest for name, digest in _S08_VIEWS]:
        raise CheckingError("the one declared manual-pair context changed")
    return [_validate_context(dict(id=_S08_CONTEXT, root="testsub", raw=raw,
                                  views=[_strict_json(v) for v in raw], digests=[_sha(v) for v in raw]))]


def _source_identity_witness(model):
    rows = sorted(model.declarations, key=lambda d: d["ordinal"])
    if [r["ordinal"] for r in rows] != list(range(1, 147)):
        raise CheckingError("source identity is not the approved old140+6")
    return [(r["symbol"], r["ordinal"]) for r in rows]


def _source_route_instances(model):
    """Specialize the six Source contracts, not a selector or a parameter-name heuristic."""
    context = _validate_context(model.context)
    root = context["root"]
    views = {v["name"]: v for v in context["views"]}
    routes = []
    for p in model.paths:
        comp = p["component"]
        if comp:
            for name, view in views.items():
                if comp in ("UnitsCollection", "UnitItem"):
                    values = [view["unit"]["rows"]]
                    replaced = "rows"
                elif comp in ("TableCollection", "TableItem"):
                    values = list(view.get("tables", {}))
                    replaced = "table"
                elif comp == "PassRoot":
                    passed = view.get("door", {}).get("pass", [])
                    values = passed if type(passed) is list else passed.get("routes", [])
                    replaced = "pass"
                elif comp == "ConsoleFile":
                    values = view.get("console", {}).get("files", [])
                    replaced = "file"
                else:
                    raise CheckingError("unknown standard source contract")
                for value in values:
                    _typed(value, str)
                    if not value or value.startswith("/"):
                        raise CheckingError("invalid declared catalogue route literal")
                    variants = [True] if comp == "ConsoleFile" or name != root else [False, True]
                    for mounted in variants:
                        segments, ranks = [], []
                        if mounted and comp != "ConsoleFile":
                            segments.append(name)
                            ranks.append(1)
                        for seg in p["segs"]:
                            if seg == "{" + replaced + "}":
                                pieces = value.split("/") if comp == "ConsoleFile" else [value]
                                segments += pieces
                                ranks += [1] * len(pieces)
                            elif comp == "ConsoleFile" and seg == "{sub}":
                                segments.append(name)
                                ranks.append(1)
                            else:
                                segments.append(seg)
                                ranks.append(0 if seg.startswith("{") else 2)
                        # Match retains decoded original adapter parameter names even
                        # when routing specializes them to catalogue literals. Removing
                        # bound OpenAPI Parameter Objects does not rename that interface.
                        captures = {replaced: value}
                        if mounted or comp == "ConsoleFile":
                            captures["sub"] = name
                        routes.append(dict(p=p, segments=segments, ranks=ranks,
                                           prefixed=mounted and comp != "ConsoleFile", captures=captures,
                                           owner=name, tail=comp == "PassRoot", bound=set(), component=comp))
        else:
            # Existing ordinary contracts retain captured parameters. Their owners follow the
            # declared source path/server position, not a server example or a guessed first view.
            names = list(views) if "{sub}" in p["segs"] else [root]
            for name in names:
                for mounted in ([False, True] if p["prefixed"] else [False]):
                    owners = list(views) if mounted and "{sub}" not in p["segs"] else [name]
                    for owner in owners:
                        segments = ([owner] if mounted else []) + list(p["segs"])
                        captures = {"sub": owner} if mounted else {}
                        ranks = [0 if seg.startswith("{") else 2 for seg in segments]
                        if mounted:
                            ranks[0] = 1
                        if "{sub}" in segments:
                            idx = segments.index("{sub}")
                            segments[idx], ranks[idx], captures["sub"] = owner, 1, owner
                        choices = [(segments, ranks, captures)]
                        # These exact procedural source addresses own the existing rows/table slots.
                        bindings = {}
                        if p["path"] == "/{rows}/{id}/{blob_field}":
                            bindings["rows"] = [views[owner]["unit"]["rows"]]
                        elif p["path"].startswith("/domain/at/{cluster}/{sub}/{rows}"):
                            v = views[owner]
                            bindings["rows"] = (list(v.get("door", {}).get("routes", [])) if p["path"].endswith("/{tail}") else
                                [v["unit"]["rows"], *(table for table, definition in v.get("tables", {}).items()
                                                        if not definition.get("service"))])
                            if p["path"].endswith("/{id}"):
                                bindings["rows"] += list(v.get("door", {}).get("routes", []))
                        if p["path"] in ("/where/{table}/{place}", "/{sub}/where/{table}/{place}",
                                         "/domain/at/{cluster}/{sub}/where/{table}/{place}"):
                            bindings["table"] = list(views[owner].get("tables", {}))
                        for key, values in bindings.items():
                            expanded = []
                            for segs, rs, ps in choices:
                                for value in values:
                                    idx = segs.index("{" + key + "}")
                                    ns, nr, np = list(segs), list(rs), dict(ps)
                                    ns[idx], nr[idx], np[key] = value, 1, value
                                    expanded.append((ns, nr, np))
                            choices = expanded
                        for segs, rs, ps in choices:
                            routes.append(dict(p=p, segments=segs, ranks=rs, captures=ps,
                                               prefixed=mounted, owner=owner,
                                               tail=p["path"].endswith("/{tail}"), bound=set(), component=""))
    return routes


def _route_in_context(model, method, raw, segments):
    views = {v["name"]: v for v in model.context["views"]}
    hits = []
    for entry in model.routes:
        p, template = entry["p"], entry["segments"]
        tail_parameter = template[-1] == "{tail}" if template else False
        fixed = len(template) - (1 if tail_parameter else 0)
        if entry["tail"]:
            if len(segments) < (len(template) if tail_parameter else fixed):
                continue
        elif len(segments) != len(template):
            continue
        params, ranks, good = dict(entry.get("captures", {})), list(entry["ranks"]), True
        for i, t in enumerate(template):
            match = re.fullmatch(r"\{(.+)\}", t)
            if match and match[1] == "tail" and entry["tail"]:
                params["tail"] = "/".join(raw[i:])
                break
            if i >= len(segments):
                good = False
                break
            v = segments[i]
            if not match:
                good = t == v
            else:
                key = match[1]
                check = p["records"].get(method, {}).get("path_checks", p["checks"]).get(key)
                good = bool(v) and (check is None and key == "sub" or
                                   check is not None and check["validator"].is_valid(v))
                params[key] = v
                if key == "sub":
                    good = good and v in views
                    ranks[i] = 1
            if not good:
                break
        if not good:
            continue
        sub = params.get("sub", entry["owner"] or model.context["root"])
        view = views.get(sub)
        if view is None:
            continue
        # Ordinary domain-at paths are owned by P/06.7-R008; forwarding routes are not rows.
        if p["path"].startswith("/domain/at/") and "rows" in params:
            forwarding = params["rows"] in view.get("door", {}).get("routes", [])
            row = (params["rows"] == view.get("unit", {}).get("rows") or
                   params["rows"] in view.get("tables", {}) and
                   not view["tables"][params["rows"]].get("service"))
            forwarding = forwarding and ("id" in params)
            if ("tail" in params and not forwarding) or ("tail" not in params and not (row or forwarding)):
                continue
            if "{rows}" in template:
                ranks[template.index("{rows}")] = 1
        elif "rows" in params and params["rows"] != view.get("unit", {}).get("rows"):
            continue
        if "table" in params and params["table"] not in view.get("tables", {}):
            continue
        hits.append((entry, params, ranks))
    if not hits:
        return ("err", 404)
    priority = max(h[2] for h in hits)
    best = [h for h in hits if h[2] == priority]
    if len({(h[0]["p"]["path"], h[0]["prefixed"]) for h in best}) != 1:
        return ("err", 0)
    entry, params, _ = best[0]
    p = entry["p"]
    if method not in p["ops"]:
        return ("err", 405 if p["all405"] else 404)
    return ("op", p["path"], method, {k: v for k, v in params.items() if k not in entry["bound"]}, entry["prefixed"])


def _source_projection(model):
    """Expected raw metadata from full source resources; generated/private metadata is only actual."""
    reader = model.reader
    def params(record, values, pointer):
        out = []
        for i, value in enumerate(values):
            prm, _, _ = reader.resolve_object(record["file"], pointer + "/" + str(i), "parameter")
            out.append({"name": prm["name"], "in": prm["in"], "required": bool(prm.get("required"))})
        return out
    ops, private = [], []
    for r in sorted(model.declarations, key=lambda v: v["ordinal"]):
        item, operation = r["item"], r["operation"]
        ip = params(r, item.get("parameters", []), r["item_pointer"] + "/parameters")
        op = params(r, operation.get("parameters", []), r["pointer"] + "/parameters")
        by_key = {(v["in"], v["name"]): v for v in ip}
        by_key.update({(v["in"], v["name"]): v for v in op})
        responses = []
        for status in operation.get("responses", {}):
            value, _, _ = reader.resolve_object(r["file"], r["pointer"] + "/responses/" + reader.escape(status), "response")
            responses.append(dict(code=str(status), media=sorted(value.get("content", {})),
                                  headers=sorted(value.get("headers", {}))))
        media, required = [], False
        if "requestBody" in operation:
            body, _, _ = reader.resolve_object(r["file"], r["pointer"] + "/requestBody", "request")
            media, required = sorted(body.get("content", {})), bool(body.get("required"))
        # OpenAPI's absent servers means the single relative root server.
        urls = operation.get("servers", item.get("servers", model.doc.get("servers", [{"url": "/"}])))
        ops.append(dict(op=r["ordinal"], method=r["method"].upper(), path=r["route"],
                        prefixed=any(s["url"] == "{origin}/{sub}" for s in urls),
                        params=sorted(by_key.values(), key=lambda v: (v["in"], v["name"])),
                        responses=sorted(responses, key=lambda v: v["code"]),
                        request_media=media, request_required=required))
        servers = []
        for server in urls:
            mounted = server["url"] == "{origin}/{sub}"
            subs = server.get("variables", {}).get("sub", {}).get("enum") if mounted else None
            servers.append(dict(mounted=mounted, subs=subs))
        checks = []
        p = next(p for p in model.paths if p["path"] == r["route"])
        for name, c in sorted(r["path_checks"].items()):
            neg = c["not"] or {}
            enums, patterns = [], []
            for term in neg.get("anyOf", [neg]):
                enums.extend(term.get("enum", []))
                if "pattern" in term:
                    patterns.append(term["pattern"])
            checks.append(dict(name=name, min=c["min"], max=c["max"] if c["max"] is not None else -1,
                               pattern=c["pattern"], enum=c["enum"], not_enum=enums or None,
                               not_patterns=patterns))
        private.append(dict(op=r["ordinal"], path=r["route"], component=r["component"],
                            source=str(r["file"].relative_to(ROOT)) + "#" + r["pointer"],
                            base=str(r["file"].relative_to(ROOT)), servers=servers,
                            segments=[dict(literal="" if s.startswith("{") else s,
                                           parameter=s[1:-1] if s.startswith("{") else "")
                                      for s in ([] if r["route"] == "/" else r["route"][1:].split("/"))],
                            checks=checks, item_parameters=ip, operation_parameters=op,
                            security=json.dumps(operation.get("security", model.doc.get("security", [])),
                                                separators=(",", ":"))))
    references = sorted({str(file.relative_to(ROOT)) + " " + ref + " -> " +
                         str(target.relative_to(ROOT)) + "#" + fragment
                         for (file, ptr, ref, kind), (target, fragment) in reader.edges.items()})
    documents = [dict(path=str(file.relative_to(ROOT)), sha256=_sha(_regular_bytes(file)))
                 for file in sorted(reader.docs)]
    return dict(ops=ops, symbols=[dict(name=name, op=op) for name, op in _source_identity_witness(model)],
                provenance=dict(operations=private, references=references, documents=documents))


def _expected_route_observation(model, probe):
    result = expected(model, probe)
    if "err" in result:
        if result["err"] == 0:
            raise CheckingError("independent context is unresolved/ambiguous")
        return dict(result=result, op=None, sub=None)
    record = next(r for r in model.declarations if r["route"] == result["path"] and
                  r["method"].upper() == result["method"])
    sub = result["params"].get("sub", "")
    if record["component"] and result["prefixed"]:
        sub = probe[1].partition("?")[0][1:].split("/")[0]
    return dict(result=result, op=record["ordinal"], sub=sub)


def _mandatory_observation_inputs(model):
    """Every applicable specialization is mandatory; random optional probes cannot cover a missing sample."""
    obligations = []
    for entry_no, entry in enumerate(model.routes):
        p = entry["p"]
        vals = []
        for seg in entry["segments"]:
            match = re.fullmatch(r"\{(.+)\}", seg)
            value = model.sample(p, match[1]) if match else seg
            if value is None:
                raise AssertionError(f"mandatory source sample GAP: {p['path']} {seg}")
            vals.append(value)
        for method in p["ops"]:
            probe = (method, "/" + "/".join(vals))
            actual_expected = model.route(*probe)
            if actual_expected[:3] != ("op", p["path"], method):
                raise AssertionError(f"mandatory specialization is unproven: {p['path']} {method} {probe}")
            obligations.append((f"source:{entry_no}:{method}:base", probe))
            if entry["tail"]:
                prefix = vals[:-1] if vals and entry["segments"][-1] == "{tail}" else vals
                for suffix_no, suffix in enumerate(([], ["one"], ["one", "two"], ["one", "two?x=%2F&x=2"])):
                    obligations.append((f"source:{entry_no}:{method}:tail:{suffix_no}",
                                        (method, "/" + "/".join(prefix + suffix))))
        obligations.append((f"source:{entry_no}:unsupported", ("TRACE", "/" + "/".join(vals))))
    for i, probe in enumerate((("GET", "/unknown-sub/counters"), ("GET", "/testsub2/not-a-table"),
                               ("GET", "/testsub2/deep/er/Name_1-2.v3.js/extra"),
                               ("GET", "/%zz"), ("GET", "/testsub2/entries/a/b?raw=%2F"))):
        obligations.append((f"negative:{i}", probe))
    return _mandatory_inputs(obligations)


def _mandatory_inputs(obligations):
    if type(obligations) is not list or not obligations:
        raise CheckingError("no mandatory source obligations")
    ids, inputs = [], []
    for identity, probe in obligations:
        if type(identity) is not str or not identity or identity in ids or probe is None:
            raise CheckingError("missing/duplicate mandatory source sample")
        _requests([probe])
        ids.append(identity)
        inputs.append(probe)
    return ids, inputs


def _compare_observations(frames, inputs, want_meta, want_route):
    """Called after all process, transport, trust and premise gates; returns named semantic mismatches."""
    if any(f["result"].get("err") == 0 for f in frames[1:-1]):
        raise CheckingError("context/capability/ambiguity RouteError.Code0 is not a semantic kill")
    differences = []
    meta = frames[0]
    for field in ("ops", "symbols", "provenance"):
        actual = copy.deepcopy(meta[field])
        expected_value = copy.deepcopy(want_meta[field])
        if field == "ops":
            for side in (actual, expected_value):
                for operation in side:
                    operation["params"].sort(key=lambda p: (p["in"], p["name"]))
                    operation["responses"].sort(key=lambda r: r["code"])
                    operation["request_media"].sort()
                    for response in operation["responses"]:
                        response["media"].sort()
                        response["headers"].sort()
        if field == "provenance":
            for name in ("operations", "references", "documents"):
                actual.pop(name + "_count", None)
            for side in (actual, expected_value):
                for operation in side["operations"]:
                    operation["security"] = _strict_json(operation["security"])
        if actual != expected_value:
            differences.append(("metadata:" + field, expected_value, actual))
    for i, (probe, frame) in enumerate(zip(inputs, frames[1:-1]), 1):
        wanted = want_route(probe)
        actual = {key: frame[key] for key in ("result", "op", "sub")}
        if actual != wanted:
            differences.append((f"route:{i}", wanted, actual))
    for key, wanted in (("boolean_calls", 0), ("snapshot_unchanged", True)):
        if frames[-1][key] != wanted:
            differences.append(("premise-observation:" + key, wanted, frames[-1][key]))
    return differences


_CONTEXT_GO = r'''package main
import "encoding/json"
func (cat) CatalogSnapshot() (string, []map[string]any) {
    var views []map[string]any
    if err := json.Unmarshal([]byte(__VIEWS__), &views); err != nil { panic(err) }
    return __ROOT__, views
}
'''

_OBSERVER_GO = r'''package apidoor
import (
    "encoding/json"
    "os"
    "reflect"
    "sort"
    "testing"
)
type review103Catalogue struct { root string; views []map[string]any; booleanCalls int }
func (c *review103Catalogue) Sub(string) bool { c.booleanCalls++; return false }
func (c *review103Catalogue) Rows(string,string) bool { c.booleanCalls++; return false }
func (c *review103Catalogue) Table(string,string) bool { c.booleanCalls++; return false }
func (c *review103Catalogue) Pass(string,string) bool { c.booleanCalls++; return false }
func (c *review103Catalogue) CatalogSnapshot() (string, []map[string]any) { return c.root, c.views }
func review103Params(ps []Param) []map[string]any {
    out := []map[string]any{}
    for _, p := range ps { out = append(out,map[string]any{"name":p.Name,"in":p.In,"required":p.Required}) }
    return out
}
func TestReview103S08Observation(t *testing.T) {
    var views []map[string]any
    if err := json.Unmarshal([]byte(__VIEWS__), &views); err != nil { t.Fatal(err) }
    cat := &review103Catalogue{root:__ROOT__, views:views}
    initial, err := json.Marshal(views); if err != nil { t.Fatal(err) }
    var requests []struct{ ID int; Method,Path string }
    if err := json.Unmarshal([]byte(__REQUESTS__), &requests); err != nil { t.Fatal(err) }
    if len(requests)==0 { t.Fatal("empty observation") }
    f, err := os.OpenFile(__REPORT__,os.O_WRONLY|os.O_CREATE|os.O_EXCL,0600); if err != nil { t.Fatal(err) }
    enc := json.NewEncoder(f)
    emit := func(v map[string]any) { if err := enc.Encode(v); err != nil { f.Close(); t.Fatal(err) } }
    shared := func(kind string,id int) map[string]any { return map[string]any{"kind":kind,"id":id,"run":__RUN__,"context":__CONTEXT__} }
    ops := []map[string]any{}; ids := []int{}
    for op := range Ops { ids=append(ids,int(op)) }; sort.Ints(ids)
    for _, id := range ids {
        v := Ops[Op(id)]; responses := []map[string]any{}
        for _, r := range v.Responses { responses=append(responses,map[string]any{"code":r.Code,"media":append([]string{},r.Media...),"headers":append([]string{},r.Headers...)}) }
        ops=append(ops,map[string]any{"op":id,"method":v.Method,"path":v.Path,"prefixed":v.Prefixed,"params":review103Params(v.Params),"responses":responses,"request_media":append([]string{},v.RequestMedia...),"request_required":v.RequestRequired})
    }
    symbols := []map[string]any{__SYMBOLS__}
    spec := p06Bindings(); if spec==nil { f.Close(); t.Fatal("missing private binding spec") }
    operations := []map[string]any{}
    for _, v := range spec.operations {
        servers:=[]map[string]any{}; for _, s:=range v.servers { servers=append(servers,map[string]any{"mounted":s.mounted,"subs":s.subs}) }
        segments:=[]map[string]any{}; for _, s:=range v.segments { segments=append(segments,map[string]any{"literal":s.literal,"parameter":s.parameter}) }
        names:=[]string{}; for name:=range v.checks { names=append(names,name) }; sort.Strings(names)
        checks:=[]map[string]any{}
        for _, name:=range names {
            c:=v.checks[name]; var pattern any; if c.rx!=nil { pattern=c.rx.String() }
            notPatterns:=[]string{}; for _, rx:=range c.notRx { notPatterns=append(notPatterns,rx.String()) }
            checks=append(checks,map[string]any{"name":name,"min":c.minLen,"max":c.maxLen,"pattern":pattern,"enum":c.enum,"not_enum":c.notEnum,"not_patterns":notPatterns})
        }
        operations=append(operations,map[string]any{"op":int(v.op),"path":v.path,"component":v.component,"source":v.source,"base":v.base,"servers":servers,"segments":segments,"checks":checks,"item_parameters":review103Params(v.itemParameters),"operation_parameters":review103Params(v.operationParameters),"security":v.security})
    }
    documents:=[]map[string]any{}; names:=[]string{}; for path:=range spec.documents { names=append(names,path) }; sort.Strings(names)
    for _, name:=range names { documents=append(documents,map[string]any{"path":name,"sha256":spec.documents[name]}) }
    references:=append([]string{},spec.references...)
    meta:=shared("meta",0); meta["package"]=__PACKAGE__; meta["test"]="TestReview103S08Observation"
    meta["ops_count"]=len(ops);meta["ops"]=ops;meta["symbols_count"]=len(symbols);meta["symbols"]=symbols
    meta["provenance"]=map[string]any{"operations_count":len(operations),"operations":operations,"references_count":len(references),"references":references,"documents_count":len(documents),"documents":documents};emit(meta)
    for i, r:=range requests {
        if r.ID!=i+1 { f.Close();t.Fatal("request identity") }
        match, failure:=Route(r.Method,r.Path,cat); frame:=shared("route",r.ID)
        if failure!=nil { frame["result"]=map[string]any{"err":failure.Code};frame["op"]=nil;frame["sub"]=nil;frame["reason"]=failure.Reason
        } else { info:=Ops[match.Op];frame["result"]=map[string]any{"path":info.Path,"method":info.Method,"params":match.Params,"prefixed":match.Prefixed};frame["op"]=int(match.Op);frame["sub"]=match.Sub;frame["reason"]=nil }
        emit(frame)
    }
    after,err:=json.Marshal(views);if err!=nil { f.Close();t.Fatal(err) }
    end:=shared("end",len(requests)+1);end["meta"]=1;end["routes"]=len(requests);end["boolean_calls"]=cat.booleanCalls;end["snapshot_unchanged"]=reflect.DeepEqual(initial,after);emit(end)
    if err:=f.Close();err!=nil { t.Fatal(err) }
}
'''


def _go_template(template, values):
    # One substitution pass: source/user text containing a template token stays opaque data.
    def put(match):
        key = match[1]
        if key not in values:
            raise CheckingError("unknown private Go template token")
        return values[key]
    return re.sub(r"__([A-Z]+)__", put, template)


def _context_go(context):
    _validate_context(context)
    raw = b"[" + b",".join(context["raw"]) + b"]"
    return _go_template(_CONTEXT_GO, dict(VIEWS=json.dumps(raw.decode("utf-8"), ensure_ascii=False),
                                          ROOT=json.dumps(context["root"], ensure_ascii=False)))


def _owned_context_module(source, destination, context):
    _validate_context(context)
    _copy_owned(source, destination)
    path = Path(destination) / "cmd/judgeroutes/context.go"
    _new_path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = _context_go(context).encode("utf-8")
        with path.open("xb") as f:
            f.write(raw)
    except OSError as exc:
        raise CheckingError("cannot install context companion") from exc
    return Path(destination), (path.relative_to(destination).as_posix(), _sha(raw))


def _observer_module(source, destination, context, inputs, model, report, run_id):
    requests = _requests(inputs)
    _validate_context(context)
    _new_path(report)
    _copy_owned(source, destination)
    symbols = _source_identity_witness(model)
    body = _OBSERVER_GO
    replacements = dict(VIEWS=json.dumps((b"[" + b",".join(context["raw"]) + b"]").decode("utf-8"), ensure_ascii=False),
                        ROOT=json.dumps(context["root"]), REQUESTS=json.dumps(json.dumps(requests), ensure_ascii=True),
                        REPORT=json.dumps(str(report)), RUN=json.dumps(run_id), CONTEXT=json.dumps(context["id"]),
                        PACKAGE=json.dumps(_S08_PACKAGE),
                        SYMBOLS=",".join('{"name":' + json.dumps(name) + ',"op":int(' + name + ')}' for name, _ in symbols))
    body = _go_template(body, replacements)
    path = Path(destination) / "apidoor/review103_s08_observe_test.go"
    _new_path(path)
    try:
        with path.open("xb") as f:
            f.write(body.encode("utf-8"))
    except OSError as exc:
        raise CheckingError("cannot install private observer") from exc
    return _tree_receipt(destination)


def _go_observer(module, report, context, inputs, symbols, run_id, trusted_snapshot):
    _requests(inputs)
    _validate_context(context)
    _new_path(report)
    _verify_tree(module, trusted_snapshot)
    try:
        done = subprocess.run(["go", "test", "-json", "-count=1", "-run", "^" + _S08_TEST + "$", "./apidoor"],
                              cwd=module, env=GOENV, capture_output=True)
    except (OSError, UnicodeError, subprocess.SubprocessError) as exc:
        raise CheckingError(f"observer process failed: {exc}") from exc
    _complete_observer_go_test(done)
    _verify_tree(module, trusted_snapshot)
    return _read_observation_frames(report, inputs, run_id, context["id"], symbols)


def _observe_baseline(case):
    ids, inputs = _mandatory_observation_inputs(case.model)
    run_id = os.urandom(16).hex()
    module, report = case.tmp / ("observer-" + run_id), case.tmp / ("observation-" + run_id + ".ndjson")
    snapshot = _observer_module(case._b0, module, case.context, inputs, case.model, report, run_id)
    frames = _go_observer(module, report, case.context, inputs,
                          [name for name, _ in _source_identity_witness(case.model)], run_id, snapshot)
    _verify_tree(case._b0, case.original_snapshot)
    differences = _compare_observations(frames, inputs, _source_projection(case.model),
                                        lambda p: _expected_route_observation(case.model, p))
    case.assertEqual(differences, [], "normal mandatory/source observer baseline disagrees")
    return dict(context=copy.deepcopy(case.context), original=case.original_snapshot,
                module=module, snapshot=snapshot, obligations=ids, frames=frames)


def _component_checked_run(case, module, inputs):
    _requests(inputs)
    _validate_context(case.context)
    receipt = getattr(case, "_observer_receipt", None)
    if not receipt or receipt["context"] != case.context:
        raise CheckingError("real P06 has no context-bound normal baseline receipt")
    _verify_tree(case._b0, receipt["original"])
    _verify_tree(receipt["module"], receipt["snapshot"])
    companion, digest = case._companion
    path = Path(module) / companion
    if _sha(_regular_bytes(path)) != digest or _sha(_context_go(case.context).encode()) != digest:
        raise CheckingError("context companion missing/changed in route or mutant copy")
    got = run(module, inputs)             # unchanged J06 transport/completeness helper
    if any(row.get("err") == 0 for row in got):
        raise CheckingError("P06 capability/context/ambiguity Code0 is not a semantic result")
    return got


def _run_required_original_mutants(required, attempted, outcomes):
    """Audit real normal attempts separately from the unchanged old dictionary/loop."""
    if set(required) != {"prefix-lost", "all405", "pattern", "rank"}:
        raise CheckingError("source-required old mutant inventory changed")
    if set(attempted) != set(required) or set(outcomes) != set(required):
        raise AssertionError("source-applicable old mutant coverage GAP")
    for name in required:
        if outcomes[name] == "checking-error":
            raise CheckingError(f"{name}: incomplete mutant execution")
        if outcomes[name] != "semantic-mismatch":
            raise AssertionError(f"{name} survives or lacks a distinguishing source witness")



_PRIORITY_GO = r'''package apidoor
import("encoding/json";"os";"testing")
func TestReview103S08Priority(t *testing.T) {
 var views []map[string]any
 if err:=json.Unmarshal([]byte(__VIEWS__),&views);err!=nil{t.Fatal(err)}
 var view map[string]any;for _,v:=range views{if v["name"]==__ROOT__{view=v}}
 if view==nil{t.Fatal("missing declared root view")}
 spec:=p06Bindings();if spec==nil{t.Fatal("missing private spec")}
 bind:=func(id Op)p06Candidate{
  var found *p06Operation
  for i:=range spec.operations{if spec.operations[i].op==id{if found!=nil{t.Fatal("duplicate operation")};found=&spec.operations[i]}}
  if found==nil{t.Fatal("missing operation")}
  choices,err:=p06Choices(*found,view);if err!=nil{t.Fatal(err)};if len(choices)!=1{t.Fatal("priority fixture needs a single source choice")}
  return p06Bind(*found,p06Server{mounted:false},__ROOT__,choices[0])
 }
 row,lit,free:=bind(Op(__ROW__)),bind(Op(__LITERAL__)),bind(Op(__FREE__))
 if len(free.segments)!=2{t.Fatal("free source path shape")}
 singleFree:=free;singleFree.segments=free.segments[1:]
 file,err:=os.OpenFile(__REPORT__,os.O_WRONLY|os.O_CREATE|os.O_EXCL,0600);if err!=nil{t.Fatal(err)}
 enc:=json.NewEncoder(file);emit:=func(v map[string]any){if err:=enc.Encode(v);err!=nil{file.Close();t.Fatal(err)}}
 shared:=func(kind string,id int)map[string]any{return map[string]any{"kind":kind,"id":id,"run":__RUN__,"context":__CONTEXT__}}
 start:=shared("start",0);start["count"]=7;emit(start)
 for i,c:=range []p06Candidate{row,lit,free}{
  ranks:=[]int{};for _,s:=range c.segments{ranks=append(ranks,s.rank)}
  f:=shared("record",i+1);f["case"]=[]string{"unit-class","literal","free-path"}[i];f["ranks"]=ranks;f["priority"]=nil;emit(f)
 }
 for i,v:=range []int{p06MoreConcrete(lit,row),p06MoreConcrete(row,singleFree),p06MoreConcrete(singleFree,row),p06MoreConcrete(row,row)}{
  f:=shared("record",i+4);f["case"]=[]string{"literal-over-class","class-over-free","free-under-class","equal-class"}[i];f["ranks"]=nil;f["priority"]=v;emit(f)
 }
 end:=shared("end",8);end["count"]=7;end["completed"]=7;emit(end)
 if err:=file.Close();err!=nil{t.Fatal(err)}
}
'''


def _priority_source_inputs(model):
    """Pick declared Source operations; expected ranks are source-owned, not generated metadata."""
    root = model.context["root"]
    def one(path, component):
        records = [r for r in model.declarations if r["method"] == "get" and
                   r["route"] == path and r["component"] == component]
        entries = [e for e in model.routes if e["p"]["path"] == path and
                   e["owner"] == root and not e["prefixed"]]
        if len(records) != 1 or len(entries) != 1:
            raise CheckingError("ambiguous/missing Source priority fixture")
        return records[0]["ordinal"], entries[0]["ranks"]
    row, rr = one("/{rows}", "UnitsCollection")
    literal, lr = one("/healthz", "")
    free, fr = one("/folders/{id}", "")
    if rr != [1] or lr != [2] or fr != [2, 0]:
        raise CheckingError("Source literal/catalogue/free priority premise changed")
    return dict(ROW=row, LITERAL=literal, FREE=free), [
        dict(case="unit-class", ranks=rr, priority=None),
        dict(case="literal", ranks=lr, priority=None),
        dict(case="free-path", ranks=fr, priority=None),
        dict(case="literal-over-class", ranks=None, priority=1),
        dict(case="class-over-free", ranks=None, priority=1),
        dict(case="free-under-class", ranks=None, priority=-1),
        dict(case="equal-class", ranks=None, priority=0)]


def _read_priority_report(raw, run_id, context):
    frames = _ndjson(raw)
    names = ["unit-class", "literal", "free-path", "literal-over-class", "class-over-free",
             "free-under-class", "equal-class"]
    if len(frames) != 9:
        raise CheckingError("priority report is incomplete/extra")
    for i, f in enumerate(frames):
        fields = {"kind", "id", "run", "context"}
        if i == 0:
            fields |= {"count"}
        elif i == 8:
            fields |= {"count", "completed"}
        else:
            fields |= {"case", "ranks", "priority"}
        _exact(f, fields)
        if (type(f["id"]) is not int or f["id"] != i or f["run"] != run_id or
                f["context"] != context or f["kind"] != ("start" if i == 0 else "end" if i == 8 else "record")):
            raise CheckingError("priority report identity/order")
        if i in (0, 8):
            if type(f["count"]) is not int or f["count"] != 7:
                raise CheckingError("priority count")
            if i == 8 and (type(f["completed"]) is not int or f["completed"] != 7):
                raise CheckingError("priority terminal incomplete")
        elif f["case"] != names[i - 1]:
            raise CheckingError("priority case identity")
        elif i <= 3:
            if (type(f["ranks"]) is not list or not f["ranks"] or
                    any(type(v) is not int for v in f["ranks"]) or f["priority"] is not None):
                raise CheckingError("priority ranks type")
        elif f["ranks"] is not None or type(f["priority"]) is not int:
            raise CheckingError("priority comparison type")
    return [{k: f[k] for k in ("case", "ranks", "priority")} for f in frames[1:-1]]


def _observe_priority(case, source):
    ids, expected_ranks = _priority_source_inputs(case.model)
    nonce = os.urandom(16).hex()
    module, report = case.tmp / ("priority-" + nonce), case.tmp / ("priority-" + nonce + ".ndjson")
    _copy_owned(source, module)
    replacements = dict(VIEWS=json.dumps((b"[" + b",".join(case.context["raw"]) + b"]").decode("utf8")),
                        ROOT=json.dumps(case.context["root"]), REPORT=json.dumps(str(report)),
                        RUN=json.dumps(nonce), CONTEXT=json.dumps(case.context["id"]),
                        **{k: str(v) for k, v in ids.items()})
    path = module / "apidoor/review103_s08_priority_test.go"
    _new_path(path)
    path.write_text(_go_template(_PRIORITY_GO, replacements), encoding="utf8")
    snapshot = _tree_receipt(module)
    try:
        done = subprocess.run(["go", "test", "-json", "-count=1", "-run", "^TestReview103S08Priority$", "./apidoor"],
                              cwd=module, env=GOENV, capture_output=True)
    except (OSError, UnicodeError, subprocess.SubprocessError) as exc:
        raise CheckingError(f"priority observer process failed: {exc}") from exc
    _complete_observer_go_test(done, test="TestReview103S08Priority")
    _verify_tree(module, snapshot)
    actual = _read_priority_report(_regular_bytes(report, mode=0o600), nonce, case.context["id"])
    return _priority_differences(expected_ranks, actual)


def _priority_differences(expected_ranks, actual):
    # Source specifies relative priority, not the private integer encoding.
    # Complete typed vectors remain actual observations; compare their path shape
    # and the existing comparator's observable decisions, never fixed rank values.
    return [(w["case"], w, a) for w, a in zip(expected_ranks, actual)
            if (w["priority"] != a["priority"] or
                w["ranks"] is not None and len(w["ranks"]) != len(a["ranks"]))]


def _active_s08_mutants(model, source):
    """Apply the four existing error meanings to active S08 code, never a dead legacy table."""
    source = Path(source)
    rt = (source / "apidoor/routes_rt.go").read_text()
    generated = (source / "apidoor/routes.go").read_text()
    def replace_once(text, before, after):
        if text.count(before) != 1:
            raise CheckingError("active Source mutant anchor missing/ambiguous")
        return text.replace(before, after)
    prefix = replace_once(rt, "for _, server := range operation.servers {",
                          "for _, server := range operation.servers {\n\t\t\tif server.mounted { continue }")
    all405 = replace_once(rt, "if unanimous || best[0].file {", "if false && (unanimous || best[0].file) {")
    record = next(r for r in model.declarations if r["route"] == "/folders/{id}" and r["method"] == "get")
    marker = "{op: " + record["symbol"] + ","
    start = generated.index(marker, generated.index("func p06Bindings"))
    end = generated.index("\n", start)
    line = generated[start:end]
    changed = replace_once(line, '"id": paramCheck{minLen: 1,', '"id": paramCheck{minLen: 3,')
    pattern = generated[:start] + changed + generated[end:]
    rank = replace_once(rt, 'p06BoundSegment{literal: part, rank: 1, raw: c.file}',
                        'p06BoundSegment{literal: part, rank: 0, raw: c.file}')
    return {"prefix-lost": ("routes_rt.go", prefix), "all405": ("routes_rt.go", all405),
            "pattern": ("routes.go", pattern), "rank": ("routes_rt.go", rank)}


def _test_source_route_mutants(case):
    inputs = _source_complete_probes(case.model, probes(case.model, random.Random(7)))
    normal = case._route_executor(case.fresh, inputs)
    case.assertEqual(disagree(inputs, normal, lambda p: expected(case.model, p)), [])
    case.assertEqual(_observe_priority(case, case.fresh), [], "normal Source priority baseline disagrees")
    outcomes = {}
    for name, (filename, changed) in _active_s08_mutants(case.model, case.fresh).items():
        with case.subTest(mutant=name):
            module = case.tmp / ("s08-mut-" + name + "-" + os.urandom(8).hex())
            _copy_owned(case.fresh, module)
            (module / "apidoor" / filename).write_text(changed)
            if name == "rank":
                bad = _observe_priority(case, module)
                channel = "compiled-private-bind-and-priority"
            else:
                got = case._route_executor(module, inputs)
                bad = disagree(inputs, got, lambda p: expected(case.model, p))
                channel = "public-Route"
            outcomes[name] = dict(status="semantic-mismatch" if bad else "survivor", channel=channel,
                                  mismatch_count=len(bad), first_named_mismatches=bad[:3])
            case.assertTrue(bad, f"{name} survives")
    case.s08_mutant_evidence = outcomes
    (case.tmp / ("s08-mutant-evidence-" + os.urandom(8).hex() + ".json")).write_text(
        json.dumps(outcomes, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    _run_required_original_mutants({"prefix-lost", "all405", "pattern", "rank"}, set(outcomes),
                                   {name: row["status"] for name, row in outcomes.items()})


def _test_catalogue_observations(self):
    receipt = self._observer_receipt
    ids, inputs = _mandatory_observation_inputs(self.model)
    self.assertEqual(receipt["obligations"], ids, "mandatory obligations changed after baseline")
    self.assertEqual(_compare_observations(receipt["frames"], inputs, _source_projection(self.model),
                                          lambda p: _expected_route_observation(self.model, p)), [])
    self.test_mutants()  # The active S08 delegate keeps the original noncontext loop intact.
    evidence = self.s08_mutant_evidence
    _run_required_original_mutants({"prefix-lost", "all405", "pattern", "rank"}, set(evidence),
                                   {name: row["status"] for name, row in evidence.items()})
    self.s08_context_limits = {"second-kind-positive": "GAP", "admission/B1/N5": "UNKNOWN"}


def _checked_observation(done, report, module, snapshot, context, inputs, run_id, symbols, want_meta, want_route):
    # The expected functions remain untouched until every service/trust/premise check is complete.
    _requests(inputs)
    _validate_context(context)
    _complete_observer_go_test(done)
    _verify_tree(module, snapshot)
    frames = _read_observation_frames(report, inputs, run_id, context["id"], symbols)
    return _compare_observations(frames, inputs, want_meta, want_route)


def _mock_observation(n=2, op_count=2):
    """Small synthetic frames, never a generated-module/native or Source proof."""
    inputs = [("GET", "/a"), ("GET", "/b")][:n]
    run_id, context = "a" * 32, "synthetic-observer-context"
    ops = [dict(op=i, method="GET", path="/a" if i == 1 else "/b", prefixed=False,
                params=[], responses=[], request_media=[], request_required=False) for i in range(1, op_count + 1)]
    priv = dict(op=1, path="/a", component="", source="fixture#/paths/~1a/get", base="fixture",
                servers=[], segments=[], checks=[], item_parameters=[], operation_parameters=[], security="[]")
    provenance = dict(operations=[priv], references=[], documents=[dict(path="fixture", sha256="1" * 64)])
    want_meta = dict(ops=copy.deepcopy(ops), symbols=[dict(name="OpA", op=1), dict(name="OpB", op=2)],
                     provenance=copy.deepcopy(provenance))
    for key in list(provenance):
        provenance[key + "_count"] = len(provenance[key])
    shared = lambda kind, i: dict(kind=kind, id=i, run=run_id, context=context)
    meta = dict(shared("meta", 0), package=_S08_PACKAGE, test=_S08_TEST, ops=ops, ops_count=len(ops),
                symbols=copy.deepcopy(want_meta["symbols"]), symbols_count=2, provenance=provenance)
    frames = [meta] + [dict(shared("route", i), result=dict(path=path, method=method, params={}, prefixed=False),
                           op=i, sub="", reason=None) for i, (method, path) in enumerate(inputs, 1)]
    frames.append(dict(shared("end", n + 1), meta=1, routes=n, boolean_calls=0, snapshot_unchanged=True))
    return inputs, run_id, context, frames, want_meta


def _mock_lifecycle(events=None, code=0, stderr=b""):
    """Injected go-test-json bytes, not a child process."""
    if events is None:
        events = [dict(Action="start", Package=_S08_PACKAGE), dict(Action="run", Package=_S08_PACKAGE, Test=_S08_TEST),
                  dict(Action="pass", Package=_S08_PACKAGE, Test=_S08_TEST), dict(Action="pass", Package=_S08_PACKAGE)]
    return subprocess.CompletedProcess(["synthetic-go-test"], code, _mock_ndjson(events), stderr)


def _mock_ndjson(frames):
    return ("\n".join(json.dumps(f, ensure_ascii=False, allow_nan=False) for f in frames) + "\n").encode("utf-8")


def _mock_context(identity="synthetic-observer-context"):
    raw = b'{"name":"root","unit":{"rows":"units"}}'
    return dict(id=identity, root="root", raw=[raw], views=[_strict_json(raw)], digests=[_sha(raw)])


def _mock_private(directory, frames):
    """Synthetic data-only file; never write a Go module, observer, provider or context companion."""
    path = Path(directory) / "private.data"
    _new_path(path)
    try:
        with path.open("xb") as f:
            f.write(_mock_ndjson(frames))
        path.chmod(0o600)
    except (OSError, UnicodeError) as exc:
        raise CheckingError("mock encode/close failed") from exc
    return path


def probes(model, rnd):
    out = []
    for p in model.paths:
        for pre in (False, True) if p["prefixed"] else (False,):
            vals = []
            good = True
            for s in p["segs"]:
                m = re.fullmatch(r"\{(.+)\}", s)
                if not m:
                    vals.append(s)
                    continue
                v = model.sample(p, m[1])
                if v is None:
                    good = False
                    break
                vals.append(v)
            if not good:
                continue
            path = "/" + "/".join((["testsub"] if pre else []) + vals)
            for meth in p["ops"]:
                out.append((meth, path))
            out.append(("TRACE", path))                       # Unsupported method.
            bad = path.replace("/" + vals[0], "/zz-unknown", 1) if vals else "/zz-unknown"
            out.append(("GET", bad))
    for p in model.paths:                             # Free-parameter minLength boundary and one character shorter.
        for k, seg in enumerate(p["segs"]):
            m = re.fullmatch(r"\{(.+)\}", seg)
            if not m or m[1] in CATALOG:
                continue
            c = p["checks"][m[1]]
            base = []
            for j, s2 in enumerate(p["segs"]):
                mm = re.fullmatch(r"\{(.+)\}", s2)
                base.append(s2 if not mm else model.sample(p, mm[1]))
            if None in base:
                continue
            for n in (c["min"], c["min"] - 1):
                if n < 1:
                    continue
                vals = list(base)
                vals[k] = "a" * n
                out.append((next(iter(p["ops"])), "/" + "/".join(vals)))
    out += [("GET", "/%zz"), ("GET", "nope"), ("GET", "/testsub/zz/zz/zz/zz/zz"), ("GET", "/zzsub/units")]
    for _ in range(300):
        segs = [rnd.choice(["testsub", "units", "tallies", "probe", "folders", "domain", "at", "c1", "zz", "",
                            "manifest", "where", "servers", "api", "metrics", "%41"]) for _ in range(rnd.randint(0, 5))]
        out.append((rnd.choice(["GET", "PUT", "POST", "DELETE", "PATCH"]), "/" + "/".join(segs)))
    return out



def _source_complete_probes(model, original):
    """Preserve every old probe; require every applicable source specialization too."""
    if not model.context:
        return original
    _, mandatory = _mandatory_observation_inputs(model)
    return list(original) + mandatory


def _source_applicable_want(model, original):
    if not model.context:
        return original
    # Empty root tables/pass do not become short routes; mounts remain separate.
    # This is full Source/catalogue expansion, never a projection of observed Ops.
    return {(entry["p"]["path"], method, entry["prefixed"])
            for entry in model.routes for method in entry["p"]["ops"]}


def expected(model, probe):
    r = model.route(*probe)
    if r[0] == "err":
        return {"err": r[1]}
    return {"path": r[1], "method": r[2], "params": r[3], "prefixed": r[4]}


class DoorLessonBase:
    LESSON = SLUG = None

    @classmethod
    def setUpClass(cls):
        if not shutil.which("go"):
            raise unittest.SkipTest("go is not in PATH")
        try:
            cls.tmp = Path(tempfile.mkdtemp(prefix="door-lesson-"))
            out = cls.tmp / "fresh"
            done = subprocess.run([sys.executable, str(HERE / "gen_door_lesson.py"), "--lesson", cls.LESSON, str(out)],
                                  capture_output=True, text=True)
        except (OSError, UnicodeError, subprocess.SubprocessError) as exc:
            raise CheckingError(f"route generation preparation/process failed: {exc}") from exc
        if type(getattr(done, "returncode", None)) is not int or done.returncode != 0:
            raise CheckingError(f"route generation failed: {done!r}")
        cls.fresh = out / "go"
        cls.original_snapshot = _tree_receipt(cls.fresh)
        cls.model = Model(cls.LESSON)

    def setUp(self):
        self._route_executor = lambda mod, pr: run(mod, pr)
        if self.LESSON != "06-console":
            return
        self.context = _given_contexts()[0]
        self._b0 = self.fresh
        _verify_tree(self._b0, self.original_snapshot)
        self.fresh, self._companion = _owned_context_module(
            self._b0, self.tmp / ("context-" + os.urandom(16).hex()), self.context)
        self._observer_receipt = _observe_baseline(self)
        self._route_executor = lambda mod, pr: _component_checked_run(self, mod, pr)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_fresh(self):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        for name in ("routes.go", "routes_rt.go"):
            kept = output_lesson.output_root() / self.SLUG / "go/apidoor" / name
            self.assertEqual(kept.read_bytes(), (self.fresh / "apidoor" / name).read_bytes(), f"{kept} is stale")

    def test_ops(self):
        text = (self.fresh / "apidoor/routes.go").read_text()
        n = sum(len(p["ops"]) for p in self.model.paths)
        self.assertEqual(len(re.findall(r"^\tOp\w+(?:\s+Op = iota \+ 1)?\s+// [A-Z]+ /", text, re.M)), n)
        for p in self.model.paths:
            for m in p["ops"]:
                self.assertIn(f'"{p["path"]} {m}": ', text)

    def test_probes(self):
        rnd = random.Random(6)
        pr = probes(self.model, rnd)
        pr = _source_complete_probes(self.model, pr)
        got = self._route_executor(self.fresh, pr)
        bad = disagree(pr, got, lambda p: expected(self.model, p))
        self.assertEqual(bad[:3], [], f"{len(bad)} of {len(pr)} probes disagree")
        hit_ops = {(g["path"], g["method"], g["prefixed"]) for g in got if "path" in g}
        want = {(p["path"], m, pre) for p in self.model.paths for m in p["ops"]
                for pre in ((False, True) if p["prefixed"] else (False,))}
        want = _source_applicable_want(self.model, want)
        missed = want - hit_ops
        # Allow at most10% probes shadowed by more-specific templates or lacking a sample.
        self.assertLessEqual(len(missed), len(want) // 10, f"probes reach too few operations: {sorted(missed)[:10]}")
        if self.model.context:
            self.assertFalse(missed, f"mandatory source route coverage GAP: {sorted(missed)}")
        codes = {g.get("err") for g in got}
        self.assertIn(404, codes)
        if any(p["all405"] for p in self.model.paths):
            self.assertIn(405, codes)

    def test_mutants(self):
        if self.model.context:
            return _test_source_route_mutants(self)
        rnd = random.Random(7)
        pr = probes(self.model, rnd)
        src = (self.fresh / "apidoor/routes.go").read_text()
        rt = (self.fresh / "apidoor/routes_rt.go").read_text()
        m405 = re.search(r'^\t("[^"]+":\s+)true,$', src[src.index("var all405"):], re.M)
        muts = {
            "prefix-lost": ("routes.go", re.sub(r"(\{path: \"[^\"]+\", segs: \[\]segment\{\{param: \"sub\"\}[^\n]*prefixed: )true",
                                                r"\1false", src, count=1)),
            "all405": ("routes.go", src.replace(f"\t{m405[1]}true,", f"\t{m405[1]}false,", 1) if m405 else src),
            "pattern": ("routes.go", re.sub(r'("(?!sub"|rows"|table"|pass")\w+": paramCheck\{minLen: )1(, maxLen: -1, rx: nil)',
                                            r"\g<1>3\2", src, count=1)),
            "rank": ("routes_rt.go", rt.replace('case s.param == "sub" || s.param == "rows"', 'case s.param == "sub" || s.param == "zz"', 1)),
        }
        prefixed = any(p["prefixed"] for p in self.model.paths)
        shapes = {}
        for p, tsegs, pre in self.model.templates():
            shapes.setdefault(tuple("{}" if re.fullmatch(r"\{.+\}", sg) else sg for sg in tsegs), []).append(tsegs)

        def rows_vs_free(group):                       # rows rank matters when a catalog parameter and a free parameter share a position.
            for i in range(len(group[0])):
                names = {sg for sg in (t[i] for t in group)}
                if "{rows}" in names and any(re.fullmatch(r"\{(.+)\}", n) and n[1:-1] not in CATALOG for n in names):
                    return True
            return False
        classes = any(len(v) > 1 and rows_vs_free(v) for v in shapes.values())
        for name, (f, text) in muts.items():
            if (name == "prefix-lost" and not prefixed) or (name == "rank" and not classes) \
                    or (name == "all405" and m405 is None):
                continue                                   # Inapplicable to lessons without prefixes/catalog classes.
            base = src if f == "routes.go" else rt
            if name == "pattern" and text == base:
                continue                                   # No free parameter with minLength1 and no pattern exists in this lesson.
            with self.subTest(mutant=name):
                if text == base:
                    raise CheckingError(f"{name}: the applicable mutant does not change its target")
                mod = self.tmp / f"mut-{name}"
                try:
                    shutil.copytree(self.fresh, mod)
                    (mod / "apidoor" / f).write_text(text)
                except (OSError, UnicodeError) as exc:
                    raise CheckingError(f"{name}: mutant preparation failed: {exc}") from exc
                got = self._route_executor(mod, pr)
                bad = disagree(pr, got, lambda p: expected(self.model, p))
                self.assertTrue(bad, f"{name} survives")


class RouteServiceControls(unittest.TestCase):
    def test_accounting_dependency_guard_rejects_helper_mutations(self):
        raw = _regular_bytes(HERE / "test_gen_machine.py")
        _complete_observer_go_test(_mock_lifecycle())
        self.assertEqual(raw.count(b"    return failed\n"), 1)
        mutated = raw.replace(b"    return failed\n", b"    return []\n")
        with patch(__name__ + "._regular_bytes", return_value=mutated), self.assertRaisesRegex(
                CheckingError, "service-accounting dependency changed"):
            _complete_observer_go_test(_mock_lifecycle())

    """Independent checking-service controls; subprocess responses here are injected."""

    def setUp(self):
        self.inputs = [("GET", "/a"), ("GET", "/b")]
        self.results = [{"err": 404}, {"err": 404}]

    def frames(self, results=None):
        return [{"id": i, "result": v} for i, v in enumerate(self.results if results is None else results, 1)]

    def report(self, frames=None, code=0):
        return subprocess.CompletedProcess(["go", "run"], code,
                                           "".join(json.dumps(f, ensure_ascii=False) + "\n"
                                                   for f in (self.frames() if frames is None else frames)), "")

    def module(self, directory):
        mod = Path(directory) / "go"
        mod.mkdir()
        (mod / "go.mod").write_text("module checking.control\n")
        return mod

    def mutant_case(self, directory):
        fresh = Path(directory) / "fresh"
        (fresh / "apidoor").mkdir(parents=True)
        # Text-only applicability fixture, never compiled or used as a route oracle.
        (fresh / "apidoor/routes.go").write_text(
            'var all405 = map[string]bool{\n\t"/{sub}/": true,\n}\n'
            '{path: "/{sub}/", segs: []segment{{param: "sub"}}, prefixed: true},\n'
            '\t"free": paramCheck{minLen: 1, maxLen: -1, rx: nil},\n')
        (fresh / "apidoor/routes_rt.go").write_text('case s.param == "sub" || s.param == "rows":\n')
        obj = DoorLesson_p06("test_mutants")
        obj.tmp, obj.fresh = Path(directory), fresh
        obj._route_executor = lambda mod, pr: run(mod, pr)
        obj.model = Mock(paths=[{"prefixed": True}])
        obj.model.context = None  # This service fixture models the noncontext executor.
        obj.model.templates.return_value = [({}, ["{rows}"], False), ({}, ["{free}"], False)]
        return obj

    def test_complete_positive(self):
        success = {"path": "/{name}", "method": "GET", "params": {"name": "a"}, "prefixed": False}
        for value in ({"err": 0}, {"err": 404}, {"err": 405}, success):
            with self.subTest(value=value):
                self.assertEqual(read_report(self.inputs, self.report(self.frames([value, value]))), [value, value])
        with tempfile.TemporaryDirectory() as td:
            mod = self.module(td)
            with patch(__name__ + ".subprocess.run", return_value=self.report()) as proc:
                self.assertEqual(run(mod, self.inputs), self.results)
            sent = [json.loads(line) for line in proc.call_args.kwargs["input"].split("\n") if line]
            self.assertEqual(sent, [{"ID": i, "Method": m, "Path": p}
                                    for i, (m, p) in enumerate(self.inputs, 1)])
            self.assertNotIn("timeout", proc.call_args.kwargs)

    def test_zero_input_before_preparation(self):
        with tempfile.TemporaryDirectory() as td, patch(__name__ + ".subprocess.run") as proc:
            for bad in ([], (), None, [("GET",)], [(True, "/a")]):
                with self.subTest(probes=bad), self.assertRaises(CheckingError):
                    run(Path(td) / "never-created", bad)
            proc.assert_not_called()
            self.assertEqual(list(Path(td).iterdir()), [])
        with self.assertRaises(CheckingError):
            read_report([], self.report([]))

    def test_zero_short_extra_reports(self):
        good = self.frames()
        for frames in ([], good[:1], good + [good[0]]):
            with self.subTest(frames=frames), self.assertRaises(CheckingError):
                read_report(self.inputs, self.report(frames))

    def test_frame_identities(self):
        good = self.frames()
        cases = [good[::-1], [good[0], good[0]], [{"result": self.results[0]}, good[1]]]
        cases += [[dict(good[0], id=v), good[1]] for v in (0, 3, True, 1.0, "1", None)]
        for frames in cases:
            with self.subTest(frames=frames), self.assertRaises(CheckingError):
                read_report(self.inputs, self.report(frames))

    def test_frame_shapes(self):
        for frame in ({"id": 1}, {"id": 1, "result": {"err": 404}, "extra": 1}, [], None):
            with self.subTest(frame=frame), self.assertRaises(CheckingError):
                read_report(self.inputs, self.report([frame, self.frames()[1]]))
        for result in ({}, {"err": 404, "path": "/a"}, {"path": "/a"}, "panic: control"):
            with self.subTest(result=result), self.assertRaises(CheckingError):
                read_report(self.inputs, self.report(self.frames([result, self.results[1]])))

    def test_typed_shapes(self):
        good = {"path": "/a", "method": "GET", "params": {}, "prefixed": False}
        bad = [{"err": True}, {"err": 404.0}, {"err": "404"}]
        bad += [dict(good, **{key: value}) for key, value in
                (("path", None), ("method", 1), ("params", None), ("params", {"x": 1}),
                 ("params", {1: "x"}), ("prefixed", 0))]
        for result in bad:
            with self.subTest(result=result), self.assertRaises(CheckingError):
                disagree(self.inputs, [result, self.results[1]], lambda p: self.results[0])

    def test_valid_wrong_values_are_semantic(self):
        want = {"path": "/a", "method": "GET", "params": {"x": "a"}, "prefixed": False}
        for got in (dict(want, path="/other"), dict(want, method="POST"),
                    dict(want, params={"x": "other"}), dict(want, prefixed=True), {"err": 500}):
            with self.subTest(got=got):
                values = read_report(self.inputs, self.report(self.frames([got, want])))
                self.assertEqual(disagree(self.inputs, values, lambda p: want), [(self.inputs[0], want, got)])

    def test_strict_json(self):
        tail = json.dumps(self.frames()[1]) + "\n"
        texts = ["", "\n\n", "{bad}\n" + tail, '\ufeff' + self.report().stdout,
                 '{"id":1,"id":1,"result":{"err":404}}\n' + tail,
                 '{"id":1,"result":{"err":404,"err":405}}\n' + tail,
                 '{"id":1,"result":{"err":NaN}}\n' + tail,
                 '{"id":1,"result":{"err":Infinity}}\n' + tail,
                 self.report().stdout + "\n", self.report().stdout + "garbage", "\ud800", b"\xff"]
        for text in texts:
            with self.subTest(text=repr(text)), self.assertRaises(CheckingError):
                read_report(self.inputs, subprocess.CompletedProcess([], 0, text, ""))

    def test_preparation_errors(self):
        with tempfile.TemporaryDirectory() as td:
            mod = self.module(td)
            for content in (b"", b"\xff"):
                (mod / "go.mod").write_bytes(content)
                with self.subTest(content=content), self.assertRaises(CheckingError):
                    run(mod, self.inputs)
            (mod / "go.mod").write_text("module checking.control\n")
            with patch.object(Path, "write_text", side_effect=OSError("driver write control")):
                with self.assertRaises(CheckingError):
                    run(mod, self.inputs)
            (mod / "go.mod").unlink()
            with self.assertRaises(CheckingError):
                run(mod, self.inputs)

    def test_start_errors(self):
        with tempfile.TemporaryDirectory() as td:
            mod = self.module(td)
            for failure in (OSError("start control"), UnicodeError("decode control"),
                            subprocess.TimeoutExpired(["go"], 1)):
                with self.subTest(failure=failure), patch(__name__ + ".subprocess.run", side_effect=failure):
                    with self.assertRaises(CheckingError):
                        run(mod, self.inputs)

    def test_compile_nonzero_even_with_complete_output(self):
        for frames in ([], self.frames()[:1], self.frames()):
            done = self.report(frames, code=1)
            done.stderr = "compile control"
            with self.subTest(frames=frames), self.assertRaises(CheckingError):
                read_report(self.inputs, done)
        self.assertFalse(issubclass(CheckingError, AssertionError))

    def test_terminal_errors_are_not_semantic(self):
        with tempfile.TemporaryDirectory() as td:
            mod = self.module(td)
            for error in ("panic: control", "scanner failed", "encoder failed"):
                done = self.report(code=1)
                done.stderr = error
                with self.subTest(error=error), patch(__name__ + ".subprocess.run", return_value=done):
                    with self.assertRaises(CheckingError):
                        run(mod, self.inputs)

    def test_generation_errors(self):
        for failure in (subprocess.CompletedProcess([], 1, "partial", "generation control"), OSError("start control")):
            with tempfile.TemporaryDirectory() as td, patch(__name__ + ".shutil.which", return_value="go"), \
                    patch(__name__ + ".tempfile.mkdtemp", return_value=td):
                kwargs = {"side_effect": failure} if isinstance(failure, Exception) else {"return_value": failure}
                with patch(__name__ + ".subprocess.run", **kwargs), self.assertRaises(CheckingError):
                    DoorLesson_p06.setUpClass()

    def test_complete_before_oracle(self):
        oracle = Mock(return_value={"err": 404})
        for got in ([], [{"err": 405}], [{"err": 405}, {}], self.results + [{"err": 404}]):
            with self.subTest(got=got), self.assertRaises(CheckingError):
                disagree(self.inputs, got, oracle)
        oracle.assert_not_called()
        with patch(__name__ + ".probes", return_value=self.inputs), \
                patch(__name__ + ".run", return_value=[{"err": 405}]), \
                patch(__name__ + ".expected") as expected_call:
            obj = DoorLesson_p06("test_probes")
            obj._route_executor = lambda mod, pr: run(mod, pr)
            obj.model, obj.fresh = Mock(), Path("unused")
            obj.model.context = None  # No catalogue or Source materialization in this service control.
            with self.assertRaises(CheckingError):
                obj.test_probes()
            expected_call.assert_not_called()
        with self.assertRaises(CheckingError):
            disagree(self.inputs, self.results, Mock(side_effect=AssertionError("oracle control")))

    def test_mutant_errors_propagate(self):
        for target in ("prefix-lost", "all405", "pattern", "rank"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as td:
                obj = self.mutant_case(td)

                def result(mod, inputs):
                    if mod.name == "mut-" + target:
                        raise CheckingError("process control")
                    return [{"err": 405}, {"err": 404}]

                with patch(__name__ + ".probes", return_value=self.inputs), \
                        patch(__name__ + ".expected", return_value={"err": 404}), \
                        patch(__name__ + ".run", side_effect=result), self.assertRaises(CheckingError):
                    obj.test_mutants()

    def test_correct_mutant_survives(self):
        for target in ("prefix-lost", "all405", "pattern", "rank"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as td:
                obj = self.mutant_case(td)

                def result(mod, inputs):
                    return self.results if mod.name == "mut-" + target else [{"err": 405}, {"err": 404}]

                with patch(__name__ + ".probes", return_value=self.inputs), \
                        patch(__name__ + ".expected", return_value={"err": 404}), \
                        patch(__name__ + ".run", side_effect=result), self.assertRaisesRegex(AssertionError, target + " survives"):
                    obj.test_mutants()

    def test_named_semantic_mismatch(self):
        self.assertEqual(disagree(self.inputs, [{"err": 405}, {"err": 404}], lambda p: {"err": 404}),
                         [(self.inputs[0], {"err": 404}, {"err": 405})])

    def test_mutation_applicability(self):
        with tempfile.TemporaryDirectory() as td:
            obj = self.mutant_case(td)
            with patch(__name__ + ".probes", return_value=self.inputs), \
                    patch(__name__ + ".expected", return_value={"err": 404}), \
                    patch(__name__ + ".run", return_value=[{"err": 405}, {"err": 404}]) as proc:
                obj.test_mutants()
                self.assertEqual([c.args[0].name for c in proc.call_args_list],
                                 ["mut-prefix-lost", "mut-all405", "mut-pattern", "mut-rank"])
            src = obj.fresh / "apidoor/routes.go"
            src.write_text(src.read_text().replace("prefixed: true", "prefixed: false"))
            with patch(__name__ + ".probes", return_value=self.inputs), \
                    patch(__name__ + ".run") as proc, self.assertRaises(CheckingError):
                obj.test_mutants()
            proc.assert_not_called()

    def test_unicode_and_terminal_lf_neighbours(self):
        for char in ("\u0085", "\u2028", "\u2029"):
            value = {"path": "/" + char, "method": "GET", "params": {"name": "a" + char + "b"}, "prefixed": False}
            text = self.report(self.frames([value, value])).stdout
            self.assertIn(char, text)
            for ending in (text, text[:-1]):
                with self.subTest(char=repr(char), final_lf=ending.endswith("\n")):
                    self.assertEqual(read_report(self.inputs, subprocess.CompletedProcess([], 0, ending, "")), [value, value])
        self.assertEqual(read_report(self.inputs, subprocess.CompletedProcess([], 0, self.report().stdout.encode(), "")),
                         self.results)


    def test_private_observer_ob01(self):
        """Mock positive: full lifecycle/private response precedes any expected comparison."""
        inputs, nonce, context, frames, want = _mock_observation()
        oracle = Mock(side_effect=lambda p: dict(result=dict(path=p[1], method=p[0], params={}, prefixed=False),
                                                 op=1 if p[1] == "/a" else 2, sub=""))
        with tempfile.TemporaryDirectory() as td:
            path = _mock_private(td, frames)
            snapshot = _tree_receipt(td)
            self.assertEqual(_checked_observation(_mock_lifecycle(), path, td, snapshot, _mock_context(context),
                                                  inputs, nonce, ["OpA", "OpB"], want, oracle), [])
            self.assertEqual(oracle.call_count, 2)
            broken = _mock_lifecycle(code=1)
            oracle.reset_mock()
            with self.assertRaises(CheckingError):
                _checked_observation(broken, path, td, snapshot, _mock_context(context),
                                     inputs, nonce, ["OpA", "OpB"], want, oracle)
            oracle.assert_not_called()

    def test_private_observer_ob02(self):
        events = _ndjson(_mock_lifecycle().stdout)
        for index, key, value in ((0, "Package", "foreign/apidoor"), (1, "Test", "Other"),
                                  (2, "Test", _S08_TEST + "/sub"), (3, "Package", "foreign/apidoor")):
            changed = copy.deepcopy(events)
            changed[index][key] = value
            with self.subTest(index=index, key=key), self.assertRaises(CheckingError):
                _complete_observer_go_test(_mock_lifecycle(changed))
        with self.assertRaises(CheckingError):
            _complete_observer_go_test(_mock_lifecycle(), test="Other")
        with self.assertRaises(CheckingError):
            _complete_observer_go_test(_mock_lifecycle(), package="foreign/apidoor")

    def test_private_observer_ob03(self):
        e = _ndjson(_mock_lifecycle().stdout)
        cases = [e[1:], [e[0], e[2], e[1], e[3]], e[:2] + [e[1]] + e[2:],
                 e[:3] + [e[2], e[3]], e[:2] + [e[3]], e[:3], e + [e[0]],
                 [e[0], e[1], e[3], e[2]], e + [dict(Action="output", Package=_S08_PACKAGE, Output="late")]]
        for i, changed in enumerate(cases):
            with self.subTest(i=i), self.assertRaises(CheckingError):
                _complete_observer_go_test(_mock_lifecycle(changed))

    def test_private_observer_ob04(self):
        e = _ndjson(_mock_lifecycle().stdout)
        for action in ("fail", "skip", "pause", "cont"):
            changed = copy.deepcopy(e)
            changed[2]["Action"] = action
            with self.subTest(action=action), self.assertRaises(CheckingError):
                _complete_observer_go_test(_mock_lifecycle(changed))
        for code in (1, -9, True, None):
            with self.subTest(code=code), self.assertRaises(CheckingError):
                _complete_observer_go_test(_mock_lifecycle(code=code))
        for text in (b"panic: control", b"compile error", b"[build failed]"):
            with self.subTest(text=text), self.assertRaises(CheckingError):
                _complete_observer_go_test(_mock_lifecycle(stderr=text))
        inputs, nonce, context, frames, want = _mock_observation()
        frames[1]["sub"] = "mismatching-but-nonzero"
        oracle = Mock()
        with tempfile.TemporaryDirectory() as td:
            path = _mock_private(td, frames); snapshot = _tree_receipt(td)
            with self.assertRaises(CheckingError):
                _checked_observation(_mock_lifecycle(code=1), path, td, snapshot, _mock_context(context),
                                     inputs, nonce, ["OpA", "OpB"], want, oracle)
            oracle.assert_not_called()
        # Injection at the process boundary; no module/observer is materialized and no Go runs.
        with tempfile.TemporaryDirectory() as td:
            snapshot = _tree_receipt(td)
            for error in (OSError("start"), subprocess.TimeoutExpired("synthetic", 1), UnicodeError("decode")):
                with patch(__name__ + ".subprocess.run", side_effect=error) as proc, self.assertRaises(CheckingError):
                    _go_observer(td, Path(td) / "absent.data", _mock_context(), [("GET", "/a")], ["OpA"], "a" * 32, snapshot)
                proc.assert_called_once()

    def test_private_observer_ob05(self):
        positive = _mock_lifecycle()
        for raw in (b"\xff", b"{}", b"{", positive.stdout + b"\n", b'{"Action":"start","Action":"run"}',
                    b'{"Action":NaN}', b'{"Elapsed":Infinity}'):
            with self.subTest(raw=raw), self.assertRaises(CheckingError):
                _complete_observer_go_test(subprocess.CompletedProcess([], 0, raw, b""))
        for key, value in (("Elapsed", True), ("Elapsed", "0"), ("Time", 0), ("Output", []),
                            ("Test", None), ("unknown", "x"), ("Action", 1)):
            events = _ndjson(positive.stdout)
            events[1][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(CheckingError):
                _complete_observer_go_test(_mock_lifecycle(events))

    def test_private_observer_ob06(self):
        inputs, nonce, context, frames, _ = _mock_observation()
        cases = [[], frames[:-1], frames[1:], frames + [frames[-1]], frames[:1] + frames[2:],
                 [frames[1], frames[0], *frames[2:]], [frames[0], frames[2], frames[1], frames[3]]]
        for i, changed in enumerate(cases):
            with self.subTest(i=i), self.assertRaises(CheckingError):
                _frame_shapes(changed, inputs, nonce, context, ["OpA", "OpB"], _S08_PACKAGE, _S08_TEST)
        with patch(__name__ + "._copy_owned") as prep, patch(__name__ + ".subprocess.run") as proc:
            for empty in ([], (), None, [(1, "/a")], [("GET", None)]):
                with self.subTest(empty=empty), self.assertRaises(CheckingError):
                    _requests(empty)
            prep.assert_not_called()
            proc.assert_not_called()

    def test_private_observer_ob07(self):
        inputs, nonce, context, frames, _ = _mock_observation()
        for index, key, value in ((0, "id", False), (1, "id", True), (1, "id", 1.0), (2, "id", 1),
                                  (1, "id", 3), (1, "run", "b" * 32), (2, "context", "other"),
                                  (0, "package", "other"), (0, "test", "other")):
            changed = copy.deepcopy(frames)
            changed[index][key] = value
            with self.subTest(index=index, key=key, value=value), self.assertRaises(CheckingError):
                _frame_shapes(changed, inputs, nonce, context, ["OpA", "OpB"], _S08_PACKAGE, _S08_TEST)
        changed = copy.deepcopy(frames)
        del changed[1]["id"]
        with self.assertRaises(CheckingError):
            _frame_shapes(changed, inputs, nonce, context, ["OpA", "OpB"], _S08_PACKAGE, _S08_TEST)

    def test_private_observer_ob08(self):
        inputs, nonce, context, frames, _ = _mock_observation()
        for raw in (b"\xff", b"[", b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'):
            with self.subTest(raw=raw), self.assertRaises(CheckingError):
                _ndjson(raw)
        for key, value in (("unknown", 1), ("result", []), ("op", True), ("sub", None), ("reason", "x")):
            changed = copy.deepcopy(frames)
            changed[1][key] = value
            with self.subTest(key=key), self.assertRaises(CheckingError):
                _frame_shapes(changed, inputs, nonce, context, ["OpA", "OpB"], _S08_PACKAGE, _S08_TEST)
        for key in frames[0]:
            changed = copy.deepcopy(frames)
            del changed[0][key]
            with self.subTest(missing=key), self.assertRaises(CheckingError):
                _frame_shapes(changed, inputs, nonce, context, ["OpA", "OpB"], _S08_PACKAGE, _S08_TEST)

    def test_private_observer_ob09(self):
        inputs, nonce, context, frames, _ = _mock_observation()
        mutations = [lambda m: m.update(ops_count=3), lambda m: m.update(symbols_count=True),
                     lambda m: m["provenance"].update(references_count=1),
                     lambda m: m["provenance"].update(documents_count=0),
                     lambda m: m["provenance"]["documents"][0].update(sha256="A" * 64),
                     lambda m: m["provenance"]["operations"][0].update(security="{"),
                     lambda m: m["provenance"]["operations"][0].update(security='{"x":1,"x":2}'),
                     lambda m: m["provenance"]["operations"][0].update(security='{"x":NaN}')]
        for i, mutate in enumerate(mutations):
            changed = copy.deepcopy(frames)
            mutate(changed[0])
            with self.subTest(i=i), self.assertRaises(CheckingError):
                _frame_shapes(changed, inputs, nonce, context, ["OpA", "OpB"], _S08_PACKAGE, _S08_TEST)

    def test_private_observer_ob10(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            regular = root / "regular.data"
            regular.write_bytes(b"{}"); regular.chmod(0o600)
            self.assertEqual(_regular_bytes(regular, mode=0o600), b"{}")
            link = root / "link.data"; link.symlink_to(regular)
            fifo = root / "fifo.data"; os.mkfifo(fifo)
            for path in (link, fifo, root, root / "missing.data"):
                with self.subTest(path=path.name), self.assertRaises(CheckingError):
                    _regular_bytes(path, mode=0o600)
            with self.assertRaises(CheckingError):
                _new_path(regular)
            with self.assertRaises(CheckingError):
                _copy_owned(root, root / "clone")
            with patch(__name__ + ".os.open", side_effect=OSError("read")), self.assertRaises(CheckingError):
                _regular_bytes(regular)
        for stage in ("encode", "close"):
            class BrokenWriter:
                def __enter__(self):
                    return self
                def write(self, raw):
                    if stage == "encode":
                        raise OSError("injected encoder write")
                def __exit__(self, typ, value, tb):
                    if stage == "close":
                        raise OSError("injected close")
            with tempfile.TemporaryDirectory() as td, patch.object(Path, "open", return_value=BrokenWriter()), \
                    self.assertRaises(CheckingError):
                _mock_private(td, [])
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "source"; source.mkdir()
            (source / "input.data").write_bytes(b"unchanged synthetic input")
            target = Path(td) / "copy"
            before = _tree_receipt(source)
            _copy_owned(source, target)
            _verify_tree(source, before); _verify_tree(target, before)
            with self.assertRaises(CheckingError):
                _copy_owned(source, target)
            (target / "input.data").write_bytes(b"changed")
            with self.assertRaises(CheckingError):
                _verify_tree(target, before)

    def test_private_observer_ob11(self):
        inputs, nonce, context, frames, _ = _mock_observation()
        text = "x\u0085y\u2028z\u2029panic: is private data"
        frames[0]["provenance"]["operations"][0]["source"] = text
        frames[1]["sub"] = text
        raw = _mock_ndjson(frames)
        for candidate in (raw, raw[:-1]):
            self.assertEqual(_frame_shapes(_ndjson(candidate), inputs, nonce, context,
                                          ["OpA", "OpB"], _S08_PACKAGE, _S08_TEST), frames)
        _complete_observer_go_test(_mock_lifecycle())
        # String-only Go template control: inserted Unicode/tokens are data, not a second substitution.
        rendered = _go_template("__VIEWS__ __ROOT__", {"VIEWS": "__ROOT__ \U0001f9ea", "ROOT": "root"})
        self.assertEqual(rendered, "__ROOT__ \U0001f9ea root")
        done = _mock_lifecycle(); done.stdout = done.stdout[:-1]
        _complete_observer_go_test(done)
        with self.assertRaises(CheckingError):
            _ndjson(raw + b"\n")

    def test_private_observer_ob12(self):
        inputs, nonce, context, frames, want = _mock_observation()
        oracle = lambda p: dict(result=dict(path=p[1], method=p[0], params={}, prefixed=False),
                                op=1 if p[1] == "/a" else 2, sub="")
        self.assertEqual(_compare_observations(frames, inputs, want, oracle), [])
        mutations = [lambda f: f[1].update(sub="wrong"), lambda f: f[1].update(op=0),
                     lambda f: f[0]["provenance"]["operations"][0].update(source="wrong#/source"),
                     lambda f: f[0]["provenance"]["documents"][0].update(sha256="2" * 64),
                     lambda f: f[0]["provenance"]["operations"][0].update(component="wrong")]
        for i, mutate in enumerate(mutations):
            changed = copy.deepcopy(frames); mutate(changed)
            _frame_shapes(changed, inputs, nonce, context, ["OpA", "OpB"], _S08_PACKAGE, _S08_TEST)
            with self.subTest(i=i):
                self.assertTrue(_compare_observations(changed, inputs, want, oracle))
        changed = copy.deepcopy(frames); changed[1]["op"] = False
        with self.assertRaises(CheckingError):
            _frame_shapes(changed, inputs, nonce, context, ["OpA", "OpB"], _S08_PACKAGE, _S08_TEST)

    def test_private_observer_ob13(self):
        good = _mock_context()
        _validate_context(good)
        for mutate in (lambda c: c.update(root=""), lambda c: c.update(root="absent"),
                       lambda c: c.update(views=[]), lambda c: c.update(raw=[]),
                       lambda c: c.update(raw=[b'{}'])):
            changed = copy.deepcopy(good); mutate(changed)
            with patch(__name__ + ".subprocess.run") as proc, self.assertRaises(CheckingError):
                _validate_context(changed)
            proc.assert_not_called()
        changed = copy.deepcopy(good); del changed["root"]
        with self.assertRaises(CheckingError):
            _validate_context(changed)
        inputs, _, _, frames, want = _mock_observation()
        frames[1].update(result={"err": 0}, op=None, sub=None, reason="context unavailable")
        oracle = Mock()
        with self.assertRaises(CheckingError):
            _compare_observations(frames, inputs, want, oracle)
        oracle.assert_not_called()

    def test_private_observer_ob14(self):
        inputs, nonce, context, frames, want = _mock_observation()
        oracle = lambda p: dict(result=dict(path=p[1], method=p[0], params={}, prefixed=False),
                                op=1 if p[1] == "/a" else 2, sub="")
        for key, value in (("boolean_calls", 1), ("snapshot_unchanged", False)):
            changed = copy.deepcopy(frames); changed[-1][key] = value
            _frame_shapes(changed, inputs, nonce, context, ["OpA", "OpB"], _S08_PACKAGE, _S08_TEST)
            self.assertIn("premise-observation:" + key,
                          [d[0] for d in _compare_observations(changed, inputs, want, oracle)])

    def test_private_observer_ob15(self):
        obligations = [("source:1", ("GET", "/a")), ("source:2", ("HEAD", "/b"))]
        self.assertEqual(_mandatory_inputs(obligations), (["source:1", "source:2"], [("GET", "/a"), ("HEAD", "/b")]))
        for value in ([], [("source:1", None)], obligations + [obligations[0]], [("", ("GET", "/a"))]):
            with self.subTest(value=value), self.assertRaises(CheckingError):
                _mandatory_inputs(value)

    def test_private_observer_ob16(self):
        names = {"prefix-lost", "all405", "pattern", "rank"}
        outcomes = {name: "semantic-mismatch" for name in names}
        _run_required_original_mutants(names, names, outcomes)
        for name in names:
            with self.subTest(missing=name), self.assertRaises(AssertionError):
                _run_required_original_mutants(names, names - {name}, outcomes)
            with self.subTest(survivor=name), self.assertRaises(AssertionError):
                _run_required_original_mutants(names, names, dict(outcomes, **{name: "survivor"}))
            with self.subTest(error=name), self.assertRaises(CheckingError):
                _run_required_original_mutants(names, names, dict(outcomes, **{name: "checking-error"}))
        # The fixed legacy executor is invoked, not replaced by a second transport or an oracle.
        with tempfile.TemporaryDirectory() as td:
            module = Path(td); ctx = _mock_context()
            companion = module / "companion.data"; companion.write_text(_context_go(ctx))
            observer = module / "observer"; observer.mkdir()
            receipt = dict(context=ctx, original=_tree_receipt(module), module=observer, snapshot=_tree_receipt(observer))
            case = Mock(context=ctx, _observer_receipt=receipt, _b0=module,
                        _companion=("companion.data", _sha(companion.read_bytes())))
            with patch(__name__ + ".run", return_value=[{"err": 404}]) as delegate:
                self.assertEqual(_component_checked_run(case, module, [("GET", "/a")]), [{"err": 404}])
                delegate.assert_called_once_with(module, [("GET", "/a")])
            with patch(__name__ + ".run", return_value=[{"err": 0}]), self.assertRaises(CheckingError):
                _component_checked_run(case, module, [("GET", "/a")])

    def test_private_observer_ob17(self):
        _assert_s08_preservation()

    def test_private_observer_ob18(self):
        inputs, nonce, context, frames, want = _mock_observation(op_count=146)
        oracle = lambda p: dict(result=dict(path=p[1], method=p[0], params={}, prefixed=False),
                                op=1 if p[1] == "/a" else 2, sub="")
        for count in (145, 146, 147):
            _, _, _, changed, _ = _mock_observation(op_count=count)
            with self.subTest(count=count), tempfile.TemporaryDirectory() as td:
                root = Path(td); module = root / "synthetic-recipe"; module.mkdir()
                recipe = module / "recipe.data"; recipe.write_bytes(b"fixed synthetic observer recipe")
                held_snapshot = _tree_receipt(module)
                path = _mock_private(root, changed)
                differences = _checked_observation(_mock_lifecycle(), path, module, held_snapshot,
                    _mock_context(context), inputs, nonce, ["OpA", "OpB"], want, oracle)
                self.assertEqual(bool(differences), count != 146)
                # Coupled fake count/payload cannot excuse a changed fixed observer recipe.
                recipe.write_bytes(b"forged recipe with matching count")
                compare = Mock()
                with patch(__name__ + "._compare_observations", compare), self.assertRaises(CheckingError):
                    _checked_observation(_mock_lifecycle(), path, module, held_snapshot, _mock_context(context),
                                         inputs, nonce, ["OpA", "OpB"], want, oracle)
                compare.assert_not_called()
        changed = copy.deepcopy(frames); changed[0]["ops_count"] = 145
        with self.assertRaises(CheckingError):
            _frame_shapes(changed, inputs, nonce, context, ["OpA", "OpB"], _S08_PACKAGE, _S08_TEST)
        for incomplete in (frames[:-1], frames[:1] + frames[2:]):
            with tempfile.TemporaryDirectory() as td:
                path = _mock_private(td, incomplete); snapshot = _tree_receipt(td)
                compare = Mock()
                with patch(__name__ + "._compare_observations", compare), self.assertRaises(CheckingError):
                    _checked_observation(_mock_lifecycle(), path, td, snapshot, _mock_context(context),
                                         inputs, nonce, ["OpA", "OpB"], want, oracle)
                compare.assert_not_called()


    def test_source_coverage_retains_all_old_probes_and_requires_the_expansion(self):
        from types import SimpleNamespace
        old = [("GET", "/unchanged-old"), ("GET", "/unchanged-old")]
        model = SimpleNamespace(context={"declared": True})
        with patch(__name__ + "._mandatory_observation_inputs", return_value=(["one"], [("GET", "/source")])):
            self.assertEqual(_source_complete_probes(model, old), old + [("GET", "/source")])
        self.assertEqual(old, [("GET", "/unchanged-old"), ("GET", "/unchanged-old")])
        unbound = SimpleNamespace(context=None)
        self.assertIs(_source_complete_probes(unbound, old), old)
        route = {"path": "/{table}", "ops": {"GET": {}, "HEAD": {}}}
        model.routes = [{"p": route, "prefixed": True}]
        want = _source_applicable_want(model, {("/{table}", "GET", False)})
        self.assertEqual(want, {("/{table}", "GET", True), ("/{table}", "HEAD", True)})
        self.assertIs(_source_applicable_want(unbound, old), old)


    def priority_frames(self):
        names = ["unit-class", "literal", "free-path", "literal-over-class", "class-over-free",
                 "free-under-class", "equal-class"]
        shared = lambda kind, i: dict(kind=kind, id=i, run="run", context="context")
        frames = [dict(shared("start", 0), count=7)]
        for i, name in enumerate(names, 1):
            frames.append(dict(shared("record", i), case=name,
                               ranks=([1], [2], [2, 0])[i - 1] if i <= 3 else None,
                               priority=None if i <= 3 else (1, 1, -1, 0)[i - 4]))
        frames.append(dict(shared("end", 8), count=7, completed=7))
        return frames

    def test_source_priority_report_is_complete_typed_and_context_bound(self):
        frames = self.priority_frames()
        self.assertEqual(len(_read_priority_report(_mock_ndjson(frames), "run", "context")), 7)
        mutants = [frames[:-1], frames + [frames[-1]], [frames[0], *frames[2:], frames[1]]]
        for index, field, value in [(1, "id", True), (1, "case", "foreign"), (2, "run", "foreign"),
                                     (2, "context", "foreign"), (1, "ranks", [True]),
                                     (1, "ranks", []), (4, "priority", True),
                                     (8, "completed", 0), (8, "completed", True),
                                     (0, "count", 0), (0, "kind", "end")]:
            bad = copy.deepcopy(frames); bad[index][field] = value; mutants.append(bad)
        for bad in mutants:
            with self.subTest(frames=bad), self.assertRaises(CheckingError):
                _read_priority_report(_mock_ndjson(bad), "run", "context")
        for bad in (b"\xff", b"{}", b"{", _mock_ndjson(frames) + b"\n",
                    _mock_ndjson(frames).replace(b'"id": 1', b'"id": 1, "id": 1', 1)):
            with self.subTest(raw=bad), self.assertRaises(CheckingError):
                _read_priority_report(bad, "run", "context")
        changed = copy.deepcopy(frames); changed[1]["ranks"] = [0]
        # A complete well-typed wrong value remains observable, not a checking refusal.
        actual = _read_priority_report(_mock_ndjson(changed), "run", "context")
        self.assertEqual(actual[0]["ranks"], [0])
        self.assertNotEqual(actual[0]["ranks"], frames[1]["ranks"])
        original = _read_priority_report(_mock_ndjson(frames), "run", "context")
        # A different private rank encoding with unchanged relative decisions is valid.
        changed[1]["ranks"], changed[2]["ranks"], changed[3]["ranks"] = [50], [100], [100, 0]
        encoded = _read_priority_report(_mock_ndjson(changed), "run", "context")
        self.assertEqual(_priority_differences(original, encoded), [])
        changed[5]["priority"] = 2
        wrong = _read_priority_report(_mock_ndjson(changed), "run", "context")
        self.assertTrue(_priority_differences(original, wrong))

    def test_source_priority_compile_errors_never_reach_semantic_receiver(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); source = root / "module"; (source / "apidoor").mkdir(parents=True)
            case = SimpleNamespace(tmp=root, model=None, context=_mock_context())
            ids = dict(ROW=1, LITERAL=2, FREE=3)
            failed = subprocess.CompletedProcess(["synthetic-go"], 1, b"", b"compile error")
            with patch(__name__ + "._priority_source_inputs", return_value=(ids, [])), \
                    patch(__name__ + ".subprocess.run", return_value=failed), \
                    patch(__name__ + "._read_priority_report") as receive, self.assertRaises(CheckingError):
                _observe_priority(case, source)
            receive.assert_not_called()


class SchemaPositionControls(unittest.TestCase):
    """Typed source-position neighbours, separate from the frozen route Model and inputs."""

    def setUp(self):
        from test_gen_door_bodies import SourceSchemaReader, SourceSchemaReaderControls, CheckingError
        self.Reader, self.Error = SourceSchemaReader, CheckingError
        self.fixture = SourceSchemaReaderControls("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_00_schema_map_array_and_escaped_pointer_neighbours(self):
        f = self.fixture
        f.schema({"$defs": {"a/b": {"type": "string"}, "~": {"type": "integer"},
                            "": {"type": "boolean"}, "01": {"type": "string"}},
                  "allOf": [{"type": "string", "minLength": 1}]})
        for pointer, good, bad in (("/$defs/a~1b", "x", 1), ("/$defs/~0", 1, "x"),
                                   ("/$defs/", True, 1), ("/$defs/01", "x", 1),
                                   ("/allOf/0", "x", "")):
            with self.subTest(pointer=pointer):
                reader = f.reader({"$ref": "../data/target.schema.json#" + pointer})
                validator = reader.validator_at(reader.source, "/components/schemas/Root")
                self.assertTrue(validator.is_valid(good))
                self.assertFalse(validator.is_valid(bad))

    def test_01_bad_array_indices_escapes_and_fragments_are_errors(self):
        f = self.fixture
        f.schema({"allOf": [{"type": "string"}]})
        for pointer in ("/allOf/01", "/allOf/+0", "/allOf/-", "/allOf/١", "/allOf/9", "/allOf/~2",
                        "/%ff", "/%zz", "anchor"):
            with self.subTest(pointer=pointer), self.assertRaises(self.Error):
                f.reader({"$ref": "../data/target.schema.json#" + pointer})

    def test_02_literal_ref_values_are_data_even_when_the_uri_is_unsafe(self):
        f = self.fixture
        literal = {"$ref": "https://not-a-resource.invalid/missing"}
        for field, value in (("default", literal), ("example", literal), ("examples", [literal]),
                             ("const", literal), ("enum", [literal])):
            with self.subTest(field=field):
                reader = f.reader({field: value})
                self.assertEqual(reader.edges, {})
                self.assertTrue(reader.validator_at(reader.source, "/components/schemas/Root").is_valid(literal))
        source = f.api(components={"examples": {"E": {"value": literal}}, "schemas": {"Root": True}},
                       paths={"/a": {"get": {"responses": {"200": {"description": "ok", "content": {
                           "application/json": {"schema": True, "example": literal, "examples": {
                               "E": {"value": literal}}}}}}}}})
        self.assertEqual(self.Reader(f.root, source).edges, {})

    def test_03_schema_of_a_property_named_ref_is_still_traversed(self):
        f = self.fixture
        f.schema({"$defs": {"S": {"type": "string"}}, "type": "object", "properties": {
            "$ref": {"$ref": "#/$defs/S"}}})
        reader = f.reader({"$ref": "../data/target.schema.json"})
        validator = reader.validator_at(reader.source, "/components/schemas/Root")
        self.assertTrue(validator.is_valid({"$ref": "x"}))
        self.assertFalse(validator.is_valid({"$ref": 1}))
        self.assertTrue(any(pointer == "/properties/$ref" for _, pointer, _, _ in reader.edges))

    def test_04_schema_ref_siblings_keep_their_own_constraints(self):
        f = self.fixture
        f.schema({"type": "string"})
        reader = f.reader({"$ref": "../data/target.schema.json", "minLength": 2})
        validator = reader.validator_at(reader.source, "/components/schemas/Root")
        self.assertTrue(validator.is_valid("ab"))
        self.assertFalse(validator.is_valid("a"))

    def test_05_schema_shaped_literal_data_is_not_a_schema_target(self):
        f = self.fixture
        f.schema({"default": {"type": "integer"}, "enum": [{"type": "integer"}]})
        for pointer in ("/default", "/enum/0"):
            with self.subTest(pointer=pointer), self.assertRaises(self.Error):
                f.reader({"$ref": "../data/target.schema.json#" + pointer})

    def test_06_json_cannot_replace_parameter_response_or_pathitem(self):
        f = self.fixture
        f.schema({"type": "string"})
        ref = {"$ref": "../data/target.schema.json"}
        # Each case is written and read separately: no later overwrite may vacuously replace an input.
        for position in ("parameter", "response", "path"):
            if position == "parameter":
                source = f.api(components={"parameters": {"P": ref}})
            elif position == "response":
                source = f.api(components={"responses": {"R": ref}})
            else:
                source = f.api(paths={"/a": ref})
            with self.subTest(position=position), self.assertRaises(self.Error):
                self.Reader(f.root, source)

    def test_07_openapi_object_kind_and_whole_document_are_preserved(self):
        f = self.fixture
        earlier = f.api("05-resource", components={"responses": {"R": {"description": "ok"}},
                                                   "schemas": {"S": {"type": "string"}}})
        reader = f.reader({"$ref": "../../05-resource/spec/05-resource.api.openapi.yaml#/components/schemas/S"})
        self.assertTrue(reader.validator_at(reader.source, "/components/schemas/Root").is_valid("x"))
        for ref in ("../../05-resource/spec/05-resource.api.openapi.yaml", "../../05-resource/spec/05-resource.api.openapi.yaml#",
                    "../../05-resource/spec/05-resource.api.openapi.yaml#/components/responses/R",
                    "08-domain.api.openapi.yaml#/components/schemas/Root"):
            with self.subTest(ref=ref), self.assertRaises(self.Error):
                f.reader({"$ref": ref})

    def test_08_local_parameter_reference_and_json_schema_parameter(self):
        f = self.fixture
        f.schema({"type": "string", "minLength": 2})
        source = f.api(components={"parameters": {"P": {"in": "query", "name": "q", "schema": {
            "$ref": "../data/target.schema.json"}}}}, paths={"/a": {"get": {
                "parameters": [{"$ref": "#/components/parameters/P"}], "responses": {}}}})
        reader = self.Reader(f.root, source)
        prm = reader.document(source)["paths"]["/a"]["get"]["parameters"][0]
        prm, base = reader.parameter(prm, source, ("OpA", "/a", "get"))
        self.assertEqual(reader.schema_type_node(prm["schema"], base)["type"], "string")
        validator = reader.parameter_validator("OpA", "query", "q", prm["schema"], base)
        self.assertTrue(validator.is_valid("ab"))
        self.assertFalse(validator.is_valid("a"))

    def test_09_parameter_aliases_keep_both_operation_declarations(self):
        f = self.fixture
        f.schema({"type": "string", "minLength": 2})
        prm = {"in": "query", "name": "q", "schema": {"$ref": "../data/target.schema.json"}}
        source = f.api(components={"parameters": {"Shared": prm}},
                       paths={route: {"get": {"parameters": [prm], "responses": {}}} for route in ("/a", "/b")})
        reader = self.Reader(f.root, source)
        for route in ("/a", "/b"):
            node = reader.document(source)["paths"][route]["get"]["parameters"][0]
            value, base = reader.parameter(node, source, ("Op" + route[1:], route, "get"))
            validator = reader.parameter_validator("Op" + route[1:], "query", "q", value["schema"], base)
            self.assertTrue(validator.is_valid("ab"))
            self.assertFalse(validator.is_valid("a"))
        positions = {ptr for (file, ptr, ref, _), _ in reader.edges.items() if file == source}
        self.assertIn("/paths/~1a/get/parameters/0/schema", positions)
        self.assertIn("/paths/~1b/get/parameters/0/schema", positions)

    def test_10_missing_parameter_context_cannot_guess_a_source(self):
        f = self.fixture
        reader = f.reader()
        with self.assertRaises(self.Error):
            reader.parameter({"name": "q", "in": "query"}, reader.source, ("OpX", "/missing", "get"))
        with self.assertRaises(self.Error):
            reader.parameter_validator("OpX", "query", "q", {"type": "string"}, reader.source)

    def test_11_extensions_are_opaque_until_a_typed_reference_enters_them(self):
        f = self.fixture
        source = f.api(schemas={"Root": {"$ref": "#/x-schema"}})
        import yamlsub
        doc = yamlsub.load(source.read_text(), source.name)
        doc["x-schema"] = {"type": "string", "minLength": 1}
        doc["x-ignored"] = {"$ref": "https://not-a-resource.invalid/ignored"}
        f.write(str(source.relative_to(f.root)), doc, yaml=True)
        reader = self.Reader(f.root, source)
        validator = reader.validator_at(source, "/components/schemas/Root")
        self.assertTrue(validator.is_valid("a"))
        self.assertFalse(validator.is_valid(""))
        self.assertFalse(any(ptr.startswith("/x-ignored") for _, ptr, _, _ in reader.edges))

    def test_12_equal_nonalias_values_do_not_share_late_permissions(self):
        f = self.fixture
        source, ref = f.late()
        import yamlsub
        doc = yamlsub.load(source.read_text(), source.name)
        doc["components"] = {"schemas": {"Bad": dict(ref)}}
        f.write(str(source.relative_to(f.root)), doc, yaml=True)
        with self.assertRaises(self.Error):
            self.Reader(f.root, source)

    def test_13_independent_schema_errors_are_not_false_verdicts(self):
        f = self.fixture
        for value in (None, 3, "integer", [True], {"type": 3}, {"minLength": -1}, {"$ref": False}):
            with self.subTest(value=value), self.assertRaises(self.Error):
                f.reader(value)


for _lesson, _slug in LESSONS.items():
    _name = "DoorLesson_" + _slug
    globals()[_name] = type(_name, (DoorLessonBase, unittest.TestCase), {"LESSON": _lesson, "SLUG": _slug})


DoorLesson_p06.test_catalogue_observations = _test_catalogue_observations


if __name__ == "__main__":
    unittest.main()
