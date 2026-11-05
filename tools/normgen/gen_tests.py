"""Генератор № 6 ADR-0125: тесты из векторов P/01 и вход команды векторов — без модели, по декларации пакетов.

Источники (только формы, проза README не читается — ADR-0125 доп. (1) п. 4):
- `Platform/01-store/vectors/jcs/canonical_json.tsv` — строки `raw`, `canonical`, `sha256` без шапки;
- `Platform/01-store/vectors/rights-evaluator/expect.tsv` (шапка `role action key expect`) и `rights.json` рядом;
- `Platform/01-store/forms/stages.tsv` — имя этапа, чей `gate` — `vectors:<пакет>`: от него имя тестов
  `Test<Этап>_…` (ADR-0126 доп. (1) п. 1, доп. (3) п. 2; `jcs` → `TestJcs_`, `rights_eval` → `TestRightsEval_`).

Декларация пакетов (PACKAGES) — ручная выжимка README пакетов и единого провода команды векторов (общий README
приёмки «The unified command of a vector package»): входные колонки, фикстуры, нативный исход. Формы у этого нет;
это место — вопрос «Спецификации» (отчёт генератора).

Выход в `tools/normgen/out/p01-1` (модуль `normgen/p01-1`, Go 1.22, только stdlib):
- `go/vectoradapter/canonical.go`, `rights.go` — заглушки адаптера по файлу на функцию: договор, который реализует реализация (или свидетель);
- `go/vectortests/` — тесты `Test<Этап>_Line<N>`, по одному на строку вектора; зовут только адаптер;
- `go/vectorcmd/vectorcmd.go` — единый провод команды векторов: jcs, rights-evaluator — через адаптер, write-checks —
  через writecheck (пробы `forms/write-checks.probes.tsv`); `go/cmd/vectors/main.go` — бинарь `bin/vectors {input}`
  (ADR-0126 доп. (5)); `go/jsonstrict`, `go/writecheck` — копии ручного `kit/go`, чтобы модуль выхода собирался;
- `vectors/<пакет>/line-<N>.json` и `cases.tsv` — входы команды векторов и ожидаемый нативный исход для судьи
  `tools/normgen/vector_judge.py` (gate `vectors:<пакет>` без Go-тестов).
Путь импорта `"normgen/p01-1/` в пакете Б заменяет `tools/normgen/kit/build_kit.py` на `"<module>/internal/`.

Запуск: python tools/normgen/gen_tests.py [корень_курса [каталог_выхода]].
"""
import base64
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

from gen_checks import camel, go_str, gofmt  # noqa: E402 — общие кирпичи генератора № 1
import gen_stagetests  # noqa: E402 — тесты этапов из сценариев (ADR-0125 доп. (3))
import gate  # noqa: E402 — общий разбор gate (ревью Codex С4)
import common_vectors  # noqa: E402 — общие пакеты векторов урока (ADR-0125 доп. (5) п. 5)
import lesson  # noqa: E402 — урок (ADR-0125 доп. (5) п. 2)
L = lesson.CURRENT

DEFAULT_OUT = L.out
GO_MODULE = L.go_module
STAGES = f"{L.rel}/forms/stages.tsv"
ACTIONS = ("read", "write", "delete")
HEX64 = re.compile(r"[0-9a-f]{64}")

# Декларация: пакет единого провода (путь от Platform/ без vectors/), таблица, входные колонки (ключи `cells`),
# входные фикстуры (ключи `files`), нативный исход. README пакетов: jcs «canonical_json.tsv» (cells={raw}, код 0 и
# {canonical, sha256} по значению); rights-evaluator — README называет только пробы через сокет, нативной формы нет:
# по общему правилу «A table whose package README names no native form» одна колонка ожидания `expect` — значение
# колонки строкой JSON (`"allow"` | `"deny"`), код 0; файл прав — фикстура `rights.json`.
PACKAGES = {
    "jcs": {"package": "01-store/jcs", "dir": "Platform/01-store/vectors/jcs", "table": "canonical_json.tsv",
            "inputs": ["raw"], "files": [], "native": "code 0, {canonical, sha256} by value"},
    "rights-evaluator": {"package": "01-store/rights-evaluator", "dir": "Platform/01-store/vectors/rights-evaluator",
                         "table": "expect.tsv", "inputs": ["role", "action", "key"], "files": ["rights.json"],
                         "native": "code 0, \"allow\" | \"deny\""},
    # write-checks — пробы таблицы проверок (ADR-0126 доп. (5)): провод драйвера раннера P/01/vectors-write-checks —
    # cells {sock, body, lim, allow}: body — ячейка как есть, lim — объект #lim, allow — строки #allow; строки nopair
    # (тело — проза) не входят; нативно {"n": 0} или {"n", "code", "kind"} первой нарушенной строки write-checks.tsv.
    # Исполняет пакет (writecheck.Check: разбор Н2.1 + проверки checks), не адаптер модели.
    "write-checks": {"package": "01-store/write-checks", "dir": "Platform/01-store/forms",
                     "table": "write-checks.probes.tsv", "inputs": ["sock", "body", "lim", "allow"], "files": [],
                     "native": "code 0, {\"n\": 0} | {\"n\", \"code\", \"kind\"} of the first violated row"},
}


class GenError(Exception):
    """Отказ генератора: вектор или форма этапов вне формы."""


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def strict_json(text, where):
    """JSON по RFC 8259 без NaN/Infinity и повторов имён — иначе GenError."""
    def pairs(items):
        keys = [k for k, _ in items]
        if len(keys) != len(set(keys)):
            raise GenError(f"{where}: repeated name in {text!r}")
        return dict(items)

    def const(name):
        raise GenError(f"{where}: {name} is not JSON")

    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=const)
    except json.JSONDecodeError as exc:
        raise GenError(f"{where}: not JSON: {exc}") from None


# ---------------------------------------------------------------- источники

class Source:
    def __init__(self, root, rel):
        self.rel = rel
        self.data = (Path(root) / rel).read_bytes()
        self.sha256 = sha256(self.data)
        try:
            self.text = self.data.decode("utf-8")
        except UnicodeDecodeError:
            raise GenError(f"{rel}: not UTF-8") from None


def read_stages(root):
    """stages.tsv → {пакет vectors: имя этапа}; Source формы."""
    src = Source(root, STAGES)
    rows = [line.split("\t") for line in src.text.split("\n") if line and not line.startswith("#")]
    if not rows or "stage" not in rows[0] or "gate" not in rows[0]:
        raise GenError(f"{STAGES}: no header with stage and gate")
    head = rows[0]
    by_pkg = {}
    for cells in rows[1:]:
        row = dict(zip(head, cells))
        if not re.fullmatch(r"[a-z][a-z0-9_]*", row.get("stage", "")):
            raise GenError(f"{STAGES}: stage {row.get('stage')!r} — a Latin name")
        try:
            checks = gate.parse(row.get("gate", ""), f"{STAGES}: {row['stage']}")
        except gate.GateError as exc:
            raise GenError(str(exc)) from None
        for c in checks:                       # элементы vectors: списка gate (ADR-0126 доп. (7) п. 3)
            if c.kind != "vectors":
                continue
            if c.package in by_pkg:
                raise GenError(f"{STAGES}: two stages judge vectors:{c.package}")
            by_pkg[c.package] = row["stage"]
    return by_pkg, src


def read_jcs(root):
    """canonical_json.tsv → [(строка файла, raw, canonical, sha256)]; сверка: sha256 — от canonical, оба — JSON."""
    decl = PACKAGES["jcs"]
    src = Source(root, f"{decl['dir']}/{decl['table']}")
    rows, seen = [], {}
    for no, line in enumerate(src.text.split("\n"), 1):
        if not line or line.startswith("#"):
            continue
        where = f"{src.rel}:{no}"
        cells = line.split("\t")
        if len(cells) != 3:
            raise GenError(f"{where}: {len(cells)} cells, expected raw, canonical, sha256")
        raw, canonical, digest = cells
        if "\r" in line:
            raise GenError(f"{where}: CR in a cell")
        if not HEX64.fullmatch(digest):
            raise GenError(f"{where}: sha256 {digest!r} — 64 lowercase hex")
        if sha256(canonical.encode("utf-8")) != digest:
            raise GenError(f"{where}: sha256 is not the sha256 of canonical")
        strict_json(raw, f"{where}: raw")
        strict_json(canonical, f"{where}: canonical")
        if raw in seen and seen[raw] != canonical:
            raise GenError(f"{where}: raw repeats line {seen[raw][0]} with another canonical")
        seen[raw] = canonical
        rows.append((no, raw, canonical, digest))
    if not rows:
        raise GenError(f"{src.rel}: no vectors")
    return rows, src


def read_rights(root):
    """expect.tsv + rights.json → ([(строка файла, role, action, key, allow)], Source таблицы, Source файла прав)."""
    decl = PACKAGES["rights-evaluator"]
    src = Source(root, f"{decl['dir']}/{decl['table']}")
    rights = Source(root, f"{decl['dir']}/rights.json")
    doc = strict_json(rights.text, rights.rel)
    roles = doc.get("roles") if isinstance(doc, dict) else None
    if not isinstance(roles, dict) or not roles:
        raise GenError(f"{rights.rel}: no roles")
    rows, header, seen = [], None, {}
    for no, line in enumerate(src.text.split("\n"), 1):
        if not line or line.startswith("#"):
            continue
        cells = line.split("\t")
        where = f"{src.rel}:{no}"
        if header is None:
            if cells != ["role", "action", "key", "expect"]:
                raise GenError(f"{where}: header must be role, action, key, expect")
            header = cells
            continue
        if len(cells) != 4:
            raise GenError(f"{where}: {len(cells)} cells, expected 4")
        role, action, key, expect = cells
        if role not in roles:
            raise GenError(f"{where}: role {role!r} is not in {rights.rel}")
        if action not in ACTIONS:
            raise GenError(f"{where}: action {action!r} — one of {ACTIONS}")
        if expect not in ("allow", "deny"):
            raise GenError(f"{where}: expect {expect!r} — allow or deny")
        if (role, action, key) in seen and seen[role, action, key] != expect:
            raise GenError(f"{where}: repeats an earlier row with another expect")
        seen[role, action, key] = expect
        rows.append((no, role, action, key, expect == "allow"))
    if not rows:
        raise GenError(f"{src.rel}: no vectors")
    return rows, src, rights


def read_probes(root):
    """write-checks.probes.tsv + write-checks.tsv → ([(строка, sock, body, ожидание)], lim, allow, [Source])."""
    decl = PACKAGES["write-checks"]
    src = Source(root, f"{decl['dir']}/{decl['table']}")
    table = Source(root, f"{decl['dir']}/write-checks.tsv")
    trows = [line.split("\t") for line in table.text.split("\n") if line and not line.startswith("#")]
    if not trows or not {"n", "code", "kind"} <= set(trows[0]):
        raise GenError(f"{table.rel}: no header with n, code, kind")
    head = trows[0]
    checks = {}
    for cells in trows[1:]:
        row = dict(zip(head, cells))
        if not re.fullmatch(r"[1-9][0-9]*", row["n"]) or int(row["n"]) != len(checks) + 1 or \
                not re.fullmatch(r"[1-5][0-9]{2}", row["code"]) or not re.fullmatch(r"[a-z]+", row["kind"]):
            raise GenError(f"{table.rel}: n {row.get('n')!r}: n from 1, a code NNN, a kind")
        checks[int(row["n"])] = (int(row["code"]), row["kind"])
    lim, allow, rows, header = {}, [], [], None
    for no, line in enumerate(src.text.split("\n"), 1):
        where = f"{src.rel}:{no}"
        if line.startswith("#lim "):
            m = re.fullmatch(r"#lim ([A-Z][A-Z0-9_]*) (0|[1-9][0-9]*)", line)
            if not m or m[1] in lim:
                raise GenError(f"{where}: #lim NAME <integer>, once per name")
            lim[m[1]] = int(m[2])
            continue
        if line.startswith("#allow "):
            if not re.fullmatch(r"#allow \S+ \S+( \S+)?", line):
                raise GenError(f"{where}: #allow <sock> <op|*> [<prefix>]")
            allow.append(line[len("#allow "):])
            continue
        if not line or line.startswith("#"):
            continue
        cells = line.split("\t")
        if header is None:
            if cells != ["n", "case", "sock", "body"]:
                raise GenError(f"{where}: header must be n, case, sock, body")
            header = cells
            continue
        if len(cells) != 4:
            raise GenError(f"{where}: {len(cells)} cells, expected 4")
        n, kind, sock, body = cells
        if kind not in ("only", "pair", "nopair", "pass") or not re.fullmatch(r"0|[1-9][0-9]*", n) or not sock:
            raise GenError(f"{where}: n, only|pair|nopair|pass, a socket")
        n = int(n)
        if (kind == "pass") != (n == 0) or (n and n not in checks):
            raise GenError(f"{where}: pass is n 0, any other case names a row of {table.rel}")
        if kind == "nopair":
            continue
        rows.append((no, sock, body, {"n": 0} if n == 0 else {"n": n, "code": checks[n][0], "kind": checks[n][1]}))
    if not rows or not lim or not allow:
        raise GenError(f"{src.rel}: no probes, #lim or #allow")
    return rows, lim, allow, [src, table]


# ---------------------------------------------------------------- Go

def test_prefix(stages, pkg):
    if pkg not in stages:
        raise GenError(f"{STAGES}: no stage with gate vectors:{pkg}")
    return f"Test{camel(stages[pkg])}_"


def go_head(sources, extra=""):
    lines = ["// Code generated by tools/normgen/gen_tests.py (ADR-0125 № 6); DO NOT EDIT."]
    lines += [f"// Source {s.rel} sha256 {s.sha256}." for s in sources]
    if extra:
        lines.append("// " + extra)
    return "\n".join(lines) + "\n"


ADAPTER_HEAD = ('// Generated by tools/normgen/gen_tests.py (ADR-0125 № 6). YOURS from here: the kit puts this file once and\n'
               '// never overwrites it — edit it.\n')

ADAPTER_DOC = '''// Package vectoradapter — the adapter of an implementation to the generated vector tests (vectortests) and to the
// vector command (vectorcmd) of P/01 (ADR-0125 № 6). Each file is a STUB generated as the contract, one function per
// file (canonical.go — Canonical, stage jcs; rights.go — LoadRights, stage rights_eval): an implementation replaces the
// body with calls of its own functions and keeps the signature; editing one file never touches the other. The kit
// puts each file once and never overwrites it.
package vectoradapter

import "errors"

'''

ADAPTER_CANONICAL = '''// Canonical returns the RFC 8785 (JCS) canonical text of the JSON text raw — the bytes the store compares and signs
// (P/01.1 Н1 id; ADR-0072; vectors/jcs). An error means raw is not a JSON text.
func Canonical(raw []byte) ([]byte, error) {
	return nil, errors.New("vectoradapter.Canonical: not implemented")
}
'''

ADAPTER_RIGHTS = '''// LoadRights parses the bytes of a rights file (P/01.2 Н1.2) and returns its evaluator (P/01.2 Н1.3): allowed(role,
// action, key) reports whether the role may do the action on the key; action is "read", "write" or "delete". The
// returned function must be safe to call many times. An error means the file is not a rights file.
func LoadRights(file []byte) (func(role, action, key string) bool, error) {
	return nil, errors.New("vectoradapter.LoadRights: not implemented")
}
'''

DOC_GO = '''// Package vectortests — Go tests of the vectors of P/01, one test per vector row, generated by
// tools/normgen/gen_tests.py (ADR-0125 № 6). Names follow the stages of forms/stages.tsv (ADR-0126 addendum (1) p. 1):
//
//	%s<N> — vectors/jcs/canonical_json.tsv, line N;
//	%s<N> — vectors/rights-evaluator/expect.tsv, line N.
//
// The tests call only package vectoradapter of the implementation.
package vectortests
'''

JCS_HELPERS = '''
import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"testing"

	"%(module)s/vectoradapter"
)

var _ func([]byte) ([]byte, error) = vectoradapter.Canonical

func canonical(s string) (out []byte, err error) {
	defer func() {
		if r := recover(); r != nil {
			out, err = nil, fmt.Errorf("panic: %%v", r)
		}
	}()
	return vectoradapter.Canonical([]byte(s))
}

// jcsRow — one row: Canonical(raw) is canonical byte for byte, its sha256 is sum; the canonical column is its own
// canonical text (the row canonical -> canonical).
func jcsRow(t *testing.T, raw, want, sum string) {
	t.Helper()
	got, err := canonical(raw)
	if err != nil {
		t.Fatalf("Canonical(%%q): %%v", raw, err)
	}
	if !bytes.Equal(got, []byte(want)) {
		t.Fatalf("Canonical(%%q)\\n got %%q\\nwant %%q", raw, got, want)
	}
	if h := sha256.Sum256(got); hex.EncodeToString(h[:]) != sum {
		t.Fatalf("sha256 of Canonical(%%q) is %%x, want %%s", raw, h, sum)
	}
	again, err := canonical(want)
	if err != nil {
		t.Fatalf("Canonical(%%q): %%v", want, err)
	}
	if !bytes.Equal(again, []byte(want)) {
		t.Fatalf("Canonical(%%q) of a canonical text\\n got %%q\\nwant it unchanged", want, again)
	}
}
'''

RIGHTS_HELPERS = '''
import (
	"fmt"
	"testing"

	"%(module)s/vectoradapter"
)

var _ func([]byte) (func(role, action, key string) bool, error) = vectoradapter.LoadRights

// rightsFile — the bytes of vectors/rights-evaluator/rights.json.
const rightsFile = %(rights)s

func allowed(role, action, key string) (ok bool, err error) {
	defer func() {
		if r := recover(); r != nil {
			ok, err = false, fmt.Errorf("panic: %%v", r)
		}
	}()
	eval, err := vectoradapter.LoadRights([]byte(rightsFile))
	if err != nil {
		return false, fmt.Errorf("LoadRights(rights.json): %%v", err)
	}
	if eval == nil {
		return false, fmt.Errorf("LoadRights(rights.json): nil evaluator")
	}
	return eval(role, action, key), nil
}

// rightsRow — one row: by rights.json the role may (allow) or may not (deny) do the action on the key.
func rightsRow(t *testing.T, role, action, key string, want bool) {
	t.Helper()
	got, err := allowed(role, action, key)
	if err != nil {
		t.Fatal(err)
	}
	if got != want {
		t.Fatalf("allowed(%%q, %%q, %%q) = %%v, want %%v", role, action, key, got, want)
	}
}
'''


def go_jcs_tests(rows, src, stages_src, prefix):
    out = [go_head([src, stages_src]), "package vectortests\n", JCS_HELPERS % {"module": GO_MODULE}]
    for no, raw, canonical, digest in rows:
        out.append(f"\n// {src.rel}:{no}\nfunc {prefix}Line{no}(t *testing.T) {{\n"
                   f"\tjcsRow(t, {go_str(raw)}, {go_str(canonical)}, {go_str(digest)})\n}}\n")
    return gofmt("".join(out))


def go_rights_tests(rows, src, rights, stages_src, prefix):
    out = [go_head([src, rights, stages_src]), "package vectortests\n",
           RIGHTS_HELPERS % {"module": GO_MODULE, "rights": go_str(rights.text)}]
    for no, role, action, key, allow in rows:
        word = "allow" if allow else "deny"
        out.append(f"\n// {src.rel}:{no} — {word}\nfunc {prefix}Line{no}(t *testing.T) {{\n"
                   f"\trightsRow(t, {go_str(role)}, {go_str(action)}, {go_str(key)}, {'true' if allow else 'false'})\n}}\n")
    return gofmt("".join(out))


VECTORCMD_GO = '''// Package vectorcmd — the unified command of a vector package (the common acceptance README, «The unified command of a
// vector package»; the wire of the runner cammeta-acceptance, «Единая команда пакета векторов») for the packages of
// P/01, on top of package vectoradapter (jcs, rights-evaluator — the model's code) and package writecheck (write-checks —
// the kit's checks). Generated by tools/normgen/gen_tests.py (ADR-0125 № 6).
//
// Use: the binary cmd/vectors of the kit (ADR-0126 addendum (5)), built by the profile's build into bin/vectors; the
// vector command is `bin/vectors {input}`; its main is os.Exit(vectorcmd.Main(os.Args[1:], os.Stdout, os.Stderr)). {input} is a JSON file {format, package, table, case, variant, cells, files}; the answer on stdout is
// {exit_code, stdout_b64, stderr_b64} of the native outcome, the outer code is 0; an input out of the wire — outer
// code 2, empty stdout.
//
// Packages (native outcome):
%(packages)s
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
	"sort"
	"strings"

%(imports)s)

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

// Run runs one vector of the input text data (the same as Main without the file): the native outcome; err — the
// input is out of the wire.
func Run(data []byte) (code int, stdout, stderr []byte, err error) {
	in, err := parse(data)
	if err != nil {
		return 0, nil, nil, err
	}
	return run(in)
}

// Main runs one vector: args is [path of {input}]. It returns the outer exit code.
func Main(args []string, stdout, stderr io.Writer) int {
	if len(args) != 1 {
		fmt.Fprintln(stderr, "vectors: usage: vectors <input.json>")
		return 2
	}
	data, err := os.ReadFile(args[0])
	if err != nil {
		fmt.Fprintf(stderr, "vectors: %%v\\n", err)
		return 2
	}
	in, err := parse(data)
	if err != nil {
		fmt.Fprintf(stderr, "vectors: %%s: %%v\\n", args[0], err)
		return 2
	}
	code, out, errOut, err := run(in)
	if err != nil {
		fmt.Fprintf(stderr, "vectors: %%s: %%v\\n", args[0], err)
		return 2
	}
	enc, _ := json.Marshal(answer{code, base64.StdEncoding.EncodeToString(out), base64.StdEncoding.EncodeToString(errOut)})
	stdout.Write(append(enc, '\\n'))
	return 0
}

func parse(data []byte) (*input, error) {
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.DisallowUnknownFields()
	var in input
	if err := dec.Decode(&in); err != nil {
		return nil, err
	}
	if dec.More() {
		return nil, fmt.Errorf("more than one JSON value")
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

// run — the native outcome of one row: code, stdout, stderr; err — the input is out of the wire.
func run(in *input) (code int, stdout, stderr []byte, err error) {
	pkg := *in.Package + " " + *in.Table
	want := map[string][2]string{
%(want)s	}
	shape, ok := want[pkg]
	if !ok {
		return 0, nil, nil, fmt.Errorf("package %%q table %%q is not a package of this command", *in.Package, *in.Table)
	}
	if *in.Variant != "" {
		return 0, nil, nil, fmt.Errorf("variant %%q, want \\"\\"", *in.Variant)
	}
	if keys(in.Cells) != shape[0] || keys(in.Files) != shape[1] {
		return 0, nil, nil, fmt.Errorf("cells {%%s} files {%%s}, want cells {%%s} files {%%s}",
			keys(in.Cells), keys(in.Files), shape[0], shape[1])
	}
	files := map[string][]byte{}
	for k, v := range in.Files {
		b, err := base64.StdEncoding.Strict().DecodeString(*v)
		if err != nil {
			return 0, nil, nil, fmt.Errorf("files.%%s: %%v", k, err)
		}
		files[k] = b
	}
	defer func() {
		if r := recover(); r != nil {
			code, stdout, stderr, err = 1, nil, []byte(fmt.Sprintf("panic: %%v\\n", r)), nil
		}
	}()
	cell := func(name string) string { return *in.Cells[name] }
	var value any
	switch pkg {
%(cases)s	}
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(value); err != nil {
		return 1, nil, []byte(err.Error() + "\\n"), nil
	}
	return 0, buf.Bytes(), nil, nil
}
%(extra)s'''

VECTORCMD_CASES = {
    "jcs": '''	case %(key)s:
		c, err := vectoradapter.Canonical([]byte(cell("raw")))
		if err != nil {
			return 1, nil, []byte("Canonical: " + err.Error() + "\\n"), nil
		}
		h := sha256.Sum256(c)
		value = map[string]string{"canonical": string(c), "sha256": hex.EncodeToString(h[:])}
''',
    "write-checks": '''	case %(key)s:
		var lim map[string]int64
		if err := json.Unmarshal([]byte(cell("lim")), &lim); err != nil {
			return 0, nil, nil, fmt.Errorf("cells.lim: %%v", err)
		}
		var allow []string
		if err := json.Unmarshal([]byte(cell("allow")), &allow); err != nil {
			return 0, nil, nil, fmt.Errorf("cells.allow: %%v", err)
		}
		var rules [][3]string
		for _, a := range allow {
			f := strings.Fields(a)
			if len(f) != 2 && len(f) != 3 {
				return 0, nil, nil, fmt.Errorf("cells.allow: %%q is not <sock> <op|*> [<prefix>]", a)
			}
			rules = append(rules, [3]string{f[0], f[1], strings.Join(f[2:], "")})
		}
		allowed := func(sock, op, key string) bool {
			for _, r := range rules {
				if r[0] == sock && (r[1] == "*" || r[1] == op) && strings.HasPrefix(key, r[2]) {
					return true
				}
			}
			return false
		}
		ref, _ := writecheck.Check([]byte(cell("body")), cell("sock"), lim, allowed)
		switch {
		case ref == nil:
			value = map[string]any{"n": 0}
		case ref.N == 0:
			return 1, nil, []byte("the body is not JSON by H2.1: " + ref.Reason + "\\n"), nil
		default:
			value = map[string]any{"n": ref.N, "code": ref.Code, "kind": ref.Kind}
		}
''',
    "rights-evaluator": '''	case %(key)s:
		allowed, err := vectoradapter.LoadRights(files["rights.json"])
		if err != nil {
			return 1, nil, []byte("LoadRights: " + err.Error() + "\\n"), nil
		}
		if allowed == nil {
			return 1, nil, []byte("LoadRights: nil evaluator\\n"), nil
		}
		if allowed(cell("role"), cell("action"), cell("key")) {
			value = "allow"
		} else {
			value = "deny"
		}
''',
}


MAIN_GO = '''// Command vectors — the vector command of the kit (ADR-0126 addendum (5)): `bin/vectors {input}`.
package main

import (
	"os"

	"%(module)s/vectorcmd"
)

func main() { os.Exit(vectorcmd.Main(os.Args[1:], os.Stdout, os.Stderr)) }
'''


def go_vectorcmd(sources):
    packages, want, cases = [], [], []
    decls = [(name, decl, VECTORCMD_CASES[name]) for name, decl in PACKAGES.items()]
    for name, table in common_vectors.composition(L.key):          # общие пакеты урока (ADR-0125 доп. (5) п. 5)
        d = common_vectors.DECLS[name]
        decls.append((name, {"package": f"common/{name}", "table": table, "inputs": d["inputs"],
                             "files": list(d["files"]), "native": d["native"]}, common_vectors.VECTORCMD[name]))
    for name, decl, case in decls:
        key = go_str(f"{decl['package']} {decl['table']}")
        packages.append(f"//   - {decl['package']} {decl['table']}: cells {{{', '.join(decl['inputs'])}}}, "
                        f"files {{{', '.join(decl['files'])}}}; {decl['native']}.")
        want.append(f"\t\t{key}: {{{go_str(','.join(sorted(decl['inputs'])))}, "
                    f"{go_str(','.join(sorted(decl['files'])))}}},\n")
        cases.append(case % {"key": key})
    fam = common_vectors.uses_families(L.key)
    imports = "".join(f'\t"{GO_MODULE}/{p}"\n' for p in (["families"] if fam else []) + ["vectoradapter", "writecheck"])
    body = VECTORCMD_GO % {"packages": "\n".join(packages) + "\n//", "module": GO_MODULE, "want": "".join(want),
                           "cases": "".join(cases), "imports": "\n" + imports,
                           "extra": common_vectors.FAMILY_READ_GO if fam else ""}
    return gofmt(go_head(sources) + "\n" + body)


# ---------------------------------------------------------------- входы команды векторов

def wire_input(decl, no, cells, files):
    doc = {"format": 1, "package": decl["package"], "table": decl["table"], "case": f"line-{no}", "variant": "",
           "cells": cells, "files": {k: base64.b64encode(v).decode("ascii") for k, v in files.items()}}
    return (json.dumps(doc, ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def cases_tsv(decl, sources, rows):
    """rows: [(case, файл входа, нативный код, ожидаемый stdout — JSON одной строкой)]."""
    head = [f"# Inputs of the vector command for {decl['package']} {decl['table']} (tools/normgen/gen_tests.py, ADR-0125 № 6).",
            f"# Native outcome: {decl['native']}; stdout is compared as one JSON value by value (tools/normgen/vector_judge.py)."]
    head += [f"# source {s.rel} sha256 {s.sha256}" for s in sources]
    lines = head + ["case\tinput\texit\tstdout"]
    lines += [f"{case}\t{name}\t{code}\t{out}" for case, name, code, out in rows]
    return ("\n".join(lines) + "\n").encode("utf-8")


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


# ---------------------------------------------------------------- сборка

def render(root=ROOT):
    """→ {путь относительно каталога выхода: байты}; GenError — источник вне формы."""
    try:
        lesson.require(L, "gen_tests (PACKAGES)")
    except lesson.LessonError as exc:
        raise GenError(str(exc)) from None
    root = Path(root)
    stages, stages_src = read_stages(root)
    probes, probe_lim, probe_allow, probe_srcs = read_probes(root)
    jcs, jcs_src = read_jcs(root)
    rights, rights_src, rights_file = read_rights(root)
    files = {
        "go/vectoradapter/canonical.go": gofmt(ADAPTER_HEAD + "\n" + ADAPTER_DOC + ADAPTER_CANONICAL).encode("utf-8"),
        "go/vectoradapter/rights.go": gofmt(ADAPTER_HEAD + "\n" + ADAPTER_DOC + ADAPTER_RIGHTS).encode("utf-8"),
        "go/vectortests/doc.go": gofmt(go_head([stages_src]) + "\n" + DOC_GO % (
            test_prefix(stages, "jcs") + "Line", test_prefix(stages, "rights-evaluator") + "Line")).encode("utf-8"),
        "go/vectortests/jcs_test.go": go_jcs_tests(jcs, jcs_src, stages_src,
                                                   test_prefix(stages, "jcs")).encode("utf-8"),
        "go/vectortests/rights_eval_test.go": go_rights_tests(rights, rights_src, rights_file, stages_src,
                                                              test_prefix(stages, "rights-evaluator")).encode("utf-8"),
        "go/vectorcmd/vectorcmd.go": go_vectorcmd([jcs_src, rights_src] + probe_srcs).encode("utf-8"),
        "go/cmd/vectors/main.go": gofmt(go_head([]) + "\n" + MAIN_GO % {"module": GO_MODULE}).encode("utf-8"),
    }
    # Копии ручного пакета kit/go (jsonstrict, writecheck): модуль выхода собирается сам по себе (vectorcmd импортирует
    # writecheck); в пакет Б они идут из kit/go частью writecheck, не частью tests.
    for sub in ("jsonstrict", "writecheck"):
        text = (HERE / "kit/go" / sub / f"{sub}.go").read_text(encoding="utf-8")
        text = text.replace('"kitmodule/internal/', f'"{GO_MODULE}/')
        files[f"go/{sub}/{sub}.go"] = gofmt(f"// Code generated by tools/normgen/gen_tests.py: copy of tools/normgen/kit/go/"
                                            f"{sub}/{sub}.go; DO NOT EDIT.\n\n" + text).encode("utf-8")
    try:
        staged, _ = gen_stagetests.build(root)
    except gen_stagetests.GenError as exc:
        raise GenError(str(exc)) from None
    for rel, text in staged.items():
        files[rel] = (gofmt(text) if rel.endswith(".go") else text).encode("utf-8")
    decl = PACKAGES["jcs"]
    base = f"vectors/{decl['package']}"
    case_rows = []
    for no, raw, canonical, digest in jcs:
        name = f"line-{no}.json"
        files[f"{base}/{name}"] = wire_input(decl, no, {"raw": raw}, {})
        case_rows.append((f"line-{no}", name, 0, compact({"canonical": canonical, "sha256": digest})))
    files[f"{base}/cases.tsv"] = cases_tsv(decl, [jcs_src], case_rows)
    decl = PACKAGES["rights-evaluator"]
    base = f"vectors/{decl['package']}"
    case_rows = []
    for no, role, action, key, allow in rights:
        name = f"line-{no}.json"
        files[f"{base}/{name}"] = wire_input(decl, no, {"role": role, "action": action, "key": key},
                                             {"rights.json": rights_file.data})
        case_rows.append((f"line-{no}", name, 0, compact("allow" if allow else "deny")))
    files[f"{base}/cases.tsv"] = cases_tsv(decl, [rights_src, rights_file], case_rows)
    decl = PACKAGES["write-checks"]
    base = f"vectors/{decl['package']}"
    case_rows = []
    shared = {"lim": compact(probe_lim), "allow": compact(probe_allow)}
    for no, sock, body, want in probes:
        name = f"line-{no}.json"
        files[f"{base}/{name}"] = wire_input(decl, no, {"sock": sock, "body": body, **shared}, {})
        case_rows.append((f"line-{no}", name, 0, compact(want)))
    files[f"{base}/cases.tsv"] = cases_tsv(decl, probe_srcs, case_rows)
    try:
        common(root, files)
    except common_vectors.CommonError as exc:
        raise GenError(str(exc)) from None
    return files


def common(root, files):
    """Общие пакеты векторов урока (common_vectors): заготовки адаптера, тесты TestCommon<Пакет>_Line<N>, входы судьи."""
    for fname, text in common_vectors.adapters(L.key).items():
        files[f"go/vectoradapter/{fname}"] = gofmt(text).encode("utf-8")

    def head(*rels):
        return go_head([Source(root, r) for r in rels if r])
    for fname, text in common_vectors.go_tests(L.key, root, go_str, head, GO_MODULE).items():
        files[f"go/vectortests/{fname}"] = gofmt(text).encode("utf-8")
    for name, table, rel, _, items, fx_rels in common_vectors.wire_rows(L.key, root):
        d = common_vectors.DECLS[name]
        decl = {"package": f"common/{name}", "table": table, "native": d["native"]}
        base = f"vectors/common/{name}"
        rows = []
        for no, cells, fxs, want in items:
            files[f"{base}/line-{no}.json"] = wire_input(decl, no, cells, fxs)
            rows.append((f"line-{no}", f"line-{no}.json", 0, want))
        files[f"{base}/cases.tsv"] = cases_tsv(decl, [Source(root, rel)] + [Source(root, r) for r in fx_rels], rows)


# ---------------------------------------------------------------- часть пакета Б `tests` (ADR-0126 доп. (2) п. 1)

# Части пакета Б (ADR-0126 доп. (7) п. 4): vectors — тесты векторов и команда векторов; stagetests — тесты этапов из
# сценариев и адаптер ядра. Каталоги частей заменяются целиком (../cmd/vectors — <dst>/01-store/cmd/vectors); своё у
# реализации (vectoradapter/, coreadapter/open.go) кладётся, только если его нет.
PART_DIRS = {"vectors": ("vectortests", "vectorcmd", "../cmd/vectors"), "stagetests": ("stagetests",)}
PART_OWN_DIRS = {"vectors": ("vectoradapter",), "stagetests": ("coreadapter",)}
KIT_DIRS = PART_DIRS["vectors"] + PART_DIRS["stagetests"]
KIT_IMPORT = f'"{GO_MODULE}/'


def kit_files(module, part="vectors", out=DEFAULT_OUT):
    """→ [(каталог в internal, имя, байты, происхождение, источник, своё у реализации)] части; GenError — out устарел."""
    fresh = render(ROOT)
    dirs = {"cmd/vectors" if d == "../cmd/vectors" else d for d in PART_DIRS[part] + PART_OWN_DIRS[part]}
    parts = []
    for rel in sorted(fresh):
        if not rel.startswith("go/"):
            continue
        sub_rel = rel[3:].rsplit("/", 1)[0]
        if sub_rel not in dirs:
            continue
        kept = Path(out) / rel
        if not kept.is_file() or kept.read_bytes() != fresh[rel]:
            raise GenError(f"{kept} is stale: run tools/normgen/gen_tests.py")
        data = fresh[rel].replace(KIT_IMPORT.encode(), f'"{module}/internal/'.encode())
        name = rel.rsplit("/", 1)[1]
        sub = "../cmd/vectors" if sub_rel == "cmd/vectors" else sub_rel
        own = sub == "vectoradapter" or rel == "go/coreadapter/open.go"
        parts.append((sub, name, data, "generated", str(kept.relative_to(ROOT)), own))
    return parts


KIT_MD = """
## Part `tests`: vector tests and the vector command (generated)

| Package | Import path | Origin |
|---|---|---|
| `vectoradapter` | `{module}/internal/vectoradapter` | **yours**: a generated stub you edit (the kit never overwrites it) |
| `vectortests` | `{module}/internal/vectortests` | generated from `vectors/jcs`, `vectors/rights-evaluator`, `forms/stages.tsv` — Go tests only |
| `vectorcmd` | `{module}/internal/vectorcmd` | generated: the wire of the unified vector command |
| `cmd/vectors` | `{module}/cmd/vectors` | generated: the vector binary, `main` is `vectorcmd.Main` |

### The adapter — `internal/vectoradapter` (you write it), one function per file

```go
// canonical.go (stage jcs):
func Canonical(raw []byte) ([]byte, error)                                    // RFC 8785 text of the JSON text raw
// rights.go (stage rights_eval):
func LoadRights(file []byte) (func(role, action, key string) bool, error)     // rights file → evaluator; action read|write|delete
```

Edit only the file of your stage: for `Canonical` — `canonical.go`, for `LoadRights` — `rights.go`. Never rewrite one
file to change the other and never delete a function: the vector tests and `cmd/vectors` call both, so the build
breaks. Your own code may live in other files or packages. Replace the bodies of the stub with calls of your own code; keep the package path and the signatures. The evaluator
has the type of `writecheck.Check`'s `allowed`. The stub compiles, so `go build` and `go vet` pass from the start; the
tests fail with «not implemented» until you connect your code.

### The tests (`internal/vectortests`)

- `TestJcs_Line<N>` — one per row N of `vectors/jcs/canonical_json.tsv` (stage `jcs`): `Canonical(raw)` is `canonical`
  byte for byte, its sha256 is the third column, and `Canonical(canonical)` is `canonical` again.
- `TestRightsEval_Line<N>` — one per row N of `vectors/rights-evaluator/expect.tsv` (stage `rights_eval`):
  `LoadRights(rights.json)`, then `allowed(role, action, key)` is `expect` (`allow` = true).
- Run one stage: `go test -run '^TestJcs_' ./...`, `go test -run '^TestRightsEval_' ./...`.

### The vector command (`cmd/vectors`, `internal/vectorcmd`)

The kit's own binary `cmd/vectors` is the vector command of all three packages. The profile builds it in `build`
(`go build -o bin/vectors ./cmd/vectors` next to your daemon, artifact `vectors: bin/vectors`); the vector command is
`bin/vectors {input}` (nothing is built during acceptance: the tree is sealed). Your daemon needs no `vectors`
subcommand.

- `vectors:write-checks` (stage `model`) — the kit's checks (`writecheck.Check`), none of your code;
- `vectors:jcs`, `vectors:rights-evaluator` — your adapter `internal/vectoradapter` (`Canonical`, `LoadRights`):
  until you connect it they answer «not implemented».
{common}
"""

COMMON_MD = """
### The common vector packages of the lesson (`Platform/common/vectors`)

The profile maps each of them to the same command: `common/<package>: 'bin/vectors {input}'`. Its tests are
`TestCommon<Package>_Line<N>` (one per row; `go test -run '^TestCommonCrl_' ./...`).

| Package (table) | How it answers | Yours |
|---|---|---|
{rows}

Each adapter file holds one function; its comment says the input and the native answer (code 0, one JSON value).
`common/family-read` needs none of your code: the kit's part `families` reads the row — the tests are green as is.
"""


def kit_md():
    """Справка части vectors: общие пакеты урока — из common_vectors (их состав у урока)."""
    rows = []
    for name, table in common_vectors.composition(L.key):
        d = common_vectors.DECLS[name]
        rows.append(f"| `common/{name}` (`{table}`) | {d['native']} | "
                    + (f"`{d['adapter']}`: `{d['go']}`" if d["adapter"] else "— (the kit's `families`)") + " |")
    return KIT_MD.replace("{common}", COMMON_MD.replace("{rows}", "\n".join(rows)) if rows else "")


KIT_MD_STAGETESTS = """
## Part `stagetests`: stage tests from the scenarios (`internal/stagetests`, `internal/coreadapter`)

`internal/stagetests` — generated from `acceptance/1/scenarios.tsv` and `seams.tsv` by the `tests:` gates of
`forms/stages.tsv` (ADR-0125 addenda (3), (4); ADR-0126 addendum (7)): one test `Test<Stage>_<Scenario>` per scenario,
its steps are subtests in order on one core; the comparison is the runner's (status, the body by value with `$names`
bound, `ASSERT`). `inventory.tsv` lists every step: translated or excluded with the reason; `race yes` — the test has
`@parallel` and is judged with `-race`. Run one stage: `go test -run '^TestStoreCore_' ./internal/stagetests`. Your own
tests with the same prefix do not close a stage: the judge runs only `internal/stagetests` by its inventory.

The kit's `coreadapter.go`: `Config`, `Call`, `Core`, `Handle` (the body limit — 413 before the route,
`apidoor.Route`, `apidoor.Dispatch` to your Core, `apidoor.Encode`) and `NotInStage`. Yours — `open.go`:

```go
type Ctx = *coreadapter.Request          // or your own type: what Context gives each request
func Open(cfg Config) (Core, error)      // a fresh core: your store in cfg.DataDir, clock cfg.Now, rights cfg.Rights
type Config struct {
    BodyLimit, RowCeiling int64          // the stand: 1048576, 524288
    Rights  []byte                       // the role acc with read, write, delete on acc/*
    Now     func() time.Time             // take every time of the core from it
    DataDir string                       // fresh per scenario; @reopen opens the same directory again
}
type Core interface {                    // your value
    apidoor.Handler[Ctx]                 // Get, List, Write, QueryRefused — your core of Н3; embed coreadapter.NotInStage
                                         // for Rights, Status, Join, Leave, Metrics (503 «not in this stage»)
    Context(call Call, header map[string]string) Ctx // Call{Sock}: "acc" — the role socket, "admin" — admin.sock
    Close()
}
```

`Handle` may be called concurrently (`@parallel`): the core must hold that. The seams of `seams.tsv`: `@clock ±N` —
the test clock moves N seconds, N decimal (`+0.25`, `-100.125`; from 2000000000 at the first Open): `cfg.Now()` carries
the fraction — never truncate it to whole seconds, keep it in what you store and compare, `@reopen` — Close and Open on the same DataDir and
clock (what was written must read back), `@parallel K` — the next request K times at once.
"""


def counts(root=ROOT):
    """→ {пакет: число строк-векторов} — для отчёта и сверки покрытия."""
    return {"jcs": len(read_jcs(root)[0]), "rights-evaluator": len(read_rights(root)[0])}


def generate(root=ROOT, out=DEFAULT_OUT):
    out = Path(out)
    files = render(root)
    for sub in ("go/vectoradapter", "go/vectortests", "go/vectorcmd", "go/cmd/vectors", "go/stagetests", "go/coreadapter",
                "vectors"):
        target = out / sub
        if target.exists():
            for p in sorted(target.rglob("*"), reverse=True):
                p.unlink() if p.is_file() else p.rmdir()
            target.rmdir()
    for rel, data in files.items():
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_bytes(data)
    if not (out / "go/go.mod").exists():
        (out / "go/go.mod").write_text(f"module {GO_MODULE}\n\ngo 1.22\n", encoding="utf-8")
    return files


def main(argv):
    root = Path(argv[1]) if len(argv) > 1 else ROOT
    out = Path(argv[2]) if len(argv) > 2 else DEFAULT_OUT
    try:
        files = generate(root, out)
        n = counts(root)
    except GenError as exc:
        print(f"gen_tests: {exc}", file=sys.stderr)
        return 1
    print(f"gen_tests: {len(files)} files in {out}; vectors {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
