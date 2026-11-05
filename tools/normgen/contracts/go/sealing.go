package contracts

import (
	"bytes"
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"math/big"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"unicode/utf8"
)

// Sealing contract (common/contracts/sealing.md): the envelope enc:v2, the AAD path, the ring file, resealing a value.

// ErrSealed — the envelope does not open (not by the grammar, not in its place, a foreign key, the tag): the value
// stays sealed.
var ErrSealed = errors.New("sealed")

const (
	nonceSize = 12
	tagSize   = 16
)

var b64 = base64.RawURLEncoding.Strict()

// b64Canonical — base64url without «=» in the canonical notation (the residual bits of the last character are zeros).
func b64Canonical(s string) ([]byte, bool) {
	if strings.ContainsAny(s, "=") {
		return nil, false
	}
	b, err := b64.DecodeString(s)
	return b, err == nil && b64.EncodeToString(b) == s
}

// ValidKid — a kid: non-empty, without «:», blanks (U+0020, U+0009, U+000D, U+000A) and U+FEFF, not from «#».
func ValidKid(kid string) bool {
	return kid != "" && !strings.ContainsAny(kid, ": \t\r\n\uFEFF") && !strings.HasPrefix(kid, "#") &&
		utf8.ValidString(kid)
}

// PointerSegment — one JSON Pointer segment: «~» → «~0», «/» → «~1».
func PointerSegment(s string) string {
	return strings.ReplaceAll(strings.ReplaceAll(s, "~", "~0"), "/", "~1")
}

// Pointer — the full JSON Pointer of the path from the root of the row: a string — a key, a non-negative integer — an
// index (decimal without leading zeros).
func Pointer(path []any) (string, error) {
	var b strings.Builder
	for _, seg := range path {
		b.WriteByte('/')
		switch v := seg.(type) {
		case string:
			b.WriteString(PointerSegment(v))
		case int:
			if v < 0 {
				return "", ErrRefuse
			}
			b.WriteString(strconv.Itoa(v))
		default:
			return "", ErrRefuse
		}
	}
	return b.String(), nil
}

// AAD — UTF-8(row key) + 0x00 + UTF-8(pointer); a row key with NUL or a pointer without the leading «/» — ErrRefuse
// (before the cryptographic operation).
func AAD(rowKey, pointer string) ([]byte, error) {
	if strings.ContainsRune(rowKey, 0) || !strings.HasPrefix(pointer, "/") {
		return nil, ErrRefuse
	}
	return append(append([]byte(rowKey), 0), pointer...), nil
}

// LooksSealed — everything that begins with enc: is taken for an envelope.
func LooksSealed(v string) bool { return strings.HasPrefix(v, "enc:") }

// Envelope — the parts of enc:v2:<kid>:<nonce>:<ct> by the strict grammar.
type Envelope struct {
	Kid   string
	Nonce []byte
	CT    []byte
}

// ParseEnvelope — strict: enc:v2, five parts by «:», a kid by the grammar, a nonce of 12 bytes and a ct not shorter than
// the tag in canonical base64url without «=»; otherwise ErrSealed without the cryptographic operation.
func ParseEnvelope(s string) (Envelope, error) {
	parts := strings.Split(s, ":")
	if len(parts) != 5 || parts[0] != "enc" || parts[1] != "v2" || !ValidKid(parts[2]) {
		return Envelope{}, ErrSealed
	}
	nonce, ok1 := b64Canonical(parts[3])
	ct, ok2 := b64Canonical(parts[4])
	if !ok1 || !ok2 || len(nonce) != nonceSize || len(ct) < tagSize {
		return Envelope{}, ErrSealed
	}
	return Envelope{Kid: parts[2], Nonce: nonce, CT: ct}, nil
}

func gcm(key []byte) (cipher.AEAD, error) {
	if len(key) != 32 {
		return nil, ErrRefuse
	}
	block, err := aes.NewCipher(key)
	if err != nil {
		return nil, err
	}
	return cipher.NewGCM(block)
}

// Seal — the envelope of plaintext under key/kid at (rowKey, pointer); nonce nil — 12 random bytes. An empty value is
// not sealed (returned as is); a value from enc: or a wrong context — ErrRefuse.
func Seal(key []byte, kid string, nonce []byte, rowKey, pointer, plaintext string) (string, error) {
	if plaintext == "" {
		return "", nil
	}
	if LooksSealed(plaintext) || !ValidKid(kid) {
		return "", ErrRefuse
	}
	aad, err := AAD(rowKey, pointer)
	if err != nil {
		return "", err
	}
	if nonce == nil {
		nonce = make([]byte, nonceSize)
		if _, err := rand.Read(nonce); err != nil {
			return "", err
		}
	}
	if len(nonce) != nonceSize {
		return "", ErrRefuse
	}
	a, err := gcm(key)
	if err != nil {
		return "", err
	}
	ct := a.Seal(nil, nonce, []byte(plaintext), aad)
	return "enc:v2:" + kid + ":" + b64.EncodeToString(nonce) + ":" + b64.EncodeToString(ct), nil
}

// Open — the value of the envelope with key at (rowKey, pointer); the single context, no former ways; ErrSealed.
func Open(key []byte, envelope, rowKey, pointer string) (string, error) {
	e, err := ParseEnvelope(envelope)
	if err != nil {
		return "", err
	}
	aad, err := AAD(rowKey, pointer)
	if err != nil {
		return "", ErrSealed
	}
	a, err := gcm(key)
	if err != nil {
		return "", ErrSealed
	}
	plain, err := a.Open(nil, e.Nonce, e.CT, aad)
	if err != nil {
		return "", ErrSealed
	}
	return string(plain), nil
}

// RingKey — an entry of the ring file.
type RingKey struct {
	Kid string
	Key []byte
}

// Ring — the keys in the order of the file; the first is the current one.
type Ring struct{ Keys []RingKey }

// Current — the current entry.
func (r *Ring) Current() RingKey { return r.Keys[0] }

// Key — the key of kid (nil — no such kid).
func (r *Ring) Key(kid string) []byte {
	for _, k := range r.Keys {
		if k.Kid == kid {
			return k.Key
		}
	}
	return nil
}

var hex64RE = regexp.MustCompile(`^[0-9a-fA-F]{64}$`)

// ReadRing — the ring file: strictly UTF-8, one leading BOM skipped; lines by LF (CR before LF — the end of the line);
// blanks U+0020 and U+0009 at the edges ignored; empty lines and lines from «#» skipped; an entry — exactly two fields
// <kid> <64 hex>; at least one key, distinct kids. Otherwise ErrRefuse (unreadable, not unset).
func ReadRing(file []byte) (*Ring, error) {
	if !utf8.Valid(file) {
		return nil, ErrRefuse
	}
	text := strings.TrimPrefix(string(file), "\uFEFF")
	r := &Ring{}
	seen := map[string]bool{}
	for _, line := range strings.Split(text, "\n") {
		line = strings.TrimSuffix(line, "\r")
		line = strings.Trim(line, " \t")
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		f := strings.FieldsFunc(line, func(c rune) bool { return c == ' ' || c == '\t' })
		if len(f) != 2 || !ValidKid(f[0]) || !hex64RE.MatchString(f[1]) || seen[f[0]] {
			return nil, ErrRefuse
		}
		key, _ := hex.DecodeString(f[1])
		seen[f[0]] = true
		r.Keys = append(r.Keys, RingKey{Kid: f[0], Key: key})
	}
	if len(r.Keys) == 0 {
		return nil, ErrRefuse
	}
	return r, nil
}

var knRE = regexp.MustCompile(`^k([1-9][0-9]*)$`)

// RotateName — the name rotate gives: k<max+1> by the numbers N, without machine overflow; a name not kN — ErrRefuse
// (the command is refused without a change of the file).
func (r *Ring) RotateName() (string, error) {
	max := new(big.Int)
	for _, k := range r.Keys {
		m := knRE.FindStringSubmatch(k.Kid)
		if m == nil {
			return "", ErrRefuse
		}
		n, _ := new(big.Int).SetString(m[1], 10)
		if n.Cmp(max) > 0 {
			max = n
		}
	}
	return "k" + max.Add(max, big.NewInt(1)).String(), nil
}

// Reseal outcome of one secret.
const (
	ResealSame      = "same"      // the bytes are the same (current kid, an empty value)
	ResealSealed    = "sealed"    // sealed with the current kid (old kid or a plain value)
	ResealUntouched = "untouched" // enc:v1, not by the grammar, a kid not in the ring, the tag does not open
)

// ResealResult — the row: Skip (a json field is not JSON — the row does not change), Changed, the new elements; and by
// the pointer of each secret its outcome and the new envelope.
type ResealResult struct {
	Skip      bool
	Changed   bool
	Row       map[string]string
	Outcome   map[string]string
	Envelopes map[string]string
}

// ResealValue — what is done with one value (current, old, plain, untouched; empty — same).
func ResealValue(ring *Ring, rowKey, pointer, v string) (string, string) {
	cur := ring.Current()
	if v == "" {
		return v, ResealSame
	}
	if !LooksSealed(v) {
		env, err := Seal(cur.Key, cur.Kid, nil, rowKey, pointer, v)
		if err != nil {
			return v, ResealUntouched
		}
		return env, ResealSealed
	}
	e, err := ParseEnvelope(v)
	if err != nil {
		return v, ResealUntouched
	}
	if e.Kid == cur.Kid {
		return v, ResealSame
	}
	key := ring.Key(e.Kid)
	if key == nil {
		return v, ResealUntouched
	}
	plain, err := Open(key, v, rowKey, pointer)
	if err != nil {
		return v, ResealUntouched
	}
	env, err := Seal(cur.Key, cur.Kid, nil, rowKey, pointer, plain)
	if err != nil {
		return v, ResealUntouched
	}
	return env, ResealSealed
}

// Reseal — the walk of one row: the fields *_secret at the top level and nested in the text of the json fields (at
// any depth, the full pointer from the root of the row).
func Reseal(ring *Ring, rowKey string, row map[string]string, jsonFields []string) ResealResult {
	res := ResealResult{Row: map[string]string{}, Outcome: map[string]string{}, Envelopes: map[string]string{}}
	for k, v := range row {
		res.Row[k] = v
	}
	isJSON := map[string]bool{}
	for _, f := range jsonFields {
		isJSON[f] = true
	}
	names := make([]string, 0, len(row))
	for k := range row {
		names = append(names, k)
	}
	sort.Strings(names)
	parsed := map[string]any{}
	for _, name := range names {
		if !isJSON[name] {
			continue
		}
		var doc any
		d := json.NewDecoder(strings.NewReader(row[name]))
		d.UseNumber()
		if d.Decode(&doc) != nil || d.More() {
			return ResealResult{Skip: true}
		}
		parsed[name] = doc
	}
	apply := func(pointer, v string) string {
		nv, out := ResealValue(ring, rowKey, pointer, v)
		res.Outcome[pointer] = out
		if out == ResealSealed {
			res.Envelopes[pointer] = nv
			res.Changed = true
		}
		return nv
	}
	for _, name := range names {
		if isJSON[name] {
			before := len(res.Envelopes)
			doc := walkSecrets(parsed[name], "/"+PointerSegment(name), apply)
			if len(res.Envelopes) > before {
				var b bytes.Buffer
				enc := json.NewEncoder(&b)
				enc.SetEscapeHTML(false)
				_ = enc.Encode(doc)
				res.Row[name] = strings.TrimSuffix(b.String(), "\n")
			}
			continue
		}
		if strings.HasSuffix(name, "_secret") {
			res.Row[name] = apply("/"+PointerSegment(name), row[name])
		}
	}
	return res
}

func walkSecrets(v any, at string, apply func(pointer, v string) string) any {
	switch x := v.(type) {
	case map[string]any:
		keys := make([]string, 0, len(x))
		for k := range x {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		for _, k := range keys {
			p := at + "/" + PointerSegment(k)
			if s, ok := x[k].(string); ok && strings.HasSuffix(k, "_secret") {
				x[k] = apply(p, s)
			} else {
				x[k] = walkSecrets(x[k], p, apply)
			}
		}
	case []any:
		for i := range x {
			x[i] = walkSecrets(x[i], at+"/"+strconv.Itoa(i), apply)
		}
	}
	return v
}

// B64URL — a nonce or a ct in canonical base64url without «=».
func B64URL(s string) ([]byte, error) {
	b, ok := b64Canonical(s)
	if !ok {
		return nil, ErrRefuse
	}
	return b, nil
}
