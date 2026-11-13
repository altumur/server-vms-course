"""Generate lesson vectors and unified-command inputs (ADR-0125 addendum(5), item 5).

  python3 tools/normgen/gen_vectors.py --lesson 02-installer [<out>]
The roster combines local stages.kit.tsv vectors gates with common consumers.tsv packages. P/02 and P/06 use wire.tsv via wire.py for inputs, fixtures, expectations and comparisons; wire_vectors/wire_api_p06 declare Go signatures. Validate complete native responses, then compare/assert rules. Other lessons use wire_draft. journal/modes.tsv describes layout only.

The unified bin/vectors {input} command maps {format, package, table, case, variant, cells, files} frames to {exit_code, stdout_b64, stderr_b64}. Stand commands bin/vectors stand <key> {input} use native exits and single-line JSON+LF or raw stdout. One YOURS adapter file per package returns Answer{Code, Value, Raw}. Emit vectoradapter types/scaffolds, vectortests, vectorcmd, cmd/vectors and vectors/<package>/<table> judge inputs. test_gen_vectors.py checks default failures without panic, passing fixture adapters and mutants."""
import base64
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import common_vectors  # noqa: E402
import gate  # noqa: E402
import vector_consumers  # noqa: E402
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
    """Encode bytes as a Go string literal: printable ASCII unchanged, everything else as \\xNN, including BOM, NUL and invalid UTF-8."""
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
    """Apply the Vectors rule: a cell is its JSON value if valid JSON, otherwise a JSON string (word, hex, marker)."""
    try:
        return json.loads(c)
    except ValueError:
        return c


# Other lessons retain the agreed wire_draft.py projection until the complete form exists.
WIRE = {}


# P/03, P/04 temporary wire projection before wire.tsv; wire_draft.py records its sources.
from wire_draft import WIRE as _WIRE_DRAFT, SKIP_LESSON  # noqa: E402

WIRE.update(_WIRE_DRAFT)


def package_dir(root, pkg):
    owner, name = pkg.split("/", 1)
    return Path(root) / "Platform" / owner / "vectors" / name


def read_table(root, decl):
    if decl.get("_form"):
        b = decl["_runs"][0].binding if decl["_runs"] else decl["_excluded"][0].binding
        import wire
        return wire.package_dir(root, b.package), wire.package_dir(root, b.package) / b.table, wire.read_rows(root, b)
    d = package_dir(root, decl["package"])
    path = d / decl["table"]
    if not path.is_file():
        raise GenError(f"no {path.relative_to(root)}")
    import tsv_input
    header = decl.get("header", "file")
    try:
        table = tsv_input.read(path, root=root, positional=header is None,
                               names=decl["fields"] if header is None else None)
    except tsv_input.TSVError as exc:
        raise GenError(str(exc)) from None
    if header is not None:
        need = set(decl.get("inputs", [])) | ({decl["input"]} if isinstance(decl.get("input"), str) else set())
        if need - set(table.columns):
            raise GenError(f"{path.relative_to(root)}: columns {sorted(need - set(table.columns))} not in the header")
    return d, path, table.rows


def plan(root=ROOT):
    """Return (declarations, common package/table pairs); roster packages without declarations raise GenError."""
    if L.key == "06-console":
        import wire_api_p06
        try:
            return wire_api_p06.declarations(root), common_vectors.composition(L.key, root, known_only=True)
        except wire_api_p06.WireError as exc:
            raise GenError(str(exc)) from None
    if L.key == "02-installer":
        import wire_vectors
        try:
            return wire_vectors.declarations(root), common_vectors.composition(L.key, root, known_only=True)
        except wire_vectors.wire.WireError as exc:
            raise GenError(str(exc)) from None
    decls = WIRE.get(L.key)
    if decls is None:
        raise GenError(f"gen_vectors: no declaration for lesson {L.key}")
    import consumer_vectors
    try:
        decls = list(decls) + consumer_vectors.declarations(root, sys.modules[__name__])
    except consumer_vectors.wire.WireError as exc:
        raise GenError(str(exc)) from None
    declared = {(d["package"], d["table"]) for d in decls}
    stages_path = Path(root) / L.rel / "forms/stages.kit.tsv"
    stages = [ln.split("\t") for ln in stages_path.read_text(encoding="utf-8").split("\n")
              if ln and not ln.startswith("#")] if stages_path.is_file() else [[]]   # Historical P/06 sources before forms have no stages.
    known = common_vectors.composition(L.key, root, known_only=True)
    available = {p for p, _ in declared} | {f"common/{p}" for p, _ in known}
    try:
        packages = {p for row in stages[1:]
                    for p in gate.vector_packages(row[stages[0].index("gate")], L.key)}
    except gate.GateError as exc:
        raise GenError(f"stages.kit.tsv: {exc}") from None
    for pkg in sorted(packages):
        if pkg not in available:
            raise GenError(f"stages.kit.tsv gate vectors:{pkg}: no declaration of its wire")
    for pkg, table in lesson_consumers(root):
        if (pkg, table) in SKIP or (pkg, table) in SKIP_LESSON.get(L.key, {}) or (pkg, table) in declared \
                or (pkg.startswith("common/") and (pkg[len("common/"):], table) in known):
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


FULL_STAND = r'''// Stand runs the native stand command; StandResult preserves execution errors for the generated judge.
func Stand(key, path string, stdout, stderr io.Writer) int {
    code, out, errout, err := StandResult(key, path)
    if err != nil { fmt.Fprintln(stderr, err); return 1 }
    stdout.Write(out); stderr.Write(errout); return code
}
func StandResult(key, path string) (code int, stdout, stderr []byte, err error) {
    data, err := os.ReadFile(path)
    if err != nil { return 0,nil,nil,err }
    _ = data
    defer func() { if r:=recover();r!=nil { code,stdout,stderr,err=0,nil,nil,fmt.Errorf("panic: %v",r) } }()
    var a vectoradapter.Answer
    rawFrame := false
    switch key {
{{STAND}}    default: return 0,nil,nil,fmt.Errorf("not a stand key of this lesson: %s",key)
    }
    return wireAnswer(a,rawFrame)
}
func wireAnswer(a vectoradapter.Answer, rawFrame bool) (int,[]byte,[]byte,error) {
    if a.Code < 0 || a.Code > 255 { return 0,nil,nil,fmt.Errorf("adapter did not execute: %v (code %d)",a.Value,a.Code) }
    if a.Raw != nil { return a.Code,a.Raw,nil,nil }
    if rawFrame { return 0,nil,nil,fmt.Errorf("raw native frame requires Answer.Raw") }
    var buf bytes.Buffer
    enc:=json.NewEncoder(&buf);enc.SetEscapeHTML(false)
    if err:=enc.Encode(a.Value);err!=nil { return 0,nil,nil,err }
    return a.Code,buf.Bytes(),nil,nil
}

'''


def _go_vectorcmd_full(decls, known, bindings):
    """The explicit full-wire mode; it does not change the published P/02 template."""
    if bindings is None:
        raise GenError("full wire dispatch requires bindings")
    imports = [f'\t"{GO_MODULE}/vectoradapter"']
    fam = any(n == "family-read" for n, _ in known)
    if fam:
        imports.insert(0, f'\t"{GO_MODULE}/families"')
    want, cases, stands, shapes = [], [], [], []

    def add_shape(package, table, variant, cells, files):
        key = go_str(package + " " + table + "\x00" + variant)
        # Multiple shapes of a variant are alternatives, not multiple Go map entries.
        shapes.append((key, f"{{{go_str(cells)}, {go_str(files)}}}"))

    for d in decls:
        native = d.get("native", {})
        frames = {n.get("frame") for n in (native if isinstance(native, list) else [native])}
        raw_frame = "true" if frames == {"raw"} else "false"
        fn, args = d["fn"], d["args"]
        if d["surface"] == "vectors":
            key = go_str(f"{d['package']} {d['table']}")
            want.append(f'\t\t{key}: {{"*", "*"}},\n')
            if "wire_shapes" not in d:
                raise GenError(f"{d['package']} {d['table']}: no declared full-wire input shapes")
            for variant, alternatives in d["wire_shapes"].items():
                for cells, files in alternatives:
                    add_shape(d["package"], d["table"], variant, cells, files)
            prefix = ""
            if args == "cells":
                call = f"vectoradapter.{fn}(*in.Table,cellmap,files)"
            elif args == "cells+variant":
                call = f"vectoradapter.{fn}(*in.Table,*in.Variant,cellmap,files)"
            elif args == "input":
                prefix = '\t\tvar text string\n\t\tfor _, v := range cellmap { text=v }\n'
                call = f"vectoradapter.{fn}([]byte(text))"
            elif args == "none":
                call = f"vectoradapter.{fn}()"
            else:
                raise GenError(f"{d['package']}: Go API {args} cannot read vector cells")
            branch = f"\tcase {key}:\n{prefix}\t\ta := {call}\n"
            if d.get("per_list"):
                branch += ('\t\tif a.Code==0 {\n\t\t\tb,err:=json.Marshal(a.Value);if err!=nil {return 0,nil,nil,err}\n'
                           '\t\t\tvar all map[string]any;if err=json.Unmarshal(b,&all);err!=nil{return 0,nil,nil,err}\n'
                           '\t\t\twords,ok:=all[cell("list")];if !ok{return 0,nil,nil,fmt.Errorf("missing list")}\n'
                           '\t\t\ta.Value=words\n\t\t}\n')
            cases.append(branch + f"\t\treturn wireAnswer(a,{raw_frame})\n")
        else:
            key = d["surface"].split(":",1)[1]
            if args == "source":
                call=f"vectoradapter.{fn}(filepath.Base(path),data)"
            elif args == "input":
                call=f"vectoradapter.{fn}(data)"
            elif args == "none":
                call=f"vectoradapter.{fn}()"
            else:
                raise GenError(f"{d['package']}: Go API {args} cannot read a stand argument")
            branch=f"\tcase {go_str(key)}:\n\t\ta={call}\n\t\trawFrame={raw_frame}\n"
            if branch not in stands:
                stands.append(branch)
    for name, table in known:
        cd = common_vectors.DECLS[name]
        package = f"common/{name}"
        key = go_str(f"{package} {table}")
        want.append(f'\t\t{key}: {{"*", "*"}},\n')
        binding = bindings[package, table, "vectors"]
        for d in binding.inputs:
            add_shape(package, table, d["variant"], ",".join(sorted(d["cells"])), ",".join(sorted(binding.files)))
        cases.append(common_vectors.VECTORCMD[name] % {"key": key})
    body = VECTORCMD % {"imports": "\n".join(imports)+"\n", "want": "".join(want), "cases": "".join(cases),
                        "stand": "", "extra": common_vectors.FAMILY_READ_GO if fam else ""}
    a,b=body.index("// Stand —"),body.index("func parse(")
    body=body[:a]+FULL_STAND.replace("{{STAND}}","".join(stands))+body[b:]
    a,b=body.index('\tif *in.Variant != ""'),body.index('\tfiles := map[string][]byte{}',body.index('func Run('))
    body=body[:a]+('\t_ = shape\n\tif !wireShape(pkg,*in.Variant,keys(in.Cells),keys(in.Files)) {\n'
                   '\t\treturn 0,nil,nil,fmt.Errorf("cells/files/variant are not a declared wire shape")\n\t}\n')+body[b:]
    body=body.replace('[]byte(fmt.Sprintf("panic: %v\\n", r)), nil',
                      '[]byte(fmt.Sprintf("panic: %v\\n", r)), fmt.Errorf("panic: %v", r)')
    by = {}
    for key, value in shapes:
        if value not in by.setdefault(key,[]):
            by[key].append(value)
    entries="".join(f"\t\t{k}: {{{', '.join(v)}}},\n" for k,v in by.items())
    body += ('\nfunc wireShape(pkg,variant,cells,files string) bool {\n'
             '\tshapes:=map[string][][2]string{\n'+entries+'\t}\n'
             '\tfor _,s:=range shapes[pkg+"\\x00"+variant] {if s[0]==cells && s[1]==files{return true}}\n'
             '\treturn false\n}\n')
    return gofmt(body)


def go_vectorcmd(decls, known, bindings=None, full_wire=False):
    if full_wire:
        return _go_vectorcmd_full(decls, known, bindings)
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
            elif d["compare"] == "raw":                # Framed raw outcome: creates-key Raw is stdout bytes.
                cases.append(UNIFIED_CASE.replace("\t\tvalue = a.Value\n", "\t\treturn 0, a.Raw, nil, nil\n")
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
            if branch not in stand:                    # Tables sharing one stand key (door-token verify/place).
                stand.append(branch)
    for name, table in known:
        cd = common_vectors.DECLS[name]
        key = go_str(f"common/{name} {table}")
        inputs, fixtures = cd["inputs"], cd["files"]
        if bindings is not None:
            binding = bindings[f"common/{name}", table, "vectors"]
            inputs = {k for d in binding.inputs for k in d["cells"]}
            fixtures = binding.files
        want.append(f"\t\t{key}: {{{go_str(','.join(sorted(inputs)))}, {go_str(','.join(sorted(fixtures)))}}},\n")
        branch = common_vectors.VECTORCMD[name] % {"key": key}
        cases.append(branch)
    body = VECTORCMD % {"imports": "\n".join(imports) + "\n", "want": "".join(want), "cases": "".join(cases),
                        "stand": "".join(stand), "extra": common_vectors.FAMILY_READ_GO if fam else ""}
    if not stand:                                      # Lessons without stand calls (P/05) never read stand data.
        body = body.replace("\tdata, err := os.ReadFile(path)\n", "\tdata, err := os.ReadFile(path)\n\t_ = data\n", 1)
    if variants:                                       # Packages with row halves, such as values-by-type write/read.
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


COMPARE_GO = r'''// Code generated by tools/normgen/gen_vectors.py; DO NOT EDIT.

// The compare rules of the package READMEs beyond value/raw/sets (the draft wire of P/03, P/04, P/06; replaced by the form
// Platform/common/vectors/wire.tsv when it is published).
package vectortests

import (
	"encoding/json"
	"io"
	"math/big"
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
	case strings.HasPrefix(compare, "without:"):
		g, _ := got.(map[string]any)
		wm, _ := w.(map[string]any)
		g2, w2 := map[string]any{}, map[string]any{}
		drop := map[string]bool{}
		for _, k := range strings.Split(compare[len("without:"):], ",") {
			drop[k] = true
		}
		for k, v := range g {
			if !drop[k] {
				g2[k] = v
			}
		}
		for k, v := range wm {
			if !drop[k] {
				w2[k] = v
			}
		}
		if g == nil || !reflect.DeepEqual(g2, w2) {
			errs = append(errs, "$ (without "+compare[len("without:"):]+"): "+show(g2)+", want "+show(w2))
		}
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
		// This comparison retains numeric lexemes; the other draft comparisons
		// keep their existing norm/decoded path unchanged.
		encoded, err := json.Marshal(a.Value)
		turnWant, wantOK := turnJSON(want)
		turnGot, gotOK := turnJSON(string(encoded))
		if err != nil || !wantOK || !gotOK {
			errs = append(errs, "$: turn requires one JSON value")
			break
		}
		turn(turnWant, turnGot, &errs)
	case compare == "secret-domain":
		secretDomain(w, got, &errs)
	case strings.HasPrefix(compare, "round:"):
		round(w, got, compare[len("round:"):], &errs)
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
			if v == "@any" {                     // Key is present;any value matches(the shared acceptance vocabulary).
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

// secret — secret-in, the refusal items (and masked at the console): keys only fault, text (masked); fault equals; at a
// non-empty fault text is present and repeats no whole hidden password part of ≥ 4 bytes (no-leak whole), else no text.
func secret(exp, act any, errs *[]string) {
	e, _ := exp.(map[string]any)
	a, ok := act.(map[string]any)
	if !ok {
		*errs = append(*errs, "$: want an object")
		return
	}
	_, display := e["masked"]
	for k := range a {
		if k != "fault" && k != "text" && !(display && k == "masked") {
			*errs = append(*errs, "$."+k+": an extra key")
		}
	}
	if display && !reflect.DeepEqual(a["masked"], e["masked"]) {
		*errs = append(*errs, "$.masked: "+show(a["masked"])+", want "+show(e["masked"]))
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
	// no-leak whole:true(Architect;secret-in README, Run item 3):text contains no complete hidden raw
	// UTF-8 fragment of at least4 bytes;shorter fragments are excluded by generator secret_hidden.
	hidden, _ := e["hidden"].([]any)
	for _, h := range hidden {
		if hs, _ := h.(string); len(hs) >= 4 && strings.Contains(text, hs) {
			*errs = append(*errs, "$.text repeats a hidden value of the row (no-leak whole)")
		}
	}
}

// secretDomain follows the domain secret-in native outcome:only fault/text keys;fault is checked only
// for emptiness.Its nonempty form requires text without a complete hidden fragment(no-leak whole).
func secretDomain(exp, act any, errs *[]string) {
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
	gf, _ := a["fault"].(string)
	wf, _ := e["fault"].(string)
	if _, has := a["fault"]; !has || (gf == "") != (wf == "") {
		*errs = append(*errs, "$.fault: "+show(a["fault"])+", want "+map[bool]string{true: "empty", false: "non-empty"}[wf == ""])
	}
	text, has := a["text"].(string)
	if wf == "" {
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
		if hs, _ := h.(string); len(hs) >= 4 && strings.Contains(text, hs) {
			*errs = append(*errs, "$.text repeats a hidden value of the row (no-leak whole)")
		}
	}
}

// round checks domain-envelopes field:prefix:subset expectation plus two different envelopes sharing
// the prefix;non-ok responses use subset matching.
func round(exp, act any, spec string, errs *[]string) {
	subset(exp, act, "$", errs)
	e, _ := exp.(map[string]any)
	if e["result"] != "ok" {
		return
	}
	field, prefix, _ := strings.Cut(spec, ":")
	a, _ := act.(map[string]any)
	env, _ := a[field].([]any)
	if len(env) != 2 {
		*errs = append(*errs, "$."+field+": want two envelopes, got "+show(a[field]))
		return
	}
	x, _ := env[0].(string)
	y, _ := env[1].(string)
	if !strings.HasPrefix(x, prefix) || !strings.HasPrefix(y, prefix) || x == y {
		*errs = append(*errs, "$."+field+": two distinct envelopes with the prefix "+prefix)
	}
}

func turnJSON(text string) (any, bool) {
	dec := json.NewDecoder(strings.NewReader(text))
	dec.UseNumber()
	var value, extra any
	if dec.Decode(&value) != nil {
		return nil, false
	}
	return value, dec.Decode(&extra) == io.EOF
}

// turnSame compares JSON numbers exactly by value without a Float64 fallback.
func turnSame(want, got any) bool {
	switch w := want.(type) {
	case json.Number:
		g, ok := got.(json.Number)
		a, aOK := new(big.Rat).SetString(string(w))
		b, bOK := new(big.Rat).SetString(string(g))
		return ok && aOK && bOK && a.Cmp(b) == 0
	case map[string]any:
		g, ok := got.(map[string]any)
		if !ok || len(w) != len(g) {
			return false
		}
		for k, v := range w {
			actual, has := g[k]
			if !has || !turnSame(v, actual) {
				return false
			}
		}
		return true
	case []any:
		g, ok := got.([]any)
		if !ok || len(w) != len(g) {
			return false
		}
		for i, v := range w {
			if !turnSame(v, g[i]) {
				return false
			}
		}
		return true
	default:
		return reflect.DeepEqual(want, got)
	}
}

// turn — turn cases.tsv: actions one per event; write.holder "@new" — a new non-empty mark never seen before, "@same" —
// the mark bound by an earlier "@new" (an unbound "@same" is an error); then by value.
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
					if got == "" || strings.HasPrefix(got, "@") || seen[got] {
						*errs = append(*errs, "$["+strconvI(i)+"].write.holder: want a new mark, got "+show(aw["holder"]))
						return
					}
					seen[got], current = true, got
				case "@same":                    // Only a label already bound in the current attempt(spec103 comparison item 12).
					if current == "" {
						*errs = append(*errs, "$["+strconvI(i)+"].write.holder: @same before any @new — an unbound mark")
						return
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
		if !turnSame(w, ae[i]) {
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
	case e["status"] == "ok" && e["sealed"] == true:
		r, _ := a["row"].(string)
		if a["status"] != "ok" || len(a) != 3 || !strings.HasPrefix(r, "enc:v2:") || !reflect.DeepEqual(a["plaintext"], e["plaintext"]) {
			*errs = append(*errs, "$: want {status: ok, row: enc:v2:…, plaintext: "+show(e["plaintext"])+"}")
		}
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
'''


BASE_COMPARES = ("raw", "layer1", "sets", "value")


def frames_of(d, rows, pdir):
    """Return [(line, cells, variant, frame cells or None, (exit, value, raw bytes))]; frames represent row halves."""
    if d.get("_form"):
        by_line = dict(rows)
        return [(r.lines[0], by_line[r.lines[0]], r.variant, r.cells,
                 (r.code, None if isinstance(r.value, bytes) else r.value,
                  r.value if isinstance(r.value, bytes) else None), r.compare) for r in d["_runs"]]
    out = []
    if d["compare"] == "sets":
        return out
    if "whole" in d:                                   # One call for the whole selected table (group_by=[]).
        w = d["whole"]
        return [(rows[0][0], {"case": w["case"]}, "", {}, w["expect"](rows), None)]
    for no, r in rows:
        if "frames" in d:
            for variant, cells, exp, compare in d["frames"](r):
                out.append((no, r, variant, cells, exp, compare))
        else:
            out.append((no, r, "", None, d["expect"](r, pdir), None))
    return out


def fixture(root, pdir, spec, r):
    """Resolve a fixture relative to its package directory or @root/<course-relative path>."""
    if spec.startswith("@root/"):
        return (Path(root) / spec[len("@root/"):]).read_bytes()
    return (pdir / spec.format(**r)).read_bytes()


def lesson_consumers(root):
    try:
        return vector_consumers.for_lesson(root, L.key)
    except vector_consumers.ConsumerError as exc:
        raise GenError(str(exc)) from None


def build(root=ROOT):
    """Return ({output-relative path: bytes}, [(package/table/line, status)] inventory)."""
    if L.key == "06-console":
        import wire_vectors
        try:
            return wire_vectors.build(root, sys.modules[__name__], decls=plan(root)[0], lesson=L.key)
        except wire_vectors.wire.WireError as exc:
            raise GenError(str(exc)) from None
    if L.key == "02-installer":
        import wire_vectors
        try:
            return wire_vectors.build(root, sys.modules[__name__])
        except wire_vectors.wire.WireError as exc:
            raise GenError(str(exc)) from None
    import hashlib
    decls, known = plan(root)
    files, inv = {}, []
    uses_extra = False
    by_fn = {}
    for d in decls:
        by_fn.setdefault(d["fn"], []).append(d)
    files["go/vectoradapter/vectoradapter.go"] = gofmt(TYPES_GO).encode("utf-8")
    for fn, ds in by_fn.items():
        files[f"go/vectoradapter/{fn.lower()}.go"] = gofmt(stub(ds)).encode("utf-8")
    for fname, text in common_vectors.adapters(L.key, known_only=True, root=root).items():
        files[f"go/vectoradapter/{fname}"] = gofmt(text).encode("utf-8")
    files["go/vectorcmd/vectorcmd.go"] = go_vectorcmd(decls, known).encode("utf-8")
    files["go/cmd/vectors/main.go"] = gofmt(MAIN_GO % GO_MODULE).encode("utf-8")
    files["go/vectortests/helpers_test.go"] = gofmt(HELPERS % {"module": GO_MODULE}).encode("utf-8")
    for d in decls:
        if d.get("_form"):
            continue
        if d.get("per_list"):
            inv.append((f"{d['package']} {d['table']} (vectors, per list)", "translated"))
            continue                                  # Same function; the stand-declaration set test judges it.
        pdir, path, rows = read_table(root, d)
        if "select" in d:                             # Consumer row selection follows Who performs it.
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
        if d["surface"] != "vectors" and any(x is not d and not x.get("per_list") and x["package"] == d["package"]
                                             and x["table"] == d["table"] for x in decls):
            name += "_Stand"                           # A table with stand and framed surfaces gets separate tests for each.
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
            continue                                   # Shared helpers live in helpers_test.go.
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
    import consumer_vectors
    try:
        extra, extra_inv = consumer_vectors.render(root, sys.modules[__name__], decls)
    except consumer_vectors.wire.WireError as exc:
        raise GenError(str(exc)) from None
    files.update(extra)
    inv.extend(extra_inv)
    files["go/vectortests/inventory.tsv"] = ("\n".join(["# The vector tables of the lesson (gen_vectors.py).",
                                                        "table\tstatus"] + ["\t".join(x) for x in inv]) + "\n").encode()
    return files, inv


def generate(root=ROOT, out=DEFAULT_OUT):
    files, inv = build(root)
    out = Path(out)
    for sub in ("go/vectortests", "go/vectorcmd", "go/cmd/vectors", "go/wirecheck", "vectors"):
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
        res.append((sub, name, data, "generated", L.output_source(kept, out), own))
    return res


def provenance():
    import hashlib
    import tsv_input

    def entry(path):
        return {"path": str(Path(path).relative_to(ROOT)), "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}
    def entries(paths):
        return [entry(p) for p in dict.fromkeys(p for src in paths for p in
                (tsv_input.source_files(src, root=ROOT) if src.suffix == ".tsv" else [src]))]
    generators = [entry(Path(__file__).resolve()), entry(Path(tsv_input.__file__))]
    decls, known = plan(ROOT)
    turn_sources = ([ROOT / "Platform/common/vectors/turn/README.md", ROOT / "Platform/common/contracts/turn.md"]
                    if any(d["package"] == "common/turn" for d in decls) else [])
    if L.key == "06-console":
        import wire
        runs, _ = wire.expand(ROOT, L.key)
        paths = {package_dir(ROOT, r.binding.package) / r.binding.table for r in runs}
        forms = sorted(paths | set(wire.form_paths(ROOT)) | {ROOT / common_vectors.CONSUMERS, ROOT / vector_consumers.LESSONS}
                       | set(turn_sources))
        return {"form": entries(forms), "generator": entry(Path(__file__).resolve()), "generators": generators,
                "handwritten": [entry(HERE / p) for p in ("wire_api_p06.py", "wire.py", "wire_vectors.py",
                    "vector_consumers.py", "common_vectors.py", "wirert/full/go/check.go", "doorrt2/go/schema.go")],
                "judge": entry(HERE / "test_wire_api_p06.py"),
                "judges": [entry(HERE / p) for p in ("test_gen_vectors_lessons.py", "test_wire_full.py",
                    "test_wire_vectors.py", "test_contracts.py", "wire_fakes.py", "test_turn_wire.py", "kit/test_p06_turn.py")]}
    if L.key == "02-installer":
        import wire_vectors
        runs, _ = wire_vectors.wire.expand(ROOT, L.key)
        paths = {package_dir(ROOT, r.binding.package) / r.binding.table for r in runs}
        forms = sorted(paths | set(wire_vectors.wire.form_paths(ROOT)) | {ROOT / common_vectors.CONSUMERS, ROOT / vector_consumers.LESSONS})
        return {"form": entries(forms), "generator": entry(Path(__file__).resolve()), "generators": generators,
                "handwritten": [entry(HERE / p) for p in ("wire.py", "wire_vectors.py", "vector_consumers.py", "wirert/go/check.go",
                                                          "doorrt2/go/schema.go")], "judge": entry(JUDGE),
                "judges": [entry(HERE / p) for p in ("test_wire_vectors.py", "test_wire.py", "test_consumer_packages.py", "test_wire_full.py", "wire_fakes.py")]}
    forms = sorted({read_table(ROOT, d)[1] for d in decls}) + [ROOT / common_vectors.CONSUMERS, ROOT / vector_consumers.LESSONS] + turn_sources
    if any(d.get("_form") for d in decls):
        import wire
        forms.extend(wire.form_paths(ROOT))
    hand = ["vector_consumers.py", "consumer_vectors.py"]
    if any(d.get("_form") for d in decls):
        hand += ["wire.py", "wire_vectors.py", "wirert/full/go/check.go", "doorrt2/go/schema.go"]
    return {"form": entries(forms), "generator": entry(Path(__file__).resolve()), "generators": generators,
            "handwritten": [entry(HERE / p) for p in hand], "judge": entry(JUDGE),
            "judges": [entry(HERE / p) for p in ("test_consumer_packages.py", "test_gen_vectors_lessons.py",
                                                "test_wire_full.py", "wire_fakes.py")
                       + (("test_turn_wire.py",) if turn_sources else ())]}


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
    """Preserve P/02 documentation; other lessons list unified packages and stand keys from declarations."""
    if L.key == "02-installer" or (L.key != "06-console" and L.key not in WIRE):
        return KIT_MD_P02
    decls, known = plan(ROOT)
    unified = sorted({d["package"] for d in decls if d["surface"] == "vectors"} | {f"common/{n}" for n, _ in known})
    stands = sorted({d["surface"].split(":", 1)[1] for d in decls if d["surface"] != "vectors"})
    head = KIT_MD_P02.split("Build `go build")[0]
    if L.key == "06-console":
        return head + (
            "Build `go build -o bin/vectors ./cmd/vectors`. P/06 uses the published canonical wire form\n"
            "`Platform/common/vectors/wire.tsv`: its active rows supply inputs, fixtures, native schemas, comparisons\n"
            "and assertions. The Go API is declared in `tools/normgen/wire_api_p06.py`. The profile maps\n"
            "`vectors: <package>: 'bin/vectors {input}'` (" + ", ".join(unified) + ") and\n"
            "`stand: <key>: 'bin/vectors stand <key> {input}'` (" + ", ".join(stands) + ").\n"
            "Each adapter returns `Answer{Code, Value, Raw}`. GroupOf receives the exact UTF-8 bytes of the sole raw\n"
            "cell; stand adapters receive the argument file bytes. Native output is validated before comparisons\n"
            "and assertion ignores. Native refusals retain their published exit codes; a panic or an unimplemented\n"
            "adapter is an execution error. `common/family-read` uses the kit's `families`. Layouts and inactive\n"
            "surfaces are listed as excluded, with their reasons, in `vectortests/inventory.tsv`.\n"
            "`common/turn` selects only operations for P/06. With part `contracts`, the ordinary Turn adapter\n"
            "substitutes the current attempt label for input read `@same` before calling the turn algorithm.\n"
            "Its output contains real labels; `compare=turn` checks fresh/current labels and every other value.\n"
            "`held` proves turn capture only; operations-epoch, worker execution and real-IO duties remain separate.\n")
    return head + (
        "Build `go build -o bin/vectors ./cmd/vectors`. The profile maps each package of the lesson:\n"
        "`vectors: <package>: 'bin/vectors {input}'` (the unified command: " + ", ".join(unified) + ") and the stand keys\n"
        "`stand: <key>: 'bin/vectors stand <key> {input}'` (" + ", ".join(stands) + "). Each package's function returns\n"
        "`Answer{Code, Value, Raw}`: `Code` 0 (or the published 2), `Value` — the JSON value of stdout, `Raw` — raw stdout\n"
        "bytes (creates-key, near-of). The stubs answer code -1 «not implemented». `common/family-read` needs none of your\n"
        "code (the kit's `families`). The rows a consumer does not perform (README «Who performs it») and the tables the\n"
        "lesson does not run are in `vectortests/inventory.tsv` as excluded, with the reason. The wire of this lesson is a\n"
        "draft (tools/normgen/wire_draft.py) until the form Platform/common/vectors/wire.tsv is published.\n")


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
