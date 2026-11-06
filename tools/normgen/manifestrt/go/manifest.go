// Hand-written runtime of the part `loader` (tools/normgen/manifestrt/go; the kit copies it, DO NOT EDIT): the strict
// P/02.1 N3 load(bytes, source) and P/02.2 N3 build view. Layer order is
// normative (ADR-0092): text → form → relations; relations only on a clean form. The forms are embedded by the
// generator (forms.go: the schema, the relations, the scalar table of the export, byte for byte).
package manifest

import (
	"fmt"
	"sync"
)

// Refusal reports the loader layer in Class(text|form|relations, P/02.1 N4);Message names the
// file;Path/Row are hints (N4).
type Refusal struct {
	Class   string
	Message string
	Path    []any
	Row     int
}

func (r *Refusal) Error() string { return r.Message }

// Manifest — an accepted manifest: its name and the tree of the loader (author order; integers after layer 2).
type Manifest struct {
	Name string
	Tree *Obj
}

var (
	initOnce sync.Once
	initErr  error
	schema   *schemaSet
	rows     []relRow
)

func setup() error {
	initOnce.Do(func() {
		if initErr = loadScalars(scalarsTSV); initErr != nil {
			return
		}
		if schema, initErr = newSchemaSet([]byte(schemaJSON)); initErr != nil {
			return
		}
		rows, initErr = loadRelations([]byte(relationsJSON))
	})
	return initErr
}

// Load implements P/02.1 N3:one manifest's bytes produce a manifest or a refusal naming source.
// An error of the embedded forms or of a library (not of the input) is a refusal of the class "loader".
func Load(source string, data []byte) (*Manifest, *Refusal) {
	if err := setup(); err != nil {
		return nil, &Refusal{Class: "loader", Message: fmt.Sprintf("%s: the loader cannot start: %v", source, err)}
	}
	treeText, numbers, empties, e := loadText(data)
	if e != nil {
		return nil, &Refusal{Class: "text", Message: fmt.Sprintf("%s: refused:text: %s", source, e.Error()),
			Path: e.Path}
	}
	v, err := decodeOrdered([]byte(treeText), false)
	if err != nil {
		return nil, &Refusal{Class: "loader", Message: fmt.Sprintf("%s: the tree of layer 1: %v", source, err)}
	}
	if len(numbers) > 0 {
		p, _ := numbers[0][0].([]any)
		return nil, &Refusal{Class: "form", Path: p, Message: fmt.Sprintf("%s: refused:form: %s: the number %v is "+
			"outside the scalar table (P/02.1 \u041d1.1)", source, pathText(p), numbers[0][1])}
	}
	if len(empties) > 0 {
		return nil, &Refusal{Class: "form", Path: empties[0], Message: fmt.Sprintf("%s: refused:form: %s: an empty "+
			"value (P/02.1 \u041d1.1)", source, pathText(empties[0]))}
	}
	if err := schema.validate(v); err != nil {
		return nil, &Refusal{Class: "form", Message: fmt.Sprintf("%s: refused:form: %v", source, err)}
	}
	v = schema.integers(v)
	got, err := runRelations(rows, plain(v))
	if err != nil {
		return nil, &Refusal{Class: "relations", Message: fmt.Sprintf("%s: refused:relations: %v", source, err)}
	}
	if len(got) > 0 {
		f := got[0]
		return nil, &Refusal{Class: "relations", Path: f.Path, Row: f.Row.No, Message: fmt.Sprintf(
			"%s: refused:relations: row %d (%s; %s): %s", source, f.Row.No, f.Row.Path, f.Row.Norm, pathText(f.Path))}
	}
	o := v.(*Obj)
	name, _ := o.M["name"].(string)
	return &Manifest{Name: name, Tree: o}, nil
}

// Canonical implements P/02.2 N3 steps1-2:JCS bytes of an accepted manifest's canonical view, or the
// refusal of the load (the view is not built). The ceiling of the view row (step 3) is the caller's.
func Canonical(source string, data []byte) ([]byte, *Refusal) {
	m, r := Load(source, data)
	if r != nil {
		return nil, r
	}
	b, err := JCS(schema.canonicalTree(m.Tree))
	if err != nil {
		return nil, &Refusal{Class: "loader", Message: fmt.Sprintf("%s: the canonical view: %v", source, err)}
	}
	return b, nil
}

// Layer1 — the outcome of layer 1 alone (the package yaml-suite): nil — the text passes; otherwise the rule and the
// message (LAYERS § 4).
func Layer1(data []byte) (rule string, message string, refused bool) {
	if err := setup(); err != nil {
		return "loader", err.Error(), true
	}
	if _, _, _, e := loadText(data); e != nil {
		return e.Rule, e.Error(), true
	}
	return "", "", false
}
