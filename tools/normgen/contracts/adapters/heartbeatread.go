// The kit's adapter of common/heartbeat-read over the two generated foreign heartbeat families.
// YOURS from here like any adapter: the kit puts it once instead of the stub.
package vectoradapter

import "kitmodule/internal/contracts/heartbeat"

// HeartbeatRead — cases.tsv: {readable[, fields]}; worker.tsv: {rows, others, fields}.
func HeartbeatRead(table string, cells map[string]string, files map[string][]byte) Answer {
	switch table {
	case "cases.tsv":
		r := heartbeat.ReadResource("platform/resources/srv-a/heartbeat", []byte(cells["object"]))
		if !r.Readable {
			return Answer{Value: map[string]any{"readable": false}}
		}
		return Answer{Value: map[string]any{"readable": true, "fields": r.Fields}}
	case "worker.tsv":
		return Answer{Value: heartbeat.ReadWorker(cells["key"], []byte(cells["object"]))}
	}
	return Answer{Code: 2}
}
