// The kit's adapter of common/values-by-type over the package contracts (tools/normgen/contracts; ADR-0125 addendum
// (5)). YOURS from here like any adapter: the kit puts it once instead of the stub.

package vectoradapter

import (
	"crypto/rand"
	"encoding/json"
	"strings"

	"kitmodule/internal/contracts"
)

// ValuesByType — a frame per half of a row: write {type, json} → {status: ok, row[, plaintext]} | {status: absent} |
// {status: refused[, fault]}; read {type, row} → {status: ok, value} | {status: absent} | {status: unreadable}.
func ValuesByType(table, variant string, cells map[string]string, files map[string][]byte) Answer {
	typ := cells["type"]
	if variant == "write" {
		raw := cells["json"]
		w := contracts.ValueToRow(typ, raw, raw != "@unset")
		switch w.Status {
		case "absent":
			return Answer{Value: map[string]any{"status": "absent"}}
		case "refused":
			out := map[string]any{"status": "refused"}
			if w.Fault != "" {
				out["fault"] = w.Fault
			}
			return Answer{Value: out}
		}
		if !w.Seal {
			return Answer{Value: map[string]any{"status": "ok", "row": w.Row}}
		}
		// a secret: seal on a temporary test ring by the regular procedure, open the envelope with the same ring
		key := make([]byte, 32)
		if _, err := rand.Read(key); err != nil {
			return Answer{Code: 2, Value: err.Error()}
		}
		const rowKey, pointer = "testsub2/units/u1", "/value_secret"
		env, err := contracts.Seal(key, "k1", nil, rowKey, pointer, w.Row)
		if err != nil {
			return Answer{Code: 2, Value: err.Error()}
		}
		plain, err := contracts.Open(key, env, rowKey, pointer)
		if err != nil {
			return Answer{Code: 2, Value: err.Error()}
		}
		return Answer{Value: map[string]any{"status": "ok", "row": env, "plaintext": plain}}
	}
	cell := cells["row"]
	var row *string
	sealed := false
	switch {
	case cell == "@absent":
	case cell == "@sealed":
		sealed = true
	case strings.HasPrefix(cell, "@json "):
		t := strings.TrimPrefix(cell, "@json ")
		row = &t
	default:
		var t string
		if err := json.Unmarshal([]byte(cell), &t); err != nil {
			return Answer{Code: 2, Value: err.Error()}
		}
		row = &t
	}
	r := contracts.RowToValue(typ, row, sealed)
	if r.Status != "ok" {
		return Answer{Value: map[string]any{"status": r.Status}}
	}
	return Answer{Value: map[string]any{"status": "ok", "value": r.Value}}
}
