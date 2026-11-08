# Judge-only N5 case coverage

This English text is the source; the Russian translation `ru/spec/05-resource.n5.cases.md` is derived from it (ADR-0121).

These case descriptions and their outcomes are judge-only data. The canonical normative chapter is [`05-resource.norms.md`](05-resource.norms.md). Generic rules and explicitly retained normative examples remain there.

<!-- case-coverage-block-1 -->

| № | Scenario | Norms |
|---|---|---|
| 01 | `01-objects-door` (M10/08): the objects door: a listing of an empty family, 400 on scope, 403 on a family outside the door, 404 on an absent one, 405 on PUT of a non-blob; the listing is a filter (`prefix=testsub/` — 200), `other/` — 403, an empty parameter and non-UTF-8 — 400, a directory of two parts — 403, U+2028 in a key — 400, `OPTIONS` and `PUT` of the listing — 405 (reconciliation of python and go M10/6–11) | N1.1, N2 |
| 02 | event query: 400 on keep/by/class/a bare unit; an empty answer `{events: [], state: "live"}`; the grammar of `from`/`limit`/`unit`, an empty and repeated parameter, an unknown hint parameter, non-ASCII digits — 400, `1_0` is a number; `POST /events` — 405 (reconciliation of python and go M10/6–11); at the console `from` by the grammar of the time reader: `+1`, `%2B1`, `%201`, `1e3` — 400, `%31` — 200 (C06-EVENTS-QUERY-LEXEME-162-01, the Architect's decision of 2026-10-27) | N1.3, N1.6, N2, N4 |
| 08 | resource paths: `..`, `%2F`, another's tree in `/mirrored`, `/mirror`, `/events/{path}` — 404/400; `GET` on `/mirror/…` — 405; `/buckets` not of two segments — 404 (reconciliation of python and go M10/6–11, E26, E27, E29–E31, E36); the line `{bad` in a bucket — `/events` of the resource and of the console 200 with `lines_garbled: 1` (E19); an alarm in the tree `audit/console` (not `.alarms`) — `class: alarm` by the field (the second pilot, N-2) | N1.3, N1.6, N2, N4; the event log contract |
| 09 | `09-resource-door` (M10/11): resource: the heartbeat and the door row `platform/doors/srv-a` with `at` that changes; `/servers` sees the resource `live`; `w2c_resources_live 1` | N1.4 `door_row`; P/02.4 N1.1, N3 «server start»; P/04 |
| 10 | `10-body-copy` (M10/10): the body copy at the resource: 204, the copy reads; a wrong digest — 422; without `X-Written` — 400; uppercase hex and a subsystem without a blob field — 405 | N1.1 «Bodies at the resource» `mirror`, N2 (reconciliation of python and go M10/6–11, T10, T11) |
| 16 | `16-presence-lock` (M10/11): the presence lock — the resource and the worker `w-1`: `running: [testsub/w-1]`; `@sigkill` — `running: []`; a new start of the same name — `running` again (the second pilot, N-1) | N1.4 `presence`; [the presence lock contract](../../common/contracts/presence-lock.md) |
| 17 | `17-schema-refusal`: `platform/schema` with `version` above SCHEMA or not a number — `@start resource` exits with the code 2, there is no door row; `version` 1 — it starts (coverage audit of P/05, F01) | N3 «resource start — schema check»; [the schema contract](../../common/contracts/schema.md) «Check at start» |
| 18 | `18-schema-read-wait`: the store is silent to the resource (`@cut role resource store`) — a read error of the schema: the resource waits, does not exit; the store answers — the door row without a restart (coverage audit of P/05, F01) | N3 «resource start — schema check»; the schema contract «Check at start», «Boundary» |
| 19 | `19-service-names`: the directory lock `~lock` of the write of a worker heartbeat — outside the listing of the objects door, the key `~lock` — 404 (coverage audit of P/05, F02) | N1.1 `disk`, N2; [the event log contract](../../common/contracts/event-journal.md) «File names in shared trees» |
| 20 | `20-door-room`: the field `door` in the resource heartbeat; `room.testsub2`, `live.testsub2` of the door row by the live locks — a number n ≥ 2 in `live`, the base n = 1 and a name without a number — only in `room` (coverage audit of P/05, F03) | N1.4 `heartbeat`, `door_row`, `room`; [the presence lock contract](../../common/contracts/presence-lock.md) «Count `room`» |
| 21 | `21-events-wait`: `/events/wait` — by the term `{changed: false, seq}`; `since=0` with a line under `want` — at once `changed` with `touched`; `seq` is monotonic; the cursor `since=seq` — without changes (coverage audit of P/05, F05) | N1.6, N2 |
| 22 | `22-torn-tail`: a bucket tail without LF — not in `events` and `truncated`, `partial: true`, not `lines_garbled` (coverage audit of P/05, F06) | N1.3 «Unreadable bucket line», N3 «query» step 3; the event log contract `torn` |
| 23 | `23-object-ceiling`: a body copy of exactly the resource door byte limit (OpenAPI Content-Length.maximum) — 204 and the read 200 (coverage audit of P/05, F07); +1 byte — 413 — checked by reading (C05-CEILING-PLUS-ONE-READING-01) | N1.1 «Resource ceilings», N2, N4 |
| 24 | the edges of `free_ask` on the first pass (C05-PASS-FIRST-AT-START-01; coverage audit of P/05, F04): the resource writes its own request row `free-srv-a-events`, in the heartbeat `short` ≥ 1 | N1.4 `free_ask`, `space`, `heartbeat`; N3 «resource pass» `relieve` |
| 25 | under its own key a row with `unit` — not touched (the same version), the event `free_ask.key_taken` | N1.4 `free_ask`, `space`, `heartbeat`; N3 «resource pass» `relieve` |
| 26 | under its own key a row with another's `server` — not touched, `free_ask.key_taken` | N1.4 `free_ask`, `space`, `heartbeat`; N3 «resource pass» `relieve` |
| 27 | under its own key a row with another's `volume` — not touched, `free_ask.key_taken` | N1.4 `free_ask`, `space`, `heartbeat`; N3 «resource pass» `relieve` |
| 28 | under its own key a row with a volume out of profile (`b-c`) — not touched, `free_ask.key_taken` | N1.4 `free_ask`, `space`, `heartbeat`; N3 «resource pass» `relieve` |
| 29 | `29-row-objects`: the row objects `objects.rows` and `commands/*` — 403 also with a written row `objects/<key>`, on any `scope`; their `prefix` — 403; `prefix=testsub2/` — 200 without them (coverage audit of P/05, second pass, G01) | N1.1 `row_object`, `door`; N2; N4 |
| 30 | `30-copy-written-max`: `written` of a body copy is the source one, an already lying one does not decrease — the greater of the two (G01) | N1.1 `written` (C05-COPY-WRITTEN-SOURCE-01), «Bodies at the resource»; N2 |
| 31 | `31-objects-cluster`: two resources — the body copy to the neighbour on the first pass with the source `written`; `scope=cluster`: an equal `written` — the greater server, the fresh copy wins; a silent server — `missing`, `X-Missing` at 404 (G03) | N1.1 `cluster`, «Bodies at the resource» `mirror`; N1.4 `pass`; N2 `scope`, `X-Missing` |
| 32 | `32-mirror-put-refusals`: `/mirrored` without copies — 404; `PUT /mirror` of an open bucket, without `X-Sum`, `X-Sum` not in form — 400, a wrong sum — 422, there is no copy (G04) | N1.6; N2; N4 «mirror» |
| 33 | `33-mirror-put-read`: a copy of a closed bucket — 204, `/mirrored` — `{copies}`, a repeat does not shift `written`, the bytes with `X-Sum`; the heartbeat `mirrors` (G04) | N1.6 (R05-G04); N1.4 `heartbeat`; N2 |
| 34 | `34-events-alarms-unit`: a line of the tree `testsub.alarms` — `subsystem` and `unit` without the suffix, `class: alarm`; `unit` with `.alarms` — 200 without matches (G05) | N1.2 (E32); N3 «query» step 4 (C05-QUERY-UNIT-ALARMS-01) |
| 35 | `35-events-cut-order`: `HEAD /events` — 405; an id duplicate — the first line; the order `cut` (the class, `keep`, an equal time — id), `by=occurred`, `late`, the bound `to`, `truncated` after deduplication (G05) | N1.3 `query`, `cut`; N2; N3 «query» step 6; the event log merge contract |
| 36 | `36-events-bucket-stream`: `/events/{path}` — 200 with `X-Sum`, 206 and 416 with `Content-Range`; `/buckets` of an unknown unit — 404 (G05) | N2; N4 «buckets», «bucket» |
| 37 | `37-retention-garbled`: a wrong `days` in `retention` and in `alarms_retention` — `retention_garbled`, `retention_withheld: days_garbled` on the first pass (G06) | N3 `retain`; N1.4 `heartbeat`; N4 (C05-RETENTION-PULSE-33, R05-RETENTION-MIXED-51-01) |
| 38 | `38-holds-garbled-row`: a hold row without a readable window — `garbled_rows.notches` (G06) | N3 `retain`; N1.4 `heartbeat`; [the holds contract](../../common/contracts/holds.md) |
| 39 | `39-settings-unread`: unreadable `platform/space` and `platform/mirror` — `settings_unread: [mirror, space]`, its own row `free-*` is not written (G06) | N1.4 `space`, `mirror`, `heartbeat`; N3 |
| 40 | `40-space-disabled`: `enabled: false` — its own row `free-*` is removed, `short` 0 (G07) | N1.4 `space` (E45), `heartbeat.short`; N3 `relieve` |
| 41 | `41-space-band`: early observation of the own row in the band; completion is established separately by synchronous s63-free-ask-band-completed (G07) | N1.4 `free_ask` (E44); N3 `relieve` |
| 42 | `42-heartbeat-units`: `units` of the resource heartbeat — the ids of the units from `status` of a live worker in ascending order of bytes (G08) | N1.4 `heartbeat` (E39), `running` |
| 43 | `43-spoiled-object-door`: a spoiled object — the door gives it as it is: the listing and `GET` 200 (G08) | N1.1 `door`; «Implementation decides» item 8 (C05-SPOIL-OBJECT-BYTES-01) |
| 44 | `44-objects-door-family`: `objects.door` of the manifest — `testsub2/tickets/t1` (`@put object` from `inputs/`) — `GET` 200 and in the listing; `testsub/tickets/t1` without `objects` in the manifest — 403 (G01) | N1.1 `door`; N2; N4 |
| 45 | `45-gone-door`: the tombstone `.gone/<object-key>` (`@put object` from `inputs/`) — outside the ordinary listing, `prefix=.gone/` and `GET` of the body — reading, `PUT` — 405; an older copy — 409, there is no key; a newer one — 204 with the source `written`, the tombstone is removed by the same action (G02) | N1.1 `written` (C05-GONE-REWRITE-AT-WRITE-01), `door` (C05-GONE-BODY-READ-01); N4 «deleted later»; [the tombstone contract](../../common/contracts/tombstone.md) `listing`, `rewrite` |

<!-- case-coverage-block-2 -->


The additional source seams s63–s67 in [acceptance/seams.tsv](../acceptance/seams.tsv) use the existing synchronous ports: completed relieve in the band; actual candidate selection at 144/145 and calendar fallback; independent peer retry boundaries. The unchanged process scenario41 observes only its listed early state; pass_started plus a fixed sleep does not prove relieve completion. A seam declaration is not implementation execution.

End of judge-only N5 case coverage.
