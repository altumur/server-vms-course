"""Generate an OpenAPI door (ADR-0125 generator 2), originally Platform/01-store/spec/01-store.api.openapi.yaml.

Read OpenAPI 3.1 with the standard-library YAML subset loader yamlsub.py. Emit a standard-library Go 1.22 apidoor package: generated door.go and copied doorrt/go/runtime.go. Generate route/method dispatch; form-style query parsing with required/repeated/scalar checks; response types and JSON encoding in properties order with map keys in byte order and no extra fields; operation/status binding; *Fault types and Refuse construction; chk* schema checks and Decode* for requests outside write-checks.tsv; and Handler/Dispatch for handwritten IO.

Do not generate N3 core logic, HTTP framing/N2.1 limits, identity or frame->route->identity->body ordering. Cmd/BatchCmd belong to write-checks.tsv and generator 1. description/summary prose is not interpreted.

Form/HTTP rules: unknown paths use common 404 schemas or generation refuses; an unsupported method gives 405 if every operation of that path declares it, otherwise 404 (RFC 9110 15.5.6). Response headers use optional typed values for string/integer schemas, with per-operation const and bounds checks; all-constant headers retain boolean switches. Integers exclude fraction/exponent syntax, so 1.0 is not integer. minLength/maxLength/pattern require UTF-8; a bare query string accepts arbitrary bytes because OpenAPI declares no query encoding.

  python tools/normgen/gen_door.py [openapi.yaml [output-directory]]"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import yamlsub  # noqa: E402
import lesson  # noqa: E402 -- lesson selection (ADR-0125 addendum (5), item 2)
L = lesson.CURRENT

DEFAULT_SPEC = L.openapi
DEFAULT_OUT = L.out
RUNTIME = HERE / "doorrt/go/runtime.go"
# ADR-0125 addendum (1), item 3: one form, one generator. write-checks.tsv judges write-command bodies;
# the door generator skips those schemas and everything reachable exclusively from them.
WRITECHECK = ("Cmd", "BatchCmd")
METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
ANNOTATIONS = {"description", "summary", "title", "$comment", "examples", "deprecated"}
SCHEMA_KEYS = {"$ref", "type", "properties", "required", "additionalProperties", "propertyNames", "items", "minItems",
               "maxItems", "minLength", "maxLength", "pattern", "enum", "const", "minimum", "maximum",
               "exclusiveMinimum", "exclusiveMaximum", "oneOf", "anyOf", "allOf", "not", "if", "then", "else",
               "unevaluatedProperties"} | ANNOTATIONS
JSON_TYPES = ("string", "integer", "number", "boolean", "null", "object", "array")
INT64_MAX = 2 ** 63 - 1
UINT64_MAX = 2 ** 64 - 1


class GenError(Exception):
    """Generation refusal: OpenAPI is outside the subset or the form contradicts itself."""


def camel(name):
    parts = re.split(r"[^A-Za-z0-9]+", name)
    out = "".join(p[:1].upper() + p[1:] for p in parts if p)
    if not out or not out[0].isalpha():
        raise GenError(f"name {name!r} does not give a Go identifier")
    return out


def go_str(s):
    return json.dumps(s, ensure_ascii=False)


def go_raw(s):
    return f"`{s}`" if "`" not in s else go_str(s)


def go_value(v):
    """Convert a JSON const/enum value into a Go any expression."""
    if v is None:
        return "nil"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return f"json.Number({go_str(str(v))})"
    if isinstance(v, float):
        return f"json.Number({go_str(repr(v))})"
    if isinstance(v, str):
        return go_str(v)
    raise GenError(f"const/enum value {v!r}: only scalars are in the subset")


def trivial(node):
    return isinstance(node, dict) and not (set(node) - ANNOTATIONS)


# ---------------------------------------------------------------- OpenAPI model

class Param:
    def __init__(self, name, required, schema):
        self.name, self.required, self.schema = name, required, schema


class Resp:
    def __init__(self, code, media, schemas, headers, header_schemas=None, required_headers=()):
        self.code, self.media, self.schemas, self.headers = code, media, schemas, headers
        self.header_schemas = header_schemas or {}
        self.required_headers = list(required_headers)


class Op:
    def __init__(self, name, method, path):
        self.name, self.method, self.path = name, method, path
        self.params, self.body, self.body_required, self.responses = [], None, False, {}


class Spec:
    def __init__(self, doc, name="openapi"):
        self.name = name
        if not isinstance(doc, dict) or not str(doc.get("openapi", "")).startswith("3.1"):
            raise GenError(f"{name}: openapi 3.1 expected")
        comps = doc.get("components") or {}
        self.schemas = dict(comps.get("schemas") or {})
        self.comp_responses = comps.get("responses") or {}
        self.comp_params = comps.get("parameters") or {}
        for key in comps:
            if key not in ("schemas", "responses", "parameters"):
                raise GenError(f"{name}: components.{key} is not in the subset")
        self.inline = {}               # Name -> inline response schema.
        self.ops = []
        names = set()
        for path, item in (doc.get("paths") or {}).items():
            if not isinstance(path, str) or not path.startswith("/") or "{" in path:
                raise GenError(f"{name}: path {path!r}: only literal paths are in the subset")
            methods = [m for m in item if m in METHODS]
            for key in item:
                if key not in METHODS and key not in ANNOTATIONS:
                    raise GenError(f"{name}: {path}: key {key!r} is not in the subset")
            for method in methods:
                o = item[method]
                where = f"{name}: {method.upper()} {path}"
                op_name = camel(o["operationId"]) if "operationId" in o else \
                    camel(path.rstrip("/").split("/")[-1]) + (camel(method) if len(methods) > 1 else "")
                if op_name in names:
                    raise GenError(f"{where}: operation name {op_name} repeats")
                names.add(op_name)
                op = Op(op_name, method.upper(), path)
                for key in o:
                    if key not in {"parameters", "requestBody", "responses", "operationId"} | ANNOTATIONS:
                        raise GenError(f"{where}: key {key!r} is not in the subset")
                for p in o.get("parameters") or []:
                    op.params.append(self.param(p, where))
                if "requestBody" in o:
                    rb = o["requestBody"]
                    content = rb.get("content") or {}
                    if list(content) != ["application/json"]:
                        raise GenError(f"{where}: requestBody: only application/json is in the subset")
                    op.body = self.union_names(content["application/json"]["schema"], where + ": requestBody")
                    op.body_required = bool(rb.get("required"))
                for code, r in (o.get("responses") or {}).items():
                    op.responses[self.code(code, where)] = self.response(op, self.code(code, where), r, where)
                if not op.responses:
                    raise GenError(f"{where}: no responses")
                self.ops.append(op)
        if not self.ops:
            raise GenError(f"{name}: no operations")
        for sname, s in self.schemas.items():
            self.walk(s, f"#/components/schemas/{sname}")
        for sname, s in self.inline.items():
            self.walk(s, f"response {sname}")
        for op in self.ops:
            for p in op.params:
                self.walk(p.schema, f"{op.method} {op.path} query {p.name}")
            for response in op.responses.values():
                for header, schema in response.header_schemas.items():
                    self.walk(schema, f"{op.method} {op.path} {response.code} header {header}")

    @staticmethod
    def code(code, where):
        text = str(code)
        if not re.fullmatch(r"[1-5][0-9][0-9]", text):
            raise GenError(f"{where}: response code {code!r} is not in the subset (no ranges, no default)")
        return int(text)

    def ref_name(self, ref, where, kind="schemas"):
        m = re.fullmatch(r"#/components/%s/([A-Za-z0-9_.-]+)" % kind, ref)
        if not m:
            raise GenError(f"{where}: $ref {ref!r} is not a local components/{kind} reference")
        return m[1]

    def param(self, p, where):
        if "$ref" in p:
            p = self.comp_params[self.ref_name(p["$ref"], where, "parameters")]
        for key in p:
            if key not in {"name", "in", "required", "schema", "style", "explode"} | ANNOTATIONS:
                raise GenError(f"{where}: parameter key {key!r} is not in the subset")
        if p.get("in") != "query":
            raise GenError(f"{where}: parameter {p.get('name')!r}: only in: query is in the subset")
        if p.get("style", "form") != "form" or p.get("explode", True) is not True:
            raise GenError(f"{where}: parameter {p['name']!r}: only style form, explode true")
        schema = p.get("schema")
        if schema is None:
            raise GenError(f"{where}: parameter {p['name']!r} without schema")
        base = self.resolve(schema, where)
        if base.get("type") != "string":
            raise GenError(f"{where}: parameter {p['name']!r}: only string parameters are in the subset")
        return Param(p["name"], bool(p.get("required")), schema)

    def resolve(self, node, where):
        seen = set()
        while "$ref" in node:
            name = self.ref_name(node["$ref"], where)
            if name in seen or name not in self.schemas:
                raise GenError(f"{where}: $ref {node['$ref']!r} is not resolvable")
            seen.add(name)
            node = self.schemas[name]
        return node

    def union_names(self, node, where):
        """Extract schema names from {$ref} or {oneOf: [{$ref}, ...]}."""
        if set(node) - ANNOTATIONS == {"$ref"}:
            return [self.ref_name(node["$ref"], where)]
        if set(node) - ANNOTATIONS == {"oneOf"} and all(set(x) - ANNOTATIONS == {"$ref"} for x in node["oneOf"]):
            return [self.ref_name(x["$ref"], where) for x in node["oneOf"]]
        return None

    def response(self, op, code, r, where):
        if "$ref" in r:
            r = self.comp_responses[self.ref_name(r["$ref"], where, "responses")]
        for key in r:
            if key not in {"content", "headers"} | ANNOTATIONS:
                raise GenError(f"{where}: {code}: key {key!r} is not in the subset")
        content = r.get("content") or {}
        if len(content) > 1:
            raise GenError(f"{where}: {code}: one media type per response")
        media, schemas = None, []
        if content:
            media = next(iter(content))
            schema = content[media].get("schema")
            if schema is None:
                raise GenError(f"{where}: {code}: content without schema")
            names = self.union_names(schema, f"{where}: {code}")
            if names is None:
                names = [f"{op.name}{code}"]
                self.inline[names[0]] = schema
            schemas = names
        headers, header_schemas, required_headers = {}, {}, []
        for hname, h in (r.get("headers") or {}).items():
            hs = h.get("schema") or {}
            base = self.resolve(hs, f"{where}: {code}: header {hname}")
            if "const" in base:
                if isinstance(base["const"], (dict, list)) or base["const"] is None:
                    raise GenError(f"{where}: {code}: header {hname}: a scalar const value is required")
            elif base.get("type") not in ("string", "integer"):
                raise GenError(f"{where}: {code}: header {hname}: a scalar const, string or integer schema is required")
            if type(h.get("required", False)) is not bool:
                raise GenError(f"{where}: {code}: header {hname}: required must be boolean")
            headers[hname] = base.get("const")
            header_schemas[hname] = hs
            if h.get("required", False):
                required_headers.append(hname)
        return Resp(code, media, schemas, headers, header_schemas, required_headers)

    def walk(self, node, where):
        """Reject unknown schema keywords so a constraint cannot disappear silently."""
        if node is True or node is False:
            raise GenError(f"{where}: boolean schemas are not in the subset")
        if not isinstance(node, dict):
            raise GenError(f"{where}: schema is not an object")
        for key in node:
            if key not in SCHEMA_KEYS:
                raise GenError(f"{where}: keyword {key!r} is not in the subset")
        t = node.get("type")
        for x in (t if isinstance(t, list) else [t] if t is not None else []):
            if x not in JSON_TYPES:
                raise GenError(f"{where}: type {x!r}")
        for key in ("properties",):
            for p, sub in (node.get(key) or {}).items():
                self.walk(sub, f"{where}/{key}/{p}")
        for key in ("items", "propertyNames", "not", "if", "then", "else"):
            if key in node:
                self.walk(node[key], f"{where}/{key}")
        if isinstance(node.get("additionalProperties"), dict):
            self.walk(node["additionalProperties"], f"{where}/additionalProperties")
        elif "additionalProperties" in node and node["additionalProperties"] is not False:
            raise GenError(f"{where}: additionalProperties: false or a schema")
        if "unevaluatedProperties" in node and node["unevaluatedProperties"] not in (True, False):
            raise GenError(f"{where}: unevaluatedProperties: true or false")
        for key in ("oneOf", "anyOf", "allOf"):
            for i, sub in enumerate(node.get(key) or []):
                self.walk(sub, f"{where}/{key}/{i}")
        if "pattern" in node:
            check_pattern(node["pattern"], where)
        if "$ref" in node:
            self.resolve(node, where)

    def all_schemas(self):
        return {**self.schemas, **self.inline}

    def excluded(self):
        """Schemas reachable exclusively from WRITECHECK roots."""
        def refs(node, out):
            if isinstance(node, dict):
                if "$ref" in node:
                    out.add(self.ref_name(node["$ref"], "ref"))
                for v in node.values():
                    refs(v, out)
            elif isinstance(node, list):
                for v in node:
                    refs(v, out)
            return out

        def closure(roots):
            seen, todo = set(), list(roots)
            while todo:
                n = todo.pop()
                if n in seen:
                    continue
                seen.add(n)
                todo.extend(refs(self.all_schemas()[n], set()))
            return seen
        for n in WRITECHECK:
            if n not in self.schemas:
                raise GenError(f"{self.name}: schema {n} (write-checks.tsv) is absent")
        wc = closure(WRITECHECK)
        roots = [n for n in self.all_schemas() if n not in wc]
        for op in self.ops:
            roots += [n for n in op.body or [] if n not in WRITECHECK]
            roots += [n for r in op.responses.values() for n in r.schemas]
            roots += [x for p in op.params for x in refs(p.schema, set())]
        keep = closure(roots)
        return wc - keep


def string_bound(spec, node, seen=None):
    """Check whether the schema, following refs, has minLength, maxLength or pattern constraints."""
    seen = set() if seen is None else seen
    if isinstance(node, dict):
        if "$ref" in node:
            name = spec.ref_name(node["$ref"], "ref")
            if name not in seen:
                seen.add(name)
                if string_bound(spec, spec.schemas[name], seen):
                    return True
        if {"minLength", "maxLength", "pattern"} & set(node):
            return True
        return any(string_bound(spec, v, seen) for k, v in node.items() if k not in ANNOTATIONS)
    if isinstance(node, list):
        return any(string_bound(spec, v, seen) for v in node)
    return False


def check_pattern(p, where):
    """ECMA-262 and RE2 differ on \\s, \\w, \\b, backreferences and lookaround; reject those patterns."""
    q = p.replace(r"[\s\S]", "")
    if re.search(r"\\[sSwWbB1-9]|\(\?[=!<]", q):
        raise GenError(f"{where}: pattern {p!r} uses a construct where ECMA-262 and Go RE2 differ")
    try:
        re.compile(p)
    except re.error as exc:
        raise GenError(f"{where}: pattern {p!r}: {exc}")


# ---------------------------------------------------------------- Go types

class Gen:
    def __init__(self, spec):
        self.spec = spec
        self.schemas = spec.all_schemas()
        self.excluded = spec.excluded()
        self.names = [n for n in self.schemas if n not in self.excluded]
        self.kinds = {}            # Schema name -> struct, union, variants or scalar.
        self.structs = {}          # Go type name -> (schema, SchemaName name, checker function path).
        self.unions = {}           # Interface name -> member type names.
        self.member_of = {}        # Type -> interfaces.
        self.checks = []           # Checker functions as Go source lines.
        self.check_names = {}      # id(node) -> function name.
        self.regexps = []
        self.builders = {}         # Go type expression -> map/slice constructor function name.
        self.builder_src = []
        for n in self.names:
            self.kinds[n] = self.classify(n, self.schemas[n])

    # Schema classes.

    def classify(self, name, s):
        where = f"schema {name}"
        keys = set(s) - ANNOTATIONS
        if keys == {"oneOf"} and all(set(x) - ANNOTATIONS == {"$ref"} for x in s["oneOf"]):
            return "union"
        if "oneOf" in s and keys <= {"oneOf", "unevaluatedProperties", "type"} and all(
                isinstance(x, dict) and x.get("type") == "object" and "$ref" not in x for x in s["oneOf"]):
            return "variants"
        if s.get("type") == "object" and not ({"oneOf", "anyOf", "not"} & keys):
            if isinstance(s.get("additionalProperties"), dict) and not s.get("properties"):
                raise GenError(f"{where}: a named map schema is not in the subset")
            return "struct"
        if self.scalar_type(s, where, quiet=True):
            return "scalar"
        raise GenError(f"{where}: neither an object, a union of references, object variants nor a scalar")

    def scalar_type(self, node, where, quiet=False):
        """Map a scalar schema to a Go type (string, int64, uint64, float64, bool), or None."""
        node = self.spec.resolve(node, where)
        if "const" in node:
            c = node["const"]
            return {str: "string", bool: "bool", int: "int64", float: "float64"}.get(type(c))
        if "enum" in node and all(isinstance(x, str) for x in node["enum"]):
            return "string"
        t = node.get("type")
        if t == "string":
            return "string"
        if t == "integer":
            if node.get("maximum", 0) > INT64_MAX and node.get("minimum", -1) >= 0:
                if node["maximum"] > UINT64_MAX:
                    raise GenError(f"{where}: maximum beyond uint64")
                return "uint64"
            if node.get("maximum", 0) > INT64_MAX or node.get("minimum", 0) < -INT64_MAX - 1:
                raise GenError(f"{where}: integer bounds beyond int64")
            return "int64"
        if t == "number":
            return "float64"
        if t == "boolean":
            return "bool"
        for key in ("anyOf", "oneOf"):
            if key in node and set(node) - ANNOTATIONS == {key}:
                kinds = {self.scalar_type(x, where, quiet=True) for x in node[key]}
                if len(kinds) == 1 and None not in kinds:
                    return kinds.pop()
        if quiet:
            return None
        raise GenError(f"{where}: not a scalar of the subset")

    def ftype(self, node, owner, prop, where):
        """Describe a field type: ('const', value), ('scalar', go), ('struct', name), ('iface', name), ('map', element), ('slice', element), or ('any', )."""
        if trivial(node):
            return ("any",)
        if "$ref" in node and set(node) - ANNOTATIONS == {"$ref"}:
            name = self.spec.ref_name(node["$ref"], where)
            if name in self.excluded:
                raise GenError(f"{where}: reference to {name}, judged by write-checks.tsv")
            kind = self.kinds[name]
            if kind == "struct":
                return ("struct", name)
            if kind in ("union", "variants"):
                return ("iface", name)
            return ("scalar", self.scalar_type(node, where))
        if "const" in node:
            return ("const", node["const"])
        if node.get("type") == "null":
            return ("const", None)
        if isinstance(node.get("type"), list):
            raise GenError(f"{where}: a field of several types is not in the subset of the door")
        if node.get("type") == "array":
            return ("slice", self.ftype(node.get("items", {}), owner, prop + "Item", where + "/items"))
        if node.get("type") == "object":
            if node.get("properties"):
                tname = owner + camel(prop)
                self.add_struct(tname, node, owner, where)
                return ("struct", tname)
            add = node.get("additionalProperties")
            if isinstance(add, dict):
                return ("map", self.ftype(add, owner, prop + "Value", where + "/additionalProperties"))
            return ("map", ("any",))
        st = self.scalar_type(node, where, quiet=True)
        if st:
            return ("scalar", st)
        raise GenError(f"{where}: field schema is not in the subset")

    def goexpr(self, t):
        k = t[0]
        if k == "scalar":
            return t[1]
        if k in ("struct", "iface"):
            return t[1]
        if k == "map":
            return "map[string]" + self.goexpr(t[1])
        if k == "slice":
            return "[]" + self.goexpr(t[1])
        if k == "any":
            return "any"
        raise GenError(f"no Go type for {t}")

    def add_struct(self, tname, node, schema_name, where):
        if tname in self.structs:
            raise GenError(f"{where}: Go type {tname} repeats")
        self.structs[tname] = (node, schema_name, where)

    # Schema checks.

    def chk(self, node, fname, where):
        """Generate a schema-node checker and return its name, or None for an unconstrained node."""
        if trivial(node):
            return None
        if set(node) - ANNOTATIONS == {"$ref"}:
            name = self.spec.ref_name(node["$ref"], where)
            if name in self.excluded:
                raise GenError(f"{where}: reference to {name}, judged by write-checks.tsv")
            return "chk" + name
        key = id(node)
        if key in self.check_names:
            return self.check_names[key]
        self.check_names[key] = fname
        body = []
        s = node
        if "$ref" in s:
            body.append(f"if e := {self.chk({'$ref': s['$ref']}, '', where)}(v, at); e != nil {{\nreturn e\n}}")
        if "type" in s:
            ts = s["type"] if isinstance(s["type"], list) else [s["type"]]
            test = " || ".join(f"is{camel(t)}(v)" for t in ts)
            body.append(f"if !({test}) {{\nreturn violation(at, \"type\")\n}}")
        if "const" in s:
            body.append(f"if !equalJSON(v, {go_value(s['const'])}) {{\nreturn violation(at, \"const\")\n}}")
        if "enum" in s:
            test = " || ".join(f"equalJSON(v, {go_value(x)})" for x in s["enum"]) or "false"
            body.append(f"if !({test}) {{\nreturn violation(at, \"enum\")\n}}")
        strs = [k for k in ("minLength", "maxLength", "pattern") if k in s]
        if strs:
            inner = ["if !utf8.ValidString(s) {\nreturn violation(at, \"utf8\")\n}"]
            if "minLength" in s:
                inner.append(f"if runeCount(s) < {int(s['minLength'])} {{\nreturn violation(at, \"minLength\")\n}}")
            if "maxLength" in s:
                inner.append(f"if runeCount(s) > {int(s['maxLength'])} {{\nreturn violation(at, \"maxLength\")\n}}")
            if "pattern" in s:
                re_name = f"re{len(self.regexps)}"
                self.regexps.append((re_name, s["pattern"]))
                inner.append(f"if !{re_name}.MatchString(s) {{\nreturn violation(at, \"pattern\")\n}}")
            body.append("if s, ok := v.(string); ok {\n" + "\n".join(inner) + "\n}")
        nums = [(k, op) for k, op in (("minimum", "< 0"), ("maximum", "> 0"), ("exclusiveMinimum", "<= 0"),
                                      ("exclusiveMaximum", ">= 0")) if k in s]
        if nums:
            inner = []
            for k, op in nums:
                bound = s[k]
                if isinstance(bound, bool) or not isinstance(bound, (int, float)):
                    raise GenError(f"{where}: {k} is not a number")
                inner.append(f"if c, _ := cmpBound(v, {go_str(repr(bound) if isinstance(bound, float) else str(bound))}); "
                             f"c {op} {{\nreturn violation(at, \"{k}\")\n}}")
            body.append("if isNumber(v) {\n" + "\n".join(inner) + "\n}")
        obj = []
        props = s.get("properties") or {}
        for r in s.get("required") or []:
            obj.append(f"if _, ok := m[{go_str(r)}]; !ok {{\nreturn violation(child(at, {go_str(r)}), \"required\")\n}}")
        for p, sub in props.items():
            f = self.chk(sub, fname + "_p" + camel(p), f"{where}/properties/{p}")
            if f:
                obj.append(f"if x, ok := m[{go_str(p)}]; ok {{\nif e := {f}(x, child(at, {go_str(p)})); e != nil {{\n"
                           f"return e\n}}\n}}")
        add = s.get("additionalProperties")
        names = s.get("propertyNames")
        if add is False:
            if props:
                cases = ", ".join(go_str(p) for p in props)
                obj.append(f"for _, k := range sortedKeys(m) {{\nswitch k {{\ncase {cases}:\ndefault:\n"
                           f"return violation(child(at, k), \"additionalProperties\")\n}}\n}}")
            else:
                obj.append("for _, k := range sortedKeys(m) {\nreturn violation(child(at, k), \"additionalProperties\")\n}")
        elif isinstance(add, dict):
            f = self.chk(add, fname + "_add", where + "/additionalProperties")
            if f:
                skip = ""
                if props:
                    skip = f"switch k {{\ncase {', '.join(go_str(p) for p in props)}:\ncontinue\n}}\n"
                obj.append(f"for _, k := range sortedKeys(m) {{\n{skip}if e := {f}(m[k], child(at, k)); e != nil {{\n"
                           f"return e\n}}\n}}")
        if names is not None:
            f = self.chk(names, fname + "_names", where + "/propertyNames")
            if f:
                obj.append(f"for _, k := range sortedKeys(m) {{\nif e := {f}(k, child(at, k)); e != nil {{\n"
                           f"return violation(child(at, k), \"propertyNames\")\n}}\n}}")
        if s.get("unevaluatedProperties") is False:
            branches = [self.spec.resolve(x, where) for x in s.get("oneOf") or []]
            closed = add is False or (branches and all(b.get("additionalProperties") is False for b in branches)
                                      and not ({"anyOf", "allOf", "if"} & set(s)))
            if not closed:
                raise GenError(f"{where}: unevaluatedProperties: false is in the subset only where the object "
                               f"or every oneOf branch is closed")
        if obj:
            body.append("if m, ok := v.(map[string]any); ok {\n" + "\n".join(obj) + "\n}")
        arr = []
        if "minItems" in s:
            arr.append(f"if len(a) < {int(s['minItems'])} {{\nreturn violation(at, \"minItems\")\n}}")
        if "maxItems" in s:
            arr.append(f"if len(a) > {int(s['maxItems'])} {{\nreturn violation(at, \"maxItems\")\n}}")
        if "items" in s:
            f = self.chk(s["items"], fname + "_items", where + "/items")
            if f:
                arr.append(f"for i, x := range a {{\nif e := {f}(x, index(at, i)); e != nil {{\nreturn e\n}}\n}}")
        if arr:
            body.append("if a, ok := v.([]any); ok {\n" + "\n".join(arr) + "\n}")
        for i, sub in enumerate(s.get("allOf") or []):
            f = self.chk(sub, f"{fname}_all{i + 1}", f"{where}/allOf/{i}")
            if f:
                body.append(f"if e := {f}(v, at); e != nil {{\nreturn e\n}}")
        if "anyOf" in s:
            fs = [self.chk(sub, f"{fname}_any{i + 1}", f"{where}/anyOf/{i}") for i, sub in enumerate(s["anyOf"])]
            if None not in fs:
                body.append(f"if {' && '.join(f'{f}(v, at) != nil' for f in fs)} {{\nreturn violation(at, \"anyOf\")\n}}")
        if "oneOf" in s:
            fs = [self.chk(sub, f"{fname}_one{i + 1}", f"{where}/oneOf/{i}") for i, sub in enumerate(s["oneOf"])]
            lines = ["n := 0"]
            for f in fs:
                lines.append("n++" if f is None else f"if {f}(v, at) == nil {{\nn++\n}}")
            lines.append("if n != 1 {\nreturn violation(at, \"oneOf\")\n}")
            body.append("{\n" + "\n".join(lines) + "\n}")
        if "not" in s:
            f = self.chk(s["not"], fname + "_not", where + "/not")
            body.append("return violation(at, \"not\")" if f is None else
                        f"if {f}(v, at) == nil {{\nreturn violation(at, \"not\")\n}}")
        if "if" in s and ("then" in s or "else" in s):
            fi = self.chk(s["if"], fname + "_if", where + "/if")
            ft = self.chk(s["then"], fname + "_then", where + "/then") if "then" in s else None
            fe = self.chk(s["else"], fname + "_else", where + "/else") if "else" in s else None
            cond = "true" if fi is None else f"{fi}(v, at) == nil"
            then = f"if e := {ft}(v, at); e != nil {{\nreturn e\n}}" if ft else ""
            els = f" else {{\nif e := {fe}(v, at); e != nil {{\nreturn e\n}}\n}}" if fe else ""
            if then or els:
                body.append(f"if {cond} {{\n{then}\n}}{els}")
        self.checks.append(f"// {fname} — {where}.\nfunc {fname}(v any, at string) *Violation {{\n"
                           + "\n".join(body) + "\nreturn nil\n}")
        return fname

    # Construct the typed value after validation.

    def conv(self, t, expr):
        k = t[0]
        if k == "scalar":
            return {"string": f"{expr}.(string)", "bool": f"{expr}.(bool)", "int64": f"toInt64({expr})",
                    "uint64": f"toUint64({expr})", "float64": f"toFloat64({expr})"}[t[1]]
        if k in ("struct", "iface"):
            return f"build{t[1]}({expr})"
        if k == "any":
            return expr
        if k in ("map", "slice"):
            go = self.goexpr(t)
            if go not in self.builders:
                fn = "build" + camel(go.replace("[]", "Slice ").replace("map[string]", "Map "))
                self.builders[go] = fn
                inner = self.conv(t[1], "x")
                if k == "map":
                    src = (f"func {fn}(v any) {go} {{\nm := v.(map[string]any)\nout := make({go}, len(m))\n"
                           f"for k, x := range m {{\nout[k] = {inner}\n}}\nreturn out\n}}")
                else:
                    src = (f"func {fn}(v any) {go} {{\na := v.([]any)\nout := make({go}, 0, len(a))\n"
                           f"for _, x := range a {{\nout = append(out, {inner})\n}}\nreturn out\n}}")
                self.builder_src.append(src)
            return f"{self.builders[go]}({expr})"
        raise GenError(f"no conversion for {t}")

    # JSON encoding.

    def enc(self, t, expr, depth=0):
        k = t[0]
        if k == "scalar":
            return {"string": f"b = appendString(b, {expr})", "bool": f"b = strconv.AppendBool(b, {expr})",
                    "int64": f"b = strconv.AppendInt(b, {expr}, 10)", "uint64": f"b = strconv.AppendUint(b, {expr}, 10)",
                    "float64": f"b = appendFloat(b, {expr})"}[t[1]]
        if k == "struct":
            return f"b = {expr}.appendJSON(b)"
        if k == "iface":
            return f"if {expr} == nil {{\nb = append(b, \"null\"...)\n}} else {{\nb = {expr}.appendJSON(b)\n}}"
        if k == "any":
            return f"b = appendAny(b, {expr})"
        if k == "const":
            return f"b = append(b, {go_str(json.dumps(t[1], ensure_ascii=False, separators=(',', ':')))}...)"
        d = depth + 1
        if k == "map":
            return (f"{{\nkeys{d} := make([]string, 0, len({expr}))\nfor k := range {expr} {{\n"
                    f"keys{d} = append(keys{d}, k)\n}}\nsort.Strings(keys{d})\nb = append(b, '{{')\n"
                    f"for i, k := range keys{d} {{\nif i > 0 {{\nb = append(b, ',')\n}}\nb = appendString(b, k)\n"
                    f"b = append(b, ':')\n{self.enc(t[1], f'{expr}[k]', d)}\n}}\nb = append(b, '}}')\n}}")
        if k == "slice":
            return (f"b = append(b, '[')\nfor i{d}, e{d} := range {expr} {{\nif i{d} > 0 {{\nb = append(b, ',')\n}}\n"
                    f"{self.enc(t[1], f'e{d}', d)}\n}}\nb = append(b, ']')")
        raise GenError(f"no encoder for {t}")


def struct_source(g, tname, node, schema_name, where):
    props = node.get("properties") or {}
    required = node.get("required") or []
    for r in required:
        if r not in props:
            raise GenError(f"{where}: required {r!r} without a property (not in the subset of typed answers)")
    fields, enc, build = [], [], []
    seen = set()
    for p, sub in props.items():
        fname = camel(p)
        if fname in seen:
            raise GenError(f"{where}: field {fname} repeats")
        seen.add(fname)
        t = g.ftype(sub, tname, p, f"{where}/properties/{p}")
        req = p in required
        lit = None
        if t[0] == "const":
            lit = g.enc(t, "")
            if req:
                fields.append(f"// {p}: always {json.dumps(t[1], ensure_ascii=False)} (const, required)")
                enc.append(f"b = field(b, &n, {go_str(p)})\n{lit}")
            else:
                fields.append(f"{fname} bool // {p}: true — the field is sent with {json.dumps(t[1], ensure_ascii=False)}")
                enc.append(f"if x.{fname} {{\nb = field(b, &n, {go_str(p)})\n{lit}\n}}")
                build.append(f"_, x.{fname} = m[{go_str(p)}]")
            continue
        go = g.goexpr(t)
        if req:
            fields.append(f"{fname} {go} // {p}: required")
            enc.append(f"b = field(b, &n, {go_str(p)})\n{g.enc(t, 'x.' + fname)}")
            build.append(f"x.{fname} = {g.conv(t, f'm[{go_str(p)}]')}")
        else:
            fields.append(f"{fname} *{go} // {p}: optional, nil — absent")
            enc.append(f"if x.{fname} != nil {{\nb = field(b, &n, {go_str(p)})\n{g.enc(t, '(*x.' + fname + ')')}\n}}")
            build.append(f"if y, ok := m[{go_str(p)}]; ok {{\nt := {g.conv(t, 'y')}\nx.{fname} = &t\n}}")
    doc = f"// {tname} — {where}."
    src = [doc, f"type {tname} struct {{"] + fields + ["}", ""]
    src.append(f'// SchemaName returns the OpenAPI schema name.\nfunc ({tname}) SchemaName() string {{ return {go_str(schema_name)} }}\n')
    src.append(f"func (x {tname}) appendJSON(b []byte) []byte {{\nb = append(b, '{{')\n"
               + ("n := 0\n" if enc else "") + "\n".join(enc) + "\nreturn append(b, '}')\n}\n")
    if build:
        src.append(f"func build{tname}(v any) {tname} {{\nm := v.(map[string]any)\nvar x {tname}\n" + "\n".join(build)
                   + "\nreturn x\n}\n")
    else:
        src.append(f"func build{tname}(v any) {tname} {{\n_ = v\nreturn {tname}{{}}\n}}\n")
    return "\n".join(src)


# ---------------------------------------------------------------- package

def build_go(spec, rel, sha):
    g = Gen(spec)
    types, bodies = [], {}
    # Check all schemas except write-checks.
    for n in g.names:
        where = f"#/components/schemas/{n}" if n in spec.schemas else f"response {n}"
        got = g.chk(g.schemas[n], "chk" + n, where)
        if got != "chk" + n:                 # Named checker for a ref alias, unconstrained schema or shared node: checks, unions and Decode call chk<Name>
            # by schema name (Codex review C3).
            g.checks.append(f"// chk{n} — {where}: " + (f"the alias of {got[3:]}" if got else "no constraint") + ".\n"
                            f"func chk{n}(v any, at string) *Violation {{\n"
                            + (f"return {got}(v, at)" if got else "_, _ = v, at\nreturn nil") + "\n}\n")
    # Types.
    for n in g.names:
        kind, s = g.kinds[n], g.schemas[n]
        where = f"#/components/schemas/{n}" if n in spec.schemas else f"response {n}"
        if kind == "struct":
            g.add_struct(n, s, n, where)
        elif kind == "variants":
            members = []
            for i, b in enumerate(s["oneOf"], 1):
                tname = f"{n}{i}"
                g.add_struct(tname, b, n, f"{where}/oneOf/{i - 1}")
                members.append(tname)
            g.unions[n] = members
        elif kind == "union":
            members = [spec.ref_name(x["$ref"], where) for x in s["oneOf"]]
            for m in members:
                if g.kinds.get(m) != "struct":
                    raise GenError(f"{where}: member {m} of a union is not an object schema")
            g.unions[n] = members
    for u, members in g.unions.items():
        for m in members:
            g.member_of.setdefault(m, []).append(u)
    done = set()
    while len(done) < len(g.structs):              # add_struct grows when nested objects are discovered.
        for tname in list(g.structs):
            if tname not in done:
                node, sname, where = g.structs[tname]
                types.append(struct_source(g, tname, node, sname, where))
                for u in g.member_of.get(tname, []):
                    types.append(f"func ({tname}) is{u}() {{}}\n")
                done.add(tname)
    for u, members in g.unions.items():
        kind = g.kinds[u]
        types.append(f"// {u} -- one of these schemas: {', '.join(members)}.\ntype {u} interface {{\nBody\nis{u}()\n}}\n")
        if kind == "variants":
            fs = [g.check_names[id(b)] for b in g.schemas[u]["oneOf"]]
        else:
            fs = ["chk" + m for m in members]
        lines = [f"if {f}(v, \"\") == nil {{\nreturn build{m}(v)\n}}" for f, m in zip(fs, members)]
        types.append(f"func build{u}(v any) {u} {{\n" + "\n".join(lines) + "\nreturn nil\n}\n")
    scalar_names = [n for n in g.names if g.kinds[n] == "scalar"]
    inline_types = []
    for n in spec.inline:                          # Inline scalar response schema, such as text/plain.
        if g.kinds[n] == "scalar":
            st = g.scalar_type(g.schemas[n], n)
            enc = "append(b, x...)" if st == "string" else None
            if enc is None:
                raise GenError(f"response {n}: only a string scalar is in the subset")
            inline_types.append(f'// {n} -- inline response-body schema (response {n}).\ntype {n} string\n\n'
                                f'// SchemaName returns the schema name.\nfunc ({n}) SchemaName() string {{ return {go_str(n)} }}\n\n'
                                f"func (x {n}) appendJSON(b []byte) []byte {{ return {enc} }}\n\n"
                                f"func build{n}(v any) {n} {{ return {n}(v.(string)) }}\n")

    def expand(names):
        out = []
        for n in names:
            if n in g.excluded:
                continue
            if g.kinds[n] == "union":
                out.extend(expand(g.unions[n]))
            elif g.kinds[n] == "scalar" and n not in spec.inline:
                raise GenError(f"a response of the scalar schema {n} is not in the subset")
            else:
                out.append(n)
        return out

    # Operations.
    ops_src = [r'''// Op identifies an OpenAPI operation.
type Op int
''', "const ("]
    for i, op in enumerate(spec.ops):
        ops_src.append(f"Op{op.name}" + (" Op = 1 + iota" if i == 0 else "") + f" // {op.method} {op.path}")
    ops_src.append(")\n")
    ops_src.append(r'''// String returns the operation name.
func (op Op) String() string {
switch op {
'''
                   + "".join(f"case Op{op.name}:\nreturn {go_str(op.name)}\n" for op in spec.ops)
                   + "}\nreturn \"Op(\" + strconv.Itoa(int(op)) + \")\"\n}\n")

    # Routing refusals.
    needs404 = [op for op in spec.ops if op.method != "HEAD" or any(r.schemas for r in op.responses.values())]
    not_found = {(tuple(op.responses[404].schemas), op.responses[404].media)
                 for op in needs404 if 404 in op.responses}
    if len(not_found) != 1 or any(404 not in op.responses for op in needs404):
        raise GenError(f"{spec.name}: every non-HEAD or body-bearing HEAD operation must declare the same 404 "
                       "(the answer for an unknown path)")
    nf_schemas, nf_media = next(iter(not_found))
    nf_schemas = expand(list(nf_schemas))
    if len(nf_schemas) != 1:
        raise GenError(f"{spec.name}: the 404 answer must be one schema")
    paths = {}
    for op in spec.ops:
        paths.setdefault(op.path, []).append(op)
    wrong = {}
    for path, ops in paths.items():
        # HEAD can explicitly declare a bodyless error; it is not the body schema
        # of an unsupported non-HEAD method on the same path.
        method_ops = [op for op in ops if op.method != "HEAD"] or ops
        has405 = [405 in op.responses for op in method_ops]
        if any(has405) and not all(has405):
            raise GenError(f"{spec.name}: {path}: 405 is declared by some operations of the path only")
        code = 405 if all(has405) else 404
        if any(code not in op.responses for op in method_ops):
            raise GenError(f"{spec.name}: {path}: the {code} method refusal is not declared")
        rs = {(tuple(expand(op.responses[code].schemas)), op.responses[code].media) for op in method_ops}
        if len(rs) != 1 or len(next(iter(rs))[0]) != 1:
            raise GenError(f"{spec.name}: {path}: the {code} answer must be one schema for all operations")
        required = {tuple((h, op.responses[code].headers[h]) for h in op.responses[code].required_headers)
                    for op in method_ops}
        if len(required) != 1 or any(v is None for hs in required for _, v in hs):
            raise GenError(f"{spec.name}: {path}: method refusal requires common constant headers")
        wrong[path] = (code, next(iter(rs))[0][0], next(iter(rs))[1], next(iter(required)))

    def literal(schema, msg):
        node = g.schemas[schema]
        if g.kinds.get(schema) != "struct":
            raise GenError(f"route refusal schema {schema} is not an object schema")
        parts = []
        for p in node.get("required") or []:
            sub = node["properties"][p]
            t = g.ftype(sub, schema, p, schema)
            if t[0] == "const":
                continue
            if t != ("scalar", "string"):
                raise GenError(f"route refusal schema {schema}: required {p} is not a string")
            parts.append(f"{camel(p)}: {go_str(msg)}")
        return f"{schema}{{{', '.join(parts)}}}"

    route = ['// Route selects by method and raw request-target bytes.The path before the first ? is '
             r'''compared byte-for-byte with OpenAPI paths;
'''
             '// query is the unparsed suffix.Unknown paths or unsupported methods produce the declared OpenAPI refusal.',
             "func Route(method, target string) (Op, string, *Response) {",
             "path, query, _ := strings.Cut(target, \"?\")", "switch path {"]
    for path, ops in paths.items():
        code, schema, media, required = wrong[path]
        route.append(f"case {go_str(path)}:")
        route.append("switch method {")
        for op in ops:
            route.append(f"case {go_str(op.method)}:\nreturn Op{op.name}, query, nil")
        route.append("}")
        refusal = f"routeRefusal({code}, {go_str(media)}, {literal(schema, 'no such method')})"
        if required:
            route.append("refusal := " + refusal)
            for header, value in required:
                route.append(f"refusal.Header = append(refusal.Header, [2]string{{{go_str(header)}, {go_str(str(value))}}})")
            route.append('return 0, "", refusal')
        else:
            route.append(f"return 0, \"\", {refusal}")
    route.append("}")
    route.append(f"return 0, \"\", routeRefusal(404, {go_str(nf_media)}, {literal(nf_schemas[0], 'no route')})\n}}\n")
    route.append("func routeRefusal(code int, media string, b Body) *Response {\n"
                 "return &Response{Code: code, Header: [][2]string{{\"Content-Type\", media}}, Body: b.appendJSON(nil)}\n}\n")

    # Answer and response table.
    header_names = []
    for op in spec.ops:
        for r in op.responses.values():
            for h in r.headers:
                if h not in header_names:
                    header_names.append(h)
    dynamic_headers = {h for op in spec.ops for r in op.responses.values() for h, v in r.headers.items() if v is None}
    header_types = {}
    for h in dynamic_headers:
        kinds = {g.scalar_type(r.header_schemas[h], f"header {h}")
                 for op in spec.ops for r in op.responses.values() if h in r.headers}
        if len(kinds) != 1 or not kinds <= {"string", "int64", "uint64"}:
            raise GenError(f"header {h}: incompatible scalar types across operations: {sorted(kinds)}")
        header_types[h] = kinds.pop()
    typed_headers = bool(dynamic_headers or any(r.required_headers for op in spec.ops for r in op.responses.values()))
    answer = ['// Answer contains status, a generated body(nil for none) and headers declared by '
              r'''OpenAPI
// true enables a header only on operations declaring it.''',
              "type Answer struct {", "Code int", "Body Body"]
    for h in header_names:
        if h in dynamic_headers:
            answer.append(f"{camel(h)} *{header_types[h]} // {h}: nil when absent; checked by the operation's schema")
            continue
        consts = sorted({str(op.responses[c].headers[h]) for op in spec.ops for c in op.responses
                         if h in op.responses[c].headers})
        if len(consts) != 1:
            raise GenError(f"header {h}: different const values")
        answer.append(f"{camel(h)} bool // {h}: {consts[0]}")
    answer.append("}\n")
    answer.append("type responseSpec struct {\nmedia string\njson bool\nschemas []string\nheaders []string\n" +
                  ("required []string\nheaderChecks map[string]func(any, string) *Violation\n" if typed_headers else "") + "}\n")
    table = ['// responses maps operation->status->declared media, schemas and headers.',
             "var responses = map[Op]map[int]responseSpec{"]
    for op in spec.ops:
        table.append(f"Op{op.name}: {{")
        for code in sorted(op.responses):
            r = op.responses[code]
            sch = expand(r.schemas)
            js = "true" if r.media and (r.media == "application/json" or r.media.endswith("+json")) else "false"
            hs = ", ".join(go_str(h) for h in r.headers)
            extra = ""
            if typed_headers:
                req = ", ".join(go_str(h) for h in r.required_headers)
                checks = []
                for h, schema in r.header_schemas.items():
                    if h in dynamic_headers:
                        chk = g.chk(schema, f"chk{op.name}{code}Header{camel(h)}", f"{op.method} {op.path} {code} header {h}")
                        if chk:
                            checks.append(f"{go_str(h)}: {chk}")
                extra = f", required: []string{{{req}}}, headerChecks: map[string]func(any, string) *Violation{{{', '.join(checks)}}}"
            table.append(f"{code}: {{media: {go_str(r.media or '')}, json: {js}, "
                         f"schemas: []string{{{', '.join(go_str(x) for x in sch)}}}, headers: []string{{{hs}}}{extra}}},")
        table.append("},")
    table.append("}\n")
    hconst = {h: str(next(op.responses[c].headers[h] for op in spec.ops for c in op.responses
                          if h in op.responses[c].headers)) for h in header_names if h not in dynamic_headers}
    hdr_lines = "".join(f"if a.{camel(h)} {{\nif !declared(spec.headers, {go_str(h)}) {{\n"
                        f"return nil, fmt.Errorf(\"door: %v %d: header {h} is not declared\", op, a.Code)\n}}\n"
                        f"header = append(header, [2]string{{{go_str(h)}, {go_str(hconst[h])}}})\n}}\n"
                        for h in header_names if h not in dynamic_headers)
    for h in (name for name in header_names if name in dynamic_headers):
        field, quoted = camel(h), go_str(h)
        value = f"*a.{field}"
        wire = {"string": value, "int64": f"strconv.FormatInt({value}, 10)",
                "uint64": f"strconv.FormatUint({value}, 10)"}[header_types[h]]
        hdr_lines += (f"if a.{field} != nil {{\nif !declared(spec.headers, {quoted}) {{\n"
                      f"return nil, fmt.Errorf(\"door: %v %d: header {h} is not declared\", op, a.Code)\n}}\n"
                      f"if check := spec.headerChecks[{quoted}]; check != nil {{\n"
                      f"if e := check(*a.{field}, \"\"); e != nil {{ return nil, fmt.Errorf(\"door: header {h}: %v\", e) }}\n}}\n"
                      f"header = append(header, [2]string{{{quoted}, {wire}}})\n}}\n")
    if typed_headers:
        for h in header_names:
            absent = f"a.{camel(h)} == nil" if h in dynamic_headers else f"!a.{camel(h)}"
            hdr_lines += (f"if declared(spec.required, {go_str(h)}) && {absent} {{\n"
                          f"return nil, fmt.Errorf(\"door: %v %d: required header {h} is absent\", op, a.Code)\n}}\n")
    encode = [
        "func declared(names []string, name string) bool {\nfor _, n := range names {\nif n == name {\nreturn true\n}\n}\n"
        "return false\n}\n",
        '// Encode emits wire responses.Reject undeclared status, body schema or headers of the '
        r'''operation,
// and any body outside its schema; the door never sends responses outside the OpenAPI form.''',
        "func Encode(op Op, a Answer) (*Response, error) {",
        "spec, ok := responses[op][a.Code]",
        "if !ok {\nreturn nil, fmt.Errorf(\"door: %v: code %d is not declared\", op, a.Code)\n}",
        "var header [][2]string",
        "var body []byte",
        "if a.Body == nil {\nif len(spec.schemas) != 0 {\n"
        "return nil, fmt.Errorf(\"door: %v %d: a body is required\", op, a.Code)\n}\n} else {",
        "name := a.Body.SchemaName()",
        "if !declared(spec.schemas, name) {\nreturn nil, fmt.Errorf(\"door: %v %d: schema %s is not declared\", op, a.Code, name)\n}",
        "body = a.Body.appendJSON(nil)",
        "var v any = string(body)",
        "if spec.json {\nvar err error\nif v, err = decodeJSON(body); err != nil {\n"
        "return nil, fmt.Errorf(\"door: %v %d: %v\", op, a.Code, err)\n}\n}",
        "if e := checks[name](v, \"\"); e != nil {\nreturn nil, fmt.Errorf(\"door: %v %d: %s: %v\", op, a.Code, name, e)\n}",
        "header = append(header, [2]string{\"Content-Type\", spec.media})",
        "}",
        hdr_lines,
        "return &Response{Code: a.Code, Header: header, Body: body}, nil",
        "}\n",
        r'''// AnswerOf builds a response from JSON values(map, string, int64, json.Number, ...), requiring exactly one
'''
        '// matching schema declared for(op, status);otherwise error.',
        "func AnswerOf(op Op, code int, v any) (Answer, error) {",
        "spec, ok := responses[op][code]",
        "if !ok {\nreturn Answer{}, fmt.Errorf(\"door: %v: code %d is not declared\", op, code)\n}",
        "var hit []string",
        "for _, name := range spec.schemas {\nif checks[name](v, \"\") == nil {\nhit = append(hit, name)\n}\n}",
        "if len(hit) != 1 {\nreturn Answer{}, fmt.Errorf(\"door: %v %d: the value matches %d declared schemas %v\", op, code, len(hit), hit)\n}",
        "b := builders[hit[0]](v)",
        "if !representable(v, b, spec.json) {\nreturn Answer{}, fmt.Errorf(\"door: %v %d: %s: the value is not representable by the Go type\", op, code, hit[0])\n}",
        "return Answer{Code: code, Body: b}, nil",
        "}\n",
    ]
    # Refuse requires every refusal schema (status >=400) to declare const kind and string error.
    fault_schemas = sorted({x for op in spec.ops for c, r in op.responses.items() if c >= 400 for x in expand(r.schemas)})
    for fs in fault_schemas:
        node = g.schemas[fs]
        props, req = node.get("properties") or {}, node.get("required") or []
        if not ("kind" in req and "error" in req and "const" in props.get("kind", {})
                and props.get("error", {}).get("type") == "string"):
            raise GenError(f"refusal schema {fs}: required kind (const) and error (string) — the generator builds "
                           f"Refuse on them")
    encode.append(
        r'''// Refuse selects a declared refusal schema matching kind, error and extra fields, as supplied by writecheck's
'''
        '// Code/Kind/Fault.Declared refusal schemas: '
        + ", ".join(fault_schemas) + ".\n"
        "func Refuse(op Op, code int, kind, msg string, fields map[string]any) (Answer, error) {\n"
        "m := make(map[string]any, len(fields)+2)\nfor k, x := range fields {\nm[k] = x\n}\n"
        "m[\"kind\"] = kind\nm[\"error\"] = msg\nreturn AnswerOf(op, code, m)\n}\n")

    # Checker and constructor tables by schema name.
    check_tab = ['// checks validates named components and inline response schemas.',
                 "var checks = map[string]func(any, string) *Violation{"]
    build_tab = ['// builders constructs typed response bodies after validation.', "var builders = map[string]func(any) Body{"]
    for n in g.names:
        check_tab.append(f"{go_str(n)}: chk{n},")
        if g.kinds[n] in ("struct", "variants") or n in spec.inline:
            build_tab.append(f"{go_str(n)}: func(v any) Body {{ return build{n}(v) }},")
    check_tab.append("}\n")
    build_tab.append("}\n")
    check_tab.append(r'''// CheckSchema validates an OpenAPI schema;ok reports a known schema.Cmd/BatchCmd and their parts belong
'''
                     r'''// to write-checks.tsv and are absent here.
func CheckSchema(name string, v any) (e *Violation, ok bool) {
'''
                     "f, ok := checks[name]\nif !ok {\nreturn nil, false\n}\nreturn f(v, \"\"), true\n}\n")

    # query
    query = []
    for op in spec.ops:
        if not op.params:
            continue
        tname = f"{op.name}Query"
        fields, steps = [], []
        for p in op.params:
            f = camel(p.name)
            schema_name = spec.ref_name(p.schema["$ref"], tname) if "$ref" in p.schema else ""
            chkf = g.chk(p.schema, f"chk{tname}{f}", f"{op.method} {op.path} query {p.name}")
            fields.append(f"{f} {'string' if p.required else '*string'} // {p.name}: "
                          f"{'required' if p.required else 'optional, nil — absent'}"
                          + (f"; schema {schema_name}" if schema_name else ""))
            value = (f"if e := {chkf}(vs[0], \"\"); e != nil {{\nreturn q, &QueryError{{Param: {go_str(p.name)}, "
                     f"Reason: QueryValue, Schema: {go_str(schema_name)}, Rule: e.Rule}}\n}}\n") if chkf else ""
            if string_bound(spec, p.schema):         # Any string constraint anywhere in the schema requires UTF-8 first.
                value = (f"if !utf8.ValidString(vs[0]) {{\nreturn q, &QueryError{{Param: {go_str(p.name)}, "
                         f"Reason: QueryValue, Schema: {go_str(schema_name)}, Rule: \"utf8\"}}\n}}\n") + value
            assign = f"q.{f} = vs[0]" if p.required else f"x := vs[0]\nq.{f} = &x"
            absent = (f"return q, &QueryError{{Param: {go_str(p.name)}, Reason: QueryAbsent}}" if p.required else "")
            steps.append(f"if vs := formValues(pairs, {go_str(p.name)}); len(vs) == 0 {{\n{absent}\n}} else if len(vs) > 1 {{\n"
                         f"return q, &QueryError{{Param: {go_str(p.name)}, Reason: QueryRepeated}}\n}} else {{\n{value}{assign}\n}}")
        query.append(f'// {tname} -- query parameters of operation {op.name} ({op.method} {op.path}).\ntype {tname} struct {{\n'
                     + "\n".join(fields) + "\n}\n")
        query.append(f'// Parse{tname} -- query by parameter schemas; ignore undeclared parameters. Use parameter order from '
                     f'OpenAPI,\n// For each parameter:presence, repetition, then value schema.\n'
                     f"func Parse{tname}(raw string) ({tname}, *QueryError) {{\nvar q {tname}\npairs := parseForm(raw)\n"
                     + "\n".join(steps) + "\nreturn q, nil\n}\n")

    # Request bodies.
    bodies_src = []
    body_types = []
    for op in spec.ops:
        for n in op.body or []:
            if n in g.excluded or n in WRITECHECK:
                continue
            if g.kinds.get(n) != "struct":
                raise GenError(f"{op.method} {op.path}: request body {n} is not an object schema")
            if n not in body_types:
                body_types.append(n)
    for n in body_types:
        bodies_src.append(f'// Decode{n} -- request body by schema {n}: v is JSON from kit jsonstrict or '
                          f'encoding/json with UseNumber).\nfunc Decode{n}(v any) ({n}, *Violation) {{\n'
                          f"if e := chk{n}(v, \"\"); e != nil {{\nreturn {n}{{}}, e\n}}\nx := build{n}(v)\n"
                          f"if !representable(v, x, true) {{\nreturn {n}{{}}, violation(\"\", \"representable\")\n}}\n"
                          f"return x, nil\n}}\n")

    # Operation summary for verification and the journal.
    summary = ['// Operation describes method, path, query parameters and body schemas;Writecheck schemas belong to write-checks.tsv.',
               "type Operation struct {\nOp Op\nMethod string\nPath string\nQuery []string\nBody []string\n"
               "BodyRequired bool\nWritecheck []string\n}\n",
               '// Operations retain OpenAPI order.', "var Operations = []Operation{"]
    for op in spec.ops:
        q = ", ".join(go_str(p.name) for p in op.params)
        b = ", ".join(go_str(n) for n in op.body or [] if n not in g.excluded)
        w = ", ".join(go_str(n) for n in op.body or [] if n in g.excluded)
        summary.append(f"{{Op: Op{op.name}, Method: {go_str(op.method)}, Path: {go_str(op.path)}, Query: []string{{{q}}}, "
                       f"Body: []string{{{b}}}, BodyRequired: {'true' if op.body_required else 'false'}, "
                       f"Writecheck: []string{{{w}}}}},")
    summary.append("}\n")
    summary.append(r'''// Declared maps operation statuses to expanded body schemas and headers.
'''
                   "func Declared(op Op) map[int][2][]string {\nout := map[int][2][]string{}\nfor code, s := range responses[op] {\n"
                   "out[code] = [2][]string{append([]string(nil), s.schemas...), append([]string(nil), s.headers...)}\n}\n"
                   "return out\n}\n")

    # Interface to handwritten code.
    handler = ['// Handler is handwritten code behind the door, one method per operation(N3, identity and limits).C is the '
               r'''call context
// for handwritten code (socket role, headers, ...), not inspected by the door. body is the bytes as '''
               r'''received (Cmd/BatchCmd use
// kit writecheck; other schemas use Decode<Schema> after jsonstrict).''',
               "type Handler[C any] interface {"]
    for op in spec.ops:
        args = ["c C"]
        if op.params:
            args.append(f"q {op.name}Query")
        if op.body is not None:
            args.append("body []byte")
        handler.append(f"{op.name}({', '.join(args)}) Answer // {op.method} {op.path}")
    handler.append("// QueryRefused chooses the response to an invalid query;OpenAPI's form does not specify that choice.")
    handler.append("QueryRefused(c C, op Op, e *QueryError) Answer")
    handler.append("}\n")
    handler.append("// Dispatch parses an operation's query and calls its method;Route and earlier steps belong to the caller.")
    handler.append("func Dispatch[C any](h Handler[C], c C, op Op, query string, body []byte) Answer {")
    handler.append("switch op {")
    for op in spec.ops:
        handler.append(f"case Op{op.name}:")
        args = ["c"]
        if op.params:
            handler.append(f"q, e := Parse{op.name}Query(query)\nif e != nil {{\nreturn h.QueryRefused(c, op, e)\n}}")
            args.append("q")
        else:
            handler.append("_ = query")
        if op.body is not None:
            args.append("body")
        handler.append(f"return h.{op.name}({', '.join(args)})")
    handler.append("}\npanic(\"door: Dispatch: unknown operation \" + op.String())\n}\n")

    regex = ["var ("] + [f"{name} = regexp.MustCompile({go_raw(p)})" for name, p in g.regexps] + [")\n"]
    head = (f"// Code generated by tools/normgen/gen_door.py from {rel}; DO NOT EDIT.\n"
            f"// OpenAPI sha256 {sha}.\n\n"
            '// Package apidoor implements mechanical OpenAPI behavior(ADR-0125 generator 2):routes, methods, query '
            r'''query,
// response/refusal types and encoding, schema checks, and handwritten interfaces.Cmd/BatchCmd are checked by '''
            r'''by
// write-checks.tsv (kit writecheck), not the door (ADR-0125 addendum (1), item 3).
package apidoor

'''
            "import (\n\"encoding/json\"\n\"fmt\"\n\"regexp\"\n\"sort\"\n\"strconv\"\n\"strings\"\n\"unicode/utf8\"\n)\n\n"
            "var _ = json.Number(\"\")\nvar _ = sort.Strings\nvar _ = utf8.ValidString\n\n")
    excluded_note = (f"// Schemas outside the door(reachable only from {', '.join(WRITECHECK)}, judged by write-checks.tsv): "
                     f"{', '.join(sorted(g.excluded))}.\n// Scalar schemas(validation only): {', '.join(scalar_names)}.\n\n")
    parts = [head, excluded_note, "\n".join(ops_src), "\n".join(summary), "\n".join(route), "\n".join(answer),
             "\n".join(table), "\n".join(encode), "\n".join(query), "\n".join(bodies_src), "\n".join(handler),
             "\n".join(types), "\n".join(inline_types), "\n".join(g.builder_src), "\n".join(check_tab),
             "\n".join(build_tab), "\n".join(regex), "\n".join(g.checks)]
    stats = {"routes": len(spec.ops), "paths": len(paths), "types": len(g.structs) + len(g.unions) + len(inline_types),
             "structs": len(g.structs), "interfaces": len(g.unions), "checks": len(g.checks) ,
             "schemas": len(g.names), "excluded": sorted(g.excluded),
             "responses": sum(len(op.responses) for op in spec.ops)}
    return "\n".join(parts), stats


def gofmt(src):
    exe = shutil.which("gofmt")
    if not exe:
        raise GenError("gofmt is not in PATH")
    done = subprocess.run([exe], input=src, capture_output=True, text=True)
    if done.returncode:
        raise GenError(f"gofmt rejects generated Go: {done.stderr[:2000]}")
    return done.stdout


GO_MOD = "module normgen/{name}\n\ngo 1.22\n"


def load(path):
    text = Path(path).read_text(encoding="utf-8")
    try:
        doc = yamlsub.load(text, Path(path).name)
    except yamlsub.YamlError as exc:
        raise GenError(str(exc))
    return text, doc


def emit(doc, rel, sha, out, name="openapi"):
    """Generate <out>/go/apidoor from a loaded OpenAPI document and return its summary."""
    out = Path(out)
    spec = Spec(doc, name)
    src, stats = build_go(spec, rel, sha)
    gdir = out / "go/apidoor"
    gdir.mkdir(parents=True, exist_ok=True)
    (out / "go/go.mod").write_text(GO_MOD.format(name=out.name), encoding="utf-8")
    (gdir / "door.go").write_text(gofmt(src), encoding="utf-8")
    head = f"// Code generated by tools/normgen/gen_door.py: copy of tools/normgen/{RUNTIME.relative_to(HERE)}; DO NOT EDIT.\n\n"
    (gdir / "runtime.go").write_text(gofmt(head + RUNTIME.read_text(encoding="utf-8")), encoding="utf-8")
    return stats


def generate(spec_path=DEFAULT_SPEC, out=DEFAULT_OUT):
    spec_path, out = Path(spec_path).resolve(), Path(out)
    try:
        rel = spec_path.relative_to(ROOT).as_posix()
    except ValueError:
        rel = spec_path.name
    text, doc = load(spec_path)
    return out, emit(doc, rel, hashlib.sha256(text.encode("utf-8")).hexdigest(), out, spec_path.name)


def main(argv):
    spec = argv[1] if len(argv) > 1 else DEFAULT_SPEC
    out = argv[2] if len(argv) > 2 else DEFAULT_OUT
    try:
        path, stats = generate(spec, out)
    except GenError as exc:
        print(f"gen_door: {exc}", file=sys.stderr)
        return 1
    print(f"{path}: {json.dumps(stats, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    if L.key != lesson.DEFAULT:                        # Lessons after P/01 use gen_door_lesson.py; P/01 remains byte-identical.
        import gen_door_lesson
        sys.exit(gen_door_lesson.main(sys.argv))
    sys.exit(main(sys.argv))
