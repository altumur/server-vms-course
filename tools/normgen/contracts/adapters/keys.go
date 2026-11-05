// The kit's adapter of common/keys over the package contracts (tools/normgen/contracts; ADR-0125 addendum (5)).
// YOURS from here like any adapter: the kit puts it once instead of the stub.

package vectoradapter

import (
	"bytes"
	"encoding/json"

	"kitmodule/internal/contracts"
)

// Keys — cases.tsv: {pinned, held, offered} → {result: took | holding, rev} | {result: refused, reason[, rev]}; code
// 2 — an input not of the form; revoked.tsv: {own, answer, now} → the jtis of the row the agent writes.
func Keys(table string, cells map[string]string, files map[string][]byte) Answer {
	bad := Answer{Code: 2, Value: "the input is not of the form"}
	if table == "revoked.tsv" {
		var in struct {
			Own    string   `json:"own"`
			Answer *string  `json:"answer"`
			Now    *float64 `json:"now"`
		}
		if json.Unmarshal([]byte(cells["input"]), &in) != nil || in.Now == nil {
			return bad
		}
		out, err := contracts.MergeRevoked(in.Own, in.Answer, *in.Now)
		if err != nil {
			return bad
		}
		return Answer{Value: out}
	}
	var in map[string]json.RawMessage
	if json.Unmarshal([]byte(cells["input"]), &in) != nil || len(in) != 3 {
		return bad
	}
	var pinned *contracts.Pin
	if raw, ok := in["pinned"]; !ok {
		return bad
	} else if string(raw) != "null" {
		var p map[string]string
		if json.Unmarshal(raw, &p) != nil || len(p) != 2 || p["pub"] == "" || p["domain"] == "" {
			return bad
		}
		pinned = &contracts.Pin{Pub: p["pub"], Domain: p["domain"]}
	}
	var held map[string]any
	if raw, ok := in["held"]; !ok {
		return bad
	} else if string(raw) != "null" {
		d := json.NewDecoder(bytes.NewReader(raw))
		d.UseNumber()
		if d.Decode(&held) != nil || held == nil || !contracts.KeySetForm(held, true) {
			return bad
		}
	}
	offered, ok := in["offered"]
	if !ok {
		return bad
	}
	o := contracts.Keys(pinned, held, offered)
	out := map[string]any{"result": o.Result}
	if o.Reason != "" {
		out["reason"] = o.Reason
	}
	if o.HasRev {
		out["rev"] = o.Rev
	}
	return Answer{Value: out}
}
