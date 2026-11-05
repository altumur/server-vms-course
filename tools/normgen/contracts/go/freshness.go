package contracts

import "math/big"

// Observation contract, «Freshness: LOST_AFTER»: fresh — the age of the observed version ≤ LOST_AFTER.

// LostAfter — LOST_AFTER, seconds.
const LostAfter = 45

// Fresh — the age (seconds, a fraction allowed) is not greater than LOST_AFTER; the comparison is exact, not
// coarsened to whole seconds.
func Fresh(age *big.Rat) bool { return age.Cmp(big.NewRat(LostAfter, 1)) <= 0 }
