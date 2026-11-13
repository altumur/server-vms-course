"""Judge lesson door bodies (part 3b, P/06): compare Go Validate with independent jsonschema. Require fresh output; verify combined bodies.go schemas against original OpenAPI with referencing for external P/05/P/08 refs. Judge candidates, mutants and random values must include valid and invalid examples for each combined schema. Check DecodeRequest/CheckResponse/EncodeResponse media, status, strict JSON and defaults. Synthetic schemas make otherwise-equivalent keywords observable; runtime mutants for unevaluatedProperties, oneOf, integer, byte-vs-character minLength and required must fail. Run test_gen_door_bodies.py with jsonschema, referencing and Go 1.22."""
import lesson as output_lesson
import copy
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
import hashlib
from urllib.parse import quote, unquote_to_bytes, urljoin, urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
LESSONS = {"05-resource": "p05", "06-console": "p06", "08-domain": "p08", "09-agent": "p09", "10-domain-console": "p10"}
GOENV = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off", GOTOOLCHAIN="local")
sys.path.insert(0, str(HERE))


def bundle_of(mod):
    s = (Path(mod) / "apidoor/bodies.go").read_text(encoding="utf-8")
    m = re.search(r"^const bundle = (\".*\")$", s, re.M)
    return json.loads(json.loads(m[1]))


def tables_of(mod):
    s = (Path(mod) / "apidoor/bodies.go").read_text(encoding="utf-8")
    req = dict(re.findall(r'^\t(Op\w+): \{("[^}]*)\},$', s[s.index("var requestSchemas"):s.index("var responseSchemas")], re.M))
    return req


class Gen:
    """Generate candidate valid values and corruptions from combined schemas; the oracle, not generator, decides validity."""

    def __init__(self, defs, rnd):
        self.defs, self.rnd = defs, rnd

    def node(self, s):
        seen = 0
        while isinstance(s, dict) and "$ref" in s and seen < 20:
            base = {k: v for k, v in s.items() if k != "$ref"}
            s = dict(self.defs[s["$ref"].split("/")[-1]], **base) if base else self.defs[s["$ref"].split("/")[-1]]
            seen += 1
        return s

    def strings(self, s):
        out = []
        for e in s.get("enum", []):
            if isinstance(e, str):
                out.append(e)
        if isinstance(s.get("const"), str):
            out.append(s["const"])
        lo, hi = s.get("minLength", 0), s.get("maxLength")
        base = ["c1", "testsub", "a", "srv-a", "0123456789abcdef", "abc", "x_y", "UPPER", "a b", "/", ".", "..", "é",
                "0", "1", "2026-11-05T00:00:00Z", "true"]
        for b in base:
            out.append(b)
        if lo:
            out += ["a" * lo, "a" * (lo - 1) if lo > 1 else ""]
        if hi is not None:
            out += ["a" * hi, "a" * (hi + 1)]
        if "pattern" in s:
            out += self.pattern_samples(s["pattern"])
        return out

    def pattern_samples(self, p):
        """Make rough pattern samples from character classes/repetitions using their first characters."""
        q = p.strip("^$")
        q = re.sub(r"^\(\?:(.*)\)$", r"\1", q)
        cand = []
        for rep in ("a", "0", "x", "ab", "a1", "0a"):
            t = re.sub(r"\[[^\]]*\]\{(\d+)(?:,\d*)?\}", lambda m: rep[0] * int(m[1]), q)
            t = re.sub(r"\[[^\]]*\][*+?]?", rep[0], t)
            t = re.sub(r"\\[ds]", "0" if rep[0] == "0" else "a", t)
            t = re.sub(r"[()?*+|^$\\{}\d,]", "", t) if len(t) > 40 else re.sub(r"[()?*+|^$\\]", "", t)
            cand.append(t)
        return [c for c in cand if len(c) < 80]

    def values(self, s, depth=0):
        s = self.node(s)
        if s is True:
            return [None, 1, "a"]
        if s is False:
            return [None]
        out = []
        if "const" in s:
            out.append(s["const"])
        out += list(s.get("enum", []))
        for k in ("anyOf", "oneOf", "allOf"):
            for sub in s.get(k, [])[:4]:
                out += self.values(sub, depth + 1)[:4]
        if "if" in s:
            out += self.values(s["if"], depth + 1)[:2]
            for k in ("then", "else"):
                if k in s:
                    out += self.values(s[k], depth + 1)[:2]
        if "allOf" in s and depth < 4:                 # Merge properties and required names across allOf object parts.
            merged = {"properties": {}, "required": []}
            for part in s["allOf"]:
                part = self.node(part)
                if isinstance(part, dict):
                    merged["properties"].update(part.get("properties", {}))
                    merged["required"] += part.get("required", [])
            merged["properties"].update(s.get("properties", {}))
            merged["required"] += s.get("required", [])
            if merged["properties"] or merged["required"]:
                for v in self.values(dict(merged, type="object"), depth + 1)[:6]:
                    out.append(v)
        t = s.get("type")
        types = t if isinstance(t, list) else [t] if t else []
        if not types and not out:
            types = ["object"] if "properties" in s or "required" in s else ["string"]
        for ty in types:
            if ty == "string":
                out += self.strings(s)
            elif ty in ("integer", "number"):
                for k in ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"):
                    if k in s:
                        out += [s[k], s[k] - 1, s[k] + 1]
                out += [0, 1, -1, 1.5, 10 ** 20, 1.0]
            elif ty == "boolean":
                out += [True, False]
            elif ty == "null":
                out.append(None)
            elif ty == "array":
                it = s.get("items", {})
                ivals = self.values(it, depth + 1)[:3] if depth < 4 else [None]
                out += [[], ivals[:1], ivals[:2], ivals[:1] * 2]
            elif ty == "object" or (ty is None and False):
                if depth >= 4:
                    out.append({})
                    continue
                props = s.get("properties", {})
                obj = {}
                for k in s.get("required", []):
                    vs = self.values(props.get(k, {}), depth + 1)
                    obj[k] = vs[0] if vs else "a"
                out.append(obj)
                full = dict(obj)
                for k, ps in list(props.items())[:6]:
                    vs = self.values(ps, depth + 1)
                    if vs:
                        full[k] = vs[0]
                out.append(full)
                if s.get("required"):
                    drop = dict(obj)
                    drop.pop(s["required"][0], None)
                    out.append(drop)
                out.append(dict(obj, zz_extra=1))
                for k, ps in list(props.items())[:8]:     # Generate separate samples for every nested property.
                    for sv in self.values(ps, depth + 1)[:6]:
                        out.append(dict(obj, **{k: sv}))
                for k in list(obj)[:2]:
                    out.append(dict(obj, **{k: 12345}))
        out += [None, "", 0, {}, []] if depth == 0 else []
        uniq, seen = [], set()
        for v in out:
            key = json.dumps(v, sort_keys=True, default=str)
            if key not in seen:
                seen.add(key)
                uniq.append(v)
        return uniq[:80]


DRIVER = r'''package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"unicode/utf8"

	"%s/apidoor"
)

func main() {
	sc := bufio.NewScanner(os.Stdin)
	sc.Buffer(make([]byte, 1<<22), 1<<22)
	enc := json.NewEncoder(os.Stdout)
	for sc.Scan() {
		if !utf8.Valid(sc.Bytes()) {
			fmt.Fprintln(os.Stderr, "invalid service UTF-8")
			os.Exit(2)
		}
		var c struct {
			ID    int
			Name  string
			Value json.RawMessage
		}
		if err := json.Unmarshal(sc.Bytes(), &c); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(2)
		}
		if c.ID < 1 {
			fmt.Fprintln(os.Stderr, "missing service identity")
			os.Exit(2)
		}
		v, err := apidoor.StrictJSON(c.Value)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(2)
		}
		res := apidoor.Validate(c.Name, v) == nil
		if err := enc.Encode(map[string]any{"id": c.ID, "result": res}); err != nil {
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


class CheckingError(RuntimeError):
    """A service failure is not a semantic disagreement or a killed mutant."""


def response_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise CheckingError(f"duplicate service JSON key: {key}")
        obj[key] = value
    return obj


def response_constant(word):
    raise CheckingError(f"non-JSON service constant: {word}")


def checked_values(cases, values):
    """Check the entire response before any call to the independent oracle."""
    if not cases or type(values) is not list or len(values) != len(cases):
        raise CheckingError("nonempty complete service report required")
    for value in values:
        if type(value) is not bool:
            raise CheckingError("body/parameter response must be a boolean")
        try:
            json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (UnicodeError, ValueError, TypeError) as exc:
            raise CheckingError("invalid service scalar") from exc
    return values


def read_report(cases, done):
    if done.returncode:
        raise CheckingError(f"Go service exited {done.returncode}: {done.stderr[-2000:]}")
    try:
        done.stdout.encode("utf-8")
        lines = done.stdout.split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        if not cases or len(lines) != len(cases) or any(not line for line in lines):
            raise CheckingError("nonempty complete service report required")
        frames = [json.loads(line, object_pairs_hook=response_object, parse_constant=response_constant)
                  for line in lines]
    except (UnicodeError, ValueError, TypeError, RecursionError, AttributeError) as exc:
        raise CheckingError("invalid UTF-8/JSON service report") from exc
    values = []
    for identity, frame in enumerate(frames, 1):
        if (type(frame) is not dict or set(frame) != {"id", "result"}
                or type(frame["id"]) is not int or frame["id"] != identity):
            raise CheckingError(f"service identity/order: expected {identity}")
        values.append(frame["result"])
    return checked_values(cases, values)


def go_process(mod, command, stdin=""):
    try:
        return subprocess.run(["go", "run", command], cwd=mod, input=stdin, capture_output=True,
                              text=True, encoding="utf-8", env=GOENV, timeout=120)
    except (OSError, UnicodeError, subprocess.SubprocessError) as exc:
        raise CheckingError(f"cannot execute Go service: {exc}") from exc


def disagree(cases, got, expected):
    values = checked_values(cases, got)
    return [(case, expected(case), values[i]) for i, case in enumerate(cases) if expected(case) != values[i]]


def run_go(mod, cases):
    if not cases:
        raise CheckingError("nonempty service input required")
    try:
        d = Path(mod) / "cmd/judgebodies"
        d.mkdir(parents=True, exist_ok=True)
        module = (Path(mod) / "go.mod").read_text(encoding="utf-8").split("\n")[0].split()[1]
        (d / "main.go").write_text(DRIVER % module, encoding="utf-8")
        stdin = "".join(json.dumps({"ID": i, "Name": n, "Value": v}, ensure_ascii=False, allow_nan=False) + "\n"
                        for i, (n, v) in enumerate(cases, 1))
    except (OSError, UnicodeError, ValueError, TypeError, IndexError) as exc:
        raise CheckingError("cannot prepare body service") from exc
    return read_report(cases, go_process(mod, "./cmd/judgebodies", stdin))


def oracle(defs):
    from jsonschema import Draft202012Validator
    root = {"$defs": defs}
    cache = {}

    def check(name, value):
        if name not in cache:
            cache[name] = Draft202012Validator(dict(root, **{"$ref": f"#/$defs/{name}"}))
        return cache[name].is_valid(value)
    return check


def cases_for(defs, rnd):
    g = Gen(defs, rnd)
    out = []
    for name in sorted(defs):
        for v in g.values({"$ref": f"#/$defs/{name}"}):
            out.append((name, v))
    return out


class SourceSchemaReader:
    """Independent, offline source oracle; coordinates are declarations, never names or cache permissions."""

    METHODS = ("get", "put", "post", "delete", "patch", "head", "options", "trace")
    SCHEMA_MAPS = ("properties", "patternProperties", "$defs", "dependentSchemas")
    SCHEMA_LISTS = ("allOf", "anyOf", "oneOf", "prefixItems")
    SCHEMA_SINGLE = ("items", "contains", "additionalProperties", "unevaluatedProperties",
                     "unevaluatedItems", "propertyNames", "not", "if", "then", "else", "contentSchema", "x-line-schema")
    ANNOTATIONS = {"title", "description", "$comment", "default", "examples", "$schema",
                   "readOnly", "writeOnly", "deprecated", "discriminator", "xml", "externalDocs"}

    def __init__(self, root, source):
        self.root = Path(root).resolve()
        self.platform = (self.root / "Platform").resolve()
        self.source = self.physical(source)
        self.docs, self.provenance = {}, {}
        self.kinds, self.children, self.locations = {}, {}, {}
        self.edges, self.visited, self.active = {}, set(), set()
        self.walk_stack = []
        self.parameters = {}
        self.document(self.source)
        self._walk(self.source, "", "schema" if self.is_json(self.source) else "document", (self.source,))
        # Discovering an external resource does not make all its unrelated
        # schemas descendants of the reference that happened to load it.
        while True:
            pending = [p for p in self.docs if (p, "", "schema" if self.is_json(p) else "document") not in self.visited]
            if not pending:
                break
            for path in pending:
                self._walk(path, "", "schema" if self.is_json(path) else "document", (path,))

    @staticmethod
    def escape(token):
        return str(token).replace("~", "~0").replace("/", "~1")

    @staticmethod
    def fragment(text):
        if re.search(r"%(?![0-9a-fA-F]{2})", text):
            raise CheckingError("malformed URI escape")
        try:
            text = unquote_to_bytes(text).decode("utf-8")
        except UnicodeError as exc:
            raise CheckingError("invalid URI UTF-8") from exc
        if text and not text.startswith("/"):
            raise CheckingError("unsupported fragment anchor")
        if re.search(r"~(?![01])", text):
            raise CheckingError("invalid JSON Pointer escape")
        return text

    def physical(self, path):
        try:
            path = Path(path).resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise CheckingError(f"missing/invalid physical source: {path}") from exc
        if not path.is_relative_to(self.platform) or not path.is_file():
            raise CheckingError(f"source outside Platform or not a regular file: {path}")
        self.owner(path)
        return path

    def owner(self, path):
        relative = Path(path).relative_to(self.platform)
        first = relative.parts[0]
        if first == "common":
            return None
        if not re.fullmatch(r"[0-9]{2}-[a-z][a-z0-9-]*", first):
            raise CheckingError(f"unowned physical resource: {path}")
        if str(path).endswith(".api.openapi.yaml") and Path(path).name != first + ".api.openapi.yaml":
            raise CheckingError(f"declared/physical OpenAPI owner mismatch: {path}")
        return int(first[:2])

    @staticmethod
    def is_json(path):
        return str(path).endswith(".schema.json")

    @staticmethod
    def _json_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise CheckingError(f"duplicate source JSON name: {key}")
            result[key] = value
        return result

    @staticmethod
    def _constant(value):
        raise CheckingError(f"nonfinite source JSON: {value}")

    @staticmethod
    def _json_tree(node, ancestors=()):
        if isinstance(node, (dict, list)):
            if id(node) in ancestors:
                raise CheckingError("cyclic source alias structure")
            ancestors += (id(node),)
            if isinstance(node, dict):
                if any(type(key) is not str for key in node):
                    raise CheckingError("source object keys must be strings")
                values = node.values()
            else:
                values = node
            for value in values:
                SourceSchemaReader._json_tree(value, ancestors)
        elif node is not None and type(node) not in (str, int, float, bool):
            raise CheckingError("non-JSON source value")

    def document(self, path):
        path = self.physical(path)
        try:
            raw = path.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            if path in self.docs:
                if self.provenance[path] != digest:
                    raise CheckingError(f"source changed after reading: {path}")
                return self.docs[path]
            text = raw.decode("utf-8")
            if self.is_json(path):
                doc = json.loads(text, object_pairs_hook=self._json_pairs, parse_constant=self._constant)
                if type(doc) not in (dict, bool):
                    raise CheckingError("standalone JSON resource is not a schema")
            elif str(path).endswith(".api.openapi.yaml"):
                import yamlsub
                doc = yamlsub.load(text, path.name)
                if type(doc) is not dict or not str(doc.get("openapi", "")).startswith("3.1."):
                    raise CheckingError("source is not OpenAPI 3.1")
            else:
                raise CheckingError(f"unsupported source file type: {path}")
            self._json_tree(doc)
            if self.is_json(path):
                self._check_schema(doc)
            json.dumps(doc, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.docs[path], self.provenance[path] = doc, digest
            self._index(path, "", "schema" if self.is_json(path) else "document", doc)
            return doc
        except CheckingError:
            raise
        except Exception as exc:
            raise CheckingError(f"cannot read source {path}: {exc}") from exc

    def _index(self, path, pointer, kind, node):
        key = (path, pointer)
        if key in self.kinds:
            if self.kinds[key] != kind:
                raise CheckingError(f"ambiguous source position: {path}#{pointer}")
            return
        if kind == "schema":
            if type(node) not in (dict, bool):
                raise CheckingError(f"not a Schema Object: {path}#{pointer}")
        elif type(node) is not dict:
            raise CheckingError(f"not an OpenAPI {kind}: {path}#{pointer}")
        self.kinds[key] = kind
        self.locations.setdefault((path, id(node), kind), []).append(pointer)
        self.children[(path, pointer, kind)] = []

        def child(token, child_kind, value):
            target = pointer + "/" + token
            self.children[(path, pointer, kind)].append((target, child_kind))
            self._index(path, target, child_kind, value)

        def mapping(field, child_kind):
            values = node.get(field, {})
            if type(values) is not dict:
                raise CheckingError(f"invalid {field} map at {path}#{pointer}")
            for name, value in values.items():
                child(self.escape(field) + "/" + self.escape(name), child_kind, value)

        def sequence(field, child_kind):
            values = node.get(field, [])
            if type(values) is not list:
                raise CheckingError(f"invalid {field} array at {path}#{pointer}")
            for i, value in enumerate(values):
                child(self.escape(field) + "/" + str(i), child_kind, value)

        if type(node) is bool:
            return
        if kind == "schema":
            for field in self.SCHEMA_MAPS:
                mapping(field, "schema")
            for field in self.SCHEMA_LISTS:
                sequence(field, "schema")
            for field in self.SCHEMA_SINGLE:
                if field in node:
                    child(field, "schema", node[field])
        elif kind == "document":
            dialect = node.get("jsonSchemaDialect")
            if dialect not in (None, "https://spec.openapis.org/oas/3.1/dialect/base",
                               "https://json-schema.org/draft/2020-12/schema"):
                raise CheckingError("unsupported OpenAPI schema dialect")
            mapping("paths", "path")
            components = node.get("components", {})
            if type(components) is not dict:
                raise CheckingError("invalid components")
            for field, child_kind in (("schemas", "schema"), ("parameters", "parameter"),
                    ("responses", "response"), ("headers", "header"), ("requestBodies", "request"),
                    ("examples", "example"), ("pathItems", "path"), ("callbacks", "callback"),
                    ("links", "link"), ("securitySchemes", "security")):
                values = components.get(field, {})
                if type(values) is not dict:
                    raise CheckingError(f"invalid components/{field}")
                for name, value in values.items():
                    child("components/" + field + "/" + self.escape(name), child_kind, value)
        elif kind == "path":
            sequence("parameters", "parameter")
            for method in self.METHODS:
                if method in node:
                    child(method, "operation", node[method])
        elif kind == "operation":
            sequence("parameters", "parameter")
            if "requestBody" in node:
                child("requestBody", "request", node["requestBody"])
            mapping("responses", "response")
            mapping("callbacks", "callback")
        elif kind in ("parameter", "header"):
            if "schema" in node:
                child("schema", "schema", node["schema"])
            mapping("content", "media")
            mapping("examples", "example")
        elif kind in ("response", "request"):
            mapping("content", "media")
            if kind == "response":
                mapping("headers", "header")
                mapping("links", "link")
        elif kind == "media":
            if "schema" in node:
                child("schema", "schema", node["schema"])
            mapping("examples", "example")
        elif kind == "callback" and "$ref" not in node:
            for name, value in node.items():
                if not name.startswith("x-"):
                    child(self.escape(name), "path", value)

    def value(self, path, pointer):
        node = self.document(path)
        for encoded in pointer.split("/")[1:] if pointer else []:
            token = encoded.replace("~1", "/").replace("~0", "~")
            try:
                if type(node) is list:
                    if not re.fullmatch(r"0|[1-9][0-9]*", token):
                        raise CheckingError("invalid array pointer index")
                    node = node[int(token)]
                elif type(node) is dict:
                    node = node[token]
                else:
                    raise CheckingError("pointer traverses a scalar")
            except (KeyError, IndexError) as exc:
                raise CheckingError(f"missing source pointer: {path}#{pointer}") from exc
        return node

    def at(self, path, pointer, kind):
        path = self.physical(path)
        self.document(path)
        node = self.value(path, pointer)
        actual_kind = self.kinds.get((path, pointer))
        if actual_kind is None and any(p.startswith("x-") for p in pointer.split("/")[1:]):
            # An explicitly entered extension gets its incoming type, not blanket recursive privilege.
            if not any(p in ("default", "const", "enum", "example", "examples", "value")
                       for p in pointer.split("/")[1:]):
                self._index(path, pointer, kind, node)
                actual_kind = kind
        if actual_kind != kind:
            raise CheckingError(f"wrong source kind {actual_kind}, expected {kind}: {path}#{pointer}")
        if not self.is_json(path) and pointer == "" and kind != "document":
            raise CheckingError("whole OpenAPI document is not a schema")
        return node

    def _late(self, source, pointer, target_owner):
        parts = pointer.split("/")
        if len(parts) < 3 or parts[1] != "paths" or self.is_json(source):
            return False
        door = parts[2].replace("~1", "/").replace("~0", "~")
        description = self.document(source).get("paths", {}).get(door, {}).get("description", "")
        chapter = re.search(r"\bchapter\s+([0-9]{1,2})\.([0-9]+)\b", description, re.I)
        if not chapter or int(chapter[1]) != self.owner(source):
            return False
        directory = source.parent.parent
        norm = directory / "spec" / f"{int(chapter[1]):02}.{chapter[2]}-{directory.name[3:]}.norms.md"
        norm = self.physical(norm)
        raw = norm.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if norm in self.provenance and self.provenance[norm] != digest:
            raise CheckingError("late declaration changed")
        self.provenance[norm] = digest
        header = raw.decode("utf-8").split("\n\n", 4)[:4]
        found = re.search(r"late layer:\s*lessons?\s+([0-9 ,and]+)\s+introduce", "\n".join(header), re.I)
        return bool(found and target_owner in {int(x) for x in re.findall(r"[0-9]+", found[1])})

    def _reference(self, source, pointer, ref, kind, chain):
        if type(ref) is not str:
            raise CheckingError("source $ref must be a string")
        try:
            parsed = urlsplit(ref)
        except ValueError as exc:
            raise CheckingError("invalid reference URI") from exc
        if (parsed.scheme or parsed.netloc or parsed.query or parsed.path.startswith(("/", "\\"))
                or "\\" in parsed.path):
            raise CheckingError("only offline relative references are supported")
        if re.search(r"%(?![0-9a-fA-F]{2})", parsed.path):
            raise CheckingError("invalid reference path escape")
        try:
            name = unquote_to_bytes(parsed.path).decode("utf-8")
        except UnicodeError as exc:
            raise CheckingError("invalid path UTF-8") from exc
        target = self.physical(source.parent / name) if name else source
        fragment = self.fragment(parsed.fragment)
        if name and target == source:
            raise CheckingError("own-file path reference requires a local fragment")
        if self.is_json(target) and kind != "schema":
            raise CheckingError("JSON Schema cannot replace an OpenAPI object")
        if not self.is_json(target) and not fragment:
            raise CheckingError("whole OpenAPI reference is unsupported")
        if target != source:
            origin_owner, target_owner = self.owner(source), self.owner(target)
            allowed = target_owner is None or (origin_owner is not None and
                (target_owner < origin_owner or (self.is_json(target) and target_owner == origin_owner)))
            if not allowed and not (origin_owner is not None and target_owner is not None
                                    and self._late(source, pointer, target_owner)):
                raise CheckingError(f"forbidden owner transition: {source}#{pointer} -> {target}")
        # The owner/declaration check above always runs, including for cached resources and aliases.
        self.document(target)
        self.at(target, fragment, kind)
        identity = (source, pointer, ref, kind)
        if identity in self.edges and self.edges[identity] != (target, fragment):
            raise CheckingError("physical reference target changed after reading")
        self.edges[identity] = (target, fragment)
        next_chain = chain + (target,) if target != source else chain
        return target, fragment, next_chain

    def _walk(self, path, pointer, kind, chain):
        node = self.at(path, pointer, kind)
        key = (path, pointer, kind)
        if key in self.active:
            cycle = self.walk_stack[self.walk_stack.index(key):]
            if len({entry[0] for entry in cycle}) > 1:
                raise CheckingError("cross-file reference cycle: " + " -> ".join(f"{p}#{ptr}" for p, ptr, _ in cycle))
            return
        if key in self.visited:
            return
        self.active.add(key)
        self.walk_stack.append(key)
        if kind == "schema":
            self._check_schema(node)
        if type(node) is dict and "$ref" in node:
            target, fragment, next_chain = self._reference(path, pointer, node["$ref"], kind, chain)
            self._walk(target, fragment, kind, next_chain)
        for child, child_kind in self.children[key]:
            self._walk(path, child, child_kind, chain)
        self.active.remove(key)
        self.walk_stack.pop()
        self.visited.add(key)

    @staticmethod
    def _check_schema(node):
        from jsonschema import Draft202012Validator
        if type(node) is dict:
            if any(k in node for k in ("$id", "$anchor", "$dynamicRef", "$recursiveRef", "$dynamicAnchor")):
                raise CheckingError("unsupported schema base/anchor/dynamic reference")
            if node.get("$schema") not in (None, "https://json-schema.org/draft/2020-12/schema"):
                raise CheckingError("unsupported JSON Schema dialect")
        try:
            Draft202012Validator.check_schema(node)
        except Exception as exc:
            raise CheckingError(f"invalid source Schema Object: {exc}") from exc

    @staticmethod
    def uri(path, pointer):
        return Path(path).as_uri() + "#" + quote(pointer, safe="/~$")

    def _source_graph_identity(self):
        """Keep registry reuse bound to complete bytes and original physical targets.

        A stat-only cache cannot prove Source immutability. Verify every document
        and late-declaration byte digest, and resolve each nonlocal path again.
        Permissions were checked per declaration by _walk/_reference; neither a
        cached registry nor equal schema values confer another declaration's rights.
        """
        for file, held in list(self.provenance.items()):
            if self.physical(file) != file:
                raise CheckingError("physical source changed after reading")
            if hashlib.sha256(file.read_bytes()).hexdigest() != held:
                raise CheckingError(f"source changed after reading: {file}")
        for (file, pointer, ref, kind), (target, fragment) in list(self.edges.items()):
            name = urlsplit(ref).path
            if name and self.physical(file.parent / unquote_to_bytes(name).decode("utf-8")) != target:
                raise CheckingError("physical reference target changed after reading")
        return (tuple(sorted((str(file), digest) for file, digest in self.provenance.items())),
                tuple(sorted((str(file), pointer, ref, kind, str(target), fragment)
                             for (file, pointer, ref, kind), (target, fragment) in self.edges.items())))

    def validator_at(self, path, pointer):
        from jsonschema import Draft202012Validator
        from referencing import Registry, Resource
        from referencing.jsonschema import DRAFT202012
        path = self.physical(path)
        self.document(path)
        self._walk(path, pointer, "schema", (path,))
        graph = self._source_graph_identity()
        if graph != getattr(self, "_registry_graph", None):
            def offline(uri):
                raise CheckingError(f"unregistered resource; network disabled: {uri}")

            # Complete original resources and URI aliases, with all declaration
            # guards rerun for a new graph. Do not replay all edges for every scalar.
            for (file, ptr, ref, kind), target in list(self.edges.items()):
                self._reference(file, ptr, ref, kind, (file,))
            resources = {file.as_uri(): file for file in self.docs}
            pending = list(resources.items())
            seen = set()
            while pending:
                base_uri, physical = pending.pop()
                if (base_uri, physical) in seen:
                    continue
                seen.add((base_uri, physical))
                for (file, ptr, ref, kind), (target, fragment) in self.edges.items():
                    if file != physical:
                        continue
                    alias_uri = urlsplit(urljoin(base_uri, ref))._replace(fragment="").geturl()
                    if alias_uri in resources and resources[alias_uri] != target:
                        raise CheckingError("ambiguous physical resource URI")
                    if alias_uri not in resources:
                        resources[alias_uri] = target
                        pending.append((alias_uri, target))
            registry = Registry(retrieve=offline)
            for uri, file in resources.items():
                doc = self.document(file)
                registry = registry.with_resource(uri, Resource(contents=doc, specification=DRAFT202012))
            self._source_registry = registry
            self._source_validators = {}
            self._registry_graph = self._source_graph_identity()
        key = (path, pointer)
        if key in self._source_validators:
            return self._source_validators[key]
        validator = Draft202012Validator({"$ref": self.uri(path, pointer)}, registry=self._source_registry)

        class CheckedValidator:
            def is_valid(inner, instance):
                try:
                    return validator.is_valid(instance)
                except Exception as exc:
                    raise CheckingError(f"source oracle failed at {path}#{pointer}: {exc}") from exc
        checked = CheckedValidator()
        self._source_validators[key] = checked
        return checked
    def _locations(self, node, base, kind):
        base = self.physical(base)
        result = self.locations.get((base, id(node), kind), [])
        if not result:
            raise CheckingError("source object has no typed declaration coordinate")
        return [(base, pointer) for pointer in result]

    def resolve_object(self, path, pointer, kind):
        seen = set()
        chain = (path,)
        while True:
            if (path, pointer) in seen:
                raise CheckingError("cyclic reference-only object")
            seen.add((path, pointer))
            node = self.at(path, pointer, kind)
            if type(node) is not dict or "$ref" not in node:
                return node, path, pointer
            path, pointer, chain = self._reference(path, pointer, node["$ref"], kind, chain)

    def parameter(self, node, base, binding, declaration=None):
        op, route, method = binding
        if declaration is None:
            prefix = "/paths/" + self.escape(route) + "/"
            locations = [(p, ptr) for p, ptr in self._locations(node, base, "parameter")
                         if ptr.startswith(prefix) and
                         (ptr[len(prefix):].startswith("parameters/") or
                          ptr[len(prefix):].startswith(method + "/parameters/"))]
        else:
            # The caller carries the original source slot, including a component/alias occurrence.
            p, ptr = declaration
            p = self.physical(p)
            if (p, ptr) not in self._locations(node, base, "parameter"):
                raise CheckingError("parameter is not the declared source occurrence")
            locations = [(p, ptr)]
        if not locations:
            raise CheckingError("parameter has no declaration for the operation")
        resolved = [self.resolve_object(p, ptr, "parameter") for p, ptr in locations]
        prm, file, pointer = resolved[0]
        if "name" not in prm or "in" not in prm:
            raise CheckingError("not a Parameter Object")
        if any(value != prm or p != file for value, p, _ in resolved):
            raise CheckingError("ambiguous operation parameter")
        if "schema" in prm:
            key = (op, prm["in"], prm["name"], id(prm["schema"]), file)
            self.parameters.setdefault(key, set()).update((p, ptr + "/schema") for _, p, ptr in resolved)
        return prm, file

    def schema_type_node(self, node, base):
        if type(node) is bool:
            return node
        values = []
        for file, pointer in self._locations(node, base, "schema"):
            seen = set()
            value = node
            siblings = {}
            chain = (file,)
            while type(value) is dict and "$ref" in value:
                if (file, pointer) in seen:
                    raise CheckingError("cyclic schema type alias")
                seen.add((file, pointer))
                siblings = dict({k: v for k, v in value.items() if k != "$ref"}, **siblings)
                file, pointer, chain = self._reference(file, pointer, value["$ref"], "schema", chain)
                value = self.at(file, pointer, "schema")
            values.append(dict(value, **siblings) if type(value) is dict else value)
        if any(value != values[0] for value in values):
            raise CheckingError("ambiguous aliased parameter type")
        return values[0]

    def parameter_validator(self, op, place, name, schema, base):
        coordinates = self.parameters.get((op, place, name, id(schema), self.physical(base)))
        if not coordinates:
            raise CheckingError("parameter schema has no exact source binding")
        return self.validators(coordinates)

    def validators(self, coordinates):
        validators = [self.validator_at(p, ptr) for p, ptr in sorted(coordinates)]
        if not validators:
            raise CheckingError("empty source oracle cohort")

        class Cohort:
            def is_valid(inner, value):
                got = [validator.is_valid(value) for validator in validators]
                if len(set(got)) != 1:
                    raise CheckingError("aliased source declarations disagree")
                return got[0]
        return Cohort()

    def canonical(self, file, pointer):
        seen = set()
        chain = (file,)
        while True:
            if (file, pointer) in seen:
                raise CheckingError("cyclic source alias")
            seen.add((file, pointer))
            node = self.at(file, pointer, "schema")
            if type(node) is not dict or "$ref" not in node or any(
                    key != "$ref" and key not in self.ANNOTATIONS and not key.startswith("x-") for key in node):
                return file, pointer
            file, pointer, chain = self._reference(file, pointer, node["$ref"], "schema", chain)

    def bundle_origins(self, defs, bindings=()):
        """Bind actual defs by independently known roots and paired source/actual schema edges."""
        if type(defs) is not dict or not defs:
            raise CheckingError("nonempty actual definitions required")
        origins, pairs = {}, set()

        def pair(actual, file, pointer):
            file, pointer = self.canonical(file, pointer)
            source = self.at(file, pointer, "schema")
            key = (id(actual), file, pointer)
            if key in pairs:
                return
            pairs.add(key)
            self._check_schema(actual)
            if type(actual) is dict and "$ref" in actual:
                ref = actual["$ref"]
                if type(ref) is not str or not ref.startswith("#/$defs/"):
                    raise CheckingError("actual bundle reference is not a local definition")
                token = self.fragment(ref[1:])[len("/$defs/"):]
                if "/" in token:
                    raise CheckingError("actual bundle reference is not a definition root")
                name = token.replace("~1", "/").replace("~0", "~")
                if type(source) is dict and "$ref" in source:
                    target, fragment, _ = self._reference(file, pointer, source["$ref"], "schema", (file,))
                    bind(name, target, fragment)
                else:
                    bind(name, file, pointer)
            if type(actual) is dict and type(source) is dict:
                for field in self.SCHEMA_MAPS:
                    for name, child in actual.get(field, {}).items():
                        if name not in source.get(field, {}):
                            raise CheckingError("actual nested schema has no source origin")
                        pair(child, file, pointer + "/" + field + "/" + self.escape(name))
                for field in self.SCHEMA_LISTS:
                    for i, child in enumerate(actual.get(field, [])):
                        if i >= len(source.get(field, [])):
                            raise CheckingError("actual schema composition has no source origin")
                        pair(child, file, pointer + "/" + field + "/" + str(i))
                for field in self.SCHEMA_SINGLE:
                    if field in actual:
                        if field not in source:
                            raise CheckingError("actual schema child has no source origin")
                        pair(actual[field], file, pointer + "/" + field)

        def bind(name, file, pointer):
            if name not in defs:
                raise CheckingError(f"missing actual definition: {name}")
            origin = self.canonical(file, pointer)
            old = origins.setdefault(name, set())
            if old and origin not in old:
                previous = next(iter(old))
                if previous[0] != origin[0] or self.at(*previous, "schema") is not self.at(*origin, "schema"):
                    raise CheckingError(f"ambiguous actual definition origin: {name}")
            if origin in old:
                return
            old.add(origin)
            pair(defs[name], *origin)

        for name in self.document(self.source).get("components", {}).get("schemas", {}):
            if name in defs:
                bind(name, self.source, "/components/schemas/" + self.escape(name))
        for name, file, pointer in bindings:
            bind(name, self.physical(file), pointer)
        unknown = set(defs) - set(origins)
        if unknown:
            raise CheckingError(f"actual definitions without source coverage: {sorted(unknown)}")
        return origins

    def compare(self, defs, cases, bindings=()):
        origins = self.bundle_origins(defs, bindings)
        if not cases or set(name for name, _ in cases) != set(defs):
            raise CheckingError("complete nonempty comparisons for every actual definition required")
        expected = {name: self.validators(coordinates) for name, coordinates in origins.items()}
        actual = oracle(defs)
        bad = []
        for name, value in cases:
            try:
                got = actual(name, value)
            except Exception as exc:
                raise CheckingError("actual bundle validator failed") from exc
            want = expected[name].is_valid(value)
            if want != got:
                bad.append((name, value, want, got))
        return bad

    @staticmethod
    def literal_table(text, name):
        """Read actual generated table literals; never infer expected schemas from them."""
        start = re.search(r"\bvar\s+" + re.escape(name) + r"\s*=\s*[^\n{]*\{", text)
        if not start:
            raise CheckingError(f"missing actual table: {name}")
        pos = start.end() - 1

        def token():
            nonlocal pos
            found = re.match(r'\s*("(?:\\.|[^"\\])*"|-?[0-9]+|[A-Za-z_][A-Za-z0-9_]*|[{}:,])', text[pos:])
            if not found:
                raise CheckingError("unsupported actual table literal")
            pos += found.end()
            return found[1]

        def mapping():
            if token() != "{":
                raise CheckingError("expected actual table map")
            out = {}
            key = token()
            while key != "}":
                value_key = json.loads(key) if key.startswith('"') else key
                if value_key in out or token() != ":":
                    raise CheckingError("duplicate/malformed actual table key")
                checkpoint = pos
                value = token()
                if value == "{":
                    pos_restore(checkpoint)
                    value = mapping()
                elif value.startswith('"'):
                    value = json.loads(value)
                else:
                    raise CheckingError("actual schema table value must be a string or map")
                out[value_key] = value
                following = token()
                if following == "}":
                    break
                if following != ",":
                    raise CheckingError("malformed actual table separator")
                key = token()
            return out

        def pos_restore(value):
            nonlocal pos
            pos = value
        return mapping()


    # Explicit private Source-owner input, independent of Source-root layout and
    # producer output. Verified copies may be selected on an individual reader.
    P06_OPERATION_IDENTITY_INPUT = Path(
        "/home/pilot/coord103-src/z21-p06-operation-identity-current-binding-a08-20261108/immutable-input")
    # Immutable operation coordinates keep their original API binding; current
    # payload bytes and the complete source slot roster are checked separately.
    P06_IDENTITY_BASE_API_SHA256 = "a64e0b92ab0fba1581309ef88f2b62fcaa3d29521f06e8d64126e64b3469f8d2"
    P06_CURRENT_API_SHA256 = "a189b5bb056547ac74990fb061d02f197a82a8f711983372eb138b9c20e8e323"
    P06_BINDING_SHA256 = "301877bb8402fc1f02ca5273161b2d943be6d4f139b4208c331fdc823b868751"
    P06_WITNESS_SHA256 = "af5920d7fb4e73055b33229f9a65c330bc021d4e780e9cd7719b46531d547f19"

    def _p06_identity_records(self, witness, binding):
        """Validate stable Source identities; historical schema digests are not current oracles."""
        heads = [("/folders", "OpHeadFolders"), ("/folders/{id}", "OpHeadFoldersById"),
                 ("/{sub}/operations/{id}", "OpHeadBySubOperationsById"),
                 ("/changes", "OpHeadChanges"), ("/{sub}/next_id", "OpHeadBySubNextId"),
                 ("/api/backup-part/{member}/{part}", "OpHeadApiBackupPartByMemberByPart")]
        appended = {"/paths/" + self.escape(route) + "/head": (symbol, ordinal)
                    for ordinal, (route, symbol) in enumerate(heads, 141)}
        if (type(witness) is not dict or type(witness.get("records")) is not list or
                len(witness["records"]) != 146 or type(binding) is not dict or
                type(binding.get("records")) is not list or len(binding["records"]) != 146 or
                binding.get("Source_pin") != "a08ef6ef101514c926e68d3fb00c8d121da60e01" or
                type(binding.get("current_API")) is not dict or
                binding["current_API"].get("path") != "Platform/06-console/spec/06-console.api.openapi.yaml" or
                binding["current_API"].get("sha256") != self.P06_IDENTITY_BASE_API_SHA256 or
                type(binding.get("immutable_original_witness")) is not dict or
                binding["immutable_original_witness"].get("sha256") != self.P06_WITNESS_SHA256):
            raise CheckingError("incomplete/wrong current Source identity binding")
        counts = {"original140": 140, "existing_HEAD": 6, "current_total": 146, "current_API_slots": 146}
        if (type(binding.get("counts")) is not dict or binding["counts"] != counts or
                any(type(value) is not int for value in binding["counts"].values())):
            raise CheckingError("mistyped/incomplete Source identity counts")
        original, old_heads, old_symbols, old_ordinals = {}, {}, set(), set()
        for row in witness["records"]:
            if type(row) is not dict or type(row.get("member_of_original140")) is not bool:
                raise CheckingError("mistyped historical Source identity record")
            pointer, symbol = row.get("after_pointer"), row.get("actual_adapter_Op")
            if type(pointer) is not str or type(symbol) is not str:
                raise CheckingError("missing historical Source identity")
            if row["member_of_original140"]:
                ordinal = row.get("logical_ordinal_original140")
                if (type(ordinal) is not int or not 1 <= ordinal <= 140 or pointer in original or
                        symbol in old_symbols or ordinal in old_ordinals):
                    raise CheckingError("duplicate/mistyped historical Source identity")
                original[pointer] = (symbol, ordinal)
                old_symbols.add(symbol)
                old_ordinals.add(ordinal)
            else:
                if (pointer in old_heads or pointer not in appended or
                        row.get("logical_ordinal_original140") is not None or symbol != appended[pointer][0]):
                    raise CheckingError("changed historical appended HEAD identity")
                old_heads[pointer] = symbol
        if len(original) != 140 or old_ordinals != set(range(1, 141)) or set(old_heads) != set(appended):
            raise CheckingError("incomplete historical Source identities")
        identities, symbols, ordinals = {}, set(), set()
        fields = {"member_of_original140", "after_pointer", "method", "actual_adapter_Op",
                  "logical_ordinal_original140", "logical_ordinal_current146"}
        for row in binding["records"]:
            if type(row) is not dict or set(row) != fields:
                raise CheckingError("incomplete current Source identity record")
            pointer, symbol, ordinal = row["after_pointer"], row["actual_adapter_Op"], row["logical_ordinal_current146"]
            if (type(pointer) is not str or type(symbol) is not str or not re.fullmatch(r"Op[A-Za-z0-9_]+", symbol) or
                    type(ordinal) is not int or not 1 <= ordinal <= 146 or
                    type(row["method"]) is not str or row["method"] not in {m.upper() for m in self.METHODS} or
                    not pointer.endswith("/" + row["method"].lower()) or
                    not pointer.startswith(("/paths/", "/components/pathItems/")) or
                    self.fragment(pointer) != pointer or type(row["member_of_original140"]) is not bool):
                raise CheckingError("mistyped current Source operation identity")
            if pointer in identities or symbol in symbols or ordinal in ordinals:
                raise CheckingError("duplicate current Source operation identity")
            if row["member_of_original140"]:
                if (type(row["logical_ordinal_original140"]) is not int or
                        row["logical_ordinal_original140"] != ordinal or original.get(pointer) != (symbol, ordinal)):
                    raise CheckingError("current binding changed an original140 Source identity")
            elif (row["logical_ordinal_original140"] is not None or appended.get(pointer) != (symbol, ordinal)):
                raise CheckingError("current binding changed an approved HEAD identity")
            identities[pointer] = (symbol, ordinal)
            symbols.add(symbol)
            ordinals.add(ordinal)
        if set(identities) != set(original) | set(appended) or ordinals != set(range(1, 147)):
            raise CheckingError("incomplete current146 Source identity set")
        return identities

    def _p06_operation_identities(self):
        packet = Path(self.P06_OPERATION_IDENTITY_INPUT)
        try:
            if not packet.is_absolute() or packet.is_symlink() or not packet.is_dir():
                raise CheckingError("Source identity input must be an explicit regular absolute directory")
            values = []
            for name, expected in (("operation-map.json", self.P06_WITNESS_SHA256),
                                   ("CURRENT-API-BINDING.json", self.P06_BINDING_SHA256)):
                file = packet / name
                if file.is_symlink() or not file.is_file():
                    raise CheckingError("missing/nonregular Source identity input: " + name)
                raw = file.read_bytes()
                if hashlib.sha256(raw).hexdigest() != expected:
                    raise CheckingError("Source identity input changed: " + name)
                values.append(json.loads(raw))
            if (self.source.relative_to(self.root).as_posix() != "Platform/06-console/spec/06-console.api.openapi.yaml" or
                    hashlib.sha256(self.source.read_bytes()).hexdigest() != self.P06_CURRENT_API_SHA256):
                raise CheckingError("current Source API identity changed")
        except (OSError, UnicodeError, ValueError, TypeError) as exc:
            raise CheckingError("Source operation identity input unavailable") from exc
        return self._p06_identity_records(*values)

    def operation_declarations(self):
        """Enumerate source slots, retaining coordinates independently of object/cache identity."""
        doc = self.document(self.source)
        slots = [(route, "/paths/" + self.escape(route), "") for route in doc.get("paths", {})]
        identities = None
        if self.owner(self.source) == 6:
            identities = self._p06_operation_identities()
            standard = {"UnitsCollection": "/{rows}", "UnitItem": "/{rows}/{id}",
                        "TableCollection": "/{table}", "TableItem": "/{table}/{name}",
                        "PassRoot": "/{pass}", "ConsoleFile": "/{sub}/{file}"}
            items = doc.get("components", {}).get("pathItems", {})
            if set(items) != set(standard):
                raise CheckingError("missing/extra standard source PathItem")
            slots += [(route, "/components/pathItems/" + name, name) for name, route in standard.items()]
        out, seen = [], set()
        for route, declaration, component in slots:
            item, file, pointer = self.resolve_object(self.source, declaration, "path")
            for method in self.METHODS:
                if method not in item:
                    continue
                operation_pointer = pointer + "/" + method
                source_pointer = declaration + "/" + method
                if (route, method) in seen:
                    raise CheckingError("duplicate logical source operation")
                seen.add((route, method))
                if identities is not None and source_pointer not in identities:
                    raise CheckingError("source operation has no immutable identity")
                parameters = []
                for owner, values in ((pointer, item.get("parameters", [])),
                                      (operation_pointer, item[method].get("parameters", []))):
                    for i, value in enumerate(values):
                        parameters.append((value, file, owner + "/parameters/" + str(i)))
                symbol, ordinal = (identities or {}).get(source_pointer, (None, None))
                out.append(dict(route=route, method=method, component=component, file=file,
                                item=item, operation=item[method], item_pointer=pointer,
                                pointer=operation_pointer, declaration=source_pointer,
                                parameters=parameters, symbol=symbol, ordinal=ordinal))
        if identities is not None and {r["declaration"] for r in out} != set(identities):
            raise CheckingError("uncovered source operation identity")
        return out

    @staticmethod
    def parameter_table(text):
        """Parse actual Go parameter records, independently of definition naming.

        Only the literal table is actual metadata. Required source slots, types,
        defaults and lexeme roles are derived separately from full OpenAPI.
        """
        matches = list(re.finditer(r"\bvar\s+paramSchemas\s*=\s*map\[Op\]\[\]paramSpec\s*\{", text))
        if len(matches) != 1:
            raise CheckingError("missing/ambiguous actual parameter schema table")
        pos = matches[0].end() - 1
        def token():
            nonlocal pos
            found = re.match(r'\s*("(?:\\.|[^"\\])*"|[A-Za-z_][A-Za-z0-9_]*|[{}:,&])', text[pos:])
            if not found:
                raise CheckingError("malformed actual parameter literal")
            pos += found.end()
            return found[1]
        def mapping():
            if token() != "{":
                raise CheckingError("actual parameter map expected")
            result = {}
            key = token()
            while key != "}":
                if key in result or token() != ":":
                    raise CheckingError("duplicate/malformed actual parameter field")
                result[key] = value()
                end = token()
                if end == "}":
                    break
                if end != ",":
                    raise CheckingError("malformed actual parameter separator")
                key = token()
            return result
        def sequence():
            if token() != "{":
                raise CheckingError("actual parameter list expected")
            result = []
            nonlocal pos
            checkpoint = pos
            if token() == "}":
                return result
            pos = checkpoint
            while True:
                result.append(mapping())
                end = token()
                if end == "}":
                    return result
                if end != ",":
                    raise CheckingError("malformed actual parameter list")
        def value():
            nonlocal pos
            checkpoint = pos
            item = token()
            if item.startswith('"'):
                return json.loads(item)
            if item in ("true", "false"):
                return item == "true"
            if item == "&" and token() == "queryLexeme":
                return mapping()
            if item == "{":
                pos = checkpoint
                return sequence()
            raise CheckingError("unsupported actual parameter value")
        return mapping()

    def response_declarations(self):
        """Read complete response slots from Source, before observing emitted tables."""
        responses = []
        for operation in self.operation_declarations():
            values = operation["operation"].get("responses")
            if type(values) is not dict or not values:
                raise CheckingError("nonempty Source response declarations required")
            for status in values:
                if type(status) is not str or not (re.fullmatch(r"[1-5][0-9]{2}", status) or status == "default"):
                    raise CheckingError("unsupported Source response status coordinate")
                response, file, pointer = self.resolve_object(operation["file"],
                    operation["pointer"] + "/responses/" + self.escape(status), "response")
                content = response.get("content", {})
                if (type(content) is not dict or
                        any(type(media) is not str or not media or type(value) is not dict
                            for media, value in content.items())):
                    raise CheckingError("mistyped Source response content declaration")
                responses.append(dict(operation=operation, status=status, file=file, pointer=pointer,
                                      content=content, bodyless=not content))
        return responses

    def output_operations(self, module, declarations=None):
        """Bind actual operation symbols to the complete typed Source method/path set."""
        try:
            routes = (Path(module) / "apidoor/routes.go").read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise CheckingError("cannot read actual operation identities") from exc
        ops = {}
        for raw_key, op in re.findall(r'^\s*("(?:\\.|[^"\\])*"):\s+(Op[A-Za-z0-9_]+),\s*$', routes, re.M):
            label = json.loads(raw_key)
            path, sep, method = label.rpartition(" ")
            if sep and method.lower() in self.METHODS and path.startswith("/"):
                if (path, method.lower()) in ops:
                    raise CheckingError("duplicate actual operation identity")
                ops[path, method.lower()] = op
        declarations = self.operation_declarations() if declarations is None else declarations
        if (set(ops) != {(r["route"], r["method"]) for r in declarations} or
                len(set(ops.values())) != len(ops)):
            raise CheckingError("missing/extra/aliased actual route operation")
        for record in declarations:
            if record["symbol"] is not None and ops[record["route"], record["method"]] != record["symbol"]:
                raise CheckingError("actual operation renamed its source identity")
        return ops

    def output_bindings(self, module):
        """Pair source operation coordinates with actual route/body table identities."""
        try:
            bodies = (Path(module) / "apidoor/bodies.go").read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise CheckingError("cannot read actual body binding metadata") from exc
        declarations = self.operation_declarations()
        ops = self.output_operations(module, declarations)
        request = self.literal_table(bodies, "requestSchemas")
        response = self.literal_table(bodies, "responseSchemas")
        expected = {}
        for record in declarations:
            route, method = record["route"], record["method"]
            op = ops[route, method]
            if record["symbol"] is not None and op != record["symbol"]:
                raise CheckingError("actual operation renamed its source identity")
            file, operation_pointer = record["file"], record["pointer"]
            operation = record["operation"]
            if "requestBody" in operation:
                value, base, ptr = self.resolve_object(file, operation_pointer + "/requestBody", "request")
                for media, body in value.get("content", {}).items():
                    if "schema" in body:
                        expected["request", op, media] = (base, ptr + "/content/" + self.escape(media) + "/schema")
            for status in operation.get("responses", {}):
                value, base, ptr = self.resolve_object(file, operation_pointer + "/responses/" + self.escape(status), "response")
                for media, body in value.get("content", {}).items():
                    if "schema" in body:
                        expected["response", op, str(status), media] = (base, ptr + "/content/" + self.escape(media) + "/schema")
        # Bind all query/header definition roots through their actual table,
        # never by guessing the producer's dotted-name convention.
        source_parameters = {}
        for record in declarations:
            op = ops[record["route"], record["method"]]
            merged = {}
            for node, file, pointer in record["parameters"]:
                prm, base, ptr = self.resolve_object(file, pointer, "parameter")
                if prm["in"] in ("query", "header"):
                    merged[prm["in"], prm["name"]] = (prm, base, ptr)
            for (place, name), (prm, base, ptr) in merged.items():
                key = (op, place, name)
                source_parameters[key] = (prm, base, ptr)
        if source_parameters or re.search(r"\bvar\s+paramSchemas\b", bodies):
            table = self.parameter_table(bodies)
            seen, role_mismatches = set(), []
            for op, values in table.items():
                if op not in ops.values() or type(values) is not list or not values:
                    raise CheckingError("extra/empty actual parameter operation")
                for value in values:
                    if (type(value) is not dict or
                            set(value) not in ({"name", "in", "required", "schema", "def"},
                                               {"name", "in", "required", "schema", "def", "lexeme"}) or
                            any(type(value[k]) is not str for k in ("name", "in", "schema", "def")) or
                            type(value["required"]) is not bool):
                        raise CheckingError("mistyped actual parameter record")
                    key = (op, value["in"], value["name"])
                    if key in seen or key not in source_parameters:
                        raise CheckingError("duplicate/extra actual parameter binding")
                    seen.add(key)
                    prm, base, ptr = source_parameters[key]
                    schema = prm.get("schema", {})
                    default = json.dumps(schema["default"], ensure_ascii=False) if "default" in schema else ""
                    if (value["required"] != bool(prm.get("required")) or value["def"] != default or
                            value.get("lexeme") != (dict(strip="", **prm["x-query-lexeme"])
                                                     if "x-query-lexeme" in prm and "strip" not in prm["x-query-lexeme"]
                                                     else prm.get("x-query-lexeme"))):
                        role_mismatches.append(key)
                    expected["parameter", *key] = (base, ptr + "/schema")
            if seen != set(source_parameters):
                raise CheckingError("missing actual parameter binding")
            if role_mismatches:
                raise AssertionError(f"complete actual parameter role/default mismatches source: {role_mismatches}")
        else:
            table = {}
        actual = {}
        for op, values in table.items():
            for value in values:
                actual["parameter", op, value["in"], value["name"]] = value["schema"]
        try:
            for op, values in request.items():
                for media, name in values.items():
                    actual["request", op, media] = name
            for op, statuses in response.items():
                for status, values in statuses.items():
                    for media, name in values.items():
                        actual["response", op, status, media] = name
        except AttributeError as exc:
            raise CheckingError("mistyped actual binding table") from exc
        if set(actual) != set(expected) or any(type(name) is not str for name in actual.values()):
            raise CheckingError("incomplete/extra actual body bindings")
        bindings = [(name, *expected[key]) for key, name in actual.items()]
        # Priority routes have a separate path-schema table. Its route/name
        # identities bind exact Source slots; emitted definition names are opaque.
        path_sources = {}
        for record in declarations:
            if "x-route-priority" not in record["item"]:
                continue
            merged, declared = {}, set()
            for node, file, pointer in record["parameters"]:
                prm, base, ptr = self.resolve_object(file, pointer, "parameter")
                if prm.get("in") == "path":
                    if type(prm.get("name")) is not str or not prm["name"] or "schema" not in prm:
                        raise CheckingError("incomplete source path parameter")
                    level = (file, pointer.rsplit("/parameters/", 1)[0], prm["name"])
                    if level in declared:
                        raise CheckingError("ambiguous source path parameter declaration")
                    declared.add(level)
                    merged[prm["name"]] = (base, ptr + "/schema")
            for name, coordinate in merged.items():
                path_sources.setdefault((record["route"], name), set()).add(coordinate)
        path_tables = re.findall(r"\bvar\s+pathSchemas\s*=", bodies)
        if path_sources or path_tables:
            if len(path_tables) != 1:
                raise CheckingError("missing/duplicate actual path-schema table")
            path_table = self.literal_table(bodies, "pathSchemas")
            path_actual = {}
            for route, values in path_table.items():
                if (type(route) is not str or type(values) is not dict or not values or
                        any(type(name) is not str or not name or type(value) is not str or not value
                            for name, value in values.items())):
                    raise CheckingError("mistyped/empty actual path-schema binding")
                for name, value in values.items():
                    path_actual[route, name] = value
            if set(path_actual) != set(path_sources):
                raise CheckingError("missing/extra actual path-schema binding")
            for key, name in path_actual.items():
                bindings.extend((name, *coordinate) for coordinate in sorted(path_sources[key]))
        return bindings


def source_response_probes(reader, module):
    """Expected response boundaries come solely from complete Source slots and validators."""
    declarations = reader.response_declarations()
    bodyless = [row for row in declarations if row["bodyless"]]
    if not declarations:
        raise CheckingError("empty Source response coverage")
    cases = []
    def add(row, role, value, expected, *, media="", encode=False, empty=False, code=None, unknown=False):
        operation = row["operation"]
        statuses = operation["operation"]["responses"]
        if code is None:
            code = int(row["status"]) if row["status"] != "default" else next(
                n for n in range(100, 600) if str(n) not in statuses)
        cases.append(dict(route=operation["route"], method=operation["method"], code=code, media=media,
                          value=value, expected=expected, encode=encode, empty=empty, unknown=unknown, role=role,
                          source=str(row["file"]) + "#" + row["pointer"]))
    for row in bodyless:
        add(row, "no-content-nil", None, True)
        add(row, "no-content-nonnil", {"unexpected": True}, False)
        add(row, "no-content-encode-nil", None, True, encode=True, empty=True)
        add(row, "no-content-encode-nonnil", {"unexpected": True}, False, encode=True)
    # One discriminating content/media neighbour, plus every actual body-bearing
    # HEAD and every declared media without schema. None is a bodyless shortcut.
    ordinary_media_done = False
    media_targets = 0
    media_neighbours = []
    for row in declarations:
        for media, obj in row["content"].items():
            special = row["operation"]["method"] == "head" or "schema" not in obj
            if ordinary_media_done and not special:
                continue
            if "schema" not in obj:
                candidates = [{"source": "é"}, None] if media == "application/json" or media.endswith("+json") else ["source-é\n"]
                validator = None
            else:
                pointer = row["pointer"] + "/content/" + reader.escape(media) + "/schema"
                validator = reader.validator_at(row["file"], pointer)
                def proposal_shape(file, pointer, active=()):
                    # Resolve only typed Source schema edges for candidate construction.
                    # This is not a schema oracle: every candidate is checked against
                    # the complete unmodified Source registry below.
                    key = (file, pointer)
                    if key in active:
                        return {}  # A finite proposal, never a recursive-schema verdict.
                    node = reader.at(file, pointer, "schema")
                    if type(node) is bool:
                        return {} if node else {"not": {}}
                    active = (*active, key)
                    shaped = copy.deepcopy(node)
                    shaped.pop("$defs", None)  # All reachable proposal refs are expanded explicitly.
                    for keyword in reader.SCHEMA_MAPS:
                        if keyword == "$defs" or keyword not in node:
                            continue
                        names = node[keyword]
                        if keyword == "properties" and "required" in node:
                            names = {k: v for k, v in names.items() if k in node["required"]}
                        shaped[keyword] = {k: proposal_shape(file, pointer + "/" + keyword + "/" + reader.escape(k), active)
                                           for k in names}
                    for keyword in reader.SCHEMA_LISTS:
                        if keyword in node:
                            shaped[keyword] = [proposal_shape(file, pointer + "/" + keyword + "/" + str(i), active)
                                               for i in range(len(node[keyword]))]
                    for keyword in reader.SCHEMA_SINGLE:
                        if keyword in node:
                            shaped[keyword] = proposal_shape(file, pointer + "/" + keyword, active)
                    if "$ref" in node:
                        target, fragment, _ = reader._reference(file, pointer, node["$ref"], "schema", (file,))
                        resolved = proposal_shape(target, fragment, active)
                        del shaped["$ref"]
                        shaped = {"allOf": [resolved, shaped]}
                    # Flatten nested proposal composition so the existing small
                    # value sampler sees inherited required fields and constants.
                    if "allOf" in shaped:
                        parts = []
                        for part in shaped["allOf"]:
                            if type(part) is dict and "allOf" in part:
                                parts.extend(part["allOf"])
                                sibling = {k: v for k, v in part.items() if k != "allOf"}
                                if sibling:
                                    parts.append(sibling)
                            else:
                                parts.append(part)
                        shaped["allOf"] = parts
                    return shaped
                from jsonschema import Draft202012Validator
                class ProposalValues(Gen):
                    def values(self, schema, depth=0):
                        values = super().values(schema, depth)
                        # Rank locally valid proposals before constructing their
                        # parents. This is not the original Source oracle below.
                        local = Draft202012Validator(schema)
                        return sorted(values, key=lambda value: not local.is_valid(value))
                try:
                    candidates = ProposalValues({}, random.Random(36)).values(proposal_shape(row["file"], pointer))
                except (KeyError, TypeError, ValueError, AttributeError, RecursionError):
                    candidates = []  # Candidate construction is not an expected verdict.
            valid = [value for value in candidates if validator is None or validator.is_valid(value)]
            if not valid:
                if special:
                    raise CheckingError(f"no Source-valid body-bearing HEAD/schema-less media neighbour: {row['file']}#{row['pointer']} {media}")
                continue
            value = valid[0]
            add(row, "declared-media", value, True, media=media)
            add(row, "declared-media-encode", value, True, media=media, encode=True)
            # Empty-media maps intentionally ignore a media label. Unknown-media
            # rejection is tested on a declared content/media response instead.
            unknown = "application/x-review103-undeclared"
            if unknown in row["content"]:
                raise CheckingError("unknown-media probe unexpectedly declared")
            add(row, "unknown-media", value, False, media=unknown)
            add(row, "unknown-media-encode", value, False, media=unknown, encode=True)
            ordinary_media_done = True
            media_targets += 1
            media_neighbours.append((row, media, value))
    if not ordinary_media_done:
        raise CheckingError("missing Source-valid declared/unknown-media coverage")
    neighbours = [(row, "", None) for row in bodyless] + media_neighbours
    first, media, value = neighbours[0]
    add(first, "unknown-operation", value, False, media=media, unknown=True)
    for row, media, value in neighbours:
        statuses = row["operation"]["operation"]["responses"]
        if "default" not in statuses:
            unknown = next(n for n in range(100, 600) if str(n) not in statuses)
            add(row, "unknown-status", value, False, media=media, code=unknown)
            break
    # Only now read actual operation names. Missing status-table rows cannot
    # remove expected cases or turn this test into a zero-case success.
    ops = reader.output_operations(module)
    for case in cases:
        case["op"] = None if case.pop("unknown") else ops[case["route"], case["method"]]
    return cases, dict(source_responses=len(declarations),bodyless=len(bodyless),media_targets=media_targets,
                       body_bearing_HEAD=sum(row["operation"]["method"] == "head" and bool(row["content"]) for row in declarations),
                       schema_less_media=sum("schema" not in obj for row in declarations for obj in row["content"].values()))


# Synthetic schemas make keywords observable: the lesson's open Unit makes unevaluatedProperties redundant
# because additionalProperties:true is declared. Pair synthetic schemas with discriminating values.
SYNTH = {
    "U1": {"allOf": [{"properties": {"a": {}}}], "unevaluatedProperties": False},
    "U2": {"anyOf": [{"properties": {"a": {}}, "required": ["a"]}, {"properties": {"b": {}}, "required": ["b"]}],
           "unevaluatedProperties": False},
    "U3": {"if": {"properties": {"k": {"const": 1}}, "required": ["k"]}, "then": {"properties": {"x": {}}},
           "else": {"properties": {"y": {}}}, "unevaluatedProperties": False},
    "U4": {"properties": {"a": {}}, "patternProperties": {"^p": {}}, "unevaluatedProperties": {"type": "integer"}},
    "U5": {"$ref": "#/$defs/U1", "properties": {"b": {}}, "unevaluatedProperties": False},
    "O1": {"oneOf": [{"type": "integer"}, {"minimum": 2}]},
    "D1": {"type": "object", "dependentRequired": {"a": ["b", "c"]}},
    "N1": {"not": {"anyOf": [{"enum": [".", ".."]}, {"pattern": "/"}]}, "type": "string", "minLength": 2},
    "I1": {"type": "integer", "maximum": 10, "exclusiveMinimum": 0},
    "S1": {"type": "string", "maxLength": 2, "pattern": "^[a-zé]+$"},
    "A1": {"type": "array", "items": {"type": "string"}, "uniqueItems": True, "minItems": 1, "maxItems": 2},
    "P1": {"type": "object", "propertyNames": {"pattern": "^[a-z]+$"}, "minProperties": 1, "maxProperties": 2},
}
SYNTH_VALUES = [{}, {"a": 1}, {"b": 1}, {"a": 1, "b": 2}, {"k": 1, "x": 1}, {"k": 1, "y": 1}, {"k": 2, "y": 1},
                {"k": 2, "x": 1}, {"p1": "s", "z": 1}, {"z": "s"}, {"z": 1.0}, {"a": 1, "c": 1}, 1, 2, 3, 1.0, 2.5,
                0, 10, 10.0, 11, ".", "..", "ab", "a/b", "a", "éé", "ééé", "aa", "AB", ["x"], ["x", "x"], ["x", "y"],
                [], ["x", "y", "z"], [1], {"ab": 1}, {"Ab": 1}, {"a": 1, "b": 1, "c": 1}, None, True, "1"]
SYNTH_CASES = [(n, v) for n in SYNTH for v in SYNTH_VALUES]


def synth_module(src, dst):
    shutil.copytree(src, dst)
    p = Path(dst) / "apidoor/bodies.go"
    text = p.read_text(encoding="utf-8")
    bundle = json.dumps({"$defs": SYNTH}, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    text = re.sub(r"^const bundle = \".*\"$", lambda m: "const bundle = " + json.dumps(bundle), text, count=1, flags=re.M)
    p.write_text(text, encoding="utf-8")
    return dst


class DoorBodiesBase:
    LESSON = SLUG = None

    @classmethod
    def setUpClass(cls):
        if not shutil.which("go"):
            raise unittest.SkipTest("go is not in PATH")
        try:
            import jsonschema  # noqa: F401
            import referencing  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("no jsonschema/referencing: /opt/check-env/lesson-spec/bin/python")
        cls.tmp = Path(tempfile.mkdtemp(prefix="door-bodies-"))
        out = cls.tmp / "fresh"
        done = subprocess.run([sys.executable, str(HERE / "gen_door_lesson.py"), "--lesson", cls.LESSON, str(out)],
                              capture_output=True, text=True)
        if done.returncode:
            raise CheckingError(done.stderr)
        cls.fresh = out / "go"
        cls.defs = bundle_of(cls.fresh)["$defs"]
        cls.cases = cases_for(cls.defs, random.Random(36))

    def setUp(self):
        # A is the original generated output. Existing drivers and mutants write
        # only B/C copies, and the original remains checked across every test.
        from test_gen_door_lesson import (_tree_receipt, _verify_tree, _copy_owned,
                                          CheckingError as SnapshotError)
        cls = type(self)
        try:
            if "_body_original_snapshot" not in cls.__dict__:
                cls._body_original_snapshot = _tree_receipt(cls.fresh)
            _verify_tree(cls.fresh, cls._body_original_snapshot)
            self.fresh = self.tmp / ("body-owned-" + os.urandom(16).hex())
            _copy_owned(cls.fresh, self.fresh)
        except SnapshotError as exc:
            raise CheckingError(f"body immutable output/copy: {exc}") from exc
        def unchanged():
            try:
                _verify_tree(cls.fresh, cls._body_original_snapshot)
            except SnapshotError as exc:
                raise CheckingError(f"body original output changed: {exc}") from exc
        self.addCleanup(unchanged)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_fresh(self):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        for name in ("bodies.go", "schema_rt.go", "routes.go", "routes_rt.go"):
            kept = output_lesson.output_root() / self.SLUG / "go/apidoor" / name
            self.assertEqual(kept.read_bytes(), (self.fresh / "apidoor" / name).read_bytes(), f"{kept} is stale")

    def test_bundle_equals_source(self):
        """Compare every actual definition with its complete, independently bound source resource."""
        spec = ROOT / "Platform" / self.LESSON / "spec" / f"{self.LESSON}.api.openapi.yaml"
        reader = SourceSchemaReader(ROOT, spec)
        bad = reader.compare(self.defs, self.cases, reader.output_bindings(self.fresh))
        self.assertEqual(bad[:3], [], f"{len(bad)} combined-schema verdicts disagree with source")
        self.assertGreater(len(self.cases), 2 * len(self.defs))

    def test_validate_against_oracle(self):
        check = oracle(self.defs)
        got = run_go(self.fresh, self.cases)
        self.assertEqual(len(got), len(self.cases))
        bad = disagree(self.cases, got, lambda c: check(*c))
        self.assertEqual(bad[:3], [], f"{len(bad)} of {len(self.cases)} disagree with jsonschema")
        valid = sum(1 for g in got if g is True)
        self.assertGreater(valid, len(got) // 10)
        self.assertGreater(len(got) - valid, len(got) // 10)

    def test_synthetic(self):
        """Use synthetic schemas where every checker keyword changes at least one verdict."""
        mod = synth_module(self.fresh, self.tmp / "synth")
        check = oracle(SYNTH)
        got = run_go(mod, SYNTH_CASES)
        bad = disagree(SYNTH_CASES, got, lambda c: check(*c))
        self.assertEqual(bad[:3], [], f"{len(bad)} of {len(SYNTH_CASES)} disagree")
        for name in SYNTH:
            verdicts = {check(n, v) for n, v in SYNTH_CASES if n == name}
            self.assertEqual(verdicts, {True, False}, f"{name}: the values do not split it")

    def test_params(self):
        """Compare CheckParams with an independent model of OpenAPI query/header coercion and jsonschema."""
        spec = ROOT / "Platform" / self.LESSON / "spec" / f"{self.LESSON}.api.openapi.yaml"
        reader = SourceSchemaReader(ROOT, spec)
        routes = (self.fresh / "apidoor/routes.go").read_text()
        cases = []
        for record in reader.operation_declarations():
            path, m = record["route"], record["method"]
            match = re.search(r'"' + re.escape(path) + " " + m.upper() + r'":\s+(Op\w+),', routes)
            if match is None:
                raise CheckingError("parameter operation absent from actual routes")
            op = match[1]
            if record["symbol"] is not None and op != record["symbol"]:
                raise CheckingError("parameter operation changed source identity")
            for prm, file, pointer in record["parameters"]:
                    prm, base = reader.parameter(prm, file, (op, path, m), (file, pointer))
                    if prm["in"] not in ("query", "header"):
                        continue
                    sch = prm.get("schema", {})
                    for raw in ("1", "0", "-3", "1.5", "1e3", "abc", "true", "", "local", "cluster", "newest", "t",
                                "bytes=0-9", "sha256-" + "0" * 64, "x" * 200, "1_000", "1__0", "1e400", "1e-400", ".5", "5.",
                                "007", "18446744073709551615", "18446744073709551616", "-0", "+1", "30", "30.1", "0.0"):
                        cases.append((op, prm["in"], prm["name"], raw, sch, Path(base).resolve(), bool(prm.get("required")),
                                      prm.get("x-query-lexeme")))
        if not cases:
            self.skipTest("no query/header parameters")

        def node(sch, base):
            return reader.schema_type_node(sch, base)

        def want(c):
            op, place, name, raw, sch, base, req, lex = c
            t = node(sch, base).get("type") if isinstance(node(sch, base), dict) else None
            v = raw
            if lex:                                       # Independent x-query-lexeme model from P/05 forms/README.
                if not re.fullmatch(lex["pattern"], raw):
                    return False
                text = raw.replace(lex.get("strip", "") or "\x00", "") if lex.get("strip") else raw
                if lex["parse"] == "number":
                    f = float(text)
                    if f in (float("inf"), float("-inf")):
                        return False
                    v = f
                elif lex["parse"] == "integer":
                    v = int(text)
                else:
                    n = int(text)
                    if not 0 <= n <= 2 ** 64 - 1:
                        return False
                    v = raw
            elif t in ("number", "integer") and re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?", raw):
                from decimal import Decimal              # Match Go big.Rat exactly:1e-400 is not an integer.
                v = Decimal(raw) if any(ch in raw for ch in ".eE") else int(raw)
                if isinstance(v, Decimal) and v == v.to_integral_value():
                    v = int(v)                           # A mathematically integral value such as1e3 is integer per Draft 2020-12.
            elif t == "boolean" and raw in ("true", "false"):
                v = raw == "true"
            ok = reader.parameter_validator(op, place, name, sch, base).is_valid(v)
            return ok
        prog = ["package main", "", "import (", '\t"encoding/json"', '\t"fmt"', '\t"os"',
                f'\t"{(self.fresh / "go.mod").read_text().split()[1]}/apidoor"', ")", "", "func main() {",
                "\tenc := json.NewEncoder(os.Stdout)"]
        for identity, (op, place, name, raw, *_) in enumerate(cases, 1):
            nm = name.lower() if place == "header" else name      # Header names are case-insensitive.
            prog.append(f'\t{{ _, _, v := apidoor.CheckParam(apidoor.{op}, {json.dumps(place)}, {json.dumps(nm)}, '
                        f'[]string{{{json.dumps(raw)}}}); if err := enc.Encode(map[string]any{{"id": {identity}, '
                        '"result": v == nil}); err != nil { fmt.Fprintln(os.Stderr, err); os.Exit(2) } }')
        prog.append("}")
        try:
            d = self.fresh / "cmd/judgeparams"
            d.mkdir(parents=True, exist_ok=True)
            (d / "main.go").write_text("\n".join(prog) + "\n", encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise CheckingError("cannot prepare parameter service") from exc
        got = read_report(cases, go_process(self.fresh, "./cmd/judgeparams"))
        bad = disagree(cases, got, want)
        self.assertEqual(bad[:3], [], f"{len(bad)} of {len(cases)} parameter verdicts disagree")

    def test_declared_response_body_boundaries(self):
        """Every Source no-content status requires nil body; content/media remain distinct."""
        spec = ROOT / "Platform" / self.LESSON / "spec" / f"{self.LESSON}.api.openapi.yaml"
        reader = SourceSchemaReader(ROOT, spec)
        cases, coverage = source_response_probes(reader, self.fresh)
        if not cases:
            raise CheckingError("empty declared response proof")
        module = (self.fresh / "go.mod").read_text().split()[1]
        program = ["package main", "import (", '"encoding/json"', '"fmt"', '"os"',
                   json.dumps(module + "/apidoor"), ")", "func main(){enc:=json.NewEncoder(os.Stdout)"]
        for identity, case in enumerate(cases, 1):
            op = "apidoor.Op(0)" if case["op"] is None else "apidoor." + case["op"]
            raw = json.dumps(json.dumps(case["value"], ensure_ascii=True, allow_nan=False))
            call = f'{op},{case["code"]},{json.dumps(case["media"])},value'
            program.append('{var value any; if err:=json.Unmarshal([]byte(' + raw + '),&value);err!=nil{fmt.Fprintln(os.Stderr,err);os.Exit(2)}')
            if case["encode"]:
                condition = "violation==nil && len(body)==0" if case["empty"] else "violation==nil"
                program.append(f'body,violation:=apidoor.EncodeResponse({call});_ = body; result:={condition}')
            else:
                program.append(f'result:=apidoor.CheckResponse({call})==nil')
            program.append(f'if err:=enc.Encode(map[string]any{{"id":{identity},"result":result}});err!=nil{{fmt.Fprintln(os.Stderr,err);os.Exit(2)}}' + '}')
        program.append('}')
        try:
            directory = self.fresh / "cmd/judge_response_boundaries"
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "main.go").write_text("\n".join(program) + "\n", encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise CheckingError("cannot prepare response-boundary service") from exc
        got = read_report(cases, go_process(self.fresh, "./cmd/judge_response_boundaries"))
        bad = disagree(cases, got, lambda case: case["expected"])
        self.assertEqual(bad[:3], [], f"{len(bad)} complete Source response boundary mismatches; {coverage}")

    def test_api(self):
        if self.LESSON != "06-console":
            self.skipTest("the API probe names operations of P/06")
        prog = r'''package main

import (
	"fmt"

	"%s/apidoor"
)

func main() {
	_, v1 := apidoor.DecodeRequest(apidoor.OpPutByRowsById, "application/json", []byte(`{"a":1,"a":2}`))
	_, v2 := apidoor.DecodeRequest(apidoor.OpPutByRowsById, "text/plain", []byte(`{}`))
	_, v3 := apidoor.DecodeRequest(apidoor.OpGetHealthz, "", nil)
	v4 := apidoor.CheckResponse(apidoor.OpGetHealthz, 299, "application/json", map[string]any{})
	b, v5 := apidoor.EncodeResponse(apidoor.OpGetRoot, 200, "text/html", "<p>")
	fmt.Println(v1 != nil, v2 != nil, v3 == nil, v4 != nil, v5 == nil, string(b))
}
'''
        module = (self.fresh / "go.mod").read_text().split("\n")[0].split()[1]
        d = self.fresh / "cmd/judgeapi"
        d.mkdir(parents=True, exist_ok=True)
        (d / "main.go").write_text(prog % module)
        done = subprocess.run(["go", "run", "./cmd/judgeapi"], cwd=self.fresh, capture_output=True, text=True, env=GOENV)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.strip(), "true true true true true <p>")

    def test_mutants(self):
        check = oracle(self.defs)
        rt = (self.fresh / "apidoor/schema_rt.go").read_text()
        muts = {
            "unevaluated": rt.replace('if up, ok := n["unevaluatedProperties"]; ok {', 'if up, ok := n["zz"]; ok {', 1),
            "oneOf-as-anyOf": rt.replace("if hits != 1 {", "if hits < 1 {", 1),
            "integer": rt.replace("r, ok := num(v)\n\t\treturn ok && r.IsInt()", "_, ok := num(v)\n\t\treturn ok", 1),
            "minLength-bytes": rt.replace("l := utf8.RuneCountInString(x)", "l := len(x)", 1).replace('\t"unicode/utf8"\n', "", 1),
            "required": rt.replace('fail("required " + r.(string))', '_ = r', 1),
        }
        scheck = oracle(SYNTH)
        for name, text in muts.items():
            with self.subTest(mutant=name):
                self.assertNotEqual(text, rt, f"{name}: the mutant does not apply")
                bad = []
                for kind, cases, chk in (("lesson", self.cases, check), ("synth", SYNTH_CASES, scheck)):
                    mod = self.tmp / f"mut-{name}-{kind}"
                    if kind == "synth":
                        synth_module(self.fresh, mod)
                    else:
                        shutil.copytree(self.fresh, mod)
                    (mod / "apidoor/schema_rt.go").write_text(text)
                    got = run_go(mod, cases)
                    bad += [(kind, mismatch) for mismatch in disagree(cases, got, lambda c: chk(*c))]
                self.assertTrue(bad, f"{name} survives")


class BodyServiceControls(unittest.TestCase):
    """Independent controls of the checking service, without running Go."""

    def setUp(self):
        self.cases = [("X", {"text": "é\u2028x"}), ("X", {})]
        self.value = True

    def report(self, frames):
        return subprocess.CompletedProcess(["go", "run"], 0,
                                           "".join(json.dumps(f) + "\n" for f in frames), "")

    def frames(self):
        return [{"id": i, "result": self.value} for i in range(1, len(self.cases) + 1)]

    def test_complete_equal_values_keep_distinct_input_identities(self):
        self.assertEqual(read_report(self.cases, self.report(self.frames())), [self.value, self.value])
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "go.mod").write_text("module service.control\n")
            with patch(__name__ + ".subprocess.run", return_value=self.report(self.frames())) as proc:
                self.assertEqual(run_go(td, self.cases), [self.value, self.value])
            sent = [json.loads(line) for line in proc.call_args.kwargs["input"].split("\n") if line]
            self.assertEqual([c["ID"] for c in sent], [1, 2])

    def test_reports_require_nonempty_complete_ordered_identity(self):
        good = self.frames()
        variants = [[], good[:1], good + [good[0]], [good[0], good[0]], good[::-1],
                    [{"id": True, "result": self.value}, good[1]],
                    [{"result": self.value}, good[1]],
                    [dict(good[0], extra=1), good[1]], [[], good[1]],
                    [{"id": 1, "result": "panic: control"}, good[1]]]
        for frames in variants:
            with self.subTest(frames=frames), self.assertRaises(CheckingError):
                read_report(self.cases, self.report(frames))
        for text in ('', '\n', '{bad}\n', '{"id":1,"id":1,"result":true}\n' + json.dumps(good[1]) + '\n',
                     '{"id":1,"result":NaN}\n' + json.dumps(good[1]) + '\n',
                     self.report(good).stdout + '\n', '\ud800'):
            with self.subTest(text=repr(text)), self.assertRaises(CheckingError):
                read_report(self.cases, subprocess.CompletedProcess([], 0, text, ''))

    def test_process_and_preparation_errors_are_checking_errors(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "go.mod").write_text("module service.control\n")
            for failure in (OSError("start"), UnicodeError("UTF-8"), subprocess.TimeoutExpired(["go"], 120)):
                with self.subTest(failure=failure), patch(__name__ + ".subprocess.run", side_effect=failure):
                    with self.assertRaises(CheckingError):
                        run_go(td, self.cases)
            for stderr in ("compile failed", "panic: control", "scanner failed", "encoder failed"):
                done = subprocess.CompletedProcess([], 1, self.report(self.frames()).stdout, stderr)
                with self.subTest(stderr=stderr), patch(__name__ + ".subprocess.run", return_value=done):
                    with self.assertRaises(CheckingError):
                        run_go(td, self.cases)
            with patch(__name__ + ".subprocess.run") as proc:
                with self.assertRaises(CheckingError):
                    run_go(td, [])
                proc.assert_not_called()
            (Path(td) / "go.mod").unlink()
            with self.assertRaises(CheckingError):
                run_go(td, self.cases)

    def test_complete_report_is_checked_before_the_oracle(self):
        expected = Mock(return_value=self.value)
        for got in ([], [False], [False, "bad shape"]):
            with self.subTest(got=got), self.assertRaises(CheckingError):
                disagree(self.cases, got, expected)
        expected.assert_not_called()
        self.assertEqual(disagree(self.cases, [self.value, self.value], lambda c: self.value), [])
        bad = disagree(self.cases, [False, self.value], lambda c: self.value)
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0][0], self.cases[0])

    def mutant_case(self, directory):
        fresh = Path(directory) / "fresh"
        (fresh / "apidoor").mkdir(parents=True)
        (fresh / "apidoor/schema_rt.go").write_bytes((HERE / "doorrt2/go/schema.go").read_bytes())
        (fresh / "apidoor/bodies.go").write_text("const bundle = " + json.dumps(json.dumps({"$defs": {"X": True}})) + "\n")
        obj = DoorBodies_p05("test_mutants")
        obj.defs = {"X": True}
        obj.cases = self.cases
        obj.fresh = fresh
        obj.tmp = Path(directory)
        return obj

    def test_mutant_loop_does_not_absorb_checking_errors(self):
        with tempfile.TemporaryDirectory() as td:
            obj = self.mutant_case(td)
            with patch(__name__ + ".run_go", side_effect=CheckingError("compile control")):
                with self.assertRaises(CheckingError):
                    obj.test_mutants()

    def test_a_complete_correct_mutant_report_remains_a_survivor(self):
        with tempfile.TemporaryDirectory() as td:
            obj = self.mutant_case(td)
            with patch(__name__ + ".run_go", side_effect=lambda mod, cases: [oracle(bundle_of(mod)["$defs"])(*c) for c in cases]):
                with self.assertRaisesRegex(AssertionError, "survives"):
                    obj.test_mutants()


    def test_generated_original_is_immutable_and_each_body_service_gets_a_copy(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); original = root / "original"; original.mkdir()
            (original / "payload").write_bytes(b"original")
            fixture = type("BodySnapshotFixture", (DoorBodiesBase, unittest.TestCase),
                           {"fresh": original, "tmp": root, "runTest": lambda self: None})
            first = fixture(); first.setUp()
            (first.fresh / "payload").write_bytes(b"owned service instrumentation")
            self.assertEqual((original / "payload").read_bytes(), b"original")
            self.assertTrue(first.doCleanups())
            second = fixture(); second.setUp()
            self.assertNotEqual(first.fresh, second.fresh)
            self.assertEqual((second.fresh / "payload").read_bytes(), b"original")
            self.assertTrue(second.doCleanups())
            (original / "payload").write_bytes(b"tamper")
            with self.assertRaises(CheckingError):
                fixture().setUp()


# Accepted FORMAT context, retained as a historical reader control, never current
# P08 coverage. Source-owner receipt 1b177530 pins the three primary resources;
# their full API also reads the same-pin gate-and-pass contract below.
HISTORICAL_FOUR_SOURCE_PIN = "4a4687e18a408b23d8e41cd548723c3f04ad38ad"
HISTORICAL_FOUR_SOURCE_FILES = (
    ("Platform/08-domain/spec/08-domain.api.openapi.yaml", "100644",
     "849c925eb4b2e9ed1ee499d9cd758aa26136cb99",
     "fc4d7da24ef38b8740f43717085aaeeeae3d79142bf259ca4cc369271db22245", 176718),
    ("Platform/common/data/common.schema.json", "100644",
     "4686f8f63039eed57bc5432e5716b04aee6acc97",
     "2dc6559d1bde3ec161243ad113ef447d0e709532c57ac75ad2447c3aa2c681af", 28392),
    ("Platform/08-domain/data/backup-parts.schema.json", "100644",
     "17568f529533e2c9afe1e1c46d0f4cf6f91f80b6",
     "25f842aa561591dc5858e81b15598743b423f1902f69238fc939f4ed8cd9a07f", 532),
    ("Platform/common/contracts/gate-and-pass.api.openapi.yaml", "100644",
     "1b2a582ab87d8bb397e6c6021d7e5e443a4ddc9a",
     "fc7a681e70ba1401e21ce88121836dbd4905306dab33db53d81e353368cc6c38", 2260),
)


def historical_four_source_git(*args):
    """Read only declared historical Git objects, checking the worktree first."""
    wrapper = ('cd "$1" || exit 1; '
               '[ "$(git rev-parse --show-toplevel)" = "$1" ] || exit 1; '
               'shift; git "$@"')
    try:
        result = subprocess.run(["/bin/bash", "-c", wrapper, "source-context-git", str(ROOT), *args],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        if (result.returncode != 0 or type(result.stdout) is not bytes
                or type(result.stderr) is not bytes or result.stderr):
            raise CheckingError("historical Source Git read did not complete normally")
        return result.stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise CheckingError(f"historical Source Git read failed: {exc}") from exc


def historical_four_source_projection(destination, git_read=None):
    """Authenticate every closed resource before writing an owned readonly projection."""
    destination = Path(destination)
    if destination.is_symlink() or not destination.is_dir() or any(destination.iterdir()):
        raise CheckingError("historical Source projection requires a fresh empty real directory")
    read = historical_four_source_git if git_read is None else git_read
    pin = HISTORICAL_FOUR_SOURCE_PIN
    if read("rev-parse", "--verify", pin + "^{commit}") != (pin + "\n").encode("ascii"):
        raise CheckingError("missing or wrong historical Source commit identity")
    names = [entry[0] for entry in HISTORICAL_FOUR_SOURCE_FILES]
    tree = read("ls-tree", "-z", "--full-tree", pin, "--", *names)
    expected = [f"{mode} blob {blob}\t{name}".encode("utf-8")
                for name, mode, blob, digest, size in HISTORICAL_FOUR_SOURCE_FILES]
    if (type(tree) is not bytes or not tree.endswith(b"\0")
            or sorted(tree.split(b"\0")[:-1]) != sorted(expected)):
        raise CheckingError("historical Source mode/type/blob/path roster differs")
    payloads = []
    for name, mode, blob, digest, size in HISTORICAL_FOUR_SOURCE_FILES:
        raw = read("cat-file", "blob", blob)
        if type(raw) is not bytes or len(raw) != size or hashlib.sha256(raw).hexdigest() != digest:
            raise CheckingError(f"historical Source payload identity differs: {name}")
        payloads.append((name, raw))
    try:
        for name, raw in payloads:
            path = destination / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(raw)
            path.chmod(0o444)  # Git's declared non-executable mode was checked above.
    except OSError as exc:
        raise CheckingError(f"cannot materialize historical Source projection: {exc}") from exc
    return {"context": "historical-accepted-FORMAT", "source_pin": pin,
            "current_source_coverage": False,
            "files": {name: hashlib.sha256(raw).hexdigest() for name, raw in payloads}}


class HistoricalFourSourceContextControls(unittest.TestCase):
    """Checking-service controls; injected Git replies are mocks, not Source observations."""

    @classmethod
    def setUpClass(cls):
        pin = HISTORICAL_FOUR_SOURCE_PIN
        cls.replies = {
            ("rev-parse", "--verify", pin + "^{commit}"): (pin + "\n").encode("ascii"),
            ("ls-tree", "-z", "--full-tree", pin, "--",
             *(x[0] for x in HISTORICAL_FOUR_SOURCE_FILES)): historical_four_source_git(
                 "ls-tree", "-z", "--full-tree", pin, "--",
                 *(x[0] for x in HISTORICAL_FOUR_SOURCE_FILES)),
        }
        for name, mode, blob, digest, size in HISTORICAL_FOUR_SOURCE_FILES:
            cls.replies[("cat-file", "blob", blob)] = historical_four_source_git("cat-file", "blob", blob)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="historical-source-identity-control-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def rejected(self, replies):
        with self.assertRaises(CheckingError):
            historical_four_source_projection(self.root, lambda *args: replies[args])
        self.assertEqual(list(self.root.iterdir()), [], "failed authentication wrote a partial projection")

    def test_01_missing_wrong_or_padded_pin_is_not_a_fallback(self):
        key = next(key for key in self.replies if key[0] == "rev-parse")
        for value in (b"", b"0" * 40 + b"\n", b" " + self.replies[key], self.replies[key] + b"\n"):
            with self.subTest(value=value):
                self.rejected(self.replies | {key: value})

    def test_02_missing_extra_duplicate_mode_type_or_blob_roster_is_rejected(self):
        key = next(key for key in self.replies if key[0] == "ls-tree")
        rows = self.replies[key].split(b"\0")[:-1]
        for value in (b"", b"\0".join(rows[:-1]) + b"\0",
                      self.replies[key] + rows[0] + b"\0",
                      self.replies[key] + b"100644 blob " + b"0" * 40 + b"\textra\0",
                      self.replies[key].replace(b"100644", b"100755", 1),
                      self.replies[key].replace(b" blob ", b" tree ", 1),
                      self.replies[key].replace(rows[0].split(b"\t")[0][-40:], b"0" * 40, 1)):
            with self.subTest(value=value[:80]):
                self.rejected(self.replies | {key: value})

    def test_03_each_carrier_payload_is_checked_before_any_write(self):
        for key, raw in self.replies.items():
            if key[0] != "cat-file":
                continue
            for value in (b"", raw + b"\n", bytes([raw[0] ^ 1]) + raw[1:], raw.decode("utf-8")):
                with self.subTest(blob=key[-1], kind=type(value).__name__, size=len(value)):
                    self.rejected(self.replies | {key: value})

    def test_04_git_process_and_transport_errors_are_checking_errors(self):
        outcomes = [OSError("unavailable"), subprocess.TimeoutExpired("git", 30),
                    subprocess.CompletedProcess([], 1, b"", b"fatal"),
                    subprocess.CompletedProcess([], -9, b"", b""),
                    subprocess.CompletedProcess([], 0, "not bytes", b""),
                    subprocess.CompletedProcess([], 0, b"payload", b"unexpected diagnostic")]
        for value in outcomes:
            mock = Mock(side_effect=value) if isinstance(value, Exception) else Mock(return_value=value)
            with self.subTest(outcome=repr(value)), patch.object(subprocess, "run", mock), \
                    self.assertRaises(CheckingError):
                historical_four_source_git("rev-parse", "--verify", HISTORICAL_FOUR_SOURCE_PIN + "^{commit}")

    def test_05_existing_or_symlink_destination_is_not_overwritten(self):
        marker = self.root / "preserve"
        marker.write_bytes(b"owned-before")
        read = Mock()
        with self.assertRaises(CheckingError):
            historical_four_source_projection(self.root, read)
        self.assertEqual(marker.read_bytes(), b"owned-before")
        link = self.root / "alias"
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(CheckingError):
            historical_four_source_projection(link, read)
        read.assert_not_called()


class SourceSchemaReaderControls(unittest.TestCase):
    """Python-only source/registry controls; generated output and Go are not invoked."""

    BASELINE_RECEIPTS = []

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="source-reader-control-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, relative, value, yaml=False):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if yaml:
            from io import StringIO
            from ruamel.yaml import YAML
            out = StringIO()
            emitter = YAML()
            emitter.width = 4096
            emitter.dump(value, out)
            path.write_text(out.getvalue(), encoding="utf-8")
        else:
            path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def api(self, owner="08-domain", schemas=None, paths=None, components=None):
        doc = {"openapi": "3.1.0", "info": {"title": "owned control", "version": "1"},
               "components": components or {"schemas": schemas if schemas is not None else
                                              {"Root": {"type": "integer", "minimum": 0}}}, "paths": paths or {}}
        directory = "common/contracts" if owner == "common" else owner + "/spec"
        name = "shared" if owner == "common" else owner
        return self.write(f"Platform/{directory}/{name}.api.openapi.yaml", doc, yaml=True)

    def schema(self, value, owner="08-domain", name="target"):
        if type(value) is dict:
            value = dict({"$schema": "https://json-schema.org/draft/2020-12/schema"}, **value)
        return self.write(f"Platform/{owner}/data/{name}.schema.json", value)

    def reader(self, schema=...):
        source = self.api(schemas={"Root": schema} if schema is not ... else None)
        return SourceSchemaReader(self.root, source)

    def late(self, target="08-domain", components=False, description="Chapter 6.7 N1.13"):
        self.schema({"type": "string", "minLength": 1}, owner=target)
        ref = {"$ref": f"../../{target}/data/target.schema.json"}
        path = {"description": description, "get": {"responses": {"200": {
            "description": "ok", "content": {"application/json": {"schema": ref}}}}}}
        source = self.api(owner="06-console", paths={"/api/backup": path},
                          schemas={"Also": ref} if components else {})
        norm = self.root / "Platform/06-console/spec/06.7-console.norms.md"
        norm.write_text("# P/06.7\n\n**A chapter of the late layer: lessons 8 and 10 introduce it**\n", encoding="utf-8")
        return source, ref

    def test_00_actual_four_positions_without_document_or_cache_injection(self):
        """Read accepted FORMAT4a4687 files and their contract; not current P08 coverage."""
        context = historical_four_source_projection(self.root)
        source = self.root / "Platform/08-domain/spec/08-domain.api.openapi.yaml"
        reader = SourceSchemaReader(self.root, source)
        edges = {(ptr, ref): target for (file, ptr, ref, kind), target in reader.edges.items()
                 if file == source and kind == "schema" and ".schema.json" in ref}
        prefixes = {"/components/schemas/HolderTopologyBody/properties/doc",
                    "/components/schemas/HolderTopologyBody/properties/via/propertyNames",
                    "/components/schemas/HolderTopologyBody/properties/via/additionalProperties",
                    "/components/schemas/HolderBackupPartBody"}
        self.assertEqual({p for p, _ in edges}, prefixes)
        self.assertEqual(len(edges), 4)
        common = self.root / "Platform/common/data/common.schema.json"
        backup = self.root / "Platform/08-domain/data/backup-parts.schema.json"
        self.assertEqual(edges, {
            ("/components/schemas/HolderTopologyBody/properties/doc",
             "../../common/data/common.schema.json#/$defs/common.domain_topology_doc"):
                (common, "/$defs/common.domain_topology_doc"),
            ("/components/schemas/HolderTopologyBody/properties/via/propertyNames",
             "../../common/data/common.schema.json#/$defs/common.domain_member"):
                (common, "/$defs/common.domain_member"),
            ("/components/schemas/HolderTopologyBody/properties/via/additionalProperties",
             "../../common/data/common.schema.json#/$defs/common.domain_member"):
                (common, "/$defs/common.domain_member"),
            ("/components/schemas/HolderBackupPartBody", "../data/backup-parts.schema.json"):
                (backup, ""),
        })
        self.assertEqual(set(reader.provenance), {self.root / x[0] for x in HISTORICAL_FOUR_SOURCE_FILES})
        for name, mode, blob, digest, size in HISTORICAL_FOUR_SOURCE_FILES:
            path = self.root / name
            self.assertFalse(path.is_symlink())
            self.assertEqual(path.stat().st_mode & 0o222, 0)
            self.assertEqual(reader.provenance[path], digest)
        for file in (common, backup):
            self.assertEqual(reader.document(file), json.loads(file.read_bytes()))
            self.assertEqual(reader.provenance[file], hashlib.sha256(file.read_bytes()).hexdigest())
        full = reader.validator_at(source, "/components/schemas/HolderTopologyBody")
        self.assertTrue(full.is_valid({"doc": {"rev": 0, "star": []}, "via": {"m1": "m2"}}))
        self.assertFalse(full.is_valid({"doc": {"rev": 0, "star": []}, "via": {"": "m2"}}))
        self.assertFalse(full.is_valid({"doc": {"rev": 0, "star": []}, "via": {"m1": ""}}))
        part = reader.validator_at(source, "/components/schemas/HolderBackupPartBody")
        good = {"part": "0000", "rev": 1, "state": {}, "objects": {}}
        self.assertTrue(part.is_valid(good))
        self.assertFalse(part.is_valid(dict(good, rev=0)))
        self.assertFalse(part.is_valid({k: v for k, v in good.items() if k != "state"}))
        self.BASELINE_RECEIPTS.append({"context": context, "root": str(source),
                                      "json_positions": sorted(prefixes),
                                      "files": {str(p): h for p, h in reader.provenance.items()}})

    def test_47_historical_four_position_source_mutations_are_not_hidden(self):
        """Physical owned Source mutations, not producer kills or document/cache injection."""
        historical_four_source_projection(self.root)
        payloads = {name: (self.root / name).read_bytes()
                    for name, mode, blob, digest, size in HISTORICAL_FOUR_SOURCE_FILES}
        relative = HISTORICAL_FOUR_SOURCE_FILES[0][0]
        original = payloads[relative].decode("utf-8")
        ref = "../../common/data/common.schema.json#/$defs/common.domain_topology_doc"
        self.assertEqual(original.count(ref), 1)
        anchor = "    HolderTopologyBody:\n      type: object\n      properties:\n"
        self.assertEqual(original.count(anchor), 1)
        variants = {
            "missing-edge": original.replace("$ref: " + ref, "type: object", 1),
            "instance-data": original.replace("$ref: " + ref, 'example: {"$ref": "' + ref + '"}', 1),
            "wrong-target": original.replace(ref, "../../common/data/common.schema.json#/$defs/common.domain_member", 1),
            "extra-edge": original.replace(anchor, anchor +
                "        extra:\n          $ref: ../../common/data/common.schema.json#/$defs/common.domain_member\n", 1),
            "network-URI": original.replace(ref, "https://example.invalid/common.schema.json", 1),
            "missing-pointer": original.replace(ref, ref + "_missing", 1),
        }
        for name, text in variants.items():
            with self.subTest(variant=name), tempfile.TemporaryDirectory(prefix="historical-four-source-mutant-") as tmp:
                root = Path(tmp)
                for path, raw in payloads.items():
                    target = root / path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(text.encode("utf-8") if path == relative else raw)
                source = root / relative
                if name in ("network-URI", "missing-pointer"):
                    with self.assertRaises(CheckingError):
                        SourceSchemaReader(root, source)
                    continue
                reader = SourceSchemaReader(root, source)
                edges = {(pointer, literal): target for (file, pointer, literal, kind), target
                         in reader.edges.items() if file == source and kind == "schema" and ".schema.json" in literal}
                if name in ("missing-edge", "instance-data"):
                    self.assertEqual(len(edges), 3)
                    self.assertFalse(any(pointer == "/components/schemas/HolderTopologyBody/properties/doc"
                                         for pointer, literal in edges))
                elif name == "extra-edge":
                    self.assertEqual(len(edges), 5)
                    self.assertIn(("/components/schemas/HolderTopologyBody/properties/extra",
                                   "../../common/data/common.schema.json#/$defs/common.domain_member"), edges)
                else:
                    self.assertEqual(len(edges), 4)
                    self.assertIn(("/components/schemas/HolderTopologyBody/properties/doc",
                                   "../../common/data/common.schema.json#/$defs/common.domain_member"), edges)
                    full = reader.validator_at(source, "/components/schemas/HolderTopologyBody")
                    self.assertFalse(full.is_valid({"doc": {"rev": 0, "star": []}, "via": {"m1": "m2"}}))

    def test_01_actual_p10_reference_bearing_aliases_keep_each_coordinate(self):
        source = ROOT / "Platform/10-domain-console/spec/10-domain-console.api.openapi.yaml"
        reader = SourceSchemaReader(ROOT, source)
        positions = []
        for (file, identity, kind), pointers in reader.locations.items():
            if file != source or len(pointers) < 2:
                continue
            node = reader.at(file, pointers[0], kind)
            if type(node) is dict and "$ref" in node:
                for pointer in pointers:
                    self.assertIn((file, pointer, node["$ref"], kind), reader.edges)
                    positions.append(pointer)
        self.assertTrue(positions, "the current P10 aliases must actually be exercised")
        self.BASELINE_RECEIPTS.append({"root": str(source), "alias_reference_positions": sorted(positions),
                                      "files": {str(p): h for p, h in reader.provenance.items()}})

    def test_02_root_json_and_transitive_local_source(self):
        target = self.schema({"$defs": {"N": {"type": "integer", "minimum": 1}}, "$ref": "#/$defs/N"})
        reader = self.reader({"$ref": "../data/target.schema.json"})
        validator = reader.validator_at(reader.source, "/components/schemas/Root")
        self.assertTrue(validator.is_valid(1))
        self.assertFalse(validator.is_valid(0))
        self.assertIn(target, reader.provenance)

    def test_03_boolean_schemas_are_not_scalar_errors(self):
        for value in (True, False):
            with self.subTest(schema=value):
                self.schema(value)
                reader = self.reader({"$ref": "../data/target.schema.json#"})
                self.assertEqual(reader.validator_at(reader.source, "/components/schemas/Root").is_valid({}), value)

    def test_04_early_p10_to_current_p09_pointer(self):
        relative = "Platform/09-agent/data/alarms.schema.json"
        target = self.root / relative
        target.parent.mkdir(parents=True)
        target.write_bytes((ROOT / relative).read_bytes())
        source = self.api("10-domain-console", schemas={"Root": {
            "$ref": "../../09-agent/data/alarms.schema.json#/properties/events/items/properties/id"}})
        reader = SourceSchemaReader(self.root, source)
        validator = reader.validator_at(source, "/components/schemas/Root")
        self.assertTrue(validator.is_valid("a"))
        self.assertFalse(validator.is_valid(""))
        self.assertEqual(reader.provenance[target], hashlib.sha256((ROOT / relative).read_bytes()).hexdigest())

    def test_05_exact_late_door_before_negative_neighbours(self):
        source, _ = self.late()
        reader = SourceSchemaReader(self.root, source)
        pointer = "/paths/~1api~1backup/get/responses/200/content/application~1json/schema"
        self.assertTrue(reader.validator_at(source, pointer).is_valid("x"))
        self.assertFalse(reader.validator_at(source, pointer).is_valid(""))

    def test_06_missing_chapter_and_wrong_declared_target(self):
        for target, description in (("08-domain", "not a late declaration"), ("09-agent", "Chapter 6.7")):
            with self.subTest(target=target, description=description):
                source, _ = self.late(target, description=description)
                with self.assertRaises(CheckingError):
                    SourceSchemaReader(self.root, source)
        source, _ = self.late()
        (source.parent / "06.7-console.norms.md").write_text("# ordinary chapter\n", encoding="utf-8")
        with self.assertRaises(CheckingError):
            SourceSchemaReader(self.root, source)

    def test_07_alias_under_door_and_components_does_not_inherit_permission(self):
        source, ref = self.late(components=True)
        target = self.root / "Platform/08-domain/data/target.schema.json"
        read = Path.read_bytes
        observations = []
        def observe(path):
            observations.append(path.resolve())
            return read(path)
        with patch.object(Path, "read_bytes", observe), self.assertRaises(CheckingError):
            SourceSchemaReader(self.root, source)
        self.assertIn(target, observations, "the allowed door must really have read its resource first")

    def test_08_real_cache_fill_does_not_authorize_later_declaration(self):
        source, _ = self.late(components=True)
        own = self.reader({"$ref": "../data/target.schema.json"})
        target = self.root / "Platform/08-domain/data/target.schema.json"
        self.assertIn(target, own.docs)
        with self.assertRaises(CheckingError):
            own.validator_at(source, "/components/schemas/Also")
        pointer = "/paths/~1api~1backup/get/responses/200/content/application~1json/schema"
        self.assertTrue(own.validator_at(source, pointer).is_valid("x"))

    def test_09_standalone_json_has_no_inherited_late_door(self):
        source, _ = self.late()
        self.schema({"type": "string"}, owner="09-agent")
        self.schema({"$ref": "../../09-agent/data/target.schema.json"})
        with self.assertRaises(CheckingError):
            SourceSchemaReader(self.root, source)

    def test_10_legal_reference_aliases_preserve_both_source_positions(self):
        self.schema({"type": "integer"})
        ref = {"$ref": "../data/target.schema.json"}
        source = self.api(schemas={"A": ref, "B": ref})
        reader = SourceSchemaReader(self.root, source)
        wanted = {"/components/schemas/A", "/components/schemas/B"}
        self.assertEqual({ptr for (file, ptr, value, _), _ in reader.edges.items()
                          if file == source and value == ref["$ref"]}, wanted)
        self.assertIs(reader.at(source, "/components/schemas/A", "schema"),
                      reader.at(source, "/components/schemas/B", "schema"))

    def test_11_cyclic_alias_structure_is_a_checking_error(self):
        source = self.api()
        source.write_text('openapi: 3.1.0\npaths: {}\ncomponents:\n  schemas:\n    X: &node\n      properties:\n        again: *node\n', encoding="utf-8")
        with self.assertRaises(CheckingError):
            SourceSchemaReader(self.root, source)

    def test_12_common_cannot_read_a_lesson(self):
        self.schema({"type": "string"})
        source = self.api("common", schemas={"X": {"$ref": "../../08-domain/data/target.schema.json"}})
        with self.assertRaises(CheckingError):
            SourceSchemaReader(self.root, source)

    def test_13_relative_base_is_the_actual_declaration_resource(self):
        self.schema({"$ref": "nested/value.schema.json"})
        self.write("Platform/08-domain/data/nested/value.schema.json", {"type": "string", "minLength": 2})
        reader = self.reader({"$ref": "../data/target.schema.json"})
        validator = reader.validator_at(reader.source, "/components/schemas/Root")
        self.assertTrue(validator.is_valid("ab"))
        self.assertFalse(validator.is_valid("a"))

    def test_14_network_absolute_query_and_missing_resources_are_errors(self):
        target = self.schema({"type": "integer"})
        for ref in ("https://invalid.example/schema", target.as_uri(), str(target),
                    "//invalid.example/schema", "../data/target.schema.json?q=1", "../data/missing.schema.json",
                    "../data/target.schema.json#/$defs/missing", "../data/target.schema.json#name"):
            with self.subTest(ref=ref), self.assertRaises(CheckingError):
                self.reader({"$ref": ref})

    def test_15_physical_boundary_and_real_owner_follow_symlinks(self):
        outside = self.root / "outside.schema.json"
        outside.write_text('{"type":"integer"}', encoding="utf-8")
        self.schema({"type": "integer"})
        link = self.root / "Platform/08-domain/data/link.schema.json"
        link.symlink_to(outside)
        with self.assertRaises(CheckingError):
            self.reader({"$ref": "../data/link.schema.json"})
        link.unlink()
        later = self.schema({"type": "integer"}, owner="09-agent")
        link.symlink_to(later)
        with self.assertRaises(CheckingError):
            self.reader({"$ref": "../data/link.schema.json"})
        link.unlink()
        link.symlink_to(self.root / "Platform/08-domain/data/target.schema.json")
        reader = self.reader({"$ref": "../data/link.schema.json"})
        self.assertTrue(reader.validator_at(reader.source, "/components/schemas/Root").is_valid(1))

    def test_16_cross_file_cycle_differs_from_local_recursion(self):
        self.schema({"type": "object", "additionalProperties": False, "properties": {"next": {"$ref": "#"}}})
        reader = self.reader({"$ref": "../data/target.schema.json"})
        validator = reader.validator_at(reader.source, "/components/schemas/Root")
        self.assertTrue(validator.is_valid({"next": {}}))
        self.assertFalse(validator.is_valid({"next": {"unexpected": 1}}))
        self.schema({"$ref": "other.schema.json"})
        self.schema({"$ref": "target.schema.json"}, name="other")
        with self.assertRaises(CheckingError):
            self.reader({"$ref": "../data/target.schema.json"})

    def test_17_malformed_duplicate_nonfinite_and_scalar_json(self):
        target = self.schema({"type": "integer"})
        for content in (b'{bad}', b'{"type":"integer","type":"string"}', b'{"const":NaN}',
                        b'{"const":Infinity}', b'"scalar"', b'1', b'null', b'[]', b'\xff'):
            target.write_bytes(content)
            with self.subTest(content=content), self.assertRaises(CheckingError):
                self.reader({"$ref": "../data/target.schema.json"})

    def test_cross_file_return_to_other_pointer_is_not_recursion(self):
        a = self.schema({"$defs": {"Start": {"$ref": "other.schema.json#/$defs/Start"},
                                   "Leaf": {"type": "integer", "minimum": 1}}})
        self.schema({"$defs": {"Start": {"$ref": "target.schema.json#/$defs/Leaf"}}}, name="other")
        reader = self.reader({"$ref": "../data/target.schema.json#/$defs/Start"})
        validator = reader.validator_at(a, "/$defs/Start")
        self.assertTrue(validator.is_valid(1))
        self.assertFalse(validator.is_valid(0))
        self.assertFalse(validator.is_valid("1"))
        # A cycle through object children is still a cross-file cycle.
        self.schema({"type": "object", "properties": {"next": {"$ref": "other.schema.json"}}})
        self.schema({"type": "object", "properties": {"next": {"$ref": "target.schema.json"}}}, name="other")
        with self.assertRaises(CheckingError):
            self.reader({"$ref": "../data/target.schema.json"})

    def test_18_schema_dialect_and_base_are_not_silently_changed(self):
        for bad in ({"$schema": "http://json-schema.org/draft-07/schema#"}, {"$id": "https://other/"},
                    {"$dynamicRef": "#x"}, {"$recursiveRef": "#"}, {"$anchor": "x"}):
            with self.subTest(schema=bad), self.assertRaises(CheckingError):
                self.reader(bad)

    def test_19_source_cache_is_not_healed_after_input_changes(self):
        target = self.schema({"type": "integer"})
        reader = self.reader({"$ref": "../data/target.schema.json"})
        changed = b'{"type":"string"}'
        target.write_bytes(changed)
        with self.assertRaises(CheckingError):
            reader.document(target)
        self.assertEqual(target.read_bytes(), changed)

    def test_20_actual_dotted_definition_is_covered_not_skipped(self):
        reader = self.reader()
        defs = {"Root": {"$ref": "#/$defs/internal.with.dots"},
                "internal.with.dots": {"type": "integer", "minimum": 0}}
        cases = [(name, value) for name in defs for value in (0, 1, -1)]
        before = copy.deepcopy(defs)
        self.assertEqual(reader.compare(defs, cases), [])
        self.assertEqual(defs, before)
        defs["internal.with.dots"]["minimum"] = -1
        self.assertTrue(reader.compare(defs, cases))

    def test_21_unmapped_ambiguous_and_empty_comparisons_are_errors(self):
        reader = self.reader()
        with self.assertRaises(CheckingError):
            reader.compare({"Root": {"type": "integer"}, "hidden.name": True}, [("Root", 1)])
        with self.assertRaises(CheckingError):
            reader.compare({"Root": {"type": "integer"}}, [])
        source = self.api(schemas={"A": {"type": "integer"}, "B": {"type": "integer"}})
        reader = SourceSchemaReader(self.root, source)
        with self.assertRaises(CheckingError):
            reader.bundle_origins({"X": {"type": "integer"}},
                                  [("X", source, "/components/schemas/A"), ("X", source, "/components/schemas/B")])

    def test_22_proven_alias_origins_retain_every_coordinate(self):
        schema = {"type": "integer"}
        source = self.api(schemas={"A": schema, "B": schema})
        reader = SourceSchemaReader(self.root, source)
        bindings = [("same.actual", source, "/components/schemas/A"), ("same.actual", source, "/components/schemas/B")]
        origins = reader.bundle_origins({"same.actual": {"type": "integer"}}, bindings)
        self.assertEqual(len(origins["same.actual"]), 2)
        self.assertEqual(reader.compare({"same.actual": {"type": "integer"}},
                                        [("same.actual", v) for v in (0, 1, "x")], bindings), [])

    def test_23_actual_metadata_tables_are_strict_and_are_not_the_oracle(self):
        text = 'var requestSchemas = map[Op]map[string]string{\n OpOne: {"application/json": "Dotted.name"},\n}\n'
        self.assertEqual(SourceSchemaReader.literal_table(text, "requestSchemas"),
                         {"OpOne": {"application/json": "Dotted.name"}})
        for wrong in (text.replace('"Dotted.name"', 'false'), text.replace('"application/json":', '"x": "x", "x":'),
                      text.replace('requestSchemas', 'other'), text.replace(': {', ' {', 1)):
            with self.subTest(text=wrong), self.assertRaises(CheckingError):
                SourceSchemaReader.literal_table(wrong, "requestSchemas")

    def test_24_binding_table_completeness_and_source_operation_identity(self):
        source = self.api(schemas={}, paths={"/a": {"post": {"requestBody": {"content": {
            "application/json": {"schema": {"type": "integer", "minimum": 1}}}}, "responses": {"200": {
            "description": "ok", "content": {"application/json": {"schema": {"type": "string"}}}}}}}})
        reader = SourceSchemaReader(self.root, source)
        mod = self.root / "actual/apidoor"
        mod.mkdir(parents=True)
        (mod / "routes.go").write_text('"/a POST": OpOne,\n', encoding="utf-8")
        tables = ('var requestSchemas = map[Op]map[string]string{OpOne: {"application/json": "Inline.request"},}\n'
                  'var responseSchemas = map[Op]map[int]map[string]string{OpOne: {200: {"application/json": "Inline.response"}},}\n')
        (mod / "bodies.go").write_text(tables, encoding="utf-8")
        bindings = reader.output_bindings(mod.parent)
        self.assertEqual({x[0] for x in bindings}, {"Inline.request", "Inline.response"})
        defs = {"Inline.request": {"type": "integer", "minimum": 1}, "Inline.response": {"type": "string"}}
        cases = [(name, v) for name in defs for v in (0, 1, "x")]
        self.assertEqual(reader.compare(defs, cases, bindings), [])
        (mod / "bodies.go").write_text(tables.replace('"Inline.response"', '"extra"').replace('200:', '201:'), encoding="utf-8")
        with self.assertRaises(CheckingError):
            reader.output_bindings(mod.parent)

    def test_25_ref_sibling_constraints_belong_to_the_declaration_not_its_target(self):
        self.schema({"type": "string"})
        reader = self.reader({"$ref": "../data/target.schema.json", "minLength": 2})
        defs = {"Root": {"$ref": "#/$defs/opaque.target", "minLength": 2},
                "opaque.target": {"type": "string"}}
        cases = [(name, value) for name in defs for value in ("", "a", "ab", 1)]
        self.assertEqual(reader.compare(defs, cases), [])
        actual = copy.deepcopy(defs)
        del actual["Root"]["minLength"]
        mismatch = reader.compare(actual, cases)
        self.assertTrue(mismatch)
        self.assertTrue(all(row[0] == "Root" for row in mismatch))


    def test_26_cached_validator_rechecks_complete_source_bytes(self):
        target = self.schema({"type": "string", "minLength": 1})
        reader = self.reader({"$ref": "../data/target.schema.json"})
        pointer = "/components/schemas/Root"
        self.assertTrue(reader.validator_at(reader.source, pointer).is_valid("a"))
        self.assertFalse(reader.validator_at(reader.source, pointer).is_valid(1))
        target.write_text('{"type":"integer"}', encoding="utf-8")
        with self.assertRaises(CheckingError):
            reader.validator_at(reader.source, pointer)
        self.assertEqual(target.read_text(), '{"type":"integer"}')

    def test_27_cached_validator_rejects_equal_value_symlink_repin(self):
        first = self.schema({"type": "integer"})
        second = self.schema({"type": "integer"}, name="other")
        alias = first.with_name("alias.schema.json")
        alias.symlink_to(first.name)
        reader = self.reader({"$ref": "../data/alias.schema.json"})
        pointer = "/components/schemas/Root"
        self.assertTrue(reader.validator_at(reader.source, pointer).is_valid(1))
        alias.unlink()
        alias.symlink_to(second.name)
        with self.assertRaises(CheckingError):
            reader.validator_at(reader.source, pointer)

    def test_28_cached_validator_rechecks_late_declaration_bytes(self):
        source, _ = self.late()
        reader = SourceSchemaReader(self.root, source)
        pointer = "/paths/~1api~1backup/get/responses/200/content/application~1json/schema"
        self.assertTrue(reader.validator_at(source, pointer).is_valid("a"))
        norm = self.root / "Platform/06-console/spec/06.7-console.norms.md"
        norm.write_bytes(norm.read_bytes() + b"\nchanged declaration\n")
        with self.assertRaises(CheckingError):
            reader.validator_at(source, pointer)

    def test_29_cached_registry_includes_a_new_explicit_schema_entry(self):
        self.schema({"type": "integer", "minimum": 2})
        source = self.api(schemas={"Root": {"type": "string"}})
        import yamlsub
        doc = yamlsub.load(source.read_text(), source.name)
        doc["x-explicit"] = {"$ref": "../data/target.schema.json"}
        self.write(str(source.relative_to(self.root)), doc, yaml=True)
        reader = SourceSchemaReader(self.root, source)
        self.assertTrue(reader.validator_at(source, "/components/schemas/Root").is_valid("a"))
        target = reader.validator_at(source, "/x-explicit")
        self.assertTrue(target.is_valid(2))
        self.assertFalse(target.is_valid(1))


    def parameter_fixture(self):
        spec = self.api(paths={"/x": {"get": {
            "parameters": [{"name": "n", "in": "query", "required": True,
                            "schema": {"type": "integer", "minimum": 2}}],
            "responses": {"200": {"description": "ok"}}}}})
        module = self.root / "actual-go"
        (module / "apidoor").mkdir(parents=True)
        (module / "apidoor/routes.go").write_text('var ops = map[string]Op{\n"/x GET": OpX,\n}\n')
        actual = ('var requestSchemas = map[Op]map[string]string{}\n'
                  'var responseSchemas = map[Op]map[string]map[string]string{}\n'
                  'var paramSchemas = map[Op][]paramSpec{\n'
                  'OpX: {{name: "n", in: "query", required: true, schema: "opaque-root", def: ""}},\n}\n')
        (module / "apidoor/bodies.go").write_text(actual)
        return SourceSchemaReader(self.root, spec), module, actual

    def test_30_actual_parameter_definitions_do_not_require_a_dotted_name_convention(self):
        reader, module, text = self.parameter_fixture()
        defs = {"opaque-root": {"type": "integer", "minimum": 2}}
        bindings = reader.output_bindings(module)
        self.assertEqual(reader.compare(defs, [("opaque-root", 2), ("opaque-root", 1)], bindings), [])
        self.assertEqual(len(bindings), 1)

    def test_31_parameter_table_missing_extra_duplicate_and_roles_fail(self):
        reader, module, text = self.parameter_fixture()
        row = 'OpX: {{name: "n", in: "query", required: true, schema: "opaque-root", def: ""}},'
        changed = [text.replace(row, ''), text.replace(row, row + '\n' + row),
                   text.replace('name: "n"', 'name: "unknown"'),
                   text.replace('in: "query"', 'in: "path"'),
                   text.replace('required: true', 'required: "true"'),
                   text.replace('name: "n"', 'name: "n", name: "n"'),
                   text.replace('schema: "opaque-root"', 'unexpected: "opaque-root"'),
                   text.replace('schema: "opaque-root"', 'schema: true'),
                   text.replace('paramSchemas', 'noParameterTable'), text + text]
        for mutant in changed:
            with self.subTest(mutant=mutant):
                self.assertNotEqual(mutant, text)
                (module / "apidoor/bodies.go").write_text(mutant)
                with self.assertRaises(CheckingError):
                    reader.output_bindings(module)
        for mutant in (text.replace('required: true', 'required: false'),
                       text.replace('def: ""', 'def: "2"')):
            with self.subTest(semantic_metadata=mutant), self.assertRaises(AssertionError):
                (module / "apidoor/bodies.go").write_text(mutant)
                reader.output_bindings(module)
        # An invalid later record wins over an earlier normal semantic mismatch.
        mutant = text.replace('required: true', 'required: false').replace('}},', '}, {name: "extra"}},')
        (module / "apidoor/bodies.go").write_text(mutant)
        with self.assertRaises(CheckingError):
            reader.output_bindings(module)
        (module / "apidoor/bodies.go").write_text(text)
        self.assertEqual(len(reader.output_bindings(module)), 1)

    def test_32_bound_parameter_schema_wrong_value_is_a_semantic_mismatch(self):
        reader, module, _ = self.parameter_fixture()
        bindings = reader.output_bindings(module)
        cases = [("opaque-root", 1), ("opaque-root", 2)]
        self.assertTrue(reader.compare({"opaque-root": {"type": "integer", "minimum": 1}}, cases, bindings))
        with self.assertRaises(CheckingError):
            reader.compare({"other-root": {"type": "integer"}}, [("other-root", 1)], bindings)


    def path_parameter_fixture(self, external=False, override=False, unsafe=False):
        target = {"type": "string", "pattern": "^[a-z]{2}$"}
        if unsafe:
            target.update(default={"$ref": "https://not-source.invalid/default"},
                          examples=[{"$ref": "../../99-missing/schema.json"}])
        parameter = {"name": "digest", "in": "path", "required": True, "schema": target}
        if unsafe:
            parameter["example"] = {"$ref": "https://not-source.invalid/parameter"}
        item = {"x-route-priority": 1, "parameters": [parameter],
                "get": {"responses": {"200": {"description": "ok"}}}}
        route = "/blobs/{digest}"
        if external:
            self.schema({"type": "string", "pattern": "^[a-z]{2}$"}, owner="common", name="digest")
            parameter["schema"] = {"$ref": "../data/digest.schema.json"}
            self.api("common", components={"parameters": {"Digest": parameter}})
            item["parameters"] = [{"$ref": "../../common/contracts/shared.api.openapi.yaml#/components/parameters/Digest"}]
        if override:
            item["get"]["parameters"] = [{"name": "digest", "in": "path", "required": True,
                                             "schema": {"type": "integer", "minimum": 2}}]
        spec = self.api(owner="05-resource", schemas={}, paths={route: item})
        module = self.root / "actual-path-go"
        (module / "apidoor").mkdir(parents=True)
        (module / "apidoor/routes.go").write_text('var ops = map[string]Op{\n"/blobs/{digest} GET": OpBlob,\n}\n')
        text = ('var requestSchemas = map[Op]map[string]string{}\n'
                'var responseSchemas = map[Op]map[string]map[string]string{}\n'
                'var pathSchemas = map[string]map[string]string{\n'
                '"/blobs/{digest}": {"digest": "opaque-path-root"},\n}\n')
        (module / "apidoor/bodies.go").write_text(text)
        return SourceSchemaReader(self.root, spec), module, text, target

    def test_34_path_parameter_binds_exact_slot_without_a_definition_name_convention(self):
        reader, module, _, schema = self.path_parameter_fixture()
        bindings = reader.output_bindings(module)
        self.assertEqual(bindings, [("opaque-path-root", reader.source,
            "/paths/~1blobs~1{digest}/parameters/0/schema")])
        cases = [("opaque-path-root", value) for value in ("ab", "a", "ABC", 2)]
        self.assertEqual(reader.compare({"opaque-path-root": schema}, cases, bindings), [])
        self.assertTrue(reader.compare({"opaque-path-root": {"type": "string"}}, cases, bindings))

    def test_35_path_parameter_missing_extra_duplicate_type_and_wrong_bindings_fail(self):
        reader, module, text, schema = self.path_parameter_fixture()
        bindings = reader.output_bindings(module)
        cases = [("opaque-path-root", value) for value in ("ab", "a")]
        self.assertEqual(reader.compare({"opaque-path-root": schema}, cases, bindings), [])
        row = '"/blobs/{digest}": {"digest": "opaque-path-root"},'
        mutants = [text.replace(row, ''), text.replace(row, row + '\n' + row),
                   text.replace('"digest": "opaque-path-root"', '"other": "opaque-path-root"'),
                   text.replace('"/blobs/{digest}":', '"/other/{digest}":'),
                   text.replace('"opaque-path-root"', 'true'),
                   text.replace('"opaque-path-root"', '""'),
                   text.replace('{"digest": "opaque-path-root"}', '{}'),
                   text.replace('{"digest": "opaque-path-root"}', '"opaque-path-root"'),
                   text.replace('pathSchemas', 'notPathSchemas'), text + text,
                   text.replace('"digest": "opaque-path-root"',
                                '"digest": "opaque-path-root", "extra": "opaque-path-root"')]
        for mutant in mutants:
            with self.subTest(mutant=mutant):
                self.assertNotEqual(mutant, text)
                (module / "apidoor/bodies.go").write_text(mutant)
                with self.assertRaises(CheckingError):
                    reader.output_bindings(module)
        (module / "apidoor/bodies.go").write_text(text.replace('"opaque-path-root"', '"wrong-root"'))
        wrong = reader.output_bindings(module)
        with self.assertRaises(CheckingError):
            reader.compare({"opaque-path-root": schema}, cases, wrong)
        (module / "apidoor/bodies.go").write_text(text)
        with self.assertRaises(CheckingError):
            reader.compare({"opaque-path-root": schema, "unbound": {}}, cases + [("unbound", {})], bindings)

    def test_36_path_parameter_reference_preserves_owner_and_each_uri_base(self):
        reader, module, _, _ = self.path_parameter_fixture(external=True)
        bindings = reader.output_bindings(module)
        common = self.root / "Platform/common/contracts/shared.api.openapi.yaml"
        self.assertEqual(bindings, [("opaque-path-root", common, "/components/parameters/Digest/schema")])
        target = self.root / "Platform/common/data/digest.schema.json"
        cases = [("opaque-path-root", value) for value in ("ab", "a", 1)]
        self.assertEqual(reader.compare({"opaque-path-root": {"type": "string", "pattern": "^[a-z]{2}$"}},
                                        cases, bindings), [])
        self.assertIn(target, reader.provenance)
        # An external future owner is not made legal by a parameter/table binding.
        changed = common.read_text().replace('../data/digest.schema.json',
                                            '../../10-domain-console/data/digest.schema.json')
        common.write_text(changed)
        self.schema({"type": "string"}, owner="10-domain-console", name="digest")
        with self.assertRaises(CheckingError):
            SourceSchemaReader(self.root, reader.source)

    def test_37_operation_path_parameter_override_uses_its_own_source_coordinate(self):
        reader, module, _, _ = self.path_parameter_fixture(override=True)
        bindings = reader.output_bindings(module)
        self.assertEqual(bindings, [("opaque-path-root", reader.source,
            "/paths/~1blobs~1{digest}/get/parameters/0/schema")])
        cases = [("opaque-path-root", value) for value in (2, 1, "ab")]
        self.assertEqual(reader.compare({"opaque-path-root": {"type": "integer", "minimum": 2}},
                                        cases, bindings), [])
        self.assertTrue(reader.compare({"opaque-path-root": {"type": "string", "pattern": "^[a-z]{2}$"}},
                                       cases, bindings))

    def test_38_path_parameter_examples_and_defaults_remain_instance_data(self):
        reader, module, _, schema = self.path_parameter_fixture(unsafe=True)
        self.assertFalse(reader.edges)
        bindings = reader.output_bindings(module)
        cases = [("opaque-path-root", value) for value in ("ab", "a", {"$ref": "https://instance.invalid"})]
        self.assertEqual(reader.compare({"opaque-path-root": schema}, cases, bindings), [])
        # The identical unsafe reference in an actual Schema Object is refused.
        spec = self.api(owner="05-resource", schemas={"Root": {"$ref": "https://not-source.invalid/schema"}})
        with self.assertRaises(CheckingError):
            SourceSchemaReader(self.root, spec)


    def test_39_missing_or_ambiguous_source_path_declarations_are_errors(self):
        reader, module, _, schema = self.path_parameter_fixture()
        bindings = reader.output_bindings(module)
        self.assertEqual(reader.compare({"opaque-path-root": schema},
                         [("opaque-path-root", "ab"), ("opaque-path-root", "a")], bindings), [])
        original = reader.document(reader.source)
        for variant in ("missing-parameter", "missing-schema", "duplicate", "wrong-name"):
            doc = copy.deepcopy(original)
            parameters = doc["paths"]["/blobs/{digest}"]["parameters"]
            if variant == "missing-parameter":
                parameters.clear()
            elif variant == "missing-schema":
                del parameters[0]["schema"]
            elif variant == "duplicate":
                parameters.append(copy.deepcopy(parameters[0]))
            else:
                parameters[0]["name"] = "other"
            self.write(str(reader.source.relative_to(self.root)), doc, yaml=True)
            with self.subTest(variant=variant), self.assertRaises(CheckingError):
                SourceSchemaReader(self.root, reader.source).output_bindings(module)


    def response_fixture(self, optional_ref=False):
        source = self.api(paths={
            "/x": {"get": {"responses": {
                "200": {"description": "declared media, no schema", "content": {"application/json": {}}},
                "204": {"description": "absent content"},
                "404": {"description": "empty content", "content": {}}}}},
            "/head": {"head": {"responses": {"200": {"description": "body-bearing HEAD", "content": {
                "application/json": {"schema": {"type": "object", "properties": {"ok": {"const": True}},
                                                "required": ["ok"]}}}}}}}})
        if optional_ref:
            self.schema({"type": "integer", "minimum": 0}, owner="common", name="optional")
            import yamlsub
            doc = yamlsub.load(source.read_text(), source.name)
            schema = doc["paths"]["/head"]["head"]["responses"]["200"]["content"]["application/json"]["schema"]
            schema["properties"]["more"] = {"$ref": "../../common/data/optional.schema.json"}
            self.write(str(source.relative_to(self.root)), doc, yaml=True)
        module = self.root / "actual-responses"
        (module / "apidoor").mkdir(parents=True)
        routes = 'var ops=map[string]Op{\n"/x GET": OpX,\n"/head HEAD": OpHead,\n}\n'
        (module / "apidoor/routes.go").write_text(routes)
        return SourceSchemaReader(self.root, source), module, routes

    def test_40_no_content_cases_precede_actual_response_tables_and_do_not_disappear(self):
        reader, module, _ = self.response_fixture()
        cases, coverage = source_response_probes(reader, module)
        self.assertEqual(coverage, {"source_responses": 4, "bodyless": 2, "media_targets": 2,
                                   "body_bearing_HEAD": 1, "schema_less_media": 1})
        no_content = [case for case in cases if case["role"].startswith("no-content")]
        self.assertEqual(len(no_content), 8)
        self.assertEqual({(case["method"], case["code"]) for case in no_content}, {("get", 204), ("get", 404)})
        self.assertTrue(any(case["method"] == "head" and case["role"] == "declared-media" for case in cases))
        self.assertTrue(any(case["code"] == 200 and case["method"] == "get" and
                            case["value"] is not None and case["expected"] for case in cases))
        (module / "apidoor/bodies.go").write_text("var responseSchemas=map[Op]map[string]map[string]string{}\n")
        self.assertEqual(source_response_probes(reader, module), (cases, coverage))
        self.assertTrue({"unknown-operation", "unknown-status", "unknown-media"} <= {case["role"] for case in cases})

    def test_41_response_probe_missing_extra_or_aliased_operation_is_checking_error(self):
        reader, module, routes = self.response_fixture()
        cases, _ = source_response_probes(reader, module)
        self.assertGreater(len(cases), 8)
        for mutant in (routes.replace('"/x GET": OpX,', ''),
                       routes.replace('"/x GET": OpX,', '"/x GET": OpX,\n"/extra GET": OpExtra,'),
                       routes.replace('OpHead', 'OpX'),
                       routes.replace('"/x GET": OpX,', '"/x GET": OpX,\n"/x GET": OpX,')):
            self.assertNotEqual(mutant, routes)
            (module / "apidoor/routes.go").write_text(mutant)
            with self.subTest(mutant=mutant), self.assertRaises(CheckingError):
                source_response_probes(reader, module)

    def test_42_body_bearing_head_or_schema_less_media_is_not_no_content(self):
        reader, module, _ = self.response_fixture()
        declarations = reader.response_declarations()
        self.assertEqual([(r["status"], r["bodyless"]) for r in declarations],
                         [("200", False), ("204", True), ("404", True), ("200", False)])
        document = copy.deepcopy(reader.document(reader.source))
        del document["paths"]["/x"]["get"]["responses"]["204"]
        del document["paths"]["/x"]["get"]["responses"]["404"]
        self.write(str(reader.source.relative_to(self.root)), document, yaml=True)
        cases, coverage = source_response_probes(SourceSchemaReader(self.root, reader.source), module)
        self.assertEqual(coverage["bodyless"], 0)
        self.assertGreater(len(cases), 0)
        self.assertFalse(any(case["role"].startswith("no-content") for case in cases))
        self.assertTrue(any(case["role"] == "declared-media" for case in cases))


    def test_43_optional_reference_only_affects_candidates_not_full_source_validator(self):
        reader, module, _ = self.response_fixture(optional_ref=True)
        cases, _ = source_response_probes(reader, module)
        head = [case for case in cases if case["method"] == "head" and case["role"] == "declared-media"]
        self.assertEqual(len(head), 1)
        pointer = "/paths/~1head/head/responses/200/content/application~1json/schema"
        validator = reader.validator_at(reader.source, pointer)
        self.assertTrue(validator.is_valid(head[0]["value"]))
        self.assertFalse(validator.is_valid({"ok": True, "more": "wrong type"}))
        self.assertFalse(validator.is_valid({"ok": False}))
        self.assertIn(self.root / "Platform/common/data/optional.schema.json", reader.provenance)


    def test_44_response_candidate_preserves_schema_like_literal_instance_data(self):
        reader, module, _ = self.response_fixture()
        document = copy.deepcopy(reader.document(reader.source))
        literal = {"properties": {"literal": 1}, "required": [], "$ref": "https://not-a-schema.invalid/data"}
        document["paths"]["/head"]["head"]["responses"]["200"]["content"]["application/json"]["schema"] = {"const": literal}
        self.write(str(reader.source.relative_to(self.root)), document, yaml=True)
        cases, _ = source_response_probes(SourceSchemaReader(self.root, reader.source), module)
        self.assertEqual([case["value"] for case in cases if case["method"] == "head" and
                          case["role"] == "declared-media"], [literal])


    def test_45_nested_source_composition_keeps_required_values_and_reference_bases(self):
        reader, module, _ = self.response_fixture(optional_ref=True)
        document = copy.deepcopy(reader.document(reader.source))
        schema = document["paths"]["/head"]["head"]["responses"]["200"]["content"]["application/json"]["schema"]
        document["components"]["schemas"]["BaseResponse"] = schema
        document["components"]["schemas"]["ExtendedResponse"] = {
            "allOf": [{"$ref": "#/components/schemas/BaseResponse"}, {"properties": {"ok": {"const": True}}}]}
        document["paths"]["/head"]["head"]["responses"]["200"]["content"]["application/json"]["schema"] = {
            "allOf": [{"$ref": "#/components/schemas/ExtendedResponse"},
                      {"properties": {"state": {"const": "ready"}}, "required": ["state"]}]}
        self.write(str(reader.source.relative_to(self.root)), document, yaml=True)
        full = SourceSchemaReader(self.root, reader.source)
        cases, _ = source_response_probes(full, module)
        head = next(case["value"] for case in cases if case["method"] == "head" and case["role"] == "declared-media")
        validator = full.validator_at(full.source, "/paths/~1head/head/responses/200/content/application~1json/schema")
        self.assertTrue(validator.is_valid(head))
        self.assertEqual(head["state"], "ready")
        self.assertFalse(validator.is_valid(dict(head, state="wrong")))
        self.assertFalse(validator.is_valid(dict(head, more="wrong type")))


    def test_46_response_proposals_respect_required_string_patterns_before_object_sampling(self):
        reader, module, _ = self.response_fixture()
        document = copy.deepcopy(reader.document(reader.source))
        schema = document["paths"]["/head"]["head"]["responses"]["200"]["content"]["application/json"]["schema"]
        schema["properties"]["ok"] = {"type": "string", "pattern": "^[A-Z][A-Z0-9_]{0,63}$"}
        self.write(str(reader.source.relative_to(self.root)), document, yaml=True)
        full = SourceSchemaReader(self.root, reader.source)
        cases, _ = source_response_probes(full, module)
        head = next(case["value"] for case in cases if case["method"] == "head" and case["role"] == "declared-media")
        validator = full.validator_at(full.source, "/paths/~1head/head/responses/200/content/application~1json/schema")
        self.assertTrue(validator.is_valid(head))
        self.assertFalse(validator.is_valid(dict(head, ok="lower")))


    def test_33_existing_ndjson_line_schema_is_a_typed_source_edge(self):
        spec = ROOT / "Platform/05-resource/spec/05-resource.api.openapi.yaml"
        reader = SourceSchemaReader(ROOT, spec)
        pointer = "/paths/~1buckets~1{sub}~1{unit}/get/responses/200/content/application~1x-ndjson/schema/x-line-schema"
        key = (spec, pointer, "#/components/schemas/BucketInfo", "schema")
        self.assertEqual(reader.edges[key], (spec, "/components/schemas/BucketInfo"))
        # The established extension is typed only in a Schema Object;
        # identically shaped instance/example data remains opaque.
        fixture = self.api(schemas={"Root": {"type": "object", "default": {
            "x-line-schema": {"$ref": "https://not-a-source.invalid/data"}}}})
        local = SourceSchemaReader(self.root, fixture)
        self.assertEqual(local.edges, {})


class SourceOperationIdentityControls(unittest.TestCase):
    """Current P06 Source identities and isolated checking guards; no generator or Go."""

    @classmethod
    def setUpClass(cls):
        cls.source = ROOT / "Platform/06-console/spec/06-console.api.openapi.yaml"
        cls.packet = SourceSchemaReader.P06_OPERATION_IDENTITY_INPUT
        cls.reader = SourceSchemaReader(ROOT, cls.source)
        # A normal physical current-Source baseline precedes every checking control.
        cls.baseline = cls.reader.operation_declarations()
        if len(cls.baseline) != 146:
            raise CheckingError("current146 identity baseline is incomplete")
        cls.raw_inputs = {}
        for name, expected in (("operation-map.json", SourceSchemaReader.P06_WITNESS_SHA256),
                               ("CURRENT-API-BINDING.json", SourceSchemaReader.P06_BINDING_SHA256)):
            raw = (cls.packet / name).read_bytes()
            if hashlib.sha256(raw).hexdigest() != expected:
                raise CheckingError("Source identity input changed after baseline")
            cls.raw_inputs[name] = raw
        cls.witness = json.loads(cls.raw_inputs["operation-map.json"])
        cls.binding = json.loads(cls.raw_inputs["CURRENT-API-BINDING.json"])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="source-operation-identity-")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def packet_copy(self):
        packet = self.directory / "identity-input"
        packet.mkdir(exist_ok=True)
        for name, raw in self.raw_inputs.items():
            path = packet / name
            if path.is_symlink() or path.is_dir():
                if path.is_symlink():
                    path.unlink()
                else:
                    path.rmdir()
            path.write_bytes(raw)
        return packet

    def test_00_actual_current146_keeps_original140_and_six_head_assignments(self):
        actual = {r["declaration"]: (r["symbol"], r["ordinal"], r["method"].upper()) for r in self.baseline}
        expected = {r["after_pointer"]: (r["actual_adapter_Op"], r["logical_ordinal_current146"], r["method"])
                    for r in self.binding["records"]}
        self.assertEqual(actual, expected)
        self.assertEqual(len({r["symbol"] for r in self.baseline}), 146)
        self.assertEqual({r["ordinal"] for r in self.baseline}, set(range(1, 147)))
        self.assertEqual(sum(r["member_of_original140"] for r in self.binding["records"]), 140)
        self.assertEqual(sum(r["ordinal"] > 140 for r in self.baseline), 6)

    def test_01_pathitem_parameters_keep_each_declaration_and_schema_base(self):
        items = [r for r in self.baseline if r["component"]]
        expected = {r["after_pointer"] for r in self.binding["records"]
                    if r["after_pointer"].startswith("/components/pathItems/")}
        self.assertEqual({r["declaration"] for r in items}, expected)
        self.assertEqual({r["component"] for r in items},
                         {"UnitsCollection", "UnitItem", "TableCollection", "TableItem", "PassRoot", "ConsoleFile"})
        inherited = []
        for record in items:
            for node, file, pointer in record["parameters"]:
                if pointer.startswith(record["item_pointer"] + "/parameters/"):
                    inherited.append(pointer)
                    prm, base = self.reader.parameter(node, file,
                        (record["symbol"], record["route"], record["method"]), (file, pointer))
                    self.assertEqual(file, self.source)
                    self.assertIs(self.reader.at(file, pointer, "parameter"), node)
                    if "schema" in prm:
                        coordinates = self.reader._locations(prm["schema"], base, "schema")
                        self.assertTrue(coordinates)
                        for schema_file, schema_pointer in coordinates:
                            self.assertIs(self.reader.at(schema_file, schema_pointer, "schema"), prm["schema"])
        self.assertTrue(inherited)

    def test_02_verified_external_copy_is_selected_without_a_source_sidecar(self):
        packet = self.packet_copy()
        sidecar = ROOT / "decisions/inbox/2026-11-07-p06-s08-source/operation-map.json"
        read_bytes = Path.read_bytes
        def no_source_sidecar(path):
            if path == sidecar:
                raise AssertionError("Source-root sidecar must not be consulted")
            return read_bytes(path)
        with patch.object(self.reader, "P06_OPERATION_IDENTITY_INPUT", packet), \
                patch.object(Path, "read_bytes", no_source_sidecar):
            self.assertEqual(self.reader.operation_declarations(), self.baseline)
        for name, raw in self.raw_inputs.items():
            self.assertEqual((packet / name).read_bytes(), raw)
        self.assertIn(b"b4073b39", self.raw_inputs["operation-map.json"])
        self.assertNotIn(SourceSchemaReader.P06_CURRENT_API_SHA256.encode(), self.raw_inputs["operation-map.json"])

    def test_03_missing_changed_and_nonregular_identity_inputs_are_checking_errors(self):
        packet = self.packet_copy()
        for name in self.raw_inputs:
            for variant in ("missing", "changed", "invalid-json", "directory", "symlink"):
                self.packet_copy()
                path = packet / name
                path.unlink()
                if variant == "changed":
                    path.write_bytes(self.raw_inputs[name] + b" ")
                elif variant == "invalid-json":
                    path.write_bytes(b"{")
                elif variant == "directory":
                    path.mkdir()
                elif variant == "symlink":
                    path.symlink_to(self.packet / name)
                with self.subTest(name=name, variant=variant), \
                        patch.object(self.reader, "P06_OPERATION_IDENTITY_INPUT", packet), self.assertRaises(CheckingError):
                    self.reader.operation_declarations()
        self.packet_copy()
        alias = self.directory / "packet-alias"
        alias.symlink_to(packet, target_is_directory=True)
        for path in (alias, Path("relative-input"), self.directory / "absent"):
            with self.subTest(packet=path), patch.object(self.reader, "P06_OPERATION_IDENTITY_INPUT", path), \
                    self.assertRaises(CheckingError):
                self.reader.operation_declarations()

    def test_04_changed_or_wrong_current_api_is_a_checking_error(self):
        # This narrow physical input guard does not parse/materialize another Source graph.
        root = self.directory / "owned-source"
        source = root / "Platform/06-console/spec/06-console.api.openapi.yaml"
        source.parent.mkdir(parents=True)
        raw = self.source.read_bytes()
        source.write_bytes(raw)
        reader = object.__new__(SourceSchemaReader)
        reader.root, reader.source = root, source
        reader.P06_OPERATION_IDENTITY_INPUT = self.packet_copy()
        self.assertEqual(len(reader._p06_operation_identities()), 146)
        source.write_bytes(raw + b"\n")
        with self.assertRaises(CheckingError):
            reader._p06_operation_identities()
        source.write_bytes(raw)
        wrong = source.with_name("other.api.openapi.yaml")
        source.rename(wrong)
        reader.source = wrong
        with self.assertRaises(CheckingError):
            reader._p06_operation_identities()
        reader.source = source
        with self.assertRaises(CheckingError):
            reader._p06_operation_identities()

    def test_05_bound_record_shape_types_counts_and_duplicates_are_checking_errors(self):
        self.assertEqual(len(self.reader._p06_identity_records(self.witness, self.binding)), 146)
        mutations = []
        for field, value in (("member_of_original140", 1), ("method", None),
                             ("logical_ordinal_current146", True), ("logical_ordinal_original140", True),
                             ("actual_adapter_Op", "OpWrong"), ("after_pointer", "/paths/~1wrong/get")):
            changed = copy.deepcopy(self.binding)
            changed["records"][0][field] = value
            mutations.append(changed)
        for field in ("after_pointer", "actual_adapter_Op", "logical_ordinal_current146"):
            changed = copy.deepcopy(self.binding)
            changed["records"][1][field] = changed["records"][0][field]
            mutations.append(changed)
        for variant in ("missing", "extra", "missing-field", "extra-field", "counts", "Source", "API", "witness"):
            changed = copy.deepcopy(self.binding)
            if variant == "missing":
                changed["records"].pop()
            elif variant == "extra":
                changed["records"].append(copy.deepcopy(changed["records"][0]))
            elif variant == "missing-field":
                del changed["records"][0]["method"]
            elif variant == "extra-field":
                changed["records"][0]["unexpected"] = True
            elif variant == "counts":
                changed["counts"]["current_total"] = 145
            elif variant == "Source":
                changed["Source_pin"] = "0" * 40
            elif variant == "API":
                changed["current_API"]["sha256"] = "0" * 64
            else:
                changed["immutable_original_witness"]["sha256"] = "0" * 64
            mutations.append(changed)
        for changed in mutations:
            with self.subTest(changed=changed["records"][:2]), self.assertRaises(CheckingError):
                self.reader._p06_identity_records(self.witness, changed)

    def test_06_original140_and_appended_head_changes_are_checking_errors(self):
        for variant in ("old-missing", "old-duplicate", "old-bool", "old-symbol", "head-symbol", "head-ordinal"):
            witness, binding = copy.deepcopy(self.witness), copy.deepcopy(self.binding)
            if variant == "old-missing":
                witness["records"].pop(0)
            elif variant == "old-duplicate":
                witness["records"][1] = copy.deepcopy(witness["records"][0])
            elif variant == "old-bool":
                witness["records"][0]["logical_ordinal_original140"] = True
            elif variant == "old-symbol":
                witness["records"][0]["actual_adapter_Op"] = "OpChanged"
            elif variant == "head-symbol":
                binding["records"][-1]["actual_adapter_Op"] = "OpChanged"
            else:
                binding["records"][-1]["logical_ordinal_current146"] = 140
            with self.subTest(variant=variant), self.assertRaises(CheckingError):
                self.reader._p06_identity_records(witness, binding)

    def test_07_missing_extra_and_changed_source_slots_are_checking_errors(self):
        original = self.reader.document(self.source)
        for variant in ("missing-operation", "extra-operation", "missing-PathItem"):
            doc = copy.deepcopy(original)
            if variant == "missing-operation":
                del doc["components"]["pathItems"]["UnitsCollection"]["get"]
            elif variant == "extra-operation":
                doc["components"]["pathItems"]["UnitsCollection"]["trace"] = {"responses": {"200": {"description": "ok"}}}
            else:
                del doc["components"]["pathItems"]["ConsoleFile"]
            # An explicitly injected owned document tests the enumerator's guard,
            # separately from physical input authentication and semantic comparison.
            real_document = self.reader.document
            def owned_document(file):
                return doc if Path(file) == self.source else real_document(file)
            with self.subTest(variant=variant), patch.object(self.reader, "document", side_effect=owned_document), \
                    self.assertRaises(CheckingError):
                self.reader.operation_declarations()


for _lesson, _slug in LESSONS.items():
    _name = "DoorBodies_" + _slug
    globals()[_name] = type(_name, (DoorBodiesBase, unittest.TestCase), {"LESSON": _lesson, "SLUG": _slug})


if __name__ == "__main__":
    unittest.main()
