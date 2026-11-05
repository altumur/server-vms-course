// The kit's adapter of common/log-mask mask_in.tsv over the package contracts (tools/normgen/contracts; ADR-0125
// addendum (5)). YOURS from here like any adapter: the kit puts it once instead of the stub.

package vectoradapter

import (
	"encoding/json"

	"kitmodule/internal/contracts"
)

// LogMaskIn — mask_in: cells value (a JSON string) → {mask}.
func LogMaskIn(table string, cells map[string]string, files map[string][]byte) Answer {
	var v string
	if err := json.Unmarshal([]byte(cells["value"]), &v); err != nil {
		return Answer{Code: 2, Value: err.Error()}
	}
	return Answer{Value: map[string]any{"mask": contracts.MaskIn(v)}}
}
