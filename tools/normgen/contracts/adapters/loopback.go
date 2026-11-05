// The kit's adapter of common/loopback over the package contracts (tools/normgen/contracts; ADR-0125 addendum (5)).
// YOURS from here like any adapter: the kit puts it once instead of the stub.

package vectoradapter

import (
	"encoding/json"

	"kitmodule/internal/contracts"
)

// Loopback — the loopback threshold: cells input {url} → "loopback" | "ip" | "name"; code 2 — not of the form.
func Loopback(table string, cells map[string]string, files map[string][]byte) Answer {
	var in map[string]json.RawMessage
	if json.Unmarshal([]byte(cells["input"]), &in) != nil || in == nil {
		return Answer{Code: 2, Value: "the input is not an object"}
	}
	var url string
	if raw, ok := in["url"]; !ok || json.Unmarshal(raw, &url) != nil {
		return Answer{Code: 2, Value: "no url string"}
	}
	kind, err := contracts.LoopbackKind(url)
	if err != nil {
		return Answer{Code: 2, Value: "bad_url"}
	}
	return Answer{Value: kind}
}
