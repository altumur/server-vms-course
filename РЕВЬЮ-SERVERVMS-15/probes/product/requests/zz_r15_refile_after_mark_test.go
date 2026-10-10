// R15 probe (product): a request whose row the reaper cleared AFTER writing its end into the mark (EndRequestMark,
// expired) is not filed again under the same rid while the mark stands — the fourteenth review's major 2 as the
// product performs it (the row goes only after a mark: reaper or the console's own pass). Uses filingBox from the
// r14 probe copy in the same package.
package w2cplatform_test

import (
	"testing"

	p "vmsworker.local/vmsworker/w2cplatform"
)

func TestR15RefileAfterReaperMark(t *testing.T) {
	box, vars, worker := filingBox(t)
	w := worker("testsub2", "t-1")
	now := box.Wall.Now()
	row := map[string]any{"unit": "testsub/c1", "add": 2, "valid_until": now + 600}
	a, _ := w.FileRequest("testsub", "fire-2-0", row, "t1", now)
	items, _, _ := vars.Get("testsub/requests/fire-2-0")
	if err := p.EndRequestMark(box.Objects, p.Subsystem{Name: "testsub"}, "fire-2-0", items, "expired", "", "reaper", now+60); err != nil {
		t.Fatal(err)
	}
	vars.Delete("testsub/requests/fire-2-0", p.NoCAS) // the reaper clears the row after its mark
	box.Wall.Advance(120)
	b, err := w.FileRequest("testsub", "fire-2-0", row, "t1", now)
	t.Logf("MEASURED refile after reaper mark: first=%v second=%v err=%v filings=%v", a, b, err, filingsSaid(t, box, w))
	if b {
		t.Errorf("filed twice under one rid although its mark stands")
	}
}
