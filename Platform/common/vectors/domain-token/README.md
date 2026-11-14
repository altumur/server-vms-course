# Domain token vectors

This English text is the source; the Russian translation `ru/vectors/domain-token/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The [domain token contract](../../contracts/domain-token.md) defines `token(keys, revoked, now, token)` with the recipient's `expect` (kind and its own cluster). It checks a domain token against the accepted `domain/keys` set and `domain/revoked` row, using the checker's wall clock. The owner is P/08.2.

## Run

The `vectors` call supplies the cell `input` as JSON text: `keys` (the set document), `revoked` (`{jtis}` as read, or `null`), `now`, `token`, and optional `expect` (`{kind, cluster, audience_claim?}`). `kind` is a string or a list of kinds. The contract defines the closed form of `expect`: `cluster` is mandatory and may be null only for `kind: person`.

The implementation's function receives this input and returns its output. Exit code 0 means computed, including a refusal word. A malformed input gives exit code 2; its output is not compared, as specified by the «Stand» dictionary in [common acceptance](../../acceptance/README.md).

The native output is `{"result":"ok","payload":{…}}` or `{"result":"refused","reason":<word>}`. The refusal vocabulary is `unknown_key`, `bad_signature`, `not_a_token`, `bad_claims`, `expired`, `future`, `revoked`, `no_revocations`, `wrong_kind`, `wrong_audience`. The judge's expectation is a subset of the output fields; for success it is a subset of `payload`. This expectation is separate from the recipient's `expect` input and never enters the call as a judge answer.

## Who performs

Every token checker executes all rows through one function, including the input `expect`: the cluster-console gate (`06-console`, [P/06.3](../../../06-console/spec/06.3-console.norms.md) N1.3 `identity` step 3 and N1.8); the worker as kind-token recipient and process-door holder (`03-worker`, [P/03.7](../../../03-worker/spec/03.7-worker.norms.md) N1.5 and N3, P/03.4 N1.7 `door_admission`); process `domain` at people doors (`08-domain`, [P/08.4](../../../08-domain/spec/08.4-domain.norms.md)); and the domain-console gate (`10-domain-console`, P/10 N1.5). A role executes the function its norm calls.

The member agent (`09-agent`) does not call this function: it checks the local token door's answer by `request_id` and `exp` (P/08.7 N3). A store-unreadable `domain/revoked` row at the door is checked by the stand, outside the function.

## Vector wire

The public `table` selector is `cases.tsv` for the domain-token check (judge-only: `cases.tsv`).

The `common/domain-token` rows of [the single form](../wire.tsv) (judge-only: `wire.tsv`) bind headers, selected inputs, fixtures, native framing and comparison; [wire grammar](../wire.md) defines the frame. Layout is an excluded function declaration, never proof that its separate acceptance ran. The contract governs a discrepancy; «Specification» corrects the vector.

Fixed keys, concrete `token-*` inputs, branches, expected answers, coverage and the source log are in [case data and coverage](README.cases.md) (judge-only: `README.cases.md`).
