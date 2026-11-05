package contracts

import (
	"bytes"
	"net"
	"regexp"
	"strings"
)

// Role certificate contract, «The client of a door of its own cluster» loopback: the loopback threshold over the host
// notation of a URL, before DNS.

var urlHeadRE = regexp.MustCompile(`^[A-Za-z][A-Za-z0-9+.-]*://`)

// HostNotation — the host of a URL as written: after «//» and an optional userinfo@ up to «:port», «/» or the end (an
// IP literal v6 — with its brackets). A URL without a scheme and «//» or with an empty host — ErrRefuse (bad_url).
func HostNotation(url string) (string, error) {
	head := urlHeadRE.FindString(url)
	if head == "" {
		return "", ErrRefuse
	}
	rest := url[len(head):]
	if i := strings.IndexAny(rest, "/?#"); i >= 0 {
		rest = rest[:i]
	}
	if i := strings.LastIndex(rest, "@"); i >= 0 {
		rest = rest[i+1:]
	}
	host := rest
	if strings.HasPrefix(rest, "[") {
		e := strings.IndexByte(rest, ']')
		if e < 0 {
			return "", ErrRefuse
		}
		host = rest[:e+1]
	} else if i := strings.IndexByte(rest, ':'); i >= 0 {
		host = rest[:i]
	}
	if host == "" || host == "[]" {
		return "", ErrRefuse
	}
	return host, nil
}

// IPLiteral — the host notation is an IP address (step 1 of peer): v4 of four decimal parts 0–255 without leading
// zeros, or v6 in brackets, also with a zone «%25<zone>» (zone — true).
func IPLiteral(host string) (ip net.IP, zone bool, ok bool) {
	if strings.HasPrefix(host, "[") && strings.HasSuffix(host, "]") {
		addr := host[1 : len(host)-1]
		if i := strings.Index(addr, "%25"); i >= 0 {
			if i+3 == len(addr) {
				return nil, false, false
			}
			addr, zone = addr[:i], true
		}
		if !strings.Contains(addr, ":") {
			return nil, false, false
		}
		ip = net.ParseIP(addr)
		return ip, zone, ip != nil
	}
	if strings.Contains(host, ":") {
		return nil, false, false
	}
	ip = net.ParseIP(host)
	return ip, false, ip != nil && ip.To4() != nil
}

// LoopbackKind — the loopback threshold {url} → "loopback" (v4 of four decimal parts with the first 127, or v6 with the
// value ::1 without a zone), "ip" (another IP literal of step 1 of peer) or "name"; a URL out of form — ErrRefuse.
func LoopbackKind(url string) (string, error) {
	host, err := HostNotation(url)
	if err != nil {
		return "", err
	}
	ip, zone, ok := IPLiteral(host)
	switch {
	case !ok:
		return "name", nil
	case strings.HasPrefix(host, "["):
		if !zone && bytes.Equal(ip.To16(), net.IPv6loopback) {
			return "loopback", nil
		}
		return "ip", nil
	case ip.To4()[0] == 127:
		return "loopback", nil
	}
	return "ip", nil
}
