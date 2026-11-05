# V/11 Configurator backend — instructions for an implementation

This English text is the source; the Russian translation `ru/spec/11-backend.README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

What an implementation of the subsystem `backend` does and how to check the result. The canon is the norms of the chapters `11.K-backend.norms.md`; these
instructions do not add to them. The platform is the export `cammeta-specs` `7a875c75` (the VMS pin; an increment of rights on top of the norms B, ADR-0090 addendum (17); the mark «норма платформы B» — where the chapter relies on them).

## Inputs and their priority

- The canon: the norms of the chapters `11.K-backend.norms.md` (Н1–Н5 of each chapter; the addresses `V/11.K Н…`).
- The canon of the manifest: [`backend.subsystem.yaml`](../backend.subsystem.yaml): the bytes as they are; the blocks of the second kind of pass
  (B1) and of static files (B7) are comments until the platform norms.
- The canon of the shell: [`backend.shell.html`](../backend.shell.html): the bytes as they are; the implementation does not generate it.
- The door contract: [`consolem.openapi.json`](../consolem.openapi.json) (the pinned commit, SHA-256 next to it); it is not edited.
- The mapping of kinds: the data [`data/mapping.tsv`](../data/mapping.tsv).
- The assistant harness: the data [`harness/`](../harness/), the catalogue [`data/rule-catalog.json`](../data/rule-catalog.json): the bytes as they are.
- Acceptance: the consolem API tests at the pinned commit in the capability profile (chapter 6) and the own suite [`acceptance/`](../acceptance/).
- The lecture (`ru/11-backend.md`, for people, not in the export) explains the reasons; the platform — the norms of the export of the VMS pin at the addresses `P/…`.

Record a contradiction with its place and a counterexample (the section «On a divergence»); an arbitrary refusal does not replace an
absent norm. The structure of the code is left to the implementation within the canon.

## What to create — the result by chapter

| Chapter | What the implementation has | Check |
|---|---|---|
| V/11.1 | the manifest loads with the strict loader without edits; the holder of the row `backend/instances/<name>` by labels next to `live`, the callback — TLS with the role `backend`; the answers of the pass — only JSON or SSE; the implementation does not serve the WebUI (the console does — with the shell `backend.shell.html` and the static files of the subsystem, B7); the API — `/backend/api/` | by reading; API tests |
| V/11.2 | 116 contract operations are translated, 7 — `404 NO_ROUTE` without calls to the console (including `/test/events`), `/test/reset`, `/test/clock` — only the stand and the console loopback mark, otherwise `404 TEST_SUPPORT_OFF`; `GET /reference` carries `capabilities` — the «translated» list, the kinds — `GET /kinds`; a refusal — `Problem` of the contract | API tests in the profile |
| V/11.3 | translation by the table `mapping.tsv`: read from the data, not hard-coded | API tests; by reading |
| V/11.4 | device search and the question about the model through the doors of the `cam` tables; folders and group operations, a step by the route `opstep`; assembling and disassembling records by parts, the version — a concatenation of the store indexes of the parts and tombstones (B4), the device record in one B9 package, the repeat memory of group writes, a console refusal → a contract code, id — UUID v5 of the cluster and of the row's place | API tests (after B3–B5) |
| V/11.5 | a callback only with the ticket of its own request and only by the list; `/stream` from `/changes` by the message table | API tests; the platform acceptance B1, B2 |
| V/11.6 | the profile of the product tests, the key `TEST_SUPPORT` of the subsystem file and the console loopback mark for `/test/reset`, `/test/clock` | the stand after the platform increment |
| V/11.7 | the assistant turn in `backend`: the loop V/11.9 with the model by the route `assist/chat` with the ticket, the tools and the plan check V/11.10, V/11.11 with the ticket, the plan only in the fields `DevicePatch`, stream events, the turn limit | the vectors `plan-check`, `turn` by the driver of `backend`; `tests/api-assist.js` in the profile — one row, acceptance 4/`29-assist` |
| V/11.8 | the snapshot `Access` from the domain doors, the role rows by the level table and back, the domain snapshot by the viewer's grants, applying by a difference: the domain package, `lines` of the role, the cluster rows, the divergence, refusals of the untranslatable | the API tests `api-access.js` in the profile; by reading |
| V/11.9 | the loop: the step messages from `harness/`, `tool_choice: required`, the window, the poll, parsing the answer, outcomes, the turn through requests | the vectors [`turn`](../vectors/turn/README.md) |
| V/11.10 | nine tools `harness/tools.json` with the ticket, selection over full lists, `can_edit` | the vectors `plan-check`, `turn` |
| V/11.11 | the plan check — a pure function, the words `harness/words.json`, refusals by the chapter's words | the vectors [`plan-check`](../vectors/plan-check/README.md) |
| V/11.12 | changes to apply, the secret mark, the substitution into `password` of the plan | the vectors `plan-check`; by reading |
| V/11.13 | the rule harness `harness/rules/`, the neutral plan and one translator into the body, the catalogue `data/rule-catalog.json`, check layers by the row, `ask`, `escalate`, writing only by a human | the vectors [`rules-words`](../vectors/rules-words/README.md), [`rules-neutral`](../vectors/rules-neutral/README.md), no run yet |
| V/11.14 | the contract 0.2.0 as a whole: the core paths only, no stages and no legacy paths; a composite kind by the core path — the same B9 package as the camera assembly | API tests in the profile of the contract (Н5) |
| V/11.15 | the form is served under `/backend/`, the shell byte for byte; the tab «Просмотр» second in the camera card; the condition of removing the page and the remainder | by reading; the fork's tests |
| V/11.16 | the timeline: the `backend` side — the doors of recordings and places, merging, yielding, the unavailable named; the form — windows, pages, «Закрепить», events by `occurred`, the mark with `late` | by reading; the fork's tests, V/11 |
| V/11.17 | pieces of 60 s (each moment once, a refusal — a repeat after 5 s with a new address), live: `POST live`, an offer with H.265 and the window size, repeats on 404/500/503 every 1.5 s (the first offer and 20 repeats), hang-up, reconnection with spread, the feed as a stream, talk, pan-tilt, relays | by reading; the fork's tests, a stub WHEP |
| V/11.18 | the camera's recordings (the state as a word, editing by a field, the source `replica_from`, the choice of volume, the name of a new one), holds (placing with `recordingIds`, the words `states`, «Проверить»), volumes (the space, `volume_missing`, the declaration as a whole row, `when` of `edge`, `incidents` — `admits: false`, reduction with a confirmation) | by reading; jsdom tests |
| V/11.19 | scenarios (the form = the schema `then` with `params`, the refusals of the door and of two fields before the write, the words `reason`/`unfit`/`unchecked`, firings over a day), the domain (only the assignment `PUT {cluster, origin, copies}`; the recording row is created by the cluster), stream accounts (the password once) | by reading; jsdom tests |
| V/11.20 | export (the part rows of `exp` in one batch, the order of the checks, `checkExport` without a write, the requests per part, `retry_of`, the link only to the author, the days by the timeline, `settings.tz`) | by reading |

The subsystem package carries the executable `/usr/lib/backend/worker` and puts next to the manifest the seven files of the WebUI set —
the consolem build from the pinned commit (V/09.3); the console serves them as static files of the subsystem and verifies the SHA-256
of each when serving (B7); the shell `backend.shell.html` is the lesson canon: `index.html` of the same build.

## Order

First the platform with the norms B, then `backend`: the pass of the second kind (the ticket) is the condition for enabling
`backend`; the current `door.pass` with the human's `Authorization` is not admitted for it (V/11.1 Н1.3).

## Pitfalls

| Norm | Possible mistake | How to keep the behaviour |
|---|---|---|
| V/11.1 Н1.3 | storing or waiting for the human's `Authorization` | only the request's ticket; no login of its own |
| V/11.1 Н1.4 | serving the WebUI from `backend`, by a special path or with its own markup instead of `index.html` of the build; tightening the CSP of the shell; judging the query string `?v=` of the set files | the shell `backend.shell.html` with the CSP exactly the minimum of P/06.5 and the static files of the subsystem by the manifest list (B7) |
| V/11.1 Н1.5 | calling doors outside the list (`/where` of other subsystems, writes of `/session`, keys) | only the callback list of the manifest |
| V/11.2 Н1.1 | editing the contract to suit itself | the difference — only `NO_ROUTE` and the capability declaration |
| V/11.2 Н1.4 | judging the loopback by its own TCP peer (it is always the console) | the stand key `TEST_SUPPORT` and the console mark `X-W2C-Loopback`, otherwise `404 TEST_SUPPORT_OFF` |
| V/11.4 Н1.7 | losing hidden members on `PATCH /folders` | the hidden ones stand behind the nearest former visible one |
| V/11.4 Н1.8 | taking `targetId` from the key memory | `items[].body` of the operation door; the memory row dies earlier than the operation |
| V/11.8 Н1.3 | omitting a point row relative to `*`, not writing `none` | a row for each subsystem at each point; saving only relative to the ancestor folder |
| V/11.4 Н1.2 | giving new parts random keys; guarding the camera row instead of writing it | the constant keys `<cam>`, `<cam>-<том>`, `<cam>-<kind>[-<n>]`; the camera row is written by every package of its part |
| V/11.4 Н1.4 | storing the memory in `<sub>/idem/`; checking the version before the memory | an own table `backend/repeats`; «started» `cas ""` before the snapshot; the step result — in the step package |
| V/11.4 Н1.10 | storing `Rule` next to the scenario or expanding the targets in `backend` | one row `auto/scenarios`, `RULE_INVALID` at the write, the evaluator expands the scopes |
| V/11.4 Н1.11 | computing the schedule action in `backend` | the evaluator computes the moment: the heartbeat word `object_mode` |
| V/11.4 Н1.12 | checking a revert by the row version; reverting volumes and removals | a check by the values `after`, the words `refuse` |
| V/11.3 Н1.1 | hard-coding the mapping | read `data/mapping.tsv` |
| V/11.4 Н1.1 | counting the camera version as a sum of the part revisions or as a number | an opaque string: a concatenation of the part indexes `c…r…d…`, string equality (ADR-0094 addendum (4) item 1) |
| V/11.4 Н1.2 | writing the device parts one at a time or reverting them by hand | one B9 package: the written ones with `cas`, the others by guards; a refusal — nothing is written |
| V/11.5 Н1.3 | faking the stream by polling before the feed | without `/changes` there is no stream |
| V/11.17 Н1.2 | repeating the WHEP offer longer than the delivery `grace` | the first offer and up to 20 repeats while at least `ICE_WAIT` remains until the end of `grace` |
| V/11.17 Н1.1 | repeating a refusal of a video piece without a new `where` | one repeat after 5 s with a new `where` |
| V/11.16 Н1.2 | reading the unavailable from the headers of `/timeline` | the body fields `unreachable`, `unavailable` |

## Done when

The manifest loads with the strict loader without edits; the consolem API tests in the capability profile pass on a platform with the
norms B; the «`NO_ROUTE`» operations answer 404 without calls to the console; the checklist items marked «by reading»
are confirmed by the implementation description (the section «Решает реализация» of each chapter).

## On a divergence

The order of the sources: the norms of the chapter → the consolem contract and the mapping table → the product tests → the lecture; the platform — the norms
of the export of the VMS pin. If a norm is silent or contradicts itself — a question to «Спецификация VMS» with the place, a counterexample and a
proposal; the contract — a question to «Консоль», the fork is ours (ADR-0112); a platform norm — through «Архитектор».
