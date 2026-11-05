// The kit's adapter of common/agent-sig over the package contracts (tools/normgen/contracts; ADR-0125 addendum (5)).
// YOURS from here like any adapter: the kit puts it once instead of the stub.

package vectoradapter

import (
	"encoding/hex"
	"encoding/json"
	"strings"

	"kitmodule/internal/contracts"
)

// AgentSig — cases.tsv: {key, method, path, body, header, now, window[, for]} → {result: ok} | {result: refused,
// reason}; batch-knock.tsv: {pub, domain, name, key, sig} → {result: ok} | {result: refused}.
func AgentSig(table string, cells map[string]string, files map[string][]byte) Answer {
	if table == "batch-knock.tsv" {
		var in struct{ Pub, Domain, Name, Key, Sig string }
		if err := json.Unmarshal([]byte(cells["input"]), &in); err != nil {
			return Answer{Code: 2, Value: err.Error()}
		}
		pub, err := hex.DecodeString(in.Pub)
		if err == nil && contracts.BatchKnockOK(pub, in.Domain, in.Name, in.Key, in.Sig) {
			return Answer{Value: map[string]any{"result": "ok"}}
		}
		return Answer{Value: map[string]any{"result": "refused"}}
	}
	var in struct {
		Key    *string  `json:"key"`
		Method *string  `json:"method"`
		Path   *string  `json:"path"`
		Body   *string  `json:"body"`
		Header string   `json:"header"`
		Now    *float64 `json:"now"`
		Window *float64 `json:"window"`
		For    *string  `json:"for"`
	}
	if err := json.Unmarshal([]byte(cells["input"]), &in); err != nil || in.Key == nil || in.Method == nil ||
		in.Path == nil || in.Body == nil || in.Now == nil || in.Window == nil || strings.Contains(*in.Path, "?") {
		return Answer{Code: 2, Value: "the input is not of the form"}
	}
	key, err := hex.DecodeString(*in.Key)
	if err != nil {
		return Answer{Code: 2, Value: "key: not hex"}
	}
	word := contracts.AgentSig(key, *in.Method, *in.Path, []byte(*in.Body), in.Header, *in.Now, *in.Window, in.For)
	if word == "" {
		return Answer{Value: map[string]any{"result": "ok"}}
	}
	return Answer{Value: map[string]any{"result": "refused", "reason": word}}
}
