// The kit's adapter of common/object-client over the package contracts (tools/normgen/contracts; ADR-0125 addendum
// (5)). YOURS from here like any adapter: the kit puts it once instead of the stub.

package vectoradapter

import (
	"encoding/json"

	"kitmodule/internal/contracts"
)

// ObjectClient — address.tsv: {OBJECTS, PLATFORM_DIR, SERVER_NAME?, door?} → {kind, dir[, door][, resource]} or code
// 2; read.tsv: {reply} → "object" | "absent" | "unknown" | "refused".
func ObjectClient(table string, cells map[string]string, files map[string][]byte) Answer {
	if table == "read.tsv" {
		var in struct {
			Reply json.RawMessage `json:"reply"`
		}
		if err := json.Unmarshal([]byte(cells["input"]), &in); err != nil {
			return Answer{Code: 2, Value: err.Error()}
		}
		var word string
		if json.Unmarshal(in.Reply, &word) == nil {
			return Answer{Value: contracts.ObjectOutcome(nil)}
		}
		var r struct {
			Status  int     `json:"status"`
			Missing *string `json:"X-Missing"`
		}
		if err := json.Unmarshal(in.Reply, &r); err != nil {
			return Answer{Code: 2, Value: err.Error()}
		}
		return Answer{Value: contracts.ObjectOutcome(&contracts.ObjectReply{Status: r.Status, Missing: r.Missing})}
	}
	var in struct {
		OBJECTS     string          `json:"OBJECTS"`
		PLATFORMDIR string          `json:"PLATFORM_DIR"`
		SERVERNAME  string          `json:"SERVER_NAME"`
		Door        json.RawMessage `json:"door"`
	}
	if err := json.Unmarshal([]byte(cells["input"]), &in); err != nil {
		return Answer{Code: 2, Value: err.Error()}
	}
	addr, err := contracts.ParseObjects(in.OBJECTS, in.PLATFORMDIR, in.SERVERNAME)
	if err != nil {
		return Answer{Code: 2, Value: "OBJECTS: a start refusal"}
	}
	out := map[string]any{"kind": addr.Kind, "dir": addr.Dir}
	if addr.Kind == "cluster" {
		resource := addr.Resource
		if addr.Door != "" {
			var d contracts.DoorRead
			var word string
			if json.Unmarshal(in.Door, &word) == nil {
				d.Unreadable, d.NoReply = word == "@unreadable", word == "@none"
			} else {
				_ = json.Unmarshal(in.Door, &d.Row)
			}
			out["door"] = addr.Door
			if resource = contracts.ReadDoor(d); resource == "" {
				resource = "@unknown"
			}
		}
		out["resource"] = resource
	}
	return Answer{Value: out}
}
