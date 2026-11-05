// The kit's adapter of common/fresh-age over the package contracts (tools/normgen/contracts; ADR-0125 addendum (5)).
// YOURS from here like any adapter: the kit puts it once instead of the stub.

package vectoradapter

import (
	"math/big"

	"kitmodule/internal/contracts"
)

// FreshAge — cells age (the age in seconds, a JSON number) → fresh: true | false.
func FreshAge(table string, cells map[string]string, files map[string][]byte) Answer {
	age, ok := new(big.Rat).SetString(cells["age"])
	if !ok || age.Sign() < 0 {
		return Answer{Code: 2, Value: "the age is not a non-negative number"}
	}
	return Answer{Value: contracts.Fresh(age)}
}
