# Acceptance P/01.1 — the store operations vocabulary

This English text is the source; the Russian translation `ru/acceptance/1/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md). The norm of the chapter is
[`01.1-store.norms.md`](../../spec/01.1-store.norms.md) N5.

## Profile interface

The profile is `01-store` in the [generic profile and assembly contract](../../../common/acceptance/PROFILE.md). `stand.store1` starts a fresh store instance for this chapter: it consumes the assigned data directory, administrative socket, prepared rights file and the body/row test parameters through the common stand substitutions. Its ordinary side serves the published `acc` role. `keys.request_line_limit` names the implementation's request-line boundary; `keys.role_header` names its role-forwarding header where a probe needs one. The optional `adapters.door` exposes the same ordinary/admin operations through the persistent transport of the common contract; it does not replace raw HTTP checks. The JCS package uses the `vectors` entry assigned by its [wire form](../../../common/vectors/wire.tsv), not a guessed `stand.jcs` invocation. The implementation chooses its own executable names and flags and binds these responsibilities in its profile.

## `scenarios.tsv`

The table `scenarios.tsv` of the chapter (judge-only: `acceptance/1/scenarios.tsv`) checks the requirements that the
readiness checklist of the chapter norms names next to each scenario. The format is the dictionary of directives and
doors of the common acceptance README. Specific to chapter 1.1:

- `expect` is `<code> <JSON body>`; the JSON is compared whole: the targets of this chapter have the mode `whole` of the dictionary of the common acceptance README (`<code> <JSON>`); `error` is compared only if it is named: its text is not normed. An unnamed `error` is admitted only in the root of the body; an extra field elsewhere is a mismatch.
- For a `200` answer to `GET /v1/list` the **order of names inside `keys`** is also checked: the sequence of names decoded from the JSON in the order received MUST equal the sequence in `expect`, which is given by UTF-8 bytes. The runner keeps this order when parsing the answer and does not sort what it received before the comparison. For an empty `keys` the sequence is empty. Spaces and the way of JSON escaping are insignificant; the order of other objects, `items` included, is still not checked.
- `$name` binds only a JSON string (N1: a version is a string on the wire); a number or another type is a mismatch of the step.
- Only for a body refusal the optional field `size` is admitted: if it is present, it is the integer
  JSON number of the full size of the sent body, not a string and not a boolean. After it is checked it
  is excluded from the comparison with `expect`. The absence of `size` is admissible by N2; other additional fields,
  `key` included, are not admitted (the common rule of `error` is kept). For a weight refusal the fields `key` and `size`
  are mandatory and are compared as before.

## Directives of chapters 1.1 and 1.2

Only the acceptance of P/01 uses the words below; the [dictionary of the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors) names each of them with a reference to this section. «Stand», «Role sockets» and «Terms of the stand» are those of the common acceptance README. The words of chapter 1.3 are in its [acceptance README](../3/README.md#directives-of-chapter-13).

**Request.**

| Form | Meaning |
|---|---|
| `@wire <text>` | raw HTTP: in the place of the method (`<door> @wire <text>`) the step opens a new connection to its door and writes exactly the bytes of the text, nothing added: no header, no `Content-Length`; the escapes `\r`, `\n`, `\t`, `\\` and `\xHH` (two hexadecimal digits) give one byte each and are read after the substitutions, another `\` is a data error of the table; the response is read as HTTP/1.1 on the same connection |
| `@halfclose` | the last word of a `@wire` request, after one space, not one of its bytes: after the bytes the judge closes the write side of the connection and goes on reading |
| `@rep(N,<text>)` | a substitution in any part of the request: the text repeated N times; the text runs to the first `)` and holds none |
| `@profile(<name>)` / `@profile+1(<name>)` | a substitution in any part of the request, also in the place of N of `@big(N)` and `@rep(N,<text>)`: the value of the integer key `<name>` of the profile field `keys` (`Platform/common/acceptance/forms/profile-keys.tsv`), or this value plus 1, in decimal; there is no other arithmetic; an absent key leaves the step `not_executed` with its name as the reason |
| `@pause(<seconds>)` | inside the bytes of a `@wire` request: the judge stops writing for that many seconds, a decimal number, and then writes the rest; meanwhile it reads the connection |

**Stand directives** — not HTTP; the answer is `ok` or a refusal of the runner.

| Form | Meaning |
|---|---|
| `@rights store <file\|none>` | SIGTERM to the stand store, wait for the exit, start it with the same command with the same `{data}` and the rights file `<file>` (the path from the acceptance directory of the lesson; the runner puts it into `{rights}`) or without `-rights` (`none`: in the command template of «Stand» the runner removes the occurrence `-rights {rights}` or `-rights={rights}` — the flag with the substitution `{rights}`, not any word `-rights`: in a composite command it may belong not to the store — and changes nothing else; `<file>` — the same `{rights}` points to it; there is no such occurrence in the template or there is more than one — the scenario is not_executed with a reason); the expectation: `ok` — the store is ready by the rule of «Role sockets» (`none` — without a rights file); the runner sends no request for this (`/v1/status` of chapter 1.3 may still be a stub at the stage `rights`); `@exit 2` — the process exited with code 2 no later than 10 s (the file is not in the form of P/01.2 N1.2, N4); the file of the previous row does not carry over to the following scenarios |
| `@hold <door> <N>` | open N connections to the door and write nothing on them; they stay open until the end of the scenario, then the judge closes them; the expectation `ok` — all N were accepted |
| `@io store $<name>` | bind the name to the number of bytes that the processes of the store caused to be written to storage: the field `write_bytes` of `/proc/<pid>/io`, summed over the process group of the store; the expectation `ok`. When the judge cannot read this counter, for example under another account, the step and every step that compares the name are `not_executed` with the reason `io_counter_unreadable`, not red |

**Expectation.**

| Form | Meaning |
|---|---|
| `<code> @close …` | `@close` right after the code: after its response the implementation closes the connection, within the term of `@noreply`; the rest of the cell is judged as the expectation without `@close` |
| `@noreply` | the whole expectation: no byte of a response arrives until the implementation closes the connection or the term of `@noreply` in «Terms of the stand» ends; a response is a mismatch |
| `… @by(<seconds>)` | the last word of an expectation: the response, the close of `@close` or `@noreply`, or the exit after `@sigterm store` comes no later than that many seconds after the start of the step, instead of the term of `@noreply`; with `@noreply` the implementation must also close the connection within it. It is an upper bound: the judge records the resolution of its clock and of its scheduling separately and does not widen the bound |

## The instance of the chapter

An additional check of the full key (P/01.1-16,22) runs beyond the scenario TSV on a separate instance
with rights on acc/: the keys of this prefix at the boundary lengths in UTF-8 bytes, including Cyrillic and four-byte
characters, and the same set in a non-empty guard.key. For an existing guard use its actual version, for an absent one —
index="", so as not to fall into the version comparison refusal. For a file implementation separately check its
declared limit: an earlier badkey is admissible, but the threshold 200 by itself is not a norm of the platform.
Test the full UTF-8 representation, not the number of characters.

The scenarios are run through the store door (the lesson, N2) of any implementation; the path to the door (the unix socket of a role or a stand with the same door) is a parameter of the stand. The role of the run is `acc` («Stand» of the common README): full rights on the prefix `acc/` and on nothing else. For **each scenario, including on a repeated run**, the runner creates a new isolated instance
of the store with empty application rows and an empty memory of the write identifiers `id`. In particular,
both test prefixes are empty — `acc/` and `other/`. Cleaning the rows `acc/<scenario>/` in the previous instance
is not enough: it does not clear the replay memory. Versions need not start from a given number.

The preparation of the instance, its data directory and its rights is done by the runner before the scenario starts; the checked requests
go from the indicated role with rights on `acc/`, except the steps through the door `admin` of the dictionary. A row outside those rights is written by such a step through `admin.sock` of the instance (`{socket}` of «Stand» of the common README); a listing sees its name
and version without the value, although the role has no read rights there (N3 «list»). A query of `POST /v1/write` and a body of `GET` are not read; `Infinity` and a BOM in the body — N2.1.
Parallel scenarios use different instances and share neither rows nor the `id` memory.

The parameters of each instance (N5 of the lesson): the row ceiling **524288 bytes**, the read limit of an HTTP body
**1048576 bytes**. The runner checks both values before the scenarios by behaviour on a probe instance obtained in the same way.
The runner obtains an isolated instance in the way the implementation named in its description (the norms,
«Implementation decides» item 10). If the parameters cannot be provided or the check did not agree, the run is not performed;
the expected bytes must not be adjusted to the available settings.

The runner passes the bytes of the body from `request` after the substitutions, without re-serialization or other additions.

## `seams.tsv` — scenarios over the seams of the process (ADR-0125 addendum (4) item 7)

[`seams.tsv`](seams.tsv) (judge-only: `acceptance/1/seams.tsv`) — the original six scenarios plus the six additions below, covering the properties of the core that the checklist checks «by reading»: the `id`
memory does not forget by time alone (P/01.1-11), equality and both sides of fractional admission-time bounds for put, delete and batch
(P/01.1-25), the admission time retains its fraction when clocks go back and after a restart (P/01.1-26), concurrent CAS of one row (P/01.1-15), a batch whole after a
restart (P/01.1-31). The runner executes them through the seam adapter, by the [normalization below](#seam-normalization) (the directives `@clock`, `@reopen`, `@parallel` are defined there and in the header of the file). The stages — `store_core` (`@clock`, `@parallel`) and `durable` (`@reopen`) of `forms/stages.tsv`, by `seams:1.1:<scenarios>` in their `gate`.

### Seam normalization

P/01.1 `seams.tsv` (judge-only: `acceptance/1/seams.tsv`) has no `CALL` rows. Its steps are HTTP requests and the directives `@clock`, `@reopen` and `@parallel`. Over the [bridge](../../../common/acceptance/README.md#explicit-test-side-seam-bridge) of the common acceptance README each HTTP or directive step becomes `method: call` with one of three public tokens. No bridge field or method is added.

| `name` | Step | `input` | Observation |
|---|---|---|---|
| `store-http` | `GET` or `POST` | closed object: required `method` and `target` (the path with the query, as written in the step), optional `body` (the text of the body of the step as one string, absent when the step has none) | `{kind: "value", value: {"status": <integer>, "body": <string>}}`: the status and the whole response body |
| `clock` | `@clock +N` or `@clock -N` | closed object `{"shift": <string>}`: the shift in the same syntax as the step | `{kind: "value", value: {}}` |
| `reopen` | `@reopen` | `{}` | `{kind: "value", value: {}}` |

`store-http` reaches the ordinary request handling of the store; it is not a new door. `clock` moves the controlled clock of the store by N seconds, cumulatively; the clock starts at 2000000000 and the implementation chooses how it is controlled. `reopen` closes the store and opens it again on the same data directory with the same clock. An HTTP step's `<code> <JSON body>` is compared as in the acceptance of chapter 1.1, and a directive's `ok` matches an empty object value. `@parallel K` follows the grammar of P/02 and the exception in that bridge. The `CALL` ports of P/01.3 are in its [acceptance README](../3/README.md).

## Additional check of the class of errors

A replay of delete with the same id and different items (none/null/number/object/array) must match by op/key/cas/guard. A change of key/cas/guard is a different fingerprint. Compare versions only for equality: uniqueness does not mean a numeric order. (judge-only: sc. 17) also sends arbitrary bytes or no body by the common grammar of POST — it checks P/01.1-R048 and
P/01.1-R144 (`body_form`).

This is a subject of a manual check of the specification and of a future check of an implementation. The prepared requests, the reading and the finite models of the author are not a performed stand test.
A change of `key`, `cas`, `guard`, `not_after` and `not_before` on a replay of `delete` is now scenario 30 (judge-only:
sc. 30) — it checks P/01.1-R105.

## Batch

The batch `op: batch` (N1 `batch`, N3 «write batch»): the JSON is judged whole, as in the other steps of the chapter; for a `conflict` of a batch the expectation has `key`.

The weight of `@big`: the field name plus the value.

The role `console` does not know the limit on the number of rows — chapter 1.2. Restart and the group — chapter 1.3. The refusal of a body over the limit is a common refusal before JSON parsing.

## Extra fields of a command

Scenario 23 (judge-only: sc. 23) checks put/delete and their replays with different unknown top-level
fields: they change neither the data nor the fingerprint — P/01.1-R040, P/01.1-R090, P/01.1-R385. The nested object zzz does not become a guard
or a new command. The closedness of a real guard is checked separately by (judge-only: sc. 20) — P/01.1-R032; a wrong
items of put — (judge-only: sc. 16) — P/01.1-R019 (`items`); ignoring items of delete — (judge-only: sc. 06 and 23) —
P/01.1-R099. The limit of the full body holds, ignored fields included ((judge-only: sc. 22) and reading of the size
check before parsing) — P/01.1-R034, P/01.1-R040, P/01.1-R217, P/01.1-R220.
A prepared scenario does not mean a performed HTTP run of an implementation.

The check outside the TSV: on a role socket the request GET /v1/list with a role forwarding header gets 403 forbidden before listing; an untrusted forwarding and a forbidden forwarded admin are also refused by P/01.2 N3 «check». The same admissible identity without the read right gets 200 with names/versions without values. Scenario 21 (judge-only: sc. 21) checks the latter — P/01.1-R066 — not all identity refusals; the former require a sockets/trust profile from acceptance 06 ((judge-only: sc. 08 of acceptance 06) — a header with a foreign role on a role socket; it checks P/01.1-R345 and P/01.1-R144 (`identity`)).

## A key that is absent or not a string

Scenario 24 (judge-only: sc. 24) separates the form from the rules of the key (P/01.1-R030, P/01.1-R031): an absent or non-string `key` of a command,
`guard.key` and the read parameter `key` — `400 badrequest`; a string that breaks the rules of N1 — `badkey`
((judge-only: sc. 13 and 20) — P/01.1-R031, P/01.1-R032). The last step reads the row and sees that nothing is written.

## Admission time conditions (P/01.1-25; ADR-0091 item 1)

Scenario 28 (judge-only: sc. 28) takes only the edges of the admission time (P/01.1-R079, P/01.1-R080, P/01.1-R088,
P/01.1-R090): a `not_after` that has already passed, `not_after` and `not_before` that
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

Probes of the framing and of the request line (N2.1), each on raw bytes:
- a lone LF and a lone CR at the end of a header line — `400`; an empty line before the request line — `400`;
- raw `\x00`, `\x01`, TAB, `\x7f` and `#` in the request target — `400` (`%00` is three admissible bytes, N2.1);
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

Six seam scenarios (judge-only: `s7-admitted-single-refusals` to `s12-zero-version-not-absence` of `seams.tsv`) use only the existing HTTP, @clock and @reopen grammar; they check P/01.1-R088, P/01.1-R132, P/01.1-R070, P/01.1-R090, P/01.1-R355 and P/01.1-R366. The four admitted refusals expired, early, guard and conflict for single writes and batches have zero business effects, and that coexists with retained admission metadata; the refused identifier stays reusable with a corrected condition. The same distinction holds across ordinary Close/Open; it is a graceful restart witness, not a power-cut or consensus witness.

The admission bounds compare as binary64 values: for a bound that equals the clock in binary64 not_after admits equality and not_before refuses it, for put/delete/batch. On applied put/delete/batch replays bound spellings that round to the same binary64 value are the same fingerprint, and values that differ in binary64 give different fingerprints and badrequest. The request bytes must not be normalized before the actual store parses them. The CALL engine's exact-number comparison is not a replacement store fingerprint. A nonempty string version differs from the absent marker "" in single/batch CAS and guards.

Already covered and unchanged: scenario 35 steps 8–9 (judge-only: sc. 35) choose the first failing guard in both source-list orders, steps 10–11 do the same for CAS — P/01.1-R125, P/01.1-R126; scenario 36 step 3 (judge-only: sc. 36) reorders guards on a successful replay without changing its fingerprint — P/01.1-R134. R116 and scenario 31 steps 1–4 (judge-only: sc. 31) already prove that a successful absent delete leaves read index "" and admits a later create-once; scenario 34 steps 7–8 (judge-only: sc. 34) covers batch deletion of an absent row — P/01.1-R128, P/01.1-R133. No duplicate witnesses are added for these obligations.

Opaque versions do not expose the allocator's count. The new HTTP probes observe unchanged rows/list and a reusable refused id; they do not infer zero version issuance by subtracting or ordering index strings. R089/R132's no-issued-version obligation remains subject to the existing reading check. No snapshot/effects form, new port, native command, implementation or handwritten core is supplied. These are source witnesses awaiting the ordinary implementation adapter, not executed SUT results.

## Replay and last admission metadata

A successful replay of put/delete/batch with the former id keeps the original answers and versions; a deleted row has no visible version. The replay's new last admission metadata is durable across an ordinary reopen (N3 «Admission time»). These cases (judge-only: seams `s13-replay-put-admission`, `s14-replay-delete-admission`, `s15-replay-batch-admission`) check P/01.1-R070, P/01.1-R078, P/01.1-R105, P/01.1-R122, P/01.1-R353, P/01.1-R360, P/01.1-R362 and P/01.1-R365; they are gated by durable because they include @reopen. These are source witnesses, not executed SUT acceptance.

## Admitted mismatches and admission-number domain (ADR-0129 addendum (10), item 3)

A put/delete/batch with an already-applied identifier and different content is an admitted mismatch: badrequest, with durable last admission metadata. The original rows/visible absence and first id answer remain; an original-command replay still returns that answer with again. The mismatch does not replace or free the original applied-id entry. These are admitted refusals, distinct from form/rights/framing refusals before admission; not every badrequest is admitted.

The assigned fractional binary64 admission value survives an ordinary reopen. No integer/millisecond or three-digit row-time writer may truncate it. The witness does not prescribe a metadata encoding or physical clock accuracy.

All four cases (judge-only: seams `s16-mismatched-put-admission` to `s19-admission-binary64-fraction`) check P/01.1-R078, P/01.1-R105, P/01.1-R122, P/01.1-R070, P/01.1-R361 and P/01.1-R362; they use only existing HTTP, signed-decimal @clock and @reopen steps and are selected by the existing durable gate. No port, internal API, CALL grammar, snapshot or power-cut claim is added. The 56 new source steps are not executed implementation acceptance. Constant names are owned by forms/runtime-constants.tsv; specific stand/probe input numbers remain test data.

## Production qualification coverage

The [production acceptance contract](../../spec/production-acceptance.md) assigns the workload, phase-deadline, copy/stop, fault-stage and HTTP-copy groups separately from these functional scenarios. Their declared budgets, independent activation and complete observations are required for a production result. Existing TSV inputs/expectations and ordinary/group applicability remain unchanged; a missing binding or budget is blocked/NotExecuted, not PASS.
