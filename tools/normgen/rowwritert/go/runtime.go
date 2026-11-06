// Pure row-write constructors. This overlay is compiled in the existing families
// package and uses its JSON, JCS, schema and Writer codecs. It owns no IO port.
package families

import (
	"encoding/json"
	"fmt"
	"regexp"
	"strconv"
	"strings"
	"unicode/utf8"
)

// StateSpec is the state declaration of the manifest accepted with this start.
// Schemas maps each declared state name to its logical value schema. Defs is its
// local reference context. CaptureStateStart takes independent copies of both.
type StateSpec struct {
	Schemas map[string]json.RawMessage
	Defs    map[string]json.RawMessage
}

// StartSnapshot is immutable outside this package. A zero value is not a captured
// start. Copying the value is safe: its private maps are never mutated or exposed.
type StartSnapshot struct {
	start     string
	states    map[string]string
	writerDoc string
	valid     bool
}

// RowWrite is a description for the ordinary SDK's IO procedure. It deliberately
// contains no CAS version, read callback, may_write decision or retry operation.
type RowWrite struct {
	Key   string            `json:"key"`
	Items map[string]string `json:"items"`
	Guard *RowWriteGuard    `json:"guard,omitempty"`
}

type RowWriteGuard struct {
	Key   string `json:"key"`
	Index string `json:"index"`
}

type rwRef struct {
	Source, Pointer, Literal string
}
type rwDeclaration struct{ Source, Pointer, Type string }
type rwField struct{ Field, Source, Pointer, Codec string }
type rwWrite struct {
	Name, Family, Pattern string
	Key, Guard            []rwRef
	Version               *rwRef
	Fields                []rwField
	StateName             rwRef `json:"state_name"`
}
type rwForm struct {
	Declarations   []rwDeclaration
	Writes         []rwWrite
	NamePattern    string   `json:"name_pattern"`
	VersionPattern string   `json:"version_pattern"`
	SchemaWords    []string `json:"schema_words"`
}

var rwBindings = func() rwForm {
	var f rwForm
	if err := json.Unmarshal([]byte(rowWriteBindings), &f); err != nil {
		panic("families: invalid generated row bindings: " + err.Error())
	}
	return f
}()

// rwJSON only frames scalar-UTF8 JSON before the existing codec parses it.
// In particular, no trailing garbage can be mistaken for an EOF, and the Go
// decoder must not replace an unpaired surrogate or malformed UTF8 with U+FFFD.
func rwJSON(raw []byte) (any, error) {
	if !utf8.Valid(raw) || !json.Valid(raw) || !rwScalarEscapes(raw) {
		return nil, fmt.Errorf("row constructor: invalid scalar-UTF8 JSON")
	}
	v, err := strictJSON(string(raw), true)
	if err != nil {
		return nil, fmt.Errorf("row constructor: invalid JSON: %w", err)
	}
	return v, nil
}

// This checks escape well-formedness only; strictJSON does the single decode.
func rwScalarEscapes(raw []byte) bool {
	inside := false
	for i := 0; i < len(raw); i++ {
		if raw[i] == '"' {
			inside = !inside
			continue
		}
		if !inside || raw[i] != '\\' {
			continue
		}
		i++
		if raw[i] != 'u' {
			continue
		}
		n, _ := strconv.ParseUint(string(raw[i+1:i+5]), 16, 16)
		i += 4
		if n >= 0xdc00 && n <= 0xdfff {
			return false
		}
		if n >= 0xd800 && n <= 0xdbff {
			if i+6 >= len(raw) || raw[i+1] != '\\' || raw[i+2] != 'u' {
				return false
			}
			low, err := strconv.ParseUint(string(raw[i+3:i+7]), 16, 16)
			if err != nil || low < 0xdc00 || low > 0xdfff {
				return false
			}
			i += 6
		}
	}
	return true
}

func rwObject(raw []byte) (obj, error) {
	v, err := rwJSON(raw)
	if err != nil {
		return nil, err
	}
	o, ok := v.(obj)
	if !ok {
		return nil, fmt.Errorf("row constructor: source must be an object")
	}
	return o, nil
}

func rwPointer(v any, p string) (any, bool) {
	for _, token := range unpointer(p) {
		switch x := v.(type) {
		case obj:
			var ok bool
			v, ok = x[token]
			if !ok {
				return nil, false
			}
		case []any:
			i, err := strconv.Atoi(token)
			if err != nil || i < 0 || i >= len(x) || strconv.Itoa(i) != token {
				return nil, false
			}
			v = x[i]
		default:
			return nil, false
		}
	}
	return v, true
}

func rwDeclared(source string, value obj) error {
	for _, d := range rwBindings.Declarations {
		if d.Source != source {
			continue
		}
		v, ok := rwPointer(value, d.Pointer)
		if !ok {
			return fmt.Errorf("row constructor: missing %s pointer %s", source, d.Pointer)
		}
		if d.Type != "dyn" && !isType(v, d.Type) {
			return fmt.Errorf("row constructor: %s%s must be %s", source, d.Pointer, d.Type)
		}
		if d.Type == "integer" {
			n := v.(num)
			if !n.isInt {
				return fmt.Errorf("row constructor: %s%s must use exact integer notation", source, d.Pointer)
			}
		}
	}
	return nil
}

// rwSchemaShape checks the existing executor's supported schema vocabulary and
// argument shapes, not the value semantics (those remain with schema.judgeText).
func rwSchemaShape(n node, root node, active map[string]bool) error {
	known := map[string]bool{}
	for _, word := range rwBindings.SchemaWords {
		known[word] = true
	}
	for key, value := range n {
		if !known[key] {
			return fmt.Errorf("row constructor: unsupported schema word %s", key)
		}
		child := func(v any) error {
			x, ok := v.(node)
			if !ok {
				return fmt.Errorf("row constructor: %s requires a schema object", key)
			}
			return rwSchemaShape(x, root, active)
		}
		switch key {
		case "$ref":
			ref, ok := value.(string)
			if !ok || !regexp.MustCompile(`^#(?:/(?:[^~/]|~[01])*)+$`).MatchString(ref) || active[ref] {
				return fmt.Errorf("row constructor: unsupported or cyclic schema reference")
			}
			s := &schema{doc: root}
			target := s.sub(ref)
			if target == nil {
				return fmt.Errorf("row constructor: missing schema reference %s", ref)
			}
			active[ref] = true
			err := rwSchemaShape(target, root, active)
			delete(active, ref)
			if err != nil {
				return err
			}
		case "properties", "$defs", "patternProperties":
			m, ok := value.(node)
			if !ok {
				return fmt.Errorf("row constructor: %s requires an object", key)
			}
			for name, v := range m {
				if key == "patternProperties" {
					if _, err := regexp.Compile(name); err != nil {
						return err
					}
				}
				if err := child(v); err != nil {
					return err
				}
			}
		case "items", "additionalProperties":
			if _, ok := value.(bool); !ok {
				if err := child(value); err != nil {
					return err
				}
			}
		case "if", "then", "else", "not", "propertyNames":
			if err := child(value); err != nil {
				return err
			}
		case "allOf", "anyOf", "oneOf":
			list, ok := value.([]any)
			if !ok || len(list) == 0 {
				return fmt.Errorf("row constructor: %s requires schema objects", key)
			}
			for _, v := range list {
				if err := child(v); err != nil {
					return err
				}
			}
		case "type":
			list, ok := value.([]any)
			if !ok {
				list = []any{value}
			}
			if len(list) == 0 {
				return fmt.Errorf("row constructor: empty schema type")
			}
			seen := map[string]bool{}
			for _, v := range list {
				t, ok := v.(string)
				if !ok || !contains([]string{"object", "array", "string", "integer", "number", "boolean", "null"}, t) || seen[t] {
					return fmt.Errorf("row constructor: unsupported schema type")
				}
				seen[t] = true
			}
		case "enum", "required":
			list, ok := value.([]any)
			if !ok {
				return fmt.Errorf("row constructor: %s requires an array", key)
			}
			if key == "required" {
				seen := map[string]bool{}
				for _, v := range list {
					name, ok := v.(string)
					if !ok || seen[name] {
						return fmt.Errorf("row constructor: required names must be strings")
					}
					seen[name] = true
				}
			}
		case "pattern", "$schema", "description":
			text, ok := value.(string)
			if !ok {
				return fmt.Errorf("row constructor: %s requires a string", key)
			}
			if key == "pattern" {
				if _, err := regexp.Compile(text); err != nil {
					return err
				}
			}
		case "minLength", "maxLength", "minItems", "maxItems", "minProperties", "maxProperties", "x-max-bytes", "x-max-names":
			num, ok := schemaNum(value)
			if !ok || !num.isInt || num.i.Sign() < 0 {
				return fmt.Errorf("row constructor: %s requires a nonnegative integer", key)
			}
		case "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum":
			if _, ok := schemaNum(value); !ok {
				return fmt.Errorf("row constructor: %s requires a finite number", key)
			}
		case "uniqueItems", "x-time", "x-integer", "x-whole", "x-opaque":
			if _, ok := value.(bool); !ok {
				return fmt.Errorf("row constructor: %s requires boolean", key)
			}
		case "x-encoding":
			if value != "json" && value != "jcs" {
				return fmt.Errorf("row constructor: unsupported schema encoding")
			}
		case "x-codec":
			list, ok := value.([]any)
			if !ok || len(list) == 0 {
				return fmt.Errorf("row constructor: unsupported schema codec")
			}
			for _, v := range list {
				text, ok := v.(string)
				if !ok || !contains([]string{"string", "any", "integer", "number", "boolean", "array", "time"}, text) {
					return fmt.Errorf("row constructor: unsupported schema codec")
				}
			}
		}
	}
	return nil
}

// CaptureStateStart captures start + the accepted manifest state declaration in
// one immutable value. It never borrows mutable maps, ASTs, or byte slices.
func CaptureStateStart(start json.RawMessage, spec StateSpec) (StartSnapshot, error) {
	owned := string(append([]byte(nil), start...))
	value, err := rwObject([]byte(owned))
	if err != nil {
		return StartSnapshot{}, err
	}
	if err := rwDeclared("start", value); err != nil {
		return StartSnapshot{}, err
	}
	defs := map[string]json.RawMessage{}
	for key, raw := range spec.Defs {
		owned := append([]byte(nil), raw...)
		if _, err := rwObject(owned); err != nil {
			return StartSnapshot{}, err
		}
		defs[key] = owned
	}
	states := map[string]string{}
	for name, raw := range spec.Schemas {
		raw = append([]byte(nil), raw...)
		if !regexp.MustCompile(rwBindings.NamePattern).MatchString(name) {
			return StartSnapshot{}, fmt.Errorf("row constructor: invalid declared state name")
		}
		if _, err := rwObject(raw); err != nil {
			return StartSnapshot{}, err
		}
		var doc map[string]json.RawMessage
		if err := json.Unmarshal(raw, &doc); err != nil {
			return StartSnapshot{}, err
		}
		merged := map[string]json.RawMessage{}
		for key, raw := range defs {
			merged[key] = raw
		}
		if local, has := doc["$defs"]; has {
			var own map[string]json.RawMessage
			if err := json.Unmarshal(local, &own); err != nil || own == nil {
				return StartSnapshot{}, fmt.Errorf("row constructor: invalid local defs")
			}
			for key, raw := range own {
				if old, has := merged[key]; has && string(old) != string(raw) {
					return StartSnapshot{}, fmt.Errorf("row constructor: conflicting defs")
				}
				merged[key] = raw
			}
		}
		if len(merged) != 0 {
			doc["$defs"], _ = json.Marshal(merged)
		}
		encoded, err := json.Marshal(doc)
		if err != nil {
			return StartSnapshot{}, err
		}
		sch, err := compile(string(encoded))
		if err != nil {
			return StartSnapshot{}, err
		}
		if err := rwSchemaShape(sch.doc, sch.doc, map[string]bool{}); err != nil {
			return StartSnapshot{}, err
		}
		states[name] = string(encoded)
	}
	family := ByKey(rwBindings.Writes[0].Family)
	if family == nil || family.Kind != "row" {
		return StartSnapshot{}, fmt.Errorf("row constructor: missing generated family")
	}
	return StartSnapshot{start: owned, states: states, writerDoc: strings.Clone(family.Doc), valid: true}, nil
}

func rwGet(ref rwRef, start, input obj) (any, error) {
	source := start
	if ref.Source == "input" {
		source = input
	} else if ref.Source != "start" {
		return nil, fmt.Errorf("row constructor: unsupported source reference")
	}
	v, ok := rwPointer(source, ref.Pointer)
	if !ok {
		return nil, fmt.Errorf("row constructor: missing %s pointer %s", ref.Source, ref.Pointer)
	}
	return v, nil
}

func rwKey(parts []rwRef, start, input obj) (string, error) {
	result := []string{}
	for _, p := range parts {
		if p.Source == "" {
			result = append(result, p.Literal)
			continue
		}
		v, err := rwGet(p, start, input)
		if err != nil {
			return "", err
		}
		text, ok := v.(string)
		if !ok || text == "" || strings.Contains(text, "/") {
			return "", fmt.Errorf("row constructor: key substitution must be a nonempty single segment")
		}
		result = append(result, text)
	}
	return strings.Join(result, "/"), nil
}

func rwRawPointer(raw []byte, pointer string) (json.RawMessage, error) {
	for _, token := range unpointer(pointer) {
		trim := strings.TrimLeft(string(raw), " \r\n\t")
		if strings.HasPrefix(trim, "{") {
			var m map[string]json.RawMessage
			if err := json.Unmarshal(raw, &m); err != nil {
				return nil, err
			}
			v, ok := m[token]
			if !ok {
				return nil, fmt.Errorf("row constructor: missing raw pointer")
			}
			raw = v
		} else if strings.HasPrefix(trim, "[") {
			var a []json.RawMessage
			if err := json.Unmarshal(raw, &a); err != nil {
				return nil, err
			}
			i, err := strconv.Atoi(token)
			if err != nil || i < 0 || i >= len(a) || strconv.Itoa(i) != token {
				return nil, fmt.Errorf("row constructor: missing array pointer")
			}
			raw = a[i]
		} else {
			return nil, fmt.Errorf("row constructor: missing raw pointer")
		}
	}
	return raw, nil
}

// BuildState is pure. Schema data comes only from the captured start; there is no
// parameter for a fresh schema, a reread row, current epoch version, or IO handle.
func BuildState(snapshot StartSnapshot, input json.RawMessage) (RowWrite, error) {
	if !snapshot.valid {
		return RowWrite{}, fmt.Errorf("row constructor: uncaptured start")
	}
	start, err := rwObject([]byte(snapshot.start))
	if err != nil {
		return RowWrite{}, err
	}
	ownedInput := append([]byte(nil), input...)
	args, err := rwObject(ownedInput)
	if err != nil {
		return RowWrite{}, err
	}
	if err := rwDeclared("input", args); err != nil {
		return RowWrite{}, err
	}
	w := rwBindings.Writes[0]
	var name string
	if w.StateName.Source == "" {
		name = w.StateName.Literal
	} else {
		v, err := rwGet(w.StateName, start, args)
		if err != nil {
			return RowWrite{}, err
		}
		name, _ = v.(string)
	}
	if name == "" {
		return RowWrite{}, fmt.Errorf("row constructor: state name must be a string")
	}
	doc, ok := snapshot.states[name]
	if !ok {
		return RowWrite{}, fmt.Errorf("row constructor: undeclared state name")
	}
	key, err := rwKey(w.Key, start, args)
	if err != nil {
		return RowWrite{}, err
	}
	if !regexp.MustCompile(w.Pattern).MatchString(key) {
		return RowWrite{}, fmt.Errorf("row constructor: key outside family")
	}
	items := map[string]string{}
	for _, field := range w.Fields {
		var value any
		var raw json.RawMessage
		if field.Source == "const" {
			raw = []byte(field.Pointer)
			value, err = rwJSON(raw)
		} else {
			value, err = rwGet(rwRef{Source: field.Source, Pointer: field.Pointer}, start, args)
			source := ownedInput
			if field.Source == "start" {
				source = []byte(snapshot.start)
			}
			if err == nil {
				raw, err = rwRawPointer(source, field.Pointer)
			}
		}
		if err != nil {
			return RowWrite{}, err
		}
		var text string
		switch field.Codec {
		case "string":
			var ok bool
			text, ok = value.(string)
			if !ok {
				return RowWrite{}, fmt.Errorf("row constructor: nonstring items property")
			}
		case "integer":
			n, ok := value.(num)
			if !ok || !n.isInt {
				return RowWrite{}, fmt.Errorf("row constructor: noninteger items property")
			}
			text = n.i.String()
			if _, err := decodeAs("integer", text, Writer, true); err != nil {
				return RowWrite{}, err
			}
		case "jcs":
			sch, err := compile(doc)
			if err != nil {
				return RowWrite{}, err
			}
			if !sch.judgeText("object", raw, Writer).OK() {
				return RowWrite{}, fmt.Errorf("row constructor: state value outside captured schema")
			}
			text, err = jcs(value)
			if err != nil {
				return RowWrite{}, err
			}
		default:
			return RowWrite{}, fmt.Errorf("row constructor: unsupported writer codec")
		}
		items[field.Field] = text
	}
	writer, err := compile(snapshot.writerDoc)
	if err != nil {
		return RowWrite{}, err
	}
	if !writer.judgeRow(ItemsOf(items), Writer).OK() {
		return RowWrite{}, fmt.Errorf("row constructor: built items outside Writer form")
	}
	var guard *RowWriteGuard
	if w.Version != nil {
		guardKey, err := rwKey(w.Guard, start, args)
		if err != nil {
			return RowWrite{}, err
		}
		index, err := rwGet(*w.Version, start, args)
		if err != nil {
			return RowWrite{}, err
		}
		version, ok := index.(string)
		if !ok || !regexp.MustCompile(rwBindings.VersionPattern).MatchString(version) {
			return RowWrite{}, fmt.Errorf("row constructor: guard version outside string form")
		}
		guard = &RowWriteGuard{Key: guardKey, Index: version}
	}
	return RowWrite{Key: key, Items: items, Guard: guard}, nil
}
