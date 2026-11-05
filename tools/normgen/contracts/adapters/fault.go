// The kit's adapter of common/fault over the package contracts (tools/normgen/contracts; ADR-0125 addendum (5)).
// YOURS from here like any adapter: the kit puts it once instead of the stub.

package vectoradapter

import "kitmodule/internal/contracts"

// Fault — the dictionary of the refusal words of the doors: {<word>: <HTTP code>}.
func Fault(table string, cells map[string]string, files map[string][]byte) Answer {
	out := map[string]any{}
	for w, code := range contracts.FaultWords {
		out[w] = code
	}
	return Answer{Value: out}
}
