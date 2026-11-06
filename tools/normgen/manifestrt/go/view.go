// Hand-written runtime of the part `loader` (tools/normgen/manifestrt/go; the kit copies it, DO NOT EDIT): layer 6 —
// Canonical projection (P/02.2 N1.1, Lesson2 steps):sugar(tables, bound_to, in), static schema defaults
// inside present parents or parents with defaults(R10), then
// computed P1-P5, x-ordered arrays of {name:key, ...} in author order(R14), and values by their place's type,
// JCS (ADR-0072).
package manifest

func objAt(v any, keys ...string) *Obj {
	for _, k := range keys {
		o, ok := v.(*Obj)
		if !ok {
			return nil
		}
		v = o.M[k]
	}
	o, _ := v.(*Obj)
	return o
}

// fieldDescriptors describes unit.fields.* and tables.*.fields.* (P/02.2 P4, bound_to sugar).
func fieldDescriptors(t any) []*Obj {
	var out []*Obj
	if fs := objAt(t, "unit", "fields"); fs != nil {
		for _, k := range fs.Keys {
			if f, ok := fs.M[k].(*Obj); ok {
				out = append(out, f)
			}
		}
	}
	if ts := objAt(t, "tables"); ts != nil {
		for _, tk := range ts.Keys {
			if fs := objAt(ts.M[tk], "fields"); fs != nil {
				for _, k := range fs.Keys {
					if f, ok := fs.M[k].(*Obj); ok {
						out = append(out, f)
					}
				}
			}
		}
	}
	return out
}

func secretItems(t any) []*Obj {
	var out []*Obj
	for _, f := range fieldDescriptors(t) {
		if l, ok := f.M["secret_in"].([]any); ok {
			for _, e := range l {
				if o, ok := e.(*Obj); ok {
					out = append(out, o)
				}
			}
		}
	}
	return out
}

func unitFields(t any) *Obj {
	if fs := objAt(t, "unit", "fields"); fs != nil {
		return fs
	}
	return newObj()
}

func unitStates(t any) []string {
	var out []string
	if st := objAt(t, "unit", "state"); st != nil {
		for _, k := range st.Keys {
			if k != "cursor" {
				out = append(out, k)
			}
		}
	}
	return out
}

func sugar(t any) {
	if o, ok := t.(*Obj); ok {
		if l, ok := o.M["tables"].([]any); ok {
			m := newObj()
			for _, x := range l {
				if s, ok := x.(string); ok {
					m.Set(s, newObj())
				}
			}
			o.M["tables"] = m
		}
	}
	for _, f := range fieldDescriptors(t) {
		if s, ok := f.M["bound_to"].(string); ok {
			f.M["bound_to"] = []any{s}
		}
	}
	for _, e := range secretItems(t) {
		if s, ok := e.M["in"].(string); ok {
			e.M["in"] = []any{s}
		}
	}
}

func setDefault(o *Obj, k string, v any) any {
	if x, ok := o.M[k]; ok {
		return x
	}
	o.Set(k, v)
	return v
}

func computed(t any) {
	o, ok := t.(*Obj)
	if !ok {
		return
	}
	if _, ok := o.M["snapshot"]; !ok { // P1 (ADR-0091 item 3).
		snap := []any{}
		fs := unitFields(t)
		for _, k := range fs.Keys {
			f, _ := fs.M[k].(*Obj)
			blob := false
			if f != nil {
				blob = f.M["type"] == "blob"
			}
			if len(k) >= 7 && k[len(k)-7:] == "_secret" || k == "server" || blob {
				continue
			}
			snap = append(snap, k)
		}
		for _, k := range unitStates(t) {
			snap = append(snap, "state."+k)
		}
		o.Set("snapshot", snap)
	}
	if ts, ok := o.M["tables"].(*Obj); ok { // P2.
		for _, k := range ts.Keys {
			if tbl, ok := ts.M[k].(*Obj); ok {
				if j, ok := setDefault(tbl, "journal", newObj()).(*Obj); ok {
					setDefault(j, "written", k+".written")
					setDefault(j, "deleted", k+".deleted")
				}
			}
		}
	}
	if d, ok := o.M["display"].(*Obj); ok { // P3.
		if _, has := d.M["form"]; !has {
			names := []any{}
			for _, k := range unitFields(t).Keys {
				names = append(names, k)
			}
			f := newObj()
			f.Set("fields", names)
			d.Set("form", []any{f})
		}
	}
	for _, f := range fieldDescriptors(t) { // P4.
		setDefault(f, "default", nil)
	}
	for _, e := range secretItems(t) { // P5.
		if _, ok := e.M["regex"]; ok {
			setDefault(e, "decoded", true)
		}
	}
}

// project applies defaults inside present parents(R10), with x-ordered arrays(R14).
func (s *schemaSet) project(tree any, ordered bool) any {
	var rec func(n *Obj, v any) any
	rec = func(n *Obj, v any) any {
		chain := s.chainOf(n, v)
		switch x := v.(type) {
		case *Obj:
			if truthy(chain, "x-opaque") {
				return v
			}
			out := newObj()
			for _, k := range x.Keys {
				if c := s.child(chain, v, k); c != nil {
					out.Set(k, rec(c, x.M[k]))
				} else {
					out.Set(k, x.M[k])
				}
			}
			for _, c0 := range chain {
				props, ok := c0.M["properties"].(*Obj)
				if !ok {
					continue
				}
				for _, k := range props.Keys {
					c, _ := props.M[k].(*Obj)
					if c == nil {
						continue
					}
					if _, in := x.M[k]; in {
						continue
					}
					if _, in := out.M[k]; in {
						continue
					}
					if d, has := word(s.resolve(c), "default"); has {
						out.Set(k, rec(c, deepCopy(d)))
					}
				}
			}
			if ordered && truthy(chain, "x-ordered") {
				l := []any{}
				for _, k := range x.Keys {
					e := newObj()
					e.Set("name", k)
					if eo, ok := out.M[k].(*Obj); ok {
						for _, kk := range eo.Keys {
							e.Set(kk, eo.M[kk])
						}
					}
					l = append(l, e)
				}
				return l
			}
			return out
		case []any:
			out := make([]any, len(x))
			for i, e := range x {
				if c := s.child(chain, v, i); c != nil {
					out[i] = rec(c, e)
				} else {
					out[i] = e
				}
			}
			return out
		}
		return v
	}
	return rec(s.root, tree)
}

// canonicalTree applies sugar->defaults->P1-P5->defaults/x-ordered in P/02.2 N1.1 order.
func (s *schemaSet) canonicalTree(tree any) any {
	t := deepCopy(tree)
	sugar(t)
	t = s.project(t, false)
	computed(t)
	return s.project(t, true)
}
