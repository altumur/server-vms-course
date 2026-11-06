package checks

// CEL subset runtime for gen_checks.py output (ADR-0120, item 2(a)).
// The generator copies this beside checks.go;table code calls only these functions.
// CEL values:nil(null), bool, int64, float64, string, []any, map[string]any, celType, *celErr.
// CEL errors are *celErr values, not panics, so boolean operators can absorb them(false&&error=false).
// Semantics match check_tables.py's cel-expr-python oracle.

import (
	"fmt"
	"math"
	"regexp"
	"strconv"
	"strings"
	"unicode/utf8"
)

// celErr is a CEL error value, the oracle's error status.
type celErr struct{ msg string }

// celType is a type() result or type-name value.
type celType string

const (
	typeBool    celType = "bool"
	typeInt     celType = "int"
	typeDouble  celType = "double"
	typeString  celType = "string"
	typeList    celType = "list"
	typeMap     celType = "map"
	typeNull    celType = "null_type"
	typeType    celType = "type"
	typeUnknown celType = "unknown"
)

func errf(format string, args ...any) any { return &celErr{fmt.Sprintf(format, args...)} }

func isErr(v any) bool { _, ok := v.(*celErr); return ok }

func isTrue(v any) bool { b, ok := v.(bool); return ok && b }

func isFalse(v any) bool { b, ok := v.(bool); return ok && !b }

func kindOf(v any) celType {
	switch v.(type) {
	case nil:
		return typeNull
	case bool:
		return typeBool
	case int64:
		return typeInt
	case float64:
		return typeDouble
	case string:
		return typeString
	case []any:
		return typeList
	case map[string]any:
		return typeMap
	case celType:
		return typeType
	}
	return typeUnknown
}

func noOverload(op string, args ...any) any {
	kinds := make([]string, len(args))
	for i, a := range args {
		if isErr(a) {
			kinds[i] = "error"
		} else {
			kinds[i] = string(kindOf(a))
		}
	}
	return errf("no matching overload: %s(%s)", op, strings.Join(kinds, ", "))
}

func isNum(v any) bool {
	switch v.(type) {
	case int64, float64:
		return true
	}
	return false
}

func toDouble(v any) float64 {
	if i, ok := v.(int64); ok {
		return float64(i)
	}
	return v.(float64)
}

// numCmp returns-1/0/1;ok=false for NaN/incomparability.Compare ints exactly, mixed int/double via double like cel-cpp.
func numCmp(a, b any) (int, bool) {
	ia, aInt := a.(int64)
	ib, bInt := b.(int64)
	if aInt && bInt {
		switch {
		case ia < ib:
			return -1, true
		case ia > ib:
			return 1, true
		}
		return 0, true
	}
	x, y := toDouble(a), toDouble(b)
	switch {
	case x < y:
		return -1, true
	case x > y:
		return 1, true
	case x == y:
		return 0, true
	}
	return 0, false
}

// eqv compares non-error values using CEL heterogeneous equality.
func eqv(a, b any) bool {
	if isNum(a) && isNum(b) {
		c, ok := numCmp(a, b)
		return ok && c == 0
	}
	switch x := a.(type) {
	case nil:
		return b == nil
	case bool:
		y, ok := b.(bool)
		return ok && x == y
	case string:
		y, ok := b.(string)
		return ok && x == y
	case celType:
		y, ok := b.(celType)
		return ok && x == y
	case []any:
		y, ok := b.([]any)
		if !ok || len(x) != len(y) {
			return false
		}
		for i := range x {
			if !eqv(x[i], y[i]) {
				return false
			}
		}
		return true
	case map[string]any:
		y, ok := b.(map[string]any)
		if !ok || len(x) != len(y) {
			return false
		}
		for k, v := range x {
			w, found := y[k]
			if !found || !eqv(v, w) {
				return false
			}
		}
		return true
	}
	return false
}

func celEq(a, b any) any {
	if isErr(a) {
		return a
	}
	if isErr(b) {
		return b
	}
	return eqv(a, b)
}

func celNe(a, b any) any {
	r := celEq(a, b)
	if isErr(r) {
		return r
	}
	return !r.(bool)
}

func order(op string, a, b any) any {
	if isErr(a) {
		return a
	}
	if isErr(b) {
		return b
	}
	var c int
	switch {
	case isNum(a) && isNum(b):
		var ok bool
		if c, ok = numCmp(a, b); !ok {
			return false
		}
	default:
		sa, aStr := a.(string)
		sb, bStr := b.(string)
		ba, aBool := a.(bool)
		bb, bBool := b.(bool)
		switch {
		case aStr && bStr:
			c = strings.Compare(sa, sb)
		case aBool && bBool:
			c = 0
			if !ba && bb {
				c = -1
			} else if ba && !bb {
				c = 1
			}
		default:
			return noOverload(op, a, b)
		}
	}
	switch op {
	case "<":
		return c < 0
	case "<=":
		return c <= 0
	case ">":
		return c > 0
	}
	return c >= 0
}

func celLt(a, b any) any { return order("<", a, b) }
func celLe(a, b any) any { return order("<=", a, b) }
func celGt(a, b any) any { return order(">", a, b) }
func celGe(a, b any) any { return order(">=", a, b) }

func celIn(x, c any) any {
	if isErr(x) {
		return x
	}
	if isErr(c) {
		return c
	}
	switch cc := c.(type) {
	case []any:
		for _, el := range cc {
			if eqv(x, el) {
				return true
			}
		}
		return false
	case map[string]any:
		// Map keys:string, bool, int, double.JSON keys are strings;other valid types miss.Other types error.
		switch k := x.(type) {
		case string:
			_, found := cc[k]
			return found
		case bool, int64, float64:
			return false
		}
	}
	return noOverload("in", x, c)
}

func celNot(v any) any {
	if b, ok := v.(bool); ok {
		return !b
	}
	if isErr(v) {
		return v
	}
	return noOverload("!", v)
}

// celOr handles a||b when a is not true;true absorbs errors from either side.
func celOr(a, b any) any {
	if isTrue(b) {
		return true
	}
	if isFalse(a) && isFalse(b) {
		return false
	}
	if isErr(a) {
		return a
	}
	if isErr(b) {
		return b
	}
	return noOverload("||", a, b)
}

// celAnd handles a&&b when a is not false;false absorbs errors from either side.
func celAnd(a, b any) any {
	if isFalse(b) {
		return false
	}
	if isTrue(a) && isTrue(b) {
		return true
	}
	if isErr(a) {
		return a
	}
	if isErr(b) {
		return b
	}
	return noOverload("&&", a, b)
}

func celSelect(v any, field string) any {
	switch m := v.(type) {
	case map[string]any:
		if x, ok := m[field]; ok {
			return x
		}
		return errf("no such key: %s", field)
	case *celErr:
		return v
	}
	return errf("select .%s on %s", field, kindOf(v))
}

func celHas(v any, field string) any {
	switch m := v.(type) {
	case map[string]any:
		_, ok := m[field]
		return ok
	case *celErr:
		return v
	}
	return errf("has(.%s) on %s", field, kindOf(v))
}

func celIndex(v, k any) any {
	if isErr(v) {
		return v
	}
	if isErr(k) {
		return k
	}
	switch c := v.(type) {
	case []any:
		var i int64
		switch kk := k.(type) {
		case int64:
			i = kk
		case float64:
			if kk != math.Trunc(kk) || math.Abs(kk) >= math.Exp2(63) {
				return errf("index: expected integer, got double")
			}
			i = int64(kk)
		default:
			return errf("index: expected integer, got %s", kindOf(k))
		}
		if i < 0 || i >= int64(len(c)) {
			return errf("index %d out of range %d", i, len(c))
		}
		return c[i]
	case map[string]any:
		if s, ok := k.(string); ok {
			if x, found := c[s]; found {
				return x
			}
		}
		return errf("no such key: %v", k)
	}
	return errf("index on %s", kindOf(v))
}

func celSize(v any) any {
	switch x := v.(type) {
	case string:
		return int64(utf8.RuneCountInString(x))
	case []any:
		return int64(len(x))
	case map[string]any:
		return int64(len(x))
	case *celErr:
		return v
	}
	return noOverload("size", v)
}

func celString(v any) any {
	switch x := v.(type) {
	case string:
		return x
	case bool:
		if x {
			return "true"
		}
		return "false"
	case int64:
		return strconv.FormatInt(x, 10)
	case float64:
		return strconv.FormatFloat(x, 'g', 17, 64)
	case *celErr:
		return v
	}
	return noOverload("string", v)
}

func celAdd(a, b any) any {
	if isErr(a) {
		return a
	}
	if isErr(b) {
		return b
	}
	switch x := a.(type) {
	case string:
		if y, ok := b.(string); ok {
			return x + y
		}
	case []any:
		if y, ok := b.([]any); ok {
			out := make([]any, 0, len(x)+len(y))
			return append(append(out, x...), y...)
		}
	case int64:
		if y, ok := b.(int64); ok {
			r := x + y
			if (r > x) != (y > 0) {
				return errf("integer overflow")
			}
			return r
		}
	case float64:
		if y, ok := b.(float64); ok {
			return x + y
		}
	}
	return noOverload("+", a, b)
}

func celTypeOf(v any) any {
	if isErr(v) {
		return v
	}
	if k := kindOf(v); k != typeUnknown {
		return k
	}
	return errf("type of unknown value")
}

func celStartsWith(s, p any) any {
	if isErr(s) {
		return s
	}
	if isErr(p) {
		return p
	}
	ss, ok1 := s.(string)
	ps, ok2 := p.(string)
	if ok1 && ok2 {
		return strings.HasPrefix(ss, ps)
	}
	return noOverload("startsWith", s, p)
}

func celMatches(s any, rx *regexp.Regexp) any {
	switch x := s.(type) {
	case string:
		return rx.MatchString(x)
	case *celErr:
		return s
	}
	return noOverload("matches", s)
}

func mkList(vals ...any) any {
	for _, v := range vals {
		if isErr(v) {
			return v
		}
	}
	return vals
}

func mkMap(keys []string, vals ...any) any {
	out := make(map[string]any, len(keys))
	for i, v := range vals {
		if isErr(v) {
			return v
		}
		out[keys[i]] = v
	}
	return out
}

func rangeErr(r any) any {
	if isErr(r) {
		return r
	}
	return noOverload("<iter_range>", r)
}

// predErr keeps the first exists error;a non-bool result is also an error.
func predErr(err, b any) any {
	if err != nil {
		return err
	}
	if isErr(b) {
		return b
	}
	return noOverload("||", false, b)
}

func status(v any) string {
	switch {
	case isTrue(v):
		return "true"
	case isFalse(v):
		return "false"
	}
	return "error"
}

func errText(v any) string {
	if e, ok := v.(*celErr); ok {
		return e.msg
	}
	return fmt.Sprintf("not a map: %s", kindOf(v))
}
