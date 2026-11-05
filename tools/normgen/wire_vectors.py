"""Выход gen_vectors P/02 из wire.tsv; здесь только Go API адаптеров, не провод и не ожидания.

P/01 сохраняет прежний gen_tests; уроки без полной формы — wire_draft. Все запуски P/02 (включая общие)
идут через wire.py, единую команду/стенд и проверку полного нативного ответа.
"""
import base64
import hashlib
import json
import re
from pathlib import Path

import common_vectors
import wire

# Сигнатуры Go — выбор пакета. Входы, фикстуры, ожидания, группировки и сравнения задаёт только wire.tsv.
API = [
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


def declarations(root):
    bindings = wire.lesson_bindings(root, "02-installer")
    by = {b.key: b for b in bindings if b.surface != "layout"}
    out = []
    for package, table, surface, fn, args in API:
        key = package, table, surface
        if key not in by:
            raise wire.WireError(f"{wire.FORM}: missing adapter binding {key}")
        b = by[key]
        d = dict(package=package, table=table, surface=surface, fn=fn, args=args)
        if args == "none" and surface == "vectors":
            d["per_list"] = True    # the Go API returns all lists; vectorcmd projects one selected list
        d["doc"] = f"Native input and output: Platform/{b.norm}; transport: Platform/common/vectors/wire.tsv."
        d["inputs"] = sorted({k for x in b.inputs for k in x.get("cells", {})})
        d["files"] = b.files
        d["compare"] = b.compare
        if any("literal" in v for x in b.inputs for v in x.get("cells", {}).values()):
            d["extra_cells"] = True       # vectorcmd admits the optional rotate cell (API takes a map)
        out.append(d)
    common = {(f"common/{n}", t, "vectors") for n, t in common_vectors.composition(
        "02-installer", root, known_only=True)}
    missing = set(by) - {tuple(d[k] for k in ("package", "table", "surface")) for d in out} - common
    if missing:
        raise wire.WireError(f"{wire.FORM}: no Go adapter API for {sorted(missing)}")
    if common - set(by):
        raise wire.WireError(f"{wire.FORM}: missing common bindings {sorted(common - set(by))}")
    # Fail closed before touching out when a consumer has no wire declaration.
    covered = {(b.package, b.table) for b in bindings}
    required = {k for k, owners in wire.consumers(root).items() if "02-installer" in owners}
    if required - covered:
        raise wire.WireError(f"{wire.FORM}: undeclared consumers {sorted(required - covered)}")
    stages = Path(root) / "Platform/02-installer/forms/stages.tsv"
    lines = [line.split("\t") for line in stages.read_text().splitlines() if line and not line.startswith("#")]
    gate = lines[0].index("gate")
    for pkg in {p for row in lines[1:] for p in re.findall(r"vectors:([a-z0-9-]+)", row[gate])}:
        if not any(b.package == f"02-installer/{pkg}" for b in bindings):
            raise wire.WireError(f"{wire.FORM}: undeclared stages.tsv package {pkg}")
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
    return json.dumps({"code": r.code, "ignore": r.ignore_stdout, "value": None if isinstance(r.value, bytes) else r.value,
                       "raw": base64.b64encode(r.value).decode("ascii") if isinstance(r.value, bytes) else None,
                       "compare": r.compare, "native": r.native,
                       "asserts": [a._asdict() for a in r.asserts]}, ensure_ascii=False)


def build(root, g):
    decls = declarations(root)
    runs, excluded = wire.expand(root, "02-installer")
    for r in runs:
        check_native(r.native)
        if r.compare.startswith("lines-"):
            raise wire.WireError(f"{wire.FORM}: P/02 does not support {r.compare} yet")
    known = g.common_vectors.composition("02-installer", root, known_only=True)
    files, inv = {}, []
    by_fn = {}
    for d in decls:
        by_fn.setdefault(d["fn"], []).append(d)
    files["go/vectoradapter/vectoradapter.go"] = g.gofmt(g.TYPES_GO).encode()
    for fn, ds in by_fn.items():
        files[f"go/vectoradapter/{fn.lower()}.go"] = g.gofmt(g.stub(ds)).encode()
    for name, text in g.common_vectors.adapters("02-installer", known_only=True).items():
        files[f"go/vectoradapter/{name}"] = g.gofmt(text).encode()
    bindings = {b.key: b for b in wire.lesson_bindings(root, "02-installer")}
    files["go/vectorcmd/vectorcmd.go"] = g.go_vectorcmd(decls, known, bindings).encode()
    files["go/cmd/vectors/main.go"] = g.gofmt(g.MAIN_GO % g.GO_MODULE).encode()
    files["go/vectortests/helpers_test.go"] = g.gofmt(HELPER.replace("MODULE", g.GO_MODULE)).encode()
    # Reuse the independently judged schema engine of the door, up to the HTTP-specific functions.
    schema = (g.HERE / "doorrt2/go/schema.go").read_text().split("// mediaType —", 1)[0]
    if "func validate(" not in schema or "func DecodeRequest(" in schema:
        raise g.GenError("schema runtime boundary moved")
    schema = schema.replace("package apidoor", "package wirecheck").replace('\n\t"math"', '')
    files["go/wirecheck/schema.go"] = g.gofmt(schema + '\nconst bundle = `{ "$defs": {} }`\n').encode()
    files["go/wirecheck/check.go"] = (g.HERE / "wirert/go/check.go").read_bytes()
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
