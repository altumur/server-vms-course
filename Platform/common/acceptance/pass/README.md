# The stand of the pass of the second kind

This English text is the source; the Russian translation `ru/acceptance/pass/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The scenarios of `door.pass` of the second kind: the ticket, the callback, the stream, the role leaf (ADR-0094 B1, Confirmation; the norms — [the gate-and-pass contract](../../contracts/gate-and-pass.md) «Pass of the second kind», [P/06.3](../../../06-console/spec/06.3-console.norms.md) N1.9, [P/06.5](../../../06-console/spec/06.5-console.norms.md) N1.8, [the role certificate contract](../../contracts/role-certificate.md) «The callback leaf», [P/02.5](../../../02-installer/spec/02.5-installer.norms.md) N1.5). What is checked without a live worker goes in the chapters: sc. 46 of [acceptance 6.1](../../../06-console/acceptance/1/README.md), sc. 32 of [acceptance 6.5](../../../06-console/acceptance/5/README.md).

13 scenarios / 201 steps. The runner plays the worker: a scenario needs to keep a request open, to see what reached the worker and to call the console back with a ticket and a leaf, while the test worker of the implementation does not give this and would check itself. The manifests are [`probe-p`](probe-p.subsystem.yaml) and the door of the first kind [`probe-f`](probe-f.subsystem.yaml) (sc. 10), the kits of sc. 08 — [`stand.json`](stand.json) in the form of the [TLS stand](../tls/README.md), with one new field: the `server` of a leaf in `negative` — a leaf with another server name. The callback with a leaf goes to a separate listener of the console, the substitution `{cport}` ([ADR-0094 addendum (16)](../README.md#stand-in-worker-of-the-pass-of-the-second-kind)).

By reading, with a reason: a socket of a foreign role — the stand sets up one subsystem with `door.pass.calls`, there is no socket of another role (a leaf of a foreign role — sc. 08); break-glass and the debug identity — the same step 3 of the order of `ticket` as sc. 04; the stand does not do a request by a cookie. The route of the door of a subsystem ([P/06.3](../../../06-console/spec/06.3-console.norms.md) N1.9) — the stand-in worker does not serve as a holder. `X-W2C-Loopback` without the loopback and `PASS_STREAMS_MAX` — all clients of the stand are on the loopback, a TSV will not open 256 streams. `PASS_TICKET_CHECK` — only by the upper bound of step 16 of sc. 05. The door of a worker with the leaf `console` and the SDK client — P/03.4-15, a test of the implementation: the stand-in worker does not check them.

## Executability

The runner has the directives of the dictionary, the door `socket`, the substitution `{cport}`, the key `keys.pass_stand`. The rule is the same as for the [system acceptance](../system/README.md): a scenario goes into a runner release only after a run against an implementation, each red step is analysed by the question «norm or data», and new scenarios enter the pin of the lines only by a runner release.

## Timings

`probe-p` declares `wait: {api/x: 300}`: the request of a scenario keeps the ticket alive, the limit does not mask the checks of revocation and switching off (`PASS_WAIT` 5 s would remove the ticket itself). A stream outlives `PASS_WAIT`, a stream has no limit.

## scenarios.tsv

The format is the [dictionary of directives and doors of «Stand» of the common acceptance README](../README.md#dictionary-of-directives-and-doors). The stand is [«Domain stand»](../README.md#domain-stand), `@domain m1`; the runner sets up `probe-p` on `m1` and `hold` together with the manifests of the stand; on `hold` the worker is brought up only by sc. 09. `probe-f` — together with `probe-p` only on the cluster of the scenario (`m1`; for sc. 04 the stand without a domain — `hold`); on `hold` next to `m1` it is absent: the entry `probe-f/accounts` in `door.pass.calls` of `probe-p` there is a deferral of the catalogue; while there is no `probe-f`, there is simply no door, the installer and the console accept `probe-p` ([P/02.1](../../../02-installer/spec/02.1-installer.norms.md) N1.4, `door.pass.calls[]`). Sc. 04 — the console stand without a domain, the directives without `<cluster>`.

