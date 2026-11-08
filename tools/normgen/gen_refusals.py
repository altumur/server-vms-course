r"""Generate refusal catalogue metadata from TSV (ADR-0125 generator 4).

The exact ordered columns select the executable layout (ADR-0125(6)/(8)/(9)).
All 15-column catalogues share one API, including P/02, P/03 and P/04.
Question-mark markers declare optional fields; lesson names select physical
ownership/schema context, never a refusal metadata layout.
The catalogue encodes declared metadata, not when to refuse. OpenAPI owns body
schemas/encoding; write-checks.tsv owns write-command checks and ordering. Prose
cause/outcome/diagnostic/caller cells are not executed or used to choose behavior.

Invocation and context
----------------------
  python tools/normgen/gen_refusals.py [--lesson NN-name] [table.tsv [output-dir]]

One lesson is selected at import: --lesson overrides NORMGEN_LESSON, otherwise
01-store. Its key/number/process come from ROOT/Platform/lessons.tsv. The selected
key determines default forms/refusals.tsv, OpenAPI and output module context:
NORMGEN_OUT/p01-1 for P/01, NORMGEN_OUT/pNN otherwise; module normgen/p01-1 or
normgen/pNN. NORMGEN_OUT is an external root managed by lesson.py, never Git out.
Positional arguments replace table and output paths; they do not rebind L.
render(table) returns {"refusals.go": formatted Go text}; generate(table,out)
writes out/go/refusals/refusals.go, and out/go/go.mod only if it is absent.
Generation renders/validates before creating its destination. main reports a
GenError to stderr and returns 1; success prints the generated directory.

The input path is physically resolved before reading. If it is under a directory
named Platform, that directory's lessons.tsv must uniquely register its first
path component, with a number equal to the component's first two characters.
That owner must equal the selected lesson; otherwise refuse with the required
--lesson value. A symlink cannot relabel the physical owner. Missing/ambiguous
ownership fails; a standalone fixture outside Platform retains selected context.
Ownership/provenance and schema paths are context, not a column-layout selector.

Input and common emission
--------------------------
Read UTF-8 text with Python read_text newline handling. Use literal TAB-separated
cells, without CSV quoting, escaping or cell-json decoding. Lines beginning with
# are comments. The first nonempty noncomment line selects the exact ordered
15- or 16-column layout below; otherwise the 10-column parser must accept it.
No reordered, missing or extra columns are accepted. The 10-column parser does
not discard empty lines; the other parser does. Table SHA256 is the UTF-8 encoding
of the decoded/newline-normalized input text, including comments, not necessarily
the raw on-disk byte digest. Emit the source path relative to ROOT when possible,
otherwise its basename, and this digest in comments. gofmt formats the result.

Every cell starts as a string. A name is unique and matches [a-z][a-z0-9_]*;
its Go variable is underscore-separated parts with their first letters uppercased
and concatenated (api_error -> ApiError, no initialism dictionary). The emitter
does not separately check collisions between distinct names with the same Go
spelling. Each row produces var CamelName = &Spec{...}; exported All []*Spec
preserves input order, and ByName(string) *Spec indexes the original name or
returns nil. No row/name sorting or inference from chapter prose occurs. Row is
a positive decimal without leading zero, converted to Go int. Chapter remains a
string. Norm is copied verbatim without interpreting or checking its reference.
Empty emitted lists use nil; otherwise preserve list order. Go string literals
escape quote/backslash and C0/DEL controls, retaining other Unicode characters.

Five emission cases/capabilities (the former P/02-only shape is removed)
------------------------------------------------------------------------
1. Ten-column P/01 catalogue:
   chapter,row,name,surface,code,kind,fields,headers,log,norm

   Chapter matches digits.digits. Surface is http, start or cli. At http, code is
   a three-digit 100..599 status and kind is nonempty lowercase letters; log=-.
   At start/cli, kind/fields/headers must be -, and code is exactly exit 2 or
   exit !0. Convert exit !0 to Code=1 (one chosen nonzero result, not a promise
   that the norm requires precisely 1). Convert exit 2 to Code=2; HTTP code to
   its integer. Kind is empty at non-HTTP surfaces.

   Fields is - or comma-separated names matching [a-z][a-z_]* with optional ?;
   no repeated names or kind/error entries. Remove ? and retain its Boolean role.
   Headers is - or semicolon-separated Name: value entries; names match
   [A-Za-z][A-Za-z0-9-]*, values are nonempty, surrounding entry whitespace is
   stripped. RetryAfter is true if any header name case-insensitively equals
   Retry-After. Header values are copied, not interpreted as deadlines.
   Non-HTTP log is - or comma-separated, trimmed items: «nonempty fragment» ->
   Words; otherwise an optional minus followed by letters/spaces starting with
   a letter -> Log. This parser splits commas even inside quoted fragments.

   Exact Go shape:
     type Field struct { Name string; Optional bool }
     type Spec struct {
       Chapter string; Row int; Name, Surface string; Code int; Kind string
       Fields []Field; Headers [][2]string; RetryAfter bool
       Log, Words []string; Norm string
     }
   Check(map[string]any) error applies only to http: require every nonoptional
   listed field, prohibit unknown fields, allow only int/int64/string values.
   It does not validate full OpenAPI schemas or include implicit kind/error.
   LogLine(map[string]string)(string,error) rejects http, starts with name+":",
   appends Words then present Log entries in declared order as name=quoted-value;
   unknown supplied names fail, and nonempty Log requires at least one supplied
   value, not all values. Exit(func(string),map[string]string) int logs LogLine
   (or name+": "+its error on failure) and returns Code. No IO/exit is performed.

2. Common fifteen-column catalogue:
   chapter,row,name,surface,code,kind,fields,headers,log,norm,word,
   cause,outcome,diagnostic,caller

   Chapter is digits or digits.digits; do not mix whole-lesson and dotted forms
   in one table. A plain catalogue must contain at least one row. Surface is
   call, cli, start, process or peer; kind must be -. Code - -> Exit=-1,
   AnyNonZero=false, Status=0; exit N (0 or a positive decimal without leading
   zero) -> Exit=N; exit !0 -> Exit=-1, AnyNonZero=true, Status=0. A three-digit
   100..599 code -> Status, permitted at call or peer (also http in case 4).
   A peer row cannot have an exit code. No integer upper bound is separately
   imposed before emission. Other code spellings fail.

   WordCell preserves the exact word cell, including -. Derive an index only
   when a non-- cell consists of one or more nonempty backtick-delimited tokens
   plus commas/whitespace: one token -> Word=token, Named=nil; two or more ->
   Word="", Named=the ordered tokens. Tokens may contain spaces and repeat.
   All other/unquoted prose (including empty/whitespace-only cells) -> Word="",
   Named=nil, while WordCell preserves it. A raw - likewise gives Word="" and
   Named=nil. This is an index, not an alternative-outcome selector or permission
   to accept any named result. No lesson-specific literal-word path remains.

   Log is - or captured comma-separated items, with commas inside fragments
   retained: regex whitespace*(«[^«»]*»|[^,«»]+?)whitespace*(comma|end). Nonempty
   quoted captures become Words without quotes; other nonempty captures become
   Log labels. A captured empty item fails. These are metadata labels/fragments,
   not a generated log-line format. Four final prose columns are required for
   shape but do not contribute Go fields or behavior.

   Common Go shape (case 3 explains Fields/Headers; they are ALWAYS present):
     type Spec struct {
       Chapter string; Row int; Name, Surface string
       Exit int; AnyNonZero bool; Status int; Word string
       Log, Words []string; Norm string
       Fields []string; Headers [][2]string; Named []string; WordCell string
     }
   Chapter's API comment uses the first/last distinct chapter in encounter order.
   ExitCode()(int,bool) returns (Exit,true) when Exit>=0, otherwise (1,true) for
   AnyNonZero, otherwise (0,false). Thus exit !0 yields the chosen result 1,
   never an actual process exit. No Check/LogLine/Exit methods of case 1 exist.
   All/ByName preserve rows/names as above. No cause/outcome/diagnostic/caller
   fields are emitted.

3. Direct body/header metadata (a capability of BOTH plain column layouts,
   not a lesson-selected API variant): Fields []string and Headers [][2]string
   exist even if all corresponding cells are -. Empty lists are nil. Fields
   is - or comma-separated unique names [a-z][a-z0-9_]*; trim token whitespace.
   A single ? suffix is stripped and handled by case 5. Only peer permits these
   columns in the 15-column format. Headers use case 1's Name: value syntax.
   There is no RetryAfter Boolean in the plain API and no implicit error field.
   This metadata does not itself implement HTTP body/schema validation.

4. Response-schema extension: the 16 columns are
   chapter,row,name,surface,code,kind,fields,headers,log,norm,word,response_schema,
   cause,outcome,diagnostic,caller

   Use the common plain shape, add http to the permitted surfaces and allow
   fields/headers at http as well as peer. ALWAYS add Response string to Spec:
   response_schema=- -> ""; otherwise it is a direct components/schemas name
   of the selected lesson OpenAPI, allowed only at http. Numeric HTTP codes
   become Status. Response and Word/Named/WordCell remain separate fields.

   Schema context is L.openapi, not an arbitrary fixture table's directory.
   Reuse gen_door_lesson.Docs and yamlsub for the existing offline typed schema
   reader: declarations retain document base/origin/owner/common/late guards;
   caches do not confer permissions. Validate every referenced named schema's
   full typed reference closure, even with fields=-. Follow root schema aliases
   to the actual target, relative to EACH alias's own document; annotation-only
   siblings do not hide the alias. Cyclic root aliases, absent/unsafe references,
   wrong target kinds, missing component names or unresolved targets fail.
   Constraint-bearing $ref siblings and composed schemas remain full schemas;
   they are not flattened into a made-up direct field projection.

   For explicit fields, the resolved target must expose a direct properties map
   and a required list (default []) of distinct strings. Unsupported/composed
   direct-role shapes fail rather than infer a branch. Every listed field must
   exist in properties; every schema-required field must occur unmarked in the
   form. A ? field must NOT be schema-required. An unmarked form field MAY be
   optional in the schema: the form can require it for a narrower branch. Other
   optional schema properties need not be listed; no all-properties check.
   fields=- means NO direct projection, NOT an empty field declaration: skip
   this subset/role comparison only. The complete referenced schema still
   applies to the actual body and its closure/target are still checked.
   Response is metadata, not generated body validation/encoding.

5. Explicit optional fields: only a 16-column http row with a non--
   response_schema may carry ? in fields. Strip the marker from Fields and
   preserve that ordered name in OptionalFields. If ANY row has a marker, add
     OptionalFields []string
   to the common Spec; rows without markers have nil. Without any marker this
   field is absent. Other Fields are required by the FORM projection, not
   necessarily by the wider schema. A peer field or a row with response_schema=-
   cannot acquire ? by lesson identity. Duplicate/malformed markers fail.

Selection uses exact columns, schema object shape and the explicit ? marker,
never lesson names or prose. Common rows always emit Named/WordCell and
Fields/Headers; Response is column-driven and OptionalFields is marker-driven.
Generated package comments use selected L.code; chapter comments derive from
row values. Ownership guard and physical schema/provenance paths are separate
context, not modes. No new setting, protocol, port, semantic refusal decision,
retry timing, framing, process behavior or stored outcome is implemented.

Provenance records the physical table/proof inputs, every actually loaded schema
resource, this producer and reused Docs/yamlsub/lesson helpers, plus the existing
judge. Schema-role checking changes neither the source nor the emitted full
schema (there is no schema copy in this part). Generated data and declared
methods above are the complete output contract; no lesson implementation or
historical package is read. Legacy ce8 builds pin pre-unification producer code.
"""
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
    """Read common 15/16-column metadata and explicit field roles; owner identity selects schema paths, not an output variant."""

    def __init__(self, text, name="refusals.tsv"):
        self.name = name
        self.sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
        body = [line for line in text.splitlines() if line and not line.startswith("#")]
        head = body[0].split("\t") if body else []
        self.response = head == RESPONSE_COLUMNS
        cols = RESPONSE_COLUMNS if self.response else PLAIN_COLUMNS
        if head != cols:
            raise GenError(f"{name}: columns must be {PLAIN_COLUMNS} (or with response_schema after word)")
        schema_defs, schema_docs = response_schemas(definitions=True) if self.response else ({}, None)
        schemas = set(schema_defs)
        resolved_schemas = {}
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
                if rs != "-" and rs not in resolved_schemas:
                    resolved_schemas[rs] = response_schema(schema_docs, schema_defs, rs)
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
                    if match[2] and not (self.response and r["surface"] == "http"
                                         and r["response_schema"] != "-"):
                        raise GenError(f"{where}: optional field requires an HTTP response schema")
                    r["field_list"].append(match[1])
                    if match[2]:
                        r["optional_fields"].append(match[1])
                if self.response and r["surface"] == "http" and r["response_schema"] != "-":
                    schema = resolved_schemas[r["response_schema"]]
                    if not isinstance(schema, dict) or "$ref" in schema:
                        raise GenError(f"{where}: unsupported response schema field roles")
                    properties, required = schema.get("properties"), schema.get("required", [])
                    if (not isinstance(properties, dict) or not isinstance(required, list) or
                            any(type(x) is not str for x in required) or len(set(required)) != len(required)):
                        raise GenError(f"{where}: unsupported response schema field roles")
                    if not set(required) <= set(r["field_list"]) - set(r["optional_fields"]):
                        raise GenError(f"{where}: required schema fields are missing from fields")
                    for field in r["field_list"]:
                        if field not in properties or (field in r["optional_fields"] and field in required):
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
            if r["word"] != "-":    # All plain forms preserve the cell and derive only its quoted index.
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
        self.headers = True  # Both plain layouts declare fields/headers columns, even when all cells are '-'.
        self.optional_fields = any(r["optional_fields"] for r in self.rows)
        self.word_any = True
        self.schema_inputs = set(schema_docs.inputs) if schema_docs is not None else set()
        if not self.rows:
            raise GenError(f"{name}: a plain refusal catalogue must contain a row")
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
    """Read schema declarations in the selected physical owner context."""
    from gen_door_lesson import Docs, GenError as DoorError
    try:
        docs = Docs(L.openapi)
        schemas = (docs.doc.get("components") or {}).get("schemas") or {}
        return (schemas, docs) if definitions else set(schemas)
    except DoorError as exc:
        raise GenError(str(exc)) from None


def response_schema(docs, definitions, name):
    """Check the full named reference closure, then follow root schema aliases for roles."""
    from gen_door_lesson import GenError as DoorError
    try:
        node, base = definitions[name], docs.main
        pointer = "/components/schemas/" + docs._token(name)
        docs._closure(node, base, pointer)
        seen = set()
        annotations = {"$ref", "title", "description", "$comment", "default", "examples", "deprecated", "readOnly", "writeOnly"}
        while isinstance(node, dict) and "$ref" in node:
            origin = docs.origin(node, base)
            key = (base, origin)
            if key in seen:
                raise GenError(f"{name}: cyclic response schema alias")
            seen.add(key)
            if set(node) - annotations:
                break  # Constraint siblings remain a full schema, not an invented direct field projection.
            node, base = docs.resolve(node["$ref"], base, schema=True, origin=origin)
        return node
    except DoorError as exc:
        raise GenError(str(exc)) from None


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
    """Generate the common plain API; capabilities and chapter comments follow the table."""
    api = PLAIN_API.strip("\n")
    chapters = list(dict.fromkeys(r["chapter"] for r in table.rows))
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
        api = api.replace("\n}", "\n\tOptionalFields []string // Explicit optional names; other Fields are required by this form projection.\n}", 1)
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
        table = PlainTable(DEFAULT_TABLE.read_text(encoding="utf-8"), DEFAULT_TABLE.name)
        paths += sorted(table.schema_inputs)
    helpers = [Path(__file__).resolve(), Path(tsv_input.__file__)]
    if tsv_input.read(DEFAULT_TABLE, root=ROOT).columns == tuple(RESPONSE_COLUMNS):
        import gen_door_lesson, yamlsub
        helpers += [Path(gen_door_lesson.__file__), Path(yamlsub.__file__), Path(lesson.__file__)]
    return {"form": [entry(p) for p in dict.fromkeys(paths)], "generator": entry(Path(__file__).resolve()),
            "generators": [entry(p) for p in helpers], "judge": entry(JUDGE)}


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
## Part `refusals`: the refusal catalogue (closed columns of `forms/refusals.tsv`; generated metadata)

| Package | Import path | Origin |
|---|---|---|
| `refusals` | `{module}/internal/refusals` | generated from the closed columns of `forms/refusals.tsv`; closed |

```go
type Spec struct {
    Chapter, Name, Surface string // surface: call | cli | start | process | peer__HTTP_SURFACE__
    Row        int
    Exit       int      // the exit code the form fixes; -1 — none
    AnyNonZero bool     // «exit !0»: any nonzero code (yours), never 0
    Status     int      // peer: the HTTP status of the other lesson's door
    Word       string   // a fixed refusal/diagnostic token, "" — none
    Log, Words []string // the subjects and «fragments» the diagnostic names; no stdout/stderr format
    Norm       string
    Fields []string     // direct body-field projection (peer; also http in the 16-column layout)
    Headers [][2]string // declared header name/value pairs; nil when no projection
    Named []string      // ordered index of multiple quoted tokens, not a choice of accepted outcomes
    WordCell string     // exact source cell, including "-" or prose; Word/Named only index it
__RESPONSE_FIELD____OPTIONAL_FIELD__
}
var All []*Spec; func ByName(name string) *Spec
func (s *Spec) ExitCode() (code int, ok bool) // the fixed code, 1 for «exit !0» (the kit's choice), ok false — none fixed
```

The prose of a row (its cause, outcome, diagnostic and caller action) stays in the norm (`norm`): read it there; the
package carries only what the form fixes.

The 15-column layout always emits this common Spec, including Fields/Headers and Named/WordCell, independent of
lesson identity or empty cells. `word=-` gives empty Word/nil Named; a cell made only of backtick tokens plus commas
and whitespace gives Word for one token or Named for multiple tokens. WordCell always retains the exact cell.
`code=-` fixes no code; `exit N` fixes Exit=N; `exit !0` sets AnyNonZero and ExitCode returns the chosen nonzero1.
Numeric call/peer/http codes populate Status. The 16-column layout additionally admits http and declares Response.
Only an explicit `?` marker adds OptionalFields to the table-wide Spec. Both field lists omit the marker itself.
For explicit fields, schema-required names must be required by the form, optional markers cannot name schema-required
properties, and every listed field must exist; the form may require an otherwise optional schema property.
`fields=-` is no direct projection: the full response schema remains applicable, with its reference/target checked.
Schemas and alias targets are resolved in the selected physical owner context, not inferred from a fixture path.
This part emits metadata only: full response validation/encoding, choosing a refusal and IO remain yours.
"""


def kit_md():
    """Use exactly render's column discriminator and document every emitted Spec field."""
    text = DEFAULT_TABLE.read_text(encoding="utf-8")
    head = next((x for x in text.splitlines() if x and not x.startswith("#")), "").split("\t")
    if head == COLUMNS:
        Table(text, DEFAULT_TABLE.name)
        return KIT_MD
    table = PlainTable(text, DEFAULT_TABLE.name)
    return KIT_MD_PLAIN.replace("__HTTP_SURFACE__", " | http" if table.response else "").replace(
        "__RESPONSE_FIELD__", "    Response string // named response schema; empty for '-'\n" if table.response else "").replace(
        "__OPTIONAL_FIELD__", "    OptionalFields []string // marked names; other Fields are form-required\n" if table.optional_fields else "")


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
