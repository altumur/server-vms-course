package apidoor

// Handwritten runtime for gen_door.py output, copied into the generated package.
// Only OpenAPI-independent behavior lives here: JSON values, numeric comparison, form-urlencoded query
// parsing (OpenAPI style=form, in=query), and JSON encoding.

import (
	"bytes"
	"encoding/json"
	"math"
	"math/big"
	"sort"
	"strconv"
	"strings"
	"unicode/utf8"
)

// Violation reports a schema violation: At is its JSON Pointer (empty for root); Rule is the keyword
// (type, required, pattern, minLength, const, enum, oneOf, not, additionalProperties, minimum, ...; utf8 means invalid
// UTF-8 under a string constraint). Journal only: do not return input-quoting details to callers.
type Violation struct {
	At   string
	Rule string
}

func (v *Violation) Error() string { return "schema: " + v.Rule + " at " + strconv.Quote(v.At) }

func violation(at, rule string) *Violation { return &Violation{At: at, Rule: rule} }

func child(at, name string) string {
	return at + "/" + strings.ReplaceAll(strings.ReplaceAll(name, "~", "~0"), "/", "~1")
}

func index(at string, i int) string { return at + "/" + strconv.Itoa(i) }

// Body is a generated response type. SchemaName identifies components/schemas or an inline <Op><status>
// schema; appendJSON emits body bytes, or plain text for text/plain.
type Body interface {
	SchemaName() string
	appendJSON([]byte) []byte
}

// Response is the wire status, ordered headers and body bytes, written unchanged by the handwritten frame.
// HEAD omits the body per RFC 9110 section9.3.2; that is the frame's responsibility.
type Response struct {
	Code   int
	Header [][2]string
	Body   []byte
}

// Checker inputs: nil, bool, string, []any, map[string]any and int64, uint64, float64 or json.Number.
// Both kit jsonstrict (int64 for numbers without '.' or exponent, otherwise float64) and encoding/json
// with UseNumber produce these representations.

func isString(v any) bool { _, ok := v.(string); return ok }
func isBoolean(v any) bool { _, ok := v.(bool); return ok }
func isNull(v any) bool   { return v == nil }
func isObject(v any) bool { _, ok := v.(map[string]any); return ok }
func isArray(v any) bool  { _, ok := v.([]any); return ok }

// isInteger requires lexical integers: int64, uint64 or json.Number without '.', e, E.
// This is narrower than Draft 2020-12, where1.0 is integer; the kit's N2.1 body form distinguishes1 from1.0.
func isInteger(v any) bool {
	switch x := v.(type) {
	case int64, uint64:
		return true
	case json.Number:
		return !strings.ContainsAny(string(x), ".eE")
	}
	return false
}

func isNumber(v any) bool {
	switch v.(type) {
	case int64, uint64, float64, json.Number:
		return true
	}
	return false
}

// number returns the exact JSON numeric value; inf is +/-1 for binary64 overflow, otherwise0.
func number(v any) (r *big.Rat, inf int, ok bool) {
	switch x := v.(type) {
	case int64:
		return new(big.Rat).SetInt64(x), 0, true
	case uint64:
		return new(big.Rat).SetUint64(x), 0, true
	case float64:
		if math.IsInf(x, 1) {
			return nil, 1, true
		}
		if math.IsInf(x, -1) {
			return nil, -1, true
		}
		if math.IsNaN(x) {
			return nil, 0, false
		}
		return new(big.Rat).SetFloat64(x), 0, true
	case json.Number:
		r, ok := new(big.Rat).SetString(string(x))
		if !ok {
			f, err := strconv.ParseFloat(string(x), 64)
			if err != nil && math.IsInf(f, 0) {
				if f > 0 {
					return nil, 1, true
				}
				return nil, -1, true
			}
			return nil, 0, false
		}
		return r, 0, true
	}
	return nil, 0, false
}

// cmpBound returns the sign of v-bound; bound is the schema's decimal limit.
func cmpBound(v any, bound string) (int, bool) {
	r, inf, ok := number(v)
	if !ok {
		return 0, false
	}
	if inf != 0 {
		return inf, true
	}
	b, _ := new(big.Rat).SetString(bound)
	return r.Cmp(b), true
}

// equalJSON compares JSON const/enum values, using numeric value equality.
func equalJSON(a, b any) bool {
	if isNumber(a) && isNumber(b) {
		if !isInteger(a) || !isInteger(b) {
			return toFloat64(a) == toFloat64(b)
		}
		x, xi, ok1 := number(a)
		y, yi, ok2 := number(b)
		if !ok1 || !ok2 {
			return false
		}
		if xi != 0 || yi != 0 {
			return xi == yi
		}
		return x.Cmp(y) == 0
	}
	switch x := a.(type) {
	case nil:
		return b == nil
	case bool:
		y, ok := b.(bool)
		return ok && x == y
	case string:
		y, ok := b.(string)
		return ok && x == y
	case []any:
		y, ok := b.([]any)
		if !ok || len(x) != len(y) {
			return false
		}
		for i := range x {
			if !equalJSON(x[i], y[i]) {
				return false
			}
		}
		return true
	case map[string]any:
		y, ok := b.(map[string]any)
		if !ok || len(x) != len(y) {
			return false
		}
		for k, xv := range x {
			yv, ok := y[k]
			if !ok || !equalJSON(xv, yv) {
				return false
			}
		}
		return true
	}
	return false
}

func sortedKeys(m map[string]any) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}

func runeCount(s string) int { return utf8.RuneCountInString(s) }

// Convert validated values to typed fields, only after schema validation.

func toInt64(v any) int64 {
	switch x := v.(type) {
	case int64:
		return x
	case uint64:
		return int64(x)
	case json.Number:
		i, _ := strconv.ParseInt(string(x), 10, 64)
		return i
	case float64:
		return int64(x)
	}
	return 0
}

func toUint64(v any) uint64 {
	switch x := v.(type) {
	case int64:
		return uint64(x)
	case uint64:
		return x
	case json.Number:
		u, _ := strconv.ParseUint(string(x), 10, 64)
		return u
	case float64:
		return uint64(x)
	}
	return 0
}

func toFloat64(v any) float64 {
	switch x := v.(type) {
	case int64:
		return float64(x)
	case uint64:
		return float64(x)
	case json.Number:
		f, _ := strconv.ParseFloat(string(x), 64)
		return f
	case float64:
		return x
	}
	return 0
}

// representable checks that encoding body b preserves value v without Go type loss (for example, an
// unconstrained integer beyond int64). json selects JSON value comparison; otherwise compare text.
func representable(v any, b Body, json bool) bool {
	raw := b.appendJSON(nil)
	if !json {
		s, ok := v.(string)
		return ok && s == string(raw)
	}
	w, err := decodeJSON(raw)
	return err == nil && equalJSON(v, w)
}

// decodeJSON reads checker values with encoding/json and json.Number.
func decodeJSON(b []byte) (any, error) {
	d := json.NewDecoder(bytes.NewReader(b))
	d.UseNumber()
	var v any
	if err := d.Decode(&v); err != nil {
		return nil, err
	}
	if d.More() {
		return nil, errTrailing
	}
	return v, nil
}

type constError string

func (e constError) Error() string { return string(e) }

const errTrailing = constError("trailing data after JSON value")

// Encode strings as raw UTF-8 except quotes, backslashes and controls; replace invalid UTF-8 by U+FFFD.
// Map names follow UTF-8 byte order; object fields follow schema properties order.

func appendString(b []byte, s string) []byte {
	b = append(b, '"')
	for i := 0; i < len(s); {
		c := s[i]
		if c < utf8.RuneSelf {
			switch {
			case c == '"' || c == '\\':
				b = append(b, '\\', c)
			case c < 0x20:
				switch c {
				case '\n':
					b = append(b, '\\', 'n')
				case '\r':
					b = append(b, '\\', 'r')
				case '\t':
					b = append(b, '\\', 't')
				default:
					b = append(b, '\\', 'u', '0', '0', "0123456789abcdef"[c>>4], "0123456789abcdef"[c&15])
				}
			default:
				b = append(b, c)
			}
			i++
			continue
		}
		r, n := utf8.DecodeRuneInString(s[i:])
		if r == utf8.RuneError && n == 1 {
			b = append(b, `�`...)
		} else {
			b = append(b, s[i:i+n]...)
		}
		i += n
	}
	return append(b, '"')
}

// appendFloat follows encoding/json; NaN/infinities are invalid JSON and cannot pass the body schema.
func appendFloat(b []byte, f float64) []byte {
	if math.IsNaN(f) || math.IsInf(f, 0) {
		return append(b, "null"...)
	}
	abs := math.Abs(f)
	format := byte('f')
	if abs != 0 && (abs < 1e-6 || abs >= 1e21) {
		format = 'e'
	}
	b = strconv.AppendFloat(b, f, format, -1, 64)
	if format == 'e' {
		n := len(b)
		if n >= 4 && b[n-4] == 'e' && b[n-3] == '-' && b[n-2] == '0' {
			b[n-2] = b[n-1]
			b = b[:n-1]
		}
	}
	return b
}

// field emits an object field name and its preceding comma after the first field.
func field(b []byte, n *int, name string) []byte {
	if *n > 0 {
		b = append(b, ',')
	}
	*n++
	b = appendString(b, name)
	return append(b, ':')
}

func appendAny(b []byte, v any) []byte {
	switch x := v.(type) {
	case nil:
		return append(b, "null"...)
	case bool:
		return strconv.AppendBool(b, x)
	case string:
		return appendString(b, x)
	case int64:
		return strconv.AppendInt(b, x, 10)
	case uint64:
		return strconv.AppendUint(b, x, 10)
	case float64:
		return appendFloat(b, x)
	case json.Number:
		return append(b, x...)
	case []any:
		b = append(b, '[')
		for i, e := range x {
			if i > 0 {
				b = append(b, ',')
			}
			b = appendAny(b, e)
		}
		return append(b, ']')
	case map[string]any:
		b = append(b, '{')
		n := 0
		for _, k := range sortedKeys(x) {
			b = field(b, &n, k)
			b = appendAny(b, x[k])
		}
		return append(b, '}')
	}
	return append(b, "null"...)
}

// Form-urlencoded query parsing (WHATWG URL): split '&' pairs, skip empty pairs, split at the first '=',
// default a missing value to empty, decode '+' as space and %XX as a byte; retain malformed '%' literally.
// Keep bytes without UTF-8 decoding; the parameter's schema performs that validation.

func parseForm(raw string) [][2]string {
	var out [][2]string
	for _, part := range strings.Split(raw, "&") {
		if part == "" {
			continue
		}
		name, value, _ := strings.Cut(part, "=")
		out = append(out, [2]string{percentDecode(name), percentDecode(value)})
	}
	return out
}

func unhex(c byte) (byte, bool) {
	switch {
	case '0' <= c && c <= '9':
		return c - '0', true
	case 'a' <= c && c <= 'f':
		return c - 'a' + 10, true
	case 'A' <= c && c <= 'F':
		return c - 'A' + 10, true
	}
	return 0, false
}

func percentDecode(s string) string {
	if !strings.ContainsAny(s, "%+") {
		return s
	}
	b := make([]byte, 0, len(s))
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c == '+' {
			b = append(b, ' ')
			continue
		}
		if c == '%' && i+2 < len(s) {
			hi, ok1 := unhex(s[i+1])
			lo, ok2 := unhex(s[i+2])
			if ok1 && ok2 {
				b = append(b, hi<<4|lo)
				i += 2
				continue
			}
		}
		b = append(b, c)
	}
	return string(b)
}

func formValues(pairs [][2]string, name string) []string {
	var out []string
	for _, p := range pairs {
		if p[0] == name {
			out = append(out, p[1])
		}
	}
	return out
}

// QueryReason identifies how a query parameter violates its OpenAPI form.
type QueryReason int

const (
	QueryAbsent   QueryReason = 1 + iota // A required parameter is missing.
	QueryRepeated                        // A scalar parameter repeats (schema is not array).
	QueryValue                           // Value violates its parameter schema; Schema/Rule identify the constraint.
)

// QueryError reports an invalid query parameter. OpenAPI's form does not choose its status/kind
// (description prose does); handwritten code chooses the refusal.
type QueryError struct {
	Param  string
	Reason QueryReason
	Schema string // Referenced components/schemas name, or empty for an inline parameter.
	Rule   string // Violated keyword for QueryValue.
}

func (e *QueryError) Error() string {
	switch e.Reason {
	case QueryAbsent:
		return "query: " + e.Param + " absent"
	case QueryRepeated:
		return "query: " + e.Param + " repeated"
	}
	return "query: " + e.Param + " out of schema " + e.Schema + " (" + e.Rule + ")"
}
