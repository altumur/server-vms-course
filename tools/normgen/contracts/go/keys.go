package contracts

import (
	"bytes"
	"crypto/ed25519"
	"encoding/hex"
	"encoding/json"
	"math/big"
	"sort"
	"strconv"
	"strings"
)

// Domain key set contract (common/contracts/keys.md): keys(pinned, held, offered) → took rev | holding rev | refused
// <word>; the merge of domain/revoked at a member (merge, repeat, prune).

// Pin — the pinned root {pub, domain}.
type Pin struct {
	Pub    string
	Domain string
}

// x25519SmallOrder — the u-coordinates of the points of small order of Curve25519 (bit 255 cleared).
var x25519SmallOrder = []string{
	"0000000000000000000000000000000000000000000000000000000000000000",
	"0100000000000000000000000000000000000000000000000000000000000000",
	"e0eb7a7c3b41b8ae1656e3faf19fc46ada098deb9c32b1fd866205165f49b800",
	"5f9c95bca3508c24b1d0b1559c83ef5b04445cc4581c8e86d8224eddd09f1157",
	"ecffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f",
	"edffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f",
	"eeffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f",
}

// BookSealOK — book_seal is hex of 32 bytes and not a point of small order of X25519.
func BookSealOK(v any) bool {
	s, ok := v.(string)
	b, err := hex.DecodeString(s)
	if !ok || err != nil || len(b) != 32 {
		return false
	}
	b[31] &= 0x7f
	for _, x := range x25519SmallOrder {
		p, _ := hex.DecodeString(x)
		if bytes.Equal(b, p) {
			return false
		}
	}
	return true
}

func hex32(v any) bool {
	s, ok := v.(string)
	b, err := hex.DecodeString(s)
	return ok && err == nil && len(b) == 32
}

func boundedInt(v any) (int64, bool) {
	n, ok := v.(json.Number)
	if !ok {
		return 0, false
	}
	i, ok := ExactInteger(string(n))
	if !ok || i.Sign() <= 0 || i.Cmp(big.NewInt(MaxSafeInt)) > 0 {
		return 0, false
	}
	return i.Int64(), true
}

func stringList(v any, nonEmpty bool) ([]string, bool) {
	arr, ok := v.([]any)
	if !ok {
		return nil, false
	}
	out := make([]string, 0, len(arr))
	for _, e := range arr {
		s, ok := e.(string)
		if !ok || nonEmpty && s == "" {
			return nil, false
		}
		out = append(out, s)
	}
	return out, true
}

var keySetFields = map[string]bool{"domain": true, "rev": true, "root": true, "current": true, "keys": true, "until": true,
	"keep_until": true, "issuing": true, "revoked_issuing": true, "revoked_members": true, "stolen_issuing": true,
	"thefts": true, "book_seal": true, "kid": true, "sig": true}

// KeySetForm — the doc by the closed form of «The set domain/keys» (book_seal — by withSeal: required and readable).
func KeySetForm(doc map[string]any, withSeal bool) bool {
	for k := range doc {
		if !keySetFields[k] {
			return false
		}
	}
	for _, k := range []string{"domain", "rev", "root", "current", "keys", "issuing", "revoked_issuing", "kid", "sig"} {
		if _, ok := doc[k]; !ok {
			return false
		}
	}
	if d, ok := doc["domain"].(string); !ok || d == "" {
		return false
	}
	if _, ok := boundedInt(doc["rev"]); !ok || !hex32(doc["root"]) {
		return false
	}
	if _, ok := doc["kid"].(string); !ok {
		return false
	}
	if _, ok := doc["sig"].(string); !ok {
		return false
	}
	keys, ok := doc["keys"].(map[string]any)
	if !ok || len(keys) == 0 {
		return false
	}
	for kid, v := range keys {
		if kid == "" || !hex32(v) {
			return false
		}
	}
	if _, err := ParseTokenKeys(doc); err != nil { // current, until, keep_until
		return false
	}
	if _, ok := stringList(doc["issuing"], true); !ok {
		return false
	}
	revokedIssuing, ok := stringList(doc["revoked_issuing"], true)
	if !ok {
		return false
	}
	if v, has := doc["revoked_members"]; has {
		ms, ok := stringList(v, true)
		if !ok {
			return false
		}
		for _, m := range ms {
			if !hex32(m) {
				return false
			}
		}
	}
	if v, has := doc["stolen_issuing"]; has {
		st, ok := stringList(v, true)
		if !ok {
			return false
		}
		for _, s := range st {
			if !contains(revokedIssuing, s) {
				return false
			}
		}
	}
	if v, has := doc["thefts"]; has {
		if _, ok := boundedInt(v); !ok {
			return false
		}
	}
	if withSeal && !BookSealOK(doc["book_seal"]) {
		return false
	}
	return true
}

// KeysOutcome — took | holding with Rev, or refused with Reason (Rev — at older, the rev of held).
type KeysOutcome struct {
	Result string
	Reason string
	Rev    int64
	HasRev bool
}

// Keys — steps 1–8: pinned nil — no_pin; held nil — step 7 does not judge; offered — the row as received.
func Keys(pinned *Pin, held map[string]any, offered []byte) KeysOutcome {
	refuse := func(w string) KeysOutcome { return KeysOutcome{Result: "refused", Reason: w} }
	if pinned == nil {
		return refuse("no_pin")
	}
	row, ok := objectOf(offered)
	if !ok || len(row) != 1 {
		return refuse("not_a_set")
	}
	text, ok := row["doc"].(string)
	if !ok {
		return refuse("not_a_set")
	}
	doc, ok := objectOf([]byte(text))
	if !ok || !KeySetForm(doc, false) {
		return refuse("not_a_set")
	}
	if doc["kid"] != "root" {
		return refuse("bad_signature")
	}
	if doc["root"] != pinned.Pub || doc["domain"] != pinned.Domain {
		return refuse("another_root")
	}
	sig, okSig := b64Canonical(doc["sig"].(string))
	pub, _ := hex.DecodeString(pinned.Pub)
	signed := map[string]any{}
	for k, v := range doc {
		if k != "kid" && k != "sig" {
			signed[k] = v
		}
	}
	if !okSig || len(sig) != ed25519.SignatureSize || len(pub) != ed25519.PublicKeySize ||
		!ed25519.Verify(ed25519.PublicKey(pub), []byte(CanonicalJSON(signed)), sig) {
		return refuse("bad_signature")
	}
	if !BookSealOK(doc["book_seal"]) {
		return refuse("no_book_seal")
	}
	rev, _ := boundedInt(doc["rev"])
	if held != nil {
		hrev, _ := boundedInt(held["rev"])
		if rev < hrev {
			return KeysOutcome{Result: "refused", Reason: "older", Rev: hrev, HasRev: true}
		}
		if rev == hrev {
			return KeysOutcome{Result: "holding", Rev: hrev, HasRev: true}
		}
	}
	return KeysOutcome{Result: "took", Rev: rev, HasRev: true}
}

type jtiEntry struct {
	exp  float64
	text string
}

func parseJTIs(s string) (map[string]jtiEntry, bool) {
	out := map[string]jtiEntry{}
	if s == "" {
		return out, true
	}
	for _, e := range strings.Split(s, ",") {
		jti, num, ok := strings.Cut(e, ":")
		if !ok || !jtiRE.MatchString(jti) || !jsonNumberRE.MatchString(num) {
			return nil, false
		}
		f, err := strconv.ParseFloat(num, 64)
		if err != nil {
			return nil, false
		}
		if old, has := out[jti]; !has || f > old.exp {
			out[jti] = jtiEntry{f, num}
		}
	}
	return out, true
}

// MergeRevoked — the row jtis the agent writes: its own ∪ the answer (answer nil — none) by jti, at an equal jti the
// greater exp; prune exp + TOKEN_SKEW < now; ascending by jti in bytes. Out of form — ErrRefuse.
func MergeRevoked(own string, answer *string, now float64) (string, error) {
	all, ok := parseJTIs(own)
	if !ok {
		return "", ErrRefuse
	}
	if answer != nil {
		a, ok := parseJTIs(*answer)
		if !ok {
			return "", ErrRefuse
		}
		for jti, e := range a {
			if old, has := all[jti]; !has || e.exp > old.exp {
				all[jti] = e
			}
		}
	}
	var jtis []string
	for jti, e := range all {
		if e.exp+TokenSkew >= now {
			jtis = append(jtis, jti)
		}
	}
	sort.Strings(jtis)
	parts := make([]string, len(jtis))
	for i, j := range jtis {
		parts[i] = j + ":" + all[j].text
	}
	return strings.Join(parts, ","), nil
}
