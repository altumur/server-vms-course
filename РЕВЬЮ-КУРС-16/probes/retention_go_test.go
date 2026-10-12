package w2cplatform_test

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
	p "vmsworker.local/vmsworker/w2cplatform"
)

// Independent evidence: retain the real console mark while its events remain.
// This file is copied only to a git-archive snapshot.
func TestReview16RetentionEvidence(t *testing.T) {
	cases := []struct {
		name, days    string
		mirror, stale bool
	}{
		{"valid-common", "2200", false, false},
		{"invalid-common", "broken", false, false},
		{"zero-common", "0", false, false},
		{"mirror-only-valid", "2200", true, false},
		{"stale-unit-rows", "2200", false, true},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			root := t.TempDir()
			vars := p.NewMemVariables()
			for _, family := range []string{"retention", "alarms_retention"} {
				if _, err := vars.Put("other/"+family, p.Items{"days": c.days}, p.NoCAS); err != nil {
					t.Fatal(err)
				}
				if c.stale {
					if _, err := vars.Put("other/"+family+"/7", p.Items{"days": "0"}, p.NoCAS); err != nil {
						t.Fatal(err)
					}
				}
			}
			objects, err := p.NewFsObjectStore(filepath.Join(root, "objects"))
			if err != nil {
				t.Fatal(err)
			}
			tree := filepath.Join(root, "events")
			eventTree := tree
			if c.mirror {
				eventTree = filepath.Join(tree, p.MirrorDir, "peer-1")
			}
			now := 1757500000.0
			at := now - 1500*86400.0
			log := p.NewEventLog(eventTree, "other", "7", 1, 600)
			event, err := log.Append(at, "observation", p.Observation, map[string]any{})
			if err != nil {
				t.Fatal(err)
			}
			alarm, err := log.Append(at, "alarm", p.Alarm, map[string]any{})
			if err != nil {
				t.Fatal(err)
			}
			mark, err := p.NewEventLog(tree, p.ConsoleMarks, "operator-1", 1, 600).Append(at, "mark", p.Observation, map[string]any{"of": "other/7", "user": "anna", "note": "Проверено оператором"})
			if err != nil {
				t.Fatal(err)
			}
			res := p.NewResource(tree, "srv-a", "http://srv-a", vars, objects, 600, func() float64 { return now }, nil)
			res.Journal = p.NewJournal(tree, "resource", 600, func() float64 { return now })
			removed := res.Retain()
			exists := func(path string) bool { _, e := os.Stat(path); return e == nil }
			facts := map[string]any{"scenario": c.name, "removed": removed, "events_left": exists(event), "alarms_left": exists(alarm), "operator_record_left": exists(mark)}
			raw, _ := json.Marshal(facts)
			t.Log(string(raw))
			if exists(alarm) && !exists(mark) {
				t.Errorf("operator record deleted while alarm remains")
			}
		})
	}
}

type review16Writer struct {
	p.Variables
	write func()
}

func (v *review16Writer) Get(path string) (p.Items, p.Index, error) {
	if v.write != nil {
		f := v.write
		v.write = nil
		f()
	}
	return v.Variables.Get(path)
}

// A real writer creates a fresh unit after the resource has inventoried the existing buckets.
func TestReview16ConcurrentUnitEvidence(t *testing.T) {
	root := t.TempDir()
	tree := filepath.Join(root, "events")
	now := 1757500000.0
	vars := p.NewMemVariables()
	if _, err := vars.Put("other/retention", p.Items{"days": "1"}, p.NoCAS); err != nil {
		t.Fatal(err)
	}
	old, err := p.NewEventLog(tree, "other", "7", 1, 600).Append(now-5*86400, "observation", p.Observation, nil)
	if err != nil {
		t.Fatal(err)
	}
	writer := &review16Writer{Variables: vars}
	writer.write = func() {
		if _, err := p.NewEventLog(tree, "other", "8", 1, 600).Append(now, "observation", p.Observation, nil); err != nil {
			t.Fatal(err)
		}
	}
	objects, err := p.NewFsObjectStore(filepath.Join(root, "objects"))
	if err != nil {
		t.Fatal(err)
	}
	res := p.NewResource(tree, "srv-a", "http://srv-a", writer, objects, 600, func() float64 { return now }, nil)
	res.Journal = p.NewJournal(tree, "resource", 600, func() float64 { return now })
	removed := res.Retain()
	journal := []map[string]any{}
	err = filepath.WalkDir(filepath.Join(tree, p.AuditSubsystem), func(path string, d os.DirEntry, e error) error {
		if e != nil {
			return e
		}
		if d.IsDir() || !strings.HasSuffix(path, ".events.jsonl") {
			return nil
		}
		raw, e := os.ReadFile(path)
		if e != nil {
			return e
		}
		for _, line := range strings.Split(strings.TrimSpace(string(raw)), "\n") {
			var row map[string]any
			if e := json.Unmarshal([]byte(line), &row); e != nil {
				return e
			}
			journal = append(journal, row)
		}
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
	_, e := os.Stat(old)
	facts := map[string]any{"error": nil, "removed": removed, "old_bucket_still_exists": e == nil, "journal_records": journal}
	raw, _ := json.Marshal(facts)
	t.Log(string(raw))
	if removed != 1 || e == nil || len(journal) != 1 {
		t.Errorf("retention failed to finish and journal the removed bucket")
	}
}
