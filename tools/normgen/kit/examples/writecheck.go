package example

import (
	"kitmodule/internal/apidoor"
	"kitmodule/internal/writecheck"
)

// writeBody — POST /v1/write in your Handler.Write: the checks of Н2.1 first; a refusal is the answer, nothing is
// written; otherwise execute the parsed command by Н3.
func writeBody(sock string, body []byte, rowCeiling int64, allowed func(sock, op, key string) bool) apidoor.Answer {
	lim := map[string]int64{"BATCH_WRITES": 64, "BATCH_GUARDS": 64, "ROW_CEILING": rowCeiling} // P/01.1 Н1
	ref, v := writecheck.Check(body, sock, lim, allowed)
	if ref != nil {
		a, err := apidoor.Refuse(apidoor.OpWrite, ref.Code, ref.Kind, "refused: "+ref.Check, ref.Fault)
		if err != nil {
			return apidoor.Answer{Code: 500}
		}
		return a
	}
	cmd := v.(map[string]any) // cmd["op"] — put, delete, batch, floor: yours by Н3
	_ = cmd
	a, _ := apidoor.AnswerOf(apidoor.OpWrite, 200, map[string]any{"index": "1"})
	return a
}
