# Delta 0129-z10-p01-format-floor — one current FORMAT and concrete floor bounds

change: 0129-z10-p01-format-floor rev 1. Base d034aa09e6dcad450cd4e0942457f430dda43ece; lesson delta_base 725653954. Unit normalization: LF, strip trailing spaces, one final LF. Minimal MODIFIED set follows the existing anchored P01 source partitions; no new or replacement requirement IDs. This is a review bundle, not an applied delta.

Authority: ADR-0129 (23); SOURCE-A activation f935cd4ba9af3dc4be90527013a6760a89f5a692b3c4c3eeb9fc7c7602f87817 and exact mirror adjustment de4ba859f34da6e34063ecf69ea0de2c084196528cc978cc96abf4426ba3fb9a.

## ADDED

(none)

## MODIFIED

### `Platform/01-store/spec/01.3-store.norms.md` P/01.3-R006

old-sha256: b5b149af08939eaa00968d5985e5295ba4573a63d74e7096114d9339f6866a4c

<!-- req: P/01.3-R006 -->
```yaml
daemon:
  flags:   a closed set — forms/daemon-flags.tsv; -socket is removed: the socket path is one — -sockets (the store pilot, A3)
  refuse_start: -bootstrap with -join; group-size not from {1,3,5}; an address off the loopback without -tls; a door certificate at a voter; -door without -voters; no -id and no SERVER_NAME;
           no -dir; no -id with -join, -door or -group-size 3 | 5; with -door, -id is not equal to the server of its certificate (CN/SAN,
           C01-DOOR-ID-CN-01); a directory with an unfinished import/restore attempt (after the floor, before the phase «Done» of N3;
           C01-UNFINISHED-IMPORT-WRITERS-01); the FORMAT mark is not its own (format below) — all start refusals: code 2
           (RestartPreventExitStatus=2 — a configuration error is not restarted; review of stage B 1–2, item 9)
  tuning:  lan — heartbeat 500 ms, elections 500 ms, leader lease 250 ms; the operator's word in configstore.env
group:
  sizes:   1 | 3 | 5 — the same on all servers
  join:    the daemon starts first, then joins: ask /v1/status, start with the partners, POST /v1/join;
           an even one — 409 refused without -force (with -force — a transitional state of reassembly); more than declared — 409 refused even with -force; member.json remembers the partners and how — a restart is not a joining
  leave:   leaving; one who left is not accepted back (403 / raft) until admit <id> on admin.sock of the leader
  identity: daemons — mTLS by certificates of the CA (CN configstore.<server>, SAN DNS <server>, URI urn:w2c:role:configstore);
           a certificate carries one role; -api and -raft on loopback may run without -tls (the local box); outside loopback they require -tls; -join always requires -tls (group traffic); an additional transport secret — the implementation decides
leader_wait: the effective -leader-wait interval from the loss of the leader (not per request) → 503 unavailable; a write gone to the leader without an answer → ambiguous (chapter 1.1)
sockets:   flat: <-sockets>/admin.sock and <-sockets>/<role>.sock, no subdirectories (the store pilot, A3);
           inherited ones (the sd_listen_fds protocol: LISTEN_FDS, LISTEN_FDNAMES) the daemon takes by FileDescriptorName=admin |
           <role>: the mode and the group were set by the unit (P/02.4 N1.1); a name that is neither admin nor a role of the rights file — start refusal, code 2, the log
           names the name; a socket that was not passed, the daemon creates itself in -sockets: admin.sock 0600, <role>.sock 0660
           with the group of the process (the store pilot, A10);
           admin.sock 0600 (root; everything except never of chapter 1.2; not forwarded); <role>.sock 0660 the group of the role;
           a role header on a role socket → 403; forwarding to the leader is trusted only from a daemon of the group — a voter or a door without a vote — by the role in SAN (chapter 1.2 N3)
door:      -door -id -voters a@h:p,…: without a vote; the same sockets and rights; to the leader or any voter (attempt DOOR_REQUEST_TIMEOUT, margin DOOR_REQUEST_MARGIN);
           the group membership — every DOOR_MEMBERS_EVERY; the row platform/configstore-doors/<id> {seen_at} every DOOR_SEEN_EVERY (not under platform/doors/ — there are the doors of servers, P/05 N1.4);
           it is written by the door itself: by a request to the leader over mTLS with its own role configstore-door (forwarding of roles of chapter 1.2 N3), by the command
           put of its own row without cas and guard, the only element seen_at; any other write from the role configstore-door, a batch op: batch included, — 403;
           a foreign batch the door forwards whole, in one request (chapter 1.1 N3 «write batch»; ADR-0094 B9);
           «own» — <id> = the server from the verified certificate of the peer (CN configstore-door.<server> / SAN DNS); a claimed
           identity of the door (<id> of the key, the door name in the forwarding header) not equal to it — 403, nothing is written; Cmd.id
           of the replay memory (P/01.1) is not an identity, it is not compared with the server (C01-DOOR-ID-CN-01);
           the door does not touch admin.sock and does not forward its requests (log of cammeta-go, lesson 11 № 3); it is counted in
           configstore_doors while its row reads in its own form and seen_at in it is not older than DOOR_SEEN_PERIODS × DOOR_SEEN_EVERY by the clock of the voter
           that gives the series (C01-DOORS-COUNT-FRESH-01, the Architect's decision of 2026-10-30; where and by whose clock — metrics below); a door row that does not read in its own form is not counted as a visible door — the reason goes to the log
           of the leader without the value (V7 item 3, the Architect's decision of 2026-10-28, P1; row 5 of the list); all voters unreachable → 503 unavailable; it does not do join/leave
format:    in -dir — the file FORMAT, a JSON object {format, version, impl} (string, integer, string): the implementation
           chooses the name and one current version of its internal format. This build writes and reads only that version;
           impl names the implementation and is used only in the log. In an empty directory write the mark atomically (tmp + rename) first, before
           any other write. At start the name and version equal this build's current pair — start; a non-empty unmarked
           directory, foreign or former version, or malformed mark — the existing start refusal, code 2, without writing
           or removing data. No converter or former internal version reader is required. The current portable copy/version=1
           below is unchanged.

           The refusal log names the directory and found mark. A change between current implementations uses the current portable copy into a fresh directory; preserve the original directory.
copy:      the backup copy and the import/restore input — one format for all implementations, JSON Lines: UTF-8, a line is one
           JSON object, the line end is LF; the first line is the header
           {"format": "w2c-configstore-copy", "version": 1, "index": <version>}: index — the version of the store (Version of chapter 1.1)
           at which the copy is taken, not smaller than the index of any row of the copy; then — a line per key: {key, items, index}
           (items and index — as Row of chapter 1.1) or {key, items: null, index, unreadable: true} — a damaged row as
           read (Row of chapter 1.1); the writer puts the keys in ascending order of UTF-8 bytes, the reader does not require an order;
           platform/epoch_floor is included as an ordinary input row for upper and the generation_at clock check, but is not transferred; the id replay memory (chapter 1.1 N3) is not part of the copy; the copy knows no manifests —
           rows of any families, a family check at import is not needed (import below);
           another format or version, an extra or a missing field, a line not JSON or not by Row, a repeated key, an index
           of a row higher than the index of the header — a refusal of the whole input before the first write (N4); an unreadable row in the input — also
           a refusal (N4). A copy of one implementation is restored by another (the store pilot, A2)
batch:     a batch (chapter 1.1 N3 «write batch») — one raft log record: applied on all servers whole, it has one version and
           one admission time; on a box (`box` below) and in the store `file://` — the atomicity property of the same chapter, the way — chapter 1.1
           «Implementation decides» item 3 (ADR-0094 addendum (12) item 2); the copy copy is taken between batches, it carries no half of a batch
admission: the admission time of a record (chapter 1.1 N3 «Admission time») — in every raft log record and in the raft snapshot together with
           the rows: the snapshot carries the admission time of the last record that entered it, and a daemon raised from the snapshot continues from
           it; on a box (`box` below) — in the data directory with the same barrier as the rows. The copy copy does not carry it
           (chapter 1.1 N3). admission_ahead — in /v1/status of the leader (and of a box): by how many seconds the admission time of the last
           record is ahead of its clock, if more than CLOCK_SKEW (chapter 1.1 N0 «Cluster clocks»); otherwise there is no field; a
           follower and a door without a vote have no field. While the flag stands, writes with not_after by the writers' clocks get
           expired — the leader's clock went ahead and came back (ADR-0091 item 1)
durability: there is no environment variable or operational flag that turns off the durability barriers (chapter 1.1 «Implementation decides»
           item 3); an acceptance stand that needs speed says so by a flag of its «Stand» command
           (the common acceptance README), the units of P/02.4 N1.1 do not set it; a teaching store without durability names this in its
           description («Implementation decides» item 2) (the store pilot, A10)
admin_ops: status | join [-force] | leave [id] | admit <id> | backup <file> (0600, tmp + rename) | restore --from [-force]
           | import --from <copy> [-index-base N] [-force] | recover -id -dir -peers … -isolated [-upper N] [-force] | rights [-groups]
           import/restore/floor in a group (raft) — only on admin.sock of the leader, before the first row; on a box (`box` below) —
           into a fresh directory of a stopped daemon; recover — locally on a stopped daemon (there is no leader,
           no majority — N3 «recover»), not through a socket; status/backup/leave of oneself — at any;
           backup <file>: the file path (after resolving links) outside -dir of the daemon, otherwise a refusal before writing, code ≠ 0, the data
           directory untouched: a copy into the own log of a live daemon spoils it (reconciliation of python and go M10/6–11, B8);
           import into a directory where a former import has already finished (N3 phase «Done») — a refusal, code ≠ 0, nothing changes;
           an unfinished attempt is continued by a replay (import below) (reconciliation of python and go M10/6–11, B12)
floor:                                        # platform/epoch_floor {floor, generation_at}
  generation: max((upper >> 32) + 1, whole hours of UTC since 2026-01-01); floor = generation << 32;
              upper — the maximum of floor of the row platform/epoch_floor and epoch of every row <sub>/epoch/<id> (P/03.2 N1.5)
              in the whole verified input and in the saved state of the daemon (a fresh group has none); not a single row — 0;
              example at 2026-10-17T12:30Z (6948 whole hours): upper 5 → generation max(1, 6948) = 6948, floor 29841432772608;
              upper 30064771072005 (7000 << 32 | 5) → generation max(7001, 6948) = 7001, floor 30069066039296;
              the operator must confirm that the former installation handed out nothing above upper (for example, a copy after
              the writers were stopped);
              upper ≥ the current floor and all saved epochs. No reliable bound of the lost tail — a refusal of recovery
  when:    restore, import — before the first row: in a group only op: floor on admin.sock of the leader, on a box — as the first write
           into the directory of a stopped daemon (`box`); recover — locally in the dump of a stopped
           daemon (no socket, N3 «recover» step 1); the row is not
           written by put/delete; it only grows; a clock earlier than generation_at → a refusal without -force; force allows only
           the clock going back, but not a repeat/lowering of the generation, a uint64 overflow or a parallel recovery
  form:    floor in op: floor — a JSON integer without a fraction or an exponent (`20`, not `2.0e1` and not `20.0`), 1 … 2^53 − 2^32; otherwise — 400
           badrequest before writing (reconciliation of python and go M10/6–11, B5); epochs are JSON integers < 2^53 (ADR-0070), so the floor
           leaves 2^32 numbers above itself: generation ≤ 2^21 − 1 (hours since 2026-01-01 suffice for ~239 years); a generation
           that would give more — a refusal of recovery, as an overflow (added by the pilot of data family schemas, D6)
  issue:   next_epoch = max(current, floor) + 1 (P/03.2); an issue that read the floor before the raise can write a number
           below floor — the worker does not start such an epoch: a confirmation after the write (P/03.2 N3 «take_epoch(id)»; added
           by the Quint pilot, F1)
import:    from an immutable copy (copy above) into a fresh group — not a single row, except the rows of doors without a vote
           platform/configstore-doors/<id> (service rows of the group itself, `door` above: a live door writes its own every DOOR_SEEN_EVERY —
           it does not cancel the freshness; during the transfer its write, like those of ordinary writers, waits for «Done»; a door row in the input
           is transferred like a row of any family, and the live door rewrites its own; new versions — higher than any version in the group,
           of door rows too; C01-IMPORT-DOOR-ROWS-01): transferred rows keep the versions of the copy (index of the input row), restore —
           the same; -index-base ≥ the greatest version of the input — the start of new versions: every write after the transfer gets a version
           above the base and above any version of the group (C01-IMPORT-VERSIONS-01); the versions of the copy were not handed out by the group and can coincide with
           a version handed out in the fresh group before the transfer (there are only door rows there): for a door row the version can return
           lower — no harm, the door writes its row without cas and within 30 s rewrites it above the base (C01-VERSION-ISSUED-01); -index-base ≥ the greatest version; a full preliminary
           check before changing the floor/any row: the copy form (a Row line, the key by chapter 1.1 N1, the size not above the row
           ceiling), the versions (the base, index of the header) and the epochs — a row <s>/epoch/<id> with epoch not a decimal integer or
           platform/epoch_floor with floor not decimal, an epoch or floor row unreadable (outcomes of the families epoch, epoch_floor) — upper is not
           reliable, a refusal of the whole input (V7 item 3, the Architect's decision of 2026-10-28, row 13 of the list); the copy knows no manifests: import does not check
           the families of rows, a row of any family is transferred (log of cammeta-go, lesson 11 № 10). A bad row, size, base,
           epoch — without changes.
           Transfer excludes the input platform/epoch_floor: the first write is the new floor F1, with its new index and generation_at at that raise; then all other input rows keep their copy versions.
           Completeness is every input row except that old floor, plus the new floor row; a partial replay preserves the exact saved F1 row (items and index), never copies back the old floor or raises F1 again.
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
           ambiguous) and configstore_door_voters_reachable (gauge: the voters that answered its last membership poll, once per DOOR_MEMBERS_EVERY)
           (C01-DOOR-METRICS-01, the Architect's decision of 2026-10-30, the meaning and the type — as the witness); alarms of the voters: membership ≠ declared, a follower lagging > RAFT_LAG_ALARM, more than RAFT_ELECTION_ALARM_COUNT elections in RAFT_ELECTION_ALARM_WINDOW
box:       the store of a box — a build without raft, one voter: -group-size 3 or 5, -join and -door — a start refusal with code 2
           («this build has no raft»); /v1/status — state Leader, term 1, leader — its -api address (empty without -api),
           leader_id — its id, voters [<id>],
           members {<id>: <api>} (without -api — {}, C01-STATUS-MEMBERS-NOAPI); /metrics — the series above with the values of one member (term 1, elections_total 1, last_contact 0,
           voters 1, voters_expected 1, doors 0); join of its own id — 200 {}, of a foreign one — 409 refused even with -force; leave — 409 refused
           («the last voter»); admit — a refusal, code ≠ 0; recover — a refusal, code 2 («this build has no raft»): a box has no
           group, there is nothing to recover it with, a copy — import (reconciliation of python and go M10/6–11, B15); import/restore on a box — into a fresh directory of a stopped daemon,
           not through admin.sock (in a group — admin.sock of the leader, `admin_ops` above): the floor as the first write, then the rows; restore
           coincides with import (there are no neighbours); forwarding from the role configstore-door on -api of a box — 403 (P/01.2 box: there are no trusted forwarding senders;
           a door without a vote — only in a build with raft; C01-BOX-DOOR-01)
repeat:    membership operations are repeatable: admit of an already admitted correct id — code 0, the membership and the rows do not change; a repeated join
           of the same id with the same Raft address — updates the API address; join of an id with another Raft address and leave of an unknown id —
           409 refused, without changes (guess of stage C CL-03, the Architect's decision of 2026-10-23)
```

Fixed `DOOR_*` and `RAFT_*` numeric limits are owned only by [runtime-constants.tsv](../forms/runtime-constants.tsv). The effective `-leader-wait` and connection-limit defaults are owned by [daemon-flags.tsv](../forms/daemon-flags.tsv).

### `Platform/01-store/spec/01.3-store.norms.md` P/01.3-R011

old-sha256: f7c3c52c4e0840b2a88f6f58b83947df1b51a8c7c3bb505d1029c8ae95d162c2

<!-- req: P/01.3-R011 -->
```yaml
roles:        configstore, configstore-door (with -tls for group traffic and every non-loopback -api/-raft; local loopback box doors may run without -tls)
raft:         on -raft only a leaf of the role configstore is accepted; a leaf of another role (configstore-door and others) — a refusal in
              the handshake (TLS alert), the raft stream is not opened, as with doors that judge the client certificate in the handshake
              (the role certificate contract); on -api — both roles of the daemon (C01-RAFT-DOOR-LEAF-01, the Architect's decision of 2026-10-30)
counts:       the count of invalid rereads of revoked/crl.pem and of stale CRLs (the revoke contract) — lines of the daemon log, there are no
              /metrics series (the list of N1.3 is closed; C01-TLS-COUNT-PLACE-01)
```

<!-- families:begin -->
### Data families (built from the standard files)

The form of the rows and objects that the chapter owns by the [catalog](../../common/data/catalog.tsv) is the JSON Schema 2020-12 of the family (ADR-0092). An instance of a row is `{key, row}`, of an object `{key, object}`; the key is the grammar of the column `key` of the catalog. The fields of `row` are the values of `items` after the [codec](../../common/data/codec.tsv): the writer checks the schema and its `$defs.writer`, the reader the schema (layer 3 — the words `x-*` of the schema). Unreadable — the row did not decode or did not pass the schema in the reader's mode; the outcome is by the table of outcomes of the family: the path is a prefix of the path of the refusal (empty — the whole row); with several paths of refusal the outcome of the least priority applies.

#### `platform/epoch_floor` — row

Schema — [`epoch_floor.schema.json`](../data/epoch_floor.schema.json), outcomes — [`epoch_floor.outcomes.tsv`](../data/epoch_floor.outcomes.tsv); form version 1; norm — P/01.3 N1.3 floor, P/03.2 N1.5.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `floor` | integer; ≥ 1; ≤ 9007194959773696; the whole sign for the reader too (x-whole) | required |  | the lower bound of issue after a restore; generation << 32 |
| `generation_at` | time (P/01.1 N0 «Time in a row») | required |  | the moment the floor was raised — the wall clock of the raiser at that moment, not the admission time of the log record (it may run ahead of clocks; C01-GENERATION-AT-WALL-01) |

Outcomes of an unreadable row (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| `/floor` | * | epoch issue: the issue is refused, the floor is not replaced by 0; lease confirmation: fenced; import, restore: the whole input is refused, nothing changes | 0 | row | P/03.2 N3 «take_epoch(id)», «confirm»; P/01.3 N1.3 import, N4 |
| `/generation_at` | * | epoch issue and lease confirmation do not read the field — they issue and confirm by the floor; import, restore: the whole input is refused, nothing changes (the current behaviour of both implementations; the norm does not name the outcome) | 1 | field | P/01.3 N3 «recover the store» |
| the whole row | `<s>worker` | the whole row is unreadable: epoch issue — the issue is refused, the floor is not replaced by 0; lease confirmation — fenced | 2 | row | P/03.2 N3 «take_epoch(id)», «confirm» |

#### `platform/configstore-doors/<id>` — row

Schema — [`configstore-doors.schema.json`](../data/configstore-doors.schema.json), outcomes — [`configstore-doors.outcomes.tsv`](../data/configstore-doors.outcomes.tsv); form version 1; norm — P/01.3 N1.3 door.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `seen_at` | time (P/01.1 N0 «Time in a row») | required |  | the wall time of the last confirmation of the door (every 30 s) |

Outcomes of an unreadable row (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole row | `configstore-door` | the door row is unreadable — it does not count as a visible door (not in configstore_doors), the cause goes to the leader's log without the value (P1; V7 item 3, row 5) | 1 | row | P/01.3 N1.3 door |
<!-- families:end -->

### `Platform/01-store/spec/01.3-store.norms.md` P/01.3-R029

old-sha256: 44f5aa1885e09f5ace2bd397c149de37f906fda6c8a9e44b5677fccebc2cdbbd

<!-- req: P/01.3-R029 -->
The catalogue of these refusals — [`forms/refusals.tsv`](../forms/refusals.tsv) (ADR-0125): the form is the sole source of code, kind, fields, headers and log projection. The OpenAPI fault schemas and write-check order stay their owning forms; the causes, priority and caller actions below refer to stable refusal names, without duplicating the outcome cells.

- `service_body_form`: service HTTP: unknown fields, not an object/not JSON, extra JSON, bad framing/truncation/read timeout, an inadmissible field. Caller action: fix the input; there is no side change.
- `service_body_limit`: service HTTP: a POST body larger than `-max-body`. Caller action: shrink the body; the limit is by actual bytes.
- `service_no_route`: service HTTP: no route. Caller action: fix the path.
- `service_method`: a wrong method of status/join/leave/metrics. Caller action: fix the method; for /v1/write and /v1/rights an unknown method gives 404 by their owners, chapters 1.1 and 1.2.
- `start_config`: daemon: `-bootstrap` with `-join`; `-group-size` outside its form; an address off the loopback without `-tls`; a door certificate at a voter. Caller action: fix `configstore.env`.
- `start_flags`: daemon: no `-dir`; no `-id` in a group; no `-id` and no `SERVER_NAME`; `-door` without `-voters`; a flag outside the table «Daemon flags»; an inherited socket with a name that is neither `admin` nor a role of the rights file (N1.3). Caller action: fix the unit or `configstore.env`.
- `start_format`: the data directory is not empty but there is no mark `FORMAT`; foreign `format` or `version`; `FORMAT` out of form (N1.3 `format`). Caller action: preserve the original directory; use a fresh directory and an available current portable copy/version=1. Running a former implementation or reading its internal format is not required.
- `box_no_raft`: the store of a box without raft (N1.3 `box`): `-group-size 3` or `5`, `-join`, `-door` (C01-BOX-DOOR-01). Caller action: take a build with raft.
- `box_last_voter`, `box_admit`: box: `leave` of the last voter; `admit`. Caller action: —.
- `join_parity`: a joining makes the group even or larger than declared. Caller action: `-force` only for a transitional evenness, not beyond the maximum.
- `join_left`: a joining of one who left, without `admit`. Caller action: `configstore admit <id>` at the leader.
- `join_role_socket`: `join`/`leave` from a role socket. Caller action: only `admin.sock` or a daemon of the group (B1).
- `backup_inside_dir`: `backup` to a file inside `-dir` of the daemon. Caller action: a file outside the data directory (B8).
- `import_repeated`: a repeated `import` after a finished one. Caller action: — (B12).
- `recover_box`: `recover` on a box without raft. Caller action: a copy and `import` (B15).
- `floor_not_integer`: `op: floor`: `floor` is not a JSON integer (`2.0e1`, `20.0`). Caller action: an integer (B5).
- `no_leader`: no leader for the effective `-leader-wait` interval. Caller action: wait; workers live by the lease.
- `leader_lost`: the leader is lost after a write is sent. Caller action: a replay with the same `id` (chapter 1.1).
- `connection_limit`: more connections than the limit. Caller action: repeat not before the deadline.
- `floor_socket`: `floor` not by admin. Caller action: —.
- `floor_not_higher_id`: `floor` not higher than the current one (a new id). Caller action: —.
- `floor_row_write`: `put`/`delete` of the floor row by an ordinary write. Caller action: only `op: floor`.
- `copy_input`: `import`/`restore`: the input is not in the form `copy` of N1.3; the base is smaller than the greatest version; a row larger than `-max-value`; an epoch or the floor is not decimal; unreadable (including a row `<sub>/epoch/<id>` or `platform/epoch_floor` — upper is not reliable; V7 item 3, the Architect's decision of 2026-10-28, row 13 of the list). Caller action: another base / fix the copy.
- `clock_early`: `recover`/`restore`: a clock earlier than `generation_at`. Caller action: `-force` removes only the clock refusal; the upper bound/isolation/monotonicity are required.
- `recovery_unsafe`: recovery: upper unknown, the old group not cut off, an overflow. Caller action: restore the preconditions; force does not help.
- `recover_isolated`: `recover` without `-isolated` (N3 step 0; guess of stage C S02, the Architect's decision of 2026-10-23). Caller action: isolate the former group and the writers, repeat with `-isolated`.
- `recover_upper`: `recover -upper N`: N is out of the flag form or below the computed upper. Caller action: check the bound; `-upper` only raises.
- `recover_peers`: `recover -peers`: an element not `id@<raft host:port>/<api host:port>`, an empty element, a repeated id or no `-id` among them (N1.3 «Daemon flags» `-peers`; guess of stage C S03). Caller action: fix the list.

### `Platform/01-store/spec/01.3-store.norms.md` P/01.3-R030

old-sha256: 49e81dd556ba18c094143ab7fcd25af1afe9e3cdb2e1f1ae1a6994af22da1b3e

<!-- req: P/01.3-R030 -->
---

## N5 Acceptance

The directory [`../acceptance/3/`](../acceptance/3/README.md): the stand store ([the common acceptance README](../../common/acceptance/README.md)) with the stand's rights file, its service doors, a copy and a foreign directory; sc. 07, 17, 18, 25–29, 31 — the store group stand (several daemons on the loopback, the common acceptance README «Store group stand»; formerly sc. 07 was a drill `@manual`; work rules (for people) § 4). The scenario numbers are the former numbers of the acceptance of M10/11.

| № | Scenario | Norms |
|---|---|---|
| 04 | daemon metrics: `configstore_raft_term`, `configstore_raft_voters_expected` on `/metrics` of the store | N1.3 |
| 07 | a group of three: the joining of a fourth — 409 even with `force`; a door without a vote: `Door`, a write with the same rights file, the row `seen_at`, the series `configstore_doors`, `-id` not the server of the leaf — code 2, a foreign door row — 403; a forwarded admin with a loaded rights file — 403 (A08); a door leaf on `-raft` — a refusal by the handshake (C01-RAFT-DOOR-LEAF-01) | N1.3 `join`, `door`, `metrics`, `refuse_start` |
| 08 | a replay of `op: floor` with the same `id` after a store restart — the saved outcome (`again`); another floor with this `id` — 400; a floor not as an integer (`2.0e1`) — 400; a floor above the upper bound of N1.3 `floor.form`, including the greatest uint64 — 400; the upper bound itself is admissible (the pilot of data family schemas, D6) | N2, N1.3 floor |
| 10 | a second store instance on a foreign directory: a non-empty one without `FORMAT` and one with a foreign mark — code 2, the directory is byte for byte the same (`@foreign store`) | N1.3 `format`, N4 |
| 11 | copy: the input `inputs/copy-ok.jsonl` and the same without key order are transferred into a fresh directory, the rows read, the floor is raised; the `backup` copy of the stand store is transferred and carries the manifests (`@backup store`, `@import store`) | N1.3 `copy`, `import` |
| 12 | copy: one input per each `copy` refusal — another `format`, `version`, an extra field of the header, no header, an extra and a missing field of a row, not JSON, not Row, a repeated key, `index` above the header, `unreadable`, a row key not by chapter 1.1 N1, `generation_at` of the floor not a time, a clock earlier than `generation_at` of the floor of the input — `import` is refused, not a single row is transferred | N1.3 `copy`, `import`, `floor`, N4 |
| 14 | the `id` replay memory is not part of the copy: a write with `id` before `backup`, after `import` a replay of the same `id` — a new write without `again`, the next one — `again` (B10) | N1.3 `copy` |
| 15 | service doors, steps 1–8: `join`/`leave` from a role socket — 403; a body larger than the effective `-max-body` — 413, also with a foreign method, earlier than 405; empty `raft`/`api` — 400; `HEAD` — 405 and 404 (B1–B4) | N2 |
| 16 | a single member without `-api`: `/v1/status` — `state` `Leader`, `leader` empty, `members` — `{}` (C01-STATUS-MEMBERS-NOAPI) | N1.3 `-api`, `box`; N2 `GET /v1/status` |
| 17 | sizes 2 and 4 — code 2; the `/metrics` series of the leader and a follower (A10); `leave`/`admit`, a repeat of membership operations; a restart of a follower and of the whole group — the versions are the same; a leader change — a read sees the last write; a cut-off follower (`@cut`) does not give an old version; a door and one voter — 503 | N1.3 `group`, `leave`, `repeat`, `leader_wait`, `door`; P/01.1 N3 |
| 18 | `import` into a fresh group — the transferred rows keep the versions of the copy, `cas` by them passes, a repeat — a refusal; `recover` without `-isolated` and with a low `-upper` — a refusal, with `-isolated` — the floor above the upper of the epoch row; new members join | N1.3 `import`, `floor`, `admin_ops`; N3 «recover the store» |
| 19 | the version after a daemon restart: the former row reads with the former version, two new writes — the versions are pairwise different (coverage audit P/01, A01) | P/01.1 N1 `index`; N1.3 `durability` |
| 20 | a damage of a row bypassing the door (`@spoil row`): `{items: null, index, unreadable: true}`, a listing — the name and the version, `cas` by it replaces; the loss of the version (`@spoil row-index`) — 503 for a read and a listing (A05; C01-ROW-INDEX-LOST-01) | P/01.1 N2, «Implementation decides» item 5 |
| 21 | the `id` replay memory (P/01.1 N3) holds at least two minutes: a replay after 121 s — the same `index` and `again` (A02; the sleep is the term of the norm) | P/01.1 N3 «Replay by identifier» |
| 22 | a damaged row (`@spoil row`) for a guard and a delete: the guard `""` — 412 with its version, a guard by its version holds; a delete with `cas: ""` — 409 with its version, with `cas` by it — deleted (coverage audit P/01, second pass, G05) | P/01.1 N2 |
| 23 | service doors: an extra field in `join`, `leave` and `op: floor` — 400, `floor` is not written; an `id` not in the member form in `join` and `leave` — 400 (G06) | N2 |
| 24 | a wrong method at `/metrics`, `/v1/join`, `/v1/leave` — 405 (G06) | N2, N4 |
| 25 | `/v1/status` of a door without a vote — `state` `Door`, `role` `door`, `term`, `commit`, `applied` — 0 (G06) | N2 `GET /v1/status`, N1.3 `door` |
| 26 | the role `configstore-door`: its own row with `cas`, with an extra element of `items`, and its delete — 403, its own row in form — 200 (G06) | N1.3 `door` |
| 27 | `import` into a fresh group where a live door has already written its row passes; `-index-base` below the greatest version of the copy — a refusal, nothing is transferred (G06; C01-IMPORT-DOOR-ROWS-01) | N1.3 `import`, N4 |
| 28 | `recover -peers` without its own `-id`, without the `api` address, with a repeated `id` — a refusal; `-upper` above the computed one raises the floor: `100001 << 32` (G06) | N1.3 «Daemon flags» `-peers`, `-upper`, N4 |
| 30 | a batch and a restart: the rows written and deleted by a batch read after `@restart store` with one version; a replay by `id` after the restart — `again`, not a single extra write (ADR-0094 B9) | N1.3 `batch`; P/01.1 N3 «write batch» |
| 31 | a batch in a group: a door without a vote forwards it whole; the rows read on followers with one version, a replay by `id` through a voter and through the door — `again`; a stale `cas` — nothing is written; the role `configstore-door` does not write a batch — 403; after the death of the leader the batch is intact (ADR-0094 B9) | N1.3 `batch`, `door`; P/01.1 N3 «write batch» |
| 29 | `import` of a copy whose floor has `generation_at` later than the clock (2100) — a refusal without `-force`, nothing is transferred; with `-force` — transferred (coverage audit P/01, second pass) | N1.3 `floor` `when`, «Daemon flags» `-force`, N4 |

The inputs of sc. 11–12 are `inputs/*.jsonl` (JSON Lines copies in the form of N1.3 `copy`). A copy of one implementation restored by another is the compatibility matrix of ADR-0083 item 5 on the same directives, outside the acceptance of one implementation.

`recover` — sc. 18 (the group stand; formerly the drill sc. 06 of the [system acceptance](../../common/acceptance/system/README.md)), step 9 of sc. 15 (`door.pass`) — step 1 of sc. 15 of the [acceptance of chapter 6.5](../../06-console/acceptance/5/README.md): they need writers and the issue of epochs (P/03.2) and the console.

---

## Implementation decides

Each implementation names in its description:

1. **the raft transport secret** beyond mTLS, if there is one, and its rotation on revocation; the raft wire between members and the frame of `admin.sock`
   (read-fence, admit, import) are internal to the implementation: a format with a name and a version, no new HTTP routes; the members of one
   store cluster are one implementation, a mix of languages — only by clients through `configstore:///` (guess of stage C CL-01,
   ADR-0087 addendum (12) item 7);
2. **the durability of the store** (fsync, raft snapshots: threshold, interval, tail) — a teaching store MAY be non-durable, and this is said in its description (ADR-0070 item 4); a stand flag that turns the barriers off is in the «Stand» command, not in the environment (N1.3 `durability`);
3. **the connection accounting of the daemon** and overrides of the limits by deployment, `-tuning` for slow networks; the normative defaults are N1.3;
4. **how `backup` obtains a consistent state of a running daemon** (N2); the requirement on the copy is a norm of N2, not a choice.
5. **the format mark and the profile `file://`**: the values `format` and `version` of its mark `FORMAT` — the one current version that this build writes and reads (N1.3 `format`); the on-disk format of the profile `file://`; the command by which a copy of N1.3 `copy` is taken from a store `file://` (the form of the copy is a norm) (the store pilot, A1, A2, A9).
6. **mutual exclusion of runs** of `recover`, `restore`, `import` on one installation (a lock, a mark file) — the norm requires one attempt (N3 «Races: admittance and recovery transitions»), the way is a choice (guess of stage C S02).
7. **the internal contract of `file://`** (item 5): the format of the profile `file://` is the implementation's own, not a public contract. Its description
   and the library API are written in the implementation's repository by the owner of this chapter before the code: the physical layer and the command layer — conditional
   `put`/`delete` with `guard`, the batch `batch`, CAS by version, `not_before`/`not_after`, outcomes and refusal words as at the store door (P/01.1 N1,
   N4; without retelling the norms), with vectors from its own code. Other processes of the implementation (the installer, the worker) read only
   the contract and the API; a mix of languages on `file://` is not supported — through `configstore:///` (guesses of stage C W03-E01a,
   W03-SDK-FILE-COMMAND-01, ADR-0087 addendum (12) item 7).

---

## Readiness checklist

An implementation conforms to the chapter when every norm holds; the norm id `P/01.3-MM` is what decision deltas, findings and window records refer to (ADR-0080 addendum 6):

- [ ] **P/01.3-01** the daemon: the flags of N1.3, the store of a box without raft (`box`) — sc. 04 and by reading, `members` without `-api` — `{}` (sc. 16), start refusals, sizes 1/3/5, joining and `-force`, `leave`/`admit`, the effective `-leader-wait` interval — sc. 07, 17 (the group stand); mTLS, sockets — by reading; the 503 branch «no leader for the effective `-leader-wait` interval» — sc. 17; ambiguous and unavailable with Retry-After at the connection limit — by reading N1.3/N4: the scenarios do not saturate connections and do not cut the leader's answer
- [ ] **P/01.3-02** a door without a vote: without raft, the same rights, forwarding, the row `seen_at` by the own write of the role `configstore-door` (only this row), 503 without voters — sc. 07, 17 (the group stand); the door is not part of the quorum — sc. 17; `/v1/status` of the door (`role`, `term`, `commit`, `applied`) — sc. 25; its own row only by `put` without `cas` with one `seen_at`, a delete — 403 — sc. 26; an unreadable door row outside `configstore_doors` — by reading: the TSV request does not carry a fresh `seen_at`, and with an old `seen_at` a step will not tell an unreadable row from one that the implementation does not count by age (acceptance README)
- [ ] **P/01.3-03** the epoch floor: upper and the generation formula by the clock with the example of N1.3, the replay memory of `floor` in the store, only upwards, only admin, `recover`/`restore`/`import` raise it before the first row — sc. 18 (the group stand; formerly drill 06 of the [system acceptance](../../common/acceptance/system/README.md)); the replay memory of `floor` after a restart, only upwards (the same and a smaller floor with a new id — 409), only admin (a role socket — 403) — sc. 08; `recover` without `-isolated` and with `-upper` below the computed one — a refusal before changes, `-upper` only raises upper — sc. 18 and by reading the CLI test of the implementation (guess of stage C S02); `-upper` above the computed one raises the floor, `-peers` out of form, without its own `-id`, with a repeat — a refusal — sc. 28; a clock earlier than `generation_at` of the floor of the input — a refusal without `-force` — sc. 12 steps 31–32, with `-force` — sc. 29
- [ ] **P/01.3-04** `import`/`restore`: a fresh group, an immutable input, the base ≥ the greatest; a wrong input without changes, after the floor a partial transfer is possible, a replay of the same attempt — by reading; the reason — TSV does not reproduce the error of each row and the partial restoration after the floor; a fresh group with a door row and a base below the greatest version — sc. 27; a row key not by N1 and `generation_at` of the floor not a time — sc. 12 steps 27–30
- [ ] **P/01.3-05** the daemon metrics of N1.3 — sc. 04 (two series); the series `_state`, `_elections_total`, `_index`, `_last_contact_seconds`, `_voters`, `_voters_expected` of the leader and a follower — sc. 17; the three alarms — checked by reading: the metrics test of the implementation (the subject — the list of N1.3); `configstore_doors` — the number of rows `platform/configstore-doors/<id>` that read in their own form, with `seen_at` not older than `DOOR_SEEN_PERIODS × DOOR_SEEN_EVERY` — at a voter by its own replica and its own clock, a door without a vote has no series (C01-DOORS-COUNT-FRESH-01, C01-DOORS-COUNT-PLACE-01) — sc. 07 (the group stand) (the Architect's decision on the tails of the move of lesson 1)
- [ ] **P/01.3-06** the mark `FORMAT`: a start refusal with code 2 on a foreign and on a non-empty unmarked directory, without changes — sc. 10; the first write of the mark into an empty directory, a start on its own one — sc. 08 step 2 (`@restart store`); the copy `copy` — one form for `backup` and `import`, a refusal of the input as a whole — sc. 11, 12; `restore` with the same form and a copy of another implementation — by reading and the matrix of ADR-0083 item 5; the daemon flags — a closed table, `-dir` and `-id` in a group are required, flat sockets, inherited by `FileDescriptorName` — by reading: the units and flags test of the implementation (the store pilot)
- [ ] **P/01.3-07** service doors (reconciliation of python and go M10/6–11): the order «frame → route → identity → body», 413 earlier than 405, `join`/`leave` from a role socket — 403, empty `raft`/`api` — 400, `HEAD` — 405/404 — sc. 15; extra fields of `join`, `leave`, `op: floor` and a member `id` out of form — 400 — sc. 23; 405 at `/metrics`, `/v1/join`, `/v1/leave` — sc. 24; the floor is a JSON integer < 2^53: a float notation and the greatest uint64 — 400, 2^53 − 2^32 is admissible — sc. 08 steps 10–12 (review of stage B 1–2, item 8); the replay memory is not in the copy — sc. 14; `-max-value` > 0 — by reading: the flags test of the implementation (the stand does not set daemon flags)
- [ ] **P/01.3-08** the life cycle (reconciliation of python and go M10/6–11): the `backup` target outside `-dir` — sc. 11 step 11 (`@backup store … in-data`); a repeat of a finished `import` — code ≠ 0, `recover` on a box — code 2 (N4) — by reading: the store CLI test of the implementation (the directives `@backup`/`@import` write the runner's file and each time a fresh directory, they do not give these cases)
- [ ] **P/01.3-09** verification of the TLS peer by the daemon of N1.6: CN and SAN, one role `configstore` or `configstore-door`, the signature algorithms of the chain, trust of `ca.pem` and `ca.next.pem`, revocation by content without a restart — checked by reading: the tests of the implementation on a test CA (the subject — N1.6: without a certificate, a foreign CA, a revoked one, a foreign role, its own); the reason — the CA and file rights are not changed by HTTP-TSV
- [ ] **P/01.3-10** the admission time in the log record and the snapshot, continuation from the snapshot, `admission_ahead` in `/v1/status` of the leader beyond `CLOCK_SKEW` (N1.3 `admission`) — checked by reading: the stand does not move the leader's clock and does not take a snapshot on demand
- [ ] **P/01.3-11** a batch: one log record, application on all servers whole, forwarding by a door without a vote in one request, the role `configstore-door` does not write a batch — sc. 31 (the group stand); a restart and a replay by `id` — sc. 30; a power cut in the middle of a batch — by reading (P/01.1-31)

## REMOVED

(none)
