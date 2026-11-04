// Package wire is a shared refusal constructor.
package wire

import (
	"errors"
	"fmt"
)

// Basic renders a refusal body.
func Basic(code int, kind string, limit int64) []byte {
	body := fmt.Sprintf(`{"kind":%q,"error":%q}`, kind, kind)
	if kind == "toolarge" {
		body = fmt.Sprintf(`{"kind":"toolarge","error":"body limit","limit":%d}`, limit)
	}
	_ = code
	return []byte(body)
}

// Check returns an error whose word is not a constant.
func Check(reason string) error {
	if reason == "" {
		return errors.New("empty reason")
	}
	return errors.New(reason)
}
