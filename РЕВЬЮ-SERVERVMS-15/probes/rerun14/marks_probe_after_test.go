// RERUN-15 COPY of РЕВЬЮ-SERVERVMS-14/probes/marks/go/marks_probe_test.go for product c86571d: p.LedgerPrefix is gone (ADR-0060: ledgers
// live under <sub>/asked/, not among the request rows); the rid filter uses the literal "asks-" (a no-op now).
// Probe (PRODUCT, ADR-0054, 14th review, area "marks"): runs inside package w2cplatform_test over the product tree via
// `go test -overlay` (see run_marks_probe.sh) — the tree is not touched. Uses the package's own test beds
// (newServerBed, bedOf, assign). Each test prints MEASURED lines; expected results are in each test's comment.
package w2cplatform_test

import (
	"encoding/json"
	"errors"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	p "vmsworker.local/vmsworker/w2cplatform"
)

// Race: a closer's CompleteMark (by index) against the holder's unconditional Put of its answer, two closers at once,
// two create-only writers at once, and the holder's sweep (Delete) against a closer's PutAt — on the file store and on
// the cluster store (rows over MemVariables). Expected: the answer always stands, a closer never writes over an outcome,
// exactly one closer and one create-only writer wins; a mark deleted by the sweep is not brought back by a closer.
func TestProbeMarksRace(t *testing.T) {
	const n = 300
	key := testsubSpec.Sub().CommandKey("r1")
	begun := []byte(`{"at":1,"instance":"A","slot":"w-1","unit":"c1"}`)
	answer := []byte(`{"at":1,"instance":"A","outcome":"performed","slot":"w-1","unit":"c1"}`)
	fs, _ := p.NewFsObjectStore(t.TempDir())
	cl, err := p.NewClusterObjectStore(filepath.Join(t.TempDir(), "objects"), "srv-a", "", p.NewMemVariables())
	if err != nil {
		t.Fatal(err)
	}
	type store interface {
		p.ObjectStore
		p.IndexPutter
		PutNew(string, []byte) error
	}
	race := func(fs ...func() bool) []bool {
		var wg sync.WaitGroup
		start := make(chan struct{})
		out := make([]bool, len(fs))
		for i, f := range fs {
			wg.Add(1)
			go func(i int, f func() bool) { defer wg.Done(); <-start; out[i] = f() }(i, f)
		}
		close(start)
		wg.Wait()
		return out
	}
	for name, s := range map[string]store{"files": fs, "cluster-rows": cl} {
		lost, over, both, resurrected := 0, 0, 0, 0
		closers := map[int]int{}
		for i := 0; i < n; i++ {
			s.Delete(key)
			s.PutNew(key, begun)
			race(func() bool { w, _ := p.CompleteMark(s, key, "unknown", "gone", 3); return w },
				func() bool { return s.Put(key, answer) == nil })
			if raw, _ := s.Get(key); !strings.Contains(string(raw), `"performed"`) {
				lost++
			}
			if w, _ := p.CompleteMark(s, key, "unknown", "late", 4); w {
				over++
			}
			s.Delete(key)
			s.PutNew(key, begun)
			r := race(func() bool { w, _ := p.CompleteMark(s, key, "unknown", "reaper", 5); return w },
				func() bool { w, _ := p.CompleteMark(s, key, "unknown", "holder-B", 5); return w })
			c := 0
			for _, x := range r {
				if x {
					c++
				}
			}
			closers[c]++
			s.Delete(key)
			r = race(func() bool { return s.PutNew(key, []byte(`{"outcome":"expired","ended_by":"reaper"}`)) == nil },
				func() bool { return s.PutNew(key, begun) == nil })
			if r[0] == r[1] {
				both++
			}
			// the sweep (Delete, a row gone) against a closer: a deleted mark must stay deleted
			s.Delete(key)
			s.PutNew(key, begun)
			r = race(func() bool { ok, _ := s.Delete(key); return ok },
				func() bool { w, _ := p.CompleteMark(s, key, "unknown", "gone", 6); return w })
			if raw, _ := s.Get(key); raw != nil && r[0] && r[1] {
				resurrected++
			}
		}
		t.Logf("MEASURED %s n=%d: answer lost=%d, closer over outcome=%d, two closers wrote %v, create-only both/none=%d, "+
			"mark resurrected after sweep=%d", name, n, lost, over, closers, both, resurrected)
		if lost != 0 || over != 0 || closers[0] != 0 || closers[2] != 0 || both != 0 {
			t.Errorf("%s: DEFECT", name)
		}
	}
}

// A call that does not answer: after PerformTimeout the request is answered "did not answer" (refused), its row is
// cleared by the console, and the holder's next sweep deletes the mark — if the target never answers, the request
// never had an outcome in its mark. Expected by ADR-0054 ("итог есть у каждой просьбы"): an outcome in the mark.
func TestProbeTimeoutLeavesTheMarkWithoutOutcome(t *testing.T) {
	defer func(g, h time.Duration, to float64) { p.PerformGrace, p.RequestsHold, p.PerformTimeout = g, h, to }(p.PerformGrace, p.RequestsHold, p.PerformTimeout)
	p.PerformGrace, p.RequestsHold, p.PerformTimeout = 30*time.Millisecond, 100*time.Millisecond, 10
	b := newServerBed(t, "c1")
	release := make(chan struct{})
	defer close(release)
	b.h.hang["c1"] = release
	b.file("r1", "c1", nil)
	b.look()
	*b.clock += 10
	done := b.look()
	d := outcomeOf(done, "r1")
	m := b.mark("r1")
	t.Logf("MEASURED answer=%v mark after timeout=%v (outcome=%v)", d, m, m["outcome"])
	// the console clears the answered row (fetched), the holder sweeps marks of gone rows
	b.vars.Delete(testsubSpec.Sub().RequestKey("r1"), p.NoCAS)
	*b.clock += p.MarkSweep + 1
	b.look()
	t.Logf("MEASURED mark after the row was cleared and the sweep ran=%v", b.mark("r1"))
	if m["outcome"] == nil {
		t.Errorf("DEFECT: answered %q but the mark has no outcome; then swept", p.Str(d["error"]))
	}
}

// A unit moved mid-flight: holder A's call is in flight (begun mark), holder B now holds the unit and answers the
// request `unknown`; A's call then returns `performed`. Expected per ADR-0054: the mark ends `performed` (holder wins).
// Measured: what each counts — one request counted in two outcomes.
func TestProbeMovedUnitCountsOneRequestTwice(t *testing.T) {
	defer func(g, h time.Duration, to float64) { p.PerformGrace, p.RequestsHold, p.PerformTimeout = g, h, to }(p.PerformGrace, p.RequestsHold, p.PerformTimeout)
	p.PerformGrace, p.RequestsHold, p.PerformTimeout = 30*time.Millisecond, 100*time.Millisecond, 10
	a := newServerBed(t, "c1")
	release := make(chan struct{})
	a.h.hang["c1"] = release
	a.file("r1", "c1", nil)
	a.look()
	now := func() float64 { return *a.clock }
	if _, err := a.vars.Put(testsubSpec.Sub().Assignment("w-2"), p.Assignment{Worker: "w-2", Units: []string{"c1"}, Rev: 2}.ToItems(), p.NoCAS); err != nil {
		t.Fatal(err)
	}
	w2 := p.NewWorker(testsubSpec.Sub(), a.vars, a.objects, p.WorkerOptions{Name: "w-2", Clock: now, Wall: now})
	w2.ResourceRoot = t.TempDir()
	w2.Assignment()
	h2 := newFakeHolder("c1")
	s2 := p.NewRequestServer(w2, h2)
	doneB, err := s2.Look(*a.clock)
	t.Logf("MEASURED B's look=%v err=%v B calls=%d", doneB, err, h2.callCount())
	close(release)
	time.Sleep(50 * time.Millisecond)
	a.look()
	t.Logf("MEASURED A counts=%v B counts=%v final mark=%v", a.s.Said()["command_counts"], s2.Said()["command_counts"], a.mark("r1"))
}

// The reaper and a garbled mark: a request past its deadline + ReapAfter whose mark does not parse, no holder of the unit.
// Expected: the row ends (unknown or expired). Measured: whether it stands after many reaper turns.
func TestProbeGarbledMarkKeepsTheRowForEver(t *testing.T) {
	b := bedOf(t, testsubSpec, map[string]any{"name": "c1"})
	sub := p.Subsystem{Name: "testsub"}
	for _, id := range []string{"garbled", "parsed"} {
		if code, out := b.post(t, "anna", id, map[string]any{"unit": "testsub/c1", "add": 1}); code != 202 {
			t.Fatalf("%s: %d %v", id, code, out)
		}
	}
	b.box.Objects.Put(sub.CommandKey("garbled"), []byte(`{"instance":"I-old","slot":"w-1"`)) // torn
	raw, _ := json.Marshal(map[string]any{"slot": "w-1", "instance": "I-old"})
	b.box.Objects.Put(sub.CommandKey("parsed"), raw) // no slot row: holder gone
	for i := 0; i < 5; i++ {
		b.box.Wall.Advance(3600)
		b.c.ClearRequests(true)
	}
	t.Logf("MEASURED after 5 h of reaper turns: garbled row stands=%v, parsed (holder gone) row stands=%v", b.has("testsub", "garbled"), b.has("testsub", "parsed"))
	if b.has("testsub", "garbled") {
		t.Errorf("DEFECT: a request whose mark does not parse is never ended by the reaper")
	}
}

// The ttl path of the reaper (a row with no deadline in a family with `ttl`): does it read the mark first, as the deadline
// path does? Rows: one its holder answered `refused` (mark with outcome, heartbeat lost), one a holder still holding its
// slot began (mark, no outcome). Expected (ADR-0054, the course's _close; product commit 1315207 on console-host):
// the answered one cleared uncounted, the begun one left to its holder. Measured: what the snapshot does.
func TestProbeTTLPathReadsTheMark(t *testing.T) {
	src := readTestsub2(t)
	for _, cut := range []string{"  valid_for: 30\n", "  most_valid: 600\n"} {
		src = strings.Replace(src, cut, "", 1)
	}
	src = strings.Replace(src, "    properties: {unit: {type: string}, add: {type: integer}, valid_until: {type: number}}",
		"    properties: {unit: {type: string}, add: {type: integer}, action: {type: string}}", 1)
	spec, err := strictFrom(t, src)
	if err != nil {
		t.Fatal(err)
	}
	b := bedOf(t, spec, map[string]any{"of": "c1"})
	sub := p.Subsystem{Name: "testsub2"}
	for i, id := range []string{"a1", "b1"} {
		if code, out := b.post(t, "anna", id, map[string]any{"unit": "testsub2/1", "add": i + 1}); code != 202 {
			t.Fatalf("%d %v", code, out)
		}
	}
	keys, _ := b.box.Vars.List(sub.RequestsPrefix())
	if len(keys) < 2 {
		t.Fatalf("rows: %v", keys)
	}
	var rids []string
	for _, k := range keys {
		if r := k[strings.LastIndexByte(k, '/')+1:]; !strings.HasPrefix(r, "asks-") {
			rids = append(rids, r)
		}
	}
	answered, begun := rids[0], rids[1]
	b.box.Objects.Put(sub.CommandKey(answered), []byte(`{"instance":"I","outcome":"refused","slot":"w-1","error":"x"}`))
	b.box.Objects.Put(sub.CommandKey(begun), []byte(`{"instance":"I","slot":"w-1"}`))
	b.box.Vars.Put(sub.SlotKey("w-1"), p.Items{"holder": "I"}, p.NoCAS) // the beginner still holds its name
	e0, u0 := p.RequestsEnded("testsub2")
	b.box.Wall.Advance(3602)
	b.c.ClearRequests(true)
	e, u := p.RequestsEnded("testsub2")
	raw, _ := b.box.Objects.Get(sub.CommandKey(begun))
	t.Logf("MEASURED ttl path: answered row stands=%v, begun row (holder there) stands=%v, expired +%d, unknown +%d, begun mark=%s",
		b.has("testsub2", answered), b.has("testsub2", begun), e-e0, u-u0, raw)
	if !b.has("testsub2", begun) || e-e0 != 0 {
		t.Errorf("DEFECT: the ttl path ends a begun request and counts expired without reading the mark")
	}
}

var _ = errors.New
