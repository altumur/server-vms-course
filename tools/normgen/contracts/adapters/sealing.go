// The kit's adapter of common/sealing over the package contracts (tools/normgen/contracts; ADR-0125 addendum (5)).
// YOURS from here like any adapter: the kit puts it once instead of the stub.

package vectoradapter

import (
	"encoding/hex"
	"encoding/json"
	"strings"

	"kitmodule/internal/contracts"
)

// Sealing — aad.tsv → {pointer, aad_hex}; envelope.tsv → the envelope; open.tsv → the value or "sealed"; ring.tsv →
// "current <kid>; keys <kid>, …[; rotate <kid> | rotate refused]" or "unreadable"; reseal.tsv → {row, secrets}.
func Sealing(table string, cells map[string]string, files map[string][]byte) Answer {
	bad := func(err error) Answer { return Answer{Code: 2, Value: err.Error()} }
	switch table {
	case "aad.tsv":
		var path []any
		d := json.NewDecoder(strings.NewReader(cells["path"]))
		d.UseNumber()
		if err := d.Decode(&path); err != nil {
			return bad(err)
		}
		for i, seg := range path {
			if n, ok := seg.(json.Number); ok {
				k, err := n.Int64()
				if err != nil {
					return bad(err)
				}
				path[i] = int(k)
			}
		}
		pointer, err := contracts.Pointer(path)
		if err != nil {
			return bad(err)
		}
		aad, err := contracts.AAD(cells["row_key"], pointer)
		if err != nil {
			return bad(err)
		}
		return Answer{Value: map[string]any{"pointer": pointer, "aad_hex": hex.EncodeToString(aad)}}
	case "envelope.tsv":
		key, err := hex.DecodeString(cells["key_hex"])
		if err != nil {
			return bad(err)
		}
		nonce, err := contracts.B64URL(cells["nonce_b64url"])
		if err != nil {
			return bad(err)
		}
		var plain string
		if err := json.Unmarshal([]byte(cells["plaintext"]), &plain); err != nil {
			return bad(err)
		}
		env, err := contracts.Seal(key, cells["kid"], nonce, cells["row_key"], cells["pointer"], plain)
		if err != nil {
			return bad(err)
		}
		return Answer{Value: env}
	case "open.tsv":
		if cells["key_hex"] == "" { // the ring has no key with the kid of the envelope
			return Answer{Value: "sealed"}
		}
		key, err := hex.DecodeString(cells["key_hex"])
		if err != nil {
			return bad(err)
		}
		v, err := contracts.Open(key, cells["envelope"], cells["row_key"], cells["pointer"])
		if err != nil {
			return Answer{Value: "sealed"}
		}
		return Answer{Value: v}
	case "ring.tsv":
		var file string
		if err := json.Unmarshal([]byte(cells["file"]), &file); err != nil {
			return bad(err)
		}
		ring, err := contracts.ReadRing([]byte(file))
		if err != nil {
			return Answer{Value: "unreadable"}
		}
		kids := make([]string, len(ring.Keys))
		for i, k := range ring.Keys {
			kids[i] = k.Kid
		}
		out := "current " + ring.Current().Kid + "; keys " + strings.Join(kids, ", ")
		if cells["rotate"] == "true" {
			if name, err := ring.RotateName(); err == nil {
				out += "; rotate " + name
			} else {
				out += "; rotate refused"
			}
		}
		return Answer{Value: out}
	case "reseal.tsv":
		var in struct {
			Ring       string            `json:"ring"`
			RowKey     string            `json:"row_key"`
			Row        map[string]string `json:"row"`
			JSONFields []string          `json:"json_fields"`
		}
		if err := json.Unmarshal([]byte(cells["input"]), &in); err != nil {
			return bad(err)
		}
		ring, err := contracts.ReadRing([]byte(in.Ring))
		if err != nil {
			return bad(err)
		}
		r := contracts.Reseal(ring, in.RowKey, in.Row, in.JSONFields)
		if r.Skip {
			return Answer{Value: map[string]any{"row": "skip"}}
		}
		secrets := map[string]any{}
		for p, outcome := range r.Outcome {
			switch outcome {
			case contracts.ResealSame:
				secrets[p] = "@same"
			case contracts.ResealUntouched:
				secrets[p] = "@untouched"
			default: // open the new envelope with its kid by the same AAD
				env := r.Envelopes[p]
				kid := strings.Split(env, ":")[2]
				plain, err := contracts.Open(ring.Key(kid), env, in.RowKey, p)
				if err != nil {
					return bad(err)
				}
				secrets[p] = map[string]any{"kid": kid, "plaintext": plain}
			}
		}
		row := "same"
		if r.Changed {
			row = "changed"
		}
		return Answer{Value: map[string]any{"row": row, "secrets": secrets}}
	}
	return Answer{Code: 2, Value: "unknown table " + table}
}
