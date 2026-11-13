// Handwritten environment of gen_box.py; closed in a kit, origin handwritten.
package box

import (
	"fmt"
	"math"
	"math/big"
	"regexp"
	"strconv"
	"strings"
	"time"
)

// CopyOptions are the actual command inputs. Now is supplied by the host's wall
// clock for each invocation; tests can supply it without replacing the procedure.
// IndexBase is explicit for import; restore takes the portable header's index.
type CopyOptions struct {
	IndexBase uint64
	Force     bool
	Now       time.Time
}

// CopyRefusal reports the phase which refused without hiding its actual cause.
type CopyRefusal struct {
	Phase string
	Cause string
}

func (e *CopyRefusal) Error() string { return "copy " + e.Phase + ": " + e.Cause }

func copyRefuse(phase, format string, args ...any) error {
	return &CopyRefusal{Phase: phase, Cause: fmt.Sprintf(format, args...)}
}

var copyTimeRE = regexp.MustCompile(`^(0|[1-9][0-9]*)(\.[0-9]{1,3})?$`)

// readCopyTime applies P/01.1 N0 reader grammar and the finite binary64 bound.
// Exact rationals retain the accepted millisecond precision when comparing to
// the wall clock. The writer's new generation_at is truncated to milliseconds.
func readCopyTime(s string) (*big.Rat, bool) {
	if !copyTimeRE.MatchString(s) {
		return nil, false
	}
	f, err := strconv.ParseFloat(s, 64)
	if err != nil || math.IsInf(f, 0) || math.IsNaN(f) {
		return nil, false
	}
	r, ok := new(big.Rat).SetString(s)
	return r, ok
}

func copyNowText(now time.Time) (string, error) {
	if now.Unix() < 0 {
		return "", copyRefuse("Check", "the wall clock is before the Unix epoch")
	}
	s := strconv.FormatInt(now.Unix(), 10)
	if ms := now.Nanosecond() / int(time.Millisecond); ms != 0 {
		s += "." + strings.TrimRight(fmt.Sprintf("%03d", ms), "0")
	}
	return s, nil
}

func checkCopyUpperAndClock(rows []Row, opts CopyOptions) error {
	now := new(big.Rat).SetInt64(opts.Now.Unix())
	now.Add(now, big.NewRat(int64(opts.Now.Nanosecond()), int64(time.Second)))
	for _, row := range rows {
		if row.Key == FloorKey {
			if row.Unreadable || !decimalItem(row.Items, "floor") {
				return copyRefuse("Check", "unreliable saved/input floor")
			}
			at, ok := readCopyTime(row.Items["generation_at"])
			if !ok {
				return copyRefuse("Check", "generation_at is not a time")
			}
			if !opts.Force && now.Cmp(at) < 0 {
				return copyRefuse("Check", "clock_early: wall clock precedes generation_at")
			}
		} else if epochKey.MatchString(row.Key) && (row.Unreadable || !decimalItem(row.Items, "epoch")) {
			return copyRefuse("Check", "unreliable saved/input epoch: %s", row.Key)
		}
	}
	return nil
}

func checkCopyPreflight(index uint64, rows []Row, opts CopyOptions) error {
	if opts.IndexBase < index {
		return copyRefuse("Check", "index-base is below the copy index")
	}
	if opts.IndexBase == math.MaxUint64 {
		return copyRefuse("Check", "version overflow")
	}
	if _, err := copyNowText(opts.Now); err != nil {
		return err
	}
	if err := checkCopyUpperAndClock(rows, opts); err != nil {
		return err
	}
	// Only the immutable input's bound can be checked here. A continuation
	// never allocates a generation from the current clock, even much later.
	if _, _, ok := Floor(Upper(rows, nil), Since); !ok {
		return copyRefuse("Check", "generation overflow")
	}
	return nil
}

// CopyStartAllowed is the host's ordinary startup/read/write gate. A host must
// call it using the actual durable progress; it must not discard a pending mark
// when a daemon restarts. Startup maps its refusal to code 2; an in-process store
// maps it to 503 unavailable. Only the import continuation bypasses this gate.
func CopyStartAllowed(progress *ImportProgress) error {
	if progress != nil && progress.Phase != "Done" {
		return copyRefuse(progress.Phase, "unfinished import; repeat import with the same input")
	}
	return nil
}
