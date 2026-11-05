// Ручная среда тел двери урока (ADR-0125 № 2, P/06 часть 3б): проверка значения JSON по схеме из сборки bodies.go.
//
// Подмножество JSON Schema 2020-12 — ровно слова схем OpenAPI урока: $ref (#/$defs/<имя>), type, enum, const, allOf,
// anyOf, oneOf, not, if/then/else, properties, patternProperties, additionalProperties, unevaluatedProperties,
// propertyNames, required, dependentRequired, minProperties, maxProperties, items, minItems, maxItems, uniqueItems,
// minLength, maxLength, pattern, minimum, maximum, exclusiveMinimum, exclusiveMaximum; аннотации (description,
// format, default, readOnly, contentMediaType, title, examples) не судятся. Числа — по значению (big.Rat), integer —
// математически целое (1.0 — integer, как в 2020-12); длина строки — в символах Unicode.
package wirecheck

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"math/big"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"sync"
	"unicode/utf8"
)

// Violation — первое нарушение схемы: путь значения (JSON Pointer) и правило.
type Violation struct {
	At   string
	Rule string
}

func (v *Violation) Error() string { return "schema: " + v.Rule + " at " + strconv.Quote(v.At) }

var (
	defsOnce sync.Once
	defs     map[string]any
	rxCache  sync.Map
)

func schemaDefs() map[string]any {
	defsOnce.Do(func() {
		dec := json.NewDecoder(strings.NewReader(bundle))
		dec.UseNumber()
		var root map[string]any
		if err := dec.Decode(&root); err != nil {
			panic("apidoor: the schema bundle is not JSON: " + err.Error())
		}
		defs, _ = root["$defs"].(map[string]any)
	})
	return defs
}

func rx(p string) *regexp.Regexp {
	if r, ok := rxCache.Load(p); ok {
		return r.(*regexp.Regexp)
	}
	r := regexp.MustCompile(p)
	rxCache.Store(p, r)
	return r
}

// Validate — значение v по схеме сборки name; nil — значение схемы.
func Validate(name string, v any) *Violation {
	s, ok := schemaDefs()[name]
	if !ok {
		return &Violation{At: "", Rule: "no schema " + name}
	}
	var errs []Violation
	validate(s, v, "", &errs)
	if len(errs) > 0 {
		return &errs[0]
	}
	return nil
}

// StrictJSON — одно значение JSON без повторов имён и без хвоста; числа — json.Number.
func StrictJSON(b []byte) (any, error) {
	dec := json.NewDecoder(bytes.NewReader(b))
	dec.UseNumber()
	v, err := strictValue(dec, 0)
	if err != nil {
		return nil, err
	}
	if _, err := dec.Token(); err == nil {
		return nil, errors.New("more than one JSON value")
	}
	return v, nil
}

func strictValue(dec *json.Decoder, depth int) (any, error) {
	if depth > 512 {
		return nil, errors.New("too deep")
	}
	t, err := dec.Token()
	if err != nil {
		return nil, err
	}
	switch x := t.(type) {
	case json.Delim:
		switch x {
		case '{':
			m := map[string]any{}
			for dec.More() {
				kt, err := dec.Token()
				if err != nil {
					return nil, err
				}
				k := kt.(string)
				if _, dup := m[k]; dup {
					return nil, fmt.Errorf("repeated name %q", k)
				}
				v, err := strictValue(dec, depth+1)
				if err != nil {
					return nil, err
				}
				m[k] = v
			}
			_, err := dec.Token()
			return m, err
		case '[':
			a := []any{}
			for dec.More() {
				v, err := strictValue(dec, depth+1)
				if err != nil {
					return nil, err
				}
				a = append(a, v)
			}
			_, err := dec.Token()
			return a, err
		}
	}
	return t, nil
}

func num(v any) (*big.Rat, bool) {
	switch x := v.(type) {
	case json.Number:
		r, ok := new(big.Rat).SetString(string(x))
		return r, ok
	case float64:
		r := new(big.Rat)
		if r.SetFloat64(x) == nil {
			return nil, false
		}
		return r, true
	case int:
		return new(big.Rat).SetInt64(int64(x)), true
	case int64:
		return new(big.Rat).SetInt64(x), true
	}
	return nil, false
}

func typeOf(v any) string {
	switch v.(type) {
	case nil:
		return "null"
	case bool:
		return "boolean"
	case string:
		return "string"
	case []any:
		return "array"
	case map[string]any:
		return "object"
	}
	if _, ok := num(v); ok {
		return "number"
	}
	return "?"
}

func isType(v any, t string) bool {
	got := typeOf(v)
	if t == "integer" {
		r, ok := num(v)
		return ok && r.IsInt()
	}
	return got == t
}

func equalJSONValue(a, b any) bool {
	ra, oka := num(a)
	rb, okb := num(b)
	if oka || okb {
		return oka && okb && ra.Cmp(rb) == 0
	}
	switch x := a.(type) {
	case map[string]any:
		y, ok := b.(map[string]any)
		if !ok || len(x) != len(y) {
			return false
		}
		for k, v := range x {
			w, ok := y[k]
			if !ok || !equalJSONValue(v, w) {
				return false
			}
		}
		return true
	case []any:
		y, ok := b.([]any)
		if !ok || len(x) != len(y) {
			return false
		}
		for i := range x {
			if !equalJSONValue(x[i], y[i]) {
				return false
			}
		}
		return true
	}
	return a == b
}

func childPath(at, k string) string {
	return at + "/" + strings.ReplaceAll(strings.ReplaceAll(k, "~", "~0"), "/", "~1")
}

func bound(n any) *big.Rat {
	r, _ := num(n)
	return r
}

// validate — правила узла s над v; → множество свойств объекта v, оценённых этим узлом (для unevaluatedProperties).
func validate(s any, v any, at string, errs *[]Violation) map[string]bool {
	evaluated := map[string]bool{}
	switch b := s.(type) {
	case bool:
		if !b {
			*errs = append(*errs, Violation{at, "false"})
		}
		return evaluated
	case map[string]any:
		n := b
		fail := func(rule string) { *errs = append(*errs, Violation{at, rule}) }
		sub := func(node any) (bool, map[string]bool) {
			var e []Violation
			ev := validate(node, v, at, &e)
			return len(e) == 0, ev
		}
		merge := func(m map[string]bool) {
			for k := range m {
				evaluated[k] = true
			}
		}
		if ref, ok := n["$ref"].(string); ok {
			name := strings.TrimPrefix(ref, "#/$defs/")
			target, ok := schemaDefs()[name]
			if !ok {
				fail("$ref " + ref)
			} else {
				merge(validate(target, v, at, errs))
			}
		}
		if t, ok := n["type"]; ok {
			match := false
			switch tt := t.(type) {
			case string:
				match = isType(v, tt)
			case []any:
				for _, x := range tt {
					if s, _ := x.(string); isType(v, s) {
						match = true
					}
				}
			}
			if !match {
				fail("type")
			}
		}
		if e, ok := n["enum"].([]any); ok {
			found := false
			for _, x := range e {
				if equalJSONValue(x, v) {
					found = true
				}
			}
			if !found {
				fail("enum")
			}
		}
		if c, ok := n["const"]; ok && !equalJSONValue(c, v) {
			fail("const")
		}
		if all, ok := n["allOf"].([]any); ok {
			for _, x := range all {
				merge(validate(x, v, at, errs))
			}
		}
		if any_, ok := n["anyOf"].([]any); ok {
			hit := false
			for _, x := range any_ {
				if good, ev := sub(x); good {
					hit = true
					merge(ev)
				}
			}
			if !hit {
				fail("anyOf")
			}
		}
		if one, ok := n["oneOf"].([]any); ok {
			hits := 0
			var keep map[string]bool
			for _, x := range one {
				if good, ev := sub(x); good {
					hits++
					keep = ev
				}
			}
			if hits != 1 {
				fail("oneOf")
			} else {
				merge(keep)
			}
		}
		if not, ok := n["not"]; ok {
			if good, _ := sub(not); good {
				fail("not")
			}
		}
		if cond, ok := n["if"]; ok {
			if good, ev := sub(cond); good {
				merge(ev)
				if th, ok := n["then"]; ok {
					merge(validate(th, v, at, errs))
				}
			} else if el, ok := n["else"]; ok {
				merge(validate(el, v, at, errs))
			}
		}
		switch x := v.(type) {
		case string:
			l := utf8.RuneCountInString(x)
			if m := bound(n["minLength"]); m != nil && big.NewRat(int64(l), 1).Cmp(m) < 0 {
				fail("minLength")
			}
			if m := bound(n["maxLength"]); m != nil && big.NewRat(int64(l), 1).Cmp(m) > 0 {
				fail("maxLength")
			}
			if p, ok := n["pattern"].(string); ok && !rx(p).MatchString(x) {
				fail("pattern")
			}
		case []any:
			if m := bound(n["minItems"]); m != nil && big.NewRat(int64(len(x)), 1).Cmp(m) < 0 {
				fail("minItems")
			}
			if m := bound(n["maxItems"]); m != nil && big.NewRat(int64(len(x)), 1).Cmp(m) > 0 {
				fail("maxItems")
			}
			if u, _ := n["uniqueItems"].(bool); u {
				for i := range x {
					for j := i + 1; j < len(x); j++ {
						if equalJSONValue(x[i], x[j]) {
							fail("uniqueItems")
							i, j = len(x), len(x)
						}
					}
				}
			}
			if it, ok := n["items"]; ok {
				for i, e := range x {
					validate(it, e, at+"/"+strconv.Itoa(i), errs)
				}
			}
		case map[string]any:
			keys := make([]string, 0, len(x))
			for k := range x {
				keys = append(keys, k)
			}
			sort.Strings(keys)
			if m := bound(n["minProperties"]); m != nil && big.NewRat(int64(len(x)), 1).Cmp(m) < 0 {
				fail("minProperties")
			}
			if m := bound(n["maxProperties"]); m != nil && big.NewRat(int64(len(x)), 1).Cmp(m) > 0 {
				fail("maxProperties")
			}
			if req, ok := n["required"].([]any); ok {
				for _, r := range req {
					if _, has := x[r.(string)]; !has {
						fail("required " + r.(string))
					}
				}
			}
			if dr, ok := n["dependentRequired"].(map[string]any); ok {
				for k, list := range dr {
					if _, has := x[k]; !has {
						continue
					}
					for _, r := range list.([]any) {
						if _, has := x[r.(string)]; !has {
							fail("dependentRequired " + k + " → " + r.(string))
						}
					}
				}
			}
			if pn, ok := n["propertyNames"]; ok {
				for _, k := range keys {
					validate(pn, k, childPath(at, k), errs)
				}
			}
			props, _ := n["properties"].(map[string]any)
			pats, _ := n["patternProperties"].(map[string]any)
			local := map[string]bool{}
			for _, k := range keys {
				if ps, ok := props[k]; ok {
					validate(ps, x[k], childPath(at, k), errs)
					local[k] = true
				}
				for p, ps := range pats {
					if rx(p).MatchString(k) {
						validate(ps, x[k], childPath(at, k), errs)
						local[k] = true
					}
				}
			}
			if ap, ok := n["additionalProperties"]; ok {
				for _, k := range keys {
					if !local[k] {
						validate(ap, x[k], childPath(at, k), errs)
					}
					evaluated[k] = true
				}
			}
			merge(local)
			if up, ok := n["unevaluatedProperties"]; ok {
				for _, k := range keys {
					if !evaluated[k] {
						validate(up, x[k], childPath(at, k), errs)
						evaluated[k] = true
					}
				}
			}
		}
		if r, ok := num(v); ok {
			if m := bound(n["minimum"]); m != nil && r.Cmp(m) < 0 {
				fail("minimum")
			}
			if m := bound(n["maximum"]); m != nil && r.Cmp(m) > 0 {
				fail("maximum")
			}
			if m := bound(n["exclusiveMinimum"]); m != nil && r.Cmp(m) <= 0 {
				fail("exclusiveMinimum")
			}
			if m := bound(n["exclusiveMaximum"]); m != nil && r.Cmp(m) >= 0 {
				fail("exclusiveMaximum")
			}
		}
	}
	return evaluated
}

const bundle = `{ "$defs": {} }`
