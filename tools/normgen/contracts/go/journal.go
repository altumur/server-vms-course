package contracts

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"math"
	"regexp"
	"strconv"
	"strings"
	"time"
)

// Event journal contract (common/contracts/event-journal.md): the line, the bucket, file names in shared trees.

const (
	JSONDepth   = 128 // the depth of a whole line, the root object — 1
	TempReserve = 16  // the reserve of the temporary name of the writer
	NameMax     = 255 // the longest file name
	BucketSpan  = 600 // seconds
)

// EncodeComponent — a byte from [a-z0-9._-] as is, any other UTF-8 byte as %xx lowercase; «.» — %2e, «..» — %2e%2e.
func EncodeComponent(c string) string {
	switch c {
	case ".":
		return "%2e"
	case "..":
		return "%2e%2e"
	}
	var b strings.Builder
	for i := 0; i < len(c); i++ {
		x := c[i]
		if (x >= 'a' && x <= 'z') || (x >= '0' && x <= '9') || x == '.' || x == '_' || x == '-' {
			b.WriteByte(x)
			continue
		}
		b.WriteString("%" + hex.EncodeToString([]byte{x}))
	}
	return b.String()
}

// overThreshold — the encoded component, its norm suffix and TEMP_RESERVE are longer than 255 bytes.
func overThreshold(component, suffix string) bool {
	return len(EncodeComponent(component))+len(suffix)+TempReserve > NameMax
}

// FileName — the name of a component on disk: the encoding, or %h<sha256 hex> past the threshold; + the norm suffix.
func FileName(component, suffix string) string {
	if overThreshold(component, suffix) {
		sum := sha256.Sum256([]byte(component))
		return "%h" + hex.EncodeToString(sum[:]) + suffix
	}
	return EncodeComponent(component) + suffix
}

// ReadHashedName — a %h entry by its .name file (nil — no file): the source component, or false — the entry is
// skipped with a count (no .name, a mismatching sha256 or a component that does not pass the threshold).
func ReadHashedName(entry, suffix string, nameFile *string) (string, bool) {
	if !strings.HasPrefix(entry, "%h") || !strings.HasSuffix(entry, suffix) || nameFile == nil {
		return "", false
	}
	sum := sha256.Sum256([]byte(*nameFile))
	if entry[2:len(entry)-len(suffix)] != hex.EncodeToString(sum[:]) || !overThreshold(*nameFile, suffix) {
		return "", false
	}
	return *nameFile, true
}

// WriteHashedName — the writer and the .name file (nil — none): "write", "keep" (it matches) or "refuse" (damage).
func WriteHashedName(component string, nameFile *string) string {
	switch {
	case nameFile == nil:
		return "write"
	case *nameFile == component:
		return "keep"
	}
	return "refuse"
}

// BucketName — <YYYYMMDDTHHMMSSZ>.events.jsonl of the 600-second bucket of t (UTC); a year past 9999 — ErrRefuse.
func BucketName(t float64) (string, error) {
	if t < 0 || math.IsNaN(t) || math.IsInf(t, 0) {
		return "", ErrRefuse
	}
	start := math.Floor(t/BucketSpan) * BucketSpan
	at := time.Unix(int64(start), 0).UTC()
	if at.Year() > 9999 {
		return "", ErrRefuse
	}
	return at.Format("20060102T150405Z") + ".events.jsonl", nil
}

func depth(v any) int {
	switch x := v.(type) {
	case map[string]any:
		d := 0
		for _, e := range x {
			if n := depth(e); n > d {
				d = n
			}
		}
		return d + 1
	case []any:
		d := 0
		for _, e := range x {
			if n := depth(e); n > d {
				d = n
			}
		}
		return d + 1
	}
	return 0
}

// AppendLine — the bucket after appending line: a tail without LF is completed with LF (no truncation); a line deeper
// than JSON_DEPTH — ErrRefuse, the file does not change.
func AppendLine(file, line string) (string, error) {
	dec := json.NewDecoder(strings.NewReader(line))
	dec.UseNumber()
	var v any
	if dec.Decode(&v) != nil || depth(v) > JSONDepth {
		return "", ErrRefuse
	}
	if file != "" && !strings.HasSuffix(file, "\n") {
		file += "\n"
	}
	return file + line + "\n", nil
}

var readerTime = regexp.MustCompile(`^(0|[1-9][0-9]*)(\.[0-9]{1,3})?$`)

// timeOK — a time by the reader's codec: a JSON number or string ^(0|[1-9][0-9]*)(\.[0-9]{1,3})?$, finite in binary64.
func timeOK(v any) bool {
	var text string
	switch x := v.(type) {
	case json.Number:
		text = string(x)
	case string:
		text = x
	default:
		return false
	}
	if !readerTime.MatchString(text) {
		return false
	}
	f, err := strconv.ParseFloat(text, 64)
	return err == nil && !math.IsInf(f, 0)
}

// BucketRead — the outcome of reading a bucket: the ids in file order, torn (the last fragment without LF), garbled
// (full lines not by the form line), duplicate (dropped repeats of id, the first line wins).
type BucketRead struct {
	IDs       []string
	Torn      int
	Garbled   int
	Duplicate int
}

// ReadBucket — a bucket file by the form line: a JSON object, t a time, kind and id strings, occurred a time if
// present, depth ≤ JSON_DEPTH.
func ReadBucket(file []byte) BucketRead {
	out := BucketRead{IDs: []string{}}
	seen := map[string]bool{}
	parts := bytes.Split(file, []byte("\n"))
	if last := parts[len(parts)-1]; len(last) > 0 {
		out.Torn = 1
	}
	for _, line := range parts[:len(parts)-1] {
		dec := json.NewDecoder(bytes.NewReader(line))
		dec.UseNumber()
		var v any
		obj, ok := map[string]any(nil), dec.Decode(&v) == nil
		if ok {
			if _, err := dec.Token(); err == nil {
				ok = false
			}
			obj, _ = v.(map[string]any)
		}
		id, idOK := obj["id"].(string)
		_, kindOK := obj["kind"].(string)
		occ, hasOcc := obj["occurred"]
		if !ok || obj == nil || !idOK || !kindOK || !timeOK(obj["t"]) || (hasOcc && !timeOK(occ)) || depth(v) > JSONDepth {
			out.Garbled++
			continue
		}
		if seen[id] {
			out.Duplicate++
			continue
		}
		seen[id] = true
		out.IDs = append(out.IDs, id)
	}
	return out
}
