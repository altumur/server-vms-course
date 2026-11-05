// The kit's adapter of common/peer over the package contracts (tools/normgen/contracts; ADR-0125 addendum (5)).
// YOURS from here like any adapter: the kit puts it once instead of the stub.

package vectoradapter

import (
	"encoding/json"

	"kitmodule/internal/contracts"
)

// Peer — cells input {chain, fingerprints, role, host, now} → {result: ok} | {result: refused, reason}; code 2 — an
// input not of the form.
func Peer(table string, cells map[string]string, files map[string][]byte) Answer {
	var in struct {
		Chain        *[]string `json:"chain"`
		Fingerprints *[]string `json:"fingerprints"`
		Role         *string   `json:"role"`
		Host         *string   `json:"host"`
		Now          *int64    `json:"now"`
	}
	if err := json.Unmarshal([]byte(cells["input"]), &in); err != nil || in.Chain == nil ||
		in.Fingerprints == nil || in.Role == nil || in.Host == nil || in.Now == nil {
		return Answer{Code: 2, Value: "the input is not of the form"}
	}
	r := contracts.Peer(*in.Chain, *in.Fingerprints, *in.Role, *in.Host, *in.Now)
	if r == "ok" {
		return Answer{Value: map[string]any{"result": "ok"}}
	}
	return Answer{Value: map[string]any{"result": "refused", "reason": r}}
}
