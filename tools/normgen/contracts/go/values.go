package contracts

import (
	"bytes"
	"encoding/json"
	"math"
	"math/big"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"unicode/utf16"
)

// Row check contract (common/contracts/row-check.md) values_by_type and absent: a JSON value at the input of a door →
// the text element of the row, and the element → the JSON value of the answer.

// MaxSafeInt — 2^53 − 1, the bound of int.
const MaxSafeInt = 1<<53 - 1

// ValueWrite — the outcome of a write: Status "ok" (Row — the element; Seal — the element is the plaintext of a
// *_secret field, the caller seals it), "absent" (no element) or "refused" (Fault — the word, "" — none).
type ValueWrite struct {
	Status string
	Row    string
	Seal   bool
	Fault  string
}

// ValueRead — the outcome of a read: Status "ok" (Value — the JSON value), "absent" or "unreadable".
type ValueRead struct {
	Status string
	Value  any
}

var intLexemeRE = regexp.MustCompile(`^-?(0|[1-9][0-9]*)$`)

func refused(fault string) ValueWrite { return ValueWrite{Status: "refused", Fault: fault} }

func okRow(row string) ValueWrite { return ValueWrite{Status: "ok", Row: row} }

// decodeLexeme — one JSON value with numbers as their lexemes (json.Number).
func decodeLexeme(lexeme string) (any, bool) {
	d := json.NewDecoder(strings.NewReader(lexeme))
	d.UseNumber()
	var v any
	if d.Decode(&v) != nil {
		return nil, false
	}
	if _, err := d.Token(); err == nil {
		return nil, false
	}
	return v, true
}

// FloatText — the float notation: of the notations that read in binary64 as v the one with the fewest significant
// digits, the closest, of two the even; without an exponent; -0 → 0.
func FloatText(v float64) string {
	if v == 0 {
		return "0"
	}
	return strconv.FormatFloat(v, 'f', -1, 64)
}

// ValueToRow — values_by_type of a write: typ — the type of the manifest field (string, url, int, float, bool, list,
// list:labels, json, blob, secret, int:inherit); lexeme — the JSON text of the value; given — the field is passed.
func ValueToRow(typ, lexeme string, given bool) ValueWrite {
	if !given {
		return ValueWrite{Status: "absent"}
	}
	v, ok := decodeLexeme(lexeme)
	if !ok {
		return refused("not_json")
	}
	switch typ {
	case "string", "url":
		if s, ok := v.(string); ok {
			return okRow(s)
		}
		return refused("")
	case "int", "int:inherit":
		if v == nil && typ == "int:inherit" {
			return ValueWrite{Status: "absent"}
		}
		n, ok := v.(json.Number)
		if !ok || !intLexemeRE.MatchString(string(n)) {
			return refused("not_number")
		}
		i, err := strconv.ParseInt(string(n), 10, 64)
		if err != nil || i > MaxSafeInt || i < -MaxSafeInt {
			return refused("not_number")
		}
		return okRow(strconv.FormatInt(i, 10))
	case "float":
		n, ok := v.(json.Number)
		if !ok {
			return refused("not_number")
		}
		f, err := strconv.ParseFloat(string(n), 64)
		if err != nil || math.IsInf(f, 0) {
			return refused("not_number")
		}
		return okRow(FloatText(f))
	case "bool":
		if b, ok := v.(bool); ok {
			return okRow(strconv.FormatBool(b))
		}
		return refused("")
	case "list", "list:labels":
		arr, ok := v.([]any)
		if !ok {
			return refused("")
		}
		items := make([]string, len(arr))
		for i, e := range arr {
			s, ok := e.(string)
			if !ok || typ == "list:labels" && !ValidLabel(s) {
				return refused("")
			}
			items[i] = s
		}
		return okRow(ListText(items))
	case "json":
		if v == nil {
			return ValueWrite{Status: "absent"}
		}
		return okRow(CanonicalJSON(v))
	case "blob":
		if s, ok := v.(string); ok && (s == "" || blobRE.MatchString(s)) {
			return okRow(s)
		}
		return refused("")
	case "secret":
		s, ok := v.(string)
		if !ok {
			return refused("")
		}
		if s == "" {
			return okRow("")
		}
		if LooksSealed(s) {
			return refused("")
		}
		return ValueWrite{Status: "ok", Row: s, Seal: true}
	}
	return refused("")
}

var blobRE = regexp.MustCompile(`^sha256-[0-9a-f]{64}$`)

// ListText — the list element: commas between elements; an empty element, an element with a comma or a text from
// «[» — a JSON array; [] — "".
func ListText(items []string) string {
	if len(items) == 0 {
		return ""
	}
	joined := strings.Join(items, ",")
	asJSON := strings.HasPrefix(joined, "[")
	for _, s := range items {
		asJSON = asJSON || s == "" || strings.Contains(s, ",")
	}
	if !asJSON {
		return joined
	}
	arr := make([]any, len(items))
	for i, s := range items {
		arr[i] = s
	}
	return CanonicalJSON(arr)
}

// CanonicalJSON — canonical JSON (ADR-0072, RFC 8785): keys ascending by UTF-16 code units, no whitespace,
// finite numbers by the ES6 notation (1e21 → 1e+21, -0 → 0), strings with the minimal escapes.
func CanonicalJSON(v any) string {
	var b bytes.Buffer
	canon(&b, v)
	return b.String()
}

func canon(b *bytes.Buffer, v any) {
	switch x := v.(type) {
	case nil:
		b.WriteString("null")
	case bool:
		b.WriteString(strconv.FormatBool(x))
	case json.Number:
		f, err := strconv.ParseFloat(string(x), 64)
		if err != nil {
			b.WriteString(string(x))
			return
		}
		canonNumber(b, f)
	case float64:
		canonNumber(b, x)
	case string:
		canonString(b, x)
	case []any:
		b.WriteByte('[')
		for i, e := range x {
			if i > 0 {
				b.WriteByte(',')
			}
			canon(b, e)
		}
		b.WriteByte(']')
	case map[string]any:
		keys := make([]string, 0, len(x))
		for k := range x {
			keys = append(keys, k)
		}
		sort.Slice(keys, func(i, j int) bool { return utf16Less(keys[i], keys[j]) })
		b.WriteByte('{')
		for i, k := range keys {
			if i > 0 {
				b.WriteByte(',')
			}
			canonString(b, k)
			b.WriteByte(':')
			canon(b, x[k])
		}
		b.WriteByte('}')
	}
}

func canonNumber(b *bytes.Buffer, f float64) {
	if f == 0 {
		b.WriteByte('0')
		return
	}
	// encoding/json uses the ES6 decimal/exponent thresholds and strips exponent leading zeroes.
	text, _ := json.Marshal(f)
	b.Write(text)
}

func utf16Less(a, b string) bool {
	ua, ub := utf16.Encode([]rune(a)), utf16.Encode([]rune(b))
	for i := 0; i < len(ua) && i < len(ub); i++ {
		if ua[i] != ub[i] {
			return ua[i] < ub[i]
		}
	}
	return len(ua) < len(ub)
}

func canonString(b *bytes.Buffer, s string) {
	b.WriteByte('"')
	for _, r := range s {
		switch r {
		case '"':
			b.WriteString(`\"`)
		case '\\':
			b.WriteString(`\\`)
		case '\b':
			b.WriteString(`\b`)
		case '\f':
			b.WriteString(`\f`)
		case '\n':
			b.WriteString(`\n`)
		case '\r':
			b.WriteString(`\r`)
		case '\t':
			b.WriteString(`\t`)
		default:
			if r < 0x20 {
				b.WriteString(`\u00`)
				b.WriteByte("0123456789abcdef"[r>>4])
				b.WriteByte("0123456789abcdef"[r&15])
			} else {
				b.WriteRune(r)
			}
		}
	}
	b.WriteByte('"')
}

// RowToValue — values_by_type of a read: row nil — no element; sealed — the element is an envelope (the answer is the
// mask "***").
func RowToValue(typ string, row *string, sealed bool) ValueRead {
	if row == nil && !sealed {
		return ValueRead{Status: "absent"}
	}
	if typ == "secret" {
		if sealed || *row != "" {
			return ValueRead{Status: "ok", Value: Mask}
		}
		return ValueRead{Status: "ok", Value: ""}
	}
	text := *row
	bad := ValueRead{Status: "unreadable"}
	switch typ {
	case "string", "url", "blob":
		return ValueRead{Status: "ok", Value: text}
	case "int", "int:inherit":
		n, ok := ExactInteger(text)
		if !ok || n.CmpAbs(big.NewInt(MaxSafeInt)) > 0 {
			return bad
		}
		return ValueRead{Status: "ok", Value: json.Number(n.String())}
	case "float":
		if !decimalRE.MatchString(text) {
			return bad
		}
		f, err := strconv.ParseFloat(text, 64)
		if err != nil || math.IsInf(f, 0) {
			return bad
		}
		return ValueRead{Status: "ok", Value: json.Number(FloatText(f))}
	case "bool":
		if text != "true" && text != "false" {
			return bad
		}
		return ValueRead{Status: "ok", Value: text == "true"}
	case "list", "list:labels":
		items, ok := ListRead(text)
		if !ok {
			return bad
		}
		out := make([]any, len(items))
		for i, s := range items {
			out[i] = s
		}
		return ValueRead{Status: "ok", Value: out}
	case "json":
		v, ok := decodeLexeme(text)
		if !ok {
			return bad
		}
		return ValueRead{Status: "ok", Value: v}
	}
	return bad
}

// ListRead — the list element: "" → []; a leading «[» — a JSON array of strings; otherwise split by commas.
func ListRead(text string) ([]string, bool) {
	if text == "" {
		return []string{}, true
	}
	if strings.HasPrefix(text, "[") {
		var items []string
		if json.Unmarshal([]byte(text), &items) != nil || items == nil {
			return nil, false
		}
		return items, true
	}
	return strings.Split(text, ","), true
}
