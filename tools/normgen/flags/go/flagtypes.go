package flags

// Handwritten closed flag-type vocabulary from daemon-flags.tsv's header (ADR-0125 generator 3).
// gen_flags.py copies it beside flags.go. Each type parses an argv word into a CEL value for required/bad
// f[...] expressions and a typed Flags field.
//
// CEL path/dir/file/addr/id/duration/list values retain their source strings; int, bytes and integer enums
// use int64; other enums use strings; bool uses true.

import (
	"errors"
	"net"
	"regexp"
	"strconv"
	"strings"
	"time"
)

// Member is one id@addr or id@addr/addr list element, with addresses in source order.
type Member struct {
	ID    string
	Addrs []string
}

var memberID = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$`) // P/01.3 N2:1..128 ASCII characters, starting with a letter or digit.

func valNonEmpty(raw string) (string, error) {
	if raw == "" {
		return "", errors.New("empty value")
	}
	return raw, nil
}

// valAddr follows P/01.3-R031: nonempty hostname, IPv4 or bracketed IPv6; decimal port1..65535
// without leading zeros.
func valAddr(raw string) (string, error) {
	host, port, err := net.SplitHostPort(raw)
	if err != nil {
		return "", errors.New("not host:port")
	}
	if !digits(port) || port[0] == '0' || len(port) > 5 {
		return "", errors.New("the port is not a decimal number 1–65535")
	}
	if n, _ := strconv.Atoi(port); n > 65535 {
		return "", errors.New("the port is above 65535")
	}
	switch {
	case host == "":
		return "", errors.New("an empty host")
	case strings.HasPrefix(raw, "["):
		if ip := net.ParseIP(host); ip == nil || !strings.Contains(host, ":") {
			return "", errors.New("[…] is not an IPv6 address")
		}
	case ipv4ish.MatchString(host):
		if ip := net.ParseIP(host); ip == nil || ip.To4() == nil {
			return "", errors.New("not an IPv4 address")
		}
	case !hostName.MatchString(host):
		return "", errors.New("the host is not a name, IPv4 or [IPv6]")
	}
	return raw, nil
}

var (
	ipv4ish  = regexp.MustCompile(`^[0-9.]+$`)
	hostName = regexp.MustCompile(`^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?)*$`)
	duration = regexp.MustCompile(`^([1-9][0-9]*)(ms|s|m|h)$`)
)

func valID(raw string) (string, error) {
	if !memberID.MatchString(raw) {
		return "", errors.New("not a member id (1–128 ASCII: a letter or a digit, then letters, digits, _ . -)")
	}
	return raw, nil
}

// typeInt parses optional-minus decimal integers without leading zeros within min/max; hasMax enables max.
func valInt(raw string, min, max int64, hasMax bool) (int64, error) {
	body := strings.TrimPrefix(raw, "-")
	if !digits(body) || (len(body) > 1 && body[0] == '0') {
		return 0, errors.New("not a decimal integer")
	}
	n, err := strconv.ParseInt(raw, 10, 64)
	if err != nil {
		return 0, errors.New("the integer is out of int64")
	}
	if n < min || (hasMax && n > max) {
		return 0, errors.New("the integer is out of range")
	}
	return n, nil
}

// typeBytes implements bytes:>0:positive decimal byte count without suffixes.
func valBytes(raw string) (int64, error) {
	n, err := valInt(raw, 1, 0, false)
	if err != nil {
		return 0, errors.New("not an integer of bytes > 0")
	}
	return n, nil
}

// valDuration accepts positive [1-9][0-9]*(ms|s|m|h), such as5s/250ms, not1h30m, 1.5s or microseconds.
func valDuration(raw string) (time.Duration, error) {
	m := duration.FindStringSubmatch(raw)
	if m == nil {
		return 0, errors.New("not a duration <integer>(ms|s|m|h) > 0")
	}
	n, err := strconv.ParseInt(m[1], 10, 64)
	unit := map[string]time.Duration{"ms": time.Millisecond, "s": time.Second, "m": time.Minute, "h": time.Hour}[m[2]]
	if err != nil || n > int64((1<<63-1)/unit) {
		return 0, errors.New("the duration is out of range")
	}
	return time.Duration(n) * unit, nil
}

// typeEnum accepts a listed value; ints means every choice is integral and CEL receives int64.
func valEnum(raw string, values []string, ints bool) (any, error) {
	for _, v := range values {
		if raw == v {
			if ints {
				n, _ := strconv.ParseInt(v, 10, 64)
				return n, nil
			}
			return raw, nil
		}
	}
	return nil, errors.New("not one of " + strings.Join(values, " | "))
}

// typeList parses a nonempty comma-separated list:id@addr(addrs1) or id@addr/addr(addrs2), with complete items.
func valList(raw string, addrs int) ([]Member, error) {
	if raw == "" {
		return nil, errors.New("an empty list")
	}
	var out []Member
	for _, el := range strings.Split(raw, ",") {
		id, rest, ok := strings.Cut(el, "@")
		if !ok {
			return nil, errors.New("the element " + strconv.Quote(el) + " is not id@address")
		}
		if _, err := valID(id); err != nil {
			return nil, errors.New("the element " + strconv.Quote(el) + ": " + err.Error())
		}
		parts := strings.Split(rest, "/")
		if len(parts) != addrs {
			return nil, errors.New("the element " + strconv.Quote(el) + " has not " + strconv.Itoa(addrs) + " address(es)")
		}
		for _, a := range parts {
			if _, err := valAddr(a); err != nil {
				return nil, errors.New("the element " + strconv.Quote(el) + ": " + err.Error())
			}
		}
		out = append(out, Member{ID: id, Addrs: parts})
	}
	return out, nil
}

func digits(s string) bool {
	if s == "" {
		return false
	}
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return false
		}
	}
	return true
}
