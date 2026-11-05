// Harness of family_judge.py: reads cases (JSON lines {family, key, mode, who, text}) from stdin, answers each with
// {verdict, paths, outcome} by the generated package families (the format of Platform/common/vectors/family-read).
package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"

	"normgen/p01-1/families"
)

type caseIn struct {
	Family string   `json:"family"`
	Key    string   `json:"key"`
	Mode   string   `json:"mode"`
	Who    []string `json:"who"`
	Text   string   `json:"text"`
}

func main() {
	in := bufio.NewScanner(os.Stdin)
	in.Buffer(make([]byte, 1<<20), 1<<24)
	out := json.NewEncoder(os.Stdout)
	for in.Scan() {
		var c caseIn
		if err := json.Unmarshal(in.Bytes(), &c); err != nil {
			fmt.Fprintln(os.Stderr, "harness:", err)
			os.Exit(2)
		}
		f := families.ByKey(c.Family)
		if f == nil {
			_ = out.Encode(map[string]any{"error": "no family " + c.Family})
			continue
		}
		mode := families.Reader
		if c.Mode == "writer" {
			mode = families.Writer
		}
		var r families.Result
		if jt, ok := any(f).(interface {
			JudgeText(string, []byte, families.Mode) families.Result
		}); ok && f.Kind != "row" {
			r = jt.JudgeText(c.Key, []byte(c.Text), mode) // object, file (the schema mode)
		} else {
			r = f.Judge(c.Key, families.ParseItems([]byte(c.Text)), mode)
		}
		var outcome any = []string{}
		if mode == families.Reader {
			m := map[string][]string{}
			for _, role := range c.Who {
				m[role] = f.OutcomesFor(r.Paths, role)
			}
			outcome = m
		}
		_ = out.Encode(map[string]any{"verdict": r.Verdict, "paths": r.Paths, "outcome": outcome})
	}
}
