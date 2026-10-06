// r14 probe (product, package vms_test; run with -overlay into vmsworker/vms/): an AutoWorker firing whose first action
// is refused (a different row under its rid) RETURNS the error — the firing's later actions are not filed, and Evaluate
// returns the error before the cursor moves (autoworker.go:707-709, 312-313). Expected on 2d46e95: err non-nil, rec/requests/f-1
// absent. The course (`vms/autoworker.py:552-555`) skips the refused action and files the rest.
package vms_test

import (
	"testing"

	"vmsworker.local/vmsworker/testbox"
	p "vmsworker.local/vmsworker/w2cplatform"
	"vmsworker.local/vmsworker/vms"
)

func TestR14ARefusedActionStopsTheFiring(t *testing.T) {
	box := testbox.NewBox()
	ctl := vms.NewVmsController(box.Vars, box.Objects, 50, box.Wall.Now)
	if _, err := ctl.CreateCamera(map[string]any{"name": "door", "source": "rtsp://ACME.local./ch1"}); err != nil {
		t.Fatal(err)
	}
	// a different request already stands under the firing's first rid (a scenario edited, a group moved, a person's id)
	box.Vars.Put(vms.VMS.RequestKey("f-0"), p.Items{"action": "preset", "unit": "1", "n": "9", "by": "op", "at": "1"}, p.NoCAS)
	w := autoWorker(t, box, &fakeLog{}, "a-1")
	row := p.Row{"id": "door-on-badge", "then": []any{
		map[string]any{"sub": "vms", "action": "output", "unit": "1", "port": "1"},
		map[string]any{"sub": "rec", "action": "record", "cam": "1", "minutes": "1"},
	}}
	err := w.File(row, "f", box.Wall.Now())
	rec, _, _ := box.Vars.Get(vms.RecSpec.Sub().RequestKey("f-1"))
	t.Logf("MEASURED File err=%v ; rec/requests/f-1 written=%v", err, rec != nil)
}

// r14 probe (product): a scenario named "asks-door" fires; its evaluator files vms/requests/asks-door-ev1-0 (counted
// filed); the camera's holder never looks at it (requestserver.go:212 skips rids with LedgerPrefix "asks-"), so the
// relay is not pulsed and no outcome is written. Expected on 2d46e95: filed=1, performed=0, outcome "", row still stands.
// Control: the same scenario named "door" is performed.
func TestR14AScenarioNamedAsksIsNeverPerformed(t *testing.T) {
	for _, name := range []string{"door", "asks-door"} {
		box := testbox.NewBox()
		ctl := vms.NewVmsController(box.Vars, box.Objects, 50, box.Wall.Now)
		if _, err := ctl.CreateCamera(map[string]any{"name": "door", "source": "rtsp://10.0.0.7/ch1"}); err != nil {
			t.Fatal(err)
		}
		act := vms.NewFakeActuator()
		hw := worker(t, box, "w-1", act, vms.VmsWorkerOptions{Server: "srv-1"})
		ctl.Assign("w-1", []string{"1"})
		hw.ReconcileOnce()
		aw := autoWorker(t, box, &fakeLog{}, "a-1")
		row := p.Row{"id": name, "then": []any{map[string]any{"sub": "vms", "action": "preset", "unit": "1", "n": "3"}}}
		now := box.Wall.Now()
		err := aw.File(row, name+"-ev1", now)
		for i := 0; i < 3; i++ {
			commands(t, hw, now)
		}
		it, _, _ := box.Vars.Get(vms.VMS.RequestKey(name + "-ev1-0"))
		t.Logf("MEASURED scenario %q: file err=%v filed=%d performed=%d outcome=%q row-stands=%v",
			name, err, aw.Filed(), len(act.Did), vms.CommandOutcome(box.Objects, name+"-ev1-0"), it != nil)
	}
}
