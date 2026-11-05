package contracts

import (
	"bytes"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rsa"
	"crypto/x509"
	"encoding/asn1"
	"encoding/pem"
	"time"
)

// Role certificate contract, revoke crl (common/contracts/role-certificate.md): crl.pem — one or two blocks X509 CRL
// v2, one per center of ca.pem and ca.next.pem, each signed by its center with a signature of the closed list sig.

// CRLRead — the serials revoked for the leaves of each center (canonical, ascending; [] — no block of the center;
// CANext nil — there is no ca.next.pem) and the centers whose block is stale ("ca", "ca_next"): no nextUpdate, now
// later than nextUpdate or thisUpdate later than now by more than 60 s — a log line and a count, the list is in force.
type CRLRead struct {
	CA     []string
	CANext []string
	Stale  []string
}

// ClockSkew — the tolerance of thisUpdate ahead of now, seconds.
const ClockSkew = 60

var (
	oidCRLNumber      = asn1.ObjectIdentifier{2, 5, 29, 20}
	oidDeltaCRL       = asn1.ObjectIdentifier{2, 5, 29, 27}
	oidIssuingDP      = asn1.ObjectIdentifier{2, 5, 29, 28}
	oidAuthorityKeyID = asn1.ObjectIdentifier{2, 5, 29, 35}
	oidReasonCode     = asn1.ObjectIdentifier{2, 5, 29, 21}
	oidInvalidityDate = asn1.ObjectIdentifier{2, 5, 29, 24}
)

// SigAllowed — the closed list sig for a signature by a center key: ECDSA P-256 and P-384 with SHA-256 or SHA-384,
// RSA ≥ 2048 bits PKCS#1 v1.5 and PSS with SHA-256 or SHA-384, Ed25519.
func SigAllowed(alg x509.SignatureAlgorithm, key any) bool {
	switch k := key.(type) {
	case *ecdsa.PublicKey:
		if k.Curve != elliptic.P256() && k.Curve != elliptic.P384() {
			return false
		}
		return alg == x509.ECDSAWithSHA256 || alg == x509.ECDSAWithSHA384
	case *rsa.PublicKey:
		if k.N.BitLen() < 2048 {
			return false
		}
		switch alg {
		case x509.SHA256WithRSA, x509.SHA384WithRSA, x509.SHA256WithRSAPSS, x509.SHA384WithRSAPSS:
			return true
		}
		return false
	}
	return alg == x509.PureEd25519
}

func parseCenter(p []byte) (*x509.Certificate, error) {
	b, rest := pem.Decode(p)
	if b == nil || b.Type != "CERTIFICATE" || len(bytes.TrimSpace(rest)) != 0 {
		return nil, ErrRefuse
	}
	return x509.ParseCertificate(b.Bytes)
}

// crlV2 — the TBS of the CRL carries version v2 (INTEGER 1).
func crlV2(tbs []byte) bool {
	var seq asn1.RawValue
	if _, err := asn1.Unmarshal(tbs, &seq); err != nil || seq.Tag != asn1.TagSequence {
		return false
	}
	var v int
	_, err := asn1.Unmarshal(seq.Bytes, &v)
	return err == nil && v == 1
}

// idpRestricts — issuingDistributionPoint with anything beyond distributionPoint (onlyContains…, onlySomeReasons,
// indirectCRL) restricts the scope or makes the CRL indirect.
func idpRestricts(v []byte) bool {
	var seq asn1.RawValue
	if rest, err := asn1.Unmarshal(v, &seq); err != nil || len(rest) != 0 || seq.Tag != asn1.TagSequence {
		return true
	}
	in := seq.Bytes
	for len(in) > 0 {
		var f asn1.RawValue
		rest, err := asn1.Unmarshal(in, &f)
		if err != nil || f.Class != asn1.ClassContextSpecific || f.Tag != 0 {
			return true
		}
		in = rest
	}
	return false
}

func extensionsOK(rl *x509.RevocationList) bool {
	for _, e := range rl.Extensions {
		switch {
		case e.Id.Equal(oidDeltaCRL):
			return false
		case e.Id.Equal(oidIssuingDP):
			if idpRestricts(e.Value) {
				return false
			}
		case e.Id.Equal(oidCRLNumber), e.Id.Equal(oidAuthorityKeyID):
		default:
			if e.Critical {
				return false
			}
		}
	}
	for _, r := range rl.RevokedCertificateEntries {
		for _, e := range r.Extensions {
			if e.Critical && !e.Id.Equal(oidReasonCode) && !e.Id.Equal(oidInvalidityDate) {
				return false // certificateIssuer and the like: an indirect CRL
			}
		}
	}
	return true
}

// ReadCRL — crl.pem by the centers ca.pem and ca.next.pem (caNext nil — none) at Unix time now. A defect of form, of
// signature (an issuer not of the centers, a foreign signature, a signature outside sig), an extra block of a center,
// delta CRL, indirect CRL, a scope restricted by issuingDistributionPoint, an unknown critical extension — ErrRefuse
// (the file is invalid, the refusal is closed). Dates give no refusal: they go to Stale.
func ReadCRL(caPEM, caNextPEM, crlPEM []byte, now int64) (CRLRead, error) {
	ca, err := parseCenter(caPEM)
	if err != nil {
		return CRLRead{}, ErrRefuse
	}
	centers := []*x509.Certificate{ca}
	names := []string{"ca", "ca_next"}
	if caNextPEM != nil {
		next, err := parseCenter(caNextPEM)
		if err != nil {
			return CRLRead{}, ErrRefuse
		}
		centers = append(centers, next)
	}
	revoked := make([][]string, len(centers))
	seen := make([]bool, len(centers))
	stale := make([]bool, len(centers))
	rest := crlPEM
	blocks := 0
	for len(bytes.TrimSpace(rest)) > 0 {
		var b *pem.Block
		b, rest = pem.Decode(rest)
		if b == nil || b.Type != "X509 CRL" {
			return CRLRead{}, ErrRefuse
		}
		blocks++
		rl, err := x509.ParseRevocationList(b.Bytes)
		if err != nil || !crlV2(rl.RawTBSRevocationList) || !extensionsOK(rl) {
			return CRLRead{}, ErrRefuse
		}
		at := -1
		for i, c := range centers {
			if bytes.Equal(rl.RawIssuer, c.RawSubject) && SigAllowed(rl.SignatureAlgorithm, c.PublicKey) &&
				rl.CheckSignatureFrom(c) == nil {
				at = i
				break
			}
		}
		if at < 0 || seen[at] {
			return CRLRead{}, ErrRefuse
		}
		seen[at] = true
		for _, r := range rl.RevokedCertificateEntries {
			if r.SerialNumber == nil || r.SerialNumber.Sign() < 0 {
				return CRLRead{}, ErrRefuse
			}
			revoked[at] = append(revoked[at], r.SerialNumber.Text(16))
		}
		t := time.Unix(now, 0)
		stale[at] = rl.NextUpdate.IsZero() || t.After(rl.NextUpdate) || rl.ThisUpdate.Unix() > now+ClockSkew
	}
	if blocks == 0 {
		return CRLRead{}, ErrRefuse
	}
	out := CRLRead{CA: SortSerials(revoked[0]), Stale: []string{}}
	if len(centers) > 1 {
		out.CANext = SortSerials(revoked[1])
	}
	for i := range centers {
		if stale[i] {
			out.Stale = append(out.Stale, names[i])
		}
	}
	return out, nil
}
