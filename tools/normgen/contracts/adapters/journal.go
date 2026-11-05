// The kit's adapter of common/journal over the package contracts (tools/normgen/contracts; ADR-0125 addendum (5)).
// YOURS from here like any adapter: the kit puts it once instead of the stub.

package vectoradapter

import (
	"encoding/json"
	"strconv"

	"kitmodule/internal/contracts"
)

// Journal — common/journal by table: bucket.tsv → {ids, torn, garbled, duplicate}; append.tsv → the bucket after the
// write or "@refuse"; names.tsv → the component, "@skip", or write/keep/refuse; years.tsv → the bucket name or "@refuse".
func Journal(table string, cells map[string]string, files map[string][]byte) Answer {
	str := func(k string) (string, bool) {
		var s string
		return s, json.Unmarshal([]byte(cells[k]), &s) == nil
	}
	switch table {
	case "bucket.tsv":
		f, ok := str("file")
		if !ok {
			return Answer{Code: 2}
		}
		r := contracts.ReadBucket([]byte(f))
		ids := []any{}
		for _, id := range r.IDs {
			ids = append(ids, id)
		}
		return Answer{Value: map[string]any{"ids": ids, "torn": r.Torn, "garbled": r.Garbled, "duplicate": r.Duplicate}}
	case "append.tsv":
		f, ok1 := str("file")
		l, ok2 := str("line")
		if !ok1 || !ok2 {
			return Answer{Code: 2}
		}
		out, err := contracts.AppendLine(f, l)
		if err != nil {
			return Answer{Value: "@refuse"}
		}
		return Answer{Value: out}
	case "years.tsv":
		t, err := strconv.ParseFloat(cells["t"], 64)
		if err != nil {
			return Answer{Code: 2}
		}
		name, err := contracts.BucketName(t)
		if err != nil {
			return Answer{Value: "@refuse"}
		}
		return Answer{Value: name}
	case "names.tsv":
		var in struct {
			Entry     *string `json:"entry"`
			Suffix    string  `json:"suffix"`
			NameFile  *string `json:"name_file"`
			Component *string `json:"component"`
		}
		if json.Unmarshal([]byte(cells["input"]), &in) != nil {
			return Answer{Code: 2}
		}
		if in.Component != nil {
			return Answer{Value: contracts.WriteHashedName(*in.Component, in.NameFile)}
		}
		if in.Entry == nil {
			return Answer{Code: 2}
		}
		c, ok := contracts.ReadHashedName(*in.Entry, in.Suffix, in.NameFile)
		if !ok {
			return Answer{Value: "@skip"}
		}
		return Answer{Value: c}
	}
	return Answer{Code: 2}
}
