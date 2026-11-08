"""Judge refusal catalogs against the form, acceptance and door (ADR-0125 generator 4, addendum 1, item 1).

  python tools/normgen/refusal_judge.py [--module-dir <module-with-refusals-and-door>] [--json <result>]
Default module: out/p01-1/go; stdlib and Go 1.22 suffice. Reread refusals.tsv independently and compare every harness-reported Spec's code, kind, fields, headers and log. Each acceptance chapters1..3 4xx/5xx JSON expectation must match a catalog code/kind: chapter 1.1 requires all mandatory fields plus optional fields, while1.2/1.3 use subsets. Every HTTP Spec must encode through apidoor.Refuse/Encode for at least one OpenAPI operation, with required/all fields and Retry-After where declared.

Runner refusal steps on the door stub are the door judge's task. Result: refusals:P/N PASS|FAIL; exit 0=all pass, 1=failure, 2=judge startup error."""
import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import lesson  # noqa: E402 -- lesson selection (ADR-0125 addendum(5), item 2)
L = lesson.CURRENT
TABLE = L.form("refusals.tsv")
ACCEPTANCE = L.path("acceptance")
WHOLE = {"1"}                 # Chapters comparing full bodies (acceptance1.1 README); others use subsets.


class CheckingError(RuntimeError):
    """The source or observation is unavailable, malformed or incomplete; never a semantic kill."""


def read_table(path=None):
    path = TABLE if path is None else Path(path)
    lines = [x for x in path.read_text(encoding="utf-8").splitlines() if x and not x.startswith("#")]
    columns = ["chapter", "row", "name", "surface", "code", "kind", "fields", "headers", "log", "norm"]
    if not lines or lines[0].split("\t") != columns:
        raise CheckingError("missing or malformed HTTP refusal catalogue header")
    rows = []
    names = set()
    for cells in csv.reader(lines[1:], delimiter="\t", quoting=csv.QUOTE_NONE):
        if len(cells) != len(columns):
            raise CheckingError("malformed HTTP refusal catalogue row")
        r = dict(zip(columns, cells))
        if (not re.fullmatch(r"[a-z][a-z0-9_]*", r["name"]) or r["name"] in names or
                not re.fullmatch(r"[0-9]+\.[0-9]+", r["chapter"]) or
                not re.fullmatch(r"[1-9][0-9]*", r["row"])):
            raise CheckingError("missing/duplicate name or malformed source coordinates")
        names.add(r["name"])
        fields = [] if r["fields"] == "-" else r["fields"].split(",")
        if any(not re.fullmatch(r"[a-z][a-z_]*\??", f) or f.rstrip("?") in ("kind", "error") for f in fields):
            raise CheckingError(f"{r['name']}: malformed field token")
        if len({f.rstrip("?") for f in fields}) != len(fields):
            raise CheckingError(f"{r['name']}: duplicate field")
        r["req"] = {f for f in fields if not f.endswith("?")}
        r["opt"] = {f[:-1] for f in fields if f.endswith("?")}
        if r["surface"] == "http":
            if not re.fullmatch(r"[1-5][0-9]{2}", r["code"]) or not re.fullmatch(r"[a-z]+", r["kind"]):
                raise CheckingError(f"{r['name']}: malformed HTTP code/kind")
            r["code_n"] = int(r["code"])
        elif r["surface"] in ("start", "cli"):
            if r["code"] not in ("exit 2", "exit !0") or any(r[k] != "-" for k in ("kind", "fields", "headers")):
                raise CheckingError(f"{r['name']}: malformed process refusal")
            r["code_n"] = 2 if r["code"] == "exit 2" else 1
        else:
            raise CheckingError(f"{r['name']}: unknown source surface")
        r["header_pairs"] = []
        if r["headers"] != "-":
            for header in r["headers"].split(";"):
                match = re.fullmatch(r"\s*([A-Za-z][A-Za-z0-9-]*): (\S.*?)\s*", header)
                if match is None:
                    raise CheckingError(f"{r['name']}: malformed header")
                r["header_pairs"].append([match[1], match[2]])
        logs = [] if r["log"] == "-" else [x.strip() for x in re.findall(r"«[^«»]*»|[^,«»]+", r["log"]) if x.strip()]
        r["log_names"] = [x for x in logs if not x.startswith("«")]
        r["log_words"] = [x[1:-1] for x in logs if x.startswith("«")]
        rows.append(r)
    if not rows:
        raise CheckingError("the HTTP refusal source has no catalogue rows")
    return rows


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise CheckingError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(value):
    raise CheckingError(f"nonfinite JSON constant: {value}")


def _shape(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise CheckingError("missing/extra/malformed private report members")


def _strings(value):
    if value is not None and (type(value) is not list or any(type(x) is not str for x in value)):
        raise CheckingError("private report requires a string array or null")
    for text in value or []:
        _text(text)


def _text(value):
    if type(value) is not str:
        raise CheckingError("private report requires text")
    try:
        value.encode("utf-8", "strict")
    except UnicodeError as exc:
        raise CheckingError("private report contains a non-scalar Unicode string") from exc


def read_report(raw):
    """Validate the whole service frame before comparing any generated metadata with Source."""
    try:
        if type(raw) is bytes:
            raw = raw.decode("utf-8", "strict")
        if type(raw) is not str:
            raise CheckingError("private report is not UTF-8 text")
        raw.encode("utf-8", "strict")
        report = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeError, ValueError) as exc:
        raise CheckingError(f"invalid private report: {exc}") from exc
    _shape(report, ("version", "declared", "completed", "rows"))
    if (type(report["version"]) is not int or report["version"] != 1 or
            type(report["declared"]) is not int or report["declared"] < 0 or
            type(report["completed"]) is not int or report["completed"] != report["declared"] or
            type(report["rows"]) is not list or len(report["rows"]) != report["declared"]):
        raise CheckingError("incomplete private catalogue observation")
    for row in report["rows"]:
        _shape(row, ("Chapter", "Row", "Name", "Surface", "Code", "Kind", "Fields", "Headers",
                     "RetryAfter", "Log", "Words", "Norm", "probes"))
        if (any(type(row[k]) is not str for k in ("Chapter", "Name", "Surface", "Kind", "Norm")) or
                any(type(row[k]) is not int for k in ("Row", "Code")) or type(row["RetryAfter"]) is not bool):
            raise CheckingError("mistyped observed catalogue scalar")
        for key in ("Chapter", "Name", "Surface", "Kind", "Norm"):
            _text(row[key])
        for key in ("Log", "Words"):
            _strings(row[key])
        fields = row["Fields"] or []
        if row["Fields"] is not None and type(row["Fields"]) is not list:
            raise CheckingError("mistyped observed fields")
        for field in fields:
            _shape(field, ("Name", "Optional"))
            if type(field["Name"]) is not str or type(field["Optional"]) is not bool:
                raise CheckingError("mistyped observed field role")
            _text(field["Name"])
        if row["Headers"] is not None and type(row["Headers"]) is not list:
            raise CheckingError("mistyped observed headers")
        for header in row["Headers"] or []:
            if type(header) is not list or len(header) != 2 or any(type(x) is not str for x in header):
                raise CheckingError("mistyped observed header pair")
            for value in header:
                _text(value)
        required = [f["Name"] for f in fields if not f["Optional"]]
        all_fields = [f["Name"] for f in fields]
        sets = [required] + ([all_fields] if len(required) != len(all_fields) else []) if row["Surface"] == "http" else []
        probes = row["probes"] or []
        if row["probes"] is not None and type(row["probes"]) is not list:
            raise CheckingError("mistyped probe cohort")
        if len(probes) != len(sets):
            raise CheckingError("partial/extra observation of declared field cohorts")
        for probe, expected_fields in zip(probes, sets):
            _shape(probe, ("fields", "ints", "ops", "retry", "body"))
            for key in ("fields", "ints", "ops"):
                _strings(probe[key])
            if ((probe["fields"] or []) != expected_fields or type(probe["retry"]) is not bool or
                    type(probe["body"]) is not str):
                raise CheckingError("wrong field-cohort identity or mistyped probe")
            _text(probe["body"])
    return report["rows"]


def harness(module_dir, work):
    hdir = Path(work) / "harness"
    hdir.mkdir()
    shutil.copy(HERE / "refusals/harness/main.go", hdir / "main.go")
    (hdir / "go.mod").write_text(f"module normgen/refusalharness\n\ngo 1.22\n\nrequire {L.go_module} v0.0.0\n\n"
                                 f"replace {L.go_module} => {Path(module_dir).resolve()}\n", encoding="utf-8")
    try:
        done = subprocess.run(["go", "run", "."], cwd=hdir, capture_output=True, timeout=300)
    except (OSError, subprocess.SubprocessError) as exc:
        raise CheckingError(f"cannot execute the harness: {exc}") from exc
    if type(done.returncode) is not int or done.returncode != 0 or done.stderr:
        raise CheckingError(f"the harness did not complete normally: exit={done.returncode}, stderr={done.stderr!r}")
    return read_report(done.stdout)


def expectations():
    """Return acceptance refusal expectations as [(chapter, scenario, step, status, kind, fields)]."""
    out = []
    for ch in sorted(p.name for p in ACCEPTANCE.iterdir() if p.is_dir()):
        for line in (ACCEPTANCE / ch / "scenarios.tsv").read_text(encoding="utf-8").splitlines():
            cells = line.split("\t")
            if len(cells) != 4 or not (m := re.fullmatch(r"([45][0-9]{2}) (\{.*\})", cells[3])):
                continue
            try:
                body = json.loads(m[2])
            except ValueError:
                continue
            if isinstance(body, dict) and "kind" in body:
                out.append((ch, cells[0], cells[1], int(m[1]), body["kind"], set(body) - {"kind", "error"}))
    return out


PLAIN_HARNESS = '''// Harness of refusal_judge.py for a catalogue without an HTTP door: refusals.All as one JSON.
package main

import (
	"encoding/json"
	"os"

	"%s/refusals"
)

func main() {
    rows := append([]*refusals.Spec{}, refusals.All...)
    _ = json.NewEncoder(os.Stdout).Encode(struct {
        Version int `json:"version"`
        Declared int `json:"declared"`
        Completed int `json:"completed"`
        Rows []*refusals.Spec `json:"rows"`
    }{1, len(refusals.All), len(rows), rows})
}
'''
RUN_EXIT = re.compile(r"^exit (0|[1-9][0-9]*)(;|$)")



PLAIN_COLUMNS = ("chapter row name surface code kind fields headers log norm word cause outcome diagnostic caller").split()
RESPONSE_COLUMNS = PLAIN_COLUMNS[:11] + ["response_schema"] + PLAIN_COLUMNS[11:]


class SourceSchemas:
    """Independent physical-resource admission and declaration-local schema reference chains."""
    _MAPS = ('properties', 'patternProperties', '$defs', 'dependentSchemas')
    _LISTS = ('allOf', 'anyOf', 'oneOf', 'prefixItems')
    _SINGLES = ('items', 'additionalProperties', 'unevaluatedProperties', 'not', 'if', 'then', 'else',
                'contains', 'propertyNames', 'unevaluatedItems', 'contentSchema', 'x-line-schema')

    def __init__(self, path):
        try:
            import importlib.util
            import hashlib
            import yaml
            from jsonschema import Draft202012Validator, SchemaError
            scripts = ROOT / 'skills/lesson-spec/scripts'
            parser = scripts / 'check_spec.py'
            spec = importlib.util.spec_from_file_location('refusal_source_check_spec', parser)
            grammar = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(grammar)
            except SystemExit as exc:
                raise CheckingError(f'cannot load canonical Source YAML parser: {exc}') from exc
            self.yaml, self.loader, self.object_edges = yaml, grammar.UniqueLoader, grammar.OBJECT_EDGES
            self.dependencies = {'path': str(parser), 'sha256': hashlib.sha256(parser.read_bytes()).hexdigest(),
                                 'loader': 'check_spec.UniqueLoader', 'positions': 'check_spec.OBJECT_EDGES'}
            self.validator, self.schema_error = Draft202012Validator, SchemaError
            self.main = Path(path).absolute()
            self.platform = next((p for p in self.main.parents if p.name == 'Platform'), None)
            if self.platform is None:
                raise CheckingError('schema owner must be inside Platform')
            self.cache, self.raw_identities, self.validated = {}, {}, set()
            self._typed, self._roots, self._edges = {}, {}, {}
            self._indexed, self._admitted, self._graph_checked = set(), set(), set()
            self._depth = 0
            self.doc = self.load(self.main)
        except CheckingError:
            raise
        except (OSError, UnicodeError, ValueError, TypeError, AttributeError, ImportError, RecursionError) as exc:
            raise CheckingError(f'cannot admit Source schemas: {exc}') from exc

    def _operation(self):
        from contextlib import contextmanager
        @contextmanager
        def guard():
            outer = self._depth == 0
            self._depth += 1
            try:
                if outer:
                    self._verified = set()
                    self._verify()
                yield
                if outer:
                    self._verify()
            except CheckingError:
                raise
            except (OSError, UnicodeError, ValueError, TypeError, AttributeError, KeyError, IndexError,
                    RecursionError) as exc:
                raise CheckingError(f'invalid or unavailable Source resource: {exc}') from exc
            finally:
                self._depth -= 1
        return guard()

    def _snapshot(self, path):
        import hashlib
        import stat
        path = Path(path).absolute()
        a = path.stat()
        if not stat.S_ISREG(a.st_mode):
            raise CheckingError(f'not a regular Source resource: {path}')
        raw = path.read_bytes()
        b = path.stat()
        fields = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if fields(a) != fields(b):
            raise CheckingError(f'Source resource changed during read: {path}')
        identity = {'physical': str(path.resolve()), 'stat': fields(b), 'sha256': hashlib.sha256(raw).hexdigest()}
        return raw, identity

    def _verify(self):
        # Reuse never trusts an admitted parsed value after any resource changed or disappeared.
        for path, prior in self.raw_identities.items():
            _, now = self._snapshot(path)
            if now != prior:
                raise CheckingError(f'admitted Source resource changed: {path}')
            self._verified.add(path)

    def _inside(self, path):
        import os
        declared = Path(os.path.abspath(path))
        try:
            lexical = declared.relative_to(self.platform).parts
            physical = declared.resolve().relative_to(self.platform.resolve()).parts
        except ValueError as exc:
            raise CheckingError('schema reference escapes Platform') from exc
        owner = lambda parts: parts[0] if len(parts) >= 2 and (parts[0] == 'common' or
                               re.fullmatch(r'[0-9]{2}-[a-z][a-z-]*', parts[0])) else None
        if owner(lexical) is None or owner(lexical) != owner(physical):
            raise CheckingError('schema reference changes physical owner')
        return declared, lexical, physical

    def _raw(self, path):
        path, _, _ = self._inside(path)
        raw, identity = self._snapshot(path)
        if path in self.raw_identities and self.raw_identities[path] != identity:
            raise CheckingError(f'admitted Source resource changed: {path}')
        self.raw_identities.setdefault(path, identity)
        self._verified.add(path)
        return raw

    @staticmethod
    def _json_value(value, active=()):
        import math
        if value is None or type(value) in (bool, int):
            return
        if type(value) is str:
            value.encode('utf-8', 'strict')
            return
        if type(value) is float:
            if not math.isfinite(value):
                raise CheckingError('nonfinite Source value')
            return
        if type(value) not in (dict, list) or id(value) in active:
            raise CheckingError('non-JSON or cyclic Source value')
        active = active + (id(value),)
        if type(value) is dict:
            for key, child in value.items():
                if type(key) is not str:
                    raise CheckingError('nontext Source mapping key')
                key.encode('utf-8', 'strict')
                SourceSchemas._json_value(child, active)
        else:
            for child in value:
                SourceSchemas._json_value(child, active)

    def _load(self, path):
        declared, _, _ = self._inside(path)
        physical = declared.resolve()
        if declared in self._verified and physical in self.cache:
            return self.cache[physical]
        raw = self._raw(declared)
        if physical not in self.cache:
            text = raw.decode('utf-8', 'strict')
            try:
                document = (json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
                            if physical.name.endswith('.json') else self.yaml.load(text, Loader=self.loader))
            except self.yaml.YAMLError as exc:
                raise CheckingError(f'malformed Source YAML: {exc}') from exc
            self._json_value(document)
            self.cache[physical] = document
        return self.cache[physical]

    def load(self, path):
        with self._operation():
            document = self._load(path)
            self._admit_all()
            return document

    def _validate(self, node):
        if id(node) not in self.validated:
            try:
                self.validator.check_schema(node)
            except self.schema_error as exc:
                raise CheckingError(f'malformed full response schema: {exc.message}') from exc
            self.validated.add(id(node))

    def validate(self, node):
        with self._operation():
            self._json_value(node)
            self._validate(node)

    @staticmethod
    def _token(value):
        return str(value).replace('~', '~0').replace('/', '~1')

    def _children(self, node, pointer):
        if type(node) is not dict:
            return
        for keyword in self._MAPS:
            if keyword in node:
                if type(node[keyword]) is not dict:
                    raise CheckingError('malformed schema map')
                for key, child in node[keyword].items():
                    yield pointer + '/' + keyword + '/' + self._token(key), child
        for keyword in self._LISTS:
            if keyword in node:
                if type(node[keyword]) is not list:
                    raise CheckingError('malformed schema composition')
                for index, child in enumerate(node[keyword]):
                    yield pointer + '/' + keyword + '/' + str(index), child
        for keyword in self._SINGLES:
            if keyword in node:
                yield pointer + '/' + keyword, node[keyword]

    def _index(self, path):
        if path in self._indexed:
            return
        doc = self._load(path)
        self._typed[path], self._roots[path] = {}, []
        def schema(node, at):
            if type(node) not in (dict, bool):
                raise CheckingError('malformed Schema Object')
            self._validate(node)  # Includes typed x-line-schema children; never annotation payloads.
            self._typed[path][at] = node
            for pointer, child in self._children(node, at):
                schema(child, pointer)
        def objects(node, kind, at):
            if node is None and kind != 'schema':
                return
            if kind == 'schema':
                self._roots[path].append(at)
                schema(node, at)
            elif kind.startswith('[]'):
                if type(node) is not list:
                    raise CheckingError('malformed Source object sequence')
                for i, child in enumerate(node):
                    objects(child, kind[2:], at + '/' + str(i))
            elif kind.startswith('*'):
                if type(node) is not dict:
                    raise CheckingError('malformed Source object map')
                for key, child in node.items():
                    objects(child, kind[1:], at + '/' + self._token(key))
            else:
                if type(node) is not dict:
                    raise CheckingError('malformed Source OpenAPI object')
                if kind in ('paths', 'responses', 'callback'):
                    child_kind = {'paths': 'path', 'responses': 'response', 'callback': 'path'}[kind]
                    for key, child in node.items():
                        if not key.startswith('x-') and key != '$ref':
                            objects(child, child_kind, at + '/' + self._token(key))
                else:
                    for key, child_kind in self.object_edges.get(kind, {}).items():
                        if key in node:
                            objects(node[key], child_kind, at + '/' + self._token(key))
        if path.name.endswith('.schema.json'):
            self._roots[path].append('')
            schema(doc, '')
        else:
            objects(doc, 'document', '')
        self._indexed.add(path)

    @staticmethod
    def _uri(ref):
        from urllib.parse import urlsplit, unquote
        if type(ref) is not str or not ref or re.search(r'[\x00-\x20\\]', ref) or re.search(r'%(?![0-9a-fA-F]{2})', ref):
            raise CheckingError('invalid relative schema URI')
        ref.encode('utf-8', 'strict')
        uri = urlsplit(ref)
        if uri.scheme or uri.netloc or uri.query or '?' in ref.split('#', 1)[0]:
            raise CheckingError('nonlocal schema reference')
        file = unquote(uri.path, encoding='utf-8', errors='strict')
        pointer = unquote(uri.fragment, encoding='utf-8', errors='strict')
        (file + pointer).encode('utf-8', 'strict')
        if file.startswith('/') or '\\' in file or '\x00' in file or (pointer and not pointer.startswith('/')):
            raise CheckingError('expected relative path and JSON Pointer')
        if re.search(r'~(?![01])', pointer):
            raise CheckingError('malformed JSON pointer escape')
        return file, pointer

    def _late(self, base, origin, owner):
        if not origin or not origin.startswith('/paths/'):
            return False
        tokens = origin.split('/')
        path_key = tokens[2].replace('~1', '/').replace('~0', '~')
        declaration = self.cache[base]['paths'][path_key]
        source_owner = base.relative_to(self.platform.resolve()).parts[0]
        match = re.match(r'(?:Chapter|Глава) ([0-9]+)\.([0-9]+)(?![0-9.])', str(declaration.get('description', '')))
        if not match or int(match[1]) != int(source_owner[:2]):
            return False
        norm = base.parent / f'{source_owner[:2]}.{int(match[2])}-{source_owner[3:]}.norms.md'
        if not norm.is_file():
            return False
        head = '\n'.join(self._raw(norm).decode('utf-8', 'strict').splitlines()[:12])
        numbers = r'([0-9]+(?:(?:, | and )[0-9]+)*)'
        late = (re.search(r'A chapter of the late layer: lessons? ' + numbers + r' introduce(?:s)? it', head) or
                re.search(r'A chapter of the late layer: introduced by lessons? ' + numbers, head) or
                re.search(r'Глава позднего слоя: ввод(?:ит|ят) урок(?:и)? ([0-9]+(?:(?:, | и )[0-9]+)*)', head))
        return bool(late and int(owner[:2]) in {int(n) for n in re.findall(r'[0-9]+', late[1])})

    def _edge(self, ref, base, origin=None):
        import os
        file, pointer = self._uri(ref)
        base = Path(base).resolve()
        self._load(base)
        path = Path(os.path.abspath(base.parent / file)) if file else base
        declared, lexical, physical = self._inside(path)
        target = declared.resolve()
        if file:
            standalone = path.name.endswith('.schema.json')
            if not (standalone or path.name.endswith('.openapi.yaml')):
                raise CheckingError('unsupported schema resource')
            if standalone and (len(lexical) != 3 or lexical[1] != 'data' or len(physical) != 3 or physical[1] != 'data'):
                raise CheckingError('standalone schema outside owner data directory')
            if target == base:
                raise CheckingError('same-resource reference must be a local pointer')
            source_owner = base.relative_to(self.platform.resolve()).parts[0]
            owner = physical[0]
            if source_owner == 'common' and owner != 'common':
                raise CheckingError('common schema cannot refer to a lesson owner')
            if source_owner != 'common' and owner != 'common':
                if not (standalone and owner == source_owner) and int(owner[:2]) >= int(source_owner[:2]):
                    if owner == source_owner or not self._late(base, origin, owner):
                        raise CheckingError('schema declaration lacks reference rights to this owner')
        self._index(target)  # Full physical declaration validity, not just the selected leaf.
        if pointer not in self._typed[target]:
            raise CheckingError(f'reference target is not a declared Schema Object: {ref}')
        return self._typed[target][pointer], target, pointer

    def _walk_chain(self, base, pointer, active=(), files=()):
        key = (base, pointer)
        if key in active:
            segment = active[active.index(key):]
            if any(uri != base for uri, _ in segment):
                raise CheckingError('cross-resource schema reference cycle')
            return  # Only the closed segment determines whether recursion is local.
        node = self._typed[base][pointer]
        active = active + (key,)
        if type(node) is dict and '$ref' in node:
            _, target, at = self._edges[key]
            self._walk_chain(target, at, active, files + (base,) if target != base else files)
        for at, _ in self._children(node, pointer):
            self._walk_chain(base, at, active, files)

    def _admit_all(self):
        # Physical scans start independently; they never inherit the caller's reference chain.
        while True:
            remaining = set(self.cache) - self._admitted
            if not remaining:
                break
            base = sorted(remaining)[0]
            self._index(base)
            for pointer, node in list(self._typed[base].items()):
                if type(node) is dict and '$ref' in node:
                    self._edges[(base, pointer)] = self._edge(node['$ref'], base, pointer)
            self._admitted.add(base)
        if self._graph_checked != self._admitted:
            for base in sorted(self._admitted):
                for pointer in self._roots[base]:
                    self._walk_chain(base, pointer)
            self._graph_checked = set(self._admitted)

    def target(self, ref, base):
        with self._operation():
            node, path, pointer = self._edge(ref, base)
            self._admit_all()
            return node, path, pointer

    def closure(self, node, base, active=(), files=()):
        with self._operation():
            base = Path(base).resolve()
            self._load(base)
            self._admit_all()
            self._json_value(node)
            self._validate(node)
            if type(node) is bool:
                return
            positions = [at for at, value in self._typed[base].items() if value is node]
            if not positions:
                raise CheckingError('schema lacks a declaration position')
            self._walk_chain(base, positions[0], active, files)

    def schema(self, name):
        with self._operation():
            self._load(self.main)
            self._admit_all()
            base = self.main.resolve()
            pointer = '/components/schemas/' + self._token(name)
            if pointer not in self._typed[base]:
                raise CheckingError(f'unknown response schema {name}')
            node, seen = self._typed[base][pointer], set()
            annotations = {'$ref', 'title', 'description', '$comment', 'default', 'examples', 'deprecated', 'readOnly', 'writeOnly'}
            while type(node) is dict and '$ref' in node and not set(node) - annotations:
                key = (base, pointer)
                if key in seen:
                    raise CheckingError('cyclic response schema alias')
                seen.add(key)
                node, base, pointer = self._edges[key]
            return node


def read_plain_source(path=None):
    path = TABLE if path is None else Path(path)
    lines = [x for x in path.read_text(encoding='utf-8').splitlines() if x and not x.startswith('#')]
    columns = lines[0].split('\t') if lines else []
    if columns not in (PLAIN_COLUMNS, RESPONSE_COLUMNS) or len(lines) < 2:
        raise CheckingError('missing/unknown plain catalogue columns or zero rows')
    rows, seen = [], set()
    schemas = SourceSchemas(L.openapi) if columns == RESPONSE_COLUMNS else None
    for line in lines[1:]:
        cells = line.split('\t')
        if len(cells) != len(columns) or any(not cell for cell in cells):
            raise CheckingError('malformed plain catalogue row')
        r = dict(zip(columns, cells))
        if (not re.fullmatch(r'[a-z][a-z0-9_]*', r['name']) or r['name'] in seen or
                not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', r['chapter']) or
                not re.fullmatch(r'[1-9][0-9]*', r['row']) or r['kind'] != '-'):
            raise CheckingError('malformed/duplicate source identity or kind')
        seen.add(r['name'])
        surface, code = r['surface'], r['code']
        if surface not in ('call', 'cli', 'start', 'process', 'peer') + (('http',) if schemas else ()):
            raise CheckingError('unknown source surface')
        if code != '-' and not ((surface != 'peer' and re.fullmatch(r'exit (?:0|[1-9][0-9]*|!0)', code))
                                or (surface in ('call', 'peer', 'http') and re.fullmatch(r'[1-5][0-9]{2}', code))):
            raise CheckingError('malformed source code')
        names, optional = [], []
        for token in ([] if r['fields'] == '-' else r['fields'].split(',')):
            match = re.fullmatch(r'([a-z][a-z0-9_]*)(\??)', token.strip())
            if match is None or match[1] in names or surface not in ('http', 'peer'):
                raise CheckingError('malformed/duplicate/out-of-context source field')
            names.append(match[1])
            if match[2]:
                if not schemas or surface != 'http' or r['response_schema'] == '-':
                    raise CheckingError('optional source field without response schema')
                optional.append(match[1])
        if schemas and r['response_schema'] != '-':
            if surface != 'http':
                raise CheckingError('response schema outside http')
            schema = schemas.schema(r['response_schema'])  # Always validate full closure, even fields=-.
            if r['fields'] != '-':
                if type(schema) is not dict or '$ref' in schema or type(schema.get('properties')) is not dict:
                    raise CheckingError('explicit fields lack direct schema properties')
                required = schema.get('required', [])
                if (type(required) is not list or any(type(x) is not str for x in required) or
                        len(set(required)) != len(required) or not set(required) <= set(names) - set(optional) or
                        not set(names) <= set(schema['properties'])):
                    raise CheckingError('source schema/form field roles disagree')
        if r['headers'] != '-':
            if surface not in ('peer', 'http'):
                raise CheckingError('headers outside response context')
            for header in r['headers'].split(';'):
                if not re.fullmatch(r'\s*[A-Za-z][A-Za-z0-9-]*: \S.*?\s*', header):
                    raise CheckingError('malformed source header')
        r['_fields'], r['_optional'] = names, optional
        rows.append(r)
    return rows


def read_plain_report(raw, rows):
    try:
        if type(raw) is bytes:
            raw = raw.decode('utf-8', 'strict')
        raw.encode('utf-8', 'strict')
        report = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeError, ValueError, AttributeError) as exc:
        raise CheckingError(f'invalid private plain report: {exc}') from exc
    _shape(report, ('version', 'declared', 'completed', 'rows'))
    if (type(report['version']) is not int or report['version'] != 1 or
            type(report['declared']) is not int or report['declared'] <= 0 or
            type(report['completed']) is not int or report['completed'] != report['declared'] or
            type(report['rows']) is not list or len(report['rows']) != report['declared']):
        raise CheckingError('incomplete/zero private plain catalogue observation')
    keys = 'Chapter Row Name Surface Exit AnyNonZero Status Word Log Words Norm Fields Headers Named WordCell'.split()
    if 'response_schema' in rows[0]:
        keys.append('Response')
    if any(r['_optional'] for r in rows):
        keys.append('OptionalFields')
    seen = set()
    for row in report['rows']:
        _shape(row, keys)
        for key in ('Row', 'Exit', 'Status'):
            if type(row[key]) is not int:
                raise CheckingError('mistyped plain report integer')
        if type(row['AnyNonZero']) is not bool:
            raise CheckingError('mistyped plain report boolean')
        for key in ('Chapter', 'Name', 'Surface', 'Word', 'WordCell', 'Norm') + (('Response',) if 'Response' in keys else ()):
            _text(row[key])
        if row['Name'] in seen:
            raise CheckingError('duplicate observed catalogue name')
        seen.add(row['Name'])
        for key in ('Log', 'Words', 'Fields', 'Named') + (('OptionalFields',) if 'OptionalFields' in keys else ()):
            _strings(row[key])
        if row['Headers'] is not None and type(row['Headers']) is not list:
            raise CheckingError('mistyped plain report headers')
        for header in row['Headers'] or []:
            if type(header) is not list or len(header) != 2:
                raise CheckingError('malformed plain report header pair')
            for value in header:
                _text(value)
    return report['rows']


def plain(a):
    """Compare the Source-selected plain layout with a complete compiled catalogue."""
    rows = read_plain_source()  # Complete Source oracle before invoking/reading the subject.
    with tempfile.TemporaryDirectory(prefix="refusal-judge-") as work:
        hdir = Path(work) / "harness"
        hdir.mkdir()
        (hdir / "main.go").write_text(PLAIN_HARNESS % L.go_module, encoding="utf-8")
        (hdir / "go.mod").write_text(f"module normgen/refusalharness\n\ngo 1.22\n\nrequire {L.go_module} v0.0.0\n\n"
                                     f"replace {L.go_module} => {Path(a.module_dir).resolve()}\n", encoding="utf-8")
        done = subprocess.run(["go", "run", "."], cwd=hdir, capture_output=True, timeout=300)
        if done.returncode != 0 or done.stderr:
            raise CheckingError(f"the harness failed: exit={done.returncode}, stderr={done.stderr!r}")
        got = read_plain_report(done.stdout, rows)
    results = []

    def check(name, why):
        results.append({"name": name, "ok": why is None, "why": why})
        if why:
            print(f"FAIL {name}: {why}", flush=True)

    check("catalogue: the same names in order", None if [g["Name"] for g in got] == [r["name"] for r in rows]
          else "the names differ from the table")
    by = {g["Name"]: g for g in got}
    for r in rows:
        g = by.get(r["name"])
        if not g:
            check(f"catalogue {r['name']}", "the complete compiled catalogue has no such row")
            continue
        code = r["code"]
        exit_, anyc, status = -1, code == "exit !0", 0
        if code.startswith("exit ") and code[5:].isdigit():
            exit_ = int(code[5:])
        elif code.isdigit():
            status = int(code)
        logs = [] if r["log"] == "-" else [x.strip() for x in re.findall(r"«[^«»]*»|[^,«»]+", r["log"]) if x.strip()]
        names = [x for x in logs if not x.startswith("«")]
        words = [x[1:-1] for x in logs if x.startswith("«")]
        toks = re.findall(r"`([^`]+)`", r["word"])
        plain_cell = re.sub(r"`[^`]+`|,|\s", "", r["word"]) == ""
        want_word, want_any = "", []
        if toks and plain_cell:
            want_word, want_any = (toks[0], []) if len(toks) == 1 else ("", toks)
        want_fields, want_optional = r["_fields"], r["_optional"]
        want_headers = [] if r["headers"] == "-" else [[x.strip() for x in h.split(": ", 1)] for h in r["headers"].split(";")]
        diffs = [k for k, ok in (("chapter", g["Chapter"] == r["chapter"]), ("row", g["Row"] == int(r["row"])),
                                 ("surface", g["Surface"] == r["surface"]), ("exit", g["Exit"] == exit_),
                                 ("any", g["AnyNonZero"] == anyc), ("status", g["Status"] == status),
                                 ("word", g["Word"] == want_word), ("named", (g.get("Named") or []) == want_any),
                                 ("word_cell", g["WordCell"] == r["word"]),
                                 ("fields", (g.get("Fields") or []) == want_fields),
                                 ("optional_fields", (g.get("OptionalFields") or []) == want_optional),
                                 ("headers", (g.get("Headers") or []) == want_headers),
                                 ("response", "response_schema" not in r or
                                  g.get("Response") == ("" if r["response_schema"] == "-" else r["response_schema"])),
                                 ("log", (g["Log"] or []) == names), ("words", (g["Words"] or []) == words),
                                 ("norm", g["Norm"] == r["norm"])) if not ok]
        check(f"catalogue {r['name']}", f"differs from the table in {diffs}" if diffs else None)
    codes = {g["Exit"] for g in got if g["Exit"] > 0}
    anyc = any(g["AnyNonZero"] for g in got)
    for seams in sorted(ACCEPTANCE.glob("*/seams.tsv")):
        for line in seams.read_text(encoding="utf-8").splitlines():
            cells = line.split("\t")
            if line.startswith("#") or len(cells) != 4 or not cells[2].startswith("RUN "):
                continue
            m = RUN_EXIT.match(cells[3])
            if not m or m[1] == "0":
                continue
            n = int(m[1])
            check(f"acceptance {seams.parent.name} {cells[0]} step {cells[1]}",
                  None if n in codes or anyc else f"exit {n}: no row of the catalogue with this code or «exit !0»")
    passed = sum(r["ok"] for r in results)
    verdict = "PASS" if passed == len(results) else "FAIL"
    print(f"refusals: {L.code} {passed}/{len(results)} {verdict}")
    if a.json:
        Path(a.json).write_text(json.dumps({"passed": passed, "total": len(results), "verdict": verdict,
                                            "results": results}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if verdict == "PASS" else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--module-dir", help="module to judge; default: the validated prepared lesson module")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    if a.module_dir is None:
        try:
            a.module_dir = str(lesson.ready_outputs(profiles=lesson.PROFILES)[L.slug] / "go")
        except (lesson.LessonError, OSError) as exc:
            print(f"refusal_judge: {exc}", file=sys.stderr)
            return 2
    if not shutil.which("go"):
        print("refusal_judge: go is not in PATH", file=sys.stderr)
        return 2
    try:
        head = next((x for x in TABLE.read_text(encoding="utf-8").splitlines() if x and not x.startswith("#")), None)
        if head is None:
            raise ValueError("the refusal source has no header")
    except (OSError, ValueError) as exc:
        print(f"refusal_judge: checking error: {exc}", file=sys.stderr)
        return 2
    if "word" in head.split("\t"):                         # Actual plain/response column layout.
        try:
            return plain(a)
        except (CheckingError, OSError, ValueError, KeyError, TypeError, RecursionError, subprocess.SubprocessError) as exc:
            print(f"refusal_judge: checking error: {exc}", file=sys.stderr)
            return 2
    try:
        rows = read_table()
        with tempfile.TemporaryDirectory(prefix="refusal-judge-") as work:
            got = harness(a.module_dir, work)
    except (CheckingError, OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        print(f"refusal_judge: checking error: {exc}", file=sys.stderr)
        return 2
    results = []

    def check(name, why):
        results.append({"name": name, "ok": why is None, "why": why})
        if why:
            print(f"FAIL {name}: {why}", flush=True)

    by = {g["Name"]: g for g in got}
    check("catalogue: the same names in order", None if [g["Name"] for g in got] == [r["name"] for r in rows]
          else f"{[g['Name'] for g in got]} vs the table")
    for r in rows:
        g = by.get(r["name"])
        if not g:
            check(f"catalogue {r['name']}", "the complete compiled catalogue has no such row")
            if r["surface"] == "http":
                sets = [r["req"]] + ([r["req"] | r["opt"]] if r["opt"] else [])
                for fields in sets:
                    check(f"door {r['name']} {sorted(fields)}", "the compiled catalogue has no such row")
            continue
        fields = {f["Name"]: f["Optional"] for f in g["Fields"] or []}
        want = {**{f: False for f in r["req"]}, **{f: True for f in r["opt"]}}
        headers = r["header_pairs"]
        diffs = [k for k, ok in (("chapter", g["Chapter"] == r["chapter"]), ("row", g["Row"] == int(r["row"])),
                                 ("surface", g["Surface"] == r["surface"]), ("code", g["Code"] == r["code_n"]),
                                 ("kind", g["Kind"] == ("" if r["kind"] == "-" else r["kind"])),
                                 ("fields", fields == want and len(g["Fields"] or []) == len(want)),
                                 ("headers", (g["Headers"] or []) == headers),
                                 ("retry", g["RetryAfter"] == any(h[0] == "Retry-After" for h in headers)),
                                 ("log", (g["Log"] or []) == r["log_names"]),
                                 ("words", (g["Words"] or []) == r["log_words"]),
                                 ("norm", g["Norm"] == r["norm"]))
                 if not ok]
        check(f"catalogue {r['name']}", f"differs from the table in {diffs}" if diffs else None)
        if r["surface"] == "http":
            sets = [r["req"]] + ([r["req"] | r["opt"]] if r["opt"] else [])
            for fields in sets:
                why = None
                candidates = [p for p in g["probes"] or [] if sorted(p["fields"] or []) == sorted(fields)]
                p = candidates[0] if len(candidates) == 1 else None
                if p is None:
                    why = "no unambiguous observation for the source field cohort"
                elif not p["ops"]:
                    why = f"apidoor.Refuse/Encode take the fields {p['fields'] or []} at no operation"
                elif g["RetryAfter"] and not p["retry"]:
                    why = "no operation declares Retry-After for it"
                check(f"door {r['name']} {sorted(fields)}", why)
    http = [r for r in rows if r["surface"] == "http"]
    for ch, sc, step, code, kind, fields in expectations():
        cands = [r for r in http if r["code_n"] == code and r["kind"] == kind]
        if ch in WHOLE:
            ok = any(r["req"] <= fields <= r["req"] | r["opt"] for r in cands)
        else:
            ok = any(fields <= r["req"] | r["opt"] for r in cands)
        check(f"acceptance {ch} {sc} step {step}", None if ok else
              f"{code} {kind} {sorted(fields)}: no row of the catalogue " +
              (f"(rows {[(r['name'], sorted(r['req']), sorted(r['opt'])) for r in cands]})" if cands else
               "with this code and kind"))
    passed = sum(r["ok"] for r in results)
    verdict = "PASS" if passed == len(results) else "FAIL"
    print(f"refusals: {passed}/{len(results)} {verdict}")
    if a.json:
        Path(a.json).write_text(json.dumps({"passed": passed, "total": len(results), "verdict": verdict,
                                            "results": results}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
