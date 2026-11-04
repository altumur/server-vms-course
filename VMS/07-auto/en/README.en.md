# V/07 Scenarios

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

Status: **translated** — chapters V/07.1–V/07.6 (the plan of 2026-10-23 is the history of the translation below; inquiries 5, 6 are resolved by ADR-0091 addendum (21);
the review of V/07 — 2026-10-29); the norms are by chapter below. Sources:
the inventory [`../common/inventory.md`](../../common/inventory.md) § 1, § 2 (М10B/25, except the mechanism; М10B/11 step 6; М10B/12 step 12 —
the meaning of the form; М12A/12; М12B/03 step 8; М12B/04 step 7). The platform: the export `cammeta-specs` `7a875c75`. The manifest is
[`auto.subsystem.yaml`](../auto.subsystem.yaml) (the canon; ADR-0090 addendum (6) item 8).

## What lesson V/07 is

The subsystem `auto`: a **scenario** is «when this happened (and that, within thirty seconds), do this». The unit is the
row `auto/scenarios/<id>`, `id` is a number; the evaluator is the worker `autoworker`, exactly one per scenario (epoch and lease). The evaluator is
a question to the event log, not an automaton: it reads the merged log of the cluster, decides a firing by the closing event and acts
through the owner subsystems — by a request to the camera holder (a relay, a preset) or by ordering a row for a time (a detector, a job over an
interval, a recording). Scenarios between cameras of different members live in the shared settings of the domain; they are executed by the evaluator of the
trigger's cluster, and the request goes to the receiver of the target camera with the token `ask`.

## Chapters

| Chapter | What it norms | Former steps | Platform |
|---|---|---|---|
| V/07.1 | The scenario — the unit and the language: the number key, the fields (`start`, `run_at`, `when` — up to 4 triggers `{sub, kind, unit?, target?, match?}`, `within`, `conditions`, `then` — up to 4 steps: actions and flow steps, branches up to two levels, `rate_per_minute`, `valid_for`, `enabled`, `labels`, `log_only`, the page's data), the target `target`, the step catalogue = the schema of `then`, `rights` (`cluster_rows`, `names`), placement, the snapshot, the form refusals at the door | М10B/25 steps 1–4, 8 (`rights`); М10B/12 step 12 (the meaning) | P/02.1; P/06.1 Н1.2 (the field schema); the contract gate-and-pass; P/04 Н1.3 |
| V/07.2 | The evaluator — a question to the log: what to watch (`wants`), the firing by the closing event and the window, `occurred` against `t`, `JOURNAL_SETTLE`, suppression summaries do not fire, what is fenced off is not evidence; the cursor `unit.state.cursor`, the full window, `COLD_START`, the long poll | М10B/25 steps 5, 6, 10; М10B/11 step 6 | P/05 Н1.3, Н1.6; P/06.4 Н1.3; P/03.6 Н1.7; P/03.3 |
| V/07.3 | Fit and refusals: the meaning of the scenario against what the cameras can do (`can`, `cam/devices`) and which detectors exist; `refused`, `unfit`, `unchecked`, an unreadable row is the trouble of one; the refusal texts | М10B/25 steps 3 (the meaning), 4a | V/01.4 Н1.4; V/04.1 |
| V/07.4 | Actions: the request to `cam` (`output`, `preset`; the deadline `occurred + valid_for`, the stamps); orders — a detector for a time (`worker.creates` to `det`, the base is the operator's detector, a second one is not set up), a scan (`worker.creates` to `detjob`, the window `before`/`after`, `alarms`, `mask_of`), a recording for a time (`worker.creates` to `rec`); the ceilings `rate_per_minute`, `PER_PASS`; the heartbeat, the series, the events `fired`, `suppressed` | М10B/25 steps 7, 8, 9; «Что может пойти не так» | P/03.6 Н1.5, Н1.6; P/04 Н1.3 (`ends`); V/01.4, V/02.1, V/04.1, V/05.1 |
| V/07.5 | Scenarios between cameras: the document `auto.scenarios` in the shared settings of the domain, the executor is the evaluator of the trigger's cluster, the token `ask`, the book `asks` (the publisher of the path node, the element), the request to the target's receiver (V/02.9 «просьба»), the outcomes, the receiver's limits, the relay and the ascent, the camera-cluster | М12A/12; М12B/03 step 8; М12B/04 step 7; ADR-0074 form C6 | P/06.7 Н1.14; P/08.7 Н3 (`scenario`); P/08.9 Н1.2–Н1.3; P/09.1 Н1.10; P/09.2; P/03.7 Н1.2, Н1.5 |

| V/07.6 | Schedules, modes, windows: the tables of `auto`, the moment function `in_effect`, `sun`, `object_mode`, the maintenance window, the zone `TIMEZONE`, clock changes, versions, the operator's answer | ADR-0105 items 2, 9; ADR-0106 item 7 | P/06.1 Н1.6; the environment file contract |

Neighbours: the camera holder — execution of the request and of the scenario request (V/01.4, V/01.6); the recorder — the receiver and the carrying of the request
(V/02.9), recording by order (V/02.1); the detector (V/04.1), the job (V/05.1) — rows by order; the page — the section «Сценарии» (V/11).

## Forms and doors

- **Rows and objects:** `auto/scenarios/<id>`, `auto/next_id`, the tables `auto/schedules/*`, `auto/day_groups/*`, `auto/modes/all`, `auto/mode_current/now`, `auto/windows/*`, `auto/versions/*`, `auto/answers/*`, `auto/rule_marks/*`, `auto/chains/*`, the cursor `auto/state/cursor/<scenario>`, the run row `auto/state/runs/<scenario>`, the requests `cam/requests/<rid>` (filing),
  the orders `det/units/auto-…`, `detjob/jobs/auto-…`, `rec/recordings/auto-…`, the contribution to the book `auto/asks/<слот>`, the copies
  `domain/shared`, `domain/auto/asks`; the events `auto/<scenario>/e<n>` (`fired`, `step`, `suppressed`), the alarms `auto.alarms/<scenario>/e<n>`.
- **Doors:** the rows and the tables — by the console door (P/06.1), the requests `run`, `retry` — `POST /auto/requests` (P/06.4), the shared settings — the domain
  door (P/08.9), the scenario request — the recorder's receiver (V/02.9); the holder's own door — the route `test` (V/07.4 Н2); the lesson has no OpenAPI.
- **Data families** (the class of VMS families, the analysis of the review of V/01 question 5, decision «А» of «Архитектор»): the scenario rows, the cursor
  and the run row (`unit.state`), the tables, the document `domain/shared` (`domain.shared.scenarios` with a schema) and the contribution `auto/asks/<слот>` are expressed by the manifest
  (P/02.1, P/03.7) — they have no families of their own. The lesson's own content in the open place of a platform family is [`data/`](../data/):
  `value` of the element of the book of roads `asks-entry` (the place `/*/entries/*/value` of the book `domain/auto/asks` and `domain/auto/asks/<член>`)
  — the form, the layers, the outcomes per reader; the rows are in the VMS catalogue [`../common/data/catalog.tsv`](../../common/data/catalog.tsv).
  The vectors are built by the builder `family-read` (`../common/vectors/family-read/07.tsv`). The heartbeat of `auto` is judged by no foreign process —
  it is read by the console and the page, there is no family.

## Decisions for the plan (made by «Архитектор» 2026-10-23)

1. **Recording for a time — by an order:** `worker.creates: [{sub: rec, rows: recordings, key: "{cam}"}]` → `rec/recordings/auto-<cam>`,
   `until` = the event + `minutes`, `home` ← `archive`. The obstacle: at `rec` the field `ref` is `fixed` but not `required` — the catalogue check
   (the key names every `fixed` field, substitution — only the required ones, P/02.1 Н3) would refuse. The subsystem's decision: remove `fixed` from
   `rec.ref` (V/02.1, V/02.9 Н1.1) — the match of `ref` with the camera is checked by the recorder (`waiting` «ref differs from
   cam»); no inquiry is needed.
2. **The mask of the ordered detector is `mask_of` at `det`** (as at `detjob`): the order refers to the row of the operator's detector of the same
   camera, otherwise the scenario's detector would watch the whole frame (P/03.6 Н1.6: the blob of an order is empty); the model takes the mask of this row at
   start (V/04.1 Н1.1 «Какая маска»). The former reference to the body `mask_from` was removed by the review of V/04: a reference to a body does not hold the body
   (P/06.1 Н3).
3. **A scan — by an order to `detjob`:** the key `"{cam}-{rec}-{kind}-{from}-{to}"` (as at the recorder, V/02.8 Н1.5; the spelling of the numbers —
   `values_by_type`), the window `[floor(occurred − before), ceil(occurred + after))`, the defaults 60/60 s; one job per window — an equal
   window is `unchanged` (also from another scenario: the fields of the first order), a different one is a different job; `rec` not given — the recording with id = `cam`, otherwise the first recording of the camera by name; no recording — a refusal of the evaluator;
   the fields of the operator's detector of the same pair — `params` (with the claims on top), `labels`, `alarms`, `mask_of`.
4. **A second detector is not set up:** an enabled operator's detector of the same pair (`cam`, `kind`) without `made` with `until` = 0 —
   there is no order (`watched` in the heartbeat); `det/units/` is needed in `worker.reads`.
5. **Reading the log — the contract `events-merge`** (ADR-0091 addendum (21) item 1, addenda (23)–(27)): the evaluator is a participant of the merge,
   the questions are on the triple and the class, the reading window is up to `now`, the cursor up to `now − JOURNAL_SETTLE`, the backward query `JOURNAL_BACK`, `keep: oldest`,
   the partners — `by=occurred&late`, completeness — `complete` and `truncated` = 0 (V/07.2 Н1.2).
6. **The name of a filed request — by the filer's key** (ADR-0091 addendum (21) item 2): `auto.<f>-<i>`, `f` is the first 32 hex of
   `sha256(UTF-8(<сценарий> + "\n" + <id события>))`, `i` is the step path and, for a step with a target, the device (V/07.4 Н1.1); a request between cameras carries
   `firing` = `f`, at the holder — `rec.ask-<firing>-<i>` (V/07.5 Н1.4, V/02.9).
7. **One name on both sides:** in the domain document `then.within` (the request's deadline) → `valid_for`, as in a cluster scenario;
   `action` — `enum: [preset, output]`, `arg` → `n` / `port`, the deadline ≤ 600 s, `rate_per_minute` ≤ 600 — the form at the domain door
   catches what a form can catch; the meaning (what the target can do) is a refusal of the target.
8. **`worker.reads`** + `cam/cameras/`, `cam/heartbeats/` (the cameras' `can`), `cam/devices/`, `cam/children/`, `cam/child_settings/`, `det/units/`, `rec/recordings/`,
   `rec/heartbeats/` (the receivers' addresses for the book `asks`), `domain/cam/sources`, `domain/topology`.
9. **The heartbeat and the series:** the scenario phases `running` | `pending` | `refused` | `failed` (under the taken epoch), `why` — of the platform, the words — `reason`,
   the fields `unfit`, `unchecked`, `holding`, `decided_without`, `late`; the series `creates_total{outcome}`, `made_rows`; the series
   `wants_folded` is removed (there is no folding).
10. **Carrying a request by a relay** — the protocol is in V/07.5, the forwarder's side — by a line in V/02.9 Н1.8 with a reference.

## Inquiries of the lesson

Two — above (5, 6); the registry line `V/07 no-openapi` — by an inquiry with chapter V/07.1.

## Differences from the witness that the lesson records

The job executor and `requests.elsewhere` are removed: the detector, the scan and the recording are an order of a row (`worker.creates`), the relay and the preset are
filing by the worker; the cursor is `unit.state.cursor` (not a file); the branch `domainpart` and the publisher of the books of the VMS worker at the holder
are removed — the book `asks` is published by the evaluator of the path node (ADR-0074 C6); the names of the orders are `auto-…`; the folding of `wants` is removed; reading
the log is the merged log (an inquiry).

## Manifest edits during the translation

`auto`: `worker.creates` + `rec`, `detjob`; `worker.reads` (decision 8); `unit.state.cursor`; the document `scenarios` (decision 7);
the series (decision 9); the comments — without «пишет только просьбы» and the witness code. `det` — the field `mask_of` (was `mask_from`); `rec` — `ref` without `fixed`;
V/02.9 Н1.8 — carrying the request. The product — by a debt row to «Сборка».

## Order of work

Chapter by chapter, a commit per chapter: V/07.1 → V/07.2 → V/07.3 → V/07.4 → V/07.5. The lecture `07-auto.md` and the instructions
`spec/07-auto.README.md` — with the first chapter. Acceptance: 1 (the rows, the schemas `when`/`then`, the form refusals) — the console; the firing — a
stand with the holder of a file camera and the detector `tick` (an event → `fired` → an order of a detector) — after the answer to the inquiry about the
log; the run — after the first stage C generation that has passed the platform acceptance. `lessons.tsv` — `переведён` after the
last chapter.
