// The kit's adapter of common/secret-in over the package contracts (tools/normgen/contracts; ADR-0125 addendum (5)).
// YOURS from here like any adapter: the kit puts it once instead of the stub.

package vectoradapter

import (
	"strings"

	"kitmodule/internal/contracts"
)

// secretInSide — the items of the run this lesson performs (secret-in README «Who performs it»): "display" — the
// display masked, "refusal" — fault and text; the kit fills it from the lesson's vectors.
const secretInSide = "@side"

// SecretIn — the credentials of an address: cells field, raw; files fields.yaml → {masked} and/or {fault[, text]}.
func SecretIn(table string, cells map[string]string, files map[string][]byte) Answer {
	rules, err := contracts.ReadFieldRules(files["fields.yaml"])
	if err != nil {
		return Answer{Code: 2, Value: err.Error()}
	}
	var rule *contracts.URLRule
	for i := range rules {
		if rules[i].Field == cells["field"] {
			rule = &rules[i]
		}
	}
	if rule == nil {
		return Answer{Code: 2, Value: "unknown field " + cells["field"]}
	}
	read := contracts.ReadAddress(cells["raw"], *rule, contracts.Union(rules...))
	out := map[string]any{}
	if strings.Contains(secretInSide, "display") {
		out["masked"] = read.Masked
	}
	if strings.Contains(secretInSide, "refusal") {
		out["fault"] = read.Fault
		if read.Fault != "" {
			out["text"] = contracts.URLRefusal(read, *rule)
		}
	}
	return Answer{Value: out}
}
