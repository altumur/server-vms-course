# Acceptance P/01.1 — the store operations vocabulary

This English text is the source; the Russian translation `ru/acceptance/1/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md). The norm of the chapter is
[`01.1-store.norms.md`](../../spec/01.1-store.norms.md) Н5.

## `scenarios.tsv`

The format is the dictionary of directives and doors of the common acceptance README. Specific to chapter 1.1:

- `expect` is `<код> <JSON-тело>`; the JSON is compared whole; `error` is compared only if it is named: its text is not normed.
- For a `200` answer to `GET /v1/list` the **order of names inside `keys`** is also checked: the sequence of names decoded from the JSON in the order received MUST equal the sequence in `expect`, which is given by UTF-8 bytes. The runner keeps this order when parsing the answer and does not sort what it received before the comparison. For example, in sc. 08 step 4 an answer with `b` before `a` is a mismatch, although the values match. For an empty `keys` the sequence is empty. Spaces and the way of JSON escaping are insignificant; the order of other objects, `items` included, is still not checked.
- `$имя` binds only a JSON string (Н1: a version is a string on the wire); a number or another type is a mismatch of the step.
- Only for the body refusal in sc. 22 step 1 the optional field `size` is admitted: if it is present, it is the integer
  JSON number 4194364 (the full size of the sent body), not a string and not a boolean. After it is checked it
  is excluded from the comparison with `expect`. The absence of `size` is admissible by Н2; other additional fields,
  `key` included, are not admitted (the common rule of `error` is kept). For the weight refusal in sc. 15 the fields `key` and `size`
  are mandatory and are compared as before.

## `journal/corrections-1.tsv`

The log of AI corrections (ADR-0080 addendum 1; ADR-0124: a log, not an input, not in the export): `date`, `sample` (a sample of a generation error), `fix` (which line of the lesson was clarified), `languages`. Empty: no error has repeated so far.

## Additional check of the class of errors of run 36 (Kimi)

A replay of delete with the same id and different items (none/null/number/object/array) must match by op/key/cas/guard. A change of key/cas/guard is a different fingerprint. Compare versions only for equality: uniqueness does not mean a numeric order. Sc.17 also sends arbitrary bytes or no body by the common grammar of POST.

This is a subject of a manual check of the specification and of a future check of an implementation. The prepared requests, the reading and the finite models of the author are not a performed stand test.
A change of `key`, `cas`, `guard`, `not_after` and `not_before` on a replay of `delete` is now scenario 30 (below).

## Coverage audit of P/01, second pass (sc. 30–32)

The coverage audit session, second pass (Gemini, 2026-10-30, commit 6a5817f88, `АУДИТ-ПОКРЫТИЯ-GEMINI-P01.md`, G01–G03):
- Sc. 30 — the replay fingerprint by value (Н3 «write», «delete»): for `put` a reversed order of the fields of `items` and an absent
  `cas` instead of `cas: null` give the same fingerprint (`again`); `delete` under the `id` of a `put` write — 400. For `delete` under one `id`
  (`cas`, `guard`, `not_before`, `not_after`): `items` as an array and `1.0` instead of `1` — `again`; a different `key`, `cas` `""` and no
  `cas`, a different key and version of the guard and no guard, a different `not_after` and `not_before` — 400; `put` under this `id` — 400; the row is
  deleted once.
- Sc. 31 — steps 1–4: deleting an absent row with `cas: ""` — 200 and a new version, the row is still `null, ""`,
  creation with `cas: ""` after it passes (Н3 «delete», «Races»); steps 5–7: a replay of a write for which by the time of the replay both
  `cas` and the guard are violated — its answer with `again` (the `id` memory before the guard and CAS); steps 8–13: after the refusals `early`, `guard` and
  `conflict`, the same write with the same `id` and a corrected condition — a new write without `again` (Н3: a refusal does not occupy the `id`).
- Sc. 32 — the order of the checks of a command of Н2.1 on pairs of violations; each pair tells adjacent steps apart by the kind of refusal: `op`
  before the key; the socket of `floor` before the form of `floor` and `id`; the form of the key before the guard; the rules of the key before `items`;
  `items` and `cas` before the guard (`badrequest`, not `badkey`); `id` and `not_after` before the weight and the rights (`400`, not `413` and not
  `403`); `id: null` and `not_after: 1e400` (not finite in binary64) — 400; a lone surrogate in `guard.key` — `badkey`, in a
  value of `items` — `badrequest`. Steps 13–14 see that nothing is written either under `acc/` or under `other/`.

## Batch (sc. 33–40; ADR-0094 B9)

The batch `op: batch` (Н1 `batch`, Н3 «write batch»): the JSON is judged whole, as in the other steps of the chapter; for a `conflict` of a batch the expectation has `key`.
- Sc. 33 — all or nothing: step 6 — the `cas` of the second row is stale, steps 7–8 see both rows as before; steps 4 and 10 — one version for all rows.
- Sc. 34 — creation, edit and removal in one batch; step 7 — delete of an absent row; steps 10, 12 — `items` of delete is not read; step 11 — the `cas` of the removed row is stale.
- Sc. 35 — guards: step 3 — the guard is not written; step 7 — the guard before `cas`; steps 8–9 and 10–11 — the first violation in the order of `guards` and `writes`.
- Sc. 36 — the fingerprint: steps 2–4 — the order of `guards` and of the fields of `items`, `cas: null` give the same; steps 5–9 — a different one; steps 10–12 — the memory is shared with the write; step 14 — the memory before the guard;
  steps 15–16 — a refusal does not occupy the `id`; steps 17–21 — `items` of delete is not included, `cas` is.
- Sc. 37 — deadlines: steps 5–6 — before the guards and `cas`, steps 7–8 — a refusal does not occupy the `id`.
- Sc. 38 — the form; steps 26–30 — the order of the checks of Н2.1 on pairs of violations; steps 31–32 — one over the limit, steps 35–36 — exactly at the limit; step 37 — extra top-level fields, among them the fields of a single write, are not read.
- Sc. 39 — the weight: two rows of 400000 bytes each are together heavier than the ceiling, each is lighter; a row heavier than the ceiling — 413 with its `key`. The weight of `@big`: the field name plus the value.
- Sc. 40 — rights: 403 before deadlines (step 5), a refusal does not occupy the `id` (steps 6, 8).

The role `console` does not know the limit on the number of rows — sc. 16 of chapter 1.2. Restart and the group — sc. 30, 31 of chapter 1.3. The refusal of a body over the limit is a common refusal before JSON parsing, sc. 22.

## Extra fields of a command (K37-05)

Scenario 23 checks put/delete and their replays with different unknown top-level
fields: they change neither the data nor the fingerprint. The nested object zzz does not become a guard
or a new command. The closedness of a real guard is checked separately by sc. 20; a wrong
items of put — sc. 16, ignoring items of delete — sc. 06 and 23. The limit of the full body
holds, ignored fields included (sc. 22 and reading of the size check before parsing).
A prepared scenario does not mean a performed HTTP run of an implementation.

The check R38-06 outside the TSV: on a role socket the request GET /v1/list with a role forwarding header gets 403 forbidden before listing; an untrusted forwarding and a forbidden forwarded admin are also refused by P/01.2 Н3 «check». The same admissible identity without the read right gets 200 with names/versions without values. Scenario 21 checks the latter, not all identity refusals; the former require a sockets/trust profile from acceptance 06 (sc. 08 — a header with a foreign role on a role socket).

## A key that is absent or not a string (G39-07)

Scenario 24 separates the form from the rules of the key: an absent or non-string `key` of a command,
`guard.key` and the read parameter `key` — `400 badrequest`; a string that breaks the rules of Н1 — `badkey`
(sc. 13 and 20). The last step reads the row and sees that nothing is written.

## Admission time conditions (P/01.1-25; ADR-0091 item 1)

Scenario 28 takes only the edges of the admission time: `not_after` = 1 (1970) has already passed, `not_after` and `not_before` =
4102444800 (2100) have not yet come under any clock of the stand. Steps 2–4 — `expired` and `early` write nothing; steps 5–7 —
the order «time conditions → guard → CAS»; steps 8–11 — `not_after` in the replay fingerprint (`4102444800.0` equals `4102444800`
by value, a different number and absence — `400`); steps 12–13 — the refusal `expired` does not occupy the `id`; steps 15–19 — forms
(a string, a negative, `null`, `bool` — `badrequest`; the form of the guard before `not_after` — `badkey`). The equality boundary and
the non-decrease of the admission time are by reading (Н5 of the norms).

## Request parsing (Н2.1, P/01.1-23)

Scenario 17 step 5 — `op: floor` on a role socket: `403 forbidden` before parsing the key. Scenario 20 steps 10–11 —
the form of the guard before the rules of the key: `{key: "/x", index: "x"}` and `guard: null` — `badrequest`. Scenario 25 checks the query: `+` is a space (step 3 reads the row `a b`), `%2B` is a plus (step 4), `+` in `prefix`
is a space too (step 5), a repeated parameter — `badrequest`, bytes not UTF-8 — `badkey`, `%` without digits stays
a letter of the key and does not find the row. Scenario 26 — strict JSON of the body: a repeated field name at the top level
and in `items`, `NaN` in an extra field, a lone surrogate in a key and in `items`; step 6 sees that nothing is written,
steps 7–8 that a surrogate in an extra field is not read. Scenario 27 — an unknown method and a known path
with a method that is not its own: `404` with `Fault`, not 405 or 501; the paths `/v1/%67et`, `/v1/get/` and `//v1/get` are not decoded and not
normalized — also `404`. Steps 10–12 of scenario 25 — the order of the query checks: empty pairs are skipped, `?key` is an empty
key (`badkey`), a repeat before UTF-8 (`badrequest`).

A probe outside the TSV — raw bytes into the door socket, each answer `400` with the body `Fault` `{kind: badrequest}`, not a page of the
server and not 414, 431, 501 or 505: `GET /v1/list\r\n\r\n` (no HTTP version); a request line of the length of the limit
named in the implementation description (item 9 of «Implementation decides») plus 1 byte — the runner does not know a foreign limit and takes it
from there; a header without a colon; a header with a space before the colon and an obs-fold header continuation (RFC 9112 §5.1–5.2).
Separately: a target in absolute form `GET http://localhost/v1/get?key=acc/x HTTP/1.1` — `404 badrequest` (the path is not
decoded and not normalized, Н2.1); a body with `Content-Length` and `Transfer-Encoding: chunked` together is read
as chunked (§6.3). Early refusal (Н2.1): `POST /v1/write` with `Content-Length` larger than the body limit and a body
that is still coming — the client gets `413 toolarge` with `Connection: close`, not a reset of the connection.

Probes of the framing and of the request line (Н2.1, reconciliation of python and go 2026-10-18), each on raw bytes:
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
