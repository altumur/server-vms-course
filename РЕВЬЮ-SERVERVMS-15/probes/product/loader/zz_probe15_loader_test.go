package w2cplatform_test

// Probe 15/A: the product loader's verdict on every case of PROBE15_DIR (copied into the snapshot's w2cplatform
// package to run; never into the working tree). Prints: <case>\t<ok|refused>\t<message or parsed facts>.

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"

	p "vmsworker.local/vmsworker/w2cplatform"
)

func TestProbe15LoaderVerdicts(t *testing.T) {
	dir := os.Getenv("PROBE15_DIR")
	if dir == "" {
		t.Skip("PROBE15_DIR unset")
	}
	files, _ := filepath.Glob(filepath.Join(dir, "*.subsystem.yaml"))
	sort.Strings(files)
	out, _ := os.Create(filepath.Join(dir, "product_verdicts.tsv"))
	defer out.Close()
	for _, f := range files {
		name := strings.TrimSuffix(filepath.Base(f), ".subsystem.yaml")
		s, err := p.LoadSpec(f)
		if err != nil {
			msg := strings.TrimPrefix(err.Error(), f+": ")
			if len(msg) > 220 {
				msg = msg[:220]
			}
			fmt.Fprintf(out, "%s\trefused\t%s\n", name, strings.ReplaceAll(msg, "\n", " "))
			continue
		}
		var facts []string
		if fs, ok := s.Fields["feed_secret"]; ok {
			facts = append(facts, fmt.Sprintf("bound_to=%v", fs.BoundTo))
		}
		if fs, ok := s.Fields["of"]; ok {
			facts = append(facts, fmt.Sprintf("of.fixed=%v", fs.Fixed))
		}
		if fs, ok := s.Fields["name"]; ok {
			facts = append(facts, fmt.Sprintf("name.required=%v", fs.Required))
		}
		if fs, ok := s.Fields["mode"]; ok {
			facts = append(facts, fmt.Sprintf("mode.enum=%v", fs.Enum))
		}
		facts = append(facts, fmt.Sprintf("requires=%s servers=%s tie_break=%s id=%s", s.Requires, s.Servers, s.TieBreak, s.ID))
		fmt.Fprintf(out, "%s\tok\t%s\n", name, strings.Join(facts, " "))
	}
}
