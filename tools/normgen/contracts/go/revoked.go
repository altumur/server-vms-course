package contracts

import (
	"math/big"
	"regexp"
	"sort"
	"strings"
	"unicode/utf8"
)

// Role certificate contract, revoke (common/contracts/role-certificate.md): the file revoked (file, bad_file), both
// files (both), neither (absent). Serials are compared by integer value; the canonical notation is lowercase hex
// without leading zeros, zero — "0".

var serialLineRE = regexp.MustCompile(`^[0-9a-fA-F]+$`)

// CanonicalSerial — the canonical notation of a hex serial (digits 0–9, a–f, A–F only); false — not a serial.
func CanonicalSerial(hex string) (string, bool) {
	if !serialLineRE.MatchString(hex) {
		return "", false
	}
	n, _ := new(big.Int).SetString(hex, 16)
	return n.Text(16), true
}

// SortSerials — canonical serials ascending by value, without repeats.
func SortSerials(serials []string) []string {
	set := map[string]*big.Int{}
	for _, s := range serials {
		n, _ := new(big.Int).SetString(s, 16)
		set[n.Text(16)] = n
	}
	out := make([]string, 0, len(set))
	for s := range set {
		out = append(out, s)
	}
	sort.Slice(out, func(i, j int) bool { return set[out[i]].Cmp(set[out[j]]) < 0 })
	return out
}

// ReadRevoked — the serials of the file revoked (file): UTF-8, lines by LF, the last MAY be without LF; an empty line
// and a line from «#» are skipped; any other line not of hex digits makes the whole file invalid — ErrRefuse
// (bad_file). The result is canonical, ascending, without repeats.
func ReadRevoked(file []byte) ([]string, error) {
	if !utf8.Valid(file) {
		return nil, ErrRefuse
	}
	text := string(file)
	text = strings.TrimSuffix(text, "\n")
	var out []string
	if text == "" {
		return []string{}, nil
	}
	for _, line := range strings.Split(text, "\n") {
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		s, ok := CanonicalSerial(line)
		if !ok {
			return nil, ErrRefuse
		}
		out = append(out, s)
	}
	return SortSerials(out), nil
}

// RevokedUnion — the revoked serials by both files (both, absent): revoked nil — no file revoked; crl nil — no
// crl.pem, otherwise the serials the CRL of the leaf's issuer revokes (already read by ReadCRL; an invalid crl.pem is
// the caller's ErrRefuse). Neither file — ErrRefuse (absent: the refusal is closed); an invalid revoked — ErrRefuse.
// The union is by integer value.
func RevokedUnion(revoked []byte, crl []string) ([]string, error) {
	if revoked == nil && crl == nil {
		return nil, ErrRefuse
	}
	var out []string
	if revoked != nil {
		r, err := ReadRevoked(revoked)
		if err != nil {
			return nil, err
		}
		out = append(out, r...)
	}
	for _, s := range crl {
		c, ok := CanonicalSerial(s)
		if !ok {
			return nil, ErrRefuse
		}
		out = append(out, c)
	}
	return SortSerials(out), nil
}
