package contracts

import (
	"bytes"
	"crypto/ed25519"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"math"
	"regexp"
	"strconv"
	"strings"
)

// Domain token contract (common/contracts/domain-token.md): token(keys, revoked, now, token, expect) → ok payload |
// refused <word>.

// TokenSkew — TOKEN_SKEW, seconds, both directions.
const TokenSkew = 60

var jtiRE = regexp.MustCompile(`^[A-Za-z0-9_-]{1,64}$`)

var jsonNumberRE = regexp.MustCompile(`^-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?$`)

// TokenKeys — the accepted set domain/keys for the check: keys, until, keep_until.
type TokenKeys struct {
	Keys      map[string]ed25519.PublicKey
	Until     map[string]float64
	KeepUntil map[string]float64
}

// TokenExpect — what the checker expects: Kinds (one kind — List false), Cluster (nil — person, the audience is not
// checked), AudienceClaim by kind (no entry — aud), Keep — the kinds with keep.
type TokenExpect struct {
	Kinds         []string
	List          bool
	Cluster       *string
	AudienceClaim map[string]string
	Keep          []string
}

// noDuplicateKeys — a JSON text without a repeated key in any object.
func noDuplicateKeys(b []byte) bool {
	d := json.NewDecoder(bytes.NewReader(b))
	d.UseNumber()
	var walk func() bool
	walk = func() bool {
		t, err := d.Token()
		if err != nil {
			return false
		}
		switch t {
		case json.Delim('{'):
			seen := map[string]bool{}
			for d.More() {
				k, err := d.Token()
				if err != nil {
					return false
				}
				ks, _ := k.(string)
				if seen[ks] {
					return false
				}
				seen[ks] = true
				if !walk() {
					return false
				}
			}
			_, err = d.Token()
			return err == nil
		case json.Delim('['):
			for d.More() {
				if !walk() {
					return false
				}
			}
			_, err = d.Token()
			return err == nil
		}
		return true
	}
	if !walk() {
		return false
	}
	_, err := d.Token()
	return err != nil // nothing after the value
}

func finiteNumber(v any) (float64, bool) {
	n, ok := v.(json.Number)
	if !ok {
		return 0, false
	}
	f, err := strconv.ParseFloat(string(n), 64)
	return f, err == nil && !math.IsInf(f, 0) && !math.IsNaN(f)
}

func objectOf(b []byte) (map[string]any, bool) {
	if !noDuplicateKeys(b) {
		return nil, false
	}
	d := json.NewDecoder(bytes.NewReader(b))
	d.UseNumber()
	var m map[string]any
	if d.Decode(&m) != nil || m == nil {
		return nil, false
	}
	return m, true
}

// ReadRevokedJTIs — the row domain/revoked {jtis: "<jti>:<number>,…"} (raw nil — no row, no revocations); out of form
// — ErrRefuse (no_revocations).
func ReadRevokedJTIs(raw []byte) (map[string]bool, error) {
	out := map[string]bool{}
	if raw == nil {
		return out, nil
	}
	var row map[string]json.RawMessage
	if json.Unmarshal(raw, &row) != nil || len(row) != 1 {
		return nil, ErrRefuse
	}
	var jtis string
	if r, ok := row["jtis"]; !ok || json.Unmarshal(r, &jtis) != nil {
		return nil, ErrRefuse
	}
	if jtis == "" {
		return out, nil
	}
	for _, e := range strings.Split(jtis, ",") {
		jti, num, ok := strings.Cut(e, ":")
		if !ok || !jtiRE.MatchString(jti) || !jsonNumberRE.MatchString(num) {
			return nil, ErrRefuse
		}
		if f, err := strconv.ParseFloat(num, 64); err != nil || math.IsInf(f, 0) {
			return nil, ErrRefuse
		}
		out[jti] = true
	}
	return out, nil
}

// ParseTokenKeys — the set for the check from the document of domain/keys: keys (kid → hex of 32 bytes, non-empty),
// current ∈ keys and ∉ until, until and keep_until of kids of keys, keep_until only with until; otherwise ErrRefuse.
func ParseTokenKeys(doc map[string]any) (TokenKeys, error) {
	tk := TokenKeys{Keys: map[string]ed25519.PublicKey{}, Until: map[string]float64{}, KeepUntil: map[string]float64{}}
	keys, ok := doc["keys"].(map[string]any)
	if !ok || len(keys) == 0 {
		return tk, ErrRefuse
	}
	for kid, v := range keys {
		s, ok := v.(string)
		b, err := hex.DecodeString(s)
		if kid == "" || !ok || err != nil || len(b) != ed25519.PublicKeySize {
			return tk, ErrRefuse
		}
		tk.Keys[kid] = ed25519.PublicKey(b)
	}
	times := func(field string, into map[string]float64) error {
		v, has := doc[field]
		if !has {
			return nil
		}
		m, ok := v.(map[string]any)
		if !ok {
			return ErrRefuse
		}
		for kid, t := range m {
			f, ok := finiteNumber(t)
			if _, known := tk.Keys[kid]; !ok || !known {
				return ErrRefuse
			}
			into[kid] = f
		}
		return nil
	}
	if times("until", tk.Until) != nil || times("keep_until", tk.KeepUntil) != nil {
		return tk, ErrRefuse
	}
	for kid := range tk.KeepUntil {
		if _, ok := tk.Until[kid]; !ok {
			return tk, ErrRefuse
		}
	}
	current, ok := doc["current"].(string)
	if _, inUntil := tk.Until[current]; !ok || tk.Keys[current] == nil || inUntil {
		return tk, ErrRefuse
	}
	return tk, nil
}

// ParseTokenExpect — the closed form {kind, cluster, audience_claim?, keep?}: kind a string (audience_claim a non-empty
// string) or a non-empty list without repeats and without person (audience_claim a map with keys from the list);
// cluster required, null only with kind person as a string; otherwise ErrRefuse (code 2).
func ParseTokenExpect(raw []byte) (*TokenExpect, error) {
	m, ok := objectOf(raw)
	if !ok {
		return nil, ErrRefuse
	}
	for k := range m {
		switch k {
		case "kind", "cluster", "audience_claim", "keep":
		default:
			return nil, ErrRefuse
		}
	}
	e := &TokenExpect{AudienceClaim: map[string]string{}}
	switch k := m["kind"].(type) {
	case string:
		if k == "" {
			return nil, ErrRefuse
		}
		e.Kinds = []string{k}
		if ac, has := m["audience_claim"]; has {
			s, ok := ac.(string)
			if !ok || s == "" {
				return nil, ErrRefuse
			}
			e.AudienceClaim[k] = s
		}
	case []any:
		if len(k) == 0 {
			return nil, ErrRefuse
		}
		e.List = true
		seen := map[string]bool{}
		for _, x := range k {
			s, ok := x.(string)
			if !ok || s == "" || s == "person" || seen[s] {
				return nil, ErrRefuse
			}
			seen[s] = true
			e.Kinds = append(e.Kinds, s)
		}
		if ac, has := m["audience_claim"]; has {
			mm, ok := ac.(map[string]any)
			if !ok {
				return nil, ErrRefuse
			}
			for kind, f := range mm {
				s, ok := f.(string)
				if !ok || s == "" || !seen[kind] {
					return nil, ErrRefuse
				}
				e.AudienceClaim[kind] = s
			}
		}
	default:
		return nil, ErrRefuse
	}
	c, has := m["cluster"]
	if !has {
		return nil, ErrRefuse
	}
	switch x := c.(type) {
	case nil:
		if e.List || e.Kinds[0] != "person" {
			return nil, ErrRefuse
		}
	case string:
		e.Cluster = &x
	default:
		return nil, ErrRefuse
	}
	if kp, has := m["keep"]; has {
		arr, ok := kp.([]any)
		if !ok {
			return nil, ErrRefuse
		}
		for _, x := range arr {
			s, ok := x.(string)
			if !ok {
				return nil, ErrRefuse
			}
			e.Keep = append(e.Keep, s)
		}
	}
	return e, nil
}

// CheckToken — the steps 1–11; revoked nil — no row; token any JSON value; expect nil — none. The refusal word or ""
// with the payload.
func CheckToken(keys TokenKeys, revoked []byte, now float64, token any, expect *TokenExpect) (string, map[string]any) {
	jtis, err := ReadRevokedJTIs(revoked)
	if err != nil {
		return "no_revocations", nil
	}
	s, ok := token.(string)
	parts := strings.Split(s, ".")
	if !ok || len(parts) != 3 {
		return "not_a_token", nil
	}
	raw := make([][]byte, 3)
	for i, p := range parts {
		b, err := base64.RawURLEncoding.Strict().DecodeString(p)
		if err != nil {
			return "not_a_token", nil
		}
		raw[i] = b
	}
	header, ok1 := objectOf(raw[0])
	payload, ok2 := objectOf(raw[1])
	if !ok1 || !ok2 || header["alg"] != "EdDSA" {
		return "not_a_token", nil
	}
	kid, ok := header["kid"].(string)
	if !ok {
		return "not_a_token", nil
	}
	pub := keys.Keys[kid]
	if pub == nil {
		return "unknown_key", nil
	}
	if !ed25519.Verify(pub, []byte(parts[0]+"."+parts[1]), raw[2]) {
		return "bad_signature", nil
	}
	iat, okI := finiteNumber(payload["iat"])
	exp, okE := finiteNumber(payload["exp"])
	jti, okJ := payload["jti"].(string)
	kind, okK := payload["kind"].(string)
	if !okI || !okE || !okJ || !jtiRE.MatchString(jti) || !okK || kind == "" {
		return "bad_claims", nil
	}
	if until, has := keys.Until[kid]; has && now > until {
		keepUntil, kept := keys.KeepUntil[kid]
		if !(expect != nil && contains(expect.Keep, kind) && kept && now <= keepUntil) {
			return "unknown_key", nil
		}
	}
	if now > exp+TokenSkew {
		return "expired", nil
	}
	if now < iat-TokenSkew {
		return "future", nil
	}
	if jtis[jti] {
		return "revoked", nil
	}
	if expect != nil {
		if !contains(expect.Kinds, kind) {
			return "wrong_kind", nil
		}
		if expect.Cluster != nil {
			field := expect.AudienceClaim[kind]
			if field == "" {
				field = "aud"
			}
			aud, ok := payload[field].([]any)
			found := false
			for _, a := range aud {
				s, isStr := a.(string)
				if !isStr {
					ok = false
				}
				found = found || s == *expect.Cluster
			}
			if !ok || !found {
				return "wrong_audience", nil
			}
		}
	}
	return "", payload
}
