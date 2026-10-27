// Раннер стандартного стека В7 на Go (ADR-0092): JSON Schema 2020-12 (santhosh-tekuri/jsonschema/v6) и CEL (cel-go).
//
// Запросы — строки JSON на stdin, ответы — строки JSON на stdout, по одной на запрос:
//
//	{"op":"schema","file":ПУТЬ,"ptr":"" | "#/$defs/writer","instance":ЗНАЧЕНИЕ} → {"records":[{"path","kw","extra"}]}
//	{"op":"cel_load","file":ПУТЬ relations.json}                               → {"rows":N}
//	{"op":"cel","doc":ДЕРЕВО}                                                  → {"fired":[[строка, путь]…]}
//
// Записи схемы — листья дерева ошибок библиотеки (как у Python: путь, слово, данные); место отказа (слой 4) — общий
// norm на Python. Своё здесь — только то, что зависит от библиотеки: путь `propertyNames` (у v6 ошибка имени —
// отдельный корень без места объекта, validator.go:294) — место объекта и имя.
package main

import (
	"bufio"
	"bytes"
	"io"
	"encoding/json"
	"fmt"
	"math"
	"net/url"
	"os"
	"path/filepath"
	"reflect"
	"strconv"
	"strings"

	"github.com/google/cel-go/cel"
	"github.com/google/cel-go/common/types"
	"github.com/google/cel-go/common/types/ref"
	"github.com/google/cel-go/common/types/traits"
	"github.com/google/cel-go/ext"
	"github.com/santhosh-tekuri/jsonschema/v6"
	"github.com/santhosh-tekuri/jsonschema/v6/kind"
	"go.yaml.in/yaml/v3"
)

// jsonable — значение yaml.v3 → JSON: ключи не строкой — "<nonstring>", числа вне JSON — строка с пометкой.
func jsonable(v any) any {
	switch x := v.(type) {
	case map[string]any:
		for k, y := range x {
			x[k] = jsonable(y)
		}
		return x
	case map[any]any:
		out := map[string]any{}
		for k, y := range x {
			out[fmt.Sprintf("<nonstring:%v>", k)] = jsonable(y)
		}
		return out
	case []any:
		for i, y := range x {
			x[i] = jsonable(y)
		}
		return x
	case float64:
		if math.IsInf(x, 0) || math.IsNaN(x) {
			return fmt.Sprintf("<float:%v>", x)
		}
		return x
	case int, int64, uint64, bool, string, nil:
		return x
	}
	return fmt.Sprintf("<%T:%v>", v, v)
}

type request struct {
	Op       string          `json:"op"`
	File     string          `json:"file"`
	Ptr      string          `json:"ptr"`
	Instance json.RawMessage `json:"instance"`
	Doc      json.RawMessage `json:"doc"`
	Schema   json.RawMessage `json:"schema"`
	Expr     string          `json:"expr"`
	Raw      bool            `json:"raw"`
	Data     []byte          `json:"data"`
	Scalars  string          `json:"scalars"`
}

type record struct {
	Path  []string `json:"path"`
	Kw    string   `json:"kw"`
	Extra any      `json:"extra"`
}

var schemas = map[string]*jsonschema.Schema{}

// raw — без слоя 4 (место ошибки имени — как отдаёт библиотека): тест дефекта D7.
var raw bool

func compile(file, ptr string) (*jsonschema.Schema, error) {
	key := file + ptr
	if s, ok := schemas[key]; ok {
		return s, nil
	}
	abs, err := filepath.Abs(file)
	if err != nil {
		return nil, err
	}
	c := jsonschema.NewCompiler()
	s, err := c.Compile("file://" + abs + ptr)
	if err != nil {
		return nil, err
	}
	schemas[key] = s
	return s, nil
}

func records(e *jsonschema.ValidationError, parent []string, base string, inst any, out *[]record) {
	if os.Getenv("V7DEBUG") != "" {
		fmt.Fprintf(os.Stderr, "%T %v %s parent=%v base=%s\n", e.ErrorKind, e.InstanceLocation, e.SchemaURL, parent, base)
	}
	switch k := e.ErrorKind.(type) {
	case *kind.Schema, *kind.Group, *kind.AllOf, *kind.Reference:
		if len(e.Causes) == 0 {
			*out = append(*out, record{e.InstanceLocation, fmt.Sprintf("%T", k), nil})
		}
		b := e.SchemaURL
		if r, ok := k.(*kind.Reference); ok {
			b = r.URL
		}
		for _, c := range e.Causes {
			records(c, e.InstanceLocation, b, inst, out)
		}
	case *kind.PropertyNames:
		// Ошибка имени у v6 — корень отдельной проверки (validator.go:294): места объекта нет, а единственная ошибка
		// подсхемы не обёрнута своим местом. Слой 4: место объекта — от места родителя по пути ключевых слов от
		// схемы родителя до propertyNames (properties/<k> — шаг ключа; additionalProperties, patternProperties,
		// items — любой ключ или элемент), среди мест — объекты с этим именем.
		if raw {
			*out = append(*out, record{e.InstanceLocation, "propertyNames", k.Property})
			return
		}
		for _, loc := range nameOwners(parent, base, e.SchemaURL, inst, k.Property) {
			*out = append(*out, record{loc, "propertyNames", k.Property})
		}
	case *kind.Required:
		*out = append(*out, record{e.InstanceLocation, "required", k.Missing})
	case *kind.AdditionalProperties:
		*out = append(*out, record{e.InstanceLocation, "additionalProperties", k.Properties})
	case *kind.UniqueItems:
		*out = append(*out, record{e.InstanceLocation, "uniqueItems", nil})
	default:
		kw := strings.TrimPrefix(fmt.Sprintf("%T", k), "*kind.")
		*out = append(*out, record{e.InstanceLocation, kw, nil})
	}
}

func valueAt(v any, loc []string) (any, bool) {
	for _, s := range loc {
		switch x := v.(type) {
		case map[string]any:
			y, ok := x[s]
			if !ok {
				return nil, false
			}
			v = y
		case []any:
			i, err := strconv.Atoi(s)
			if err != nil || i < 0 || i >= len(x) {
				return nil, false
			}
			v = x[i]
		default:
			return nil, false
		}
	}
	return v, true
}

func nameOwners(parent []string, base, at string, inst any, name string) [][]string {
	locs := [][]string{append([]string{}, parent...)}
	_, bfrag, _ := strings.Cut(base, "#")
	_, afrag, _ := strings.Cut(at, "#")
	if strings.HasPrefix(afrag, bfrag) {
		toks := strings.Split(strings.TrimPrefix(strings.TrimSuffix(afrag[len(bfrag):], "/propertyNames"), "/"), "/")
		for i := 0; i < len(toks); i++ {
			t := toks[i]
			if t == "" {
				continue
			}
			var next [][]string
			step := func(f func(loc []string, v any) [][]string) {
				for _, l := range locs {
					if v, ok := valueAt(inst, l); ok {
						next = append(next, f(l, v)...)
					}
				}
			}
			switch t {
			case "properties":
				i++
				key := unescape(toks[i])
				step(func(l []string, v any) [][]string {
					if m, ok := v.(map[string]any); ok {
						if _, ok := m[key]; ok {
							return [][]string{append(append([]string{}, l...), key)}
						}
					}
					return nil
				})
			case "patternProperties", "prefixItems":
				i++
				fallthrough
			case "additionalProperties", "items":
				step(func(l []string, v any) [][]string {
					var r [][]string
					switch x := v.(type) {
					case map[string]any:
						for k := range x {
							r = append(r, append(append([]string{}, l...), k))
						}
					case []any:
						for j := range x {
							r = append(r, append(append([]string{}, l...), strconv.Itoa(j)))
						}
					}
					return r
				})
			case "allOf", "anyOf", "oneOf":
				i++
				continue
			default: // if, then, else, not — без шага по экземпляру
				continue
			}
			locs = next
		}
	}
	var out [][]string
	for _, l := range locs {
		if v, ok := valueAt(inst, l); ok {
			if m, ok := v.(map[string]any); ok {
				if _, ok := m[name]; ok {
					out = append(out, l)
				}
			}
		}
	}
	if len(out) == 0 {
		out = [][]string{parent}
	}
	return out
}

func unescape(t string) string {
	if u, err := url.PathUnescape(t); err == nil {
		t = u
	}
	return strings.ReplaceAll(strings.ReplaceAll(t, "~1", "/"), "~0", "~")
}

// ---------------------------------------------------------------- CEL

type row struct {
	No  int    `json:"no"`
	Cel string `json:"cel"`
	prg cel.Program
}

var rows []row

var jsonSliceType = reflect.TypeOf([]any{})

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

func template(args ...ref.Val) ref.Val {
	s, ok := args[0].(types.String)
	if !ok {
		return types.False
	}
	t, plain, ints, bare := string(s), args[1], args[2], args[3] == types.True
	if bare && !strings.Contains(t, "{") {
		return types.Bool(inList(types.String(t), plain))
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
		set := plain
		if sep {
			set = ints
		}
		if !inList(types.String(name), set) {
			return types.False
		}
		i = b + 1
	}
}

// jcsNumber — запись числа по RFC 8785 § 3.2.2.3 (ECMAScript Number.toString).
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
			out = append(out, types.String(jcsNumber(float64(x))))
		default:
			out = append(out, x)
		}
	}
	return types.DefaultTypeAdapter.NativeToValue(out)
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

func celLoad(file string) (int, error) {
	data, err := os.ReadFile(file)
	if err != nil {
		return 0, err
	}
	var rel struct {
		Rows []row `json:"rows"`
	}
	if err := json.Unmarshal(data, &rel); err != nil {
		return 0, err
	}
	env, err := celEnv()
	if err != nil {
		return 0, err
	}
	rows = nil
	for _, r := range rel.Rows {
		ast, iss := env.Compile(r.Cel)
		if iss.Err() != nil {
			return 0, fmt.Errorf("row %d: %v", r.No, iss.Err())
		}
		prg, err := env.Program(ast)
		if err != nil {
			return 0, fmt.Errorf("row %d: %v", r.No, err)
		}
		r.prg = prg
		rows = append(rows, r)
	}
	return len(rows), nil
}

// native — значение JSON с числами json.Number → int64 (целая запись) или float64 (дробь, экспонента).
func native(v any) any {
	switch x := v.(type) {
	case json.Number:
		s := string(x)
		if !strings.ContainsAny(s, ".eE") {
			if i, err := strconv.ParseInt(s, 10, 64); err == nil {
				return i
			}
		}
		f, _ := strconv.ParseFloat(s, 64)
		return f
	case map[string]any:
		for k, y := range x {
			x[k] = native(y)
		}
	case []any:
		for i, y := range x {
			x[i] = native(y)
		}
	}
	return v
}

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

func celRun(raw json.RawMessage) ([][2]any, error) {
	dec := json.NewDecoder(strings.NewReader(string(raw)))
	dec.UseNumber()
	var doc any
	if err := dec.Decode(&doc); err != nil {
		return nil, err
	}
	doc = native(doc)
	fired := [][2]any{}
	for _, r := range rows {
		v, _, err := r.prg.Eval(map[string]any{"doc": doc})
		if err != nil {
			return nil, fmt.Errorf("row %d: %v", r.No, err)
		}
		var paths []any
		if err := collect(v, &paths); err != nil {
			return nil, fmt.Errorf("row %d: %v", r.No, err)
		}
		for _, p := range paths {
			fired = append(fired, [2]any{r.No, p})
		}
	}
	return fired, nil
}

func main() {
	in := bufio.NewScanner(os.Stdin)
	in.Buffer(make([]byte, 64<<20), 64<<20)
	out := json.NewEncoder(os.Stdout)
	for in.Scan() {
		var req request
		resp := map[string]any{}
		if err := json.Unmarshal(in.Bytes(), &req); err != nil {
			resp["error"] = err.Error()
			out.Encode(resp)
			continue
		}
		raw = req.Raw
		switch req.Op {
		case "schema":
			s, err := compile(req.File, req.Ptr)
			if err != nil {
				resp["error"] = err.Error()
				break
			}
			inst, err := jsonschema.UnmarshalJSON(strings.NewReader(string(req.Instance)))
			if err != nil {
				resp["error"] = err.Error()
				break
			}
			recs := []record{}
			if err := s.Validate(inst); err != nil {
				verr, ok := err.(*jsonschema.ValidationError)
				if !ok {
					resp["error"] = err.Error()
					break
				}
				records(verr, nil, "", inst, &recs)
			}
			resp["records"] = recs
		case "schema_inline":                  // тесты дефектов: схема в запросе
			doc, err := jsonschema.UnmarshalJSON(strings.NewReader(string(req.Schema)))
			if err != nil {
				resp["error"] = err.Error()
				break
			}
			c := jsonschema.NewCompiler()
			if err := c.AddResource("mem:///inline.json", doc); err != nil {
				resp["error"] = err.Error()
				break
			}
			s, err := c.Compile("mem:///inline.json")
			if err != nil {
				resp["error"] = err.Error()
				break
			}
			inst, err := jsonschema.UnmarshalJSON(strings.NewReader(string(req.Instance)))
			if err != nil {
				resp["error"] = err.Error()
				break
			}
			recs := []record{}
			if err := s.Validate(inst); err != nil {
				records(err.(*jsonschema.ValidationError), nil, "", inst, &recs)
			}
			resp["records"] = recs
		case "cel_eval":                       // тесты дефектов: выражение над doc в среде связей
			env, err := celEnv()
			if err != nil {
				resp["error"] = err.Error()
				break
			}
			ast, iss := env.Compile(req.Expr)
			if iss.Err() != nil {
				resp["error"] = iss.Err().Error()
				break
			}
			prg, err := env.Program(ast)
			if err != nil {
				resp["error"] = err.Error()
				break
			}
			dec := json.NewDecoder(strings.NewReader(string(req.Doc)))
			dec.UseNumber()
			var d any
			dec.Decode(&d)
			v, _, err := prg.Eval(map[string]any{"doc": native(d)})
			if err != nil {
				resp["error"] = err.Error()
				break
			}
			resp["value"] = v.Value()
		case "text":                           // слой 1: байты → дерево (порядок автора) или отказ text
			if scalarRows == nil || req.Scalars != "" {
				if err := loadScalars(req.Scalars); err != nil {
					resp["error"] = err.Error()
					break
				}
			}
			tree, numbers, empties, e := loadText(req.Data)
			if e != nil {
				resp["refused"] = e
				break
			}
			resp["tree"] = json.RawMessage(tree)
			resp["numbers"] = numbers
			resp["empties"] = empties
		case "yaml_docs":                      // yaml-test-suite: только парсер (go.yaml.in/yaml/v3), документы в JSON
			dec := yaml.NewDecoder(bytes.NewReader(req.Data))
			docs := []any{}
			var perr error
			for {
				var node yaml.Node
				err := dec.Decode(&node)
				if err == io.EOF {
					break
				}
				if err != nil {
					perr = err
					break
				}
				var v any
				if err := node.Decode(&v); err != nil {
					docs = append(docs, "<construct:"+err.Error()+">")
					continue
				}
				docs = append(docs, jsonable(v))
			}
			if false {
				var v any
				err := dec.Decode(&v)
				if err == io.EOF {
					break
				}
				if err != nil {
					perr = err
					break
				}
				docs = append(docs, jsonable(v))
			}
			if perr != nil {
				resp["parse_error"] = perr.Error()
			} else {
				resp["docs"] = docs
			}
		case "cel_load":
			n, err := celLoad(req.File)
			if err != nil {
				resp["error"] = err.Error()
				break
			}
			resp["rows"] = n
		case "cel":
			fired, err := celRun(req.Doc)
			if err != nil {
				resp["error"] = err.Error()
				break
			}
			resp["fired"] = fired
		default:
			resp["error"] = "unknown op " + req.Op
		}
		out.Encode(resp)
	}
}
