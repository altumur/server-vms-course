// Shared runtime of declarative policies. No SDK operations are performed here.
package workerpolicy

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"strconv"
	"strings"
	"unicode/utf8"
)

// DecodeJSON preserves integer lexemes and rejects duplicate keys, invalid UTF-8,
// unpaired UTF-16 escapes and trailing values. This is semantic JSON, not TSV transport.
func DecodeJSON(raw []byte) (any, error) {
	if !utf8.Valid(raw) {
		return nil, fmt.Errorf("JSON: invalid UTF-8")
	}
	// encoding/json repairs malformed surrogate escapes. Reject them before decoding.
	quoted := false
	for i := 0; i < len(raw); i++ {
		if raw[i] == '"' {
			quoted = !quoted
			continue
		}
		if !quoted || raw[i] != '\\' {
			continue
		}
		i++
		if i >= len(raw) {
			break
		}
		if raw[i] != 'u' {
			continue
		}
		if i+4 >= len(raw) {
			return nil, fmt.Errorf("JSON: incomplete Unicode escape")
		}
		n, err := strconv.ParseUint(string(raw[i+1:i+5]), 16, 16)
		if err != nil {
			return nil, fmt.Errorf("JSON: invalid Unicode escape")
		}
		i += 4
		if n >= 0xdc00 && n <= 0xdfff {
			return nil, fmt.Errorf("JSON: unpaired low surrogate")
		}
		if n < 0xd800 || n > 0xdbff {
			continue
		}
		if i+6 >= len(raw) || raw[i+1] != '\\' || raw[i+2] != 'u' {
			return nil, fmt.Errorf("JSON: unpaired high surrogate")
		}
		low, e := strconv.ParseUint(string(raw[i+3:i+7]), 16, 16)
		if e != nil || low < 0xdc00 || low > 0xdfff {
			return nil, fmt.Errorf("JSON: unpaired high surrogate")
		}
		i += 6
	}
	d := json.NewDecoder(bytes.NewReader(raw))
	d.UseNumber()
	v, err := jsonToken(d)
	if err != nil {
		return nil, err
	}
	if _, e := d.Token(); e != io.EOF {
		return nil, fmt.Errorf("JSON: trailing data")
	}
	return v, nil
}

func jsonToken(d *json.Decoder) (any, error) {
	t, err := d.Token()
	if err != nil {
		return nil, err
	}
	switch v := t.(type) {
	case json.Delim:
		switch v {
		case '{':
			out := map[string]any{}
			for d.More() {
				key, e := d.Token()
				if e != nil {
					return nil, e
				}
				k, ok := key.(string)
				if !ok {
					return nil, fmt.Errorf("JSON: object key")
				}
				if _, ok := out[k]; ok {
					return nil, fmt.Errorf("JSON: duplicate key %q", k)
				}
				value, e := jsonToken(d)
				if e != nil {
					return nil, e
				}
				out[k] = value
			}
			end, e := d.Token()
			if e != nil || end != json.Delim('}') {
				return nil, fmt.Errorf("JSON: unclosed object")
			}
			return out, nil
		case '[':
			out := []any{}
			for d.More() {
				value, e := jsonToken(d)
				if e != nil {
					return nil, e
				}
				out = append(out, value)
			}
			end, e := d.Token()
			if e != nil || end != json.Delim(']') {
				return nil, fmt.Errorf("JSON: unclosed array")
			}
			return out, nil
		}
		return nil, fmt.Errorf("JSON: unexpected delimiter %v", v)
	case json.Number:
		if strings.ContainsAny(string(v), ".eE") {
			f, e := v.Float64()
			if e != nil || !finite(f) {
				return nil, fmt.Errorf("JSON: nonfinite number")
			}
		}
		return v, nil
	default:
		return v, nil
	}
}

func finite(f float64) bool { return !math.IsNaN(f) && !math.IsInf(f, 0) }

func copyValue(v any) any {
	switch x := v.(type) {
	case map[string]any:
		o := map[string]any{}
		for k, v := range x {
			o[k] = copyValue(v)
		}
		return o
	case []any:
		o := make([]any, len(x))
		for i, v := range x {
			o[i] = copyValue(v)
		}
		return o
	default:
		return x
	}
}

func typeChoices(t string) []string {
	depth, start := 0, 0
	out := []string{}
	for i, ch := range t {
		if ch == '<' {
			depth++
		}
		if ch == '>' {
			depth--
		}
		if ch == '|' && depth == 0 {
			out = append(out, strings.TrimSpace(t[start:i]))
			start = i + 1
		}
	}
	return append(out, strings.TrimSpace(t[start:]))
}

func (p *Program) typed(v any, typ string) (any, error) {
	choices := typeChoices(typ)
	if len(choices) > 1 {
		for _, t := range choices {
			if o, e := p.typed(v, t); e == nil {
				return o, nil
			}
		}
		return nil, fmt.Errorf("expected %s", typ)
	}
	switch typ {
	case "dyn":
		return copyValue(v), nil
	case "null":
		if v == nil {
			return nil, nil
		}
	case "bool", "boolean":
		if b, ok := v.(bool); ok {
			return b, nil
		}
	case "string":
		if s, ok := v.(string); ok && utf8.ValidString(s) {
			return s, nil
		}
	case "int", "integer":
		switch n := v.(type) {
		case int64:
			return n, nil
		case json.Number:
			if !strings.ContainsAny(string(n), ".eE") {
				if i, e := n.Int64(); e == nil {
					return i, nil
				}
			}
		}
	case "double", "number":
		f, ok := numeric(v)
		if ok && finite(f) {
			if typ == "double" {
				return f, nil
			}
			return v, nil
		}
	case "object":
		if m, ok := v.(map[string]any); ok {
			return copyValue(m), nil
		}
	case "array":
		if a, ok := v.([]any); ok {
			return copyValue(a), nil
		}
	default:
		if strings.HasPrefix(typ, "list<") && strings.HasSuffix(typ, ">") {
			if a, ok := v.([]any); ok {
				out := make([]any, len(a))
				for i, x := range a {
					y, e := p.typed(x, typ[5:len(typ)-1])
					if e != nil {
						return nil, e
					}
					out[i] = y
				}
				return out, nil
			}
		} else if strings.HasPrefix(typ, "map<string,") && strings.HasSuffix(typ, ">") {
			if m, ok := v.(map[string]any); ok {
				out := map[string]any{}
				for k, x := range m {
					y, e := p.typed(x, strings.TrimSpace(typ[11:len(typ)-1]))
					if e != nil {
						return nil, e
					}
					out[k] = y
				}
				return out, nil
			}
		} else if fields, ok := p.d.Types[typ]; ok {
			return p.record(v, fields)
		}
	}
	return nil, fmt.Errorf("expected %s, got %T", typ, v)
}

func (p *Program) record(v any, fields []Field) (map[string]any, error) {
	m, ok := v.(map[string]any)
	if !ok {
		return nil, fmt.Errorf("expected an object")
	}
	if len(m) != len(fields) {
		return nil, fmt.Errorf("payload fields differ from declaration")
	}
	out := map[string]any{}
	for _, f := range fields {
		x, ok := m[f.Name]
		if !ok {
			return nil, fmt.Errorf("missing payload field %s", f.Name)
		}
		y, e := p.typed(x, f.Type)
		if e != nil {
			return nil, fmt.Errorf("%s: %w", f.Name, e)
		}
		out[f.Name] = y
	}
	return out, nil
}

func numeric(v any) (float64, bool) {
	switch n := v.(type) {
	case int64:
		return float64(n), true
	case float64:
		return n, true
	case json.Number:
		f, e := n.Float64()
		return f, e == nil
	}
	return 0, false
}

func celInput(v any) (any, error) {
	switch x := v.(type) {
	case json.Number:
		if !strings.ContainsAny(string(x), ".eE") {
			i, e := x.Int64()
			if e != nil {
				return nil, fmt.Errorf("CEL integer outside int64: %s", x)
			}
			return i, nil
		}
		f, e := x.Float64()
		if e != nil || !finite(f) {
			return nil, fmt.Errorf("CEL number is not finite")
		}
		return f, nil
	case map[string]any:
		m := map[string]any{}
		for k, v := range x {
			y, e := celInput(v)
			if e != nil {
				return nil, e
			}
			m[k] = y
		}
		return m, nil
	case []any:
		a := make([]any, len(x))
		for i, v := range x {
			y, e := celInput(v)
			if e != nil {
				return nil, e
			}
			a[i] = y
		}
		return a, nil
	default:
		return v, nil
	}
}
