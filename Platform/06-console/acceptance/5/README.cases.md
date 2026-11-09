# Judge-only case data

This English text is the source; the Russian translation `ru/acceptance/5/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing named case associations as judge-only provenance.

The norm of the chapter is [`06.5-console.norms.md`](../../spec/06.5-console.norms.md) N5. The scenarios were moved from the acceptance of
M10/09 (01, 02, 04–12; 03 — the session — into
[the acceptance of chapter 6.3](../3/README.md)) and of M10/11
(02 → 14, 09 → 16, 13, 15 step 1), and from M10/10 —
03 and 08 → 17 whole (the step `/metrics` of the console; analysis of the review of stage A 6–7, № 32) (stage B, ADR-0083 addendum (1): without a change of behaviour); the numbers, the names of the scenarios and the steps are
the former ones (sc. 08 and 19 — the first step `@start resource`: the console reads the heartbeats of the workers through the objects door of the resource of its own server, without the resource «unknown», [the object store client contract](../../../common/contracts/object-client.md) `door`; P03-OBJECTS-DEFAULT-1FD; the Architect's decision of 2026-10-27), except `14-resource-silent` (in M10/11 — `02-resource-silent`) and `16-resource-unreadable-heartbeat` (in M10/11 —
`09-resource-unreadable-heartbeat`) and `17-snapshot-garbled` (in M10/10 — `08-snapshot-garbled`): the numbers 02, 08 and 09 are taken
by the scenarios of M10/09. In total 33 scenarios / 327 steps: 13 — sc. 33 (a write only by the ticket writes_via, ADR-0119 addendum (10)), 13 — sc. 32 (a pass of the second kind without a worker, ADR-0094 B1), 9 — sc. 31 (the feed series, ADR-0094 B2), 14 — sc. 30 (the counter door, ADR-0094 B4), 15 — sc. 29 (the counter of the batch door, ADR-0094 B9), 72 — sc. 26–28 (static files and the shell of a mounted subsystem, ADR-0094 B7), 23 — sc. 24–25 (the second pass of the coverage audit of P/06, Gemini), 30 — sc. 20–23 (the coverage audit of P/06), 8 — sc. 19 `19-place-held-no-row` (C06-WHERE-PLACE-SERVER-33-01), 5 — sc. 18 `18-id-default` (`{id}` in the default, VMS request № 1), 85 in the scenarios of M10/09 (the steps 04/8 and 12/12–13 were added — analysis of the review of stage B 6–7, № 19,
№ 20), 23 from M10/11, 14 from M10/10.

Doors: without a prefix — the console (scenarios 01–12, as in M10/09), `console` and `console2` (scenarios 13–16, as in M10/11; 03 and 17, as in M10/10), `resource` (03, 17),

## Stand of sc. 01, 02, 04–12 (from M10/09), 18–33

Before each automatic scenario stop the processes of the previous one, create separate empty row/object stores and clear the variables/replay memory. Load the unchanged testsub and testsub2 and the third manifest of this directory `probe-x.subsystem.yaml` (a name with «-»: `metrics.prefix` is `probe_x`, mutation check 7cecaf2 № 40) and the fourth `probe-w.subsystem.yaml` (the word `writes_via`, sc. 33); root is testsub, the second is available under /testsub2, the third under /probe-x, the fourth under /probe-w; there is no domain, requests come from the loopback. The background controller/resource/worker do not work before @start. The build is schema 1; the store is fresh and empty — there is no row platform/schema, the runner does not write it (reading of the commits «cammeta-acceptance» 2026-10-20). For each POST that creates a unit the runner issues a fresh Idempotency-Key, kept only for the replays of the same step. A table POST does not get a promise of replay memory from this.

Without workers there is no placement; the counter c4 is created only in 04. The domain login, closed grants, CSP and a repeat of a logical action are checked by a separate stand/module test, not by this TSV.

Scenario 01 compares the published page/module bytes with the P/07 canon: [console.html](../../../07-console-module/module/console.html), [console.js](../../../07-console-module/module/console.js) and [console.css](../../../07-console-module/module/console.css). Publication remains synchronous at the existing paths with `?v=1`; the existing refusal of `?v=2` stays unchanged. These file comparisons prove byte publication, not UI-language or date-format behaviour, which is checked independently by the module owner. The subsystem static-file inputs of scenarios 26–28 remain separate and unchanged.

- **Processes.** Sc. 08–10 bring up processes by the directives of the «Stand» (`@start worker`, `@start resource`,
  `@start controller testsub2`); before `@start` there are no background processes. The worker is `w-1` of the subsystem `testsub` on `srv-a`.

- **The store door.** Sc. 07 writes an intent row bypassing the controller: `@as testsubcontroller store` — the role socket of the
  controller `testsub` by the installation rights file (P/02.5). There is no controller `testsub` in sc. 07, nobody will
  rewrite the row.

- **Spoiling a heartbeat.** Sc. 08 spoils the heartbeat by the directive `@spoil object`: after it the heartbeat is unreadable (P/05 N1.1). The worker is
  killed before that (`@sigkill`): its heartbeat remains an object and is no longer written.

- **Static files and the shell of `testsub2` (sc. 26–28; ADR-0094 B7).** The bytes lie in `inputs/testsub2/`: the files of the list
  `console.files` of the manifest and `testsub2.shell.html`. The stand puts them next to the manifest before `manifest-put` (common README, «Manifests»).
  The files are acceptance data: the fonts are not real (magic and all byte values), `logo.svg` carries a script, `bundle.js` is 300045 bytes, two
  parts of `FILE_PART` (262144 and 37901 bytes), the second is shorter. Its filler is ASCII; this fixture checks byte-part framing, not a split within a multibyte character; `empty.css` is empty, it has no parts; `api.js` and
  `apis/app.css` are names that only begin with `api`, next to the prohibition of `api/`. The manifest `probe-x` does not carry the word `console.shell`: on
  it sc. 06 steps 4–5 and sc. 27 steps 13–14 see a mounted subsystem without a page.
  Sc. 26 steps with `store` read by the role `console` the field `files` and the part rows of `bundle.js` (the form — P/02.3 N1.5; `<n>` from 0, there is no part 2);
  the JSON of the field is JCS, so the substring is stable. Sc. 27 step 4: the hash `sha256-Fv4QBmn4e5D3uUQvTmVKsZm0dTPMrjp+nycLTD2M1wc=` is the SHA-256 of the text
  of the inline script of the shell. Sc. 27 steps 9–10: the shell refers to a relative `app.js`, the CSP carries `'self'`, the file is given out.
  Sc. 28 by the role `admin` (the socket `admin.sock`) spoils the parts: `app.js` — not base64, `app.css` — base64 of other bytes (`x`), the part of
  `data.json` it deletes; `@restart console` — because the console is entitled to keep the checked bytes in memory (N2). The restart does not refuse:
  a file without bytes is an outcome of the door, not of the start.

  exactly this set of labels, if named) and the value, if named; several — through « ~» (sc. 05 step 6, sc. 10
  step 3); not a substring: `fake_counter_age` does not satisfy `~counter_age`, a repeat of a series or a line not by the series form —

- **Feed series.** Sc. 31 runs on its own new instance of the console and the store: the counters `w2c_changes_*` count from the start, and the values 0 and 1 are correct only there.

### Inputs `inputs/` (sc. 05, 11, 12, 21, 25)

| File | Key | What is in it |
|---|---|---|
| `res-srv-p-stalled.json` | `platform/resources/srv-p/heartbeat` | a full heartbeat of the resource of P/05 N1.4 with `pass_stalled: 12.5` (C12); only a neutral valid loopback `door` is added for current P/05-R026 |
| `res-srv-q-extra-field.json` | `platform/resources/srv-q/heartbeat` | the same heartbeat and the field `bogus` outside `ResourceRow` (C11); only a neutral valid loopback `door` is added for current P/05-R026 |
| `res-srv-r-wrong-server.json` | `platform/resources/srv-r/heartbeat` | `server: "srv-x"` ≠ the server of the key (C11); only a neutral valid loopback `door` is added for current P/05-R026 |
| `res-srv-s-no-url.json` | `platform/resources/srv-s/heartbeat` | there is no mandatory `url` (C11); only a neutral valid loopback `door` is added for current P/05-R026 |
| `hb-w-1-labels.json` | `testsub/heartbeats/w-1` | a heartbeat of the worker on `srv-a` with the node labels `a,b` (C16) |
| `hb-w-7-other-name.json` | `testsub/heartbeats/w-7` | `worker: "w-8"` ≠ the name of the key (C15) |
| `hb-W-9-bad-name.json` | `testsub/heartbeats/W-9` | the name of the key is not by the grammar of a slot name (C15) |
| `hb-w-3-no-server.json` | `testsub/heartbeats/w-3` | `server: ""` — the server is unknown (C14) |
| `hb-w-1-future.json` | `testsub/heartbeats/w-1` | a heartbeat of the worker `w-1` on `srv-a` of the instance `acc:9:0f0f0f` with `ts` 9999999999 — found by the new `w-1` (sc. 21) |
| `ct-w-1-b1-other-name.json` | `testsub/contenders/w-1/b1` | a contender mark (the form of P/03.2 N1.4a) with `name: "w-2"` ≠ the key segment `w-1` — unreadable (sc. 25) |
| `ct-dash-b2.json` | `testsub/contenders/-/b2` | a search mark without a given name, `name: "-"`, `state: waiting` — not a contender for the name (sc. 25) |
| `hb-t-1-belt-slow.json` | `testsub2/heartbeats/t-1` | `jam: "stuck"` (a word from `heartbeat.strings`), `belt.state: "slow"` — a word not from `heartbeat.strings` (C20) |

## Stand of sc. 03 and 17 (from M10/10)

The stand of sc. 13–16 with the controller `testsub` (`@start controller`) and the resource (`@start resource`); a catalogue of two manifests.
The steps before `/metrics` of the console are preparation: the controller writes the snapshot shard `testsub/snapshot/unplaced`, the resource gives it out
through the objects door (`@until 20`, `@time` — the dictionary of the «Stand»); their subject is the acceptance of [P/04](../../../04-controller/acceptance/README.md)
(sc. 03, 08 with the same steps). The row `testsub/counters/s7` with `start: notint` sc. 17 writes bypassing the console by the role
of the console (`@as console store`).


## Stand of sc. 13–16 (from M10/11)

- **Time in a row (sc. 13).** The rule of N0 P/01.1 «Time in a row» (the Architect's decision of 2026-10-18), the reader side:
  the same course as sc. 16, but the door row is written with `at` with 6 fraction digits (`901.123456`, `906.654321`) — a write of a form
  that the reader accepts and the writer does not write; the outcome is the same.


R36-08: a stable active intent directs u to w-2 with placement=w-1 or with its absence — /where uses w-2; target="" gives 404 with the reason intent. A foreign id/idle use placement. A change of the intent version requires repeating the read, a non-answer of any mandatory read — 503. The heartbeat is read after the effective decision; the absence of a door does not turn into null. Scenario 04 checks only the absence of a placement, active/interleavings are not executed in the current TSV.

Run 36 (Kimi): check both outcomes of the absence of v and the mounted /servers, /unplaceable, /where, /metrics and the page. For where(table,place): an unknown table 404 before unit; then the form/view, a confirmed hold and the heartbeat, a read error 503, the absence of a hold 404 with X-Unreachable. door is optional and appears only with a confirmed addressee/holder/signer; the issue is journaled. Sc.04/6 sees empty resources and does not check the fields of ResourceRow. (The loopback, trust, Origin and the emergency login — [the acceptance of chapter 6.3](../3/README.md).)
