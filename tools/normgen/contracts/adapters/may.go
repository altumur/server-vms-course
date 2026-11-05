// The kit's adapter of common/may over the package contracts (tools/normgen/contracts; ADR-0125 addendum (5)).
// YOURS from here like any adapter: the kit puts it once instead of the stub.

package vectoradapter

import (
	"encoding/json"

	"kitmodule/internal/contracts"
)

// May — cases.tsv: the input of may → {result: allow} | {result: deny, reason} | {result: unavailable}; covers.tsv:
// {scope, ref, row} → true | false; code 2 — an input not of the form.
func May(table string, cells map[string]string, files map[string][]byte) Answer {
	bad := Answer{Code: 2, Value: "the input is not of the form"}
	if table == "covers.tsv" {
		var in map[string]json.RawMessage
		if json.Unmarshal([]byte(cells["input"]), &in) != nil {
			return bad
		}
		var scope string
		var ref struct{ Sub, ID string }
		if json.Unmarshal(in["scope"], &scope) != nil || json.Unmarshal(in["ref"], &ref) != nil ||
			!contracts.ValidGrantScope(scope) {
			return bad
		}
		var word string
		if json.Unmarshal(in["row"], &word) == nil {
			if word != "@unreadable" {
				return bad
			}
			// an unreadable row: only * and unit: by the name of ref
			u := contracts.MayUnit{Kind: "unit", Sub: ref.Sub, ID: ref.ID, AboutUnknown: true}
			return Answer{Value: scope == "*" || len(scope) > 5 && scope[:5] == "unit:" && contracts.ScopeCovers(scope, &u)}
		}
		row := map[string]json.RawMessage{}
		if json.Unmarshal(in["row"], &row) != nil {
			return bad
		}
		row["sub"], _ = json.Marshal(ref.Sub)
		row["id"], _ = json.Marshal(ref.ID)
		raw, _ := json.Marshal(row)
		u, err := contracts.ParseMayUnitJSON(raw)
		if err != nil {
			return bad
		}
		return Answer{Value: contracts.ScopeCovers(scope, &u)}
	}
	in, err := contracts.ParseMayInput([]byte(cells["input"]))
	if err != nil {
		return bad
	}
	o := contracts.May(in)
	out := map[string]any{"result": o.Result}
	if o.Reason != "" {
		out["reason"] = o.Reason
	}
	return Answer{Value: out}
}
