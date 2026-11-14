# The event journal contract: the line, the id, the bucket, file names, writers, writing a line

This English text is the source; the Russian translation `ru/contracts/event-journal.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Platform» (ADR-0083 addendum (5): a contract that several processes read and write lies in
`Platform/common/`; review of stage A 3–5, № 9). The owner is the resource [P/05](../../05-resource/spec/05-resource.norms.md):
it reads the buckets (the index P/05 N1.3), copies the closed ones (P/05 N1.4 `mirror`), removes them by term and pulls them back
(P/05 N3 «resource pass», N1.4 «Bucket restore»); the order of writing a line is the section «Writing a line» below (moved
from P/05 N3 «write an event»; review of stage B 3–5, V1). Lines are appended
(`append`) by: the worker — the events of the subsystem by `observe` (chapter [P/03.6](../../03-worker/spec/03.6-worker.norms.md)),
the console — the journal and the marks of the operator (chapter [P/06.4](../../06-console/spec/06.4-console.norms.md)),
each process of the platform — the journal `audit` of its role; the encoding of file names is performed by each process that puts a file into
the root of events or of objects. Moved from M10/8 N1.1 (the paragraph «File names in shared trees») and N1.2 (the blocks `line`,
`bucket`, `class`, `journal`, `writer`, the paragraph on the id) without a change of behaviour: the suppression of repeats (`suppress`) — chapter
P/03.6 N1.2; `older_epochs` and the marks of the operator (`marks`) — chapter P/06.4 N1.2. The vectors — the section «Vectors» below.

Normative keywords follow the [course canon](../NORMATIVE-TERMS.md).

## The line and the bucket

```yaml
line:                                        # one JSON line in the bucket file
  t:        <seconds of the wall clock of the writer when written>  # MUST; selects the bucket
  kind:     <kind>                                                  # MUST
  id:       e1-<hexUTF8(tree)>-<hexUTF8(unit)>-<epoch>-<hexUTF8(instance)>-<number>                   # MUST; unique; duplicates of copies are removed by it
  of:       <sub>/<id>                                             # the unit the line is about; set by the platform from about;
                                                                   # its own of — only the trees console and audit
  class:    alarm                                                  # only in an alarm; observation is not written
  occurred: <seconds>                                              # when it happened; optional
  # t and occurred are time of common.time, as all times (P/01.1 N0 «Time in a row»): the writer writes strictly (the codec
  # Platform/common/data/codec.tsv time: a number, up to three fraction digits), the reader uses the same fraction bound (a number or a string by
  # the codec of the reader); the form of the line — the families events of P/05 by tree (Platform/05-resource/data/events-<tree>.schema.json and .outcomes.tsv: events-unit,
  # events-unit-alarms, events-audit, events-audit-alarms, events-console, events-console-alarms, events-mirror); the vectors of reading —
  # common/vectors/journal bucket.tsv t-* (the stage C guess EJ-G07, the Architect's decision of 2026-10-23)
  <fields>:   words of the subsystem                                 # v is not written: absence = version 1; v is a positive
                                                                   # integer by the form, v = 2 is kept, there is no choice of behaviour
                                                                   # by v (EJ-L04); v is an additional
                                                                   # field, the reader tolerates it, the writer writes strictly by the form
                                                                   # without v (the stage C guess EJ-G10)
  depth:    the depth of the whole line (the object of the line, extra and the values of names included) — no more than JSON_DEPTH = 128
            (P/01.1 N2.1; the count of levels is there too: nested objects and arrays, the root object — 1); the writer does not write a line
            that is deeper — a refusal to the caller, nothing is written; the reader (the resource, the merger — the console and the worker) — the line
            is unreadable: a skip and the count garbled (lines_garbled, P/05 N1.3), as the others not by the form (EJ-DEPTH-BASELINE33, the Architect's decision of 2026-10-25)
bucket:
  path:     <root>/<tree>/<unit>/e<epoch>/<YYYYMMDDTHHMMSSZ>.events.jsonl    # root: RESOURCE_ROOT | <PLATFORM_DIR>/events;
                                                                          # the tree — <sub> of the subsystem, console or audit (review of stage B 6–7, № 35)
  alarms:   <root>/<tree>.alarms/<unit>/e<epoch>/…                              # each tree has a tree of its own
  span:     600 s; the start = floor(t / 600) × 600 by UTC; closed when end ≤ now; rolls only by the clock
  years:    the year of the bucket name — four digits, 0001–9999 (from below time is limited by t ≥ 0, P/01.1 N0); t later than the year 9999 — a refusal
            of the write before an id is allocated (vectors common/vectors/journal years.tsv; the stage C guess EJ-G06)
  durable:  an alarm and the journal — fsync of the line and of the directories up to the root; an observation — no
  modes:    the group of the event trees — w2c-events (P/02.4 N1.1 users_groups; the events root — RESOURCE_ROOT (the environment file contract «Environment variables»; the default
            <PLATFORM_DIR>/events, the same object; EJ-G12) — 2771 w2c:w2c-events:
            passage for others without reading, the path to the presence locks .workers — the presence lock contract modes, the stage C guess PL-G03, the Architect's decision of 2026-10-23,
            N1.1 dirs); a directory in which more than one user of the group writes or deletes (the tree, <unit>, e<epoch>:
            created by the writer, the closed buckets are deleted by the resource P/05), — 2770; a directory of one writing user — 2750;
            a bucket file — 0660 if processes of different users of the group write it, otherwise 0640; the writers and the readers are
            members of the group by the units of P/02.4 (workers, the console, controllers, the resource, the domain processes); others — nothing;
            0755/0644 for all — no (the stage C guess EJ-L02/L03/L04, the Architect's decision of 2026-10-23);
            an existing directory or bucket with other permissions or group — the append is refused before the write, a line
            of the log and a count; the writer does not change existing objects itself (chmod/chown is a matter of the installation, P/02.4), new ones
            it creates with the permissions and the group of the norm (the stage C guess EJ-G11, the Architect's decision of 2026-10-23);
            the acceptance stand: the group of the root and of the event trees at all writers is the primary group of the stand process, on any
            OS and whether or not the machine has w2c-events (the modes are the same); the installation — w2c-events, as above (ACC-EJ-STAND-GROUP-01, the Architect's decision of 2026-10-28)
  torn:     the last fragment without LF — even a parsable JSON — is not a line: a skip and the count torn (the writer may be appending);
            a full line with LF not parsed by the form line (a JSON object: t — time, kind and id — strings; the depth — line depth) — a skip of this
            line and the count garbled, the bucket is read further, not a refusal of the bucket; a repeat of an id in the bucket — the first line wins,
            the following ones are dropped with the count duplicate (the journal is «at least once», the stage C guess EJ-L06, the Architect's decision of 2026-10-23) (vectors common/vectors/journal bucket.tsv;
            the stage C guess EJ-G03, the Architect's decision of 2026-10-23)
class:      [alarm, observation]             # closed; the class of a line is its field class: alarm — an alarm, no field —
                                             # observation; the index takes the class from the field, the tree does not override it;
                                             # the layout .alarms is at the writer: it puts an alarm into <tree>.alarms of any
                                             # tree, audit.alarms and console.alarms included (the term alarms_retention)
                                             # (the Architect's decision, the second pilot, N-2; changes the choice of the reconciliation M10/6–11 E18)
```

## The journal and the writers of the file

```yaml
journal:    the tree audit/<role>/e1/…: the lines of the platform about itself (unit.created|changed|deleted, door.issued, pass.called, schema.raised,
            events.removed, policy.changed, drain.*, server.*, worker.name_taken (alarm), door.keys_conflict (alarm; P/06.5 N3 «/where/<id>»; the Architect's decision of 2026-10-20, review of stage B 6–7), worker.name_back (observation; chapter P/03.2 N3 «rejoin»), worker.hung, clock.skew, free_ask.key_taken, …);
            fields: what the line is about — sub and target (the unit; not subsystem/unit), the address of the client in lines about a door — addr;
            these fields have no second name (ADR-0069)
door_journal: the door journal of a subsystem process (P/03.4 N1.7 journal) — lines of door kinds in audit/<role>/e1 by its own writer
            of the journal (writer below); the common fields: user (the name from the door token) or role (the role of the leaf), sub (the subsystem of the door),
            target, of, bytes (the bytes of the body served), status (the code of the answer), addr (the address of the client); the kinds and their fields beyond
            the common ones are named by the owner lesson of the door (archive.read — V/02) (ADR-0091 addendum (7) item 4, addendum (8) item 9); the same
            field role in lines of audit/domainconsole about a request with an accepted X-Operator: console (the forwarding contract
            x_operator) — role: "console"; without an accepted header there is no field; there is no new kind (C10-XOPERATOR-JOURNAL-01)
writer:     the console is a separate process; it writes the journal and the marks into the events root of its server (the same as
            that of the resource of this server), the resource indexes them as its own buckets; a file has one writer, except the journal:
            into audit/<role>/e1 all processes of this role on the server write (the path does not carry the instance, the unit of the journal is the role);
            a line is appended whole under an exclusive lock of the file (flock(2) LOCK_EX, as the presence lock; review of stage B 6–7, № 35), the lines of different processes do not interleave,
            the id tells them apart (the instance is in it); the bucket is the same by t at all writers (journal of cammeta-go, lesson 8 № 5)
```

## The event id and the writer instance

`hexUTF8` is the lowercase hex pairs of the UTF-8 bytes without a prefix, separators and normalization.
The tree and the unit are non-empty components of the bucket path (for the journal audit/role, for the marks
console/instance). The epoch is a canonical decimal integer ≥0, the number is ≥1, without leading zeros.
The number is allocated atomically by a common counter of the instance for each new published line,
the outcome of a suppression included; it is not reused at a change of the unit, the tree, the epoch or the bucket.
The outcome of a suppression gets a new id, not the id of the first line of the window. A mirror/a repeated output
keeps the id of the source line. When the counter is exhausted, new lines are not published until a new
unique instance; wrapping the counter is forbidden.
The writer instance is a non-empty string unique with regard to boxes and restarts (`INSTANCE_ID`, `BOX_ID` — [the environment file contract «Environment variables»](env-file.md); the grammar and the computation — [the instance contract](instance.md)); a local PID
is not enough, a repeat of a former INSTANCE_ID by a new process is outside the profile. The instance is one
path component: not `.`/`..`, without `/`, `\`, `|`, `"`, a comma, Cc/Zl/Zp. This condition
of the profile applies both to INSTANCE_ID from the environment and to the computed value; it is checked
before the start/the first publication together with the file representability («File names in shared trees» below). A violation is a refusal
of the start with a diagnostic of the instance name, without truncation/normalization. The hex components
do not contain the separator `-`, so different admissible tuples do not glue into one id.
The fields of the platform
in a line/an answer are not overwritten by arbitrary fields of the subsystem. JSON numbers are finite.
`of` of a platform line without an addressee unit is an empty string; for a line of the subsystem
the addressee is determined by the manifest.

## File names in shared trees

**File names in shared trees** — one encoding for all implementations: objects and event trees (P/05 N1.1, N1.2,
N1.4) are written by processes of different implementations on one box (the Architect's decision, the second pilot, N-3; it carries out the reconciliation of python and go
M10/3–5 item 14 and U20). Any logical key that the grammar of [P/01.1](../../01-store/spec/01.1-store.norms.md), the grammars of the id ([P/06.1](../../06-console/spec/06.1-console.norms.md) N1.3) and of the slot ([P/03.2](../../03-worker/spec/03.2-worker.norms.md) N1.4) and the limit
of the full key permit is representable on disk. The layout of directories is by the logical key, component by component (between `/`):

- a byte of a component from `[a-z0-9._-]` is written as is, any other UTF-8 byte — as `%` and two lowercase hex digits (`A` —
  `%41`, `:` — `%3a`, `%` — `%25`, `me` — `%d1%8f`); the component `.` — `%2e`, `..` — `%2e%2e`;
- the threshold is by the full name of the file or directory: if the encoded component, the norm suffix of a composite component (below:
  `.alarms`, `.lock`) and the reserve of the temporary name `TEMP_RESERVE` = 16 bytes together are longer than 255 bytes, the component is written
  as `%h<sha256 hex of the bytes of the source component>` (the sha256 hex of the bytes of the source component; the norm suffix — after it: `%h<sha256>.lock`), next to it the file
  `%h<sha256>.name` with the source component (UTF-8 bytes, without a line feed); the temporary name of the writer (temp + rename)
  is the final name, `~` and no more than 15 bytes (together with `~` no more than `TEMP_RESERVE`; ADR-0083 addendum (16)), so that neither
  the final nor the temporary name gets ENAMETOOLONG (review of stage B 3–5, № 20; ADR-0083 addendum (11));
- the file `.name`: the writer — there is no file — writes it (the content is given by the key); it exists and matches — leaves it; it exists and does not
  match — a refusal of the write without overwriting (damage, not a collision); the reader — `sha256` of the content of `.name` is equal to the name and
  the encoded source component passes the threshold «longer than 255» above — otherwise the record is skipped with a count, as
  unreadable; there is no `.name` — the same (vectors common/vectors/journal names.tsv; the stage C guess EJ-G04, the Architect's decision of
  2026-10-23);
- decoding is the inverse; truncation and normalization of a key are forbidden, different keys — different paths, there is no file profile narrower
  than the grammar;
- a service name contains `~` (ADR-0083 addendum (16)): the encoding does not write the byte `~` raw (`%7e`), so a service name does not
  coincide with a key. The directory lock of the objects root (P/05 N1.1 `disk`) is the file `<dir>/~lock` in the directory of
  the object being written, `flock(LOCK_EX)` for the time of the write; the file is not deleted. The temporary name — the item above. A walk
  of a tree skips names with `~`; another non-canonical name — by the former norm;
- encoded are the components taken from names and keys: `<sub>`, the tree, `<unit>`, the role, the instance, `<server>`, the segments of the key
  of an object; the components whose form the norm itself sets are written as is — the bucket name `<YYYYMMDDTHHMMSSZ>.events.jsonl`,
  `e<epoch>`, the suffix `.alarms`, the directories `.workers`, `.mirror`, `.gone`, the endings `.lock`, `.name`, the service `~lock` and the tail of the temporary name with `~` (`T` and `Z` of the
  bucket name — not `%54`, `%5a`); a composite component is the encoded name plus the norm suffix: `testsub.alarms`,
  `<instance>.lock` (journal of cammeta-go, lesson 8 № 10; the Architect's decision). The step — sc. 08 steps 12–16 of the [acceptance of P/05](../../05-resource/acceptance/README.md): a bucket that
  the runner writes past the writer under the name of the norm is read by the resource.

## Bucket write time

A bucket's own `written` is its logical wall-clock write stamp in seconds of common.time, recorded on a successful append of its bytes by the writer. It is not the start/end of its ten-minute window, a line's optional `occurred`, nor filesystem `mtime`. It is retained with the bucket across restarts and reindexing; reads, cache eviction and touching a file do not refresh it. The implementation chooses the local persistence representation of this metadata, not a new event field or public HTTP field. Before writer code, the owner of P/05 publishes that local persistence/read contract and library API in the implementation repository; all event writers and the resource use it. The stand observes the persisted stamp and retention after append, restart and restore, not the private bytes; this requires no new common module. An unreadable stamp is unknown: retain keeps that bucket and reports the read failure rather than inferring a stamp from the path or `mtime`.

For `.mirror/<server>/…`, the copy's own `written` is its receiver's publication time from P/05-R034, unchanged on an identical repeat. Restore carries that copy's `written` to the restored local bucket; receipt of restore and reindexing do not give it a newer stamp. This is distinct from the source version stamp of a copied object body, which is preserved by `X-Written` (ADR-0127, review of P/05 C4).

## Retention of a tree

The defaults of the retention of trees are from P/02.4 N1.9 (the forms of the rows `retention`, `alarms_retention`) and P/05 N3 «resource pass»
`retain` without a change of behaviour: the retention rows are written by the installer and the operator, the resource removes by term (layout audit A-23, the Architect's decision of 2026-10-25).
The forms of the rows are `Platform/02-installer/data/retention.schema.json` (the outcomes — `Platform/02-installer/data/retention.outcomes.tsv`), `Platform/02-installer/data/alarms-retention.schema.json` (the outcomes — `Platform/02-installer/data/alarms-retention.outcomes.tsv`) and
their `.outcomes.tsv`; what the resource does at a wrong or unknown term — P/05 N3 `retain`.

```yaml
retention:   the term of a tree in days when there is no retention row: <sub> — the row <sub>/retention, default 365; <sub>.alarms — the row
             <sub>/alarms_retention, default 1095; audit — 1095; console — 1095, not earlier than the longest tree; the row
             exists, but days is not a finite number > 0 or was not read — «not known», the default is not substituted (ADR-0076)
```

## Writing a line

From P/05 N3 «write an event (the platform, by observe of the subsystem)» (review of stage B 3–5, V1): the side of the owner of the
file contract — the steps that each writer of a line executes (the worker by `observe` — chapter
[P/03.6](../../03-worker/spec/03.6-worker.norms.md) N1.2, the console — chapter [P/06.4](../../06-console/spec/06.4-console.norms.md)
N1.2, the journal `audit` — the process of the role); the refusals of the writer — «Refusals of the writer» below (moved from P/05 N4; layout audit B-29, the Architect's decision of 2026-10-25).

```
1. a line deeper than JSON_DEPTH (line depth) — a refusal, nothing is written (EJ-DEPTH-BASELINE33); class ∈ {alarm, observation}; the field class among the fields of the subsystem — a refusal (the class is written by the writer: alarm — by the field class of the line,
   observation — without the field; review of stage B 6–7, № 35); occurred not a number — a refusal; v — a refusal
2. of: from about of the manifest — <about.sub>/<the value of the field about.field of the unit row>; for a manifest without about and at an empty value of the field
   (or no field) — the unit itself, <sub>/<id> (C02-ABOUT-EMPTY-01); a line of the subsystem with its own of → the refusal «of is the platform's to write»;
   the trees console and audit — their own of
3. suppression (events.suppress.<kind>) — only at the writer of the events of the subsystem (the worker by observe, chapter P/03.6 N1.2);
   the journal of the console (the tree console) and audit are not suppressed: each line is written (the Architect's decision, review
   of stage B 6–7, № 34)
4. the bucket by t: <root>/<tree>/<unit>/e<epoch>/<start>Z.events.jsonl; a new directory — the directory barrier
5. append the line; an alarm/the journal — fsync of the line and of the directories up to the root; the file does not end with LF (a tail of a former writer
   without LF) — first LF, then the line, no extra bytes: the tail becomes a full line — a full parsable JSON —
   an ordinary line with its own id, a damaged one — garbled (EJ-G03); there is no truncation; therefore the journal is «at least once»:
   an event written before a failure without LF can stand next to its repeat, the reader takes the first by id (the stage C guess EJ-L06, the Architect's decision of 2026-10-23); an I/O error — without an automatic repeat, an error to the caller (the stage C guess EJ-L02/L03/L04, the Architect's decision of 2026-10-23)
```

**Refusals of the writer.** The line is not published, no HTTP is assigned (the write is a call, not a door):

| Reason | Outcome | Body / write | What the caller does |
|---|---|---|---|
| a wrong class, its own class/of, occurred not a finite number, v (step 1) | a refusal of the write | a diagnostic, no HTTP is assigned | fix the source; the line is not published |
| a line deeper than JSON_DEPTH (line depth) | a refusal of the write | nothing is written | fix the source (EJ-DEPTH-BASELINE33) |
| t later than the year 9999 (bucket years) | a refusal of the write before an id is allocated | — | fix the time (EJ-G06) |
| a directory or bucket with other permissions or group (bucket modes) | the append is refused before the write | a line of the log and a count | the installation (P/02.4) (EJ-G11) |
| an I/O error (step 5) | an error to the caller, without an automatic repeat | — | the caller decides (EJ-L02/L03/L04) |

**Races.** One writer per bucket (P/05 N1.1; the journal — under the lock of the file, `writer` above): appending does not compete; two processes of one `of` (a move, an epoch) write into different paths — the path carries the epoch — and do not mix; the rotation of a bucket by `t` is closing the old one and opening a new one in one writer.

## Implementation decides

1. **A diagnostic line without a kind named by the norm** (C-JOURNAL-DIAG-KIND-01, the Architect's decision of 2026-10-29). Where a norm
   prescribes «journal» or «journal without the value» and does not name the kind, the implementation chooses the kind and the fields of the line: the form `line` above
   (the family events of P/05 by tree), the tree `audit/<role>` of its writer; `kind` is a string by the form `line` that coincides with none of
   the kinds named by the norms; there are no values of secrets («without the value» — without the value, the name of the field is admissible). The acceptance does not judge such
   lines; the contract introduces no new words.

## Production obligations

ADR-0130 Addendum (10), Q6: each writer MUST publish nondecreasing event stamps `t` across appends and restart, using its retained last published watermark and the current owner clock rule. Bucket selection uses that stamp; `occurred` keeps its existing meaning. Persist the watermark by an implementation-chosen local representation, without a new public field. All local deadlines use monotonic clocks. An uncertain forward or backward wall-clock jump MUST NOT justify early destructive pruning of buckets, keys, request marks or replay memory: defer pruning until eligibility is proved under the qualified clock environment. A forward stamp alone is not proof of elapsed retention. Deferred pruning remains subject to finite resource/admission budgets and visible existing refusal/backpressure, never unsafe deletion. Qualification supplies clock bounds; none are invented here.

## Vectors

The package [`journal`](../vectors/journal/README.md): `bucket.tsv` (reading a bucket, a torn tail, unreadable lines), `names.tsv` (file names), `years.tsv` (the choice of a bucket), `append.tsv` (appending a line, the section «Writing a line» step 5; EJ-L03), `modes.tsv` (the modes of the events root, of the trees and of the buckets). (ADR-0083 addendum (32) item 2)

[Common finite budgets and acceptance limits](production-obligations.md) are required for the applicable phases of this contract.
