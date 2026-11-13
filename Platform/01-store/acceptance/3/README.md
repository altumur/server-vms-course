# Acceptance P/01.3 — the store daemon

This English text is the source; the Russian translation `ru/acceptance/3/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors).
The acceptance checks the requirements of P/01.3 named below.

Directives and doors: `admin`, `store`, `@as`, `@big`, `@restart store`, `@foreign store`, `@backup store`,
`@import store` and the door `restored`; the store group stand — `@group-setup`, `@store-start`,
`@restart store@<id>`, `@sigterm`/`@sigkill store@<id>`, `@store-op`, the doors `store@<id>`, `admin@<id>`, the probe `@tls` to
`api@<id>` (sc. 07, 17, 18, 25–29, 31–35; the section [«Store group stand»](#store-group-stand)). The stand store is durable — it survives a restart (the directory `{data}`); sc. 08 relies on this. An implementation with
a non-durable training store (the norms of chapter 1.3, «Implementation decides» item 2) does not run sc. 08 and says so in the description.

## Profile interface

Use the `01-store` [profile format](../../../common/acceptance/PROFILE.md). `stand.store` starts the durable daemon. It carries the stand's substitutions in its own flags, each once, and none of the flags that the group stand appends ([substitutions](../../../common/acceptance/PROFILE.md#substitutions)); the group stand appends the member flags ([store group stand](#store-group-stand)). `stand.backup` copies through `{socket}` to `{file}`; `stand.import` imports `{file}` into the stopped fresh `{data}` using `{index_base}`. Group operator calls use `stand.store-op` with `{socket}`, `{dir}`, `{id}`, `{tls}` and prepared `{args}`; row-corruption checks use `stand.spoil-row` with `{data}`, `{key}` and `{what}` as assigned by their existing stand contract. `keys.store_build` declares `raft` or `box` with the applicability below; omission or another value does not silently select one. The role header uses `keys.role_header`. Program names and wrappers belong to the implementation; operation semantics and the flags appended by the group stand remain those of the referenced norms and common stand.

## Stand

The stand store: schema 1, the manifest rows `testsub` and `testsub2` are written by the runner itself through `admin.sock`, without the installer
(ADR-0083 addendum (98)): `put` with `cas: ""` and exactly the fields of the writer of P/02.3 N1.5 — `yaml` (the bytes of the file), `sha256`
of these bytes, `rev` `"1"`; the rights file `{rights}` is the prepared rights file of P/01.2-R007; the runner puts it before the store starts. Of it, the steps of the chapter need only the role socket
`console` without the rights of `admin` (`@as console`: sc. 08 step 8, sc. 15 steps 1–2) and the manifest rows `testsub`, `testsub2` (sc. 11
steps 9–10: the copy `backup` carries the manifest rows). The resource, the controller, the console and the workers are not needed by the chapter. The stand store of the chapter is
a single member of a box without `-api` (N1.3 `-api`: the flag is not mandatory; the box has no partners): sc. 16 relies on this.

- **Copy commands** (P/01.3 N1.3 `copy`, `admin_ops`): `backup` — a template with `{socket}` and `{file}`: a copy of the store through
  `admin.sock` into a file, code 0 — the copy is taken; `import` — a template with `{data}`, `{file}` and `{index_base}`: the transfer of a copy into
  a fresh directory of a stopped store (P/01.3 N1.3 `box`), code 0 — transferred, another — a refusal. The implementation names
  both (P/01.3 «Implementation decides» items 4, 11).

## Directives of chapter 1.3

Only the acceptance of P/01 uses the words below; the [dictionary of the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors) names each of them with a reference to this section. «Stand», «Role sockets» and «Terms of the stand» are those of the common acceptance README. The words of chapters 1.1 and 1.2 (`@hold`, `@by` and the others) are in the [acceptance README of chapter 1.1](../1/README.md#directives-of-chapters-11-and-12).

**Door.**

| Door | Where |
|---|---|
| `restored` | the door through `admin.sock` of the store instance which the last `@import store` of the scenario brought up |

**Stand directives** — not HTTP; the answer is `ok` or a refusal of the runner.

| Form | Meaning |
|---|---|
| `@restart store` | SIGTERM to the store, wait for the exit, start it with the same command with the same `{data}`, wait for its readiness by the rule of «Role sockets» |
| `@sigterm store` | on the stand of one store: SIGTERM to the process group of the store; the expectation `ok` — the process exited, `@exit <code>` — it exited with this code, not by a signal |
| `@backup store <name>` | take a copy of the stand store with the command `backup` of «Stand» into a file of the runner `<name>` (it lives until the end of the scenario); `ok` — code 0 and the file in the form of P/01.3 N1.3 `copy` (a header, Row rows, keys in ascending byte order); otherwise a refusal of the runner |
| `@backup store <name> in-data` | the command `backup` of «Stand» with `{file}` = `{data}/configstore/<name>` — inside the data directory of the stand store (`-dir`); the expectation `refused` — code ≠ 0 and there is no file `{data}/configstore/<name>` |
| `@import store <file>` / `@import store backup <name>` | the input is a file from the acceptance directory of the lesson or a copy `@backup store <name>` of this scenario; the runner takes a new empty `{data}`, calls the command `import` of «Stand» with `{index_base}` — the `index` of the header of the input (the header is not readable — `0`), then on this `{data}` starts a second store instance with the command of «Stand» with its own `{socket}` and waits for its readiness by the rule of «Role sockets» — its door is `restored`. The expectation `ok` — the code of `import` is 0; `refused` — code ≠ 0 (that the directory remained without rows is seen by the following steps `restored`). The stand store is not touched |
| `@foreign store nolabel` / `@foreign store otherlabel` | a second store instance with the same command with a new directory `{data}` and its own `{socket}`; before the start the runner puts into the store directory `{data}/configstore`: `nolabel` — a file `rows` with the bytes `x` and without `FORMAT`; `otherlabel` — `FORMAT` with the bytes `{"format":"w2c-acceptance-foreign","version":1,"impl":"runner"}`. `ok` — the process exited with code 2 no later than 10 s and the directory tree (names, bytes) is the same as before the start; otherwise a refusal of the runner. The stand store is not touched (P/01.3 N1.3 `format`) |

## Batch and restart (sc. 30)

The batch `op: batch` on the stand store (P/01.1 N3 «write batch», ADR-0094 B9): the rows and the `id` memory survive `@restart store`, a replay answers
`again` with the earlier version; the next batch edits one row and removes another. The stand does not reproduce a power cut in the middle of a batch — by reading
(P/01.1-31).

## A foreign directory (sc. 10)

The store format mark (chapter 1.3 N1.3 `format`): a second store instance on a non-empty directory without
`FORMAT` and on a directory with a foreign mark does not start (code 2) and changes nothing in the directory. The scenario does not
touch the stand store. The first write of the mark into an empty directory and a start on one's own directory — every start of the stand and `@restart store` of sc. 08.

The separate executable probe `05-data-ownership` uses a healthy completed directory state, not scenario 10's foreign/missing `FORMAT` mark. It checks `start_data_dir_owned` and `local_data_dir_owned`: refusal of the second daemon before readiness/any write, unchanged first owner/data/ownership; refusal of offline box import/restore and local recover. A separate simultaneous-start race, including an empty directory, yields exactly one owner; ownership checking precedes other directory-dependent reasons. After orderly exit and `SIGKILL`, lawful start without manual cleanup is checked on a healthy completed state. This does not cancel `start_format` or refusal of unfinished `import`/`restore`: unfinished transfer is a separate negative case after the owner dies. Only owned isolated processes and directories are used. Independent live-owner confirmation, check-order observation and write attribution are required; lawful background work of the first daemon is not attributed to the second attempt. Missing native binding is `NotExecuted`, not a successful refusal.

## The copy (sc. 11, 12)

**Copying damaged rows.** An existing row with a damaged body and retained version stays in backup as `{key, items: null, index, unreadable: true}`, where `index` is its exact nonempty version; the existing key order and coherent copy header remain. This is separate from import/restore refusing unreadable input under N4. A lost version requires the P/01.1 R028 log entry, a nonzero backup CLI exit and preservation of the previous published file. HTTP copy may return `503 UnavailableFault` before `200` or close incompletely after `200`; a completed copy that omits the row or invents its `index` is invalid. An import refusal of unreadable input does not permit omitting a damaged row from backup. The `spoil-row` binding uses `what=body` or `what=index`; without it the dependent observation stays `NotExecuted`.

The store copy (chapter 1.3 N1.3 `copy`). The input (`--from`) is JSON Lines; the reader does not require an order of the rows;
the copy does not interpret manifest rows (`platform/manifest/*`): `import` carries a row of any family (chapter 1.3 N1.3
`import`). On a `copy` refusal
nothing is transferred.

A refusal of `copy`: a wrong `format` or `version` of the header, an extra field of the header or of a row, a first line that is not a header, a row without `index`, a line that is not JSON, a value of `items` that is not a string, a key twice, the `index` of a row above the `index` of the header, a row `unreadable`, an epoch or floor row that is not decimal (upper is not reliable), a row key that is not a key of chapter 1.1 N1, a `generation_at` of the floor that is not a time; a correct copy whose floor `generation_at` is later than the stand clock is a refusal without `-force`.

The input floor is used only for the upper and generation_at checks and is not transferred; `import` raises a new floor above
the upper of the input before transferring the other rows (N1.3 `floor`); the number depends on the clock. The copy `backup` of the stand store, transferred into a fresh directory, carries the manifest rows.
The writer side of the rule «Time in a row» (N0 of chapter 1.1): the floor after `import`, `generation_at`
(`@time`).

## Actual body ceiling in status (ADR-0127 P/06 C2)

The Status response of the default stand carries the required `max_body: 1048576` and the unchanged `max_value: 524288`. Repeat the ordinary status GET on a fresh store configured through the existing `-max-body 2097152` and `-max-value 524288`: max_body is2097152, max_value stays524288. This is an actual daemon/HTTP obligation; the source/schema audit does not execute that repeat. Do not add acceptance.yaml keys or guess the limits from defaults.

The independent schema checks use complete Status responses: positive body ceilings1/1048576/2097152, and missing/zero/negative/nonintegral/bool/string/null negatives. Apply the existing Status schema to the whole response. max_body counts entity bytes, including an actual LF; HTTP request/header/chunk framing does not enter it. The static P06 profile gate uses the value from this result, not a new flag or a replacement for max_value.

## A member without `-api` (sc. 16)

A member without `-api` is not in `members` of `/v1/status`,
the map of a single member of a box is `{}` (N1.3 `-api`, `box`; N2 `GET /v1/status`); `leader` is empty. The expectation `members`
`{}` is exactly an empty map (the dictionary of the common README, the line `<code> <JSON>`); `{"<id>": ""}` is not by the form of the OpenAPI of the lesson
(`minLength: 1`), and the step does not pass.

## Store group stand

A raft group of several store daemons on one machine of the stand — the acceptance of this chapter
. The properties of the group — the composition, the elections, a restart, a door without a vote, `recover`, `import` into the group — the stand
sees from outside; drills on a real cluster ([system acceptance](../../../common/acceptance/system/README.md)) no longer replace this.
The norms are P/01.3 N1.3 (`group`, `door`, `floor`, `import`, `leader_wait`, `repeat`), N1.6, N3
«recover the store»; the section introduces no new norms.

- **Members** — by the name `<id>`: the voters `s1`…`s5`, the doors without a vote `d1`, `d2`. The acceptance group has three voters and uses mTLS between members. The server name of the leaf of a member is its `<id>`
  (the leaf `configstore.<id>` for a voter, `configstore-door.<id>` for a door; the [role certificate contract](../../../common/contracts/role-certificate.md), `cert`); the addresses are the loopback
  `127.0.0.1`, the ports are handed out by the runner (free ones on the loopback; there are no addresses in the kit description): `{raft@<id>}`, `{api@<id>}` —
  substitutions in flags, requests and probes; both are the addresses of proxies of the runner, which the member names to its partners (below). A member learns its partners as in the norm: a joining one — by the flag `-join {api@<id>}`
  (P/01.3 N1.3 `join`), a door — by `-voters`, a restart — from its `member.json`; the runner does not pass a list of peers. The daemon
  checks the name of a peer against the `<id>` of the participant, not against the host of the address (the address is the loopback for all).
- **Kits** — the kit setup of the acceptance of chapter 1.3: one CA of the group, a leaf for each member; the layout — the [role certificate contract](../../../common/contracts/role-certificate.md),
  `kit` (`ca.pem`, `<role>/server.pem`, `<role>/server.key`), `revoked` is empty, there is no `ca.next.pem`. The runner creates the test kit under its isolated stand directory and runs the daemon under the invoking user account. The kit directories are owned by that account with mode 0750; the key uses the contract's 0600 branch, owned by the same daemon account. The daemon can traverse the directories and read its kit without a privileged setup.
- **Store build — the feature of the implementation profile `keys.store_build`**: `raft` — a build with a group, the scenarios of the stand
  are executed; `box` — the store of a box without raft, lawful per P/01.3 N1.3 `box` (one voter; `-raft`, `-bootstrap`, `-group-size 3`/`5`,
  `-join`, `-door` — a start refusal, code 2): the scenarios of the group stand are not_applicable, they do not enter the result and are not red, the lesson
  is credited without them; there is no feature or another value — the scenarios are not executed (not_executed, as without `keys.tls_stand`; not
  GREEN). The refusals of the build `box` are checked by sc. 04/16 of the stand store and by reading (P/01.3-01); the group stand does not judge it.
- **Member launch** — the store command of «Stand» (the same as for the stand store), with the environment `BOX_ID=<id>`, `SERVER_NAME=<id>`, `PLATFORM_DIR={data}/<id>` (on the three-server stand — the `PLATFORM_DIR` of its server), and
  the member's substitutions: `{data}` is its `PLATFORM_DIR`, `{rundir}` is `{data}/run`, `{socket}` is `admin.sock` there, and `{rights}`. The template carries them in its own flags `-dir {data}/configstore`, `-sockets {rundir}`, `-rights {rights}`, `-max-body {body_limit}`, `-max-value {row_ceiling}` ([substitutions](../../../common/acceptance/PROFILE.md#substitutions)), so the store directory of the member is `{data}/configstore` of its `PLATFORM_DIR`. The runner appends only these flags: `-id <id>`, `-tls <kit dir>`,
  `-api {api@<id>}` (the address of the API proxy of the runner, which the member names to its partners: `members`, `leader`, its join) and `-api-bind <own port>` (where it listens for the service doors; P/01.3-R007), `-tuning lan`; for a voter also `-raft {raft@<id>}` (the address of the proxy of the runner,
  which the member names to its partners) and `-raft-bind <own port>` (where it listens; P/01.3 N1.3 «Daemon flags»). The other flags — from the line
  of the directive as written (`-bootstrap`, `-join`, `-group-size`, `-force`, `-door`, `-voters`). The template holds none of the appended flags: a repeated flag is a start refusal (P/01.3 N1.3).
- **API proxy** — on `{api@<id>}` of every member: mTLS on both sides. To the caller the proxy presents the leaf of `<id>` and verifies the leaf of the caller by the CA of the group; to the own port of the member it connects with the leaf of that caller from the kits, so the member sees the same peer and its role in SAN (P/01.2 N3). By default it passes any application byte stream unchanged in both directions, without parsing HTTP or rejecting non-HTTP frames. It parses HTTP only while `@cut store@<id> answer` is active. The channel used for internal member frames remains the implementation's choice.
- **Member doors**: `store@<id> <request>` — the door of P/01.1 through the socket of the role of the scenario of the member (the role is named by the chapter README, `@as`
  changes it); `admin@<id> <request>` — through its `admin.sock` (not forwarded: the write is at the leader).
- **Boundaries**: between scenarios the runner stops all members and deletes their directories; the kits — per scenario.

| Form | Meaning | Lesson |
|---|---|---|
| `@group-setup <description path>` | as the first step of a scenario: the runner issues the kits per the description (the path — from the acceptance directory of the lesson) by its own clock; the expectation `ok`; a scenario with this step the runner plans by `keys.store_build` (above): `raft` — executes it, `box` — not_applicable, otherwise — not_executed | P/01.3 |
| `@store-start <id> [kit=<id2>] [<flags>…]` | start the member `<id>` (the flags above); `kit=<id2>` — the member `<id>` receives the kit of the member `<id2>` (its leaf and key) instead of its own: `-id <id>`, and the leaf names the server `<id2>` (the check «`-id` is the server of its own leaf»); the expectation: `ok` — the [startup observation](#startup-observation) succeeds no later than 20 s from process start; `@exit 2` — the process exited with code 2 no later than 10 s (a start refusal, P/01.3 N1.3 `refuse_start`) | P/01.3 |
| `@sigterm store@<id>` / `@sigkill store@<id>` | stop the member; the data directory remains; the expectation `ok` — the process exited | P/01.3 |
| `@restart store@<id>` | start a stopped member with the same command, with the same flags, directory and kit (a restart is not a join: `member.json`, P/01.3 N1.3 `join`); the expectation: `ok` — `admin@<id> GET /v1/status` answers 200 no later than 20 s from process start; a restart does not apply the fresh-join barrier | P/01.3 |
| `@cut store@<id>` / `@mend store@<id>` | the proxy of the runner on the raft address of the voter `<id>` breaks the live incoming connections and does not accept new ones / lets them through again; the outgoing connections of the member go to the others directly (on one machine they cannot be cut) — the member does not receive the journal entries and the heartbeats of the leader; `-api` is not cut; the expectation `ok` — the proxy has switched | P/01.3 |
| `@cut store@<id> answer` | the API proxy of the member `<id>` (above), from now until `@mend store@<id>`: passes every `POST /v1/write` to the member, waits for the complete answer of the member, does not pass it to the caller and closes the connection to the caller; other requests and their answers pass. So the write is executed and committed by the member, and the caller — a door or a follower that forwards to the leader — does not get the answer. The expectation `ok` — the proxy has switched; `@mend store@<id>` makes it pass everything again, as for the raft proxy | P/01.3 |
| `@store-op <id> <operation> [<arguments>…]` | an operator operation of P/01.3 N1.3 `admin_ops` in the words of the command line, as in the norm (`admit s3`, `import --from inputs/copy-ok.jsonl -index-base 7`, `recover -peers … -isolated`), by the command `store-op` of «Stand» — a template with `{socket}` (the `admin.sock` of the member), `{dir}` (its `-dir`, the `configstore` directory of its `PLATFORM_DIR`), `{id}`, `{tls}` (the kit directory of the member `<id>`, even when it was started with `kit=<id2>`) and `{args}`; for `recover` the member is stopped by a step of the scenario (a live member is a data error), the command works with its `-dir`, `-id` (N3 «recover» step 1); `{raft@…}`, `{api@…}` are substituted, the path `inputs/…` — from the acceptance directory of the lesson; the expectation: `ok` — code 0; `refused` — code ≠ 0; the output is not compared | P/01.3 |
| `@tls <probe path>` with the door `raft@<id>` | a probe to the raft port of the voter (its real port, not the proxy of `@cut`): the input `{door: "raft@<id>", client: "<id2>", request: null}` — only a handshake, there is no request; the client presents the leaf of the member `<id2>`; the outcome — the closed form of the README of the [TLS stand](../../../common/acceptance/tls/README.md) (`handshake: alert` — `http: null`) | P/01.3 N1.6 `raft` |
| `@tls <probe path>` with the door `api@<id>` | a probe to the own port of the member (`-api-bind`, not the API proxy): the input `{door: "api@<id>", client: "<id2>", request}` — the client presents the leaf of the member `<id2>` of the stand kit setup, checks the server by the CA of the group and `<id>`; the outcome — the closed form of the README of the [TLS stand](../../../common/acceptance/tls/README.md); the role forwarding header in `request` is a designation, the name is substituted from the description of the implementation by the same profile key as `X-Configstore-Role` in the acceptance of chapter 1.2 sc. 08 | P/01.3 |

### Startup observation

For a voter with `-bootstrap` or a door, `ok` means that `admin@<id> GET /v1/status` answers 200 within the startup interval. A bootstrap voter does not wait for the declared group size: the later steps start the other voters.

For a voter that starts on an empty directory with `-join`, the runner first reads `GET /v1/status` through the admin socket of the live voter named by `-join`. The expected `voters` are that status's voter ids with the joining `<id>` added. The expected `members` map contains exactly those voter ids, each mapped to its assigned `{api@<id>}`. A door is not added to `voters`. This snapshot is taken anew after a recovery; the former cut-off members are not added back.

After starting the joining voter, the runner polls `admin@<id> GET /v1/status` of the joining voter and of every already running voter in the expected membership. The fresh-join barrier succeeds when one polling round obtains 200 from each, each `id` identifies the queried voter, every `voters` equals the expected set (order is insignificant), every `members` equals the expected map, and all have the same nonempty `leader_id` belonging to that set. All these observations fit in the same 20 s interval from the joining process's start; reading one 200 alone does not complete the join step. A failed barrier fails that step and leaves the dependent steps unrun by the common scenario-abort rule.

The runner starts no next joining voter until this barrier succeeds. It polls status without sending another join or adding `-force`. The startup-refusal expectation `@exit 2`, starts with `-bootstrap`, door starts and `@restart` do not use this fresh-join barrier.

## The store group (sc. 07, 17, 18, 25–29, 31)

The group stand is the section [«Store group stand»](#store-group-stand): the members `s1`…`s5`, `d1`, `d2` on the loopback, the stand supplies kits by P/01.3-R009 (one centre, the server name of a leaf is the `<id>` of the member), the scenario role at the doors `store@<id>` is `console`
(the stand rights file). These scenarios do not need the stand store of the chapter. The assembly 1→2→3: the second member joins with `-force` (a group of two is a transitional parity, P/01.3 N1.3 `join`), the third without it, after the second has passed the fresh-join barrier of [startup observation](#startup-observation). The stand group has three voters and uses mTLS between members. The box store build
(`keys.store_build: box`, P/01.3 N1.3 `box`) has no group: sc. 07, 17, 18, 25–29, 31–35 are not_applicable for it, not red; without
the marker they are not executed («Store group stand» above).

- **A batch in the group (ADR-0094 B9).** A door forwards a batch whole: the followers read both rows with one version; a replay by `id` goes through a voter and through a door; a stale `cas` of a row means the others are not written. The door's own row by a batch — 403 (N1.3 `door`). After `@sigkill` of the leader the new leader gives both rows.
- **Size and the door without a vote.** A join beyond the declared size — 409 `refused` both without `force` and with `force` (`-force` does not take beyond the declared size; N1.3 `join`). A door (`-door -voters`): `state` `Door`, a write through it — by the same rights file (forwarding to the leader, visible at a follower), the row `platform/configstore-doors/<id>` with a fresh `seen_at`, the metrics row `configstore_doors` at the leader. A door whose `-id` is not the server of its leaf — a start refusal. The leaf of a door writes at the leader a foreign row of the family `platform/configstore-doors/` — 403, its own — 200 (N1.3 `door` «own»); the role forwarding header in a probe is a designation, the name is from the implementation description.
- **Membership, restart, leader change, quorum.** A size outside `sizes` of N1.3 — a start refusal; `leave` of a stopped member, its `join` before `admit` — 403, `admit` is repeatable (code 0), after it `join` with the same address — 200, with another Raft address — 409, `leave` of an unknown member — 409 (N1.3 `leave`, `repeat`); a restarted member is a follower again. After a restart of a follower and of the whole group the versions are the same at all members, and a write with `cas` of that version passes (the log is not applied again). After a leader change a read at the remaining members sees the version of a write, a returned member too (the read is linearizable, P/01.1 N3). A write through a door and through a voter without a quorum — 503 `unavailable` after the effective `-leader-wait` interval: the door is not part of the quorum.
- **`import` into a group and `recover`.** `import` of a copy into a fresh group at the leader; a repeat of a completed one — a refusal (N1.3 `admin_ops`). The transferred rows keep the versions of the copy, and `cas` by them passes (P/01.3 N1.3 `import`, N3 «the copy is replayed into exactly those rows and versions»): an implementation that rewrites the transfer by ordinary `put` with new small versions fails here. That the new versions after the transfer are above `-index-base`, the scenario does not judge by numbers (the strings are compared only by `==`/`!=`) — by reading. With the majority lost, `recover` without `-isolated` and with `-upper` below the computed one — a refusal before any changes; with `-isolated` — the floor by the upper of the epoch rows, the rows and the epochs are kept (upper is from all epoch rows). The former members with old directories do not return (N3 step 0); new members join from empty directories (`-force` at a transitional parity); the floor is visible at a new follower.
- **A door leaf on `-raft`**: the leaf of a door on the raft port of a member — `handshake: alert` (P/01.3 N1.6 `raft`).
- **Forwarding, metrics and a cut raft port**: the leaf of a voter with the role forwarding header `admin` at the leader with a loaded rights file — 403 (P/01.2 N3); the `/metrics` rows of the leader and of a follower (the names of N1.3 `metrics`, the state in lowercase per ADR-0070); a proxy on the raft port of a member cuts incoming connections (the outgoing connections of the member go directly): after a write a read at the cut member — the new version or 503, not the earlier one, after `@mend` — the new one (the steps do not assume who the leader is).
- **Door status, door rows, import and recover edges**: `/v1/status` of a door whole by N2: `Door`, `role` `door`, `term`, `commit`, `applied` — 0; the leaf of a door at the leader: its own row with `cas: ""`, with an extra element and its deletion — 403, its own row by the form — 200 (N1.3 `door`: only `put` without `cas` and `guard`, the single `seen_at`); a live door has written its row: `import` of a copy with `-index-base` below the versions of the copy — a refusal, no rows; with `-index-base` not below them — transferred, the version of the copy is kept (a door row does not cancel freshness); with the majority lost `recover -peers` without its own member, without an `api` address, with a repeat of a member — a refusal; a `-upper` above the computed one raises the floor; `import` of a copy with a future `generation_at` of the floor without `-force` — a refusal, nothing is transferred, with `-force` — transferred, the floor is raised (N1.3 `floor` `when`, «Daemon flags» `-force`).
- **A lost answer of a forwarded write**: `@cut store@s1 answer` at the leader `s1`, then a write. The leader executes and commits it, its answer does not reach the caller. A door with `id`, a follower with `id` and a door without `id` answer 503 `ambiguous`, not `unavailable`: the write went to the leader without an answer. A door with `id` may retry at other voters; they forward to the leader through the same proxy, their answer is `ambiguous` too, so the outcome of the door stays `ambiguous` within its attempts. A commit through another member, after a change of the leader, does not change this outcome either: the proxy holds the answer, not the commit. Before `@mend` a read at the leader already gives the version of the write; after `@mend` a replay with the same `id` through the door and through a voter gives `again` with that version; the same `cas: ""` write without `id` gives 409 `conflict` with that version, not a second write. That a door does not retry a write without `id` stays by reading: a retry of a `cas` write leaves no second effect to observe.
- **A foreign membership over mTLS** (sc. 35): the leaf of the member `s2` on the own port of the leader asks `leave` of `s3` and `join` of a new id `x9`, on the own port of the follower `s3` — `leave` of `s1`: each is 403 `forbidden` (P/01.3 N2 `membership_foreign`), the membership of the leader and of the follower is unchanged (`x9` is absent, `s1`–`s3` remain). The `join` of `x9` into the full group would be 409 by the size; 403 shows that the authority is checked before the membership. The own membership over mTLS is the joining of `s2` and `s3` by `-join` in the assembly of the same scenario.
- **Remaining by reading**: a full cut of a member in both directions (the outgoing connections of a member on one machine are not cut);
  that a door does not retry a write without `id` (sc. 34 above); writers during `import` (the window between the floor and «Done») other than the interrupted attempt of seam s11 (below, «Review seams»); the door leaf
  on `-raft` is now not by reading: sc. 07, the last step, above; an unreadable door row outside `configstore_doors` (N1.3
  `door`) — a TSV request does not carry the current time for a fresh `seen_at`, and a row with an old `seen_at` the implementation is entitled
  not to count as a visible door by the deadline (the door writes it every 30 s): the step would not tell an unreadable row from a stale one; `recover` with the clock earlier than
  the `generation_at` of the floor — the stand does not put a floor with a future `generation_at` into the group (`op: floor` writes the clock of the leader).

## The stand store: restart, a copy with an epoch, row spoiling, replay memory, service doors (sc. 12, 19–24)

- An `import` of an input with an epoch row or a floor row that is not decimal — upper is not reliable, a refusal of the whole input, nothing is transferred (N1.3 `import`).
- The version after a restart of the daemon on the same directory — the earlier row with the earlier version, the new versions
  differ from it (P/01.1 N1 `index`); a non-durable training store does not run this check.
- `@spoil row` / `@spoil row-index` (common README) — spoiling bypassing the door by the profile command `spoil-row`
  with the store stopped, then a start: the body is unreadable — `items: null`, the version is intact, `cas` by it replaces the row;
  the version is lost — 503 for a read and for an affected listing (P/01.1 N2). Without the profile command —
  not_executed.
- The lost version of a row that the store reads after a restart (sc. 36): two rows, `@restart store`, then `@spoil row-index` of one of them. The step of `@spoil row-index` (step 4) spoils the version in the place from which the restarted store reads that key: for a store that moves its rows into a saved state at a checkpoint or at a stop, that saved state, not only the tail of its log; a spoiling of a copy that the store does not read after the restart leaves the scenario without its subject, and the implementation names in its description where its command spoils. Then the read, the listing of the key, `put` with `cas: ""`, `put` without `cas` and a guard on the key are each 503 `unavailable` (`version_lost`, P/01.1 R028, R212), not an absence; the guarded write leaves no row, the key still reads 503, the neighbouring row reads with its version.
- The `id` replay memory (P/01.1 N3) is held for no less than two minutes; the right to forget after 2 min and 50 000 writes — by reading.
- A row key with `..`, the `generation_at` of the floor not a time, the stand clock earlier than the `generation_at` of the floor of the input (without `-force` of the directive `@import store`) — a refusal of the whole input (N1.3 `import`, `floor`; the outcomes of the family `epoch_floor`). A damaged row exists for a guard and for a deletion (P/01.1 N2): the guard `""` — 412 with its version, by the version — holds; deletion with `cas: ""` — 409, with `cas` by the version — the row is gone; without the profile command `spoil-row` — not_executed. Service doors (N2): an extra field in `join`, `leave` and `op: floor` and a bad member `id` — 400; a refused floor is not written. 405 for `POST /metrics`, `GET /v1/join`, `GET /v1/leave` (N4).

## Scenario boundaries

Between scenarios the runner stops the processes, resets the store and the variables; the group members and their directories too.

## Full form and reproducibility

Before each automatic scenario stop the processes of the previous one, create separate empty row/object stores and clear the variables/replay memory. Load the unchanged testsub and testsub2; root is testsub, the second is available under /testsub2; there is no domain, requests come from the loopback. The background controller/resource/worker do not work before @start. The build is schema 1; the absence of platform/schema is confirmed by reading. For each POST that creates a unit the runner issues a fresh Idempotency-Key, kept only for the replays of the same step. A table POST does not get a promise of replay memory from this.

A subset of expect does not replace the check of the full HTTP form of the OpenAPI of the lesson: check the mandatory fields, types, Content-Type, special headers and the absence of a body for HEAD/204. In expectation lines `$name` is first bound only after a successful match of the whole answer; the following uses compare, and requests use only values already bound. A failed attempt of @until does not change the variables. @until repeats a read until the given local deadline, not a mutation; after it expires — FAIL with the last answer. @any admits any value of a present field, @absent requires absence; they do not replace the types of the full schema. A JSON object is compared by subset (`{}` at any level is exactly an empty object: the dictionary of the common README), an array by length and order. Raw HTML/text is compared as UTF-8 bytes with the given substring, it is not parsed as JSON.

In total 29 scenarios / 350 steps, all automatic (judge-only: `acceptance/3/scenarios.tsv`). The floor goes only upwards, only admin. The replay memory of `op: floor` is in the store
(chapter 1.3 N2): a replay with the same `id` after a restart — the same `index` and `again`, a different `floor` with this `id` — 400; an implementation
that keeps it in process memory answers 409 «only upwards» after a restart, and the scenario does not pass.

## Additional check by reading

By reading: 503 unavailable after the effective -leader-wait interval without a leader, ambiguous after an unknown outcome (a lost answer of a forwarded write — sc. 32–34) and unavailable with Retry-After at the connection limit are different branches. Sc. 05 of [the system acceptance](../../../common/acceptance/system/README.md) with one dropped server keeps the quorum and does not check all the 503 branches. A replay of id with another floor — 400 badrequest. For /v1/write and /v1/rights an unknown method gives the 404 of the owners; 405 only for status/join/leave/metrics. The metric of sc.04 is configstore_raft_voters_expected. The launcher values follow P/02.4 and the daemon defaults belong only to forms/daemon-flags.tsv; an override of the profile is declared before acceptance.

This is a subject of a manual check of the specification and of a future check of an implementation. The prepared requests, the reading and the finite models of the author are not a performed stand test.

## Review seams

The kit seams checking P/01.3-R006, P/01.3-R026 and P/01.3-R156 use the CALL/JSON grammar of [P/02](../../../02-installer/forms/README.md). These five kit seams assist the existing acceptance and reading; they are not new public runner targets. The existing chapter 1.1 s2 seam repeats the **same id** after early and a clock advance (judge-only: seam s2 of `acceptance/1/seams.tsv`).

`store-start-flags` invokes the ordinary daemon command-line parsing and startup configuration admission (before build-specific Raft capability checks), not a validator that exists only for tests. Valid temporary dir/sockets, id and all neutral inputs are supplied. loopback/non_loopback select valid addresses under the existing loopback predicate, not new address syntax. Missing TLS must refuse before network setup; observe actual calls and exit code. Acceptance here proves configuration admission, not full process/group execution.

`store-copy-floor` uses the actual durable backup/import/continuation paths. First restore a valid seed, take a real backup of that restored store with its existing floor and at least two other rows, then import that immutable backup into a fresh destination. Interrupt I/O after one non-floor target row has been durably transferred; close and continue the same attempt with the same input. Capture the first new floor row F1, including items/index/generation_at, and compare it after continuation. Inspect actual write order, every non-floor row/version, completeness and absence of an old-floor transfer. Use a controlled wall clock; no canned backup/import result or fabricated expected observation. A panic, unrelated failure or unexecuted path fails.

`store-import-held` uses the actual daemons of a group and the actual durable import and continuation paths. Start a live group of three voters with mTLS that holds no business rows, take a real backup of a store with at least two non-floor rows and import it into the group through `admin.sock` of the leader. Interrupt the operator command after one non-floor target row has been durably transferred and before the next one; the members keep running, so the attempt stays unfinished. Then read a transferred key at the leader and at a follower through their ordinary role sockets and write a key through the leader. Continue the same attempt with the same input through `admin.sock` of the leader. A panic, an unrelated failure or an unexecuted path fails.

Each port receives exactly the JSON object below and returns its own result object as the value of the existing CALL/bridge protocol. Inputs and results are closed objects: every named field is required, except the conditional fields stated below; no other fields are admitted. These are test-side observations of the ordinary implementation, not product command payloads.

| CALL port | Input object | Result object |
|---|---|---|
| `store-start-flags` | `api`, `raft`, `join`: each is a string from `absent`, `loopback`, `non_loopback`; `tls`: boolean | `config_accepted`: boolean. If true, this is the only field. If false, also `exit`: integer CLI exit code, and `network_setup_calls`: nonnegative integer count of actual network setup calls before refusal. |
| `store-copy-floor` | `input`: the string `backup_of_restored_store`; `interrupt_after_target_rows`: integer `1` | Six booleans: `first_write_is_new_floor`, `new_floor_greater_than_input`, `old_floor_transferred`, `same_floor_row_after_resume`, `other_rows_and_versions_equal`, `complete`. |
| `store-import-held` | `input`: the string `backup_into_live_group`; `interrupt_after_target_rows`: integer `1` | Four booleans: `leader_read_unavailable`, `follower_read_unavailable`, `write_unavailable`, `complete`. |

For startup, `absent` omits that flag, while each address class selects an otherwise valid address in that class; `tls` chooses a valid kit or its absence. The adapter supplies a fresh valid dir/sockets and explicit id, and leaves other neutral flags at their valid values. `config_accepted` observes admission after ordinary flag/configuration checks, before build-specific Raft capability checks; it does not claim a serving process. On refusal the adapter reports the actual exit and network setup count. No test-only validator substitutes for startup.

For the copy port, the input token selects the seed/backup/import/continuation procedure above. The controlled wall clock makes the seed valid and stays fixed throughout transfer and continuation. `first_write_is_new_floor` compares the first destination row write with the new floor row; `new_floor_greater_than_input` compares its numeric floor with the backup floor; `old_floor_transferred` records whether the input floor row was ever transferred as a target row.

`same_floor_row_after_resume` compares F1's exact items, index and generation_at before and after continuation. `other_rows_and_versions_equal` compares every non-floor row with the immutable backup; `complete` observes successful completion with exactly those rows plus F1. Interruption occurs after the first non-floor target row's durability barrier and before the next target row, so the attempt remains unfinished. Values come from actual I/O and retained state; a panic or unrelated failure is a failed call, not a result object.

For the held import, `leader_read_unavailable` and `follower_read_unavailable` observe that the read of a transferred key at the leader and at the follower while the attempt is unfinished is 503 `unavailable` with no row data: reads answer as the store `file://` (P/01.3 R156, R159, R413); `write_unavailable` observes 503 `unavailable` for the write at the leader, and that its key is absent after the continuation. `complete` observes that the continuation exits 0 and that the leader and the follower then read every row of the backup with its version. Values come from actual answers of the daemons; a panic or unrelated failure is a failed call, not a result object.

## Non-default service body limit

Use the existing fresh-stand body_limit parameter (the daemon -max-body), for example2097152 from the status-limit witness above (judge-only: `acceptance/3/inputs/status-body-limits.json`). Let B be that actual limit reported by max_body. Send POST /metrics with one JSON object padded by JSON whitespace to exactly B entity bytes: the frame passes and the existing method outcome is405. At B+1 entity bytes the answer is413 before the method outcome, with BodyTooLargeFault.limit equal to B, not the row ceiling or the default of the flag. Repeat the oversized body at a service POST route: it is refused before JSON/body or membership work. Compare membership before/after; it is unchanged. Preserve the ordinary full Fault/header checks and the independent max_value observation. No new profile key, command spelling or request grammar is needed. These are raw HTTP probe obligations on the actual daemon, not a source/schema execution result.

## Production qualification coverage

The [production acceptance contract](../../qualification/README.md) (judge-only: qualification procedures) assigns the workload, phase-deadline, copy/stop, fault-stage and HTTP-copy groups separately from these functional scenarios. Their declared budgets, independent activation and complete observations are required for a production result. Existing TSV inputs/expectations and ordinary/group applicability remain unchanged; a missing binding or budget is blocked/NotExecuted, not PASS.

For the bindings of the target `P/01/production` the words of the payload mean the following. The boundary `admission_time` is the wall clock of the daemon process that P/01.1 N3 «Admission time» reads at admission: the provider observes this clock domain of the process, and the admission time that the daemon stores is judged by the public outcomes of the case, not by the provider. The resource `heap` is the resident anonymous memory of the process (`RssAnon` of `/proc/<pid>/status`), and `memory` is its resident set (`VmRSS`); a heap figure of a language runtime is no resource of the form. With the latch `sink` the provider is the reader of the output, and `cancel` is its deactivation: the provider closes the sink at `deactivate`, the `monotonic_ns` of the deactivation record is that moment, and no observation carries `cancel`. The phase `recover_mark` names no file: the mark is the first changing step of `recover` in `-dir` (P/01.3 R265), and the point of the fault is the first change of `-dir` after the first top-level entry that `recover` completes, so neither the payload nor the invocation carries a name of the mark. The phase `copy_after_headers` is the end of the stream as the client receives it after the complete header block of a `200`, made between the daemon and the client: it gives the half of `RUN-H03` that the CLI judges. The half of the daemon after `200`, only an incomplete close and no second fault, is judged on its own stream under the cancellation, the stalled sink and the stop that the judge makes; a failure inside the daemon has no binding.
