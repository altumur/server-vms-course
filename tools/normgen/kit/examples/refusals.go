package example

import (
	"log"

	"kitmodule/internal/apidoor"
	"kitmodule/internal/refusals"
)

// guardMismatch — a refusal of N4 by its catalogue row: code, kind and fields from forms/refusals.tsv.
func guardMismatch(key, index string) apidoor.Answer {
	s := refusals.GuardMismatch // 412 guard {key, index}
	a, err := apidoor.Refuse(apidoor.OpWrite, s.Code, s.Kind, "the guard does not hold", map[string]any{"key": key, "index": index})
	if err != nil {
		return apidoor.Answer{Code: 500}
	}
	return a
}

// replayLimit — the caller computes seconds until admission from its own replay budget.
// DynamicHeaders declares the header name; the catalogue does not choose its value.
func replayLimit(seconds int64) apidoor.Answer {
	s := refusals.ReplayLimit
	a, err := apidoor.Refuse(apidoor.OpWrite, s.Code, s.Kind, "replay limit", nil)
	if err != nil {
		return apidoor.Answer{Code: 500}
	}
	a.RetryAfter = &seconds
	return a
}

// startRefused — a start refusal with the log line of its row; returns the exit code.
func startRefused(dir, mark string) int {
	return refusals.StartFormat.Exit(func(s string) { log.Print(s) }, map[string]string{"dir": dir, "mark": mark})
}
