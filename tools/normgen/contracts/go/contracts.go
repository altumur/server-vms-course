// Package contracts — the kit's implementation of the common contracts of the platform (Platform/common/contracts/*.md),
// shared by every lesson (ADR-0125 addendum (5); the inventory of generation, item 1). Handwritten once for the
// vocabulary, judged by the common vectors (Platform/common/vectors/<package>): tools/normgen/test_contracts.py runs
// the lessons' generated vector tests with the adapters in tools/normgen/contracts/adapters, which call this package.
//
// A function here is the pure computation of its contract; reading files, the environment and the clock is the
// caller's (a lesson's process passes the values in).
package contracts

import "errors"

// ErrRefuse — the contract refuses the input (a start refusal or a refused value; the caller maps it to its code).
var ErrRefuse = errors.New("refused by the contract")
