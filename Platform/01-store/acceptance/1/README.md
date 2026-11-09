# Acceptance P/01.1 — the store operations vocabulary

This English text is the source; the Russian translation `ru/acceptance/1/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md). The norm of the chapter is
[`01.1-store.norms.md`](../../spec/01.1-store.norms.md) N5.

## Profile interface

The profile is `01-store` in the [generic profile and assembly contract](../../../common/acceptance/PROFILE.md). `stand.store1` starts a fresh store instance for this chapter: it consumes the assigned data directory, administrative socket, prepared rights file and the body/row test parameters through the common stand substitutions. Its ordinary side serves the published `acc` role. `keys.request_line_limit` names the implementation's request-line boundary; `keys.role_header` names its role-forwarding header where a probe needs one. The optional `adapters.door` exposes the same ordinary/admin operations through the persistent transport of the common contract; it does not replace raw HTTP checks. The JCS package uses the `vectors` entry assigned by its [wire form](../../../common/vectors/wire.tsv), not a guessed `stand.jcs` invocation. The implementation chooses its own executable names and flags and binds these responsibilities in its profile.

## `scenarios.tsv`

The format is the dictionary of directives and doors of the common acceptance README. Specific to chapter 1.1:

- `expect` is `<code> <JSON body>`; the JSON is compared whole; `error` is compared only if it is named: its text is not normed.
- For a `200` answer to `GET /v1/list` the **order of names inside `keys`** is also checked: the sequence of names decoded from the JSON in the order received MUST equal the sequence in `expect`, which is given by UTF-8 bytes. The runner keeps this order when parsing the answer and does not sort what it received before the comparison. For an empty `keys` the sequence is empty. Spaces and the way of JSON escaping are insignificant; the order of other objects, `items` included, is still not checked.
- `$name` binds only a JSON string (N1: a version is a string on the wire); a number or another type is a mismatch of the step.
- Only for a body refusal the optional field `size` is admitted: if it is present, it is the integer
  JSON number of the full size of the sent body, not a string and not a boolean. After it is checked it
  is excluded from the comparison with `expect`. The absence of `size` is admissible by N2; other additional fields,
  `key` included, are not admitted (the common rule of `error` is kept). For a weight refusal the fields `key` and `size`
  are mandatory and are compared as before.

## `seams.tsv` — scenarios over the seams of the process (ADR-0125 addendum (4) item 7)

[`seams.tsv`](seams.tsv) — the original six scenarios plus the six additions below, covering the properties of the core that the checklist checks «by reading»: the `id`
memory does not forget by time alone (P/01.1-11), equality and both sides of fractional admission-time bounds for put, delete and batch
(P/01.1-25), the admission time retains its fraction when clocks go back and after a restart (P/01.1-26), concurrent CAS of one row (P/01.1-15), a batch whole after a
restart (P/01.1-31). The runner executes them through the seam adapter, by the [normalization of the common acceptance README](../../../common/acceptance/README.md#p01-seam-normalization) (the directives `@clock`, `@reopen`, `@parallel` are defined there and in the header of the file). The stages — `store_core` (`@clock`, `@parallel`) and `durable` (`@reopen`) of `forms/stages.tsv`, by `seams:1.1:<scenarios>` in their `gate`.

## Additional check of the class of errors of run 36 (Kimi)

A replay of delete with the same id and different items (none/null/number/object/array) must match by op/key/cas/guard. A change of key/cas/guard is a different fingerprint. Compare versions only for equality: uniqueness does not mean a numeric order. Sc.17 also sends arbitrary bytes or no body by the common grammar of POST.

This is a subject of a manual check of the specification and of a future check of an implementation. The prepared requests, the reading and the finite models of the author are not a performed stand test.
A change of `key`, `cas`, `guard`, `not_after` and `not_before` on a replay of `delete` is now scenario 30.

## Batch

The batch `op: batch` (N1 `batch`, N3 «write batch»): the JSON is judged whole, as in the other steps of the chapter; for a `conflict` of a batch the expectation has `key`.

The weight of `@big`: the field name plus the value.

The role `console` does not know the limit on the number of rows — chapter 1.2. Restart and the group — chapter 1.3. The refusal of a body over the limit is a common refusal before JSON parsing.

## Extra fields of a command (K37-05)

Scenario 23 checks put/delete and their replays with different unknown top-level
fields: they change neither the data nor the fingerprint. The nested object zzz does not become a guard
or a new command. The closedness of a real guard is checked separately by sc. 20; a wrong
items of put — sc. 16, ignoring items of delete — sc. 06 and 23. The limit of the full body
holds, ignored fields included (sc. 22 and reading of the size check before parsing).
A prepared scenario does not mean a performed HTTP run of an implementation.

The check R38-06 outside the TSV: on a role socket the request GET /v1/list with a role forwarding header gets 403 forbidden before listing; an untrusted forwarding and a forbidden forwarded admin are also refused by P/01.2 N3 «check». The same admissible identity without the read right gets 200 with names/versions without values. Scenario 21 checks the latter, not all identity refusals; the former require a sockets/trust profile from acceptance 06 (sc. 08 — a header with a foreign role on a role socket).

## A key that is absent or not a string (G39-07)

Scenario 24 separates the form from the rules of the key: an absent or non-string `key` of a command,
`guard.key` and the read parameter `key` — `400 badrequest`; a string that breaks the rules of N1 — `badkey`
(sc. 13 and 20). The last step reads the row and sees that nothing is written.

## Admission time conditions (P/01.1-25; ADR-0091 item 1)

Scenario 28 takes only the edges of the admission time: a `not_after` that has already passed, `not_after` and `not_before` that
have not yet come under any clock of the stand. `expired` and `early` write nothing; the order is
«time conditions → guard → CAS»; `not_after` is in the replay fingerprint (a numerically equal spelling is the same value, a different number and absence — `400`);
the refusal `expired` does not occupy the `id`; forms
(a string, a negative, `null`, `bool` — `badrequest`; the form of the guard before `not_after` — `badkey`). The equality boundary and
the non-decrease of the admission time are by reading (N5 of the norms).

## Request parsing (N2.1, P/01.1-23)

On a role socket `op: floor` is `403 forbidden` before parsing the key. The form of the guard goes before the rules of the key:
`guard: null` is `badrequest`. The query: `+` is a space, `%2B` is a plus, `+` in `prefix`
is a space too, a repeated parameter is `badrequest`, bytes not UTF-8 are `badkey`, `%` without digits stays
a letter of the key and does not find the row. Strict JSON of the body: a repeated field name at the top level
and in `items`, `NaN` in an extra field, a lone surrogate in a key and in `items`; nothing is written,
a surrogate in an extra field is not read. An unknown method and a known path
with a method that is not its own: `404` with `Fault`, not 405 or 501; the paths `/v1/%67et`, `/v1/get/` and `//v1/get` are not decoded and not
normalized — also `404`. The order of the query checks: empty pairs are skipped, `?key` is an empty
key (`badkey`), a repeat before UTF-8 (`badrequest`).

A probe outside the TSV — raw bytes into the door socket, each answer `400` with the body `Fault` `{kind: badrequest}`, not a page of the
server and not 414, 431, 501 or 505: `GET /v1/list\r\n\r\n` (no HTTP version); a request line of the length of the limit
named in the implementation description (item 9 of «Implementation decides») plus 1 byte — the runner does not know a foreign limit and takes it
from there; a header without a colon; a header with a space before the colon and an obs-fold header continuation (RFC 9112 §5.1–5.2).
Separately: a target in absolute form `GET http://localhost/v1/get?key=acc/x HTTP/1.1` — `404 badrequest` (the path is not
decoded and not normalized, N2.1); a body with `Content-Length` and `Transfer-Encoding: chunked` together is read
as chunked (§6.3), closing the connection after the response (RFC 9112 §6.1). For a valid HTTP/1.1 request this is not an automatic `400`: its own operation determines the response. An HTTP/1.0 request with `Transfer-Encoding` has faulty framing: `400 badrequest` and close (R054; RFC 9112 §6.1). Early refusal (N2.1): `POST /v1/write` with `Content-Length` larger than the body limit and a body
that is still coming — the client gets `413 toolarge` with `Connection: close`, not a reset of the connection.

Probes of the framing and of the request line (N2.1, reconciliation of python and go 2026-10-18), each on raw bytes:
- a lone LF and a lone CR at the end of a header line — `400`; an empty line before the request line — `400`;
- raw `\x00`, `\x01`, TAB, `\x7f` and `#` in the request target — `400` (`%00` — sc. 25, `200`);
- headers whose field lines without CRLF sum to exactly 65536 bytes are parsed (an answer by the route), 65537 — `400`; 2000
  short header lines within the limit are parsed;
- a body with JSON of depth 128 in an extra field — written, 129 — `400`;
- `Content-Length: +5` — `400`; two `Content-Length` with different values — `400` and closing; a `Content-Length` of 23
  nines — `413 toolarge` without `size`; a chunk size `0x5` — `400`; `Transfer-Encoding: gzip, chunked` and two TE lines —
  `400`; after each framing error the connection is closed;
- a truncated body: `Content-Length: 50`, 20 bytes and a half-close of the write side; chunked without the last chunk — no answer; then
  a `GET` over a new connection sees the previous value of the row;
- no `Host`, two `Host`, `Host: a b/c` — as with an ordinary `Host`; `HEAD /v1/get?key=acc/x` — `404` without a body.

## ADR-0129 core clarification witnesses

The original six seam scenarios and all 73 steps remain byte-exact. Added six scenarios use only the existing HTTP, @clock and @reopen grammar. The four admitted refusals expired, early, guard and conflict for single writes and batches have zero business effects, and that coexists with retained admission metadata; the refused identifier stays reusable with a corrected condition. The same distinction holds across ordinary Close/Open; it is a graceful restart witness, not a power-cut or consensus witness.

The admission bounds compare as binary64 values: for a bound that equals the clock in binary64 not_after admits equality and not_before refuses it, for put/delete/batch. On applied put/delete/batch replays bound spellings that round to the same binary64 value are the same fingerprint, and values that differ in binary64 give different fingerprints and badrequest. The request bytes must not be normalized before the actual store parses them. The CALL engine's exact-number comparison is not a replacement store fingerprint. A nonempty string version differs from the absent marker "" in single/batch CAS and guards.

Already covered and unchanged: scenario 35 steps 8–9 choose the first failing guard in both source-list orders, steps 10–11 do the same for CAS; scenario 36 step 3 reorders guards on a successful replay without changing its fingerprint. R116 and scenario 31 steps 1–4 already prove that a successful absent delete leaves read index "" and admits a later create-once; scenario 34 steps 7–8 covers batch deletion of an absent row. No duplicate witnesses are added for these obligations.

Opaque versions do not expose the allocator's count. The new HTTP probes observe unchanged rows/list and a reusable refused id; they do not infer zero version issuance by subtracting or ordering index strings. R089/R132's no-issued-version obligation remains subject to the existing reading check. No snapshot/effects form, new port, native command, implementation or handwritten core is supplied. These are source witnesses awaiting the ordinary implementation adapter, not executed SUT results.

## Replay and last admission metadata

A successful replay of put/delete/batch with the former id keeps the original answers and versions; a deleted row has no visible version. The replay's new last admission metadata is durable across an ordinary reopen (N3 «Admission time»). These cases are gated by durable because they include @reopen; former steps and store_core gates are unchanged. These are source witnesses, not executed SUT acceptance.

## Admitted mismatches and admission-number domain (ADR-0129 addendum (10), item 3)

The complete previous 15 seam scenarios / 239 steps remain byte-exact. A put/delete/batch with an already-applied identifier and different content is an admitted mismatch: badrequest, with durable last admission metadata. The original rows/visible absence and first id answer remain; an original-command replay still returns that answer with again. The mismatch does not replace or free the original applied-id entry. These are admitted refusals, distinct from form/rights/framing refusals before admission; not every badrequest is admitted.

The assigned fractional binary64 admission value survives an ordinary reopen. No integer/millisecond or three-digit row-time writer may truncate it. The witness does not prescribe a metadata encoding or physical clock accuracy.

All four cases use only existing HTTP, signed-decimal @clock and @reopen steps and are selected by the existing durable gate. No port, internal API, CALL grammar, snapshot or power-cut claim is added. The 56 new source steps are not executed implementation acceptance. Constant names are owned by forms/runtime-constants.tsv; specific stand/probe input numbers remain test data.

## Production qualification coverage

The [production acceptance contract](../../spec/production-acceptance.md) assigns the workload, phase-deadline, copy/stop, fault-stage and HTTP-copy groups separately from these functional scenarios. Their declared budgets, independent activation and complete observations are required for a production result. Existing TSV inputs/expectations and ordinary/group applicability remain unchanged; a missing binding or budget is blocked/NotExecuted, not PASS.
