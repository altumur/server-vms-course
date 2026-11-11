# The stand of the pass of the second kind

This English text is the source; the Russian translation `ru/acceptance/pass/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The scenarios of `door.pass` of the second kind: the ticket, the callback, the stream, the role leaf (the norms — [the gate-and-pass contract](../../contracts/gate-and-pass.md) «Pass of the second kind», [P/06.3](../../../06-console/spec/06.3-console.norms.md) N1.9, [P/06.5](../../../06-console/spec/06.5-console.norms.md) N1.8, [the role certificate contract](../../contracts/role-certificate.md) «The callback leaf», [P/02.5](../../../02-installer/spec/02.5-installer.norms.md) N1.5). What is checked without a live worker goes in the chapters: sc. 46 of [acceptance 6.1](../../../06-console/acceptance/1/README.md), sc. 32 of [acceptance 6.5](../../../06-console/acceptance/5/README.md).

13 scenarios / 201 steps. The runner plays the worker: a scenario needs to keep a request open, to see what reached the worker and to call the console back with a ticket and a leaf, while the test worker of the implementation does not give this and would check itself. The manifests are [`probe-p`](probe-p.subsystem.yaml) and the door of the first kind [`probe-f`](probe-f.subsystem.yaml) (sc. 10; judge-only: the manifests of the stand), the kits of sc. 08 — [`stand.json`](stand.json) (judge-only: the kit description) in the form of the [TLS stand](../tls/README.md), with one new field: the `server` of a leaf in `negative` — a leaf with another server name. The callback with a leaf goes to a separate listener of the console, the substitution `{cport}` ([the stand-in worker](#stand-in-worker-of-the-pass-of-the-second-kind)).

By reading, with a reason: a socket of a foreign role — the stand sets up one subsystem with `door.pass.calls`, there is no socket of another role (a leaf of a foreign role — sc. 08); break-glass and the debug identity — the same step 3 of the order of `ticket` as sc. 04; the stand does not do a request by a cookie. The route of the door of a subsystem ([P/06.3](../../../06-console/spec/06.3-console.norms.md) N1.9) — the stand-in worker does not serve as a holder. `X-W2C-Loopback` without the loopback and `PASS_STREAMS_MAX` — all clients of the stand are on the loopback, a TSV will not open 256 streams. `PASS_TICKET_CHECK` — only by the upper bound of step 16 of sc. 05. The door of a worker with the leaf `console` and the SDK client — P/03.4-15, a test of the implementation: the stand-in worker does not check them.

## Executability

The runner has the directives of the dictionary, the door `socket`, the substitution `{cport}`, the key `keys.pass_stand`. The rule is the same as for the [system acceptance](../system/README.md): a scenario goes into a runner release only after a run against an implementation, each red step is analysed by the question «norm or data», and new scenarios enter the pin of the lines only by a runner release.

## Timings

`probe-p` declares `wait: {api/x: 300}`: the request of a scenario keeps the ticket alive, the limit does not mask the checks of revocation and switching off (`PASS_WAIT` 5 s would remove the ticket itself). A stream outlives `PASS_WAIT`, a stream has no limit.

## Stand-in worker of the pass of the second kind

The directives of this stand. The runner executes them (section [Executability](#executability)). The runner plays the worker: so a scenario keeps a request open and sees what reached the worker. In the directives `<cluster>` is present on the domain stand; on the console stand it is absent.

| Form | Meaning | Lesson |
|---|---|---|
| `@pass-worker [<cluster>] <sub> <name> [kit=<leaf>]` | the runner listens on a door on the loopback (without `kit` the `url` is `http://127.0.0.1:<port>`; with `kit` — https with the server leaf `<leaf>` of the kits of `@tls-setup`: the host of the `url` is the server name of the kit and the chain is the leaf and the `ca.pem` of the cluster of the leaf; a cluster instead of the leaf name — the leaf `<cluster>-<sub>worker`); when a worker of the same name is replaced, the runner waits until a probe `GET /<sub>/api/x` through the console comes to the new listener: the `url` of the issue is not named; it writes and refreshes the object `<sub>/heartbeats/<name>` with `worker`, the `url` of this door, like a live worker with a door; it keeps an accepted request open; the expectation `ok` — the console sees it alive. The previous worker `<name>` is stopped | P/06 |
| `@pass-open <label> <door> <request>` | a request to the console in the background, under a label; a `POST` without `Idempotency-Key` gets the key by the rule `@key`; waits until the stand-in worker accepts it. The expectation `ok <JSON>` — the accepted request by subset: `{method, path, query, body, ticket, headers}`, `ticket` — the value of `X-W2C-Pass-Ticket`, the absence of the header — `@absent`; it did not get through — the answer to the client, the form `<code> <JSON>` | P/06 |
| `@pass-answer <label> <code> <Content-Type\|-> [<body>]` | the worker answers the request of the label: the status `<code>`, `Connection: close`, `Content-Length` except for 204, `Content-Type` unless `-`; the expectation — the answer to the client, the forms of the dictionary | P/06 |
| `@pass-chunk <label> <text>` | the worker sends a part of the stream: the status 200, `Content-Type: text/event-stream`, chunked encoding, each part is the text followed by an empty line; the expectation `<code> ~<text>` — the client has already received it, the answer is still open | P/06 |
| `@pass-result <label>` | the answer to the client without an action of the worker: the worker side is silent; the expectation — the forms of the dictionary | P/06 |
| `@pass-abort <label>` | the client breaks the connection; the expectation `ok` — the worker saw the close | P/06 |
| `@pass-closed <label>` | the console closed the connection of the client no later than `PASS_TICKET_CHECK` + 30 s; the expectation `ok` | P/06 |
| `@pass-fill <cluster> <sub>` | open requests `GET /<sub>/api/x` to the route until the console answers 503 `busy`; they live until the end of the scenario; the expectation `ok` | P/06 |
| `@pass-seen <name>` | how many requests the stand-in worker accepted, without the probes of a worker replacement; the expectation `ok {"requests": N}` | P/06 |
| `@pass-call <client> <request>` | one probe of the door `callback <cluster>`: the callback listener, the address — `X-W2C-Pass-Console` of the last `@pass-open`, the port — `{cport}`; the client — a leaf of `stand.json` (judge-only: the kit description) or `null`, the outcome — the closed form of `@tls`, with the substitutions `$name` | P/06 |
| `@pass-step <label> [<name>]` | wait for a step call of an operation on the stand-in worker (the route `door.pass.operations.step`, [P/06.9](../../../06-console/spec/06.9-console.norms.md) N2; a call is recognised by its path: without its leading and trailing `/` the path equals the route, the query does not count) and hold it: no longer than 40 s (`OPS_STEP_WAIT` + 2 × `OPS_TICK`). The expectation `ok <JSON>` — the accepted call by subset `{method, path, ticket, headers, id, index, body, secret, expected, opcount}`, `secret` without a value — `@absent`. `@pass-open` does not take step calls, `@pass-seen` counts everything accepted | P/06 |
| `@pass-step-answer <label> <code> <Content-Type\|-> [<body>]` | answer the step call; the expectation `ok`. The console does not read the answer body | P/06 |
| `@pass-step-none <name> <s>` | no step call came within the term; the term counts as a sleep: the lesson README names the reason; the expectation `ok` | P/06 |
| `@pass-step-drop <label>` | break off the step call without an answer: a lost answer, `OPS_STEP_TRIES`; the expectation `ok` | P/06 |

**Terms of the stand-in worker.**

| What | Term |
|---|---|
| `@pass-open`: the stand-in worker accepts the request | 30 s |
| `@pass-worker`: the console sees the worker alive | 30 s |
| the heartbeat of the stand-in worker | every 5 s |
| `@pass-answer`, `@pass-result`: the answer to the client | read within 120 s, judged within 180 s |
| `@pass-chunk`, `@pass-abort`, the answer to a request of `@pass-fill` | 30 s |
| `@pass-fill` | at most 4096 requests; the limit reached without `503` `busy` is a failure of the stand, not an outcome of the implementation |

The substitution `{cport}` is the port of the callback listener of the console: the stand sets `CONSOLE_CALL_PORT={cport}` for a console with a kit (the environment file contract). The console profile declares `keys.pass_stand: 1`; without it the checks of this stand are not executed (not GREEN). Without a kit there is no substitution: the listener is not opened.

The door `socket [<cluster>[#<n>]] <role>` — a request to the worker role socket to the console `<PLATFORM_DIR>/run/console/<role>.sock`, in the same request form ([P/02.5](../../../02-installer/spec/02.5-installer.norms.md) N1.5); `#<n>` — the copy of the console `console#<n>`, without a number — the first.

## scenarios.tsv

The format is the [dictionary of directives and doors of «Stand» of the common acceptance README](../README.md#dictionary-of-directives-and-doors). The stand is [«Domain stand»](../domain-stand.md#domain-stand), `@domain m1`; the runner sets up `probe-p` on `m1` and `hold` together with the manifests of the stand; on `hold` the worker is brought up only by sc. 09. `probe-f` — together with `probe-p` only on the cluster of the scenario (`m1`; for sc. 04 the stand without a domain — `hold`); on `hold` next to `m1` it is absent: the entry `probe-f/accounts` in `door.pass.calls` of `probe-p` there is a deferral of the catalogue; while there is no `probe-f`, there is simply no door, the installer and the console accept `probe-p` ([P/02.1](../../../02-installer/spec/02.1-installer.norms.md) N1.4, `door.pass.calls[]`). Sc. 04 — the console stand without a domain, the directives without `<cluster>`.

