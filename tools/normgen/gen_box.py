"""Generate the closed box part from P/01.3 norms and forms (owner B-24; Architect, 2026-11-05). The implementation supplies store indices and row IO.

  python3 tools/normgen/gen_box.py [<out>]
Default: tools/normgen/out/p01-1. Only these source locations are read:
- P/01.3-R006 YAML: copy header and generation/floor; anchored N1.3 paragraphs: box outcomes, copy input checks, F1 continuation and backup containment.
- forms/status-fields.tsv and forms/metrics.tsv: box state, term, metric series/labels and values.
- P/01.1 N1 row.items: row-weight ceiling.
- forms/refusals.tsv: named refusals.
- OpenAPI: Status, Refused, Empty and Metrics200 response types from the door part.
- common/data/README.md placeholder table: <sub>/<id> grammar for <sub>/epoch/<id>.

Output <out>/go/box is DO NOT EDIT. box.go defines Config, Indices, Status, Metrics, Join, Leave, Admit, Recover and StartRefusal. copy.go defines Row, EncodeCopy, DecodeCopy with all input checks, Upper, Floor, BackupTarget and ImportRepeated. test_gen_box.py uses an independent Python model from the same normative locations, Go cases and mutants."""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import lesson  # noqa: E402
L = lesson.CURRENT

DEFAULT_OUT = L.out
GO_MODULE = L.go_module
NORMS_13 = L.path("spec/01.3-store.norms.md")
NORMS_11 = L.path("spec/01.1-store.norms.md")
REFUSALS = L.form("refusals.tsv")
FLAGS = L.form("daemon-flags.tsv")
METRICS = L.form("metrics.tsv")
STATUS_FIELDS = L.form("status-fields.tsv")
OPENAPI = L.openapi
KEYS_README = ROOT / "Platform/common/data/README.md"
JUDGE = HERE / "test_gen_box.py"
COPY_JUDGE = HERE / "test_copy_storage.py"
COPY_RUNTIME = {f"box/copy_{name}.go": HERE / f"copyrt/go/{name}.go"
                for name in ("storage", "validation", "import", "control")}
STATES = ("Leader", "Follower", "Candidate", "Shutdown", "Door")
REFUSAL_NAMES = ("box_no_raft", "box_last_voter", "box_admit", "join_parity", "recover_box", "service_body_form",
                 "backup_inside_dir", "import_repeated", "copy_input")


class GenError(Exception):
    pass


def go_str(s):
    return json.dumps(s, ensure_ascii=False)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def block_line(text, word):
    """Read a word: clause of the N1.3 YAML block up to the next clause at the same indentation."""
    m = re.search(r"^%s:\s+(.*?)(?=^[a-z_]+:\s)" % re.escape(word), text, re.M | re.S)
    if not m:
        raise GenError(f'{NORMS_13.name}: no item {word}: in the N1.3 YAML block')
    return " ".join(x.strip() for x in m[1].split("\n"))


def row_ceiling(text):
    """Read the declared default, not the effective ceiling of a store instance."""
    if "ROW_CEILING" in text:
        bindings = re.findall(r"(?m)^\s*ceiling:\s*([^\s#]+)", text)
        if bindings != ["ROW_CEILING"]:
            raise GenError("row.items requires one ceiling: ROW_CEILING binding")
        import gen_flags
        try:
            table = gen_flags.Table(FLAGS.read_text(encoding="utf-8"), str(FLAGS.relative_to(ROOT)))
        except (OSError, gen_flags.GenError) as exc:
            raise GenError(f"ROW_CEILING flags binding: {exc}") from None
        rows = [row for row in table.rows if row["flag"] == "-max-value"]
        if len(rows) != 1 or rows[0]["type"] != "bytes:>0":
            raise GenError("ROW_CEILING requires one -max-value bytes:>0 flag")
        default = rows[0]["default_go"]
        match = re.fullmatch(r"int64\(([1-9][0-9]*)\)", default or "")
        if match is None:
            raise GenError("ROW_CEILING requires a literal positive -max-value default")
        return int(match[1]), True
    # Only the explicitly recognized earlier numeric form is supported here.
    matches = re.findall(r"ceiling: (\d+)\s+# 512 KiB", text)
    if len(matches) != 1:
        raise GenError(f"{NORMS_11.name}: row.items ceiling declaration is not found")
    return int(matches[0]), False


def facts():
    """Extract the normative numbers and names from their current forms and anchored paragraphs."""
    t13 = NORMS_13.read_text(encoding="utf-8")
    t11 = NORMS_11.read_text(encoding="utf-8")
    floor = block_line(t13, "floor")
    import gen_core
    clauses = gen_core.anchored(NORMS_13)
    def clause(anchor):
        if anchor not in clauses:
            raise GenError(f"{NORMS_13.name}: no req anchor {anchor}")
        return gen_core.plain(clauses[anchor]).replace("`", "")
    box = clause("P/01.3-R169")
    copy_ = " ".join(clause(a) for a in ("P/01.3-R093", "P/01.3-R295", "P/01.3-R100"))
    import yamlsub
    try:
        api = yamlsub.load(OPENAPI.read_text(encoding="utf-8"), OPENAPI.name)
        status = api["components"]["schemas"]["Status"]
        properties = status.get("properties", {})
        present = "max_body" in properties
        body = properties.get("max_body")
    except (yamlsub.YamlError, KeyError, TypeError, AttributeError) as exc:
        raise GenError(f"Status schema: {exc}") from None
    if present and (not isinstance(body, dict) or "max_body" not in status.get("required", []) or
                    body.get("type") != "integer" or type(body.get("minimum")) not in (int, float) or
                    body.get("minimum") != 1):
        raise GenError("Status.max_body must be a required positive integer")
    f = {"status_max_body": present}
    import tsv_input
    try:
        metric_rows = tsv_input.read(METRICS, root=ROOT).rows
        status_rows = {r["field"]: r for _, r in tsv_input.read(STATUS_FIELDS, root=ROOT).rows}
    except tsv_input.TSVError as exc:
        raise GenError(str(exc)) from None
    f["series"], f["values"] = [], {}
    for _, row in metric_rows:
        if "box" not in [v.strip() for v in row["emitted_by"].split(",")]:
            continue
        name, label = row["series"], row["labels"]
        if label == "-":
            f["series"].append((name, None, None))
            value = re.search(r"\bbox: ([0-9]+)\b", row["value_rule"])
            if not value:
                raise GenError(f"{METRICS.name}: {name}: no numeric box value")
            short = name.removeprefix("configstore_raft_").removeprefix("configstore_")
            f["values"][short] = int(value[1])
        else:
            label_parts = re.fullmatch(r"([a-z_]+)=([a-z_|]+)", label)
            if not label_parts:
                raise GenError(f"{METRICS.name}: {name}: unsupported labels {label!r}")
            f["series"].append((name, label_parts[1], label_parts[2].split("|")))
    state = re.search(r"\bbox: (\w+)", status_rows["state"]["value_rule"])
    term = re.search(r"\bbox: (\d+)", status_rows["term"]["value_rule"])
    if not state or state[1] not in STATES or not term or int(term[1]) != f["values"]["term"]:
        raise GenError("status-fields.tsv: no supported box state/term")
    f["state"] = state[1]
    for phrase in ("join of its own id MUST give 200 {}", "join of a foreign id MUST give 409 refused",
                   "leave MUST give 409 refused", "admit MUST be a refusal, code ≠ 0",
                   "recover MUST be a refusal, code 2"):
        if phrase not in box:
            raise GenError(f"P/01.3-R169: missing box rule {phrase!r}")
    if "MUST refuse to start with box_no_raft, code 2" not in clause("P/01.3-R164"):
        raise GenError("P/01.3-R164: missing no-raft refusal")
    hm = re.search(r'\{"format": "([\w-]+)", "version": (\d+), "index": <version>\}', copy_)
    if not hm:
        raise GenError('N1.3 copy: the header line is not found')
    f["copy_format"], f["copy_version"] = hm[1], int(hm[2])
    for phrase in ("line per key: {key, items, index}", "{key, items: null, index, unreadable: true}",
                   "ascending order of UTF-8 bytes", "a repeated key", "index of a row higher than the index of the header",
                   "If an unreadable row is in the input"):
        if phrase not in copy_:
            raise GenError(f"P/01.3 copy: missing {phrase!r}")
    import_ = clause("P/01.3-R149") + " " + clause("P/01.3-R151")
    for phrase in ("transfer MUST exclude the input platform/epoch_floor", "first write MUST be new F1",
                   "partial replay MUST preserve the exact saved F1 row (items and index)"):
        if phrase not in import_:
            raise GenError(f"P/01.3 import: missing F1 rule {phrase!r}")
    f["copy_storage"] = True
    time_pattern = r"^(0|[1-9][0-9]*)(\.[0-9]{1,3})?$"
    for anchor in ("P/01.1-R007", "P/01.1-R008"):
        if time_pattern not in gen_core.anchored(NORMS_11).get(anchor, ""):
            raise GenError(f"{anchor}: current writer/reader time notation is absent")
    gm = re.search(r"generation: max\(\(upper >> (\d+)\) \+ 1, whole hours of UTC since (\d{4})-(\d\d)-(\d\d)\); "
                   r"floor = generation << (\d+)(?:;| )", floor)
    bm = re.search(r"1 … 2\^53 − 2\^32", floor)
    lm = re.search(r"generation ≤ 2\^21 − 1", floor)
    if not gm or gm[1] != gm[5] or not bm or not lm:
        raise GenError('N1.3 floor: generation/floor formula is not found')
    f["shift"], f["since"] = int(gm[1]), (int(gm[2]), int(gm[3]), int(gm[4]))
    f["max_generation"] = 2 ** 21 - 1
    if not re.search(r"weight \(sum of byte lengths of every key and every value\) at most the store's ceiling", t11):
        raise GenError(f"{NORMS_11.name}: row.items ceiling is not found")
    f["ceiling"], f["ceiling_from_flags"] = row_ceiling(t11)
    if "not outside -dir of the daemon" not in clause("P/01.3-R121"):
        raise GenError('P/01.3-R121: backup outside -dir is not found')
    keys = KEYS_README.read_text(encoding="utf-8")
    for ph in ("<sub>", "<id>"):
        km = re.search(r"^\| `%s` \| `(.+?)` \| " % re.escape(ph), keys, re.M)
        if not km:
            raise GenError(f"{KEYS_README.name}: no grammar of {ph}")
        f[ph] = km[1].replace("\\|", "|")
    rows = {}
    for line in REFUSALS.read_text(encoding="utf-8").split("\n"):
        c = line.split("\t")
        if len(c) > 4 and c[0] == "1.3":
            rows[c[2]] = c
    for n in REFUSAL_NAMES:
        if n not in rows:
            raise GenError(f"{REFUSALS.name}: no row {n}")
    f["refusals"] = {g: g for g in ("".join(w.capitalize() for w in n.split("_")) for n in REFUSAL_NAMES)}
    return f


BOX_GO = r'''// Code generated by tools/normgen/gen_box.py; DO NOT EDIT.
// Source %(norms)s sha256 %(norms_sha)s, %(refusals)s sha256 %(refusals_sha)s.

// Package box implements fully normative P/01.3 box/metrics behavior:/v1/status, member metrics,
// join/leave/admit/recover and no-raft startup refusal. Your implementation supplies last/commit/applied
// store indices;this package supplies the rest.
package box

import (
	"fmt"
	"strings"

	"%(module)s/apidoor"
	"%(module)s/flags"
	"%(module)s/jsonstrict"
	"%(module)s/refusals"
)

// Config contains -id (or SERVER_NAME), -api, -tls and -max-value from daemon flags. Status max_value is the
// actual row-weight byte ceiling (spec103, 2026-11-05).
%(max_body_comment)stype Config struct {
	ID       string
	API      string // Empty when -api is absent:leader empty, members {} (C01-STATUS-MEMBERS-NOAPI).
	TLS      bool
	MaxValue int64
%(max_body_field)s}

// ConfigOf maps parsed daemon flags, including ID already defaulted from SERVER_NAME by launch parsing.
func ConfigOf(f *flags.Flags) Config {
	return Config{ID: f.ID, API: f.API, TLS: f.TLS != "", MaxValue: f.MaxValue%(max_body_flags)s}
}

// Indices are last written, committed and applied store indices;on box they normally coincide.
type Indices struct {
	Last, Commit, Applied uint64
}

// Status returns box's200Status:state %(state)s, term %(term)d, leader=-api(empty if absent), leader_id=id,
// voters[id], members{id:api} or {};admissionAhead supplies admission_ahead(N1.3 admission), nil omits it.
func Status(c Config, ix Indices, admissionAhead *float64) apidoor.Answer {
	members := map[string]string{}
	if c.API != "" {
		members[c.ID] = c.API
	}
	st := apidoor.Status{Id: c.ID, State: %(state_go)s, Leader: c.API, LeaderId: c.ID, Term: %(term)d, Commit: ix.Commit,
		Applied: ix.Applied, Voters: []string{c.ID}, Members: members, Tls: c.TLS, MaxValue: c.MaxValue,%(max_body_status)s
		AdmissionAhead: admissionAhead}
	return apidoor.Answer{Code: 200, Body: st}
}

// Series is the closed voter-store /metrics series list in normative order(N1.3 metrics).
var Series = []string{%(series_names)s}

// MetricsText emits normative single-member box metrics with ix indices;state is lowercase and only the
// current state is emitted(sc17steps6/7:state=leader), without # TYPE.
func MetricsText(ix Indices) string {
	var b strings.Builder
%(metrics_body)s	return b.String()
}

// Metrics — 200 text/plain MetricsText.
func Metrics(ix Indices) apidoor.Answer {
	return apidoor.Answer{Code: 200, Body: apidoor.Metrics200(MetricsText(ix))}
}

func line(b *strings.Builder, name, labels string, v uint64) {
	b.WriteString(name)
	if labels != "" {
		b.WriteString("{" + labels + "}")
	}
	fmt.Fprintf(b, " %%d\n", v)
}

// label escapes a Prometheus text label value's backslash, quote and newline.
func label(k, v string) string {
	r := strings.NewReplacer(`\`, `\\`, `"`, `\"`, "\n", `\n`)
	return k + `="` + r.Replace(v) + `"`
}

// body requires exactly one strict JSON object for service POST(P/01.3-R017);otherwise400service_body_form.
func body(op apidoor.Op, raw []byte) (any, *apidoor.Answer) {
	v, _, err := jsonstrict.Decode(raw, 64)
	if err != nil {
		a := refuse(op, refusals.%(ServiceBodyForm)s, "the body is not one JSON object: "+err.Error())
		return nil, &a
	}
	return v, nil
}

func refuse(op apidoor.Op, s *refusals.Spec, msg string) apidoor.Answer {
	a, err := apidoor.Refuse(op, s.Code, s.Kind, msg, nil)
	if err != nil {
		return apidoor.Answer{Code: s.Code}
	}
	return a
}

// Join handles box POST /v1/join:the caller checks identity first.Require Join schema or400;own ID gives
//200{};another ID gives409refused/join_parity(group larger than declared), even with -force.
func Join(c Config, raw []byte) apidoor.Answer {
	v, bad := body(apidoor.OpJoin, raw)
	if bad != nil {
		return *bad
	}
	j, vio := apidoor.DecodeJoin(v)
	if vio != nil {
		return refuse(apidoor.OpJoin, refusals.%(ServiceBodyForm)s, "join: "+vio.Error())
	}
	if j.Id == c.ID {
		a, err := apidoor.AnswerOf(apidoor.OpJoin, 200, map[string]any{})
		if err != nil {
			return apidoor.Answer{Code: 200}
		}
		return a
	}
	return refuse(apidoor.OpJoin, refusals.%(JoinParity)s, "a box has one voter: "+j.Id+" cannot join")
}

// Leave validates its schema or400, then always409refused/the last voter(box_last_voter) on box.
func Leave(c Config, raw []byte) apidoor.Answer {
	v, bad := body(apidoor.OpLeave, raw)
	if bad != nil {
		return *bad
	}
	if _, vio := apidoor.DecodeLeave(v); vio != nil {
		return refuse(apidoor.OpLeave, refusals.%(ServiceBodyForm)s, "leave: "+vio.Error())
	}
	return refuse(apidoor.OpLeave, refusals.%(BoxLastVoter)s, "the last voter")
}

// Admit on box refuses box_admit/the last voter with nonzero exit.
func Admit(logf func(string), id string) int {
	return refusals.%(BoxAdmit)s.Exit(logf, map[string]string{})
}

// Recover on box refuses recover_box/this build has no raft with exit 2.
func Recover(logf func(string)) int {
	return refusals.%(RecoverBox)s.Exit(logf, map[string]string{})
}

// StartRefusal returns box_no_raft/exit 2 for group-size3/5, -join or -door;ok=false permits startup under
// this rule only.Other startup refusals belong to the implementation.
func StartRefusal(f *flags.Flags, logf func(string)) (code int, refused bool) {
	if f.GroupSize == 3 || f.GroupSize == 5 || f.Join != "" || f.Door {
		return refusals.%(BoxNoRaft)s.Exit(logf, map[string]string{}), true
	}
	return 0, false
}
'''

COPY_GO = r'''// Code generated by tools/normgen/gen_box.py; DO NOT EDIT.
// Source %(norms)s sha256 %(norms_sha)s.
%(ceiling_sources)s

package box

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"

	"%(module)s/apidoor"
	"%(module)s/jsonstrict"
	"%(module)s/refusals"
)

// Copy format(N1.3 copy):JSON Lines starts with format %(format_go)s, version %(version)d and index,
// then one {key, items, index} row per key(chapter 1.1), sorted by UTF-8 key bytes.
const (
	CopyFormat  = %(format_go)s
	CopyVersion = %(version)d
	RowCeiling  = %(ceiling)d // Default P/01.1 N1 row.items.ceiling;the actual ceiling is daemon -max-value.
)

// Row is a copy key, items and Index;Unreadable represents an as-read corrupt row(items null).
type Row struct {
	Key        string
	Items      map[string]string
	Index      uint64
	Unreadable bool
}

// CopyError refuses copy input with nonzero exit, line number(1header, 0whole input) and reason.
type CopyError struct {
	Line  int
	Cause string
}

func (e *CopyError) Error() string { return "line " + strconv.Itoa(e.Line) + ": " + e.Cause }

// Exit logs the copy_input reason and returns its exit code.
func (e *CopyError) Exit(logf func(string)) int {
	return refusals.%(CopyInput)s.Exit(logf, map[string]string{"cause": e.Error()})
}

// EncodeCopy emits a header and UTF-8-key-sorted rows at index;any row version greater than index errors
// because copies are taken between batches and cannot precede a contained row.
func EncodeCopy(index uint64, rows []Row) ([]byte, error) {
	rs := append([]Row(nil), rows...)
	sort.Slice(rs, func(i, j int) bool { return rs[i].Key < rs[j].Key })
	var b bytes.Buffer
	b.WriteString(`{"format":` + jsonString(CopyFormat) + `,"version":` + strconv.Itoa(CopyVersion) + `,"index":"` +
		strconv.FormatUint(index, 10) + "\"}\n")
	for i, r := range rs {
		if i > 0 && rs[i-1].Key == r.Key {
			return nil, &CopyError{0, "a repeated key " + strconv.Quote(r.Key)}
		}
		if r.Index > index {
			return nil, &CopyError{0, "the version of " + strconv.Quote(r.Key) + " is above the index of the copy"}
		}
		b.WriteString(`{"key":` + jsonString(r.Key) + `,"items":`)
		if r.Unreadable {
			b.WriteString("null")
		} else {
			names := make([]string, 0, len(r.Items))
			for k := range r.Items {
				names = append(names, k)
			}
			sort.Strings(names)
			b.WriteByte('{')
			for j, k := range names {
				if j > 0 {
					b.WriteByte(',')
				}
				b.WriteString(jsonString(k) + ":" + jsonString(r.Items[k]))
			}
			b.WriteByte('}')
		}
		b.WriteString(`,"index":"` + strconv.FormatUint(r.Index, 10) + `"`)
		if r.Unreadable {
			b.WriteString(`,"unreadable":true`)
		}
		b.WriteString("}\n")
	}
	return b.Bytes(), nil
}

func jsonString(s string) string {
	var b bytes.Buffer
	enc := json.NewEncoder(&b)
	enc.SetEscapeHTML(false)
	_ = enc.Encode(s)
	return strings.TrimSuffix(b.String(), "\n")
}

var (
	epochKey = regexp.MustCompile(`^%(sub)s/epoch/%(id)s$`)
	decimal  = regexp.MustCompile(`^(?:0|[1-9][0-9]*)$`)
)

// FloorKey names the N1.3 floor row, which is an ordinary copy row.
const FloorKey = "platform/epoch_floor"

// DecodeCopy fully prevalidates import/restore before any write:header format/version/fields, Row objects,
// chapter 1.1 N1 keys, no extra/missing fields, no unreadable rows, item weight at most actual ceiling,
// unique keys, row versions not above the header index, and decimal epoch/floor values so upper is valid.
// Input row order is unrestricted.Return(header index, rows) or copy_input refusal.
func DecodeCopy(data []byte, ceiling int64) (uint64, []Row, *CopyError) {
	if len(data) == 0 {
		return 0, nil, &CopyError{0, "the input is empty: no header"}
	}
	if !bytes.HasSuffix(data, []byte("\n")) {
		return 0, nil, &CopyError{0, "the last line has no LF"}
	}
	lines := bytes.Split(data[:len(data)-1], []byte("\n"))
	head, err := object(lines[0])
	if err != "" {
		return 0, nil, &CopyError{1, "the header: " + err}
	}
	if !sameKeys(head, "format", "version", "index") {
		return 0, nil, &CopyError{1, "the header: fields are not {format, version, index}"}
	}
	if f, ok := head["format"].(string); !ok || f != CopyFormat {
		return 0, nil, &CopyError{1, "the header: format is not " + CopyFormat}
	}
	if v, ok := head["version"].(int64); !ok || v != CopyVersion { // jsonstrict represents lexical integers without '.'/exponent as int64.
		return 0, nil, &CopyError{1, "the header: version is not " + strconv.Itoa(CopyVersion)}
	}
	index, ok := version(head["index"])
	if !ok {
		return 0, nil, &CopyError{1, "the header: index is not a version"}
	}
	seen := map[string]bool{}
	var rows []Row
	for i, ln := range lines[1:] {
		no := i + 2
		m, err := object(ln)
		if err != "" {
			return 0, nil, &CopyError{no, err}
		}
		key, ok := m["key"].(string)
		if !ok {
			return 0, nil, &CopyError{no, "no key or the key is not a string"}
		}
		if e, ok := apidoor.CheckSchema("Key", key); !ok || e != nil {
			return 0, nil, &CopyError{no, "the key " + strconv.Quote(key) + " is not by chapter 1.1 \u041d1"}
		}
		if seen[key] {
			return 0, nil, &CopyError{no, "a repeated key " + strconv.Quote(key)}
		}
		seen[key] = true
		delete(m, "key")
		if u, isU := m["unreadable"]; isU {
			if u == true {
				return 0, nil, &CopyError{no, "an unreadable row " + strconv.Quote(key)}
			}
			return 0, nil, &CopyError{no, "the row " + strconv.Quote(key) + " is not by Row"}
		}
		if e, ok := apidoor.CheckSchema("Row", m); !ok || e != nil || m["items"] == nil {
			return 0, nil, &CopyError{no, "the row " + strconv.Quote(key) + " is not by Row"}
		}
		ix, _ := version(m["index"])
		if ix > index {
			return 0, nil, &CopyError{no, "the version of " + strconv.Quote(key) + " is above the index of the header"}
		}
		items := map[string]string{}
		var weight int64
		for k, v := range m["items"].(map[string]any) {
			items[k] = v.(string)
			weight += int64(len(k) + len(items[k]))
		}
		if weight > ceiling {
			return 0, nil, &CopyError{no, "the row " + strconv.Quote(key) + " is larger than the row ceiling"}
		}
		if epochKey.MatchString(key) && !decimalItem(items, "epoch") {
			return 0, nil, &CopyError{no, "the epoch of " + strconv.Quote(key) + " is not decimal: upper is not reliable"}
		}
		if key == FloorKey && !decimalItem(items, "floor") {
			return 0, nil, &CopyError{no, "the floor is not decimal: upper is not reliable"}
		}
		rows = append(rows, Row{Key: key, Items: items, Index: ix})
	}
	return index, rows, nil
}

func object(ln []byte) (map[string]any, string) {
	v, _, err := jsonstrict.Decode(ln, 64)
	if err != nil {
		return nil, "not JSON: " + err.Error()
	}
	m, ok := v.(map[string]any)
	if !ok {
		return nil, "not a JSON object"
	}
	return m, ""
}

func sameKeys(m map[string]any, keys ...string) bool {
	if len(m) != len(keys) {
		return false
	}
	for _, k := range keys {
		if _, ok := m[k]; !ok {
			return false
		}
	}
	return true
}

func version(v any) (uint64, bool) {
	s, ok := v.(string)
	if !ok || !decimal.MatchString(s) {
		return 0, false
	}
	n, err := strconv.ParseUint(s, 10, 64)
	return n, err == nil
}

func decimalItem(items map[string]string, name string) bool {
	_, ok := version(items[name])
	return ok
}

// Upper is the maximum platform/epoch_floor floor and every <sub>/epoch/<id> epoch across copy input and
// saved daemon state;fresh directories have no saved state.Default0 when absent.Rows have already
// passed DecodeCopy's decimal validation.
func Upper(rows []Row, saved []Row) uint64 {
	var up uint64
	for _, rs := range [][]Row{rows, saved} {
		for _, r := range rs {
			var s string
			switch {
			case r.Key == FloorKey:
				s = r.Items["floor"]
			case epochKey.MatchString(r.Key):
				s = r.Items["epoch"]
			default:
				continue
			}
			if n, ok := version(s); ok && n > up {
				up = n
			}
		}
	}
	return up
}

// Since is the N1.3 floor generation clock epoch.
var Since = time.Date(%(since_y)d, %(since_m)d, %(since_d)d, 0, 0, 0, 0, time.UTC)

// MaxGeneration bounds generation so floor=generation<<%(shift)d stays at most2^53-2^32.
const MaxGeneration = %(max_generation)d

// Floor computes generation=max((upper>>%(shift)d)+1, whole UTC hours since Since), then
// floor=generation<<%(shift)d.Refuse overflow beyond MaxGeneration with ok=false.
func Floor(upper uint64, now time.Time) (generation, floor uint64, ok bool) {
	generation = (upper >> %(shift)d) + 1
	if h := now.UTC().Sub(Since); h > 0 {
		if hours := uint64(h / time.Hour); hours > generation {
			generation = hours
		}
	}
	if generation > MaxGeneration {
		return 0, 0, false
	}
	return generation, generation << %(shift)d, true
}

// BackupTarget requires a backup outside daemon -dir(N1.3 admin_ops, B8).Resolve symlinks, using the parent
// for a nonexistent file.Refuse inside/equal-dir paths before writing;otherwise return nil.
func BackupTarget(file, dir string) error {
	d, err := realPath(dir)
	if err != nil {
		return err
	}
	f, err := realPath(file)
	if err != nil {
		return err
	}
	if d == string(filepath.Separator) { // the filesystem root has no outside target
		return &InsideDir{File: f, Dir: d}
	}
	if f == d || strings.HasPrefix(f, d+string(filepath.Separator)) {
		return &InsideDir{File: f, Dir: d}
	}
	return nil
}

// InsideDir represents backup_inside_dir for a copy path within the data directory.
type InsideDir struct{ File, Dir string }

func (e *InsideDir) Error() string { return "backup " + e.File + " is inside the data directory " + e.Dir }

// Exit logs backup_inside_dir(path, dir) and returns its exit code.
func (e *InsideDir) Exit(logf func(string)) int {
	return refusals.%(BackupInsideDir)s.Exit(logf, map[string]string{"path": e.File, "dir": e.Dir})
}

func realPath(p string) (string, error) {
	abs, err := filepath.Abs(p)
	if err != nil {
		return "", err
	}
	if r, err := filepath.EvalSymlinks(abs); err == nil {
		return r, nil
	} else if !os.IsNotExist(err) {
		return "", err
	}
	parent, err := realPath(filepath.Dir(abs))
	if err != nil {
		return "", err
	}
	return filepath.Join(parent, filepath.Base(abs)), nil
}

// ImportRepeated rejects import after Done, the N3 phase marker owned by your implementation, with
// import_repeated, nonzero exit and no changes.
func ImportRepeated(logf func(string)) int {
	return refusals.%(ImportRepeated)s.Exit(logf, map[string]string{"phase": "Done"})
}
'''


def metrics_body(f):
    v, out = f["values"], []
    for name, lab, vals in f["series"]:
        short = name[len("configstore_raft_"):] if name.startswith("configstore_raft_") else name[len("configstore_"):]
        if lab == "state":
            out.append(f'\tline(&b, {go_str(name)}, label("state", {go_str(f["state"].lower())}), 1)\n')
        elif lab == "kind":
            for k in vals:
                field = {"last": "Last", "commit": "Commit", "applied": "Applied"}.get(k)
                if field is None:
                    raise GenError(f'N1.3 metrics: {name}{{kind={k}}} has no index')
                out.append(f'\tline(&b, {go_str(name)}, label("kind", {go_str(k)}), ix.{field})\n')
        elif lab is None and short in v:
            out.append(f'\tline(&b, {go_str(name)}, "", {v[short]})\n')
        elif lab is None and name == "configstore_raft_term":
            out.append(f'\tline(&b, {go_str(name)}, "", {v["term"]})\n')
        else:
            raise GenError(f'N1.3 metrics: {name} has no value of one member in «box»')
    return "".join(out)


def gofmt(src):
    done = subprocess.run(["gofmt"], input=src.encode(), capture_output=True)
    if done.returncode:
        raise GenError("gofmt: " + done.stderr.decode())
    return done.stdout.decode()


def render():
    f = facts()
    common = {"module": GO_MODULE, "norms": str(NORMS_13.relative_to(ROOT)), "norms_sha": sha(NORMS_13),
              "refusals": str(REFUSALS.relative_to(ROOT)), "refusals_sha": sha(REFUSALS), **f["refusals"]}
    body = {"max_body_comment": "// MaxBody is this instance's configured HTTP entity-body byte ceiling.\n",
            "max_body_field": "\tMaxBody int64\n", "max_body_flags": ", MaxBody: f.MaxBody",
            "max_body_status": " MaxBody: c.MaxBody,"}
    if not f["status_max_body"]:
        body = {name: "" for name in body}
    box = BOX_GO % dict(common, **body, state=f["state"], state_go=go_str(f["state"]), term=f["values"]["term"],
                        series_names=", ".join(go_str(n) for n, _, _ in f["series"]), metrics_body=metrics_body(f))
    ceiling_sources = (f"// ROW_CEILING default source {FLAGS.relative_to(ROOT)} sha256 {sha(FLAGS)}\n"
                       if f["ceiling_from_flags"] else "")
    cp = COPY_GO % dict(common, ceiling_sources=ceiling_sources,
                        format_go=go_str(f["copy_format"]), version=f["copy_version"], ceiling=f["ceiling"],
                        sub=f["<sub>"][4:-2], id=f["<id>"][4:-2], since_y=f["since"][0], since_m=f["since"][1],
                        since_d=f["since"][2], shift=f["shift"], max_generation=f["max_generation"])
    files = {"box/box.go": gofmt(box), "box/copy.go": gofmt(cp)}
    if f["copy_storage"]:
        files.update({rel: gofmt(source.read_text(encoding="utf-8")) for rel, source in COPY_RUNTIME.items()})
    return files, f


def generate(out=DEFAULT_OUT):
    gdir = Path(out) / "go"
    files, _ = render()
    for rel in COPY_RUNTIME:
        if rel not in files:
            (gdir / rel).unlink(missing_ok=True)  # an older export must not retain a newer procedure
    for rel, text in files.items():
        (gdir / rel).parent.mkdir(parents=True, exist_ok=True)
        (gdir / rel).write_text(text, encoding="utf-8")
    return gdir


def kit_files(module, out=DEFAULT_OUT):
    """Return [(internal directory, name, bytes, origin, source, editable)]; stale output raises GenError."""
    files = []
    for rel, text in sorted(render()[0].items()):
        kept = Path(out) / "go" / rel
        if not kept.is_file() or kept.read_text(encoding="utf-8") != text:
            raise GenError(f"{kept} is stale: run tools/normgen/gen_box.py")
        data = kept.read_bytes().replace(f'"{GO_MODULE}/'.encode(), f'"{module}/internal/'.encode())
        sub, name = rel.rsplit("/", 1)
        origin = "handwritten" if rel in COPY_RUNTIME else "generated"
        source = COPY_RUNTIME.get(rel, kept)
        files.append((sub, name, data, origin, L.output_source(kept, out) if source == kept else str(source.relative_to(ROOT)), False))
    return files


def provenance():
    import tsv_input

    def entry(path):
        return {"path": str(Path(path).relative_to(ROOT)), "sha256": sha(path)}
    f = facts()
    storage = f["copy_storage"]
    def entries(sources):
        return [entry(p) for p in dict.fromkeys(p for src in sources for p in
                (tsv_input.source_files(src, root=ROOT) if src.suffix == ".tsv" else [src]))]
    return {"form": entries([NORMS_13, NORMS_11, REFUSALS, OPENAPI, KEYS_README, METRICS, STATUS_FIELDS] +
                            ([FLAGS] if f["ceiling_from_flags"] else [])),
            "generator": entry(Path(__file__).resolve()), "handwritten": [entry(p) for p in COPY_RUNTIME.values()] if storage else [],
            "generators": [entry(Path(__file__).resolve()), entry(Path(tsv_input.__file__)), entry(HERE / "yamlsub.py"),
                           entry(HERE / "gen_core.py")] +
                          ([entry(HERE / "gen_flags.py")] if f["ceiling_from_flags"] else []),
            "judge": entry(JUDGE), "judges": [entry(JUDGE), entry(COPY_JUDGE)] if storage else [entry(JUDGE)],
            "judge_inputs": entries([L.form("stages.kit.tsv"),
                            *sorted(L.path("acceptance/3").glob("*.tsv")),
                            L.path("acceptance/3/README.md"),
                            *sorted(L.path("acceptance/3/inputs").glob("*.jsonl")),
                            ROOT / "Platform/common/data/testsub/testsub.subsystem.yaml",
                            ROOT / "Platform/common/data/testsub/testsub2.subsystem.yaml"]) if storage else []}


KIT_MD = """
## Part `box`: what the norm fixes on one box (generated code with a handwritten store environment, closed)

| File | Origin |
|---|---|
| `{module}/internal/box/box.go` | kit (closed): `Status`, `Metrics`, `Join`, `Leave`, `Admit`, `Recover`, `StartRefusal` |
| `{module}/internal/box/copy.go` | kit (closed): the copy format — `EncodeCopy`, `DecodeCopy`, `Upper`, `Floor`, `BackupTarget`, `ImportRepeated` |
| `{module}/internal/box/copy_storage.go`, `copy_validation.go`, `copy_import.go`, `copy_control.go` | handwritten kit environment (closed): `CopyStorage`, `ImportCopy`, `BackupCopy`, `CopyControl`, `CopyStartAllowed` |

The store of a box (P/01.3 N1.3 `box`) answers its service doors by the norm alone; you give it only the indices of
your store. Wire it from your files (one line each), after your identity check (a role socket — 403 before the body):

```go
// coreadapter/status.go, metrics.go, join.go, leave.go
return box.Status(box.ConfigOf(f), box.Indices{Last: …, Commit: …, Applied: …}, nil)
return box.Metrics(box.Indices{…})
return box.Join(cfg, body)      // own id — 200 {}, a foreign id — 409 refused, a body out of form — 400
return box.Leave(cfg, body)     // 409 refused «the last voter»
// admin/admit.go, recover.go; the daemon start
return box.Admit(logf, id)      // code ≠ 0 «the last voter»
return box.Recover(logf)        // code 2 «this build has no raft»
if code, refused := box.StartRefusal(f, logf); refused { return code }   // -group-size 3|5, -join, -door
```

**The copy** (N1.3 `copy`, `import`, `floor`; N3 phases; `admin_ops` backup): implement `box.CopyStorage` over your actual
store. `WithCopyLock` excludes ordinary writers/batches for the whole callback. Inside it, `CopyTxn.Snapshot` reads actual
rows and the index; `BeginImport` atomically makes the new F1 and progress durable and advances the index;
`WriteImport` durably writes one supplied row with its exact version; `FinishImport` persists Done. Source replay/admission
memory is not an input: retain the normal metadata of YOUR new floor operation, not that of the source store.
Use your ordinary durability barriers. Save the complete progress and F1 in your on-disk metadata. After reopening,
read the same metadata; do not reconstruct a new F1. `box.CopyStartAllowed(progress)` gates ordinary startup (exit 2)
and in-process reads/writes (503) while Transfer is pending. Only continuation bypasses that gate.

The kit owns `box.ImportCopy`/`BackupCopy`/`CopyControl`: complete preflight, upper/clock/overflow, first F1, immutable-input
identity, continuation and actual completeness; the input floor participates in upper/clock checks and is NEVER
transferred. Other rows keep their versions. Backup takes one snapshot between batches, has no replay/admission memory,
and writes an external 0600 file with sync/temp/rename/directory-sync. A repeated completed import refuses.

Connect `admin.Env.Copy` to a `box.CopyControl` with the ACTUAL store Dir/Ceiling, your wall clock and `Open(command)`.
For import/restore the target directory is `f.Dir`. Backup has no -dir flag: its Dir must be the LIVE daemon's actual
data directory, not the empty CLI field; missing Dir refuses. Ceiling is the operative row ceiling (zero uses the
normative default), not a guessed limit from an unrelated process.
The opener gives the actual live store for backup, or an exclusive stopped target for box import/restore; it also
supplies close. When Source declares admin-only HTTP copy, live backup must follow that contract. This port does not implement or
qualify HTTP framing/completion, the snapshot provider, its lock scope or its budgets. The host supplies that
connection; the kit chooses no storage format or private alias for that public copy contract.
Use the existing `launch.App.Admin` hook to call `admin.Run` with that environment. Fresh Backup/Import/Restore wrappers
delegate when Copy is connected; existing YOURS wrappers remain yours and can call the same port. Without a connection
they fail explicitly. You still implement the storage/CLI transport connection; this kit is not a complete store core.
"""


def kit_md():
    if facts()["copy_storage"]:
        return KIT_MD
    return """\n## Part `box`: the earlier form of the box primitives (closed)

`box.go`: Status/Metrics/Join/Leave/Admit/Recover/StartRefusal. `copy.go`: EncodeCopy/DecodeCopy/Upper/Floor/BackupTarget.
This export predates the complete F1 continuation rule. It receives these earlier primitives, not the new store
procedure; the implementation connects the copy to its store under this export's own norms.
"""


def main(argv):
    out = Path(argv[0]) if argv else DEFAULT_OUT
    try:
        gdir = generate(out)
    except GenError as exc:
        print(f"gen_box: {exc}", file=sys.stderr)
        return 2
    print(gdir / "box")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
