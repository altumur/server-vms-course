"""Generate a refusal catalog without a model (ADR-0125 generator 4).

Read refusals.tsv columns chapter, row, name, surface, code, kind, fields, headers, log, norm under a comment header. Emit standard-library Go 1.22 go/refusals/refusals.go with a CamelCase *Spec per row, All, ByName, Check, LogLine and Exit.

Responsibilities remain separate (addendum(1), item 5): OpenAPI *Fault defines body shape and the door encodes it; this table defines catalog metadata; write-checks.tsv defines write-command conditions/order. This package supplies status, kind, fields, headers and validates the field set without encoding bodies. Reasons and caller behavior remain N4 prose and are not interpreted.

  python tools/normgen/gen_refusals.py [table.tsv [output-directory]]"""
import hashlib
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

from gen_checks import GenError, camel, go_str, gofmt  # noqa: E402

import lesson  # noqa: E402 -- lesson selection (ADR-0125 addendum (5), item 2)
L = lesson.CURRENT
DEFAULT_TABLE = L.form("refusals.tsv")
DEFAULT_OUT = L.out
COLUMNS = ["chapter", "row", "name", "surface", "code", "kind", "fields", "headers", "log", "norm"]
KIT_DIRS = ("refusals",)
JUDGE = HERE / "refusal_judge.py"
EXIT_ANY = 1          # exit !0 means any nonzero code; the kit returns1.


class Table:
    def __init__(self, text, name="refusals.tsv"):
        self.name = name
        self.sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
        body = [line for line in text.splitlines() if not line.startswith("#")]
        if not body or body[0].split("\t") != COLUMNS:
            raise GenError(f"{name}: columns must be {COLUMNS}")
        self.rows, seen = [], set()
        for k, line in enumerate(body[1:], 2):
            cells = line.split("\t")
            if len(cells) != len(COLUMNS):
                raise GenError(f"{name}: line {k}: {len(cells)} cells, expected {len(COLUMNS)}")
            r = dict(zip(COLUMNS, cells))
            where = f"{name}: {r['name']}"
            if not re.fullmatch(r"[a-z][a-z0-9_]*", r["name"]) or r["name"] in seen:
                raise GenError(f"{where}: name — snake_case, unique")
            seen.add(r["name"])
            if not re.fullmatch(r"[0-9]+\.[0-9]+", r["chapter"]) or not re.fullmatch(r"[1-9][0-9]*", r["row"]):
                raise GenError(f"{where}: chapter {r['chapter']!r} / row {r['row']!r}")
            r["row"] = int(r["row"])
            s = r["surface"]
            if s == "http":
                if not re.fullmatch(r"[1-5][0-9]{2}", r["code"]) or not re.fullmatch(r"[a-z]+", r["kind"]):
                    raise GenError(f"{where}: an http row has a code NNN and a kind")
                r["status"] = int(r["code"])
            elif s in ("start", "cli"):
                if r["kind"] != "-" or r["fields"] != "-" or r["headers"] != "-":
                    raise GenError(f"{where}: a {s} row has no kind, fields, headers (-)")
                if r["code"] == "exit 2":
                    r["status"] = 2
                elif r["code"] == "exit !0":
                    r["status"] = EXIT_ANY
                else:
                    raise GenError(f"{where}: code {r['code']!r} — exit 2 or exit !0")
            else:
                raise GenError(f"{where}: surface {s!r} — http, start, cli")
            r["field_list"] = []
            if r["fields"] != "-":
                for f in r["fields"].split(","):
                    m = re.fullmatch(r"([a-z][a-z_]*)(\??)", f)
                    if not m or m[1] in ("kind", "error") or m[1] in [x for x, _ in r["field_list"]]:
                        raise GenError(f"{where}: field {f!r} — a name, ? for optional, not kind or error, no repeats")
                    r["field_list"].append((m[1], bool(m[2])))
            r["header_list"] = []
            if r["headers"] != "-":
                for h in r["headers"].split(";"):
                    m = re.fullmatch(r"\s*([A-Za-z][A-Za-z0-9-]*): (\S.*?)\s*", h)
                    if not m:
                        raise GenError(f"{where}: header {h!r} — Name: value")
                    r["header_list"].append((m[1], m[2]))
            r["log_names"], r["log_words"] = [], []
            if r["log"] != "-":
                if s == "http":
                    raise GenError(f"{where}: an http row has no log (-)")
                for item in r["log"].split(","):
                    item = item.strip()
                    if m := re.fullmatch(r"«([^«»]+)»", item):
                        r["log_words"].append(m[1])
                    elif re.fullmatch(r"-?[A-Za-z][A-Za-z ]*", item):
                        r["log_names"].append(item)
                    else:
                        raise GenError(f"{where}: log item {item!r} — a value name or «literal words»")
            r["var"] = camel(r["name"])
            self.rows.append(r)


def go_spec(r):
    fields = ", ".join(f"{{{go_str(n)}, {'true' if o else 'false'}}}" for n, o in r["field_list"])
    headers = ", ".join(f"{{{go_str(n)}, {go_str(v)}}}" for n, v in r["header_list"])
    retry = any(n.lower() == "retry-after" for n, _ in r["header_list"])
    lst = lambda xs: "[]string{" + ", ".join(go_str(x) for x in xs) + "}" if xs else "nil"  # noqa: E731
    return (f"// {r['var']} — {r['chapter']} row {r['row']}: {r['surface']} {r['code']}"
            f"{' ' + r['kind'] if r['kind'] != '-' else ''}; {r['norm']}\n"
            f"var {r['var']} = &Spec{{Chapter: {go_str(r['chapter'])}, Row: {r['row']}, Name: {go_str(r['name'])}, "
            f"Surface: {go_str(r['surface'])}, Code: {r['status']}, "
            f"Kind: {go_str(r['kind'] if r['kind'] != '-' else '')}, "
            f"Fields: {('[]Field{' + fields + '}') if fields else 'nil'}, "
            f"Headers: {('[][2]string{' + headers + '}') if headers else 'nil'}, RetryAfter: {'true' if retry else 'false'}, "
            f"Log: {lst(r['log_names'])}, Words: {lst(r['log_words'])}, Norm: {go_str(r['norm'])}}}")


GO_API = r'''
// Field describes refusal-body fields besides kind/error;Optional represents the table's '?'.
type Field struct {
	Name     string
	Optional bool
}

// Spec is a catalog row.
type Spec struct {
	Chapter    string      // Lesson chapter:1.1, 1.2, 1.3.
	Row        int         // Row within the chapter's N4 catalog.
	Name       string      // Condition name, or write-checks.tsv check name.
	Surface    string      // http door, start daemon, or cli admin command.
	Code       int         // HTTP status or start/CLI exit code(2;!0 maps to1).
	Kind       string      // HTTP kind token;empty on other surfaces.
	Fields     []Field     // HTTP body fields besides kind/error.
	Headers    [][2]string // HTTP response headers.
	RetryAfter bool        // Headers includes Retry-After, for apidoor.Answer.RetryAfter.
	Log        []string    // Start/CLI values named by the log.
	Words      []string    // Start/CLI words carried literally by the log.
	Norm       string
}

// ByName returns a named catalog row, or nil.
func ByName(name string) *Spec { return byName[name] }

// Check requires all mandatory HTTP body fields, no extras, and integer(int/int64) or string values.
// apidoor.Refuse(op, s.Code, s.Kind, msg, values) encodes the OpenAPI *Fault body.
func (s *Spec) Check(values map[string]any) error {
	if s.Surface != "http" {
		return fmt.Errorf("refusal %s: surface %s has no body", s.Name, s.Surface)
	}
	for _, f := range s.Fields {
		if _, ok := values[f.Name]; !ok && !f.Optional {
			return fmt.Errorf("refusal %s: no field %s", s.Name, f.Name)
		}
	}
	for k, v := range values {
		known := false
		for _, f := range s.Fields {
			known = known || f.Name == k
		}
		if !known {
			return fmt.Errorf("refusal %s: field %s is not of the catalogue", s.Name, k)
		}
		switch v.(type) {
		case int, int64, string:
		default:
			return fmt.Errorf("refusal %s: field %s is %T, not an integer or a string", s.Name, k, v)
		}
	}
	return nil
}

// LogLine emits the start/CLI refusal name, literal Words and supplied name=value pairs.
// Values outside Log error;nonempty Log requires at least one supplied value, for example flag/socket.
func (s *Spec) LogLine(values map[string]string) (string, error) {
	if s.Surface == "http" {
		return "", fmt.Errorf("refusal %s: an http refusal has no log line", s.Name)
	}
	parts := []string{s.Name + ":"}
	parts = append(parts, s.Words...)
	given := 0
	for _, n := range s.Log {
		if v, ok := values[n]; ok {
			parts = append(parts, n+"="+strconv.Quote(v))
			given++
		}
	}
	if given != len(values) {
		for k := range values {
			if !contains(s.Log, k) {
				return "", fmt.Errorf("refusal %s: %s is not a value of its log %v", s.Name, k, s.Log)
			}
		}
	}
	if len(s.Log) > 0 && given == 0 {
		return "", fmt.Errorf("refusal %s: the log names none of %v", s.Name, s.Log)
	}
	return strings.Join(parts, " "), nil
}

// Exit logs LogLine and returns s.Code;LogLine errors are logged alongside available information.
func (s *Spec) Exit(logf func(string), values map[string]string) int {
	line, err := s.LogLine(values)
	if err != nil {
		line = s.Name + ": " + err.Error()
	}
	logf(line)
	return s.Code
}

func contains(xs []string, x string) bool {
	for _, y := range xs {
		if y == x {
			return true
		}
	}
	return false
}
'''


def go_module(table, rel):
    parts = [f"// Code generated by tools/normgen/gen_refusals.py from {rel}; DO NOT EDIT.\n"
             f'// Table sha256 {table.sha256}.\n\n'
             r'''// Package refusals implements the P/01.1-P/01.3 N4 catalog(ADR-0125 generator 4).
'''
             "package refusals\n\n"
             'import (\n"fmt"\n"strconv"\n"strings"\n)',
             GO_API.strip("\n")]
    parts += [go_spec(r) for r in table.rows]
    parts.append(r'''// All retains catalog table order.
var All = []*Spec{''' +
                 ", ".join(r["var"] for r in table.rows) + "}")
    parts.append("var byName = map[string]*Spec{" + ", ".join(f"{go_str(r['name'])}: {r['var']}"
                                                              for r in table.rows) + "}")
    return "\n\n".join(parts) + "\n"


# ---------------------------------------------------------------- catalog without HTTP (P/02, 15 columns)

PLAIN_COLUMNS = ["chapter", "row", "name", "surface", "code", "kind", "fields", "headers", "log", "norm", "word",
                 "cause", "outcome", "diagnostic", "caller"]
PLAIN_SURFACES = ("call", "cli", "start", "process", "peer")
# P/05 has ResourceError text bodies: response_schema follows word on the http surface.
RESPONSE_COLUMNS = PLAIN_COLUMNS[:11] + ["response_schema"] + PLAIN_COLUMNS[11:]


class PlainTable:
    """Read closed columns for lessons without a local door (P/02 Refusal catalogue): chapter, row, name, surface, code, word, log, norm. kind/fields/headers are '-'; final prose columns imply no generated behavior."""

    def __init__(self, text, name="refusals.tsv"):
        self.name = name
        self.sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
        body = [line for line in text.splitlines() if line and not line.startswith("#")]
        head = body[0].split("\t") if body else []
        self.response = head == RESPONSE_COLUMNS
        cols = RESPONSE_COLUMNS if self.response else PLAIN_COLUMNS
        if head != cols:
            raise GenError(f"{name}: columns must be {PLAIN_COLUMNS} (or with response_schema after word)")
        schema_defs = response_schemas(definitions=True) if self.response and L.key == "06-console" else {}
        schemas = set(schema_defs) if schema_defs else response_schemas() if self.response else set()
        surfaces = PLAIN_SURFACES + (("http",) if self.response else ())
        body_at = ("peer", "http") if self.response else ("peer",)
        self.rows, seen = [], set()
        for k, line in enumerate(body[1:], 2):
            cells = line.split("\t")
            if len(cells) != len(cols):
                raise GenError(f"{name}: line {k}: {len(cells)} cells, expected {len(cols)}")
            r = dict(zip(cols, cells))
            where = f"{name}: {r['name']}"
            if not re.fullmatch(r"[a-z][a-z0-9_]*", r["name"]) or r["name"] in seen:
                raise GenError(f"{where}: name — snake_case, unique")
            seen.add(r["name"])
            if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", r["chapter"]) or not re.fullmatch(r"[1-9][0-9]*", r["row"]):
                raise GenError(f"{where}: chapter {r['chapter']!r} / row {r['row']!r}")
            r["row"] = int(r["row"])
            if r["surface"] not in surfaces:
                raise GenError(f"{where}: surface {r['surface']!r} — one of {surfaces}")
            if self.response:
                rs = r["response_schema"]
                if rs != "-" and (r["surface"] != "http" or rs not in schemas):
                    raise GenError(f"{where}: response_schema {rs!r} — a components/schemas of the lesson OpenAPI at http, or -")
            if r["kind"] != "-":
                raise GenError(f"{where}: kind is - (no HTTP Fault of the lesson)")
            r["field_list"] = []
            r["optional_fields"] = []
            if r["fields"] != "-":                 # A neighboring door's response fields (P/03 door_token_forbidden:error).
                if r["surface"] not in body_at:
                    raise GenError(f"{where}: fields only at the surface {'/'.join(body_at)} (no HTTP body of the lesson)")
                for field in r["fields"].split(","):
                    match = re.fullmatch(r"([a-z][a-z0-9_]*)(\??)", field.strip())
                    if match is None or match[1] in r["field_list"]:
                        raise GenError(f"{where}: fields {r['fields']!r} — names with one optional suffix and no repeats")
                    if match[2] and not (L.key == "06-console" and self.response and r["surface"] == "http"
                                         and r["response_schema"] != "-"):
                        raise GenError(f"{where}: optional field requires the P/06 HTTP response schema")
                    r["field_list"].append(match[1])
                    if match[2]:
                        r["optional_fields"].append(match[1])
                if schema_defs and r["surface"] == "http" and r["response_schema"] != "-":
                    schema = schema_defs[r["response_schema"]]
                    properties, required = schema.get("properties"), schema.get("required", [])
                    if (not isinstance(properties, dict) or not isinstance(required, list) or
                            any(type(x) is not str for x in required) or len(set(required)) != len(required)):
                        raise GenError(f"{where}: unsupported response schema field roles")
                    if not set(required) <= set(r["field_list"]):
                        raise GenError(f"{where}: required schema fields are missing from fields")
                    for field in r["field_list"]:
                        if field not in properties or ((field in r["optional_fields"]) == (field in required)):
                            raise GenError(f"{where}: field {field} required/optional role differs from response schema")
            r["header_list"] = []
            if r["headers"] != "-":                # A neighboring door's headers (P/03 process_busy:Retry-After).
                if r["surface"] not in body_at:
                    raise GenError(f"{where}: headers only at the surface {'/'.join(body_at)}")
                for h in r["headers"].split(";"):
                    m = re.fullmatch(r"\s*([A-Za-z][A-Za-z0-9-]*): (\S.*?)\s*", h)
                    if not m:
                        raise GenError(f"{where}: header {h!r} — Name: value")
                    r["header_list"].append((m[1], m[2]))
            code = r["code"]
            r["status"], r["exit"], r["any"] = 0, -1, False
            if code == "-":
                pass
            elif m := re.fullmatch(r"exit (0|[1-9][0-9]*)", code):
                r["exit"] = int(m[1])
            elif code == "exit !0":
                r["any"] = True
            elif re.fullmatch(r"[1-5][0-9]{2}", code):
                if r["surface"] not in body_at + ("call",):
                    raise GenError(f"{where}: a numeric outcome code only at the surface {'/'.join(body_at)}/call")
                r["status"] = int(code)
            else:
                raise GenError(f"{where}: code {code!r} — exit N, exit !0, NNN (peer) or -")
            if r["surface"] == "peer" and (r["exit"] >= 0 or r["any"]):
                raise GenError(f"{where}: a peer row has no exit code")
            r["word_any"], r["word_cell"] = [], r["word"]
            if L.key != "02-installer" and r["word"] != "-":    # P/03+: word preserves the normative cell (spec103).
                toks = re.findall(r"`([^`]+)`", r["word"])   # A token may also be a phrase: exact refusal text (P/06.7).
                if toks and re.sub(r"`[^`]+`|,|\s", "", r["word"]) == "":
                    # Quoted tokens form a derived index: one token or named outcomes.
                    r["word"], r["word_any"] = (toks[0], []) if len(toks) == 1 else ("-", toks)
                else:
                    r["word"] = "-"                                # Preserve prose cells without projection.
            if r["word"] != "-" and not r["word"].strip():
                raise GenError(f"{where}: word {r['word']!r} — one token or -")
            r["log_names"], r["log_words"] = [], []
            if r["log"] != "-":
                items = re.findall(r"\s*(«[^«»]*»|[^,«»]+?)\s*(?:,|$)", r["log"])  # Commas inside quoted fragments belong to those fragments.
                for item in items:
                    if m := re.fullmatch(r"«([^«»]+)»", item):
                        r["log_words"].append(m[1])
                    elif item:
                        r["log_names"].append(item)
                    else:
                        raise GenError(f"{where}: an empty log item")
            r["var"] = camel(r["name"])
            self.rows.append(r)
        self.headers = any(r["header_list"] or r["field_list"] for r in self.rows)
        self.optional_fields = any(r["optional_fields"] for r in self.rows)
        self.word_any = L.key != "02-installer"             # P/03+: every row exposes Named and WordCell.
        whole = [r["chapter"] for r in self.rows if "." not in r["chapter"]]
        if whole and len(whole) != len(self.rows):
            raise GenError(f"{name}: chapters of a lesson in one chapter and of chapters NN.K together")


PLAIN_API = r'''
// Spec — a row of the refusal catalogue of the lesson (forms/refusals.tsv; the closed columns only — the prose
// columns cause, outcome, diagnostic, caller stay in the norm).
type Spec struct {
	Chapter string   // the chapter of the lesson: 2.1 … 2.5
	Row     int      // Row of the chapter's N4 catalog;two outcomes of one prose row produce two Specs.
	Name    string   // the condition
	Surface string   // call (a pure procedure), cli (an operator command), start, process (a running process), peer
	Exit    int      // cli, start, process: the exit code fixed by the form; -1 — none fixed (see AnyNonZero)
	AnyNonZero bool  // «exit !0»: any nonzero exit code (2 included) — the code is yours, never 0
	Status  int      // peer/http: the door status; call: a stored outcome code fixed by the form; 0 — none
	Word    string   // a fixed refusal/diagnostic token; "" — none
	Log     []string // the subjects the diagnostic must name; it fixes no stdout/stderr format
	Words   []string // the fixed fragments «…» the diagnostic must carry
	Norm    string
}

// ByName — the row by its name; nil — none.
func ByName(name string) *Spec { return byName[name] }

// ExitCode — the exit code of the refusal: the fixed one, or 1 for «exit !0» (the kit's choice of a nonzero code —
// any nonzero code is the norm); ok false — the form fixes no exit code (call, peer, a «-» code).
func (s *Spec) ExitCode() (code int, ok bool) {
	switch {
	case s.Exit >= 0:
		return s.Exit, true
	case s.AnyNonZero:
		return 1, true
	}
	return 0, false
}
'''


def response_schemas(definitions=False):
    """Return lesson OpenAPI component schema names for response_schema."""
    import yamlsub
    doc = yamlsub.load(L.openapi.read_text(encoding="utf-8"), L.openapi.name)
    schemas = (doc.get("components") or {}).get("schemas") or {}
    return schemas if definitions else set(schemas)


def go_spec_plain(r, headers=False, word_any=False, response=False, optional=False):
    lst = lambda xs: "[]string{" + ", ".join(go_str(x) for x in xs) + "}" if xs else "nil"  # noqa: E731
    return (f"// {r['var']} — {r['chapter']} row {r['row']}: {r['surface']} {r['code']}"
            f"{' ' + r['word'] if r['word'] != '-' else ''}; {r['norm']}\n"
            f"var {r['var']} = &Spec{{Chapter: {go_str(r['chapter'])}, Row: {r['row']}, Name: {go_str(r['name'])}, "
            f"Surface: {go_str(r['surface'])}, Exit: {r['exit']}, AnyNonZero: {'true' if r['any'] else 'false'}, "
            f"Status: {r['status']}, Word: {go_str('' if r['word'] == '-' else r['word'])}, "
            f"Log: {lst(r['log_names'])}, Words: {lst(r['log_words'])}, Norm: {go_str(r['norm'])}"
            + (f", Fields: {lst(r['field_list'])}, Headers: {go_headers(r['header_list'])}" if headers else "")
            + (f", Named: {lst(r['word_any'])}, WordCell: {go_str(r['word_cell'])}" if word_any else "")
            + (f", Response: {go_str('' if r['response_schema'] == '-' else r['response_schema'])}" if response else "")
            + (f", OptionalFields: {lst(r['optional_fields'])}" if optional and r["optional_fields"] else "") + "}")


def go_headers(hs):
    return "[][2]string{" + ", ".join(f"{{{go_str(n)}, {go_str(v)}}}" for n, v in hs) + "}" if hs else "nil"


def plain_api(table):
    """Generate catalog API with byte-identical P/02 output; chapter and Headers follow the table."""
    api = PLAIN_API.strip("\n")
    chapters = list(dict.fromkeys(r["chapter"] for r in table.rows))
    if L.key != "02-installer":
        api = api.replace("// the chapter of the lesson: 2.1 … 2.5",
                          "// the chapter of the lesson: " + (" … ".join([chapters[0], chapters[-1]])
                                                               if len(chapters) > 1 else chapters[0]))
    if table.headers:
        api = api.replace("\tNorm    string\n}", "\tNorm    string\n\tFields  []string    // peer: the HTTP body fields of the imported door's "
                          "answer fixed by the form; nil — none\n\tHeaders [][2]string // peer: the headers of the imported door's "
                          "answer fixed by the form; nil — none\n}", 1)
    if table.response:
        api = api.replace("\n}", "\n\tResponse string // http: the components/schemas of the body in the lesson OpenAPI; \"\" — "
                          "no body or text\n}", 1)
        api = api.replace("// call (a pure procedure), cli (an operator command), start, process (a running process), peer",
                          "// call (a pure procedure), cli, start, process, peer, http (the lesson's own door)", 1)
        api = api.replace("// peer: the HTTP status of the peer's door (its owner is another lesson); 0 — none",
                          "// http, peer: the HTTP status (peer — the imported door); 0 — none", 1)
    if table.optional_fields:
        api = api.replace("\n}", "\n\tOptionalFields []string // Explicit optional names; other Fields are required by the response schema.\n}", 1)
    if table.word_any:
        api = api.replace("\n}", "\n\tNamed   []string // the named outcomes the word cell lists (two or more `…`): a "
                          "catalogue index — which applies is the norm's, not «any of»\n\tWordCell string  // the "
                          "word cell of the norm as it is (\"-\" — none); Word and Named only index it\n}", 1)
        api = api.replace("// the subjects the diagnostic must name; it fixes no stdout/stderr format",
                          "// the log cell: the subjects or the diagnostic index of the row; no log line format", 1)
    return api


def go_module_plain(table, rel):
    parts = [f"// Code generated by tools/normgen/gen_refusals.py from {rel}; DO NOT EDIT.\n"
             f'// Table sha256 {table.sha256}.\n\n'
             f"// Package refusals — the refusal catalogue of {L.code} (ADR-0125 № 4, addendum (5)): no HTTP body of the lesson.\n"
             "package refusals",
             plain_api(table)]
    parts += [go_spec_plain(r, table.headers, table.word_any, table.response, table.optional_fields) for r in table.rows]
    parts.append("// All — the rows of the catalogue in the order of the table.\nvar All = []*Spec{" +
                 ", ".join(r["var"] for r in table.rows) + "}")
    parts.append("var byName = map[string]*Spec{" + ", ".join(f"{go_str(r['name'])}: {r['var']}"
                                                              for r in table.rows) + "}")
    return "\n\n".join(parts) + "\n"


def _check_table_owner(table_path):
    """Canonical physical tables must match the process's selected lesson."""
    platform = next((p for p in table_path.parents if p.name == "Platform"), None)
    if platform is None:
        return  # Standalone fixture tables retain their explicitly selected process context.
    registry = platform / "lessons.tsv"
    try:
        rows = [line.split("\t") for line in registry.read_text(encoding="utf-8").splitlines()
                if line and not line.startswith("#")]
    except OSError as exc:
        raise GenError(f"{table_path}: cannot establish lesson ownership: {exc}") from None
    owner = table_path.relative_to(platform).parts[0]
    matches = [row for row in rows if len(row) >= 4 and row[1] == owner]
    if len(matches) != 1 or matches[0][0] != owner[:2]:
        raise GenError(f"{table_path}: no unique lesson owner in {registry}")
    if owner != L.key:
        raise GenError(f"{table_path}: owned by {owner}, selected {L.key}; use --lesson {owner}")


def render(table_path=DEFAULT_TABLE):
    table_path = Path(table_path).resolve()
    _check_table_owner(table_path)
    try:
        rel = table_path.relative_to(ROOT).as_posix()
    except ValueError:
        rel = table_path.name
    text = table_path.read_text(encoding="utf-8")
    head = next((ln for ln in text.splitlines() if ln and not ln.startswith("#")), "")
    if head.split("\t") in (PLAIN_COLUMNS, RESPONSE_COLUMNS):  # Lesson without a local door (P/02) or with a text body (P/05).
        return {"refusals.go": gofmt(go_module_plain(PlainTable(text, table_path.name), rel))}
    table = Table(text, table_path.name)
    return {"refusals.go": gofmt(go_module(table, rel))}


def generate(table_path=DEFAULT_TABLE, out=DEFAULT_OUT):
    files = render(table_path)
    gdir = Path(out) / "go/refusals"
    gdir.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (gdir / name).write_text(text, encoding="utf-8")
    mod = Path(out) / "go/go.mod"                     # Lesson output module; gen_tests writes it for P/01.
    if not mod.exists():
        mod.write_text(f"module {L.go_module}\n\ngo 1.22\n", encoding="utf-8")
    return gdir


def kit_files(out=DEFAULT_OUT):
    """Return [(internal directory, name, bytes, origin, source)]; stale output raises GenError."""
    files = []
    for name, text in sorted(render().items()):
        kept = Path(out) / "go/refusals" / name
        if not kept.is_file() or kept.read_text(encoding="utf-8") != text:
            raise GenError(f"{kept} is stale: run tools/normgen/gen_refusals.py")
        files.append(("refusals", name, kept.read_bytes(), "generated", L.output_source(kept, out)))
    return files


def provenance():
    """Part provenance (ADR-0125 addendum (1), item 6(a)): form, generator and judge with paths/SHA256."""
    import tsv_input

    def entry(path):
        return {"path": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    paths = tsv_input.source_files(DEFAULT_TABLE, root=ROOT)
    if tsv_input.read(DEFAULT_TABLE, root=ROOT).columns == tuple(RESPONSE_COLUMNS):
        paths.append(L.openapi)
    return {"form": [entry(p) for p in dict.fromkeys(paths)], "generator": entry(Path(__file__).resolve()),
            "generators": [entry(Path(__file__).resolve()), entry(Path(tsv_input.__file__))], "judge": entry(JUDGE)}


KIT_MD = """
## Part `refusals`: the refusal catalogue (generated from `forms/refusals.tsv`)

| Package | Import path | Origin |
|---|---|---|
| `refusals` | `{module}/internal/refusals` | generated from `Platform/01-store/forms/refusals.tsv` (N4 of chapters 1.1–1.3) |

One `*refusals.Spec` per row, named after the row (`refusals.KeyRules`, `refusals.ConnectionLimit`,
`refusals.StartFlags`, …); `refusals.All`, `refusals.ByName(name)`.

```go
type Spec struct {
    Chapter string; Row int; Name string
    Surface string      // "http" (a door), "start" (the daemon start), "cli" (an administrative command)
    Code int            // http — the HTTP status; start, cli — the exit code (2; «non-zero» — 1)
    Kind string         // http — the wire kind
    Fields []Field      // http — the fields besides kind and error; Field{Name string; Optional bool}
    Headers [][2]string // http — the headers of the answer
    RetryAfter bool     // Headers carry Retry-After
    Log, Words []string // start, cli — the values the log names, the words it carries literally
    Norm string
}
func (s *Spec) Check(values map[string]any) error                // http: the field set of the body
func (s *Spec) LogLine(values map[string]string) (string, error) // start, cli: the log line
func (s *Spec) Exit(logf func(string), values map[string]string) int // logs LogLine, returns Code
```

- An http refusal: pick the row by its condition (the names are the conditions of N4; the rows of the write command
  carry the names of `write-checks.tsv` checks), then with part `door`:
  `a, err := apidoor.Refuse(op, s.Code, s.Kind, msg, values)`; `a.RetryAfter = s.RetryAfter`. `Check(values)` first if
  you want the catalogue to judge the fields; the door judges the body against the OpenAPI `*Fault`.
- A start refusal: `os.Exit(refusals.StartFlags.Exit(log.Print, map[string]string{"flag": r.Flag}))` (with part
  `flags`: `r` is the `*flags.Refusal`).
- The catalogue says the code, the kind, the fields, the header and what the log names — not when a refusal happens:
  the conditions in words are the prose of N4, the write command order is `write-checks.tsv` (part `writecheck`).
"""


KIT_MD = KIT_MD.replace("Platform/01-store/", L.rel + "/")      # Lesson paths; other text describes P/01.

KIT_MD_PLAIN = """
## Part `refusals`: the refusal catalogue (generated from `forms/refusals.tsv`; the lesson has no HTTP door)

| Package | Import path | Origin |
|---|---|---|
| `refusals` | `{module}/internal/refusals` | generated from the closed columns of `forms/refusals.tsv`; closed |

```go
type Spec struct {
    Chapter, Name, Surface string // surface: call | cli | start | process | peer
    Row        int
    Exit       int      // the exit code the form fixes; -1 — none
    AnyNonZero bool     // «exit !0»: any nonzero code (yours), never 0
    Status     int      // peer: the HTTP status of the other lesson's door
    Word       string   // a fixed refusal/diagnostic token, "" — none
    Log, Words []string // the subjects and «fragments» the diagnostic names; no stdout/stderr format
    Norm       string
}
var All []*Spec; func ByName(name string) *Spec
func (s *Spec) ExitCode() (code int, ok bool) // the fixed code, 1 for «exit !0» (the kit's choice), ok false — none fixed
```

The prose of a row (its cause, outcome, diagnostic and caller action) stays in the norm (`norm`): read it there; the
package carries only what the form fixes.
"""


def kit_md():
    """Use KIT_MD_PLAIN for a15-column catalog without a door (P/02), otherwise P/01 HTTP catalog documentation."""
    head = next((x for x in DEFAULT_TABLE.read_text(encoding="utf-8").splitlines() if x and not x.startswith("#")), "")
    return KIT_MD_PLAIN if head.split("\t") == PLAIN_COLUMNS else KIT_MD


def main(argv):
    table = argv[1] if len(argv) > 1 else DEFAULT_TABLE
    out = argv[2] if len(argv) > 2 else DEFAULT_OUT
    try:
        print(generate(table, out))
    except GenError as exc:
        print(f"gen_refusals: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
