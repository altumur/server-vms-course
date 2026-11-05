# The stand of the pass of the second kind

This English text is the source; the Russian translation `ru/acceptance/pass/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The scenarios of `door.pass` of the second kind: the ticket, the callback, the stream, the role leaf (ADR-0094 B1, Confirmation; the norms — [the gate-and-pass contract](../../contracts/gate-and-pass.md) «Pass of the second kind», [P/06.3](../../../06-console/spec/06.3-console.norms.md) Н1.9, [P/06.5](../../../06-console/spec/06.5-console.norms.md) Н1.8, [the role certificate contract](../../contracts/role-certificate.md) «The callback leaf», [P/02.5](../../../02-installer/spec/02.5-installer.norms.md) Н1.5). What is checked without a live worker goes in the chapters: sc. 46 of [acceptance 6.1](../../../06-console/acceptance/1/README.md), sc. 32 of [acceptance 6.5](../../../06-console/acceptance/5/README.md).

13 scenarios / 201 steps. The runner plays the worker: a scenario needs to keep a request open, to see what reached the worker and to call the console back with a ticket and a leaf, while the test worker of the implementation does not give this and would check itself. The manifests are [`probe-p`](probe-p.subsystem.yaml) and the door of the first kind [`probe-f`](probe-f.subsystem.yaml) (sc. 10), the kits of sc. 08 — [`stand.json`](stand.json) in the form of the [TLS stand](../tls/README.md), with one new field: the `server` of a leaf in `negative` — a leaf with another server name. The callback with a leaf goes to a separate listener of the console, the substitution `{cport}` ([ADR-0094 addendum (16)](../README.md#stand-in-worker-of-the-pass-of-the-second-kind)).

| № | Scenario | Norms |
|---|---|---|
| 01 | the ticket lives with the request: the credentials do not leave, the door of the list works, a write by the ticket; outside the list, the write `/session`, a foreign subsystem, without a ticket, over TCP — 401; the answer is given — the ticket is dead; the series and the journal `pass.called` | `ticket`, `journal`, `counter`, P/06.3 Н1.9 |
| 02 | the headers to the worker and to the client; 412 `problem+json`, 204, a type outside the list — 502; `nosniff`, `sandbox`; the limit `wait` — 504 | `to_worker`, `to_client`, `types`, `timeout` |
| 03 | a fresh `may` — 403; two tokens, one revoked: the ticket of the first is 401, the second works; a switched-off person on a member: the ticket is alive, `grants: []`, the stream is closed | `ticket` step 5, `close` |
| 04 | the console is open: there is a ticket, the kind of the session gives no callback | `ticket` step 3 |
| 05 | the stream: reads and `/changes`, a write — 401, `Last-Event-ID`, the answer as it arrives; the stream closes with the request and on the revocation of the token | `stream`, `close`, `ticket` step 4 |
| 06 | a table `service: true` by the ticket: a person without rights reads and writes their own, a row in a batch; a row outside the list — 401 of the whole batch; without a ticket the door is closed; the feed by the ticket: a row of one's own `user` comes also on removal, a foreign one and one without the field `user` — do not | `service`, P/06.3 Н1.9 «Batch rows», P/06.1 Н1.6, Н2 «Change feed» |
| 07 | the common lane is busy with passes, their callbacks go through | P/06.5 Н2, the contract `order` step 1 |
| 08 | the callback listener: its own role and server — yes; without a ticket, a foreign role, another server — 401; without a leaf, a foreign CA, the validity, EKU — a handshake refusal; the main listener does not accept a ticket; a server leaf not of the role of the addressee — no pass, the body did not leave | `callback_transport`, `transport`, «The callback leaf» |
| 09 | a switched-off person at the holder: the ticket is 401, the stream is closed by `domain/disabled` | `ticket` step 5, `close` |
| 10 | a write of the first kind: the worker of the door receives the token of the person in `Authorization`, the addressee of the ticket does not see it, the door has no ticket header; a door outside the list — 401 | `first_kind`, P/06.3 Н1.9 |
| 11–13 | the check without login under a race (ADR-0119 addendum (18)): `POST /domain/verify` by the ticket of `probe-p`; at the bounds of the keys 4 (pair), 19 (author), 9 (name, three authors) two simultaneous wrong ones (`@together`) — one 401, the second 429; after — 429 also with the right password: the count is not more than 5/20/10; a success at the bound does not spend the budget; an author whose only exhausted key is the name key checks another name | the gate contract «Attempt limit» `verify` `answer`, `outcome`, `retry`; P/08.4 Н1.2а, Н1.10; P/06.7 Н1.15 |

By reading, with a reason: a socket of a foreign role — the stand sets up one subsystem with `door.pass.calls`, there is no socket of another role (a leaf of a foreign role — sc. 08); break-glass and the debug identity — the same step 3 of the order of `ticket` as sc. 04; the stand does not do a request by a cookie. The route of the door of a subsystem ([P/06.3](../../../06-console/spec/06.3-console.norms.md) Н1.9) — the stand-in worker does not serve as a holder. `X-W2C-Loopback` without the loopback and `PASS_STREAMS_MAX` — all clients of the stand are on the loopback, a TSV will not open 256 streams. `PASS_TICKET_CHECK` — only by the upper bound of step 16 of sc. 05. The door of a worker with the leaf `console` and the SDK client — P/03.4-15, a test of the implementation: the stand-in worker does not check them.

## Executability

The runner executes sc. 01–09: the directives of the dictionary, the door `socket`, the substitution `{cport}`, the key `keys.pass_stand`; the Go probe 53ee5148 passed them in a dry run 124/124 on the pin 36c2531, runner b02d743, run 20261102T054511Z-pass-53ee514-dry, not a credited one. Sc. 10 and `probe-f`, sc. 11–13 (`@together`, `domain/verify` in `calls` of `probe-p`) were not run by an implementation. The rule is the same as for the [system acceptance](../system/README.md): a scenario goes into a runner release only after a run against an implementation, each red step is analysed by the question «norm or data», and new scenarios enter the pin of the lines only by a runner release.

## Timings

`probe-p` declares `wait: {api/x: 300}`: the request of a scenario keeps the ticket alive, the limit does not mask the checks of revocation and switching off (`PASS_WAIT` 5 s would remove the ticket itself). The limit 504 is judged by `api/slow` 2 s. The sleep of sc. 05 step 13, 7 s: the stream outlives `PASS_WAIT`, a stream has no limit; `PASS_WAIT` + 2 s of the margin of the stand.

## scenarios.tsv

The format is the [dictionary of directives and doors of «Стенда» of the common acceptance README](../README.md#dictionary-of-directives-and-doors). The stand is [«Domain stand»](../README.md#domain-stand), `@domain m1`; the runner sets up `probe-p` on `m1` and `hold` together with the manifests of the stand; on `hold` the worker is brought up only by sc. 09. `probe-f` — together with `probe-p` only on the cluster of the scenario (`m1`; for sc. 04 the stand without a domain — `hold`); on `hold` next to `m1` it is absent: the entry `probe-f/accounts` in `door.pass.calls` of `probe-p` there is a deferral of the catalogue; while there is no `probe-f`, there is simply no door, the installer and the console accept `probe-p` ([P/02.1](../../../02-installer/spec/02.1-installer.norms.md) Н1.4, `door.pass.calls[]`). Sc. 04 — the console stand without a domain, the directives without `<cluster>`.

## `journal/corrections-pass.tsv`

The correction log of the acceptance (ADR-0124: a log, not an input, not in the export): `date`, `sample`, `fix`, `languages`.
