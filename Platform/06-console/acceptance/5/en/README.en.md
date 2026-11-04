# Acceptance P/06.5 — observations of the console

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../../common/acceptance/README.md#словарь-директив-и-дверей).
The norm of the chapter is [`06.5-console.norms.md`](../../../spec/06.5-console.norms.md) Н5. The scenarios were moved from the acceptance of
М10/09 (01, 02, 04–12; 03 — the session — into
[the acceptance of chapter 6.3](../../3/README.md)) and of М10/11
(02 → 14, 09 → 16, 13, 15 step 1), and from М10/10 —
03 and 08 → 17 whole (the step `/metrics` of the console; analysis of the review of stage A 6–7, № 32) (stage B, ADR-0083 addendum (1): without a change of behaviour); the numbers, the names of the scenarios and the steps are
the former ones (sc. 08 and 19 — the first step `@start resource`: the console reads the heartbeats of the workers through the objects door of the resource of its own server, without the resource «не известно», [the object store client contract](../../../../common/contracts/object-client.md) `door`; P03-OBJECTS-DEFAULT-1FD; the Architect's decision of 2026-10-27), except `14-resource-silent` (in М10/11 — `02-resource-silent`) and `16-resource-unreadable-heartbeat` (in М10/11 —
`09-resource-unreadable-heartbeat`) and `17-snapshot-garbled` (in М10/10 — `08-snapshot-garbled`): the numbers 02, 08 and 09 are taken
by the scenarios of М10/09. In total 33 scenarios / 324 steps: 12 — sc. 33 (a write only by the ticket writes_via, ADR-0119 addendum (10)), 11 — sc. 32 (a pass of the second kind without a worker, ADR-0094 B1), 9 — sc. 31 (the feed series, ADR-0094 B2), 14 — sc. 30 (the counter door, ADR-0094 B4), 15 — sc. 29 (the counter of the batch door, ADR-0094 B9), 72 — sc. 26–28 (static files and the shell of a mounted subsystem, ADR-0094 B7), 23 — sc. 24–25 (the second pass of the coverage audit of P/06, Gemini), 30 — sc. 20–23 (the coverage audit of P/06), 8 — sc. 19 `19-place-held-no-row` (C06-WHERE-PLACE-SERVER-33-01), 5 — sc. 18 `18-id-default` (`{id}` in the default, VMS request № 1), 85 in the scenarios of М10/09 (the steps 04/8 and 12/12–13 were added — analysis of the review of stage B 6–7, № 19,
№ 20), 23 from М10/11, 14 from М10/10.

Doors: without a prefix — the console (scenarios 01–12, as in М10/09), `console` and `console2` (scenarios 13–16, as in М10/11; 03 and 17, as in М10/10), `resource` (03, 17),
`store` with `@as`; the directives `@start`, `@sigkill`, `@sigterm`, `@spoil object`, `@put object`, `@sleep`, `@until`; the expectations
`~текст`, `!contains`, `@header`, `@file`, `@any`, `@absent`, `@not`.

## corrections.tsv

The log of AI corrections (ADR-0080 addendum 1): `date`, `sample`, `fix`, `languages`. The rows from before the move are from `corrections.tsv`
of the acceptances of М10/09, М10/10 and М10/11 (removed by the move of lesson 6, `e11928b21`), at the beginning of this log by the scenarios of the chapter, with the former paths and numbers (they are
resolved by `Platform/common/id-map.tsv`); the rows without a scenario are in all successor chapters (analysis of the review of stage B 6–7, № 18).

## Stand of sc. 01, 02, 04–12 (from М10/09), 18–33

Before each automatic scenario stop the processes of the previous one, create separate empty row/object stores and clear the variables/replay memory. Load the unchanged testsub and testsub2 and the third manifest of this directory `probe-x.subsystem.yaml` (a name with «-»: `metrics.prefix` is `probe_x`, mutation check 7cecaf2 № 40) and the fourth `probe-w.subsystem.yaml` (the word `writes_via`, sc. 33); root is testsub, the second is available under /testsub2, the third under /probe-x, the fourth under /probe-w; there is no domain, requests come from the loopback. The background controller/resource/worker do not work before @start. The build is schema 1; the store is fresh and empty — there is no row platform/schema, the runner does not write it (reading of the commits «cammeta-acceptance» 2026-10-20). For each POST that creates a unit the runner issues a fresh Idempotency-Key, kept only for the replays of the same step. A table POST does not get a promise of replay memory from this.

Without workers there is no placement; the counter c4 is created only in 04. The domain login, closed grants, CSP and a repeat of a logical action are checked by a separate stand/module test, not by this TSV.

- **A pass of the second kind (sc. 32; ADR-0094 B1).** `probe-x` declares `door.pass` of the second kind, it has no worker. Steps 1–2 — a refusal of the console by the form of the manifest: `no worker…` becomes `{code, message}`; step 3 — the first segment of the route, while the path is outside `api/v1`; step 4 — `apix`: the comparison is by whole segments. Steps 5–8 — there is no ticket with such a value: the console is open, and still the identity is only the ticket, 401, no write. Step 9 — an open route does not read the ticket. A live ticket — [the stand of the pass of the second kind](../../../../common/acceptance/pass/README.md).
- **Processes.** Sc. 08–10 bring up processes by the directives of the «Stand» (`@start worker`, `@start resource`,
  `@start controller testsub2`); before `@start` there are no background processes. The worker is `w-1` of the subsystem `testsub` on `srv-a`.
- **The store door.** Sc. 07 writes an intent row bypassing the controller: `@as testsubcontroller store` — the role socket of the
  controller `testsub` by the installation rights file (P/02.5). There is no controller `testsub` in sc. 07, nobody will
  rewrite the row.
- **A place without a row (sc. 19).** The worker `t-1` of the subsystem `testsub2` on `srv-a` (`@start worker testsub2 t-1 on srv-a`);
  its instance is the `holder` of the slot (`$t1`). The hold rows `testsub2/holds/s9` (the instance `$t1`) and `s8` (a foreign
  instance `box:1:ffffff`) are written by the role of the worker `@as testsub2worker store` bypassing the worker; there are no rows `shelves/s9`, `s8`,
  they do not become candidates of the worker. Step 4 waits for the heartbeat of `t-1` in `/testsub2/servers`. `s9` is a hold in effect:
  200, `server` is the field of the heartbeat; `s8` — the instance is not the one, the hold is not in effect, there is no place row — 404 `s8@?`
  (P/06.5 Н3 `/where/<table>/<place>`; C06-WHERE-PLACE-SERVER-33-01).
- **Spoiling a heartbeat.** Sc. 08 spoils the heartbeat by the directive `@spoil object`: after it the heartbeat is unreadable (P/05 Н1.1). The worker is
  killed before that (`@sigkill`): its heartbeat remains an object and is no longer written.
- **A restart of a worker under the former name (sc. 20, 21; the coverage audit of P/06).** The series `failover_seconds{kind=last,worker}` and
  `failovers_unmeasured` (Н3 «/metrics — text») are computed from the heartbeat fields `started`, `previous_hb`, `previous_instance`
  (P/03.4 Н1.1: what the worker found under its name at the start, P/03.2 Н3 «start()» step 4). Sc. 20: `w-1` is stopped by
  `@sigterm`; a new instance is started only after the release of the slot (`released: "true"`, step 5) — the last heartbeat of the former one is
  written before the release (P/03.4 Н3 «stop by SIGTERM» steps 3–4), so `started` of the new one is not less than `previous_hb`, the failover is
  measured, `failovers_unmeasured 0` (the value of `failover_seconds` is a difference of times, the TSV does not fix it). Sc. 21: a found
  heartbeat — the input `hb-w-1-future.json` with `ts` 9999999999: `previous_hb` is greater than `started`, `last` is −1, an instance with
  `previous_instance` and an unmeasured `last` — `failovers_unmeasured 1`. Step 3 of sc. 21 waits until the objects door of the resource
  gives out the input: the worker reads the found heartbeat through it. The series `kind=worst` — by reading (P/06.5-06).
- **A write only by a ticket (sc. 33; ADR-0119 addendum (10), (11)).** `probe-w`: `unit.writes_via` and `tables.log.writes_via` are `[probe-x]` (P/06.1 Н1.1а). The stand session (loopback, all rights) gets `403 writes via` for `POST`, `PUT`, `DELETE` of a unit, for the table `log` and for a batch row — the whole batch, a table row without the word in it is not written either (steps 7, 8). `PUT` and `DELETE` of an absent row — `403`, not `404`: the word is judged right after the parsing of the key, before the read of the row and the rights (steps 3, 4). The table `free` without the word is open (step 10), reading does not change (steps 11, 12). A write by the ticket `probe-x` and `may` of the person of the ticket — the pass stand; until it — by reading (P/06.1-35). The field `reason` of the row `access.denied` — by reading: the stand does not read the audit journal.
- **A numeric id (sc. 22; the coverage audit of P/06).** `probe-x` (`id: numeric`): the first number is 1, the counter row `probe-x/next_id`
  `{n}` is the last issued one (read by the role `console`), a tombstone does not return the number (P/06.1 Н1.3 numeric); in the path `01` —
  400 `badkey`, `%32` — the unit 2 (P/06.1 Н2).
- **The counter of the batch door (sc. 29; ADR-0094 B9).** `probe-x` (`id: numeric`), the steps through the door `POST /console/batch` (P/06.1 Н2 «Batch door»): the number of the unit is named by the caller, the row `probe-x/next_id`
  with `cas` goes in the same batch, `n` is the largest number of the batch; `POST /probe-x/probes` after the batch takes the next number (steps 6, 15). The index of the counter — through the door `GET /probe-x/next_id` (steps 2, 4, 7), the index of the unit row — through the store door by the role `console`.
- **The counter door (sc. 30; ADR-0094 B4).** `GET /probe-x/next_id` (P/06.1 Н2 «Counter door»), the door only reads: step 1 — an empty subsystem, `n: 0`, `index: ""`; step 2 — a batch by this read; step 4 — `index` equals the index of the store; step 6 — `testsub` with a named id — 404; step 8 — the counter row is removed bypassing the console (`admin`), step 9 — `n` by recover, step 10 — `POST` takes `n + 1`; steps 12–14 — an unreadable row: `n` by recover, `index` is its version.
- **The weight field (sc. 23; the coverage audit of P/06).** `probe-x` has the field `cost: {type: int, default: 1}` and `placement.weight:
  {field: cost, default: 1}` (the form — «Дополнительные проверки прогона 25» of the acceptance README of chapter 6.1): POST without `cost` — 1;
  `cost` 0 and −1 for POST and PUT — 400 `error: type`, `field: /cost`, `detail` «cost must be at least 1» without `fault`; `"1"` and `true` — 400 `not_number` by the ordinary
  type check (earlier than the weight, the row check contract П2); a refused PUT — the row and `revision` are the earlier ones. The numbers burnt
  by refused POSTs the TSV does not compare.
- **Static files and the shell of `testsub2` (sc. 26–28; ADR-0094 B7).** The bytes lie in `inputs/testsub2/`: the files of the list
  `console.files` of the manifest and `testsub2.shell.html`. The stand puts them next to the manifest before `manifest-put` (common README, «Манифесты»).
  The files are acceptance data: the fonts are not real (magic and all byte values), `logo.svg` carries a script, `bundle.js` is 300045 bytes, two
  parts of `FILE_PART`, the second is shorter, a text with non-ASCII at the boundary is not aligned; `empty.css` is empty, it has no parts; `api.js` and
  `apis/app.css` are names that only begin with `api`, next to the prohibition of `api/`. The manifest `probe-x` does not carry the word `console.shell`: on
  it sc. 06 steps 4–5 and sc. 27 steps 13–14 see a mounted subsystem without a page.
  Sc. 26 steps with `store` read by the role `console` the field `files` and the part rows of `bundle.js` (the form — P/02.3 Н1.5; `<n>` from 0, there is no part 2);
  the JSON of the field is JCS, so the substring is stable. Sc. 27 step 4: the hash `sha256-Fv4QBmn4e5D3uUQvTmVKsZm0dTPMrjp+nycLTD2M1wc=` is the SHA-256 of the text
  of the inline script of the shell. Sc. 27 steps 9–10: the shell refers to a relative `app.js`, the CSP carries `'self'`, the file is given out.
  Sc. 28 by the role `admin` (the socket `admin.sock`) spoils the parts: `app.js` — not base64, `app.css` — base64 of other bytes (`x`), the part of
  `data.json` it deletes; `@restart console` — because the console is entitled to keep the checked bytes in memory (Н2). The restart does not refuse:
  a file without bytes is an outcome of the door, not of the start.
- **The holder's door in `/where` (sc. 24; the second pass of the coverage audit of P/06, Gemini).** The preparation is as in sc. 11 of the acceptance of
  [P/04](../../../../04-controller/acceptance/README.md): the controller `testsub2`, the worker `t-1`, the shelf `s-1` on `srv-a` (step 5 waits for
  the hold), the unit `ta` — the controller puts it on `t-1`. `testsub2` has `door: {routes: [read, play]}`: `/where/ta` gives
  the field `door` with the token `door1.…` (Н3 «`/where/<id>`»), the console at the first issue creates `door/signer` — `seed_secret`
  in an envelope of the stand ring, and writes its kid into `door/keys`. Step 10 rewrites `door/keys` by the role `console` (`$kid` → 64 `f`,
  cas by the read version): another value under its own kid — there is no `door`, the row is not rewritten (the version `$kw` is the earlier one), the alarm
  `door.keys_conflict {kid}` is in the journal (Н3, Н4). The check of the token by the holder — by reading (P/03.4-08).
- **The slot and the contenders in `WorkerRow` (sc. 25; the second pass of the coverage audit of P/06, Gemini).** The heartbeat of `w-1` is the input
  `hb-w-1-labels.json` (as in sc. 12); the slot row `testsub/slots/w-1` is written by the role `testsubworker` bypassing the worker: `released:
  "taking"` — `released: false`, `slot_taking: true`, `slot_garbled: false`; then `gen: "x"` (not by the form of P/03.2 Н1.4) —
  `slot_garbled: true`, `slot_until: null`, there are no `released` and `slot_taking` (Н2 «Выдачи»). The contender marks are objects
  `@put object`: under `w-1` with `name: "w-2"` (not equal to the key segment — unreadable, but fresh: a contender for `w-1`,
  `name_conflict_unreadable: true`) and the search mark `-` (not a contender); the series `testsub_name_conflicts` is 1 (Н3 «/servers»
  «Соперники»; the vectors `contender-projection` `name-mismatch`, `dash-not-contender`).
- **Series.** The expectation `~<ряд>[ <значение>]` on the body of `/metrics` of the console (with the door prefix and without) — a series with this name (and
  exactly this set of labels, if named) and the value, if named; several — through « ~» (sc. 05 step 6, sc. 10
  step 3); not a substring: `fake_counter_age` does not satisfy `~counter_age`, a repeat of a series or a line not by the series form —
  a mismatch. Series without values: the value is not fixed.
- **Feed series.** Sc. 31 runs on its own new instance of the console and the store: the counters `w2c_changes_*` count from the start, and the values 0 and 1 are correct only there.
- **Shortage.** Sc. 09: `testsub2` has `grows: true`, there are no workers — the unit `t1` waits, the pass report names the shortage.
  The answer of `/testsub2/metrics` is 200 with the series `testsub2_units_short`, not a break.

### Inputs `inputs/` (sc. 05, 11, 12, 21, 25)

Heartbeats of a given form are put by `@put object <ключ> inputs/<файл>` bypassing the writer (the exception `P/06 acceptance-entry
5/inputs`). There are no workers in these scenarios; the resource `srv-a` — the first step `@start resource`: the console reads the heartbeats through the objects door of the resource of its own server (C06-PULSE-LAPSE-503-03, the Architect's decision of 2026-10-29). The first look of the console at a heartbeat is fresh
([the observation contract](../../../../common/contracts/observation.md): `resource_state`, the first observation; `worker_state` —
[chapter 6.1](../../../spec/06.1-console.norms.md) Н2).

| File | Key | What is in it |
|---|---|---|
| `res-srv-p-stalled.json` | `platform/resources/srv-p/heartbeat` | a full heartbeat of the resource of P/05 Н1.4 with `pass_stalled: 12.5` (C12) |
| `res-srv-q-extra-field.json` | `platform/resources/srv-q/heartbeat` | the same heartbeat and the field `bogus` outside `ResourceRow` (C11) |
| `res-srv-r-wrong-server.json` | `platform/resources/srv-r/heartbeat` | `server: "srv-x"` ≠ the server of the key (C11) |
| `res-srv-s-no-url.json` | `platform/resources/srv-s/heartbeat` | there is no mandatory `url` (C11) |
| `hb-w-1-labels.json` | `testsub/heartbeats/w-1` | a heartbeat of the worker on `srv-a` with the node labels `a,b` (C16) |
| `hb-w-7-other-name.json` | `testsub/heartbeats/w-7` | `worker: "w-8"` ≠ the name of the key (C15) |
| `hb-W-9-bad-name.json` | `testsub/heartbeats/W-9` | the name of the key is not by the grammar of a slot name (C15) |
| `hb-w-3-no-server.json` | `testsub/heartbeats/w-3` | `server: ""` — the server is unknown (C14) |
| `hb-w-1-future.json` | `testsub/heartbeats/w-1` | a heartbeat of the worker `w-1` on `srv-a` of the instance `acc:9:0f0f0f` with `ts` 9999999999 — found by the new `w-1` (sc. 21) |
| `ct-w-1-b1-other-name.json` | `testsub/contenders/w-1/b1` | a contender mark (the form of P/03.2 Н1.4а) with `name: "w-2"` ≠ the key segment `w-1` — unreadable (sc. 25) |
| `ct-dash-b2.json` | `testsub/contenders/-/b2` | a search mark without a given name, `name: "-"`, `state: waiting` — not a contender for the name (sc. 25) |
| `hb-t-1-belt-slow.json` | `testsub2/heartbeats/t-1` | `jam: "stuck"` (a word from `heartbeat.strings`), `belt.state: "slow"` — a word not from `heartbeat.strings` (C20) |

Sc. 12 step 7: two unreadable heartbeats (`w-7`, `W-9`) — `testsub_heartbeats_garbled 2`. Step 8 writes the row
`platform/servers/srv-a` by the role `console` (P/02.5 Н1.4).

## Stand of sc. 03 and 17 (from М10/10)

The stand of sc. 13–16 with the controller `testsub` (`@start controller`) and the resource (`@start resource`); a catalogue of two manifests.
The steps before `/metrics` of the console are preparation: the controller writes the snapshot shard `testsub/snapshot/unplaced`, the resource gives it out
through the objects door (`@until 20`, `@time` — the dictionary of the «Stand»); their subject is the acceptance of [P/04](../../../../04-controller/acceptance/README.md)
(sc. 03, 08 with the same steps). The subject of the chapter: sc. 03 step 5 — the series `testsub_snapshot_age_seconds` (Н1.3 `age`); sc. 17 steps
7–9 — the controller is stopped, the shard is spoiled (`@spoil object`), `/metrics` 200 with `testsub_snapshot_garbled_shards 1` (Н1.3
`metrics`; Н0 P/01.1 «Stability of output»). The row `testsub/counters/s7` with `start: notint` sc. 17 writes bypassing the console by the role
of the console (`@as console store`).

## Stand of sc. 13–16 (from М10/11)

The stand of the acceptances of P/03 (formerly М10/5; analysis of the review of stage B 3–5, № 34) with the resource (`@start resource`, `@sigkill resource`, `@sigterm resource`). The build with schema
1. Load the unchanged testsub and testsub2 (without `probe-x`); root is testsub, the second is available under /testsub2; there is no domain,
requests come from the loopback. The background controller/resource/worker do not work before @start. Between scenarios the runner stops
the processes, resets the store and the variables.

- **Time in a row (sc. 13).** The rule of Н0 P/01.1 «Time in a row» (the Architect's decision of 2026-10-18), the reader side:
  the same course as sc. 16, but the door row is written with `at` with 6 fraction digits (`901.123456`, `906.654321`) — a write of a form
  that the reader accepts and the writer does not write; the outcome is the same.
- **Sc. 15 step 1** (the former step 9 of sc. 15 of М10/11; steps 1–8 — in [the acceptance of P/01.3](../../../../01-store/acceptance/3/README.md)):
  `door.pass` of `testsub2` (`pass: [entries]`) without a worker with a door — 503 `{"error": "denied"}` (Н1.8; reconciliation of python and go М10/6–11, B26; the word — GP-L03, the Architect's decision of 2026-10-28); the door
  `console2` is the same console with the prefix `/testsub2`.
- **Sc. 16** (reconciliation of python and go 2026-10-18): the heartbeat of the resource is spoiled (`@spoil object`), while the door row is fresh — the state
  `unreachable` (`resource_state` of [the observation contract](../../../../common/contracts/observation.md): the rules in order,
  an unreadable heartbeat does not confirm life). The resource is stopped before the spoiling so that it does not rewrite the heartbeat; the runner
  changes the door row itself by the role `resource`.
- **The deadline of 90 s** of sc. 14 is the waiting limit of exactly this stand; after `@sigkill` the heartbeat seen earlier is used.

### Sleeps (`@sleep`, ADR-0080 addendum (17) item 4)

| Sc./step | Sleep | Reason |
|---|---|---|
| 16/6, 13/6 | 5 s | time before an action: two writes of the door row by the role `resource` are spaced by the clock of the console — the row is fresh, while the heartbeat is spoiled (`unreachable`, `resource_state` of the observation contract) |

## Full form and reproducibility

A subset of expect does not replace the check of the full HTTP form of [the contract of the lesson](../../../spec/06-console.api.openapi.yaml): check the mandatory fields, types, Content-Type, special headers and the absence of a body for HEAD/204. In expectation lines `$имя` is first bound only after a successful match of the whole answer; the following uses compare, and requests use only values already bound. A failed attempt of @until does not change the variables. @until repeats a read until the given local deadline, not a mutation; after it expires — FAIL with the last answer. @any admits any value of a present field, @absent requires absence; they do not replace the types of the full schema. A JSON object is compared by subset (`{}` at any level is exactly an empty object: the dictionary of the common README, ACC-EMPTY-OBJECT-01), an array by length and order. Raw HTML/text is compared as UTF-8 bytes with the given substring, it is not parsed as JSON.

A successful open /session contains login_url (the session scenario — [the acceptance of chapter 6.3](../../3/README.md)).

## Additional check by reading

R36-08: a stable active intent directs u to w-2 with placement=w-1 or with its absence — /where uses w-2; target="" gives 404 with the reason intent. A foreign id/idle use placement. A change of the intent version requires repeating the read, a non-answer of any mandatory read — 503. The heartbeat is read after the effective decision; the absence of a door does not turn into null. Scenario 04 checks only the absence of a placement, active/interleavings are not executed in the current TSV.

Run 36 (Kimi): check both outcomes of the absence of v and the mounted /servers, /unplaceable, /where, /metrics and the page. For where(table,place): an unknown table 404 before unit; then the form/view, a confirmed hold and the heartbeat, a read error 503, the absence of a hold 404 with X-Unreachable. door is optional and appears only with a confirmed addressee/holder/signer; the issue is journaled. Sc.04/6 sees empty resources and does not check the fields of ResourceRow. (The loopback, trust, Origin and the emergency login — [the acceptance of chapter 6.3](../../3/README.md).)

R37 (Codex): check the root/mount catalogues: the name where is not loaded; two separate correct manifests with mount b and the family root b do not form an admissible catalogue. Repeat for unit.rows and a table (including a list table), both directions of the pair and root of each choice. For GET/HEAD of both mounted pages the sets of codes are the same, 200 is absent. The delegation list does not add GET of a single unit to the owner (chapter 6.1).

This is a subject of a manual check of the specification and of a future check of an implementation. The prepared requests, the reading and the finite models of the author are not a performed stand test.
