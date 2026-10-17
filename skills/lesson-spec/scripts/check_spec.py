#!/usr/bin/env python3
"""Read-only structural checks for the published lecture + shared spec layout.

No product imports, execution of acceptance requests, or network reference loading.
Requires PyYAML, openapi-spec-validator and markdown-it-py; see validation.md.
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

EXCEPTIONS = Path(__file__).resolve().parent.parent / "exceptions.tsv"


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
SCENARIO_HEADER = ["scenario", "step", "request", "expect"]


def scenario_counts(text):
    """Scenarios, steps and scenario names of any scenarios.tsv format: one row per step, the scenario first."""
    steps = Counter()
    for line in text.splitlines():
        cols = line.split("\t")
        if line and not line.startswith("#") and cols != SCENARIO_HEADER and cols[0]:
            steps[cols[0]] += 1
    return len(steps), sum(steps.values()), set(steps)


class Check:
    def __init__(self, root, exceptions=None):
        self.root = root.resolve()
        self.errors = []
        self.stats = Counter()
        self.excepted = []
        self.registry = {}
        self.used = set()
        if exceptions is not None:
            self.load_exceptions(exceptions)

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
                        re.fullmatch(r"М[0-9]+[A-ZА-Я]*/[0-9]+-[0-9]+", children[2].content)):
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
                if not isinstance(paths, list) or not paths or any(not isinstance(p, list) or not p or any(not isinstance(k, str) or not k for k in p) for p in paths):
                    raise ValueError("paths must be nonempty arrays of nonempty string segments")
                if len({tuple(p) for p in paths}) != len(paths):
                    raise ValueError("duplicate diagnostic paths")
                if not isinstance(lines, list) or any(type(n) is not int or n < 1 for n in lines):
                    raise ValueError("line numbers must be positive JSON integers")
                if len(lines) != len(set(lines)):
                    raise ValueError("duplicate diagnostic line numbers")
                self.stats["diagnostics"] += 1
            except (ValueError, TypeError) as exc:
                self.error(path, f"line {line}: {exc}")

    def lesson(self, lesson):
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
        contract = spec / f"{lesson.stem}.api.openapi.yaml"
        if self.exception(key, "no-openapi") is None:
            self.openapi(contract)
        elif contract.exists():
            self.used.add((key, "no-openapi", "-"))
            self.error(contract, "stale exception no-openapi: the contract exists")
        else:
            self.except_(contract, key, "no-openapi", "-")
        acceptance = self.root / "Source/tests/testdata/acceptance" / module / f"{number:02}"
        readme = acceptance / "README.md"
        text = self.read(readme)
        if text is not None:
            texts[readme] = text
            self.markdown(readme, text)
        self.tsv(acceptance / "corrections.tsv", 4, ["date", "sample", "fix", "languages"])
        supported = {"README.md", "corrections.tsv", "scenarios.tsv", "verdicts.tsv", "diagnostics.tsv", "cases"}
        extra = {value for (lesson_key, kind, value) in self.registry
                 if lesson_key == key and kind == "acceptance-entry"}
        try:
            names = set()
            for entry in acceptance.iterdir():
                names.add(entry.name)
                if entry.name in extra and entry.name in supported:
                    self.used.add((key, "acceptance-entry", entry.name))
                    self.error(entry, "stale exception acceptance-entry: the entry is supported without it")
                elif entry.name in extra:
                    self.except_(entry, key, "acceptance-entry", entry.name)
                elif entry.name not in supported:
                    self.error(entry, "unsupported acceptance entry; add a format-specific check")
                elif entry.name != "cases" and not entry.is_file():
                    self.error(entry, "acceptance table/document must be a file")
        except OSError as exc:
            self.error(acceptance, str(exc))
        formats = 0
        scenarios = None
        if (acceptance / "scenarios.tsv").exists():
            table = acceptance / "scenarios.tsv"
            scenarios = scenario_counts(self.read(table) or "")
            own = self.exception(key, "scenarios-format", "own") is not None
            silenced = self.scenarios(table, own)
            if own and silenced:
                self.except_(table, key, "scenarios-format", "own", f"{silenced} generic grammar messages")
            formats += 1
        verdict_counts = None
        if (acceptance / "verdicts.tsv").exists():
            verdicts = self.verdicts(acceptance / "verdicts.tsv")
            values = list(verdicts.values()) if isinstance(verdicts, dict) else []
            verdict_counts = (len(values), values.count("ok"), values.count("refused"))
            if (acceptance / "diagnostics.tsv").exists():
                self.diagnostics(acceptance / "diagnostics.tsv", verdicts)
            formats += 1
        elif (acceptance / "diagnostics.tsv").exists():
            self.error(acceptance, "diagnostics.tsv without verdicts.tsv")
        if (acceptance / "cases").exists() and not (acceptance / "verdicts.tsv").is_file():
            self.error(acceptance, "cases/ without verdicts.tsv")
        if not formats:
            self.error(acceptance, "no supported acceptance table; add a format-specific check")
        choices = None
        if norms in texts:
            section = re.search(r"^## Решает реализация\s*$(.*?)(?=^## |\Z)", texts[norms], re.S | re.M)
            choices = len(re.findall(r"^\d+\.\s", section.group(1), re.M)) if section else None
        for path, text in texts.items():
            self.counts(path, text, prefix, ids, scenarios, path == instructions, verdict_counts, choices or None,
                        lecture=path == lesson)
        if scenarios is not None:
            stands = self.root / "Source/tests/testdata/acceptance"
            self.directives(acceptance / "scenarios.tsv", [stands / "М10_Platform/01/README.md", stands / module / "01/README.md"])
        for row in sorted(r for r in self.registry if r[0] == key and r not in self.used):
            self.error(acceptance, f"stale exception {row[1]} {row[2]}: this lesson does not need it")
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
