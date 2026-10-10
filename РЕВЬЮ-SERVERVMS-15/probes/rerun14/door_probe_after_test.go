// RERUN-15 COPY of РЕВЬЮ-SERVERVMS-14/probes/door/go/door_probe_test.go for product c86571d: p.LedgerName/p.LedgerPrefix are gone
// (ledgers moved to <sub>/asked/<16hex>, Subsystem.AskedKey, ADR-0060). Replaced: ledger key = testsub2Spec.Sub().AskedKey("anna"),
// rid case "ledger_name" = the basename of that key; the 400-claim check on that rid is dropped (no such claim any more).
package w2cplatform_test

// Probe (r14 door, PRODUCT): the request door (SpecConsole.FileRequest / PrepareRequest / countAsk / ClearRequests) —
// same rid under another person and body, rid edge cases (unicode length, backslash, U+2028, U+0085), a garbled request
// row named in a person's ledger, the ledger row after ttl. Run against the product tree without touching it:
//   go test -overlay overlay.json -run TestR14Door -v ./vmsworker/w2cplatform/
// (overlay.json maps vmsworker/w2cplatform/zz_r14_door_probe_test.go to this file). It logs what it measures; it fails
// only where the product claims a behaviour: rid "asks-…" refused (400), a garbled own row not a 500.
// Expected (correct): cross-person same rid -> 409; measured 202 with the other's row = defect (same as the course).

import (
	"bytes"
	"encoding/json"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"vmsworker.local/vmsworker/testbox"
	p "vmsworker.local/vmsworker/w2cplatform"
)

func r14Bed(t *testing.T, key bool) (*testbox.Box, *p.SpecConsole, func(user, idem string, body map[string]any) (int, map[string]any)) {
	t.Helper()
	spec := *testsub2Spec
	req := *spec.Requests
	sch, err := p.LoadJSONSchema(map[string]any{"type": "object", "required": []any{"unit", "add"}, "additionalProperties": false,
		"properties": map[string]any{"unit": map[string]any{"type": "string"}, "add": map[string]any{"type": "integer"},
			"valid_until": map[string]any{"type": "number"}, "id": map[string]any{"type": "string"},
			"note": map[string]any{"type": "string", "maxLength": 32}}}, "probe")
	if err != nil {
		t.Fatal(err)
	}
	req.Schema = sch
	if !key {
		req.Key = ""
	}
	spec.Requests = &req
	box := testbox.NewBox()
	ctl := p.NewSpecController(&spec, box.Vars, box.Objects, 50, box.Wall.Now, "cluster-a")
	c := p.NewSpecConsole(ctl, p.ConsoleOptions{LostAfter: 45, Wall: box.Wall.Now})
	for i := 0; i < 2; i++ {
		if r := c.Create(map[string]any{"of": "c1"}); r.Status >= 300 {
			t.Fatalf("a tally: %+v", r)
		}
	}
	h := c.Handler()
	post := func(user, idem string, body map[string]any) (int, map[string]any) {
		raw, _ := json.Marshal(body)
		r := httptest.NewRequest("POST", "/requests", bytes.NewReader(raw))
		r.Header.Set("Idempotency-Key", idem)
		r.Header.Set("X-User", user)
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, r)
		var out map[string]any
		json.Unmarshal(rec.Body.Bytes(), &out)
		return rec.Code, out
	}
	return box, c, post
}

func TestR14DoorCrossPersonSameRid(t *testing.T) {
	_, _, post := r14Bed(t, false)
	a, _ := post("anna", "k1", map[string]any{"unit": "testsub2/1", "add": 1, "id": "r1", "note": "anna's"})
	b, out := post("boris", "k2", map[string]any{"unit": "testsub2/2", "add": 9, "id": "r1", "note": "boris's"})
	t.Logf("cross_person_same_rid: anna %d, boris %d, boris was told %v", a, b, out["queued"])
}

func TestR14DoorRidEdges(t *testing.T) {
	_, _, post := r14Bed(t, false)
	for _, c := range []struct{ name, rid string }{{"cyr150", strings.Repeat("я", 150)}, {"cyr100", strings.Repeat("я", 100)},
		{"backslash", `a\b`}, {"u2028", "a b"}, {"u0085", "a\u0085b"}, {"bidi", "a‮b"}, {"dotdot", ".."}, {"slash", "a/b"},
		{"ledger_name", ledgerBase(testsub2Spec.Sub().AskedKey("anna"))}} {
		code, out := post("anna", "e-"+c.name, map[string]any{"unit": "testsub2/1", "add": 1, "id": c.rid})
		t.Logf("rid_%s: %d %v", c.name, code, out["error"])
		if false && c.name == "ledger_name" && code != 400 {
			t.Errorf("the product claims a rid asks-… is refused: %d", code)
		}
	}
	code, out := post("anna", "long", map[string]any{"unit": "testsub2/1", "add": 1, "note": strings.Repeat("x", 100000)})
	t.Logf("note_100000: %d %v", code, out["fault"])
}

func TestR14DoorGarbledOwnRowInLedger(t *testing.T) {
	box, _, post := r14Bed(t, false)
	if code, out := post("vera", "v1", map[string]any{"unit": "testsub2/1", "add": 1, "id": "own-1"}); code != 202 {
		t.Fatalf("%d %v", code, out)
	}
	// the request row does not read: written as no row of the store's form
	var files []string
	filepath.WalkDir(box.Root, func(path string, d os.DirEntry, err error) error {
		if err == nil && !d.IsDir() && strings.Contains(filepath.Base(path), "own-1") {
			files = append(files, path)
		}
		return nil
	})
	if len(files) != 1 {
		t.Fatalf("the row's file: %v", files)
	}
	os.WriteFile(files[0], []byte("{torn"), 0o644)
	if _, _, err := box.Vars.Get("testsub2/requests/own-1"); err == nil {
		t.Fatal("the row still reads")
	}
	box.Wall.Advance(31)
	code, out := post("vera", "v2", map[string]any{"unit": "testsub2/1", "add": 1, "id": "own-2"})
	t.Logf("garbled_own_row_in_ledger: %d %v", code, out["error"])
}

func TestR14DoorLedgerAfterTTL(t *testing.T) {
	box, c, post := r14Bed(t, true)
	post("anna", "a1", map[string]any{"unit": "testsub2/1", "add": 1})
	name := testsub2Spec.Sub().AskedKey("anna")
	before, _, _ := box.Vars.Get(name)
	box.Wall.Advance(testsub2Spec.Requests.TTL + 120)
	c.ClearRequests(true)
	after, _, _ := box.Vars.Get(name)
	t.Logf("ledger_after_ttl_sweep: before %d fields, after %d fields (0 = removed)", len(before), len(after))
}

func TestR14DoorIdempotencyKey(t *testing.T) {
	_, _, post := r14Bed(t, false)
	body := map[string]any{"unit": "testsub2/1", "add": 2, "id": "r2"}
	c1, o1 := post("anna", "K-1", body)
	c2, o2 := post("anna", "K-1", body)
	c3, o3 := post("anna", "K-1", map[string]any{"unit": "testsub2/1", "add": 3, "id": "r2"})
	c4, o4 := post("boris", "K-1", body)
	same, _ := json.Marshal(o1)
	again, _ := json.Marshal(o2)
	t.Logf("idem_same: %d %d equal=%v; idem_other_body: %d %v; idem_other_user: %d %v", c1, c2, string(same) == string(again),
		c3, o3["error"], c4, o4["error"])
}

func ledgerBase(key string) string { return key[strings.LastIndexByte(key, '/')+1:] }
