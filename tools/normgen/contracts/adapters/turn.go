// The kit's adapter of common/turn over the package contracts (tools/normgen/contracts; ADR-0125 addendum (5)).
// YOURS from here like any adapter: the kit puts it once instead of the stub.

package vectoradapter

import (
	"encoding/json"

	"kitmodule/internal/contracts"
)

// Turn — cells input {kind, turn, me, steps} → the actions, one per event.
func Turn(table string, cells map[string]string, files map[string][]byte) Answer {
	var in struct {
		Kind  string            `json:"kind"`
		Turn  string            `json:"turn"`
		Me    map[string]string `json:"me"`
		Steps []map[string]json.RawMessage
	}
	if err := json.Unmarshal([]byte(cells["input"]), &in); err != nil {
		return Answer{Code: 2, Value: err.Error()}
	}
	t := &contracts.Turn{Kind: in.Kind, Me: in.Me["manifest_rev"]}
	if in.Kind == "signer" {
		t.Me = in.Me["holder"]
	}
	str := func(r json.RawMessage) string {
		var s string
		if json.Unmarshal(r, &s) == nil {
			return s
		}
		return string(r)
	}
	var out []any
	for _, st := range in.Steps {
		var a contracts.TurnAction
		switch {
		case st["read"] != nil:
			r := contracts.TurnRead{Version: str(st["version"])}
			_ = json.Unmarshal(st["seen"], &r.Seen)
			if s := str(st["read"]); s == "@unreadable" {
				r.Unreadable = true
			} else if string(st["read"]) != "null" {
				if json.Unmarshal(st["read"], &r.Row) != nil {
					return Answer{Code: 2, Value: "read: not a row"}
				}
				if r.Row["holder"] == "@same" { // substitute before the ordinary algorithm, never in its output
					r.Row["holder"] = t.Mark()
				}
			}
			a = t.Read(r)
		case st["reply"] != nil:
			a = t.Reply(str(st["reply"]), str(st["version"]))
		case st["renew"] != nil:
			a = t.Renew()
		case st["target"] != nil:
			var age float64
			_ = json.Unmarshal(st["age"], &age)
			a = t.Target(age)
		case st["target_reply"] != nil:
			a = t.TargetReply(str(st["target_reply"]))
		case st["end"] != nil:
			a = t.End()
		default:
			return Answer{Code: 2, Value: "an unknown event"}
		}
		out = append(out, turnAction(in.Turn, a))
	}
	return Answer{Value: out}
}

func turnAction(key string, a contracts.TurnAction) any {
	version := func(v string) any {
		if v == "" {
			return ""
		}
		return json.Number(v)
	}
	switch {
	case a.Write != nil:
		w := map[string]any{}
		for k, v := range a.Write {
			w[k] = v
		}
		return map[string]any{"write": w, "cas": version(a.Cas)}
	case a.Word != "":
		return a.Word
	}
	return map[string]any{"guard": map[string]any{"key": key, "index": version(a.Guard)}}
}
