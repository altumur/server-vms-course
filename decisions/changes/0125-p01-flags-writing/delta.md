# Delta 0125-p01-flags-writing — the writing of the daemon flags and the integer of a body (P/01)

change: 0125-p01-flags-writing rev 1. Source: the English norms of P/01 (`delta_base` 725653954). Units by ADR-0122
addendum (1) item 1 (from the anchor to the next anchor or heading; hash — sha256 of UTF-8 after LF and trailing-space strip).

## ADDED

### `Platform/01-store/spec/01.3-store.norms.md` — after P/01.3-R008 (before «### Н1.6»)

<!-- req: P/01.3-R031 -->
The writing of the flags (ADR-0125 addendum (2)): a flag is `-name value` or `-name=value`, the name exactly as the table writes it (`--from` with two hyphens); a flag of the type `bool` is written without a value (`-door=true` is a refusal); `--` alone ends the flags. A repeated flag, a flag of another command, a value out of its type and a positional word of the daemon are a start refusal, code 2; positional words are only those of `admin_ops` by its grammar above (`admit <id>`, `backup <file>`, `leave [id]`). The values: `bytes` and `int` — a decimal integer without a sign, a plus or leading zeros (`0` itself is allowed), `bytes` without a unit suffix (`512KiB` is the writing of the prose, not a value); `duration` — `<integer><unit>`, the unit `ms`, `s`, `m` or `h`, greater than `0` (`5s`, `250ms`); `addr` — `host:port`, a non-empty host (a name, IPv4 or `[IPv6]`) and a decimal port `1`–`65535`. `-id` outside a group defaults to `SERVER_NAME`; an empty or absent `SERVER_NAME` gives no default.

### `Platform/01-store/spec/01.1-store.norms.md` — after P/01.1-R055 (before «## Н3»)

<!-- req: P/01.1-R146 -->
- **An integer of a body** is an integer by its notation: `-?(0|[1-9][0-9]*)`, without a fraction and an exponent; `20.0` and `2.0e1` are not integers — a refusal of the form, 400 `badrequest` (P/01.3 Н4 `floor`; ADR-0125 addendum (2)).

## MODIFIED

### `Platform/01-store/spec/01.3-store.norms.md` P/01.3-R006 — `refuse_start`: «no -id and no SERVER_NAME»

old-sha256: 7efc220a772d2ebf9088c0a647cbb473152847345071b76707d355883f3c1d8c

<!-- req: P/01.3-R006 -->
```yaml
daemon:
  flags:   a closed set — the table «Daemon flags» below; -socket is removed: the socket path is one — -sockets (the store pilot, А3)
  refuse_start: -bootstrap with -join; group-size not from {1,3,5}; an address off the loopback without -tls; a door certificate at a voter; -door without -voters; no -id and no SERVER_NAME;
           no -dir; no -id with -join, -door or -group-size 3 | 5; with -door, -id is not equal to the server of its certificate (CN/SAN,
           C01-DOOR-ID-CN-01); a directory with an unfinished import/restore attempt (after the floor, before the phase «Done» of Н3;
           C01-UNFINISHED-IMPORT-WRITERS-01); the FORMAT mark is not its own (format below) — all start refusals: code 2
           (RestartPreventExitStatus=2 — a configuration error is not restarted; review of stage B 1–2, item 9)
  tuning:  lan — heartbeat 500 ms, elections 500 ms, leader lease 250 ms; the operator's word in configstore.env
group:
  sizes:   1 | 3 | 5 — the same on all servers
  join:    the daemon starts first, then joins: ask /v1/status, start with the partners, POST /v1/join;
           an even one — 409 refused without -force (with -force — a transitional state of reassembly); more than declared — 409 refused even with -force; member.json remembers the partners and how — a restart is not a joining
  leave:   leaving; one who left is not accepted back (403 / raft) until admit <id> on admin.sock of the leader
  identity: daemons — mTLS by certificates of the CA (CN configstore.<server>, SAN DNS <server>, URI urn:w2c:role:configstore);
           a certificate carries one role; -api and -join only with -tls; an additional transport secret — the implementation decides
leader_wait: 5 s from the loss of the leader (not per request) → 503 unavailable; a write gone to the leader without an answer → ambiguous (chapter 1.1)
sockets:   flat: <-sockets>/admin.sock and <-sockets>/<role>.sock, no subdirectories (the store pilot, А3);
           inherited ones (the sd_listen_fds protocol: LISTEN_FDS, LISTEN_FDNAMES) the daemon takes by FileDescriptorName=admin |
           <role>: the mode and the group were set by the unit (P/02.4 Н1.1); a name that is neither admin nor a role of the rights file — start refusal, code 2, the log
           names the name; a socket that was not passed, the daemon creates itself in -sockets: admin.sock 0600, <role>.sock 0660
           with the group of the process (the store pilot, А10);
           admin.sock 0600 (root; everything except never of chapter 1.2; not forwarded); <role>.sock 0660 the group of the role;
           a role header on a role socket → 403; forwarding to the leader is trusted only from a daemon of the group — a voter or a door without a vote — by the role in SAN (chapter 1.2 Н3)
door:      -door -id -voters a@h:p,…: without a vote; the same sockets and rights; to the leader or any voter (attempt 2 s, margin 1 s);
           the group membership — every 5 s; the row platform/configstore-doors/<id> {seen_at} every 30 s (not under platform/doors/ — there are the doors of servers, P/05 Н1.4);
           it is written by the door itself: by a request to the leader over mTLS with its own role configstore-door (forwarding of roles of chapter 1.2 Н3), by the command
           put of its own row without cas and guard, the only element seen_at; any other write from the role configstore-door, a batch op: batch included, — 403;
           a foreign batch the door forwards whole, in one request (chapter 1.1 Н3 «write batch»; ADR-0094 B9);
           «own» — <id> = the server from the verified certificate of the peer (CN configstore-door.<server> / SAN DNS); a claimed
           identity of the door (<id> of the key, the door name in the forwarding header) not equal to it — 403, nothing is written; Cmd.id
           of the replay memory (P/01.1) is not an identity, it is not compared with the server (C01-DOOR-ID-CN-01);
           the door does not touch admin.sock and does not forward its requests (log of cammeta-go, lesson 11 № 3); it is counted in
           configstore_doors while its row reads in its own form and seen_at in it is not older than 3 × 30 s by the clock of the voter
           that gives the series (C01-DOORS-COUNT-FRESH-01, the Architect's decision of 2026-10-30; where and by whose clock — metrics below); a door row that does not read in its own form is not counted as a visible door — the reason goes to the log
           of the leader without the value (В7 item 3, the Architect's decision of 2026-10-28, П1; row 5 of the list); all voters unreachable → 503 unavailable; it does not do join/leave
format:    in -dir — the file FORMAT, a JSON object {format, version, impl} (string, integer, string): format and version — the on-disk format
           of this implementation, impl — the name of the implementation, only for the log; the daemon writes it first into an empty directory
           (tmp + rename), before any other write; start: the directory is empty → write FORMAT; format and version are those that
           this build reads → start; otherwise (the directory is not empty but there is no FORMAT; foreign format or version; FORMAT out of
           form) → start refusal, code 2, the log names the directory and the mark found; nothing is written to or
           removed from the directory. A change of implementation — only by a copy (copy below) into a fresh directory (the store pilot, А1)
copy:      the backup copy and the import/restore input — one format for all implementations, JSON Lines: UTF-8, a line is one
           JSON object, the line end is LF; the first line is the header
           {"format": "w2c-configstore-copy", "version": 1, "index": <version>}: index — the version of the store (Version of chapter 1.1)
           at which the copy is taken, not smaller than the index of any row of the copy; then — a line per key: {key, items, index}
           (items and index — as Row of chapter 1.1) or {key, items: null, index, unreadable: true} — a damaged row as
           read (Row of chapter 1.1); the writer puts the keys in ascending order of UTF-8 bytes, the reader does not require an order;
           platform/epoch_floor is an ordinary row; the id replay memory (chapter 1.1 Н3) is not part of the copy; the copy knows no manifests —
           rows of any families, a family check at import is not needed (import below);
           another format or version, an extra or a missing field, a line not JSON or not by Row, a repeated key, an index
           of a row higher than the index of the header — a refusal of the whole input before the first write (Н4); an unreadable row in the input — also
           a refusal (Н4). A copy of one implementation is restored by another (the store pilot, А2)
batch:     a batch (chapter 1.1 Н3 «write batch») — one raft log record: applied on all servers whole, it has one version and
           one admission time; on a box (`box` below) and in the store `file://` — the atomicity property of the same chapter, the way — chapter 1.1
           «Implementation decides» item 3 (ADR-0094 addendum (12) item 2); the copy copy is taken between batches, it carries no half of a batch
admission: the admission time of a record (chapter 1.1 Н3 «Admission time») — in every raft log record and in the raft snapshot together with
           the rows: the snapshot carries the admission time of the last record that entered it, and a daemon raised from the snapshot continues from
           it; on a box (`box` below) — in the data directory with the same barrier as the rows. The copy copy does not carry it
           (chapter 1.1 Н3). admission_ahead — in /v1/status of the leader (and of a box): by how many seconds the admission time of the last
           record is ahead of its clock, if more than CLOCK_SKEW 60 s (chapter 1.1 Н0 «Cluster clocks»); otherwise there is no field; a
           follower and a door without a vote have no field. While the flag stands, writes with not_after by the writers' clocks get
           expired — the leader's clock went ahead and came back (ADR-0091 item 1)
durability: there is no environment variable or operational flag that turns off the durability barriers (chapter 1.1 «Implementation decides»
           item 3); an acceptance stand that needs speed says so by a flag of its «Stand» command
           (the common acceptance README), the units of P/02.4 Н1.1 do not set it; a teaching store without durability names this in its
           description («Implementation decides» item 2) (the store pilot, А10)
admin_ops: status | join [-force] | leave [id] | admit <id> | backup <file> (0600, tmp + rename) | restore --from [-force]
           | import --from <copy> [-index-base N] [-force] | recover -id -dir -peers … -isolated [-upper N] [-force] | rights [-groups]
           import/restore/floor in a group (raft) — only on admin.sock of the leader, before the first row; on a box (`box` below) —
           into a fresh directory of a stopped daemon; recover — locally on a stopped daemon (there is no leader,
           no majority — Н3 «recover»), not through a socket; status/backup/leave of oneself — at any;
           backup <file>: the file path (after resolving links) outside -dir of the daemon, otherwise a refusal before writing, code ≠ 0, the data
           directory untouched: a copy into the own log of a live daemon spoils it (reconciliation of python and go М10/6–11, B8);
           import into a directory where a former import has already finished (Н3 phase «Done») — a refusal, code ≠ 0, nothing changes;
           an unfinished attempt is continued by a replay (import below) (reconciliation of python and go М10/6–11, B12)
floor:                                        # platform/epoch_floor {floor, generation_at}
  generation: max((upper >> 32) + 1, whole hours of UTC since 2026-01-01); floor = generation << 32;
              upper — the maximum of floor of the row platform/epoch_floor and epoch of every row <sub>/epoch/<id> (P/03.2 Н1.5)
              in the whole verified input and in the saved state of the daemon (a fresh group has none); not a single row — 0;
              example at 2026-10-17T12:30Z (6948 whole hours): upper 5 → generation max(1, 6948) = 6948, floor 29841432772608;
              upper 30064771072005 (7000 << 32 | 5) → generation max(7001, 6948) = 7001, floor 30069066039296;
              the operator must confirm that the former installation handed out nothing above upper (for example, a copy after
              the writers were stopped);
              upper ≥ the current floor and all saved epochs. No reliable bound of the lost tail — a refusal of recovery
  when:    restore, import — before the first row: in a group only op: floor on admin.sock of the leader, on a box — as the first write
           into the directory of a stopped daemon (`box`); recover — locally in the dump of a stopped
           daemon (no socket, Н3 «recover» step 1); the row is not
           written by put/delete; it only grows; a clock earlier than generation_at → a refusal without -force; force allows only
           the clock going back, but not a repeat/lowering of the generation, a uint64 overflow or a parallel recovery
  form:    floor in op: floor — a JSON integer without a fraction or an exponent (`20`, not `2.0e1` and not `20.0`), 1 … 2^53 − 2^32; otherwise — 400
           badrequest before writing (reconciliation of python and go М10/6–11, B5); epochs are JSON integers < 2^53 (ADR-0070), so the floor
           leaves 2^32 numbers above itself: generation ≤ 2^21 − 1 (hours since 2026-01-01 suffice for ~239 years); a generation
           that would give more — a refusal of recovery, as an overflow (added by the pilot of data family schemas, Д6)
  issue:   next_epoch = max(current, floor) + 1 (P/03.2); an issue that read the floor before the raise can write a number
           below floor — the worker does not start such an epoch: a confirmation after the write (P/03.2 Н3 «take_epoch(id)»; added
           by the Quint pilot, F1)
import:    from an immutable copy (copy above) into a fresh group — not a single row, except the rows of doors without a vote
           platform/configstore-doors/<id> (service rows of the group itself, `door` above: a live door writes its own every 30 s —
           it does not cancel the freshness; during the transfer its write, like those of ordinary writers, waits for «Done»; a door row in the input
           is transferred like a row of any family, and the live door rewrites its own; new versions — higher than any version in the group,
           of door rows too; C01-IMPORT-DOOR-ROWS-01): transferred rows keep the versions of the copy (index of the input row), restore —
           the same; -index-base ≥ the greatest version of the input — the start of new versions: every write after the transfer gets a version
           above the base and above any version of the group (C01-IMPORT-VERSIONS-01); the versions of the copy were not handed out by the group and can coincide with
           a version handed out in the fresh group before the transfer (there are only door rows there): for a door row the version can return
           lower — no harm, the door writes its row without cas and within 30 s rewrites it above the base (C01-VERSION-ISSUED-01); -index-base ≥ the greatest version; a full preliminary
           check before changing the floor/any row: the copy form (a Row line, the key by chapter 1.1 Н1, the size not above the row
           ceiling), the versions (the base, index of the header) and the epochs — a row <s>/epoch/<id> with epoch not a decimal integer or
           platform/epoch_floor with floor not decimal, an epoch or floor row unreadable (outcomes of the families epoch, epoch_floor) — upper is not
           reliable, a refusal of the whole input (В7 item 3, the Architect's decision of 2026-10-28, row 13 of the list); the copy knows no manifests: import does not check
           the families of rows, a row of any family is transferred (log of cammeta-go, lesson 11 № 10). A bad row, size, base,
           epoch — without changes.
           After the floor is published a refusal can leave part of the rows; a replay continues the same attempt with the same floor,
           a new attempt — a new generation. Ordinary writers are not admitted until completion: the daemon does not
           start on such a directory (code 2, the log — repeat import with the same input), the store file:// in the process answers writes and reads with
           503 unavailable, the directory does not change (C01-UNFINISHED-IMPORT-WRITERS-01)
metrics:   configstore_raft_term, _state{state}, _elections_total, _index{kind=last|commit|applied}, _last_contact_seconds,
           _voters, _voters_expected, configstore_doors; configstore_doors is given by every voter — the leader and a follower — by its own
           replica of the rows and its own clock, without asking the leader (with an unreachable leader the series is the same); a door without a vote holds no replica
           of the rows and does not give the series configstore_doors (C01-DOORS-COUNT-PLACE-01, as the witness);
           a door without a vote is not a raft member: it gives no series configstore_raft_* and configstore_doors (otherwise dashboards would count it as a
           member of the group); its series are configstore_door_forwards_total{outcome=answered|unavailable|ambiguous} (counter:
           requests that it passed to the group, by outcome: answered — an answer of a voter was received, with any code; unavailable —
           no voter was reached, the door answered 503 unavailable; ambiguous — the write was sent, there is no answer, 503
           ambiguous) and configstore_door_voters_reachable (gauge: the voters that answered its last membership poll, once per 5 s)
           (C01-DOOR-METRICS-01, the Architect's decision of 2026-10-30, the meaning and the type — as the witness); alarms of the voters: membership ≠ declared, a follower lagging > 1000, more than 3 elections in 10 min
box:       the store of a box — a build without raft, one voter: -group-size 3 or 5, -join and -door — a start refusal with code 2
           («this build has no raft»); /v1/status — state Leader, term 1, leader — its -api address (empty without -api),
           leader_id — its id, voters [<id>],
           members {<id>: <api>} (without -api — {}, C01-STATUS-MEMBERS-NOAPI); /metrics — the series above with the values of one member (term 1, elections_total 1, last_contact 0,
           voters 1, voters_expected 1, doors 0); join of its own id — 200 {}, of a foreign one — 409 refused even with -force; leave — 409 refused
           («the last voter»); admit — a refusal, code ≠ 0; recover — a refusal, code 2 («this build has no raft»): a box has no
           group, there is nothing to recover it with, a copy — import (reconciliation of python and go М10/6–11, B15); import/restore on a box — into a fresh directory of a stopped daemon,
           not through admin.sock (in a group — admin.sock of the leader, `admin_ops` above): the floor as the first write, then the rows; restore
           coincides with import (there are no neighbours); forwarding from the role configstore-door on -api of a box — 403 (P/01.2 box: there are no trusted forwarding senders;
           a door without a vote — only in a build with raft; C01-BOX-DOOR-01)
repeat:    membership operations are repeatable: admit of an already admitted correct id — code 0, the membership and the rows do not change; a repeated join
           of the same id with the same Raft address — updates the API address; join of an id with another Raft address and leave of an unknown id —
           409 refused, without changes (guess of stage C CL-03, the Architect's decision of 2026-10-23)
```

### `Platform/01-store/spec/01.3-store.norms.md` P/01.3-R029 — Н4 row 6: «no `-id` and no `SERVER_NAME`»

old-sha256: f2816d7cfea0c4ecb74739cc60b46b723f7760c571099b7d25df0f4fe2659444

<!-- req: P/01.3-R029 -->
The catalogue of these refusals — [`forms/refusals.tsv`](../forms/refusals.tsv) (ADR-0125: code, kind, fields, norm by the rows of this table); `check_spec` checks that it agrees with this table, with the OpenAPI `*Fault` and with `forms/write-checks.tsv`.

| Cause | Outcome | Words | What the operator does |
|---|---|---|---|
| service HTTP: unknown fields, not an object/not JSON, extra JSON, bad framing/truncation/read timeout, an inadmissible field | 400 | BadRequestFault of chapter 1.1, Н2 | fix the input; there is no side change |
| service HTTP: a POST body larger than 1 MiB | 413 | BodyTooLargeFault of chapter 1.1 | shrink the body; the limit is by actual bytes |
| service HTTP: no route | 404 | BadRequestFault of chapter 1.1 | fix the path |
| a wrong method of status/join/leave/metrics | 405 | BadRequestFault of chapter 1.1, Н2 | fix the method; for /v1/write and /v1/rights an unknown method gives 404 by their owners, chapters 1.1 and 1.2 |
| daemon: `-bootstrap` with `-join`; a size not 1/3/5; an address off the loopback without `-tls`; a door certificate at a voter | does not start, code 2 | log | fix `configstore.env` |
| daemon: no `-dir`; no `-id` in a group; no `-id` and no `SERVER_NAME`; `-door` without `-voters`; a flag outside the table «Daemon flags»; an inherited socket with a name that is neither `admin` nor a role of the rights file (Н1.3) | does not start, code 2 | the log names the flag or the socket name | fix the unit or `configstore.env` |
| the data directory is not empty but there is no mark `FORMAT`; foreign `format` or `version`; `FORMAT` out of form (Н1.3 `format`) | does not start, code 2; nothing is written to or removed from the directory | log: the directory and the mark found | take a copy with the former implementation (`backup`) and restore it into a fresh directory |
| the store of a box without raft (Н1.3 `box`): `-group-size 3` or `5`, `-join`, `-door` (C01-BOX-DOOR-01) | does not start, code 2 | «this build has no raft» | take a build with raft |
| box: `leave` of the last voter; `admit` | 409 `refused` / code ≠ 0 | «the last voter» | — |
| a joining makes the group even or larger than declared | 409 `refused` | `{kind: refused, error}` | `-force` only for a transitional evenness, not beyond the maximum |
| a joining of one who left, without `admit` | 403 | ForbiddenFault of chapter 1.1 (Н2 `POST /v1/join`) | `configstore admit <id>` at the leader |
| `join`/`leave` from a role socket | 403 `forbidden` | ForbiddenFault of chapter 1.1 | only `admin.sock` or a daemon of the group (B1) |
| `backup` to a file inside `-dir` of the daemon | a refusal before writing, code ≠ 0 | log: the path and the data directory | a file outside the data directory (B8) |
| a repeated `import` after a finished one | a refusal, code ≠ 0, without changes | phase «Done» | — (B12) |
| `recover` on a box without raft | not performed, code 2 | «this build has no raft» | a copy and `import` (B15) |
| `op: floor`: `floor` is not a JSON integer (`2.0e1`, `20.0`) | 400 `badrequest` | chapter 1.1 Н4 | an integer (B5) |
| no leader for 5 s | 503 `unavailable` | — | wait; workers live by the lease |
| the leader is lost after a write is sent | 503 `ambiguous` | — | a replay with the same `id` (chapter 1.1) |
| more connections than the limit | 503 `unavailable`, `Retry-After: 1` (chapter 1.1 Н4; the write is not done) | — | repeat not before the deadline |
| `floor` not by admin | 403 `forbidden` | chapter 1.2 | — |
| `floor` not higher than the current one (a new id) | 409 `refused` | chapter 1.1 Н4 | — |
| `put`/`delete` of the floor row by an ordinary write | 403 `forbidden` | chapter 1.2 Н1.3 `never` | only `op: floor` |
| `import`/`restore`: the input is not in the form `copy` of Н1.3; the base is smaller than the greatest version; a row larger than 512 KiB; an epoch or the floor is not decimal; unreadable (including a row `<sub>/epoch/<id>` or `platform/epoch_floor` — upper is not reliable; В7 item 3, the Architect's decision of 2026-10-28, row 13 of the list) | a refusal as a whole before the first write | words | another base / fix the copy |
| `recover`/`restore`: a clock earlier than `generation_at` | a refusal | phase/cause | `-force` removes only the clock refusal; the upper bound/isolation/monotonicity are required |
| recovery: upper unknown, the old group not cut off, an overflow | a refusal before changes | phase/cause | restore the preconditions; force does not help |
| `recover` without `-isolated` (Н3 step 0; guess of stage C S02, the Architect's decision of 2026-10-23) | a refusal before changes, code ≠ 0 | log: «-isolated» | isolate the former group and the writers, repeat with `-isolated` |
| `recover -upper N`: N is not an integer 0 … 2^53 − 1 or is below the computed upper | a refusal before changes, code ≠ 0 | log: the computed upper and N | check the bound; `-upper` only raises |
| `recover -peers`: an element not `id@<raft host:port>/<api host:port>`, an empty element, a repeated id or no `-id` among them (Н1.3 «Daemon flags» `-peers`; guess of stage C S03) | a refusal before changes, code ≠ 0 | log: the element and the cause | fix the list |

## REMOVED

(none)
