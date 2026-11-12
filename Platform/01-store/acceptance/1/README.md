# Acceptance P/01.1 — the store operations vocabulary

This English text is the source; the Russian translation `ru/acceptance/1/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md). The acceptance checks the requirements of P/01.1 named below.

## Profile interface

The profile is `01-store` in the [generic profile and assembly contract](../../../common/acceptance/PROFILE.md). `stand.store1` starts a fresh store instance for this chapter: it consumes the assigned data directory, administrative socket, prepared rights file and the body/row test parameters through the common stand substitutions. Its ordinary side serves the published `acc` role. `keys.request_line_limit` names the implementation's request-line boundary; `keys.role_header` names its role-forwarding header where a probe needs one. The optional `adapters.door` exposes the same ordinary/admin operations through the persistent transport of the common contract; it does not replace raw HTTP checks. The JCS package uses the `vectors` entry assigned by its [wire form](../../../common/vectors/wire.tsv), not a guessed `stand.jcs` invocation. The implementation chooses its own executable names and flags and binds these responsibilities in its profile.

- **Durability.** The store command keeps the durability barriers on (P/01.3-R111); the stand does not disable them.

## `scenarios.tsv`

The chapter checks the requirements named by its readiness checklist. Its scenario format is the common dictionary of directives and doors, with these chapter-specific rules:

- `expect` is `<code> <JSON body>`; the JSON is compared whole: the targets of this chapter have the mode `whole` of the dictionary of the common acceptance README (`<code> <JSON>`); `error` is compared only if it is named: its text is not normed. An unnamed `error` is admitted only in the root of the body; an extra field elsewhere is a mismatch. The targets of the chapter admit only the unnamed root fields `error` and `size` under these two rules.
- For a `200` answer to `GET /v1/list` the **order of names inside `keys`** is also checked: the sequence of names decoded from the JSON in the order received MUST equal the sequence in `expect`, which is given by UTF-8 bytes. The runner keeps this order when parsing the answer and does not sort what it received before the comparison. For an empty `keys` the sequence is empty. Spaces and the way of JSON escaping are insignificant; the order of other objects, `items` included, is still not checked.
- `$name` binds only a JSON string (N1: a version is a string on the wire); a number or another type is a mismatch of the step.
- An unnamed `size` is admitted only in the root of the body of a body refusal (the row `body_limit` of `forms/refusals.tsv`: `413` with the kind `toolarge` and the body limit as `limit`): it is checked to be an integer JSON number equal to the known full entity-body size in bytes, not a string and not a boolean, and is then excluded from the comparison with `expect`. A valid, representable `Content-Length` defines that full size even for an early answer after only a prefix of the body has been sent. With `Transfer-Encoding: chunked`, `Content-Length` is ignored: the full size of a completed chunked body is the sum of the decoded chunk-data bytes, excluding chunk framing and trailers; for an incomplete chunked body the full size is unknown and `size` is absent. A refusal for an unrepresentable framing length has no `size`. The absence of `size` remains admissible when the full size is known; other unnamed fields, `key` included, are not admitted. A weight refusal names `key` and `size` in `expect`, and they are compared as named fields.

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
| `@hold <door> <N>` | open N connections to the door and write nothing on them; the judge keeps its sockets open until the end of the scenario, then closes them; the expectation `ok` — independent Linux observation matches each client socket to a live accepted server socket descriptor held by the store process group, with all N alive together by the readiness term; queued connections do not count. The observation and failure rules below apply |
| `@io store $<name>` | bind the name to the number of bytes that the processes of the store caused to be written to storage: the field `write_bytes` of `/proc/<pid>/io`, summed over the process group of the store; the expectation `ok`. When the judge cannot read this counter, for example under another account, the step and every step that compares the name are `not_executed` with the reason `io_counter_unreadable`, not red |

For `@hold`, the runner records the identities of its N client sockets and observes their server peers through Linux socket metadata and the open socket descriptors of the store process group. For a Unix socket, it obtains the client inode, resolves its peer inode through Unix socket diagnostics and confirms that this peer inode belongs to an open socket descriptor in that process group. A socket still in the listener queue has no such accepted descriptor and does not satisfy the observation. A successful `connect` or a sleep alone proves no acceptance. This observes accepted sockets; it prescribes neither an internal connection counter nor a new door of the implementation.

The readiness term is the `@hold` row of [Terms of the stand](../../../common/acceptance/README.md#dictionary-of-directives-and-doors). It is one monotonic interval from the first attempt to open a client connection through confirmation that all N matched server sockets are alive together, at or before the term. Opening or retrying another connection does not reset the interval; it is not a separate term for each connection.

The runner records closures and rechecks the held set before each dependent step, then watches it through that step. If a held socket closes, or its independent observation becomes unavailable or fails, while the store command remains alive, the result is `stand`: proof of the test-side precondition has been lost. This applies before and during a dependent step, including a closure permitted by the declared idle deadline; the response code or timeout of an already running dependent HTTP step does not become an `implementation` mismatch under that lost precondition. That current step is `stand`, the scenario ends, and later steps remain unrun by the common scenario-abort rule. Closures caused by an explicit scenario stop directive are effects of that directive and do not invalidate earlier successful preparation. An independently proven unexpected exit or signal of the store command remains an `implementation` failure under the command-failure rule.

The implementation's declared idle deadlines remain in force. `@hold` does not judge those deadlines, impose a minimum, disable the timer, write data into the held sockets or reopen closed sockets to keep them alive. If independent observation is unavailable or fails, the result is `stand`. Only when observation works, no held socket has closed and no observation failure has occurred, failure to confirm all N live accepted sockets by the readiness term is `implementation`. Loss of a held socket or observation failure takes priority over that readiness timeout.

**Expectation.**

| Form | Meaning |
|---|---|
| `<code> @close …` | `@close` right after the code: after its response the implementation closes the connection, within the term of `@noreply`; the rest of the cell is judged as the expectation without `@close` |
| `@noreply` | the whole expectation: no byte of a response arrives until the implementation closes the connection or the term of `@noreply` in «Terms of the stand» ends; a response is a mismatch |
| `… @by(<seconds>)` | the last word of the expectation: the answer, closure `@close` or `@noreply`, or exit after `@sigterm store` arrives no later than that many seconds, instead of the `@noreply` term; for a request the interval starts at the first request byte written by the judge, or at connection establishment if it writes no request bytes; for `@sigterm store` it starts when the judge sends the signal. With `@noreply` the implementation also closes the connection within that interval. This is an upper bound: the judge records its clock and scheduler resolution separately and does not widen the bound |

## The instance of the chapter

An additional check of the full key (P/01.1-16,22) runs beyond the scenario TSV on a separate instance
with rights on acc/: the keys of this prefix at the boundary lengths in UTF-8 bytes, including Cyrillic and four-byte
characters, and the same set in a non-empty guard.key. For an existing guard use its actual version, for an absent one —
index="", so as not to fall into the version comparison refusal. Every implementation accepts the full key up to
KEY_BYTES; one byte more is badkey.
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

The process seams cover the properties of the core that the checklist checks «by reading»: the `id`
memory does not forget by time alone (P/01.1-11), equality and both sides of fractional admission-time bounds for put, delete and batch
(P/01.1-25), the admission time retains its fraction when clocks go back and after a restart (P/01.1-26), concurrent CAS of one row (P/01.1-15), a batch whole after a
restart (P/01.1-31). The runner executes them through the seam adapter, by the [normalization below](#seam-normalization) (the directives `@clock`, `@reopen`, `@parallel` are defined there and in the header of the file). The stages — `store_core` (`@clock`, `@parallel`) and `durable` (`@reopen`) of `forms/stages.tsv`, by `seams:1.1:<scenarios>` in their `gate`.

### Seam normalization

The review seams of P/01.1 have no `CALL` rows. Its steps are HTTP requests and the directives `@clock`, `@reopen` and `@parallel`. Over the [bridge](../../../common/acceptance/seams.md#explicit-test-side-seam-bridge) of the common acceptance README each HTTP or directive step becomes `method: call` with one of three public tokens. No bridge field or method is added.

| `name` | Step | `input` | Observation |
|---|---|---|---|
| `store-http` | `GET` or `POST` | closed object: required `method` and `target` (the path with the query, as written in the step), optional `body` (the text of the body of the step as one string, absent when the step has none) | `{kind: "value", value: {"status": <integer>, "body": <string>}}`: the status and the whole response body |
| `clock` | `@clock +N` or `@clock -N` | closed object `{"shift": <string>}`: the shift in the same syntax as the step | `{kind: "value", value: {}}` |
| `reopen` | `@reopen` | `{}` | `{kind: "value", value: {}}` |

`store-http` reaches the ordinary request handling of the store; it is not a new door. `clock` moves the controlled clock of the store by N seconds, cumulatively; the clock starts at 2000000000 and the implementation chooses how it is controlled. `reopen` closes the store and opens it again on the same data directory with the same clock. An HTTP step's `<code> <JSON body>` is compared as in the acceptance of chapter 1.1, and a directive's `ok` matches an empty object value. `@parallel K` follows the grammar of P/02 and the exception in that bridge. The `CALL` ports of P/01.3 are in its [acceptance README](../3/README.md).

## Additional check of the class of errors

A replay of delete with the same id and different items (none/null/number/object/array) matches by op/key/cas/guard. Changing key, cas, guard, not_after or not_before gives a different fingerprint (P/01.1-R105). Versions are compared only for equality: uniqueness does not imply numeric order. The POST checks also send arbitrary bytes or no body under the common grammar, checking P/01.1-R048 and P/01.1-R144 (`body_form`).

These are subjects of a manual specification check and a future implementation check. Prepared requests, reading and the author's finite models are not a performed stand test.

## Batch

The batch `op: batch` (N1 `batch`, N3 «write batch»): the JSON is judged whole, as in the other steps of the chapter; for a `conflict` of a batch the expectation has `key`.

The weight of `@big`: the field name plus the value.

The role `console` does not know the limit on the number of rows — chapter 1.2. Restart and the group — chapter 1.3. The refusal of a body over the limit is a common refusal before JSON parsing.

## Extra fields of a command

Put/delete and their replays accept different unknown top-level fields without changing data or the fingerprint (P/01.1-R040, P/01.1-R090). The nested object zzz does not become a guard or a new command. A real guard stays closed under P/01.1-R032; put checks the `items` form of P/01.1-R019; delete ignores `items` under P/01.1-R099. The full-body limit still applies, ignored fields included, before parsing (P/01.1-R034). A prepared scenario is not a performed HTTP implementation run.

Outside the TSV, check a valid GET /v1/list on a role socket with a role-forwarding header: it gets 403 forbidden before listing. Untrusted forwarding and a forbidden forwarded admin are also refused by P/01.2 N3 «check». The same admissible identity without read rights gets 200 with names and versions, without values. Identity refusals need a sockets/trust profile, including a foreign-role header on a role socket, under P/01.1-R066 and P/01.1-R144 (`identity`).

## A key that is absent or not a string

The checks distinguish the form from the key rules (P/01.1-R030, P/01.1-R031): an absent or non-string command key, guard.key or read parameter key gives `400 badrequest`; a string that breaks N1 gives `badkey` under P/01.1-R031 and P/01.1-R032. The final read confirms that nothing was written.

## Admission time conditions (P/01.1-25; ADR-0091 item 1)

The admission-time checks cover only the edges of the admission time (P/01.1-R079, P/01.1-R088,
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

Six seam scenarios (judge-only: `s7-admitted-single-refusals` to `s12-zero-version-not-absence` of `seams.tsv`) use only the existing HTTP, @clock and @reopen grammar; they check P/01.1-R088, P/01.1-R132, P/01.1-R070, P/01.1-R090, P/01.1-R355. The four admitted refusals expired, early, guard and conflict for single writes and batches have zero business effects, and that coexists with retained admission metadata; the refused identifier stays reusable with a corrected condition. The same distinction holds across ordinary Close/Open; it is a graceful restart witness, not a power-cut or consensus witness.

The admission bounds compare as binary64 values: for a bound that equals the clock in binary64 not_after admits equality and not_before refuses it, for put/delete/batch. On applied put/delete/batch replays bound spellings that round to the same binary64 value are the same fingerprint, and values that differ in binary64 give different fingerprints and badrequest. The request bytes must not be normalized before the actual store parses them. The CALL engine's exact-number comparison is not a replacement store fingerprint. A nonempty string version differs from the absent marker "" in single/batch CAS and guards.

Guard and CAS checks choose the first failure in both source-list orders (P/01.1-R125). Reordering guards on a successful replay does not change its fingerprint (P/01.1-R134). A successful absent delete leaves read index "" and admits a later create-once (R116); batch deletion of an absent row follows P/01.1-R128 and P/01.1-R133. These obligations need no duplicate witnesses.

Opaque versions do not expose the allocator's count. The new HTTP probes observe unchanged rows/list and a reusable refused id; they do not infer zero version issuance by subtracting or ordering index strings. R089/R132's no-issued-version obligation remains subject to the existing reading check. No snapshot/effects form, new port, native command, implementation or handwritten core is supplied. These are source witnesses awaiting the ordinary implementation adapter, not executed SUT results.

## Replay and last admission metadata

A successful replay of put/delete/batch with the former id keeps the original answers and versions; a deleted row has no visible version. The replay's new last admission metadata is durable across an ordinary reopen (N3 «Admission time»). These cases check P/01.1-R070, P/01.1-R078, P/01.1-R105, P/01.1-R122; they are gated by durable because they include @reopen. These are source witnesses, not executed SUT acceptance.

## Admitted mismatches and admission-number domain (ADR-0129 addendum (10), item 3)

A put/delete/batch with an already-applied identifier and different content is an admitted mismatch: badrequest, with durable last admission metadata. The original rows/visible absence and first id answer remain; an original-command replay still returns that answer with again. The mismatch does not replace or free the original applied-id entry. These are admitted refusals, distinct from form/rights/framing refusals before admission; not every badrequest is admitted.

The assigned fractional binary64 admission value survives an ordinary reopen. No integer/millisecond or three-digit row-time writer may truncate it. The witness does not prescribe a metadata encoding or physical clock accuracy.

All four cases check P/01.1-R078, P/01.1-R105, P/01.1-R122, P/01.1-R070; they use only existing HTTP, signed-decimal @clock and @reopen steps and are selected by the existing durable gate. No port, internal API, CALL grammar, snapshot or power-cut claim is added. The 56 new source steps are not executed implementation acceptance. Constant names are owned by forms/runtime-constants.tsv; specific stand/probe input numbers remain test data.

## Production qualification coverage

The [production acceptance contract](../../qualification/README.md) assigns the workload, phase-deadline, copy/stop, fault-stage and HTTP-copy groups separately from these functional scenarios. Their declared budgets, independent activation and complete observations are required for a production result. Existing TSV inputs/expectations and ordinary/group applicability remain unchanged; a missing binding or budget is blocked/NotExecuted, not PASS.
