#!/usr/bin/env python3
"""Read-only structural checks for the published lecture + shared spec layout.

No product imports, execution of acceptance requests, or network reference loading.
Requires PyYAML and openapi-spec-validator; invocation and limits: validation.md.
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

try:
    import yaml
    from openapi_spec_validator import validate
except ImportError as exc:
    raise SystemExit(f"Missing dependency: {exc}. See references/validation.md")


class UniqueLoader(yaml.SafeLoader):
    """Reject duplicate contract keys instead of silently keeping the last one."""


def unique_mapping(loader, node, deep=False):
    loader.flatten_mapping(node)
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
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


def references(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref":
                yield value
            else:
                yield from references(value)
    elif isinstance(node, list):
        for value in node:
            yield from references(value)


def pointer(document, ref):
    if not isinstance(ref, str) or not (ref == "#" or ref.startswith("#/")):
        raise ValueError(f"external or unsupported reference {ref!r}; not checked offline")
    value = document
    fragment = unquote(ref[1:])
    for part in fragment.split("/")[1:]:
        part = part.replace("~1", "/").replace("~0", "~")
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


class Check:
    def __init__(self, root):
        self.root = root.resolve()
        self.errors = []
        self.stats = Counter()

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
        if re.search(r"\{\{[^\n]*?\}\}", text):
            self.error(path, "unfilled template marker {{...}}")
        plain = re.sub(r"^\s*(```|~~~).*?^\s*\1\s*$", "", text, flags=re.M | re.S)
        for target in re.findall(r"(?<!!)\[[^\]\n]+\]\(([^\s)]+)(?:\s+[^)]*)?\)", plain):
            url = urlsplit(target.strip("<>"))
            if url.scheme or url.netloc or not url.path:
                continue
            if url.path.startswith("/"):
                self.error(path, f"absolute local link is not portable: {target}")
            elif not (path.parent / unquote(url.path)).exists():
                self.error(path, f"missing link target: {target}")
            self.stats["local_links"] += 1

    def openapi(self, path):
        text = self.read(path)
        if text is None:
            return
        if "{{" in text:
            self.error(path, "unfilled contract template")
        try:
            doc = yaml.load(text, Loader=UniqueLoader)
            if not isinstance(doc, dict):
                raise ValueError("OpenAPI document must be an object")
            if not str(doc.get("openapi", "")).startswith("3.1."):
                raise ValueError("expected OpenAPI 3.1.x")
            if not isinstance(doc.get("paths"), dict) or not doc["paths"]:
                raise ValueError("no HTTP paths: unfinished contract or layout decision needed")
            # Resolve every ref before invoking the library: it cannot fetch an external one.
            for ref in references(doc):
                try:
                    pointer(doc, ref)
                except (KeyError, IndexError, TypeError, ValueError) as exc:
                    raise ValueError(f"unresolved/unsupported $ref {ref!r}: {exc}") from exc
                self.stats["local_refs"] += 1
            validate(doc)
            self.stats["openapi"] += 1
        except Exception as exc:
            self.error(path, f"OpenAPI: {exc}")

    def norms(self, path, text, prefix):
        headers = re.findall(r"^##\s+(Н[0-5])(?:\s|$)", text, re.M)
        if headers != [f"Н{i}" for i in range(6)]:
            self.error(path, "expected Н0–Н5 once, in order")
        ids = re.findall(r"^\s*- \[[ xX]\] \*\*(М\d+[A-ZА-Я]*/\d+-\d+)\*\*", text, re.M)
        if not ids:
            self.error(path, "no normative checklist ids")
        for value, count in Counter(ids).items():
            if count != 1 or not value.startswith(prefix + "-"):
                self.error(path, f"duplicate or foreign checklist id {value}")
        for title in ["Решает реализация", "Чеклист готовности"]:
            if not re.search(r"^## " + title + r"\s*$", text, re.M):
                self.error(path, f"missing section {title}")
        self.stats["norm_ids"] += len(ids)

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

    def scenarios(self, path):
        steps = Counter()
        for line, (scenario, step, request, expect) in self.tsv(path, 4):
            steps[scenario] += 1
            if not scenario or step != str(steps[scenario]):
                self.error(path, f"line {line}: invalid scenario/step sequence")
            if request.startswith("ASSERT "):
                if expect or not re.fullmatch(r"ASSERT \$\w+ != \$\w+(?: \$\w+)*", request):
                    self.error(path, f"line {line}: invalid ASSERT or nonempty expectation")
                continue
            # Deliberately invalid JSON requests are acceptance data, not parse errors here.
            if not re.match(r"^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS) /", request):
                self.error(path, f"line {line}: unsupported request form; needs format-specific check")
            code, separator, body = expect.partition(" ")
            try:
                if not separator or not re.fullmatch(r"[1-5]\d\d", code):
                    raise ValueError("expected HTTP status and JSON body")
                strict_json(body)
            except (ValueError, TypeError) as exc:
                self.error(path, f"line {line}: {exc}")
        self.stats["scenarios"] += len(steps)
        self.stats["steps"] += sum(steps.values())
        if not steps:
            self.error(path, "empty scenarios table")

    def verdicts(self, path):
        verdicts = {}
        for line, (case, result) in self.tsv(path, 2):
            invalid_name = not case or case in {".", ".."} or any(c in case for c in ["/", "\\", "\x00"])
            if case in verdicts or result not in {"ok", "refused"} or invalid_name:
                self.error(path, f"line {line}: duplicate/invalid case or verdict")
            verdicts[case] = result
        actual = {p.name.removesuffix(".subsystem.yaml") for p in (path.parent / "cases").glob("*.subsystem.yaml")}
        if actual != set(verdicts):
            self.error(path, f"cases/verdicts differ: missing={sorted(set(verdicts)-actual)}, unlisted={sorted(actual-set(verdicts))}")
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
        if lesson.parent.parent != self.root or not re.fullmatch(r"\d{2}-.+\.md", lesson.name):
            self.error(lesson, "expected module/NN-slug.md under repository root")
            return
        module = lesson.parent.name
        number = int(lesson.name[:2])
        prefix = f"{module.split('_', 1)[0]}/{number}"
        spec = lesson.parent / "spec"
        norms = spec / f"{lesson.stem}.norms.md"
        instructions = spec / f"{lesson.stem}.README.md"
        for path in [lesson, norms, instructions]:
            text = self.read(path)
            if text is not None:
                self.markdown(path, text)
                if path == norms:
                    self.norms(path, text, prefix)
        self.openapi(spec / f"{lesson.stem}.api.openapi.yaml")
        acceptance = self.root / "Source/tests/testdata/acceptance" / module / f"{number:02}"
        readme = acceptance / "README.md"
        text = self.read(readme)
        if text is not None:
            self.markdown(readme, text)
        self.tsv(acceptance / "corrections.tsv", 4, ["date", "sample", "fix", "languages"])
        formats = 0
        if (acceptance / "scenarios.tsv").exists():
            self.scenarios(acceptance / "scenarios.tsv")
            formats += 1
        if (acceptance / "verdicts.tsv").exists():
            verdicts = self.verdicts(acceptance / "verdicts.tsv")
            if (acceptance / "diagnostics.tsv").exists():
                self.diagnostics(acceptance / "diagnostics.tsv", verdicts)
            formats += 1
        elif (acceptance / "diagnostics.tsv").exists():
            self.error(acceptance, "diagnostics.tsv without verdicts.tsv")
        if not formats:
            self.error(acceptance, "no supported acceptance table; add a format-specific check")
        self.stats["lessons"] += 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lessons", nargs="+", help="module/NN-slug.md; only the new shared-spec layout")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root, default cwd")
    args = parser.parse_args()
    check = Check(args.root)
    for name in args.lessons:
        check.lesson((check.root / name).resolve())
    for error in check.errors:
        print("ERROR", error)
    print("COUNTS", " ".join(f"{key}={value}" for key, value in sorted(check.stats.items())))
    print("FAIL" if check.errors else "PASS", "structural checks only; semantic review and implementation acceptance remain separate")
    return int(bool(check.errors))


if __name__ == "__main__":
    sys.exit(main())
