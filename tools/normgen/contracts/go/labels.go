package contracts

import (
	"encoding/json"
	"regexp"
	"sort"
	"strings"
)

// Labels contract (common/contracts/labels.md).

var labelRE = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$`)

// ValidLabel — 1–64 ASCII: the first a letter or a digit, then letters, digits, «_», «.», «:», «-».
func ValidLabel(s string) bool { return labelRE.MatchString(s) }

// LabelSetWrite — the text the platform writes for a label set: ascending UTF-8 bytes, comma-separated; a label not
// by the alphabet or a repeat — ErrRefuse.
func LabelSetWrite(labels []string) (string, error) {
	seen := map[string]bool{}
	for _, l := range labels {
		if !ValidLabel(l) || seen[l] {
			return "", ErrRefuse
		}
		seen[l] = true
	}
	out := append([]string{}, labels...)
	sort.Strings(out)
	return strings.Join(out, ","), nil
}

// splitLabels — a list text: a leading «[» — a JSON array of labels; otherwise comma-separated; "" — none.
func splitLabels(text string) ([]string, error) {
	if text == "" {
		return []string{}, nil
	}
	if strings.HasPrefix(text, "[") {
		var arr []string
		if json.Unmarshal([]byte(text), &arr) != nil {
			return nil, ErrRefuse
		}
		return arr, nil
	}
	return strings.Split(text, ","), nil
}

// LabelTextRead — a label list read: every element by the alphabet, no empty element, no repeat; → ascending bytes.
func LabelTextRead(text string) ([]string, error) {
	items, err := splitLabels(text)
	if err != nil {
		return nil, err
	}
	seen := map[string]bool{}
	for _, l := range items {
		if !ValidLabel(l) || seen[l] {
			return nil, ErrRefuse
		}
		seen[l] = true
	}
	sort.Strings(items)
	return items, nil
}

// EnvLabels — LABELS of the worker environment: every label by the alphabet (otherwise a start refusal); a repeat is
// compacted; → the set in ascending bytes.
func EnvLabels(text string) ([]string, error) {
	items, err := splitLabels(text)
	if err != nil {
		return nil, err
	}
	set := map[string]bool{}
	for _, l := range items {
		if !ValidLabel(l) {
			return nil, ErrRefuse
		}
		set[l] = true
	}
	out := make([]string, 0, len(set))
	for l := range set {
		out = append(out, l)
	}
	sort.Strings(out)
	return out, nil
}
