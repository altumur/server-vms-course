package contracts

import (
	"math"
	"math/big"
	"regexp"
	"strconv"
)

// Schema contract (common/contracts/schema.md): the check of the row platform/schema at start.

// ReaderTime — «Time in a row» in the reader's notation (common/data/codec.tsv time): a finite binary64.
func ReaderTime(s string) (float64, bool) {
	if !readerTime.MatchString(s) {
		return 0, false
	}
	v, err := strconv.ParseFloat(s, 64)
	return v, err == nil && !math.IsInf(v, 0)
}

var decimalRE = regexp.MustCompile(`^-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]{1,4})?$`)

// ExactInteger — an integer in the reader's notation (common/data/codec.tsv integer: a decimal notation whose exact
// value is an integer, 1.0 — 1), without a machine bound (the schema version, as a slot number).
func ExactInteger(s string) (*big.Int, bool) {
	if !decimalRE.MatchString(s) {
		return nil, false
	}
	r, ok := new(big.Rat).SetString(s)
	if !ok || !r.IsInt() {
		return nil, false
	}
	return r.Num(), true
}

// SchemaRow — the elements of platform/schema as text (nil — there is no row).
type SchemaRow struct {
	Version  string
	At       string
	Revision *string
}

// SchemaCheck — the outcome of check: Start with Version, or a refusal Refuse "too_new" with the exact N, or
// "not_a_form".
type SchemaCheck struct {
	Start   bool
	Version string
	Refuse  string
	N       string
}

// CheckSchema — check(row, SCHEMA): no row — the own SCHEMA; the version an exact integer ≥ 1 without overflow, at a
// moment of the row; version > SCHEMA — too_new with N; out of form — not_a_form.
func CheckSchema(row *SchemaRow, schema int64) SchemaCheck {
	if row == nil {
		return SchemaCheck{Start: true, Version: strconv.FormatInt(schema, 10)}
	}
	bad := SchemaCheck{Refuse: "not_a_form"}
	v, ok := ExactInteger(row.Version)
	if !ok || v.Sign() <= 0 {
		return bad
	}
	if _, ok := ReaderTime(row.At); !ok {
		return bad
	}
	if row.Revision != nil {
		if r, ok := ExactInteger(*row.Revision); !ok || r.Sign() <= 0 {
			return bad
		}
	}
	if v.Cmp(big.NewInt(schema)) > 0 {
		return SchemaCheck{Refuse: "too_new", N: v.String()}
	}
	return SchemaCheck{Start: true, Version: v.String()}
}
