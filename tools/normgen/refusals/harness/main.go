// refusal_judge harness (ADR-0125 generator 4):print refusals.All as JSON and test every HTTP Spec through
// apidoor.Refuse against a declared schema of at least one operation, checking generator agreement.
package main

import (
	"encoding/json"
	"fmt"
	"os"
	"reflect"
	"strconv"
	"strings"

	"normgen/p01-1/apidoor"
	"normgen/p01-1/refusals"
)

type wireProbe struct {
	Op        string      `json:"op"`
	Requested [][2]string `json:"requested"` // Explicit probe inputs, not a deadline calculation.
	Headers   [][2]string `json:"headers"`   // Actual Encode output.
}

type probe struct {
	Fields []string    `json:"fields"` // Probe fields.
	Ints   []string    `json:"ints"`   // Integer fields among them.
	Ops    []string    `json:"ops"`    // Operations that encoded the body.
	Retry  bool        `json:"retry"`  // Retry-After was accepted by at least one operation.
	Body   string      `json:"body"`
	Wire   []wireProbe `json:"wire"`
}

type row struct {
	*refusals.Spec
	Probes []probe `json:"probes"`
}

type report struct {
	Version   int   `json:"version"`
	Declared  int   `json:"declared"`
	Completed int   `json:"completed"`
	Rows      []row `json:"rows"`
}

func main() {
	declared := len(refusals.All)
	out := make([]row, 0, declared)
	for _, s := range refusals.All {
		r := row{Spec: s}
		if s.Surface == "http" {
			var req, all []string
			for _, f := range s.Fields {
				if !f.Optional {
					req = append(req, f.Name)
				}
				all = append(all, f.Name)
			}
			sets := [][]string{req}
			if len(all) != len(req) {
				sets = append(sets, all)
			}
			for _, set := range sets {
				r.Probes = append(r.Probes, try(s, set))
			}
		}
		out = append(out, r)
	}
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", " ")
	if err := enc.Encode(report{Version: 1, Declared: declared, Completed: len(out), Rows: out}); err != nil {
		fmt.Fprintln(os.Stderr, "refusal readback encoding:", err)
		os.Exit(2)
	}
}

// try selects the first field-value arrangement(integer, version string, key string) encoding for any operation.
func try(s *refusals.Spec, set []string) probe {
	best := probe{Fields: set, Ints: []string{}, Ops: []string{}, Wire: []wireProbe{}}
	choices := []any{int64(4194364), "1", "testsub/k"} // Integer, version string, key string.
	total := 1
	for range set {
		total *= len(choices)
	}
	for combo := 0; combo < total; combo++ {
		values, ints := map[string]any{}, []string{}
		for k, c := 0, combo; k < len(set); k, c = k+1, c/len(choices) {
			values[set[k]] = choices[c%len(choices)]
			if c%len(choices) == 0 {
				ints = append(ints, set[k])
			}
		}
		if s.Check(values) != nil {
			continue
		}
		p := probe{Fields: set, Ints: ints, Ops: []string{}, Wire: []wireProbe{}}
		for _, op := range apidoor.Operations {
			a, err := apidoor.Refuse(op.Op, s.Code, s.Kind, "x", values)
			if err != nil {
				continue
			}
			requested := [][2]string{}
			for _, pair := range s.Headers {
				if setHeader(&a, pair[0], pair[1]) {
					requested = append(requested, pair)
				}
			}
			for _, name := range s.DynamicHeaders {
				// 17 is an input to exercise scalar transport; the implementation owns admission timing.
				if setHeader(&a, name, "17") {
					requested = append(requested, [2]string{name, "17"})
				}
			}
			resp, err := apidoor.Encode(op.Op, a)
			if err != nil {
				a, _ = apidoor.Refuse(op.Op, s.Code, s.Kind, "x", values)
				requested = [][2]string{}
				if resp, err = apidoor.Encode(op.Op, a); err != nil {
					continue
				}
			}
			for _, pair := range resp.Header {
				if strings.EqualFold(pair[0], "Retry-After") {
					p.Retry = true
				}
			}
			p.Ops = append(p.Ops, op.Op.String())
			p.Wire = append(p.Wire, wireProbe{Op: op.Op.String(), Requested: requested, Headers: append([][2]string{}, resp.Header...)})
			p.Body = string(resp.Body)
		}
		if len(p.Ops) > len(best.Ops) {
			best = p
		}
	}
	return best
}

// setHeader binds a declared probe value to the generated Answer scalar field.
// A framing-owned header such as Connection has no Answer field and stays metadata-only.
func setHeader(a *apidoor.Answer, name, value string) bool {
	answer := reflect.ValueOf(a).Elem()
	var field reflect.Value
	for i := 0; i < answer.NumField(); i++ {
		if strings.EqualFold(answer.Type().Field(i).Name, strings.ReplaceAll(name, "-", "")) {
			field = answer.Field(i)
			break
		}
	}
	if !field.IsValid() || !field.CanSet() {
		return false
	}
	if field.Kind() == reflect.Bool {
		field.SetBool(true)
		return true
	}
	if field.Kind() != reflect.Ptr {
		return false
	}
	x := reflect.New(field.Type().Elem())
	switch x.Elem().Kind() {
	case reflect.String:
		x.Elem().SetString(value)
	case reflect.Int64:
		n, e := strconv.ParseInt(value, 10, 64)
		if e != nil {
			return false
		}
		x.Elem().SetInt(n)
	case reflect.Uint64:
		n, e := strconv.ParseUint(value, 10, 64)
		if e != nil {
			return false
		}
		x.Elem().SetUint(n)
	default:
		return false
	}
	field.Set(x)
	return true
}
