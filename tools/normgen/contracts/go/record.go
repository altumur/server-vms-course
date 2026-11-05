package contracts

import (
	"crypto/ed25519"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"regexp"
	"strconv"
	"strings"
	"unicode/utf8"
)

// The term record contract (common/contracts/record.md): the caller names the accepted document kinds.
type RecordKinds uint8

const (
	TermRecord RecordKinds = 1 << iota
	BackupRecord
	GrantRecord
	MembersRecord
	SharedRecord
)

const RecordDepth = 64

type RecordResult struct {
	Result string         `json:"result"`
	Reason string         `json:"reason,omitempty"`
	Term   int64          `json:"term,omitempty"`
	Holder string         `json:"holder,omitempty"`
	Doc    map[string]any `json:"-"`
}

type RecordInput struct {
	Keys map[string]any
	Row  any
	Part string
	Have any
}

func closedObject(m map[string]any, required, optional string) bool {
	if m == nil {
		return false
	}
	allowed := map[string]bool{}
	for _, k := range strings.Fields(required) {
		if _, ok := m[k]; !ok {
			return false
		}
		allowed[k] = true
	}
	for _, k := range strings.Fields(optional) {
		allowed[k] = true
	}
	for k := range m {
		if !allowed[k] {
			return false
		}
	}
	return true
}

// ParseRecordInput checks trusted command inputs. Document refusals belong to Record, not to this error.
func ParseRecordInput(raw []byte, take bool) (*RecordInput, error) {
	in, ok := strictJSONObject(raw)
	required := "keys row"
	if take {
		required += " part have"
	}
	if !ok || !closedObject(in, required, "") {
		return nil, ErrRefuse
	}
	keys, ok := in["keys"].(map[string]any)
	if !ok || depth(keys) > RecordDepth || !finiteJSON(keys) || !recordTrustedKeys(keys) {
		return nil, ErrRefuse
	}
	out := &RecordInput{Keys: keys, Row: in["row"], Have: in["have"]}
	if take {
		part, ok := in["part"].(string)
		if !ok || !recordPartRE.MatchString(part) {
			return nil, ErrRefuse
		}
		out.Part = part
	}
	return out, nil
}

func recordTrustedKeys(keys map[string]any) bool {
	// An accepted set is read by the time codec (strings included); KeySetForm is also used for offered sets.
	check := map[string]any{}
	for k, v := range keys {
		check[k] = v
	}
	for _, k := range []string{"until", "keep_until"} {
		if v, has := keys[k]; has {
			times, ok := v.(map[string]any)
			if !ok {
				return false
			}
			copy := map[string]any{}
			for kid, v := range times {
				if !timeOK(v) {
					return false
				}
				if text, ok := v.(string); ok {
					v = json.Number(text)
				}
				copy[kid] = v
			}
			check[k] = copy
		}
	}
	return KeySetForm(check, false) && hex32(keys["book_seal"])
}

var recordMemberRE = regexp.MustCompile(`^[a-z0-9-]{1,64}$`)
var recordHexRE = regexp.MustCompile(`^[0-9a-f]{64}$`)
var recordPartRE = regexp.MustCompile(`^(0[0-9]{3}|[1-3][0-9]{3}|40[0-8][0-9]|409[0-5])$`)

// strictJSONObject rejects trailing bytes, duplicate names, invalid UTF-8 and unpaired UTF-16 escapes; Go's
// encoding/json alone replaces malformed Unicode, which must not turn into signed replacement characters.
func strictJSONObject(raw []byte) (map[string]any, bool) {
	if !json.Valid(raw) || !utf8.Valid(raw) {
		return nil, false
	}
	quoted := false
	for i := 0; i < len(raw); i++ {
		if raw[i] == '"' {
			quoted = !quoted
		}
		if !quoted || raw[i] != '\\' {
			continue
		}
		i++
		if raw[i] != 'u' {
			continue
		}
		x, _ := strconv.ParseUint(string(raw[i+1:i+5]), 16, 16)
		i += 4
		if x >= 0xDC00 && x <= 0xDFFF {
			return nil, false
		}
		if x >= 0xD800 && x <= 0xDBFF {
			if i+6 >= len(raw) || raw[i+1] != '\\' || raw[i+2] != 'u' {
				return nil, false
			}
			y, err := strconv.ParseUint(string(raw[i+3:i+7]), 16, 16)
			if err != nil || y < 0xDC00 || y > 0xDFFF {
				return nil, false
			}
			i += 6
		}
	}
	return objectOf(raw)
}

func finiteJSON(v any) bool {
	switch x := v.(type) {
	case json.Number:
		_, ok := finiteNumber(x)
		return ok
	case map[string]any:
		for _, v := range x {
			if !finiteJSON(v) {
				return false
			}
		}
	case []any:
		for _, v := range x {
			if !finiteJSON(v) {
				return false
			}
		}
	}
	return true
}

func recordString(v any) bool { _, ok := v.(string); return ok }
func recordMember(v any) bool {
	s, ok := v.(string)
	return ok && recordMemberRE.MatchString(s)
}
func recordHex(v any) bool {
	s, ok := v.(string)
	return ok && recordHexRE.MatchString(s)
}

func termRev(v any) bool {
	m, ok := v.(map[string]any)
	if !ok || !closedObject(m, "term rev", "") {
		return false
	}
	_, a := boundedInt(m["term"])
	_, b := boundedInt(m["rev"])
	return a && b
}

// MemberPart — first 12 bits of SHA-256(UTF-8(name)), in four decimal digits (P/08.3 Н1.1).
func MemberPart(name string) string {
	h := sha256.Sum256([]byte(name))
	return fmt.Sprintf("%04d", int(h[0])<<4|int(h[1])>>4)
}

func recordForm(doc map[string]any, kinds RecordKinds) bool {
	if depth(doc) > RecordDepth || !finiteJSON(doc) || !recordHex(doc["issuer"]) || !recordString(doc["kid"]) || !recordString(doc["sig"]) {
		return false
	}
	if _, ok := boundedInt(doc["term"]); !ok {
		return false
	}
	common := "term issuer kid sig"
	if _, has := doc["url"]; has && kinds&TermRecord != 0 {
		if !closedObject(doc, common+" domain holder url at", "ca key restored_from") || !recordMember(doc["holder"]) {
			return false
		}
		if s, ok := doc["url"].(string); !ok || s == "" {
			return false
		}
		if _, ok := finiteNumber(doc["at"]); !ok {
			return false
		}
		if v, has := doc["key"]; has && !recordHex(v) {
			return false
		}
		if v, has := doc["ca"]; has {
			list, ok := stringList(v, true)
			if !ok || len(list) < 1 || len(list) > 2 || len(list) == 2 && list[0] == list[1] {
				return false
			}
			for _, fp := range list {
				if !recordHex(fp) {
					return false
				}
			}
		}
		if v, has := doc["restored_from"]; has {
			t, _ := boundedInt(doc["term"])
			if t == 1 || !termRev(v) {
				return false
			}
		}
		return true
	}
	if _, has := doc["backup_key_rev"]; has && kinds&BackupRecord != 0 {
		if !closedObject(doc, common+" rev holder at members state objects backup_key_rev", "raw parts counts holder_member_key") ||
			!recordMember(doc["holder"]) {
			return false
		}
		if _, ok := boundedInt(doc["rev"]); !ok {
			return false
		}
		if _, ok := boundedInt(doc["backup_key_rev"]); !ok {
			return false
		}
		if _, ok := finiteNumber(doc["at"]); !ok {
			return false
		}
		members, ok := stringList(doc["members"], true)
		if !ok {
			return false
		}
		seen := map[string]bool{}
		for _, m := range members {
			if !recordMember(m) || seen[m] {
				return false
			}
			seen[m] = true
		}
		state, ok := doc["state"].(map[string]any)
		if !ok {
			return false
		}
		for _, row := range state {
			items, ok := row.(map[string]any)
			if !ok {
				return false
			}
			for _, v := range items {
				if !recordString(v) {
					return false
				}
			}
		}
		objects, ok := doc["objects"].(map[string]any)
		if !ok {
			return false
		}
		if v, has := doc["raw"]; has {
			raw, ok := v.(map[string]any)
			if !ok {
				return false
			}
			for key, v := range raw {
				s, ok := v.(string)
				b, err := base64.StdEncoding.Strict().DecodeString(s)
				_, both := objects[key]
				if !ok || both || err != nil || base64.StdEncoding.EncodeToString(b) != s {
					return false
				}
			}
		}
		if v, has := doc["parts"]; has {
			parts, ok := v.(map[string]any)
			if !ok {
				return false
			}
			for part, value := range parts {
				link, ok := value.(map[string]any)
				if !ok || !recordPartRE.MatchString(part) || !closedObject(link, "sha256 rev key_rev", "") || !recordHex(link["sha256"]) {
					return false
				}
				if _, ok := boundedInt(link["rev"]); !ok {
					return false
				}
				if _, ok := boundedInt(link["key_rev"]); !ok {
					return false
				}
			}
		}
		if v, has := doc["counts"]; has {
			counts, ok := v.(map[string]any)
			if !ok || !closedObject(counts, "servers cameras", "") {
				return false
			}
			for _, v := range counts {
				n, ok := v.(json.Number)
				if !ok {
					return false
				}
				i, ok := ExactInteger(string(n))
				if !ok || i.Sign() < 0 || !i.IsInt64() || i.Int64() > MaxSafeInt {
					return false
				}
			}
		}
		if v, has := doc["holder_member_key"]; has && !recordHex(v) {
			return false
		}
		return true
	}
	if _, has := doc["grant"]; has && kinds&GrantRecord != 0 {
		if !closedObject(doc, common+" grant domain to from rev at", "") || doc["grant"] != "handover" ||
			!recordMember(doc["to"]) || !recordMember(doc["from"]) {
			return false
		}
		_, rev := boundedInt(doc["rev"])
		_, at := finiteNumber(doc["at"])
		return rev && at
	}
	if _, has := doc["part"]; has && kinds&MembersRecord != 0 {
		if !closedObject(doc, common+" domain part rev members", "gathered new") {
			return false
		}
		part, ok := doc["part"].(string)
		if !ok || !recordPartRE.MatchString(part) {
			return false
		}
		if _, ok := boundedInt(doc["rev"]); !ok {
			return false
		}
		members, ok := doc["members"].(map[string]any)
		if !ok {
			return false
		}
		for name, entry := range members {
			if _, ok := entry.(map[string]any); !ok || !recordMember(name) || MemberPart(name) != part {
				return false
			}
		}
		if v, has := doc["gathered"]; has && v != nil && !termRev(v) {
			return false
		}
		if v, has := doc["new"]; has {
			names, ok := stringList(v, true)
			if !ok {
				return false
			}
			for _, name := range names {
				if _, has := members[name]; !has {
					return false
				}
			}
		}
		return true
	}
	if _, has := doc["shared"]; has && kinds&SharedRecord != 0 {
		if !closedObject(doc, common+" domain rev at by shared", "") || !recordString(doc["by"]) {
			return false
		}
		if _, ok := boundedInt(doc["rev"]); !ok {
			return false
		}
		if _, ok := finiteNumber(doc["at"]); !ok {
			return false
		}
		shared, ok := doc["shared"].(map[string]any)
		if !ok {
			return false
		}
		for sub, v := range shared {
			if _, ok := v.(map[string]any); !ok || !manifestNameRE.MatchString(sub) {
				return false
			}
		}
		return true
	}
	return false
}

func recordDoc(row any) (map[string]any, bool) {
	m, ok := row.(map[string]any)
	if !ok || !closedObject(m, "doc", "") || depth(m) > RecordDepth {
		return nil, false
	}
	text, ok := m["doc"].(string)
	if !ok {
		return nil, false
	}
	doc, ok := strictJSONObject([]byte(text))
	return doc, ok && depth(doc) <= RecordDepth
}

// Record — steps 1–6 over an already accepted key set. The set's root signature is not checked again.
func Record(keys map[string]any, row any, kinds RecordKinds) RecordResult {
	refuse := func(w string) RecordResult { return RecordResult{Result: "refused", Reason: w} }
	doc, ok := recordDoc(row)
	if !ok || !recordForm(doc, kinds) {
		return refuse("not_a_record")
	}
	if domain, has := doc["domain"]; has {
		if s, ok := domain.(string); !ok || s != keys["domain"] {
			return refuse("another_domain")
		}
	}
	kid := doc["kid"].(string)
	revoked, _ := stringList(keys["revoked_issuing"], true)
	if contains(revoked, kid) {
		return refuse("revoked_issuer")
	}
	issuing, _ := stringList(keys["issuing"], true)
	if !contains(issuing, kid) {
		return refuse("unknown_issuer")
	}
	issuer := doc["issuer"].(string)
	pub, _ := hex.DecodeString(issuer)
	sig, ok := b64Canonical(doc["sig"].(string))
	signed := map[string]any{}
	for k, v := range doc {
		if k != "kid" && k != "sig" {
			signed[k] = v
		}
	}
	if kid != issuer[:16] || !ok || len(sig) != ed25519.SignatureSize || SmallOrderKey(pub) ||
		!ed25519.Verify(ed25519.PublicKey(pub), []byte(CanonicalJSON(signed)), sig) {
		return refuse("bad_signature")
	}
	term, _ := boundedInt(doc["term"])
	holder, _ := doc["holder"].(string)
	if from, ok := doc["from"].(string); ok {
		holder = from
	}
	return RecordResult{Result: "ok", Term: term, Holder: holder, Doc: doc}
}

// TakeMemberRecord — a freshness bound by (term, rev); a revoked former issuer does not serve as a bound.
func TakeMemberRecord(keys map[string]any, row any, part string, have any) RecordResult {
	checked := Record(keys, row, MembersRecord)
	if checked.Result != "ok" {
		return checked
	}
	if checked.Doc["part"] != part {
		return RecordResult{Result: "refused", Reason: "another_part"}
	}
	former, ok := recordDoc(have)
	if !ok {
		return RecordResult{Result: "take"}
	}
	t, _ := boundedInt(checked.Doc["term"])
	r, _ := boundedInt(checked.Doc["rev"])
	ft, _ := boundedInt(former["term"])
	fr, _ := boundedInt(former["rev"])
	if t > ft || t == ft && r > fr {
		return RecordResult{Result: "take"}
	}
	if t == ft && r == fr {
		return RecordResult{Result: "same"}
	}
	if Record(keys, have, MembersRecord).Reason == "revoked_issuer" {
		return RecordResult{Result: "take"}
	}
	return RecordResult{Result: "older"}
}
