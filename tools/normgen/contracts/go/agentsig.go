package contracts

import (
	"bytes"
	"crypto/ed25519"
	"crypto/sha256"
	"encoding/hex"
	"math"
	"regexp"
	"strconv"
	"strings"
)

// Agent signature contract (common/contracts/agent-signature.md): the check of X-Agent-Signature: <ms>.<sig>, and the
// signature of a batch knock (common/contracts/accept.md «The batch knock»).

// MemberWindow, UnitWindow — the windows, seconds.
const (
	MemberWindow = 300
	UnitWindow   = 60
)

var msRE = regexp.MustCompile(`^(0|[1-9][0-9]{0,15})$`)

// smallOrder — the encodings of the points of small order of Edwards25519 with the sign bit cleared (libsodium's list:
// [8]A is the neutral element), including the non-canonical ones.
var smallOrder = []string{
	"0000000000000000000000000000000000000000000000000000000000000000",
	"0100000000000000000000000000000000000000000000000000000000000000",
	"26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc05",
	"c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac037a",
	"ecffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f",
	"edffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f",
	"eeffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f",
}

// SmallOrderKey — the public key A has [8]A neutral (the sign bit is not taken into account).
func SmallOrderKey(pub []byte) bool {
	if len(pub) != ed25519.PublicKeySize {
		return true
	}
	k := append([]byte{}, pub...)
	k[31] &= 0x7f
	for _, s := range smallOrder {
		b, _ := hex.DecodeString(s)
		b[31] &= 0x7f
		if bytes.Equal(k, b) {
			return true
		}
	}
	return false
}

// AgentSigMessage — the signed bytes: METHOD \n path \n ms \n hex sha256(body) [\n for].
func AgentSigMessage(method, path, ms string, body []byte, agentFor *string) []byte {
	h := sha256.Sum256(body)
	s := method + "\n" + path + "\n" + ms + "\n" + hex.EncodeToString(h[:])
	if agentFor != nil {
		s += "\n" + *agentFor
	}
	return []byte(s)
}

// AgentSig — agent-sig(key, method, path, body, header, now, window[, for]) → "" (ok) or the first word: no_signature,
// not_a_signature, out_of_window, bad_signature (also a GET with a body, a key of small order or not of the curve).
func AgentSig(key []byte, method, path string, body []byte, header string, now, window float64, agentFor *string) string {
	if header == "" {
		return "no_signature"
	}
	ms, sig64, ok := strings.Cut(header, ".")
	if !ok || !msRE.MatchString(ms) {
		return "not_a_signature"
	}
	sig, okSig := b64Canonical(sig64)
	if !okSig || len(sig) != ed25519.SignatureSize {
		return "not_a_signature"
	}
	t, _ := strconv.ParseFloat(ms, 64)
	if math.Abs(now-t/1000) > window {
		return "out_of_window"
	}
	if method == "GET" && len(body) != 0 || SmallOrderKey(key) {
		return "bad_signature"
	}
	if !ed25519.Verify(ed25519.PublicKey(key), AgentSigMessage(method, path, ms, body, agentFor), sig) {
		return "bad_signature"
	}
	return ""
}

// BatchKnockOK — the signature of a batch knock: Ed25519 of the batch key pub over UTF-8(JCS {purpose: "batch-knock",
// domain, name, key}); sig — 128 hex.
func BatchKnockOK(pub []byte, domain, name, key string, sigHex string) bool {
	sig, err := hex.DecodeString(sigHex)
	if err != nil || len(sig) != ed25519.SignatureSize || len(pub) != ed25519.PublicKeySize || SmallOrderKey(pub) {
		return false
	}
	msg := CanonicalJSON(map[string]any{"purpose": "batch-knock", "domain": domain, "name": name, "key": key})
	return ed25519.Verify(ed25519.PublicKey(pub), []byte(msg), sig)
}
