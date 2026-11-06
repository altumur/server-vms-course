// refusal_judge harness (ADR-0125 generator 4):print refusals.All as JSON and test every HTTP Spec through
// apidoor.Refuse against a declared schema of at least one operation, checking generator agreement.
package main

import (
	"encoding/json"
	"os"

	"normgen/p01-1/apidoor"
	"normgen/p01-1/refusals"
)

type probe struct {
	Fields []string `json:"fields"` // Probe fields.
	Ints   []string `json:"ints"`   // Integer fields among them.
	Ops    []string `json:"ops"`    // Operations that encoded the body.
	Retry  bool     `json:"retry"`  // Retry-After was accepted by at least one operation.
	Body   string   `json:"body"`
}

type row struct {
	*refusals.Spec
	Probes []probe `json:"probes"`
}

func main() {
	var out []row
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
	_ = enc.Encode(out)
}

// try selects the first field-value arrangement(integer, version string, key string) encoding for any operation.
func try(s *refusals.Spec, set []string) probe {
	best := probe{Fields: set, Ints: []string{}, Ops: []string{}}
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
		p := probe{Fields: set, Ints: ints, Ops: []string{}}
		for _, op := range apidoor.Operations {
			a, err := apidoor.Refuse(op.Op, s.Code, s.Kind, "x", values)
			if err != nil {
				continue
			}
			a.RetryAfter = s.RetryAfter
			resp, err := apidoor.Encode(op.Op, a)
			if err != nil {
				a.RetryAfter = false
				if resp, err = apidoor.Encode(op.Op, a); err != nil {
					continue
				}
			} else if s.RetryAfter {
				p.Retry = true
			}
			p.Ops = append(p.Ops, op.Op.String())
			p.Body = string(resp.Body)
		}
		if len(p.Ops) > len(best.Ops) {
			best = p
		}
	}
	return best
}
