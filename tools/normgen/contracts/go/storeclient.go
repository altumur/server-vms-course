package contracts

import (
	"bytes"
	"encoding/json"
	"regexp"
	"strings"
)

// Store client contract (common/contracts/store-client.md): the outcome of a store answer for the client by the closed
// answer forms of the door of P/01.1 (Row, Listing, Written, Fault of 01-store.api.openapi.yaml).

// StoreReply — the answer that came: the HTTP code and the JSON body. No answer, a cut-off answer and a refused
// connection are a nil *StoreReply (no_reply).
type StoreReply struct {
	Status int
	Body   []byte
}

var versionRE = regexp.MustCompile(`^(?:0|[1-9][0-9]{0,19})$`)

// ValidVersion — a version on the wire: a decimal number without a sign and leading zeros, up to 20 digits.
func ValidVersion(s string) bool { return versionRE.MatchString(s) }

// ValidStoreKey — the form of a store key (Key): non-empty, not from «/», no «..» segment.
func ValidStoreKey(s string) bool {
	if s == "" || strings.HasPrefix(s, "/") {
		return false
	}
	for _, seg := range strings.Split(s, "/") {
		if seg == ".." {
			return false
		}
	}
	return true
}

// faultCodes — the HTTP codes of each refusal kind (P/01.1 N4); a kind under another code is not of the closed form.
var faultCodes = map[string][]int{
	"badkey": {400}, "badrequest": {400, 404}, "forbidden": {403}, "conflict": {409}, "expired": {409},
	"early": {409}, "refused": {409}, "guard": {412}, "toolarge": {413}, "unavailable": {503}, "ambiguous": {503},
}

// StoreOutcome — outcome(operation, answer): op "get" | "list" | "write" (a write, a delete and a batch); reply nil —
// no_reply. The result is "row", "absent", "unreadable", "listing", "written" or the kind of a Fault; an answer not
// by the closed form of its operation is no_reply: "unavailable" for get and list, "ambiguous" for write. An op out of
// the list — ErrRefuse.
func StoreOutcome(op string, reply *StoreReply) (string, error) {
	var noReply string
	switch op {
	case "get", "list":
		noReply = "unavailable"
	case "write":
		noReply = "ambiguous"
	default:
		return "", ErrRefuse
	}
	if reply == nil {
		return noReply, nil
	}
	body, ok := decodeObject(reply.Body)
	if !ok {
		return noReply, nil
	}
	if reply.Status == 200 {
		if out, ok := successForm(op, body); ok {
			return out, nil
		}
		return noReply, nil
	}
	if kind, ok := faultForm(reply.Status, body); ok {
		return kind, nil
	}
	return noReply, nil
}

func decodeObject(b []byte) (map[string]json.RawMessage, bool) {
	d := json.NewDecoder(bytes.NewReader(b))
	var m map[string]json.RawMessage
	if d.Decode(&m) != nil || m == nil {
		return nil, false
	}
	if _, err := d.Token(); err == nil { // trailing data after the object
		return nil, false
	}
	return m, true
}

func onlyFields(m map[string]json.RawMessage, required []string, optional ...string) bool {
	allowed := map[string]bool{}
	for _, f := range required {
		if _, ok := m[f]; !ok {
			return false
		}
		allowed[f] = true
	}
	for _, f := range optional {
		allowed[f] = true
	}
	for f := range m {
		if !allowed[f] {
			return false
		}
	}
	return true
}

func jsonString(r json.RawMessage) (string, bool) {
	var s string
	if r == nil || r[0] != '"' || json.Unmarshal(r, &s) != nil {
		return "", false
	}
	return s, true
}

func isNull(r json.RawMessage) bool { return string(r) == "null" }

func isTrue(r json.RawMessage) bool { return string(r) == "true" }

func successForm(op string, m map[string]json.RawMessage) (string, bool) {
	switch op {
	case "get":
		idx, ok := jsonString(m["index"])
		if !ok {
			return "", false
		}
		if _, has := m["unreadable"]; has {
			if onlyFields(m, []string{"items", "index", "unreadable"}) && isNull(m["items"]) &&
				isTrue(m["unreadable"]) && ValidVersion(idx) {
				return "unreadable", true
			}
			return "", false
		}
		if !onlyFields(m, []string{"items", "index"}) {
			return "", false
		}
		if isNull(m["items"]) {
			return "absent", idx == ""
		}
		var items map[string]string
		if m["items"][0] != '{' || json.Unmarshal(m["items"], &items) != nil {
			return "", false
		}
		return "row", ValidVersion(idx)
	case "list":
		if !onlyFields(m, []string{"keys"}) {
			return "", false
		}
		var keys map[string]json.RawMessage
		if m["keys"][0] != '{' || json.Unmarshal(m["keys"], &keys) != nil {
			return "", false
		}
		for k, v := range keys {
			s, ok := jsonString(v)
			if !ok || !ValidStoreKey(k) || !ValidVersion(s) {
				return "", false
			}
		}
		return "listing", true
	default: // write
		if !onlyFields(m, []string{"index"}, "again") {
			return "", false
		}
		if a, has := m["again"]; has && !isTrue(a) {
			return "", false
		}
		idx, ok := jsonString(m["index"])
		return "written", ok && ValidVersion(idx)
	}
}

func versionOrAbsent(r json.RawMessage) bool {
	s, ok := jsonString(r)
	return ok && (s == "" || ValidVersion(s))
}

func storeKey(r json.RawMessage) bool {
	s, ok := jsonString(r)
	return ok && ValidStoreKey(s)
}

func integerAtLeast(r json.RawMessage, min int64) bool {
	var n json.Number
	if r == nil || json.Unmarshal(r, &n) != nil {
		return false
	}
	i, err := n.Int64()
	return err == nil && i >= min
}

func faultForm(status int, m map[string]json.RawMessage) (string, bool) {
	kind, ok := jsonString(m["kind"])
	if !ok {
		return "", false
	}
	if _, ok := jsonString(m["error"]); !ok {
		return "", false
	}
	codeOK := false
	for _, c := range faultCodes[kind] {
		codeOK = codeOK || c == status
	}
	if !codeOK {
		return "", false
	}
	base := []string{"kind", "error"}
	switch kind {
	case "conflict":
		if _, has := m["key"]; has {
			ok = onlyFields(m, append(base, "key", "index")) && storeKey(m["key"]) && versionOrAbsent(m["index"])
		} else {
			ok = onlyFields(m, append(base, "index")) && versionOrAbsent(m["index"])
		}
	case "guard":
		ok = onlyFields(m, append(base, "key", "index")) && storeKey(m["key"]) && versionOrAbsent(m["index"])
	case "toolarge":
		if _, has := m["key"]; has { // a row heavier than the ceiling
			ok = onlyFields(m, append(base, "key", "size", "limit")) && storeKey(m["key"]) &&
				integerAtLeast(m["size"], 1) && integerAtLeast(m["limit"], 0)
		} else { // a body larger than the limit
			ok = onlyFields(m, append(base, "limit"), "size") && integerAtLeast(m["limit"], 1)
			if s, has := m["size"]; has && ok {
				ok = integerAtLeast(s, 1)
			}
		}
	default:
		ok = onlyFields(m, base)
	}
	return kind, ok
}
