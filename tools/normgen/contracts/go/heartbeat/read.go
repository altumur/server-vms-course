// Heartbeat reading by the two foreign families and their outcomes (common/contracts/observation.md).
package heartbeat

import (
	"encoding/json"
	"sort"
	"strconv"
	"strings"
)

// ResourceResult — whether a resource heartbeat is readable, and its field outcomes in family order.
type ResourceResult struct {
	Readable bool
	Fields   []string
}

// WorkerResult — GET /{rows} skips malformed status elements; the other readers reject the whole heartbeat.
// Rows is "unreadable" or RowItems. Fields are stated only when Others is "readable".
type WorkerResult struct {
	Rows   any      `json:"rows"`
	Others string   `json:"others"`
	Fields []string `json:"fields"`
}

type RowItems struct {
	Skip []int `json:"skip"`
}

func init() {
	// Family.Matches caches its key regexp; initialize it before concurrent reads.
	Heartbeats.Matches("testsub/heartbeats/w-1")
	ResourcesHeartbeat.Matches("platform/resources/srv-a/heartbeat")
}

// effects keeps the outcome for each refusal separately: a low-priority-number field outcome must not hide
// an unreadable whole object or a malformed status element at a different path.
func effects(f *Family, paths []string) map[string]bool {
	out := map[string]bool{}
	for _, path := range paths {
		for _, effect := range f.OutcomesFor([]string{path}, "console") {
			out[effect] = true
		}
	}
	return out
}

func fields(f *Family, active map[string]bool) []string {
	out := []string{}
	for _, o := range f.Outcomes {
		if o.Unit == unitField && active[o.Path] {
			out = append(out, strings.TrimPrefix(o.Path, "/"))
		}
	}
	return out
}

// ReadResource — the resource heartbeat form, without consulting observation history or a clock.
func ReadResource(key string, text []byte) ResourceResult {
	f := ResourcesHeartbeat
	active := effects(f, f.JudgeText(key, text, Reader).Paths)
	return ResourceResult{Readable: !active[""], Fields: fields(f, active)}
}

// ReadWorker — the worker form and worker == the name in its key (P/03.4 N1.1). A whole-object error precedes
// element handling; a malformed status list is a whole-object error, rather than one skipped element.
func ReadWorker(key string, text []byte) WorkerResult {
	unreadable := WorkerResult{Rows: "unreadable", Others: "unreadable", Fields: []string{}}
	f := Heartbeats
	paths := f.JudgeText(key, text, Reader).Paths
	var obj struct {
		Worker string            `json:"worker"`
		Status []json.RawMessage `json:"status"`
	}
	if json.Unmarshal(text, &obj) != nil || obj.Worker != key[strings.LastIndex(key, "/")+1:] {
		return unreadable
	}
	active := effects(f, paths)
	if active[""] {
		return unreadable
	}
	bad := map[int]bool{}
	for _, path := range paths {
		if path != "/status" && !strings.HasPrefix(path, "/status/") {
			continue
		}
		parts := strings.Split(path, "/")
		if len(parts) < 3 {
			return unreadable
		}
		i, err := strconv.Atoi(parts[2])
		if err != nil || i < 0 || i >= len(obj.Status) {
			return unreadable
		}
		bad[i] = true
	}
	skip := []int{}
	for i := range bad {
		skip = append(skip, i)
	}
	sort.Ints(skip)
	out := WorkerResult{Rows: RowItems{Skip: skip}, Others: "readable", Fields: fields(f, active)}
	if len(skip) != 0 {
		out.Others, out.Fields = "unreadable", []string{}
	}
	return out
}
