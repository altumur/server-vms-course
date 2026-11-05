// The kit's adapter of common/revoked over the package contracts (tools/normgen/contracts; ADR-0125 addendum (5)).
// YOURS from here like any adapter: the kit puts it once instead of the stub.

package vectoradapter

import (
	"encoding/json"

	"kitmodule/internal/contracts"
)

func serialList(xs []string) []any {
	out := make([]any, 0, len(xs))
	for _, x := range xs {
		out = append(out, x)
	}
	return out
}

// Revoked — the revoked serials by the cell file: a JSON string — revoked; "@absent" — neither file; {revoked, crl}
// — both (revoked "@absent" — no file; crl the serials of the CRL already read or "@bad"). "@bad" — the refusal.
func Revoked(file []byte) (any, error) {
	var content string
	var revoked []byte
	var crl []string
	if string(file) == "@absent" {
		// neither revoked nor crl.pem
	} else if json.Unmarshal(file, &content) == nil {
		if content != "@absent" {
			revoked = []byte(content)
		}
	} else {
		var both struct {
			Revoked string          `json:"revoked"`
			CRL     json.RawMessage `json:"crl"`
		}
		if err := json.Unmarshal(file, &both); err != nil {
			return nil, err
		}
		if both.Revoked != "@absent" {
			revoked = []byte(both.Revoked)
		}
		var word string
		if json.Unmarshal(both.CRL, &word) == nil {
			if word == "@bad" {
				return "@bad", nil
			}
		} else if err := json.Unmarshal(both.CRL, &crl); err != nil {
			return nil, err
		} else if crl == nil {
			crl = []string{}
		}
	}
	out, err := contracts.RevokedUnion(revoked, crl)
	if err != nil {
		return "@bad", nil
	}
	return serialList(out), nil
}
