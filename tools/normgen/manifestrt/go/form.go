// Hand-written runtime of the part `loader` (tools/normgen/manifestrt/go; the kit copies it, DO NOT EDIT): layer of the
// form (P/02.1 Н3 step 2) — JSON Schema 2020-12 by the pinned github.com/santhosh-tekuri/jsonschema/v6 v6.0.2 over the
// embedded `02.1-installer.schema.json`; layer 2 (x-integer-place, LAYERS § 2) and the walk of the schema places
// (the chain of a place: the place, the target of `$ref`, `allOf` with `$ref`; variants `allOf` of `if: {type}`/`then`).
package manifest

import (
	"bytes"
	"fmt"
	"math"
	"regexp"
	"strconv"
	"strings"
	"sync"

	"github.com/santhosh-tekuri/jsonschema/v6"
)

const schemaURL = "manifest.schema.json"

type schemaSet struct {
	root     *Obj
	c        *jsonschema.Compiler
	mu       sync.Mutex
	compiled map[string]*jsonschema.Schema
	patterns map[string]*regexp.Regexp
}

func newSchemaSet(data []byte) (*schemaSet, error) {
	v, err := decodeOrdered(data, true)
	if err != nil {
		return nil, fmt.Errorf("schema: %v", err)
	}
	root, ok := v.(*Obj)
	if !ok {
		return nil, fmt.Errorf("schema: the root is not an object")
	}
	doc, err := jsonschema.UnmarshalJSON(bytes.NewReader(data))
	if err != nil {
		return nil, fmt.Errorf("schema: %v", err)
	}
	c := jsonschema.NewCompiler()
	if err := c.AddResource(schemaURL, doc); err != nil {
		return nil, fmt.Errorf("schema: %v", err)
	}
	s := &schemaSet{root: root, c: c, compiled: map[string]*jsonschema.Schema{}, patterns: map[string]*regexp.Regexp{}}
	if _, err := s.at(""); err != nil {
		return nil, err
	}
	return s, nil
}

func (s *schemaSet) at(ptr string) (*jsonschema.Schema, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if x, ok := s.compiled[ptr]; ok {
		return x, nil
	}
	x, err := s.c.Compile(schemaURL + "#" + ptr)
	if err != nil {
		return nil, fmt.Errorf("schema %s: %v", ptr, err)
	}
	s.compiled[ptr] = x
	return x, nil
}

// validate — the whole tree against the schema: nil — the form is clean.
func (s *schemaSet) validate(tree any) error {
	x, err := s.at("")
	if err != nil {
		return err
	}
	return x.Validate(forSchema(tree))
}

func (s *schemaSet) valid(node *Obj, v any) bool {
	x, err := s.at(node.Ptr)
	if err != nil {
		return false
	}
	return x.Validate(forSchema(v)) == nil
}

func (s *schemaSet) sub(ref string) *Obj {
	var n any = s.root
	for _, seg := range strings.Split(strings.TrimPrefix(ref, "#/"), "/") {
		o, ok := n.(*Obj)
		if !ok {
			return nil
		}
		n = o.M[strings.ReplaceAll(strings.ReplaceAll(seg, "~1", "/"), "~0", "~")]
	}
	o, _ := n.(*Obj)
	return o
}

// resolve — the chain of a place: the place first (its marks matter more), `allOf` elements with `$ref` and without
// `if`, then the target of `$ref`.
func (s *schemaSet) resolve(n *Obj) []*Obj {
	var out []*Obj
	for n != nil {
		out = append(out, n)
		if all, ok := n.M["allOf"].([]any); ok {
			for _, x := range all {
				if xo, ok := x.(*Obj); ok {
					if _, r := xo.M["$ref"]; r {
						if _, i := xo.M["if"]; !i {
							out = append(out, s.resolve(xo)...)
						}
					}
				}
			}
		}
		r, ok := n.M["$ref"].(string)
		if !ok {
			break
		}
		n = s.sub(r)
	}
	return out
}

func word(chain []*Obj, k string) (any, bool) {
	for _, n := range chain {
		if v, ok := n.M[k]; ok {
			return v, true
		}
	}
	return nil, false
}

func truthy(chain []*Obj, k string) bool {
	v, ok := word(chain, k)
	if !ok {
		return false
	}
	b, isB := v.(bool)
	return !isB || b
}

// variant — the node of the chosen variant (`allOf` of `if: {type}` / `then`) or nil.
func (s *schemaSet) variant(chain []*Obj, v any) *Obj {
	for _, n := range chain {
		all, _ := n.M["allOf"].([]any)
		for _, x := range all {
			xo, ok := x.(*Obj)
			if !ok {
				continue
			}
			cond, ok := xo.M["if"].(*Obj)
			then, okT := xo.M["then"].(*Obj)
			if ok && okT && len(cond.Keys) == 1 && cond.Keys[0] == "type" && s.valid(cond, v) {
				return then
			}
		}
	}
	return nil
}

func (s *schemaSet) pattern(p string) *regexp.Regexp {
	s.mu.Lock()
	defer s.mu.Unlock()
	if re, ok := s.patterns[p]; ok {
		return re
	}
	re, err := regexp.Compile(p)
	if err != nil {
		re = nil
	}
	s.patterns[p] = re
	return re
}

// child — the node of the place of key k (an object) or index k (a list); nil — no place or the name is not in form.
func (s *schemaSet) child(chain []*Obj, v any, k any) *Obj {
	for _, n := range chain {
		switch v.(type) {
		case *Obj:
			name, _ := k.(string)
			if props, ok := n.M["properties"].(*Obj); ok {
				if c, ok := props.M[name].(*Obj); ok {
					return c
				}
			}
			if pp, ok := n.M["patternProperties"].(*Obj); ok {
				for _, p := range pp.Keys {
					if re := s.pattern(p); re != nil && re.MatchString(name) {
						c, _ := pp.M[p].(*Obj)
						return c
					}
				}
			}
			if ap, ok := n.M["additionalProperties"].(*Obj); ok {
				if pn, ok := n.M["propertyNames"].(*Obj); ok && !s.valid(pn, name) {
					return nil
				}
				return ap
			}
		case []any:
			if it, ok := n.M["items"].(*Obj); ok {
				return it
			}
		}
	}
	return nil
}

func (s *schemaSet) chainOf(n *Obj, v any) []*Obj {
	chain := s.resolve(n)
	if va := s.variant(chain, v); va != nil {
		chain = append(chain, s.resolve(va)...)
	}
	return chain
}

// walk — visit(chain, value) → the new value of the place; then the children of the new value (not inside x-opaque).
func (s *schemaSet) walk(n *Obj, v any, visit func([]*Obj, any) any) any {
	chain := s.chainOf(n, v)
	v = visit(chain, v)
	switch x := v.(type) {
	case *Obj:
		if truthy(chain, "x-opaque") {
			return v
		}
		for _, k := range x.Keys {
			if c := s.child(chain, v, k); c != nil {
				x.M[k] = s.walk(c, x.M[k], visit)
			}
		}
	case []any:
		for i := range x {
			if c := s.child(chain, v, i); c != nil {
				x[i] = s.walk(c, x[i], visit)
			}
		}
	}
	return v
}

// integers — layer 2: at an integer place a value with an integer value is an integer (`4.0` → `4`).
func (s *schemaSet) integers(tree any) any {
	return s.walk(s.root, tree, func(chain []*Obj, v any) any {
		if f, ok := v.(float64); ok && truthy(chain, "x-integer-place") && f == math.Trunc(f) && math.Abs(f) <= 1<<53-1 {
			return int64(f)
		}
		return v
	})
}

func pathText(p []any) string {
	var b strings.Builder
	for i, x := range p {
		if i > 0 {
			b.WriteByte('.')
		}
		switch y := x.(type) {
		case string:
			b.WriteString(y)
		case int:
			b.WriteString(strconv.Itoa(y))
		default:
			fmt.Fprint(&b, y)
		}
	}
	return b.String()
}
