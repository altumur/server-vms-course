package contracts

import (
	"regexp"
	"sort"
	"strings"
	"unicode/utf8"
)

// Log mask contract (common/contracts/log-mask.md): mask(text, catalogue) of free text as a whole, and the mask at
// the input mask_in.

var authHeaderRE = regexp.MustCompile(`(?i)(?:proxy-)?authorization[ \t]*:[ \t]*(?:basic|bearer)[ \t]+`)

var jsonPairRE = regexp.MustCompile(`"((?:[^"\\]|\\.)*)"[ \t]*:[ \t]*`)

var jsonScalarRE = regexp.MustCompile(`^(?:"(?:[^"\\]|\\.)*"|-?[0-9][0-9.eE+-]*|true|false|null)`)

// MaskLog — mask(text, catalogue): the credentials of the headers Authorization and Proxy-Authorization (Basic,
// Bearer), the values of pairs with a secret name (name=value and a JSON pair) and the passwords of addresses are
// replaced by "***"; the rest stays byte for byte. catalogue — the united rule of the url fields of the process
// (empty — common_words and the address contract only).
func MaskLog(text string, catalogue URLRule) string {
	rd := &reader{catalogue: catalogue}
	s := &scan{r: rd, rule: &catalogue, t: text}
	// headers: the credentials to the first white space or the end of the line
	for _, m := range authHeaderRE.FindAllStringIndex(text, -1) {
		e := m[1]
		for e < len(text) {
			r, n := utf8.DecodeRuneInString(text[e:])
			if isSpace(r) {
				break
			}
			e += n
		}
		s.add(kindSecret, m[1], e)
	}
	// JSON pairs: the scalar of the value
	jsonValues := map[int]int{}
	for _, m := range jsonPairRE.FindAllStringSubmatchIndex(text, -1) {
		name := text[m[2]:m[3]]
		v := jsonScalarRE.FindString(text[m[1]:])
		if v == "" || v == `""` || nameKind(name, &catalogue) != kindSecret {
			continue
		}
		jsonValues[m[1]] = m[1] + len(v)
	}
	// addresses of free text: from the scheme to a space, a quote, «\», «<» or «>»
	var addrs [][2]int
	for i := 0; i < len(text); {
		p := strings.Index(text[i:], "://")
		if p < 0 {
			break
		}
		p += i
		a := p
		for a > 0 && schemeChar(text[a-1]) {
			a--
		}
		for a < p && !isLetter(text[a]) {
			a++
		}
		e := p + 3
		for e < len(text) {
			r, n := utf8.DecodeRuneInString(text[e:])
			if isSpace(r) || r == '"' || r == '\\' || r == '<' || r == '>' {
				break
			}
			e += n
		}
		if a < p {
			addrs = append(addrs, [2]int{a, e})
			s.address(a, e)
		}
		i = e
	}
	inAddr := func(i int) bool {
		for _, ad := range addrs {
			if i >= ad[0] && i < ad[1] {
				return true
			}
		}
		return false
	}
	s.textPairs(0, len(text), inAddr)
	return maskWith(text, s.out, jsonValues)
}

// maskWith — the stretches of passwords merged (overlapping and adjacent — one mask); a JSON value becomes the string
// "***" (a scalar is one token of JSON, the character after it stays).
func maskWith(text string, fs []finding, jsonValues map[int]int) string {
	type stretch struct{ a, b int }
	var st []stretch
	for _, f := range fs {
		if f.kind == kindSecret && f.b > f.a {
			st = append(st, stretch{f.a, f.b})
		}
	}
	for a, b := range jsonValues {
		st = append(st, stretch{a, b})
	}
	sort.Slice(st, func(i, j int) bool { return st[i].a < st[j].a || st[i].a == st[j].a && st[i].b > st[j].b })
	var out strings.Builder
	at := 0
	for i := 0; i < len(st); {
		g := st[i]
		for i++; i < len(st) && st[i].a <= g.b; i++ {
			if st[i].b > g.b {
				g.b = st[i].b
			}
		}
		out.WriteString(text[at:g.a])
		if b, ok := jsonValues[g.a]; ok && b == g.b {
			out.WriteString(`"` + Mask + `"`)
		} else {
			out.WriteString(Mask)
		}
		at = g.b
	}
	out.WriteString(text[at:])
	return out.String()
}

// maskInSet — the characters of a display mask at the input.
const maskInSet = "*＊∗⁎✱•●∙·⋅◦○⚫"

// MaskIn — mask_in: the value without white space at its edges is at least three characters, all of the set.
func MaskIn(value string) bool {
	v := strings.TrimFunc(value, isSpace)
	n := 0
	for _, r := range v {
		if !strings.ContainsRune(maskInSet, r) {
			return false
		}
		n++
	}
	return n >= 3
}
