// b4 (product): a STRICT place (row names no server) held by A, whose store went silent; B's wall clock is 8 s ahead.
// The base's ClaimHold takes a hold when B's wall passes the `until` A wrote by A's wall (Slot.Claimable) — while A's
// HoldFreshFor (its own wall, until − margin) still lets A write. Course: `_hold_stale` waits slot_ttl + HOLD_SKEW of
// an unchanged row by the claimant's own clock (worker.py:650). Expected (ADR-0013/0029 single writer): never both.
// Tree: product, package w2cplatform_test (overlay into vmsworker/w2cplatform/). Prints TWO_WRITERS=true on the defect.
package w2cplatform_test

import (
	"testing"

	p "vmsworker.local/vmsworker/w2cplatform"
)

func TestProbeB4ClaimHoldByAForeignClock(t *testing.T) {
	real := 1000.0
	wallA := func() float64 { return real }
	wallB := func() float64 { return real + 8 } // B's clock 8 s ahead: well inside ClockAhead (60 s)
	mem := p.NewMemVariables()
	mem.Put("testsub2/shelves/net", p.Items{"enabled": "true"}, p.NoCAS) // any box may write it: strict
	va := &quietVars{Variables: mem}
	a := p.NewWorker(testsub2Spec.Sub(), va, nil, p.WorkerOptions{Instance: "hostA:1:a", Name: "t-1", Clock: wallA, Wall: wallA, Server: "srv-a", Spec: testsub2Spec})
	b := p.NewWorker(testsub2Spec.Sub(), mem, nil, p.WorkerOptions{Instance: "hostB:1:b", Name: "t-2", Clock: wallB, Wall: wallB, Server: "srv-b", Spec: testsub2Spec})
	if got, _ := a.ClaimHold([]string{"net"}); got != "net" {
		t.Fatal("A did not take it", got)
	}
	va.down = true // A is cut off from the store: it renews nothing, and writes while HoldFresh says so
	for _, at := range []float64{30, 36, 37.5, 39, 41} {
		real = 1000 + at
		got, _ := b.ClaimHold([]string{"net"})
		t.Logf("t=+%.1fs A.fresh=%v B.claim=%q TWO_WRITERS=%v", at, a.HoldFreshFor("net"), got, a.HoldFreshFor("net") && b.Hold == "net")
	}
}
