// The kit's adapter of common/crl over the package contracts (tools/normgen/contracts; ADR-0125 addendum (5)).
// YOURS from here like any adapter: the kit puts it once instead of the stub.

package vectoradapter

import (
	"encoding/json"

	"kitmodule/internal/contracts"
)

func crlList(xs []string) []any {
	out := make([]any, 0, len(xs))
	for _, x := range xs {
		out = append(out, x)
	}
	return out
}

// CRL — crl.pem by the centers: input {ca, ca_next (null — none), crl, now}; {ca, ca_next, stale} or "@bad".
func CRL(input []byte) (any, error) {
	var in struct {
		CA     string  `json:"ca"`
		CANext *string `json:"ca_next"`
		CRL    string  `json:"crl"`
		Now    int64   `json:"now"`
	}
	if err := json.Unmarshal(input, &in); err != nil {
		return nil, err
	}
	var next []byte
	if in.CANext != nil {
		next = []byte(*in.CANext)
	}
	r, err := contracts.ReadCRL([]byte(in.CA), next, []byte(in.CRL), in.Now)
	if err != nil {
		return "@bad", nil
	}
	out := map[string]any{"ca": crlList(r.CA), "ca_next": nil, "stale": crlList(r.Stale)}
	if r.CANext != nil {
		out["ca_next"] = crlList(r.CANext)
	}
	return out, nil
}
