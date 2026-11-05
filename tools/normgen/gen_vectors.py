"""Генератор части vectors урока без своей двери (P/02; ADR-0125 доп. (5) п. 5 — полный состав урока).

Запуск: python3 tools/normgen/gen_vectors.py --lesson 02-installer [<out>]

Состав — свои пакеты урока (stages.tsv: gate vectors:<пакет>) и общие по Platform/common/vectors/consumers.tsv.
Провод таблицы — объявление WIRE ниже: черновик формы Platform/common/vectors/wire.tsv («да» «Архитектора»; пишет
«Спецификация»), выписанный из README пакетов, общего правила «Vectors» и раннера-судьи (/home/pilot/wire-p02-draft.md);
форма его заменит. Пакеты, уже объявленные для P/01 (crl, revoked, log-mask, store-client, family-read), идут через
common_vectors.py теми же функциями адаптера. journal/modes.tsv — не исполняется (тест раскладки; README пакета).

Провод двух видов: единая команда `bin/vectors {input}` (кадр {format, package, table, case, variant, cells, files} →
{exit_code, stdout_b64, stderr_b64}) и команда стенда `bin/vectors stand <ключ> {input}` (свой код выхода, stdout —
JSON одной строкой с LF или сырые байты). Адаптер — YOURS, по файлу на пакет: функция пакета → Answer{Code, Value, Raw}.

Выход <out>/go: vectoradapter/ (vectoradapter.go — Answer, закрыт; заготовки — YOURS), vectortests/ (тест на строку:
Test<Пакет>_<Таблица>_Line<N>), vectorcmd/, cmd/vectors/; <out>/vectors/<пакет>/<таблица>/ — входы судьи векторов.
Судья — test_gen_vectors.py (заглушки — красное без паники; подставной адаптер по ожиданиям — зелёное; мутанты).
"""
import base64
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import common_vectors  # noqa: E402
import lesson  # noqa: E402
from gen_checks import go_str, gofmt  # noqa: E402

L = lesson.CURRENT
DEFAULT_OUT = L.out
GO_MODULE = L.go_module
SKIP = {("common/journal", "modes.tsv"): "a layout test, not a function (journal README; runner EXCLUDED_EXECUTION_TABLES)"}


class GenError(Exception):
    pass


def camel(name):
    return "".join(w[:1].upper() + w[1:] for w in re.split(r"[-_./]", name) if w)


def go_bytes(b):
    """Байты → строковый литерал Go: печатный ASCII как есть, прочее — \\xNN (BOM, NUL, не-UTF-8 — допустимы)."""
    out = ['"']
    for x in b:
        c = chr(x)
        if c == '"' or c == "\\":
            out.append("\\" + c)
        elif 0x20 <= x < 0x7f:
            out.append(c)
        else:
            out.append("\\x%02x" % x)
    out.append('"')
    return "".join(out)


def gstr(s):
    return go_bytes(s.encode("utf-8"))


def cell_value(c):
    """Общее правило «Vectors»: ячейка — значение JSON, если это JSON; иначе — JSON-строка (слово, hex, маркер)."""
    try:
        return json.loads(c)
    except ValueError:
        return c


# Объявление провода (черновик wire.tsv). surface: vectors | stand:<ключ>; inputs — колонки cells (vectors) или
# колонка/правило входа стенда; expect(row) → (код, значение | None, сырые байты | None); compare: value | raw |
# layer1 | sets; fn — функция адаптера пакета; args — вид её аргументов.
WIRE = {
    "02-installer": [
        {"package": "02-installer/canonical", "table": "cases.tsv", "surface": "stand:canonical", "fn": "Canonical",
         "args": "source", "input": "input", "compare": "raw",
         "expect": lambda r, d: (0, None, (d / r["expect"]).read_bytes()),
         "doc": "the canonical projection (P/02.2 Н1.1) of the manifest file: the JCS bytes of the projection — stdout is "
                "compared with expect/<case>.json byte for byte (no LF)"},
        {"package": "02-installer/exec", "table": "cases.tsv", "surface": "stand:exec", "fn": "Exec", "args": "input",
         "input": "exec", "compare": "value",
         "expect": lambda r, d: (0, {"result": "refused"} if r["expect"] == "@refuse"
                                 else {"result": "ok", "argv": json.loads(r["expect"])}, None),
         "doc": "the parsing of worker.exec (the bytes of a JSON string): {\"result\":\"ok\",\"argv\":[…]} or "
                "{\"result\":\"refused\"}; stdout — one object and one LF"},
        {"package": "02-installer/install-order", "table": "cases.tsv", "surface": "stand:install-order",
         "fn": "InstallOrder", "args": "input", "input": "input", "compare": "value",
         "expect": lambda r, d: (0, {"result": "refused"} if r["expect"] == "@exit 2"
                                 else {"result": "ok", "order": json.loads(r["expect"])}, None),
         "doc": "the initial installation order (P/02.4 Н1.7 order) of {manifests, installed}: {\"result\":\"ok\","
                "\"order\":[…]} or {\"result\":\"refused\"} (code 0)"},
        {"package": "02-installer/workers-script", "table": "cases.tsv", "surface": "stand:workers-script",
         "fn": "WorkersScript", "args": "input", "input": "input", "compare": "value",
         "expect": lambda r, d: (0, json.loads(r["expect"]), None),
         "doc": "the decisions of the workers script (P/02.4 Н1.5) for the input: {start:[…], stop:[…]}"},
        {"package": "02-installer/platform-lists", "table": "cases.tsv", "surface": "stand:platform-lists",
         "fn": "PlatformLists", "args": "none", "header": None, "fields": ["list", "word"], "compare": "sets",
         "doc": "the closed lists of the platform (P/02.5 Н1.3, Н1.4): Value — map[string][]string, list → its words "
                "(compared as sets); the unified command answers one list per call (cells {list}), the stand — all five"},
        {"package": "02-installer/platform-lists", "table": "cases.tsv", "surface": "vectors", "fn": "PlatformLists",
         "args": "none", "header": None, "fields": ["list", "word"], "inputs": ["list"], "per_list": True,
         "compare": "sets"},                  # канон (решение «Архитектора»): вызов на список, cells {list} → массив
        {"package": "common/env-file", "table": "cases.tsv", "surface": "stand:env-line", "fn": "EnvLine",
         "args": "input", "input": "line", "compare": "value",
         "expect": lambda r, d: (0, cell_value(r["expect"]), None),
         "doc": "a line of an environment file (the bytes of a JSON string): [\"K\",\"V\"], \"skip\" or \"bad\""},
        {"package": "common/env-file", "table": "files.tsv", "surface": "vectors", "fn": "EnvFile", "args": "cells",
         "inputs": ["input"], "compare": "value",
         "expect": lambda r, d: (2, None, None) if r["expect"] == "@exit 2" else (0, json.loads(r["expect"]), None),
         "doc": "the environment after the reading pass of the files (files.tsv input {route?, command_role?, unit, "
                "files}): an object of strings, or code 2 — a refusal to start"},
        {"package": "common/domain-backup-key", "table": "cases.tsv", "surface": "vectors", "fn": "DomainBackupKey",
         "args": "cells", "inputs": ["root_key", "backup_key_rev"], "compare": "value",
         "expect": lambda r, d: (0, r["expect"], None),
         "doc": "the domain backup copy key (HMAC-SHA256 of root_key and backup_key_rev): \"<64 hex>\" or \"@refuse\""},
        {"package": "common/domain-founding", "table": "book-seal.tsv", "surface": "vectors", "fn": "DomainFounding",
         "args": "cells", "inputs": ["seed_secret"], "compare": "value",
         "expect": lambda r, d: (0, r["expect"], None),
         "doc": "book-seal.tsv: the hex of book_seal of seed_secret; recovery.tsv: {domain, root_pub, fingerprint} or "
                "\"@refuse\" (the table name tells which)"},
        {"package": "common/domain-founding", "table": "recovery.tsv", "surface": "vectors", "fn": "DomainFounding",
         "args": "cells", "inputs": ["input"], "compare": "value",
         "expect": lambda r, d: (0, cell_value(r["expect"]), None)},
        {"package": "common/loopback", "table": "cases.tsv", "surface": "vectors", "fn": "Loopback", "args": "cells",
         "inputs": ["input"], "compare": "value",
         "expect": lambda r, d: (2, None, None) if r["expect"] == "@exit 2" else (0, json.loads(r["expect"]), None),
         "doc": "the kind of an address of the own cluster: \"loopback\", \"ip\" or \"name\"; code 2 — not an address"},
        {"package": "common/sealing", "table": "aad.tsv", "surface": "vectors", "fn": "Sealing", "args": "cells",
         "inputs": ["row_key", "path"], "compare": "value",
         "expect": lambda r, d: (0, {"pointer": r["pointer"], "aad_hex": r["aad_hex"]}, None),
         "doc": "the sealing contract by table: aad.tsv → {pointer, aad_hex}; envelope.tsv → the envelope string; open.tsv, "
                "reseal.tsv, ring.tsv → the word or value of expect"},
        {"package": "common/sealing", "table": "envelope.tsv", "surface": "vectors", "fn": "Sealing", "args": "cells",
         "inputs": ["key_hex", "kid", "nonce_b64url", "row_key", "pointer", "plaintext"], "compare": "value",
         "expect": lambda r, d: (0, r["envelope"], None)},
        {"package": "common/sealing", "table": "open.tsv", "surface": "vectors", "fn": "Sealing", "args": "cells",
         "inputs": ["key_hex", "envelope", "row_key", "pointer"], "compare": "value",
         "expect": lambda r, d: (0, "sealed" if r["expect"] == "sealed" else cell_value(r["expect"]), None)},
        {"package": "common/sealing", "table": "reseal.tsv", "surface": "vectors", "fn": "Sealing", "args": "cells",
         "inputs": ["input"], "compare": "value",
         "expect": lambda r, d: (0, cell_value(r["expect"]), None)},
        {"package": "common/sealing", "table": "ring.tsv", "surface": "vectors", "fn": "Sealing", "args": "cells",
         "inputs": ["file"], "extra_cells": lambda r: {"rotate": "true"} if r["case"].startswith("rotate") else {},
         "compare": "value", "expect": lambda r, d: (0, r["expect"], None)},
        {"package": "common/yaml-suite", "table": "expect.tsv", "surface": "vectors", "fn": "YamlSuite", "args": "cells",
         "case": "id", "inputs": ["id"], "files": {"in.yaml": "inputs/{id}.yaml"}, "compare": "layer1",
         "expect": lambda r, d: (0, {"layer1": r["layer1"]}, None),
         "doc": "layer 1 of the manifest text on a yaml-test-suite input (files in.yaml): {layer1: \"ok\"|\"refused\"[, "
                "rule]} — only layer1 is compared, rule is a hint"},
    ],
}


# Черновик провода P/03, P/04 — временная проекция до формы wire.tsv (wire_p03p04.py, источники — там).
from wire_p03p04 import WIRE as _WIRE_DRAFT, SKIP_LESSON  # noqa: E402

WIRE.update(_WIRE_DRAFT)


def package_dir(root, pkg):
    owner, name = pkg.split("/", 1)
    return Path(root) / "Platform" / owner / "vectors" / name


def read_table(root, decl):
    d = package_dir(root, decl["package"])
    path = d / decl["table"]
    if not path.is_file():
        raise GenError(f"no {path.relative_to(root)}")
    rows, header = [], decl.get("header", "file")
    head = None if header is None else None
    for no, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
        if not line or line.startswith("#"):
            continue
        cells = line.split("\t")
        if header is None:
            rows.append((no, dict(zip(decl["fields"], cells))))
            continue
        if head is None:
            head = cells
            continue
        if len(cells) != len(head):
            raise GenError(f"{path.relative_to(root)}:{no}: {len(cells)} cells, header {head}")
        rows.append((no, dict(zip(head, cells))))
    if header is not None:
        need = set(decl.get("inputs", [])) | ({decl["input"]} if isinstance(decl.get("input"), str) else set())
        if head is None or need - set(head):
            raise GenError(f"{path.relative_to(root)}: columns {sorted(need - set(head or []))} not in the header")
    return d, path, rows


def plan(root=ROOT):
    """→ ([объявление], [(пакет, таблица) общих из common_vectors]) урока; пакет состава без объявления — GenError."""
    decls = WIRE.get(L.key)
    if decls is None:
        raise GenError(f"gen_vectors: no declaration for lesson {L.key}")
    declared = {(d["package"], d["table"]) for d in decls}
    stages = [ln.split("\t") for ln in (Path(root) / L.rel / "forms/stages.tsv").read_text(encoding="utf-8").split("\n")
              if ln and not ln.startswith("#")]
    own = sorted({m for r in stages[1:] for m in re.findall(r"vectors:([a-z0-9-]+)", r[4])})
    for pkg in own:
        if not any(p == f"{L.key}/{pkg}" for p, _ in declared):
            raise GenError(f"stages.tsv gate vectors:{pkg}: no declaration of its wire")
    known = common_vectors.composition(L.key, root, known_only=True)
    for line in (Path(root) / common_vectors.CONSUMERS).read_text(encoding="utf-8").split("\n")[1:]:
        cells = line.split("\t")
        if line.startswith("#") or len(cells) != 4 or cells[2] != L.key:
            continue
        pkg, table = cells[0], cells[1]
        if (pkg, table) in SKIP or (pkg, table) in SKIP_LESSON.get(L.key, {}) or (pkg, table) in declared \
                or (pkg[7:], table) in known:
            continue
        raise GenError(f"consumers.tsv: {pkg} {table} → {L.key}: no declaration of its wire")
    return decls, known


# ---------------------------------------------------------------- Go

TYPES_GO = '''// Code generated by tools/normgen/gen_vectors.py; DO NOT EDIT.

// Package vectoradapter — the adapter of the lesson to its vector tests (vectortests) and to the vector command
// (vectorcmd): Answer is the kit's type (closed); each package's function is YOURS in its own file.
package vectoradapter

// Answer — the native outcome of a vector function: Code — its exit code (0, or the published 2); Value — the JSON
// value of stdout (a map, a slice, a string…); Raw — raw stdout bytes instead of Value (the stand canonical).
type Answer struct {
	Code  int
	Value any
	Raw   []byte
}

// NotImplemented — the answer of a stub: code -1 is not an exit code, every test of the package is red.
func NotImplemented(name string) Answer { return Answer{Code: -1, Value: name + ": not implemented"} }
'''

STUB_HEAD = '''// Generated by tools/normgen/gen_vectors.py. YOURS from here: the kit puts this file once and never overwrites it.
// One package per file: replace the body with a call of your own code; keep the signature.

package vectoradapter

'''


def stub(decls_of_fn):
    d = decls_of_fn[0]
    fn = d["fn"]
    tables = ", ".join(f"{x['package']} {x['table']} ({x['surface']})" for x in decls_of_fn)
    doc = next((x["doc"] for x in decls_of_fn if "doc" in x), "")
    lines = [f"// {fn} — {tables}:", "//"] + [f"//\t{s}" for s in _wrap(doc, 108)]
    if d["args"] == "cells":
        sig = f"func {fn}(table string, cells map[string]string, files map[string][]byte) Answer"
        lines.append("// cells — the input columns of the row as written (the raw TSV cell strings); files — the fixtures.")
    elif d["args"] == "cells+variant":
        sig = f"func {fn}(table, variant string, cells map[string]string, files map[string][]byte) Answer"
        lines.append("// variant — the half of the row (write | read); cells — the input columns of that half as written.")
    elif d["args"] == "source":
        sig = f"func {fn}(source string, text []byte) Answer"
        lines.append("// source — the file name, text — its bytes; return Raw (the bytes of stdout).")
    elif d["args"] == "none":
        sig = f"func {fn}() Answer"
    else:
        sig = f"func {fn}(input []byte) Answer"
        lines.append("// input — the bytes of the {input} file of the stand command (the cell as written).")
    return STUB_HEAD + "\n".join(lines) + f"\n{sig} {{\n\treturn NotImplemented({go_str(fn)})\n}}\n"


def _wrap(text, n):
    out, cur = [], ""
    for w in text.split(" "):
        if len(cur) + len(w) + 1 > n and cur:
            out.append(cur)
            cur = ""
        cur += (" " if cur else "") + w
    return out + ([cur] if cur else [])


VECTORCMD = r'''// Code generated by tools/normgen/gen_vectors.py; DO NOT EDIT.

// Package vectorcmd — the vector command of the lesson: the unified command (`vectors {input}`: the frame {format,
// package, table, case, variant, cells, files} → {exit_code, stdout_b64, stderr_b64}, the common acceptance README
// «The unified command of a vector package») and the stand commands (`vectors stand <key> {input}`: the native code
// and stdout directly). Each package goes to its function of package vectoradapter (yours).
package vectorcmd

import (
	"bytes"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"

%(imports)s)

var _ = sha256.Sum256
var _ = hex.EncodeToString
var _ = filepath.Base

type input struct {
	Format  *int               `json:"format"`
	Package *string            `json:"package"`
	Table   *string            `json:"table"`
	Case    *string            `json:"case"`
	Variant *string            `json:"variant"`
	Cells   map[string]*string `json:"cells"`
	Files   map[string]*string `json:"files"`
}

type answer struct {
	ExitCode  int    `json:"exit_code"`
	StdoutB64 string `json:"stdout_b64"`
	StderrB64 string `json:"stderr_b64"`
}

// Main — `vectors <input.json>` (the unified command) or `vectors stand <key> <input>`; the outer exit code.
func Main(args []string, stdout, stderr io.Writer) int {
	if len(args) == 3 && args[0] == "stand" {
		return Stand(args[1], args[2], stdout, stderr)
	}
	if len(args) != 1 {
		fmt.Fprintln(stderr, "vectors: usage: vectors <input.json> | vectors stand <key> <input>")
		return 2
	}
	data, err := os.ReadFile(args[0])
	if err != nil {
		fmt.Fprintf(stderr, "vectors: %%v\n", err)
		return 2
	}
	code, out, errOut, err := Run(data)
	if err != nil {
		fmt.Fprintf(stderr, "vectors: %%s: %%v\n", args[0], err)
		return 2
	}
	enc, _ := json.Marshal(answer{code, base64.StdEncoding.EncodeToString(out), base64.StdEncoding.EncodeToString(errOut)})
	stdout.Write(append(enc, '\n'))
	return 0
}

// Stand — a stand command: the native code is the exit code, stdout — Raw or the JSON value and one LF.
func Stand(key, path string, stdout, stderr io.Writer) int {
	data, err := os.ReadFile(path)
	if err != nil {
		fmt.Fprintf(stderr, "vectors stand %%s: %%v\n", key, err)
		return 2
	}
	var a vectoradapter.Answer
	func() {
		defer func() {
			if r := recover(); r != nil {
				a = vectoradapter.Answer{Code: 1, Value: fmt.Sprintf("panic: %%v", r)}
			}
		}()
		switch key {
%(stand)s		default:
			a = vectoradapter.Answer{Code: 2, Value: "not a stand key of the kit: " + key}
		}
	}()
	if a.Code < 0 {
		fmt.Fprintf(stderr, "vectors stand %%s: %%v\n", key, a.Value)
		return 1
	}
	if a.Raw != nil {
		stdout.Write(a.Raw)
		return a.Code
	}
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(a.Value); err != nil {
		fmt.Fprintf(stderr, "vectors stand %%s: %%v\n", key, err)
		return 1
	}
	stdout.Write(buf.Bytes())
	return a.Code
}

func parse(data []byte) (*input, error) {
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.DisallowUnknownFields()
	var in input
	if err := dec.Decode(&in); err != nil {
		return nil, err
	}
	if in.Format == nil || in.Package == nil || in.Table == nil || in.Case == nil || in.Variant == nil ||
		in.Cells == nil || in.Files == nil {
		return nil, fmt.Errorf("fields format, package, table, case, variant, cells, files are required")
	}
	if *in.Format != 1 {
		return nil, fmt.Errorf("format %%d, want 1", *in.Format)
	}
	for k, v := range in.Cells {
		if v == nil {
			return nil, fmt.Errorf("cells.%%s is not a string", k)
		}
	}
	for k, v := range in.Files {
		if v == nil {
			return nil, fmt.Errorf("files.%%s is not a string", k)
		}
	}
	return &in, nil
}

func keys(m map[string]*string) string {
	ks := make([]string, 0, len(m))
	for k := range m {
		ks = append(ks, k)
	}
	sort.Strings(ks)
	return strings.Join(ks, ",")
}

// Run — one frame of the unified command: the native code, stdout, stderr; err — the frame is out of the wire.
func Run(data []byte) (code int, stdout, stderr []byte, err error) {
	in, err := parse(data)
	if err != nil {
		return 0, nil, nil, err
	}
	pkg := *in.Package + " " + *in.Table
	want := map[string][2]string{
%(want)s	}
	shape, ok := want[pkg]
	if !ok {
		return 0, nil, nil, fmt.Errorf("package %%q table %%q is not a package of this command", *in.Package, *in.Table)
	}
	if *in.Variant != "" {
		return 0, nil, nil, fmt.Errorf("variant %%q, want \"\"", *in.Variant)
	}
	if shape[0] != "*" && keys(in.Cells) != shape[0] {
		return 0, nil, nil, fmt.Errorf("cells {%%s}, want {%%s}", keys(in.Cells), shape[0])
	}
	if keys(in.Files) != shape[1] {
		return 0, nil, nil, fmt.Errorf("files {%%s}, want {%%s}", keys(in.Files), shape[1])
	}
	files := map[string][]byte{}
	for k, v := range in.Files {
		b, err := base64.StdEncoding.Strict().DecodeString(*v)
		if err != nil {
			return 0, nil, nil, fmt.Errorf("files.%%s: %%v", k, err)
		}
		files[k] = b
	}
	cellmap := map[string]string{}
	for k, v := range in.Cells {
		cellmap[k] = *v
	}
	cell := func(name string) string { return cellmap[name] }
	_ = cell
	defer func() {
		if r := recover(); r != nil {
			code, stdout, stderr, err = 1, nil, []byte(fmt.Sprintf("panic: %%v\n", r)), nil
		}
	}()
	var value any
	switch pkg {
%(cases)s	}
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(value); err != nil {
		return 1, nil, []byte(err.Error() + "\n"), nil
	}
	return 0, buf.Bytes(), nil, nil
}

// answerOf — a vectoradapter.Answer as the native outcome: -1 (a stub) — code 1 with its message on stderr.
func answerOf(a vectoradapter.Answer) (int, []byte, []byte, bool) {
	switch {
	case a.Code < 0:
		return 1, nil, []byte(fmt.Sprint(a.Value) + "\n"), true
	case a.Code != 0:
		return a.Code, nil, nil, true
	}
	return 0, nil, nil, false
}
%(extra)s'''

PER_LIST_CASE = r'''	case %(key)s:
		a := vectoradapter.%(fn)s()
		if c, o, e, done := answerOf(a); done {
			return c, o, e, nil
		}
		var lists map[string]any
		if b, err := json.Marshal(a.Value); err != nil || json.Unmarshal(b, &lists) != nil {
			return 1, nil, []byte("%(fn)s: Value is not an object of lists\n"), nil
		}
		words, ok := lists[cell("list")]
		if !ok {
			return 1, nil, []byte("%(fn)s: no list " + cell("list") + "\n"), nil
		}
		value = words
'''

UNIFIED_CASE = '''	case %(key)s:
		a := vectoradapter.%(fn)s(*in.Table, cellmap, files)
		if c, o, e, done := answerOf(a); done {
			return c, o, e, nil
		}
		value = a.Value
'''


def go_vectorcmd(decls, known):
    imports = [f'\t"{GO_MODULE}/vectoradapter"']
    fam = any(n == "family-read" for n, _ in known)
    if fam:
        imports.insert(0, f'\t"{GO_MODULE}/families"')
    want, cases, stand, variants = [], [], [], []
    for d in decls:
        if d["surface"] == "vectors":
            key = go_str(f"{d['package']} {d['table']}")
            cells = sorted(set(d["inputs"]))
            if "extra_cells" in d or "frames" in d:
                cells = ["*"]
            want.append(f"\t\t{key}: {{{go_str(','.join(cells))}, {go_str(','.join(sorted(d.get('files', {}))))}}},\n")
            if d["args"] == "cells+variant":
                variants.append(key)
                cases.append(UNIFIED_CASE.replace("(*in.Table, cellmap", "(*in.Table, *in.Variant, cellmap")
                             % {"key": key, "fn": d["fn"]})
            else:
                cases.append((PER_LIST_CASE if d.get("per_list") else UNIFIED_CASE) % {"key": key, "fn": d["fn"]})
        else:
            k = d["surface"].split(":", 1)[1]
            if d["args"] == "source":
                call = f"vectoradapter.{d['fn']}(filepath.Base(path), data)"
            elif d["args"] == "none":
                call = f"vectoradapter.{d['fn']}()"
            else:
                call = f"vectoradapter.{d['fn']}(data)"
            branch = f"\t\tcase {go_str(k)}:\n\t\t\ta = {call}\n"
            if branch not in stand:                    # таблицы одного ключа стенда (door-token verify, place)
                stand.append(branch)
    for name, table in known:
        cd = common_vectors.DECLS[name]
        key = go_str(f"common/{name} {table}")
        want.append(f"\t\t{key}: {{{go_str(','.join(sorted(cd['inputs'])))}, {go_str(','.join(sorted(cd['files'])))}}},\n")
        branch = common_vectors.VECTORCMD[name] % {"key": key}
        cases.append(branch)
    body = VECTORCMD % {"imports": "\n".join(imports) + "\n", "want": "".join(want), "cases": "".join(cases),
                        "stand": "".join(stand), "extra": common_vectors.FAMILY_READ_GO if fam else ""}
    if variants:                                       # пакеты с половинами строки (values-by-type: write | read)
        old = '\tif *in.Variant != "" {\n\t\treturn 0, nil, nil, fmt.Errorf("variant %q, want \\"\\"", *in.Variant)\n\t}\n'
        if old not in body:
            raise GenError("vectorcmd template: the variant check moved")
        allowed = "".join(f"\t\t{k}: true,\n" for k in variants)
        body = body.replace(old, "\thalves := map[string]bool{\n" + allowed + "\t}\n"
                            '\tif halves[pkg] != (*in.Variant == "write" || *in.Variant == "read") || '
                            '(!halves[pkg] && *in.Variant != "") {\n'
                            '\t\treturn 0, nil, nil, fmt.Errorf("variant %q is not a variant of %s", *in.Variant, pkg)\n\t}\n')
    return gofmt(body)


MAIN_GO = '''// Code generated by tools/normgen/gen_vectors.py; DO NOT EDIT.

// Command vectors — the vector command of the kit: `bin/vectors {input}` and `bin/vectors stand <key> {input}`.
package main

import (
	"os"

	"%s/vectorcmd"
)

func main() { os.Exit(vectorcmd.Main(os.Args[1:], os.Stdout, os.Stderr)) }
'''

TESTS_HEAD = '''// Code generated by tools/normgen/gen_vectors.py; DO NOT EDIT.
// Source %s sha256 %s.

package vectortests

import (
	"testing"

	"%s/vectoradapter"
)

var _ = vectoradapter.NotImplemented
'''

HELPERS = r'''// Code generated by tools/normgen/gen_vectors.py; DO NOT EDIT.

// Package vectortests — the vector tests of the lesson: one test per row of each table (Test<Package>_<Table>_Line<N>);
// they call only package vectoradapter (yours) and, for family-read, the kit's families through vectorcmd.
package vectortests

import (
	"encoding/json"
	"fmt"
	"reflect"
	"sort"
	"testing"

	"%(module)s/vectoradapter"
	"%(module)s/vectorcmd"
)

var _ = vectorcmd.Run

func call(f func() vectoradapter.Answer) (a vectoradapter.Answer, err error) {
	defer func() {
		if r := recover(); r != nil {
			err = fmt.Errorf("panic: %%v", r)
		}
	}()
	return f(), nil
}

func norm(v any) any {
	b, err := json.Marshal(v)
	if err != nil {
		return fmt.Sprintf("not JSON: %%v", err)
	}
	var out any
	_ = json.Unmarshal(b, &out)
	return out
}

func decoded(want string) any {
	var v any
	if err := json.Unmarshal([]byte(want), &v); err != nil {
		panic(err)
	}
	return v
}

// check — the answer against (code, JSON value | raw bytes) by the compare rule of the table.
func check(t *testing.T, where string, f func() vectoradapter.Answer, code int, want string, raw []byte, compare string) {
	t.Helper()
	a, err := call(f)
	if err != nil {
		t.Fatalf("%%s: %%v", where, err)
	}
	if a.Code < 0 {
		t.Fatalf("%%s: %%v", where, a.Value)
	}
	if a.Code != code {
		t.Fatalf("%%s: code %%d, want %%d (%%v)", where, a.Code, code, a.Value)
	}
	if code != 0 {
		return
	}
	switch compare {
	case "raw":
		if string(a.Raw) != string(raw) {
			t.Fatalf("%%s: stdout differs from the expected bytes\n got %%q\nwant %%q", where, clip(a.Raw), clip(raw))
		}
	case "layer1":
		got, _ := norm(a.Value).(map[string]any)
		if got == nil || got["layer1"] != decoded(want).(map[string]any)["layer1"] {
			t.Fatalf("%%s: %%v, want layer1 %%v", where, norm(a.Value), decoded(want))
		}
		for k := range got {
			if k != "layer1" && k != "rule" {
				t.Fatalf("%%s: an extra key %%q", where, k)
			}
		}
	case "sets":
		got, _ := norm(a.Value).(map[string]any)
		w := decoded(want).(map[string]any)
		if len(got) != len(w) {
			t.Fatalf("%%s: lists %%v, want %%v", where, keysOf(got), keysOf(w))
		}
		for k, wv := range w {
			if !sameSet(got[k], wv) {
				t.Fatalf("%%s: list %%s = %%v, want the set %%v", where, k, got[k], wv)
			}
		}
	default:
		if !reflect.DeepEqual(norm(a.Value), decoded(want)) {
			b, _ := json.Marshal(a.Value)
			t.Fatalf("%%s\n got %%s\nwant %%s", where, b, want)
		}
	}
}

func keysOf(m map[string]any) []string {
	out := []string{}
	for k := range m {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}

func sameSet(a, b any) bool {
	la, ok1 := a.([]any)
	lb, ok2 := b.([]any)
	if !ok1 || !ok2 {
		return false
	}
	seen := map[string]bool{}
	for _, x := range la {
		s, ok := x.(string)
		if !ok || seen[s] {
			return false
		}
		seen[s] = true
	}
	want := map[string]bool{}
	for _, x := range lb {
		want[x.(string)] = true
	}
	if len(want) != len(seen) {
		return false
	}
	for k := range want {
		if !seen[k] {
			return false
		}
	}
	return true
}

func clip(b []byte) string {
	if len(b) > 200 {
		return string(b[:200]) + "…"
	}
	return string(b)
}

// commonWire — one row through the kit's vector command (vectorcmd.Run): code 0, stdout — want (family-read).
func commonWire(t *testing.T, input, want string) {
	t.Helper()
	code, stdout, stderr, err := vectorcmd.Run([]byte(input))
	if err != nil {
		t.Fatalf("the input is out of the wire: %%v", err)
	}
	if code != 0 {
		t.Fatalf("code %%d, stderr %%s", code, stderr)
	}
	var v any
	if err := json.Unmarshal(stdout, &v); err != nil {
		t.Fatalf("stdout is not JSON: %%v", err)
	}
	if !reflect.DeepEqual(v, decoded(want)) {
		t.Fatalf("family-read\n got %%s\nwant %%s", stdout, want)
	}
}

// sameJSON, safe — the helpers of the common packages (crl, revoked, log-mask, store-client).
func sameJSON(t *testing.T, what string, got any, want string) {
	t.Helper()
	if !reflect.DeepEqual(norm(got), decoded(want)) {
		b, _ := json.Marshal(got)
		t.Fatalf("%%s\n got %%s\nwant %%s", what, b, want)
	}
}

func safe(f func() (any, error)) (v any, err error) {
	defer func() {
		if r := recover(); r != nil {
			v, err = nil, fmt.Errorf("panic: %%v", r)
		}
	}()
	return f()
}
'''


COMPARE_GO = r"""// Code generated by tools/normgen/gen_vectors.py; DO NOT EDIT.

// The compare rules of the package READMEs beyond value/raw/sets (the draft wire of P/03, P/04; replaced by the form
// Platform/common/vectors/wire.tsv when it is published).
package vectortests

import (
	"encoding/json"
	"reflect"
	"sort"
	"strings"
	"testing"

	"normgen/vectoradapter"
)

// checkBy — the answer against the expectation by the named rule: subset, fields:<a,b>, setarrays, events, row,
// secret, turn, vbt-write.
func checkBy(t *testing.T, where string, f func() vectoradapter.Answer, code int, want string, raw []byte, compare string) {
	t.Helper()
	a, err := call(f)
	if err != nil {
		t.Fatalf("%s: %v", where, err)
	}
	if a.Code < 0 {
		t.Fatalf("%s: %v", where, a.Value)
	}
	if a.Code != code {
		t.Fatalf("%s: code %d, want %d (%v)", where, a.Code, code, a.Value)
	}
	if code != 0 {
		return
	}
	got, w := norm(a.Value), decoded(want)
	var errs []string
	switch {
	case compare == "subset":
		subset(w, got, "$", &errs)
	case strings.HasPrefix(compare, "fields:"):
		g, _ := got.(map[string]any)
		wm, _ := w.(map[string]any)
		if g == nil {
			errs = append(errs, "$: want an object")
		}
		for _, k := range strings.Split(compare[len("fields:"):], ",") {
			if g != nil && !reflect.DeepEqual(g[k], wm[k]) {
				errs = append(errs, "$."+k+": "+show(g[k])+", want "+show(wm[k]))
			}
		}
	case compare == "setarrays":
		if !sameSetDeep(got, w) {
			errs = append(errs, "$: "+show(got)+", want (arrays as sets) "+show(w))
		}
	case compare == "events":
		events(w, got, &errs)
	case compare == "row":
		rowRule(w, got, &errs)
	case compare == "secret":
		secret(w, got, &errs)
	case compare == "turn":
		turn(w, got, &errs)
	case compare == "vbt-write":
		vbtWrite(w, got, &errs)
	default:
		errs = append(errs, "unknown compare rule "+compare)
	}
	if len(errs) > 0 {
		t.Fatalf("%s:\n  %s\n got %s", where, strings.Join(errs, "\n  "), show(got))
	}
}

func show(v any) string { b, _ := json.Marshal(v); return string(b) }

// subset — the common acceptance subset: an object by the listed keys ({} — exactly empty, "@absent" — no key), a list
// element by element, the rest by value.
func subset(exp, act any, path string, errs *[]string) {
	switch e := exp.(type) {
	case map[string]any:
		a, ok := act.(map[string]any)
		if !ok {
			*errs = append(*errs, path+": want an object, got "+show(act))
			return
		}
		if len(e) == 0 && len(a) != 0 {
			*errs = append(*errs, path+": want {} exactly, got "+show(act))
			return
		}
		for k, v := range e {
			av, has := a[k]
			if v == "@absent" {
				if has {
					*errs = append(*errs, path+"."+k+": want absent")
				}
				continue
			}
			if !has {
				*errs = append(*errs, path+"."+k+": missing")
				continue
			}
			subset(v, av, path+"."+k, errs)
		}
	case []any:
		a, ok := act.([]any)
		if !ok || len(a) != len(e) {
			*errs = append(*errs, path+": want "+show(exp)+", got "+show(act))
			return
		}
		for i := range e {
			subset(e[i], a[i], path+"["+strconvI(i)+"]", errs)
		}
	default:
		if !reflect.DeepEqual(exp, act) {
			*errs = append(*errs, path+": want "+show(exp)+", got "+show(act))
		}
	}
}

func strconvI(i int) string { b, _ := json.Marshal(i); return string(b) }

// sameSetDeep — by value, every array as a set of distinct elements.
func sameSetDeep(a, b any) bool {
	switch bv := b.(type) {
	case []any:
		av, ok := a.([]any)
		if !ok || len(av) != len(bv) {
			return false
		}
		x, y := keysSorted(av), keysSorted(bv)
		for i := range x {
			if x[i] != y[i] || (i > 0 && x[i] == x[i-1]) {
				return false
			}
		}
		return true
	case map[string]any:
		am, ok := a.(map[string]any)
		if !ok || len(am) != len(bv) {
			return false
		}
		for k, v := range bv {
			if !sameSetDeep(am[k], v) {
				return false
			}
		}
		return true
	}
	return reflect.DeepEqual(a, b)
}

func keysSorted(xs []any) []string {
	out := make([]string, len(xs))
	for i, x := range xs {
		out[i] = show(x)
	}
	sort.Strings(out)
	return out
}

// events — events-merge: the top keys but events by the subset of the object (each by its full value); events — the
// same length and order, each element by its listed fields.
func events(exp, act any, errs *[]string) {
	e, _ := exp.(map[string]any)
	a, ok := act.(map[string]any)
	if !ok {
		*errs = append(*errs, "$: want an object")
		return
	}
	for k, v := range e {
		av, has := a[k]
		switch {
		case v == "@absent":
			if has {
				*errs = append(*errs, "$."+k+": want absent")
			}
		case !has:
			*errs = append(*errs, "$."+k+": missing")
		case k == "events":
			we, _ := v.([]any)
			ae, ok := av.([]any)
			if !ok || len(ae) != len(we) {
				*errs = append(*errs, "$.events: want "+show(v)+", got "+show(av))
				continue
			}
			for i := range we {
				wo, _ := we[i].(map[string]any)
				ao, _ := ae[i].(map[string]any)
				for f, fv := range wo {
					if fv == "@absent" {
						if _, has := ao[f]; has {
							*errs = append(*errs, "$.events["+strconvI(i)+"]."+f+": want absent")
						}
					} else if !reflect.DeepEqual(ao[f], fv) {
						*errs = append(*errs, "$.events["+strconvI(i)+"]."+f+": "+show(ao[f])+", want "+show(fv))
					}
				}
			}
		default:
			if !reflect.DeepEqual(av, v) {
				*errs = append(*errs, "$."+k+": "+show(av)+", want "+show(v))
			}
		}
	}
}

// rowRule — row-check cases.tsv: result, word, field ("@absent" — no key); for ok the elements named by the column row
// ("@absent" — no key; {} — row empty; a text "[…" also by JSON value); no column row — the row is not compared.
func rowRule(exp, act any, errs *[]string) {
	e, _ := exp.(map[string]any)
	a, ok := act.(map[string]any)
	if !ok {
		*errs = append(*errs, "$: want an object")
		return
	}
	for _, k := range []string{"result", "word", "field"} {
		v, want := e[k]
		if !want {
			continue
		}
		av, has := a[k]
		if v == "@absent" {
			if has {
				*errs = append(*errs, "$."+k+": want absent")
			}
		} else if !reflect.DeepEqual(av, v) {
			*errs = append(*errs, "$."+k+": "+show(av)+", want "+show(v))
		}
	}
	wr, has := e["row"]
	if !has {
		return
	}
	ar, ok := a["row"].(map[string]any)
	if !ok {
		*errs = append(*errs, "$.row: want an object of texts, got "+show(a["row"]))
		return
	}
	wm, _ := wr.(map[string]any)
	if len(wm) == 0 && len(ar) != 0 {
		*errs = append(*errs, "$.row: want {} exactly")
	}
	for k, v := range wm {
		av, has := ar[k]
		if v == "@absent" {
			if has {
				*errs = append(*errs, "$.row."+k+": want absent")
			}
			continue
		}
		ws, _ := v.(string)
		as, isText := av.(string)
		if !has || !isText {
			*errs = append(*errs, "$.row."+k+": want the text "+show(v)+", got "+show(av))
			continue
		}
		if as == ws {
			continue
		}
		if strings.HasPrefix(ws, "[") {
			var x, y any
			if json.Unmarshal([]byte(ws), &x) == nil && json.Unmarshal([]byte(as), &y) == nil && reflect.DeepEqual(x, y) {
				continue
			}
		}
		*errs = append(*errs, "$.row."+k+": "+show(av)+", want "+show(v))
	}
}

// secret — secret-in, the refusal items: keys only fault and text; fault equals; at a non-empty fault text is present
// and carries none of the hidden password substrings (hidden), otherwise no text.
func secret(exp, act any, errs *[]string) {
	e, _ := exp.(map[string]any)
	a, ok := act.(map[string]any)
	if !ok {
		*errs = append(*errs, "$: want an object")
		return
	}
	for k := range a {
		if k != "fault" && k != "text" {
			*errs = append(*errs, "$."+k+": an extra key")
		}
	}
	if !reflect.DeepEqual(a["fault"], e["fault"]) {
		*errs = append(*errs, "$.fault: "+show(a["fault"])+", want "+show(e["fault"]))
	}
	text, has := a["text"].(string)
	if e["fault"] == "" {
		if _, present := a["text"]; present {
			*errs = append(*errs, "$.text: want absent at an empty fault")
		}
		return
	}
	if !has {
		*errs = append(*errs, "$.text: missing at a refusal")
		return
	}
	hidden, _ := e["hidden"].([]any)
	for _, h := range hidden {
		if hs, _ := h.(string); hs != "" && strings.Contains(text, hs) {
			*errs = append(*errs, "$.text repeats a hidden value of the row")
		}
	}
}

// turn — turn cases.tsv: actions one per event; write.holder "@new" — a new non-empty mark never seen before, "@same" —
// the current mark; then by value.
func turn(exp, act any, errs *[]string) {
	we, _ := exp.([]any)
	ae, ok := act.([]any)
	if !ok || len(ae) != len(we) {
		*errs = append(*errs, "$: want "+show(exp)+", got "+show(act))
		return
	}
	seen, current := map[string]bool{}, ""
	for i := range we {
		w := we[i]
		if wo, ok := w.(map[string]any); ok {
			if ww, ok := wo["write"].(map[string]any); ok {
				ao, _ := ae[i].(map[string]any)
				aw, _ := ao["write"].(map[string]any)
				got, _ := aw["holder"].(string)
				switch ww["holder"] {
				case "@new":
					if got == "" || seen[got] {
						*errs = append(*errs, "$["+strconvI(i)+"].write.holder: want a new mark, got "+show(aw["holder"]))
						return
					}
					seen[got], current = true, got
				case "@same":
					if current == "" && got != "" {
						seen[got], current = true, got
					}
					if got != current {
						*errs = append(*errs, "$["+strconvI(i)+"].write.holder: want the current mark "+show(current))
						return
					}
				}
				cp := map[string]any{}
				for k, v := range wo {
					cp[k] = v
				}
				cw := map[string]any{}
				for k, v := range ww {
					cw[k] = v
				}
				if ww["holder"] == "@new" || ww["holder"] == "@same" {
					cw["holder"] = got
				}
				cp["write"] = cw
				w = cp
			}
		}
		if !reflect.DeepEqual(ae[i], w) {
			*errs = append(*errs, "$["+strconvI(i)+"]: "+show(ae[i])+", want "+show(w))
		}
	}
}

// vbtWrite — values-by-type, the write half: ok with row — exactly {status, row}, the text byte for byte; ok with
// rowjson — row begins with [ and equals it by value; absent — exactly {status: absent}; refused — fault only if named.
func vbtWrite(exp, act any, errs *[]string) {
	e, _ := exp.(map[string]any)
	a, ok := act.(map[string]any)
	if !ok {
		*errs = append(*errs, "$: want an object")
		return
	}
	switch {
	case e["status"] == "ok" && e["rowjson"] != nil:
		r, _ := a["row"].(string)
		var v any
		if a["status"] != "ok" || len(a) != 2 || !strings.HasPrefix(r, "[") || json.Unmarshal([]byte(r), &v) != nil ||
			!reflect.DeepEqual(v, e["rowjson"]) {
			*errs = append(*errs, "$: want {status: ok, row: [the JSON "+show(e["rowjson"])+"]}")
		}
	case e["status"] == "refused":
		if a["status"] != "refused" {
			*errs = append(*errs, "$.status: want refused")
		}
		for k := range a {
			if k != "status" && k != "fault" {
				*errs = append(*errs, "$."+k+": an extra key")
			}
		}
		if f, named := e["fault"]; named && !reflect.DeepEqual(a["fault"], f) {
			*errs = append(*errs, "$.fault: "+show(a["fault"])+", want "+show(f))
		}
	default:
		if !reflect.DeepEqual(act, exp) {
			*errs = append(*errs, "$: want "+show(exp))
		}
	}
}
"""


BASE_COMPARES = ("raw", "layer1", "sets", "value")


def frames_of(d, rows, pdir):
    """[(строка, cells, variant, cells кадра | None, (код, значение, сырые байты))]; frames — половины строки."""
    out = []
    if d["compare"] == "sets":
        return out
    for no, r in rows:
        if "frames" in d:
            for variant, cells, exp, compare in d["frames"](r):
                out.append((no, r, variant, cells, exp, compare))
        else:
            out.append((no, r, "", None, d["expect"](r, pdir), None))
    return out


def fixture(root, pdir, spec, r):
    """Фикстура: путь от каталога пакета или «@root/<путь от корня курса>»."""
    if spec.startswith("@root/"):
        return (Path(root) / spec[len("@root/"):]).read_bytes()
    return (pdir / spec.format(**r)).read_bytes()


def lesson_consumers(root):
    out = set()
    for line in (Path(root) / common_vectors.CONSUMERS).read_text(encoding="utf-8").split("\n")[1:]:
        cells = line.split("\t")
        if not line.startswith("#") and len(cells) == 4 and cells[2] == L.key:
            out.add((cells[0], cells[1]))
    return out


def build(root=ROOT):
    """→ ({путь от out: байты}, опись [(пакет таблица строка, статус)])."""
    import hashlib
    decls, known = plan(root)
    files, inv = {}, []
    uses_extra = False
    runs = set()
    by_fn = {}
    for d in decls:
        by_fn.setdefault(d["fn"], []).append(d)
    files["go/vectoradapter/vectoradapter.go"] = gofmt(TYPES_GO).encode("utf-8")
    for fn, ds in by_fn.items():
        files[f"go/vectoradapter/{fn.lower()}.go"] = gofmt(stub(ds)).encode("utf-8")
    for fname, text in common_vectors.adapters(L.key, known_only=True).items():
        files[f"go/vectoradapter/{fname}"] = gofmt(text).encode("utf-8")
    files["go/vectorcmd/vectorcmd.go"] = go_vectorcmd(decls, known).encode("utf-8")
    files["go/cmd/vectors/main.go"] = gofmt(MAIN_GO % GO_MODULE).encode("utf-8")
    files["go/vectortests/helpers_test.go"] = gofmt(HELPERS % {"module": GO_MODULE}).encode("utf-8")
    for d in decls:
        if d.get("per_list"):
            inv.append((f"{d['package']} {d['table']} (vectors, per list)", "translated"))
            continue                                  # функция та же — её судит тест множеств stand-объявления
        pdir, path, rows = read_table(root, d)
        if "select" in d:                             # выбор строк потребителя (README «Who performs it»)
            kept_rows = []
            for no, r in rows:
                why = d["select"](r)
                if why is True:
                    kept_rows.append((no, r))
                else:
                    inv.append((f"{d['package']} {d['table']} {no}", "excluded: " + why))
            rows = kept_rows
        rel = str(path.relative_to(root))
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        name = camel(d["package"].split("/", 1)[1]) + "_" + camel(d["table"].rsplit(".", 1)[0])
        out = [TESTS_HEAD % (rel, sha, GO_MODULE)]
        wire_rows = []
        if d["compare"] == "sets":
            lists = {}
            for no, r in rows:
                lists.setdefault(r["list"], []).append(r["word"])
            want = json.dumps(lists, ensure_ascii=False, sort_keys=True)
            out.append(f"\n// {rel}: one call, the lists as sets.\nfunc Test{name}_Lists(t *testing.T) {{\n"
                       f"\tcheck(t, {go_str(rel)}, func() vectoradapter.Answer {{ return vectoradapter.{d['fn']}() }}, 0, "
                       f"{go_str(want)}, nil, \"sets\")\n}}\n")
            inv.append((f"{d['package']} {d['table']} *", "translated"))
        for no, r, variant, frame_cells, (code, value, raw), frame_compare in frames_of(d, rows, pdir):
            compare = frame_compare or d["compare"]
            suffix = camel(variant) if variant else ""
            want = json.dumps(value, ensure_ascii=False) if value is not None else "null"
            if d["surface"] == "vectors":
                cells = frame_cells if frame_cells is not None else {c: r[c] for c in d["inputs"]}
                cells.update(d.get("extra_cells", lambda _: {})(r))
                fx = {k: fixture(root, pdir, v, r) for k, v in d.get("files", {}).items()}
                go_cells = "map[string]string{" + ", ".join(f"{go_str(k)}: {gstr(v)}" for k, v in cells.items()) + "}"
                go_files = "map[string][]byte{" + ", ".join(f"{go_str(k)}: []byte({go_bytes(v)})"
                                                             for k, v in fx.items()) + "}"
                if d["args"] == "cells+variant":
                    f = (f"func() vectoradapter.Answer {{ return vectoradapter.{d['fn']}({go_str(d['table'])}, "
                         f"{go_str(variant)}, {go_cells}, {go_files}) }}")
                else:
                    f = f"func() vectoradapter.Answer {{ return vectoradapter.{d['fn']}({go_str(d['table'])}, {go_cells}, {go_files}) }}"
                case = r.get(d.get("case", "case"), f"line-{no}")
                run = (d["package"], d["table"], d["surface"], variant, case)
                if run in runs:                            # запуск уникален (wire grammar spec103): дубль — ошибка
                    raise GenError(f"{d['package']} {d['table']}: the run {variant or '-'} {case} repeats (line {no})")
                runs.add(run)
                wire_rows.append((no, case, cells, fx, code, value, variant))
            elif d["args"] == "source":
                src = Path(root) / r[d["input"]]
                f = (f"func() vectoradapter.Answer {{ return vectoradapter.{d['fn']}({go_str(src.name)}, "
                     f"[]byte({go_bytes(src.read_bytes())})) }}")
            else:
                data = d["input"](r) if callable(d["input"]) else r[d["input"]].encode("utf-8")
                f = f"func() vectoradapter.Answer {{ return vectoradapter.{d['fn']}([]byte({go_bytes(data)})) }}"
            go_raw = "nil" if raw is None else f"[]byte({go_bytes(raw)})"
            fn_check = "check" if compare in BASE_COMPARES else "checkBy"
            uses_extra = uses_extra or fn_check == "checkBy"
            out.append(f"\n// {rel}:{no} {r.get('case', r.get('id', ''))}{(' ' + variant) if variant else ''}\n"
                       f"func Test{name}_Line{no}{suffix}(t *testing.T) {{\n"
                       f"\t{fn_check}(t, {go_str(f'{rel}:{no}' + ((' ' + variant) if variant else ''))}, {f}, {code}, "
                       f"{gstr(want)}, {go_raw}, {go_str(compare)})\n}}\n")
            inv.append((f"{d['package']} {d['table']} {no}{(' ' + variant) if variant else ''}", "translated"))
        files[f"go/vectortests/{name.lower()}_test.go"] = gofmt("".join(out)).encode("utf-8")
        for no, case, cells, fx, code, value, variant in wire_rows:
            doc = {"format": 1, "package": d["package"], "table": d["table"], "case": case, "variant": variant,
                   "cells": cells, "files": {k: base64.b64encode(v).decode("ascii") for k, v in fx.items()}}
            files[f"vectors/{d['package']}/{d['table'][:-4]}/line-{no}{('-' + variant) if variant else ''}.json"] = (
                json.dumps(doc, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
        if wire_rows:
            lines = [f"# Inputs of the vector command for {d['package']} {d['table']} (gen_vectors.py); compare {d['compare']}.",
                     f"# source {rel} sha256 {sha}", "case\tinput\texit\tstdout"]
            for no, case, cells, fx, code, value, variant in wire_rows:
                v = ("-" + variant) if variant else ""
                lines.append(f"line-{no}{v}\tline-{no}{v}.json\t{code}\t"
                             + (json.dumps(value, ensure_ascii=False, separators=(",", ":")) if code == 0 else ""))
            files[f"vectors/{d['package']}/{d['table'][:-4]}/cases.tsv"] = ("\n".join(lines) + "\n").encode("utf-8")

    def head(*rels):
        return "// Code generated by tools/normgen/gen_vectors.py (common packages); DO NOT EDIT.\n" + "".join(
            f"// Source {r} sha256 {hashlib.sha256((Path(root) / r).read_bytes()).hexdigest()}.\n" for r in rels if r)
    for fname, text in common_vectors.go_tests(L.key, root, go_str, head, GO_MODULE, known_only=True).items():
        if fname == "common_test.go":
            continue                                   # помощники — в helpers_test.go
        files[f"go/vectortests/{fname}"] = gofmt(text).encode("utf-8")
        inv.append((fname, "translated"))
    if uses_extra:
        files["go/vectortests/compare_test.go"] = gofmt(COMPARE_GO.replace('"normgen/vectoradapter"',
                                                                            f'"{GO_MODULE}/vectoradapter"')).encode("utf-8")
    for pkg, table in SKIP:
        if (pkg, table) in lesson_consumers(root):
            inv.append((f"{pkg} {table}", "excluded: " + SKIP[pkg, table]))
    for (pkg, table), why in SKIP_LESSON.get(L.key, {}).items():
        inv.append((f"{pkg} {table}", "excluded: " + why))
    files["go/vectortests/inventory.tsv"] = ("\n".join(["# The vector tables of the lesson (gen_vectors.py).",
                                                        "table\tstatus"] + ["\t".join(x) for x in inv]) + "\n").encode()
    return files, inv


def generate(root=ROOT, out=DEFAULT_OUT):
    files, inv = build(root)
    out = Path(out)
    for sub in ("go/vectortests", "go/vectorcmd", "go/cmd/vectors", "vectors"):
        t = out / sub
        if t.exists():
            for p in sorted(t.rglob("*"), reverse=True):
                p.unlink() if p.is_file() else p.rmdir()
    for rel, data in files.items():
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_bytes(data)
    mod = out / "go/go.mod"
    if not mod.exists():
        mod.write_text(f"module {GO_MODULE}\n\ngo 1.22\n", encoding="utf-8")
    return out, inv


KIT_DIRS = ("vectortests", "vectorcmd", "../cmd/vectors")
JUDGE = HERE / "test_gen_vectors.py"


def kit_files(module, out=DEFAULT_OUT):
    fresh, _ = build(ROOT)
    res = []
    for rel, data in sorted(fresh.items()):
        if not rel.startswith("go/"):
            continue
        kept = Path(out) / rel
        if not kept.is_file() or kept.read_bytes() != data:
            raise GenError(f"{kept} is stale: run tools/normgen/gen_vectors.py --lesson {L.key}")
        data = data.replace(f'"{GO_MODULE}/'.encode(), f'"{module}/internal/'.encode())
        sub, name = rel[3:].rsplit("/", 1)
        sub = "../cmd/vectors" if sub == "cmd/vectors" else sub
        own = sub == "vectoradapter" and name != "vectoradapter.go"
        res.append((sub, name, data, "generated", str(kept.relative_to(ROOT)), own))
    return res


def provenance():
    import hashlib

    def entry(path):
        return {"path": str(Path(path).relative_to(ROOT)), "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}
    decls, known = plan(ROOT)
    forms = sorted({read_table(ROOT, d)[1] for d in decls}) + [ROOT / common_vectors.CONSUMERS]
    return {"form": [entry(f) for f in forms], "generator": entry(Path(__file__).resolve()), "handwritten": [],
            "judge": entry(JUDGE)}


KIT_MD = """
## Part `vectors`: the vector tests and the vector command of the lesson (generated)

| Package | Import path | Origin |
|---|---|---|
| `vectoradapter` | `{module}/internal/vectoradapter` | `vectoradapter.go` — `Answer` (closed); one file per package — **yours** |
| `vectortests` | `{module}/internal/vectortests` | generated: one test per row of each table (`inventory.tsv`) |
| `vectorcmd`, `cmd/vectors` | `{module}/internal/vectorcmd`, `{module}/cmd/vectors` | generated: the vector command |

Build `go build -o bin/vectors ./cmd/vectors`. The profile maps each package of the lesson:
`vectors: <package>: 'bin/vectors {input}'` (the unified command: domain-backup-key, domain-founding, env-file,
loopback, sealing, yaml-suite, crl, revoked, log-mask, store-client, family-read) and the stand keys
`stand: <key>: 'bin/vectors stand <key> {input}'` (canonical, exec, install-order, workers-script, platform-lists,
env-line). Each package's function returns `Answer{Code, Value, Raw}`: `Code` 0 (or the published 2), `Value` — the
JSON value of stdout, `Raw` — the raw stdout bytes (canonical). The stubs answer code -1 «not implemented».
`common/family-read` needs none of your code (the kit's `families`). `journal/modes.tsv` is a layout test — not here.
"""


KIT_MD_P02 = KIT_MD


def lesson_kit_md():
    """Справка части урока: у P/02 — прежний текст; у прочих — пакеты единой команды и ключи стенда из объявлений."""
    if L.key == "02-installer" or L.key not in WIRE:
        return KIT_MD_P02
    decls, known = plan(ROOT)
    unified = sorted({d["package"] for d in decls if d["surface"] == "vectors"} | {f"common/{n}" for n, _ in known})
    stands = sorted({d["surface"].split(":", 1)[1] for d in decls if d["surface"] != "vectors"})
    head = KIT_MD_P02.split("Build `go build")[0]
    return head + (
        "Build `go build -o bin/vectors ./cmd/vectors`. The profile maps each package of the lesson:\n"
        "`vectors: <package>: 'bin/vectors {input}'` (the unified command: " + ", ".join(unified) + ") and the stand keys\n"
        "`stand: <key>: 'bin/vectors stand <key> {input}'` (" + ", ".join(stands) + "). Each package's function returns\n"
        "`Answer{Code, Value, Raw}`: `Code` 0 (or the published 2), `Value` — the JSON value of stdout, `Raw` — raw stdout\n"
        "bytes (creates-key, near-of). The stubs answer code -1 «not implemented». `common/family-read` needs none of your\n"
        "code (the kit's `families`). The rows a consumer does not perform (README «Who performs it») and the tables the\n"
        "lesson does not run are in `vectortests/inventory.tsv` as excluded, with the reason. The wire of this lesson is a\n"
        "draft (tools/normgen/wire_p03p04.py) until the form Platform/common/vectors/wire.tsv is published.\n")


KIT_MD = lesson_kit_md()


def main(argv):
    out = Path(argv[1]) if len(argv) > 1 else DEFAULT_OUT
    try:
        _, inv = generate(ROOT, out)
    except (GenError, common_vectors.CommonError) as exc:
        print(f"gen_vectors: {exc}", file=sys.stderr)
        return 1
    print(f"gen_vectors: {L.code} {sum(1 for _, s in inv if s == 'translated')} translated, "
          f"{sum(1 for _, s in inv if s != 'translated')} excluded")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
