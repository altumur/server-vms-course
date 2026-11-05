// The kit's adapter of common/domain-token over the package contracts (tools/normgen/contracts; ADR-0125 addendum
// (5)). YOURS from here like any adapter: the kit puts it once instead of the stub.

package vectoradapter

import (
	"bytes"
	"encoding/json"

	"kitmodule/internal/contracts"
)

// DomainToken — cells input {keys, revoked, now, token, expect?} → {result: ok, payload} | {result: refused, reason};
// code 2 — an input not of the form (expect, the set).
func DomainToken(table string, cells map[string]string, files map[string][]byte) Answer {
	var in map[string]json.RawMessage
	if err := json.Unmarshal([]byte(cells["input"]), &in); err != nil {
		return Answer{Code: 2, Value: err.Error()}
	}
	d := json.NewDecoder(bytes.NewReader(in["keys"]))
	d.UseNumber()
	var doc map[string]any
	if d.Decode(&doc) != nil {
		return Answer{Code: 2, Value: "keys: not an object"}
	}
	keys, err := contracts.ParseTokenKeys(doc)
	if err != nil {
		return Answer{Code: 2, Value: "keys: not a set"}
	}
	var expect *contracts.TokenExpect
	if raw, has := in["expect"]; has {
		if expect, err = contracts.ParseTokenExpect(raw); err != nil {
			return Answer{Code: 2, Value: "expect: out of form"}
		}
	}
	var now float64
	if err := json.Unmarshal(in["now"], &now); err != nil {
		return Answer{Code: 2, Value: "now: not a number"}
	}
	var revoked []byte
	if raw, has := in["revoked"]; has && string(raw) != "null" {
		revoked = raw
	}
	var token any
	_ = json.Unmarshal(in["token"], &token)
	word, payload := contracts.CheckToken(keys, revoked, now, token, expect)
	if word != "" {
		return Answer{Value: map[string]any{"result": "refused", "reason": word}}
	}
	return Answer{Value: map[string]any{"result": "ok", "payload": payload}}
}
