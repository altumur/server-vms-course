package contracts

import (
	"bytes"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/hex"
	"encoding/pem"
	"net"
	"strings"
	"time"
)

// Peer contract (common/contracts/peer.md): peer(chain, fingerprints, role, host, now) — a client about the server of
// another cluster, by the steps in order. The outcome is "ok" or the refusal word.

// RolePrefix — the SAN URI of a role: urn:w2c:role:<role>.
const RolePrefix = "urn:w2c:role:"

// HostIsIP — step 1: host is an IP address (v4 of four decimal parts, v6, also with a zone %<zone>); 127.1 is a name.
func HostIsIP(host string) bool {
	if strings.Contains(host, ":") {
		addr, _, _ := strings.Cut(host, "%")
		return net.ParseIP(addr) != nil
	}
	ip := net.ParseIP(host)
	return ip != nil && ip.To4() != nil
}

// parseChainElement — exactly one CERTIFICATE block, strict base64, the DER parses whole.
func parseChainElement(p string) (*x509.Certificate, bool) {
	b, rest := pem.Decode([]byte(p))
	if b == nil || b.Type != "CERTIFICATE" || len(bytes.TrimSpace(rest)) != 0 || len(b.Headers) != 0 {
		return nil, false
	}
	// strict base64: the body of the block re-encodes to the same characters
	body := string(p)
	i := strings.Index(body, "-----BEGIN CERTIFICATE-----")
	j := strings.Index(body, "-----END CERTIFICATE-----")
	if i < 0 || j < i {
		return nil, false
	}
	text := strings.Join(strings.Fields(body[i+len("-----BEGIN CERTIFICATE-----"):j]), "")
	if base64.StdEncoding.EncodeToString(b.Bytes) != text {
		return nil, false
	}
	c, err := x509.ParseCertificate(b.Bytes)
	return c, err == nil
}

// Fingerprint — sha256 hex of the DER of a centre (P/08.3 N1.6 fingerprint).
func Fingerprint(c *x509.Certificate) string {
	s := sha256.Sum256(c.Raw)
	return hex.EncodeToString(s[:])
}

// Peer — the steps 1–9: ip_address, bad_chain, foreign_ca, bad_chain (the path), expired, no_role, wrong_role,
// wrong_name, ok.
func Peer(chain, fingerprints []string, role, host string, now int64) string {
	if HostIsIP(host) {
		return "ip_address"
	}
	if len(chain) == 0 {
		return "bad_chain"
	}
	certs := make([]*x509.Certificate, len(chain))
	for i, p := range chain {
		c, ok := parseChainElement(p)
		if !ok {
			return "bad_chain"
		}
		certs[i] = c
	}
	known := map[string]bool{}
	for _, f := range fingerprints {
		known[strings.ToLower(f)] = true
	}
	anchor := -1
	for i := 1; i < len(certs); i++ {
		if certs[i].IsCA && known[Fingerprint(certs[i])] {
			anchor = i
			break
		}
	}
	if anchor < 0 {
		return "foreign_ca"
	}
	for i := 0; i < anchor; i++ {
		child, parent := certs[i], certs[i+1]
		if !parent.IsCA || !SigAllowed(child.SignatureAlgorithm, parent.PublicKey) ||
			parent.CheckSignature(child.SignatureAlgorithm, child.RawTBSCertificate, child.Signature) != nil {
			return "bad_chain"
		}
	}
	t := time.Unix(now, 0)
	for i := 0; i <= anchor; i++ {
		if t.Before(certs[i].NotBefore) || t.After(certs[i].NotAfter) {
			return "expired"
		}
	}
	leaf := certs[0]
	var roles []string
	for _, u := range leaf.URIs {
		if s := u.String(); strings.HasPrefix(s, RolePrefix) {
			roles = append(roles, s[len(RolePrefix):])
		}
	}
	if len(roles) != 1 || roles[0] == "" {
		return "no_role"
	}
	if roles[0] != role {
		return "wrong_role"
	}
	for _, d := range leaf.DNSNames {
		if d == host {
			return "ok"
		}
	}
	return "wrong_name"
}
