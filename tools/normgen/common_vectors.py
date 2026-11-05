"""Общие пакеты векторов урока для части vectors (ADR-0125 доп. (5) п. 5: полный состав урока; у P/01 не было пяти —
crl, revoked, log-mask, store-client, family-read). Модуль генератора № 6 (gen_tests.py): чтение таблиц пакетов,
заготовки адаптера (YOURS, по файлу на функцию), тесты `TestCommon<Пакет>_Line<N>`, ветви единой команды векторов
(vectorcmd), входы и ожидания судьи vector_judge.py.

Состав урока — форма «Спецификации» Platform/common/vectors/consumers.tsv (package, table, lesson, norm): строки урока.
Нативный исход — разделы «Native outcome» README пакетов и общий провод «The unified command of a vector package»:
код 0 и одно значение JSON. family-read исполняет пакет сам — часть families (families.ByKey(...).Judge), не модель.
"""
import json
from pathlib import Path

import vector_consumers

COMMON = "Platform/common/vectors"

# Состав урока — форма «Спецификации» Platform/common/vectors/consumers.tsv (package common/<имя>, table, lesson,
# norm; ADR-0125 доп. (5) п. 5): строки урока по порядку формы. Пакет без объявления DECLS — отказ генератора.
CONSUMERS = f"{COMMON}/consumers.tsv"
CONSUMER_COLUMNS = ["package", "table", "lesson", "norm"]
# Выгрузки до формы (4c101570, 00ab401a — пакеты P/01 -28…-34): прежнее объявление состава P/01 по «Who performs it»
# README; с формой оно не читается (её строки P/01 те же пять — сверено 0c2e519ca).
BEFORE_FORM = {
    "01-store": [("crl", "cases.tsv"), ("revoked", "cases.tsv"), ("log-mask", "cases.tsv"),
                 ("store-client", "cases.tsv"), ("family-read", "01.tsv")],
}

# Пакет → форма таблицы и функция адаптера. header None — таблица без шапки (поля по README); inputs — колонки входа
# провода (cells); files — фикстуры (имя → путь от корня курса); expect — колонка ожидания и её чтение.
DECLS = {
    "crl": dict(header=["case", "input", "expect", "note"], inputs=["input"], files={}, expect="json-or-bad",
                go="CRL", adapter="crl.go",
                native='code 0, one JSON value: the object {ca, ca_next, …} by the form of expect or the string "@bad"',
                doc='''// CRL reads the file crl.pem of the role certificate contract (`revoke`: crl, both, absent) for the input of one
// row of Platform/common/vectors/crl/cases.tsv: input is the JSON object {ca, ca_next, crl, now} (ca, ca_next —
// the PEM of ca.pem and ca.next.pem or null, crl — the content of crl.pem, now — Unix seconds). It returns the JSON
// value of the native outcome (README «Native outcome»): the object {ca, ca_next, …} by the form of the column
// expect (the revoked serials of the leaves of each centre in the canonical notation of the package revoked: lowercase
// hex without leading zeros, ascending by value), or the string "@bad" — the file is wrong, the refusal is closed.
// An error is only «cannot answer» (not implemented), never a refusal of the file.
func CRL(input []byte) (any, error) {
	return nil, errors.New("vectoradapter.CRL: not implemented")
}
'''),
    "revoked": dict(header=["case", "file", "expect", "note"], inputs=["file"], files={}, expect="json-or-bad",
                    go="Revoked", adapter="revoked.go",
                    native='code 0, one JSON value: the array of serials or the string "@bad"',
                    doc='''// Revoked reads the revocation file `revoked` of the role certificate contract (`revoke`: file, bad_file, both,
// absent) for the cell file of one row of Platform/common/vectors/revoked/cases.tsv: a JSON string — the content of
// the file; "@absent" — neither revoked nor crl.pem; an object {revoked, crl} — both files (README). It returns the JSON
// value of the native outcome: the array of the revoked serials by value in the canonical notation (lowercase hex
// without leading zeros, zero — "0", ascending by value, without repeats), or the string "@bad" — the file is wrong
// as a whole. An error is only «cannot answer» (not implemented).
func Revoked(file []byte) (any, error) {
	return nil, errors.New("vectoradapter.Revoked: not implemented")
}
'''),
    "log-mask": dict(tables=("cases.tsv",), header=None, fields=["raw", "masked", "note"], inputs=["raw"],
                     files={"fields.yaml": "Platform/common/vectors/secret-in/fields.yaml"}, expect="string",
                     go="LogMask", adapter="logmask.go",
                     native="code 0, the JSON string of the masked text, compared byte for byte",
                     doc='''// LogMask masks the text raw (a log line, an error, a JSON document, a connection string — as written, not a value
// of a field) by the log mask of the platform (the contract `log-mask`; Platform/common/vectors/log-mask/cases.tsv):
// the credentials of the headers Authorization and Proxy-Authorization, the value of every pair with a secret name
// (`name=value` and a JSON pair) and every address. fields is the bytes of fields.yaml of the vectors secret-in (the
// rules of the catalog for the table; the store daemon itself loads no manifests — its own catalog is empty). It
// returns the masked text; the vectors compare it with masked byte for byte. An error is only «cannot answer».
func LogMask(raw string, fields []byte) (string, error) {
	return "", errors.New("vectoradapter.LogMask: not implemented")
}
'''),
    "store-client": dict(header=["case", "input", "expect", "note"], inputs=["input"], files={}, expect="json",
                         go="StoreClient", adapter="storeclient.go",
                         native="code 0, one JSON string: the outcome of the store client contract",
                         doc='''// StoreClient is the outcome of a store answer for the client (the store client contract «Outcomes and what the
// client does»: outcome, no_reply) for the input of one row of Platform/common/vectors/store-client/cases.tsv: the JSON
// object {op, reply} — op "get" | "list" | "write", reply {status, body} or "@none" (no answer), "@truncated",
// "@refused". It returns the outcome: "row", "absent", "unreadable", "listing", "written" or the kind of the refusal
// ("conflict", "guard", "unavailable", "ambiguous", …). Use the same function your admin_ops client uses on admin.sock.
func StoreClient(input []byte) (string, error) {
	return "", errors.New("vectoradapter.StoreClient: not implemented")
}
'''),
    "family-read": dict(header=["case", "family", "key", "kind", "mode", "who", "text", "verdict", "paths", "outcome",
                                "note"], inputs=["family", "key", "kind", "mode", "who", "text"], files={},
                        expect="family", go=None, adapter=None,
                        native='code 0, the object {"verdict", "paths", "outcome"} (paths and each outcome sorted)'),
}


class CommonError(Exception):
    pass


def camel(name):
    return "".join(w[:1].upper() + w[1:] for w in name.replace("-", " ").split())


def strict(text, where):
    try:
        return json.loads(text)
    except ValueError as exc:
        raise CommonError(f"{where}: not JSON: {exc}") from None


def composition(lesson_key, root=None, known_only=False):
    """[(пакет, таблица)] урока по consumers.tsv; пакет без объявления адаптера — CommonError с его именем (known_only —
    только пакеты DECLS: прочие объявляет генератор урока, gen_vectors.py)."""
    root = Path(root) if root else Path(__file__).resolve().parent.parent.parent
    path = root / CONSUMERS
    if not path.is_file():
        return list(BEFORE_FORM.get(lesson_key, []))
    try:
        assigned = vector_consumers.read(root)
        if lesson_key not in vector_consumers.lessons(root):
            raise vector_consumers.ConsumerError(f"{CONSUMERS}: unknown lesson {lesson_key!r}")
    except vector_consumers.ConsumerError as exc:
        raise CommonError(str(exc)) from None
    out = []
    for (package, table), owners in assigned.items():
        if lesson_key not in owners or not package.startswith("common/"):
            continue                 # own/foreign packages are dispatched by gen_tests/gen_vectors, not these APIs
        name = package[len("common/"):]
        if known_only and name in DECLS and table not in DECLS[name].get("tables", (table,)):
            continue
        if name not in DECLS:
            if known_only:
                continue
            raise CommonError(f"{CONSUMERS}: {package} {table} → {lesson_key}: no declaration of its adapter in "
                              f"tools/normgen/common_vectors.py DECLS")
        out.append((name, table))
    return out


def read(root, name, table):
    """Таблица пакета → (rel, текст, [(строка, {колонка: ячейка})]); форма по DECLS — иначе CommonError."""
    decl = DECLS[name]
    rel = f"{COMMON}/{name}/{table}"
    path = Path(root) / rel
    if not path.is_file():
        raise CommonError(f"no {rel}")
    text = path.read_text(encoding="utf-8")
    rows, header = [], decl["header"]
    seen_header = header is None
    for no, line in enumerate(text.split("\n"), 1):
        if not line or line.startswith("#"):
            continue
        cells = line.split("\t")
        if not seen_header:
            if cells != header:
                raise CommonError(f"{rel}:{no}: header {cells}, want {header}")
            seen_header = True
            continue
        cols = header or decl["fields"]
        if len(cells) != len(cols):
            raise CommonError(f"{rel}:{no}: {len(cells)} cells, want {len(cols)} ({', '.join(cols)})")
        rows.append((no, dict(zip(cols, cells))))
    if not rows:
        raise CommonError(f"{rel}: no vectors")
    return rel, text, rows


def expected(name, row, where):
    """Ожидаемый нативный stdout (значение JSON) строки."""
    kind = DECLS[name]["expect"]
    if kind == "json-or-bad":
        return "@bad" if row["expect"] == "@bad" else strict(row["expect"], f"{where}: expect")
    if kind == "json":
        return strict(row["expect"], f"{where}: expect")
    if kind == "string":
        return row["masked"]
    paths = strict(row["paths"], f"{where}: paths")
    outcome = strict(row["outcome"], f"{where}: outcome")
    if row["mode"] == "reader":
        outcome = {k: sorted(v) for k, v in outcome.items()}
    return {"verdict": row["verdict"], "paths": sorted(paths), "outcome": outcome}


def fixtures(root, name):
    out = {}
    for fname, rel in DECLS[name]["files"].items():
        p = Path(root) / rel
        if not p.is_file():
            raise CommonError(f"no fixture {rel}")
        out[fname] = (rel, p.read_bytes())
    return out


ADAPTER_HEAD = '''// Generated by tools/normgen/gen_tests.py (ADR-0125 № 6, ADR-0125 addendum (5) item 5: a common vector package of
// the lesson). YOURS from here: the kit puts this file once and never overwrites it — edit it.

package vectoradapter

import "errors"

'''


def adapters(lesson_key, known_only=False, root=None):
    """{имя файла vectoradapter: текст Go} заготовок общих пакетов урока (без family-read — его исполняет пакет)."""
    return {DECLS[n]["adapter"]: ADAPTER_HEAD + DECLS[n]["doc"] for n, _ in composition(lesson_key, root=root, known_only=known_only)
            if DECLS[n]["adapter"]}


def uses_families(lesson_key):
    return any(n == "family-read" for n, _ in composition(lesson_key, known_only=True))


# Ветви единой команды (vectorcmd.run): value — нативное значение JSON.
VECTORCMD = {
    "crl": '''	case %(key)s:
		v, err := vectoradapter.CRL([]byte(cell("input")))
		if err != nil {
			return 1, nil, []byte("CRL: " + err.Error() + "\\n"), nil
		}
		value = v
''',
    "revoked": '''	case %(key)s:
		v, err := vectoradapter.Revoked([]byte(cell("file")))
		if err != nil {
			return 1, nil, []byte("Revoked: " + err.Error() + "\\n"), nil
		}
		value = v
''',
    "log-mask": '''	case %(key)s:
		m, err := vectoradapter.LogMask(cell("raw"), files["fields.yaml"])
		if err != nil {
			return 1, nil, []byte("LogMask: " + err.Error() + "\\n"), nil
		}
		value = m
''',
    "store-client": '''	case %(key)s:
		o, err := vectoradapter.StoreClient([]byte(cell("input")))
		if err != nil {
			return 1, nil, []byte("StoreClient: " + err.Error() + "\\n"), nil
		}
		value = o
''',
    "family-read": '''	case %(key)s:
		v, err := familyRead(cell("family"), cell("key"), cell("kind"), cell("mode"), cell("who"), cell("text"))
		if err != nil {
			return 1, nil, []byte("family-read: " + err.Error() + "\\n"), nil
		}
		value = v
''',
}

FAMILY_READ_GO = '''
// familyRead — a row of common/family-read by the kit's part families (the schemas of the catalog, the kit's code):
// {verdict, paths, outcome}, the paths and the outcome of each role sorted (the runner compares them as sets).
func familyRead(family, key, kind, mode, whoText, text string) (any, error) {
	f := families.ByKey(family)
	if f == nil {
		return nil, fmt.Errorf("no family %q in package families", family)
	}
	if kind != f.Kind {
		return nil, fmt.Errorf("family %q is of kind %q, the row says %q", family, f.Kind, kind)
	}
	var who []string
	if err := json.Unmarshal([]byte(whoText), &who); err != nil {
		return nil, fmt.Errorf("who: %v", err)
	}
	var m families.Mode
	switch mode {
	case "writer":
		m = families.Writer
	case "reader":
		m = families.Reader
	default:
		return nil, fmt.Errorf("mode %q, want writer or reader", mode)
	}
	var r families.Result
	if jt, ok := any(f).(interface {
		JudgeText(string, []byte, families.Mode) families.Result
	}); ok && f.Kind != "row" {
		r = jt.JudgeText(key, []byte(text), m) // object, file (the schema mode)
	} else {
		r = f.Judge(key, families.ParseItems([]byte(text)), m)
	}
	paths := append([]string{}, r.Paths...)
	sort.Strings(paths)
	var outcome any = []string{}
	if m == families.Reader {
		byRole := map[string][]string{}
		for _, role := range who {
			o := append([]string{}, f.OutcomesFor(r.Paths, role)...)
			sort.Strings(o)
			byRole[role] = o
		}
		outcome = byRole
	}
	return map[string]any{"verdict": r.Verdict, "paths": paths, "outcome": outcome}, nil
}
'''

TESTS_HELPERS = '''
import (
	"encoding/json"
	"fmt"
	"reflect"
	"testing"

	"%(module)s/vectorcmd"
)

// sameJSON — got (any JSON-able value) equals want (a JSON text) by value.
func sameJSON(t *testing.T, what string, got any, want string) {
	t.Helper()
	b, err := json.Marshal(got)
	if err != nil {
		t.Fatalf("%%s: the answer is not JSON: %%v", what, err)
	}
	var g, w any
	if err := json.Unmarshal(b, &g); err != nil {
		t.Fatalf("%%s: %%v", what, err)
	}
	if err := json.Unmarshal([]byte(want), &w); err != nil {
		t.Fatalf("%%s: the expectation: %%v", what, err)
	}
	if !reflect.DeepEqual(g, w) {
		t.Fatalf("%%s\\n got %%s\\nwant %%s", what, b, want)
	}
}

// safe — the adapter call with a panic as an error.
func safe(f func() (any, error)) (v any, err error) {
	defer func() {
		if r := recover(); r != nil {
			v, err = nil, fmt.Errorf("panic: %%v", r)
		}
	}()
	return f()
}

// commonWire — one row through the kit's vector command (vectorcmd.Run — the wire of the runner): code 0, stdout want.
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
	sameJSON(t, "family-read", v, want)
}
'''

TEST_CALL = {
    "crl": 'func() (any, error) { return vectoradapter.CRL([]byte(%(input)s)) }',
    "revoked": 'func() (any, error) { return vectoradapter.Revoked([]byte(%(file)s)) }',
    "store-client": 'func() (any, error) { return vectoradapter.StoreClient([]byte(%(input)s)) }',
    "log-mask": 'func() (any, error) { return vectoradapter.LogMask(%(raw)s, []byte(%(fixture)s)) }',
}


def go_tests(lesson_key, root, go_str, head, module, known_only=False):
    """{имя файла vectortests: текст Go} — по тесту на строку общих пакетов урока; head(rel) — шапка с sha источника."""
    comp = composition(lesson_key, root, known_only)
    if not comp:
        return {}
    files = {"common_test.go": head(None) + "\npackage vectortests\n" + TESTS_HELPERS % {"module": module}}
    for name, table in comp:
        rel, text, rows = read(root, name, table)
        prefix = f"TestCommon{camel(name)}_Line"
        fx = fixtures(root, name)
        var = f"{camel(name)[0].lower() + camel(name)[1:]}Fixture"
        out = [head(rel, *[r for r, _ in fx.values()]), "\npackage vectortests\n"]
        if DECLS[name]["adapter"]:
            out.append(f'\nimport (\n\t"testing"\n\n\t"{module}/vectoradapter"\n)\n')
        else:
            out.append('\nimport "testing"\n')
        for no, row in rows:
            want = json.dumps(expected(name, row, f"{rel}:{no}"), ensure_ascii=False, separators=(",", ":"))
            out.append((f"\n// {rel}:{no} {row.get('case', '')}").rstrip() + f"\nfunc {prefix}{no}(t *testing.T) {{\n")
            if not DECLS[name]["adapter"]:
                doc = {"format": 1, "package": f"common/{name}", "table": table, "case": f"line-{no}", "variant": "",
                       "cells": {c: row[c] for c in DECLS[name]["inputs"]}, "files": {}}
                out.append(f"\tcommonWire(t, {go_str(json.dumps(doc, ensure_ascii=False))}, {go_str(want)})\n}}\n")
                continue
            args = {c: go_str(row[c]) for c in DECLS[name]["inputs"]}
            args["fixture"] = var
            call = TEST_CALL[name] % args
            out.append(f"\tgot, err := safe({call})\n\tif err != nil {{\n\t\tt.Fatalf(\"{DECLS[name]['go']}: %v\", err)\n\t}}\n"
                       f"\tsameJSON(t, {go_str(f'{rel}:{no}')}, got, {go_str(want)})\n}}\n")
        for fname, (frel, data) in fx.items():
            out.append(f"\n// {var} — {frel} byte for byte.\nvar {var} = {go_str(data.decode('utf-8'))}\n")
        files[f"common_{name.replace('-', '_')}_test.go"] = "".join(out)
    return files


def wire_rows(lesson_key, root, known_only=False):
    """[(пакет, таблица, rel, текст, [(строка, cells, files, ожидание JSON одной строкой)])] — входы команды векторов."""
    out = []
    for name, table in composition(lesson_key, root, known_only):
        rel, text, rows = read(root, name, table)
        fx = fixtures(root, name)
        items = []
        for no, row in rows:
            items.append((no, {c: row[c] for c in DECLS[name]["inputs"]}, {f: d for f, (_, d) in fx.items()},
                          json.dumps(expected(name, row, f"{rel}:{no}"), ensure_ascii=False, separators=(",", ":"))))
        out.append((name, table, rel, text, items, [r for r, _ in fx.values()]))
    return out
