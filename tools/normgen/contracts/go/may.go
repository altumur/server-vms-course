package contracts

import (
	"bytes"
	"encoding/json"
	"math"
	"regexp"
	"strconv"
	"strings"
	"unicode"
	"unicode/utf8"
)

// Right contract (common/contracts/may.md): the function may — the right of a person (or of a role) by the grant lines;
// the input form of the vectors may (README «Form of the input of the command may»), covers.

// GrantLifetime — GRANT_LIFETIME, seconds.
const GrantLifetime = 86400

var manifestNameRE = regexp.MustCompile(`^[a-z][a-z0-9_-]{0,31}$`)

var folderIDRE = regexp.MustCompile(`^[0-9a-f]{32}$`)

// ValidPersonName — the person name contract name: 1–64 characters without White_Space, control characters and
// : | ( ) " /, not exactly break-glass.
func ValidPersonName(s string) bool {
	n := utf8.RuneCountInString(s)
	if n < 1 || n > 64 || !utf8.ValidString(s) || s == "break-glass" {
		return false
	}
	for _, r := range s {
		if isSpace(r) || r < 0x20 || r == 0x7F || strings.ContainsRune(`:|()"/`, r) {
			return false
		}
	}
	return true
}

// ValidNamedID — a named id (row check «Identifier and field constraints»): non-empty, not «.»/«..», without / \ | " ,
// control characters (Cc), Zl, Zp and non-ASCII digits (Nd).
func ValidNamedID(s string) bool {
	if s == "" || s == "." || s == ".." || !utf8.ValidString(s) || strings.ContainsAny(s, `/\|",`) {
		return false
	}
	for _, r := range s {
		if unicode.Is(unicode.Cc, r) || unicode.Is(unicode.Zl, r) || unicode.Is(unicode.Zp, r) ||
			unicode.Is(unicode.Nd, r) && (r < '0' || r > '9') {
			return false
		}
	}
	return true
}

var capRank = map[string]int{"none": 0, "view": 1, "edit": 2, "admin": 3}

// GrantLine — a line of grants: Subject (a person or role:<name>), Cap, Sub ("" — none), Scope, Until (0 — no term).
type GrantLine struct {
	Subject string
	Cap     string
	Sub     string
	Scope   string
	Until   float64
}

// MayUnit — the unit of the check: Kind "null" | "*" | "any" | "unit"; Sub, ID, Labels; About (nil — no about),
// AboutUnknown; Chains (nil — unknown).
type MayUnit struct {
	Kind         string
	Sub, ID      string
	Labels       []string
	About        *MayUnit
	AboutUnknown bool
	Chains       [][]string
}

// RoleAssign — {role, until, at} of the roles table.
type RoleAssign struct {
	Role      string
	Until, At float64
}

// UnreadRole — {role, sub?} of unread.
type UnreadRole struct {
	Role, Sub string
}

// MayInput — the input of may. Grants nil — null; AsOf, Sub, Iat nil — null; Roles nil and RolesUnreadable — the
// table; UnreadAll — "all"; AsRole — "" a person.
type MayInput struct {
	Grants          []GrantLine
	HasGrants       bool
	AsOf            *float64
	Disabled        []string
	User            string
	Glass           bool
	Cap             string
	Unit            MayUnit
	Now             float64
	Sub             *string
	Roles           map[string][]RoleAssign
	RolesUnreadable bool
	Unread          []UnreadRole
	UnreadAll       bool
	Iat             *float64
	Anywhere        map[string]float64
	AsRole          string
}

// MayOutcome — allow | deny with Reason | unavailable.
type MayOutcome struct {
	Result string
	Reason string
}

func (u *MayUnit) folderObject() bool { return u.Kind == "unit" && u.Sub == "platform" }

func inChains(chains [][]string, id string) bool {
	for _, c := range chains {
		if contains(c, id) {
			return true
		}
	}
	return false
}

// ScopeCovers — step 7: whether a scope covers the unit (about "unknown" and chains unknown do not cover).
func ScopeCovers(scope string, u *MayUnit) bool {
	if scope == "*" {
		return true
	}
	if u.Kind != "unit" {
		return false
	}
	switch {
	case strings.HasPrefix(scope, "unit:"):
		if u.folderObject() {
			return false
		}
		s, i, _ := strings.Cut(scope[5:], "/")
		return u.Sub == s && u.ID == i || u.About != nil && u.About.Sub == s && u.About.ID == i
	case strings.HasPrefix(scope, "labels:"):
		if u.folderObject() || u.AboutUnknown {
			return false
		}
		have := u.Labels
		if u.About != nil {
			have = u.About.Labels
		}
		for _, l := range strings.Split(scope[7:], ",") {
			if !contains(have, l) {
				return false
			}
		}
		return true
	case strings.HasPrefix(scope, "folder:"):
		id := scope[7:]
		return u.Chains != nil && inChains(u.Chains, id) || u.About != nil && u.About.Chains != nil && inChains(u.About.Chains, id)
	}
	return false
}

func effective(l GrantLine, in *MayInput) bool {
	if !(l.Until == 0 || in.Now < l.Until) {
		return false
	}
	return l.Sub == "" || in.Sub == nil || l.Sub == *in.Sub
}

// roleLevel — the level of a role group for (cap, unit): the first tier with a covering line; ok false — no tier.
// unreadable — the group is unreadable from tier k (k = 0 — readable); could — an unreadable group could allow.
func roleLevel(lines []GrantLine, role string, in *MayInput, need int) (level int, ok bool, unreadable bool, could bool) {
	u := &in.Unit
	maxCap := func(ls []GrantLine) (int, bool) {
		m, any := -1, false
		for _, l := range ls {
			if r := capRank[l.Cap]; r > m {
				m = r
			}
			any = true
		}
		return m, any
	}
	var unitLines, aboutLines, folderLines, starLines []GrantLine
	hasUnitLine, hasFolderLine := false, false
	for _, l := range lines {
		switch {
		case l.Scope == "*":
			starLines = append(starLines, l)
		case strings.HasPrefix(l.Scope, "unit:"):
			hasUnitLine = true
			if u.Kind == "unit" && !u.folderObject() {
				s, i, _ := strings.Cut(l.Scope[5:], "/")
				if u.Sub == s && u.ID == i {
					unitLines = append(unitLines, l)
				} else if u.About != nil && u.About.Sub == s && u.About.ID == i {
					aboutLines = append(aboutLines, l)
				}
			}
		case strings.HasPrefix(l.Scope, "folder:"):
			hasFolderLine = true
			folderLines = append(folderLines, l)
		}
	}
	couldFrom := func(k int) bool {
		for _, l := range lines {
			if capRank[l.Cap] < need {
				continue
			}
			switch {
			case k == 1:
				return true
			case k == 2 && (strings.HasPrefix(l.Scope, "unit:") || strings.HasPrefix(l.Scope, "folder:") || l.Scope == "*"):
				return true
			case k == 3 && (strings.HasPrefix(l.Scope, "folder:") || l.Scope == "*"):
				return true
			}
		}
		return false
	}
	// k = 1
	if in.UnreadAll {
		return 0, false, true, couldFrom(1)
	}
	for _, r := range in.Unread {
		if r.Role == role && (r.Sub == "" || in.Sub != nil && r.Sub == *in.Sub) {
			return 0, false, true, couldFrom(1)
		}
	}
	if u.Kind != "unit" {
		lv, any := maxCap(starLines)
		return lv, any, false, false
	}
	if lv, any := maxCap(unitLines); any {
		return lv, true, false, false
	}
	if lv, any := maxCap(aboutLines); any {
		return lv, true, false, false
	}
	if u.AboutUnknown && hasUnitLine && !u.folderObject() {
		return 0, false, true, couldFrom(2)
	}
	chainsUnknown := u.Chains == nil || u.AboutUnknown || u.About != nil && u.About.Chains == nil
	if hasFolderLine && chainsUnknown {
		// the cut-off: the result does not depend on the membership
		allHigh, allLow := true, true
		for _, l := range folderLines {
			if capRank[l.Cap] >= need {
				allLow = false
			} else {
				allHigh = false
			}
		}
		star, anyStar := maxCap(starLines)
		starAllows := anyStar && star >= need
		if allHigh && starAllows {
			return star, true, false, false
		}
		if allLow && !starAllows {
			return star, anyStar, false, false
		}
		return 0, false, true, couldFrom(3)
	}
	// tier 3: the nearest folders with a line of the group in each chain
	var tier3 []GrantLine
	for _, chains := range [][][]string{u.Chains, aboutChains(u)} {
		for _, c := range chains {
			for _, f := range c {
				var at []GrantLine
				for _, l := range folderLines {
					if l.Scope == "folder:"+f {
						at = append(at, l)
					}
				}
				if len(at) > 0 {
					tier3 = append(tier3, at...)
					break
				}
			}
		}
	}
	if lv, any := maxCap(tier3); any {
		return lv, true, false, false
	}
	lv, any := maxCap(starLines)
	return lv, any, false, false
}

func aboutChains(u *MayUnit) [][]string {
	if u.About != nil {
		return u.About.Chains
	}
	return nil
}

// May — the steps 1–8 (and «Action as a role» with AsRole).
func May(in *MayInput) MayOutcome {
	allow := MayOutcome{Result: "allow"}
	deny := func(w string) MayOutcome { return MayOutcome{Result: "deny", Reason: w} }
	asRole := in.AsRole != ""
	if !asRole {
		if in.Glass {
			return allow
		}
		if contains(in.Disabled, in.User) {
			return deny("disabled")
		}
	}
	if !in.HasGrants {
		if _, any := in.Anywhere[in.User]; in.Unit.Kind != "null" || !any || asRole {
			return deny("no_grant")
		}
	}
	if in.AsOf != nil && in.Now-*in.AsOf > GrantLifetime {
		return deny("stale")
	}
	if asRole && in.AsRole == "admin" {
		return deny("no_grant")
	}
	if !asRole && in.Roles != nil {
		for _, a := range in.Roles[in.User] {
			if a.Role == "admin" && (a.Until == 0 || in.Now < a.Until) &&
				(in.Iat == nil || math.Floor(*in.Iat) >= math.Floor(a.At)) {
				return allow
			}
		}
	}
	// step 5: the selection
	var direct []GrantLine
	groups := map[string][]GrantLine{}
	var order []string
	roleUntil := map[string]float64{}
	if asRole {
		roleUntil[in.AsRole] = 0
		order = append(order, in.AsRole)
	} else if in.Roles != nil {
		for _, a := range in.Roles[in.User] {
			if a.Role == "admin" {
				continue
			}
			old, seen := roleUntil[a.Role]
			if !seen {
				order = append(order, a.Role)
				roleUntil[a.Role] = a.Until
			} else if old != 0 && (a.Until == 0 || a.Until > old) {
				roleUntil[a.Role] = a.Until
			}
		}
	}
	var live []string
	for _, r := range order {
		if t := roleUntil[r]; t == 0 || in.Now < t {
			live = append(live, r)
		}
	}
	for _, l := range in.Grants {
		if !effective(l, in) {
			continue
		}
		if !asRole && l.Subject == in.User {
			direct = append(direct, l)
		}
		if strings.HasPrefix(l.Subject, "role:") && contains(live, l.Subject[5:]) {
			groups[l.Subject[5:]] = append(groups[l.Subject[5:]], l)
		}
	}
	need := capRank[in.Cap]
	// step 6
	if in.Unit.Kind == "null" && in.Cap == "view" {
		if len(direct) > 0 {
			return allow
		}
		for _, r := range live {
			for _, l := range groups[r] {
				if l.Cap != "none" {
					return allow
				}
			}
		}
		if t, ok := in.Anywhere[in.User]; ok && (t == 0 || in.Now < t) {
			return allow
		}
	}
	// step 6a
	if in.Unit.Kind == "any" {
		for _, l := range direct {
			if capRank[l.Cap] >= need {
				return allow
			}
		}
		for _, r := range live {
			for _, l := range groups[r] {
				if capRank[l.Cap] >= need {
					return allow
				}
			}
		}
		if in.RolesUnreadable && !asRole {
			return MayOutcome{Result: "unavailable"}
		}
		return deny("no_grant")
	}
	// step 7
	for _, l := range direct {
		if capRank[l.Cap] >= need && ScopeCovers(l.Scope, &in.Unit) {
			return allow
		}
	}
	// step 7a, 7c
	couldAny := false
	for _, r := range live {
		lv, ok, unreadable, could := roleLevel(groups[r], r, in, need)
		if unreadable {
			couldAny = couldAny || could
			continue
		}
		if ok && lv >= need {
			return allow
		}
	}
	if in.RolesUnreadable && !asRole {
		return MayOutcome{Result: "unavailable"}
	}
	if couldAny {
		return MayOutcome{Result: "unavailable"}
	}
	return deny("no_grant")
}

// --- the input form ---

func exactKeys(m map[string]json.RawMessage, required []string, optional ...string) bool {
	for _, k := range required {
		if _, ok := m[k]; !ok {
			return false
		}
	}
	allowed := map[string]bool{}
	for _, k := range append(append([]string{}, required...), optional...) {
		allowed[k] = true
	}
	for k := range m {
		if !allowed[k] {
			return false
		}
	}
	return true
}

func rawObject(r json.RawMessage) (map[string]json.RawMessage, bool) {
	var m map[string]json.RawMessage
	if len(r) == 0 || r[0] != '{' || json.Unmarshal(r, &m) != nil {
		return nil, false
	}
	return m, true
}

func rawString(r json.RawMessage) (string, bool) {
	var s string
	if len(r) == 0 || r[0] != '"' || json.Unmarshal(r, &s) != nil {
		return "", false
	}
	return s, true
}

func rawNumber(r json.RawMessage) (float64, bool) {
	s := strings.TrimSpace(string(r))
	if !jsonNumberRE.MatchString(s) {
		return 0, false
	}
	f, err := strconv.ParseFloat(s, 64)
	return f, err == nil && !math.IsInf(f, 0)
}

func rawStrings(r json.RawMessage) ([]string, bool) {
	var arr []json.RawMessage
	if len(r) == 0 || r[0] != '[' || json.Unmarshal(r, &arr) != nil {
		return nil, false
	}
	out := make([]string, 0, len(arr))
	for _, e := range arr {
		s, ok := rawString(e)
		if !ok {
			return nil, false
		}
		out = append(out, s)
	}
	return out, true
}

func rawNull(r json.RawMessage) bool { return strings.TrimSpace(string(r)) == "null" }

// loneSurrogate — a JSON string lexeme with a \uD800–\uDFFF escape that is not a pair.
var surrogateRE = regexp.MustCompile(`\\u[dD][89abAB][0-9a-fA-F]{2}\\u[dD][c-fC-F][0-9a-fA-F]{2}|\\u[dD][89a-fA-F][0-9a-fA-F]{2}`)

func loneSurrogate(lexeme string) bool {
	for _, m := range surrogateRE.FindAllString(lexeme, -1) {
		if len(m) == 6 {
			return true
		}
	}
	return false
}

func parseTime(r json.RawMessage) (float64, bool) {
	f, ok := rawNumber(r)
	return f, ok && f >= 0 && readerTime.Match(r)
}

func validScope(scope string, roleLine bool) bool {
	switch {
	case scope == "*":
		return true
	case strings.HasPrefix(scope, "unit:"):
		s, i, ok := strings.Cut(scope[5:], "/")
		return ok && manifestNameRE.MatchString(s) && ValidNamedID(i)
	case strings.HasPrefix(scope, "labels:"):
		if roleLine {
			return false
		}
		for _, l := range strings.Split(scope[7:], ",") {
			if !ValidLabel(l) {
				return false
			}
		}
		return true
	case strings.HasPrefix(scope, "folder:"):
		return folderIDRE.MatchString(scope[7:])
	}
	return false
}

func parseLine(r json.RawMessage) (GrantLine, bool) {
	m, ok := rawObject(r)
	if !ok || !exactKeys(m, []string{"subject", "cap", "scope", "until", "by"}, "sub") {
		return GrantLine{}, false
	}
	var l GrantLine
	var ok1, ok2, ok3, ok4 bool
	l.Subject, ok1 = rawString(m["subject"])
	l.Cap, ok2 = rawString(m["cap"])
	l.Scope, ok3 = rawString(m["scope"])
	l.Until, ok4 = parseTime(m["until"])
	_, ok5 := rawString(m["by"])
	if !ok1 || !ok2 || !ok3 || !ok4 || !ok5 {
		return l, false
	}
	role := strings.HasPrefix(l.Subject, "role:")
	if role {
		if n := l.Subject[5:]; !ValidPersonName(n) || n == "admin" {
			return l, false
		}
	} else if !ValidPersonName(l.Subject) {
		return l, false
	}
	if _, known := capRank[l.Cap]; !known || l.Cap == "none" && !role {
		return l, false
	}
	if s, has := m["sub"]; has {
		if l.Sub, ok = rawString(s); !ok || !manifestNameRE.MatchString(l.Sub) {
			return l, false
		}
	}
	return l, validScope(l.Scope, role)
}

func parseMayUnit(r json.RawMessage, about bool) (MayUnit, bool) {
	m, ok := rawObject(r)
	if !ok {
		return MayUnit{}, false
	}
	opt := []string{"chains"}
	if !about {
		opt = append(opt, "about")
	}
	if !exactKeys(m, []string{"sub", "id", "labels"}, opt...) {
		return MayUnit{}, false
	}
	u := MayUnit{Kind: "unit"}
	var ok1, ok2, ok3 bool
	u.Sub, ok1 = rawString(m["sub"])
	u.ID, ok2 = rawString(m["id"])
	u.Labels, ok3 = rawStrings(m["labels"])
	if !ok1 || !ok2 || !ok3 {
		return u, false
	}
	if c, has := m["chains"]; has {
		if s, isStr := rawString(c); isStr {
			if s != "unknown" {
				return u, false
			}
		} else {
			var arr []json.RawMessage
			if len(c) == 0 || c[0] != '[' || json.Unmarshal(c, &arr) != nil {
				return u, false
			}
			u.Chains = [][]string{}
			for _, e := range arr {
				ch, ok := rawStrings(e)
				if !ok {
					return u, false
				}
				u.Chains = append(u.Chains, ch)
			}
		}
	}
	if a, has := m["about"]; has && !about {
		if s, isStr := rawString(a); isStr {
			if s != "unknown" {
				return u, false
			}
			u.AboutUnknown = true
		} else {
			au, ok := parseMayUnit(a, true)
			if !ok {
				return u, false
			}
			u.About = &au
		}
	}
	return u, true
}

// ParseMayInput — the input form of the command may; out of form — ErrRefuse (code 2), the whole form before steps 1–2.
func ParseMayInput(raw []byte) (*MayInput, error) {
	m, ok := rawObject(bytes.TrimSpace(raw))
	if !ok {
		return nil, ErrRefuse
	}
	for _, k := range []string{"grants", "as_of", "disabled", "user", "glass", "cap", "unit", "now"} {
		if _, ok := m[k]; !ok {
			return nil, ErrRefuse
		}
	}
	in := &MayInput{Anywhere: map[string]float64{}}
	bad := func() (*MayInput, error) { return nil, ErrRefuse }
	if !rawNull(m["grants"]) {
		g, ok := rawObject(m["grants"])
		if !ok || !exactKeys(g, []string{"lines"}) {
			return bad()
		}
		var lines []json.RawMessage
		if len(g["lines"]) == 0 || g["lines"][0] != '[' || json.Unmarshal(g["lines"], &lines) != nil {
			return bad()
		}
		for _, lr := range lines {
			l, ok := parseLine(lr)
			if !ok {
				return bad()
			}
			in.Grants = append(in.Grants, l)
		}
		in.HasGrants = true
	}
	if !rawNull(m["as_of"]) {
		f, ok := rawNumber(m["as_of"])
		if !ok {
			return bad()
		}
		in.AsOf = &f
	}
	if in.Disabled, ok = rawStrings(m["disabled"]); !ok {
		return bad()
	}
	if in.User, ok = rawString(m["user"]); !ok || loneSurrogate(string(m["user"])) {
		return bad()
	}
	switch strings.TrimSpace(string(m["glass"])) {
	case "true":
		in.Glass = true
	case "false":
	default:
		return bad()
	}
	if in.Cap, ok = rawString(m["cap"]); !ok || in.Cap == "none" || capRank[in.Cap] == 0 {
		return bad()
	}
	switch s, isStr := rawString(m["unit"]); {
	case rawNull(m["unit"]):
		in.Unit = MayUnit{Kind: "null"}
	case isStr && (s == "*" || s == "any"):
		in.Unit = MayUnit{Kind: s}
	case isStr:
		return bad()
	default:
		if in.Unit, ok = parseMayUnit(m["unit"], false); !ok {
			return bad()
		}
	}
	if in.Now, ok = rawNumber(m["now"]); !ok {
		return bad()
	}
	if s, has := m["sub"]; has && !rawNull(s) {
		v, ok := rawString(s)
		if !ok || !manifestNameRE.MatchString(v) {
			return bad()
		}
		in.Sub = &v
	}
	if r, has := m["roles"]; has && !rawNull(r) {
		if s, isStr := rawString(r); isStr {
			if s != "unreadable" {
				return bad()
			}
			in.RolesUnreadable = true
		} else {
			t, ok := rawObject(r)
			if !ok {
				return bad()
			}
			in.Roles = map[string][]RoleAssign{}
			for name, list := range t {
				var arr []json.RawMessage
				if len(list) == 0 || list[0] != '[' || json.Unmarshal(list, &arr) != nil {
					return bad()
				}
				for _, e := range arr {
					o, ok := rawObject(e)
					if !ok || !exactKeys(o, []string{"role", "until", "at"}) {
						return bad()
					}
					var a RoleAssign
					var ok1, ok2, ok3 bool
					a.Role, ok1 = rawString(o["role"])
					a.Until, ok2 = parseTime(o["until"])
					a.At, ok3 = parseTime(o["at"])
					if !ok1 || !ok2 || !ok3 {
						return bad()
					}
					in.Roles[name] = append(in.Roles[name], a)
				}
			}
		}
	}
	if u, has := m["unread"]; has {
		if s, isStr := rawString(u); isStr {
			if s != "all" {
				return bad()
			}
			in.UnreadAll = true
		} else {
			var arr []json.RawMessage
			if len(u) == 0 || u[0] != '[' || json.Unmarshal(u, &arr) != nil {
				return bad()
			}
			for _, e := range arr {
				o, ok := rawObject(e)
				if !ok || !exactKeys(o, []string{"role"}, "sub") {
					return bad()
				}
				var ur UnreadRole
				if ur.Role, ok = rawString(o["role"]); !ok {
					return bad()
				}
				if s, has := o["sub"]; has {
					if ur.Sub, ok = rawString(s); !ok {
						return bad()
					}
				}
				in.Unread = append(in.Unread, ur)
			}
		}
	}
	if i, has := m["iat"]; has && !rawNull(i) {
		f, ok := rawNumber(i)
		if !ok {
			return bad()
		}
		in.Iat = &f
	}
	if a, has := m["anywhere"]; has {
		o, ok := rawObject(a)
		if !ok {
			return bad()
		}
		for name, t := range o {
			f, ok := parseTime(t)
			if !ok {
				return bad()
			}
			in.Anywhere[name] = f
		}
	}
	if r, has := m["as_role"]; has {
		if in.AsRole, ok = rawString(r); !ok {
			return bad()
		}
	}
	return in, nil
}

// ValidGrantScope — a scope by the grammar of a grant line (a direct line: labels: allowed).
func ValidGrantScope(scope string) bool { return validScope(scope, false) }

// ParseMayUnitJSON — a unit {sub, id, labels, about?, chains?} of the may form.
func ParseMayUnitJSON(raw []byte) (MayUnit, error) {
	u, ok := parseMayUnit(raw, false)
	if !ok {
		return u, ErrRefuse
	}
	return u, nil
}
