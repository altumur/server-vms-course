// b1 (product): a key up longer than Backoff.Max whose in-place Restart keeps failing must count failures (lagging, then
// stalled; the delay doubles) — ADR-0033. Also: a wanted key at Rev 0 whose start always fails, what Status says.
// Tree: product, package w2cplatform_test (drop into vmsworker/w2cplatform/ or use `go test -overlay`).
// Expected: RESTART counts 1..6, stalled from 3; REV0 reported (defect if) converged.
package w2cplatform_test

import (
	"errors"
	"testing"
	"time"

	p "vmsworker.local/vmsworker/w2cplatform"
)

func TestProbeB1RestartFailuresOfALongHeldKey(t *testing.T) {
	now := time.Unix(0, 0)
	r, _ := p.NewReconciler(func(string, p.Want) error { return nil }, func(string) error { return nil }, p.Backoff{Base: time.Second, Max: time.Minute, Jitter: 0.5})
	r.Now = func() time.Time { return now }
	r.Rand = func() float64 { return 0.5 }
	r.Restart = func(string, p.Want) error { return errors.New("no") }
	r.Once(map[string]p.Want{"a": {Rev: 1}})
	now = now.Add(100 * time.Second)
	for i := 0; i < 8; i++ {
		ps := r.Once(map[string]p.Want{"a": {Rev: 2}})
		st := r.Status()["a"]
		t.Logf("t=%v failed=%v waiting=%v state=%s failures=%d wait=%v", now.Unix(), len(ps.Failed), ps.Waiting, st.State, st.Failures, st.RetryAt.Sub(now))
		now = now.Add(3 * time.Second)
	}
	r2, _ := p.NewReconciler(func(string, p.Want) error { return errors.New("no") }, func(string) error { return nil }, p.DefaultBackoff)
	n2 := time.Unix(0, 0)
	r2.Now = func() time.Time { return n2 }
	for i := 0; i < 5; i++ {
		r2.Once(map[string]p.Want{"z": {Rev: 0}})
		n2 = n2.Add(100 * time.Second)
	}
	t.Logf("REV0_FAILING_STATUS %+v", r2.Status()["z"])
}
