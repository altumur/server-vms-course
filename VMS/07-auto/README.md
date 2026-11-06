# V/07 Scenarios

This English text is the source; the Russian translation `ru/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

Status: translated. The platform export pin is `cammeta-specs` `7a875c75`.

## What lesson V/07 is

The subsystem `auto`: a **scenario** is «when this happened (and that, within thirty seconds), do this». The unit is the
row `auto/scenarios/<id>`, `id` is a number; the evaluator is the worker `autoworker`, exactly one per scenario (epoch and lease). The evaluator is
a question to the event log, not an automaton: it reads the merged log of the cluster, decides a firing by the closing event and acts
through the owner subsystems — by a request to the camera holder (a relay, a preset) or by ordering a row for a time (a detector, a job over an
interval, a recording). Scenarios between cameras of different members live in the shared settings of the domain; they are executed by the evaluator of the
trigger's cluster, and the request goes to the receiver of the target camera with the token `ask`.

## Chapters

| Chapter | What it norms | Platform |
|---|---|---|
| V/07.1 | The scenario — the unit and the language: the number key, the fields (`start`, `run_at`, `when` — up to 4 triggers `{sub, kind, unit?, target?, match?}`, `within`, `conditions`, `then` — up to 4 steps: actions and flow steps, branches up to two levels, `rate_per_minute`, `valid_for`, `enabled`, `labels`, `log_only`, the page's data), the target `target`, the step catalogue = the schema of `then`, `rights` (`cluster_rows`, `names`), placement, the snapshot, the form refusals at the door | P/02.1; P/06.1 N1.2 (the field schema); the contract gate-and-pass; P/04 N1.3 |
| V/07.2 | The evaluator — a question to the log: what to watch (`wants`), the firing by the closing event and the window, `occurred` against `t`, `JOURNAL_SETTLE`, suppression summaries do not fire, what is fenced off is not evidence; the cursor `unit.state.cursor`, the full window, `COLD_START`, the long poll | P/05 N1.3, N1.6; P/06.4 N1.3; P/03.6 N1.7; P/03.3 |
| V/07.3 | Fit and refusals: the meaning of the scenario against what the cameras can do (`can`, `cam/devices`) and which detectors exist; `refused`, `unfit`, `unchecked`, an unreadable row is the trouble of one; the refusal texts | V/01.4 N1.4; V/04.1 |
| V/07.4 | Actions: the request to `cam` (`output`, `preset`; the deadline `occurred + valid_for`, the stamps); orders — a detector for a time (`worker.creates` to `det`, the base is the operator's detector, a second one is not set up), a scan (`worker.creates` to `detjob`, the window `before`/`after`, `alarms`, `mask_of`), a recording for a time (`worker.creates` to `rec`); the ceilings `rate_per_minute`, `PER_PASS`; the heartbeat, the series, the events `fired`, `suppressed` | P/03.6 N1.5, N1.6; P/04 N1.3 (`ends`); V/01.4, V/02.1, V/04.1, V/05.1 |
| V/07.5 | Scenarios between cameras: the document `auto.scenarios` in the shared settings of the domain, the executor is the evaluator of the trigger's cluster, the token `ask`, the book `asks` (the publisher of the path node, the element), the request to the target's receiver (V/02.9 «request»), the outcomes, the receiver's limits, the relay and the ascent, the camera-cluster | P/06.7 N1.14; P/08.7 N3 (`scenario`); P/08.9 N1.2–N1.3; P/09.1 N1.10; P/09.2; P/03.7 N1.2, N1.5 |

| V/07.6 | Schedules, modes, windows: the tables of `auto`, the moment function `in_effect`, `sun`, `object_mode`, the maintenance window, the zone `TIMEZONE`, clock changes, versions, the operator's answer | ADR-0105 items 2, 9; ADR-0106 item 7 | P/06.1 N1.6; the environment file contract |

Neighbours: the camera holder — execution of the request and of the scenario request (V/01.4, V/01.6); the recorder — the receiver and the carrying of the request
(V/02.9), recording by order (V/02.1); the detector (V/04.1), the job (V/05.1) — rows by order; the page — the section Scenarios (V/11).

## Forms and doors

- **Rows and objects:** `auto/scenarios/<id>`, `auto/next_id`, the tables `auto/schedules/*`, `auto/day_groups/*`, `auto/modes/all`, `auto/mode_current/now`, `auto/windows/*`, `auto/versions/*`, `auto/answers/*`, `auto/rule_marks/*`, `auto/chains/*`, the cursor `auto/state/cursor/<scenario>`, the run row `auto/state/runs/<scenario>`, the requests `cam/requests/<rid>` (filing),
  the orders `det/units/auto-…`, `detjob/jobs/auto-…`, `rec/recordings/auto-…`, the contribution to the book `auto/asks/<slot>`, the copies
  `domain/shared`, `domain/auto/asks`; the events `auto/<scenario>/e<n>` (`fired`, `step`, `suppressed`), the alarms `auto.alarms/<scenario>/e<n>`.
- **Doors:** the rows and the tables — by the console door (P/06.1), the requests `run`, `retry` — `POST /auto/requests` (P/06.4), the shared settings — the domain
  door (P/08.9), the scenario request — the recorder's receiver (V/02.9); the holder's own door — the route `test` (V/07.4 N2); the lesson has no OpenAPI.
- **Data families** (the class of VMS families, the analysis of the review of V/01 question 5, decision «A» of Architect): the scenario rows, the cursor
  and the run row (`unit.state`), the tables, the document `domain/shared` (`domain.shared.scenarios` with a schema) and the contribution `auto/asks/<slot>` are expressed by the manifest
  (P/02.1, P/03.7) — they have no families of their own. The lesson's own content in the open place of a platform family is [`data/`](data/):
  `value` of the element of the book of roads `asks-entry` (the place `/*/entries/*/value` of the book `domain/auto/asks` and `domain/auto/asks/<member>`)
  — the form, the layers, the outcomes per reader; the rows are in the VMS catalogue [`../common/data/catalog.tsv`](../common/data/catalog.tsv).
  The vectors are built by the builder `family-read` (`../common/vectors/family-read/07.tsv`). The heartbeat of `auto` is judged by no foreign process —
  it is read by the console and the page, there is no family.
