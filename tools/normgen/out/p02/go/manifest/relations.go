// Hand-written runtime of the part `loader` (tools/normgen/manifestrt/go; the kit copies it, DO NOT EDIT): the relations
// (P/02.1 Н3 step 3; LAYERS § 5, layer 7) — every row of the embedded `02.1-installer.relations.json` by the pinned
// github.com/google/cel-go v0.26.1 with the extensions strings and two-var-comprehensions and the three functions of
// layer 7: depth, template, text. A row gives a list of violations {p: path}; an execution error is a refusal, not
// «the relation holds» (D5). Based on the V7 Go stack of the course (skills/lesson-spec/scripts/v7/go/main.go).
package manifest

import (
	"encoding/json"
	"fmt"
	"math"
	"reflect"
	"strconv"
	"strings"

	"github.com/google/cel-go/cel"
	"github.com/google/cel-go/common/types"
	"github.com/google/cel-go/common/types/ref"
	"github.com/google/cel-go/common/types/traits"
	"github.com/google/cel-go/ext"
)

type relRow struct {
	No    int    `json:"no"`
	Path  string `json:"path"`
	Class string `json:"class"`
	Norm  string `json:"norm"`
	Cel   string `json:"cel"`
	prg   cel.Program
}

func celEnv() (*cel.Env, error) {
	return cel.NewEnv(
		ext.Strings(), ext.TwoVarComprehensions(),
		cel.Variable("doc", cel.DynType),
		cel.Function("depth", cel.Overload("depth_dyn", []*cel.Type{cel.DynType}, cel.IntType,
			cel.UnaryBinding(func(v ref.Val) ref.Val { return types.Int(depth(v)) }))),
		cel.Function("template", cel.Overload("template_dyn_list_list_bool",
			[]*cel.Type{cel.DynType, cel.ListType(cel.DynType), cel.ListType(cel.DynType), cel.BoolType}, cel.BoolType,
			cel.FunctionBinding(template))),
		cel.Function("text", cel.Overload("text_list", []*cel.Type{cel.ListType(cel.DynType)},
			cel.ListType(cel.DynType), cel.UnaryBinding(text))),
	)
}

func loadRelations(data []byte) ([]relRow, error) {
	var rel struct {
		Rows []relRow `json:"rows"`
	}
	if err := json.Unmarshal(data, &rel); err != nil {
		return nil, fmt.Errorf("relations: %v", err)
	}
	env, err := celEnv()
	if err != nil {
		return nil, err
	}
	for i := range rel.Rows {
		r := &rel.Rows[i]
		ast, iss := env.Compile(r.Cel)
		if iss.Err() != nil {
			return nil, fmt.Errorf("relations row %d: %v", r.No, iss.Err())
		}
		if r.prg, err = env.Program(ast); err != nil {
			return nil, fmt.Errorf("relations row %d: %v", r.No, err)
		}
	}
	return rel.Rows, nil
}

// fired — the row and the path of one violation.
type fired struct {
	Row  relRow
	Path []any
}

func runRelations(rows []relRow, doc any) ([]fired, error) {
	var out []fired
	for _, r := range rows {
		v, _, err := r.prg.Eval(map[string]any{"doc": doc})
		if err != nil {
			return nil, fmt.Errorf("relations row %d: CEL execution error: %v", r.No, err)
		}
		var paths []any
		if err := collect(v, &paths); err != nil {
			return nil, fmt.Errorf("relations row %d: %v", r.No, err)
		}
		for _, p := range paths {
			pl, _ := p.([]any)
			out = append(out, fired{r, pl})
		}
	}
	return out, nil
}

var jsonSliceType = reflect.TypeOf([]any{})

func collect(v ref.Val, out *[]any) error {
	switch x := v.(type) {
	case traits.Mapper:
		p, ok := x.Find(types.String("p"))
		if !ok {
			return fmt.Errorf("violation without p")
		}
		path, err := p.ConvertToNative(jsonSliceType)
		if err != nil {
			return err
		}
		*out = append(*out, path)
	case traits.Lister:
		n := int(x.Size().(types.Int))
		for i := 0; i < n; i++ {
			if err := collect(x.Get(types.Int(i)), out); err != nil {
				return err
			}
		}
	default:
		return fmt.Errorf("unexpected %v", v)
	}
	return nil
}

// depth — the depth of a value: a scalar 0, a mapping or a list — 1 + the deepest element.
func depth(v ref.Val) int {
	switch x := v.(type) {
	case traits.Mapper:
		m := 0
		it := x.Iterator()
		for it.HasNext() == types.True {
			if d := depth(x.Get(it.Next())); d > m {
				m = d
			}
		}
		return 1 + m
	case traits.Lister:
		m := 0
		n := int(x.Size().(types.Int))
		for i := 0; i < n; i++ {
			if d := depth(x.Get(types.Int(i))); d > m {
				m = d
			}
		}
		return 1 + m
	}
	return 0
}

func inList(v ref.Val, l ref.Val) bool {
	ls := l.(traits.Lister)
	n := int(ls.Size().(types.Int))
	for i := 0; i < n; i++ {
		if v.Equal(ls.Get(types.Int(i))) == types.True {
			return true
		}
	}
	return false
}

// template(t, plain, ints, bare) — every substitution {name} of t names an element of plain, {name:int} — of ints;
// bare — a text without braces must itself be an element of plain.
func template(args ...ref.Val) ref.Val {
	s, ok := args[0].(types.String)
	if !ok {
		return types.False
	}
	t, plainSet, ints, bare := string(s), args[1], args[2], args[3] == types.True
	if bare && !strings.Contains(t, "{") {
		return types.Bool(inList(types.String(t), plainSet))
	}
	i := 0
	for {
		a := strings.Index(t[i:], "{")
		if a < 0 {
			return types.True
		}
		a += i
		b := strings.Index(t[a:], "}")
		if b < 0 {
			return types.False
		}
		b += a
		if strings.Contains(t[a+1:b], "{") {
			return types.False
		}
		inner := t[a+1 : b]
		name, conv, sep := inner, "", false
		if j := strings.Index(inner, ":"); j >= 0 {
			name, conv, sep = inner[:j], inner[j+1:], true
		}
		if sep && conv != "int" {
			return types.False
		}
		set := plainSet
		if sep {
			set = ints
		}
		if !inList(types.String(name), set) {
			return types.False
		}
		i = b + 1
	}
}

// text — values as text: bool, int — their notation, double — JCS notation, others as is.
func text(v ref.Val) ref.Val {
	ls := v.(traits.Lister)
	n := int(ls.Size().(types.Int))
	out := make([]ref.Val, 0, n)
	for i := 0; i < n; i++ {
		switch x := ls.Get(types.Int(i)).(type) {
		case types.Bool:
			out = append(out, types.String(strconv.FormatBool(bool(x))))
		case types.Int:
			out = append(out, types.String(strconv.FormatInt(int64(x), 10)))
		case types.Double:
			f := float64(x)
			if math.IsInf(f, 0) || math.IsNaN(f) {
				out = append(out, x)
			} else {
				out = append(out, types.String(jcsNumber(f)))
			}
		default:
			out = append(out, x)
		}
	}
	return types.DefaultTypeAdapter.NativeToValue(out)
}
