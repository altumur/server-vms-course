// b3 (product): the base's TakeEpoch for a unit the lease step let go to a newer epoch, BEFORE the assignment is read
// again. Course (worker.py take_epoch, ADR-0013 / 13th review M6) refuses it — "the rule is the epoch's, whoever asks";
// expected the same in the product. Tree: product, package w2cplatform_test (overlay into vmsworker/w2cplatform/).
// Prints TAKEN_BACK=true when the base gives the epoch back over the new holder (the rule kept only by callers).
package w2cplatform_test

import (
	"testing"

	"vmsworker.local/vmsworker/testbox"
	p "vmsworker.local/vmsworker/w2cplatform"
)

func TestProbeB3TakeEpochAfterLostToEpoch(t *testing.T) {
	box := testbox.NewBox()
	c := p.NewController(testsub2Spec.Sub(), box.Vars, box.Objects, box.Wall.Now)
	w := p.NewWorker(testsub2Spec.Sub(), box.Vars, box.Objects, p.WorkerOptions{Instance: "A", Clock: box.Clock.Now, Wall: box.Wall.Now, Spec: testsub2Spec})
	name, err := w.ClaimSlot("")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := c.Assign(name, []string{"u1"}); err != nil {
		t.Fatal(err)
	}
	w.Assignment()
	e1, err := w.TakeEpoch("u1")
	if err != nil {
		t.Fatal(err)
	}
	theirs, _, _ := p.NextEpoch(box.Vars, testsub2Spec.Sub().EpochKey("u1")) // the unit's new holder
	lost := w.RenewLeases()
	t.Logf("lost=%v LostToEpoch=%v", lost, w.LostToEpoch("u1"))
	w.Release("u1")
	e3, err := w.TakeEpoch("u1") // no assignment read since the loss
	t.Logf("mine=%d theirs=%d retake=%d err=%v TAKEN_BACK=%v", e1, theirs, e3, err, err == nil)
}
