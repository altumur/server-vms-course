package example

import "kitmodule/internal/vectoradapter"

// The adapter is yours (internal/vectoradapter, put once): replace the bodies with calls of your code, keep the
// signatures. Then: go test ./internal/vectortests -run '^TestJcs_'; the vector command is bin/vectors {input}.
var (
	_ func(raw []byte) ([]byte, error)                                = vectoradapter.Canonical  // RFC 8785 text
	_ func(file []byte) (func(role, action, key string) bool, error) = vectoradapter.LoadRights // the evaluator
)

// canonicalOrEmpty — how your code calls it (a sketch).
func canonicalOrEmpty(raw []byte) []byte {
	out, err := vectoradapter.Canonical(raw)
	if err != nil {
		return nil
	}
	return out
}
