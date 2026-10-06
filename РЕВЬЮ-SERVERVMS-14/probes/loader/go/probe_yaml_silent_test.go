package w2cplatform_test

// probe_yaml_silent_test.go — PRODUCT tree (ADR-0012 strict loader, ADR-0019 one YAML). Drop into
// vmsworker/w2cplatform/ (or run with `go test -overlay`) and `go test -run TestProbeYAMLSilent ./vmsworker/w2cplatform/`.
// Expected by ADR-0012: each spec below is REFUSED (a key is ignored, not refused). Measured at 2d46e95: all four
// are ACCEPTED — the test FAILS while the defects stand (two specs read by the parser as other than they are written).

import (
	"os"
	"path/filepath"
	"testing"

	p "vmsworker.local/vmsworker/w2cplatform"
)

const probeBase = `name: probe
unit:
  rows: counters
  id: name
  fields:
    name: {type: string, required: true}
placement:
  capacity: {from: capacity, default: 4}
`

func TestProbeYAMLSilent(t *testing.T) {
	cases := map[string]string{
		// a duplicate key: the first is dropped, the second wins (lease forever, though `off` is written first)
		"duplicate_key": probeBase + "lease: {unconfirmed_max: off}\nlease: {unconfirmed_max: forever}\n",
		// a duplicate inside a flow map
		"duplicate_in_flow": probeBase + "lease: {unconfirmed_max: off, unconfirmed_max: forever}\n",
		// a folded scalar: ParseYAML stops at the deeper line and drops the rest of the file, unknown key included
		"block_scalar_drops_tail": probeBase + "display:\n  unit: >\n    counter\nbogus_after: 1\n",
		// a plain scalar continued on the next line: the same
		"continued_scalar_drops_tail": probeBase + "display:\n  unit: counter\n    of things\nbogus_after: 1\n",
	}
	dir := t.TempDir()
	for name, src := range cases {
		f := filepath.Join(dir, name+".subsystem.yaml")
		if err := os.WriteFile(f, []byte(src), 0o644); err != nil {
			t.Fatal(err)
		}
		if s, err := p.LoadSpec(f); err == nil {
			t.Errorf("%s: loaded (unconfirmed_max=%s) — a key was ignored, not refused (ADR-0012)", name, s.UnconfirmedMax)
		}
	}
}
