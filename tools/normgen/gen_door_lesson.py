"""Генератор № 2 ADR-0125 для уроков после P/01 (P/06, часть 3а): маршруты двери из OpenAPI урока.

Запуск: python3 tools/normgen/gen_door_lesson.py --lesson 06-console [<out>]   (gen_door.py на уроке ≠ 01-store передаёт сюда)

Источник — `spec/<урок>.api.openapi.yaml` (загрузчик yamlsub; внешние `$ref` — по относительному пути файла урока).
Проза (description, summary, x-mounting) не читается. Выход <out>/go/apidoor/:
- `routes.go` (сгенерирован): `Op` — операция на пару (путь, метод) в порядке OpenAPI; `Ops` — сведения: метод, путь,
  `Prefixed` (у пути есть сервер `{origin}/{sub}` — тот же шаблон и с префиксом `/{sub}`), параметры (имя, место,
  обязательность), ответы (код, media types, заголовки), media types тела запроса; таблицы маршрутизатора —
  шаблоны, проверки параметров пути по схеме (minLength, maxLength, pattern, enum, const; `$ref` разворачивается),
  пары путь+метод → операция, методы пути, «все операции пути объявляют 405»;
- `routes_rt.go` — копия ручной среды `doorrt2/go/routes.go`: `Route(method, path, Catalog)`, `Catalog` (YOURS —
  каталог загруженных имён: sub, rows, table, pass), `Match`, `RouteError`.
Что генератор не делает (часть 3б): разбор и проверку тел по схемам, запись ответов (Encode), сборку тел отказов.
Судья — test_gen_door_lesson.py (своя модель маршрутов по OpenAPI, пробы и мутанты).
"""
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
import lesson  # noqa: E402

L = lesson.CURRENT
DEFAULT_OUT = L.out
METHODS = ("get", "put", "post", "delete", "patch", "head", "options", "trace")
RUNTIME = HERE / "doorrt2/go/routes.go"
SCHEMA_RT = HERE / "doorrt2/go/schema.go"
PRIORITY_RT = HERE / "doorrt2/go/routes_priority.go"   # режим x-route-priority (P/05-R057)
SCHEMA_WORDS = {"$ref", "type", "enum", "const", "allOf", "anyOf", "oneOf", "not", "if", "then", "else", "properties",
                "patternProperties", "additionalProperties", "unevaluatedProperties", "propertyNames", "required",
                "dependentRequired", "minProperties", "maxProperties", "items", "minItems", "maxItems", "uniqueItems",
                "minLength", "maxLength", "pattern", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
                "description", "format", "default", "readOnly", "contentMediaType", "title", "examples", "$comment"}
SUBSCHEMA_MAPS = ("properties", "patternProperties", "dependentRequired")
SUBSCHEMA_ONE = ("not", "if", "then", "else", "additionalProperties", "unevaluatedProperties", "propertyNames", "items")
SUBSCHEMA_LIST = ("allOf", "anyOf", "oneOf")
PARAM_KEYS = {"type", "minLength", "maxLength", "pattern", "enum", "const", "$ref", "description", "title", "examples",
              "not"}
CLASSES = ("sub", "rows", "table", "pass")


class GenError(Exception):
    pass


def go_str(s):
    return json.dumps(s, ensure_ascii=False)


class Docs:
    """Документ урока и внешние документы по `$ref`."""

    def __init__(self, path):
        self.main = Path(path).resolve()
        self.cache = {}
        self.doc = self.load(self.main)

    def load(self, path):
        path = Path(path).resolve()
        if path not in self.cache:
            if not path.is_file():
                raise GenError(f"$ref: no file {path}")
            try:
                self.cache[path] = yamlsub.load(path.read_text(encoding="utf-8"), path.name)
            except yamlsub.YamlError as exc:
                raise GenError(str(exc)) from None
        return self.cache[path]

    def resolve(self, ref, base):
        """→ (узел, файл узла)."""
        file, _, pointer = ref.partition("#")
        path = (Path(base).parent / file).resolve() if file else Path(base)
        node = self.load(path)
        for part in pointer.lstrip("/").split("/") if pointer else []:
            part = part.replace("~1", "/").replace("~0", "~")
            if not isinstance(node, dict) or part not in node:
                raise GenError(f"$ref {ref}: no {part}")
            node = node[part]
        return node, path

    def deref_list(self, item, op, base):
        """Параметры пути и операции с их x-* словами (после разворота $ref)."""
        return [self.deref(p, base)[0] for p in item.get("parameters", []) + op_raw(item, op).get("parameters", [])]

    def deref(self, node, base, seen=()):
        while isinstance(node, dict) and "$ref" in node and len(node) == 1:
            if node["$ref"] in seen:
                raise GenError(f"$ref cycle {node['$ref']}")
            seen = seen + (node["$ref"],)
            node, base = self.resolve(node["$ref"], base)
        return node, base


class Bundle:
    """Схемы тел в одну сборку {"$defs": …}: компоненты урока — по имени, внешние — «NN.<имя>», встроенные — по месту."""

    def __init__(self, docs):
        self.docs, self.defs, self.names = docs, {}, {}

    def prefix(self, file):
        if Path(file) == self.docs.main:
            return ""
        m = re.match(r"(\d\d)-", Path(file).name)
        return (m[1] if m else Path(file).stem) + "."

    def ref(self, ref, base):
        file, _, pointer = ref.partition("#")
        path = (Path(base).parent / file).resolve() if file else Path(base).resolve()
        key = (str(path), pointer)
        if key not in self.names:
            last = pointer.rstrip("/").split("/")[-1] if pointer else path.stem
            name = self.prefix(path) + (last if pointer.startswith("/components/schemas/") else
                                        pointer.strip("/").replace("/", "."))
            name = re.sub(r"[/~]", "_", name.replace("~1", "_").replace("~0", "_"))   # имя — без «/» и «~» (JSON Pointer)
            if name in self.defs:
                raise GenError(f"schema bundle: two schemas named {name}")
            self.names[key] = name
            self.defs[name] = None
            node, nbase = self.docs.resolve(ref, base)
            self.defs[name] = self.rewrite(node, nbase, name)
        return "#/$defs/" + self.names[key]

    def inline(self, name, node, base):
        if name in self.defs:
            raise GenError(f"schema bundle: {name} repeats")
        self.defs[name] = self.rewrite(node, base, name)
        return name

    def rewrite(self, node, base, where):
        if isinstance(node, bool):
            return node
        if not isinstance(node, dict):
            raise GenError(f"{where}: a schema is not an object")
        extra = set(k for k in node if not k.startswith("x-")) - SCHEMA_WORDS
        if extra:
            raise GenError(f"{where}: schema words {sorted(extra)} are out of the body subset")
        out = {}
        for k, v in node.items():
            if k.startswith("x-"):
                continue
            if k == "$ref":
                out[k] = self.ref(v, base)
            elif k in SUBSCHEMA_ONE:
                out[k] = self.rewrite(v, base, f"{where}/{k}")
            elif k in SUBSCHEMA_LIST:
                out[k] = [self.rewrite(x, base, f"{where}/{k}/{i}") for i, x in enumerate(v)]
            elif k in ("properties", "patternProperties"):
                out[k] = {n: self.rewrite(x, base, f"{where}/{k}/{n}") for n, x in v.items()}
            else:
                out[k] = v
        return out


def op_raw(item, op):
    return item[op["method"].lower()]


def param_check(docs, schema, base, where):
    """Схема параметра пути → {minLen, maxLen, pattern, enum}; вне подмножества — GenError."""
    out = {"min": 0, "max": -1, "pattern": None, "enum": None, "not_enum": [], "not_pattern": []}
    node, base = docs.deref(schema, base)
    if not isinstance(node, dict):
        raise GenError(f"{where}: schema is not an object")
    extra = set(node) - PARAM_KEYS
    if extra:
        raise GenError(f"{where}: path parameter schema words {sorted(extra)} are out of the router subset")
    if "$ref" in node:
        inner = param_check(docs, {"$ref": node["$ref"]}, base, where)
        out.update({k: v for k, v in inner.items() if v not in (None, 0, -1, [])})
    if node.get("type", "string") != "string":
        raise GenError(f"{where}: a path parameter of type {node.get('type')!r} — only string")
    if "minLength" in node:
        out["min"] = max(out["min"], int(node["minLength"]))
    if "maxLength" in node:
        out["max"] = int(node["maxLength"]) if out["max"] < 0 else min(out["max"], int(node["maxLength"]))
    if "pattern" in node:
        if out["pattern"] and out["pattern"] != node["pattern"]:
            raise GenError(f"{where}: two patterns")
        out["pattern"] = node["pattern"]
    if "enum" in node:
        out["enum"] = [str(v) for v in node["enum"]]
    if "const" in node:
        out["enum"] = [str(node["const"])]
    if "not" in node:                                  # запреты: not {enum} | not {pattern} | not {anyOf: [они]}
        neg = node["not"]
        items = neg["anyOf"] if isinstance(neg, dict) and set(neg) == {"anyOf"} else [neg]
        for it in items:
            if not isinstance(it, dict) or len(it) != 1 or next(iter(it)) not in ("enum", "pattern"):
                raise GenError(f"{where}: not {it!r} — only enum or pattern (or anyOf of them)")
            if "enum" in it:
                out["not_enum"] += [str(v) for v in it["enum"]]
            else:
                out["not_pattern"].append(it["pattern"])
    return out


def ident(method, path):
    if path == "/":
        return "Op" + method.capitalize() + "Root"
    words = [method.capitalize()]
    for seg in path.strip("/").split("/"):
        if not seg:
            words.append("Slash")
            continue
        m = re.fullmatch(r"\{(.+)\}", seg)
        name = m[1] if m else seg
        words.append(("By" if m else "") + "".join(w[:1].upper() + w[1:] for w in re.split(r"[^A-Za-z0-9]+", name) if w))
    return "Op" + "".join(words)


def segments(path):
    if path == "/":
        return []
    out = []
    for seg in path[1:].split("/"):
        m = re.fullmatch(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", seg)
        if "{" in seg and not m:
            raise GenError(f"{path}: segment {seg!r} — a literal or a whole {{param}}")
        out.append(("", m[1]) if m else (seg, ""))
    return out


def prefixed(item):
    servers = item.get("servers") or []
    urls = [s.get("url", "") for s in servers]
    if not urls:
        return False
    literal = [u for u in urls if "{" not in u]       # адрес-пример без переменных (P/09) — путь без префикса
    if not set(urls) - set(literal) <= {"{origin}", "{origin}/{sub}"}:
        raise GenError(f"servers {urls}: only {{origin}}, {{origin}}/{{sub}} or literal example URLs")
    return "{origin}/{sub}" in urls


bodies = []          # (req|resp, Op, код, media, схема, файл) — собирает build для bodies.go
priority = []        # шаблоны режима x-route-priority — собирает build


def build(root=ROOT):
    spec = Path(root) / L.rel / "spec" / f"{L.key}.api.openapi.yaml"
    docs = Docs(spec)
    doc = docs.doc
    ops, templates, checks, by_pm, methods_of, all405 = [], [], {}, {}, {}, {}
    names = set()
    bodies.clear()
    priority.clear()
    for path, item in doc.get("paths", {}).items():
        segs = segments(path)
        pre = prefixed(item)
        item_params = item.get("parameters", [])
        path_ops = []
        for m in METHODS:
            if m not in item:
                continue
            op = item[m]
            name = ident(m, path)
            if name in names:
                raise GenError(f"{path} {m}: the op name {name} repeats")
            names.add(name)
            params = []
            for prm in item_params + op.get("parameters", []):
                prm, pbase = docs.deref(prm, spec)
                params.append({"name": prm["name"], "in": prm["in"], "required": bool(prm.get("required")),
                               "schema": prm.get("schema", {}), "base": pbase})
            declared = {p["name"] for p in params if p["in"] == "path"}
            want = {s[1] for s in segs if s[1]}
            if declared != want:
                raise GenError(f"{path} {m}: path parameters {sorted(declared)} ≠ template {sorted(want)}")
            for p in params:
                if p["in"] == "path":
                    c = param_check(docs, p["schema"], p["base"], f"{path} {m} {p['name']}")
                    prev = checks.setdefault(path, {}).get(p["name"])
                    if prev is not None and prev != c:
                        raise GenError(f"{path}: parameter {p['name']} differs between methods")
                    checks[path][p["name"]] = c
            responses = []
            for code, r in op.get("responses", {}).items():
                r, _ = docs.deref(r, spec)
                responses.append({"code": str(code), "media": list((r.get("content") or {}).keys()),
                                  "headers": list((r.get("headers") or {}).keys())})
            if not responses:
                raise GenError(f"{path} {m}: no responses")
            rb = op.get("requestBody")
            req_content = ((docs.deref(rb, spec)[0] or {}).get("content") or {}) if rb else {}
            req_media = list(req_content.keys())
            for r_code, r_raw in op.get("responses", {}).items():
                r_node, r_base = docs.deref(r_raw, spec)
                for media, mo in (r_node.get("content") or {}).items():
                    bodies.append(("resp", name, str(r_code), media, mo.get("schema"), r_base))
                    sch = mo.get("schema") or {}
                    if isinstance(sch, dict) and "x-line-schema" in sch:      # x-ndjson: схема строки
                        bodies.append(("line", name, str(r_code), media, sch["x-line-schema"], r_base))
            for prm in item.get("parameters", []) + op.get("parameters", []):
                prm, pbase = docs.deref(prm, spec)
                if prm["in"] in ("query", "header"):
                    sch = prm.get("schema") or {}
                    sch_node = docs.deref(sch, pbase)[0] if isinstance(sch, dict) else {}
                    lex = prm.get("x-query-lexeme")
                    if lex is not None:                # P/05-R022, R031: закрытое расширение query
                        stype = sch_node.get("type") if isinstance(sch_node, dict) else None
                        want = {"number": "number", "integer": "integer", "uint64": "string"}.get(lex.get("parse"))
                        if prm["in"] != "query" or set(lex) - {"pattern", "parse", "strip"} or "pattern" not in lex \
                                or want is None or want != stype or ("strip" in lex and (lex["strip"] != "_" or
                                                                                       lex["parse"] != "number")):
                            raise GenError(f"{path} {m} {prm['name']}: x-query-lexeme {lex} — closed keys pattern, "
                                           f"parse (number|integer|uint64, matching the schema type), strip «_» for number")
                        try:
                            re.compile(lex["pattern"])
                        except re.error as exc:
                            raise GenError(f"{path} {m} {prm['name']}: x-query-lexeme pattern: {exc}") from None
                    bodies.append(("param", name, prm["in"], prm["name"], sch, pbase,
                                   bool(prm.get("required")), sch_node.get("default") if isinstance(sch_node, dict) else None,
                                   lex))
            for media, mo in req_content.items():
                bodies.append(("req", name, "", media, mo.get("schema"), docs.deref(rb, spec)[1]))
            ops.append({"name": name, "method": m.upper(), "path": path, "prefixed": pre, "params": params,
                        "responses": responses, "req": req_media, "req_required": bool(rb and rb.get("required"))})
            by_pm[f"{path} {m.upper()}"] = name
            path_ops.append(ops[-1])
        if not path_ops:
            continue
        if "x-route-priority" in item:                 # режим P/05-R057: приоритет пути и захват/декодирование/ошибки
            caps, decs, errs, schemas = {}, {}, {}, {}
            for o in path_ops:
                for prm in o["params"]:
                    if prm["in"] != "path":
                        continue
                    raw_prm = next(x for x in docs.deref_list(item, o, spec) if x["name"] == prm["name"] and x["in"] == "path")
                    cap = raw_prm.get("x-path-capture", "segment")
                    if cap not in ("segment", "remainder"):
                        raise GenError(f"{path} {prm['name']}: x-path-capture {cap!r}")
                    if caps.setdefault(prm["name"], cap) != cap:
                        raise GenError(f"{path} {prm['name']}: x-path-capture differs between methods")
                    dec = raw_prm.get("x-path-decode", "none")
                    if dec not in ("percent-segment", "none"):
                        raise GenError(f"{path} {prm['name']}: x-path-decode {dec!r}")
                    decs[prm["name"]] = dec == "percent-segment"
                    for meth, pe in (raw_prm.get("x-path-error") or {}).items():
                        errs.setdefault(prm["name"], {})[meth.upper()] = (int(pe["status"]), pe.get("response_schema", "-"))
                    schemas[prm["name"]] = (prm["schema"], prm["base"])
            segs_p = []
            for k, (lit, prm) in enumerate(segs):
                rem = bool(prm) and caps.get(prm) == "remainder"
                if rem and k != len(segs) - 1:
                    raise GenError(f"{path}: remainder {prm} is not the last segment")
                segs_p.append((lit, prm, rem))
            priority.append({"path": path, "segs": segs_p, "priority": int(item["x-route-priority"]),
                             "decode": decs, "errors": errs, "schemas": schemas})
        methods_of[path] = [o["method"] for o in path_ops]
        all405[path] = all(any(r["code"] == "405" for r in o["responses"]) for o in path_ops)
        templates.append((path, segs, False))
        if pre:
            if any(s[1] == "sub" for s in segs):
                raise GenError(f"{path}: servers {{origin}}/{{sub}} and a parameter sub in the path")
            templates.append((path, [("", "sub")] + segs, True))
            checks.setdefault(path, {})["sub"] = server_sub_check(docs, item, spec, path)
    return ops, templates, checks, by_pm, methods_of, all405, docs


def server_sub_check(docs, item, spec, path):
    """Переменная sub сервера {origin}/{sub}: enum переменной или без ограничений (каталог судит имя)."""
    for s in item.get("servers") or []:
        if s.get("url") == "{origin}/{sub}":
            var = (s.get("variables") or {}).get("sub") or {}
            return {"min": 1, "max": -1, "pattern": None, "enum": [str(v) for v in var["enum"]] if "enum" in var else None,
                    "not_enum": [], "not_pattern": []}
    raise GenError(f"{path}: no {{origin}}/{{sub}} server")


def go_check(c):
    rx = f"regexp.MustCompile({go_str(c['pattern'])})" if c["pattern"] else "nil"
    enum = ("[]string{" + ", ".join(go_str(e) for e in c["enum"]) + "}") if c["enum"] is not None else "nil"
    ne = ("[]string{" + ", ".join(go_str(e) for e in c["not_enum"]) + "}") if c["not_enum"] else "nil"
    nrx = ("[]*regexp.Regexp{" + ", ".join(f"regexp.MustCompile({go_str(x)})" for x in c["not_pattern"]) + "}"
           if c["not_pattern"] else "nil")
    return f"paramCheck{{minLen: {c['min']}, maxLen: {c['max']}, rx: {rx}, enum: {enum}, notEnum: {ne}, notRx: {nrx}}}"


def go_source(ops, templates, checks, by_pm, methods_of, all405, rel, sha, roles=None):
    out = [f"// Code generated by tools/normgen/gen_door_lesson.py from {rel} (sha256 {sha[:16]}); DO NOT EDIT.", "",
           f"// Package apidoor — the door of {L.code} by its OpenAPI, part 3a: the operations, the router tables and the",
           "// declared responses and media types. The bodies (decode, check, encode) are part 3b.",
           "package apidoor", "", ('import "regexp"' if not priority else ""), "",
           "// Op — an operation of the OpenAPI (path, method) in the order of the document.", "type Op int", "",
           "const ("]
    for k, o in enumerate(ops):
        out.append(f"\t{o['name']}{' Op = iota + 1' if k == 0 else ''} // {o['method']} {o['path']}")
    out += [")", "",
            "// Param — a parameter of an operation: name, place (path, query, header, cookie), required.",
            "type Param struct {", "\tName     string", "\tIn       string", "\tRequired bool", "}", "",
            "// Response — a declared response: code (\"200\"… or \"default\"), media types, header names.",
            "type Response struct {", "\tCode    string", "\tMedia   []string", "\tHeaders []string", "}", "",
            "// OpInfo — the declaration of an operation. Prefixed — the path also serves under /{sub} (server {origin}/{sub}).",
            "type OpInfo struct {", "\tMethod          string", "\tPath            string", "\tPrefixed        bool",
            "\tParams          []Param", "\tResponses       []Response", "\tRequestMedia    []string",
            "\tRequestRequired bool", "}", "",
            "// Ops — every operation of the OpenAPI.", "var Ops = map[Op]OpInfo{"]
    for o in ops:
        params = ", ".join(f"{{{go_str(p['name'])}, {go_str(p['in'])}, {str(p['required']).lower()}}}" for p in o["params"])
        resps = ", ".join("{" + go_str(r["code"]) + ", " + ("[]string{" + ", ".join(go_str(x) for x in r["media"]) + "}"
                                                            if r["media"] else "nil") + ", "
                          + ("[]string{" + ", ".join(go_str(x) for x in r["headers"]) + "}" if r["headers"] else "nil") + "}"
                          for r in o["responses"])
        req = "[]string{" + ", ".join(go_str(x) for x in o["req"]) + "}" if o["req"] else "nil"
        out.append(f"\t{o['name']}: {{Method: {go_str(o['method'])}, Path: {go_str(o['path'])}, Prefixed: "
                   f"{str(o['prefixed']).lower()}, Params: []Param{{{params}}}, Responses: []Response{{{resps}}}, "
                   f"RequestMedia: {req}, RequestRequired: {str(o['req_required']).lower()}}},")
    if priority:
        out += ["}", "", "var prioTemplates = []prioTemplate{"]
        for t in priority:
            ss = ", ".join(f"{{lit: {go_str(lit)}}}" if not prm else
                           f"{{param: {go_str(prm)}, remainder: {str(rem).lower()}}}" for lit, prm, rem in t["segs"])
            out.append(f"\t{{path: {go_str(t['path'])}, segs: []prioSegment{{{ss}}}, priority: {t['priority']}}},")
        out += ["}", "", "var pathDecode = map[string]map[string]bool{"]
        out += [f"\t{go_str(t['path'])}: {{" + ", ".join(f"{go_str(k)}: {str(v).lower()}" for k, v in t["decode"].items())
                + "}," for t in priority]
        out += ["}", "", "var pathErrors = map[string]map[string]map[string]pathError{"]
        for t in priority:
            out.append(f"\t{go_str(t['path'])}: {{" + ", ".join(
                f"{go_str(n)}: {{" + ", ".join(f"{go_str(m)}: {{status: {st}, response: {go_str('' if rs == '-' else rs)}}}"
                                               for m, (st, rs) in es.items()) + "}" for n, es in t["errors"].items()) + "},")
        out += ["}", "", "var byPathMethod = map[string]Op{"]
        out += [f"\t{go_str(k)}: {v}," for k, v in by_pm.items()]
        out += ["}", "", "// opRoles — door-roles.tsv: роли, допущенные к операции (режим mtls).",
                "var opRoles = map[Op][]string{"]
        for op, rs in (roles or {}).items():
            out.append(f"\t{op}: {{" + ", ".join(go_str(r) for r in rs) + "},")
        out += ["}", ""]
        return "\n".join(out)
    out += ["}", "", "var templates = []template{"]
    for path, segs, pre in templates:
        ss = ", ".join(f"{{lit: {go_str(lit)}}}" if not prm else f"{{param: {go_str(prm)}}}" for lit, prm in segs)
        out.append(f"\t{{path: {go_str(path)}, segs: []segment{{{ss}}}, prefixed: {str(pre).lower()}}},")
    out += ["}", "", "var paramChecks = map[string]map[string]paramCheck{"]
    for path, cs in checks.items():
        out.append(f"\t{go_str(path)}: {{" + ", ".join(f"{go_str(n)}: {go_check(c)}" for n, c in cs.items()) + "},")
    out += ["}", "", "var byPathMethod = map[string]Op{"]
    out += [f"\t{go_str(k)}: {v}," for k, v in by_pm.items()]
    out += ["}", "", "var methodsOf = map[string][]string{"]
    out += [f"\t{go_str(k)}: {{" + ", ".join(go_str(m) for m in v) + "}," for k, v in methods_of.items()]
    out += ["}", "", "var all405 = map[string]bool{"]
    out += [f"\t{go_str(k)}: {str(v).lower()}," for k, v in all405.items()]
    out += ["}", ""]
    return "\n".join(out)


def bodies_source(docs, rel, sha):
    b = Bundle(docs)
    req, resp, lines, params = {}, {}, {}, {}
    for entry in bodies:
        if entry[0] == "param":
            _, op, place, pname, schema, base, required, default, lex = entry
            if isinstance(schema, dict) and set(schema) == {"$ref"}:
                sname = b.ref(schema["$ref"], base)[len("#/$defs/"):]
            elif schema:
                sname = b.inline(f"{op}.param.{place}.{re.sub(r'[^A-Za-z0-9_-]', '_', pname)}", schema, base)
            else:
                sname = ""
            params.setdefault(op, []).append((pname, place, required, sname,
                                              "" if default is None else json.dumps(default, ensure_ascii=False), lex))
            continue
        kind, op, code, media, schema, base = entry
        if kind == "line":
            if isinstance(schema, dict) and set(schema) == {"$ref"}:
                lines.setdefault(op, {})[code] = b.ref(schema["$ref"], base)[len("#/$defs/"):]
            else:
                lines.setdefault(op, {})[code] = b.inline(f"{op}.line.{code}", schema, base)
            continue
        if schema is None:
            name = ""
        elif isinstance(schema, dict) and set(schema) == {"$ref"}:
            name = b.ref(schema["$ref"], base)[len("#/$defs/"):]
        else:
            safe = media.replace("*", "any").replace("/", "_")     # имя сборки — без «/» (JSON Pointer $ref)
            name = b.inline(f"{op}.{kind}.{code or 'body'}.{safe}", schema, base)
        if kind == "req":
            req.setdefault(op, {})[media] = name
        else:
            resp.setdefault(op, {}).setdefault(code, {})[media] = name
    path_schemas = {}
    for t in priority:                                 # схемы параметров пути (режим x-route-priority)
        for name, (schema, base) in t["schemas"].items():
            if isinstance(schema, dict) and set(schema) == {"$ref"}:
                path_schemas.setdefault(t["path"], {})[name] = b.ref(schema["$ref"], base)[len("#/$defs/"):]
            else:
                safe = re.sub(r"[/{}~]", "_", t["path"])
                path_schemas.setdefault(t["path"], {})[name] = b.inline(f"path{safe}.{name}", schema, base)
    bundle = json.dumps({"$defs": b.defs}, ensure_ascii=True, sort_keys=True, separators=(",", ":"))  # BOM в Go — нельзя
    out = [f"// Code generated by tools/normgen/gen_door_lesson.py from {rel} (sha256 {sha[:16]}); DO NOT EDIT.", "",
           "package apidoor", "",
           f"// bundle — the schemas of the bodies of the OpenAPI ({len(b.defs)}; external $ref inlined): data of schema_rt.go.",
           f"const bundle = {go_str(bundle)}", "",
           "// requestSchemas — the schema of the request body by media type (\"\" — no schema).",
           "var requestSchemas = map[Op]map[string]string{"]
    for op, ms in req.items():
        out.append(f"\t{op}: {{" + ", ".join(f"{go_str(m)}: {go_str(n)}" for m, n in ms.items()) + "},")
    out += ["}", "", "// responseSchemas — the schema of a response body by code (or \"default\") and media type.",
            "var responseSchemas = map[Op]map[string]map[string]string{"]
    for op, codes in resp.items():
        out.append(f"\t{op}: {{" + ", ".join(f"{go_str(c)}: {{" + ", ".join(f"{go_str(m)}: {go_str(n)}" for m, n in ms.items())
                                              + "}" for c, ms in codes.items()) + "},")
    out += ["}", "", "// paramSchemas — параметры query и header операции: имя, место, обязательность, схема, умолчание (JSON).",
            "var paramSchemas = map[Op][]paramSpec{"]
    for op, ps in params.items():
        out.append(f"\t{op}: {{" + ", ".join(
            f"{{name: {go_str(n)}, in: {go_str(i)}, required: {str(r).lower()}, schema: {go_str(sn)}, def: {go_str(d)}"
            + (f", lexeme: &queryLexeme{{pattern: {go_str(lx['pattern'])}, parse: {go_str(lx['parse'])}, "
               f"strip: {go_str(lx.get('strip', ''))}}}" if lx else "") + "}" for n, i, r, sn, d, lx in ps) + "},")
    out += ["}", "", "// ndjsonLines — схема строки тела application/x-ndjson ответа по коду (x-line-schema).",
            "var ndjsonLines = map[Op]map[string]string{"]
    for op, cs in lines.items():
        out.append(f"\t{op}: {{" + ", ".join(f"{go_str(c)}: {go_str(n)}" for c, n in cs.items()) + "},")
    out += ["}", ""]
    if priority:
        out += ["// pathSchemas — схема параметра пути в сборке (режим x-route-priority).",
                "var pathSchemas = map[string]map[string]string{"]
        out += [f"\t{go_str(p)}: {{" + ", ".join(f"{go_str(n)}: {go_str(v)}" for n, v in ms.items()) + "},"
                for p, ms in path_schemas.items()]
        out += ["}", ""]
    return "\n".join(out), len(b.defs)


def read_roles(ops):
    """forms/door-roles.tsv урока: method path roles norm → {Op: [роли]}; каждая строка — операция OpenAPI."""
    path = L.form("door-roles.tsv")
    if not path.is_file():
        return {}
    lines = [ln.split("\t") for ln in path.read_text(encoding="utf-8").split("\n") if ln and not ln.startswith("#")]
    if not lines or lines[0] != ["method", "path", "roles", "norm"]:
        raise GenError("door-roles.tsv: columns must be method path roles norm")
    by = {(o["method"], o["path"]): o["name"] for o in ops}
    out = {}
    for cells in lines[1:]:
        if len(cells) != 4:
            raise GenError(f"door-roles.tsv: {cells[:2]}: {len(cells)} cells")
        op = by.get((cells[0].upper(), cells[1]))
        if op is None:
            raise GenError(f"door-roles.tsv: {cells[0]} {cells[1]} is not an operation of the OpenAPI")
        roles = [r.strip() for r in cells[2].split(",")]
        if not all(re.fullmatch(r"\*|<sub>worker|[a-z][a-z0-9_-]*", r) for r in roles):
            raise GenError(f"door-roles.tsv: {cells[1]}: roles {cells[2]!r}")
        out[op] = roles
    return out


def gofmt(src):
    exe = shutil.which("gofmt")
    if not exe:
        raise GenError("gofmt is not in PATH")
    done = subprocess.run([exe], input=src, capture_output=True, text=True)
    if done.returncode:
        raise GenError(f"gofmt rejects generated Go: {done.stderr[:2000]}")
    return done.stdout


def render(root=ROOT):
    ops, templates, checks, by_pm, methods_of, all405, docs = build(root)
    for path, cs in checks.items():
        for name, c in cs.items():
            for pat in [c["pattern"]] * bool(c["pattern"]) + c["not_pattern"]:
                try:
                    re.compile(pat)
                except re.error as exc:
                    raise GenError(f"{path} {name}: pattern {pat!r}: {exc}") from None
    spec = Path(root) / L.rel / "spec" / f"{L.key}.api.openapi.yaml"
    sha = hashlib.sha256(spec.read_bytes()).hexdigest()
    rel = f"{L.rel}/spec/{spec.name}"
    head = "// Code generated by tools/normgen/gen_door_lesson.py: copy of tools/normgen/doorrt2/go/{}; DO NOT EDIT.\n\n"
    bodies_go, _ = bodies_source(docs, rel, sha)
    roles = read_roles(ops) if priority else None
    if priority:
        return {"routes.go": gofmt(go_source(ops, templates, checks, by_pm, methods_of, all405, rel, sha, roles)),
                "routes_rt.go": gofmt(head.format("routes_priority.go") + PRIORITY_RT.read_text(encoding="utf-8")),
                "bodies.go": gofmt(bodies_go),
                "schema_rt.go": gofmt(head.format("schema.go") + SCHEMA_RT.read_text(encoding="utf-8"))}, len(ops), len(templates)
    # операции без ответов с телом и без тела запроса — пустые записи (таблицы полны по Op)
    return {"routes.go": gofmt(go_source(ops, templates, checks, by_pm, methods_of, all405, rel, sha)),
            "routes_rt.go": gofmt(head.format("routes.go") + RUNTIME.read_text(encoding="utf-8")),
            "bodies.go": gofmt(bodies_go),
            "schema_rt.go": gofmt(head.format("schema.go") + SCHEMA_RT.read_text(encoding="utf-8"))}, len(ops), len(templates)


def generate(root=ROOT, out=DEFAULT_OUT):
    files, n_ops, n_t = render(root)
    gdir = Path(out) / "go/apidoor"
    gdir.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (gdir / name).write_text(text, encoding="utf-8")
    mod = Path(out) / "go/go.mod"
    if not mod.exists():
        mod.write_text(f"module {L.go_module}\n\ngo 1.22\n", encoding="utf-8")
    return n_ops, n_t


JUDGE = HERE / "test_gen_door_lesson.py"


def kit_files(out=DEFAULT_OUT):
    """→ [(каталог в internal, имя, байты, происхождение, источник)]; GenError — out устарел."""
    files, _, _ = render(ROOT)
    res = []
    for name, text in sorted(files.items()):
        kept = Path(out) / "go/apidoor" / name
        if not kept.is_file() or kept.read_text(encoding="utf-8") != text:
            raise GenError(f"{kept} is stale: run tools/normgen/gen_door_lesson.py --lesson {L.key}")
        origin, src = {"routes.go": ("generated", kept), "bodies.go": ("generated", kept),
                       "routes_rt.go": ("handwritten", RUNTIME), "schema_rt.go": ("handwritten", SCHEMA_RT)}[name]
        res.append(("apidoor", name, kept.read_bytes(), origin, str(Path(src).relative_to(ROOT))))
    return res


def provenance():
    def entry(path):
        return {"path": str(Path(path).relative_to(ROOT)), "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}
    spec = Path(ROOT) / L.rel / "spec" / f"{L.key}.api.openapi.yaml"
    return {"form": [entry(spec)], "generator": entry(Path(__file__).resolve()),
            "handwritten": [entry(RUNTIME), entry(SCHEMA_RT)],
            "judge": entry(JUDGE)}


def kit_md():
    """Справка части: что решает Catalog и какие группы шаблонов одной формы он различает (по таблицам урока)."""
    ops, templates, checks, by_pm, methods_of, all405, docs = build(ROOT)
    if priority:
        return KIT_MD_PRIORITY + KIT_MD_TAIL
    groups = {}
    for path, segs, pre in templates:
        shape = tuple("{}" if prm else lit for lit, prm in segs)
        groups.setdefault(shape, []).append(("/{sub}" if pre else "") + path)
    lines = []
    for shape, paths in groups.items():
        if len(paths) > 1:
            lines.append("- `/" + "/".join(shape) + "`: " + ", ".join(f"`{p}`" for p in paths))
    return KIT_MD_HEAD + "\n".join(lines) + "\n" + KIT_MD_TAIL


KIT_MD_HEAD = """
## Part `door` (3a): the routes of the lesson's OpenAPI (generated; the catalog is **yours**)

| Package | Import path | Origin |
|---|---|---|
| `apidoor` | `{module}/internal/apidoor` | `routes.go` generated from the OpenAPI; `routes_rt.go` — the kit's router; closed |

```go
func Route(method, path string, cat Catalog) (Match, *RouteError) // the operation of a request, or 404 / 405
type Catalog interface { Sub(name string) bool; Rows(sub, name string) bool; Table(sub, name string) bool; Pass(sub, name string) bool }
var Ops map[Op]OpInfo // method, path, Prefixed (/{sub}), params, declared responses (code, media, headers), request media
```

**What `Catalog` decides.** The router enumerates every template whose literals match the path and whose path
parameters pass their schemas (a template of a path with the server `{origin}/{sub}` also with the prefix `/{sub}`).
For each such candidate it asks your `Catalog` about every parameter named `sub`, `rows`, `table` or `pass`:
`Sub(name)` — is it a loaded subsystem; `Rows(sub, name)` — a unit family of that subsystem; `Table(sub, name)` —
a table; `Pass(sub, name)` — a pass door. `sub` is the value of the prefix or of the parameter `sub`, `""` — the short
path (no prefix). A candidate any answer refuses is dropped. Of the rest the most concrete wins: at the first position
where they differ a literal beats a catalog name, a catalog name beats a free parameter. `Catalog` never gets the
candidate list and never picks an operation — it only answers names from your loaded manifests (the rules of
`x-mounting` are prose: you implement them in these answers). Two candidates of equal rank left — `RouteError.Code`
0: your catalog answered one name for two kinds. A method missing at the chosen path — 405 if every operation of the
path declares 405, otherwise 404.

The templates of one shape that only the catalog tells apart:
"""

KIT_MD_PRIORITY = """
## Part `door`: the routes of the lesson's OpenAPI by x-route-priority (generated)

| Package | Import path | Origin |
|---|---|---|
| `apidoor` | `{module}/internal/apidoor` | `routes.go` generated from the OpenAPI and `forms/door-roles.tsv`; `routes_rt.go` — the kit's router; closed |

```go
func Route(method, rawPath string) (Match, *RouteError)          // rawPath — the target without the query, not decoded
func Admitted(op Op, role string, isSub func(string) bool) bool // door-roles.tsv (mode mtls); isSub — your loaded catalogue
func CheckParam(op Op, in, name string, vals []string) (any, bool, *Violation); func CheckParams(op Op, query, header map[string][]string) (map[string]any, *Violation)
```

The router follows P/05-R057: the literals are compared on the raw bytes of the segments (the path is not decoded as
a whole, a trailing «/» is not normalized, «%2F» does not split a segment); `segment` takes one raw segment,
`remainder` (last only) the raw rest; of the templates of the matching shape those with the request method stay, then
the least `x-route-priority`. A matching shape without the method — `RouteError{Code: 405}` without a body; no match —
404 without a body. Then each parameter is decoded segment by segment (a decoded «/», a bad %XX, an empty capture,
not UTF-8, or out of its schema — a parameter error): `RouteError{Code, Response, Op, Param}` from `x-path-error` of
the method — `Response` names the body schema, "" — no body; no other operation is tried. The role check goes after
matching, before the handler; the TLS chain and the role certificate stay yours.
"""

KIT_MD_TAIL = """
**The bodies (3b).** `bodies.go` bundles every schema of a request or response body (the lesson's components, the
external `$ref` of other lessons as `NN.<name>`, the inline ones as `<Op>.<req|resp>.<code>.<media>`); `schema_rt.go`
checks a JSON value by it (JSON Schema 2020-12, the words the OpenAPI uses; `integer` — a mathematical integer,
lengths in characters, annotations such as `format`, `readOnly`, `contentMediaType` not judged).

```go
func DecodeRequest(op Op, media string, body []byte) (any, *Violation)  // declared media; JSON strictly (one value, no repeated names); the schema
func CheckResponse(op Op, code int, media string, v any) *Violation     // the code (or default) and media are declared, v is of the schema
func EncodeResponse(op Op, code int, media string, v any) ([]byte, *Violation) // CheckResponse and the bytes (JSON without HTML escaping)
func Validate(name string, v any) *Violation                            // a value by a schema of the bundle
```

Yours stay: the order of the checks of a request (frame, limits, identity, route, body — the norms; `x-validation-order`
of two operations names steps of the norm), the byte limits (`x-byte-limits` is prose of the norm), which refusal and
code a violation becomes (the norms and `forms/refusals.tsv`), the headers of the answers.
"""


def main(argv):
    out = Path(argv[1]) if len(argv) > 1 else DEFAULT_OUT
    try:
        n_ops, n_t = generate(ROOT, out)
    except GenError as exc:
        print(f"gen_door_lesson: {exc}", file=sys.stderr)
        return 1
    print(f"gen_door_lesson: {L.code} {n_ops} operations, {n_t} route templates")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
