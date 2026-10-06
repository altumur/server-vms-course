// specload: loads each spec file given on the command line with the PRODUCT's loader (w2cplatform.LoadSpec:
// ParseYAML + SpecFromMap) and prints `<file>\tACCEPT|REFUSE\t<why>` — the Go half of probe_spec_loaders.py.
// Run: GOWORK=<this dir>/../go.work go run . <files...>   (go.work names this dir and <product>/vmsworker)
package main

import (
	"fmt"
	"os"
	"strings"
	"time"

	p "vmsworker.local/vmsworker/w2cplatform"
)

func main() {
	for _, f := range os.Args[1:] {
		t0 := time.Now()
		res := make(chan string, 1)
		go func() {
			defer func() {
				if r := recover(); r != nil {
					res <- fmt.Sprintf("PANIC\t%v", r)
				}
			}()
			s, err := p.LoadSpec(f)
			if err != nil {
				res <- "REFUSE\t" + strings.ReplaceAll(err.Error(), "\n", " ")
				return
			}
			res <- fmt.Sprintf("ACCEPT\tname=%s unconfirmed_max=%s", s.Name, s.UnconfirmedMax.String())
		}()
		select {
		case r := <-res:
			fmt.Printf("%s\t%s\t%.2fs\n", f, r, time.Since(t0).Seconds())
		case <-time.After(60 * time.Second):
			fmt.Printf("%s\tHANG\t>60s\n", f)
		}
	}
}
