// The kit's adapter of common/log-mask over the package contracts (tools/normgen/contracts; ADR-0125 addendum (5)).
// YOURS from here like any adapter: the kit puts it once instead of the stub.

package vectoradapter

import (
	"kitmodule/internal/contracts"
)

// LogMask — the log mask of raw by the catalogue of the url fields of fields (fields.yaml of the vectors secret-in).
func LogMask(raw string, fields []byte) (string, error) {
	rules, err := contracts.ReadFieldRules(fields)
	if err != nil {
		return "", err
	}
	return contracts.MaskLog(raw, contracts.Union(rules...)), nil
}
