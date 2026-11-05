// The kit's adapter of common/events-merge over the package contracts. YOURS from here.
package vectoradapter

import "kitmodule/internal/contracts"

func EventsMerge(table string, cells map[string]string, files map[string][]byte) Answer {
	var value map[string]any
	var err error
	switch table {
	case "cases.tsv":
		value, err = contracts.MergeEvents([]byte(cells["input"]))
	case "resource.tsv":
		value, err = contracts.FilterResourceEvents([]byte(cells["input"]))
	default:
		return Answer{Code: 2}
	}
	if err != nil {
		return Answer{Code: 2}
	}
	return Answer{Value: value}
}
