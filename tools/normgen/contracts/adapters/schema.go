// The kit's adapter of common/schema over the package contracts (tools/normgen/contracts; ADR-0125 addendum (5)).
// YOURS from here like any adapter: the kit puts it once instead of the stub.

package vectoradapter

import (
	"encoding/json"

	"kitmodule/internal/contracts"
)

// Schema — the schema start check: cells input {SCHEMA, row} → {start: true, version} | {refuse: "too_new", n} |
// {refuse: "not_a_form"}.
func Schema(table string, cells map[string]string, files map[string][]byte) Answer {
	var in struct {
		SCHEMA int64                       `json:"SCHEMA"`
		Row    map[string]*json.RawMessage `json:"row"`
	}
	if err := json.Unmarshal([]byte(cells["input"]), &in); err != nil {
		return Answer{Code: 2, Value: err.Error()}
	}
	var row *contracts.SchemaRow
	if in.Row != nil {
		row = &contracts.SchemaRow{}
		for k, raw := range in.Row {
			var s string
			if raw == nil || json.Unmarshal(*raw, &s) != nil {
				return Answer{Value: map[string]any{"refuse": "not_a_form"}}
			}
			switch k {
			case "version":
				row.Version = s
			case "at":
				row.At = s
			case "revision":
				row.Revision = &s
			default:
				return Answer{Value: map[string]any{"refuse": "not_a_form"}}
			}
		}
	}
	c := contracts.CheckSchema(row, in.SCHEMA)
	switch {
	case c.Start:
		return Answer{Value: map[string]any{"start": true, "version": c.Version}}
	case c.Refuse == "too_new":
		return Answer{Value: map[string]any{"refuse": "too_new", "n": c.N}}
	}
	return Answer{Value: map[string]any{"refuse": "not_a_form"}}
}
