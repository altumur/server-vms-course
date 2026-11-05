package contracts

import (
	"strings"
	"unicode"
)

// Instance contract (common/contracts/instance.md): instance = <box>:<pid>:<6 hex>; the box is the part up to the
// first «:».

// ValidPathComponent — the instance profile of the event journal contract («The event id and the writer instance»):
// one path component — not «.»/«..», no «/», «\», «|», «"», comma, Cc/Zl/Zp.
func ValidPathComponent(s string) bool {
	if s == "" || s == "." || s == ".." {
		return false
	}
	for _, r := range s {
		if strings.ContainsRune(`/\|",`, r) || unicode.Is(unicode.Cc, r) || unicode.Is(unicode.Zl, r) ||
			unicode.Is(unicode.Zp, r) {
			return false
		}
	}
	return true
}

// ValidBox — the box grammar: non-empty, without «:», a valid path component.
func ValidBox(s string) bool { return s != "" && !strings.Contains(s, ":") && ValidPathComponent(s) }

// GivenInstance — INSTANCE_ID as given (the form «given»): <box>:<pid>:<hex6>, pid ASCII digits not all zeros
// (leading zeros admitted), hex [0-9a-fA-F]{6}; used byte for byte. Otherwise ErrRefuse (a start refusal, code 2).
func GivenInstance(s string) (string, error) {
	parts := strings.Split(s, ":")
	if len(parts) != 3 || !ValidBox(parts[0]) || !ValidPathComponent(s) {
		return "", ErrRefuse
	}
	pid, hex := parts[1], parts[2]
	if pid == "" || strings.Trim(pid, "0") == "" {
		return "", ErrRefuse
	}
	for _, c := range pid {
		if c < '0' || c > '9' {
			return "", ErrRefuse
		}
	}
	if len(hex) != 6 {
		return "", ErrRefuse
	}
	for _, c := range hex {
		if !strings.ContainsRune("0123456789abcdefABCDEF", c) {
			return "", ErrRefuse
		}
	}
	return s, nil
}

// BoxSources — the inputs of the box resolver: BOX_ID (nil — not set), the content of /etc/machine-id (Missing — no
// file, Error — a read error), the hostname of the system.
type BoxSources struct {
	BoxID     *string
	MachineID string
	Missing   bool
	Error     bool
	Hostname  string
}

func trimSource(s string) string {
	if i := strings.IndexByte(s, '\n'); i >= 0 {
		s = s[:i] // the first line, then trimming SP, TAB, CR, LF at both ends
	}
	return strings.Trim(s, " \t\r\n")
}

// ResolveBox — the box and its source (BOX_ID, machine-id, hostname) by the order of the contract («sources»):
// BOX_ID non-empty — it (not by the grammar — ErrRefuse); machine-id — the first line trimmed, unfit — the next
// source; the hostname trimmed, unfit — ErrRefuse («no box name»).
func ResolveBox(s BoxSources) (box, source string, err error) {
	if s.BoxID != nil && *s.BoxID != "" {
		if !ValidBox(*s.BoxID) {
			return "", "", ErrRefuse
		}
		return *s.BoxID, "BOX_ID", nil
	}
	if !s.Missing && !s.Error {
		if m := trimSource(s.MachineID); m != "" && ValidBox(m) {
			return m, "machine-id", nil
		}
	}
	if h := trimSource(s.Hostname); h != "" && ValidBox(h) {
		return h, "hostname", nil
	}
	return "", "", ErrRefuse
}
