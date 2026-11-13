# Acceptance P/10 — the domain console

This English text is the source; the Russian translation `ru/acceptance/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The stand, the dictionary of directives and doors — [the common acceptance README](../../common/acceptance/README.md#dictionary-of-directives-and-doors) and its
section [«Domain stand»](../../common/acceptance/domain-stand.md#domain-stand) (the door `holder` — the domain console on `hold`, the doors
`member`, the directives `@domain`, `@person`, `@stop agent`, `@start agent`). The norm of the lesson is
[`10-domain-console.norms.md`](../spec/10-domain-console.norms.md) N5. The command `alarms` — the vector [`vectors/alarms`](../vectors/alarms/README.md) (the current corpus). The forms of foreign doors — their owners.

## Stand

The preparation is as the acceptance README of [chapter 8.3](../../08-domain/acceptance/3/README.md) («Preparation of each scenario»: the clusters `hold`, `m1`, `m2`, the catalogue `testsub`); for selected scenarios — with a declaration of the shared in `testsub`, as the acceptance README of
[chapter 8.9](../../08-domain/acceptance/9/README.md):
- `domain.shared: [step, marks, {rounds}]`;
- `step` — `int` with `inherit: 1`;
- `marks` — `list` with `inherit: []`, `merge: union`.

The runner goes as the human `root` (the first administrator — chapter 8.4, the directive `@person`).

- The doors of the holder page (the norms N1.7). The calls of the module in the mode `domain` are checked by the test of the module at its
  owner ([P/07](../../07-console-module/spec/07-console-module.norms.md) N1.6), not by this acceptance.

The JavaScript response bytes are compared with the same [P/07 console.js](../../07-console-module/module/console.js) as the cluster console, at the existing synchronous `/platform/console.js?v=1`. The unchanged requests, statuses and headers remain mandatory. This byte-publication check does not replace the module-owner tests of UI language and date rendering; no locale fetch, new route or version is introduced.

The refusal `not in the directory` (a manifest without `domain.ref`, N1.2a) — by reading: the manifests of the stand (`testsub`, `testsub2`)
have `domain.ref`.

The neighbours on the stand: the edit of the shared document is passed by the domain console to the process `domain` (the norms N1.3;
the execution — [chapter 8.9](../../08-domain/spec/08.9-domain.norms.md) N1.3); the content of `delivery` —
`view.shared` of chapter 8.9 (N1.6), the door `GET /domain/shared` — this lesson (P/10-14); the document is taken by the agent of the member
([chapter 9.1](../../09-agent/spec/09.1-agent.norms.md)); the agent signature at `/events` of the cluster console of the member
([the agent signature contract](../../common/contracts/agent-signature.md), the gate P/06.3).

The stand does not call the alarm page (the front once a second, the urgent report, `truncated`): the stand has no training subsystem that
raises alarms. This is checked by the vector `alarms` and by reading.

## Store rows on the stand

The rows of the store of
`hold` are written by the runner through the door `member hold store` (`admin.sock`); it cannot delete a row under `domain/` (P/01.2 N1.3
`never`: delete under `domain/` — only by the domain role), therefore the stand does not create «no row» — an unreadable row is written by a `put`
not by the form of its family, and the former one — by a `put` of a value by the form. The writer of these rows is the process `domain` (the data catalogue); before
the spoiling it is stopped (`@on hold @sigterm domain`), the domain console is alive and answers itself.

## scenarios.tsv

The format — [the dictionary of directives and doors of the «Stand» of the common acceptance README](../../common/acceptance/README.md#dictionary-of-directives-and-doors)
and the section «Domain stand»: a subset of the fields, `~` — a substring, `@file` — the bytes of a file. In total 16 scenarios / 163 steps.

The subset of expect does not replace the check of the full HTTP form of the OpenAPI of the lesson: check the required fields, the types, the Content-Type.

## Forwarding credential seams

The forwarding-credential seam table uses `scenario step request expect`, literal TAB, and the CALL/JSON grammar of [P/02](../../02-installer/forms/README.md). `CALL console-forward-credentials <JSON>` is an acceptance adapter over the ordinary gate, HTTP forwarding and writer admission, not a new product API or native vectors command. P/06.7 uses the same port. Each case has a fresh temporary root, valid catalogue, confirmed holder, readable rows, current turn, ordinary keys/signatures, independent real sessions for persons `a` and `b`, and the grants needed by the selected valid operation. The adapter obtains tokens and cookie proof through the ordinary code. It does not supply a successful gate result or echo an expectation.

`transition` is the **first external cookie hop**: 1 is a non-holder cluster console, 2 the holder's cluster console, 3 a direct request to the domain console. For 1/2, use the actual cluster-console forwarding path; running only domainconsole is insufficient. Subsequent receivers and the final writer run their ordinary admission code. A controlled HTTP transport may intercept the outgoing request at the first hop and deliver it to those ordinary handlers; it does not replace their identity, need, may or CSRF decisions. This port alone is not the full multi-process stand.

`credential=cookie` uses the live person-a session with no Authorization. `authorization-and-cookie` supplies a valid person-b Authorization together with person-a's cookie: both people are independently authorized, and the exact presented header must survive. `bad-authorization-and-cookie` supplies an invalid presented Authorization and a valid cookie; `bad-cookie` supplies an invalid person cookie. Neither may fall through to another credential or debug. `debug` uses the ordinary configured loopback debug person with no presented token/cookie; it may not manufacture a credential for the writer. `unrelated_session=b` additionally populates another real session/cache entry, while the request is still proved by person-a's session.

`guard=ok` uses a valid unsafe writer operation, `PUT /domain/topology` with a matching base revision and valid body. `guard=csrf` makes only the **original** unsafe cookie request's Origin invalid. `guard=need` chooses a declared domain forwarding operation whose ordinary need resolution refuses under its published rule; `guard=may` keeps a valid resolved need but removes its necessary grant. These cases execute the relevant ordinary guard and retain its original refusal; they prescribe no new HTTP code. Identity failure likewise uses the ordinary guard. Fixture interventions may alter confirmed input data or I/O, never substitute the final guard decision.

The returned JSON normalizes actual observations: `refused` means a non-success response; `forward_calls` counts outgoing requests from the first console; `writer_calls` counts actual entry to the writer; `cookie_out`, `x_user_out` and `ticket_out` record the presence of those actual outgoing headers; `bearer_set` records creation of a Bearer by this hop; `authorization_unchanged` compares the actual presented/outgoing header bytes; `session_token_equal` compares the outgoing Bearer token to the exact token proved by this cookie session; `other_session_used` compares it to the unrelated session's distinct token. For a refusal before forwarding the header-presence/creation observations are false. No token bytes are printed. A panic, unrelated failure, omitted handler or precomputed expected answer fails the seam. The ordinary scenarios, existing worker/ticket rules and full stand remain mandatory.

## Kit assistance seams

The kit seam table provides 82 CALL steps of 44 scenarios over ordinary implementation paths. The fixture/port contract is [forms/README.md](../forms/README.md); [stages.tsv](../forms/stages.tsv) selects them. They assist the kit and do not replace the ordinary scenarios of this directory, the vector `alarms`, the neighbours on the stands of lesson P/08 or the items checked by reading.

The forms README defines the real collector, own reads, closed-route dispatch and composed hop fixtures.
