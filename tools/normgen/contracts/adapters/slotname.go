// The kit's adapter of common/slot-name over the package contracts (tools/normgen/contracts; ADR-0125 addendum (5)).
// YOURS from here like any adapter: the kit puts it once instead of the stub.

package vectoradapter

import (
	"encoding/json"

	"kitmodule/internal/contracts"
)

// SlotName — common/slot-name by op: order → the names in order; next → the next name; role → {server, n} |
// "not_role".
func SlotName(table string, cells map[string]string, files map[string][]byte) Answer {
	var in struct {
		Prefix string   `json:"prefix"`
		Names  []string `json:"names"`
		Name   string   `json:"name"`
		Server *string  `json:"server"`
	}
	if json.Unmarshal([]byte(cells["input"]), &in) != nil {
		return Answer{Code: 2}
	}
	switch cells["op"] {
	case "order":
		out := []any{}
		for _, n := range contracts.SlotOrder(in.Prefix, in.Names) {
			out = append(out, n)
		}
		return Answer{Value: out}
	case "next":
		return Answer{Value: contracts.NextName(in.Prefix, in.Names)}
	case "role":
		s, n, ok := contracts.RoleOf(in.Prefix, in.Name, in.Server)
		if !ok {
			return Answer{Value: "not_role"}
		}
		return Answer{Value: map[string]any{"server": s, "n": n}}
	}
	return Answer{Code: 2}
}
