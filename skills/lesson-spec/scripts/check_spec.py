#!/usr/bin/env python3
"""Read-only structural checks for the published lecture + shared spec layout.

No product imports, execution of acceptance requests, or network reference loading.
Requires PyYAML, openapi-spec-validator and markdown-it-py; a lesson with a form schema next to its norms (ADR-0085)
also jsonschema, ruamel.yaml and regress. See validation.md.
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

SCRIPTS = Path(__file__).resolve().parent
EXCEPTIONS = SCRIPTS.parent / "exceptions.tsv"
# Form schema next to the norm (ADR-0085): spec/<lesson>.schema.yaml and .references.tsv, run by spec_schema/run.py.
SCHEMA_INSTALL = ("uv run --no-project --with pyyaml --with openapi-spec-validator --with markdown-it-py "
                  "--with jsonschema --with ruamel.yaml --with regress python skills/lesson-spec/scripts/check_spec.py …")


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lessons", nargs="+", help="module/NN-slug.md; only the new shared-spec layout")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root, default cwd")
    parser.add_argument("--exceptions", type=Path, default=EXCEPTIONS,
                        help="registry of allowed deviations, default the skill's exceptions.tsv")
    return parser


try:
    import yaml
    from jsonschema_path import SchemaPath
    from markdown_it import MarkdownIt
    from openapi_spec_validator import OpenAPIV31SpecValidator
except ImportError as exc:
    if __name__ == "__main__":
        arguments().parse_args()                     # a wrong call exits 2 before the missing dependency is named
    raise SystemExit(f"Missing dependency: {exc}. See references/validation.md")


class UniqueLoader(yaml.SafeLoader):
    """Read JSON-compatible YAML using the YAML 1.2 Core scalar schema."""


# Inherit only the Core-compatible null resolver, then add Core scalar rules.
# YAML 1.1 merge/value rules must not reinterpret ordinary << or = strings.
# Keep these changes local: verdict fixtures use their own lesson grammar.
UniqueLoader.yaml_implicit_resolvers = {
    first: [(tag, pattern) for tag, pattern in entries if tag == "tag:yaml.org,2002:null"]
    for first, entries in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
UniqueLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
    list("tTfF"))
UniqueLoader.add_implicit_resolver(
    "tag:yaml.org,2002:int",
    re.compile(r"^(?:[-+]?[0-9]+|0o[0-7]+|0x[0-9a-fA-F]+)$"), list("-+0123456789"))
UniqueLoader.add_implicit_resolver(
    "tag:yaml.org,2002:float",
    re.compile(r"^(?:[-+]?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)(?:[eE][-+]?[0-9]+)?"
               r"|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN))$"),
    list("-+0123456789."))


def core_int(loader, node):
    value = loader.construct_scalar(node)
    if value.startswith("0o"):
        return int(value[2:], 8)
    if value.startswith("0x"):
        return int(value[2:], 16)
    return int(value, 10)


UniqueLoader.add_constructor("tag:yaml.org,2002:int", core_int)


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            raise ValueError(f"OpenAPI object key must be a string, line {key_node.start_mark.line + 1}")
        if key in result:
            raise ValueError(f"duplicate YAML key {key!r}, line {key_node.start_mark.line + 1}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key {key!r}")
            result[key] = value
        return result

    def constant(value):
        raise ValueError(f"not JSON: {value}")

    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


# Each edge names an OpenAPI object, a map (*) or a sequence ([]) of such objects.
# Raw application data (example, Example.value, default, enum, const, etc.) has no edge.
OBJECT_EDGES = {
    "document": {"paths": "paths", "webhooks": "*path", "components": "components"},
    "components": {
        "schemas": "*schema", "responses": "*response", "parameters": "*parameter",
        "examples": "*example", "requestBodies": "*body", "headers": "*parameter",
        "securitySchemes": "*security", "links": "*link", "callbacks": "*callback",
        "pathItems": "*path",
    },
    "path": {**{method: "operation" for method in
                ("get", "put", "post", "delete", "options", "head", "patch", "trace")},
             "parameters": "[]parameter"},
    "operation": {"parameters": "[]parameter", "requestBody": "body",
                  "responses": "responses", "callbacks": "*callback"},
    "parameter": {"schema": "schema", "examples": "*example", "content": "*media"},
    "body": {"content": "*media"},
    "response": {"headers": "*parameter", "content": "*media", "links": "*link"},
    "media": {"schema": "schema", "examples": "*example", "encoding": "*encoding"},
    "encoding": {"headers": "*parameter"},
    "schema": {
        **{key: "*schema" for key in ("properties", "patternProperties", "$defs", "dependentSchemas")},
        **{key: "schema" for key in ("items", "contains", "additionalProperties", "propertyNames",
                                    "unevaluatedProperties", "unevaluatedItems", "not", "if", "then",
                                    "else", "contentSchema")},
        **{key: "[]schema" for key in ("allOf", "anyOf", "oneOf", "prefixItems")},
    },
}
REFERENCE_OBJECTS = {"schema", "path", "response", "parameter", "body", "example", "security", "link", "callback"}


def references(document):
    """Walk reference-bearing positions, including local targets, without interpreting payloads."""
    seen = set()

    def walk(node, kind):
        if not isinstance(node, (dict, list)) or (id(node), kind) in seen:
            return
        seen.add((id(node), kind))
        if kind.startswith("[]"):
            if isinstance(node, list):
                for value in node:
                    yield from walk(value, kind[2:])
            return
        if not isinstance(node, dict):
            return
        if kind.startswith("*"):
            for value in node.values():
                yield from walk(value, kind[1:])
            return
        if kind == "schema":
            # These alter reference resolution; never claim root-pointer validation for them.
            for keyword in ("$id", "$dynamicRef", "$recursiveRef"):
                if keyword in node:
                    raise ValueError(f"unsupported schema keyword {keyword}; needs resolver-specific check")
            if "$schema" in node and node["$schema"] not in {
                "https://spec.openapis.org/oas/3.1/dialect/base", "https://json-schema.org/draft/2020-12/schema"
            }:
                raise ValueError("unsupported schema dialect; needs dialect-specific check")
        if kind in REFERENCE_OBJECTS and "$ref" in node:
            ref = node["$ref"]
            # Resolve before yielding or calling the library, including targets in extensions.
            try:
                target = pointer(document, ref)
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                raise ValueError(f"unresolved/unsupported $ref {ref!r}: {exc}") from exc
            yield ref
            yield from walk(target, kind)
        if kind in {"paths", "responses", "callback"}:
            child = {"paths": "path", "responses": "response", "callback": "path"}[kind]
            for key, value in node.items():
                if isinstance(key, str) and not key.startswith("x-") and key != "$ref":
                    yield from walk(value, child)
        else:
            for key, child in OBJECT_EDGES.get(kind, {}).items():
                yield from walk(node.get(key), child)

    yield from walk(document, "document")


def markdown_links(tokens):
    for token in tokens:
        if token.type == "link_open":
            yield token.attrGet("href")
        elif token.type == "image":
            yield token.attrGet("src")
            # Children form the alt text, not independently rendered links or HTML.
            continue
        elif token.type in {"html_inline", "html_block"}:
            raise ValueError("unsupported raw HTML; local links/resources need a separate check")
        if token.children:
            yield from markdown_links(token.children)


def validate(document):
    # Defense in depth: the dependency must not fetch anything even if its traversal changes.
    OpenAPIV31SpecValidator(SchemaPath.from_dict(document, handlers={})).validate()


def pointer(document, ref):
    if not isinstance(ref, str) or not ref.startswith("#"):
        raise ValueError(f"external or unsupported reference {ref!r}; not checked offline")
    encoded = ref[1:]
    if re.search(r"%(?![0-9a-fA-F]{2})", encoded):
        raise ValueError("invalid percent escape in JSON Pointer URI fragment")
    fragment = unquote(encoded, encoding="utf-8", errors="strict")
    if fragment and not fragment.startswith("/"):
        raise ValueError(f"unsupported reference {ref!r}; expected root JSON Pointer")
    value = document
    for part in fragment.split("/")[1:]:
        if re.search(r"~(?![01])", part):
            raise ValueError(f"invalid JSON Pointer escape in token {part!r}")
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            if not re.fullmatch(r"0|[1-9][0-9]*", part):
                raise ValueError(f"invalid JSON Pointer array index {part!r}")
            value = value[int(part)]
        elif isinstance(value, dict):
            value = value[part]
        else:
            raise ValueError(f"JSON Pointer cannot traverse a scalar at token {part!r}")
    return value


EXCEPTION_KINDS = {"no-openapi", "scenarios-format", "acceptance-entry"}
# Classes of a loader refusal (М10/2 Н4): `refused:<class>`.
REFUSAL_CLASSES = {"text", "key", "value", "reference", "name", "catalogue"}


# Data contract catalog (ADR-0083 доп. (2) п. 1–2, form decisions/inbox/2026-10-18-каталог-данных-форма.md).
CATALOG = Path("Platform/common/data/catalog.tsv")
CATALOG_FIELDS = ["key", "kind", "owner", "ops", "readers", "when", "version", "schema", "norm"]
CATALOG_KINDS = {"row", "object", "file", "dir"}
CATALOG_OPS = {"create", "put", "cas", "guard", "mark", "delete", "append"}
ROLE = r"(?:console|resource|domainagent|domainconsole|domain|admin|configstore-door|<s>(?:controller|worker|domain)|proc:[0-9]{2}-[a-z][a-z-]*)"
LESSON = r"(?:М[0-9]+[A-ZА-Я]*/[0-9]{1,2}|P/[0-9]{2}(?:\.[0-9]+)?)"
DATA_LINE = re.compile(r"^- (владеет|пишет|читает):\s*(.*?);?\s*$")


def parse_roles(text, what):
    """`role(cond),role` → {role}; a condition belongs to its role, never holds `;` or nested `(`."""
    roles, pos = set(), 0
    while pos < len(text):
        match = re.match(ROLE + r"(?:\(([^()]*)\))?", text[pos:])
        if not match or (match.group(1) is not None and ";" in match.group(1)):
            raise ValueError(f"{what}: expected role[(condition)] at {text[pos:]!r}")
        roles.add(re.match(ROLE, text[pos:]).group(0))
        pos += match.end()
        if pos < len(text):
            if text[pos] != ",":
                raise ValueError(f"{what}: expected ',' at {text[pos:]!r}")
            pos += 1 + (text[pos + 1:pos + 2] == " ")
    if not roles:
        raise ValueError(f"{what}: no roles")
    return roles


def parse_ops(text):
    """`op=role(cond),role; op=…` → {op: {role}}; a condition belongs to its role, never holds `;` or nested `(`."""
    ops = {}
    for part in text.split("; "):
        op, sep, rest = part.partition("=")
        if not sep or op not in CATALOG_OPS or op in ops:
            raise ValueError(f"operation {op!r} unknown, repeated or without participants")
        ops[op] = parse_roles(rest, f"participants of {op}")
    return ops


def key_pattern(key):
    """Catalog key → (regex, literal length, sample key, spec keys): `<слово>` is one segment, a trailing `/*` the
    family; `<spec:ключ>` is a segment named by that spec key — patterns with different spec keys never overlap."""
    family = key.endswith("/*")
    body = key[:-2] if family else key
    parts = re.split(r"(<[^<>]+>)", body)
    regex = "".join("[^/]+" if part.startswith("<") else re.escape(part) for part in parts)
    sample = "".join("x" if part.startswith("<") else part for part in parts)
    literal = sum(len(part) for part in parts if not part.startswith("<"))
    spec_keys = tuple(part[6:-1] for part in parts if part.startswith("<spec:"))
    if family:
        regex, sample = regex + "/.+", sample + "/x"
    return re.compile(regex), literal, sample, spec_keys


def path_segment(segment):
    """A diagnostic path segment: a mapping key (nonempty string) or a list index (non-negative integer)."""
    if isinstance(segment, str):
        return bool(segment)
    return type(segment) is int and segment >= 0
SCENARIO_HEADER = ["scenario", "step", "request", "expect"]


def scenario_counts(text):
    """Scenarios, steps and scenario names of any scenarios.tsv format: one row per step, the scenario first."""
    steps = Counter()
    for line in text.splitlines():
        cols = line.split("\t")
        if line and not line.startswith("#") and cols != SCENARIO_HEADER and cols[0]:
            steps[cols[0]] += 1
    return len(steps), sum(steps.values()), set(steps)


# Every object schema of a contract says its openness: `additionalProperties` (false — closed, a schema — a map, true —
# open on purpose) or, on a composite, `unevaluatedProperties`. Parts of a composition (allOf/anyOf/oneOf members,
# if/then/else, not, and a component schema referenced as such a member) are closed by their composite, not one by one: a
# closed part would refuse its siblings' properties, and `additionalProperties: true` on a part would evaluate them all.
COMPOSE = ("allOf", "anyOf", "oneOf")
SUBSCHEMA_MAPS = ("properties", "patternProperties", "$defs", "dependentSchemas")
SUBSCHEMAS = ("items", "additionalProperties", "unevaluatedProperties", "propertyNames", "contains", "unevaluatedItems")


def objectlike(node):
    return isinstance(node, dict) and (node.get("type") == "object" or "properties" in node or "required" in node)


def unstated_openness(doc):
    out = []

    def schema(node, pointer, part=False):
        if not isinstance(node, dict) or "$ref" in node:
            return
        parts = [m for k in COMPOSE for m in node.get(k) or []] + [node.get(k) for k in ("then", "else")]
        said = "additionalProperties" in node or "unevaluatedProperties" in node
        if not part and not said and (objectlike(node) or any(objectlike(m) for m in parts)):
            out.append(pointer)
        for key in SUBSCHEMA_MAPS:
            if isinstance(node.get(key), dict):
                for name, sub in node[key].items():
                    schema(sub, f"{pointer}/{key}/{name}")
        for key in SUBSCHEMAS:
            schema(node.get(key), f"{pointer}/{key}")
        for i, item in enumerate(node.get("prefixItems") or []):
            schema(item, f"{pointer}/prefixItems/{i}")
        for key in COMPOSE:
            for i, sub in enumerate(node.get(key) or []):
                schema(sub, f"{pointer}/{key}/{i}", part=True)
        for key in ("if", "then", "else", "not"):    # `not: {required: […]}` is a condition: openness would change it
            schema(node.get(key), f"{pointer}/{key}", part=True)

    def walk(node, pointer):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in ("example", "examples"):
                    continue
                if key == "schema":
                    schema(value, f"{pointer}/schema")
                elif pointer == "#/components" and key == "schemas" and isinstance(value, dict):
                    for name, sub in value.items():
                        schema(sub, f"{pointer}/schemas/{name}")
                else:
                    walk(value, f"{pointer}/{key}")
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, f"{pointer}/{i}")

    parts = {m["$ref"] for m in composition_members(doc) if isinstance(m, dict) and isinstance(m.get("$ref"), str)}
    walk(doc, "#")
    return [p for p in out if p not in parts]


def composition_members(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("example", "examples"):
                continue
            if key in COMPOSE and isinstance(value, list):
                yield from value
            elif key in ("then", "else"):
                yield value
            yield from composition_members(value)
    elif isinstance(node, list):
        for value in node:
            yield from composition_members(value)


class Check:
    def __init__(self, root, exceptions=None):
        self.root = root.resolve()
        self.errors = []
        self.stats = Counter()
        self.excepted = []
        self.registry = {}
        self.used = set()
        self.catalog = None
        if exceptions is not None:
            self.load_exceptions(exceptions)
        if (self.root / CATALOG).exists():
            self.load_catalog(self.root / CATALOG)

    # Allowed deviations, each with its reason: lesson (module/NN), kind, value, reason. A row a checked lesson
    # no longer needs is an error, so the registry cannot keep hiding what has been fixed.
    def load_exceptions(self, path):
        text = self.read(path)
        for line_no, line in enumerate((text or "").splitlines(), 1):
            if not line or line.startswith("#"):
                continue
            cols = line.split("\t")
            if len(cols) != 4 or not all(cols) or cols[1] not in EXCEPTION_KINDS:
                self.error(path, f"line {line_no}: expected lesson, kind ({', '.join(sorted(EXCEPTION_KINDS))}), "
                                 "value, reason")
                continue
            lesson, kind, value, reason = cols
            if (lesson, kind, value) in self.registry:
                self.error(path, f"line {line_no}: duplicate exception")
            self.registry[(lesson, kind, value)] = reason

    def lesson_norms(self, address):
        """`М10/3` → М10_Platform/spec/03-*.norms.md; `P/03` → Platform/NN-<процесс>/spec/03-*.norms.md, каталог — по
        Platform/lessons.tsv (None if absent)."""
        module, _, number = address.partition("/")
        number, _, chapter = number.partition(".")
        if module == "P":
            lessons = self.root / "Platform/lessons.tsv"
            names = dict(row for _, row in [(n, c[:2]) for n, c in self.tsv(lessons, 3)]) if lessons.exists() else {}
            dirs = [self.root / "Platform" / names[number]] if number in names else []
        else:
            dirs = sorted(self.root.glob(f"{module}_*"))
        for directory in dirs:
            found = sorted((directory / "spec").glob(f"{int(number):02}-*.norms.md"))
            found = [f for f in found if re.fullmatch(r"[0-9]{2}-[^.]+\.norms\.md", f.name)]
            if module == "P":
                # A lesson split into chapters: the named chapter, else the first one.
                chapters = sorted((directory / "spec").glob(f"{int(number):02}.{chapter or '[1-9]'}-*.norms.md"))
                found += [f for f in chapters if re.fullmatch(r"[0-9]{2}\.[1-9]-[^.]+\.norms\.md", f.name)]
            if found:
                return found[0]
        return None

    def load_catalog(self, path):
        rows = self.tsv(path, len(CATALOG_FIELDS))
        if not rows or rows[0][1] != CATALOG_FIELDS:
            self.error(path, f"expected header {' '.join(CATALOG_FIELDS)}")
            return
        self.catalog = {}
        for line, cols in rows[1:]:
            row = dict(zip(CATALOG_FIELDS, cols))
            try:
                if not row["key"] or (row["key"], row["kind"]) in self.catalog:
                    raise ValueError("key and kind empty or repeated")
                if any(not re.fullmatch(r"spec:[a-z_]+(?:\.[a-z_]+)*", v) for v in re.findall(r"<(spec:[^<>]*)>", row["key"])):
                    raise ValueError("a spec variable is <spec:ключ.спеки>")
                if row["kind"] not in CATALOG_KINDS:
                    raise ValueError(f"kind is one of {sorted(CATALOG_KINDS)}")
                if not re.fullmatch(LESSON, row["owner"]):
                    raise ValueError("owner is a lesson address (М10/3, М11/6, P/03)")
                row["ops"] = parse_ops(row["ops"])
                if row["readers"] != "*":
                    parse_roles(row["readers"], "readers")
                if not re.fullmatch(r"-|[a-z_]+(?:\.[a-z_]+)*", row["when"]):
                    raise ValueError("when is - or a spec key")
                if not re.fullmatch(r"[1-9][0-9]*", row["version"]):
                    raise ValueError("version is an integer ≥ 1")
                if row["schema"] != "-" and not (self.root / "Platform" / row["schema"]).is_file():
                    raise ValueError(f"schema {row['schema']} is not a file under Platform/")
                norm = re.match(LESSON, row["norm"])
                if not norm or self.lesson_norms(norm.group(0)) is None:
                    raise ValueError("norm names an existing lesson")
                if self.lesson_norms(row["owner"]) is None:
                    raise ValueError("owner names an existing lesson")
            except ValueError as exc:
                self.error(path, f"line {line}: {exc}")
                continue
            row["pattern"] = key_pattern(row["key"])
            self.catalog[(row["key"], row["kind"])] = row
        patterns = list(self.catalog.values())
        for i, a in enumerate(patterns):
            for b in patterns[i + 1:]:
                (ra, la, sa, ka), (rb, lb, sb, kb) = a["pattern"], b["pattern"]
                if a["kind"] != b["kind"] or ka != kb:
                    continue
                if la == lb and (rb.fullmatch(sa) or ra.fullmatch(sb)):
                    self.error(path, f"keys {a['key']} and {b['key']} overlap with equal narrowness")
        self.stats["catalog_rows"] += len(self.catalog)

    # Paragraph «Данные» in Н1 of a lesson against the catalog: what the lesson owns, writes and reads.
    def data_paragraph(self, path, text, prefix, lesson=None):
        """`lesson` — the lesson address of a chapter (P/01 for P/01.3): its rows may be claimed by any chapter;
        returns what the paragraph says the file owns."""
        if self.catalog is None:
            return set()
        owned = {key for (key, _), row in self.catalog.items() if row["owner"] == prefix}
        shared = {key for (key, _), row in self.catalog.items() if lesson and row["owner"] == lesson}
        by_key = {}
        for (key, _), row in self.catalog.items():
            by_key.setdefault(key, []).append(row)
        lines = text.splitlines()
        start = next((i for i, line in enumerate(lines) if line.startswith("**Данные**")), None)
        if start is None:
            if owned:
                self.error(path, f"no «Данные» paragraph, the catalog says it owns {sorted(owned)}")
            return set()
        said = {"владеет": set(), "пишет": {}, "читает": set()}
        for line in lines[start + 1:]:
            match = DATA_LINE.match(line)
            if not match:
                break
            for key, op in re.findall(r"`([^`]+)`(?:\s*\(([a-z]+)\))?", match.group(2)):
                if key not in by_key:
                    self.error(path, f"«Данные»: {key} is not in the catalog")
                    continue
                if match.group(1) == "пишет":
                    said["пишет"][key] = op
                    if not op or not any(op in row["ops"] for row in by_key[key]):
                        self.error(path, f"«Данные»: write ({op or 'no operation'}) is not among the catalog ops of {key}")
                else:
                    said[match.group(1)].add(key)
        if not owned <= said["владеет"] <= owned | shared:
            self.error(path, f"«Данные»: owns {sorted(said['владеет'])}, the catalog says {sorted(owned)}"
                             + (f" (and the lesson's {sorted(shared)})" if shared else ""))
        self.stats["data_paragraphs"] += 1
        return said["владеет"]

    def exception(self, lesson, kind, value="-"):
        return self.registry.get((lesson, kind, value))

    def except_(self, path, lesson, kind, value, detail=""):
        self.used.add((lesson, kind, value))
        reason = self.registry[(lesson, kind, value)]
        self.excepted.append(f"{lesson} {kind} {value}: {reason}" + (f" ({detail})" if detail else ""))

    def error(self, path, message):
        try:
            name = path.relative_to(self.root)
        except ValueError:
            name = path
        self.errors.append(f"{name}: {message}")

    def read(self, path):
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            self.error(path, str(exc))
            return None

    def markdown(self, path, text):
        if re.search(r"\{\{.*?\}\}", text, re.S):
            self.error(path, "unfilled template marker {{...}}")
        try:
            for target in markdown_links(MarkdownIt("commonmark").parse(text)):
                url = urlsplit(target)
                if url.scheme or url.netloc or not url.path:
                    continue
                if url.path.startswith("/"):
                    self.error(path, f"absolute local link is not portable: {target}")
                elif not (path.parent / unquote(url.path)).exists():
                    self.error(path, f"missing link target: {target}")
                self.stats["local_links"] += 1
        except ValueError as exc:
            self.error(path, str(exc))

    def openapi(self, path):
        text = self.read(path)
        if text is None:
            return
        if "{{" in text:
            self.error(path, "unfilled contract template")
        try:
            doc = yaml.load(text, Loader=UniqueLoader)
            # OpenAPI's YAML representation must still represent JSON data.
            json.dumps(doc, allow_nan=False)
            if not isinstance(doc, dict):
                raise ValueError("OpenAPI document must be an object")
            if not str(doc.get("openapi", "")).startswith("3.1."):
                raise ValueError("expected OpenAPI 3.1.x")
            if not isinstance(doc.get("paths"), dict) or not doc["paths"]:
                raise ValueError("no HTTP paths: unfinished contract or layout decision needed")
            if doc.get("jsonSchemaDialect", "https://spec.openapis.org/oas/3.1/dialect/base") not in {
                "https://spec.openapis.org/oas/3.1/dialect/base", "https://json-schema.org/draft/2020-12/schema"
            }:
                raise ValueError("unsupported schema dialect; needs dialect-specific check")
            # Check actual reference positions, not similarly named fields in application data.
            self.stats["local_refs"] += sum(1 for _ in references(doc))
            validate(doc)
            for pointer in unstated_openness(doc):
                self.error(path, f"OpenAPI: object schema {pointer} does not say its openness "
                                 "(additionalProperties, or unevaluatedProperties on a composite)")
            self.stats["openapi"] += 1
        except Exception as exc:
            self.error(path, f"OpenAPI: {exc}")

    def norms(self, path, text, prefix):
        tokens = MarkdownIt("commonmark").parse(text)
        headings, ids, stack = [], [], []
        section = None
        for pos, token in enumerate(tokens):
            if token.type == "heading_open" and token.tag == "h1" and token.level == 0:
                section = None
            if token.type == "heading_open" and token.tag == "h2" and token.level == 0:
                inline = tokens[pos + 1]
                section = "".join(child.content for child in inline.children or []
                                  if child.type in {"text", "code_inline"}).strip()
                headings.append(section)
            if (token.type == "inline" and section == "Чеклист готовности" and
                    len(stack) == 3 and stack[0] in {"bullet_list_open", "ordered_list_open"} and
                    stack[1:] == ["list_item_open", "paragraph_open"]):
                children = [child for child in token.children or []
                            if child.type != "text" or child.content]
                if (len(children) >= 4 and children[0].type == "text" and
                        re.fullmatch(r"\[[ xX]\]\s+", children[0].content) and
                        children[1].type == "strong_open" and children[2].type == "text" and
                        children[3].type == "strong_close" and
                        re.fullmatch(r"(?:М[0-9]+[A-ZА-Я]*/[0-9]+|P/[0-9]{2}(?:\.[1-9])?)-[0-9]+", children[2].content)):
                    ids.append(children[2].content)
            if token.nesting == 1:
                stack.append(token.type)
            elif token.nesting == -1:
                stack.pop()
        headers = [match.group(1) for heading in headings
                   if (match := re.match(r"(Н[0-5])(?:\s|$)", heading))]
        if headers != [f"Н{i}" for i in range(6)]:
            self.error(path, "expected Н0–Н5 once, in order")
        if not ids:
            self.error(path, "no normative checklist ids")
        for value, count in Counter(ids).items():
            if count != 1 or not value.startswith(prefix + "-"):
                self.error(path, f"duplicate or foreign checklist id {value}")
        for title in ["Решает реализация", "Чеклист готовности"]:
            if title not in headings:
                self.error(path, f"missing section {title}")
        self.stats["norm_ids"] += len(ids)
        return ids

    # Counts and ranges a text states about the lesson must match its tables: a fix that adds a norm or
    # a scenario has to update every place that counts them. Only unambiguous whole-lesson phrases are read.
    def counts(self, path, text, prefix, ids, scenarios, instruction, verdicts=None, choices=None, lecture=False):
        def mismatch(said, actual, what):
            self.error(path, f"says {said} {what}, the tables have {actual}")
        # Examples in code are not the lesson's counts; a phrase that announces a subset is not its total.
        text = re.sub(r"^```.*?^```", "", text, flags=re.S | re.M)
        def is_total(match):
            return not re.search(r"подмножеств|из них|кроме|только|например|пример", text[max(0, match.start() - 80):match.start()])
        if choices is not None:
            for match in re.finditer(r"(\d+)\s+(?:выбор\w*|пункт\w*\s+«?Решает реализация)", text):
                if is_total(match):
                    self.stats["count_phrases"] += 1
                    if int(match.group(1)) != choices:
                        mismatch(match.group(1), choices, "«Решает реализация» items")
        if lecture:
            return
        if verdicts is not None:
            # A corpus phrase names files or verdicts with both the ok and the refused count: the whole table.
            for match in re.finditer(r"(\d+)\s+(?:файл|вердикт|случа)\w*[^\n]*?(?:(\d+)\s*`?ok`?\s*[,/]\s*(\d+)\s*`?refused"
                                     r"|`?ok`?\s*\((\d+)\)[^\n]*?`?refused`?\s*\((\d+)\))", text):
                if not is_total(match):
                    continue
                self.stats["count_phrases"] += 1
                ok, refused = (match.group(2), match.group(3)) if match.group(2) else (match.group(4), match.group(5))
                said = (int(match.group(1)), int(ok), int(refused))
                if said != verdicts:
                    mismatch("%d (%d ok, %d refused)" % said, "%d (%d ok, %d refused)" % verdicts, "verdicts")
        if scenarios is not None and path.name.endswith(".norms.md"):
            # Every scenario row of the Н5 table names a scenario of scenarios.tsv by its number.
            n5 = re.search(r"^## Н5\b.*?(?=^## |\Z)", text, re.S | re.M)
            numbers = {name.split("-", 1)[0] for name in scenarios[2]}
            rows = set()
            for match in re.finditer(r"^\|\s*(\d{2})\s*\|", n5.group(0) if n5 else "", re.M):
                self.stats["count_phrases"] += 1
                rows.add(match.group(1))
                if match.group(1) not in numbers:
                    self.error(path, f"Н5 names scenario {match.group(1)}, scenarios.tsv has no such scenario")
            for number in sorted(numbers - rows) if rows else []:
                self.error(path, f"scenario {number} of scenarios.tsv has no row in the Н5 table")
        if scenarios is not None:
            total, steps, _ = scenarios
            for match in re.finditer(r"(\d+)\s*сценари\w*\s*[/,]\s*(\d+)\s*шаг\w*", text):
                if not is_total(match):
                    continue
                self.stats["count_phrases"] += 1
                if int(match.group(1)) != total:
                    mismatch(match.group(1), total, "scenarios")
                if int(match.group(2)) != steps:
                    mismatch(match.group(2), steps, "steps")
            for match in re.finditer(r"scenarios\.tsv\s*\((\d+)\s*[–…-]\s*(\d+)\)", text):
                self.stats["count_phrases"] += 1
                if int(match.group(1)) != 1 or int(match.group(2)) != total:
                    mismatch(f"{match.group(1)}–{match.group(2)}", f"01–{total:02}", "scenarios")
        if path.name.endswith(".norms.md"):
            return
        for match in re.finditer(re.escape(prefix) + r"-0?1\s*[…–-]\s*(\d+)", text):
            self.stats["count_phrases"] += 1
            if int(match.group(1)) != len(ids):
                mismatch(f"{prefix}-01…{match.group(1)}", f"{len(ids)} ids", "checklist ids")
        if instruction:
            for match in re.finditer(r"(\d+)\s+(?:id(?!\w)|пункт\w*\s+чеклиста)|[Вв]с[её]\w*\s+(\d+)\s+норм", text):
                self.stats["count_phrases"] += 1
                said = match.group(1) or match.group(2)
                if int(said) != len(ids):
                    mismatch(said, len(ids), "checklist ids")

    # Every directive a scenario uses is in a stand dictionary (README of lesson 1, «Словарь директив»): the shared one
    # of М10 and the module's own, which adds only its new directives.
    def directives(self, table, stands):
        known, found = set(), False
        for stand in dict.fromkeys(stands):
            text = self.read(stand) if stand.exists() else None
            section = re.search(r"Словарь директив.*?(?=^## |\Z)", text or "", re.S | re.M)
            if section is not None:
                found = True
                known |= set(re.findall(r"(?<![\w@])(@[a-z]+)", section.group(0)))
        if not found:
            return
        used = set()
        for line in (self.read(table) or "").splitlines():
            if line and not line.startswith("#"):
                used |= set(re.findall(r"(?<![\w@])(@[a-z]+)", line))
        for name in sorted(used - known):
            self.error(table, f"directive {name} is not in a stand dictionary (lesson 1 README of М10 or of the module)")

    def tsv(self, path, width, header=None):
        text = self.read(path)
        rows = []
        if text is None:
            return rows
        for line_no, line in enumerate(text.splitlines(), 1):
            if not line or line.startswith("#"):
                continue
            cols = line.split("\t")
            if header and cols == header:
                continue
            if len(cols) != width:
                self.error(path, f"line {line_no}: expected {width} TSV columns, got {len(cols)}")
            else:
                rows.append((line_no, cols))
        return rows

    # The structure (columns, scenario/step numbering) is checked for every format; the generic grammar of requests
    # and expectations only for the generic one. With `own`, returns how many grammar messages its format silenced.
    def scenarios(self, path, own=False):
        steps = Counter()
        silenced = 0
        for line, (scenario, step, request, expect) in self.tsv(path, 4, SCENARIO_HEADER):
            steps[scenario] += 1
            if not scenario or step != str(steps[scenario]):
                self.error(path, f"line {line}: invalid scenario/step sequence")
            before = len(self.errors)
            self.scenario_form(path, line, request, expect)
            if own:
                silenced += len(self.errors) - before
                del self.errors[before:]
        self.stats["scenarios"] += len(steps)
        self.stats["steps"] += sum(steps.values())
        if not steps:
            self.error(path, "empty scenarios table")
        return silenced

    def scenario_form(self, path, line, request, expect):
        if request.startswith("ASSERT "):
            if expect or not re.fullmatch(r"ASSERT \$\w+ != \$\w+(?: \$\w+)*", request):
                self.error(path, f"line {line}: invalid ASSERT or nonempty expectation")
            return
        # Deliberately invalid JSON requests are acceptance data, not parse errors here.
        if not re.match(r"^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS) /", request):
            self.error(path, f"line {line}: unsupported request form; needs format-specific check")
        code, separator, body = expect.partition(" ")
        try:
            if not separator or not re.fullmatch(r"[1-5][0-9]{2}", code):
                raise ValueError("expected HTTP status and JSON body")
            strict_json(body)
        except (ValueError, TypeError) as exc:
            self.error(path, f"line {line}: {exc}")

    def verdicts(self, path):
        verdicts = {}
        for line, (case, result) in self.tsv(path, 2):
            invalid_name = not case or case in {".", ".."} or any(c in case for c in ["/", "\\", "\x00"])
            if case in verdicts or result not in {"ok", "refused"} or invalid_name:
                self.error(path, f"line {line}: duplicate/invalid case or verdict")
            verdicts[case] = result
        cases = path.parent / "cases"
        expected = {f"{case}.subsystem.yaml" for case in verdicts}
        try:
            entries = list(cases.iterdir())
            actual = {p.name for p in entries}
            if actual != expected:
                self.error(path, f"cases/verdicts differ: missing={sorted(expected-actual)}, unlisted={sorted(actual-expected)}")
            for entry in entries:
                if not entry.is_file():
                    self.error(entry, "acceptance case must be a file")
        except OSError as exc:
            self.error(cases, str(exc))
        self.stats["verdicts"] += len(verdicts)
        if not verdicts:
            self.error(path, "empty verdicts table")
        # Invalid YAML/encoding in cases is intentional: never load them as contracts.
        return verdicts

    def diagnostics(self, path, verdicts):
        seen = set()
        for line, (case, paths, lines) in self.tsv(path, 3):
            try:
                if case in seen or verdicts.get(case) != "refused":
                    raise ValueError("diagnostic case must be unique and have refused verdict")
                seen.add(case)
                paths, lines = strict_json(paths), strict_json(lines)
                if not isinstance(paths, list) or not paths or any(not isinstance(p, list) or not p or not all(map(path_segment, p)) for p in paths):
                    raise ValueError("paths must be nonempty arrays of nonempty string keys or non-negative integer indexes")
                if len({tuple(p) for p in paths}) != len(paths):
                    raise ValueError("duplicate diagnostic paths")
                if not isinstance(lines, list) or any(type(n) is not int or n < 1 for n in lines):
                    raise ValueError("line numbers must be positive JSON integers")
                if len(lines) != len(set(lines)):
                    raise ValueError("duplicate diagnostic line numbers")
                self.stats["diagnostics"] += 1
            except (ValueError, TypeError) as exc:
                self.error(path, f"line {line}: {exc}")

    def classes(self, path, verdicts):
        seen = {}
        for line, (case, kind) in self.tsv(path, 2):
            if case in seen or verdicts.get(case) != "refused" or kind not in REFUSAL_CLASSES:
                self.error(path, f"line {line}: class case must be unique, have refused verdict and a class of {sorted(REFUSAL_CLASSES)}")
            seen[case] = kind
        if not seen:
            self.error(path, "empty classes table")
        return seen

    # The form schema is a check next to the norm, not the norm (ADR-0085): every case of the lesson corpus goes through
    # the text layer, the schema and the reference pass; its verdict must be verdicts.tsv's and its class classes.tsv's.
    # A difference is a defect of the schema, the norm or the corpus. Missing dependencies fail, never skip.
    def spec_schema(self, schema, references, cases, verdicts, classes):
        for path in (schema, references):
            if not path.is_file():
                self.error(path, "form schema check needs both .schema.yaml and .references.tsv (ADR-0085)")
                return
        if verdicts is None:
            self.error(schema, "form schema without verdicts.tsv: nothing to check it against")
            return
        if str(SCRIPTS) not in sys.path:
            sys.path.insert(0, str(SCRIPTS))
        try:
            from spec_schema.run import Runner
        except ImportError as exc:
            self.error(schema, f"form schema check needs jsonschema, ruamel.yaml and regress (ADR-0085), missing: {exc}; "
                               f"run: {SCHEMA_INSTALL}")
            return
        try:
            runner = Runner(schema, references)
        except Exception as exc:
            self.error(schema, f"form schema: {exc}")
            return
        for case, expected in sorted(verdicts.items()):
            path = cases / f"{case}.subsystem.yaml"
            try:
                got = runner.judge(path.read_bytes())
            except OSError:
                continue                                 # verdicts() has named the missing case
            except Exception as exc:
                self.error(path, f"form schema: runner failed: {exc!r}")
                continue
            why = f"layer {got['layer']}" + (f": {got['errors'][0]}" if got["errors"] else "")
            if got["verdict"] != expected:
                self.error(path, f"form schema: verdict expected {expected}, got {got['verdict']} ({why})")
            elif case in classes and got["class"] != classes[case]:
                self.error(path, f"form schema: class expected {classes[case]}, got {got['class']} ({why})")
            self.stats["schema_cases"] += 1
        # Every subsystem spec of the course must load too, not only the corpus (ADR-0085 доп. (1), Р3).
        # Corpora (cases/, spec_verdicts/) hold refused specs on purpose; only the specs subsystems ship are checked here.
        specs = [*(self.root / "Source" / "vms").glob("*.subsystem.yaml"),
                 *(self.root / "Source" / "tests" / "testdata").glob("*.subsystem.yaml")]
        for path in sorted(specs):
            try:
                got = runner.judge(path.read_bytes())
            except Exception as exc:
                self.error(path, f"form schema: runner failed: {exc!r}")
                continue
            if got["verdict"] != "ok":
                why = f"layer {got['layer']}" + (f": {got['errors'][0]}" if got["errors"] else "")
                self.error(path, f"form schema: course spec refused {got['verdict']} ({why})")
            self.stats["schema_specs"] += 1

    # The stands whose «Словарь директив» a scenario may use: the shared stand of the Platform module (lesson 1
    # moves it there), the М10 one until then, and the module's own.
    def stands(self, module=None):
        acceptance = self.root / "Source/tests/testdata/acceptance"
        return [self.root / "Platform/common/acceptance/README.md", acceptance / "М10_Platform/01/README.md"] + \
               ([acceptance / module / "01/README.md"] if module else [])

    # One acceptance directory: the supported tables, each with its format check. `entry` prefixes the value of an
    # acceptance-entry exception (a chapter directory of a Platform lesson: `K/name`).
    def acceptance(self, acceptance, key, entry=""):
        texts = {}
        readme = acceptance / "README.md"
        text = self.read(readme)
        if text is not None:
            texts[readme] = text
            self.markdown(readme, text)
        self.tsv(acceptance / "corrections.tsv", 4, ["date", "sample", "fix", "languages"])
        supported = {"README.md", "corrections.tsv", "scenarios.tsv", "verdicts.tsv", "diagnostics.tsv", "classes.tsv", "cases"}
        extra = {value[len(entry):] for (lesson_key, kind, value) in self.registry
                 if lesson_key == key and kind == "acceptance-entry" and value.startswith(entry)}
        try:
            for item in acceptance.iterdir():
                value = entry + item.name
                if item.name in extra and item.name in supported:
                    self.used.add((key, "acceptance-entry", value))
                    self.error(item, "stale exception acceptance-entry: the entry is supported without it")
                elif item.name in extra:
                    self.except_(item, key, "acceptance-entry", value)
                elif item.name not in supported:
                    self.error(item, "unsupported acceptance entry; add a format-specific check")
                elif item.name != "cases" and not item.is_file():
                    self.error(item, "acceptance table/document must be a file")
        except OSError as exc:
            self.error(acceptance, str(exc))
        formats = 0
        scenarios = None
        if (acceptance / "scenarios.tsv").exists():
            table = acceptance / "scenarios.tsv"
            scenarios = scenario_counts(self.read(table) or "")
            # A chapter's own grammar is excepted per chapter (`K/own`), like acceptance-entry.
            own = self.exception(key, "scenarios-format", entry + "own") is not None
            silenced = self.scenarios(table, own)
            if own and silenced:
                self.except_(table, key, "scenarios-format", entry + "own", f"{silenced} generic grammar messages")
            formats += 1
        verdict_counts = None
        verdicts, classes = None, {}
        if (acceptance / "verdicts.tsv").exists():
            verdicts = self.verdicts(acceptance / "verdicts.tsv")
            values = list(verdicts.values()) if isinstance(verdicts, dict) else []
            verdict_counts = (len(values), values.count("ok"), values.count("refused"))
            if (acceptance / "diagnostics.tsv").exists():
                self.diagnostics(acceptance / "diagnostics.tsv", verdicts)
            if (acceptance / "classes.tsv").exists():
                classes = self.classes(acceptance / "classes.tsv", verdicts)
            formats += 1
        else:
            for table in ("diagnostics.tsv", "classes.tsv"):
                if (acceptance / table).exists():
                    self.error(acceptance, f"{table} without verdicts.tsv")
        if (acceptance / "cases").exists() and not (acceptance / "verdicts.tsv").is_file():
            self.error(acceptance, "cases/ without verdicts.tsv")
        if not formats:
            self.error(acceptance, "no supported acceptance table; add a format-specific check")
        return texts, scenarios, verdict_counts, verdicts, classes

    def choices(self, text):
        section = re.search(r"^## Решает реализация\s*$(.*?)(?=^## |\Z)", text, re.S | re.M)
        return len(re.findall(r"^\d+\.\s", section.group(1), re.M)) if section else None

    def openapi_or_exception(self, contract, key):
        if self.exception(key, "no-openapi") is None:
            self.openapi(contract)
        elif contract.exists():
            self.used.add((key, "no-openapi", "-"))
            self.error(contract, "stale exception no-openapi: the contract exists")
        else:
            self.except_(contract, key, "no-openapi", "-")

    def stale(self, key, where):
        for row in sorted(r for r in self.registry if r[0] == key and r not in self.used):
            self.error(where, f"stale exception {row[1]} {row[2]}: this lesson does not need it")

    def lesson(self, lesson):
        if lesson.parent.parent == self.root / "Platform":
            return self.platform_lesson(lesson)
        if lesson.parent.parent != self.root or not re.fullmatch(r"[0-9]{2}-.+\.md", lesson.name):
            self.error(lesson, "expected module/NN-slug.md under repository root")
            return
        module = lesson.parent.name
        number = int(lesson.name[:2])
        key = f"{module}/{number:02}"
        prefix = f"{module.split('_', 1)[0]}/{number}"
        spec = lesson.parent / "spec"
        norms = spec / f"{lesson.stem}.norms.md"
        instructions = spec / f"{lesson.stem}.README.md"
        texts, ids = {}, []
        for path in [lesson, norms, instructions]:
            text = self.read(path)
            if text is not None:
                texts[path] = text
                self.markdown(path, text)
                if path == norms:
                    ids = self.norms(path, text, prefix)
                    self.data_paragraph(path, text, prefix)
        self.openapi_or_exception(spec / f"{lesson.stem}.api.openapi.yaml", key)
        acceptance = self.root / "Source/tests/testdata/acceptance" / module / f"{number:02}"
        more, scenarios, verdict_counts, verdicts, classes = self.acceptance(acceptance, key)
        texts.update(more)
        schema, schema_refs = spec / f"{lesson.stem}.schema.yaml", spec / f"{lesson.stem}.references.tsv"
        if schema.exists() or schema_refs.exists():
            self.spec_schema(schema, schema_refs, acceptance / "cases", verdicts, classes)
        choices = self.choices(texts[norms]) if norms in texts else None
        for path, text in texts.items():
            self.counts(path, text, prefix, ids, scenarios, path == instructions, verdict_counts, choices or None,
                        lecture=path == lesson)
        if scenarios is not None:
            self.directives(acceptance / "scenarios.tsv", self.stands(module))
        self.stale(key, acceptance)
        self.stats["lessons"] += 1

    # A lesson of the Platform module (ADR-0083): Platform/NN-<процесс>/NN-<процесс>.md, norms per chapter
    # spec/NN.K-<процесс>.norms.md (or one spec/NN-<процесс>.norms.md), one instruction and one OpenAPI, acceptance per
    # chapter acceptance/K/ (or acceptance/). Each chapter is checked as a lesson of its own; the lecture and the
    # instruction count the whole lesson. An ADR-0085 pair next to chapter norms checks that chapter's corpus.
    def platform_lesson(self, lesson):
        stem = lesson.stem
        if not re.fullmatch(r"[0-9]{2}-[a-z][a-z-]*", stem) or lesson.parent.name != stem:
            self.error(lesson, "expected Platform/NN-<процесс>/NN-<процесс>.md")
            return
        number, process = stem[:2], stem[3:]
        key = f"P/{number}"
        spec, acceptance = lesson.parent / "spec", lesson.parent / "acceptance"
        whole = spec / f"{stem}.norms.md"
        chapters = sorted(p for p in spec.glob(f"{number}.[1-9]-{process}.norms.md"))
        if whole.exists() and chapters:
            self.error(whole, "a lesson has either one norms file or chapter norms, not both")
        parts = [(p.name.split("-", 1)[0].split(".")[1], p) for p in chapters] or [(None, whole)]
        instructions = spec / f"{stem}.README.md"
        texts, all_ids, owned, total_choices = {}, [], set(), 0
        totals = {"scenarios": None, "verdicts": None}
        for path in [lesson, instructions]:
            text = self.read(path)
            if text is not None:
                texts[path] = text
                self.markdown(path, text)
        self.openapi_or_exception(spec / f"{stem}.api.openapi.yaml", key)
        try:
            entries = sorted(acceptance.iterdir()) if chapters else []
        except OSError as exc:
            self.error(acceptance, str(exc))
            entries = []
        names = {chapter for chapter, _ in parts}
        for entry in entries:
            if not (entry.is_dir() and entry.name in names):
                self.error(entry, "acceptance of a lesson with chapters holds only chapter directories acceptance/K/")
        for chapter, norms in parts:
            prefix = f"{key}.{chapter}" if chapter else key
            text = self.read(norms)
            ids, scenarios, verdict_counts, chapter_texts = [], None, None, {}
            if text is not None:
                self.markdown(norms, text)
                ids = self.norms(norms, text, prefix)
                owned |= self.data_paragraph(norms, text, prefix, key if chapter else None)
                chapter_texts[norms] = text
            where = acceptance / chapter if chapter else acceptance
            verdicts, classes = None, {}
            if where.is_dir():
                more, scenarios, verdict_counts, verdicts, classes = self.acceptance(where, key, f"{chapter}/" if chapter else "")
                chapter_texts.update(more)
                if scenarios is not None:
                    self.directives(where / "scenarios.tsv", self.stands())
            # The ADR-0085 pair moves with the chapter that owns the corpus (ADR-0086 Р4) until the lesson takes its
            # form source (ADR-0087): spec/NN.K-<процесс>.schema.yaml and .references.tsv next to the chapter norms.
            base = norms.name[:-len(".norms.md")]
            schema, schema_refs = spec / f"{base}.schema.yaml", spec / f"{base}.references.tsv"
            if schema.exists() or schema_refs.exists():
                self.spec_schema(schema, schema_refs, where / "cases", verdicts, classes)
            elif not chapter:
                self.error(acceptance, "no acceptance directory")
            choices = self.choices(text) if text is not None else None
            # A chapter's own texts count the chapter.
            for path, body in chapter_texts.items():
                self.counts(path, body, prefix, ids, scenarios, False, verdict_counts, choices or None)
            all_ids += ids
            total_choices += choices or 0
            for name, value in (("scenarios", scenarios), ("verdicts", verdict_counts)):
                if value is not None:
                    old = totals[name]
                    if name == "scenarios":
                        totals[name] = (value if old is None else
                                        (old[0] + value[0], old[1] + value[1], old[2] | {f"{chapter}/{n}" for n in value[2]}))
                    else:
                        totals[name] = value if old is None else tuple(a + b for a, b in zip(old, value))
        if self.catalog is not None and chapters:
            shared = {k for (k, _), row in self.catalog.items() if row["owner"] == key}
            for missing in sorted(shared - owned):
                self.error(lesson, f"«Данные»: no chapter owns {missing}, the catalog gives it to {key}")
        # The lecture and the instruction count the whole lesson: sums over the chapters.
        for path, text in texts.items():
            self.counts(path, text, key, all_ids, totals["scenarios"], path == instructions, totals["verdicts"],
                        total_choices or None, lecture=path == lesson)
        self.stale(key, acceptance)
        self.stats["lessons"] += 1

def main():
    args = arguments().parse_args()
    check = Check(args.root, args.exceptions)
    for name in args.lessons:
        check.lesson((check.root / name).resolve())
    for error in check.errors:
        print("ERROR", error)
    for line in check.excepted:
        print("EXCEPTION", line)
    print("COUNTS", " ".join(f"{key}={value}" for key, value in sorted(check.stats.items())))
    verdict = "FAIL" if check.errors else f"PASS with {len(check.excepted)} exceptions" if check.excepted else "PASS"
    print(verdict, "structural checks only; semantic review and implementation acceptance remain separate")
    return int(bool(check.errors))


if __name__ == "__main__":
    sys.exit(main())
