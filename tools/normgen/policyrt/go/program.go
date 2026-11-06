// Shared runtime of declarative policies. The generated IR is closed; compile before use.
package workerpolicy

import (
	"bytes"
	"encoding/json"
	"fmt"
	"math"
	"sort"
	"strconv"
	"strings"

	"github.com/google/cel-go/cel"
	"github.com/google/cel-go/common/types"
	"github.com/google/cel-go/common/types/ref"
	"github.com/google/cel-go/common/types/traits"
	"github.com/google/cel-go/ext"
)

type Field struct {
	Name string `json:"name"`
	Type string `json:"type"`
}
type Variable struct {
	Name string `json:"name"`
	Type string `json:"type"`
	Init any    `json:"init"`
}
type Expression struct {
	Name string `json:"name"`
	Expr string `json:"expr"`
}
type Action struct {
	Args []Field      `json:"args"`
	Set  []Expression `json:"set"`
	IO   string       `json:"io"`
}
type Call struct {
	Action string   `json:"action"`
	Args   []string `json:"args"`
}
type Transition struct {
	ID    string   `json:"id"`
	Event string   `json:"event"`
	From  []string `json:"from"`
	If    string   `json:"if"`
	Do    []Call   `json:"do"`
	To    *string  `json:"to"`
	Stop  bool     `json:"stop"`
}
type Timer struct {
	Name     string       `json:"name"`
	Event    string       `json:"event"`
	Every    bool         `json:"every"`
	Duration string       `json:"duration"`
	Origin   string       `json:"origin"`
	AfterIO  string       `json:"after_io"`
	Payload  []Expression `json:"payload"`
}
type definition struct {
	Machine     string             `json:"machine"`
	Norm        string             `json:"norm"`
	States      []string           `json:"states"`
	Initial     string             `json:"initial"`
	Terminal    []string           `json:"terminal"`
	Input       []Field            `json:"input"`
	Types       map[string][]Field `json:"types"`
	Const       map[string]any     `json:"const"`
	Vars        []Variable         `json:"vars"`
	Events      map[string][]Field `json:"events"`
	Actions     map[string]Action  `json:"actions"`
	Invariants  []Expression       `json:"invariants"`
	Timers      []Timer            `json:"timers"`
	Transitions []Transition       `json:"transitions"`
	Env         []string           `json:"env"`
	Functions   []string           `json:"functions"`
}

// Program is immutable after Compile and may start independent concurrent runs.
type Program struct {
	d           definition
	expressions map[string]cel.Program
	names       []string
	varTypes    map[string]string
	terminal    map[string]bool
}

// Compile accepts the ordered, validated generator IR, never a hand-written machine YAML.
// Every CEL expression is compiled, including unreachable transitions and unused actions.
func Compile(raw []byte) (*Program, error) {
	v, e := DecodeJSON(raw)
	if e != nil {
		return nil, e
	}
	object, ok := v.(map[string]any)
	required := []string{"machine", "norm", "states", "initial", "terminal", "input", "types", "const", "vars", "timers", "events", "env", "functions", "actions", "invariants", "transitions"}
	if !ok || len(object) != len(required) {
		return nil, fmt.Errorf("policy IR: all declared sections are required")
	}
	for _, key := range required {
		if value, exists := object[key]; !exists || value == nil {
			return nil, fmt.Errorf("policy IR: missing/null section %s", key)
		}
	}
	d := json.NewDecoder(bytes.NewReader(raw))
	d.DisallowUnknownFields()
	d.UseNumber()
	p := &Program{expressions: map[string]cel.Program{}, varTypes: map[string]string{}, terminal: map[string]bool{}}
	if e := d.Decode(&p.d); e != nil {
		return nil, fmt.Errorf("policy IR: %w", e)
	}
	if p.d.Machine == "" || p.d.Norm == "" {
		return nil, fmt.Errorf("policy IR: machine and norm are nonempty")
	}
	states := map[string]bool{}
	for _, s := range p.d.States {
		if states[s] {
			return nil, fmt.Errorf("duplicate state %s", s)
		}
		states[s] = true
	}
	if !states[p.d.Initial] {
		return nil, fmt.Errorf("undeclared initial state")
	}
	for _, s := range p.d.Terminal {
		if !states[s] {
			return nil, fmt.Errorf("undeclared terminal")
		}
		p.terminal[s] = true
	}
	names := map[string]bool{"input": true, "vars": true, "const": true, "now": true, "s0": true, "state": true}
	for n := range p.d.Const {
		names[n] = true
	}
	for _, v := range p.d.Vars {
		if _, ok := p.varTypes[v.Name]; ok {
			return nil, fmt.Errorf("duplicate variable")
		}
		p.varTypes[v.Name] = v.Type
		names[v.Name] = true
		if _, e := p.typed(v.Init, v.Type); e != nil {
			return nil, fmt.Errorf("init %s: %w", v.Name, e)
		}
	}
	for _, ev := range p.d.Events {
		for _, f := range ev {
			names[f.Name] = true
		}
	}
	for _, a := range p.d.Actions {
		for _, f := range a.Args {
			names[f.Name] = true
		}
	}
	opts := []cel.EnvOption{ext.Strings(), ext.TwoVarComprehensions()}
	for _, f := range p.d.Functions {
		if f != "same_set" {
			return nil, fmt.Errorf("undeclared extension %s", f)
		}
		opts = append(opts, cel.Function("same_set", cel.Overload("same_set_list_list", []*cel.Type{cel.ListType(cel.DynType), cel.ListType(cel.DynType)}, cel.BoolType, cel.BinaryBinding(sameSet))))
	}
	for n := range names {
		p.names = append(p.names, n)
	}
	sort.Strings(p.names)
	for _, n := range p.names {
		opts = append(opts, cel.Variable(n, cel.DynType))
	}
	env, e := cel.NewEnv(opts...)
	if e != nil {
		return nil, e
	}
	compile := func(expr, where string) error {
		if _, ok := p.expressions[expr]; ok {
			return nil
		}
		ast, issues := env.Compile(expr)
		if issues != nil && issues.Err() != nil {
			return fmt.Errorf("%s: %w", where, issues.Err())
		}
		pr, e := env.Program(ast)
		if e != nil {
			return fmt.Errorf("%s: %w", where, e)
		}
		p.expressions[expr] = pr
		return nil
	}
	for name, a := range p.d.Actions {
		for _, s := range a.Set {
			if _, ok := p.varTypes[s.Name]; !ok {
				return nil, fmt.Errorf("action %s sets undeclared variable %s", name, s.Name)
			}
			if e := compile(s.Expr, "action "+name); e != nil {
				return nil, e
			}
		}
	}
	ids := map[string]bool{}
	for _, t := range p.d.Transitions {
		if ids[t.ID] {
			return nil, fmt.Errorf("duplicate transition id")
		}
		ids[t.ID] = true
		if _, ok := p.d.Events[t.Event]; !ok {
			return nil, fmt.Errorf("transition %s: undeclared event", t.ID)
		}
		for _, s := range t.From {
			if !states[s] || p.terminal[s] {
				return nil, fmt.Errorf("transition %s: invalid from", t.ID)
			}
		}
		if t.To != nil && !states[*t.To] {
			return nil, fmt.Errorf("transition %s: invalid to", t.ID)
		}
		if e := compile(t.If, t.ID); e != nil {
			return nil, e
		}
		for _, c := range t.Do {
			a, ok := p.d.Actions[c.Action]
			if !ok || len(a.Args) != len(c.Args) {
				return nil, fmt.Errorf("transition %s: invalid action/arity", t.ID)
			}
			for _, x := range c.Args {
				if e := compile(x, t.ID+" argument"); e != nil {
					return nil, e
				}
			}
		}
	}
	for _, i := range p.d.Invariants {
		if e := compile(i.Expr, "invariant "+i.Name); e != nil {
			return nil, e
		}
	}
	for _, t := range p.d.Timers {
		if _, ok := p.d.Events[t.Event]; !ok {
			return nil, fmt.Errorf("timer %s: invalid event", t.Name)
		}
		if t.AfterIO != "" && p.d.Actions[t.AfterIO].IO == "" {
			return nil, fmt.Errorf("timer %s: invalid after_io", t.Name)
		}
		if e := compile(t.Origin, "timer "+t.Name+" origin"); e != nil {
			return nil, e
		}
		if e := compile(t.Duration, "timer "+t.Name+" duration"); e != nil {
			return nil, e
		}
		for _, f := range t.Payload {
			if e := compile(f.Expr, "timer "+t.Name+" payload"); e != nil {
				return nil, e
			}
		}
	}
	return p, nil
}

func sameSet(a, b ref.Val) ref.Val {
	stringsOf := func(v ref.Val) ([]string, error) {
		l, ok := v.(traits.Lister)
		if !ok {
			return nil, fmt.Errorf("same_set: list required")
		}
		out := []string{}
		it := l.Iterator()
		for it.HasNext() == types.True {
			x, e := plain(it.Next())
			if e != nil {
				return nil, e
			}
			switch v := x.(type) {
			case bool:
				if v {
					out = append(out, "True")
				} else {
					out = append(out, "False")
				}
			case nil:
				out = append(out, "None")
			case float64:
				// Python's scalar str keeps the decimal marker and uses fixed
				// notation in this range (the reference same_set contract).
				format := byte('g')
				if v == 0 || math.Abs(v) >= 1e-4 && math.Abs(v) < 1e16 {
					format = 'f'
				}
				s := strconv.FormatFloat(v, format, -1, 64)
				if !strings.ContainsAny(s, ".e") {
					s += ".0"
				}
				out = append(out, s)
			default:
				out = append(out, fmt.Sprint(v))
			}
		}
		sort.Strings(out)
		return out, nil
	}
	x, e := stringsOf(a)
	if e != nil {
		return types.NewErr("%v", e)
	}
	y, e := stringsOf(b)
	if e != nil {
		return types.NewErr("%v", e)
	}
	if len(x) != len(y) {
		return types.False
	}
	for i := range x {
		if x[i] != y[i] {
			return types.False
		}
	}
	return types.True
}

func plain(v ref.Val) (any, error) {
	if types.IsError(v) || types.IsUnknown(v) {
		return nil, fmt.Errorf("CEL: %v", v)
	}
	switch x := v.(type) {
	case types.Null:
		return nil, nil
	case types.Bool:
		return bool(x), nil
	case types.Int:
		return int64(x), nil
	case types.Uint:
		if uint64(x) <= math.MaxInt64 {
			return int64(x), nil
		}
		return json.Number(strconv.FormatUint(uint64(x), 10)), nil
	case types.Double:
		f := float64(x)
		if !finite(f) {
			return nil, fmt.Errorf("CEL: nonfinite double")
		}
		return f, nil
	case types.String:
		return string(x), nil
	case traits.Lister:
		out := []any{}
		it := x.Iterator()
		for it.HasNext() == types.True {
			a, e := plain(it.Next())
			if e != nil {
				return nil, e
			}
			out = append(out, a)
		}
		return out, nil
	case traits.Mapper:
		out := map[string]any{}
		it := x.Iterator()
		for it.HasNext() == types.True {
			key := it.Next()
			k, ok := key.(types.String)
			if !ok {
				return nil, fmt.Errorf("CEL: JSON map keys must be strings")
			}
			a, e := plain(x.Get(key))
			if e != nil {
				return nil, e
			}
			out[string(k)] = a
		}
		return out, nil
	default:
		return nil, fmt.Errorf("CEL: non-JSON result %s", strings.TrimSpace(fmt.Sprint(v.Type())))
	}
}
