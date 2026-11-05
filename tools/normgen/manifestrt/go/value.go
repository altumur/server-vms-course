// Hand-written runtime of the part `loader` (tools/normgen/manifestrt/go; the kit copies it, DO NOT EDIT): values of
// the tree in author order, conversions for the libraries, JCS (RFC 8785; ADR-0072).
package manifest

import (
	"bytes"
	"encoding/json"
	"fmt"
	"math"
	"sort"
	"strconv"
	"strings"
	"unicode/utf16"
)

// Obj — a JSON object in author order (the tree of the loader, the schema). Ptr — the JSON Pointer of a schema node.
type Obj struct {
	Keys []string
	M    map[string]any
	Ptr  string
}

func newObj() *Obj { return &Obj{M: map[string]any{}} }

// Get — the value of a key and whether it is there.
func (o *Obj) Get(k string) (any, bool) {
	v, ok := o.M[k]
	return v, ok
}

// Set — put a key (appended at the end of author order when new).
func (o *Obj) Set(k string, v any) {
	if _, ok := o.M[k]; !ok {
		o.Keys = append(o.Keys, k)
	}
	o.M[k] = v
}

// decodeOrdered — JSON text → values: *Obj (author order), []any, string, bool, nil, int64 (an integer notation),
// float64 (a fraction or an exponent); ptrs — set Ptr of every object (the schema).
func decodeOrdered(data []byte, ptrs bool) (any, error) {
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.UseNumber()
	v, err := decodeValue(dec, "", ptrs)
	if err != nil {
		return nil, err
	}
	if dec.More() {
		return nil, fmt.Errorf("extra JSON after the value")
	}
	return v, nil
}

func escapePtr(s string) string { return strings.ReplaceAll(strings.ReplaceAll(s, "~", "~0"), "/", "~1") }

func decodeValue(dec *json.Decoder, ptr string, ptrs bool) (any, error) {
	t, err := dec.Token()
	if err != nil {
		return nil, err
	}
	switch x := t.(type) {
	case json.Delim:
		switch x {
		case '{':
			o := newObj()
			if ptrs {
				o.Ptr = ptr
			}
			for dec.More() {
				kt, err := dec.Token()
				if err != nil {
					return nil, err
				}
				k := kt.(string)
				v, err := decodeValue(dec, ptr+"/"+escapePtr(k), ptrs)
				if err != nil {
					return nil, err
				}
				o.Set(k, v)
			}
			if _, err := dec.Token(); err != nil {
				return nil, err
			}
			return o, nil
		case '[':
			l := []any{}
			for i := 0; dec.More(); i++ {
				v, err := decodeValue(dec, ptr+"/"+strconv.Itoa(i), ptrs)
				if err != nil {
					return nil, err
				}
				l = append(l, v)
			}
			if _, err := dec.Token(); err != nil {
				return nil, err
			}
			return l, nil
		}
	case json.Number:
		s := string(x)
		if !strings.ContainsAny(s, ".eE") {
			if i, err := strconv.ParseInt(s, 10, 64); err == nil {
				return i, nil
			}
		}
		f, err := strconv.ParseFloat(s, 64)
		if err != nil {
			return nil, err
		}
		return f, nil
	case string, bool, nil:
		return x, nil
	}
	return nil, fmt.Errorf("unexpected token %v", t)
}

// plain — values for CEL: map[string]any, []any, int64, float64, string, bool, nil.
func plain(v any) any {
	switch x := v.(type) {
	case *Obj:
		m := make(map[string]any, len(x.Keys))
		for _, k := range x.Keys {
			m[k] = plain(x.M[k])
		}
		return m
	case []any:
		out := make([]any, len(x))
		for i, e := range x {
			out[i] = plain(e)
		}
		return out
	}
	return v
}

// forSchema — values for jsonschema v6: numbers as json.Number (an integer stays an integer notation).
func forSchema(v any) any {
	switch x := v.(type) {
	case *Obj:
		m := make(map[string]any, len(x.Keys))
		for _, k := range x.Keys {
			m[k] = forSchema(x.M[k])
		}
		return m
	case []any:
		out := make([]any, len(x))
		for i, e := range x {
			out[i] = forSchema(e)
		}
		return out
	case int64:
		return json.Number(strconv.FormatInt(x, 10))
	case float64:
		return json.Number(strconv.FormatFloat(x, 'g', -1, 64))
	}
	return v
}

func deepCopy(v any) any {
	switch x := v.(type) {
	case *Obj:
		o := &Obj{Keys: append([]string(nil), x.Keys...), M: make(map[string]any, len(x.M)), Ptr: x.Ptr}
		for k, e := range x.M {
			o.M[k] = deepCopy(e)
		}
		return o
	case []any:
		out := make([]any, len(x))
		for i, e := range x {
			out[i] = deepCopy(e)
		}
		return out
	}
	return v
}

// JCS — the canonical bytes (RFC 8785): keys by UTF-16 code units, numbers as ECMAScript Number.toString.
func JCS(v any) ([]byte, error) {
	var b bytes.Buffer
	if err := jcs(&b, v); err != nil {
		return nil, err
	}
	return b.Bytes(), nil
}

func jcs(b *bytes.Buffer, v any) error {
	switch x := v.(type) {
	case nil:
		b.WriteString("null")
	case bool:
		b.WriteString(strconv.FormatBool(x))
	case int64:
		if x > 1<<53 || x < -(1<<53) {
			return fmt.Errorf("JCS: integer %d outside binary64", x)
		}
		b.WriteString(jcsNumber(float64(x)))
	case float64:
		if math.IsInf(x, 0) || math.IsNaN(x) {
			return fmt.Errorf("JCS: non-finite number")
		}
		b.WriteString(jcsNumber(x))
	case string:
		jcsString(b, x)
	case []any:
		b.WriteByte('[')
		for i, e := range x {
			if i > 0 {
				b.WriteByte(',')
			}
			if err := jcs(b, e); err != nil {
				return err
			}
		}
		b.WriteByte(']')
	case *Obj:
		keys := append([]string(nil), x.Keys...)
		sort.Slice(keys, func(i, j int) bool { return utf16Less(keys[i], keys[j]) })
		b.WriteByte('{')
		for i, k := range keys {
			if i > 0 {
				b.WriteByte(',')
			}
			jcsString(b, k)
			b.WriteByte(':')
			if err := jcs(b, x.M[k]); err != nil {
				return err
			}
		}
		b.WriteByte('}')
	default:
		return fmt.Errorf("JCS: value %T", v)
	}
	return nil
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

func jcsString(b *bytes.Buffer, s string) {
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
				fmt.Fprintf(b, `\u%04x`, r)
			} else {
				b.WriteRune(r)
			}
		}
	}
	b.WriteByte('"')
}

// jcsNumber — RFC 8785 § 3.2.2.3 (ECMAScript Number.toString).
func jcsNumber(f float64) string {
	if f == 0 {
		return "0"
	}
	a := math.Abs(f)
	if a >= 1e-6 && a < 1e21 {
		return strconv.FormatFloat(f, 'f', -1, 64)
	}
	s := strconv.FormatFloat(f, 'e', -1, 64)
	m, e, _ := strings.Cut(s, "e")
	sign, digits := e[:1], strings.TrimLeft(e[1:], "0")
	return m + "e" + sign + digits
}
