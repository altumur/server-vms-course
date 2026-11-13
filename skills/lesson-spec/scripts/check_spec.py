#!/usr/bin/env python3
"""Read-only structural checks for the published lecture + shared spec layout.

No product imports, execution of acceptance requests, or network reference loading.
Requires PyYAML, openapi-spec-validator and markdown-it-py; a lesson with a form schema next to its norms (ADR-0085)
also jsonschema, ruamel.yaml and regress. See validation.md.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

SCRIPTS = Path(__file__).resolve().parent
EXCEPTIONS = SCRIPTS.parent / "exceptions.tsv"
# Form schema next to the norm (ADR-0085): spec/<lesson>.schema.yaml and .references.tsv, run by manifest_schema/run.py.
# One environment for check_spec (both modes), the skill tests, the В7 stack and the SUT: pinned with hashes.
REQUIREMENTS = Path(__file__).resolve().parent / "requirements.txt"
SCHEMA_INSTALL = ("uv run --no-project --python 3.12 --with-requirements skills/lesson-spec/scripts/requirements.txt "
                  "python skills/lesson-spec/scripts/check_spec.py")


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lessons", nargs="*",
                        help="module/NN-slug.md; only the new shared-spec layout; none — every Platform lesson of "
                             "Platform/lessons.tsv and every VMS/NN-*/NN-*.md lesson, strictly (one result for one tree, whatever the shell globs)")
    parser.add_argument("--root", type=Path, default=Path.cwd(),
                        help="complete course source root, default cwd; exports require a separate identity proof")
    parser.add_argument("--exceptions", type=Path, default=EXCEPTIONS,
                        help="registry of allowed deviations, default the skill's exceptions.tsv")
    parser.add_argument("--cyrillic-debt", type=Path, default=SCRIPTS.parent / "cyrillic-debt.tsv",
                        help="ADR-0121 (8) per-file debt for this source snapshot")
    parser.add_argument("--strict-coverage", action="store_true",
                        help="every references.tsv row of a form source must be the sole cause of a corpus case")
    parser.add_argument("--scope", choices=("all", "platform", "vms"), default="all",
                        help="independent source phases; canonical VMS always uses VMS/PLATFORM_PIN")
    parser.add_argument("--vms-candidate", help="full course commit: separate proposed-repin report; never changes Owner pin")
    parser.add_argument("--vms-live", action="store_true",
                        help="separate nonblocking diagnostic against current working Platform")
    parser.add_argument("--vms-evidence", type=Path,
                        help="fresh directory outside source for retained VMS views and JSON phase report")
    return parser


try:
    import yaml
    from jsonschema import Draft202012Validator
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


def pointer_token(key):
    return str(key).replace("~", "~0").replace("/", "~1")


def references(document, external=None, place=lambda where: where, *, root_kind="document"):
    """Walk reference-bearing positions, including their targets, without interpreting payloads.

    A local `#…` resolves in the document that holds the $ref. Without `external` every other $ref is unsupported;
    with it a cross-file $ref goes to `external(ref, position, kind)`, which returns the target document,
    fragment, position formatter and its own external resolver. The latter keeps nested relative refs based
    on their referring resource. `root_kind="schema"` walks a standalone JSON Schema, not an OpenAPI document."""
    seen, active = set(), []

    def walk(node, kind, doc, where, here, resolve):
        if not isinstance(node, (dict, list)) or (id(node), kind) in seen:
            return
        active.append((here(where), id(doc)))
        try:
            yield from visit(node, kind, doc, where, here, resolve)
        finally:
            active.pop()

    def visit(node, kind, doc, where, here, resolve):
        if not isinstance(node, (dict, list)) or (id(node), kind) in seen:
            return
        seen.add((id(node), kind))
        if kind.startswith("[]"):
            if isinstance(node, list):
                for index, value in enumerate(node):
                    yield from walk(value, kind[2:], doc, f"{where}/{index}", here, resolve)
            return
        if not isinstance(node, dict):
            return
        if kind.startswith("*"):
            for key, value in node.items():
                yield from walk(value, kind[1:], doc, f"{where}/{pointer_token(key)}", here, resolve)
            return
        if kind == "schema":
            # These alter reference resolution; never claim root-pointer validation for them.
            for keyword in ("$id", "$dynamicRef", "$recursiveRef"):
                if keyword in node:
                    raise ValueError(f"unsupported schema keyword {keyword} at {here(where)}; "
                                     "needs resolver-specific check")
            if "$schema" in node and node["$schema"] not in {
                "https://spec.openapis.org/oas/3.1/dialect/base", "https://json-schema.org/draft/2020-12/schema"
            }:
                raise ValueError(f"unsupported schema dialect at {here(where)}; needs dialect-specific check")
        if kind in REFERENCE_OBJECTS and "$ref" in node:
            ref = node["$ref"]
            at = here(f"{where}/$ref")
            # Resolve before yielding or calling the library, including targets in extensions.
            try:
                if resolve is not None and isinstance(ref, str) and not ref.startswith("#"):
                    target_doc, fragment, target_here, target_resolve = resolve(ref, at, kind)
                else:
                    target_doc, fragment, target_here, target_resolve = doc, ref, here, resolve
                target = pointer(target_doc, fragment)
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                raise ValueError(f"unresolved/unsupported $ref {ref!r} at {at}: {exc}") from exc
            canonical_fragment = "#" + unquote(fragment.removeprefix("#"), errors="strict")
            target_at = target_here(canonical_fragment)
            chain = [name for name, _ in active]
            if target_at in chain:
                first = chain.index(target_at)
                closed = active[first:] + [(target_at, id(target_doc))]
                if len({identity for _, identity in closed}) > 1:
                    raise ValueError("cycle of cross-file $ref: " + " → ".join(name for name, _ in closed))
            yield ref
            yield from walk(target, kind, target_doc, canonical_fragment, target_here, target_resolve)
        if kind in {"paths", "responses", "callback"}:
            child = {"paths": "path", "responses": "response", "callback": "path"}[kind]
            for key, value in node.items():
                if isinstance(key, str) and not key.startswith("x-") and key != "$ref":
                    yield from walk(value, child, doc, f"{where}/{pointer_token(key)}", here, resolve)
        else:
            for key, child in OBJECT_EDGES.get(kind, {}).items():
                yield from walk(node.get(key), child, doc, f"{where}/{pointer_token(key)}", here, resolve)

    yield from walk(document, root_kind, document, "#", place, external)


# Built sections between their markers: the form of ADR-0087, the data families of ADR-0088 and the form of the
# canonical view of ADR-0089 (chapter 2.2).
FORM_MARKERS = {"<!-- form:begin -->", "<!-- form:end -->", "<!-- families:begin -->", "<!-- families:end -->",
                "<!-- canonical:begin -->", "<!-- canonical:end -->",
                "<!-- checklist-inventory:begin -->", "<!-- checklist-inventory:end -->"}   # опись чеклистов (2026-11-06)
# Acceptance chapters whose puts.tsv (and puts/) the script checks (form_source.vectors.Chapter.puts): chapter 2.2 with
# the view column, chapter 2.3 in three columns.
PUTS_CHAPTERS = {("P/02", "2/"), ("P/02", "3/")}
VARIANTS_CHAPTER = ("P/02", "5/")                     # variants/ — форма (аудит Gemini P/02, свойства 24, 25)


REQ_ANCHOR = re.compile(r"<!-- (?:req: (?:P/[0-9]{2}(?:\.[0-9]+)?-R[0-9]{3}|P/AC-R[0-9]{3})|removed: (?:P/[0-9]{2}(?:\.[0-9]+)?-R[0-9]{3}|P/AC-R[0-9]{3}) by ADR-[0-9]{4}) -->")   # P/NN-RNNN — урок одной главой (как check_forms.REQ)


def _template_marker_source(text):
    """Mask only the two literal brace tokens recognized as inline code by CommonMark."""
    from markdown_it.rules_inline.backticks import backtick
    from markdown_it.rules_inline.image import image

    parser = MarkdownIt("commonmark")
    source = text

    def normalized(state):
        nonlocal source
        source = state.src

    def positioned(rule, kind):
        def apply(state, silent):
            start, count = state.pos, len(state.tokens)
            matched = rule(state, silent)
            if matched and not silent and len(state.tokens) > count:
                token = state.tokens[-1]
                if token.type == kind and (kind == "image" or token.content in ("{{", "}}")):
                    token.meta["template_source_span"] = (start, state.pos)
            return matched
        return apply

    parser.core.ruler.after("normalize", "template_source_positions", normalized)
    parser.inline.ruler.at("backticks", positioned(backtick, "code_inline"))
    parser.inline.ruler.at("image", positioned(image, "image"))
    try:
        tokens = parser.parse(text)
    except ValueError:
        return text                         # The unchanged link pass reports the parser error; exempt nothing.
    masked = list(source)
    lines = source.split("\n")
    starts, offset = [], 0
    for line in lines:
        starts.append(offset)
        offset += len(line) + 1
    for inline in tokens:
        if inline.type != "inline" or inline.map is None:
            continue

        def positions(children, base=0):
            for child in children or []:
                span = child.meta.get("template_source_span")
                if span is None:
                    continue
                begin, end = span
                if child.type == "code_inline":
                    yield from (base + i for i in range(begin, end) if inline.content[base + i] in "{}")
                elif child.type == "image":
                    # CommonMark parses the image label's children from the text immediately after ![.
                    yield from positions(child.children, base + begin + 2)

        marked, offset = set(positions(inline.children)), 0
        for number, line in enumerate(inline.content.split("\n"), inline.map[0]):
            body = line.strip(" \t")
            if body and number < len(lines):
                at = lines[number].find(body)
                # Container prefixes/heading syntax are outside this literal line slice. Never guess an alignment.
                if at >= 0 and at == lines[number].rfind(body):
                    left = len(line) - len(line.lstrip(" \t"))
                    for position in marked:
                        if offset + left <= position < offset + left + len(body):
                            masked[starts[number] + at + position - offset - left] = " "
            offset += len(line) + 1
    return "".join(masked)


def markdown_links(tokens):
    for token in tokens:
        if token.type == "link_open":
            yield token.attrGet("href")
        elif token.type == "image":
            yield token.attrGet("src")
            # Children form the alt text, not independently rendered links or HTML.
            continue
        elif token.type == "html_block" and token.content.strip() in FORM_MARKERS:
            continue                                  # a built section (ADR-0087, ADR-0088) between its markers
        elif token.type == "html_block" and REQ_ANCHOR.fullmatch(token.content.strip()):
            continue                                  # the anchor of a requirement or its tombstone (ADR-0122 доп. (1) п. 1)
        elif token.type in {"html_inline", "html_block"}:
            raise ValueError("unsupported raw HTML; local links/resources need a separate check")
        if token.children:
            yield from markdown_links(token.children)


def validate(document, path=None, loaded=None):
    # Defense in depth: the dependency must not fetch anything even if its traversal changes. A cross-file $ref,
    # already resolved and checked by `references`, is served from the documents read (`loaded`: file URI → document).
    if not loaded:
        OpenAPIV31SpecValidator(SchemaPath.from_dict(document, handlers={})).validate()
        return
    served = {unquote(uri): doc for uri, doc in loaded.items()}

    def serve(uri):
        if unquote(uri) not in served:
            raise ValueError(f"reference outside the checked documents: {uri}")
        return served[unquote(uri)]

    OpenAPIV31SpecValidator(SchemaPath.from_dict(document, base_uri=path.as_uri(), handlers={"file": serve})).validate()


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


# Files a desktop leaves in any directory; never part of a lesson (not tracked by git).
IGNORED = {".DS_Store"}


# The layout of a lesson (ADR-0124; addendum (1) item 6: both layouts for the time of the move). A lesson (or `common`)
# with `ru/` is in the new one: the English source on the canonical path, the Russian text for people in `ru/` (the
# lecture `ru/NN-<имя>.md`, the translation of every source `X` — `ru/X`), logs in `journal/`. Without `ru/` — the former
# one (ADR-0121: `en/<имя>.en.md` next to the Russian text, the lecture and `corrections.tsv` in place).
def lesson_home(path):
    """The directory of a lesson for its lecture or any file of it in `ru/`: `Platform/NN-x/ru/NN-x.md` → `Platform/NN-x`."""
    path = Path(path)
    return path.parent.parent if path.parent.name == "ru" else path.parent


def lecture_of(home):
    """The lecture of a lesson by its layout: `ru/NN-<имя>.md` (ADR-0124) or `NN-<имя>.md`."""
    home = Path(home)
    return home / "ru" / f"{home.name}.md" if (home / "ru").is_dir() else home / f"{home.name}.md"


def human_text(path, root):
    """The Russian text of a lesson file: in the layout of ADR-0124 the translation `ru/X` of the source `X`, otherwise the
    file itself. The checks of norms, «Данные», counts and families read the Russian text (their words are Russian);
    `en_mirror` holds the source and the translation to one content."""
    import en_mirror                                # the homes of the layout: lessons, the root, a module directory
    path = Path(path)
    moved = en_mirror.home_of(path, root)
    if moved and moved[1].parts[0] not in ("ru", "journal"):
        return moved[0] / "ru" / moved[1]
    return path


def outside_export(path, root):
    """`ru/` or `journal/` of a lesson in the layout of ADR-0124, `ru/` of the root or of a module directory — not in the
    export (ADR-0124 item 4, addendum (1) item 4)."""
    import en_mirror
    moved = en_mirror.home_of(os.path.normpath(path), root)
    return bool(moved) and moved[1].parts[0] in ("ru", "journal")


def source_file(path, root):
    """A Markdown file the generator reads and the export carries: outside `ru/` and `journal/` of a lesson in the layout
    of ADR-0124, a source `X` of the root or of a module directory with `ru/X`, or an English `en/<имя>.en.md` of the
    former layout."""
    import en_mirror
    moved = en_mirror.home_of(path, root)
    if moved:
        return moved[1].parts[0] not in ("ru", "journal")
    try:
        parts = Path(path).relative_to(root).parts
    except ValueError:
        return False
    if len(parts) < 3 or parts[0] not in ("Platform", "VMS"):
        return False
    if (Path(root) / parts[0] / parts[1] / "ru").is_dir():
        return False
    return len(parts) >= 2 and parts[-2] == "en" and parts[-1].endswith(".en.md")
EXCEPTION_KINDS = {"no-openapi", "scenarios-format", "acceptance-entry", "no-acceptance", "no-schema",
                   "data-paragraph", "family-read", "implied"}
# Виды, которые читает только режим В7 (стандартные файлы): их устаревание он и называет, не уборка урока.
V7_EXCEPTIONS = {"family-read", "implied"}
# Classes of a loader refusal (М10/2 Н4): `refused:<class>`. On the standard files of В7 the class is the layer of the
# refusal (ADR-0092 п. 6).
REFUSAL_CLASSES = {"text", "key", "value", "reference", "name", "catalogue"}
REFUSAL_CLASSES_V7 = {"text", "form", "relations", "catalogue"}
# The standard files of В7 (ADR-0092; PLAN-TRANSITION п. 1): the form of the manifest in JSON Schema. Their presence
# switches the form, family and canonical checks from the dialect (form_source) to the В7 stack (v7/).
MANIFEST_SCHEMA_V7 = Path("Platform/02-installer/spec/02.1-installer.schema.json")
V7_INSTALL = SCHEMA_INSTALL


# Data family sections (ADR-0088): markers in the norms of the owning chapter, common definitions of the schemas.
FAMILIES_BEGIN, FAMILIES_END = "<!-- families:begin -->", "<!-- families:end -->"
FAMILIES_COMMON = Path("Platform/common/data/common.form.yaml")


def family_place(row, v7=False):
    """A catalog schema is NN-<процесс>/data/<семья>.form.yaml (on В7 — .schema.json) of the owner lesson, for row, JSON
    object and JSON file only (ADR-0088 п. 1, доп. (1) Р2; file — ADR-0083 доп. (11), JSON content is checked when the
    family builds); the same rule as form_source.families.schema_place, without the text layer."""
    suffix = r"\.schema\.json(?:#[a-z][a-z0-9-]*)?" if v7 else r"\.form\.yaml"   # #<слово>: V7-DOMAIN-SLOT-PULSE-SCHEMA-01
    match = re.fullmatch(r"([0-9]{2})-[a-z][a-z-]*/data/[^/#]+" + suffix, row["schema"])
    if not match:
        raise ValueError(f"schema {row['schema']} is not NN-<процесс>/data/<семья>"
                         f"{'.schema.json[#<слово>]' if v7 else '.form.yaml'} (ADR-0088 п. 1)")
    if row["kind"] not in {"row", "object", "file"}:
        raise ValueError("a schema is only for row, JSON object and JSON file (ADR-0088 доп. (1) Р2, ADR-0083 доп. (11))")
    if not re.fullmatch(rf"P/{match.group(1)}(\.(?:0|[1-9][0-9]?))?", row["owner"]):
        raise ValueError(f"schema {row['schema']} is not in the lesson of its owner {row['owner']}")


# Lessons of the Platform module: Platform/lessons.tsv. Columns process (the lesson's process: role and argument of
# the runner w2c-run.sh) and unit (its systemd unit in P/02.4 Н1.1) are checked against the lifecycle heads and the
# unit block; `-` — no process or no unit. Without both columns (transition) the check is skipped.
LESSONS = Path("Platform/lessons.tsv")
LESSONS_BASE = ["lesson", "dir", "title"]
LESSONS_NAMES = ["process", "unit"]
LESSONS_DELTA = ["delta_base"]   # ADR-0122 доп. (1) п. 7: SHA курса, с которого урок правится дельтами; «-» — урок по ADR-0114
DELTA_BASE = re.compile(r"-|[0-9a-f]{9,40}")
UNITS_NORMS = Path("Platform/02-installer/spec/02.4-installer.norms.md")
# Entries of the unit block that are not the unit of one process; exempt from «every `.service` entry with a role is
# the process of a lesson».
UNITS_EXEMPT = {
    "common",                       # общее всех долгоживущих юнитов, не юнит
    "w2c-workers.service/.timer",   # скрипт воркеров по заказу (Н1.5): один на сервер, все роли сервера, своей роли нет
}
UNIT_ENTRY = re.compile(r"^  ([^\s:#][^:]*?):(?=\s|$)(.*)$")
UNIT_ROLE = re.compile(r"(?<![\w-])роль\s+([^\s;,()]+)")
UNIT_RUNNER = re.compile(r"(?<![\w-])w2c-run\.sh\s+([^\s;,()]+)(?:\s+(<[^\s<>;,()]+>))?")


def lifecycle_head(text):
    """The head of a lifecycle.md: the title and the first paragraph after it, up to a blank line, a list, a heading
    or a table."""
    lines = text.splitlines()
    head, started = lines[:1], False
    for line in lines[1:]:
        stripped = line.strip()
        if not stripped:
            if started:
                break
            continue
        if re.match(r"(#|[-*+] |[0-9]+[.)] |\|)", stripped):
            break
        head.append(line)
        started = True
    return "\n".join(head)


def unit_entries(text):
    """The unit block of P/02.4 Н1.1: `units:` of the first yaml block after the heading «Н1.1»; each entry
    `  <имя>[, <имя>]: …` (indent two) with its continuation lines (deeper indent) → (line, names, text)."""
    heading = re.search(r"^#{2,6} [НN]1\.1\b.*$", text, re.M)
    if not heading:
        return None
    rest = text[heading.end():]
    fence = re.search(r"^```ya?ml\n(.*?)^```", rest, re.M | re.S)
    if not fence:
        return None
    first = text[:heading.end()].count("\n") + rest[:fence.start(1)].count("\n") + 1
    entries, inside = [], False
    for offset, line in enumerate(fence.group(1).splitlines()):
        if line and not line[0].isspace():
            inside = line.split("#", 1)[0].strip() == "units:"
            continue
        if not inside or not line.strip():
            continue
        match = UNIT_ENTRY.match(line)
        if match:
            names = [n.strip() for n in match.group(1).split(",")]
            entries.append([first + offset, names, match.group(2)])
        elif entries and line.startswith("   "):
            entries[-1][2] += "\n" + line
    return [tuple(e) for e in entries]


# Data contract catalog (ADR-0083 доп. (2) п. 1–2, form decisions/inbox/2026-10-18-каталог-данных-форма.md).
CATALOG = Path("Platform/common/data/catalog.tsv")
CATALOG_FIELDS = ["key", "kind", "owner", "ops", "readers", "when", "version", "schema", "norm"]
# `when` resolves against the manifest form source (P/02.1); the closed list of derived words stands in the catalog
# header: `# when — … закрытого перечня: <слово> — <пояснение>[; <слово> — <пояснение>]…` (решение «Архитектора»
# 2026-10-20, коммит курса 9ca4837ad).
MANIFEST_FORM = Path("Platform/02-installer/spec/02.1-installer.form.yaml")
WHEN_WORDS = re.compile(r"(?:перечня:|closed list:|;)\s*([a-z_]+(?:\.[a-z_]+)*) — ")   # en — шапка по-английски (ADR-0121)
CATALOG_KINDS = {"row", "object", "file", "dir"}
CATALOG_OPS = {"create", "put", "cas", "guard", "mark", "delete", "append"}
ROLE = r"(?:console|resource|domainagent|domainconsole|domain|admin|configstore-door|<s>(?:controller|worker|domain)|proc:[0-9]{2}-[a-z][a-z-]*)"
LESSON = r"(?:М[0-9]+[A-ZА-Я]*/[0-9]{1,2}|P/[0-9]{2}(?:\.[0-9]+)?)"
DATA_LINE = re.compile(r"^- (владеет|пишет|читает):\s*(.*?);?\s*$")
SEE_ALSO_LINE = re.compile(r"^\s*(?:See also|См\. также):")
# The roles of a lesson's process among the catalog participants and readers (участник — роль файла прав, форма
# каталога): the process of Platform/lessons.tsv by this table, else the process name itself; and always
# `proc:<каталог урока>`. `<s>domain` — воркер подсистемы на домене (P/03.7), `admin` — установщик `w2cctl`,
# `configstore-door` — демон хранилища.
PROCESS_ROLES = {
    "<sub>worker": {"<s>worker", "<s>domain"},
    "<sub>controller": {"<s>controller"},
    "configstore": {"configstore-door"},
    "w2cctl": {"admin"},
}
# `schema` = `manifest`: the form of the row is given by the subsystem manifest (its manifest key in the catalog key); no
# family in data/ (ADR-0083 доп. (11), решение «Архитектора» по ревью стадии B 3–5; ADR-0086). Only for keys with one of
# these manifest keys.
MANIFEST_FORMS = {"unit.rows", "tables", "objects.rows", "domain.books.from", "domain.kept"}
# id-map of the old norms (ADR-0083, module-design «Прослеживаемость»): the column `new` holds checklist ids P/NN[.K]-MM
# (and scenario and vector addresses, which these checks do not read).
IDMAP = Path("decisions/history/platform/id-map.tsv")
IDMAP_FIELDS = ["old", "new", "chapter", "subject", "note"]
TESTSUB = Path("Platform/common/data/testsub")
TESTSUB_FILES = ("testsub.subsystem.yaml", "testsub2.subsystem.yaml")
LEGACY_VERDICTS = Path("Platform/02-installer/acceptance/1/spec_verdicts")
# The VMS module (ADR-0090 доп. (1) «Условия старта», доп. (2)): its lessons, data catalog and id-map are read from
# VMS/common/; a lesson's manifest is VMS/NN-<имя>/<subsystem>.subsystem.yaml. The bytes of Source/vms/ are the frozen
# witness's (доп. (6) п. 8, (7) п. 4): after the start nobody edits them, the list of their sha256 is recorded at the
# start next to the boundary hooks and every file of Source/vms/ must match it.
VMS_DIR = Path("VMS")
VMS_LESSONS = Path("VMS/common/lessons.tsv")
VMS_LESSONS_FIELDS = ["lesson", "dir", "title", "subsystem", "status"]
VMS_STATUS = {"translated", "not translated"}
VMS_CATALOG = Path("VMS/common/data/catalog.tsv")
# The VMS catalog (решение «Архитектора» по запросу VMS «семьи в открытых местах», вариант А): the Platform columns and
# `place` — a row is the value of an open place of a Platform family (v7.vms); owner V/NN[.K], the norm a VMS or
# Platform lesson address.
VMS_CATALOG_FIELDS = CATALOG_FIELDS + ["place"]
VMS_LESSON = r"V/[0-9]{2}(?:\.(?:0|[1-9][0-9]?))?"
VMS_IDMAP = Path("decisions/history/vms/id-map.tsv")
VMS_FROZEN = Path("tools/vms-boundary/source-vms.sha256")
VMS_FROZEN_DIR = Path("Source/vms")
# A chapter of a VMS lesson that waits for the decision of a request (ADR-0090 доп. (1) «Запрос»): its status line
# links an existing request file; until the decision it has the sections Н0–Н5 and an empty checklist. A stub with
# checklist ids is stale: the marker goes with the first norm.
VMS_STUB = re.compile(r"^\*\*Статус: ждёт решения запроса\*\*", re.M)
VMS_REQUEST = re.compile(r"\]\(([^()\s]*decisions/inbox/[0-9]{4}-[0-9]{2}-[0-9]{2}-запрос-vms-[^()\s]*\.md)\)")


def chapter_key(path):
    """Порядок глав по номеру, а не по строке: 8.0, 8.1, …, 8.9, 8.10."""
    m = re.match(r"[0-9]{2}\.([0-9]+)-", path.name)
    return (int(m.group(1)) if m else -1, path.name)


# Номер главы — 0, 1–99 (главы 8.0 и 8.10 урока 8).
CHAPTER = r"(?:0|[1-9][0-9]?)"
STAND_NAME = r"[a-z][a-z0-9-]*"     # a stand directory acceptance/<name>/ of a lesson; the same as target_registry.STAND
NORM_ID = r"(?:М[0-9]+[A-ZА-Я]*/[0-9]+|[PV]/[0-9]{2}(?:\." + CHAPTER + r")?|P/AC)-[0-9]+"
REGISTERED_SHARED_LESSONS = {
    "P/AC": {
        "kind": "shared_acceptance_lesson_not_platform_process",
        "norms": Path("Platform/common/acceptance/spec/acceptance.norms.md"),
        "instructions": Path("Platform/common/acceptance/spec/acceptance.README.md"),
    },
}
# The system checklist (ADR-0130 Addendum (19) п. 6): items of a lesson that need several lessons, the OS or a host; an
# optional h2 after the readiness checklist, in both languages. Its ids are checklist ids (id-map, ru↔en), they carry no
# stage of stages.tsv and may not be placed on one.
SYSTEM_EN, SYSTEM_RU = "System checklist", "Перечень урока системы"
STAGE_NORM_REQUIRED = {"P/01", "P/02", "P/03", "P/04"}   # ADR-0133 (43): explicit adoption; absence of item elements cannot opt out.
INVENTORY_BEGIN = "<!-- checklist-inventory:begin -->"   # опись чеклистов в instruction (решение 2026-11-06)
INVENTORY_END = "<!-- checklist-inventory:end -->"
# A section of an old lesson that moved keeps only a pointer: its text starts with «Перенесено в»; «Остаётся здесь» —
# part of it stays.
MOVED_SECTION = re.compile(r"^Перенесено в\b")
STAYS = re.compile(r"[Оо]стаётся здесь")


def parse_roles(text, what, role=ROLE):
    """`role(cond),role` → {role}; a condition belongs to its role, never holds `;` or nested `(`."""
    roles, pos = set(), 0
    while pos < len(text):
        match = re.match(role + r"(?:\(([^()]*)\))?", text[pos:])
        if not match or (match.group(1) is not None and ";" in match.group(1)):
            raise ValueError(f"{what}: expected role[(condition)] at {text[pos:]!r}")
        roles.add(re.match(role, text[pos:]).group(0))
        pos += match.end()
        if pos < len(text):
            if text[pos] != ",":
                raise ValueError(f"{what}: expected ',' at {text[pos:]!r}")
            pos += 1 + (text[pos + 1:pos + 2] == " ")
    if not roles:
        raise ValueError(f"{what}: no roles")
    return roles


def parse_ops(text, role=ROLE):
    """`op=role(cond),role; op=…` → {op: {role}}; a condition belongs to its role, never holds `;` or nested `(`."""
    ops = {}
    for part in text.split("; "):
        op, sep, rest = part.partition("=")
        if not sep or op not in CATALOG_OPS or op in ops:
            raise ValueError(f"operation {op!r} unknown, repeated or without participants")
        ops[op] = parse_roles(rest, f"participants of {op}", role)
    return ops


def key_pattern(key):
    """Catalog key → (regex, literal length, sample key, manifest keys): `<слово>` is one segment, a trailing `/*` the
    family; `<manifest:ключ>` is a segment named by that manifest key — patterns with different manifest keys never
    overlap."""
    family = key.endswith("/*")
    body = key[:-2] if family else key
    parts = re.split(r"(<[^<>]+>)", body)
    regex = "".join("[^/]+" if part.startswith("<") else re.escape(part) for part in parts)
    sample = "".join("x" if part.startswith("<") else part for part in parts)
    literal = sum(len(part) for part in parts if not part.startswith("<"))
    manifest_keys = tuple(part[10:-1] for part in parts if part.startswith("<manifest:"))
    if family:
        regex, sample = regex + "/.+", sample + "/x"
    return re.compile(regex), literal, sample, manifest_keys


def path_segment(segment):
    """A diagnostic path segment: a mapping key (nonempty string) or a list index (non-negative integer)."""
    if isinstance(segment, str):
        return bool(segment)
    return type(segment) is int and segment >= 0
SCENARIO_HEADER = ["scenario", "step", "request", "expect"]
# Count words of a scenario total («восемь сценариев»): nominative, up to twenty; larger totals are written in digits.
NUMBER_WORDS = {w: i for i, w in enumerate(
    "один два три четыре пять шесть семь восемь девять десять одиннадцать двенадцать тринадцать четырнадцать "
    "пятнадцать шестнадцать семнадцать восемнадцать девятнадцать двадцать".split(), 1)}


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


def outline(text, id_pattern=NORM_ID, checklist_title="Чеклист готовности"):
    """Norms text → (h2 headings, checklist ids): an id is the strong text that opens a list item of «Чеклист
    готовности» after `[ ]`/`[x]`. `checklist_title` is one h2 title or a tuple of them (the readiness checklist and
    the system checklist, ADR-0130 Addendum (19) п. 6)."""
    titles = (checklist_title,) if isinstance(checklist_title, str) else tuple(checklist_title)
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
        if (token.type == "inline" and section in titles and
                len(stack) == 3 and stack[0] in {"bullet_list_open", "ordered_list_open"} and
                stack[1:] == ["list_item_open", "paragraph_open"]):
            children = [child for child in token.children or []
                        if child.type != "text" or child.content]
            if (len(children) >= 4 and children[0].type == "text" and
                    re.fullmatch(r"\[[ xX]\]\s+", children[0].content) and
                    children[1].type == "strong_open" and children[2].type == "text" and
                    children[3].type == "strong_close" and
                    (id_pattern is None or re.fullmatch(id_pattern, children[2].content))):
                ids.append(children[2].content)
            elif id_pattern is None:
                ids.append("")                 # registered lessons reject a checklist row without an id
        if token.nesting == 1:
            stack.append(token.type)
        elif token.nesting == -1:
            stack.pop()
    return headings, ids


def section_latin(name):
    """`Н1.2а` and `N1.2a` are one section number (ADR-0121 addendum (5) item 1: N… in Latin, the suffix by its order)."""
    return re.sub(r"^Н", "N", name).translate(str.maketrans("абвгдежз", "abcdefgh"))


def section_body(text, name):
    """The text of the section `Нx[.y]` of old norms (heading `## Нx …` or `### Нx.y …`) up to the next heading,
    stripped; None if there is no such heading."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        match = re.match(r"(#{2,4}) ([НN][0-9](?:\.[0-9]+[а-яa-h]?)?)(?:\s|$)", line)
        if match and section_latin(match.group(2)) == section_latin(name):
            body = []
            for rest in lines[i + 1:]:
                if re.match(r"#{1,6} ", rest):
                    break
                body.append(rest)
            return "\n".join(body).strip()
    return None


class Check:
    def __init__(self, root, exceptions=None, strict_coverage=False, *, scope=None):
        if scope not in (None, "platform", "vms"):
            raise ValueError("unknown checker source phase")
        self.scope = scope
        self.root = root.resolve()
        self.strict_coverage = strict_coverage
        self.errors = []
        self.system_ids = set()   # ids of system checklists (SYSTEM_RU/SYSTEM_EN): checklist ids without a stage
        self.stats = Counter()
        self.excepted = []
        self.registry = {}
        self.used = set()
        self.catalog = None
        self.lessons = None
        self.vms_request_forms = None
        self._refusal_words = None
        self._standard_forms = None
        self.processes_checked = False
        self.catalog_checked = False
        self.idmap = None
        self.vms_idmap = {}
        self.vms_rows = None                         # строки каталога VMS (v7.vms.read_catalog), судит vms_families()
        self.contracts = {}                          # OpenAPI file → (document or None, checked without errors)
        self.schema_documents = {}                   # standalone JSON Schema, separate from OpenAPI contracts
        self.loading = []                            # documents being checked: a cross-file $ref back is a cycle
        self.cross_refs = set()                      # positions of cross-file $ref counted once per run
        self.v7 = (self.root / MANIFEST_SCHEMA_V7).is_file()
        self.star_readers = {}                       # ключ каталога → роли, чьи нормы его читают (readers `*`)
        self.lessons_seen = set()
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
        """`М12A/3` → М12A_*/spec/03-*.norms.md; `P/03` → Platform/NN-<процесс>/spec/03-*.norms.md, каталог — по
        Platform/lessons.tsv (None if absent)."""
        module, _, number = address.partition("/")
        number, _, chapter = number.partition(".")
        if module == "P":
            names = {row["lesson"]: row["dir"] for _, row in self.lessons_table()[1]}
            dirs = [self.root / "Platform" / names[number]] if number in names else []
        else:
            dirs = sorted(self.root.glob(f"{module}_*"))
        for directory in dirs:
            found = sorted((directory / "spec").glob(f"{int(number):02}-*.norms.md"))
            found = [f for f in found if re.fullmatch(r"[0-9]{2}-[^.]+\.norms\.md", f.name)]
            if module == "P":
                # A lesson split into chapters: the named chapter, else the first one.
                chapters = sorted((directory / "spec").glob(f"{int(number):02}.{chapter or '*'}-*.norms.md"), key=chapter_key)
                found += [f for f in chapters if re.fullmatch(r"[0-9]{2}\." + CHAPTER + r"-[^.]+\.norms\.md", f.name)]
            if found:
                return found[0]
        return None

    def lessons_table(self):
        """Platform/lessons.tsv → (has the process and unit columns, [(line, {column: value})]); columns by its header
        `# lesson<TAB>dir<TAB>title[<TAB>process<TAB>unit]`. Read once."""
        if self.lessons is not None:
            return self.lessons
        path = self.root / LESSONS
        self.lessons = (False, [])
        if not path.exists():
            return self.lessons
        text = self.read(path) or ""
        header = next((line[1:].strip().split("\t") for line in text.splitlines() if line.startswith("# lesson\t")),
                      LESSONS_BASE)
        if header not in (LESSONS_BASE, LESSONS_BASE + LESSONS_NAMES, LESSONS_BASE + LESSONS_NAMES + LESSONS_DELTA):
            self.error(path, f"header expected {' '.join(LESSONS_BASE)} [{' '.join(LESSONS_NAMES)} [{' '.join(LESSONS_DELTA)}]], "
                             f"got {' '.join(header)}")
            header = LESSONS_BASE
        rows = [(n, dict(zip(header, cols))) for n, cols in self.tsv(path, len(header))]
        for n, row in rows:
            base = row.get("delta_base")
            if base is not None and not DELTA_BASE.fullmatch(base):
                self.error(path, f"line {n}: delta_base {base!r} is neither - nor a commit sha (ADR-0122 addendum (1) item 7)")
        self.lessons = (header != LESSONS_BASE, rows)
        return self.lessons

    # Process names (Platform/lessons.tsv process, unit): the lifecycle head of a lesson with a process names it in
    # backquotes; its unit is an entry of the P/02.4 Н1.1 unit block whose `роль` and `w2c-run.sh` argument are the
    # process; every other `.service` entry with a role is the process of some lesson. Once per run.
    def process_names(self):
        self.processes_checked = True
        present, rows = self.lessons_table()
        if not present:
            if rows:
                self.stats["process_names"] = "absent"
            return
        table, units_path = self.root / LESSONS, self.root / UNITS_NORMS
        entries, processes, checked = None, set(), 0

        def units():
            nonlocal entries
            if entries is None:
                text = self.read(units_path) if units_path.exists() else None
                entries = (unit_entries(text) if text is not None else None) or []
                if not entries:
                    self.error(units_path, "no unit block: `units:` in the yaml block of «Н1.1»")
            return entries

        for line, row in rows:
            process, unit = row["process"], row["unit"]
            if not process or not unit:
                self.error(table, f"line {line}: lesson {row['lesson']}: process and unit are required (`-` — none)")
                continue
            if process != "-":
                processes.add(process)
            if process == "-" and unit == "-":
                continue
            checked += 1
            if process != "-":
                lifecycle = self.root / "Platform" / row["dir"] / "lifecycle.md"
                if not lifecycle.exists():
                    self.error(lifecycle, f"lesson {row['lesson']} has process {process} but no lifecycle.md")
                else:
                    text = self.read(human_text(lifecycle, self.root))
                    if text is not None and f"`{process}`" not in lifecycle_head(text):
                        self.error(lifecycle, f"the head (title and first paragraph) does not name the process "
                                              f"`{process}` (lessons.tsv line {line})")
            if unit == "-":
                continue
            found = [e for e in units() if unit in e[1]]
            if not found:
                if entries:
                    self.error(units_path, f"Н1.1 units: no entry {unit}: (lesson {row['lesson']}, lessons.tsv line "
                                           f"{line})")
                continue
            entry_line, _, body = found[0]
            if process == "-":
                continue
            for word, pattern in (("роль", UNIT_ROLE), ("w2c-run.sh", UNIT_RUNNER)):
                for value in pattern.findall(body):
                    if isinstance(value, tuple):
                        # runner command with a subsystem argument names the process by both words:
                        # `w2c-run.sh worker <sub>` — process `<sub>worker` (ADR-0091 доп. (5) п. 1)
                        value, arg = value
                        if arg and process == arg + value:
                            continue
                    if value != process:
                        self.error(units_path, f"line {entry_line}: {unit} {word} {value}, lessons.tsv gives "
                                               f"process {process} (lesson {row['lesson']})")
        for entry_line, names, body in (units() if units_path.exists() else []):
            if any(name in UNITS_EXEMPT for name in names) or not any(n.endswith(".service") for n in names):
                continue
            for role in UNIT_ROLE.findall(body):
                if role not in processes:
                    self.error(units_path, f"line {entry_line}: {', '.join(names)} роль {role} is not a process of "
                                           f"lessons.tsv")
        self.stats["process_names"] = checked

    def load_catalog(self, path):
        rows = self.tsv(path, len(CATALOG_FIELDS))
        if not rows or rows[0][1] != CATALOG_FIELDS:
            self.error(path, f"expected header {' '.join(CATALOG_FIELDS)}")
            return
        self.catalog = {}
        words = self.when_words(path)
        when_key = self.manifest_key(path, words)
        for line, cols in rows[1:]:
            row = dict(zip(CATALOG_FIELDS, cols))
            try:
                if not row["key"] or (row["key"], row["kind"]) in self.catalog:
                    raise ValueError("key and kind empty or repeated")
                if any(not re.fullmatch(r"manifest:[a-z_]+(?:\.[a-z_]+)*", v)
                       for v in re.findall(r"<(manifest:[^<>]*)>", row["key"])):
                    raise ValueError("a manifest variable is <manifest:ключ.манифеста>")
                if "<spec:" in row["key"]:
                    raise ValueError("<spec:…> is renamed <manifest:…> (ADR-0086)")
                if row["kind"] not in CATALOG_KINDS:
                    raise ValueError(f"kind is one of {sorted(CATALOG_KINDS)}")
                if not re.fullmatch(LESSON, row["owner"]):
                    raise ValueError("owner is a lesson address (М10/3, М11/6, P/03)")
                row["ops"] = parse_ops(row["ops"])
                row["reader_roles"] = None if row["readers"] == "*" else parse_roles(row["readers"], "readers")
                if not re.fullmatch(r"-|[a-z_]+(?:\.[a-z_]+)*", row["when"]):
                    raise ValueError("when is - or a manifest key")
                if row["when"] != "-" and row["when"] not in words and not when_key(row["when"]):
                    raise ValueError(f"when {row['when']} is neither a key path of {MANIFEST_FORM} nor a derived "
                                     f"word of the catalog header ({', '.join(sorted(words)) or 'none'})")
                if not re.fullmatch(r"[1-9][0-9]*", row["version"]):
                    raise ValueError("version is an integer ≥ 1")
                if row["schema"] == "manifest":
                    named = {v[9:] for v in re.findall(r"<(manifest:[^<>]*)>", row["key"])}
                    if not named & MANIFEST_FORMS or row["kind"] not in {"row", "object"}:
                        raise ValueError(f"schema manifest is for a row or object whose key names one of "
                                         f"{', '.join(sorted(MANIFEST_FORMS))} (<manifest:…>)")
                elif row["schema"] != "-" and not (self.root / "Platform" / row["schema"].split("#", 1)[0]).is_file():
                    raise ValueError(f"schema {row['schema']} is not a file under Platform/")
                elif row["schema"] != "-":
                    family_place(row, self.v7)
                norm = re.match(LESSON, row["norm"])
                if not norm or self.lesson_norms(norm.group(0)) is None:
                    raise ValueError("norm names an existing lesson")
                if self.lesson_norms(row["owner"]) is None:
                    raise ValueError("owner names an existing lesson")
            except ValueError as exc:
                self.error(path, f"line {line}: {exc}")
                continue
            row["pattern"] = key_pattern(row["key"])
            row["line"] = line
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

    # The closed list of derived `when` words from the header line `# when — …` of the catalog.
    def when_words(self, path):
        text = self.read(path) or ""
        heads = [line for line in text.splitlines() if line.startswith("# when — ")]
        return set(WHEN_WORDS.findall(heads[0])) if heads else set()

    # `when` as a key path of the manifest form source: segments go by the keys of mappings, under `names` any segment.
    # Returns the predicate (key path → exists); a missing or broken source refuses every path.
    def manifest_key(self, path, words):
        if self.v7:
            return self.manifest_key_v7(path, words)
        source = self.root / MANIFEST_FORM
        form = None
        if source.is_file():
            if str(SCRIPTS) not in sys.path:
                sys.path.insert(0, str(SCRIPTS))
            try:
                from form_source.source import ANY, SourceError, load_form
                form = load_form(source)
            except ImportError as exc:
                self.error(path, f"when needs the form source loader (ruamel.yaml), missing: {exc}; run: {SCHEMA_INSTALL}")
            except SourceError as exc:
                self.error(source, f"form source: {exc}")
        if form is None:
            return lambda key: False
        for word in sorted(words):
            if form.node_at(word.split(".")) not in (None, ANY):
                self.error(path, f"derived when word {word} is also a key path of {MANIFEST_FORM}")
        return lambda key: form.node_at(key.split(".")) not in (None, ANY)

    # `when` on В7: a key path is a place of the manifest schema (v7.spec.Places).
    def manifest_key_v7(self, path, words):
        if str(SCRIPTS) not in sys.path:
            sys.path.insert(0, str(SCRIPTS))
        try:
            from v7.spec import Places
            places = Places(json.loads((self.root / MANIFEST_SCHEMA_V7).read_text(encoding="utf-8")))
        except (ImportError, OSError, ValueError) as exc:
            self.error(self.root / MANIFEST_SCHEMA_V7, f"when needs the manifest schema: {exc}")
            return lambda key: False

        def has(key):
            return bool(places.place("/" + "/".join(s.replace("~", "~0").replace("/", "~1") for s in key.split("."))))
        for word in sorted(words):
            if has(word):
                self.error(path, f"derived when word {word} is also a key path of {MANIFEST_SCHEMA_V7}")
        return has

    # Paragraph «Данные» in Н1 of a lesson against the catalog: what the lesson owns, writes and reads.
    def data_paragraph(self, path, text, prefix, lesson=None):
        """`lesson` — the lesson address of a chapter (P/01 for P/01.3): its rows may be claimed by any chapter;
        returns what the paragraph says: {"владеет": {key}, "пишет": {key: operation}, "читает": {key}}."""
        said = {"владеет": set(), "пишет": {}, "читает": set()}
        if self.catalog is None:
            return said
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
            return said
        rest = lines[start + 1:]
        for at, line in enumerate(rest):
            if SEE_ALSO_LINE.match(line):          # a «See also» line of the requirement does not end the paragraph
                continue
            match = DATA_LINE.match(line)
            if not match:
                # the list ends here; a later list line before the blank line would be silently dropped (P01.200 judge)
                for later in rest[at + 1:]:
                    if not later.strip():
                        break
                    if DATA_LINE.match(later):
                        self.error(path, f"«Данные»: the list is broken by «{line.strip()[:40]}» before «{later.strip()[:30]}»")
                        break
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
        return said

    def lesson_roles(self, number):
        """Roles of the process of Platform lesson NN among the catalog participants and readers (PROCESS_ROLES and
        `proc:<каталог>`); empty without its row in Platform/lessons.tsv."""
        row = next((r for _, r in self.lessons_table()[1] if r.get("lesson") == number), None)
        if row is None or not row.get("dir"):
            return set()
        roles = {f"proc:{row['dir']}"}
        process = row.get("process") or "-"
        if process != "-":
            roles |= PROCESS_ROLES.get(process, {process})
        return roles

    @staticmethod
    def in_lesson(owner, key):
        """`P/03.2` and `P/03` are in the lesson `P/03`."""
        return owner == key or owner.startswith(key + ".")

    # Paragraphs «Данные» of a moved lesson against the catalog by the roles of its process (разбор ревью стадии B 3–5,
    # №10): a row the process writes (a role of it among the participants of an operation) is in «пишет» of some
    # chapter; a row it reads (a role among the readers; `*` names no reader) — in «читает» or «пишет»; rows of the
    # lesson itself — in «владеет» (data_paragraph). Back: a key in «пишет» has that operation with a role of the process
    # among its participants; a key in «читает» has a role of the process among its readers or participants, readers
    # `*`, or the lesson as owner. «There» skips a row whose owner is an M11 lesson (not yet moved) that no norms file of
    # the lesson names (until lessons 8–10 move), and a row with the exception data-paragraph (lesson P/NN, value — the
    # key); the exception that is not needed is stale (решение «Архитектора» по ревью стадии B 3–5, №10).
    def data_roles(self, lesson, key, number, saids):
        if self.catalog is None:
            return
        roles = self.lesson_roles(number)
        if not roles:
            return
        process = ", ".join(sorted(roles))
        writes, named = set(), set()
        for _, said in saids:
            writes |= set(said["пишет"])
            named |= said["читает"] | set(said["пишет"]) | said["владеет"]
        by_key = {}
        for row in self.catalog.values():
            by_key.setdefault(row["key"], []).append(row)
        texts = [self.read(norms) or "" for norms, _ in saids]
        for k, rows in by_key.items():
            if any(self.in_lesson(r["owner"], key) for r in rows):
                continue
            ops = sorted({op for r in rows for op, who in r["ops"].items() if who & roles})
            if ops and k not in writes:
                message = f"«Данные»: no chapter writes {k}, the catalog gives {', '.join(ops)} to the process ({process})"
            elif not ops and k not in named and any(r["reader_roles"] and r["reader_roles"] & roles for r in rows):
                message = f"«Данные»: no chapter reads {k}, the catalog names the process ({process}) among its readers"
            else:
                continue
            if all(r["owner"].startswith("М11/") for r in rows) and not any(k in text for text in texts):
                self.stats["data_late_layer"] += 1
                continue
            if self.exception(key, "data-paragraph", k) is not None:
                self.except_(lesson, key, "data-paragraph", k)
                continue
            self.error(lesson, message)
        for norms, said in saids:
            for k, op in said["пишет"].items():
                rows = by_key.get(k, [])
                if rows and op and any(op in r["ops"] for r in rows) and                         not any(r["ops"].get(op, set()) & roles for r in rows):
                    self.error(norms, f"«Данные»: writes {k} ({op}), the catalog does not give {op} to the process "
                                      f"({process})")
            for k in said["читает"]:
                rows = by_key.get(k, [])
                if rows and not any(r["reader_roles"] is None or r["reader_roles"] & roles or self.in_lesson(r["owner"], key)
                                    or any(who & roles for who in r["ops"].values()) for r in rows):
                    self.error(norms, f"«Данные»: reads {k}, the catalog names the process ({process}) neither among "
                                      f"its readers nor among its participants")
        self.stats["data_roles"] += 1

    def id_map_rows(self, table=IDMAP):
        """Platform history (or the VMS map) → [(line, {column: value})]. The Platform map is required; cached."""
        if table != IDMAP:
            if table not in self.vms_idmap:
                path = self.root / table
                rows = self.tsv(path, len(IDMAP_FIELDS), IDMAP_FIELDS) if path.exists() else []
                self.vms_idmap[table] = [(line, dict(zip(IDMAP_FIELDS, cols))) for line, cols in rows]
            return self.vms_idmap[table]
        if self.idmap is None:
            path = self.root / IDMAP
            rows = self.tsv(path, len(IDMAP_FIELDS))
            self.idmap = []
            if not rows or rows[0][1] != IDMAP_FIELDS:
                self.error(path, f"expected header {' '.join(IDMAP_FIELDS)}")
            else:
                self.idmap = [(line, dict(zip(IDMAP_FIELDS, cols))) for line, cols in rows[1:]]
                if not self.idmap:
                    self.error(path, "expected at least one id-map row")
        return self.idmap

    # The checklist of a moved chapter against id-map (разбор ревью стадии B 3–5, №36): each id of the checklist is a
    # `new` of id-map, and each `new` of the chapter (P/NN.K-MM, P/NN-MM without chapters) is in the checklist, unless
    # its `old` id is still in the checklist of an old lesson (the norm moves with that lesson: a late-layer chapter,
    # ADR-0083 module-design «Глава позднего слоя»).
    def id_map_chapter(self, norms, prefix, ids, table=IDMAP):
        rows = self.id_map_rows(table)
        if not rows:
            return
        news = {}
        for line, row in rows:
            if re.fullmatch(NORM_ID, row["new"]):
                news.setdefault(row["new"], []).append((line, row["old"]))
        for value in ids:
            if value not in news and not (table == VMS_IDMAP and self.id_map_added_after_move(value, prefix, rows, news)):
                self.error(norms, f"checklist id {value} is not in the column new of {table}")
        for value, entries in sorted(news.items()):
            if not re.fullmatch(re.escape(prefix) + r"-[0-9]+", value) or value in ids:
                continue
            for line, old in entries:
                if old not in self.old_ids():
                    self.error(norms, f"{table} line {line}: new {value} is not in the checklist, and its old {old} "
                                      "is in no old lesson's checklist")
        self.stats["id_map_ids"] += len(ids)

    @staticmethod
    def id_map_added_after_move(value, prefix, rows, news):
        """A VMS item added after the move has no predecessor, so the archived map stays byte-exact without it.

        Owner of the VMS Source, 2026-11-08: such an id is not in the column old and numbers after the last mapped
        id of its chapter; anything else is a renumbering and still needs the map.
        """
        number = re.compile(re.escape(prefix) + r"-([0-9]+)")
        match = number.fullmatch(value)
        if not match or any(row["old"] == value for _, row in rows):
            return False
        mapped = [int(found.group(1)) for found in map(number.fullmatch, news) if found]
        return bool(mapped) and int(match.group(1)) > max(mapped)

    def old_ids(self):
        """Checklist ids of the old lessons (М*_*/spec/NN-*.norms.md). Read once."""
        if getattr(self, "_old_ids", None) is None:
            self._old_ids = set()
            for path in sorted(self.root.glob("М*_*/spec/[0-9][0-9]-*.norms.md")):
                text = self.read(path)
                if text is not None:
                    self._old_ids |= set(outline(text)[1])
        return self._old_ids

    def platform_ids(self):
        """Checklist ids of every Platform norms file (spec/NN-<процесс>.norms.md, spec/NN.K-<процесс>.norms.md)."""
        ids = set()
        for path in sorted((self.root / "Platform").glob("[0-9][0-9]-*/spec/*.norms.md")):
            if re.fullmatch(r"[0-9]{2}(?:\." + CHAPTER + r")?-[^.]+\.norms\.md", path.name):
                text = self.read(path)
                if text is not None:
                    ids |= set(outline(text, NORM_ID, ("Чеклист готовности", SYSTEM_RU))[1])
        return ids

    def norm_moved(self, norm):
        """The norm cell of a catalog row has moved: each of its addresses is a Platform lesson or names sections of an
        old lesson that keep only a pointer («Перенесено в», without «Остаётся здесь»). An old address without a
        section, or with a section that is not found, has not moved."""
        parts = list(re.finditer(LESSON, norm))
        if not parts:
            return False
        for i, match in enumerate(parts):
            address = match.group(0)
            if address.startswith("P/"):
                continue
            tail = norm[match.end():parts[i + 1].start() if i + 1 < len(parts) else len(norm)]
            sections = re.findall(r"(?<![\w.])[НN][0-9](?:\.[0-9]+[а-яa-h]?)?(?![\w.])", tail)
            path = self.lesson_norms(address)
            text = self.read(path) if sections and path is not None else None
            if text is None:
                return False
            for section in sections:
                body = section_body(text, section)
                if body is None or not MOVED_SECTION.match(body) or STAYS.search(body):
                    return False
        return True

    # The catalog against the moved lessons, once per run. №35 (разбор ревью стадии B 3–5): the owner of a row is not an
    # old lesson that has moved — every id of it in id-map has its `new` in a Platform checklist, or the row's norm has
    # moved (norm_moved). В1 (ADR-0083 доп. (11)): a row or JSON object read or written by the process of a moved lesson
    # (a Platform lesson with a lecture; owner — this lesson, or a role of its process among the participants or
    # readers) has `schema`, or the exception no-schema (lesson — the row's owner, value — the key) with its reason;
    # the exception for a row that has a schema or is touched by no moved lesson is stale.
    def catalog_lessons(self):
        self.catalog_checked = True
        if self.catalog is None:
            return
        path = self.root / CATALOG
        moved = {}
        for _, row in self.lessons_table()[1]:
            directory = row.get("dir")
            if directory and lecture_of(self.root / "Platform" / directory).exists():
                moved[row["lesson"]] = self.lesson_roles(row["lesson"])
        ids = self.platform_ids()
        old = {}
        for _, row in self.id_map_rows():
            match = re.fullmatch(r"(М[0-9]+[A-ZА-Я]*/[0-9]+)-[0-9]+", row["old"])
            if match:
                old.setdefault(match.group(1), []).append(row["new"] in ids)
        done = {address for address, landed in old.items() if all(landed)}
        rows = sorted(self.catalog.values(), key=lambda r: r["line"])
        for row in rows:
            owner = row["owner"]
            if owner.startswith("P/"):
                continue
            if owner in done:
                why = f"every id of {owner} in {IDMAP} is in a Platform checklist"
            elif self.norm_moved(row["norm"]):
                why = f"its norm «{row['norm']}» has moved to Platform"
            else:
                continue
            self.error(path, f"line {row['line']}: owner {owner} of {row['key']} is a moved lesson ({why}); "
                             "readdress it by id-map")
            self.stats["moved_owners"] += 1
        need = {}
        for row in rows:
            if row["kind"] not in ("row", "object"):
                continue
            touched = set(r for r in (row["reader_roles"] or set())) | set().union(*row["ops"].values())
            lessons = sorted(n for n, roles in moved.items()
                             if self.in_lesson(row["owner"], f"P/{n}") or roles & touched)
            if lessons:
                need.setdefault(row["key"], []).append((row, lessons))
        for key, entries in need.items():
            without = [(row, lessons) for row, lessons in entries if row["schema"] == "-"]
            owner = entries[0][0]["owner"]
            registered = (owner, "no-schema", key) in self.registry
            if without and registered:
                self.except_(path, owner, "no-schema", key,
                             "read or written by " + ", ".join(sorted({f"P/{n}" for _, ls in without for n in ls})))
                continue
            for row, lessons in without:
                self.error(path, f"line {row['line']}: {key} ({row['kind']}) is read or written by the process of "
                                 f"{', '.join(f'P/{n}' for n in lessons)} and has no schema: a family in data/ or the "
                                 f"exception no-schema {owner} {key} (ADR-0083 доп. (11))")
        for exc in sorted(r for r in self.registry if r[1] == "no-schema" and r not in self.used):
            self.used.add(exc)
            self.error(path, f"stale exception no-schema {exc[0]} {exc[2]}: the row has a schema, is not in the "
                             "catalog under this owner, or no moved lesson reads or writes it")
        self.stats["schema_needed"] = sum(len(e) for e in need.values())

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
            if path.suffix == ".tsv":
                return path.read_bytes().decode("utf-8")
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            self.error(path, str(exc))
            return None

    def markdown(self, path, text):
        if re.search(r"\{\{.*?\}\}", _template_marker_source(text), re.S):
            self.error(path, "unfilled template marker {{...}}")
        try:
            for target in markdown_links(MarkdownIt("commonmark").parse(text)):
                url = urlsplit(target)
                if url.scheme or url.netloc:
                    continue
                if not url.path:                         # an anchor of the same file (as it lies on disk)
                    if url.fragment and unquote(url.fragment) not in self.anchors(path):
                        self.error(path, f"missing anchor: {unquote(target)} — no such heading in this file")
                    continue
                whole = path.parent / unquote(url.path)
                if url.path.startswith("/"):
                    self.error(path, f"absolute local link is not portable: {target}")
                elif not whole.exists():
                    self.error(path, f"missing link target: {target}")
                elif url.fragment and whole.suffix == ".md" and whole.is_file() and \
                        unquote(url.fragment) not in self.anchors(whole):
                    self.error(path, f"missing anchor: {unquote(target)} — no such heading in {self.name(whole)} (anchors as "
                                     "GitHub builds them; ADR-0124 доп. (1) п. 3: a source has English headings)")
                elif source_file(Path(path).resolve(), self.root) and \
                        outside_export(Path(path).resolve().parent / unquote(url.path), self.root):
                    self.error(path, f"a source links into ru/ or journal/, which the export has not: {target} — "
                                     "name it by text (ADR-0124 addendum (1) item 3)")
                self.stats["local_links"] += 1
        except ValueError as exc:
            self.error(path, str(exc))

    def anchors(self, path):
        """Anchors of the headings of a Markdown file as GitHub builds them (github-slugger over the rendered text of
        a heading; a repeated one gets -1, -2…). Read once per run."""
        path = Path(os.path.normpath(Path(path).resolve()))
        cache = self.__dict__.setdefault("_anchors", {})
        if path not in cache:
            import unicodedata
            seen, out, level = {}, set(), None
            try:
                tokens = MarkdownIt("commonmark").parse(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError):
                tokens = []
            for tok in tokens:
                if tok.type == "heading_open":
                    level = tok.tag
                elif tok.type == "inline" and level is not None:
                    words = "".join(c.content for c in (tok.children or []) if c.type in ("text", "code_inline"))
                    base = "".join("-" if ch == " " else ch for ch in words.strip().lower()
                                   if ch in "-_ " or unicodedata.category(ch)[0] in "LNM")
                    n = seen.get(base, 0)
                    seen[base] = n + 1
                    out.add(base if n == 0 else f"{base}-{n}")
                    level = None
            cache[path] = out
            self.stats["anchored_files"] += 1
        return cache[path]

    def openapi(self, path):
        """A lesson's own contract: a checked OpenAPI document with HTTP paths."""
        self.stats["openapi_cross_refs"] += 0
        if self.contract(path, paths=True):
            self.stats["openapi"] += 1

    def contract(self, path, paths=False):
        """Read and check one OpenAPI document once per run: the YAML profile, OpenAPI 3.1, the dialect, every
        reference (local and cross-file), the validator, the openness of object schemas. A lesson's contract also
        needs HTTP paths; a contract another one refers to may hold components only. True if no error."""
        if path in self.contracts:
            doc, clean = self.contracts[path]
            if paths and doc is not None and not (isinstance(doc.get("paths"), dict) and doc["paths"]):
                self.error(path, "OpenAPI: no HTTP paths: unfinished contract or layout decision needed")
                return False
            return clean
        self.contracts[path] = (None, False)
        text = self.read(path)
        if text is None:
            return False
        errors = len(self.errors)
        if "{{" in text:
            self.error(path, "unfilled contract template")
        self.loading.append(path)
        try:
            doc = yaml.load(text, Loader=UniqueLoader)
            # OpenAPI's YAML representation must still represent JSON data.
            json.dumps(doc, allow_nan=False)
            if not isinstance(doc, dict):
                raise ValueError("OpenAPI document must be an object")
            if not str(doc.get("openapi", "")).startswith("3.1."):
                raise ValueError("expected OpenAPI 3.1.x")
            self.contracts[path] = (doc, False)
            if paths and (not isinstance(doc.get("paths"), dict) or not doc["paths"]):
                raise ValueError("no HTTP paths: unfinished contract or layout decision needed")
            if doc.get("jsonSchemaDialect", "https://spec.openapis.org/oas/3.1/dialect/base") not in {
                "https://spec.openapis.org/oas/3.1/dialect/base", "https://json-schema.org/draft/2020-12/schema"
            }:
                raise ValueError("unsupported schema dialect; needs dialect-specific check")
            # Check actual reference positions, not similarly named fields in application data.
            crossed = []
            refs = list(references(doc, lambda ref, at, kind: self.cross_ref(path, ref, at, crossed, kind),
                                   lambda where: f"{self.name(path)}:{where}"))
            self.stats["local_refs"] += sum(1 for ref in refs if ref.startswith("#"))
            validate(doc, path, {p.as_uri(): d for p, (d, _) in
                                (*self.contracts.items(), *self.schema_documents.items()) if d is not None}
                     if crossed else None)
            for pointer in unstated_openness(doc):
                self.error(path, f"OpenAPI: object schema {pointer} does not say its openness "
                                 "(additionalProperties, or unevaluatedProperties on a composite)")
            if self.v7:                              # V7-OPENAPI-PATTERN-LOOKAHEAD-01: подмножество LAYERS § 3
                self.portable_patterns(path, doc)
        except Exception as exc:
            self.error(path, f"OpenAPI: {exc}")
        finally:
            self.loading.pop()
        clean = len(self.errors) == errors
        self.contracts[path] = (self.contracts[path][0], clean)
        return clean

    def schema_document(self, path):
        """Check a standalone JSON Schema resource without treating it as an OpenAPI contract."""
        if path in self.schema_documents:
            return self.schema_documents[path][1]
        self.schema_documents[path] = (None, False)
        text = self.read(path)
        if text is None:
            return False
        errors = len(self.errors)
        self.loading.append(path)
        try:
            doc = strict_json(text)
            if not isinstance(doc, (dict, bool)) or isinstance(doc, dict) and "openapi" in doc:
                raise ValueError("expected a standalone JSON Schema object or boolean, not an OpenAPI document")
            self.schema_documents[path] = (doc, False)
            Draft202012Validator.check_schema(doc)
            crossed = []
            refs = list(references(doc, lambda ref, at, kind: self.cross_ref(path, ref, at, crossed, kind),
                                   lambda where: f"{self.name(path)}:{where}", root_kind="schema"))
            self.stats["local_refs"] += sum(1 for ref in refs if ref.startswith("#"))
            # Keep the owner schema's declared JSON Schema semantics. The explicit-openness style rule
            # applies to schemas written in an OpenAPI contract, not to standalone data-family resources.
            if self.v7:
                self.portable_patterns(path, doc)
        except Exception as exc:
            self.error(path, f"JSON Schema: {exc}")
        finally:
            self.loading.pop()
        clean = len(self.errors) == errors
        self.schema_documents[path] = (self.schema_documents[path][0], clean)
        return clean

    def portable_patterns(self, path, doc):
        """`pattern` и ключи `patternProperties` контракта — в переносимом подмножестве (ADR-0092 п. 14, LAYERS § 3):
        полное совпадение `^(?:…)$`, без просмотров, обратных ссылок, `.` и `\\d \\w`; как у схем семей и манифеста."""
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from v7 import spec as v7spec
        for why in v7spec.unportable(doc):
            self.error(path, f"OpenAPI: {why}")
        self.stats["openapi_patterns"] += len(v7spec.patterns(doc))

    # A cross-file $ref between Platform contracts (decision on the lesson 6 transfer plan, В7): a relative
    # <path>.openapi.yaml#<JSON Pointer> inside Platform/, to the contract of a lesson with a smaller number or to a
    # common contract (Platform/common/); a common contract refers to common contracts only. A closed ref chain through another resource is forbidden;
    # returning to a different pointer of the same file is valid.
    # A later lesson L only from a door of a late-layer chapter that L introduces (decision on commit 10, chapter 6.7):
    # the $ref sits under paths/<door> whose description starts «Глава N.K», and the header of N.K-….norms.md says
    # «Глава позднего слоя: вводит урок L» (or «вводят уроки L1 и L2»); such a chapter is read after 8–10 (step 15).
    def cross_ref(self, source, ref, at, crossed, kind="schema"):
        url = urlsplit(ref)
        if url.scheme or url.netloc or url.query or not url.path:
            raise ValueError("external reference; only a relative <path>.openapi.yaml#<JSON Pointer> "
                             "between Platform/ contracts is checked offline")
        relative = unquote(url.path, errors="strict")
        standalone = relative.endswith(".schema.json")
        if relative.startswith("/") or not (standalone or relative.endswith(".openapi.yaml")):
            raise ValueError("expected a relative OpenAPI contract or standalone .schema.json")
        if standalone and kind != "schema":
            raise ValueError(f"standalone JSON Schema cannot replace an OpenAPI {kind} object")
        if not standalone and "#" not in ref:
            raise ValueError("expected a JSON Pointer after # (the whole document is not a schema)")
        platform = self.root / "Platform"
        target = Path(os.path.normpath(source.parent / relative))
        try:
            where = target.relative_to(platform).parts
            source_where = source.relative_to(platform).parts
            target.resolve().relative_to(platform.resolve())
        except ValueError:
            raise ValueError("a cross-file $ref stays between contracts inside Platform/") from None
        owner = lambda parts: ("common" if parts[0] == "common" else
                               int(parts[0][:2]) if re.fullmatch(r"[0-9]{2}-[a-z][a-z-]*", parts[0]) else None)
        lesson, source_lesson = owner(where), owner(source_where)
        if len(where) < 2 or lesson is None:
            raise ValueError("the target is not in a lesson directory NN-<процесс>/ or common/")
        if target == source:
            raise ValueError("a reference to its own file; use a local #/…")
        if source_lesson == "common" and lesson != "common":
            raise ValueError(f"a common contract refers to lesson {lesson:02}; common contracts refer to common ones")
        if standalone:
            resolved = target.resolve().relative_to(platform.resolve()).parts
            if (len(where) != 3 or where[1] != "data" or len(resolved) != 3 or resolved[1] != "data" or
                    resolved[0] != where[0]):
                raise ValueError("a standalone JSON Schema stays in its declared owner data/ inside Platform/")
            target = target.resolve()
        if (source_lesson != "common" and lesson != "common" and lesson >= source_lesson and
                not (standalone and where[0] == source_where[0])):
            chapter = self.door_chapter(source, source_lesson, at) if source in self.contracts else None
            if lesson == source_lesson or lesson not in self.late_chapters(source.parent).get(chapter, ()):
                raise ValueError(f"reference to a lesson read later: P/{lesson:02} is not read before "
                                 f"P/{source_lesson:02} (allowed: a smaller lesson number, Platform/common/, or a "
                                 f"door under paths/ of a late-layer chapter that lesson {lesson} introduces)")
        if not target.is_file():
            raise ValueError(f"file not found: {self.name(target)}")
        # A target already being checked has a parsed document in its cache.
        # Read that resource without scheduling its whole-file check again;
        # references() detects an actual closed URI+pointer chain.
        in_progress = target in self.loading
        if standalone:
            if not in_progress and not self.schema_document(target):
                raise ValueError(f"the target JSON Schema {self.name(target)} has errors (reported for that file)")
            document = self.schema_documents[target][0]
            fragment = "#" + url.fragment
            value = pointer(document, fragment)
            if not isinstance(value, (dict, bool)):
                raise ValueError("the JSON Pointer target is not a Schema object or boolean")
            Draft202012Validator.check_schema(value)
        else:
            if not in_progress and not self.contract(target):
                raise ValueError(f"the target contract {self.name(target)} has errors (reported for that file)")
            document = self.contracts[target][0]
            fragment = "#" + url.fragment
        if at not in self.cross_refs:
            self.cross_refs.add(at)
            self.stats["openapi_cross_refs"] += 1
        crossed.append(target)
        return (document, fragment, lambda where: f"{self.name(target)}:{where}",
                lambda ref, at, kind: self.cross_ref(target, ref, at, crossed, kind))

    # The chapter K of the door that holds a $ref: paths/<door> whose description starts «Глава N.K»; else None.
    def door_chapter(self, source, lesson, at):
        tokens = at.split(":", 1)[-1].removeprefix("#").split("/")
        if len(tokens) < 3 or tokens[0] or tokens[1] != "paths":
            return None
        door = (self.contracts[source][0] or {}).get("paths", {}).get(tokens[2].replace("~1", "/").replace("~0", "~"))
        found = re.match(r"(?:Глава|Chapter) ([0-9]+)\.([0-9]+)(?![0-9.])", str((door or {}).get("description", "")))  # ADR-0121: описания дверей — по-английски
        return int(found[2]) if found and int(found[1]) == lesson else None

    # Late-layer chapters of a lesson: K → the lessons that introduce it, from the header of NN.K-<процесс>.norms.md.
    def late_chapters(self, spec):
        chapters = {}
        for norms in sorted(spec.glob("[0-9][0-9].*-*.norms.md")):
            key = re.match(r"[0-9]{2}\.([0-9]+)-", norms.name)
            head = "\n".join(human_text(norms, self.root).read_text(encoding="utf-8").splitlines()[:12])   # ru/ (ADR-0124)
            late = re.search(r"Глава позднего слоя: ввод(?:ит|ят) урок(?:и)? ([0-9]+(?:(?:, | и )[0-9]+)*)", head)
            if key and late:
                chapters[int(key[1])] = {int(n) for n in re.findall(r"[0-9]+", late[1])}
        return chapters

    def name(self, path):
        try:
            return path.relative_to(self.root)
        except ValueError:
            return path

    def norms(self, path, text, prefix, allow_empty=False):
        headings, ids = outline(text, NORM_ID, ("Чеклист готовности", SYSTEM_RU))
        for readiness, system in (("Чеклист готовности", SYSTEM_RU),):
            if system in headings and (headings.count(system) != 1 or readiness not in headings
                                       or headings.index(system) < headings.index(readiness)):
                self.error(path, f"the section {system} comes once, after {readiness}")
        self.system_ids |= set(outline(text, NORM_ID, SYSTEM_RU)[1])
        headers = [match.group(1) for heading in headings
                   if (match := re.match(r"[НN]([0-5])(?:\s|$)", heading))]   # N0–N5 латиницей (ADR-0121 доп. (5) п. 1)
        if headers != [str(i) for i in range(6)]:
            self.error(path, "expected Н0–Н5 once, in order")
        if not ids and not allow_empty:
            self.error(path, "no normative checklist ids")
        for value, count in Counter(ids).items():
            if count != 1 or not value.startswith(prefix + "-"):
                self.error(path, f"duplicate or foreign checklist id {value}")
        for title in ["Решает реализация", "Чеклист готовности"]:
            if title not in headings:
                self.error(path, f"missing section {title}")
        self.stats["norm_ids"] += len(ids)
        return ids

    def registered_shared_lessons(self):
        """Validate only explicitly registered nonprocess lessons, without process requirements."""
        import check_forms
        for prefix, registration in REGISTERED_SHARED_LESSONS.items():
            source = self.root / registration["norms"]
            instructions = self.root / registration["instructions"]
            russian, ru_instructions = human_text(source, self.root), human_text(instructions, self.root)
            paths = (source, instructions, russian, ru_instructions)
            if not any(path.exists() or path.is_symlink() for path in paths):
                continue                         # a source snapshot before introduction has no such lesson
            texts = {}
            for path in dict.fromkeys(paths):
                if not path.is_file() or path.is_symlink():
                    self.error(path, "registered shared lesson needs a regular nonsymlink document")
                    continue
                text = self.read(path)
                if text is not None:
                    texts[path] = text
            if source not in texts or russian not in texts:
                continue
            if russian == source:
                self.error(source, "registered shared lesson needs its Russian mirror")
                continue
            source_text, russian_text = texts[source], texts[russian]
            # Reuse the norms parser; its ordinary numeric lesson defaults remain unchanged.
            normalized = source_text.replace("## Implementation decides", "## Решает реализация").replace(
                "## Readiness checklist", "## Чеклист готовности").replace(f"## {SYSTEM_EN}", f"## {SYSTEM_RU}")
            self.norms(source, normalized, prefix)
            en_headings, en_ids = outline(source_text, None, ("Readiness checklist", SYSTEM_EN))
            ru_headings, ru_ids = outline(russian_text, None, ("Чеклист готовности", SYSTEM_RU))
            for path, headings, ids, decides, readiness in (
                    (source, en_headings, en_ids, "Implementation decides", "Readiness checklist"),
                    (russian, ru_headings, ru_ids, "Решает реализация", "Чеклист готовности")):
                structural = [("N" + match[1]) if (match := re.match(r"[НN]([0-5])(?:\s|$)", title))
                              else title for title in headings]
                n6 = ("N6 Production qualification of P/01" if path == source
                      else "N6 Боевая квалификация P/01")
                n6_positions = [i for i, title in enumerate(structural) if title == n6]
                system = SYSTEM_EN if path == source else SYSTEM_RU
                required = [title for title in structural if title != n6]
                if required[-1:] == [system]:
                    required = required[:-1]     # the optional system checklist closes the outline
                if (required != [*(f"N{i}" for i in range(6)), decides, readiness]
                        or len(n6_positions) > 1
                        or any(i <= structural.index("N5") for i in n6_positions
                               if "N5" in structural)):
                    self.error(path, "registered shared lesson expects N0–N5, Implementation decides and Readiness checklist once in order")
                if not ids:
                    self.error(path, "registered shared lesson has no checklist ids")
                for number, count in Counter(ids).items():
                    if not re.fullmatch(re.escape(prefix) + r"-[0-9]+", number) or count != 1:
                        self.error(path, f"duplicate, missing or foreign registered checklist id {number!r}")
            if en_ids != ru_ids:
                self.error(source, "ru↔en: registered checklist ids differ")
            anchors = check_forms.ANCHOR.findall(source_text)
            self.stats["req_anchors"] += len(anchors)
            removed = check_forms.TOMBSTONE.findall(source_text)
            if not anchors:
                self.error(source, "registered shared lesson has no requirement anchors")
            for number, count in Counter(anchors + removed).items():
                if not re.fullmatch(re.escape(prefix) + r"-R[0-9]{3}", number):
                    self.error(source, f"requirement anchor {number} is not of registered lesson {prefix}")
                if count != 1:
                    self.error(source, f"requirement anchor {number} repeats or reuses a removed number")
            for path, text in texts.items():
                if path != source and (check_forms.ANCHOR.search(text) or check_forms.TOMBSTONE.search(text)):
                    self.error(path, "requirement anchors belong only to the registered English norms source")
            for path in self.root.glob("Platform/**/*.md"):
                if path in texts or path.is_symlink() or not path.is_file():
                    continue
                text = self.read(path)
                if text is None or prefix + "-R" not in text:
                    continue
                for token in MarkdownIt("commonmark").parse(text):
                    if token.type == "html_block":
                        numbers = [number for marker in REQ_ANCHOR.finditer(token.content)
                                   for number in (check_forms.ANCHOR.findall(marker.group()) +
                                                  check_forms.TOMBSTONE.findall(marker.group()))]
                        if any(number.startswith(prefix + "-") for number in numbers):
                            self.error(path, f"{prefix} requirement anchors belong to {registration['norms']}")
                            break
            for path, text in texts.items():
                self.markdown(path, text)
            self.stats["registered_shared_lessons"] += 1

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
            n5 = re.search(r"^## [НN]5\b.*?(?=^## |\Z)", text, re.S | re.M)
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
            # «N сценариев / M шагов»; число сценариев — и словом до двадцати, через одно слово («восемь независимых
            # сценариев, 121 шаг»).
            words = "|".join(sorted(NUMBER_WORDS, key=len, reverse=True))
            for match in re.finditer(r"(?<!\w)(\d+|(?i:%s)(?!\w))\s*(?:[а-яё]+\s+)?сценари\w*\s*[/,]\s*(\d+)\s*шаг\w*"
                                     % words, text):
                if not is_total(match):
                    continue
                self.stats["count_phrases"] += 1
                said = match.group(1)
                if (int(said) if said.isdigit() else NUMBER_WORDS[said.lower()]) != total:
                    mismatch(said, total, "scenarios")
                if int(match.group(2)) != steps:
                    mismatch(match.group(2), steps, "steps")
            # Шаги без сценариев — только фразой «Всего N шагов» с начала предложения.
            for match in re.finditer(r"(?:^|(?<=[.:;!?]\s))Всего\s+(\d+)\s+шаг\w*", text, re.M):
                if not is_total(match):
                    continue
                self.stats["count_phrases"] += 1
                if int(match.group(1)) != steps:
                    mismatch(match.group(1), steps, "steps")
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

    # The checklist inventory of the instruction (решение «Архитектора» 2026-11-06, P/08): a block between
    # INVENTORY_BEGIN and INVENTORY_END with the table `| chapter | ids |`; every id in full, in backticks, no ranges.
    # The ids of the block are the ids of all checklists of the lesson, once each; a count said in the block or in the
    # line before it matches; the source and the translation (ADR-0124) hold one set. A lesson without the block in
    # either file owes nothing.
    def inventory_block(self, path, text, key):
        """→ (ids in order, chapter of each id) or None without the block."""
        begin, end = text.find(INVENTORY_BEGIN), text.find(INVENTORY_END)
        if begin < 0 and end < 0:
            return None
        if begin < 0 or end < begin or text.count(INVENTORY_BEGIN) != 1 or text.count(INVENTORY_END) != 1:
            self.error(path, "checklist inventory: expected one begin marker and one end marker after it")
            return None
        body = text[begin + len(INVENTORY_BEGIN):end]
        before = [ln for ln in text[:begin].splitlines() if ln.strip()][-1:]
        before = [ln for ln in before if ln.lstrip().startswith("#")]      # the heading of the block, if right above
        ids, rows, said = [], 0, []
        for line in [*before, *body.splitlines()]:
            stripped = line.strip()
            if not stripped.startswith("|"):
                said += re.findall(r"(?<![\w/.-])(\d+)\s+(?:ids?(?!\w)|id-\w*|пункт\w*|норм\w*|items?(?!\w))",
                                   stripped)
                continue
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) != 2:
                self.error(path, f"checklist inventory: a row of the table | chapter | ids | has {len(cells)} cells")
                continue
            if cells == ["chapter", "ids"] or re.fullmatch(r":?-+:?", cells[0]):
                continue
            rows += 1
            chapter = re.match(r"`?(?:[PV]/)?(?:[0-9]{1,2}\.)?(" + CHAPTER + r")`?(?!\S)", cells[0])   # P/08.0, 08.0, 8.0, 0
            prefix = f"{key}.{chapter[1]}-" if chapter else None
            tokens = re.findall(r"`([^`]*)`", cells[1])
            if re.sub(r"`[^`]*`", "", cells[1]).strip(" ,;") or not tokens:
                self.error(path, f"checklist inventory: chapter {cells[0]}: ids must be full ids in backticks, "
                                 f"separated by commas, got {cells[1]!r}")
            for token in tokens:
                if not re.fullmatch(NORM_ID, token):
                    self.error(path, f"checklist inventory: `{token}` is not a full checklist id (no ranges)")
                    continue
                if prefix and not token.startswith(prefix):
                    self.error(path, f"checklist inventory: {token} is not an id of chapter {cells[0]}")
                ids.append(token)
        if not rows:
            self.error(path, "checklist inventory: no rows in the table | chapter | ids |")
        for value, count in Counter(ids).items():
            if count != 1:
                self.error(path, f"checklist inventory: {value} repeats")
        for number in said:
            self.stats["count_phrases"] += 1
            if int(number) != len(ids):
                self.error(path, f"checklist inventory: says {number} ids, the block lists {len(ids)}")
        return ids

    def checklist_inventory(self, source, translation, key, all_ids):
        blocks = {}
        for path in dict.fromkeys([source, translation]):
            text = self.read(path) if path.exists() else None
            blocks[path] = self.inventory_block(path, text, key) if text is not None else None
        if all(b is None for b in blocks.values()):
            return
        self.stats["checklist_inventories"] += 1
        wanted = set(all_ids)
        for path, ids in blocks.items():
            if ids is None:
                self.error(path, "checklist inventory: the block is missing here, the other language has it")
                continue
            for value in sorted(wanted - set(ids)):
                self.error(path, f"checklist inventory: checklist id {value} is not listed")
            for value in sorted(set(ids) - wanted):
                self.error(path, f"checklist inventory: {value} is in no checklist of the lesson")
        listed = [set(ids) for ids in blocks.values() if ids is not None]
        if len(listed) == 2 and listed[0] != listed[1]:
            self.error(translation, "checklist inventory: the ids differ from the source "
                                    f"({sorted(listed[0] ^ listed[1])})")

    def stage_norms(self, home, key):
        """Required lessons cover all items; other lessons validate item elements they name."""
        required = key in STAGE_NORM_REQUIRED
        table = home / "forms/stages.tsv"
        if not required and not table.exists() and not table.is_symlink():
            return
        if table.is_symlink() or not table.is_file():
            self.error(table, "stage norms: expected an ordinary stages.tsv file")
            return
        text = self.read(table)
        if text is None:
            return
        head = next((line.split("\t") for line in text.split("\n")
                     if line and not line.startswith("#")), [])
        if not {"stage", "norms"} <= set(head):
            if required:
                self.error(table, "stage norms: expected stage and norms columns")
            return
        if len(head) != len(set(head)):
            self.error(table, "stage norms: expected unique stage and norms columns")
            return
        rows = self.tsv(table, len(head), head)
        # A lesson with chapters (spec/NN.K-<process>.norms.md) names items P/NN.K-MM; a lesson without chapters (one
        # spec/NN-<process>.norms.md, as P/04) names them P/NN-MM (audit P/04, defect 1). The other form is an error.
        chaptered = any(re.fullmatch(r"[0-9]{2}\." + CHAPTER + r"-[^.]+\.norms\.md", f.name)
                        for f in (home / "spec").glob("*.norms.md"))
        item = re.compile(r"P/[0-9]{2}\." + CHAPTER + r"-[0-9]{2}" if chaptered else r"P/[0-9]{2}-[0-9]{2}")
        any_item = re.compile(r"P/[0-9]{2}(?:\." + CHAPTER + r")?-[0-9]{2}")
        prefix = key + ("." if chaptered else "-")
        counts, stages = Counter(), {}
        for line, cells in rows:
            row = dict(zip(head, cells))
            for element in row["norms"].split(";"):
                value = element.strip()
                if item.fullmatch(value):
                    counts[value] += 1
                    stages.setdefault(value, []).append(row["stage"])
                elif any_item.fullmatch(value):
                    self.error(table, f"stage norms: {value} has the item form of a lesson "
                                      f"{'without' if chaptered else 'with'} chapters")
        if not required and not counts:
            return
        import m_form
        wanted, system_items, withdrawn = [], set(), set()
        sources = sorted((home / "spec").glob("*.norms.md"))
        if not sources:
            self.error(home / "spec", "stage norms: no canonical norms files")
        for path in sources:
            if path.is_symlink() or not path.is_file():
                self.error(path, "stage norms: expected an ordinary canonical norms file")
                continue
            body = self.read(path)
            if body is None:
                continue
            for value in outline(body, None, "Readiness checklist")[1]:
                if not item.fullmatch(value) or not value.startswith(prefix):
                    self.error(path, f"stage norms: malformed or foreign checklist item {value!r}")
                else:
                    wanted.append(value)
            system_items.update(outline(body, None, SYSTEM_EN)[1])
            withdrawn.update(m_form.withdrawn_items(body))
        expected = set(wanted)
        # A withdrawn item («removed: `ADR-…`», m_form.WITHDRAWN) keeps its id and no requirement: it needs no stage
        # (the Architect on P01.176 item 4, P01.228); a stage may still name it until the stage table drops it.
        withdrawn &= expected
        if required and not expected:
            self.error(home / "spec", "stage norms: no canonical checklist items")
        for value, count in Counter(wanted).items():
            if count != 1:
                self.error(home / "spec", f"stage norms: duplicate canonical checklist item {value}")
        for value in sorted(expected if required else counts.keys() & expected):
            if counts[value] == 0 and value not in withdrawn:
                self.error(table, f"stage norms: checklist item {value} is at no stage")
            elif counts[value] > 1:
                self.error(table, f"stage norms: checklist item {value} repeats at stages {stages[value]}")
        for value in sorted(counts.keys() & system_items):
            self.error(table, f"stage norms: {value} is a system checklist item and has no stage (ADR-0130 Addendum (19) п. 6)")
        for value in sorted(counts.keys() - expected - system_items):
            self.error(table, f"stage norms: {value} is no checklist item of this lesson")
        self.stats["stage_norm_items"] += len(expected)
        self.stats["stage_norm_withdrawn"] += len(withdrawn)
        self.stats["stage_norm_placements"] += sum(counts.values())

    # Every directive a scenario uses is in a stand dictionary («Словарь директив»): the shared one of the Platform
    # module and the module's own (README of lesson 1), which adds only its new directives.
    def directives(self, table, stands):
        known, found = set(), False
        for stand in dict.fromkeys(stands):
            stand = human_text(stand, self.root)       # «Словарь директив» — русский заголовок (ADR-0124: ru/ у common)
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
            self.error(table, f"directive {name} is not in a stand dictionary (Platform/common/acceptance or lesson 1 README of the module)")

    def tsv(self, path, width, header=None):
        text = self.read(path)
        rows = []
        if text is None:
            return rows
        import source_cells
        first = next((line.split("\t") for line in text.split("\n") if line and not line.startswith("#")), [])
        names, decoded, problems = source_cells.table(text, header, bool(header and first != header))
        if problems:
            for problem in problems:
                self.error(path, problem)
            return rows
        if names:
            columns = header if header is not None else (list(decoded[0][1]) if decoded else [])
            for line_no, row in decoded:
                if len(row) != width:
                    self.error(path, f"line {line_no}: expected {width} TSV columns, got {len(row)}")
                else:
                    rows.append((line_no, [row[name] for name in columns]))
            return rows
        for line_no, line in enumerate(text.split("\n"), 1):
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
    def scenarios(self, path, own=False, forms=None):
        steps = Counter()
        silenced = 0
        requests, keys = {}, []
        for line, (scenario, step, request, expect) in self.tsv(path, 4, SCENARIO_HEADER):
            steps[scenario] += 1
            if not scenario or step != str(steps[scenario]):
                self.error(path, f"line {line}: invalid scenario/step sequence")
            requests[(scenario, step)] = request
            keys += [(line, scenario, n) for n in re.findall(r"@key\((\d+)\)", request)]
            before = len(self.errors)
            self.scenario_form(path, line, request, expect, forms)
            if own:
                silenced += len(self.errors) - before
                del self.errors[before:]
            self.refusal_word(path, line, expect)
            self.module_file_binding(path, line, expect)
        # `@key(N)` repeats the key bytes of step N of the same scenario: that step exists and carries a writing
        # request (ACC-06-KEY-SHIFT-01, решение «Архитектора» 2026-10-29: a step inserted before it shifts the number).
        for line, scenario, n in keys:
            target = requests.get((scenario, n))
            if target is None or not re.search(r"(?<!\S)(?:POST|PUT|DELETE) /", target):
                self.error(path, f"line {line}: @key({n}) names step {n} of scenario {scenario}, which has no POST, PUT or DELETE")
        self.stats["scenarios"] += len(steps)
        self.stats["steps"] += sum(steps.values())
        if not steps:
            self.error(path, "empty scenarios table")
        return silenced

    def module_file_binding(self, path, line, expect):
        """Actual @file expectations bind canonical module bytes, never Source witnesses."""
        if not Path(path).is_relative_to(self.root / "Platform"):
            return
        match = re.fullmatch(r"[1-5][0-9]{2} @file (\S+)", expect)
        if match is None or Path(match[1]).name not in {"console.js", "console.css", "console.html"}:
            return
        canonical = Path("Platform/07-console-module/module") / Path(match[1]).name
        target = self.root / canonical
        if match[1] != canonical.as_posix():
            self.error(path, f"line {line}: @file module input must be {canonical}; Source is a frozen witness")
        elif not target.is_file() or target.resolve() != target.absolute():
            self.error(path, f"line {line}: missing canonical module input {canonical} (no symlinks)")
        self.stats["module_file_bindings"] += 1

    # The word of `error` in an expectation is a word of a closed table `data/refusal-words.tsv` (стандарт пробы, ADR-0083,
    # правка В-7). Judged against the union of the tables, not door by door: `@any`, `!contains`, `~`, `$имя` are not words.
    def refusal_words(self):
        if self._refusal_words is None:
            self._refusal_words = set()
            for table in sorted(self.root.glob("*/*/data/refusal-words.tsv")):
                rows = [row.split("\t") for row in table.read_text(encoding="utf-8").splitlines()
                        if row and not row.startswith("#")]
                column = rows[0].index("error")
                self._refusal_words |= {row[column] for row in rows[1:] if len(row) > column}
        return self._refusal_words

    def refusal_word(self, path, line, expect):
        words = self.refusal_words()
        for word in re.findall(r'"error"\s*:\s*"([^"]+)"', expect) if words else ():
            if word[0] not in "@!~$" and word not in words:
                self.error(path, f"line {line}: error word {word!r} is in no refusal-words table")

    # Request forms a VMS scenario may use besides `<МЕТОД> /<путь>` of the console: the table «Директивы и двери VMS»
    # of VMS/common/acceptance/README.md (ADR-0090; one rule for every VMS lesson instead of `K/own` rows per chapter).
    # A form's literal words stay literal; `<МЕТОД>` is an HTTP method, `<путь>` a path from `/`, `<запрос>` (last) a
    # nested request, any other `<…>` one word. Returns ({directive: (pattern, nested)}, [door patterns]).
    def vms_forms(self):
        if self.vms_request_forms is not None:
            return self.vms_request_forms
        readme = human_text(self.root / VMS_DIR / "common/acceptance/README.md", self.root)   # «Директивы и двери VMS» — русский заголовок (ADR-0124: ru/ у common)
        text = self.read(readme) if readme.exists() else None
        section = re.search(r"^## Директивы и двери VMS.*?(?=^## |\Z)", text or "", re.S | re.M)
        directives, doors = {}, []
        def word(token):
            parts = re.split(r"(<[^>]+>)", token)
            out = ""
            for part in parts:
                if part == "<МЕТОД>":
                    out += "(?:GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)"
                elif part == "<путь>":
                    out += r"/\S*"
                elif part.startswith("<") and part.endswith(">"):
                    out += r"\S+"
                else:
                    out += re.escape(part)
            return out
        for form in re.findall(r"^\|\s*`([^`]+)`", section.group(0) if section else "", re.M):
            tokens = form.split()
            nested = tokens[-1] == "<запрос>"
            body = " ".join(word(token) for token in (tokens[:-1] if nested else tokens))
            pattern = re.compile(body + (r" (?P<request>.+)" if nested else ""))
            if tokens[0].startswith("@"):
                directives.setdefault(tokens[0], []).append((pattern, nested))
            else:
                doors.append(pattern)
        self.vms_request_forms = (directives, doors)
        return self.vms_request_forms

    def platform_doors(self):
        """Names of the doors of the common acceptance: the table «**Doors**» of Platform/common/acceptance/README.md (the prefix of `request`)."""
        cached = getattr(self, "_platform_doors", None)
        if cached is not None:
            return cached
        readme = self.root / "Platform/common/acceptance/README.md"
        text = self.read(readme) if readme.exists() else ""
        section = re.search(r"^\*\*Doors\*\*.*?(?=^\*\*Request\.\*\*)", text or "", re.S | re.M)
        self._platform_doors = set(re.findall(r"^\|\s*`([a-z][a-z0-9]*)`\s*\|", section.group(0), re.M)) if section else set()
        return self._platform_doors

    def scenario_form(self, path, line, request, expect, forms=None):
        # `@manual <причина>` — шаг, который стенд не исполняет (ADR-0102 доп. (4) п. 8); ожидание — слово `manual`.
        if request.startswith("@manual "):
            if expect != "manual":
                self.error(path, f"line {line}: @manual expects manual")
            return
        if forms is not None:
            directives, doors = forms
            name = request.split(" ", 1)[0]
            for pattern, nested in directives.get(name, []):
                match = pattern.fullmatch(request)
                if match and nested:
                    return self.scenario_form(path, line, match.group("request"), expect, forms)
                if match:
                    # `@stream-wait` alone waits for `ok <JSON>`, a subset of the message (общий словарь приёмки).
                    if name == "@stream-wait":
                        try:
                            strict_json(expect.removeprefix("ok "))
                            if not expect.startswith("ok "):
                                raise ValueError
                        except (ValueError, TypeError):
                            self.error(path, f"line {line}: directive {name} expects ok <JSON>")
                    elif expect != "ok":
                        self.error(path, f"line {line}: directive {name} expects ok")
                    return
            if any(pattern.fullmatch(request) for pattern in doors):
                request = "GET /"                   # a VMS door form; the expectation is checked as for the console
        # A named door of the common acceptance before the method (README «Doors»): the request after it is checked as usual.
        head, separator, rest = request.partition(" ")
        if separator and re.fullmatch(r"[a-z][a-z0-9]*", head) and re.match(r"^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS) /", rest):
            if head not in self.platform_doors():
                self.error(path, f"line {line}: unknown door {head}; the doors are the table «Doors» of the common acceptance")
                return
            request = rest
        if request.startswith("ASSERT "):
            if expect or not re.fullmatch(r"ASSERT \$\w+ != \$\w+(?: \$\w+)*", request):
                self.error(path, f"line {line}: invalid ASSERT or nonempty expectation")
            return
        # Deliberately invalid JSON requests are acceptance data, not parse errors here.
        if not re.match(r"^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS) /", request):
            self.error(path, f"line {line}: unsupported request form; needs format-specific check")
        # `@oneof <код> <JSON> | <код> <JSON>` — one of the branches (C-ONEOF-01, решение «Архитектора» 2026-10-29);
        # a code class `2xx` stands alone, without a body (общий словарь приёмки).
        oneof = expect.startswith("@oneof ")
        branches = expect[len("@oneof "):].split(" | ") if oneof else [expect]
        if oneof and len(branches) < 2:
            self.error(path, f"line {line}: @oneof needs at least two branches separated by « | »")
        for branch in branches:
            if not oneof and re.fullmatch(r"[1-5]xx", branch):
                continue
            code, separator, body = branch.partition(" ")
            try:
                if not separator or not re.fullmatch(r"[1-5][0-9]{2}", code):
                    raise ValueError("expected HTTP status and JSON body" + (" in every @oneof branch" if oneof else ""))
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
        allowed = REFUSAL_CLASSES_V7 if self.v7 else REFUSAL_CLASSES
        for line, (case, kind) in self.tsv(path, 2):
            if case in seen or verdicts.get(case) != "refused" or kind not in allowed:
                self.error(path, f"line {line}: class case must be unique, have refused verdict and a class of {sorted(allowed)}")
            seen[case] = kind
        if not seen:
            self.error(path, "empty classes table")
        return seen

    # The form schema is a check next to the norm, not the norm (ADR-0085): every case of the lesson corpus goes through
    # the text layer, the schema and the reference pass; its verdict must be verdicts.tsv's and its class classes.tsv's.
    # A difference is a defect of the schema, the norm or the corpus. Missing dependencies fail, never skip.
    def manifest_schema(self, schema, references, cases, verdicts, classes):
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
            from manifest_schema.run import Runner
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
        # Every subsystem manifest of the course must load too, not only the corpus (ADR-0085 доп. (1), Р3).
        # Corpora (cases/, spec_verdicts/) hold refused manifests on purpose; only the manifests subsystems ship are
        # checked here. The VMS manifests are checked in VMS/ (their canon since the start, ADR-0090 доп. (6) п. 8);
        # Source/vms/ holds the frozen witness's bytes and is never form-checked.
        manifests = self.course_manifests()
        for path in sorted(manifests):
            try:
                got = runner.judge(path.read_bytes())
            except Exception as exc:
                self.error(path, f"form schema: runner failed: {exc!r}")
                continue
            if got["verdict"] != "ok":
                why = f"layer {got['layer']}" + (f": {got['errors'][0]}" if got["errors"] else "")
                self.error(path, f"form schema: course manifest refused {got['verdict']} ({why})")
            self.stats["schema_manifests"] += 1

    # The form source of ADR-0087 next to the chapter norms: the section built from it stands in the norms byte for byte
    # between the markers, the corpus goes through the loader built from it (verdict, class, paths, lines), every
    # course manifest loads, and the coverage of references.tsv is counted (strict with --strict-coverage).
    def form_source(self, norms, text, form, references, scalars, acceptance, verdicts, classes):
        if str(SCRIPTS) not in sys.path:
            sys.path.insert(0, str(SCRIPTS))
        try:
            from form_source import Loader, SourceError, build_section, held_rows
            from form_source.section import BEGIN, END
        except ImportError as exc:
            self.error(form, f"form source check needs ruamel.yaml (text layer Н1.1), missing: {exc}; run: {SCHEMA_INSTALL}")
            return
        for path in (references, scalars):
            if not path.is_file():
                self.error(path, "form source needs .form.yaml, .references.tsv and .scalars.tsv (ADR-0087 п. 1)")
                return
        try:
            loader = Loader(form, references, scalars)
            section = build_section(form, references, scalars)
        except SourceError as exc:
            self.error(form, f"form source: {exc}")
            return
        if text is not None:
            lines = text.split("\n")
            begins = [i for i, line in enumerate(lines) if line == BEGIN]
            ends = [i for i, line in enumerate(lines) if line == END]
            if len(begins) != 1 or len(ends) != 1 or ends[0] < begins[0]:
                self.error(norms, f"form source: the norms hold the built section once, between {BEGIN} and {END}")
            else:
                said = "\n".join(lines[begins[0] + 1:ends[0]]) + "\n"
                if said != section:
                    old, new = said.splitlines(), section.splitlines()
                    at = next((i for i, (a, b) in enumerate(zip(old, new)) if a != b), min(len(old), len(new)))
                    self.error(norms, f"form source: the section differs from the built one at its line {at + 1} "
                                      f"(rebuild: python skills/lesson-spec/scripts/form_source/build.py {norms.relative_to(self.root)})")
        if verdicts is None:
            self.error(form, "form source without verdicts.tsv: nothing to check it against")
            return
        diagnostics = {}
        if (acceptance / "diagnostics.tsv").exists():
            for _, (case, paths, lines_) in self.tsv(acceptance / "diagnostics.tsv", 3):
                try:
                    diagnostics[case] = (strict_json(paths), strict_json(lines_))
                except ValueError:
                    pass                                    # diagnostics() names the bad row
        results = []
        for case, expected in sorted(verdicts.items()):
            path = acceptance / "cases" / f"{case}.subsystem.yaml"
            try:
                got = loader.judge(path.read_bytes())
            except OSError:
                continue                                    # verdicts() has named the missing case
            except Exception as exc:
                self.error(path, f"form source: loader failed: {exc!r}")
                continue
            results.append(got)
            why = f"layer {got['layer']}" + (f": {got['why'][0]}" if got["why"] else "")
            if got["verdict"] != expected:
                self.error(path, f"form source: verdict expected {expected}, got {got['verdict']} ({why})")
            elif case in classes and got["class"] != classes[case]:
                self.error(path, f"form source: class expected {classes[case]}, got {got['class']} ({why})")
            elif case in diagnostics:
                paths, lines_ = diagnostics[case]
                if sorted(map(json.dumps, paths)) != sorted(map(json.dumps, got["paths"])):
                    self.error(path, f"form source: paths expected {json.dumps(paths, ensure_ascii=False)}, "
                                     f"got {json.dumps(got['paths'], ensure_ascii=False)} ({why})")
                elif not set(lines_) <= set(got["lines"]):
                    self.error(path, f"form source: lines expected {lines_}, got {got['lines']}")
            self.stats["form_cases"] += 1
        manifests = self.course_manifests()
        for path in sorted(manifests):
            got = loader.judge(path.read_bytes())
            if got["verdict"] != "ok":
                why = f"layer {got['layer']}" + (f": {got['why'][0]}" if got["why"] else "")
                self.error(path, f"form source: course manifest refused {got['class']} ({why})")
            self.stats["form_manifests"] += 1
        held = held_rows(results)
        self.stats["form_rows"] += len(loader.rows)
        self.stats["form_rows_held"] += len(held)
        if self.strict_coverage:
            for row in loader.rows:
                if row.no not in held:
                    self.error(references, f"line {row.no}: no corpus case has this row as its sole cause (ADR-0087 доп. (1) Р10)")

    # The standard files of В7 next to the chapter norms (ADR-0092; PLAN-TRANSITION п. 1.3): the schema, relations and
    # layers are sound, the section «Форма» between the markers is the built one, the corpus goes through the В7 loader
    # (verdict and class — the layer — strictly; diagnostics.tsv paths are a hint, ADR-0092 п. 5), every course manifest
    # loads, the relation rows are held by corpus cases (strict with --strict-coverage).
    def form_v7(self, norms, text, base, acceptance, verdicts, classes):
        if str(SCRIPTS) not in sys.path:
            sys.path.insert(0, str(SCRIPTS))
        try:
            from v7.spec import manifest_check
        except ImportError as exc:
            self.error(norms, f"the standard files need the В7 stack, missing: {exc}; run: {V7_INSTALL}")
            return
        manifests = self.course_manifests()
        try:
            implied = {value for (lesson, kind, value) in self.registry if kind == "implied"}
            extra = self.numeric_loader(base)
            errors, stats = manifest_check(self.root, norms, text, base, acceptance, verdicts, classes, manifests,
                                           self.strict_coverage, implied, extra)
        except ImportError as exc:
            self.error(norms, f"the standard files need the В7 stack, missing: {exc}; run: {V7_INSTALL}")
            return
        for where, message in errors:
            self.error(where, message)
        if "implied_marked" not in stats:            # связи не прочитаны: о реестре implied судить не по чему (Kimi М-5)
            self.stats.update(stats)
            return
        for value in sorted(stats.pop("implied_marked")):
            key = next((k for (k, kind, v) in self.registry if kind == "implied" and v == value), None)
            if key is not None:
                self.except_(base, key, "implied", value)
        for (key, kind, value) in sorted(self.registry):
            if kind == "implied" and (key, kind, value) not in self.used:
                self.used.add((key, kind, value))
                self.error(base, f"stale exception implied {key} {value}: no relation row {value} with x-implied-by")
        self.stats.update(stats)

    def course_manifests(self):
        """Canonical manifests only; a missing new home must not turn a glob empty."""
        paths = []
        for name in TESTSUB_FILES:
            path = self.root / TESTSUB / name
            if not path.is_file() or path.resolve() != path.absolute():
                self.error(path, "required canonical course manifest (regular file without symlinks)")
            else:
                paths.append(path)
        home = self.root / TESTSUB
        if home.is_dir():
            for path in sorted(home.glob("*.subsystem.yaml")):
                if path.name not in TESTSUB_FILES:
                    self.error(path, "unexpected canonical course manifest; expected exactly testsub and testsub2")
        vms = [] if self.scope == "platform" else list((self.root / VMS_DIR).glob("[0-9][0-9]-*/*.subsystem.yaml"))
        return [*vms, *paths]

    def canonical_layout(self):
        """ADR-0083 (115): root notes and frozen Source copies are not aliases."""
        for name in ("Platform/common/NORMATIVE-TERMS.md", "Platform/07-console-module/CONSOLE-MODULE.md"):
            path = self.root / name
            if not path.is_file() or path.resolve() != path.absolute():
                self.error(path, "required canonical document (regular file without symlinks)")
        for name in ("NORMATIVE-TERMS.md", "CONSOLE-MODULE.md", "ru/NORMATIVE-TERMS.md", "ru/CONSOLE-MODULE.md"):
            path = self.root / name
            if path.exists() or path.is_symlink():
                self.error(path, "legacy root document is forbidden; use its Platform canonical home")

    def legacy_spec_verdicts(self):
        """Relocated headerless roster, separate from P02's active corpus and canonical vectors."""
        home = self.root / LEGACY_VERDICTS
        table = home / "spec_verdicts.tsv"
        rows = self.tsv(table, 2)
        seen = set()
        for line, (case, verdict) in rows:
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", case) or case in seen:
                self.error(table, f"line {line}: invalid or duplicate legacy case {case!r}")
                continue
            seen.add(case)
            if verdict not in {"ok", "refused"}:
                self.error(table, f"line {line}: legacy verdict is ok or refused")
            path = home / f"{case}.subsystem.yaml"
            if not path.is_file() or path.resolve() != path.absolute():
                self.error(path, "missing legacy verdict input (regular file without symlinks)")
        if not seen:
            self.error(table, "empty legacy verdict roster")
        try:
            for path in sorted(home.iterdir()):
                if path.name == table.name or path.name in IGNORED:
                    continue
                if path.name == "README.md" and path.is_file():
                    text = self.read(path)
                    if text is not None:
                        self.markdown(path, text)
                    continue
                if path.name not in {f"{case}.subsystem.yaml" for case in seen}:
                    self.error(path, "unlisted legacy verdict input")
        except OSError as exc:
            self.error(home, str(exc))
        self.stats["legacy_spec_verdicts"] += len(seen)

    # The numeric-loader witnesses of P/06 C3 (решение «Архитектора» 2026-11-06): a separate binding outside the corpus
    # of P/02.1 — each row of numeric-loader.cases.tsv is loaded by the same loader as the corpus, refused exactly by
    # its own relation row (which it then holds) or ok. Silent while P/02.1 declares none of the rows; once it declares
    # any, the table, each of the nine named rows and each witness file must be there. → [(path, expect, no)].
    NUMERIC_LOADER_BASE = "Platform/02-installer/spec/02.1-installer"
    NUMERIC_LOADER_TABLE = "Platform/06-console/forms/numeric-loader.cases.tsv"
    NUMERIC_LOADER_ROWS = (160, 161, 162)
    NUMERIC_LOADER_CASES = ("p06-c3-numeric-retire", "p06-c3-numeric-ends", "p06-c3-numeric-delete",
                            "p06-c3-fixed-ends", "p06-c3-fixed-retire", "p06-c3-fixed-delete",
                            "p06-c3-named-retire", "p06-c3-named-ends", "p06-c3-named-delete")

    def numeric_loader(self, base):
        if Path(base).resolve() != (self.root / self.NUMERIC_LOADER_BASE).resolve():
            return []
        try:
            rel = json.loads(Path(str(base) + ".relations.json").read_text(encoding="utf-8"))
            declared = {r.get("no") for r in rel.get("rows", []) if isinstance(r, dict)} & set(self.NUMERIC_LOADER_ROWS)
        except (OSError, ValueError, AttributeError):
            return []                                    # manifest_check names the broken relations file
        table = self.root / self.NUMERIC_LOADER_TABLE
        if not declared and not table.exists():
            return []
        if not table.is_file():
            self.error(table, f"numeric loader: P/02.1 declares relation rows {sorted(declared)}, their witness "
                              "table is missing (решение «Архитектора» 2026-11-06)")
            return []
        header = ["case", "input", "expect", "relation", "norm"]
        out, seen, refused = [], set(), set()
        for line_no, (case, input_, expect, relation, _norm) in self.tsv(table, 5, header):
            where = f"line {line_no}"
            if case not in self.NUMERIC_LOADER_CASES:
                self.error(table, f"{where}: case {case!r} is not one of the nine witnesses of P/06 C3")
                continue
            if case in seen:
                self.error(table, f"{where}: case {case} repeated")
                continue
            seen.add(case)
            if input_ != f"numeric-loader/{case}.subsystem.yaml":
                self.error(table, f"{where}: input of {case} is numeric-loader/{case}.subsystem.yaml, got {input_!r}")
                continue
            if expect == "ok":
                if relation != "-":
                    self.error(table, f"{where}: an ok witness names no relation row, got {relation!r}")
                    continue
                no = None
            elif expect == "refused:relations":
                if relation not in {str(n) for n in self.NUMERIC_LOADER_ROWS}:
                    self.error(table, f"{where}: a refused witness names one of rows {list(self.NUMERIC_LOADER_ROWS)}, "
                                      f"got {relation!r}")
                    continue
                no = int(relation)
                refused.add(no)
            else:
                self.error(table, f"{where}: expect is ok or refused:relations, got {expect!r}")
                continue
            path = table.parent / input_
            if not path.is_file():
                self.error(path, f"numeric loader: witness {case} of {table.name} is missing")
                continue
            out.append((path, expect, no))
        for case in self.NUMERIC_LOADER_CASES:
            if case not in seen:
                self.error(table, f"numeric loader: the row of witness {case} is missing")
        for no in sorted(declared - refused):
            self.error(table, f"numeric loader: relation row {no} of P/02.1 has no refused witness")
        return out

    # Completeness of the unreadable outcomes (решение владельца 2026-10-28, PLAN-TRANSITION п. 1.3): each family of
    # the catalog with a schema names the outcome «the whole row is unreadable» (empty path) for each of its readers —
    # readers ∪ the participants of cas and guard (they read the row before writing); readers `*` — the roles of the
    # lessons whose «Данные» read the key (all Platform lessons in the run, else skipped and counted). A role there
    # without being a reader is red too.
    def outcome_readers(self):
        if not self.v7 or self.catalog is None:
            return
        try:
            from v7.spec import SpecError, is_v7_family, load_family, reading_roles
        except ImportError:
            return                                   # the families check has named the missing stack
        star = {k: set(v) for k, v in self.star_readers.items()}
        rows = [row for _, row in self.lessons_table()[1]
                if row.get("lesson") not in self.lessons_seen
                and any((self.root / "Platform" / row.get("dir", "-") / "spec").glob("*.norms.md"))]
        if rows:                                     # уроки вне прогона: их «Данные» — вспомогательным проходом, без ошибок
            import contextlib
            import io
            aux = Check(self.root, None, False)
            with contextlib.redirect_stdout(io.StringIO()):
                for row in rows:
                    lesson = lecture_of(self.root / "Platform" / row["dir"])
                    if lesson.is_file():
                        aux.lesson(lesson)
            for k, v in aux.star_readers.items():
                star.setdefault(k, set()).update(v)
        everyone = True
        for row in self.catalog.values():
            if not is_v7_family(row):
                continue
            want = reading_roles(row, star.get(row["key"], set()) if everyone else None)
            if want is None:
                self.stats["outcome_readers_skipped"] += 1
                continue
            try:
                _, _, _, path, outcomes = load_family(self.root, row)
            except (SpecError, OSError):
                continue                             # the families check names it
            named = {o.reader for o in outcomes if o.path == ""}
            for o in outcomes:                      # строка поля: роль — `*` или читатель семьи (ревью Claude С-3)
                if o.path and o.reader != "*" and o.reader not in want:
                    self.error(path, f"outcomes: {o.path} names {o.reader}, not a reader of {row['key']} by the catalog "
                                     f"(readers ∪ cas/guard) and not *")
            for role in sorted(want - named):
                self.error(path, f"outcomes: no outcome of the whole row (empty path) for the reader {role} of "
                                 f"{row['key']} (readers ∪ cas/guard of the catalog; решение владельца 2026-10-28)")
            for role in sorted(named - want):
                self.error(path, f"outcomes: {role} is not a reader of {row['key']} by the catalog (readers ∪ "
                                 f"cas/guard)")
            self.stats["outcome_readers"] += len(want)

    # Package family-read (ADR-0087 доп. (9) п. 2): form, catalog and the outcome of every row on the В7 stack.
    # Заготовочный текст перехода В7 (решение «Архитектора» 2026-10-28): пробел исхода, оставленный вопросом, — не норма.
    # В исходах и нормах его быть не должно; упоминание прошлого вопроса («прежде — вопрос …») — история, не заготовка.
    STUB_TEXT = re.compile(r"исход не назван нормой|(?<!прежде — )вопрос «Архитектору»")

    def stub_text(self):
        platform = Path(os.path.normpath(self.root / "Platform"))
        files = sorted(platform.glob("*/data/*.outcomes.tsv")) + sorted(platform.glob("*/spec/*.norms.md")) + \
            sorted(platform.glob("*/ru/spec/*.norms.md"))       # ADR-0124: the Russian text of a moved lesson
        for path in files:
            for no, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
                m = self.STUB_TEXT.search(line)
                if m:
                    self.error(path, f"line {no}: placeholder text «{m.group(0)}» — the gap needs a norm (a decision of "
                                     "the «Архитектор»), not a question in the outcome or the norm")
        self.stats["stub_scanned_files"] += len(files)

    # Слова x-* (V7-LAYERS-ROOT-HASH-01): таблица layers.tsv несёт ровно слова со слоем LAYERS § 3 (кроме слов схемы вида
    # и строки связей), её построитель — v7.schema.LAYER_WORDS; слово x-* схемы вне § 3 — ошибка.
    def layer_words(self):
        if not self.v7:
            return
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from v7 import schema as v7schema
        layers = human_text(self.root / "Platform/common/LAYERS.md", self.root)
        words, inside = {}, False
        for line in layers.read_text(encoding="utf-8").split("\n"):
            if line.startswith("## "):
                inside = line.startswith("## 3.")
            cells = [c.strip() for c in line.strip().strip("|").split("|")] if inside and line.startswith("| `x-") else []
            for w in re.findall(r"`(x-[a-z-]+)`", cells[0] if cells else ""):
                words[w] = cells[1]
        if not words:
            self.error(layers, "§ 3: no table of the x-* words")
            return
        for w, layer in sorted(words.items()):
            if layer == "—" and w not in v7schema.NOT_IN_TABLE:
                self.error(layers, f"§ 3: {w} has no layer, but the skill puts it into layers.tsv")
            elif layer != "—" and w not in v7schema.NOT_IN_TABLE and v7schema.LAYER_WORDS.get(w) != layer:
                self.error(layers, f"§ 3: {w} — layer {layer}, the skill's layers.tsv says "
                                   f"{v7schema.LAYER_WORDS.get(w, 'nothing')}")
        for w in sorted(set(v7schema.LAYER_WORDS) | v7schema.NOT_IN_TABLE):
            if w not in words:
                self.error(layers, f"§ 3: no row for {w} (the skill knows it)")

        def keys(x, out):
            if isinstance(x, dict):
                for k, v in x.items():
                    if k.startswith("x-"):
                        out.add(k)
                    if k in ("properties", "patternProperties", "$defs") and isinstance(v, dict):
                        for vv in v.values():
                            keys(vv, out)
                    elif k not in ("enum", "const", "default", "examples") and not k.startswith("x-"):
                        keys(v, out)
            elif isinstance(x, list):
                for v in x:
                    keys(v, out)
            return out
        platform = self.root / "Platform"
        for path in sorted(platform.glob("*/data/*.schema.json")) + sorted(platform.glob("*/spec/*.schema.json")):
            try:
                found = keys(json.loads(path.read_text(encoding="utf-8")), set())
            except ValueError:
                continue                                 # the schema check names it
            for w in sorted(found - set(words)):
                self.error(path, f"{w} is not a word of LAYERS.md § 3")
        self.stats["layer_words"] = len(words)

    # Перечень дефектов закреплённых версий библиотек для реализаций (Platform/common/versions/DEFECTS.md, ADR-0092 п. 9):
    # id — дефекты библиотек v7/DEFECTS.tsv навыка (не эталона), у каждой записи — существующая строка вектора или «страж».
    LIBRARY_DEFECTS = Path("Platform/common/versions/DEFECTS.md")
    VECTOR_REF = re.compile(r"(family-read|yaml-suite|corpus|canonical):(\S+)")

    def english_mirrors(self):
        """ADR-0120 п. 1 (б), доп. (1): английский текст — источник, русский — производный; один набор номеров норм,
        ссылок, кодов и слов отказов (`en_mirror.compare`), иначе отказ. Пары — по раскладке урока: `X` ↔ `ru/X` (ADR-0124)
        или `en/<имя>.en.md` ↔ `<имя>.md` (ADR-0121); в `ru/` без источника — только лекция."""
        import en_mirror
        modules = ("Platform",) if self.scope == "platform" else ("VMS",) if self.scope == "vms" else ("Platform", "VMS")
        prefixes = None if self.scope is None else tuple(p for p in en_mirror.FULL_ENGLISH_DONE
                                                        if p.split("/", 1)[0] in modules)
        for path, message in en_mirror.full_english_errors(self.root, prefixes):
            self.error(path, message)
        import source_cells
        sources = en_mirror.english_sources(self.root, tuple(m + "/" for m in modules))
        for path, message in source_cells.errors(self.root, [p for p in sources if p.suffix == ".tsv"],
                                                  source_scopes=modules if self.scope is not None else None):
            self.error(path, message)
        for ru, en in en_mirror.pairs(self.root):
            if self.scope is not None and en.relative_to(self.root).parts[0] not in modules:
                continue
            texts = self.read(en), ru.is_file() and self.read(ru)
            if not ru.is_file():
                self.error(en, f"no Russian text {self.name(ru)} for this English source")
            if not all(texts):
                continue
            self.markdown(en, en_mirror.BUILT.sub("", texts[0]))   # построенный блок — русская копия, ссылки от ru
            for message in en_mirror.compare(texts[1], texts[0], ru, en, self.root):
                self.error(en, f"ru↔en: {message}")
            self.stats["english_mirrors"] += 1
        for ru in sorted([*(p for m in modules for p in self.root.glob(m + "/**/*.md")),
                          *(self.root.glob("ru/*.md") if self.scope is None else [])]):
            if ru.parent.name == "en":
                continue
            moved = en_mirror.home_of(ru, self.root)
            if moved and moved[1].parts[0] == "ru":
                home, rel = moved[0], moved[1].relative_to("ru")
                if not (home / rel).is_file() and ru != lecture_of(home):
                    self.error(ru, f"a Russian text in ru/ without its source {self.name(home / rel)}: in ru/ only the "
                                   "lecture lives without a pair (ADR-0124 п. 1)")
                continue
            text = ru.read_text(encoding="utf-8")
            en = ru.parent / "en" / ru.name.replace(".md", ".en.md")
            if en_mirror.MARK in "\n".join(text.splitlines()[:12]) and not en.is_file():
                self.error(ru, f"marked «{en_mirror.MARK}», but {self.name(en)} is missing")

    def standard_forms(self):
        """Validate the selected Platform package once and share its raw rows."""
        if self._standard_forms is None:
            self._standard_forms = {}, set()
            if (self.root / "Platform/01-store").is_dir():
                import frictionless_forms
                tables, selected = self._standard_forms
                selected.update(self.root / "Platform" / path for path in frictionless_forms.RESOURCES.values())
                errors, stats = frictionless_forms.check(self.root, tables=tables)
                for message in errors:
                    self.error(self.root / frictionless_forms.PACKAGE, message)
                self.stats.update(stats)
        return self._standard_forms

    def check_tables(self):
        """ADR-0120 п. 2 (а): таблицы проверок команды `Platform/*/forms/*-checks.tsv` (в прежней раскладке — `data/`) — форма, CEL, функции #fn,
        параметры #lim и пробы `*-checks.probes.tsv`, сверенные прогоном (`check_tables.check`)."""
        import check_tables
        import check_machines
        for path in [*check_tables.tables(self.root), *check_machines.machines(self.root)]:
            if path.parent.name == "data" and (path.parent.parent / "ru").is_dir():
                self.error(path, "a form of a lesson in the layout of ADR-0124 lives in forms/; data/ holds the data "
                                 "families only (ADR-0124 п. 1)")
        standard, selected = self.standard_forms()
        for path in check_tables.tables(self.root):
            probes = path.with_name(path.name.replace(".tsv", ".probes.tsv"))
            if any(file in selected and file not in standard for file in (path, probes)):
                continue
            errors, stats = check_tables.check(path, validated=standard.get(path),
                                               validated_probes=standard.get(probes))
            for message in errors:
                self.error(path, message)
            self.stats.update(stats)

    def check_machines(self):
        """ADR-0120 п. 2 (б): автоматы норм `Platform/*/forms/*.machine.yaml` (в прежней раскладке — `data/`) — закрытые наборы, CEL, трассы
        `*.traces.tsv` прогоном эталонного исполнителя (`check_machines.check`)."""
        import check_machines
        for path in check_machines.machines(self.root):
            errors, stats = check_machines.check(path)
            for message in errors:
                self.error(path, message)
            self.stats.update(stats)

    def lesson_stands(self):
        """{(lesson, name): [(path, line, id)]} of target_registry.stands, read once per run."""
        if getattr(self, "_stands", None) is None:
            import target_registry
            self._stands = target_registry.stands(self.root)
        return self._stands

    def target_registry(self):
        """ADR-0135 addendum (14): the acceptance target registry assembled from the common header and the rows of the lessons
        (`target_registry`): common header in every source, unique ids, a lesson's rows owned by it, one routing row per
        target in the same place."""
        import target_registry
        _targets, _routing, errors, stats = target_registry.assemble(self.root)
        for path, message in errors:
            self.error(path, message)
        self.stats.update(stats)

    def export_lists(self):
        """ADR-0135 addendum (14): the export filters M and J assembled from the common filters and the lists
        forms/export.json of the lessons (`export_lists`): form of a list, a lesson's files each named once in model and in
        judge, one record per path, M and J name the same paths, the routing of the judge never in M; the input Q
        (ADR-0130 addendum (20)): Q files outside M, their translations outside the exports, the form and composition of
        Platform/common/qualification-input-filter.json where it is."""
        import export_lists
        _filters, errors, stats = export_lists.assemble(self.root)
        for path, message in errors:
            self.error(path, message)
        self.stats.update(stats)

    def m_form(self):
        """The reading form of M (ADR-0133 addenda (56), (93), (94), P01.175; m_form.py): history_phrases, index_refs,
        see_also_refs, judge_only_refs, production_scoped, history_rows, checklist_marks, req_map, req_refs over the
        lessons of m_form.M_FORM_LESSONS this run checks, qualification_refs over the files of M; stage A (history_phrases, judge_only_refs, history_rows,
        req_map, req_refs) over those of m_form.M_FORM_STAGE_A."""
        import m_form
        m_form.run(self, {f"{n}" for n in self.lessons_seen})

    def check_forms(self):
        """ADR-0125 п. 2, доп. (1) п. 5: `forms/daemon-flags.tsv` и `forms/refusals.tsv` урока — форма и согласие с таблицами
        прозы (флаги, Н4), с `*Fault` OpenAPI и с `forms/*-checks.tsv` (`check_forms`)."""
        import check_forms
        standard, selected_standard = self.standard_forms()
        for path in check_forms.flag_forms(self.root):
            if path in selected_standard and path not in standard:
                continue
            errors, stats = check_forms.check_flags(path, validated=standard.get(path))
            for message in errors:
                self.error(path, message)
            self.stats.update(stats)
        for path in check_forms.refusal_forms(self.root):
            if path in selected_standard and path not in standard:
                continue
            errors, stats = check_forms.check_refusals(path, validated=standard.get(path))
            for message in errors:
                self.error(path, message)
            self.stats.update(stats)
        for path in check_forms.seam_files(self.root):
            errors, stats = check_forms.check_seams(path)
            for message in errors:
                self.error(path, message)
            self.stats["seam_steps"] = self.stats.get("seam_steps", 0) + stats["seam_steps"]
        for path in check_forms.runtime_constant_forms(self.root):
            if path in selected_standard and path not in standard:
                continue
            errors, stats = check_forms.check_runtime_constants(path, validated=standard.get(path))
            for message in errors:
                self.error(path, message)
            self.stats.update(stats)
        if (self.root / "Platform/01-store").is_dir():
            import check_constants
            errors, stats = check_constants.check_p01_constants(self.root)
            for path, message in errors:
                self.error(path, message)
            self.stats.update(stats)
        if (self.root / "Platform/06-console").is_dir():
            import check_constants
            errors, stats = check_constants.check_p06_folder_constants(self.root)
            for path, message in errors:
                self.error(path, message)
            self.stats.update(stats)
            errors, stats = check_constants.check_p06_numeric_constants(self.root)
            for path, message in errors:
                self.error(path, message)
            self.stats.update(stats)
        if (self.root / "Platform/08-domain").is_dir():
            import check_constants
            errors, stats = check_constants.check_p08_constants(self.root)
            for path, message in errors:
                self.error(path, message)
            self.stats.update(stats)
            errors, stats = check_constants.check_p08_named_constants(self.root)
            for path, message in errors:
                self.error(path, message)
            self.stats.update(stats)
            errors, stats = check_constants.check_p08_entry_url_bytes(self.root)
            for path, message in errors:
                self.error(path, message)
            self.stats.update(stats)
        if (self.root / "Platform/09-agent").is_dir():
            import check_constants
            errors, stats = check_constants.check_p09_numeric_constants(self.root)
            for path, message in errors:
                self.error(path, message)
            self.stats.update(stats)
        for path in check_forms.versioned_door_forms(self.root):     # версии дверей P/08.0 Н1.9 (forms/README)
            errors, stats = check_forms.check_versioned_doors(path)
            for message in errors:
                self.error(path, message)
            self.stats.update(stats)
        for path in check_forms.finite_profile_forms(self.root):     # конечный профиль удаления P/06 C2 (P02.3 6a/3a)
            errors, stats = check_forms.check_finite_profile(path)
            for message in errors:
                self.error(path, message)
            self.stats.update(stats)
        for path in check_forms.deletion_body_witness_forms(self.root):  # кодек-свидетели тела P/06.8 N1.3
            errors, stats = check_forms.check_deletion_body_witnesses(path)
            for message in errors:
                self.error(path, message)
            self.stats.update(stats)
        for path in check_forms.row_write_binding_forms(self.root):  # конструкторы записи строки (P03-GEN-01, ADR-0127 доп. (1) п. 3)
            errors, stats = check_forms.check_row_write_bindings(path)
            for message in errors:
                self.error(path, message)
            self.stats["row_write_bindings"] = self.stats.get("row_write_bindings", 0) + stats["row_write_bindings"]
        for path in check_forms.route_lessons(self.root):
            errors, stats = check_forms.check_openapi_routing(path)
            for message in errors:
                self.error(path, message)
            self.stats.update(stats)
        for path in check_forms.door_role_forms(self.root):
            errors, stats = check_forms.check_door_roles(path)
            for message in errors:
                self.error(path, message)
            self.stats.update(stats)
        for path in check_forms.operator_forms(self.root):
            errors, stats = check_forms.check_operator_commands(path)
            for message in errors:
                self.error(path, message)
            self.stats.update(stats)
        wire_seen, wire_stats = set(), {}
        for path in check_forms.wire_forms(self.root):          # one wire form, public and judge carriers
            errors, stats = check_forms.check_wire(path, seen=wire_seen)
            for message in errors:
                self.error(path, message)
            for name, value in stats.items():
                wire_stats[name] = wire_stats.get(name, 0) + value
        self.stats.update(wire_stats)
        for path in check_forms.stage_forms(self.root):
            if path in selected_standard and path not in standard:
                continue  # Source structure/environment already failed; do not reinterpret it with a legacy parser.
            errors, stats = check_forms.check_stage_parts(path, validated=standard.get(path))
            for message in errors:
                self.error(path, message)
            self.stats.update(stats)
        for lesson in check_forms.req_lessons(self.root):
            errors, stats = check_forms.check_req_anchors(lesson)
            for message in errors:
                self.error(lesson, message)
            self.stats["req_anchors"] = self.stats.get("req_anchors", 0) + stats["req_anchors"]

    def form_refs(self):
        """ADR-0133 доп. (102): ссылки ячеек форм уроков и common (`Platform/*/forms/**/*.tsv`,
        `Platform/common/**/forms/**/*.tsv`) — путь к файлу, строки `:N`/`:N–M`, якорь, раздел норм `P/NN.K Nx`, `«Заголовок»`,
        пункт готовности `P/NN.K-MM` — существуют; ссылка из файла M на файл вне M висит в M (`form_refs`). Висячая
        ссылка — ошибка без ведомости долга. Цели ворот этапов судит `check_forms.gate_errors`."""
        import form_refs
        form_refs.run(self)

    def check_cyrillic(self, debt_path=None):
        """All Platform bytes, independently of the selected lessons; tools/normgen is frozen
        (check_cyrillic.FROZEN_SOURCE, ADR-0125 доп. (14) п. 3) and not judged."""
        import check_cyrillic
        scopes = ("Platform",) if self.scope == "platform" else ("VMS",) if self.scope == "vms" else None
        errors, stats = check_cyrillic.check(self.root, debt_path or check_cyrillic.DEBT, source_scopes=scopes)
        self.errors.extend(errors)
        self.stats.update(stats)

    def library_defects(self):
        if not self.v7:
            return
        path = human_text(Path(os.path.normpath(self.root / self.LIBRARY_DEFECTS)), self.root).with_name("DEFECTS.cases.md")
        layers = human_text(self.root / "Platform/common/LAYERS.md", self.root)
        if not path.is_file():
            if layers.is_file() and "versions/DEFECTS.md" in layers.read_text(encoding="utf-8"):
                self.error(path, "no file: LAYERS.md names the list of library defects")
            return
        skill = {}
        for line in (Path(__file__).resolve().parent / "v7/DEFECTS.tsv").read_text(encoding="utf-8").split("\n"):
            cols = line.split("\t")
            if re.fullmatch(r"D[0-9]+", cols[0]) and not cols[1].startswith("эталон"):
                skill[cols[0]] = cols[1]
        vectors = self.vector_rows()
        head, seen = None, []
        for no, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
            if not line.startswith("|"):
                head = None if not seen else head
                continue
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]
            if head is None:
                head = cells if "id" in cells and "Вектор" in cells else None
                continue
            if set(line.replace("|", "").strip()) <= set("-: "):
                continue
            r = dict(zip(head, cells))
            did, cell = r.get("id", ""), r.get("Вектор", "")
            seen.append(did)
            if did not in skill:
                self.error(path, f"line {no}: {did} is not a library defect of v7/DEFECTS.tsv of the skill")
            refs = self.VECTOR_REF.findall(cell)
            if not refs and not cell.startswith("страж"):
                self.error(path, f"line {no}: {did} has no vector row (family-read:<case>, yaml-suite:<id>, "
                                 f"corpus:<случай>, canonical:<case>) and is not «страж»")
            for kind, ref in refs:
                ref = ref.strip("`,")
                if ref not in vectors[kind]:
                    self.error(path, f"line {no}: {did}: no vector row {kind}:{ref}")
            self.stats["library_defects"] += 1
            self.stats["library_defect_vectors"] += len(refs)
        for did in sorted(set(skill) - set(seen), key=lambda d: int(d[1:])):
            self.error(path, f"{did} ({skill[did]}) of v7/DEFECTS.tsv is not in the list")

    def vector_rows(self):
        """Имена строк векторов: family-read — case, yaml-suite — id, corpus — случай verdicts.tsv P/02.1, canonical — case."""
        platform = self.root / "Platform"
        out = {"family-read": set(), "yaml-suite": set(), "corpus": set(), "canonical": set()}

        def first(path):
            if not path.is_file():
                return []
            return [ln.split("\t")[0] for ln in path.read_text(encoding="utf-8").split("\n") if ln and not ln.startswith("#")]
        for t in sorted((platform / "common/vectors/family-read").glob("[0-9][0-9].tsv")):
            out["family-read"].update(first(t)[1:])
        out["yaml-suite"].update(first(platform / "common/vectors/yaml-suite/expect.tsv")[1:])
        out["corpus"].update(first(platform / "02-installer/acceptance/1/verdicts.tsv"))
        out["canonical"].update(first(platform / "02-installer/vectors/canonical/cases.tsv"))
        return out

    # Common contracts (V7-OPENAPI-PATTERN-LOOKAHEAD-01): every Platform/common/contracts/*.yaml is read and checked once
    # per run, also when no lesson refers to it.
    def common_contracts(self):
        if not self.v7:
            return
        for path in sorted(Path(os.path.normpath(self.root / "Platform/common/contracts")).glob("*.yaml")):
            self.contract(path)

    def family_read(self):
        # Once per run from main(), whatever lessons are named (ревью Kimi М-4): the package is the catalog's, not 02's.
        if not self.v7 or self.catalog is None:
            return
        if str(SCRIPTS) not in sys.path:
            sys.path.insert(0, str(SCRIPTS))
        try:
            from v7.spec import FAMILY_READ, family_read, is_v7_family, read_catalog
            catalog = read_catalog(self.root)                   # строки каталога как в файле (ops — текст)
            errors, stats = family_read(self.root, catalog)
        except ImportError as exc:
            self.error(self.root / "Platform/common/vectors", f"family-read needs the В7 stack, missing: {exc}; run: {V7_INSTALL}")
            return
        for where, message in errors:
            self.error(self.root / where, message)
        for name, value in stats.items():
            self.stats[name] = value
        document = self.root / FAMILY_READ / "README.cases.md"
        if document.is_file() and not document.is_symlink():
            text = self.read(document)
            if text is not None:
                self.markdown(document, text)
        # Таблица на каждого урока-владельца семей со схемой (ревью Claude С-1); отложенная — исключение family-read
        # (урок P/NN, значение NN.tsv); таблица есть, а исключение осталось — устарело.
        package = self.root / FAMILY_READ
        for lesson in sorted({row["owner"][2:4] for row in catalog if is_v7_family(row)}):
            key, name = f"P/{lesson}", f"{lesson}.tsv"
            have = (package / name).is_file()
            if self.exception(key, "family-read", name) is not None:
                if have:
                    self.used.add((key, "family-read", name))
                    self.error(package / name, f"stale exception family-read {key} {name}: the table is there")
                else:
                    self.except_(package, key, "family-read", name)
            elif not have:
                self.error(package, f"family-read: no table {name} for the families of {key}: one table per owner "
                                    f"lesson; deferring it is a decision of the «Архитектор» (exception family-read)")

    # The data families of ADR-0088 that a chapter owns by the catalog (owner = the chapter, schema named): each schema
    # builds from the dialect (data-form/1 with common.form.yaml), its outcomes.tsv is in form and names places of the
    # schema; if the norms hold the markers, the section between them is the built one byte for byte. Without markers
    # (transition) it is no error; COUNTS says how many families have the section and how many do not.
    def families(self, norms, text, prefix):
        self.stats["families_with_section"] += 0
        self.stats["families_without_section"] += 0
        if self.catalog is None:
            return
        if self.v7:
            if str(SCRIPTS) not in sys.path:
                sys.path.insert(0, str(SCRIPTS))
            try:
                from v7.spec import families_check
            except ImportError as exc:
                self.error(norms, f"families on В7 need the В7 stack, missing: {exc}; run: {V7_INSTALL}")
                return
            vms = Path(norms).resolve().is_relative_to(self.root / VMS_DIR)
            errors, stats = families_check(self.root, norms, text, prefix,
                                           self.vms_catalog() if vms else list(self.catalog.values()))
            for where, message in errors:
                self.error(where, message)
            self.stats.update(stats)
            return
        rows = [row for row in self.catalog.values() if row["owner"] == prefix and row["schema"] not in ("-", "manifest")]
        lines = text.split("\n") if text is not None else []
        if not rows and not any(line in (FAMILIES_BEGIN, FAMILIES_END) for line in lines):
            return
        if str(SCRIPTS) not in sys.path:
            sys.path.insert(0, str(SCRIPTS))
        try:
            from form_source import SourceError
            from form_source.families import build_families_section, load_family
            from form_source.source import load_common
        except ImportError as exc:
            self.error(norms, f"families check needs ruamel.yaml (text layer Н1.1), missing: {exc}; run: {SCHEMA_INSTALL}")
            return
        built = []
        try:
            common = load_common(self.root / FAMILIES_COMMON)
        except (SourceError, OSError) as exc:
            self.error(self.root / FAMILIES_COMMON, f"families: {exc}")
            return
        for row in rows:
            try:
                built.append(load_family(self.root, row, common))
            except (SourceError, OSError) as exc:
                self.error(self.root / "Platform" / row["schema"], f"families: {exc}")
                continue
            self.stats["family_schemas"] += 1
            self.stats["family_outcomes"] += len(built[-1].outcomes)
        if text is None:
            return
        begins = [i for i, line in enumerate(lines) if line == FAMILIES_BEGIN]
        ends = [i for i, line in enumerate(lines) if line == FAMILIES_END]
        if not begins and not ends:
            self.stats["families_without_section"] += len(rows)
            return
        if len(begins) != 1 or len(ends) != 1 or ends[0] < begins[0]:
            self.error(norms, f"families: the norms hold the built section once, between {FAMILIES_BEGIN} and {FAMILIES_END}")
            return
        if not rows:
            self.error(norms, "families: section markers, but the catalog gives this chapter no family with a schema")
            return
        if len(built) != len(rows):
            return                                          # the family that does not build is named above
        said = "\n".join(lines[begins[0] + 1:ends[0]]) + "\n"
        section = build_families_section(norms, self.root, built)
        if said != section:
            old, new = said.splitlines(), section.splitlines()
            at = next((i for i, (a, b) in enumerate(zip(old, new)) if a != b), min(len(old), len(new)))
            self.error(norms, f"families: the section differs from the built one at its line {at + 1} (rebuild: python "
                              f"skills/lesson-spec/scripts/form_source/build_families.py {norms.relative_to(self.root)})")
            return
        self.stats["families_with_section"] += len(rows)

    # Chapter 2.2 «Канонический вид» (ADR-0089): the view of every accepted corpus case and course manifest passes the built
    # schema, the built section stands in the norms between its markers, the vectors canonical are the built bytes and
    # hold every default, ordered and step of the projection (mutants, strict with --strict-coverage), puts.tsv of
    # acceptance/2/ names vectors. Without any file of the chapter it is skipped: COUNTS says canonical=absent. The
    # three-column puts.tsv of the other PUTS_CHAPTERS (2.3) is checked here too (puts_cases).
    def canonical_chapter(self):
        if str(SCRIPTS) not in sys.path:
            sys.path.insert(0, str(SCRIPTS))
        try:
            if self.v7:
                from v7.vectors import Chapter, present
            else:
                from form_source.vectors import Chapter, present
        except ImportError as exc:
            self.error(self.root / "Platform/02-installer", f"canonical check needs ruamel.yaml (text layer Н1.1), missing: {exc}; run: {SCHEMA_INSTALL}")
            return
        chapter = Chapter(self.root, self.strict_coverage)
        if present(self.root):
            chapter.run()                           # puts.tsv of acceptance/2/ — with the vectors
        else:
            chapter.stats["canonical"] = "absent"
        for key, entry in sorted(PUTS_CHAPTERS):
            where = Path("Platform/02-installer/acceptance") / entry.rstrip("/")
            if key == "P/02" and entry != "2/" and (self.root / where / "puts.tsv").is_file():
                chapter.stats["puts_cases"] = chapter.stats.get("puts_cases", 0) + chapter.puts(where)
        for path, message in chapter.errors:
            self.error(self.root / path, message)
        for name, value in chapter.stats.items():
            self.stats[name] = value

    # The stands whose «Словарь директив» a scenario may use: the shared stand of the Platform module and the module's
    # own.
    def stands(self, module=None):
        acceptance = self.root / "Source/tests/testdata/acceptance"
        return [self.root / "Platform/common/acceptance/README.md"] + \
               ([acceptance / module / "01/README.md"] if module else [])

    # One acceptance directory: the supported tables, each with its format check. `entry` prefixes the value of an
    # acceptance-entry exception (a chapter directory of a Platform lesson: `K/name`).
    def acceptance(self, acceptance, key, entry=""):
        texts = {}
        readme = human_text(acceptance / "README.md", self.root)
        text = self.read(readme)
        if text is not None:
            texts[readme] = text
            self.markdown(readme, text)
        home = acceptance.parent.parent if entry else acceptance.parent
        moved = (home / "ru").is_dir() and home.parent in (self.root / "Platform", self.root / VMS_DIR)
        # Histories of both modules live under decisions/journal; no lesson-specific fallback.
        if home.parent == self.root / "Platform":
            journal = self.root / "decisions/journal/platform" / home.name
        elif home.parent == self.root / VMS_DIR:
            journal = self.root / "decisions/journal/vms" / home.name
        else:
            journal = home / "journal"
        log = journal / (f"corrections-{entry.rstrip('/')}.tsv" if entry else "corrections.tsv") if moved \
            else acceptance / "corrections.tsv"
        if moved and (acceptance / "corrections.tsv").exists():
            self.error(acceptance / "corrections.tsv", f"the log lives in {self.name(log)} (ADR-0124 доп. (1) п. 8 (2))")
        self.tsv(log, 4, ["date", "sample", "fix", "languages"])
        supported = {"README.md", "corrections.tsv", "scenarios.tsv", "verdicts.tsv", "diagnostics.tsv", "classes.tsv", "cases",
                     "en",                     # en/README.en.md — английский источник README (ADR-0121), сверка english_mirrors
                     "seams.tsv",                # швы процесса (ADR-0126 доп. (7) п. 1) — check_forms.check_seams
                     "sleeps.cases.md", "README.cases.md"}  # judge-only Markdown, not an executable format
        legacy = acceptance == self.root / LEGACY_VERDICTS.parent
        if legacy:
            supported.add("spec_verdicts")
            self.legacy_spec_verdicts()
        puts = (key, entry) in PUTS_CHAPTERS
        if puts:
            supported |= {"puts.tsv", "puts"}
            if entry == "2/":
                supported.add("puts-ceiling.tsv")       # потолок не по умолчанию (аудит P/02, B00): checked with puts.tsv
        extra = {value[len(entry):] for (lesson_key, kind, value) in self.registry
                 if lesson_key == key and kind == "acceptance-entry" and value.startswith(entry)}
        own_format = False                          # an excepted entry checked by the README of the acceptance
        try:
            for item in acceptance.iterdir():
                if item.name in IGNORED:
                    continue
                value = entry + item.name
                if item.name in extra and item.name in supported:
                    self.used.add((key, "acceptance-entry", value))
                    self.error(item, "stale exception acceptance-entry: the entry is supported without it")
                elif item.name in extra:
                    self.except_(item, key, "acceptance-entry", value)
                    own_format = True
                elif item.name not in supported:
                    self.error(item, "unsupported acceptance entry; add a format-specific check")
                elif item.name not in ("cases", "puts", "en", "spec_verdicts") and \
                        (not item.is_file() or (item.name in ("sleeps.cases.md", "README.cases.md") and item.is_symlink())):
                    self.error(item, "acceptance table/document must be a file")
                elif item.name in ("sleeps.cases.md", "README.cases.md"):
                    document = self.read(item)
                    if document is not None:
                        self.markdown(item, document)
        except OSError as exc:
            self.error(acceptance, str(exc))
        formats = 0
        scenarios = None
        if (acceptance / "scenarios.tsv").exists():
            table = acceptance / "scenarios.tsv"
            scenarios = scenario_counts(self.read(table) or "")
            # A chapter's own grammar is excepted per chapter (`K/own`), like acceptance-entry.
            own = self.exception(key, "scenarios-format", entry + "own") is not None
            silenced = self.scenarios(table, own, self.vms_forms() if key.startswith("V/") else None)
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
        if puts and (acceptance / "puts.tsv").is_file():
            formats += 1                            # checked with the vectors of the chapter (canonical_chapter)
        if (acceptance / "seams.tsv").is_file():
            formats += 1                            # швы процесса — check_forms.check_seams (ADR-0125 доп. (5))
        if (key, entry) == VARIANTS_CHAPTER and (acceptance / "variants").is_dir():
            self.variants(acceptance / "variants")  # README of the chapter checks the meaning; the form is checked here
        if not formats and not own_format:
            self.error(acceptance, "no supported acceptance table; add a format-specific check")
        return texts, scenarios, verdict_counts, verdicts, classes

    # Variants of chapter 2.5 (аудит Gemini P/02, свойства 24, 25; решение «Архитектора» 2026-10-30): each `v<N>-<slug>/`
    # holds manifests and exactly one of `expect.tsv` (rights and probes), `refused` (the generation refuses: one line —
    # `name` of a manifest of the variant), `check.tsv` with `check/` (`rights --check <file>`: code 0 or !0).
    def variants(self, root):
        for v in sorted(p for p in root.iterdir() if p.name not in IGNORED):
            if not v.is_dir() or not re.fullmatch(r"v[1-9][0-9]*-[a-z0-9-]+", v.name):
                self.error(v, "a variant is a directory v<N>-<slug>")
                continue
            names = set()
            for m in v.glob("*.subsystem.yaml"):
                found = re.search(r"(?m)^name:\s*([A-Za-z0-9_-]+)\s*$", self.read(m) or "")
                if found:
                    names.add(found.group(1))
            if not names:
                self.error(v, "a variant holds at least one <name>.subsystem.yaml with name:")
            forms = [n for n in ("expect.tsv", "refused", "check.tsv") if (v / n).is_file()]
            if len(forms) != 1:
                self.error(v, "a variant holds exactly one of expect.tsv, refused, check.tsv (has: %s)" % (", ".join(forms) or "none"))
            for item in v.iterdir():
                if item.name in IGNORED or item.name.endswith(".subsystem.yaml") or item.name in ("expect.tsv", "refused", "check.tsv"):
                    continue
                if item.name == "check" and item.is_dir() and (v / "check.tsv").is_file():
                    continue
                self.error(item, "unsupported entry of a variant; add it to the form check")
            if (v / "refused").is_file():
                lines = [ln for ln in (self.read(v / "refused") or "").split("\n") if ln.strip() and not ln.startswith("#")]
                if len(lines) != 1 or lines[0].strip() not in names:
                    self.error(v / "refused", "refused holds one line: the name of a manifest of the variant (%s)" % ", ".join(sorted(names)))
            if (v / "check.tsv").is_file():
                rows = [ln.split("\t") for ln in (self.read(v / "check.tsv") or "").split("\n") if ln and not ln.startswith("#")]
                if not rows or rows[0] != ["case", "file", "code"]:
                    self.error(v / "check.tsv", "the first row is the header case<TAB>file<TAB>code")
                    continue
                cases, files = set(), set()
                for no, r in enumerate(rows[1:], 2):
                    if len(r) != 3 or not re.fullmatch(r"[a-z0-9_]+", r[0]) or r[0] in cases:
                        self.error(v / "check.tsv", "row %d: case [a-z0-9_]+ unique, three fields" % no)
                        continue
                    cases.add(r[0])
                    if not re.fullmatch(r"check/[A-Za-z0-9_.-]+", r[1]) or not (v / r[1]).is_file():
                        self.error(v / "check.tsv", "row %d: no file %s" % (no, r[1]))
                    files.add(r[1])
                    if r[2] not in ("0", "!0"):
                        self.error(v / "check.tsv", "row %d: code is 0 or !0" % no)
                for extra in sorted((v / "check").glob("*")) if (v / "check").is_dir() else []:
                    if "check/" + extra.name not in files and extra.name not in IGNORED:
                        self.error(extra, "no row of check.tsv names this file")

    def choices(self, text):
        section = re.search(r"^## Решает реализация\s*$(.*?)(?=^## |\Z)", text, re.S | re.M)
        return len(re.findall(r"^\d+\.\s", section.group(1), re.M)) if section else None

    def openapi_or_exception(self, contract, key):
        if self.exception(key, "no-openapi") is None:
            self.openapi(contract)
        elif contract.exists():
            self.used.add((key, "no-openapi", "-"))
            self.error(contract, "stale exception no-openapi: the contract exists")
            self.openapi(contract)                   # a stale row must not hide the contract's own errors
        else:
            self.except_(contract, key, "no-openapi", "-")

    def stale(self, key, where):
        # no-schema rows belong to the catalog, not to a lesson: catalog_lessons() names the stale ones.
        for row in sorted(r for r in self.registry if r[0] == key and r not in self.used
                          and r[1] != "no-schema" and r[1] not in V7_EXCEPTIONS):
            self.error(where, f"stale exception {row[1]} {row[2]}: this lesson does not need it")

    # A hash a vectors README names is the hash of the bytes it links (C08-VEC-MANIFEST-SHA-01): nothing else saw three go stale.
    def vector_hashes(self):
        patterns = ("Platform/**/vectors/**/README.md",) if self.scope == "platform" else (
            "VMS/**/vectors/**/README.md",) if self.scope == "vms" else ("*/**/vectors/**/README.md",)
        patterns += tuple(pattern.removesuffix("README.md") + "README.cases.md" for pattern in patterns)
        for readme in sorted(p for pattern in patterns for p in self.root.glob(pattern)):
            for line, text in enumerate(readme.read_text(encoding="utf-8").splitlines(), 1):
                match = re.search(r"\]\(([^)]+)\)\s*\|\s*`([0-9a-f]{64})`", text)
                if match:
                    target = readme.parent / match.group(1)
                    if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != match.group(2):
                        self.error(readme, f"line {line}: sha256 is not of {match.group(1)}")

    def lesson(self, lesson):
        if lesson_home(lesson).parent == self.root / "Platform":
            return self.platform_lesson(lesson)
        if lesson_home(lesson).parent == self.root / VMS_DIR:
            return self.platform_lesson(lesson, vms=True)
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
        # A lesson whose whole acceptance moved to Platform lessons keeps its norms only (no-acceptance); a table
        # left in its directory makes the exception stale.
        if self.exception(key, "no-acceptance") is not None:
            left = [t for t in ("scenarios.tsv", "verdicts.tsv", "cases") if (acceptance / t).exists()]
            if left:
                self.used.add((key, "no-acceptance", "-"))
                self.error(acceptance, f"stale exception no-acceptance: the lesson still has {', '.join(left)}")
            else:
                self.except_(acceptance, key, "no-acceptance", "-")
            more, scenarios, verdict_counts, verdicts, classes = {}, None, None, None, {}
        else:
            more, scenarios, verdict_counts, verdicts, classes = self.acceptance(acceptance, key)
        texts.update(more)
        schema, schema_refs = spec / f"{lesson.stem}.schema.yaml", spec / f"{lesson.stem}.references.tsv"
        if schema.exists() or schema_refs.exists():
            self.manifest_schema(schema, schema_refs, acceptance / "cases", verdicts, classes)
        choices = self.choices(texts[norms]) if norms in texts else None
        for path, text in texts.items():
            self.counts(path, text, prefix, ids, scenarios, path == instructions, verdict_counts, choices or None,
                        lecture=path == lesson)
        if scenarios is not None:
            self.directives(acceptance / "scenarios.tsv", self.stands(module))
        self.stale(key, acceptance)
        self.stats["lessons"] += 1

    # A VMS lesson is a row of VMS/common/lessons.tsv with its directory (vms_module checks the table's form).
    def vms_lesson_listed(self, lesson, number, stem):
        path = self.root / VMS_LESSONS
        rows = [dict(zip(VMS_LESSONS_FIELDS, cols)) for _, cols in self.tsv(path, len(VMS_LESSONS_FIELDS))] \
            if path.is_file() else []
        if not any(row["lesson"] == number and row["dir"] == stem for row in rows):
            self.error(lesson, f"lesson {stem} is not in {VMS_LESSONS} (ADR-0090 доп. (2))")
            return False
        return True

    # A stub chapter of a VMS lesson: the status line «ждёт решения запроса» and a link to an existing request file of
    # the inbox (decisions/inbox/<дата>-запрос-vms-<тема>.md). A status line without such a link is an error.
    def vms_stub(self, norms, text):
        if not VMS_STUB.search(text):
            return False
        links = [link for link in VMS_REQUEST.findall(text) if (norms.parent / link).resolve().is_file()]
        if not links:
            self.error(norms, "a stub chapter («ждёт решения запроса») links an existing request "
                              "decisions/inbox/<дата>-запрос-vms-<тема>.md")
            return False
        self.stats["vms_stub_chapters"] += 1
        return True

    # A lesson of the Platform module (ADR-0083): Platform/NN-<процесс>/NN-<процесс>.md, norms per chapter
    # spec/NN.K-<процесс>.norms.md (or one spec/NN-<процесс>.norms.md), one instruction and one OpenAPI, acceptance per
    # chapter acceptance/K/ (or acceptance/). Each chapter is checked as a lesson of its own; the lecture and the
    # instruction count the whole lesson. An ADR-0085 pair next to chapter norms checks that chapter's corpus.
    def platform_lesson(self, lesson, vms=False):
        """`vms` — a lesson of the VMS module (ADR-0090 доп. (2)): VMS/NN-<имя>/NN-<имя>.md, ids V/NN.K-MM, its row in
        VMS/common/lessons.tsv, historical id-map decisions/history/vms/id-map.tsv; the checks of a Platform process (lessons.tsv process and
        unit, the catalog by the roles of a process, the canonical chapter) do not apply; a chapter waiting for a
        request is a stub (VMS_STUB)."""
        if not vms and not self.processes_checked:
            self.process_names()
        if not vms and not self.catalog_checked:
            self.catalog_lessons()
        stem = lesson.stem
        home = lesson_home(lesson)
        human = lambda path: human_text(path, self.root)   # noqa: E731 — the Russian text of a source (ADR-0124)
        if not re.fullmatch(r"[0-9]{2}-[a-z][a-z0-9-]*" if vms else r"[0-9]{2}-[a-z][a-z-]*", stem) or \
                home.name != stem or lesson != lecture_of(home):
            self.error(lesson, "expected VMS/NN-<имя>/NN-<имя>.md" if vms else "expected Platform/NN-<процесс>/NN-<процесс>.md")
            return
        number, process = stem[:2], stem[3:]
        key = f"V/{number}" if vms else f"P/{number}"
        if vms and not self.vms_lesson_listed(lesson, number, stem):
            return
        spec, acceptance = home / "spec", home / "acceptance"
        whole = spec / f"{stem}.norms.md"
        chapters = sorted((p for p in spec.glob(f"{number}.*-{process}.norms.md")
                           if re.fullmatch(rf"{number}\." + CHAPTER + rf"-{re.escape(process)}\.norms\.md", p.name)), key=chapter_key)
        if whole.exists() and chapters:
            self.error(whole, "a lesson has either one norms file or chapter norms, not both")
        parts = [(p.name.split("-", 1)[0].split(".")[1], human(p)) for p in chapters] or [(None, human(whole))]
        instructions = human(spec / f"{stem}.README.md")
        texts, all_ids, owned, total_choices, saids = {}, [], set(), 0, []
        totals = {"scenarios": None, "verdicts": None}
        for path in [lesson, instructions]:
            text = self.read(path)
            if text is not None:
                texts[path] = text
                self.markdown(path, text)
        self.openapi_or_exception(spec / f"{stem}.api.openapi.yaml", key)
        # A lesson with chapters none of which has acceptance (a page checked by reading and jsdom tests, V/08) carries
        # no-acceptance as a one-file lesson does: no acceptance/ directory (git keeps no empty one) is then no error.
        lesson_no_acceptance = chapters and self.exception(key, "no-acceptance") is not None
        if lesson_no_acceptance and not acceptance.exists():
            entries = []
            self.except_(acceptance, key, "no-acceptance", "-")
        else:
            if lesson_no_acceptance:
                self.used.add((key, "no-acceptance", "-"))
                self.error(acceptance, "stale exception no-acceptance: the lesson has an acceptance directory")
            try:
                entries = sorted(p for p in acceptance.iterdir() if p.name not in IGNORED) if chapters else []
            except OSError as exc:
                self.error(acceptance, str(exc))
                entries = []
        names = {chapter for chapter, _ in parts}
        # OBSH.43: beside the chapters, stand directories acceptance/<name>/ (a name that begins with a letter), each named
        # in the column `acceptance` of forms/targets.routing.tsv (target_registry.stands); both directions are judged.
        stands = {} if vms else {name: refs for (lesson_dir, name), refs in self.lesson_stands().items()
                                 if lesson_dir == home.name}
        for entry in entries:
            if entry.is_dir() and entry.name in names:
                continue
            if not vms and re.fullmatch(STAND_NAME, entry.name) and entry.is_dir() and not entry.is_symlink():
                if entry.name in stands:
                    self.stats["acceptance_stands"] = self.stats.get("acceptance_stands", 0) + 1
                else:
                    self.error(entry, f"stand directory acceptance/{entry.name}/ is named by no row of the column "
                                      f"acceptance of forms/targets.routing.tsv ({self.name(acceptance / entry.name)})")
                continue
            self.error(entry, "acceptance of a lesson with chapters holds only chapter directories acceptance/K/" +
                       ("" if vms else " and stand directories acceptance/<name>/ named in forms/targets.routing.tsv"))
        for name, refs in sorted(stands.items()):
            if not (chapters and (acceptance / name).is_dir() and not (acceptance / name).is_symlink()):
                for path, line, target in refs:
                    self.error(path, f"line {line}: routing row {target} names the stand directory "
                                     f"{self.name(acceptance / name)}, " +
                                     ("which does not exist" if chapters else "but only a lesson with chapters keeps stands"))
        for chapter, norms in parts:
            prefix = f"{key}.{chapter}" if chapter else key
            text = self.read(norms)
            ids, scenarios, verdict_counts, chapter_texts = [], None, None, {}
            stub = vms and chapter is not None and text is not None and self.vms_stub(norms, text)
            if text is not None:
                self.markdown(norms, text)
                ids = self.norms(norms, text, prefix, allow_empty=stub)
                if stub and ids:
                    self.error(norms, "stale stub: the chapter has checklist ids, its status line «ждёт решения запроса» "
                                      "goes with the first norm")
                said = self.data_paragraph(norms, text, prefix, key if chapter else None)
                owned |= said["владеет"]
                saids.append((norms, said))
                self.id_map_chapter(norms, prefix, ids, VMS_IDMAP if vms else IDMAP)
                chapter_texts[norms] = text
            where = acceptance / chapter if chapter else acceptance
            verdicts, classes = None, {}
            # A lesson without acceptance of its own (a browser library, P/07) carries the no-acceptance exception, as
            # lesson() does; an acceptance directory next to that exception makes it stale.
            no_acceptance = not chapter and self.exception(key, "no-acceptance") is not None
            if where.is_dir():
                if no_acceptance:
                    self.used.add((key, "no-acceptance", "-"))
                    self.error(where, "stale exception no-acceptance: the lesson has an acceptance directory")
                more, scenarios, verdict_counts, verdicts, classes = self.acceptance(where, key, f"{chapter}/" if chapter else "")
                chapter_texts.update(more)
                if scenarios is not None:
                    self.directives(where / "scenarios.tsv",
                                    self.stands() + ([self.root / VMS_DIR / "common/acceptance/README.md"] if vms else []))
            elif no_acceptance:
                self.except_(acceptance, key, "no-acceptance", "-")
            elif not chapter:
                self.error(acceptance, "no acceptance directory")
            # The ADR-0085 pair moves with the chapter that owns the corpus (ADR-0086 Р4) until the lesson takes its
            # form source (ADR-0087): spec/NN.K-<процесс>.form.yaml, .references.tsv, .scalars.tsv next to the norms.
            base = norms.name[:-len(".norms.md")]
            schema, schema_refs = spec / f"{base}.schema.yaml", spec / f"{base}.references.tsv"
            source = spec / f"{base}.form.yaml"
            if (spec / f"{base}.schema.json").exists():
                if source.exists() or schema.exists():
                    self.error(spec / f"{base}.schema.json", "a chapter has either the standard files of В7 or the "
                                                             "dialect form source, not both (ADR-0092)")
                self.form_v7(norms, text, spec / base, where, verdicts, classes)
            elif source.exists():
                if schema.exists():
                    self.error(schema, "a chapter has either the ADR-0085 pair or the ADR-0087 form source, not both")
                self.form_source(norms, text, source, schema_refs, spec / f"{base}.scalars.tsv", where, verdicts,
                                 classes)
            elif schema.exists() or schema_refs.exists():
                self.manifest_schema(schema, schema_refs, where / "cases", verdicts, classes)
            self.families(norms, text, prefix)
            choices = self.choices(text) if text is not None else None
            # A chapter's own texts count the chapter.
            for path, body in chapter_texts.items():
                self.counts(path, body, prefix, ids, scenarios, False, verdict_counts, choices or None)
            all_ids += [value for value in ids if value not in self.system_ids]   # the inventory lists readiness items
            total_choices += choices or 0
            for name, value in (("scenarios", scenarios), ("verdicts", verdict_counts)):
                if value is not None:
                    old = totals[name]
                    if name == "scenarios":
                        totals[name] = (value if old is None else
                                        (old[0] + value[0], old[1] + value[1], old[2] | {f"{chapter}/{n}" for n in value[2]}))
                    else:
                        totals[name] = value if old is None else tuple(a + b for a, b in zip(old, value))
        if stem == "02-installer" and not vms:
            self.canonical_chapter()
        if self.catalog is not None and chapters:
            shared = {k for (k, _), row in self.catalog.items() if row["owner"] == key}
            for missing in sorted(shared - owned):
                self.error(lesson, f"«Данные»: no chapter owns {missing}, the catalog gives it to {key}")
        if not vms:
            self.data_roles(lesson, key, number, saids)
            named = {r for r in self.lesson_roles(number) if not r.startswith("proc:")}
            reader = named or self.lesson_roles(number)  # роль процесса; `proc:<каталог>` — только у урока без неё
            for _, said in saids:                   # читатели `*` по нормам: роли процесса урока, чей «Данные» читает
                for k in said["читает"]:
                    self.star_readers.setdefault(k, set()).update(reader)
            self.lessons_seen.add(number)
        else:
            self.stats["vms_lessons_checked"] += 1
        # The lecture and the instruction count the whole lesson: sums over the chapters.
        for path, text in texts.items():
            self.counts(path, text, key, all_ids, totals["scenarios"], path == instructions, totals["verdicts"],
                        total_choices or None, lecture=path == lesson)
        self.checklist_inventory(spec / f"{stem}.README.md", instructions, key, all_ids)
        if not vms:
            self.stage_norms(home, key)
        self.stale(key, acceptance)
        self.stats["lessons"] += 1

    # The VMS module (constants VMS_*): the three common tables in form, every lesson of lessons.tsv has its directory
    # and, if it names a subsystem, its manifest there; every manifest under VMS/ belongs to the lesson of its
    # directory. Without VMS/ (an export before the start) nothing is checked.
    def vms_module(self):
        if not (self.root / VMS_DIR).is_dir():
            return
        path = self.root / VMS_LESSONS
        if not path.is_file():
            self.error(path, "the VMS module reads its lessons from VMS/common/lessons.tsv (ADR-0090 доп. (1))")
            return
        text = self.read(path) or ""
        header = next((line[1:].strip().split("\t") for line in text.splitlines() if line.startswith("# lesson\t")), None)
        if header != VMS_LESSONS_FIELDS:
            self.error(path, f"header expected # {chr(9).join(VMS_LESSONS_FIELDS)}")
        lessons = {}
        for line, cols in self.tsv(path, len(VMS_LESSONS_FIELDS)):
            row = dict(zip(VMS_LESSONS_FIELDS, cols))
            if not re.fullmatch(r"[0-9]{2}", row["lesson"]) or not re.fullmatch(rf"{row['lesson']}-[a-z][a-z0-9-]*", row["dir"]):
                self.error(path, f"line {line}: lesson NN and dir NN-<имя>")
                continue
            if row["dir"] in lessons:
                self.error(path, f"line {line}: dir {row['dir']} repeated")
            if row["status"] not in VMS_STATUS:
                self.error(path, f"line {line}: status is one of {sorted(VMS_STATUS)}")
            where = self.root / VMS_DIR / row["dir"]
            if not where.is_dir():
                self.error(path, f"line {line}: no directory VMS/{row['dir']}")
            elif row["subsystem"] != "-" and not (where / f"{row['subsystem']}.subsystem.yaml").is_file():
                self.error(path, f"line {line}: no manifest VMS/{row['dir']}/{row['subsystem']}.subsystem.yaml")
            lessons[row["dir"]] = row
            self.stats["vms_lessons"] += 1
        for manifest in sorted((self.root / VMS_DIR).glob("*/*.subsystem.yaml")):
            row = lessons.get(manifest.parent.name)
            if row is None or manifest.name != f"{row['subsystem']}.subsystem.yaml":
                self.error(manifest, "a VMS manifest lies in the directory of the lesson that lessons.tsv gives it")
            self.stats["vms_manifests"] += 1
        for table, fields in ((VMS_CATALOG, VMS_CATALOG_FIELDS), (VMS_IDMAP, IDMAP_FIELDS)):
            rows = self.tsv(self.root / table, len(fields)) if (self.root / table).is_file() else None
            if rows is None:
                self.error(self.root / table, "missing (ADR-0090 доп. (1), «Условия старта»)")
            elif not rows or rows[0][1] != fields:
                self.error(self.root / table, f"expected header {' '.join(fields)}")
            else:
                self.stats["vms_table_rows"] += len(rows) - 1

    def vms_catalog(self):
        """Строки каталога VMS как в файле (v7.vms.read_catalog), [] — нет файла или заголовок не тот (называет
        vms_families)."""
        if self.vms_rows is None:
            from v7 import spec as v7spec, vms
            try:
                self.vms_rows = vms.read_catalog(self.root) or []
            except v7spec.SpecError:
                self.vms_rows = []
        return self.vms_rows

    def vms_norms(self, address):
        """`V/NN[.K]` → the lesson file VMS/NN-<имя>/NN-<имя>.md or the chapter VMS/NN-<имя>/spec/NN.K-*.norms.md; None
        if absent."""
        number, _, chapter = address[2:].partition(".")
        path = self.root / VMS_LESSONS
        dirs = [cols[1] for _, cols in self.tsv(path, len(VMS_LESSONS_FIELDS)) if cols[0] == number] \
            if path.is_file() else []
        for d in dirs:
            found = sorted((self.root / VMS_DIR / d / "spec").glob(f"{number}.{chapter}-*.norms.md")) if chapter \
                else [p for p in [lecture_of(self.root / VMS_DIR / d)] if p.is_file()]
            if found:
                return found[0]
        return None

    # Families of VMS in the open places of Platform families (решение «Архитектора» по запросу VMS, вариант А): the
    # rows of VMS/common/data/catalog.tsv in form (columns of the Platform catalog, roles of the VMS subsystems, owner
    # V/NN[.K]), each an instance of one Platform family with a schema, its place open there, its schema, layers and
    # outcomes sound (v7.vms.check_rows); the outcome of the whole value for each reader (readers ∪ cas/guard), as on
    # the Platform; the vectors VMS/common/vectors/family-read/NN.tsv on the В7 stack. Once per run from main().
    def vms_families(self):
        if not self.v7 or not (self.root / VMS_CATALOG).is_file():
            return
        if str(SCRIPTS) not in sys.path:
            sys.path.insert(0, str(SCRIPTS))
        try:
            from v7 import spec as v7spec, vms
        except ImportError as exc:
            self.error(self.root / VMS_CATALOG, f"VMS families need the В7 stack, missing: {exc}; run: {V7_INSTALL}")
            return
        path = self.root / VMS_CATALOG
        try:
            rows = vms.read_catalog(self.root) or []
        except v7spec.SpecError:
            return                                   # vms_module names the header
        roles = v7spec.vms_roles(self.root)
        role = "(?:" + "|".join(re.escape(r) for r in sorted(roles, key=len, reverse=True)) + "|" + ROLE[3:] \
            if roles else ROLE
        words = self.when_words(self.root / CATALOG)
        when_key = self.manifest_key(path, words)
        good = []
        for row in rows:
            try:
                if not row["key"]:
                    raise ValueError("key is empty")
                if row["kind"] not in {"row", "object", "file"}:
                    raise ValueError("kind is the kind of a Platform family with a schema: row, object or file")
                if not re.fullmatch(VMS_LESSON, row["owner"]) or self.vms_norms(row["owner"]) is None:
                    raise ValueError("owner names an existing VMS lesson or chapter (V/NN[.K])")
                ops = parse_ops(row["ops"], role)
                readers = parse_roles(row["readers"], "readers", role)
                if not re.fullmatch(r"-|[a-z_]+(?:\.[a-z_]+)*", row["when"]) or (
                        row["when"] != "-" and row["when"] not in words and not when_key(row["when"])):
                    raise ValueError(f"when is - or a key path of the manifest (as in {CATALOG})")
                if not re.fullmatch(r"[1-9][0-9]*", row["version"]):
                    raise ValueError("version is an integer ≥ 1")
                norm = re.match(rf"{VMS_LESSON}|{LESSON}", row["norm"])
                if not norm or (self.vms_norms(norm.group(0)) if norm.group(0).startswith("V/")
                                else self.lesson_norms(norm.group(0))) is None:
                    raise ValueError("norm names an existing VMS or Platform lesson")
            except ValueError as exc:
                self.error(path, f"line {row['line']}: {exc}")
                continue
            good.append((row, readers | ops.get("cas", set()) | ops.get("guard", set())))
        self.stats["vms_catalog_rows"] += len(rows)
        errors, judges = vms.check_rows(self.root)
        for where, message in errors:
            self.error(self.root / where, message)
        for row, want in good:
            j = judges.get((row["key"], row["kind"], row["place"]))
            if j is None:
                continue
            self.stats["vms_families"] += 1
            named = {o.reader for o in j.outcomes if o.path == ""}
            where = j.outcomes_path
            for o in j.outcomes:
                if o.path and o.reader != "*" and o.reader not in want:
                    self.error(where, f"outcomes: {o.path} names {o.reader}, not a reader of {row['key']} by the VMS "
                                      f"catalog (readers ∪ cas/guard) and not *")
            for r in sorted(want - named):
                self.error(where, f"outcomes: no outcome of the whole value (empty path) for the reader {r} of "
                                  f"{row['key']} (readers ∪ cas/guard of the VMS catalog)")
            for r in sorted(named - want):
                self.error(where, f"outcomes: {r} is not a reader of {row['key']} by the VMS catalog (readers ∪ "
                                  f"cas/guard)")
        errors, stats = vms.check_tables(self.root, judges)
        for where, message in errors:
            self.error(self.root / where, message)
        self.stats.update(stats)

    # The witness's bytes in Source/vms/ are frozen at the start of the VMS kit (ADR-0090 доп. (7) п. 4): every file
    # there (bytecode caches aside) is in the list with its sha256, and nothing else is there. Without the list (an
    # export, a slice before the start) nothing is checked.
    def vms_frozen(self):
        frozen = self.root / VMS_FROZEN
        if not frozen.is_file():
            return
        import hashlib
        listed = {}
        for line_no, line in enumerate((self.read(frozen) or "").splitlines(), 1):
            if not line or line.startswith("#"):
                continue
            match = re.fullmatch(r"([0-9a-f]{64})  (Source/vms/\S.*)", line)
            if not match:
                self.error(frozen, f"line {line_no}: expected <sha256><two spaces>Source/vms/<path>")
                continue
            listed[match.group(2)] = match.group(1)
        present = {str(p.relative_to(self.root)) for p in (self.root / VMS_FROZEN_DIR).rglob("*")
                   if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}
        for name in sorted(present - set(listed)):
            self.error(self.root / name, "Source/vms/ is frozen since the VMS start: a new file (ADR-0090 доп. (7) п. 4)")
        for name, digest in sorted(listed.items()):
            path = self.root / name
            if name not in present:
                self.error(path, "Source/vms/ is frozen since the VMS start: the file is gone (ADR-0090 доп. (7) п. 4)")
            elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                self.error(path, "Source/vms/ is frozen since the VMS start: the bytes changed (ADR-0090 доп. (7) п. 4)")
            self.stats["vms_frozen"] += 1

def environment():
    """Pins of REQUIREMENTS against the installed distributions: [(package, installed or None, pinned)] that differ. The
    result of the check must not depend on the environment: a missing or other version is an error, never a skip."""
    from importlib import metadata
    norm = lambda name: re.sub(r"[-_.]+", "-", name).lower()   # noqa: E731
    out = []
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        m = re.match(r"([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;]+)", line)
        if not m:
            continue
        try:
            got = metadata.version(norm(m.group(1)))
        except metadata.PackageNotFoundError:
            got = None
        if got != m.group(2):
            out.append((m.group(1), got, m.group(2)))
    return out


def _platform_phase(args, names):
    """Current Platform source pipeline; no VMS inventories or VMS globals."""
    check = Check(args.root, args.exceptions, args.strict_coverage, scope="platform")
    if (check.root / LESSONS).is_file():
        check.canonical_layout()
    for name, got, want in environment():
        check.error(REQUIREMENTS, f"environment: {name} {got or 'is missing'}, pinned {want}; run: {SCHEMA_INSTALL}")
    rows = check.lessons_table()[1]
    if names is None:
        names = [lecture_of(check.root / "Platform" / row["dir"]).relative_to(check.root).as_posix()
                 for _, row in rows if row.get("dir") and lecture_of(check.root / "Platform" / row["dir"]).is_file()]
    for line, row in rows:
        if not row.get("dir") or not lecture_of(check.root / "Platform" / row["dir"]).is_file():
            check.error(check.root / LESSONS, f"line {line}: lesson {row.get('lesson')} has no file "
                                              f"Platform/{row.get('dir')}/{row.get('dir')}.md (or ru/ by ADR-0124)")
    if not names:
        check.error(check.root / LESSONS, "no lessons: name them or keep Platform/lessons.tsv")
    for name in names:
        check.lesson((check.root / name).resolve())
    for method in ("registered_shared_lessons", "vector_hashes", "outcome_readers", "family_read", "common_contracts", "stub_text",
                   "library_defects", "layer_words", "english_mirrors", "check_tables", "check_machines", "check_forms",
                   "form_refs", "target_registry", "export_lists", "m_form"):
        getattr(check, method)()
    check.check_cyrillic(args.cyrillic_debt)
    return check


def _vms_phase(args, view, names):
    """Current VMS source with fixed Platform dependencies; dependency errors stay errors."""
    check = Check(view, args.exceptions, True, scope="vms")
    for name, got, want in environment():
        check.error(REQUIREMENTS, f"environment: {name} {got or 'is missing'}, pinned {want}; run: {SCHEMA_INSTALL}")
    lessons = ([lecture_of(d) for d in sorted((view / "VMS").glob("[0-9][0-9]-*")) if lecture_of(d).is_file()]
               if names is None else [view / name for name in names])
    for path in lessons:
        check.lesson(path.resolve())
    check.stats["vms_lessons_checked"] = len(lessons)
    for method in ("vms_module", "vector_hashes", "vms_frozen", "vms_families", "english_mirrors"):
        getattr(check, method)()
    check.check_cyrillic(args.cyrillic_debt)
    return check


def _phase_result(check, label):
    return {"phase": label, "status": "FAIL" if check.errors else "PASS",
            "errors": list(check.errors), "exceptions": list(check.excepted), "counts": dict(check.stats)}


def _print_phase(result):
    print("PHASE", result["phase"], result["status"])
    for error in result["errors"]:
        print("ERROR", result["phase"], error)
    for line in result.get("exceptions", []):
        print("EXCEPTION", result["phase"], line)
    print("COUNTS", result["phase"], " ".join(f"{k}={v}" for k, v in sorted(result.get("counts", {}).items())))


def _code_binding(args):
    """Bind local checker bytes as well as the source/pin identities in the report."""
    paths = {*SCRIPTS.rglob("*.py"), REQUIREMENTS, args.exceptions, args.cyrillic_debt}
    return [{"path": str(p.resolve()), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in sorted(paths) if p.is_file()]


def _vms_reports(args, names):
    import tempfile
    import traceback
    from vms_platform_pin import PinError, read_pin, verify_owner_pin, materialize_vms_view, _git
    root = args.root.resolve()
    evidence = args.vms_evidence.absolute() if args.vms_evidence else Path(tempfile.mkdtemp(prefix="check-spec-vms-")).resolve()
    if evidence == root or root in evidence.parents or evidence.parent.resolve() != evidence.parent.absolute():
        raise PinError("VMS evidence must be outside source without symlink parents")
    if args.vms_evidence:
        evidence.mkdir(parents=True, exist_ok=False)
    report = {"format": "check_spec.vms-platform-pin/1", "source_root": str(root),
              "code_inputs": _code_binding(args),
              "checker_source_root": str(SCRIPTS.parents[2]),
              "checker_source_commit": _git(SCRIPTS.parents[2], "rev-parse", "HEAD").decode().strip(),
              "selected_vms_lessons": names, "strict_vms_coverage": True,
              "interpreter": {"path": sys.executable, "version": sys.version},
              "owner_pin_writer": "Owner representative only",
              "canonical_policy": "Owner pin required; no live fallback; diagnostics do not change canonical verdict",
              "phases": []}
    owner = None
    try:
        owner = read_pin(root)
        report["owner_platform_commit"] = owner.commit
        report["owner_pin_sha256"] = owner.source_sha256
    except Exception as exc:
        report["phases"].append({"phase": "VMS_CANONICAL", "status": "ERROR",
                                 "errors": [f"{type(exc).__name__}: {exc}"], "counts": {},
                                 "traceback": traceback.format_exc()})
    if owner is not None:
        modes = [("VMS_CANONICAL", None, False)]
        if args.vms_candidate:
            modes.append(("VMS_REPIN_CANDIDATE", args.vms_candidate, False))
        if args.vms_live:
            modes.append(("VMS_LIVE_NONBLOCKING", None, True))
        for label, candidate, live in modes:
            view = evidence / label.lower()
            result = {"phase": label, "status": "ERROR", "errors": [], "counts": {},
                      "candidate_commit": candidate, "nonblocking": label != "VMS_CANONICAL", "view": str(view)}
            try:
                result["inputs"] = materialize_vms_view(root, owner, view, candidate=candidate, live=live)
                result.update(_phase_result(_vms_phase(args, view, names), label))
                verify_owner_pin(root, owner)
            except Exception as exc:
                # A failed checker/input operation is an ERROR with preserved traceback,
                # never a semantic pass or an invitation to substitute live dependencies.
                result["status"] = "ERROR"
                result["errors"].append(f"{type(exc).__name__}: {exc}")
                result["traceback"] = traceback.format_exc()
            report["phases"].append(result)
        try:
            verify_owner_pin(root, owner)
        except (PinError, OSError) as exc:
            report["phases"][0]["status"] = "ERROR"
            report["phases"][0]["errors"].append(str(exc))
    report["canonical_status"] = report["phases"][0]["status"]
    path = evidence / "report.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for result in report["phases"]:
        _print_phase(result)
    if args.vms_evidence or report["canonical_status"] != "PASS":
        print("VMS_REPORT", path)
    else:                                   # OBSH.54: a passing run without --vms-evidence keeps no temporary directory
        shutil.rmtree(evidence, ignore_errors=True)
        print("VMS_REPORT removed (PASS; pass --vms-evidence <dir> to keep the evidence)")
    return report


def main():
    parser = arguments()
    args = parser.parse_args()
    if args.scope == "platform" and (args.vms_candidate or args.vms_live or args.vms_evidence):
        parser.error("VMS report options require --scope vms or all")
    normalized = []
    for name in args.lessons:
        path = Path(name)
        if path.is_absolute():
            try:
                path = path.relative_to(args.root.resolve())
            except ValueError:
                parser.error("selected lessons must be under the source root")
        if ".." in path.parts:
            parser.error("selected lessons cannot traverse outside their source module")
        normalized.append(path.as_posix())
    args.lessons = normalized
    # A selected VMS lesson is still checked through the mandatory pinned view.
    vms_names = [name for name in args.lessons if Path(name).parts and Path(name).parts[0] == "VMS"]
    platform_names = [name for name in args.lessons if name not in vms_names]
    if args.scope == "platform" and vms_names or args.scope == "vms" and platform_names:
        parser.error("selected lessons must belong to the requested source phase")
    import check_cyrillic
    root = args.root.resolve()
    if check_cyrillic.export_mode(root):
        check = Check(root, args.exceptions, args.strict_coverage)
        check.error(root, "check_spec requires the full course source at the exact nested COURSE_COMMIT; "
                          "an export omits history and frozen witnesses. Run source check_spec and the "
                          "separate export identity/roster proof plus check_cyrillic --export; see validation.md")
        check.check_cyrillic(args.cyrillic_debt)
        _print_phase(_phase_result(check, "SOURCE_REQUIRED"))
        print("FAIL source proof requires the complete course tree; no export checks were silently skipped")
        return 1
    failed = False
    if args.scope in ("all", "platform") and (not args.lessons or platform_names):
        result = _phase_result(_platform_phase(args, platform_names if args.lessons else None), "PLATFORM_CURRENT")
        _print_phase(result)
        failed |= result["status"] != "PASS"
    if args.scope in ("all", "vms"):
        try:
            report = _vms_reports(args, vms_names if args.lessons else None)
            failed |= report["canonical_status"] != "PASS"
        except (OSError, ValueError) as exc:
            print("ERROR VMS_CANONICAL report setup:", exc)
            failed = True
    print("FAIL" if failed else "PASS", "structural checks only; semantic review and implementation acceptance remain separate")
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
