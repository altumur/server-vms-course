// The kit's adapter of common/record over the package contracts. YOURS from here.
package vectoradapter

import "kitmodule/internal/contracts"

func Record(table string, cells map[string]string, files map[string][]byte) Answer {
	if table != "cases.tsv" && table != "shared.tsv" && table != "take.tsv" {
		return Answer{Code: 2}
	}
	in, err := contracts.ParseRecordInput([]byte(cells["input"]), table == "take.tsv")
	if err != nil {
		return Answer{Code: 2}
	}
	if table == "take.tsv" {
		return Answer{Value: contracts.TakeMemberRecord(in.Keys, in.Row, in.Part, in.Have)}
	}
	kinds := contracts.TermRecord | contracts.BackupRecord | contracts.GrantRecord | contracts.MembersRecord
	if table == "shared.tsv" {
		kinds = contracts.SharedRecord
	}
	return Answer{Value: contracts.Record(in.Keys, in.Row, kinds)}
}
