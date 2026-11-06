# P/05 — Resource: norms

This English text is the source; the Russian translation `ru/spec/05-resource.norms.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The canon of the lesson. Lecture (`ru/05-resource.md`, for people, not in the export), [contract](05-resource.api.openapi.yaml), [instructions](05-resource.README.md),
[life cycle](../lifecycle.md), [acceptance](../acceptance/README.md). The lesson is moved from
M10/8 (stage B, ADR-0083 addendum (1): without a change of
behaviour): N1.1, N1.2 without suppression, N1.3, N1.4, N1.6 without the form `answered`, the resource doors of N2, the procedures «write
an event» (the side of the owner of the file contract), «query (resource)» and «resource pass», the resource rows of N4 and N5; from
M10/10 — the bodies at the resource: the body copy to a neighbour and its door (N1.5
`mirror`, N2), its own ceilings (N1.4), tombstones and convergence of copies (N1.5 `delete`) — here N1.1 «Bodies at the resource», «Tombstones»,
and the schema check at the resource start (N3, part of M10/10-01); from
M10/11 — `restore` of events from neighbours (N1.4
there, here N1.4 «Bucket restore»). The numbers of the subsections are the former numbers of M10/8. The form of the event line, the event id,
the buckets, the writers of the file, the encoding of names and the writing of a line (review of stage B 3–5, V1) are [the event log contract](../../common/contracts/event-journal.md); the presence
lock and the count `room` are [the presence lock contract](../../common/contracts/presence-lock.md) (review of stage A
3–5, № 9): the lesson is the owner of both. The request of N1.5, the merge, the reaper, the submission and the console doors are [chapter 6.4](../../06-console/spec/06.4-console.norms.md) (P/06);
repeat suppression and the execution of requests are [chapter 3.6](../../03-worker/spec/03.6-worker.norms.md). «P/0N» is a lesson of the
module, «P/0N.K» is its chapter; «M10/N» without an address is a former lesson (the history of the move). Norm ids are `P/05-MM`;
the map to former ids is `id-map.tsv` (historical record).

## N0 Vocabulary

<!-- req: P/05-R001 -->

Normative keywords (MUST, MUST NOT, SHOULD, MAY by RFC 2119 and RFC 8174) follow the [course canon](../../common/NORMATIVE-TERMS.md). The rules of the module are [P/01.1 N0](../../01-store/spec/01.1-store.norms.md#n0-vocabulary).

## N1 Form

<!-- req: P/05-R002 -->

**Time.** The time fields of the rows and objects of the lesson are time by [the canon of N0 of P/01.1](../../01-store/spec/01.1-store.norms.md#time-in-a-row): the event line — `t` ([the event log contract](../../common/contracts/event-journal.md)); the resource heartbeat object `platform/resources/<server>/heartbeat` — `ts`, `usage_at`, `pass_started`; the door row `platform/doors/<host>` — `since`, `at`; `<sub>/requests/free-<server>-<volume>` — `at`; the tombstone `.gone/<object-key>` — `written` (written by the console, [P/06.1](../../06-console/spec/06.1-console.norms.md) N1.5).

<!-- req: P/05-R003 -->

**Data** ([catalogue](../../common/data/catalog.tsv)):
- owns: `platform/resources/<server>/heartbeat`, `platform/doors/<host>`, `<sub>/requests/free-<server>-<volume>`, `<events root>/<sub>/<unit>/e<epoch>/<YYYYMMDDTHHMMSSZ>.events.jsonl`, `<events root>/<sub>.alarms/<unit>/e<epoch>/<YYYYMMDDTHHMMSSZ>.events.jsonl`, `<events root>/audit/<role>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl`, `<events root>/audit.alarms/<role>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl`, `<events root>/console/<instance>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl`, `<events root>/console.alarms/<instance>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl`, `<events root>/.mirror/<server>/<tree>/<unit>/e<epoch>/<YYYYMMDDTHHMMSSZ>.events.jsonl`, `<events root>/.workers/<sub>/<instance>.lock`, `<events or objects root>/<path>/%h<sha256>.name`, `<objects root>/<dir>/~lock` (ADR-0083 addendum (16)), `.gone/<object-key>`, `objects/<sub>/<manifest:objects.rows>`, `objects/<sub>/<manifest:objects.rows>/*`;
- writes: `<sub>/blobs/sha256-<hex>` (put);
- reads: `platform/manifest/<sub>`, `platform/manifest/<sub>/rev`, `platform/schema`, `<sub>/heartbeats/<name>`, `platform/decommission/<host>`, `platform/doors/<host>`, `platform/resources/<server>/heartbeat`, `<sub>/retention`, `<sub>/alarms_retention`, `platform/space`, `platform/mirror`, `<sub>/<manifest:tables>/<name>`, `<sub>/<manifest:unit.rows>/<id>` (the unit rows of the manifest with about — the addressee of a hold, the holds contract; P/02.5 N1.4), `/etc/w2c/tls/<role>/server.key`.

<!-- req: P/05-R004 -->

The resource reads the key of its own kit with `RESOURCE_TLS=1` (N1.4 `door.mode` `mtls`, `cert_until`; «Admission to the
resource doors»; [the role certificate contract](../../common/contracts/role-certificate.md) `kit`) (review of stage B 3–5, № 10).

<!-- req: P/05-R005 -->

The resource puts body copies to a neighbour (put) and deletes its own copy older than the tombstone (delete); it confirms tombstones (cas) and
removes them (delete) — N1.1 «Bodies at the resource», «Tombstones».

### N1.1 Object

<!-- req: P/05-R006 -->

```yaml
object:
  client:    the address OBJECTS, the operations (rule, api, ops), the reading of cluster objects, the outcomes and the action of the client — the object
             store client contract common/contracts/object-client.md (moved there without a change of behaviour; C10-OBJECT-ADDRESS-32)
  key:       <family>/… ; the families of the platform: heartbeats, contenders (P/03.4, P/03.2), controller (P/04), snapshot, blobs (added by M10/10),
             commands (the contract of the request and its mark, «Mark» mark; review of stage B 6–7, № 24) — the manifest does not name them
  writer:    one directory — one writer: worker → <s>/heartbeats/*, <s>/contenders/*;
             controller → <s>/snapshot/* (added by M10/10), <s>/snapshot-tables/* (ADR-0110), <s>/controller/*; console → <s>/blobs/* (added by M10/10); resource → platform/resources/*
  cluster:   a file on the server of the writer; on reading the fresh copy (written) wins; a server that did not answer is missing
  written:   the mark of the keeper resource at the write of the key (X-Written of the door, written of the listing), not a time field of the body; every
             write of the key sets written strictly greater than the former written of the same key: the clock has not moved forward — the former
             + 0.001 s; therefore a new write of the same bytes is a new version, the same (server, written) is the same version
             (the observation contract «changed»; guess of stage C C06-OBJECT-VERSION-33-01, the decision of the Architect of 2026-10-23);
             a body copy (PUT .../blobs/<digest> with X-Written, the mirror) keeps the written of the source copy, not its own: otherwise a copy
             that lay before the delete would be newer than the tombstone; for a copy of the same key already lying there written does not decrease
             (the greater of the two) (C05-COPY-WRITTEN-SOURCE-01); for a key deleted here the former written is the written of its
             tombstone `.gone/<object-key>` while it lies: a new write is strictly greater than it (otherwise the neighbours would count it older than
             the delete, the tombstone contract `drop`, `rewrite`); there is no separate memory — the tombstone is the mark; a write
             after written removes the tombstone by the same action, before the answer of the write (the tombstone contract `rewrite`;
             C05-GONE-REWRITE-AT-WRITE-01, the decision of the Architect of 2026-10-30, norm questions of the Gemini audit, P/05 item 1); the tombstone
             is removed — the bound is only the former rules (C05-WRITTEN-AFTER-GONE-01); the tombstone is unreadable (garbled) — the bound
             is not known, the write is not refused: written by the former rules, the tombstone stays (it is not removed: a write
             after written is not proven), the next delete of the body rewrites it (C05-WRITTEN-AFTER-GONE-02)
  row_object: keys whose next writer can be on another server are store rows objects/<key>
             (objects.rows of the manifest; commands/* — always, for a manifest with requests); put_new = a write with cas ""
  door:      only the families PLATFORM_DOOR (platform/resources/*, domain/* (M11), */heartbeats/*, */contenders/*, */snapshot/*, */snapshot-tables/*,
             */controller/*, */blobs/*; snapshot and blobs — added by M10/10) and objects.door of the manifest; anything else — 403;
             tombstones .gone/<object-key> — read only: the listing prefix=.gone/ and GET of the body (the tombstone contract; C05-GONE-BODY-READ-01);
             `*` of the first part is a subsystem of the manifest catalogue: `other/heartbeats/x` without a manifest other — 403 (reconciliation of python and go M10/6–11, E5)
             the resource does not parse the bodies of door objects: an object unreadable by its family (a worker heartbeat, a mark) it gives
             as it is, the judgement is with the reader (V7 item 3, the decision of the Architect of 2026-10-28, on the proposal; line 24 of the list)
  disk:      <PLATFORM_DIR>/objects/<key>; directory 0775, file 0644; the write — temp + rename under the directory lock `<dir>/~lock`, flock(LOCK_EX), the file
             is not deleted; service names (the lock, the temporary name) — the event log contract «File names» (ADR-0083 addendum (16))
```

<!-- req: P/05-R007 -->

An object key is a non-empty relative path: non-empty segments, without exact `.`/`..`,
backslash and control characters. `prefix` is the beginning of such a key, also emptiness
or an ending `/`; it is not a full key. The objects door does not give row objects even from
an allowed prefix. With equal `written` the server with the lexicographically greater
name is chosen; the absence of an answer is called `missing`, not the absence of the object. A
listing returns the closed form ObjectListing of N2; deleted objects are tombstones `.gone/<object-key>` (below, «Tombstones»): an ordinary listing does not show them, `prefix=.gone/` is
a read-only listing of tombstones (log of cammeta-go, lesson 10 № 2).

<!-- req: P/05-R008 -->

A listing gives only the keys of the door families under `prefix` — a filter, not a refusal: `prefix=testsub/`, `prefix=t`, an empty
`prefix` — 200 with the keys of the door families that start with it; keys outside the door families do not enter the listing. A `prefix`
with which no possible key of the door families starts (`other/`) — 403. A `prefix` not in UTF-8 (`%FF`) — 400. Reading
a key: a key not by the grammar (not UTF-8, Cc, Zl, Zp — including U+2028, `.`/`..`, an empty segment) — 400; a key outside the door
families, including the directory `testsub/heartbeats` of two parts, — 403; a key of a family that does not exist (including a directory inside
a family, `testsub/heartbeats/sub`), — 404; a key that differs from the written one only by case or normalization (`W-1` with
`w-1`), is its own key: 404, not another's object (reconciliation of python and go M10/6–11, E1, E2, E4, E7, E8).

<!-- req: P/05-R009 -->

**File names in shared trees** — one encoding for all implementations: [the event log contract](../../common/contracts/event-journal.md#file-names-in-shared-trees)
(moved there from this subsection; review of stage A 3–5, № 9).

<!-- req: P/05-R010 -->

A file system error after admission is a refusal of the write, not a success and not «there is no file».

<!-- req: P/05-R011 -->

**Bodies at the resource** (moved from M10/10 N1.5 `mirror` and N1.4, parts of
M10/10-06, -07, -08 by the `note` of id-map; the decision of the Specification on question V2 of the move; the field `blob`, the digest, the bytes door of
the console, the cleanup of bodies — [chapter 6.1](../../06-console/spec/06.1-console.norms.md) N1.5):

<!-- req: P/05-R012 -->

```yaml
mirror:   every local body — to the next copies live neighbours of the ring (N1.4 mirror), always, regardless of mirror.enabled;
          copies — from the row platform/mirror (an integer ≥ 0), no row or no field copies — 1 (log of cammeta-go, lesson 10 № 1); the row
          does not read — bodies are not copied in this pass, the reason is in the heartbeat (settings_unread: mirror; V7 item 3, the decision of the Architect of 2026-10-28, P1; line 20 of the list);
          reception: hash while reading; PEER_FAILS 3; the copy door exists only for the key `<sub>/blobs/sha256-<64 lowercase hex>`
          of a subsystem with a blob field; another key (uppercase hex, without `sha256-`, a subsystem without a blob field) — an ordinary object,
          its owner writes it: 405 (reconciliation of python and go M10/6–11, T11)
```

<!-- req: P/05-R013 -->

Resource ceilings (the rows of the table M10/10 N1.4 «Ceilings», now [P/06.1](../../06-console/spec/06.1-console.norms.md) N1.4; checked at the door before reading the body where
possible; a refusal, not a truncation):

<!-- req: P/05-R014 -->

| What | Limit | Where | Words / code |
|---|---|---|---|
| an object at the resource door (reading, body copy, mirror piece) | 64 MiB | the resource door (N2) | `413` |
| lines in the answer of `/events` | 1000 by default, 10,000 the limit | the index (N1.3) | truncation, `truncated` |
| retention term | a finite number > 0 | the resource (N1.3 `retention`) | «not known», remove nothing |
| the object store | `max_bytes` (0 — no ceiling); the store says it itself | `put` | `TooLarge` «over this store's limit» |

<!-- req: P/05-R015 -->

Body cleanup ([P/06.1](../../06-console/spec/06.1-console.norms.md) N3 «body sweep»): in the exclusive window the operator also closes the incoming mirror copies; a copy
than which the tombstone of the deleter is newer is not accepted (N4, «deleted later» — 409).

<!-- req: P/05-R016 -->

**Tombstones and convergence of body copies** (moved from M10/10 N1.5 `delete`,
M10/10-09; the bodies, their digest, the bytes door of the console, the mirror of bodies at the console and the cleanup — [P/06.1](../../06-console/spec/06.1-console.norms.md) N1.5):

<!-- req: P/05-R017 -->

```yaml
delete:   the tombstone .gone/<object-key> {written, peers, acked}, the neighbours peers, the reading by a neighbour, the confirmation 404 and the removal —
          [the tombstone contract](../../common/contracts/tombstone.md) (moved there without a change of behaviour; C06-BLOB-GC-33-01, the decision of the Architect of 2026-10-25);
          the objects door has no DELETE
```

### N1.2 Event

<!-- req: P/05-R018 -->

The form of the event line (`line`), the bucket and its path (`bucket`), the class (`class`), the journal `audit` (`journal`), the writers of the file
(`writer`), the event id and the writer instance — [the event log contract](../../common/contracts/event-journal.md)
(moved there from this subsection; review of stage A 3–5, № 9). The lesson is its owner: the resource reads buckets (N1.3),
copies the closed ones (N1.4 `mirror`), removes them by term (N3 «resource pass»). Repeat suppression (`suppress`) —
[chapter 3.6 N1.2](../../03-worker/spec/03.6-worker.norms.md); `older_epochs` and the operator marks (`marks`) —
[chapter 6.4](../../06-console/spec/06.4-console.norms.md) N1.2 (the console).

<!-- req: P/05-R019 -->

`subsystem` of an index line is the name of the manifest, for the lines of the alarm tree too (`testsub`, not `testsub.alarms`; reconciliation of python and go M10/6–11, E32).
`unit` in the answer of the index is the full reference `<tree>/<unit>`;
for the journal it is `audit/<role>`, for a mark — `console/<instance>`, and its `of` is the addressee. The reference is logical: the tree is without the suffix
`.alarms`, which is the layout of the writer ([the event log contract](../../common/contracts/event-journal.md) `class`); a line from `audit.alarms/<role>`
answers and is selected by a query as `audit/<role>`, from `<sub>.alarms/<unit>` — as `<sub>/<unit>`, together with the observations (N3 «query»
step 2; the Architect's decision of 2026-10-27).

### N1.3 Index and term

<!-- req: P/05-R020 -->

```yaml
index:
  one_per_resource: over its own tree and the .mirror/<server>/ copies; the state is always live; there is no rebuild
  cache:    bounded (64 MiB), dropped without loss of correctness; a file is reread by size/mtime/inode from the place
  query:    the query rules that the merge needs (parameters, defaults, by) — the event log merge contract «The resource query and answer»
            (moved there, EM-READ-33-01); the grammar of the parameters and the refusals — below this block
  row:      {id, subsystem, unit, of, epoch, t, kind, server, bucket, class, epoch_is, fenced, …fields}
            # server — the owner of the bucket; a line with its own field server (a line about a server: drain.*,
            # server.decommission_*, workers.no_server) keeps it — in such a row server is the server the line is about, the index
            # does not overwrite it, as class (G06-AUDIT-SERVER-01, the Specification's decision of 2026-11-05)
            # epoch_is and fenced are set by the merger — the console or the worker by the event log merge contract; at the resource the lines
            # are without them (the decision of the Architect, review of stage A; ADR-0091 addendum (27) item 7)
  epoch_is: current | fenced | earlier-run | unknown   # by current_epochs from <sub>/epoch/* and the policy of the manifest; unknown — only
            # at the worker for an epoch that it did not declare in worker.reads; the needed epoch is not read — a line without epoch_is,
            # incomplete[<sub>/epoch] (the event log merge contract «Epochs»; ADR-0091 addendum (24) item 4, addendum (27) item 2)
  cut, answer: the cut, the mirror copies, truncated, partial — the event log merge contract «The resource query and answer»; the answer
            of the merger (the console, the worker: + complete, incomplete) — in the same place, «The answer» (moved, EM-READ-33-01)
retention:
  <sub>/retention:        {days}      # the default — the event log contract «Retention of a tree»; the form of the row — P/02.4 N1.9
  <sub>/alarms_retention: {days}      # the default — the event log contract «Retention of a tree»; the form of the row — P/02.4 N1.9
  writer:   of both rows — admin by the operator command w2cctl retention (P/02.4 N1.9); the resource and the console only read them
            (P/02.5 N1.4; the store pilot, the decision of the Architect of 2026-10-18)
  rule:     per subsystem, not per unit (ADR-0076); days — a finite number > 0, anything else — «not known», remove nothing;
            the console marks live no less than the longest tree; the holds (holds) keep buckets (the holds contract);
            mirror copies — an hour longer; what is removed — the journal events.removed
```

**Retention deadline** (ADR-0127, review of P/05 C4). Use the bucket's own persisted logical `written` from the event-journal contract “Bucket write time”. First resolve term reads and holds conservatively; a hold or unknown dependency keeps the bucket. For a closed, unheld bucket with readable `written`, delete exactly when `now >= written + seconds`: normal `<sub>` uses `seconds = retention.days * 86400`; `<sub>.alarms` uses `alarms_retention.days * 86400`; `audit`/`audit.alarms` use their journal term; `console`/`console.alarms` use their term with the longest-tree floor. A mirror copy uses the corresponding tree's term plus `3600`, measured from its own copy `written`. Equality deletes; a time below the deadline keeps it. Neither window start/end nor filesystem `mtime` substitutes for `written`. Restore preserves the copy's `written`; it does not restart the retention clock. All usual conservative holds and read outcomes precede this predicate.

<!-- req: P/05-R021 -->

The merge of the resource answers by the console (`merge`) — [chapter 6.4](../../06-console/spec/06.4-console.norms.md) N1.3
and N3 «merge» (the console); the form of the console answer (`answer` above, `ConsoleEvents` of the contract) is common with the resource.

<!-- req: P/05-R022 -->

A query uses finite `from`/`to`, `from ≤ to`; `limit` is an integer 1…10000 (reconciliation of python and go M10/6–11, E12–E15):
- `from`, `to` — an ASCII decimal number: an optional `-`, digits (`_` is allowed between digits), an optional dot with
  digits on at least one side, an optional exponent `e`/`E` with a sign; `1_0`, `.5`, `5.`, `1e3` are numbers,
  `1e-400` is 0; `+1`, a space (`%201`, `1%20`), non-ASCII digits (`١`), `0x10`, an overflow — 400;
- `limit` — only ASCII digits (leading zeros are allowed: `01`), otherwise 400; `since` of the hint — by N1.6;
- `unit` — UnitRef `<sub>/<id>`: a bare id, empty, `testsub/`, `/c1` — 400;
- `late` — an integer ≥ 0 in decimal notation, only together with `by=occurred`: anything else — 400 (C05-QUERY-LATE-01);
- an empty or repeated parameter — 400 (N2); an unknown non-empty parameter is not read (for `/events/wait` — 400, N1.6).

<!-- req: P/05-R023 -->

**Unreadable bucket line** (P/01.1 N0 «Stability of output»; reconciliation of python and go M10/6–11, E19, E24, E32). A line that is not JSON,
not an object, with a BOM, with a number outside JSON (`NaN`), without `kind`, `t` or `id`, with `id` not a string, and also a file not in its place
(a bucket path not by N1.2, for example `e01`) is skipped: it does not enter `events` and `truncated`, the answer is 200, and the number of such
lines is `lines_garbled` of the answer (the field is present only when it is greater than 0). A torn last line is still `partial`,
not `lines_garbled`. The console adds up the `lines_garbled` of the answering resources and itself skips a line of a resource answer not
in the form EventRow, adding it to its own `lines_garbled`. `events` in BucketInfo is the number of whole readable lines of the bucket;
500 of a listing — only an unreadable directory or metadata.

<!-- req: P/05-R024 -->

Another query form — 400, including NaN/Infinity, a fractional limit and a bare unit. `by`, the defaults, `truncated` of the resource and
of the merger — the event log merge contract «The resource query and answer» (EM-READ-33-01).
`fenced=true` if and only if `epoch_is=fenced`; earlier-run is not fenced.
This lesson does not promise an atomic snapshot of several files or resources.
An unknown read of the term or of the holds does not equal absence: a dependent tree is not deleted
until a reliable read. An absent retention row gives the default, a read error does not.
`complete`, `partial` of the merger — the event log merge contract «The answer», «The resource query and answer».

### N1.4 Resource

<!-- req: P/05-R025 -->

```yaml
resource:                                    # one process per server; without a controller
  heartbeat: the object platform/resources/<server>/heartbeat every 10 s
    {server, ts, url, schema, build, usage, usage_at, space: {total, free, used, full}, volumes, units: {sub: [id]},
     workers, running, short, waits, mirrors: {server: n}, pass_started, pass_stalled, restore, mirror, door,
     retention_garbled?: [<sub>…], retention_withheld?: {<sub>: days_garbled | unknown | holds_unread}, …}
    # retention_garbled, retention_withheld — the reasons of the retention pass (N3 retain, N4; no reason — no fields; C05-RETENTION-PULSE-33)
    # settings_unread?: [mirror | space] — the setting rows of the pass that did not read: the step mirror (and the body copies of N1.1) or
    # relieve is not executed in this pass; in ascending order of bytes; none — no field (V7 item 3, the decision of the Architect of 2026-10-28, P1; lines 20, 21 of the list)
    # door: {addr, mode: loopback | mtls, cert_until} — in every heartbeat, written by the resource (ADR-0075 addendum (3)): addr —
    # RESOURCE_HOST:RESOURCE_PORT; mode — loopback without RESOURCE_TLS (loopback only), mtls with RESOURCE_TLS=1; cert_until —
    # the wall seconds of the end of the term of the server certificate of its own kit, with mtls; with mtls the server presents the leaf, then its authority
    # (the role certificate contract server; the client — own_client, the object client contract tls; norm review of ADR-0075, Claude fd85ea8cc, S-2); read by w2cctl tls status (P/02.4 N1.9; review of stage B 3–5, № 28)
    # waits, restore, mirror, units — in every heartbeat (reconciliation of python and go M10/6–11, E39): units — {<sub>: [<id>…]} of the units that
    # the heartbeats of the workers of this box from running name in status, ids in ascending order of bytes; none — {}; a worker heartbeat
    # is unreadable (the family heartbeats P/03.4: the whole object, for the resource also an element status[] not in form) — its units do not
    # enter units: the unreadable does not widen (C05-UNITS-PULSE-GARBLED-01, the decision of the Architect of 2026-10-30, norm questions of the Gemini audit, P/05 item 3)
  workers:   [<sub>/<slot name>…] — all the slots that the resource knows about on its box; running: [<sub>/<slot name>…] — with a
             live process (it holds the presence lock, the content in form with a non-empty worker); unknown: [<sub>/<slot name>…] —
             the presence did not read and the slot is known from current readable content (otherwise the whole-role unknown snapshot below): the lock file does not read (review of stage B 3–5, № 23) or flock/stat of the lock gave an error,
             except «busy» and ENOENT of stat (the presence lock contract; (the decision of the Architect of 2026-10-20, review of stage B 6–7));
             instances: {<sub>/<slot name>: <instance>}; the key is with the subsystem: a slot name is unique only within its own
             subsystem (P/03.2 `<sub>/slots/<name>`), two subsystems with one `slot.prefix` have the same names; pass_stalled: <seconds>, only while the pass hangs (PULSE_LIMIT)
             # one heartbeat form: the console gives it as ResourceRow P/06.5 (a derived output), the controller
             # derives the presence from it (below, P/04 «fate»)
  usage:     an integer — the bytes of the bucket files of the trees of this server and of the copies in .mirror/; usage_at — the wall seconds
             of the measurement; space — the volume of the event tree: total, free, used — bytes (statfs), full — the share used/total from 0 to 1
             (not a flag); volumes — the same per volume (log of cammeta-go, lesson 9 № 1)
  door_row:  platform/doors/<host> {url, since, at, room.<sub>…, live.<sub>…}; at — every ALIVE_EVERY (the observation contract «Resource state»; layout audit, the decision of the Architect of 2026-10-25, A-10)
  room:      the elements room.<sub> and live.<sub> — by the presence lock contract «Count room» (presence-lock.md; moved
             there, review of stage A 3–5, № 9; live.<sub> — ADR-0084 addendum (3) R14′, № 3, 19)
            do not write the door while platform/decommission/<my server> stands (the observation contract «Server decommissioned» narrower; the console deleted it)
  lost_after: LOST_AFTER                      # the observation contract «Freshness» (layout audit, the decision of the Architect of 2026-10-25, A-01); by a change on the clock of the reader
  pass:      the first — at start, right after readiness (the door row is written); then every 600 s from the end of the pass
             (C05-PASS-FIRST-AT-START-01): retain → usage → relieve → mirror; each step in its own attempt; pass_stalled on a hang
  space:     platform/space {enabled: true | false, high: 0.85, low: 0.75}   # shares; enabled until switched off:
             # no row — enabled with the thresholds 0.85/0.75; enabled: false — the resource removes its own row free-* (reconciliation of python and go M10/6–11, E45)
             # the row does not read — the step relieve is not executed: the defaults 0.85/0.75 are not substituted, its own row free-* is
             # neither written nor removed, the reason is in the heartbeat settings_unread: space (V7 item 3, the decision of the Architect of 2026-10-28, on the proposal; line 21 of the list)
             # the form of the row — P/02.4 N1.9 (written by admin, w2cctl space)
  free_ask:  <sub>/requests/free-<server>-<volume> {free, volume, server, at}   # its own form (ADR-0059): written and rewritten with cas only
             by the resource, not create-once, without unit/digest/family schema; for manifests with requests.free, while the volume > high;
             for requests.free volume — a non-empty name of ASCII A-Z/a-z/0-9/_, 1–64 bytes, without a hyphen (a box has one volume —
             the file system of the event tree, the name events); server — a non-empty key segment of P/01.1, hyphens are allowed.
             The split at the last hyphen is unambiguous. Another volume is out of profile: diagnose the configuration, do not create/change the request of this volume;
             free = used − total·low − Σ freeing from the heartbeats (only the freeing not yet reflected in used); with free ≤ 0 (and under the mark low) the row is removed (ADR-0059); nobody executes or marks it;
             the addressee — all the workers of the subsystem <sub> on the server <server>; <volume> — the volume of the resource, not a place of the subsystem;
             Σ freeing — the sum of freeing.<volume> (P/03.4 N1.1) over the live heartbeats of the workers <sub> on this server, no field — 0
             (vectors 05-resource/vectors/relieve; the VMS request freeing, the decision of the Architect of 2026-10-23);
             between low and high, while need > 0, its own row stands as it is — it is neither removed nor rewritten (reconciliation of python and go M10/6–11, E44)
  mirror:    platform/mirror {enabled, copies}; no row or no field enabled — enabled: false, buckets
             are not copied until enabled: true (guess of stage C R05-G05, the decision of the Architect of 2026-10-23); the row does not read —
             the step mirror is not executed, the reason is in the heartbeat settings_unread: mirror, `copies 1, enabled false` are not substituted
             (V7 item 3, the decision of the Architect of 2026-10-28, P1; line 20 of the list); bodies — N1.1 mirror;
             the neighbours — the next copies live servers by name; liveness — by the door row platform/doors/<host>, as in the merge
             contract «Live resources» (the version changed within the last LOST_AFTER on the clock of this resource, the first look — as fresh), the heartbeat
             of the neighbour does not judge here (the decision of the Architect of 2026-10-31); only closed buckets;
             the copy in .mirror/<server>/…; a copy is never a source while the owner answers; PEER_FAILS 3, a bucket ≤ 64 MiB
             as a whole, a copy ages an hour later than the original; a closed bucket larger than 64 MiB (the mirror reception limit) is not
             copied: there is no assembly from pieces and no partial copy, it enters mirror.skipped of the heartbeat on every pass,
             the other buckets are copied (log of cammeta-go, lesson 8 № 7)
             # the form of the row platform/mirror — P/02.4 N1.9 (written by admin, w2cctl mirror)
  presence:  runs | gone | unlisted | unknown   # about the worker process of its own box — a conclusion from the heartbeat fields above:
             # the key <sub>/<name> of the worker slot of the subsystem <sub>: in running — runs; in unknown — unknown; in workers, but not in
             # running and not in unknown, — gone (the resource knew
             # the process, it is dead); not named in workers — unlisted (not registered at the resource); a heartbeat without these fields —
             # nothing about the worker (P/04 «fate»); an absent one of the three fields is an empty list, not unreadability: the order
             # unknown, running, workers, otherwise unlisted (C04-PRESENCE-PARTIAL-01).
             # The listing <events root>/.workers/<sub>/ is not obtained (an error, except ENOENT of a directory not yet created — that one
             # is empty): the heartbeat has none of the three fields — nothing about the workers (P/04 wait), the former names are not carried over, there is no partial
             # set; the rest of the heartbeat — as usual (C05-PRESENCE-SCAN-UNKNOWN-01). How the resource learns the presence — the presence lock contract
             # silent is a state of the resource itself (the observation contract), not a value of the presence
  presence_lock:  <events root>/.workers/<sub>/<instance>.lock — the presence lock contract (presence-lock.md;
             moved there, review of stage A 3–5, № 9); after flock the resource compares fstat(fd) and stat(path); if they do not
             match (ENOENT of stat too, review of stage B 3–5, № 19), it does not touch the file (ADR-0083 addendum (10)); the flock of the worker is blocking;
             the content — the family presence-lock (data/presence-lock.schema.json, presence-lock.outcomes.tsv; below):
             {instance, sub, worker, server, pid}, worker "" before the name is captured; a busy lock with empty or out-of-form
             content — a live process without a number (in room, not in workers, running, live); unknown — only an unreadable file
             (review of stage B 3–5, № 23; ADR-0083 addendum (11)) and an error of flock or stat, except «busy» and ENOENT (the decision of the Architect of 2026-10-20, review of stage B 6–7)
  requires:  placement.requires: resource — the worker is outside the pool while the resource of its server is silent (P/04)
```

<!-- req: P/05-R026 -->

**Writer and reader heartbeat forms** (ADR-0127, review of P/05 C3). The writer MUST include `door`, `waits`, `restore`, `mirror` and `units`. At initialization before any operations: `units = {}`, `restore = {}` if there are no necessary neighbours, `waits = {waiting:0, held:0, full:0, replaced:0, max:LONG_POLL_WAITERS}`, and the mirror counters `skipped`, `failed`, `peer_errors`, `lines_garbled` are zero. Existing necessary neighbours still have their actual restore entries, including incomplete ones; neutral values do not erase an error or a pending attempt. `door` always has its actual `addr` and `mode`; `mtls` additionally requires the actual server-certificate `cert_until`. The root schema remains the tolerant reader form for old incomplete heartbeats; `$defs.writer` strengthens only the writer. A reader does not synthesize successful operation or TLS state from an absent old field.

**Unnamed presence uncertainty** (ADR-0127, review of P/05 C2). A current lock error without a readable slot name makes the whole role snapshot unknown, even after a successful listing and at cold start. Apply the presence-lock contract's “An unknown role snapshot”: omit `workers`, `running`, `unknown` and snapshot-derived `instances`, set the affected `room.<sub>` to `"unknown"`, omit its `live.<sub>`, keep independently complete room/live of other roles. Do not infer a slot from the filename, prior memory, or another lock; do not interpret the omission as `unlisted` or `gone`.

The content of the presence lock is the family `presence-lock` of the lesson: [schema](../data/presence-lock.schema.json),
[outcomes](../data/presence-lock.outcomes.tsv) (layers — [LAYERS](../../common/LAYERS.md)): an instance is `{key, file}`, the text of the file with `x-encoding: json` at the root
(LAYERS § 6), the column `schema` of the catalogue row names the family, the section is «Data families» below; the meaning is [the presence
lock contract](../../common/contracts/presence-lock.md) (review of stage B 3–5, № 23; ADR-0083 addendum (11); review of stage B 6–7, № 44).

<!-- req: P/05-R027 -->

**Cluster objects — through the resource of its own server** (ADR-0084 addendum (2) R17; review of stage B 3–5, № 24). A process
of the platform reads the objects of other servers (the heartbeats of workers and resources, the pass reports) through the objects door of the resource of its own
server (N2, `scope`); without a resource on its own server with `cluster://` — «not known», not «no» ([the object store client contract](../../common/contracts/object-client.md) `door`; P03-OBJECTS-DEFAULT-1FD; the Architect's decision of 2026-10-27). A stand that needs the heartbeats of workers
puts a resource on the server of the reader ([P/04](../../04-controller/spec/04-controller.norms.md) N3 «pass()» step 0).

<!-- req: P/05-R028 -->

PULSE_LIMIT is a finite positive limit of the duration of one step of the resource in seconds,
chosen and declared by the implementation before the start. The duration is measured by the local
monotonic clock, not by t/at of the writer; exceeding it gives pass_stalled in the next heartbeat.
It is a diagnostic threshold, not a promise to stop a hung call or to wait for an answer.

<!-- req: P/05-R029 -->

**Bucket restore** (moved from M10/11 N1.4
`restore`, M10/11-09; a server failure and `power_pull` — [P/04](../../04-controller/spec/04-controller.norms.md) N1.4a, the drill — [system
acceptance](../../common/acceptance/system/README.md)):

<!-- req: P/05-R030 -->

```yaml
restore:    at start the resource pulls its closed buckets from the neighbours whose heartbeats mirrors name it: GET /mirrored/<me>,
            each bucket by its sum, tmp + rename; PEER_FAILS 3 in a row — the neighbour is skipped for the attempt; RESTORE_RETRY 10 s,
            doubling up to 600; done when the full lists are received and the copies are checked from all known necessary neighbours;
            the necessary neighbours — those whose readable heartbeats mirrors name this server; the local events are lost, and the heartbeats
            of the neighbours do not read or there is no heartbeat of a neighbour — all known server doors are necessary (platform/doors, door_row above),
            except its own: each is to answer with a full listing GET /mirrored/<me> (a full empty listing and 404 — there are no
            copies, so that neighbour is complete); 404 of GET of an already listed bucket is a missing copy, not an empty listing: the attempt stays incomplete. A restored bucket keeps the listed copy's written as its own retention stamp, not the receive time or filesystem mtime; an unknown or unreadable door leaves the restore incomplete (log of cammeta-go, lesson 11 № 4);
            a skipped/unreadable neighbour leaves the restore incomplete; 500 of a listing and a broken answer by N2, N4 do not count as an empty full list. If there were never any neighbours, there is no remote restore;
            restored of the heartbeat — only the buckets actually pulled from this neighbour; a bucket already lying on the volume does not count
            (the decision of the Architect of 2026-10-31);
            then — the reindexing of the subsystem; a copy is never a source while the owner answers (mirror above)
```

### N1.6 Hint and HTTP representations

<!-- req: P/05-R031 -->

`GET /events/wait` of the resource is a hint by ADR-0038, not a delivery of events. The profile of the lesson:
`want` — a non-empty comma-separated list `<sub>/<kind>[/<unit>]`; each part of ASCII letters,
digits, `_`, `-`, `.`, 1…64 characters, not starting with a dot. `client`, if given, — 1…128
printable ASCII characters without a space. `since` — a decimal uint64 without a sign/leading zeros,
0 by default. `timeout` — a finite number of seconds in (0,30], 30 by default.
Empty/repeated parameters, unknown parameters (`&foo=1`), other forms and values out of range — 400; `since` and
`timeout` — only ASCII digits (and a dot for `timeout`), non-ASCII digits — 400 (reconciliation of python and go M10/6–11, E14, E16). `since=0` —
the client has no position: the answer at once is `{changed: true, seq, touched}` if under want there are lines in the buckets of the resource of any
age; seq is an opaque monotonic number of the resource process, the client only compares it and passes it back
(reconciliation of python and go M10/6–11, E46). The hint is given by the subsystem trees of the catalogue (`<sub>`, `<sub>.alarms`); the trees `console` and `audit`
give no hint (both implementations do so, there was no norm).
This bounded profile does not require accepting any internal unit names: the periodic
pass of the client stays mandatory and works without the hint.

<!-- req: P/05-R032 -->

The answer is one of the closed forms WaitAnswer: `{changed:true, seq, touched:[…]}`,
`{changed:false, seq}`, `{changed:false, seq, full:true}` or
`{changed:false, seq, replaced:true}`. In touched — the sorted unique
`<sub>/<kind>/<unit>` that match want; the events themselves are not there. seq belongs to one process
of the resource; after a restart/an unknown sequence the client makes an ordinary pass.
With full/replaced the client does not advance its cursor by seq, but returns to the ordinary pass.
By default up to 16 waits (the deployment parameter LONG_POLL_WAITERS); a new wait when
full is answered 200/full. First replace the former wait of the same verified CN and named client: it receives 200/replaced and releases its place; only then check capacity for the new wait. Thus at 16 pending waits a replacement is admitted and 16 remain; a different CN cannot free that place (ADR-0127, review of P/05 M2).
A wait does not take the lane of 8 requests /events (N3 «query»); it holds its connection of the door until the answer
(changed, term, full, replaced) or until the noticed departure of the client (no later than 1 s) — the «common lane» of N2 is the connection limit
of the resource door («Implementation decides» item 10; C05-WAIT-COMMON-LANE-01).
In TLS the identity is the CN of the certificate plus client; another CN does not displace a wait (ADR-0075).
Without client the deployment uses a separate wait per client address; a repeat with a busy
address — full. The current buckets are observed every 0.1 s while there are waiting ones; a missed
hint or a write to an old bucket is made up for by the ordinary pass, not by a promise of delivery.

<!-- req: P/05-R033 -->

Paths `/mirror/{server}/{path}`, `/mirrored/{server}[/{path}]`, `/events/{path}` (reconciliation of python and go M10/6–11, E26, E27, E29, E34):
`{server}` — one segment by the grammar of a server name (P/02.4 N1.2 `SERVER_NAME`); `{path}` — a bucket path of N1.2
(`<tree>/<unit>/e<epoch>/<start>Z.events.jsonl`), no segment is empty or `.`/`..`, `%2F` is not a separator,
`.tmp` is not a bucket. Otherwise: `GET /mirrored/…` and `GET /events/…` — 404 without a body, `PUT /mirror/…` — 400 without a body. The resource never
reads or writes a file outside its tree (`.mirror/<server>/` for copies). `PUT /mirror` of a bucket whose end by name
is later than the clock of the receiver — 400: the mirror accepts only closed buckets. `PUT /mirror/<own server>/…` (a copy from itself) —
accept or refuse — «Implementation decides» item 11 (C05-MIRROR-PUT-SELF-01). The value of `X-Sum` is an HTTP field: the spaces at the edges
(OWS) are dropped before the check of the form (E35).

<!-- req: P/05-R034 -->

The HTTP representations are in the schemas of N2. `BucketInfo` is the description of one bucket, not an event;
`/buckets` gives UTF-8 JSON Lines: one object per LF, without an array. `/mirrored/<server>`
by the canon of this lesson gives `{copies:[{path,written,size,sum}]}`. `written` of a copy is the wall seconds (N0) when the receiver
published this copy at itself (the time of the copy file or its own record): `PUT /mirror` does not carry the time of the source bucket, only
`X-Sum`; the bytes of the bucket do not change; a repeated reception of the same bucket with the same sum does not shift `written` (guess of stage C
R05-G04, the Architect's decision of 2026-10-23). The bytes of a copy are a separate
GET. The field `sum` and the header X-Sum are 64 lowercase hex digits of the SHA-256 of the whole body.
The form `answered` (the mark row of a request, AnsweredMark) — [chapter 6.4](../../06-console/spec/06.4-console.norms.md) N1.6
(the console door).

<!-- families:begin -->
### Data families (built from the standard files)

The form of the rows and objects and JSON files that the chapter owns by the [catalog](../../common/data/catalog.tsv) is the JSON Schema 2020-12 of the family (ADR-0092). An instance of a row is `{key, row}`, of an object `{key, object}`, of a file `{key, file}` (the text of the file in UTF-8; the root of the schema is its parse, `x-encoding`); the key is the grammar of the column `key` of the catalog. The fields of `row` are the values of `items` after the [codec](../../common/data/codec.tsv): the writer checks the schema and its `$defs.writer`, the reader the schema (layer 3 — the words `x-*` of the schema). Unreadable — the row did not decode or did not pass the schema in the reader's mode; the outcome is by the table of outcomes of the family: the path is a prefix of the path of the refusal (empty — the whole row); with several paths of refusal the outcome of the least priority applies.

#### `platform/doors/<host>` — row

Schema — [`doors.schema.json`](../data/doors.schema.json), outcomes — [`doors.outcomes.tsv`](../data/doors.outcomes.tsv); form version 1; norm — P/05 N1.4 door_row; the presence lock contract; P/06.6 N3 «decommission a server» (delete by the console).

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `url` | string | required |  | the address of the resource door (RESOURCE_URL) |
| `since` | time (P/01.1 N0 «Time in a row») | required |  | the moment of the resource start |
| `at` | time (P/01.1 N0 «Time in a row») | required |  | the moment of the last mark, every 15 s; judged by a change of the row version, not by the value (resource_state of the observation contract) |
| `.<name>` | string | optional |  | name: `room.<sub>` — an element for each subsystem of the catalogue whose role file `roles/<sub>worker.env` is present on the box; next to it `live.<sub>` (ADR-0084 addendum (3) R14′); a decimal ≥ 0 — how many more processes of the role `<sub>worker` the server will start (the presence lock contract «Count room»), or "unknown"; the reader does not refuse an element out of form at the row level: the element is absent, unreadable or unknown — the server is not a candidate for an order of this role (P/04 N3 «order()»); for `live.<sub>` — the numbers n ≥ 2 of the live locks of the role, comma-separated, ascending, without repeats, from the same snapshot as `room.<sub>`, or empty; absent or unreadable — the server is not a candidate (the presence lock contract, live) |

Only at the writer (`$defs.writer`):

| Key | Also |
|---|---|
| `.<name> (name)` | any value; matching `(room\|live)\.[a-z][a-z0-9_-]{0,31}` in full |
| `.<name>` | matching `0\|[1-9][0-9]*\|unknown\|([2-9]\|[1-9][0-9])(,([2-9]\|[1-9][0-9]))*\|` in full |

Outcomes of an unreadable row (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole row | `<s>controller` | the whole row is unreadable: the server is not a candidate for an order; the fields of the unreadable row are not replaced by absence, the cause goes to the log (layout audit, G-09; rule DF-OUTCOMES-109, the Architect's decision of 2026-10-25) | 0 | row | P/04 N1, N3 «order()» |
| the whole row | `console` | the whole row is unreadable: the life of the resource is judged by a change of the row version (resource_state of the observation contract), not by its fields; the fields of the unreadable row are not replaced by absence; the door row of a decommissioned server is unreadable — the console pass deletes it all the same: delete with cas by the version read, the content is not needed for the deletion (V7 item 3, row 12); the cause goes to the log (layout audit, G-09; rule DF-OUTCOMES-109, the Architect's decision of 2026-10-25) | 0 | row | observation contract resource_state; P/06.6 N3 «decommission_server» |
| the whole row | `resource` | the whole row is unreadable: restore — the door is unreadable, the restoration is incomplete; mirror — there is no address, the server is not a neighbour of this pass; the fields of the unreadable row are not replaced by absence, the cause goes to the log (layout audit, G-09; rule DF-OUTCOMES-109, the Architect's decision of 2026-10-25) | 0 | row | P/05 N1.4 door_row, «Bucket restore» |
| the whole row | `<s>worker` | the door row of its own server is unreadable: the object client with a bare cluster:// — reading the cluster objects is «unknown», not «no», not a start refusal and not a refusal of writing to its own catalogue; on the next access the row is read anew (P3; V7 item 3, row 11) | 0 | row | the object store client contract door (P03-OBJECTS-DEFAULT-1FD) |

#### `platform/resources/<server>/heartbeat` — object

Schema — [`resource-heartbeat.schema.json`](../data/resource-heartbeat.schema.json), outcomes — [`resource-heartbeat.outcomes.tsv`](../data/resource-heartbeat.outcomes.tsv); form version 1; norm — P/05 N1.4.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `server` | string; matching `[a-z0-9]+(-[a-z0-9]+)*` in full | required |  | its own server — SERVER_NAME by the grammar of the environment file contract «Environment variables», as for the presence lock (stage C guess R05-G07, the Architect's decision of 2026-10-23); not by it or not equal to the server of the key — the heartbeat is unreadable (P/06.5 N2) |
| `box` | string | optional |  | the box (BOX_ID, the environment file contract «Environment variables») |
| `ts` | time (P/01.1 N0 «Time in a row») | required |  | wall-clock seconds of the heartbeat; written every 10 s |
| `url` | string | required |  | the address of the resource door |
| `schema` | integer; ≥ 1; ≤ 9007199254740991; the whole sign for the reader too (x-whole) | required |  | SCHEMA of the build (P/06.6 N1.1a heartbeat): a JSON integer without a fractional part and exponent, ≥ 1; `1.0`, `1e0`, `-1`, a string, null — the process schema is unknown |
| `build` | string | required |  | the build word (BUILD); not a string — the field is unknown: null in the console's answers (V7 item 3, the Architect's decision of 2026-10-28, P1; row 14 of the list) |
| `usage` | integer; ≥ 0; ≤ 9007199254740991 | required |  | bytes of the bucket files of the trees of this server and of the copies in .mirror/ |
| `usage_at` | time (P/01.1 N0 «Time in a row») | required |  | wall-clock seconds of the usage measurement |
| `space` | by the definition `disk` | required |  | the volume of the event tree |
| `volumes` | map author names: name — string, value — by the definition `disk` | required |  | the same per volume (log of cammeta-go, lesson 9 № 1) |
| `volumes.<name>` | by the definition `disk` | optional |  |  |
| `units` | map author names: name — string; matching `[a-z][a-z0-9_-]{0,31}` in full, value — list, element — string | required |  | `{<sub>: [<id>…]}`; none such — {}; in every heartbeat (E39) |
| `units.<name>` | list, element — string | optional |  | ids of the units named in status by the heartbeats of the workers of this box from running, in ascending byte order |
| `units.<name>[]` | string | optional |  |  |
| `workers` | by the definition `slot_list` | optional |  | all slots the resource knows about on its box (by the presence locks) |
| `running` | by the definition `slot_list` | optional |  | slots with a live process (it holds the presence lock) |
| `unknown` | by the definition `slot_list` | optional |  | presence could not be read |
| `instances` | map author names: name — string; matching `[^/]+/[^/]+` in full, value — string; matching `[\s\S]+` in full | optional |  | `{<sub>/<slot name>: <instance>}` |
| `instances.<name>` | string; matching `[\s\S]+` in full | optional |  |  |
| `short` | integer; ≥ 0; ≤ 9007199254740991 | required |  | how many bytes the mark asked to free and could not (P/06.5 N3 /metrics w2c_resource_short_bytes): Σ over the volumes of the largest need (> 0) among the effective own `free-<server>-<volume>` of this relieve pass — subsystems on one volume are not summed; need — by N3 relieve, rounded up to a whole byte, saturation 2^53−1; platform/space disabled, no requests, need ≤ 0 — 0; the pass input was not read — the previous value (stage C guess R05-G03, the Architect's decision of 2026-10-23) |
| `waits` | map `{waiting, held, full, replaced, max}` | optional |  | counters of the /events/wait waits (N1.6); in every heartbeat (E39) |
| `waits.waiting` | integer; ≥ 0; ≤ 9007199254740991 | required |  | an integer from 0 to 2^53 − 1 |
| `waits.held` | integer; ≥ 0; ≤ 9007199254740991 | required |  | an integer from 0 to 2^53 − 1 |
| `waits.full` | integer; ≥ 0; ≤ 9007199254740991 | required |  | an integer from 0 to 2^53 − 1 |
| `waits.replaced` | integer; ≥ 0; ≤ 9007199254740991 | required |  | an integer from 0 to 2^53 − 1 |
| `waits.max` | integer; ≥ 0; ≤ 9007199254740991 | required |  | an integer from 0 to 2^53 − 1 |
| `mirrors` | map author names: name — string, value — integer; ≥ 0; ≤ 9007199254740991 | required |  | `{<server>: n}` — copies of neighbours in .mirror/ |
| `mirrors.<name>` | integer; ≥ 0; ≤ 9007199254740991 | optional |  | an integer from 0 to 2^53 − 1 |
| `pass_started` | time (P/01.1 N0 «Time in a row») | optional |  | the start of the current pass (N3 «resource pass») |
| `pass_stalled` | number; ≥ 0 | optional |  | seconds, only while the pass is hung (PULSE_LIMIT) |
| `volumes_stuck` | map author names: name — string, value — number | optional |  | volumes whose probe did not answer (P/06.5 ResourceRow) |
| `volumes_stuck.<name>` | number | optional |  |  |
| `door` | map `{addr, mode, cert_until?}` | optional |  | the state of the resource door (P/06.5 ResourceRow DoorState); written by the resource in every heartbeat (P/05 N1.4; ADR-0075 addendum (3); analysis of review of stage B 3–5, № 28) |
| `door.addr` | string | required |  | the address of the resource door — RESOURCE_HOST:RESOURCE_PORT |
| `door.mode` | string; one of: `loopback`, `mtls` | required |  | loopback — without RESOURCE_TLS, loopback only; mtls — RESOURCE_TLS=1, mutual TLS (ADR-0075) |
| `door.cert_until` | number | optional |  | wall-clock seconds of the expiry of the server certificate of its own set (W2C_TLS_DIR); with mtls |
| `garbled_rows` | map author names: name — string, value — integer; ≥ 0; ≤ 9007199254740991 | optional |  | unreadable rows of the tables read by the resource (holds), per table |
| `garbled_rows.<name>` | integer; ≥ 0; ≤ 9007199254740991 | optional |  | an integer from 0 to 2^53 − 1 |
| `retention_garbled` | list, at least 1 items, without repeats, element — string; matching `[a-z][a-z0-9_-]{0,31}` in full | optional |  | subsystems where any term (`<sub>/retention` or `<sub>/alarms_retention`) has a wrong days (P/05 N1.3 retention rule), regardless of retention_withheld (R05-RETENTION-MIXED-51-01), in ascending byte order; none such — the field is absent (P/05 N3 retain, N4; stage C guess C05-RETENTION-PULSE-33, the Architect's decision of 2026-10-25) |
| `retention_garbled[]` | string; matching `[a-z][a-z0-9_-]{0,31}` in full | optional |  |  |
| `retention_withheld` | map author names: name — string; matching `[a-z][a-z0-9_-]{0,31}` in full, value — string; one of: `days_garbled`, `unknown`, `holds_unread` | optional |  | why a dependent tree of the subsystem was not cleaned up by term in this pass — a closed list: days_garbled — a wrong days, unknown — the term row was not read (the store did not answer), holds_unread — the holds were not read (the holds contract); a subsystem has one cause, in the order unknown → days_garbled → holds_unread; each tree is held by its own term (R05-G08, R05-RETENTION-MIXED-51-01); no cause — the field is absent (P/05 N3 retain, N4; C05-RETENTION-PULSE-33) |
| `retention_withheld.<name>` | string; one of: `days_garbled`, `unknown`, `holds_unread` | optional |  |  |
| `settings_unread` | list, at least 1 items, without repeats, element — one of: `mirror`, `space` | optional |  | the settings rows of the resource pass that were not read in this pass: mirror — platform/mirror (the mirror step and the body copies are not executed), space — platform/space (the relieve step is not executed); in ascending byte order; none such — the field is absent (P/05 N1.4 mirror, space, N3; V7 item 3, the Architect's decision of 2026-10-28, P1; rows 20, 21 of the list) |
| `settings_unread[]` | one of: `mirror`, `space` | optional |  |  |
| `restore` | map author names: name — string, value — map `{done, silent?, last_ok?, last_error?, error_at?, restored, missing, failures, lines_garbled?, next?}` | optional |  | `{<neighbour>: …}` — restoring buckets from copies of neighbours (N1.4 «Bucket restore»); in every heartbeat (E39) |
| `restore.<name>` | map `{done, silent?, last_ok?, last_error?, error_at?, restored, missing, failures, lines_garbled?, next?}` | optional |  |  |
| `restore.<name>.done` | bool | required |  |  |
| `restore.<name>.silent` | bool | optional |  |  |
| `restore.<name>.last_ok` | number | optional |  |  |
| `restore.<name>.last_error` | string | optional |  |  |
| `restore.<name>.error_at` | number | optional |  |  |
| `restore.<name>.restored` | integer; ≥ 0; ≤ 9007199254740991 | required |  | only the buckets actually pulled from this neighbour; a bucket already lying on the volume is not counted (N1.4 «Bucket restore») |
| `restore.<name>.missing` | integer; ≥ 0; ≤ 9007199254740991 | required |  | an integer from 0 to 2^53 − 1 |
| `restore.<name>.failures` | integer; ≥ 0; ≤ 9007199254740991 | required |  | an integer from 0 to 2^53 − 1 |
| `restore.<name>.lines_garbled` | integer; ≥ 0; ≤ 9007199254740991 | optional |  | an integer from 0 to 2^53 − 1 |
| `restore.<name>.next` | number | optional |  |  |
| `mirror` | map `{skipped, failed, peer_errors, lines_garbled, sum_refused?, peer_sum_refused?, pull_sum_bad?, unsummed?}` | optional |  | mirror counters (N1.4 mirror; skipped — buckets larger than 64 MiB); in every heartbeat (E39) |
| `mirror.skipped` | integer; ≥ 0; ≤ 9007199254740991 | required |  | an integer from 0 to 2^53 − 1 |
| `mirror.failed` | integer; ≥ 0; ≤ 9007199254740991 | required |  | an integer from 0 to 2^53 − 1 |
| `mirror.peer_errors` | integer; ≥ 0; ≤ 9007199254740991 | required |  | an integer from 0 to 2^53 − 1 |
| `mirror.lines_garbled` | integer; ≥ 0; ≤ 9007199254740991 | required |  | an integer from 0 to 2^53 − 1 |
| `mirror.sum_refused` | integer; ≥ 0; ≤ 9007199254740991 | optional |  | an integer from 0 to 2^53 − 1 |
| `mirror.peer_sum_refused` | integer; ≥ 0; ≤ 9007199254740991 | optional |  | an integer from 0 to 2^53 − 1 |
| `mirror.pull_sum_bad` | integer; ≥ 0; ≤ 9007199254740991 | optional |  | an integer from 0 to 2^53 − 1 |
| `mirror.unsummed` | integer; ≥ 0; ≤ 9007199254740991 | optional |  | an integer from 0 to 2^53 − 1 |

Only at the writer (`$defs.writer`):

| Key | Also |
|---|---|
| `<root>` |  |
| `door` |  |

**`disk`**

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `<disk>` | map `{total, free, used, full}` |  |  |  |
| `<disk>.total` | integer; ≥ 0; ≤ 9007199254740991 | required |  | bytes (statfs) |
| `<disk>.free` | integer; ≥ 0; ≤ 9007199254740991 | required |  | bytes |
| `<disk>.used` | integer; ≥ 0; ≤ 9007199254740991 | required |  | bytes |
| `<disk>.full` | number; ≥ 0; ≤ 1 | required |  | the fraction used/total from 0 to 1 (not a flag) |

**`slot_list`**

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `<slot_list>` | list, element — string; matching `[^/]+/[^/]+` in full |  |  |  |
| `<slot_list>[]` | string; matching `[^/]+/[^/]+` in full | optional |  | `<sub>/<slot name>` |

Outcomes of an unreadable object (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| `/schema` | * | the process schema is unknown: in processes of the door /schema — schema: null; in ResourceRow of the door /resources — schema: null (analysis of review of stage B 6–7, № 6); the heartbeat stays readable | 0 | field | P/06.6 N1.1a heartbeat, N2.3; P/06.5 N2 «Outputs» |
| `/build` | * | build is not a string — the field is unknown: null in ResourceRow (/resources) and in processes of the door /schema, not ""; the heartbeat stays readable (P1; V7 item 3, row 14) | 0 | field | P/06.5 N2; P/06.6 N2.3 |
| `/retention_garbled` | * | a field out of form is unknown: null in ResourceRow, not absence (the term causes are not replaced by «no causes»); the heartbeat stays readable (P1; V7 item 3, row 14) | 0 | field | P/05 N3 retain; P/06.5 N2 |
| `/retention_withheld` | * | a field out of form is unknown: null in ResourceRow, not absence (the term causes are not replaced by «no causes»); the heartbeat stays readable (P1; V7 item 3, row 14) | 0 | field | P/05 N3 retain; P/06.5 N2 |
| the whole object | `<s>controller` | the heartbeat is unreadable: it does not confirm the life of the resource, nor does its change (resource_state: unreachable with a fresh door row, otherwise by the order of the rules); it gives no presence of processes | 1 | row | observation contract resource_state |
| the whole object | `console` | the heartbeat is unreadable: it does not confirm the life of the resource, nor does its change (resource_state: unreachable with a fresh door row, otherwise by the order of the rules); it does not enter /resources, it is counted in w2c_resource_heartbeats_garbled, the answer is 200 | 1 | row | observation contract resource_state; P/06.5 N2 «Outputs» |
| the whole object | `resource` | the neighbour's heartbeat is unreadable: restore of the neighbour — the heartbeat is not read, the restoration is incomplete (all known doors are required) | 1 | row | P/05 N1.4 «Bucket restore» |

#### `<sub>/requests/free-<server>-<volume>` — row

Schema — [`free-ask.schema.json`](../data/free-ask.schema.json), outcomes — [`free-ask.outcomes.tsv`](../data/free-ask.outcomes.tsv); form version 1; norm — P/05 N1.4 free_ask.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `free` | number; > 0 | required |  | need = used − total·low − Σ freeing from the heartbeats, bytes; need ≤ 0 — the row is removed, not written |
| `volume` | string; matching `[A-Za-z0-9_]{1,64}` in full | required |  | the volume name of ASCII A-Z/a-z/0-9/_, 1–64 bytes, without a hyphen; on the box there is one volume — events |
| `server` | string; matching `[\s\S]+` in full | required |  | its own server — a non-empty key segment of P/01.1, hyphens allowed; matches `<server>` of the key |
| `at` | time (P/01.1 N0 «Time in a row») | required |  | the write stamp |

Outcomes of an unreadable row (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole row | `<s>worker` | a row not in the resource's form is not a request: skipped, the cause goes to the log without the value (V7 item 3, row 10) | 0 | row | P/03.6 N3 «holder's look» |
| the whole row | `console` | a resource row without a live owner is removed by ttl | 0 | row | P/06.4 N3 «reaper» |
| the whole row | `resource` | not its own form (unit present, someone else's server/volume, a spoiled form): do not touch, log free_ask.key_taken, skip | 0 | row | P/05 N1.4 free_ask, N3 «resource pass» relieve |

#### `<events root>/<sub>/<unit>/e<epoch>/<YYYYMMDDTHHMMSSZ>.events.jsonl` — file

Schema — [`events-unit.schema.json`](../data/events-unit.schema.json), outcomes — [`events-unit.outcomes.tsv`](../data/events-unit.outcomes.tsv); form version 1; norm — P/05 N1.2; the event journal contract.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `t` | time (P/01.1 N0 «Time in a row») | required |  | the writer's wall-clock seconds when it was written; selects the bucket (years up to 9999 — EJ-G06) |
| `kind` | string | required |  | the event kind |
| `id` | string | required |  | `e1-<hexUTF8(tree)>-<hexUTF8(unit)>-<epoch>-<hexUTF8(instance)>-<number>`; unique, duplicate copies are removed by it |
| `of` | string | optional |  | `<sub>/<id>` — the unit it is about; set by the platform from about |
| `class` | string; one of: `alarm` | optional |  | only for an alarm; not written for observation |
| `occurred` | time (P/01.1 N0 «Time in a row») | optional |  | when it happened; optional |
| `v` | integer; ≥ 1 | optional |  | the line version — an additional field: the reader tolerates it (LAYERS.md § 6), the writer does not write it — absence = version 1; a positive integer, v = 2 is preserved, there is no choice of behaviour by v (the event log contract line; stage C guesses EJ-G10, EJ-L04) |
| `.<name>` | any value | optional |  | the subsystem's words; fields beyond the form are kept by the reader as is, the writer writes the line strictly by the form (EJ-G10) |

Outcomes of an unreadable file (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole file | `resource` | a full line (with LF) out of the form line — not a JSON object, no t, kind or id, the time not by the reader's codec, deeper than JSON_DEPTH 128 (P/01.1 N2.1; the event log contract line depth, EJ-DEPTH-BASELINE33): this line is skipped and counted in garbled, the bucket is read further, not a refusal of the bucket; the last fragment without LF is not a line, counted in torn | 0 | row | the event journal contract `bucket` `torn`; stage C guesses EJ-G03, EJ-G07 |

#### `<events root>/<sub>.alarms/<unit>/e<epoch>/<YYYYMMDDTHHMMSSZ>.events.jsonl` — file

Schema — [`events-unit-alarms.schema.json`](../data/events-unit-alarms.schema.json), outcomes — [`events-unit-alarms.outcomes.tsv`](../data/events-unit-alarms.outcomes.tsv); form version 1; norm — P/05 N1.2; the event journal contract.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `t` | time (P/01.1 N0 «Time in a row») | required |  | the writer's wall-clock seconds when it was written; selects the bucket (years up to 9999 — EJ-G06) |
| `kind` | string | required |  | the event kind |
| `id` | string | required |  | `e1-<hexUTF8(tree)>-<hexUTF8(unit)>-<epoch>-<hexUTF8(instance)>-<number>`; unique, duplicate copies are removed by it |
| `of` | string | optional |  | `<sub>/<id>` — the unit it is about; set by the platform from about |
| `class` | string; one of: `alarm` | optional |  | only for an alarm; not written for observation |
| `occurred` | time (P/01.1 N0 «Time in a row») | optional |  | when it happened; optional |
| `v` | integer; ≥ 1 | optional |  | the line version — an additional field: the reader tolerates it (LAYERS.md § 6), the writer does not write it — absence = version 1; a positive integer, v = 2 is preserved, there is no choice of behaviour by v (the event log contract line; stage C guesses EJ-G10, EJ-L04) |
| `.<name>` | any value | optional |  | the subsystem's words; fields beyond the form are kept by the reader as is, the writer writes the line strictly by the form (EJ-G10) |

Outcomes of an unreadable file (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole file | `resource` | a full line (with LF) out of the form line — not a JSON object, no t, kind or id, the time not by the reader's codec, deeper than JSON_DEPTH 128 (P/01.1 N2.1; the event log contract line depth, EJ-DEPTH-BASELINE33): this line is skipped and counted in garbled, the bucket is read further, not a refusal of the bucket; the last fragment without LF is not a line, counted in torn | 0 | row | the event journal contract `bucket` `torn`; stage C guesses EJ-G03, EJ-G07 |

#### `<events root>/audit/<role>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl` — file

Schema — [`events-audit.schema.json`](../data/events-audit.schema.json), outcomes — [`events-audit.outcomes.tsv`](../data/events-audit.outcomes.tsv); form version 1; norm — P/05 N1.2; the event journal contract.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `t` | time (P/01.1 N0 «Time in a row») | required |  | the writer's wall-clock seconds when it was written; selects the bucket (years up to 9999 — EJ-G06) |
| `kind` | string | required |  | the event kind |
| `id` | string | required |  | `e1-<hexUTF8(tree)>-<hexUTF8(unit)>-<epoch>-<hexUTF8(instance)>-<number>`; unique, duplicate copies are removed by it |
| `of` | string | optional |  | `<sub>/<id>` — the unit it is about; set by the platform from about |
| `class` | string; one of: `alarm` | optional |  | only for an alarm; not written for observation |
| `occurred` | time (P/01.1 N0 «Time in a row») | optional |  | when it happened; optional |
| `v` | integer; ≥ 1 | optional |  | the line version — an additional field: the reader tolerates it (LAYERS.md § 6), the writer does not write it — absence = version 1; a positive integer, v = 2 is preserved, there is no choice of behaviour by v (the event log contract line; stage C guesses EJ-G10, EJ-L04) |
| `.<name>` | any value | optional |  | the subsystem's words; fields beyond the form are kept by the reader as is, the writer writes the line strictly by the form (EJ-G10) |

Outcomes of an unreadable file (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole file | `resource` | a full line (with LF) out of the form line — not a JSON object, no t, kind or id, the time not by the reader's codec, deeper than JSON_DEPTH 128 (P/01.1 N2.1; the event log contract line depth, EJ-DEPTH-BASELINE33): this line is skipped and counted in garbled, the bucket is read further, not a refusal of the bucket; the last fragment without LF is not a line, counted in torn | 0 | row | the event journal contract `bucket` `torn`; stage C guesses EJ-G03, EJ-G07 |

#### `<events root>/audit.alarms/<role>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl` — file

Schema — [`events-audit-alarms.schema.json`](../data/events-audit-alarms.schema.json), outcomes — [`events-audit-alarms.outcomes.tsv`](../data/events-audit-alarms.outcomes.tsv); form version 1; norm — P/05 N1.2; the event journal contract.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `t` | time (P/01.1 N0 «Time in a row») | required |  | the writer's wall-clock seconds when it was written; selects the bucket (years up to 9999 — EJ-G06) |
| `kind` | string | required |  | the event kind |
| `id` | string | required |  | `e1-<hexUTF8(tree)>-<hexUTF8(unit)>-<epoch>-<hexUTF8(instance)>-<number>`; unique, duplicate copies are removed by it |
| `of` | string | optional |  | `<sub>/<id>` — the unit it is about; set by the platform from about |
| `class` | string; one of: `alarm` | optional |  | only for an alarm; not written for observation |
| `occurred` | time (P/01.1 N0 «Time in a row») | optional |  | when it happened; optional |
| `v` | integer; ≥ 1 | optional |  | the line version — an additional field: the reader tolerates it (LAYERS.md § 6), the writer does not write it — absence = version 1; a positive integer, v = 2 is preserved, there is no choice of behaviour by v (the event log contract line; stage C guesses EJ-G10, EJ-L04) |
| `.<name>` | any value | optional |  | the subsystem's words; fields beyond the form are kept by the reader as is, the writer writes the line strictly by the form (EJ-G10) |

Outcomes of an unreadable file (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole file | `resource` | a full line (with LF) out of the form line — not a JSON object, no t, kind or id, the time not by the reader's codec, deeper than JSON_DEPTH 128 (P/01.1 N2.1; the event log contract line depth, EJ-DEPTH-BASELINE33): this line is skipped and counted in garbled, the bucket is read further, not a refusal of the bucket; the last fragment without LF is not a line, counted in torn | 0 | row | the event journal contract `bucket` `torn`; stage C guesses EJ-G03, EJ-G07 |

#### `<events root>/console/<instance>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl` — file

Schema — [`events-console.schema.json`](../data/events-console.schema.json), outcomes — [`events-console.outcomes.tsv`](../data/events-console.outcomes.tsv); form version 1; norm — P/05 N1.2; the event journal contract.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `t` | time (P/01.1 N0 «Time in a row») | required |  | the writer's wall-clock seconds when it was written; selects the bucket (years up to 9999 — EJ-G06) |
| `kind` | string | required |  | the event kind |
| `id` | string | required |  | `e1-<hexUTF8(tree)>-<hexUTF8(unit)>-<epoch>-<hexUTF8(instance)>-<number>`; unique, duplicate copies are removed by it |
| `of` | string | optional |  | `<sub>/<id>` — the unit it is about; set by the platform from about |
| `class` | string; one of: `alarm` | optional |  | only for an alarm; not written for observation |
| `occurred` | time (P/01.1 N0 «Time in a row») | optional |  | when it happened; optional |
| `v` | integer; ≥ 1 | optional |  | the line version — an additional field: the reader tolerates it (LAYERS.md § 6), the writer does not write it — absence = version 1; a positive integer, v = 2 is preserved, there is no choice of behaviour by v (the event log contract line; stage C guesses EJ-G10, EJ-L04) |
| `.<name>` | any value | optional |  | the subsystem's words; fields beyond the form are kept by the reader as is, the writer writes the line strictly by the form (EJ-G10) |

Outcomes of an unreadable file (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole file | `resource` | a full line (with LF) out of the form line — not a JSON object, no t, kind or id, the time not by the reader's codec, deeper than JSON_DEPTH 128 (P/01.1 N2.1; the event log contract line depth, EJ-DEPTH-BASELINE33): this line is skipped and counted in garbled, the bucket is read further, not a refusal of the bucket; the last fragment without LF is not a line, counted in torn | 0 | row | the event journal contract `bucket` `torn`; stage C guesses EJ-G03, EJ-G07 |

#### `<events root>/console.alarms/<instance>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl` — file

Schema — [`events-console-alarms.schema.json`](../data/events-console-alarms.schema.json), outcomes — [`events-console-alarms.outcomes.tsv`](../data/events-console-alarms.outcomes.tsv); form version 1; norm — P/05 N1.2; the event journal contract.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `t` | time (P/01.1 N0 «Time in a row») | required |  | the writer's wall-clock seconds when it was written; selects the bucket (years up to 9999 — EJ-G06) |
| `kind` | string | required |  | the event kind |
| `id` | string | required |  | `e1-<hexUTF8(tree)>-<hexUTF8(unit)>-<epoch>-<hexUTF8(instance)>-<number>`; unique, duplicate copies are removed by it |
| `of` | string | optional |  | `<sub>/<id>` — the unit it is about; set by the platform from about |
| `class` | string; one of: `alarm` | optional |  | only for an alarm; not written for observation |
| `occurred` | time (P/01.1 N0 «Time in a row») | optional |  | when it happened; optional |
| `v` | integer; ≥ 1 | optional |  | the line version — an additional field: the reader tolerates it (LAYERS.md § 6), the writer does not write it — absence = version 1; a positive integer, v = 2 is preserved, there is no choice of behaviour by v (the event log contract line; stage C guesses EJ-G10, EJ-L04) |
| `.<name>` | any value | optional |  | the subsystem's words; fields beyond the form are kept by the reader as is, the writer writes the line strictly by the form (EJ-G10) |

Outcomes of an unreadable file (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole file | `resource` | a full line (with LF) out of the form line — not a JSON object, no t, kind or id, the time not by the reader's codec, deeper than JSON_DEPTH 128 (P/01.1 N2.1; the event log contract line depth, EJ-DEPTH-BASELINE33): this line is skipped and counted in garbled, the bucket is read further, not a refusal of the bucket; the last fragment without LF is not a line, counted in torn | 0 | row | the event journal contract `bucket` `torn`; stage C guesses EJ-G03, EJ-G07 |

#### `<events root>/.mirror/<server>/<tree>/<unit>/e<epoch>/<YYYYMMDDTHHMMSSZ>.events.jsonl` — file

Schema — [`events-mirror.schema.json`](../data/events-mirror.schema.json), outcomes — [`events-mirror.outcomes.tsv`](../data/events-mirror.outcomes.tsv); form version 1; norm — P/05 N1.4 mirror.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `t` | time (P/01.1 N0 «Time in a row») | required |  | the writer's wall-clock seconds when it was written; selects the bucket (years up to 9999 — EJ-G06) |
| `kind` | string | required |  | the event kind |
| `id` | string | required |  | `e1-<hexUTF8(tree)>-<hexUTF8(unit)>-<epoch>-<hexUTF8(instance)>-<number>`; unique, duplicate copies are removed by it |
| `of` | string | optional |  | `<sub>/<id>` — the unit it is about; set by the platform from about |
| `class` | string; one of: `alarm` | optional |  | only for an alarm; not written for observation |
| `occurred` | time (P/01.1 N0 «Time in a row») | optional |  | when it happened; optional |
| `v` | integer; ≥ 1 | optional |  | the line version — an additional field: the reader tolerates it (LAYERS.md § 6), the writer does not write it — absence = version 1; a positive integer, v = 2 is preserved, there is no choice of behaviour by v (the event log contract line; stage C guesses EJ-G10, EJ-L04) |
| `.<name>` | any value | optional |  | the subsystem's words; fields beyond the form are kept by the reader as is, the writer writes the line strictly by the form (EJ-G10) |

Outcomes of an unreadable file (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole file | `resource` | a full line (with LF) out of the form line — not a JSON object, no t, kind or id, the time not by the reader's codec, deeper than JSON_DEPTH 128 (P/01.1 N2.1; the event log contract line depth, EJ-DEPTH-BASELINE33): this line is skipped and counted in garbled, the bucket is read further, not a refusal of the bucket; the last fragment without LF is not a line, counted in torn | 0 | row | the event journal contract `bucket` `torn`; stage C guesses EJ-G03, EJ-G07 |

#### `<events root>/.workers/<sub>/<instance>.lock` — file

Schema — [`presence-lock.schema.json`](../data/presence-lock.schema.json), outcomes — [`presence-lock.outcomes.tsv`](../data/presence-lock.outcomes.tsv); form version 1; norm — P/05 N1.4; the presence lock contract.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `instance` | string; not one of: `""` | required |  | the worker instance (the instance contract common/contracts/instance.md: INSTANCE_ID or `<box>:<pid>:<6 hex>`); the lock file name is the same instance in the name encoding of the event log contract |
| `sub` | string; matching `[a-z][a-z0-9_-]{0,31}` in full | required |  | the worker's subsystem — the directory `.workers/<sub>/` of the lock |
| `worker` | string; matching `\|[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` in full | required |  | the slot name (P/03.2 N1.4) or "" — before the name is captured and while the worker searches without a name (nobody); the number n of the name `<prefix>-<server>-<n>` — for room and live (the presence lock contract «Count room») |
| `server` | string; matching `[a-z0-9]+(-[a-z0-9]+)*` in full | required |  | the worker's server — SERVER_NAME (P/02.4 N1.2) |
| `pid` | integer; ≥ 1; ≤ 9007199254740991; the whole sign for the reader too (x-whole) | required |  | pid of the worker process — an integer ≥ 1; for display: presence is by flock, not by pid (kill(pid, 0) is not a source) |

Outcomes of an unreadable file (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole file | `resource` | the content is empty or out of form (not a JSON object, a field missing, a field out of form, an extra field): the lock is busy — a live process without a number: it enters `room.<sub>`, does not enter workers, running, `live.<sub>`; the lock is taken by the resource and the check matched — gone by the file, there is no key `<sub>/<worker>`, the file MAY be deleted; unknown — a file that cannot be read (an open or read error), and an flock or fstat/stat error, except «busy» and ENOENT at stat (the Architect's decision of 2026-10-20, analysis of review of stage B 6–7), not its content (analysis of review of stage B 3–5, № 23) | 0 | row | the presence lock contract «Lock», «Count room»; P/05 N1.4 workers, room |

#### `.gone/<object-key>` — object

Schema — [`gone.schema.json`](../data/gone.schema.json), outcomes — [`gone.outcomes.tsv`](../data/gone.outcomes.tsv); form version 1; norm — P/05 N1.1 «Tombstones»; P/06.1 N3 «body cleanup»; the tombstone contract.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `written` | time (P/01.1 N0 «Time in a row») | required |  | the moment the body was deleted at the deleter |
| `peers` | list, element — string; matching `[\s\S]+` in full | required |  | neighbours of the ring that could have had a copy of the body |
| `peers[]` | string; matching `[\s\S]+` in full | optional |  |  |
| `acked` | list, element — string; matching `[\s\S]+` in full | required |  | neighbours from `peers` that confirmed the deletion (404 on GET of the copy) |
| `acked[]` | string; matching `[\s\S]+` in full | optional |  |  |

Outcomes of an unreadable object (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole object | `resource` | the whole object is unreadable: the neighbour does not drop the copy, the deleter does not append confirmations and does not remove the tombstone — an unknown outcome is not a confirmation (the tombstones contract garbled); the cause goes to the pass log (layout audit, G-10; rule DF-OUTCOMES-109, the Architect's decision of 2026-10-25) | 0 | row | P/05 N1.1 «Tombstones» |
<!-- families:end -->

---

## N2 Doors

<!-- req: P/05-R035 -->

The full contract: [OpenAPI](05-resource.api.openapi.yaml).
GET of an object is limited to 64 MiB by the bytes actually read: exactly the limit is allowed,
+1 byte — 413 ResourceError before the success headers; until the size is confirmed the body is
buffered within bounds or checked against an immutable object with a reliable size.
The ceiling of the store itself can be higher and does not cancel this limit of the door. It distinguishes
the resource and the console, JSON answers, a byte stream and the absence of a body. The schemas set the required
fields and the allowed extensions; the checks of existence, rights, UTF-8 size and state
are performed separately. An outer array does not replace JSON Lines.

<!-- req: P/05-R036 -->

| Input | Success | Application refusals |
|---|---|---|
| resource GET /v1/objects | 200 ObjectListing | 400 ResourceError; 403 ResourceError or ResourceDenied; 503 ResourceError |
| resource GET /v1/objects/{key} | 200 bytes; X-Written, X-Server, X-Missing when needed | 400/403/404/413/503 ResourceError |
| resource PUT /v1/objects/{non-blob} | none | 405 ResourceError; key/scope — 400 |
| resource GET /buckets/{sub}/{unit} | 200 JSON Lines of BucketInfo | 404/500 without a body |
| resource GET /events | 200 ResourceEvents; at the resource `HEAD` — 405 | resource 400 ResourceError (the parsing below); resource 503 ResourceError |
| resource GET /events/wait | 200 WaitAnswer, including full/replaced | 400 ResourceError; the common lane is busy — 503 ResourceError |
| resource GET /events/{path} | 200 whole bytes + X-Sum; 206 one range + Content-Range | 404/500 without a body; 416 text/plain + Content-Range |
| resource PUT /mirror/{server}/{path} | 204 without a body; the header `X-Sum` — SHA-256 of the body (64 lowercase hex), required | no `X-Sum` or it is not in form — 400, the body is not accepted; the SHA-256 of the body does not match — 422; 408/413/500 — without a body |
| resource GET /mirrored/{server} | 200 MirroredListing | 404/500 without a body |
| resource GET /mirrored/{server}/{path} | 200 bytes + X-Sum | 404/500 without a body |
| resource `PUT /v1/objects/<sub>/blobs/<digest>` | 204 without a body. Required are a length ≤64 MiB, `X-Written` — a non-negative time of the source copy (absent or not a number — 400), a sha256 name with 64 lowercase hex; bytes of another digest — 422; a key not of the blob form or a subsystem without a blob field — 405, as for any object (N1.1 «Bodies at the resource» `mirror`; reconciliation of python and go M10/6–11, T10, T11). On reading the actual limit/sum are checked | 400/404/405/408/409/411/413/422/503 — `ResourceError`, 403 — it or `ResourceDenied`. The common refusals of the console do not apply here (moved from M10/10 N2) |

<!-- req: P/05-R037 -->

`GET /events` of the console (the merge, ConsoleEvents, `HEAD`) and the console doors `POST /marks`, `POST /{sub}/requests`,
`DELETE /{sub}/asked/{sha16}` — [chapter 6.4](../../06-console/spec/06.4-console.norms.md) N2; the schemas
of the answer of `/events` common to both doors (`EventRow`, `UnitRef` and below) are in the contract of this lesson.

<!-- req: P/05-R038 -->

For both listings (`/buckets/{sub}/{unit}` and `/mirrored/{server}`) all the necessary
reads of the directory/metadata complete before the success headers: unknownness/an error —
500 without a body, not 404 and not an empty 200. It is an observed listing, not a snapshot of several files.
A break of an already started transfer of a listing is not a full answer; a new HTTP status
is not sent after the headers.

<!-- req: P/05-R039 -->

**`scope`** of `/v1/objects` and `/v1/objects/{key}` (ADR-0084 addendum (2) R17; review of stage B 3–5, № 24): `local`
(the default) — only the objects directory of this server; `cluster` — the cluster objects by N1.1 `cluster` (the fresh copy by
`written` wins, a server that did not answer is `missing`); another value — 400 (N4). The resource is the read door of the cluster
objects for the processes of its own server (N1.4 «Cluster objects — through the resource of its own server»).

<!-- req: P/05-R040 -->

ResourceError is only `{error: text}`. A refusal 404 on reading an object means «not among those who answered»;
with an incomplete poll X-Missing is required, completeness is not derived from the code 404 itself.

<!-- req: P/05-R041 -->

**Query parsing.** The resource door — by P/01.1 N2.1
(query, the path byte for byte, HTTP by RFC 9112, an early refusal) with deviations: a refusal of query parsing — 400 ResourceError
`{error}`; an empty or repeated parameter — 400; no path and an unsupported method — 404/405 without a body, including
`OPTIONS`, `POST /events`, `PUT /v1/objects` (the listing), `GET`/`POST`/`DELETE` on `/mirror/…`; `PUT /v1/objects/{non-blob}` —
the application 405 ResourceError (N4); `/buckets/{sub}/{unit}` — exactly two non-empty segments, `/buckets/testsub/`,
`/buckets/../objects`, `/buckets/testsub%2Fc1` — 404 without a body; the bodies of `PUT` are bytes, JSON is not parsed (reconciliation of python and go M10/6–11,
E9, E10, E17, E30, E31, E36).

<!-- req: P/05-R042 -->

ResourceDenied (`error=refused`, detail,
role on a refusal of the role) — 403 of the resource gateway, before the route handler. A TLS refusal before HTTP
does not get an invented HTTP body. Every applicable common answer is entered in the OpenAPI.
With busy — Retry-After: 1. On an unknown path — 404; on an unsupported method of a known
path — 405; at the resource both are without a body. This common rule is enough:
it does not create a separate OpenAPI method for every impossible operation.

<!-- req: P/05-R057 -->

**Route matching form.** The OpenAPI path item has a unique integer `x-route-priority`: smaller is earlier. Match the raw path exactly, with no percent-decoding of literals, path normalization or implicit trailing slash. A path parameter declares `x-path-capture` (`segment` or `remainder`, only at the end) and `x-path-decode: percent-segment`. Capture the raw remainder including an empty tail and empty inner segments; decode each captured segment separately. A decoded slash does not create a separator and is invalid. Empty or other out-of-form values are parameter errors of the selected operation, not a fallback to another route. First filter the structurally matching templates by the HTTP method, then select their lowest priority; only when no such method exists is the answer the common bodyless 405 (no matching template: bodyless 404). The parameter’s `x-path-error` maps each applicable HTTP method to `{status, response_schema}`: the existing OpenAPI component name or `-` for no body. In particular the generic objects GET remains available for a blob-shaped key when the specific blob route has only PUT. The exact priorities, capture mode and refusal projections are the OpenAPI form, not a second route list in prose. Schema refusal and decoding refusal do not normalize a foreign or invalid key into a file path. Error text inside ResourceError remains a non-empty diagnostic, not a new fixed error word.

<!-- req: P/05-R043 -->

**Admission to the resource doors** (ADR-0075 addendum of 2026-10-12 (3)). The resource with TLS checks the client: the chain up to the authority,
the serial number not in `revoked` ([the role certificate contract](../../common/contracts/role-certificate.md) `revoke`), exactly one role of the route row, CN = `<role>.<SAN DNS>`; otherwise a refusal
of the handshake or 403 `ResourceDenied` with the role and the route. The client checks the role `resource` and the SAN DNS of the server against the host
of the address; an IP with TLS — a refusal of the client.

<!-- req: P/05-R044 -->

For door mode `mtls`, the per-operation role table is [forms/door-roles.tsv](../forms/door-roles.tsv), with the paths and methods of the OpenAPI. `<sub>worker` expands only over the loaded manifest catalogue; `*` means any authenticated kit role. The role check precedes the matched operation handler; the TLS checks above remain mandatory. The loopback mode keeps the admission of the role certificate contract. This does not admit unknown paths or methods.

<!-- req: P/05-R045 -->

**Profile limits.** A bucket file is read whole or by one Range; multiple Ranges and
conditional HTTP requests are not part of the lesson. The size of the answer is fixed before reading; the answer
does not promise a snapshot of the whole tree. After the output has started, a break of the stream does not turn into a second
HTTP status: the caller does not accept incomplete bytes as a whole copy. The mirror reception is limited by
64 MiB and by the read term declared by the deployment; exceeding the size — 413, the term — 408.
`PUT /v1/objects/<sub>/blobs/<digest>` is the body copy of a neighbour (the table above; N1.1 «Bodies at the resource»); `PUT /<rows>/<id>/<blob_field>`
belongs wholly to [P/06.1](../../06-console/spec/06.1-console.norms.md) N2 (the bytes door of the console); other
objects the resource door does not write — a refusal of the write of a non-blob, there is no partial copy of the blobs contract.

---

## N3 Procedures

### resource start — schema check

<!-- req: P/05-R046 -->

The process input inventory is [forms/daemon-flags.tsv](../forms/daemon-flags.tsv); derived defaults and imported validation remain the linked rules. It introduces no CLI flags.

<!-- req: P/05-R047 -->

The resource side of the common block [P/06.6](../../06-console/spec/06.6-console.norms.md) N3 «console start — schema check» (from M10/10 N3,
part of M10/10-01); the row `platform/schema` and its raising — P/06.6 N1.1a; the other processes — P/06.6, P/03.2,
P/04). The order of the resource start — [life cycle](../lifecycle.md).

<!-- req: P/05-R048 -->

```
as the first step of the resource start, before reading the manifest (P/02.3): the schema contract «Check at start» ([the schema contract](../../common/contracts/schema.md); moved there
without a change; layout audit A-02, the decision of the Architect of 2026-10-25; review of stage B 3–5, № 26)
```

### write an event (the platform, by observe of the subsystem)

<!-- req: P/05-R049 -->

The steps of writing a line (the class, `of`, suppression, the bucket by `t`, appending and `fsync`) and their «Races» — [the event log contract](../../common/contracts/event-journal.md)
«Writing a line» (the lesson is the owner of the contract; moved there from this procedure so that the writers — chapters P/03.6 and P/06.4 — do not
stand on the norms of the lesson; review of stage B 3–5, V1). The refusals of the write — N4.

### query (resource) → {events, state, truncated}

<!-- req: P/05-R050 -->

```
1. check the parameters (N1.3)                                         → 400 (ResourceError at the resource, ConsoleRefusal at the console)
2. candidates: a window ≤ 144 buckets — names by time; wider — a listing of the directory; if a bound cannot be represented by a calendar name — a listing, without an overflow; both trees of the subsystem (and .alarms);
   the copies .mirror/*: the same bucket is a duplicate, it answers under the name of the owner
3. read the files from the place of the last read (a cache by size/mtime/inode); a torn line — skip it (partial);
   an unreadable line or a file not in its place — skip it and count it in lines_garbled (N1.3), the answer is not 503
4. filter: kind, subsystem, unit — the logical reference <tree>/<unit>, for a line of the tree .alarms — without the suffix (and the lines with of = unit; a parameter with the suffix .alarms — the form UnitRef allows it — is not normalized and matches no line: 200 without matches, C05-QUERY-UNIT-ALARMS-01), class, the window from ≤ t < to (or likewise by occurred: buckets up to to + late, the event log merge contract `by`)
5. epoch_is and fenced the resource does not set: they are set by the merger (the event log merge contract); the resource needs no rights to <sub>/epoch/*
6. remove the id duplicates, order and take the first limit by cut (the event log merge contract); truncated = the number of candidates after deduplication minus the number given
→ the lines of N1.3; more than 8 requests at once → 503 busy, Retry-After: 1 (counted are the requests /events that are being computed now;
  a held wait /events/wait does not take this lane — C05-WAIT-COMMON-LANE-01)
```

<!-- req: P/05-R051 -->

**Races.** Reading an open bucket during appending: only whole lines are given, a torn one is not given and the answer carries `partial: true` (`truncated` is a number, N1); a listing does not fix the content of the files: a file that has vanished does not confirm an empty bucket. A read error of a file or a directory is not given as a full answer; after the HTTP stream has started — a break, before it — 503 ResourceError. An unreadable line is not a read error: it is skipped and counted (N1.3, P/01.1 N0 «Stability of output»).

### resource pass — at start, then every 600 s from the end of the pass

<!-- req: P/05-R052 -->

The first pass is right after readiness (the door row is written), not after 600 s: the reconciliation after a restart and the edges of
`free_ask` do not wait for a window of up to 10 min; the next one is 600 s after the end of the previous one (C05-PASS-FIRST-AT-START-01, the decision of
the Specification on the recommendation of the Architect, 2026-10-30).

<!-- req: P/05-R053 -->

```
retain:  for each tree: days = <sub>/retention | the default (tree.alarms — alarms_retention | the default; audit, console —
         the default; the defaults — the event log contract «Retention of a tree», layout audit A-23, the decision of the Architect of 2026-10-25);
         days is not a number or ≤ 0 or the row did not answer → not known: remove nothing, name it in the heartbeat — a wrong days:
         <sub> in retention_garbled and retention_withheld[<sub>] = days_garbled; the row did not answer — retention_withheld[<sub>] =
         unknown; the holds are not read (the holds contract) — retention_withheld[<sub>] = holds_unread (C05-RETENTION-PULSE-33);
         each tree is kept by its own term (<sub> — retention, <sub>.alarms — alarms_retention); retention_withheld[<sub>]
         — one reason in the order: unknown → days_garbled → holds_unread; retention_garbled — a <sub> for which any term
         (retention or alarms_retention) is wrong, regardless of retention_withheld (R05-RETENTION-MIXED-51-01, the decision of the Architect of 2026-10-25);
         apply the inclusive deadline now >= written + seconds of N1.3 retention, only to closed buckets (the console marks — not earlier than the longest; holds keep — also the buckets
         of the units of other subsystems whose about names the held one, and the buckets of unknown units; what a row holds, the window,
         an incomplete declaration and unreadable rows — the holds contract common/contracts/holds.md, P/06.4 N1.5;
         the mirror copies — days + 1 h); the journal events.removed; index.forget
usage:   measure the volumes (a probe ≤ 5 s); the heartbeat space/volumes
relieve: platform/space.enabled ∧ used/total > high → for manifests with requests.free: need = used − total·low − Σ freeing
         (Σ — over the live heartbeats of the workers of this subsystem on this server, freeing.<volume> of this volume; N1.4 free_ask);
         platform/space does not read — the step is not executed (N1.4 space); a heartbeat of a worker of this subsystem on this server does not
         read — the need of this subsystem is not computed, the step neither writes nor removes its row free-*, the reason goes to the journal (P1;
         the class of lines 21, 24 of the list V7 item 3)
         need > 0 → write free-<server>-<volume> {free: need, volume, server, at}: cas "" or cas by the version of a row of ITS OWN form
         (without unit AND with the exact server/volume of the current volume); before the write check the grammar of N1.4 `free_ask`;
         under this key a row with unit, another's server/volume or a spoiled form → do not touch it, the journal free_ask.key_taken, skip;
         need ≤ 0 (all that is needed is already being freed, ADR-0059) or below low → delete the row of its own form if there is one: delete with cas of the version
         on which the absence of unit AND the exact match of server/volume were checked (P/01.1); conflict — under the key there is already another row (an ordinary request or a new own one) → do not touch it,
         the journal free_ask.key_taken
mirror:  platform/mirror does not read → the step is not executed, settings_unread: mirror (N1.4 mirror); platform/mirror.enabled → the neighbours = the next copies live ones by name (liveness — the door row, N1.4 mirror); the closed buckets that the neighbour does not have
         (the sum) → PUT /mirror/<me>/<path> with X-Sum = SHA-256 of the bucket; PEER_FAILS in a row → the neighbour is skipped for the pass
each step is its own attempt; a step longer than PULSE_LIMIT → pass_stalled in the heartbeat
```

<!-- req: P/05-R054 -->

**Races.** In one pass retain precedes mirror; this is not a lock against another read/cleanup. Only a whole closed bucket with a checked sum is copied; a disappearance/an incomplete read gives a failed attempt, without the publication of a partial copy. The next pass lists the available buckets anew. The owner and the copy: a copy is never a source while the owner answers; `restore` (N1.4 «Bucket restore») pulls copies back only at the word of the owner. The removal of `free_ask` and an ordinary request under the same key: the resource checked the form at the version v and stopped; the reaper removed its old row by ttl, the console accepted an ordinary request with the same rid — the key has the version v′; `delete` with cas v answers conflict, the accepted request is intact; without cas it would have been deleted without an outcome (ADR-0054).

---

## N4 Refusals

<!-- req: P/05-R055 -->

The refusals of the console doors, of requests, marks and the reaper — [chapter 6.4](../../06-console/spec/06.4-console.norms.md) N4 (the holder side — chapter 3.6); the refusals of loading `suppress` — chapter 3.6, `older_epochs` — chapter 6.4.

<!-- req: P/05-R056 -->

The closed catalogue is [forms/refusals.tsv](../forms/refusals.tsv), `chapter = 5`. It preserves the four original cells in `cause`, `outcome`, `diagnostic`, `caller`; multiple fixed HTTP projections keep the same source `row`. `response_schema` is the OpenAPI component or `-` for a bodyless/text result; no error discriminator is invented. The original Range/hint/skipped-line success outcomes remain success outcomes.

---

## N5 Acceptance

The directory [`../acceptance/`](../acceptance/README.md): 35 independent scenarios, 292 steps — the objects door, the event
query, the resource paths (from the acceptance of M10/08), the door row
of the server and the presence lock (from the acceptance of M10/11;
sc. 16 — the Architect's decision on V2 of the plan of the move of lesson 6), the body copy at the
resource (from the acceptance of M10/10), sc. 17–28 of the coverage audit of P/05 (2026-10-30) and sc. 29–45 of its second pass (Gemini). Each gets
an empty store, objects and events, all except `10-body-copy` also a new console (the scenario `10-body-copy` needs no console and no
controller; review of stage B 3–5, № 26); the resource srv-a ([the common acceptance README](../../common/acceptance/README.md),
«Resource») is ready before the first step, for `09-resource-door`, `10-body-copy`, `16-presence-lock`, 17–28, 31 and 37–41 a step of the scenario starts it (`@start resource`; for 31 also the resource `srv-b`); the worker `w-1` — only for `16-presence-lock`, `19-service-names`, 42 and 43, the workers of `testsub2` — for `20-door-room` and 24–28, the controller — for 42. The installed manifest
`testsub` (for `10-body-copy`, `20-door-room`, `23-object-ceiling`, 24–31, 37–41, 44 and 45 — the catalogue `testsub` and `testsub2`) is part of the preparation, not user data. The numbers and names of the scenarios are
the former ones, except `09-resource-door` from M10/11 (there — 01; the number 01 is taken by `01-objects-door` from M10/08).

| № | Scenario | Norms |
|---|---|---|
| 01 | `01-objects-door` (M10/08): the objects door: a listing of an empty family, 400 on scope, 403 on a family outside the door, 404 on an absent one, 405 on PUT of a non-blob; the listing is a filter (`prefix=testsub/` — 200), `other/` — 403, an empty parameter and non-UTF-8 — 400, a directory of two parts — 403, U+2028 in a key — 400, `OPTIONS` and `PUT` of the listing — 405 (reconciliation of python and go M10/6–11) | N1.1, N2 |
| 02 | event query: 400 on keep/by/class/a bare unit; an empty answer `{events: [], state: "live"}`; the grammar of `from`/`limit`/`unit`, an empty and repeated parameter, an unknown hint parameter, non-ASCII digits — 400, `1_0` is a number; `POST /events` — 405 (reconciliation of python and go M10/6–11); at the console `from` by the grammar of the time reader: `+1`, `%2B1`, `%201`, `1e3` — 400, `%31` — 200 (C06-EVENTS-QUERY-LEXEME-162-01, the Architect's decision of 2026-10-27) | N1.3, N1.6, N2, N4 |
| 08 | resource paths: `..`, `%2F`, another's tree in `/mirrored`, `/mirror`, `/events/{path}` — 404/400; `GET` on `/mirror/…` — 405; `/buckets` not of two segments — 404 (reconciliation of python and go M10/6–11, E26, E27, E29–E31, E36); the line `{bad` in a bucket — `/events` of the resource and of the console 200 with `lines_garbled: 1` (E19); an alarm in the tree `audit/console` (not `.alarms`) — `class: alarm` by the field (the second pilot, N-2) | N1.3, N1.6, N2, N4; the event log contract |
| 09 | `09-resource-door` (M10/11): resource: the heartbeat and the door row `platform/doors/srv-a` with `at` that changes; `/servers` sees the resource `live`; `w2c_resources_live 1` | N1.4 `door_row`; P/02.4 N1.1, N3 «server start»; P/04 |
| 10 | `10-body-copy` (M10/10): the body copy at the resource: 204, the copy reads; a wrong digest — 422; without `X-Written` — 400; uppercase hex and a subsystem without a blob field — 405 | N1.1 «Bodies at the resource» `mirror`, N2 (reconciliation of python and go M10/6–11, T10, T11) |
| 16 | `16-presence-lock` (M10/11): the presence lock — the resource and the worker `w-1`: `running: [testsub/w-1]`; `@sigkill` — `running: []`; a new start of the same name — `running` again (the second pilot, N-1) | N1.4 `presence`; [the presence lock contract](../../common/contracts/presence-lock.md) |
| 17 | `17-schema-refusal`: `platform/schema` with `version` above SCHEMA or not a number — `@start resource` exits with the code 2, there is no door row; `version` 1 — it starts (coverage audit of P/05, F01) | N3 «resource start — schema check»; [the schema contract](../../common/contracts/schema.md) «Check at start» |
| 18 | `18-schema-read-wait`: the store is silent to the resource (`@cut role resource store`) — a read error of the schema: the resource waits, does not exit; the store answers — the door row without a restart (coverage audit of P/05, F01) | N3 «resource start — schema check»; the schema contract «Check at start», «Boundary» |
| 19 | `19-service-names`: the directory lock `~lock` of the write of a worker heartbeat — outside the listing of the objects door, the key `~lock` — 404 (coverage audit of P/05, F02) | N1.1 `disk`, N2; [the event log contract](../../common/contracts/event-journal.md) «File names in shared trees» |
| 20 | `20-door-room`: the field `door` in the resource heartbeat; `room.testsub2`, `live.testsub2` of the door row by the live locks — a number n ≥ 2 in `live`, the base n = 1 and a name without a number — only in `room` (coverage audit of P/05, F03) | N1.4 `heartbeat`, `door_row`, `room`; [the presence lock contract](../../common/contracts/presence-lock.md) «Count `room`» |
| 21 | `21-events-wait`: `/events/wait` — by the term `{changed: false, seq}`; `since=0` with a line under `want` — at once `changed` with `touched`; `seq` is monotonic; the cursor `since=seq` — without changes (coverage audit of P/05, F05) | N1.6, N2 |
| 22 | `22-torn-tail`: a bucket tail without LF — not in `events` and `truncated`, `partial: true`, not `lines_garbled` (coverage audit of P/05, F06) | N1.3 «Unreadable bucket line», N3 «query» step 3; the event log contract `torn` |
| 23 | `23-object-ceiling`: a body copy of exactly 64 MiB — 204 and the read 200 (coverage audit of P/05, F07); +1 byte — 413 — checked by reading (C05-CEILING-PLUS-ONE-READING-01) | N1.1 «Resource ceilings», N2, N4 |
| 24 | the edges of `free_ask` on the first pass (C05-PASS-FIRST-AT-START-01; coverage audit of P/05, F04): the resource writes its own request row `free-srv-a-events`, in the heartbeat `short` ≥ 1 | N1.4 `free_ask`, `space`, `heartbeat`; N3 «resource pass» `relieve` |
| 25 | under its own key a row with `unit` — not touched (the same version), the event `free_ask.key_taken` | N1.4 `free_ask`, `space`, `heartbeat`; N3 «resource pass» `relieve` |
| 26 | under its own key a row with another's `server` — not touched, `free_ask.key_taken` | N1.4 `free_ask`, `space`, `heartbeat`; N3 «resource pass» `relieve` |
| 27 | under its own key a row with another's `volume` — not touched, `free_ask.key_taken` | N1.4 `free_ask`, `space`, `heartbeat`; N3 «resource pass» `relieve` |
| 28 | under its own key a row with a volume out of profile (`b-c`) — not touched, `free_ask.key_taken` | N1.4 `free_ask`, `space`, `heartbeat`; N3 «resource pass» `relieve` |
| 29 | `29-row-objects`: the row objects `objects.rows` and `commands/*` — 403 also with a written row `objects/<key>`, on any `scope`; their `prefix` — 403; `prefix=testsub2/` — 200 without them (coverage audit of P/05, second pass, G01) | N1.1 `row_object`, `door`; N2; N4 |
| 30 | `30-copy-written-max`: `written` of a body copy is the source one, an already lying one does not decrease — the greater of the two (G01) | N1.1 `written` (C05-COPY-WRITTEN-SOURCE-01), «Bodies at the resource»; N2 |
| 31 | `31-objects-cluster`: two resources — the body copy to the neighbour on the first pass with the source `written`; `scope=cluster`: an equal `written` — the greater server, the fresh copy wins; a silent server — `missing`, `X-Missing` at 404 (G03) | N1.1 `cluster`, «Bodies at the resource» `mirror`; N1.4 `pass`; N2 `scope`, `X-Missing` |
| 32 | `32-mirror-put-refusals`: `/mirrored` without copies — 404; `PUT /mirror` of an open bucket, without `X-Sum`, `X-Sum` not in form — 400, a wrong sum — 422, there is no copy (G04) | N1.6; N2; N4 «mirror» |
| 33 | `33-mirror-put-read`: a copy of a closed bucket — 204, `/mirrored` — `{copies}`, a repeat does not shift `written`, the bytes with `X-Sum`; the heartbeat `mirrors` (G04) | N1.6 (R05-G04); N1.4 `heartbeat`; N2 |
| 34 | `34-events-alarms-unit`: a line of the tree `testsub.alarms` — `subsystem` and `unit` without the suffix, `class: alarm`; `unit` with `.alarms` — 200 without matches (G05) | N1.2 (E32); N3 «query» step 4 (C05-QUERY-UNIT-ALARMS-01) |
| 35 | `35-events-cut-order`: `HEAD /events` — 405; an id duplicate — the first line; the order `cut` (the class, `keep`, an equal time — id), `by=occurred`, `late`, the bound `to`, `truncated` after deduplication (G05) | N1.3 `query`, `cut`; N2; N3 «query» step 6; the event log merge contract |
| 36 | `36-events-bucket-stream`: `/events/{path}` — 200 with `X-Sum`, 206 and 416 with `Content-Range`; `/buckets` of an unknown unit — 404 (G05) | N2; N4 «buckets», «bucket» |
| 37 | `37-retention-garbled`: a wrong `days` in `retention` and in `alarms_retention` — `retention_garbled`, `retention_withheld: days_garbled` on the first pass (G06) | N3 `retain`; N1.4 `heartbeat`; N4 (C05-RETENTION-PULSE-33, R05-RETENTION-MIXED-51-01) |
| 38 | `38-holds-garbled-row`: a hold row without a readable window — `garbled_rows.notches` (G06) | N3 `retain`; N1.4 `heartbeat`; [the holds contract](../../common/contracts/holds.md) |
| 39 | `39-settings-unread`: unreadable `platform/space` and `platform/mirror` — `settings_unread: [mirror, space]`, its own row `free-*` is not written (G06) | N1.4 `space`, `mirror`, `heartbeat`; N3 |
| 40 | `40-space-disabled`: `enabled: false` — its own row `free-*` is removed, `short` 0 (G07) | N1.4 `space` (E45), `heartbeat.short`; N3 `relieve` |
| 41 | `41-space-band`: between `low` and `high` with `need > 0` its own row stands as it is (G07) | N1.4 `free_ask` (E44); N3 `relieve` |
| 42 | `42-heartbeat-units`: `units` of the resource heartbeat — the ids of the units from `status` of a live worker in ascending order of bytes (G08) | N1.4 `heartbeat` (E39), `running` |
| 43 | `43-spoiled-object-door`: a spoiled object — the door gives it as it is: the listing and `GET` 200 (G08) | N1.1 `door`; «Implementation decides» item 8 (C05-SPOIL-OBJECT-BYTES-01) |
| 44 | `44-objects-door-family`: `objects.door` of the manifest — `testsub2/tickets/t1` (`@put object` from `inputs/`) — `GET` 200 and in the listing; `testsub/tickets/t1` without `objects` in the manifest — 403 (G01) | N1.1 `door`; N2; N4 |
| 45 | `45-gone-door`: the tombstone `.gone/<object-key>` (`@put object` from `inputs/`) — outside the ordinary listing, `prefix=.gone/` and `GET` of the body — reading, `PUT` — 405; an older copy — 409, there is no key; a newer one — 204 with the source `written`, the tombstone is removed by the same action (G02) | N1.1 `written` (C05-GONE-REWRITE-AT-WRITE-01), `door` (C05-GONE-BODY-READ-01); N4 «deleted later»; [the tombstone contract](../../common/contracts/tombstone.md) `listing`, `rewrite` |

TSV observes only the listed steps. The other evidence is listed separately
in the acceptance README: the writing/reading of buckets and the real fsync barriers, retention/holds, the mirror and a stream with a break, free_ask
(the computation of `relieve` with the answer of the workers `freeing` — [vectors](../vectors/relieve/README.md); the VMS request freeing),
the waits wait `full`/`replaced`, `restore` and tombstones on two resources. Reading the specification
checks the consistency of the order; reading the implementation — the corresponding branches and operations;
neither replaces the execution of timers, TLS, fsync, streams and failures on a stand.

---

## Implementation decides

An implementation is to name in its description:

1. **the object store on the box and in the cluster** — the layout on disk (directories, the delete tombstones `.gone/<object-key>` — the tombstone contract) and the size limits; the address `OBJECTS` and the access of the client — [the object store client contract](../../common/contracts/object-client.md) (C10-OBJECT-ADDRESS-32);
2. ~~**how the resource learns the presence of processes**~~ — normed: [the presence lock contract](../../common/contracts/presence-lock.md) `presence_lock` (the second pilot, N-1);
3. **the eviction policy of the index cache** within 64 MiB (N1.3); the number of merge lanes (8) and the term (3 s) are a norm of [P/06.4](../../06-console/spec/06.4-console.norms.md) N3 «merge», not a choice;
4. **the long poll `/events/wait`**: the structure of the memory of observations and the deployable limit of waits; the forms of want/the answer and the profile of the timeout are N1.6, not a choice;
5. **the journal line**: the fields beyond `sub`/`target`/`addr` of the event log contract `journal`, the writer role, the epoch of the tree (`e1`);
6. **streams and the reading of a body**: the term of the mirror reception, the way to check the whole body before publication, the distinction of a refusal before the headers and a break after them (the limits and terms of the POST of the console — [chapter 6.4](../../06-console/spec/06.4-console.norms.md) «Implementation decides» item 3);
7. **PULSE_LIMIT** of the resource: a finite positive number of seconds from the declared profile, unchanged for the duration of a run; N1.4 sets the measurement and the outcome, not a particular number.
8. **the commands to write and to spoil an object** for acceptance (`@put object <key> <file>`, `@spoil object <key>` of the vocabulary of the «Stand»): an object with the bytes of the file; after spoiling, the read of the object is unreadable: the bytes of the object are spoiled, not its file or directory — the door gives the object as it is (N1.1 `door`), the reader counts it as garbled (C05-SPOIL-OBJECT-BYTES-01, the decision of the Specification; from M10/11 «Implementation decides» item 10, the move of lesson 6).
9. **the internal contract of a local object**: the bytes of the object file on disk (the families `heartbeats`, `contenders` and other
   objects of N1.1) are the implementation's own, not a public contract; what is observed is the norm (N1.1 «whole or nothing», N4 «object:
   the copy/listing does not read» — 503). The description and the API of the library are written in the repository of the implementation by the owner of this lesson before the
   code; the worker and the other writers of the families read only the contract and the API; a mix of languages in one box is not supported
   (guesses of stage C W03-OBJ, OF-G01/G02, ADR-0087 addendum (12) item 7).
10. **the connection limit of the resource door** (the «common lane» of N2) for all routes: no less than 64 at once and 32 per address (no less than
   LONG_POLL_WAITERS + 8 with a margin, so that full and busy are reachable); beyond it — 503 busy, Retry-After: 1
   (C05-WAIT-COMMON-LANE-01).
11. **`PUT /mirror/<own server>/…`** — a copy of its own bucket from itself: accept it (a copy in `.mirror/<own server>/`) or refuse
   (400 without a body); a copy from itself breaks nothing (a copy is never a source while the owner answers, N1.4 `mirror`),
   acceptance does not check it (C05-MIRROR-PUT-SELF-01, the Architect's decision of 2026-10-30, norm questions of the Gemini audit, P/05 item 2).

---

## Readiness checklist

An implementation conforms to the lesson when every norm is fulfilled; a norm id `P/05-MM` is what the decision deltas, findings and window records refer to (ADR-0080 addendum 6):

- [ ] **P/05-01** the object of N1.1: whole or nothing, a writer per directory, create-once, the platform families are closed; one encoding of names ([the event log contract](../../common/contracts/event-journal.md) «File names in shared trees»: `%XX`, `%h<sha256>`; the threshold of `%h` — by the full file name: the component, the suffix of the norm, `TEMP_RESERVE` 16 bytes — checked by reading, review of stage B 3–5, № 20) — sc. 03 step 10 [of the acceptance of chapter 6.4](../../06-console/acceptance/4/README.md) (`:` of the console instance), the rest — by reading the contract/README; the presence lock ([the presence lock contract](../../common/contracts/presence-lock.md)) — sc. 16 (from M10/11), sc. 12 [of the acceptance of P/04](../../04-controller/acceptance/README.md); row objects for `objects.rows` and `commands/*` — sc. 29 (`testsub2/marks/*`, `commands/*` of both subsystems; the second pass of the audit); sc. 05 [of the acceptance of chapter 3.6](../../03-worker/acceptance/6/README.md); checked by reading
- [ ] **P/05-02** the objects door of N2: the families `PLATFORM_DOOR`, the codes — sc. 01; the fresh copy, an equal `written` — the greater server, `missing`, `X-Missing` at 404 — sc. 31; `objects.door` of the manifest (`testsub2/tickets/*`; for a manifest without `objects` — 403) — sc. 44; the tombstones `.gone/` — read only (the listing `prefix=.gone/`, the body, `PUT` — 405) — sc. 45; spoiling the bytes of an object — the door gives it as it is — sc. 43; the listing is a filter, `*` is a subsystem of the catalogue, the grammar of the key and the parameters, `OPTIONS` — sc. 01; the case of the key — sc. 05 step 13 [of the acceptance of chapter 3.6](../../03-worker/acceptance/6/README.md); the service names with `~` outside the listing and not a key ([the event log contract](../../common/contracts/event-journal.md) «File names in shared trees», ADR-0083 addendum (16)): the directory lock `~lock` — sc. 19; the temporary name of the writer — by the same rule of traversal, checked by reading (the stand does not stop a write between temp and rename)
- [ ] **P/05-03** the event line (the event log contract «The line and the bucket»): `t`, `kind`, `id`, `of` of the platform, `class` only for an alarm, without `v` — sc. 03 of the acceptance of chapter 6.4; checked by reading
- [ ] **P/05-04** the bucket by `t`, 600 s, the epoch in the path, the alarm tree, `fsync` of alarms and of the journal (the event log contract) — checked by reading; a torn line — sc. 22 (reading by the index)
- [ ] **P/05-05** the index: one per resource, without rebuild, the cache does not affect correctness; the query of N1.3 with `epoch_is`, the cut and `truncated` — sc. 02; sc. 03 of the acceptance of chapter 6.4; an id duplicate, the order `cut`, `keep`, `by=occurred`, `late`, `truncated` after deduplication, `HEAD /events` — 405 — sc. 35; `/events/{path}` 200 with `X-Sum`, 206 and 416 with `Content-Range`, `/buckets` of an unknown unit — 404 — sc. 36; the grammar of the parameters — sc. 02; the journal without `requests.journal`, BucketInfo JSON Lines, Range — sc. 04 of the acceptance of chapter 6.4; an unreadable bucket line and a file not in its place — 200 and `lines_garbled` (P/01.1 N0 «Stability of output») (sc. 08 steps 12–14; a finding of the move); a torn tail — `partial: true`, not in `events`/`truncated`, not `lines_garbled` — sc. 22; the class from the line's class field, absence means observation; .alarms selects writer layout and retention, never overrides class, `subsystem` and `unit` of alarms without the suffix, `unit` with `.alarms` — 200 without matches — sc. 34
- [ ] **P/05-06** the term per subsystem: 365/1095, «not known» — do not remove, the floor of the marks, holds, the journal `events.removed` — checked by reading; the reasons in the heartbeat: a wrong `days` in `retention` and `alarms_retention` — `retention_garbled`, `retention_withheld: days_garbled` — sc. 37; a hold row without a readable window — `garbled_rows` — sc. 38
- [ ] **P/05-07** the resource of N1.4: the heartbeat 10 s, the door row, its `room.<sub>` and `live.<sub>` (the numbers n ≥ 2 of the live locks, ADR-0084 addendum (3) R14′; review of stage B 3–5, № 26) by the live locks (ADR-0084; the presence lock contract «Count room»); the lock: the flock of the resource without waiting, ENOENT of stat — a mismatch, the delete of gone only after a matched comparison — checked by reading: a test with the worker stopped between open and flock (review of stage B 3–5, № 19); the content of the lock by the family presence-lock: empty or out of form at a busy one — a live one without a number (in `room.<sub>`, not in `workers`, `running`, `live.<sub>`), `unknown` — only an unreadable file — checked by reading (review of stage B 3–5, № 23); the pass of 600 s in the order of N3, `pass_stalled` — checked by reading; the field `door {addr, mode: loopback | mtls, cert_until}` in the heartbeat — sc. 20 (`cert_until` with mtls — checked by reading; review of stage B 3–5, № 28); `room.<sub>` and `live.<sub>` by the live locks: without workers, the number n ≥ 2, the base n = 1, a name without a number — sc. 20; the heartbeat fields `units`, `waits`, `restore`, `mirror` — sc. 05 step 12 of the acceptance of chapter 3.6; `units` of two units in ascending order of bytes — sc. 42; an unreadable worker heartbeat does not enter `units` (C05-UNITS-PULSE-GARBLED-01) — checked by reading; `mirrors` — sc. 33; `settings_unread` — sc. 39
- [ ] **P/05-08** the disk marks by shares (no row `platform/space` — enabled 0.85/0.75 — checked by reading; disabled — its own row is removed, `short` 0 — sc. 40; between low and high with need > 0 it stands — sc. 41; the row does not read — `relieve` is not executed — sc. 39), the request `free-*` by the formula, the write with `cas` by the version of its own form, the removal under the mark only by `delete` with `cas` of the checked version (conflict — do not touch); volume without a hyphen by N1.4 `free_ask`, a row with `unit` or another's server/volume under its own key is not touched — the journal `free_ask.key_taken` (its own row and `short`, four edges of a foreign form — sc. 24–28); nobody executes or marks it; the resource itself deletes nothing except buckets — checked by reading
- [ ] **P/05-09** the mirror: the neighbours by name and liveness by the door row (the bound — the vector `fresh-age`), closed buckets, a copy is not a source, the limits, `mirror.skipped` — checked by reading; the paths `/mirror`, `/mirrored`, `/events/{path}`, `/buckets` (`..`, `%2F`, another's tree) and the methods — sc. 08; the reception of a copy: an open bucket (a window in the future), no `X-Sum` or not in form — 400, the sum — 422 without a copy — sc. 32; 204, the listing `/mirrored`, a repeat does not shift `written`, the bytes with `X-Sum` — sc. 33; OWS of `X-Sum`, the copying of buckets on two resources — checked by reading (a bucket closes after 600 s)
- [ ] **P/05-10** `/events/wait` — the hint of N1.6: the forms `{changed: false, seq}` by the term and `{changed: true, seq, touched}`, `since=0` with lines under `want`, a monotonic `seq`, the cursor `since=seq` — sc. 21; the forms full/replaced, the profile of the parameters, the limit of waits and the displacement of its own identity; full/replaced does not advance the cursor; the periodic pass is mandatory — separate probes of the acceptance README, not TSV; an unknown parameter and non-ASCII digits — sc. 02; the trees console/audit without a hint — checked by reading
- [ ] **P/05-11** the delete tombstones and the convergence of copies (N1.1 «Tombstones»): the tombstone at the deleter — outside the ordinary listing, `prefix=.gone/` and the body — reading, an older copy — 409, a newer write removes it by the same action (C05-GONE-REWRITE-AT-WRITE-01) — sc. 45; the dropping of copies by a neighbour, the confirmations and the removal by `peers ⊆ acked` — checked by reading (the stand of the [system acceptance](../../common/acceptance/system/README.md) with two resources; there is no scenario)
- [ ] **P/05-12** `restore` of events from neighbours at the resource start (N1.4 «Bucket restore»), repeats, «done» only after a full attempt, all known doors; `restored` — only the pulled buckets (step 49 of the drill `05-power-pull`)
  on the loss of the local events — checked by reading (a stand with two resources)
- [ ] **P/05-13** the schema check at the resource start (N3 «resource start — schema check»; part of M10/10-01): no row — its own SCHEMA, not a number or version > SCHEMA — do not start (the Architect's decision of 2026-11-04, as P/03.2), with the code 2, a read error — wait without starting work. Version above SCHEMA and not a number — the code 2, there is no door row, version 1 — it starts — sc. 17; a read error — it waits, without a restart it starts after the store returns — sc. 18; no row — its own SCHEMA — every scenario with `@start resource`; «before reading the manifest» — checked by reading
- [ ] **P/05-14** the body copy at the resource (N1.1 «Bodies at the resource» `mirror`, N2; part of M10/10-07): the mirror of bodies always (copies 1 without the row `platform/mirror`, on the first pass to the neighbour with the source `written`) — sc. 31; the reception with a hash, the copy door only for a blob key of a subsystem with a blob field — sc. 10; `written` of a copy does not decrease — sc. 30; the refusals of the copy door (422, 400 without `X-Written`, 405) — sc. 10; 409 «deleted later» — sc. 45; 408, 411 and the closing of incoming copies in the cleanup window (part of M10/10-08) — checked by reading
- [ ] **P/05-15** the resource ceilings (N1.1 «Resource ceilings»; part of M10/10-06): 64 MiB at the resource door — the refusal 413, not a truncation; `limit` of `/events` — sc. 02; a body copy of exactly 64 MiB — 204 and the read 200 — sc. 23, +1 byte — 413 without a write — checked by reading (413 before reading the body; the door is not obliged to drain beyond its volume — the client can get a break, P/01.1 N2.1 and item 9; C05-CEILING-PLUS-ONE-READING-01, -02); GET of an object larger than 64 MiB and `max_bytes` of the object store — checked by reading (the acceptance README, evidence outside TSV)
- [ ] **P/05-16** the request to free space: the addressee — the workers of the subsystem on the server `<server>`, `<volume>` — the volume of the resource, `Σ freeing` — over the live heartbeats of this subsystem on this server for this volume (N1.4 `free_ask`, N3 `relieve`) — the vectors [`relieve`](../vectors/relieve/README.md): the answer `freeing: 0` and `freeing: N` (the VMS request freeing)

