package contracts

import (
	"strings"
	"unicode"
	"unicode/utf8"
)

// The address contract (common/contracts/url-credentials.md, A1–A15): where the login and the password are in a url
// value — the display (A14) and the refusal (A15) — and the reading of addresses in free text for the log mask
// (common/contracts/log-mask.md).

// CommonWords — the common vocabulary common_words.
var CommonWords = []string{"password", "passwd", "pass", "pwd", "secret", "token", "key", "credential", "credentials",
	"psk", "privkey", "apikey", "=auth", "=pin"}

// Mask — the display mask.
const Mask = "***"

// MaxNesting — the deepest level of a nested address that is read (A8).
const MaxNesting = 3

const (
	kindNone = iota
	kindLogin
	kindSecret
)

type finding struct {
	kind int
	a, b int // the stretch in the written text
}

// isSpace — white_space of the person name contract (White_Space of Unicode 15.0.0).
func isSpace(r rune) bool { return unicode.Is(unicode.White_Space, r) }

// --- A4: the name of a pair ---

var invisible = map[rune]bool{0xAD: true, 0x34F: true, 0x180E: true, 0xFEFF: true}

func init() {
	for r := rune(0x200B); r <= 0x200F; r++ {
		invisible[r] = true
	}
	for r := rune(0x2060); r <= 0x2064; r++ {
		invisible[r] = true
	}
}

func isHex(c byte) bool {
	return c >= '0' && c <= '9' || c >= 'a' && c <= 'f' || c >= 'A' && c <= 'F'
}

func unhex(c byte) byte {
	switch {
	case c >= '0' && c <= '9':
		return c - '0'
	case c >= 'a' && c <= 'f':
		return c - 'a' + 10
	}
	return c - 'A' + 10
}

// decodeOnce — one pass of %XX; a «%» without two hex characters stays.
func decodeOnce(s string) string {
	if !strings.Contains(s, "%") {
		return s
	}
	var b strings.Builder
	for i := 0; i < len(s); i++ {
		if s[i] == '%' && i+2 < len(s) && isHex(s[i+1]) && isHex(s[i+2]) {
			b.WriteByte(unhex(s[i+1])<<4 | unhex(s[i+2]))
			i += 2
			continue
		}
		b.WriteByte(s[i])
	}
	return b.String()
}

// DecodeFix — %XX decoded to a fixed point (the bytes as they are).
func DecodeFix(s string) string {
	for {
		d := decodeOnce(s)
		if d == s {
			return s
		}
		s = d
	}
}

// decodeMap — the fixed point with the written stretch of every decoded byte.
func decodeMap(s string, base int) (string, []int, []int) {
	st, en := make([]int, len(s)), make([]int, len(s))
	for i := range s {
		st[i], en[i] = base+i, base+i+1
	}
	for {
		var b []byte
		var ns, ne []int
		changed := false
		for i := 0; i < len(s); i++ {
			if s[i] == '%' && i+2 < len(s) && isHex(s[i+1]) && isHex(s[i+2]) {
				b = append(b, unhex(s[i+1])<<4|unhex(s[i+2]))
				ns, ne = append(ns, st[i]), append(ne, en[i+2])
				i += 2
				changed = true
				continue
			}
			b = append(b, s[i])
			ns, ne = append(ns, st[i]), append(ne, en[i])
		}
		if !changed {
			return s, st, en
		}
		s, st, en = string(b), ns, ne
	}
}

type pairName struct {
	whole string
	words []string
	head  string
}

// readName — A4 steps 1–6.
func readName(raw string) pairName {
	s := strings.ToValidUTF8(DecodeFix(raw), "�")
	s = NFKC(s)
	s = strings.Map(func(r rune) rune {
		if invisible[r] {
			return -1
		}
		return r
	}, s)
	if i := strings.LastIndex(s, "."); i >= 0 {
		s = s[i+1:]
	}
	sep := func(r rune) bool { return r == '_' || r == '-' || r == '+' || r == ' ' }
	whole := strings.Map(func(r rune) rune {
		if sep(r) {
			return -1
		}
		return r
	}, strings.ToLower(s))
	var words []string
	for _, chunk := range strings.FieldsFunc(s, sep) {
		rs := []rune(chunk)
		start := 0
		for i := 1; i < len(rs); i++ {
			prev, cur := rs[i-1], rs[i]
			if unicode.IsUpper(cur) && (unicode.IsLower(prev) || unicode.IsDigit(prev)) ||
				unicode.IsUpper(cur) && unicode.IsUpper(prev) && i+1 < len(rs) && unicode.IsLower(rs[i+1]) {
				words = append(words, string(rs[start:i]))
				start = i
			}
		}
		words = append(words, string(rs[start:]))
	}
	var out []string
	for _, w := range words {
		w = strings.TrimRightFunc(strings.ToLower(w), unicode.IsDigit)
		if w != "" {
			out = append(out, w)
		}
	}
	n := pairName{whole: whole, words: out}
	if len(out) > 0 {
		n.head = out[len(out)-1]
	}
	return n
}

// matchPattern — A5.
func (n pairName) match(p string) bool {
	p = strings.ToLower(p)
	switch {
	case strings.HasPrefix(p, "="):
		return n.whole == p[1:]
	case strings.HasPrefix(p, "*"):
		return strings.HasSuffix(n.head, p[1:])
	case strings.HasSuffix(p, "*"):
		for _, w := range n.words {
			if strings.HasPrefix(w, p[:len(p)-1]) {
				return true
			}
		}
		return false
	}
	return n.whole == p || n.head == p
}

func contains(xs []string, x string) bool {
	for _, y := range xs {
		if y == x {
			return true
		}
	}
	return false
}

// nameKind — A5: a secret, then a login, otherwise nothing.
func nameKind(raw string, rule *URLRule) int {
	n := readName(raw)
	for _, w := range CommonWords {
		if n.match(w) {
			return kindSecret
		}
	}
	for _, p := range rule.Params {
		for _, w := range p.Param {
			if !contains(p.Login, w) && n.match(w) {
				return kindSecret
			}
		}
	}
	for _, p := range rule.Params {
		for _, w := range p.Login {
			if n.match(w) {
				return kindLogin
			}
		}
	}
	return kindNone
}

// --- the reader ---

type reader struct {
	catalogue URLRule // the united rule of the catalogue (nested addresses)
}

type scan struct {
	r     *reader
	rule  *URLRule
	t     string
	level int
	out   []finding
	nest  []finding // the stretches of nested addresses (A8, A9)
}

func (s *scan) add(kind, a, b int) {
	if kind != kindNone {
		s.out = append(s.out, finding{kind, a, b})
	}
}

func (s *scan) addNested(kind, a, b int) {
	s.add(kind, a, b)
	if kind != kindNone {
		s.nest = append(s.nest, finding{kind, a, b})
	}
}

func strongest(fs []finding) int {
	k := kindNone
	for _, f := range fs {
		if f.kind > k {
			k = f.kind
		}
	}
	return k
}

// nestedKind — the strongest kind of a nested address (decoded text from its scheme) at level+1.
func (s *scan) nestedKind(decoded string) int {
	if s.level+1 > MaxNesting {
		return kindSecret
	}
	p := strings.Index(decoded, "://")
	if p < 0 {
		return kindNone
	}
	a := p
	for a > 0 && schemeChar(decoded[a-1]) {
		a--
	}
	for a < p && !isLetter(decoded[a]) {
		a++
	}
	u := Union(*s.rule, s.r.catalogue)
	sub := &scan{r: s.r, rule: &u, t: decoded[a:], level: s.level + 1}
	sub.address(0, len(sub.t))
	return strongest(sub.out)
}

func isLetter(c byte) bool { return c >= 'a' && c <= 'z' || c >= 'A' && c <= 'Z' }

func schemeChar(c byte) bool {
	return isLetter(c) || c >= '0' && c <= '9' || c == '+' || c == '.' || c == '-'
}

// wordEnd — the end of the word without spaces from i (A10).
func (s *scan) wordEnd(i, end int) int {
	for j := i; j < end; {
		r, n := utf8.DecodeRuneInString(s.t[j:])
		if isSpace(r) {
			return j
		}
		j += n
	}
	return end
}

// --- the parts of an address (A2) ---

type parts struct {
	scheme                                     string
	p                                          int // the first «://»
	auth0, auth1, path0, path1, q0, q1, f0, f1 int
	fragNone                                   bool
}

func (s *scan) parts(a, end int) parts {
	t := s.t
	p := a + strings.Index(t[a:end], "://")
	sa := p
	for sa > a && schemeChar(t[sa-1]) {
		sa--
	}
	pr := parts{scheme: strings.ToLower(t[sa:p]), p: p}
	if sr, ok := s.rule.Schemes[pr.scheme]; ok {
		pr.fragNone = sr.FragmentNone
	} else if sr, ok := s.r.catalogue.Schemes[pr.scheme]; ok {
		pr.fragNone = sr.FragmentNone
	}
	stop := func(i int, chars string) int {
		for ; i < end; i++ {
			if strings.IndexByte(chars, t[i]) >= 0 && !(t[i] == '#' && pr.fragNone) {
				return i
			}
		}
		return end
	}
	pr.auth0 = p + 3
	pr.auth1 = stop(pr.auth0, "/?#")
	pr.path0 = pr.auth1
	pr.path1 = stop(pr.path0, "?#")
	pr.q0, pr.q1, pr.f0, pr.f1 = -1, -1, -1, -1
	i := pr.path1
	if i < end && t[i] == '?' {
		pr.q0 = i + 1
		pr.q1 = stop(pr.q0, "#")
		i = pr.q1
	}
	if i < end && t[i] == '#' {
		pr.f0, pr.f1 = i+1, end
	}
	return pr
}

// --- reading ---

// address — an address from its scheme over [a, end): steps 3–8 of find.
func (s *scan) address(a, end int) {
	t := s.t
	first := a + strings.Index(t[a:end], "://")
	pr := s.parts(a, end)
	// 4–6 at each «://»
	for p := first; p >= 0 && p < end; {
		s.userinfo(p, end)
		s.port(p, end)
		n := strings.Index(t[p+3:end], "://")
		if n < 0 {
			break
		}
		p = p + 3 + n
	}
	s.atSigns(pr, end)
	s.regexes(pr, end)
	s.pairsAddress(pr, end)
}

// userinfo — A10 at the «://» at p.
func (s *scan) userinfo(p, end int) {
	t := s.t
	i := p + 3
	for i < end && !strings.ContainsRune("/@:?#", rune(t[i])) && t[i] != ' ' {
		i++
	}
	if i >= end || t[i] != ':' {
		return
	}
	login := i
	pw := i + 1
	we := s.wordEnd(pw, end)
	at := strings.LastIndex(t[pw:we], "@")
	if at < 0 {
		return
	}
	at += pw
	if strings.HasPrefix(t[pw:], "//") {
		return
	}
	// a port and a parameter: digits up to / ? #, then = & ; :// before «@»
	d := pw
	for d < at && t[d] >= '0' && t[d] <= '9' {
		d++
	}
	if d > pw && d < at && strings.IndexByte("/?#", t[d]) >= 0 {
		rest := t[d:at]
		if strings.ContainsAny(rest, "=&;") || strings.Contains(rest, "://") {
			return
		}
	}
	s.add(kindLogin, p+3, login)
	s.add(kindSecret, pw, at)
}

// port — A12 at the «://» at p.
func (s *scan) port(p, end int) {
	t := s.t
	a := p + 3
	b := a
	for b < end && strings.IndexByte("/?#", t[b]) < 0 {
		b++
	}
	auth := t[a:b]
	h := strings.LastIndex(auth, "@") + 1
	host := auth[h:]
	var port int
	if strings.HasPrefix(host, "[") {
		k := strings.Index(host, "]:")
		if k < 0 {
			return
		}
		port = k + 2
	} else {
		k := strings.Index(host, ":")
		if k < 0 {
			return
		}
		port = k + 1
	}
	pa := a + h + port
	pb := b
	for pb > pa && strings.IndexByte("\"'()<>[]{},.;:", t[pb-1]) >= 0 {
		pb--
	}
	if pb == pa {
		return
	}
	for i := pa; i < pb; i++ {
		if t[i] < '0' || t[i] > '9' {
			s.add(kindSecret, pa, pb)
			return
		}
	}
}

// atSigns — A11a: each «@» after the first «://» outside authority.
func (s *scan) atSigns(pr parts, end int) {
	t := s.t
	for i := pr.auth1; i < end; i++ {
		if t[i] != '@' {
			continue
		}
		j := i
		for j > pr.auth0 && strings.IndexByte("/?&;=", t[j-1]) < 0 {
			j--
		}
		seg := t[j:i]
		if c := strings.IndexByte(seg, ':'); c >= 0 {
			s.add(kindSecret, j+c+1, i)
		} else {
			s.add(kindLogin, j, i)
		}
	}
}

// regexes — A13 over the parts of the outer address.
func (s *scan) regexes(pr parts, end int) {
	for _, rx := range s.rule.Regexes {
		if len(rx.Schemes) > 0 {
			ok := false
			for _, sc := range rx.Schemes {
				ok = ok || strings.EqualFold(sc, pr.scheme)
			}
			if !ok {
				continue
			}
		}
		for _, part := range rx.In {
			var a, b int
			switch part {
			case "authority":
				a, b = pr.auth0, pr.auth1
			case "path":
				a, b = pr.path0, pr.path1
			case "query":
				a, b = pr.q0, pr.q1
			case "fragment":
				a, b = pr.f0, pr.f1
			}
			if a < 0 {
				continue
			}
			text := s.t[a:b]
			var st, en []int
			if rx.Decoded {
				text, st, en = decodeMap(text, a)
			} else {
				st, en = make([]int, len(text)), make([]int, len(text))
				for i := range text {
					st[i], en[i] = a+i, a+i+1
				}
			}
			for _, m := range rx.Re.FindAllStringSubmatchIndex(text, -1) {
				for gi, name := range rx.Re.SubexpNames() {
					ga, gb := m[2*gi], m[2*gi+1]
					if ga < 0 || gb <= ga {
						continue
					}
					switch name {
					case "secret":
						s.add(kindSecret, st[ga], en[gb-1])
					case "login":
						s.add(kindLogin, st[ga], en[gb-1])
					}
				}
			}
		}
	}
}

// pair — one pair name=value at [na, nb) [va, vb) (vb — the end of the value by its part; ext — the end by A6).
func (s *scan) pair(na, nb, va, vb int) {
	t := s.t
	name, value := t[na:nb], t[va:vb]
	if name == "" {
		return
	}
	if strings.Contains(name, "%") {
		dn := DecodeFix(name)
		if strings.ContainsAny(dn, "=&;") {
			k := s.hidden(dn + "=" + DecodeFix(value))
			s.add(k, na, vb)
			if k != kindNone {
				return
			}
		}
	}
	dv := DecodeFix(value)
	if contains(s.rule.Nested, readName(name).whole) && strings.Contains(dv, "://") {
		s.addNested(s.nestedKind(dv), va, vb)
	} else if strings.Contains(value, "%") {
		if strings.Contains(dv, "://") {
			s.addNested(s.nestedKind(dv), va, vb)
		} else {
			s.add(s.hidden(dv), va, vb)
		}
	}
	s.add(nameKind(name, s.rule), va, vb)
}

// hidden — A7(b): the decoded text cut by & and ; — the strongest kind of its pairs.
func (s *scan) hidden(dv string) int {
	k := kindNone
	for _, part := range strings.FieldsFunc(dv, func(r rune) bool { return r == '&' || r == ';' }) {
		if e := strings.IndexByte(part, '='); e > 0 {
			if pk := nameKind(part[:e], s.rule); pk > k {
				k = pk
			}
		}
	}
	return k
}

// pairsAddress — A3 over an address; A6 for the end of a secret value; A8 (3), (4) for the segments with «%».
func (s *scan) pairsAddress(pr parts, end int) {
	t := s.t
	r1 := end
	if q := strings.IndexByte(t[pr.auth0:end], '?'); q >= 0 {
		r1 = pr.auth0 + q
	}
	// authority and path: segments by «/», parts by & ; #
	for seg0 := pr.auth0; seg0 <= r1; {
		seg1 := seg0
		for seg1 < r1 && t[seg1] != '/' {
			seg1++
		}
		segment := t[seg0:seg1]
		if strings.Contains(segment, "%") {
			d := DecodeFix(segment)
			if strings.Contains(d, "://") {
				s.addNested(s.nestedKind(d), seg0, seg1)
			} else if strings.HasSuffix(d, ":") && strings.HasPrefix(t[seg1:], "//") {
				pe := r1
				if h := strings.IndexByte(t[seg0:r1], '#'); h >= 0 && !pr.fragNone {
					pe = seg0 + h
				}
				s.addNested(s.nestedKind(DecodeFix(t[seg0:pe])), seg0, pe)
			}
		}
		for p0 := seg0; p0 <= seg1; {
			p1 := p0
			for p1 < seg1 && strings.IndexByte("&;#", t[p1]) < 0 {
				p1++
			}
			if e := strings.IndexByte(t[p0:p1], '='); e >= 0 {
				vb := p1
				// A6: «/» right after the value and «;» or «&» before the next ? # or the end
				if vb == seg1 && seg1 < r1 && t[seg1] == '/' && nameKind(t[p0:p0+e], s.rule) == kindSecret {
					stopAt := end
					if k := strings.IndexAny(t[seg1:end], "?#"); k >= 0 {
						stopAt = seg1 + k
					}
					if k := strings.IndexAny(t[seg1:stopAt], ";&"); k >= 0 {
						vb = seg1 + k
					}
				}
				s.pair(p0, p0+e, p0+e+1, vb)
			}
			p0 = p1 + 1
		}
		seg0 = seg1 + 1
	}
	if r1 >= end {
		return
	}
	// the query to the end of the value: parts by & ;
	s.pairsBy(r1+1, end, "&;")
	if h := strings.IndexByte(t[r1:end], '#'); h >= 0 {
		s.pairsBy(r1+h+1, end, "&;")
	}
}

func (s *scan) pairsBy(a, end int, seps string) {
	t := s.t
	for p0 := a; p0 <= end; {
		p1 := p0
		for p1 < end && strings.IndexByte(seps, t[p1]) < 0 {
			p1++
		}
		if e := strings.IndexByte(t[p0:p1], '='); e >= 0 {
			s.pair(p0, p0+e, p0+e+1, p1)
		}
		p0 = p1 + 1
	}
}

func textNameChar(r rune) bool {
	return r >= 0x80 || unicode.IsLetter(r) || unicode.IsDigit(r) || r == '_' || r == '.' || r == '-' || r == '%'
}

// textPairs — A1 pairs of text over [a, end): a name of letters, digits, _ . - % and non-ASCII before «=», a value to
// & ; , or a space. skip — the positions of «=» that belong to an address of free text.
func (s *scan) textPairs(a, end int, skip func(int) bool) {
	t := s.t
	for i := a; i < end; i++ {
		if t[i] != '=' || (skip != nil && skip(i)) {
			continue
		}
		na := i
		for na > a {
			r, n := utf8.DecodeLastRuneInString(t[a:na])
			if !textNameChar(r) {
				break
			}
			na -= n
		}
		if na == i {
			continue
		}
		vb := i + 1
		for vb < end {
			r, n := utf8.DecodeRuneInString(t[vb:])
			if r == '&' || r == ';' || r == ',' || isSpace(r) {
				break
			}
			vb += n
		}
		s.pair(na, i, i+1, vb)
		i = vb
	}
}

// head — A11b: each «@» of the head [0, end).
func (s *scan) head(end int) {
	t := s.t
	for i := 0; i < end; i++ {
		if t[i] != '@' {
			continue
		}
		if c := strings.LastIndexByte(t[:i], ':'); c >= 0 {
			s.add(kindSecret, c+1, i)
		} else {
			s.add(kindLogin, 0, i)
		}
	}
}

// value — find(value, rule, 0) of a field value.
func (s *scan) value() {
	t := s.t
	p := strings.Index(t, "://")
	if p < 0 {
		s.head(len(t))
		s.textPairs(0, len(t), nil)
		if strings.Contains(t, "%") {
			if d := DecodeFix(t); strings.Contains(d, "://") {
				s.addNested(s.nestedKind(d), 0, len(t))
			}
		}
		return
	}
	s.head(p)
	s.address(0, len(t))
}

// --- the display and the refusal ---

func maskSpans(t string, fs []finding) string { return maskWith(t, fs, nil) }

// unparsable — a character that the grammar of RFC 3986 admits nowhere (A2).
func unparsable(t string) bool {
	for _, r := range t {
		if r < 0x20 || r == 0x7F || r == ' ' || strings.ContainsRune("\"<>\\^`{|}", r) {
			return true
		}
	}
	return false
}

// URLRead — the reading of a url value by its field rule: Masked — the display (A14); Fault — the credentials field
// the refusal names ("" — the credentials do not refuse the value; A15).
type URLRead struct {
	Masked string
	Fault  string
}

// ReadAddress — read_address(value, field rule, catalogue) (the catalogue is the united rule of all url fields).
func ReadAddress(value string, rule, catalogue URLRule) URLRead {
	rd := &reader{catalogue: catalogue}
	s := &scan{r: rd, rule: &rule, t: value}
	s.value()
	k := strongest(s.out)
	if unparsable(value) {
		k = kindSecret
	}
	out := URLRead{}
	switch k {
	case kindSecret:
		out.Fault = rule.Secret
	case kindLogin:
		out.Fault = rule.Login
	}
	// the display: the nested addresses with a password as a whole, then the value again
	t2 := maskSpans(value, s.nest)
	s2 := &scan{r: rd, rule: &rule, t: t2}
	s2.value()
	out.Masked = maskSpans(t2, s2.out)
	return out
}

// URLRefusal — the text of a refusal by the credentials: the word bad_url and the names of the fields, without the
// value.
func URLRefusal(read URLRead, rule URLRule) string {
	if read.Fault == "" {
		return ""
	}
	if read.Fault == rule.Secret && rule.Login != "" {
		return "bad_url: the url carries credentials (" + rule.Secret + ", " + rule.Login + ")"
	}
	return "bad_url: the url carries credentials (" + read.Fault + ")"
}
