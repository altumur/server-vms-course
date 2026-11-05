package contracts

import "sort"

// NFKC of Unicode 15.0.0 (UAX #15) over the tables of nfkc_tables.go; Hangul syllables are algorithmic.

const (
	hangulSBase, hangulLBase, hangulVBase, hangulTBase = 0xAC00, 0x1100, 0x1161, 0x11A7
	hangulLCount, hangulVCount, hangulTCount           = 19, 21, 28
	hangulNCount                                       = hangulVCount * hangulTCount
	hangulSCount                                       = hangulLCount * hangulNCount
)

func nfkdRune(r rune, out []rune) []rune {
	if s := r - hangulSBase; s >= 0 && s < hangulSCount {
		out = append(out, hangulLBase+s/hangulNCount, hangulVBase+(s%hangulNCount)/hangulTCount)
		if t := s % hangulTCount; t != 0 {
			out = append(out, hangulTBase+t)
		}
		return out
	}
	if d, ok := nfkdTable[r]; ok {
		return append(out, []rune(d)...)
	}
	return append(out, r)
}

// NFKC — the compatibility composition of s.
func NFKC(s string) string {
	var d []rune
	for _, r := range s {
		d = nfkdRune(r, d)
	}
	// canonical ordering: a stable sort of each run of non-starters by class
	for i := 0; i < len(d); {
		if cccTable[d[i]] == 0 {
			i++
			continue
		}
		j := i
		for j < len(d) && cccTable[d[j]] != 0 {
			j++
		}
		run := d[i:j]
		sort.SliceStable(run, func(a, b int) bool { return cccTable[run[a]] < cccTable[run[b]] })
		i = j
	}
	// canonical composition
	out := make([]rune, 0, len(d))
	starter := -1
	var last uint8
	for _, r := range d {
		c := cccTable[r]
		if starter >= 0 && (len(out)-1 == starter || (last != 0 && last < c)) {
			if p, ok := compose(out[starter], r); ok {
				out[starter] = p
				continue
			}
		}
		if c == 0 {
			starter = len(out)
			last = 0
		} else {
			last = c
		}
		out = append(out, r)
	}
	return string(out)
}

func compose(a, b rune) (rune, bool) {
	if l := a - hangulLBase; l >= 0 && l < hangulLCount {
		if v := b - hangulVBase; v >= 0 && v < hangulVCount {
			return hangulSBase + (l*hangulVCount+v)*hangulTCount, true
		}
	}
	if s := a - hangulSBase; s >= 0 && s < hangulSCount && s%hangulTCount == 0 {
		if t := b - hangulTBase; t > 0 && t < hangulTCount {
			return a + t, true
		}
	}
	p, ok := compTable[[2]rune{a, b}]
	return p, ok
}
