package contracts

import (
	"encoding/json"
	"math/big"
	"sort"
	"strings"
	"unicode"
)

// EventQuery — typed values of the resource query, after the HTTP lexeme checks (common/contracts/events-merge.md).
type EventQuery struct {
	From, To                               float64
	Limit                                  int
	Keep, By, Kind, Subsystem, Unit, Class string
	Late                                   float64
}

func eventQuery(v any) (EventQuery, bool) {
	q := EventQuery{To: 1e12, Limit: 1000, Keep: "newest", By: "t", Late: 3600}
	if v == nil {
		return q, true
	}
	m, ok := v.(map[string]any)
	if !ok || !closedObject(m, "", "from to limit keep by kind subsystem unit class late") {
		return q, false
	}
	for _, field := range []struct {
		name string
		dst  *string
	}{
		{"keep", &q.Keep}, {"by", &q.By}, {"kind", &q.Kind}, {"subsystem", &q.Subsystem}, {"unit", &q.Unit}, {"class", &q.Class},
	} {
		if v, has := m[field.name]; has {
			s, ok := v.(string)
			if !ok {
				return q, false
			}
			*field.dst = s
		}
	}
	for _, field := range []struct {
		name string
		dst  *float64
	}{{"from", &q.From}, {"to", &q.To}, {"late", &q.Late}} {
		if v, has := m[field.name]; has {
			n, ok := finiteNumber(v)
			if !ok || n < 0 {
				return q, false
			}
			*field.dst = n
		}
	}
	if v, has := m["limit"]; has {
		n, ok := eventCount(v)
		if !ok || n < 1 || n > 10000 {
			return q, false
		}
		q.Limit = n
	}
	_, late := m["late"]
	if late {
		if _, ok := eventInteger(m["late"]); !ok {
			return q, false
		}
	}
	if q.Keep != "newest" && q.Keep != "oldest" || q.By != "t" && q.By != "occurred" ||
		q.Class != "" && q.Class != "alarm" && q.Class != "observation" || q.From > q.To ||
		late && q.By != "occurred" {
		return q, false
	}
	if q.Unit != "" && !eventUnit(q.Unit) {
		return q, false
	}
	return q, true
}

func eventCount(v any) (int, bool) {
	i, ok := eventInteger(v)
	if !ok || !i.IsInt64() || i.Int64() > MaxSafeInt {
		return 0, false
	}
	return int(i.Int64()), true
}

func eventInteger(v any) (*big.Int, bool) {
	n, ok := v.(json.Number)
	if !ok {
		return nil, false
	}
	i, ok := ExactInteger(string(n))
	if !ok || i.Sign() < 0 {
		return nil, false
	}
	_, finite := finiteNumber(n)
	return i, finite
}

func eventSafeSegment(s string) bool {
	if s == "" || s == "." || s == ".." {
		return false
	}
	for _, r := range s {
		if r == '/' || r == '\\' || unicode.IsControl(r) || r == '\u2028' || r == '\u2029' {
			return false
		}
	}
	return true
}

func eventUnit(ref string) bool {
	sub, id, ok := strings.Cut(ref, "/")
	return ok && manifestNameRE.MatchString(strings.TrimSuffix(sub, ".alarms")) && eventSafeSegment(id) &&
		!strings.ContainsAny(id, "|\",")
}

func eventRow(v any) (map[string]any, bool) {
	m, ok := v.(map[string]any)
	if !ok || !finiteJSON(m) {
		return nil, false
	}
	for _, key := range []string{"id", "subsystem", "unit", "of", "kind", "server", "bucket", "class"} {
		if _, ok := m[key].(string); !ok {
			return nil, false
		}
	}
	if m["subsystem"] == "" || !eventUnit(m["unit"].(string)) || !eventSafeSegment(m["server"].(string)) ||
		m["class"] != "alarm" && m["class"] != "observation" {
		return nil, false
	}
	for _, seg := range strings.Split(m["bucket"].(string), "/") {
		if !eventSafeSegment(seg) {
			return nil, false
		}
	}
	if _, ok := eventInteger(m["epoch"]); !ok {
		return nil, false
	}
	if _, ok := finiteNumber(m["t"]); !ok {
		return nil, false
	}
	for _, key := range []string{"occurred", "since", "until"} {
		if v, has := m[key]; has {
			if _, ok := finiteNumber(v); !ok {
				return nil, false
			}
		}
	}
	if v, has := m["repeats"]; has {
		if n, ok := eventInteger(v); !ok || n.Sign() < 1 {
			return nil, false
		}
	}
	// ResourceEventRow carries no merger-owned marks; other subsystem fields remain open.
	if _, has := m["epoch_is"]; has {
		return nil, false
	}
	if _, has := m["fenced"]; has {
		return nil, false
	}
	out := map[string]any{}
	for k, v := range m {
		out[k] = v
	}
	return out, true
}

func eventTime(row map[string]any, by string) float64 {
	if by == "occurred" {
		if n, ok := finiteNumber(row["occurred"]); ok {
			return n
		}
	}
	n, _ := finiteNumber(row["t"])
	return n
}

// CutEvents — deduplicate by id, alarm first, time by keep, equal time by UTF-8 id, then limit. It does not
// modify the source rows or their order; the returned rows are the original complete values.
func CutEvents(rows []map[string]any, q EventQuery) ([]map[string]any, int) {
	seen := map[string]bool{}
	unique := []map[string]any{}
	for _, row := range rows {
		id, _ := row["id"].(string)
		if !seen[id] {
			unique = append(unique, row)
			seen[id] = true
		}
	}
	sort.SliceStable(unique, func(i, j int) bool {
		a, b := unique[i], unique[j]
		if a["class"] != b["class"] {
			return a["class"] == "alarm"
		}
		ta, tb := eventTime(a, q.By), eventTime(b, q.By)
		if ta != tb {
			if q.Keep == "oldest" {
				return ta < tb
			}
			return ta > tb
		}
		return a["id"].(string) < b["id"].(string)
	})
	if len(unique) > q.Limit {
		return unique[:q.Limit], len(unique) - q.Limit
	}
	return unique, 0
}

// FilterResourceEvents — P/05-R050 steps 4 and 6 over already-read valid candidates. I/O and partial bucket
// reads belong to the caller. No epoch marks, visibility or completeness are added at the resource.
func FilterResourceEvents(raw []byte) (map[string]any, error) {
	in, ok := strictJSONObject(raw)
	if !ok || !closedObject(in, "events", "query") {
		return nil, ErrRefuse
	}
	q, ok := eventQuery(in["query"])
	if !ok {
		return nil, ErrRefuse
	}
	list, ok := in["events"].([]any)
	if !ok {
		return nil, ErrRefuse
	}
	rows := []map[string]any{}
	for _, value := range list {
		row, ok := eventRow(value)
		if !ok {
			return nil, ErrRefuse
		}
		t := eventTime(row, q.By)
		written, _ := finiteNumber(row["t"])
		if t < q.From || t >= q.To || q.By == "occurred" && written > q.To+q.Late ||
			q.Kind != "" && row["kind"] != q.Kind || q.Subsystem != "" && row["subsystem"] != q.Subsystem ||
			q.Unit != "" && row["unit"] != q.Unit && row["of"] != q.Unit || q.Class != "" && row["class"] != q.Class {
			continue
		}
		rows = append(rows, row)
	}
	selected, truncated := CutEvents(rows, q)
	return map[string]any{"events": selected, "state": "live", "truncated": truncated}, nil
}

// MergeEvents — the console/worker merge, with resource replies and confirmed epoch reads supplied by the caller.
// A string "did not answer" at epochs[sub] is a failed read; an absent unit in a read map is a confirmed absence.
func MergeEvents(raw []byte) (map[string]any, error) {
	in, ok := strictJSONObject(raw)
	if !ok || !closedObject(in, "participant resources", "query policies epochs grant units") {
		return nil, ErrRefuse
	}
	q, ok := eventQuery(in["query"])
	if !ok {
		return nil, ErrRefuse
	}
	console := in["participant"] == "console"
	declared := []string{}
	if !console {
		p, ok := in["participant"].(map[string]any)
		if !ok || !closedObject(p, "worker", "") {
			return nil, ErrRefuse
		}
		declared, ok = stringList(p["worker"], true)
		if !ok {
			return nil, ErrRefuse
		}
	}
	resources, ok := in["resources"].(map[string]any)
	if !ok {
		return nil, ErrRefuse
	}
	policies, epochs, units := map[string]any{}, map[string]any{}, map[string]any{}
	for _, f := range []struct {
		name string
		dst  *map[string]any
	}{{"policies", &policies}, {"epochs", &epochs}, {"units", &units}} {
		if v, has := in[f.name]; has {
			m, ok := v.(map[string]any)
			if !ok {
				return nil, ErrRefuse
			}
			*f.dst = m
		}
	}
	grants := []string{"*"}
	for sub, value := range policies {
		if !manifestNameRE.MatchString(sub) || value != "fenced" && value != "earlier-run" {
			return nil, ErrRefuse
		}
	}
	if v, has := in["grant"]; has {
		grants, ok = stringList(v, true)
		if !ok {
			return nil, ErrRefuse
		}
		for _, g := range grants {
			if !ValidGrantScope(g) {
				return nil, ErrRefuse
			}
		}
	}
	incomplete := map[string]string{}
	rows := []map[string]any{}
	truncated, garbled := new(big.Int), new(big.Int)
	partial := false
	servers := []string{}
	owners := map[string]bool{}
	for s := range resources {
		servers = append(servers, s)
	}
	sort.Strings(servers)
	for _, server := range servers {
		value := resources[server]
		if word, ok := value.(string); ok {
			if word != "silent" && word != "did not answer" {
				return nil, ErrRefuse
			}
			incomplete[server] = word
			continue
		}
		reply, ok := value.(map[string]any)
		if !ok {
			return nil, ErrRefuse
		}
		if said, ok := reply["said"].(string); ok {
			incomplete[server] = "said " + said
			continue
		}
		if state, ok := reply["state"].(string); ok && state != "live" {
			incomplete[server] = "said " + state
			continue
		}
		if !closedObject(reply, "events state truncated", "partial lines_garbled") || reply["state"] != "live" {
			return nil, ErrRefuse
		}
		n, ok := eventInteger(reply["truncated"])
		if !ok {
			return nil, ErrRefuse
		}
		truncated.Add(truncated, n)
		if v, has := reply["partial"]; has {
			if v != true {
				return nil, ErrRefuse
			}
			partial = true
		}
		if v, has := reply["lines_garbled"]; has {
			n, ok := eventInteger(v)
			if !ok || n.Sign() < 1 {
				return nil, ErrRefuse
			}
			garbled.Add(garbled, n)
		}
		list, ok := reply["events"].([]any)
		if !ok {
			return nil, ErrRefuse
		}
		for _, value := range list {
			row, ok := eventRow(value)
			if !ok {
				garbled.Add(garbled, big.NewInt(1))
				continue
			}
			if row["server"] != server {
				owners[row["server"].(string)] = true
			}
			rows = append(rows, row)
		}
	}
	state := "live"
	for _, server := range servers {
		if _, unavailable := incomplete[server]; unavailable {
			state += "; " + server + " unreachable"
			if owners[server] {
				state += "; " + server + " from mirror"
			}
		}
	}
	seen, withheld := map[string]bool{}, map[string]bool{}
	visible := []map[string]any{}
	for _, row := range rows {
		id := row["id"].(string)
		if seen[id] {
			continue
		}
		seen[id] = true
		sub := row["subsystem"].(string)
		_, unit, _ := strings.Cut(row["unit"].(string), "/")
		mark := "current"
		if !console && !contains(declared, sub) {
			mark = "unknown"
		} else {
			read := epochs[sub]
			if read == "did not answer" {
				incomplete[sub+"/epoch"] = "did not answer"
				mark = ""
			} else if read != nil {
				current, ok := read.(map[string]any)
				if !ok {
					return nil, ErrRefuse
				}
				if v, has := current[unit]; has {
					epoch, ok := eventInteger(v)
					if !ok {
						incomplete[sub+"/epoch"] = "did not answer"
						mark = ""
					} else {
						former, _ := eventInteger(row["epoch"])
						if former.Cmp(epoch) < 0 {
							mark = "fenced"
							if policies[sub] == "earlier-run" {
								mark = "earlier-run"
							}
						}
					}
				}
			}
		}
		if mark != "" {
			row["epoch_is"] = mark
		}
		row["fenced"] = mark == "fenced"
		if console && !contains(grants, "*") {
			ref := row["of"].(string)
			if ref == "" {
				ref = row["unit"].(string)
			}
			s, i, _ := strings.Cut(row["unit"].(string), "/")
			// An audit/platform event without of names no subsystem unit and needs view on *.
			unitRow := sub != "audit" && sub != "console" || row["of"] != ""
			u := &MayUnit{Kind: "unit", Sub: s, ID: i}
			labelSource := u
			if row["of"] != "" {
				s, i, _ := strings.Cut(ref, "/")
				u.About = &MayUnit{Kind: "unit", Sub: s, ID: i}
				labelSource = u.About
			}
			if sub == "audit" || sub == "console" {
				// A platform row has no own subsystem unit; only its nonempty of can name one.
				u = labelSource
			}
			labels, exists := units[ref]
			unknown := labels == "@unreadable"
			if exists && !unknown {
				var ok bool
				labelSource.Labels, ok = stringList(labels, false)
				if !ok {
					return nil, ErrRefuse
				}
			}
			u.AboutUnknown = unknown
			allowed, byLabels := false, false
			for _, grant := range grants {
				byLabels = byLabels || strings.HasPrefix(grant, "labels:")
				if unitRow && ScopeCovers(grant, u) {
					allowed = true
				}
			}
			if !allowed {
				if unitRow && unknown && byLabels {
					withheld[ref] = true
				}
				continue
			}
		}
		visible = append(visible, row)
	}
	selected, skipped := CutEvents(visible, q)
	truncated.Add(truncated, big.NewInt(int64(skipped)))
	out := map[string]any{"events": selected, "state": state, "truncated": json.Number(truncated.String()), "complete": len(incomplete) == 0, "incomplete": incomplete}
	if partial {
		out["partial"] = true
	}
	if garbled.Sign() > 0 {
		out["lines_garbled"] = json.Number(garbled.String())
	}
	if len(withheld) > 0 {
		refs := []string{}
		for ref := range withheld {
			refs = append(refs, ref)
		}
		sort.Strings(refs)
		out["withheld"] = refs
	}
	return out, nil
}
