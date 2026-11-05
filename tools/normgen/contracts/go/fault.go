package contracts

// The closed dictionary of the word fault (common/vectors/fault, the owner P/06.1 Н2, Н4): the word and the HTTP code
// it comes with — 400, the body itself is wrong; 409, the refusal depends on the standing rows.
var FaultWords = map[string]int{
	"not_json":   400,
	"not_number": 400,
	"too_long":   400,
	"bad_url":    400,
	"must_match": 409,
	"unique":     409,
	"garbled":    409,
}
