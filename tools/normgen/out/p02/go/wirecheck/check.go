// Ручная среда провода wire.tsv: сравнение полного нативного ответа, не оболочки vectors.
package wirecheck

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"strings"
	"unicode/utf8"
)

type assertion struct {
	Pointer  string `json:"pointer"`
	Test     string `json:"test"`
	Compare  string `json:"compare"`
	Value    any    `json:"value"`
	MinBytes int    `json:"min_bytes"`
	Whole    bool   `json:"whole"`
	Decode   string `json:"decode"`
}
type native struct {
	Type   any    `json:"type"`
	Frame  string `json:"frame"`
	Schema any    `json:"schema"`
}
type expected struct {
	Code    int         `json:"code"`
	Ignore  bool        `json:"ignore"`
	Ignored []string    `json:"ignored"`
	Value   any         `json:"value"`
	Raw     *string     `json:"raw"`
	Compare string      `json:"compare"`
	Native  native      `json:"native"`
	Asserts []assertion `json:"asserts"`
}

// Check — код, рамка, полный тип/схема, затем сравнение и утверждения. ignore_stdout исключает только stdout.
func Check(code int, output []byte, spec string) error {
	var e expected
	dec := json.NewDecoder(strings.NewReader(spec))
	dec.UseNumber()
	if err := dec.Decode(&e); err != nil {
		return fmt.Errorf("wire expectation: %v", err)
	}
	if code != e.Code {
		return fmt.Errorf("exit %d, want %d", code, e.Code)
	}
	if e.Ignore {
		return nil
	}
	var got any
	if e.Native.Frame == "raw" {
		got = output
	} else {
		var err error
		got, err = parseJSON(output)
		if err != nil {
			return fmt.Errorf("native JSON: %v", err)
		}
		if e.Native.Frame == "json-lf" {
			d := json.NewDecoder(bytes.NewReader(output))
			var value json.RawMessage
			if err := d.Decode(&value); err != nil {
				return err
			}
			if len(output) == 0 || bytes.ContainsAny(output[:1], " \t\r\n") || string(output[d.InputOffset():]) != "\n" {
				return fmt.Errorf("native json-lf: expected value followed by exactly LF")
			}
		} else if e.Native.Frame != "json" {
			return fmt.Errorf("unknown native frame %q", e.Native.Frame)
		}
		types := []any{e.Native.Type}
		if ts, ok := e.Native.Type.([]any); ok {
			types = ts
		}
		valid := false
		for _, typ := range types {
			if typ == "value" || typ == typeOf(got) {
				valid = true
			}
		}
		if !valid {
			return fmt.Errorf("native type %s, want %v", typeOf(got), e.Native.Type)
		}
		if e.Native.Schema != nil {
			var errs []Violation
			validate(e.Native.Schema, got, "", &errs)
			if len(errs) > 0 {
				return fmt.Errorf("native %v", &errs[0])
			}
		}
	}
	want := e.Value
	if e.Raw != nil {
		raw, err := base64.StdEncoding.Strict().DecodeString(*e.Raw)
		if err != nil {
			return fmt.Errorf("raw expectation: %v", err)
		}
		want = raw
	}
	if !compare(without(want, e.Ignored), without(got, e.Ignored), e.Compare) {
		return fmt.Errorf("compare %s: got %s, want %s", e.Compare, show(got), show(want))
	}
	for _, a := range e.Asserts {
		value, found := pointer(got, a.Pointer)
		if a.Test == "absent" {
			if found {
				return fmt.Errorf("assert %s: expected absent", a.Pointer)
			}
			continue
		}
		if !found {
			return fmt.Errorf("assert %s: missing", a.Pointer)
		}
		if a.Decode == "json" {
			text, ok := value.(string)
			if !ok {
				return fmt.Errorf("assert %s: decode json expects string", a.Pointer)
			}
			var err error
			value, err = parseJSON([]byte(text))
			if err != nil {
				return fmt.Errorf("assert %s: %v", a.Pointer, err)
			}
		}
		switch a.Test {
		case "prefix":
			s, ok := value.(string)
			p, pok := a.Value.(string)
			if !ok || !pok || !strings.HasPrefix(s, p) {
				return fmt.Errorf("assert %s: prefix", a.Pointer)
			}
		case "no-leak":
			s, ok := value.(string)
			if !ok {
				return fmt.Errorf("assert %s: no-leak expects string", a.Pointer)
			}
			secrets, ok := a.Value.([]any)
			if !ok {
				return fmt.Errorf("assert %s: no-leak expects secrets array", a.Pointer)
			}
			for _, v := range secrets {
				secret, ok := v.(string)
				if !ok || a.MinBytes < 1 {
					return fmt.Errorf("assert %s: invalid no-leak", a.Pointer)
				}
				b := []byte(secret)
				if len(b) < a.MinBytes {
					continue
				}
				if a.Whole {
					if strings.Contains(s, secret) {
						return fmt.Errorf("assert %s: secret leaked", a.Pointer)
					}
				} else {
					for i := 0; i+a.MinBytes <= len(b); i++ {
						if bytes.Contains([]byte(s), b[i:i+a.MinBytes]) {
							return fmt.Errorf("assert %s: secret fragment leaked", a.Pointer)
						}
					}
				}
			}
		case "":
			rule := a.Compare
			if rule == "" {
				rule = strings.TrimPrefix(e.Compare, "lines-")
			}
			if !compare(a.Value, value, rule) {
				return fmt.Errorf("assert %s: compare %s", a.Pointer, rule)
			}
		default:
			return fmt.Errorf("assert %s: unknown test %q", a.Pointer, a.Test)
		}
	}
	return nil
}

func compare(want, got any, rule string) bool {
	switch rule {
	case "value":
		return equalJSONValue(want, got)
	case "subset":
		switch w := want.(type) {
		case map[string]any:
			g, ok := got.(map[string]any)
			if !ok || (len(w) == 0 && len(g) != 0) {
				return false
			}
			for k, v := range w {
				gv, has := g[k]
				if !has || !compare(v, gv, "subset") {
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
				if !compare(v, g[i], "subset") {
					return false
				}
			}
			return true
		default:
			return equalJSONValue(want, got)
		}
	case "raw":
		w, wok := raw(want)
		g, gok := raw(got)
		return wok && gok && bytes.Equal(w, g)
	case "set":
		w, wok := want.([]any)
		g, gok := got.([]any)
		if !wok || !gok {
			return false
		}
		for _, pair := range [][2][]any{{w, g}, {g, w}} {
			for _, a := range pair[0] {
				found := false
				for _, b := range pair[1] {
					if equalJSONValue(a, b) {
						found = true
						break
					}
				}
				if !found {
					return false
				}
			}
		}
		return true
	case "object-sets":
		w, wok := want.(map[string]any)
		g, gok := got.(map[string]any)
		if !wok || !gok || len(w) != len(g) {
			return false
		}
		for k, v := range w {
			if !compare(v, g[k], "set") {
				return false
			}
		}
		return true
	}
	return false
}
func raw(v any) ([]byte, bool) {
	switch x := v.(type) {
	case []byte:
		return x, true
	case string:
		return []byte(x), true
	}
	return nil, false
}
func show(v any) string { b, _ := json.Marshal(v); return string(b) }
func pointer(v any, p string) (any, bool) {
	if p == "" {
		return v, true
	}
	for _, s := range strings.Split(p[1:], "/") {
		s = strings.ReplaceAll(strings.ReplaceAll(s, "~1", "/"), "~0", "~")
		switch x := v.(type) {
		case map[string]any:
			var ok bool
			v, ok = x[s]
			if !ok {
				return nil, false
			}
		case []any:
			var i int
			if _, err := fmt.Sscanf(s, "%d", &i); err != nil || fmt.Sprint(i) != s || i < 0 || i >= len(x) {
				return nil, false
			}
			v = x[i]
		default:
			return nil, false
		}
	}
	return v, true
}

func parseJSON(data []byte) (any, error) {
	if !utf8.Valid(data) || !json.Valid(data) {
		return nil, fmt.Errorf("not one strict UTF-8 JSON value")
	}
	return StrictJSON(data)
}

// without resolves all paths in the original value; array indices do not shift between removals.
func without(v any, paths []string) any {
	if len(paths) == 0 {
		return v
	}
	by := map[string][]string{}
	drop := map[string]bool{}
	for _, path := range paths {
		first, rest, nested := strings.Cut(path[1:], "/")
		key := strings.ReplaceAll(strings.ReplaceAll(first, "~1", "/"), "~0", "~")
		if nested {
			by[key] = append(by[key], "/"+rest)
		} else {
			drop[key] = true
		}
	}
	switch x := v.(type) {
	case map[string]any:
		out := map[string]any{}
		for k, value := range x {
			if !drop[k] {
				out[k] = without(value, by[k])
			}
		}
		return out
	case []any:
		out := []any{}
		for i, value := range x {
			key := fmt.Sprint(i)
			if !drop[key] {
				out = append(out, without(value, by[key]))
			}
		}
		return out
	}
	return v
}
