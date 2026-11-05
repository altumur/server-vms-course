# The local token door contract of the agent: the role socket, the identity of the connection, the body, the answer, refusals

This English text is the source; the Russian translation `ru/contracts/local-token-door.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Platform» (ADR-0083 addendum (5), addendum (11) and addendum (13): a common contract can appear before the move
of the owner lesson; analysis of review of stage A 8–10, № 1 / decision 1). The owner is [chapter 9.1](../../09-agent/spec/09.1-agent.norms.md) of lesson P/09 (Н1.6,
P/09.1-10; the source is М11/7 Н1.2): the member's agent listens on the local door and passes the request on to the
holder. The participant is the worker, chapter [P/03.7](../../03-worker/spec/03.7-worker.norms.md) Н1.5: it asks for a token through this door.
The socket units — [P/02.4 Н1.1](../../02-installer/spec/02.4-installer.norms.md); the variable `AGENT_TOKEN_DIR` — in the life
cycles of the [agent](../../09-agent/lifecycle.md) and of the [worker](../../03-worker/lifecycle.md). The holder's door, the issue and the
claims of a token — chapter [P/08.7](../../08-domain/spec/08.7-domain.norms.md) (Н1.3, Н1.4, Н3); the form of a token — the [domain token contract](domain-token.md).

Moved from М11/7 Н1.2 (the block `door`, `body`, `request`, `TOKEN_BODY`, `answer`, `no_queue`, `TOKEN_WAIT`) and the rows of Н4
«у агента» without a change of behaviour. The section «The role socket» is a change of behaviour (the Architect's decision of 2026-10-20, ADR-0083 addendum
(13)): formerly the transport and the port were a choice of the implementation (М11/12 Н1.8 `local_door`, М11/12 «Implementation decides» item 3, М11/7
«Implementation decides» item 1). ADR-0080 item 2 («the mechanics of a side» is decided by the implementation) does not apply to this door: the door
connects processes of different implementations on one box, and the witnesses already differ in the socket name.

Normative keywords follow the [course canon](../../../НОРМАТИВНЫЕ-СЛОВА.md).

## Form

The holder's door to which the agent passes the request (`/api/tokens/{member}/{sub}/{kind}`; the code and the body of the holder — as received) — `Platform/08-domain/spec/08-domain.api.openapi.yaml`; the local door — `Platform/09-agent/spec/09-agent.api.openapi.yaml`, the tag `local-door` (layout audit, V-35; the Architect's decision of 2026-10-25).

## The role socket

The Architect's decision of 2026-10-20 (analysis of review of stage A 8–10, decision 1):

```yaml
transport:   on a box — a Unix stream socket (SOCK_STREAM), over it HTTP/1.1 of the door «The door» below; there is no other transport on
             a box
address:     <AGENT_TOKEN_DIR>/<role>.sock — one socket for each worker role of the manifest catalogue (<role> — <sub>worker);
             flat, no subdirectories
AGENT_TOKEN_DIR: the directory of the sockets of the local door; the default /run/w2c/domainagent; set by the agent unit and the worker unit with one
             value (P/02.4 Н1.1, Н1.2); on the stand — by the runner
identity:    the role of the connection is the role of the socket it came into; the local door has no other identity (the role is not
             named in the body, Н1.2 below)
group:       the socket <role>.sock — mode 0660, owner root, group — the group of the worker role (<dep>-<role>, P/02.4 Н1.1
             users_groups); the group is set by SocketGroup= of the socket unit, the agent gets the socket ready and is not a member of the groups of the worker
             roles — like the store daemon (P/01.3 Н1.3 sockets, P/02.4 Н1.1 users_groups rule)
units:       w2c-domainagent-token-<role>.socket — one unit per role: ListenStream=<AGENT_TOKEN_DIR>/<role>.sock;
             FileDescriptorName=token-<role>; SocketUser=root; SocketMode=0660; SocketGroup=<the role group>;
             Service=w2c-domainagent.service (P/02.4 Н1.1)
inherit:     the inherited sockets (the protocol sd_listen_fds: LISTEN_PID equals its own pid, LISTEN_FDS, LISTEN_FDNAMES) the agent
             takes by FileDescriptorName; for each it checks the type (a stream socket), listening, the path <AGENT_TOKEN_DIR>/<role>.sock
             and a repeated name — anything else or two with one name — a start refusal; its own copies of descriptors that it does not hold it closes;
             a socket that was not passed the agent creates itself: <AGENT_TOKEN_DIR>/<role>.sock, mode 0660, the group of the process;
             the path already exists — lstat without following a link: a socket and connect to it — ECONNREFUSED — stale: the agent removes
             it and creates its own; connect succeeded or returned another error — busy, not removed, a start refusal; not a socket (a file
             of another type, a symbolic link included — another type, do not follow it) — not removed, a start refusal;
             bind → EADDRINUSE — a start refusal; a path created in place of a stale one is «created by it» for the exit rule;
             at exit it removes only a path it created and only if the dev/ino of the path are the former ones (guess of stage C LTD-E03,
             the Architect's decision of 2026-10-23; LTD-STALE-PATH-33-01, the Architect's decision of 2026-10-25)
client:      the worker connects to <AGENT_TOKEN_DIR>/<W2C_ROLE>.sock of its unit; it looks for no other address
in_process:  the agent in the platform process of a cluster of one — a call, not a door (P/09.1 Н1.11 tokens; the section «The call in
             the process»): there is no socket
```

**An open question — a worker on another server of the cluster.** The local door over TCP with a role certificate (ADR-0075) for a worker
whose cluster's agent is on another server is not normed until the stand; the place is [P/09.1 Н5](../../09-agent/spec/09.1-agent.norms.md#open)
«Open» (the move plan of lesson 9, V1). While the question is open, such a door does not take the domain ports 8444–8447 ([P/02.4 Н1.12](../../02-installer/spec/02.4-installer.norms.md)).

## The door

From М11/7 Н1.2:

```yaml
door:       POST /tokens/<sub>/<kind> at the agent of its own cluster; the identity of the connection is the worker role by one of the ways of
            P/02.4 Н1.6: the role socket on a box or the role certificate (ADR-0075) in a cluster; the role is not named in the body
body:       {request_id, ref, by?, revoked?} — request_id 1–64 [A-Za-z0-9_-]; ref, by — non-empty strings; revoked — the jti of a token that the recipient refused with the word revoked (P/08.7 Н1.3), 16 hex; larger than TOKEN_BODY — 413
request:    the header Transfer-Encoding in the request (chunked together with Content-Length included) — 400; <sub> of the path is not a manifest
            of the catalogue — 404 at the agent, the request does not go to the holder (a kind not declared by the manifest — the holder decides, 403
            not_granted); added by the М11 reconciliation, T7, T8
TOKEN_BODY: 4 KiB          # the limit of the client's body at the local door of the agent; the bytes of the body as received are measured
TOKEN_HOLDER_BODY: 4608    # the limit of the body at the holder's door POST /api/tokens/<member>/<sub>/<kind> (P/08.7 Н1.3): = TOKEN_BODY + 512
                           # for what the agent adds (role and the JSON wrapping): a body of exactly TOKEN_BODY at the local door does not get
                           # 413 at the holder; the bytes of the body as received are measured (journal of cammeta-go, М11-07 № 4; moved from P/08.7
                           # Н1.3 without a change; layout audit, the Architect's decision of 2026-10-25, A-19)
refusal_413: 413 {error: "refused", detail} — a body larger than TOKEN_BODY at the local door of the agent, larger than TOKEN_HOLDER_BODY at
            the holder's door — before the signature and the parse; detail — the words of the implementation (from P/08.7 Н4 without a change; B-31)
framing:    exactly one Host and one Content-Length; Transfer-Encoding (chunked included) — 400; an ambiguous or incomplete
            message — 400; the request line and the headers ≤ 16 KiB, otherwise 400; the input of the whole request ≤ 10 s, otherwise 400; one exchange
            per connection, the answer with Connection: close; TOKEN_WAIT is counted after the body is received and includes the opening of the holder's
            answer (guess of stage C LTD-E01, the Architect's decision of 2026-10-23)
answer:     200 {request_id, token, exp} — only to this connection; anything else — the code and the body of the holder as received
no_queue:   the agent holds the request while the holder has not answered (no longer than TOKEN_WAIT); did not answer — 503 {error: "unavailable"};
            the road through a relay: the relay answered 502 did not answer (the holder did not answer it) or did not answer itself —
            also 503 {error: "unavailable"}, not the 502 of the relay (the Architect's decision of 2026-10-20 on the question of commit 9)
            (Н2: the holder cannot be reached), the worker asks again; there is no queue of answers
TOKEN_WAIT: 10          # s
```

«The role certificate in a cluster» of the row `door` is the open question of the section «The role socket»; «Н2» of the row `no_queue` is P/09.1 Н2.
The HTTP form of the door — [OpenAPI of lesson 9](../../09-agent/spec/09-agent.api.openapi.yaml), the tag `local-door`, `/tokens/{sub}/{kind}`.

## Refusals

From М11/7 Н4 (the rows «у агента»):

The code and `error` are normative; `detail` is the words of the implementation, as at the relay's door (guess of stage C LTD-E02, the Architect's decision of 2026-10-23).

| Word | Code | When |
|---|---|---|
| `unauthorized` | 401 | at the agent: there is no role identity |
| `not found` | 404 | at the agent: no route (`<sub>` of the path is not a manifest of the catalogue) |
| `bad request` | 400 | at the agent: the body is not in the form of Н1.2, the header `Transfer-Encoding`, framing («The door» `framing`), the input deadline expired |
| `refused` | 413 | at the agent: the body is larger than `TOKEN_BODY`; `detail` — for example «body exceeds TOKEN_BODY» (the form — `refusal_413` above) |
| `invalid token reply` | 502 | at the agent: `m1` did not open, a wrong `request_id`, `exp ≤ now` |
| `unavailable` | 503 | at the agent: upstream did not answer within TOKEN_WAIT — the holder or the relay; 502 `did not answer` of the relay — also 503 (`no_queue`; the Architect's decision of 2026-10-20 on the question of commit 9); 503 `frozen` of the holder (P/08.7 Н3 «issue» step 6a) — also 503 `unavailable`: the worker has no word for freezing, the request is repeated, the former token is kept (ADR-0110 addendum (12) item 3) |

413 of the local door and of the holder's door — `refusal_413` above (B-31); the code and the body of the holder passed on «as received» — [P/08.7](../../08-domain/spec/08.7-domain.norms.md) Н4. The holder's answer is opened by the agent ([P/09.1](../../09-agent/spec/09.1-agent.norms.md) Н1.6 `agent`; `m1` — [P/08.3](../../08-domain/spec/08.3-domain.norms.md) Н1.5 and the [domain envelopes contract](domain-envelopes.md)).

## The call in the process

From М11/12 Н1.3 `tokens` (the norm is [P/09.1 Н1.11](../../09-agent/spec/09.1-agent.norms.md), P/09.1-14; the Architect's decision
on the move plans of 8–10, item 4: the agent has no library contract). The rows `call`, `differs` are a reading of М11/12 Н1.3
«в процессе — вызов, а не дверь»: the former tail «без очереди, TOKEN_WAIT и 503 …» was also read as a removal of the door's refusals
(analysis of review of stage B 8–10, № 2):

```yaml
in_process:  a cluster of one MAY hold the agent in the platform process without the set of the role domainagent (P/09.1 Н1.11 where);
             the local token door is then a call, not a door: there is no socket («The role socket» in_process)
role:        the role of the requester is the role with which its component is started in the process, not a word of the request; the call has no other
             identity (as identity of «The role socket»: the role is not named in the body)
call:        the body, the answer and the refusals of the call are the same as at the door: the body {request_id, ref, by?, revoked?}, larger than TOKEN_BODY — 413
             («The door» body); the answer 200 {request_id, token, exp} — only to this call, anything else — the code and the body of the holder as
             received (answer); upstream did not answer within TOKEN_WAIT — 503 {error: "unavailable"}, there is no queue of answers (no_queue);
             the holder's answer did not open, a wrong request_id, exp ≤ now — 502 invalid token reply («Refusals»)
differs:     the difference from the door is one — there is no socket and no identity of the connection (neither a role socket nor a role certificate): the role
             of the requester is the role of its component (role above)
rights:      the same evaluator of P/01.2 by the role of each component of the process: one process is not one role, each key has one
             writer (ADR-0032)
participant: a worker component of the same process is a participant, as at the door (P/03.7 Н1.5); which components live in the process and with
             which roles — P/09.1 «Implementation decides» item 9
```

## Vectors

There are no vectors: the local token door is checked by the acceptance scenarios of its participants and by reading. (ADR-0083 addendum (32) item 2)
The path of the socket at start («The role socket» inherit: stale, live, another type, a symbolic link, EADDRINUSE) — by reading:
these are system calls over the file system of the box, not a function of data, and the stand puts no files into `AGENT_TOKEN_DIR`
(LTD-STALE-PATH-33-01).

## Correspondence to former lessons

From М11/7 (analysis of review of stage A 8–10, № 1 / decision 1): Н1.2 whole (here «The door»; in М11/7 — a pointer) and the rows of Н4
«у агента» — 401/404/400, 502 `invalid token reply`, 503 `unavailable` (here «Refusals»). From М11/12 Н1.8 — the row
`local_door` (do not take the ports 8444–8447; here «An open question»); the former «choice of the implementation» and the TCP default `8448`
are removed by decision 1. The norm is P/09.1-10 (М11/7-02; `note` of [id-map](../id-map.tsv)); the participant is P/03.7-04. From М11/12
Н1.3 `tokens` — the section «The call in the process» (the Architect's decision on the move plans of 8–10, item 4).
The contract has no vectors: the door is checked by sc. 01, 02 of the [acceptance of chapter 8.7](../../08-domain/acceptance/7/README.md) (М11/7-02 → P/09.1-10).
