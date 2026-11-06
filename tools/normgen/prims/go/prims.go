package checks

// Handwritten #fn check primitives (ADR-0120, item 2(a)), copied by the generator.
// prim+CamelCase(fn) returns (value, error);an error denotes a CEL error.
// Arguments already match declared #fn types. Missing primitives such as allowed are Fns callbacks.

import (
	"errors"
	"math"
	"net"
	"strings"
)

// primKeyOk checks N1 row.key:nonempty, no leading slash or '..' segment, at most1024 UTF-8 bytes.
func primKeyOk(k string) (bool, error) {
	if k == "" || strings.HasPrefix(k, "/") || len(k) > 1024 {
		return false, nil
	}
	for _, seg := range strings.Split(k, "/") {
		if seg == ".." {
			return false, nil
		}
	}
	return true, nil
}

// primWeight sums all item name/value UTF-8 byte lengths;non-strings error.
func primWeight(items map[string]any) (int64, error) {
	var total int64
	for name, value := range items {
		s, ok := value.(string)
		if !ok {
			return 0, errors.New("weight: items is not an object of strings")
		}
		total += int64(len(name) + len(s))
	}
	return total, nil
}

// primFinite checks binary64 finiteness;1e400 is not finite.
func primFinite(x float64) (bool, error) {
	return !math.IsInf(x, 0) && !math.IsNaN(x), nil
}

// primLoopback accepts host:port on127/8, ::1 or localhost (ADR-0125 addendum 2, item 4).
// Mapped IPv4 counts as IPv4;zones and other names are not loopback.Invalid host:port is a CEL error.
func primLoopback(addr string) (bool, error) {
	host, _, err := net.SplitHostPort(addr)
	if err != nil {
		return false, errors.New("loopback: not host:port")
	}
	if strings.EqualFold(host, "localhost") {
		return true, nil
	}
	ip := net.ParseIP(host)
	if ip == nil {
		return false, nil
	}
	if v4 := ip.To4(); v4 != nil {
		return v4[0] == 127, nil
	}
	return ip.Equal(net.IPv6loopback), nil
}
