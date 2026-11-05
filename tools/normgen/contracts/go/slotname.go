package contracts

import (
	"math/big"
	"regexp"
	"sort"
	"strings"
)

// Slot name contract (common/contracts/slot-name.md): name = <prefix>-<suffix>; «by name» — ASCII bytes.

var serverName = regexp.MustCompile(`^[a-z0-9]+(-[a-z0-9]+)*$`)

func digits(s string) bool {
	if s == "" {
		return false
	}
	for _, c := range s {
		if c < '0' || c > '9' {
			return false
		}
	}
	return true
}

func numeric(prefix, name string) (*big.Int, bool) {
	suf, ok := strings.CutPrefix(name, prefix+"-")
	if !ok || !digits(suf) {
		return nil, false
	}
	n, _ := new(big.Int).SetString(suf, 10)
	return n, true
}

// SlotOrder — the slot order: the names with an all-digit suffix by its number (on equality by name), then the
// others by name.
func SlotOrder(prefix string, names []string) []string {
	out := append([]string{}, names...)
	sort.SliceStable(out, func(i, j int) bool {
		a, an := numeric(prefix, out[i])
		b, bn := numeric(prefix, out[j])
		switch {
		case an && bn:
			if c := a.Cmp(b); c != 0 {
				return c < 0
			}
			return out[i] < out[j]
		case an != bn:
			return an
		}
		return out[i] < out[j]
	})
	return out
}

// NextName — <prefix>-<max+1> over the all-digit suffixes (max = 0 if none), without leading zeros and overflow.
func NextName(prefix string, names []string) string {
	max := new(big.Int)
	for _, n := range names {
		if v, ok := numeric(prefix, n); ok && v.Cmp(max) > 0 {
			max = v
		}
	}
	return prefix + "-" + new(big.Int).Add(max, big.NewInt(1)).String()
}

// RoleOf — the role process name <prefix>-<s>-<N> against the server of its heartbeat (nil — no heartbeat or it does
// not read): (s, N, true) when N is a decimal ≥ 1 without leading zeros, s by the SERVER_NAME grammar and s equals
// the server; otherwise not a role process.
func RoleOf(prefix, name string, server *string) (string, string, bool) {
	rest, ok := strings.CutPrefix(name, prefix+"-")
	if !ok {
		return "", "", false
	}
	i := strings.LastIndexByte(rest, '-')
	if i <= 0 {
		return "", "", false
	}
	s, n := rest[:i], rest[i+1:]
	if !digits(n) || n[0] == '0' || !serverName.MatchString(s) || server == nil || *server != s {
		return "", "", false
	}
	return s, n, true
}
