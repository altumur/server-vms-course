# Delta 0120-p01-review-replies-tls-floor — review of lesson P/01

change: 0120-p01-review-replies-tls-floor rev 1. Base d68286f29; lesson delta_base 725653954. Unit normalization: LF, strip trailing spaces, one final LF.

## ADDED

(none)

## MODIFIED

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R088

old-sha256: 6f5df45a66251cb0a2feb05519544cc20f3658def717e2a7932f664077028773

<!-- req: P/01.1-R088 -->
The order of checks inside the operation is normative: the `id` memory, then `not_after` and `not_before`, then the guard,
then CAS; with several violations the answer is by the first one (ADR-0091 item 1). A replay of an applied write gets its
answer also after `not_after` — including a replay that arrived while the first copy was not yet applied: the first one
is applied first, the replay answers with its answer. A refusal `expired` and `early`, like `conflict` and `guard`, makes no write and does not take the `id`, but the admission time of the refused
record remains the last admission time (in a group — a log record; a box and a store in the process store it as durably
as rows; C01-ADMITTED-ON-REFUSAL-01). Only `expired` remains the same refusal for the same deadline and nondecreasing admission time. `early`, `conflict` and `guard` do not occupy the `id`: the same command and `id` are checked again against the current admission time and state and may succeed. The caller still re-reads its condition and decides anew before another attempt (Н4). The guard before CAS. A guard refusal means a mismatch of the observed version and the absence of this write. The caller re-reads the condition and decides anew whether it has the right to repeat; a version mismatch by itself does not prove a loss of ownership. A CAS refusal also requires a re-read before a new attempt. A guard on an absent row (`index: ""`) holds while the row does not exist.

### `Platform/01-store/spec/01.3-store.norms.md` P/01.3-R006

old-sha256: ad07a222c1ed32aa81b6e961742ba14676089a7f309ed117d23fe4bd9a5f99ee

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
           a certificate carries one role; -api and -raft on loopback may run without -tls (the local box); outside loopback they require -tls; -join always requires -tls (group traffic); an additional transport secret — the implementation decides
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
           platform/epoch_floor is included as an ordinary input row for upper and the generation_at clock check, but is not transferred; the id replay memory (chapter 1.1 Н3) is not part of the copy; the copy knows no manifests —
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

### `Platform/01-store/spec/01.3-store.norms.md` P/01.3-R007

old-sha256: 0d9c07f167b622324809a268352134451db51a4f81a51399111e936fe71127c2

<!-- req: P/01.3-R007 -->
**Daemon flags** — a closed set (the store pilot, А3, А8). A flag outside the table is a start refusal, code 2. The machine form of the table — [`forms/daemon-flags.tsv`](../forms/daemon-flags.tsv) (ADR-0125): type, default, required, commands; `check_spec` checks that it agrees with this table.

| Flag | Type | Default | Meaning |
|---|---|---|---|
| `-dir` | path | none: required, without it a start refusal, code 2 | the data directory of the daemon; the mark `FORMAT` (`format` above); also of `recover`, `restore`, `import` — they write into the directory of a stopped daemon on a box (ADR-0125 addendum (2) item 1) |
| `-id` | member id (Н2) | in a group (`-join`, `-door`, `-group-size 3` or `5`) none: required; otherwise — `SERVER_NAME` (P/02.4 Н1.2) | the member name in `members`, `voters`, `leader_id`; also of `recover` |
| `-sockets` | directory path | `/run/configstore` | the socket directory, flat (`sockets` above); the commands `status`, `join`, `leave`, `admit`, `backup`, `restore`, `import`, `rights` find `admin.sock` by it, `recover` does not (ADR-0125 addendum (2) item 1) |
| `-rights` | file path | none: without it — only `admin.sock` (chapter 1.2 Н1.2) | the rights file |
| `-tls` | directory path | none: required with -join or a non-loopback -api/-raft | the root of the certificate kits (Н1.6), mTLS of `-raft` and `-api` |
| `-raft` | `host:port` | none | the raft address that the daemon names to its partners |
| `-raft-bind` | `host:port` | `-raft` | the address on which the daemon listens for raft, if it differs from the named one |
| `-api` | `host:port` | none: without it there is no service HTTP door for partners | the address of the service doors of Н2 for partners; the value of `members` and `leader` in `/v1/status`; without `-api` the member is not in `members` (the map can be `{}`; C01-STATUS-MEMBERS-NOAPI, the Architect's decision of 2026-10-26) |
| `-bootstrap` | no value | off | the first server of the group (`join` above); with `-join` — a start refusal |
| `-join` | `host:port` | none | the `-api` address of a group member through which the daemon joins (`join` above); always with `-tls` |
| `-group-size` | `1` \| `3` \| `5` | `1` | the declared group size, the same on all servers |
| `-force` | no value | off | joining at a transitional evenness (`join` above), also of the command `join`; for `restore`, `import`, `recover` — only the clock refusal |
| `-isolated` | no value | off | only for `recover`, required: the operator confirms that the former group and the writers are isolated and nothing was handed out above upper (Н3 step 0); without it `recover` is a refusal before changes (guess of stage C S02, the Architect's decision of 2026-10-23) |
| `-upper` | integer 0 … 2^53 − 1 | none | only for `recover`: the bound of the lost tail of epochs known to the operator; it only raises the computed upper (`floor.generation`): upper := max(computed, N); N below the computed one — a refusal before changes (guess of stage C S02, the Architect's decision of 2026-10-23) |
| `-peers` | a comma-separated list `id@<raft host:port>/<api host:port>` | none: required for `recover` | only for `recover`: the recovered membership — the remaining members, the one being recovered (`-id`) among them; the id and both addresses are required for each: raft — the address of the raft membership, api — the value of `members` in `/v1/status`; any other notation — a refusal before changes (guess of stage C S03, the Architect's decision of 2026-10-23) |
| `-door` | no value | off | a door without a vote (`door` above) |
| `-voters` | a comma-separated list `id@host:port` | none: required with `-door`, without it a start refusal, code 2 | the voters for a door without a vote: the id and the `-api` address |
| `-tuning` | `default` \| `lan` \| `slow` | `default` | the raft timing profile (`tuning` above) |
| `-leader-wait` | duration | `5s` | the leader wait (`leader_wait` above) |
| `-max-value` | bytes, > 0 (`0` and not a number — a start refusal, code 2; reconciliation of python and go М10/6–11, B7) | `512KiB` | the row ceiling (chapter 1.1 Н4, `{row_ceiling}` of «Стенд») |
| `-max-body` | bytes, > 0 (as `-max-value`) | `1MiB` | the read limit of the HTTP body of `POST /v1/write` (chapter 1.1 Н2, `{body_limit}` of «Stand»), separately from the row ceiling `-max-value` (log of cammeta-python, lesson 11 № 24) |
| `-max-conns`, `-api-conns`, `-api-per-address` | integer > 0 | 64, 32, 8 | connection limits (below) |
| `-index-base` | integer ≥ 0 | 0 | for `import`: the version base (`import` above) |
| `-groups` | no value | off | only for `rights` (`admin_ops` above; ADR-0125 addendum (2) item 1) |
| `--from` | file path | none: required for `restore`, `import` | only for `restore`, `import`: the input — the backup copy (`copy` above; `admin_ops` above; ADR-0125 addendum (2) item 1) |

### `Platform/01-store/spec/01.3-store.norms.md` P/01.3-R011

old-sha256: 8255fd885479a964342821fa290fcb82dd058e21734c3d22cef0606c5590e06f

<!-- req: P/01.3-R011 -->
```yaml
roles:        configstore, configstore-door (with -tls for group traffic and every non-loopback -api/-raft; local loopback box doors may run without -tls)
raft:         on -raft only a leaf of the role configstore is accepted; a leaf of another role (configstore-door and others) — a refusal in
              the handshake (TLS alert), the raft stream is not opened, as with doors that judge the client certificate in the handshake
              (the role certificate contract); on -api — both roles of the daemon (C01-RAFT-DOOR-LEAF-01, the Architect's decision of 2026-10-30)
counts:       the count of invalid rereads of revoked/crl.pem and of stale CRLs (the revoke contract) — lines of the daemon log, there are no
              /metrics series (the list of Н1.3 is closed; C01-TLS-COUNT-PLACE-01)
```

<!-- families:begin -->
### Семьи данных (построены из стандартных файлов)

Форма строк и объектов, которыми глава владеет по [каталогу](../../common/data/catalog.tsv), — JSON Schema 2020-12 семьи (ADR-0092). Экземпляр строки — `{key, row}`, объекта — `{key, object}`; ключ — грамматика колонки `key` каталога. Поля `row` — значения `items` после [кодека](../../common/data/codec.tsv): писатель проверяет схему и её `$defs.writer`, читатель — схему (слой 3 — слова `x-*` схемы). Нечитаемо — строка не раскодировалась или не прошла схему в режиме читателя; исход — по таблице исходов семьи: путь — префикс пути отказа (пустой — строка целиком), при нескольких путях отказа действует исход с наименьшим приоритетом.

#### `platform/epoch_floor` — строка

Схема — [`epoch_floor.schema.json`](../data/epoch_floor.schema.json), исходы — [`epoch_floor.outcomes.tsv`](../data/epoch_floor.outcomes.tsv); версия формы 1; норма — P/01.3 Н1.3 floor, P/03.2 Н1.5.

| Ключ | Тип и границы | Обязательность | Урок | Смысл |
|---|---|---|---|---|
| `floor` | целое; ≥ 0; ≤ 9007199254740991; целый знак и у читателя (x-whole) | обязателен |  | the lower bound of issue after a restore; generation << 32 |
| `generation_at` | время (P/01.1 Н0 «Время в строке») | обязателен |  | the moment the floor was raised — the wall clock of the raiser at that moment, not the admission time of the log record (it may run ahead of clocks; C01-GENERATION-AT-WALL-01) |

Исходы нечитаемой строки (читатель — роль; `*` — все читатели семьи):

| Путь отказа | Читатель | Исход | Приоритет | Единица | Норма |
|---|---|---|---|---|---|
| `/floor` | * | epoch issue: the issue is refused, the floor is not replaced by 0; lease confirmation: fenced; import, restore: the whole input is refused, nothing changes | 0 | строка | P/03.2 Н3 «take_epoch(id)», «confirm»; P/01.3 Н1.3 import, Н4 |
| `/generation_at` | * | epoch issue and lease confirmation do not read the field — they issue and confirm by the floor; import, restore: the whole input is refused, nothing changes (the current behaviour of both implementations; the norm does not name the outcome) | 1 | поле | P/01.3 Н3 «recover the store» |
| строка целиком | `<s>worker` | the whole row is unreadable: epoch issue — the issue is refused, the floor is not replaced by 0; lease confirmation — fenced | 2 | строка | P/03.2 Н3 «take_epoch(id)», «confirm» |

#### `platform/configstore-doors/<id>` — строка

Схема — [`configstore-doors.schema.json`](../data/configstore-doors.schema.json), исходы — [`configstore-doors.outcomes.tsv`](../data/configstore-doors.outcomes.tsv); версия формы 1; норма — P/01.3 Н1.3 door.

| Ключ | Тип и границы | Обязательность | Урок | Смысл |
|---|---|---|---|---|
| `seen_at` | время (P/01.1 Н0 «Время в строке») | обязателен |  | the wall time of the last confirmation of the door (every 30 s) |

Исходы нечитаемой строки (читатель — роль; `*` — все читатели семьи):

| Путь отказа | Читатель | Исход | Приоритет | Единица | Норма |
|---|---|---|---|---|---|
| строка целиком | `configstore-door` | the door row is unreadable — it does not count as a visible door (not in configstore_doors), the cause goes to the leader's log without the value (П1; В7 item 3, row 5) | 1 | строка | P/01.3 Н1.3 door |
<!-- families:end -->

### `Platform/01-store/spec/01.3-store.norms.md` P/01.3-R026

old-sha256: c3e3d0686d88f24ed928de521e866429425caa8d77672a8cabdf651af690edc0

<!-- req: P/01.3-R026 -->
| Phase | What is allowed | What is kept on a refusal |
|---|---|---|
| Isolation | Stop/cut off the old members, fix the immutable input and upper | The old data; the new group is not started yet |
| Check | Check all rows (form, key, size), the base, the epochs and upper, the uint64 bounds; families of rows — only `recover` of its own dump: for all rows — the row envelope, the key by the catalogue, the version, the size; schemas — only of the families of the store itself (P/01) and upper; the content of other families is not interpreted and is kept as is — schemas are the business of their owners (guess of stage C S04, the Architect's decision of 2026-10-23); the copy `copy` knows no manifests (Н1.3 `import`) | Neither the floor nor the rows are changed |
| New floor | Raise floor above upper durably, once; op: floor has its own replay id | On an unknown answer repeat with the same id, do not compute a new generation |
| Transfer | Keep the first new floor F1; write all other copy rows with their copy versions, excluding the old platform/epoch_floor; durable progress for continuation | A partial transfer is possible; ordinary writers are forbidden |
| Done | Check every non-floor input row and the saved new F1 row; allow the updated membership/writers | The former group stays cut off; only epochs not below floor are started — one issued with the old floor is lost (P/03.2 Н3 «take_epoch(id)») |

## REMOVED

(none)
