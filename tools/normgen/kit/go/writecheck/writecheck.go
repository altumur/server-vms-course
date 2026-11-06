// Package writecheck checks POST /v1/write before N3:strict jsonstrict parsing under P/01.1 N2.1, then
// the generated write-checks.tsv checks table (ADR-0083 addendum 86, item 2).
// Handwritten;build_kit.py rewrites kitmodule/internal imports.
package writecheck

import (
	"fmt"

	"kitmodule/internal/checks"
	"kitmodule/internal/jsonstrict"
)

// JSONDepth is P/01.1 N2.1 JSON_DEPTH, a shared normative constant, not an input parameter.
const JSONDepth = jsonstrict.Depth

// Limits are the table's #lim names;the caller's lim must include every name, checked by test_kit.py.
var Limits = []string{"BATCH_WRITES", "BATCH_GUARDS", "ROW_CEILING"}

// Refusal contains HTTP Code/Kind and optional int64/string Fault fields. N is the table row, or0 for
// JSON parsing;Check is its name ('json' for parsing);Reason is parsing/fault-evaluation detail.
// N, Check, Reason are journal-only and must not be returned to callers.
type Refusal struct {
	Code   int
	Kind   string
	Fault  map[string]any
	N      int
	Check  string
	Reason string
}

// Check receives a framed, body-size-checked body, socket role, #lim values, and the role's rights callback
// (P/01.2 N3 check:socket, read/write/delete action, key). Return first refusal and parsed body.
// A nil refusal permits N3 with that body;parse failure returns nil body. Missing Limits names or a nil
// allowed callback panic because they are code defects, not invalid input.
func Check(body []byte, sock string, lim map[string]int64, allowed func(sock, op, key string) bool) (*Refusal, any) {
	for _, name := range Limits {
		if _, ok := lim[name]; !ok {
			panic(fmt.Sprintf("writecheck: lim has no %s", name))
		}
	}
	if allowed == nil {
		panic("writecheck: allowed is nil")
	}
	value, lone, err := jsonstrict.Decode(body, JSONDepth)
	if err != nil {
		return &Refusal{Code: err.Code, Kind: err.Kind, Check: "json", Reason: err.Reason}, nil
	}
	r := checks.Check(checks.Input{Body: value, Sock: sock, Lone: lone, Lim: lim, Fns: checks.Fns{Allowed: allowed}})
	if r == nil {
		return nil, value
	}
	out := &Refusal{Code: r.Code, Kind: r.Kind, Fault: r.Fault, N: r.N, Check: r.Check}
	if r.FaultErr != "" {
		out.Reason = "fault: " + r.FaultErr
	}
	return out, value
}
