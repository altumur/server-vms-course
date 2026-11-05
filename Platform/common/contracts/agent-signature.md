# The agent signature contract: the header `X-Agent-Signature`, windows, the check `agent-sig`, refusal words

This English text is the source; the Russian translation `ru/contracts/agent-signature.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Platform» (ADR-0083 addendum (5), addendum (11) and addendum (13): a common algorithm of several processes is a contract,
not copies in chapters; analysis of the review of stage A 8–10, № 13 / decision 2). The owner is [chapter 9.1](../../09-agent/spec/09.1-agent.norms.md) of lesson P/09 (Н1.3; the source —
М11/3 Н1.4): the member agent signs its requests with the member key
`domain/member-key` (P/09.1 Н1.1). Checked by:

| Who checks | Doors | Window |
|---|---|---|
| the holder — the process `domain` ([P/08.3](../../08-domain/spec/08.3-domain.norms.md) Н2, [P/08.7](../../08-domain/spec/08.7-domain.norms.md) Н1.3) | `POST /api/member/<member>`, `GET /api/carry/<member>`, `POST /api/tokens/<member>/…` | `MEMBER_WINDOW` |
| the relay ([P/09.2](../../09-agent/spec/09.2-agent.norms.md) Н2) | the relay doors for the members behind it; the relay's batch to the holder is signed by it as well | `MEMBER_WINDOW` |
| the cluster console of its own member ([P/06.3](../../06-console/spec/06.3-console.norms.md) Н1.3 `identity` step 2) | the doors of units, of the tables `domain.edit_tables`, `POST /console/batch`, `GET /events?class=alarm` | `UNIT_WINDOW` |

Moved from М11/3 Н1.4 (the block `header`, `window`, `replay` and the paragraph on the check and the refusal words) without a change of behaviour.
The member key, its birth and its pinning in the member record are P/09.1 Н1.1 `pub`, `born` (P/09.1-01); what a door does after
the check (the knock, 403 of the key, 401) is the norms of the checking doors. References in the moved text: «Н1.1 pub», «Н2», «Н3» are of lesson
М11/3; «lesson N» is lesson М11/N. Their addresses now (analysis of the review of stage B 8–10, № 22; Claude M-1, S-7): «Н1.1 pub» — P/09.1
Н1.1 `pub`, the small order and «not a point of the curve» are defined right here («Check and refusal words»); «Н2» — P/08.3 Н2; «Н3» at
`agent-sig` — the function of this contract, at `replay` (idempotency of the report) — [the report acceptance contract](accept.md) step 2;
«lesson 4» — P/09.2; «lesson 6» — P/09.1 Н1.5; «lesson 10» — [the ask signature contract](ask-sig.md) (P/08.8).

Normative keywords follow [the course canon](../../../НОРМАТИВНЫЕ-СЛОВА.md).

## Form

The signature key of a member is `domain/member-key`: `Platform/09-agent/data/member-key.schema.json`, `Platform/09-agent/data/member-key.outcomes.tsv`. The doors where the header is checked are the OpenAPI `Platform/08-domain/spec/08-domain.api.openapi.yaml` (`POST /api/member`, `GET /api/carry`, `POST /api/tokens`), `Platform/09-agent/spec/09-agent.api.openapi.yaml` (the relay doors), `Platform/06-console/spec/06-console.api.openapi.yaml` (the doors of units, `GET /events?class=alarm`) (layout audit, V-05, V-06; the Architect's decision of 2026-10-25).

## Signature

From М11/3 Н1.4:

```yaml
header:         X-Agent-Signature: <ms>.<sig>
  <ms>:         the agent's Unix wall milliseconds, a decimal integer without a sign and leading zeros (0 — «0" itself), ≤ 16 digits
  sig:          base64url of 64 bytes of an Ed25519 signature with the member key over UTF-8:
                <METHOD> "\n" <path> "\n" <ms> "\n" <hex sha256 of the body bytes>     # the body of GET is empty: sha256 of the empty string
                with the header X-Agent-For — also "\n" <its value>
  X-Agent-For:  <person name> <iat>: whose edit; only a stored edit with by (P/08.6 Н1.4); without the header — as before
  path:         the request path without query, byte for byte as in the request line
window:         |now − <ms>/1000| ≤ window, in both directions; now — the wall seconds of the checker
  MEMBER_WINDOW: 300        # s — the doors of the holder (Н2) and of the relay (lesson 4)
  UNIT_WINDOW:   60         # s — the unit doors of the member console (P/06.3 Н1.3 identity 2: the agent edits the units of its own cluster, lesson 6)
replay:         there is no repeat cache: the same bytes within the window are accepted again — the norm names this a limit; the report door
                is idempotent by (sent_at, request_sha256) (the report acceptance contract; C08-REPEAT-KEY-01), the unit doors — POST by Idempotency-Key, PUT and DELETE — by If-Match (P/06.1 Н2: Idempotency-Key at PUT is not read)
```

## Check and refusal words

From М11/3 Н1.4:

The check is the function `agent-sig` (Н3), the refusal words: `no_signature` (the header is absent or empty), `not_a_signature` (there is no `.`,
`мс` is out of form, `sig` is not base64url without `=` or not 64 bytes), `out_of_window`, `bad_signature` (also a key of small order
or not a point of the curve, Н1.1 pub). `sig` is canonical base64url without `=`: non-zero unused bits of the last character are
`not_a_signature` (one signature — one notation of the header). The body of GET is empty: a GET with a non-empty body is `bad_signature` always,
whatever the signature is (over the empty body or over the one that came), after the window check (stage C guesses AS-01/02, the Architect's decision of 2026-10-23). The checks go in order, the refusal is the first word that fires: `no_signature` →
`not_a_signature` → `out_of_window` → `bad_signature`; the window before cryptography — a signature with a foreign key outside the window gives
`out_of_window` (the Architect's decision, analysis of the review of stage B 8–10, № 3, ADR-0083 addendum (15)). A key of small order is a point `A` of the public key for which `[8]A` is the neutral
element of the curve Edwards25519; not a point of the curve is 32 bytes that do not decode into a point (RFC 8032 §5.1.3). These doors have no other
signature form: the triple `X-W2C-Member/Time/Signature` is at the asks without a member on the path (lesson 10).

The form of the function is the column `input` of the package [`agent-sig`](../vectors/agent-sig/README.md) (the former input of the command `agent-sig`
of the acceptance of М11/3 Н5; sc. 10 was removed by the move of lesson 8): `{key, method, path, body, header, now, window}` →
`{result: ok}` | `{result: refused, reason}`; `path` with «?» is an input out of form. The triple of lesson 10 is [the ask signature
contract](ask-sig.md).

## Vectors

The package [`agent-sig`](../vectors/agent-sig/README.md) (analysis of the review of stage A 8–10, № 12, № 13): 25 rows — 19 are inputs of the command
`agent-sig` of the acceptance of М11/3 (sc. 10) without a change of bytes: the window in both directions and the boundary, 60 s of the unit doors, the body, the path, the method,
a foreign key, the forms of `мс` and `sig`, a key of small order; the scenario and the inputs were removed by the move of lesson 8 — the table is the only
source of these cases; row 20 — the order of the checks: a foreign key and outside the window → `out_of_window` (analysis of the review of stage B 8–10, № 3); rows 21–22 — AS-01/02; rows 23–25 — the header `X-Agent-For` (the input `for`, ADR-0111 item 16). Each checking side passes them with its own function, without a stand. There is also `batch-knock.tsv` — 6 rows of the signature of a batch knock ([the report acceptance contract](accept.md) «The batch knock»); performed by the process `domain`.

## Correspondence to former lessons

From М11/3 (analysis of the review of stage A 8–10, № 13 / decision 2): Н1.4 whole (here «Signature», «Check and refusal words»; in М11/3 —
a pointer). The norm М11/3-08 (the agent signature: bytes, windows; chapter 8.3 — the check at the holder) — by `note` of
[id-map](../id-map.tsv); 9.1 signs, 8.3, 8.7, 9.2 and P/06.3 Н1.3 `identity` step 2 check.
