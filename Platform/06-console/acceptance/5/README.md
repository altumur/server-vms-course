# Acceptance P/06.5 — observations of the console

This English text is the source; the Russian translation `ru/acceptance/5/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors).
The norm of the chapter is [`06.5-console.norms.md`](../../spec/06.5-console.norms.md) N5. The console reads the heartbeats of the workers through the objects door of the resource of its own server, without the resource «unknown» ([the object store client contract](../../../common/contracts/object-client.md) `door`; P03-OBJECTS-DEFAULT-1FD; the Architect's decision of 2026-10-27). In total 33 scenarios / 327 steps.

Doors: without a prefix — the console, `console` and `console2`, `resource`,
`store` with `@as`; the directives `@start`, `@sigkill`, `@sigterm`, `@spoil object`, `@put object`, `@sleep`, `@until`; the expectations
`~text`, `!contains`, `@header`, `@file`, `@any`, `@absent`, `@not`.

## Stand (from M10/09)

Before each automatic scenario stop the processes of the previous one, create separate empty row/object stores and clear the variables/replay memory. Load the unchanged testsub and testsub2 and the third manifest of this directory `probe-x.subsystem.yaml` (a name with «-»: `metrics.prefix` is `probe_x`, mutation check 7cecaf2 № 40) and the fourth `probe-w.subsystem.yaml` (the word `writes_via`); root is testsub, the second is available under /testsub2, the third under /probe-x, the fourth under /probe-w; there is no domain, requests come from the loopback. The background controller/resource/worker do not work before @start. The build is schema 1; the store is fresh and empty — there is no row platform/schema, the runner does not write it (reading of the commits «cammeta-acceptance» 2026-10-20). For each POST that creates a unit the runner issues a fresh Idempotency-Key, kept only for the replays of the same step. A table POST does not get a promise of replay memory from this.

Without workers there is no placement. The domain login, closed grants, CSP and a repeat of a logical action are checked by a separate stand/module test, not by this TSV.

The published page/module bytes are compared with the P/07 canon: [console.html](../../../07-console-module/module/console.html), [console.js](../../../07-console-module/module/console.js) and [console.css](../../../07-console-module/module/console.css). Publication remains synchronous at the existing paths with `?v=1`; the existing refusal of `?v=2` stays unchanged. These file comparisons prove byte publication, not UI-language or date-format behaviour, which is checked independently by the module owner.

- **Processes.** Selected scenarios bring up processes by the directives of the «Stand» (`@start worker`, `@start resource`,
  `@start controller testsub2`); before `@start` there are no background processes. The worker is `w-1` of the subsystem `testsub` on `srv-a`.
- **The store door.** `@as testsubcontroller store` is the role socket of the controller `testsub` by the installation rights file (P/02.5).
- **Static files and the shell of `testsub2` (ADR-0094 B7).** The bytes lie in `inputs/testsub2/`: the files of the list
  `console.files` of the manifest and `testsub2.shell.html`. The stand puts them next to the manifest before `manifest-put` (common README, «Manifests»).
- **Series.** The expectation `~<series>[ <value>]` on the body of `/metrics` of the console (with the door prefix and without) — a series with this name (and
  exactly this set of labels, if named) and the value, if named; several — through « ~»;
  not a substring: `fake_counter_age` does not satisfy `~counter_age`, a repeat of a series or a line not by the series form —
  a mismatch. Series without values: the value is not fixed.

### Inputs `inputs/`

Heartbeats of a given form are put by `@put object <key> inputs/<file>` bypassing the writer (the exception `P/06 acceptance-entry
5/inputs`). There are no workers in these scenarios; the resource `srv-a` — the first step `@start resource`: the console reads the heartbeats through the objects door of the resource of its own server (C06-PULSE-LAPSE-503-03, the Architect's decision of 2026-10-29). The first look of the console at a heartbeat is fresh
([the observation contract](../../../common/contracts/observation.md): `resource_state`, the first observation; `worker_state` —
[chapter 6.1](../../spec/06.1-console.norms.md) N2).

## Stand (from M10/11)

The stand of the acceptances of P/03 (formerly M10/5; analysis of the review of stage B 3–5, № 34) with the resource (`@start resource`, `@sigkill resource`, `@sigterm resource`). The build with schema
1. Load the unchanged testsub and testsub2 (without `probe-x`); root is testsub, the second is available under /testsub2; there is no domain,
requests come from the loopback. The background controller/resource/worker do not work before @start. Between scenarios the runner stops
the processes, resets the store and the variables.

## Full form and reproducibility

A subset of expect does not replace the check of the full HTTP form of [the contract of the lesson](../../spec/06-console.api.openapi.yaml): check the mandatory fields, types, Content-Type, special headers and the absence of a body for HEAD/204. In expectation lines `$name` is first bound only after a successful match of the whole answer; the following uses compare, and requests use only values already bound. A failed attempt of @until does not change the variables. @until repeats a read until the given local deadline, not a mutation; after it expires — FAIL with the last answer. @any admits any value of a present field, @absent requires absence; they do not replace the types of the full schema. A JSON object is compared by subset (`{}` at any level is exactly an empty object: the dictionary of the common README, ACC-EMPTY-OBJECT-01), an array by length and order. Raw HTML/text is compared as UTF-8 bytes with the given substring, it is not parsed as JSON.

A successful open /session contains login_url (the session scenario — [the acceptance of chapter 6.3](../3/README.md)).

## Additional check by reading

R36-08: a stable active intent directs u to w-2 with placement=w-1 or with its absence — /where uses w-2; target="" gives 404 with the reason intent. A foreign id/idle use placement. A change of the intent version requires repeating the read, a non-answer of any mandatory read — 503. The heartbeat is read after the effective decision; the absence of a door does not turn into null.

Run 36 (Kimi): check both outcomes of the absence of v and the mounted /servers, /unplaceable, /where, /metrics and the page. For where(table,place): an unknown table 404 before unit; then the form/view, a confirmed hold and the heartbeat, a read error 503, the absence of a hold 404 with X-Unreachable. door is optional and appears only with a confirmed addressee/holder/signer; the issue is journaled. (The loopback, trust, Origin and the emergency login — [the acceptance of chapter 6.3](../3/README.md).)

R37 (Codex): check the root/mount catalogues: the name where is not loaded; two separate correct manifests with mount b and the family root b do not form an admissible catalogue. Repeat for unit.rows and a table (including a list table), both directions of the pair and root of each choice. For GET/HEAD of both mounted pages the sets of codes are the same, 200 is absent. The delegation list does not add GET of a single unit to the owner (chapter 6.1).

This is a subject of a manual check of the specification and of a future check of an implementation. The prepared requests, the reading and the finite models of the author are not a performed stand test.

## Accepted ADR-0127 review: source catalogue until restart

For `GET /manifest/<sub>/source`, admit a changed stored manifest after console startup. Before restart the source door retains the launch catalogue's rev, served, sha256, manifest and secret_defaults; a newly installed subsystem absent from that catalogue stays404. A differing current store-row rev does not create an own503 or a per-request store read. Restart, then compare the new launch catalogue and served value. Keep independent ordinary busy/trust failures; they are not a revision-mismatch response. Inspect actual store calls if proving the no-read obligation. The frozen platform module and thirteen raw asset witnesses are unchanged.


ADR-0129(17): inspect ordinary GET /metrics for all five w2c_changes_resets_total reason series at zero: foreign, evicted, rights, labels, folders. A real folder-composition change or folder deletion already produces reset5; observe that reset and the folders counter on the same ordinary HTTP path. Manifest metrics[] vectors do not accept this global-counter state and are not relabelled as this check. HEAD controls at the six prescribed existing paths compare GET admission/status/headers and an empty body; execution needs the actual ordinary setup, not a canned response.
