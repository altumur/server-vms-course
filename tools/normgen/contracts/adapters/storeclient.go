// The kit's adapter of common/store-client over the package contracts (tools/normgen/contracts; ADR-0125 addendum (5)).
// YOURS from here like any adapter: the kit puts it once instead of the stub.

package vectoradapter

import (
	"encoding/json"
	"errors"

	"kitmodule/internal/contracts"
)

// StoreClient — the outcome of a store answer for the client: input {op, reply}, reply {status, body} or "@none",
// "@truncated", "@refused" (no_reply).
func StoreClient(input []byte) (string, error) {
	var in struct {
		Op    string          `json:"op"`
		Reply json.RawMessage `json:"reply"`
	}
	if err := json.Unmarshal(input, &in); err != nil {
		return "", err
	}
	var reply *contracts.StoreReply
	var word string
	if json.Unmarshal(in.Reply, &word) == nil {
		switch word {
		case "@none", "@truncated", "@refused":
		default:
			return "", errors.New("vectoradapter.StoreClient: unknown reply " + word)
		}
	} else {
		var r struct {
			Status int             `json:"status"`
			Body   json.RawMessage `json:"body"`
		}
		if err := json.Unmarshal(in.Reply, &r); err != nil {
			return "", err
		}
		reply = &contracts.StoreReply{Status: r.Status, Body: r.Body}
	}
	return contracts.StoreOutcome(in.Op, reply)
}
