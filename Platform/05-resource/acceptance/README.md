# Acceptance P/05 — the resource

This English text is the source; the Russian translation `ru/acceptance/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../common/acceptance/README.md#dictionary-of-directives-and-doors).
The norm of the lesson is [`05-resource.norms.md`](../spec/05-resource.norms.md) Н5. The scenarios were moved from the acceptance of
М10/08 (01, 02, 08) and
М10/11 (01 → 09, 16 — the Architect's decision on В2 of the plan of the move of lesson 6: a scenario belongs to the lesson whose norm it checks) and
М10/10 (10; the Specification's decision on В2 of the move)
(stage B, ADR-0083 addendum (1): without a change of behaviour); the numbers, the names of the scenarios and the steps are the former ones, except `09-resource-door`
(in М10/11 — `01-resource-door`; the number 01 is taken by `01-objects-door` from М10/08). Sc. 17–23 are the coverage audit of P/05 (2026-10-30,
the drafts F01–F03, F05–F07 of the audit session; the section «Coverage audit» below); sc. 24–28 — F04 (the section «Edges of `free_ask`»); sc. 29–45 —
the second pass of the coverage audit (Gemini; the section «Coverage audit of P/05, second pass (Gemini)»; sc. 44, 45 — its deferred drafts
after the Architect's decisions of 2026-10-30 on the questions of the norms of the Gemini audit, P/05 items 1, 4).

Doors and directives: `resource`, `console`, `store`, `admin` (sc. 17, 24–29, 37–41), `@start resource` (sc. 09-resource-door, 10-body-copy, 16-presence-lock, 17–28, 31, 37–41; the expectation `@exit 2` — sc. 17), `@start resource on srv-b`, `@sigterm resource`, `@sigkill resource#1` (sc. 31), `@start controller` (sc. 42), `@start worker` (sc. 16, 19, 20, 24–28, 42, 43), `@sigkill` (sc. 16-presence-lock, 43), `@spoil object` (sc. 43), `@put object` from `inputs/` (sc. 44, 45; the section «Inputs `inputs/`»), `@until`, `@append event`
(sc. 08, 21, 22, 34–38), `@append event-raw` (sc. 22), `@cut role resource store` / `@mend role resource store` and `@sleep` (sc. 18; the sleeps — the section «Sleeps»), the request forms `@header` (`X-Written`, `X-Sum`, `Range`), `@raw`, `@big` (sc. 23), the method `HEAD` (sc. 35), `ASSERT`; the expectations `@oneof` (sc. 20), `@header <Имя>: ~<текст>` (sc. 31, 33, 36), `<код> ~текст` (sc. 33, 36).

## Preparation of each scenario

The scenarios are independent. Before each one, stop and wait for all the processes of the previous
scenario, create isolated directories/ports and an empty store: the rows, the objects and
the id memory of the store are absent. Clear the event tree, the mirrors and the index cache, the variables and the replay keys of the runner.
Install the current testsub from the common testdata with its service mark with administrative
rights. There are no units and no user rows yet. The preparation is not a transfer of the state of
the previous scenario and not a check of the installer.

Start the store, a new console testsub and the resource srv-a per the section «Stand» of the common acceptance README. Their doors must be ready;
the resource is registered and available to the console before the first step. Sc. `09-resource-door`, `10-body-copy`, `16-presence-lock`, 17–28, 31 and
37–41 do not start the resource before the first step: a step of the scenario raises it (`@start resource`; in sc. 17 and 18 — step 2, in 24–28 — after
the worker, in 31 — after the resource `srv-b`, in 37–41 — after the rows its first pass reads). All the processes of this box
use one BOX_ID and server=srv-a; each new process gets a new instance.
There is no controller, except sc. 42 (`@start controller` — by a step); there are no workers, except `w-1` (`testsub`) of sc. 16-presence-lock,
19-service-names, 42 and 43, `t-srv-a-2`, `t-1`, `t-srv-a-1` (`testsub2`) of sc. 20-door-room and `t-srv-a-1` of sc. 24–28, which their
steps start. There is no second server, except the resource `srv-b` of sc. 31 (`@start resource on srv-b` — its own `PLATFORM_DIR`, its own door, the same
store; «Stand»). platform/mirror and platform/space are not set, except sc. 24–28, 39–41, where a step writes them through the door `admin`; free
requests and copies are not prepared. The build is schema 1.

Sc. `20-door-room`, `23-object-ceiling`, 24–31, 37–41, 44 and 45 install the catalogue `testsub` and `testsub2` the same way as `10-body-copy` (the order —
«Stand»; the runner installs `testsub2` when a step of the scenario names it).
Sc. `10-body-copy` (the body copy at the resource, from М10/10; T10, T11) installs the catalogue `testsub` and `testsub2` (the order — «Стенд»;
`testsub2` declares a blob field, `testsub` does not), starts the resource by step 1 (`@start resource`); the resource door `resource` with
an admissible identity of a neighbour; the digest `sha256-190267417aed…` — of the bytes `peer-copy`. It needs neither the console nor the controller.

console — the console door testsub from the loopback, access to the operations and the units is permitted (the console is needed by the steps 02/6, 8, 12–16, 08/14 —
the same door at the merge, and 09-resource-door/6–7 — `/servers`, `/metrics`; the console — P/06 (`Platform/06-console/ru/06-console.md`, for people, not in the export));
resource — the resource door srv-a with an admissible identity; store — the store door with reading of
testsub/ and `platform/doors/`; admin — the door `admin.sock` (the row `platform/schema` of sc. 17, the console writes it by the role admin, P/06.6 Н1.1а). If the deployment uses TLS, issue the corresponding
certificates and roles per P/02.4 Н1.6 (`w2c-ca.sh issue <server> <роль>`, the kit `kit`) and the address rule of P/02.4 Н1.6;
these scenarios do not replace the check of the TLS refusals.

## scenarios.tsv

The format is [the dictionary of directives and doors of the «Stand» of the common acceptance README](../../common/acceptance/README.md#dictionary-of-directives-and-doors).
In total 35 scenarios / 292 steps; sc. 29–45 (the second pass of the audit, below) — 128 steps; sc. 24–28 (the edges of `free_ask`, below) — 49 steps; the other 115: 86 HTTP (with @until; the Architect's decision of 2026-11-04 — by scenarios.tsv), four `@append event`, `@append event-raw`, 18 `@start`, `@sigkill`,
`@cut`, `@mend`, `@sleep` and two ASSERT.

Steps of the reconciliation of python and go М10/6–11 (2026-10-18):
- **01-objects-door/6–15** — the listing of the objects door — a filter by the families of the door (`prefix=testsub/` — 200 empty), `other/` — 403, an empty
  parameter and `%FF` — 400, the directory `testsub/heartbeats` — 403, `%FF` and U+2028 in a key — 400, `OPTIONS` and `PUT` of the listing —
  405 (E1, E4–E10).
- **02/7–12, 17–23** — the grammar of `unit`, `from`, `limit`, an empty and a repeated parameter, an unknown parameter and a non-ASCII
  `since` of the hint — 400; `from=1_0` — a number; `POST /events` at the resource — 405 without a body (E12–E17).
- **02/13–16** — the console: `from` by the grammar of the time reader ([the gate and pass contract](../../common/contracts/gate-and-pass.md)
  «Numeric query parameters»): `%2B1`, `%201`, `1e3` — 400, `%31` (= `1`) — 200 (C06-EVENTS-QUERY-LEXEME-162-01, the Architect's decision of 2026-10-27).
- **08** — the resource paths: `..`, `%2F` and a foreign tree in `/mirrored`, `/mirror`, `/events/{path}` — 404/400 (the write does not
  happen), `GET` on `/mirror/…` — 405, `/buckets` not of two segments — 404 (E26, E27, E29–E31, E36). The body of `PUT` is
  `@raw {}`, `X-Sum` — its SHA-256.

E19 — sc. 08 steps 12–14: `@append event` writes `{bad` into a bucket bypassing the writer, the resource and the console answer 200 with
`lines_garbled: 1`. Steps 15–16 — the bucket name and `e<эпоха>` are the form of the norm, they are not encoded; an alarm in the tree `audit/console`
(not `.alarms`) is `class: alarm` by the field ([the event journal contract](../../common/contracts/event-journal.md); the second pilot,
Н-2, Н-3). Without a step, by reading: E3, E11, E18, E22–E24, E34, E35, E37, E38, E42, E43, E46 — a stand with one resource does not write
temporary files and does not fill the disk; the dictionary does not express `X-Sum` with a trailing space. The second pass of the audit (Gemini) took as steps
E32 (an alarm of a subsystem — sc. 34), E44 and E45 (the band between the marks and the disabled marks — sc. 41, 40), an open bucket at
`PUT /mirror` — by the name of a window in the future (`20990101T000000Z`, sc. 32).

## The presence lock (sc. 16-presence-lock)

From the acceptance of М10/11 (the second pilot, Н-1; catches Б1): the resource and the worker `w-1` — in the heartbeat of the resource `running: [testsub/w-1]`;
`@sigkill w-1` — the lock is free, `running: []`; a new start of the same name — `running` again. The norm is
[the presence lock contract](../../common/contracts/presence-lock.md) (the owner is lesson P/05) and Н1.4 `presence`; the heartbeat
of the resource is read through the objects door (`resource GET /v1/objects/platform/resources/srv-a/heartbeat?scope=local`). Step 1
starts the resource, step 2 — the worker `w-1` per the section «Stand» of the common acceptance README (`BOX_ID` of the stand, `SERVER_NAME=srv-a`);
`@sigkill` waits for the confirmed termination of the process.

## Time in a row (sc. 09-resource-door; `@time`)

The rule of Н0 of P/01.1 «Time in a row» (the Architect's decision of 2026-10-18), the writer's side: step 2 of sc. 09-resource-door
reads the time field written by the resource — the door row `platform/doors/srv-a`, `since` (`@time`).

## Coverage audit (sc. 17–23)

The scenarios of the coverage audit of P/05 (2026-10-30); each expectation is from the norm:

- sc. 17-schema-refusal — the check of the schema at start (Н3 «resource start — schema check»; [the schema contract](../../common/contracts/schema.md)
  «Check at start», «Boundary»): `platform/schema` with `version` 2 (above SCHEMA 1) and `x` (not an integer) — `@start resource`
  exits with code 2; there is no door row `platform/doors/srv-a` — the check of the schema goes before the first write (lifecycle
  «Порядок старта»); with `version` 1 — the resource starts and writes the door row. The row is written by the door `admin` (the writer is the console by the role admin,
  P/06.6 Н1.1а); the values of a store row are strings (P/01.1);
- sc. 18-schema-read-wait — an error of reading `platform/schema` is «ждать доступности, не начиная работы», not code 2 (the schema
  contract): `@cut role resource store` before the start — the store is silent to the resource (the connections of the socket of the role `resource` hang without
  an answer); `@mend` closes the hanging connections — the resource gets a read error and, without exiting, reads again: the door row
  appears without a new `@start` (the deadline 90 s — the norm does not limit the repeat of the reading by a step). A resource that exited on a read
  error will not write the door row;
- sc. 19-service-names — the service names (Н1.1 `disk`; [the event journal contract](../../common/contracts/event-journal.md)
  «File names in shared trees»): the write of the heartbeat of the worker `w-1` goes by temp + rename under the lock of the directory
  `objects/testsub/heartbeats/~lock`, the lock file is not removed; the traversal of the tree skips the names with `~` — there is no
  `testsub/heartbeats/~lock` in the listing of the key; the key `~lock` is encoded into `%7elock` — the reading of the key is 404, not the lock file (a service name does not
  coincide with a key). The heartbeat of `w-1` in the listing is the control that the directory is the right one;
- sc. 20-door-room — the heartbeat of the resource (Н1.4 `heartbeat`): the field `door` with `addr` and `mode` (`loopback` without `RESOURCE_TLS`, `mtls`
  with it — «Stand» does not set `RESOURCE_TLS`, the branch `mtls` is for a deployment with TLS); the door row (Н1.4 `door_row`,
  [the presence lock contract](../../common/contracts/presence-lock.md) «Count `room`»): for `testsub2` (`grows: true`, the role file
  `testsub2worker.env` with `HOST_MEMORY_MB=4096`, `WORKER_MEMORY_MB=256` is put by the runner — «Stand») `room` =
  min(16 − the live ones, 98 − the live ones with a number n ≥ 2): without workers — 16 and `live` ""; `t-srv-a-2` (n = 2) — 15 and "2"; `t-1`
  (a name without a server — without a number, [the slot name contract](../../common/contracts/slot-name.md) «Role process name and its number»)
  — 14, does not enter `live`; `t-srv-a-1` (n = 1, the base one) — 13, does not enter `live`. `testsub` has no role file — there are no elements
  `room.testsub`, `live.testsub`, they are not expected;
- sc. 21-events-wait — the hint (Н1.6): there are no rows under `want` — the wait answers by the deadline `{changed: false, seq}`; the row
  `testsub/c1` of the kind `probe.tick` is appended — `since=0` («у клиента нет позиции») answers at once `{changed: true, seq,
  touched}` with exactly this triple; `seq` is monotonic (`ASSERT $s1 <= $s2`); the cursor `since=seq` without new rows — again
  `changed: false`. The outcomes `full`, `replaced` and the eviction require parallel waits — outside the TSV;
- sc. 22-torn-tail — a torn tail (Н1.3 «Нечитаемая строка бакета», Н3 «query» step 3; the event journal contract `torn`;
  the event journal merge contract `partial`): a whole line is given out, `truncated` 0; a tail without LF — even a parsable JSON — is not
  a line: not in `events` and not in `truncated`, the answer is `partial: true`, there is no `lines_garbled` (the field is only when it is above 0). The tail
  is written last: the next append would be glued to it;
- sc. 23-object-ceiling — the ceiling of the resource door (Н1.1 «Потолки ресурса», Н2 `PUT /v1/objects/<sub>/blobs/<digest>`, Н4):
  a body copy of exactly 64 MiB (67108864 bytes `x`, `@big`) — 204 and it is read (a GET of exactly the limit is permitted, Н2); 67108865 bytes —
  413 — by reading (the section «The ceiling +1 byte — by reading» below). The names are the SHA-256 of the bodies; `X-Written` is a number; `testsub2` declares a blob field;
  the stand does not set `max_bytes` of the object store (0 — without a ceiling). On 413 the door MAY answer without reading the body to the end: the runner
  reads the answer and does not count the break of its sending as an error of the step.

Not accepted from the drafts of the audit: F02 sc. 01 (`.tmp` is not a service name of the current norm: the component `w-9.tmp` is encoded as
it is, it is a key; the service names are with `~`, ADR-0083 addendum (16)) and the directive `@plant object` (a service name is given by the lock `~lock`
of a real write, sc. 19; the bytes of the file of an ordinary object are the implementation's own, «Implementation decides» item 9); `@freeze store` (the store is not a name for `@sigkill`/`@freeze`; a read error — `@cut role` of sc. 18). F04 (the edges of `free_ask`) was accepted later — sc. 24–28 after C05-PASS-FIRST-AT-START-01, the section [«Edges of `free_ask` on the first pass»](#edges-of-free_ask-on-the-first-pass-sc-2428) (the Architect's decision of 2026-11-04).

## Coverage audit of P/05, second pass (Gemini) (sc. 29–45)

The drafts G01–G08 of the audit session (Gemini, commit a1f4efe61), reconciled with the norm and with the current acceptance (the mark «новое» of the drafts is
against the report of the first pass, not against the acceptance); large bundles are divided among scenarios. Each expectation is from the norm:

- sc. 29-row-objects (G01 item 1) — the row objects (Н1.1 `row_object`, `door`; Н4 «строка-объект — 403»): `objects.rows` of `testsub2`
  (`marks/*`) and `commands/*` of both subsystems (the manifests with `requests`) are not given out by the objects door even with a written store row
  `objects/<ключ>` (the door `admin` writes it bypassing the writer), on any `scope`; a `prefix` under which there are no keys of the families of the door —
  403; `prefix=testsub2/` — a filter: 200, there are no row objects in the listing;
- sc. 30-copy-written-max (G01 item 2) — `written` of a body copy (Н1.1 `written`, C05-COPY-WRITTEN-SOURCE-01): the copy keeps the `written`
  of the original (`X-Written`), one already lying there does not decrease: 1700000010, then 1700000005 — stays 1700000010, then 1700000020;
- sc. 31-objects-cluster (G03) — two resources (Н1.1 `cluster`, «Тела у ресурса» `mirror`; Н2 `scope`, `X-Missing`; Н1.4 `pass`):
  `srv-b` — `@start resource on srv-b`; the body is put into `srv-a` through the copy door, then `srv-a` is restarted — its first pass at
  start (C05-PASS-FIRST-AT-START-01) copies the body to the ring neighbour `srv-b` (copies — 1, there is no row `platform/mirror`) with the original
  `written`; an equal `written` — the server with the larger name (`srv-b`) is chosen, in the listing and in the reading; the heartbeat of `srv-b` — only in `cluster`;
  the copy of `srv-a` is newer (1700000005) — `srv-a` is chosen; `@sigkill resource#1` (the first copy — `srv-b`) — the listing `cluster` names
  `missing: ["srv-b"]`, the 404 of an absent key carries `X-Missing: srv-b`. `@sigterm resource` of step 6 stops the last copy —
  `srv-a`;
- sc. 32-mirror-put-refusals, 33-mirror-put-read (G04) — the protocol of the mirror of buckets (Н1.6 `/mirror`, `/mirrored`; Н2; Н4; R05-G04):
  there are no copies of the server — `/mirrored/srv-b` 404; a bucket whose end by its name is later than the clock of the receiver (`20990101T000000Z`) — 400; no
  `X-Sum`, not 64 lowercase hex (`bad-hex`, uppercase) — 400; the sum is wrong — 422, there is no copy; the closed bucket `20260101T000000Z` with the correct
  sum (SHA-256 of the bytes `foo`) — 204, the list `{copies: [{path, written, size, sum}]}`, a repeat of the same copy does not shift `written`
  (`$w1`), the bytes of the copy — with `X-Sum`, of a foreign window — 404; the heartbeat of the resource — `mirrors: {srv-b: 1}` (the copies of the neighbour in `.mirror/`);
- sc. 34-events-alarms-unit (G05 part 1) — a row of the tree `testsub.alarms/c1` (Н1.2, E32; Н3 «query» step 4, C05-QUERY-UNIT-ALARMS-01):
  `subsystem: testsub`, `unit: testsub/c1`, `class: alarm`; `unit=testsub.alarms/c1` is not normalized — 200 without matches;
- sc. 35-events-cut-order (G05 part 2) — the resource query (Н2 `HEAD` — 405; the event journal merge contract `cut`, `by`, `late`, `truncated`;
  the event journal contract `bucket`, EJ-L06): rows with given `t` (the query window by default is 0…1e12); a duplicate id — the first row
  (`val: 1`); the alarm first, the observations by `keep`, an equal `t` — the id by bytes (…-11 before …-12, although it was written later); `by=occurred`
  (a row without `occurred` — by `t`); `truncated` — the candidates after deduplication minus the given out ones (3 − 2, 3 − 1);
- sc. 36-events-bucket-stream (G05 part 3) — the streams of a bucket (Н2 `/events/{path}`, `/buckets`; Н4): a bucket of one line — 87 bytes with
  LF, SHA-256 `395b0387…8fc3`; 200 — the bytes and `X-Sum`; `Range: bytes=0-9` — 206 `Content-Range: bytes 0-9/87`; a range outside the file — 416
  `Content-Range: bytes */87`; `/buckets/testsub/nosuch` (an unknown unit) — 404. The type of `/buckets` and 206/416 without headers — sc. 04
  of the acceptance of chapter 6.4;
- sc. 37-retention-garbled, 38-holds-garbled-row (G06 parts 1, 2) — the first pass `retain` (Н3, Н1.4 `heartbeat`; C05-RETENTION-PULSE-33,
  R05-RETENTION-MIXED-51-01; the holds contract): the retention rows are written by the door `admin` before the start, the trees — by `@append event` before the start (the pass
  judges the trees that exist); `days` 0 (`testsub/retention`) and not a number (`testsub2/alarms_retention` with a correct `testsub2/retention`)
  — `retention_garbled: [testsub, testsub2]`, `retention_withheld` — `days_garbled` for both; the hold row `testsub2/notches/…` with
  `to` not a number and without `released_at` — the window is not read, the row is not released — `garbled_rows: {notches: 1}`;
- sc. 39-settings-unread (G06 part 3) — `platform/space` and `platform/mirror` with `enabled` not by the form (`maybe`) — the rows are unreadable as a whole
  (the outcomes `space`, `mirror` of P/02.4: of `mirror` only `copies` is read by the field) — `settings_unread: [mirror, space]`; `relieve` is not
  executed: with the marks `high` 1e-7 the own row `free-*` would have been written, it is not there;
- sc. 40-space-disabled, 41-space-band (G07) — the disk marks (Н1.4 `space`, `free_ask`; Н3 `relieve`; E45, E44; R05-G03): the own row
  `free-srv-a-events` {free, volume: events, server: srv-a, at} lies there before the start; `enabled: false` — the first pass removes it, `short`
  0; the share of the occupied space between `low` 1e-8 and `high` 0.99999999, `need > 0` — the row stands as it is (the same version, the same `free`);
- sc. 42-heartbeat-units (G08 part 1) — `units` of the heartbeat of the resource (Н1.4, E39): the controller puts `c2` and `c1` to the worker `w-1`; `units.testsub`
  — `[c1, c2]` in ascending order of bytes, not in the order of creation (`instances` is not mandatory by the form of the heartbeat — it is not expected);
- sc. 43-spoiled-object-door (G08 part 2) — the spoiling of an object (Н1.1 `door`, «Implementation decides» item 8; C05-SPOIL-OBJECT-BYTES-01): the heartbeat of
  `w-1` after `@sigkill w-1` is spoiled by `@spoil object` — the objects door gives it out as it is: in the listing with `written`, `server`, `size`,
  `GET` 200, not 503;
- sc. 44-objects-door-family (G01 item 1) — `objects.door` of the manifest (Н1.1 `door`): `testsub2` declares `door: [tickets/*]` —
  the door gives out the object `testsub2/tickets/t1` (`@put object` from `inputs/ticket-t1.json`, 28 bytes): `GET` 200 with the body, in the listing
  `prefix=testsub2/tickets/` with `size` 28; `testsub` has no section `objects` — `testsub/tickets/t1` 403 (a key outside the families of the door, Н4);
- sc. 45-gone-door (G02) — the tombstone at the remover (Н1.1 `written`, `door`; [the tombstone contract](../../common/contracts/tombstone.md)
  `listing`, `rewrite`; Н4 «удалено позже»; C05-GONE-BODY-READ-01, C05-GONE-REWRITE-AT-WRITE-01): the tombstone
  `.gone/testsub2/blobs/sha256-2c26b46b…e7ae` (SHA-256 of the bytes `foo`) with `written` 1700000100 is put by `@put object` from
  `inputs/gone-foo.json`; the ordinary listing `testsub2/blobs/` does not show it — `{}`; `prefix=.gone/` — the listing of the tombstones, `GET` —
  the body `{written, peers, acked}`; `PUT` on `.gone/…` — 405 (a write of a non-blob); a body copy with `X-Written` 1700000050 (older than the
  tombstone) — 409, there is no key (404); with 1700000200 — 204, the key is read with the original `written`, and the tombstone is removed by the same action
  (the Architect's decision of 2026-10-30, P/05 item 1): the listing `prefix=.gone/` — `{}`, `GET` of the tombstone — 404, without a sleep and `@until`.

Not accepted from the drafts of the second pass (in detail — the report of the analysis):
G04 `PUT /mirror/<свой сервер>/…` — the norm does not require 400: to accept or to refuse is «Implementation decides» item 11 (C05-MIRROR-PUT-SELF-01,
the Architect's decision of 2026-10-30, P/05 item 2), the acceptance does not check this; G05 `/buckets/testsub/c1` with the type and the fields in one expectation, `X-Sum` without a value — the dictionary does not express it (the type — sc. 04
of chapter 6.4); G06 `short: 0` with an unreadable `platform/space` (R05-G03: the input of the pass is not read — the former `short`) and `copies: "bad"` as
an unreadable `platform/mirror` (by the field — `copies` 1, the row is read); G08 `units: {}` after the spoiling of the heartbeat of the frozen `w-1` (the spoiling is
at a stopped writer; the norm now names it: an unreadable heartbeat does not enter `units`, C05-UNITS-PULSE-GARBLED-01, the Architect's decision of
2026-10-30, P/05 item 3 — a scenario with the heartbeat of a live worker is not added, by reading) and the stop of the controller.

## Inputs `inputs/`

The objects that a scenario puts by `@put object <ключ> inputs/<файл>` bypassing the writer (the exception `P/05 acceptance-entry
inputs`; the Architect's decision of 2026-10-30, the questions of the norms of the Gemini audit, P/05 item 4). The bytes are those of the drafts of the coverage audit (Gemini,
G01, G02), without changes.

| File | Scenario | What is in it |
|---|---|---|
| `ticket-t1.json` | 44 | the object `testsub2/tickets/t1` of the family `objects.door` of the manifest `testsub2`: `{"id":"t1","title":"check"}` with LF, 28 bytes |
| `gone-foo.json` | 45 | the tombstone `.gone/testsub2/blobs/sha256-2c26b46b…e7ae` by the form [`gone`](../data/gone.schema.json): `written` 1700000100, `peers` `["srv-b"]`, `acked` `[]`, with LF |

## Comparison

The forms of an expectation are per the dictionary. The expectation of one code does not require an empty body.
A repeat of a variable inside expect compares its temporary value. The directives are not sent
to the server as HTTP. A full answer is additionally checked by the contract of its owner:
the store — P/01.1, the resource doors — Н2 of the lesson, the console — [P/06](../../06-console/spec/06-console.api.openapi.yaml) (chapters 6.4, 6.5).

## Sleeps (`@sleep`, ADR-0080 addendum (17) item 4)

One sleep: sc. `18-schema-read-wait` step 3, `@sleep 10` — a check of absence: while the store is silent to the resource, it does not exit
(an error of reading `platform/schema` — wait, do not start with code 2; an exit is visible by step 5 — there is still no door row); within 10 s
a started process reaches the first step of the start — the reading of the schema. The second pass of the audit (Gemini) — two more: sc. 33 step 3,
`@sleep 2` — a check of absence: a repeated reception of the same copy of a bucket does not shift `written` (R05-G04); `written` is wall-clock seconds,
an implementation may have it as an integer, therefore more than a second passes between the receptions, otherwise the shift would not be visible; sc. 41 step 6,
`@sleep 12` — a check of absence: the own row `free-*` in the band between the marks is neither removed nor rewritten; the heartbeat with
`pass_started` (step 5) says that the first pass has begun, within 12 s its step `relieve` on an empty stand is finished (the same deadline as for
sc. 24–28 after the start of the worker). Waiting for an event is `@until`: sc. 09-resource-door step 2 waits for the first door row, step 3 — for a new door mark
(`at` has changed; the mark — every 15 s, Н1.4 `door_row`), sc. 08 step 16 — for the alarm row in the index, sc. 16-presence-lock
steps 3, 5, 7 — for `running` in the heartbeat of the resource (analysis of the review of stage B 3–5, № 26); sc. 17 step 8, 18 step 5 — for the first door row; sc. 19 step 3 — for the heartbeat
of `w-1` in the listing; sc. 20 steps 3, 5, 7, 9 — for the count of the door after the mark (every 15 s); sc. 22 steps 3, 5 — for the index rows; sc. 31 steps 2, 4 — for the doors
of `srv-b` and `srv-a`, step 8 — for the copy of the body at `srv-b` after the first pass of the restarted `srv-a`; sc. 33 step 9, 37–39 the heartbeat step, 40
steps 4, 5, 41 step 5, 42 step 5 — for the heartbeat of the resource (every 10 s) after the first pass; sc. 34–36 — for the index rows; sc. 43 step 2 — for the heartbeat
of `w-1` in the listing.

## Evidence outside TSV

These are tasks of the implementation/stand, not checks already performed:

| Area | Counterexample and the required observation |
|---|---|
| Objects | An equal written, one server is silent: the choice of the name, missing and 404 without a false completeness — sc. 31; the row objects are not given out — sc. 29; a GET of an object larger than 64 MiB (put bypassing the door) — 413 ResourceError before successful headers (a body copy of exactly 64 MiB and +1 byte at the door — sc. 23) |
| Events | Two processes on different boxes and a restart: the ids differ. Both classes, of, the protected fields; fsync is confirmed by a barrier |
| Index | A torn tail — sc. 22. An empty/evicted cache keeps the answer with unchanged files; the boundaries from/to/limit and the priority of alarms |
| Wait | The outcomes `full` and `replaced` (`changed` and the deadline — sc. 21), wrong/repeated parameters and boundaries. Two CN with one client do not evict each other; after a restart/full the ordinary pass remains |
| Streams | JSONL without an array; a break of a file (200 with `X-Sum`, 206 and 416 with `Content-Range` — sc. 36). PUT of the mirror: 64 MiB and +1 byte, the deadline, a publication error: no partial copy, the former one is intact (no `X-Sum`, not by the form, a bad sum — sc. 32) |
| Retention/holds | Absence and an unknown reading are distinguished; a wrong days/unreadable holds do not permit removing a tree (the reasons in the heartbeat — sc. 37, 38). The hold window (the hold function — the vectors [`holds`](../../common/vectors/holds/README.md)), the floor of the deadline of the marks and the hour of the mirror |
| Free space | After the change of free_ask to an ordinary request with the same rid, the removal conflicts by CAS, the request is intact. freeing does not include a freeing already reflected by the measurement |

A reading of the branches and the schema confirms only the corresponding order/form. Timers,
processes, file barriers, network breaks and cryptographic identity require separate
observations. The tombstone at the remover (the listing, the body, 409, the removal on a newer write) — sc. 45; the convergence of the body copies by the neighbours
(Н1.1 «Надгробия»: `drop`, `ack`, `remove`) and `restore` (Н1.4 «Восстановление бакетов») — a stand with two resources, there is no scenario.

Restore: a full empty list, a confirmed absence of copies, a 500 of the directory and a broken answer are distinguished; the last two
leave the restoration incomplete and are repeated per Н1.4. A new process does not reuse INSTANCE_ID.
Additional probes outside the TSV.

Check the id for collisions of the composite names a-e1-j/node:1:aaaaaa and a/j-e1-node:1:aaaaaa, UTF-8, different trees/epochs/parallel numbers, a restart and the outcome of the suppression; copies keep the original id. For both lists buckets/mirrored: an absent, an empty known and an unreadable directory are distinguished; an error before the headers is 500 without a body, a break does not give a full answer. Additional probes outside the TSV.

An additional check by reading R36-07: the pairs server=a-b/volume=c and server=a/volume=b_c have different keys; volume=b-c is outside the profile of requests.free and is diagnosed without a write. Check the lengths of volume 0/1/64/65, the permitted ASCII and non-ASCII; on reading an existing row the absence of unit is not enough — server/volume must coincide. The update and the removal use CAS of exactly the checked version; a row of another owner does not change. The current TSV does not run these configurations of volumes.

By reading (run 36, Kimi): PULSE_LIMIT is a declared finite positive profile; an excess is diagnostic. The listing of objects has both 403.

Each writing participant encodes the file names itself (the event journal contract «File names in shared trees»): any permitted name is representable, different keys are different paths, including the temporary names and the mirrors (R37, Codex).

This is a subject of a manual check of the specification and of a future check of an implementation. Prepared requests, a reading and the author's finite models are not a performed stand test.

## Boundaries of scenarios

Between scenarios the runner stops the processes, resets the store and the variables. After
the last step, wait for the stop of all the created processes, then remove the state.

## `journal/corrections.tsv`

The log of AI corrections (ADR-0080 addendum 1; ADR-0124: a log, not an input, not in the export): `date`, `sample`, `fix`, `languages`. The rows from before the move are from `corrections.tsv`
of the acceptances of М10/10 and М10/11 (removed by the move of lesson 6, `e11928b21`), at the beginning of this log by the scenarios of the chapter, with the former paths and numbers (they are
resolved by `Platform/common/id-map.tsv`); the rows without a scenario are in all successor chapters (analysis of the review of stage B 6–7, № 18). The log of М10/08 is moved as a whole into the acceptance of chapter 6.4 (`Platform/06-console/journal/corrections-4.tsv`, a log, not in the export).

## Edges of `free_ask` on the first pass (sc. 24–28)

The coverage audit of P/05, F04 (audit-kimi, commit c3336f837), after the clarification C05-PASS-FIRST-AT-START-01: the first pass of the resource is
at start, therefore the edges of the step `relieve` are visible right after `@start resource`, without sleeps of 600 s. The marks of `platform/space`
(`high` 1e-7, `low` 1e-8) are set by the door `admin` before the start: the disk of the stand is always «beyond the mark», `need > 0`. Sc. 24 is the control:
the resource writes its own row `testsub2/requests/free-srv-a-events` {free, volume: events, server, at}, in the heartbeat `short` ≥ 1.
Sc. 25–28 — under the same key there lies in advance a row not of its own form (with `unit`; a foreign `server`; a foreign `volume`; a volume outside
the profile `b-c`): the resource does not touch it (the same version) and writes the event `free_ask.key_taken` (P/05 Н1.4 `free_ask`, Н3
`relieve`; the outcomes `free-ask.outcomes.tsv`; the kind of the event — the event journal contract). The volume of the box is `events`.

## The ceiling +1 byte — by reading (sc. 23; C05-CEILING-PLUS-ONE-READING-01, -02)

`PUT` of a body of 64 MiB + 1 byte: the door answers 413 by `Content-Length` before reading the body (Н1.1 «Потолки ресурса», OpenAPI) —
the early refusal of P/01.1 Н2.1: a full answer with `Connection: close`, then the drain of what was sent. The volume and the deadline of the drain are a choice of the
implementation (P/01.1 item 9 «Implementation decides»; the witness has 1 MiB), a body of 64 MiB exceeds it, and the door lawfully
closes the connection with a break while the client is still sending: the answer 413 may not reach the client (the dry run of Go 2026-10-30:
«транспорт»). The step «+1 → 413, no key» is removed from the scenario and is checked by reading: 413 by `Content-Length` before the body,
the answer before the drain, no key; exactly 64 MiB — 204 and the reading 200 — stay a scenario (as G09 item 4 of the audit of P/06).

## Kit seams

[seams.tsv](seams.tsv) contains additional CALL probes for generated stagetests; their exact fixture setup and observations are [the forms README](../forms/README.md). They invoke the real resource procedures or front door. They supplement [scenarios.tsv](scenarios.tsv), the additional probes and reading, and are not the runner’s process acceptance.
