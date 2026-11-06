// Shared policy runtime checks. No SDK or external IO is used by the policies.
package workerpolicy

import (
	"encoding/json"
	"math"
	"sync"
	"testing"
)

func TestStrictSemanticJSON(t *testing.T) {
	bad := [][]byte{
		[]byte(`{"a":1,"a":2}`), []byte(`{"x":{"a":1,"a":2}}`),
		[]byte(`"\ud800"`), []byte(`"\udfff"`), []byte(`{"\ud800":0}`),
		[]byte(`"\ud800\u0041"`), []byte(`"\udc00\ud800"`), []byte(`"\uqqqq"`),
		[]byte(`NaN`), []byte(`Infinity`), []byte(`1e400`), []byte(`true false`),
		[]byte(`{"a":1,}`), []byte(`[]x`), []byte{}, {'"', 0xff, '"'},
	}
	for _, raw := range bad {
		if _, e := DecodeJSON(raw); e == nil {
			t.Errorf("accepted invalid JSON %q", raw)
		}
	}
	for _, raw := range []string{`"\ud83d\ude00"`, `"\\ud800"`, `"a\"b"`, `{"a":"\u0000;\u2028"}`, `9007199254740993`, `-9223372036854775808`, `[]`, `{}`} {
		if _, e := DecodeJSON([]byte(raw)); e != nil {
			t.Errorf("rejected %s: %v", raw, e)
		}
	}
}

func TestIndependentRunsAndDetachedObservations(t *testing.T) {
	raw, e := Definition("contender-writer")
	if e != nil {
		t.Fatal(e)
	}
	p, e := Compile(raw)
	if e != nil {
		t.Fatal(e)
	}
	var wg sync.WaitGroup
	for i := 0; i < 24; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			r, e := p.New([]byte(`{}`), 0)
			if e != nil {
				t.Error(e)
				return
			}
			o, e := r.Step(1, "observe", []byte(`{"withdrawn":false,"foreign":false,"due":true,"wall":100}`))
			if e != nil {
				t.Error(e)
				return
			}
			o.Vars["since"] = float64(-999)
			o.IO[0].Args[0] = "modified"
			fresh := r.Snapshot()
			if fresh.Vars["since"] != float64(100) || fresh.IO[0].Args[0] != "waiting" {
				t.Error("snapshot aliases run")
			}
			for n := 0; n < 20; n++ {
				var inner sync.WaitGroup
				inner.Add(2)
				go func() { defer inner.Done(); r.Snapshot() }()
				go func() {
					defer inner.Done()
					if _, e := r.Step(1, "lost", []byte(`{}`)); e != nil {
						t.Error(e)
					}
				}()
				inner.Wait()
			}
		}()
	}
	wg.Wait()
}

func TestBadStepDoesNotAdvance(t *testing.T) {
	r, e := Open("token-cache", []byte(`{}`), 0)
	if e != nil {
		t.Fatal(e)
	}
	for _, raw := range []string{`{"day":1,"day":2}`, `{"day":1.0}`, `{"day":1e0}`, `{"day":9223372036854775808}`, `{"day":true}`} {
		if _, e := r.Step(100, "demand", []byte(raw)); e == nil {
			t.Errorf("accepted %s", raw)
		}
	}
	for _, at := range []float64{-1, math.Inf(1), math.NaN()} {
		if _, e := r.Step(at, "advance", nil); e == nil {
			t.Errorf("accepted time %v", at)
		}
	}
	if _, e := r.Step(1, "loaded", []byte(`{"opened":false,"handle":"","jti":""}`)); e != nil {
		t.Fatal("bad step advanced clock:", e)
	}
	if _, e := r.Step(2, "demand", []byte(`{"day":9007199254740993}`)); e != nil {
		t.Fatal(e)
	}
	b, e := json.Marshal(r.Snapshot())
	if e != nil {
		t.Fatal(e)
	}
	if len(b) == 0 {
		t.Fatal("empty observation")
	}
}
