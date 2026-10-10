// RERUN-15 COPY of РЕВЬЮ-SERVERVMS-14/probes/filings/go/r14_filings_platform_test.go for product c86571d: p.LedgerPrefix is gone (ADR-0060);
// the final sanity check on the prefix is replaced by the literal "asks-".
// r14 probe (product, package w2cplatform_test; run with -overlay into vmsworker/w2cplatform/): Worker.FileRequest
// claims and edges. Expected on 2d46e95: claims hold (stamps refused, repeat=false+again, conflict=refused);
// DEFECTS shown: a Get failure after a conflict is counted nowhere (filings stay 0/0/0); a row gone after a conflict
// is called "a different request"; a refile after the row was cleared is a fresh filing (true); rid "asks-*" is filed
// (the holder and the reaper skip that prefix: requestserver.go:212, requests.go:598); NaN `at` is written as "NaN".
package w2cplatform_test

import (
	"errors"
	"math"
	"strings"
	"testing"

	p "vmsworker.local/vmsworker/w2cplatform"
)

type r14Flaky struct {
	p.Variables
	conflict bool
	getErr   error
	getNil   bool
}

func (v *r14Flaky) Put(path string, it p.Items, cas p.Index) (p.Index, error) {
	if v.conflict {
		return p.Absent, p.ErrConflict
	}
	return v.Variables.Put(path, it, cas)
}

func (v *r14Flaky) Get(path string) (p.Items, p.Index, error) {
	if v.getErr != nil {
		return nil, p.Absent, v.getErr
	}
	if v.getNil {
		return nil, p.Absent, nil
	}
	return v.Variables.Get(path)
}

func TestR14ClaimsHold(t *testing.T) {
	box, vars, worker := filingBox(t)
	w := worker("testsub2", "t-1")
	for _, k := range []string{"by", "at", "filed"} {
		_, err := w.FileRequest("testsub", "s-"+k, map[string]any{"unit": "testsub/c1", k: "x"}, "", 0)
		refusedWith(t, err, "the platform's to stamp")
	}
	now := box.Wall.Now()
	row := map[string]any{"unit": "testsub/c1", "add": 2, "valid_until": now + 30}
	if ok, err := w.FileRequest("testsub", "r1", row, "t1", now-4); !ok || err != nil {
		t.Fatal(ok, err)
	}
	box.Wall.Advance(7)
	if ok, err := w.FileRequest("testsub", "r1", row, "t1", now-4); ok || err != nil {
		t.Fatalf("repeat: %v %v", ok, err)
	}
	if _, err := w.FileRequest("testsub", "r1", map[string]any{"unit": "testsub/c1", "add": 3, "valid_until": now + 30}, "t1", now-4); !errors.Is(err, p.ErrConflict) {
		t.Fatalf("conflict: %v", err)
	}
	f := filingsSaid(t, box, w)
	t.Logf("MEASURED filings after 3 stamps + file + repeat + conflict: %v (keys %v)", f, listed(t, vars, "testsub/requests/"))
}

func TestR14GetFailureAfterConflictIsCountedNowhere(t *testing.T) {
	box, vars, _ := filingBox(t)
	s, _ := p.LoadSpec("testdata/testsub2.subsystem.yaml")
	fl := &r14Flaky{Variables: vars, conflict: true, getErr: errors.New("store did not answer")}
	w := p.NewWorker(s.Sub(), fl, box.Objects, p.WorkerOptions{Name: "t-9", Clock: box.Clock.Now, Wall: box.Wall.Now, Spec: s})
	ok, err := w.FileRequest("testsub", "g1", map[string]any{"unit": "testsub/c1", "add": 1}, "", 0)
	var rr *p.RequestRefused
	t.Logf("MEASURED get-error-after-conflict: filed=%v err=%v isRefused=%v isConflict=%v filings=%v",
		ok, err, errors.As(err, &rr), errors.Is(err, p.ErrConflict), filingsSaid(t, box, w))
	fl.getErr, fl.getNil = nil, true
	_, err = w.FileRequest("testsub", "g2", map[string]any{"unit": "testsub/c1", "add": 1}, "", 0)
	t.Logf("MEASURED row-gone-after-conflict: err=%v (course says: 'the row that stood under this rid is gone')", err)
}

func TestR14RefileAfterClearAndLedgerPrefixAndNaN(t *testing.T) {
	box, vars, worker := filingBox(t)
	w := worker("testsub2", "t-1")
	now := box.Wall.Now()
	row := map[string]any{"unit": "testsub/c1", "add": 2, "valid_until": now + 600}
	a, _ := w.FileRequest("testsub", "fire-1-0", row, "t1", now)
	vars.Delete("testsub/requests/fire-1-0", p.NoCAS) // the console's clear_requests after the holder answered
	box.Wall.Advance(120)                             // a refile within valid_until (failover: cursor lost, fired forgotten)
	b, err := w.FileRequest("testsub", "fire-1-0", row, "t1", now)
	t.Logf("MEASURED refile after clear: first=%v second=%v err=%v filings=%v", a, b, err, filingsSaid(t, box, w))
	c, err := w.FileRequest("testsub", "asks-door-ev1-0", map[string]any{"unit": "testsub/c1", "add": 1}, "", 0)
	t.Logf("MEASURED rid with the ledger prefix: filed=%v err=%v (holder skips HasPrefix(rid, LedgerPrefix))", c, err)
	d, err := w.FileRequest("testsub", "nan-1", map[string]any{"unit": "testsub/c1", "add": 1}, "", math.NaN())
	it, _, _ := vars.Get("testsub/requests/nan-1")
	t.Logf("MEASURED NaN at: filed=%v err=%v at=%q", d, err, it["at"])
	if !strings.HasPrefix("asks-", "asks") {
		t.Fatal("ledger prefix changed")
	}
}
