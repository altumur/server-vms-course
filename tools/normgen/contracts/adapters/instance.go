// The kit's adapter of common/instance over the package contracts (tools/normgen/contracts; ADR-0125 addendum (5)).
// YOURS from here like any adapter: the kit puts it once instead of the stub.

package vectoradapter

import (
	"encoding/json"

	"kitmodule/internal/contracts"
)

// Instance — common/instance: box.tsv → {box, source} or "@refuse"; cases.tsv → {instance} or "@refuse" (code 0).
func Instance(table string, cells map[string]string, files map[string][]byte) Answer {
	var in map[string]any
	if json.Unmarshal([]byte(cells["input"]), &in) != nil {
		return Answer{Code: 2}
	}
	str := func(k string) (string, bool) { v, ok := in[k].(string); return v, ok }
	if table == "cases.tsv" {
		id, _ := str("INSTANCE_ID")
		inst, err := contracts.GivenInstance(id)
		if err != nil {
			return Answer{Value: "@refuse"}
		}
		return Answer{Value: map[string]any{"instance": inst}}
	}
	if id, ok := str("INSTANCE_ID"); ok && id != "" {
		if _, err := contracts.GivenInstance(id); err != nil {
			return Answer{Value: "@refuse"}
		}
	}
	src := contracts.BoxSources{}
	if b, ok := str("BOX_ID"); ok {
		src.BoxID = &b
	}
	m, _ := str("machine_id")
	src.Missing, src.Error, src.MachineID = m == "@missing", m == "@error", m
	src.Hostname, _ = str("hostname")
	box, source, err := contracts.ResolveBox(src)
	if err != nil {
		return Answer{Value: "@refuse"}
	}
	return Answer{Value: map[string]any{"box": box, "source": source}}
}
