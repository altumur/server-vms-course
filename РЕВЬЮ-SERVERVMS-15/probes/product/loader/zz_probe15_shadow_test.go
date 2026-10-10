package w2cplatform_test

// Probe 15/A-C: a spec whose table (or rows) is named like one of the console's own routes loads in the product, and
// the console then answers the table where its own route stood (tableRoute runs before the GET switch, console.go
// Handler). The course refuses such a spec at load (spec.CONSOLE_ROUTES). Prints MEASURED lines.

import (
	"net/http/httptest"
	"strings"
	"testing"

	"vmsworker.local/vmsworker/testbox"
	p "vmsworker.local/vmsworker/w2cplatform"
)

const shadowYAML = `
name: shadow
unit:
  rows: things
  id: name
  fields:
    name: {type: string, required: true}
placement:
  capacity: {from: capacity, default: 4}
tables:
  metrics:
    key: name
    fields:
      name: {type: string, required: true}
  events:
    key: name
    fields:
      name: {type: string, required: true}
`

const shadowRowsYAML = `
name: shadow2
unit:
  rows: servers
  id: name
  fields:
    name: {type: string, required: true}
placement:
  capacity: {from: capacity, default: 4}
`

func TestProbe15ATableNamedLikeAConsoleRouteShadowsIt(t *testing.T) {
	for _, tc := range []struct{ yaml, path, want string }{
		{shadowYAML, "/metrics", "text/plain"},
		{shadowYAML, "/events", "events"},
		{shadowRowsYAML, "/servers", "servers"},
	} {
		v, perr := p.ParseYAML(tc.yaml)
		if perr != nil {
			t.Fatal(perr)
		}
		s, err := p.SpecFromMap(v.(map[string]any))
		if err != nil {
			t.Logf("MEASURED %s: the loader refused: %v", tc.path, err)
			continue
		}
		box := testbox.NewBox()
		c := p.NewSpecConsole(p.NewSpecController(s, varsOf(box), box.Objects, 4, box.Wall.Now, "cluster-a"),
			p.ConsoleOptions{LostAfter: 45, Wall: box.Wall.Now})
		rec := httptest.NewRecorder()
		c.Handler().ServeHTTP(rec, httptest.NewRequest("GET", tc.path, nil))
		body := strings.TrimSpace(rec.Body.String())
		if len(body) > 160 {
			body = body[:160]
		}
		t.Logf("MEASURED spec %s loaded; GET %s -> %d %s %q", s.Name, tc.path, rec.Code, rec.Header().Get("Content-Type"), body)
	}
}
