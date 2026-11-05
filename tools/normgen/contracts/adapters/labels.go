// The kit's adapter of common/labels over the package contracts (tools/normgen/contracts; ADR-0125 addendum (5)).
// YOURS from here like any adapter: the kit puts it once instead of the stub.

package vectoradapter

import (
	"encoding/json"

	"kitmodule/internal/contracts"
)

func labelList(xs []string) []any {
	out := make([]any, 0, len(xs))
	for _, x := range xs {
		out = append(out, x)
	}
	return out
}

// Labels — common/labels by op: label → "ok" | "@refuse"; set_write → the text; text_read, env_labels → the labels.
func Labels(table string, cells map[string]string, files map[string][]byte) Answer {
	refuse := Answer{Value: "@refuse"}
	switch cells["op"] {
	case "label":
		var s string
		if json.Unmarshal([]byte(cells["input"]), &s) != nil {
			return Answer{Code: 2}
		}
		if contracts.ValidLabel(s) {
			return Answer{Value: "ok"}
		}
		return refuse
	case "set_write":
		var in []string
		if json.Unmarshal([]byte(cells["input"]), &in) != nil {
			return Answer{Code: 2}
		}
		t, err := contracts.LabelSetWrite(in)
		if err != nil {
			return refuse
		}
		return Answer{Value: t}
	case "text_read", "env_labels":
		var s string
		if json.Unmarshal([]byte(cells["input"]), &s) != nil {
			return Answer{Code: 2}
		}
		read := contracts.LabelTextRead
		if cells["op"] == "env_labels" {
			read = contracts.EnvLabels
		}
		out, err := read(s)
		if err != nil {
			return refuse
		}
		return Answer{Value: labelList(out)}
	}
	return Answer{Code: 2}
}
