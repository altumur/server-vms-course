"""P/02 gen_vectors output from wire.tsv; this module specifies only the adapters' Go API, not wiring or expectations.

P/01 keeps gen_tests; lessons without a complete form use wire_draft. Every P/02 run, including shared packages,
uses wire.py, the unified command/stand and validation of the full native response.
"""
import base64
import hashlib
import json
import re
from pathlib import Path

import common_vectors
import gate
import wire

# Go signatures are a package choice. Only wire.tsv defines inputs, fixtures, expectations, grouping and comparisons.
API_P02 = [
    ('02-installer/canonical', 'cases.tsv', 'stand:canonical', 'Canonical', 'source'),
    ('02-installer/exec', 'cases.tsv', 'stand:exec', 'Exec', 'input'),
    ('02-installer/install-order', 'cases.tsv', 'stand:install-order', 'InstallOrder', 'input'),
    ('02-installer/workers-script', 'cases.tsv', 'stand:workers-script', 'WorkersScript', 'input'),
    ('02-installer/platform-lists', 'cases.tsv', 'stand:platform-lists', 'PlatformLists', 'none'),
    ('02-installer/platform-lists', 'cases.tsv', 'vectors', 'PlatformLists', 'none'),
    ('common/env-file', 'cases.tsv', 'stand:env-line', 'EnvLine', 'input'),
    ('common/env-file', 'files.tsv', 'vectors', 'EnvFile', 'cells'),
    ('common/domain-backup-key', 'cases.tsv', 'vectors', 'DomainBackupKey', 'cells'),
    ('common/domain-founding', 'book-seal.tsv', 'vectors', 'DomainFounding', 'cells'),
    ('common/domain-founding', 'recovery.tsv', 'vectors', 'DomainFounding', 'cells'),
    ('common/loopback', 'cases.tsv', 'vectors', 'Loopback', 'cells'),
    ('common/sealing', 'aad.tsv', 'vectors', 'Sealing', 'cells'),
    ('common/sealing', 'envelope.tsv', 'vectors', 'Sealing', 'cells'),
    ('common/sealing', 'open.tsv', 'vectors', 'Sealing', 'cells'),
    ('common/sealing', 'reseal.tsv', 'vectors', 'Sealing', 'cells'),
    ('common/sealing', 'ring.tsv', 'vectors', 'Sealing', 'cells'),
    ('common/yaml-suite', 'expect.tsv', 'vectors', 'YamlSuite', 'cells'),
]


def declarations(root, lesson="02-installer", api=API_P02):
    bindings = wire.lesson_bindings(root, lesson)
    runs, _ = wire.expand(root, lesson)
    active = {}
    for run in runs:
        active.setdefault(run.binding.key, []).append(run)
    by = {b.key: b for b in bindings if b.key in active}
    out = []
    columns = ("package", "table", "surface", "fn", "args")
    api_rows, seen_api, signatures = [], set(), {}
    for row in api:
        if isinstance(row, dict):
            if set(row) != set(columns):
                raise wire.WireError(f"Go API admits only {columns}, got {sorted(row)}")
            row = tuple(row[k] for k in columns)
        else:
            row = tuple(row)
        if len(row) != 5 or not all(isinstance(x, str) for x in row):
            raise wire.WireError(f"invalid Go API mapping {row!r}")
        if row[:3] in seen_api:
            raise wire.WireError(f"duplicate Go API mapping {row[:3]}")
        seen_api.add(row[:3])
        fn, args = row[3:]
        if not re.fullmatch(r"[A-Z][A-Za-z0-9_]*", fn) or (fn in signatures and signatures[fn] != args):
            raise wire.WireError(f"conflicting/invalid Go API function {fn!r}")
        signatures[fn] = args
        api_rows.append(row)
    jcs = ("01-store/jcs", "canonical_json.tsv", "vectors")
    if lesson == "02-installer" and jcs in by and not any(row[:3] == jcs for row in api_rows):
        api_rows.append((*jcs, "JCS", "cells"))
    for package, table, surface, fn, args in api_rows:
        key = package, table, surface
        if key not in by:
            raise wire.WireError(f"{wire.FORM}: missing adapter binding {key} for {lesson}")
        b, selected = by[key], active[key]
        if args not in {"cells", "cells+variant", "source", "input", "none"}:
            raise wire.WireError(f"{key}: unknown Go API args {args!r}")
        if surface == "vectors" and args == "input" and any(len(r.cells) != 1 or r.files for r in selected):
            raise wire.WireError(f"{key}: input API requires exactly one cell and no fixtures")
        if surface == "vectors" and args == "source":
            raise wire.WireError(f"{key}: source API requires a stand argument file")
        d = dict(package=package, table=table, surface=surface, fn=fn, args=args)
        if package == "02-installer/platform-lists" and args == "none" and surface == "vectors":
            d["per_list"] = True
        d["doc"] = f"Native input and output: Platform/{b.norm}; transport: Platform/common/vectors/wire.tsv."
        d["inputs"] = sorted({k for r in selected for k in (r.cells or {})})
        d["files"] = {k: b.files[k] for r in selected for k in r.files}
        d["compare"] = b.compare
        d["native"] = b.native
        shapes = {}
        for r in selected:
            shape = (",".join(sorted(r.cells or {})), ",".join(sorted(r.files)))
            if shape not in shapes.setdefault(r.variant, []):
                shapes[r.variant].append(shape)
        d["wire_shapes"] = shapes
        if any("literal" in v for x in b.inputs for v in x.get("cells", {}).values()):
            d["extra_cells"] = True
        out.append(d)
    common = {(f"common/{n}", t, "vectors") for n, t in common_vectors.composition(lesson, root, known_only=True)}
    missing = set(by) - {tuple(d[k] for k in ("package", "table", "surface")) for d in out} - common
    if missing:
        raise wire.WireError(f"{wire.FORM}: no Go adapter API for {sorted(missing)}")
    if common - set(by):
        raise wire.WireError(f"{wire.FORM}: missing common bindings {sorted(common - set(by))}")
    covered = {(b.package, b.table) for b in bindings}
    required = {key for key, owners in wire.consumers(root).items() if lesson in owners}
    if required - covered:
        raise wire.WireError(f"{wire.FORM}: undeclared consumers {sorted(required - covered)}")
    stages = Path(root) / "Platform" / lesson / "forms/stages.kit.tsv"
    if stages.is_file():
        lines = [line.split("\t") for line in stages.read_text().splitlines() if line and not line.startswith("#")]
        gate_column = lines[0].index("gate")
        try:
            packages = {p for row in lines[1:]
                        for p in gate.vector_packages(row[gate_column], lesson)}
        except gate.GateError as exc:
            raise wire.WireError(f"stages.kit.tsv: {exc}") from None
        for pkg in sorted(packages):
            if not any(b.package == pkg for b in bindings):
                raise wire.WireError(f"{wire.FORM}: undeclared stages.kit.tsv package {pkg}")
    return out


def check_native(native):
    supported = {"type", "enum", "const", "allOf", "anyOf", "oneOf", "not", "if", "then", "else", "properties",
                 "patternProperties", "additionalProperties", "unevaluatedProperties", "propertyNames", "required",
                 "dependentRequired", "minProperties", "maxProperties", "items", "minItems", "maxItems", "uniqueItems",
                 "minLength", "maxLength", "pattern", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
                 "description", "title", "default", "examples", "format", "readOnly", "contentMediaType"}
    def walk(s):
        if isinstance(s, bool):
            return
        if not isinstance(s, dict) or set(s) - supported:
            raise wire.WireError(f"{wire.FORM}: unsupported native schema {s!r}")
        for k in ("properties", "patternProperties"):
            for sub in s.get(k, {}).values():
                walk(sub)
        for k in ("allOf", "anyOf", "oneOf"):
            for sub in s.get(k, []):
                walk(sub)
        for k in ("not", "if", "then", "else", "additionalProperties", "unevaluatedProperties", "propertyNames", "items"):
            if k in s:
                walk(s[k])
    if "schema" in native:
        walk(native["schema"])


def payload(r):
    return json.dumps({"format": 1, "package": r.binding.package, "table": r.binding.table,
                       "case": r.case, "variant": r.variant, "cells": r.cells,
                       "files": {k: base64.b64encode(v).decode("ascii") for k, v in r.files.items()}},
                      ensure_ascii=False, indent=1) + "\n"


def expectation(r):
    out = {"code": r.code, "ignore": r.ignore_stdout, "value": None if isinstance(r.value, bytes) else r.value,
           "raw": base64.b64encode(r.value).decode("ascii") if isinstance(r.value, bytes) else None,
           "compare": r.compare, "native": r.native,
           "asserts": [{k: v for k, v in a._asdict().items() if k != "ignore" or v is not None} for a in r.asserts]}
    if r.ignore:
        out["ignored"] = r.ignore
    return json.dumps(out, ensure_ascii=False)


def build(root, g, decls=None, lesson=None):
    key = lesson or g.L.key
    decls = declarations(root, key) if decls is None else decls
    runs, excluded = wire.expand(root, key)
    known = g.common_vectors.composition(key, root, known_only=True)
    return render(root, g, decls, runs, excluded, known)


def runtime_files(g, full=False):
    # P/02 remains byte-for-byte on its published runtime. Full grammar is explicitly selected by its caller.
    schema = (g.HERE / "doorrt2/go/schema.go").read_text()
    if schema.count("// mediaType ") != 1:
        raise g.GenError("schema runtime boundary moved")
    schema = schema.split("// mediaType ", 1)[0]
    if "func validate(" not in schema or "func DecodeRequest(" in schema:
        raise g.GenError("schema runtime boundary moved")
    schema = schema.replace("package apidoor", "package wirecheck").replace('\n\t"math"', '')
    checker = "wirert/full/go/check.go" if full else "wirert/go/check.go"
    return {"go/wirecheck/schema.go": g.gofmt(schema + '\nconst bundle = `{ "$defs": {} }`\n').encode(),
            "go/wirecheck/check.go": (g.HERE / checker).read_bytes()}


def render(root, g, decls, runs, excluded, known=(), scaffold=True):
    for r in runs:
        check_native(r.native)
    files, inv = {}, []
    by_fn = {}
    for d in decls:
        by_fn.setdefault(d["fn"], []).append(d)
    files["go/vectoradapter/vectoradapter.go"] = g.gofmt(g.TYPES_GO).encode()
    for fn, ds in by_fn.items():
        files[f"go/vectoradapter/{fn.lower()}.go"] = g.gofmt(g.stub(ds)).encode()
    if scaffold:
        for name, text in g.common_vectors.adapters(g.L.key, known_only=True, root=root).items():
            files[f"go/vectoradapter/{name}"] = g.gofmt(text).encode()
    bindings = {r.binding.key: r.binding for r in runs}
    if scaffold:
        files["go/vectorcmd/vectorcmd.go"] = (g.go_vectorcmd(decls, known, bindings) if g.L.key == "02-installer"
                                                else g.go_vectorcmd(decls, known, bindings, full_wire=True)).encode()
        files["go/cmd/vectors/main.go"] = g.gofmt(g.MAIN_GO % g.GO_MODULE).encode()
    helper = "helpers_test.go" if scaffold else "consumer_helpers_test.go"
    helper_text = HELPER
    if scaffold and g.L.key != "02-installer":
        helper_text = helper_text.replace("code = vectorcmd.Stand(stand, p, &o, &e)\n        out, errout = o.Bytes(), e.Bytes()",
                                          "var err error\n        code, out, errout, err = vectorcmd.StandResult(stand, p)\n        if err != nil { t.Fatal(err) }")
        helper_text = helper_text.replace("var o, e bytes.Buffer", "")
        helper_text = helper_text.replace('    "bytes"\n', '')
    files["go/vectortests/" + helper] = g.gofmt(helper_text.replace("MODULE", g.GO_MODULE)).encode()
    files.update(runtime_files(g, full=g.L.key != "02-installer"))
    groups = {}
    for r in runs:
        groups.setdefault(r.binding.key, []).append(r)
    for (pkg, table, surface), rs in groups.items():
        common = pkg.startswith("common/") and (pkg[7:], table) in known
        name = ("Common" if common else "") + g.camel(pkg.split("/", 1)[1])
        if not common:
            name += "_" + g.camel(table[:-4])
        if surface.startswith("stand:") and (pkg, table, "vectors") in groups:
            name += "_Stand"
        source = f"Platform/{pkg.split('/')[0]}/vectors/{pkg.split('/')[1]}/{table}"
        sha = hashlib.sha256((Path(root) / source).read_bytes()).hexdigest()
        out = ["// Code generated by tools/normgen/gen_vectors.py from wire.tsv; DO NOT EDIT.\n",
               f"// Source {source} sha256 {sha}.\npackage vectortests\nimport \"testing\"\n"]
        case_lines = []
        for r in rs:
            suffix = "_Lists" if len(r.lines) > 1 and surface.startswith("stand:") else f"_Line{r.lines[0]}{g.camel(r.variant)}"
            test = f"Test{name}{suffix}"
            arg = payload(r).encode() if surface == "vectors" else r.arg
            key = "" if surface == "vectors" else surface.split(":", 1)[1]
            out.append(f"\nfunc {test}(t *testing.T) {{ checkWire(t, {g.go_str(key)}, {g.go_str(Path(r.arg_path).name if r.arg_path else 'input')}, []byte({g.go_bytes(arg)}), {g.gstr(expectation(r))}) }}\n")
            label = f"{pkg} {table} {','.join(map(str,r.lines))} {surface} {r.variant}".rstrip()
            inv.append((label, "translated"))
            if surface == "vectors":
                stem = f"line-{r.lines[0]}" + (f"-{r.variant}" if r.variant else "")
                files[f"vectors/{pkg}/{table[:-4]}/{stem}.json"] = payload(r).encode()
                case_lines.append(f"{stem}\t{stem}.json\t{r.code}\t" + json.dumps(r.value, ensure_ascii=False))
        files[f"go/vectortests/{'common_' + pkg[7:].replace('-', '_') if common else name.lower()}_test.go"] = g.gofmt("".join(out)).encode()
        if case_lines:
            files[f"vectors/{pkg}/{table[:-4]}/cases.tsv"] = ("case\tinput\texit\tstdout\n" + "\n".join(case_lines) + "\n").encode()
    for e in excluded:
        why = "a layout test (wire.tsv)" if e.binding.surface == "layout" else e.reason
        inv.append((f"{e.binding.package} {e.binding.table}" + (f" {e.line}" if e.line else ""), "excluded: " + why))
    files["go/vectortests/inventory.tsv"] = ("# Vector runs from wire.tsv; layout and unselected rows are excluded.\ntable\tstatus\n" + "\n".join("\t".join(x) for x in inv) + "\n").encode()
    if not scaffold:
        files.pop("go/vectoradapter/vectoradapter.go", None)
        files.pop("go/vectortests/inventory.tsv", None)
    return files, inv


HELPER = r'''// Code generated by tools/normgen/gen_vectors.py; DO NOT EDIT.
package vectortests
import (
    "bytes"
    "os"
    "path/filepath"
    "testing"
    "MODULE/vectorcmd"
    "MODULE/wirecheck"
)
func checkWire(t *testing.T, stand, name string, input []byte, spec string) {
    t.Helper()
    var code int
    var out, errout []byte
    if stand == "" {
        var err error
        code, out, errout, err = vectorcmd.Run(input)
        if err != nil { t.Fatal(err) }
    } else {
        p := filepath.Join(t.TempDir(), name)
        if err := os.WriteFile(p, input, 0600); err != nil { t.Fatal(err) }
        var o, e bytes.Buffer
        code = vectorcmd.Stand(stand, p, &o, &e)
        out, errout = o.Bytes(), e.Bytes()
    }
    if err := wirecheck.Check(code, out, spec); err != nil {
        t.Fatalf("%v; stderr %s", err, errout)
    }
}
'''
