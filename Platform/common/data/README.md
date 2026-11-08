# Data catalogue

This English text is the source; the Russian translation `ru/data/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

[`catalog.tsv`](catalog.tsv) is the catalogue of the rows, objects and files of the module: the key, the kind, the owner, the operations, the readers, the condition,
the version, the family schema, the norm (ADR-0083). [`codec.tsv`](codec.tsv) is the codec of the store rows; [`common.schema.json`](common.schema.json)
is the common definitions of the family schemas, for reference. The reading layers of the families — [LAYERS.md](../LAYERS.md) § 6, § 7.

## Schema-column sentinels and owner forms

The `schema` column either names the family's JSON Schema file or contains `-` or `manifest`. The two sentinels are outside common `family-read`; invoking that schema-based family check for either sentinel is a concrete `MissingBinding`, not `ok`. No serialized `MissingBinding` output form is assigned here. An open or empty schema is not a substitute.

`-` says that no schema file is supplied in `data/`. It does not mean that any bytes are valid: the key template, kind, owner, readers and the rest of the catalogue row remain mandatory, and its `norm` identifies the governing value or file format. `manifest` means that the owner rule depends on the subsystem manifest; it does not invariably mean that the manifest describes the value. The following table is the owner-rule list for these entries (Architect decision 2026-11-08, ADR-0088 R2, R3, C16).

| Catalogue family (`schema`) | Governing value or file form | Public owner |
|---|---|---|
| `/etc/w2c/secrets/platform.key`, `/etc/w2c/tls/ca.pem`, `/etc/w2c/tls/ca.next.pem`, `/etc/w2c/tls/revoked`, `/etc/w2c/tls/crl.pem`, `/etc/w2c/tls/<role>/server.pem`, `/etc/w2c/tls/<role>/server.key`, `/etc/w2c/roles/<role>.env`, `<domain recovery file>`, `<events or objects root>/<path>/%h<sha256>.name`, `<objects root>/<dir>/~lock` (`-`) | The file format in that catalogue row's norm. These files do not become an unconstrained byte family. | ADR-0088 R2; [P/02.4](../../02-installer/spec/02.4-installer.norms.md) N1.2, N1.5, N1.6, N1.9, N3; [secret files](../contracts/secret-files.md), [environment file](../contracts/env-file.md), [event journal](../contracts/event-journal.md) “File names in shared trees”; [P/05](../../05-resource/spec/05-resource.norms.md) N1.1 |
| `<sub>/blobs/sha256-<hex>` (`-`) | Bytes; the name is their sha256. | [P/06.1](../../06-console/spec/06.1-console.norms.md) N1.5 |
| `/etc/w2c/configstore-rights.json` (`-`) | `RightsFile`. | [P/01.2](../../01-store/spec/01.2-store.norms.md) N1.2, N2 |
| `<sub>/idem/<key>` (`-`) | The implementation chooses the form; only the console reads it. There is no cross-implementation value judgment. | [P/06.1](../../06-console/spec/06.1-console.norms.md) N1.1 |
| `<sub>/<manifest:domain.witness.report>/<name>` (`-`) | The `domain.witness` declaration and P/10 N1.8. | [P/10](../../10-domain-console/spec/10-domain-console.norms.md) ownership paragraph, N1.8; [P/02.1](../../02-installer/spec/02.1-installer.norms.md) N1.2b |
| `<sub>/<manifest:unit.rows>/<id>` (`manifest`) | `unit.fields` and the row check contract. | [Row check](../contracts/row-check.md); [P/06.1](../../06-console/spec/06.1-console.norms.md) N1.2 |
| `<sub>/<manifest:tables>/<name>` (`manifest`) | `tables.<t>.fields`. | [P/06.1](../../06-console/spec/06.1-console.norms.md) N1.6; [P/02.1](../../02-installer/spec/02.1-installer.norms.md) N1.2a |
| `<sub>/<manifest:domain.books.from>`, `<sub>/<manifest:domain.books.from>/<slot>` (`manifest`) | The domain envelopes contract's `entry` through `domain.books`. | [P/03.7](../../03-worker/spec/03.7-worker.norms.md) N1.2; [domain envelopes](../contracts/domain-envelopes.md) “Contribution” |
| `domain/<sub>/<manifest:domain.kept>`, `domain/<sub>/<manifest:domain.kept>/*` (`manifest`) | For tables named in `domain.tables`, P/06.1 N1.6; for the others, the subsystem owns the form. | [P/03.7](../../03-worker/spec/03.7-worker.norms.md) N1.6 `kept`; [P/06.1](../../06-console/spec/06.1-console.norms.md) N1.6 |
| `objects/<sub>/<manifest:objects.rows>`, `objects/<sub>/<manifest:objects.rows>/*` (`manifest`) | The manifest supplies only the family name (`strList`); the subsystem owns the body. | [P/02.1](../../02-installer/spec/02.1-installer.norms.md) `objects.rows`; [P/05](../../05-resource/spec/05-resource.norms.md) N1.1 |

For the rows whose form belongs to the subsystem, the platform checks the key, owner and readers, not the value. The table does not manufacture a platform value schema or an implementation-specific decoder. The governing rule must be available in the norm or form without vectors or scenarios as its sole definition (ADR-0133 addendum (1)); named normative examples may illustrate it, but the judge corpus is not the definition.

## Key by the template (V7-FAMILY-KEY-PLACEHOLDER-01)

[`key-placeholders.tsv`](key-placeholders.tsv) is the canonical typed input for readers and generators; the first table below presents the same grammars and examples. The human translation dictionary in `ru/placeholders.tsv` is not a generation input. `<host>` and `<server>`, and `<object-key>` and `<key>`, retain their distinct grammars.

The column `key` of the catalogue is the key template: literals and placeholders `<…>` (and `*` — any key under the prefix). The key
of an instance belongs to a family if it matches the template whole: the literals — exactly, a placeholder — by a full match of
the grammar of the first table below on the substring of the key that it occupies (the portable expression `^(?:…)$`, [LAYERS.md](../LAYERS.md)
§ 3 «Expression»; `/` — only if the grammar takes it). For a placeholder whose norm does not give its own grammar —
a non-empty component `[^/]+`, for a root — an absolute path, for a path and an object key — non-empty components (the choice of the generator,
accepted by the Architect). Where a placeholder means different things in different families (`<name>`, `<id>`), the key is judged by the union, while
the writer writes by the norm of its own family (the second table). The constraints that the portable expression does not hold
(reserved words, `free-…`, the length in bytes) are not judged by the key — they are held by the norm of the writer.

`<manifest:X>` is the value of the key `X` of the manifest of the subsystem `<sub>`; the key is judged by the grammar of the value, the manifest is not
read. A key not by the template — a refusal on the empty path `""`, the value is not judged ([LAYERS.md](../LAYERS.md) § 6). The example is
the substitution by which the vectors [`family-read`](../vectors/family-read/README.md) build the column `key` of the rows with a key by
the template.

| Placeholder | Grammar | Example | Norm |
|---|---|---|---|
| `<sub>` | `^(?:[a-z][a-z0-9_-]{0,31})$` | `testsub` | the subsystem name P/02.1 N1.2 (reserved words and `free-…` are not judged by the key) |
| `<id>` | `^(?:[^/.][^/]*\|\.[^/.][^/]*\|\.\.[^/]+)$` | `t1` | the unit id P/06.1 N1.3 (numeric and named) and the participant id P/01.3 N1.3: a non-empty component, not `.` and not `..` |
| `<name>` | `^(?:[^/.][^/]*\|\.[^/.][^/]*\|\.\.[^/]+)$` | `w-1` | by families — the table below; the key — the union: a non-empty component, not `.` and not `..` |
| `<worker>` | `^(?:[a-z]{1,8}-[a-z0-9]+(?:-[a-z0-9]+)*)$` | `w-1` | the slot name P/03.2 N1.4; P/04 N1.3a |
| `<slot>` | `^(?:[a-z]{1,8}-[a-z0-9]+(?:-[a-z0-9]+)*)$` | `w-1` | the slot name P/03.2 N1.4; P/03.7 N1.2 |
| `<box>` | `^(?:[^/:.][^/:]*\|\.[^/:.][^/:]*\|\.\.[^/:]+)$` | `box-a` | the instance contract `box` |
| `<place>` | `^(?:[^/.][^/]*\|\.[^/.][^/]*\|\.\.[^/]+)$` | `sh7` | P/03.2 N1.3; P/06.1 N1.6 |
| `<host>` | `^(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*)$` | `srv-a` | the host name RFC 1123 P/06.6 N2.1 and `SERVER_NAME` (its subset) |
| `<server>` | `^(?:[a-z0-9]+(?:-[a-z0-9]+)*)$` | `srv-a` | `SERVER_NAME` — the environment file contract; P/05 N1.4 |
| `<volume>` | `^(?:[A-Za-z0-9_]{1,64})$` | `events` | P/05 N1.4 free_ask |
| `<rid>` | `^(?:[^/.][^/]*\|\.[^/.][^/]*\|\.\.[^/]+)$` | `r-0123456789abcdef` | the contract of a request and its mark `rid` (`free-…` is not judged by the key) |
| `<sha16(name)>` | `^(?:[0-9a-f]{16})$` | `0123456789abcdef` | P/06.4 N1.5 |
| `<key>` | `^(?:[^/]+)$` | `k1` | P/06.1 N1.1, N3 «create» |
| `<i>` | `^(?:0\|[1-9][0-9]*)$` | `0` | the step number of an operation from zero: P/06.9 N1.2 |
| `<root>` | `^(?:[^/.][^/]*\|\.[^/.][^/]*\|\.\.[^/]+)$` | `testsub.c1` | the target root of an operation: P/06.9 N1.3 |
| `<hex>` | `^(?:[0-9a-f]{64})$` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | P/06.1 N1.5 |
| `<manifest:unit.rows>` | `^(?:[a-z][a-z0-9_-]{0,31})$` | `counters` | P/02.1 `unit.rows`; P/06.1 N1.1 |
| `<manifest:tables>` | `^(?:[a-z][a-z0-9_-]{0,31})$` | `shelves` | P/02.1 N1.2a `tableName` |
| `<manifest:domain.books>` | `^(?:[a-z0-9][a-z0-9_-]*)$` | `notes` | P/02.1 `domain.books` |
| `<book>` | `^(?:[a-z0-9][a-z0-9_-]*)$` | `notes` | P/08.5 N1.7 |
| `<manifest:domain.books.from>` | `^(?:[a-z][a-z0-9_-]{0,31})$` | `notes` | `from` without `<sub>/` and the final `/`: P/02.1 `domain.books`; P/03.7 N1.2 |
| `<manifest:domain.kept>` | `^(?:[^/]+)$` | `ledger` | P/02.1 `domain.kept`; P/03.7 N1.6 |
| `<manifest:objects.rows>` | `^(?:[^/]+(?:/[^/]+)*)$` | `marks` | P/02.1 relation 84; P/05 N1.1 |
| `<manifest:domain.witness.report>` | `^(?:[^/]+)$` | `witness` | P/10 N1.8 |
| `*` | `^(?:[^/]+(?:/[^/]+)*)$` | `x` | any key under the prefix: non-empty components |
| `<member>` | `^(?:[a-z0-9-]{1,64})$` | `m1` | P/08.1 N1.1 |
| `<kind>` | `^(?:[a-z][a-z0-9_-]{0,31})$` | `stream` | the key `domain.tokens`: P/08.2 N1.6a |
| `<sha16>` | `^(?:[0-9a-f]{16})$` | `0123456789abcdef` | the first 16 characters of the hex sha256 of the UTF-8 value: P/08.2 N1.6a |
| `<relay>` | `^(?:[a-z0-9-]{1,64})$` | `m1` | the member name: P/08.3 N1.2 |
| `<part>` | `^(?:0[0-9]{3}\|[1-3][0-9]{3}\|40[0-8][0-9]\|409[0-5])$` | `0123` | the first 12 bits of the SHA-256 of the member name: P/08.3 N1.1 |
| `<table>` | `^(?:[a-z][a-z0-9_-]{0,31})$` | `shelves` | the key `domain.view_tables`: P/02.1, P/04 N1.3b |
| `<cluster>` | `^(?:[a-z0-9-]{1,64})$` | `m1` | the member name: P/08.4 N1.3 |
| `<rev>` | `^(?:[1-9][0-9]*)$` | `7` | P/08.3 N1.3; P/08.8 N1.5; P/08.9 N1.2 |
| `<ref>` | `^(?:[^/]+)$` | `t1` | the value of `domain.ref`: P/08.1 N1.2 |
| `<events root>` | `^(?:(?:/[^/]+)+)$` | `/data/platform/events` | the environment file contract; the event journal contract |
| `<events or objects root>` | `^(?:(?:/[^/]+)+)$` | `/data/platform/objects` | P/05 N1.1 |
| `<objects root>` | `^(?:(?:/[^/]+)+)$` | `/data/platform/objects` | P/05 N1.1 |
| `<domain recovery file>` | `^(?:(?:/[^/]+)+)$` | `/root/domain-recovery` | P/02.4 N3 «domain installation»; P/08.2 N1.1 |
| `<unit>` | `^(?:[^/]+)$` | `t1` | the event journal contract; P/05 N1.2 |
| `<epoch>` | `^(?:0\|[1-9][0-9]*)$` | `3` | the event journal contract |
| `<YYYYMMDDTHHMMSSZ>` | `^(?:[0-9]{8}T[0-9]{6}Z)$` | `20261023T000000Z` | the event journal contract |
| `<role>` | `^(?:[a-z][a-z0-9_-]{0,63})$` | `console` | P/01.2 N1.1 |
| `<instance>` | `^(?:[^/]+)$` | `box-a%3a4242%3a0a1b2c` | the instance contract; the event journal contract |
| `<tree>` | `^(?:[^/]+)$` | `testsub` | the event journal contract; P/05 N1.6 |
| `<object-key>` | `^(?:[^/]+(?:/[^/]+)*)$` | `testsub/blobs/sha256-e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | P/05 N1.1 «Tombstones» |
| `<path>` | `^(?:[^/]+(?:/[^/]+)*)$` | `testsub/marks` | P/05 N1.1 |
| `<dir>` | `^(?:[^/]+(?:/[^/]+)*)$` | `testsub/marks` | P/05 N1.1 |
| `<sha256>` | `^(?:[0-9a-f]{64})$` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | the event journal contract «File names in shared trees»; P/02.3 N1.5 |
| `<n>` | `^(?:0\|[1-9][0-9]*)$` | `0` | P/02.3 N1.5 |

The values of the placeholders by families and the grammar of the norm of the writer:

| Placeholder | Where (templates) | What | Grammar of the norm | Components | Norm |
|---|---|---|---|---|---|
| `<sub>` | `platform/manifest/<sub>…`, `<sub>/…`, `objects/<sub>/…`, `domain/<sub>/…`, `domain/{placement,placed,names}/<sub>/…`, `<events root>/<sub>…`, `.workers/<sub>/…` | the subsystem name — the `name` of the manifest | `[a-z][a-z0-9_-]{0,31}`, not one of the 23 reserved words, not `free-[\s\S]*` (`common.sub_name`) | 1 | P/02.1 N1.2 |
| `<sha256>`, `<n>` | `platform/manifest/<sub>/files/<sha256>/<n>` | the digest of the file bytes; the part number from 0 | 64 lowercase hex; a decimal integer without leading zeros | 1 each | P/02.3 N1.5 |
| `<id>` | `<sub>/placement/<id>`, `<sub>/<manifest:unit.rows>/<id>`, `<sub>/state/<name>/<id>`, `<sub>/epoch/<id>` | the unit id | by the `unit.id` of the manifest: numeric — `[1-9][0-9]*`; named — the id grammar of N1.3 (`common.named_id`); without a manifest — the union of both | 1 | P/06.1 N1.3 |
| `<id>` | `platform/configstore-doors/<id>` | the id of a participant of the store group (`-id`, outside a group — `SERVER_NAME`) | a non-empty component | 1 | P/01.3 N1.3 |
| `<name>`, `<worker>`, `<slot>` | `<sub>/slots/<name>`, `<sub>/heartbeats/<name>`, `<sub>/workers/<name>`, `<sub>/snapshot/<worker>`, `<sub>/<manifest:domain.books.from>/<slot>` | the slot (worker) name: `<prefix>-<suffix>` | `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*`; `<worker>` — not `unplaced` | 1 | P/03.2 N1.4; the slot name contract; P/04 N1.3a |
| `<name>` | `<sub>/state/<name>/<id>` | the name of a unit state (`unit.state`) | `[a-z][a-z0-9_-]{0,31}` | 1 | P/02.1 `unit.state`; P/03.6 N1.7 |
| `<name>` | `<sub>/contenders/<name>/<box>` | the sought slot name or `-` without a name | the slot name grammar or `-` | 1 | P/03.2 N1.4a |
| `<box>` | `<sub>/contenders/<name>/<box>` | the box of the instance | a non-empty component without `:` | 1 | the instance contract `box` |
| `<name>` | `<sub>/<manifest:tables>/<name>` | the name of a table row | a non-empty component, not `.`, not `..` | 1 | P/06.1 N1.6, N3 «table — write a row» |
| `<place>` | `<sub>/holds/<place>` | the row name of the table of places | a non-empty component, not `.`, not `..` | 1 | P/03.2 N1.3; P/06.1 N1.6 |
| `<name>` | `domain/users/<name>`, `domain/deleting/<name>` | the person name | the person name grammar (`common.person_name`), not `break-glass` | 1 | P/08.4 N1.1; the person name contract |
| `<name>` | `<sub>/<manifest:domain.witness.report>/<name>` | the name of a witness report | a non-empty component | 1 | P/10 N1.8 |
| `<host>` | `platform/servers/<host>`, `platform/decommission/<host>`, `<sub>/decommissioned/<host>`, `<sub>/decommission-pending/<host>` | the server name at the console door (a copy — at the decommission) | a host name RFC 1123: labels `[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?` separated by `.`, no longer than 253 bytes | 1 | P/06.6 N2.1; P/04 N1.1 |
| `<host>`, `<server>` | `platform/doors/<host>`, `platform/resources/<server>/heartbeat`, `<sub>/want/<host>`, `<sub>/requests/free-<server>-<volume>`, `<events root>/.mirror/<server>/…` | its own server — `SERVER_NAME` | `[a-z0-9]+(-[a-z0-9]+)*` | 1 | the environment file contract `SERVER_NAME`; P/04; P/05 N1.4, N1.6 |
| `<volume>` | `<sub>/requests/free-<server>-<volume>` | the volume of the resource | `[A-Za-z0-9_]{1,64}` | part of 1 | P/05 N1.4 free_ask |
| `<rid>` | `<sub>/requests/<rid>` | the request id | a non-empty component, not `.`, not `..`, not `free-[\s\S]*` | 1 | the contract of a request and its mark `rid`; P/06.4 N1.5 |
| `<sha16(name)>` | `<sub>/asked/<sha16(name)>` | the first 16 characters of the sha256 of the person name | `[0-9a-f]{16}` | 1 | P/06.4 N1.5 |
| `<key>` | `<sub>/idem/<key>`, `domain/idem/<key>` | the digest of the submission key `(user, method, path, Idempotency-Key)` | `[0-9a-f]{64}` | 1 | P/06.1 N1.1, N3 «repeat memory»; P/08.0 N1.9 |
| `<id>` | `platform/folders/<id>`, `<sub>/operations/<id>`, `<sub>/opsteps/<id>/<i>`, `<sub>/opdone/<id>/<i>`, `<sub>/opcount/<id>` | the folder id, the operation id | 128 random bits: `[0-9a-f]{32}` | 1 | P/06.8 N1.1; P/06.9 N1.2 |
| `<sub>`, `<manifest:unit.rows>`, `<id>` | `platform/memberof/<sub>/<manifest:unit.rows>/<id>` | a member unit: a reference from the composition of a folder | as for `<sub>/<manifest:unit.rows>/<id>` | 3 | P/06.8 N1.1 |
| `<i>` | `<sub>/opsteps/<id>/<i>`, `<sub>/opdone/<id>/<i>` | the step number of an operation from zero | `0\|[1-9][0-9]*` | 1 | P/06.9 N1.2 |
| `<root>` | `<sub>/opbusy/<root>` | the target root: the subsystem names it | a non-empty component, not `.`, not `..`, no more than 200 bytes of UTF-8 | 1 | P/06.9 N1.3 |
| `<hex>` | `<sub>/blobs/sha256-<hex>` | the digest of the bytes | `[0-9a-f]{64}` | part of 1 | P/06.1 N1.5 |
| `<manifest:unit.rows>` | `<sub>/<manifest:unit.rows>/<id>` | the name of the unit table | `[a-z][a-z0-9_-]{0,31}`, not one of the forbidden table names and not `cluster`, `worker`, `ts` | 1 | P/02.1 `unit.rows`; P/06.1 N1.1 |
| `<manifest:tables>` | `<sub>/<manifest:tables>/<name>` | the table name | `[a-z][a-z0-9_-]{0,31}`, not one of the forbidden table names | 1 | P/02.1 N1.2a `tableName` |
| `<manifest:domain.books>`, `<book>` | `domain/<sub>/<manifest:domain.books>…`, `domain/names/<sub>/<book>` | the name of a domain book | `[a-z0-9][a-z0-9_-]*` | 1 | P/02.1 `domain.books`; P/08.5 N1.7 |
| `<manifest:domain.books.from>` | `<sub>/<manifest:domain.books.from>…` | the source row of a book: the value of `from` without the first segment `<sub>/` and the final `/` | `[a-z][a-z0-9_-]{0,31}` | 1 | P/02.1 `domain.books`; P/03.7 N1.2 |
| `<manifest:domain.kept>` | `domain/<sub>/<manifest:domain.kept>…` | an element of `kept` without the final `/` | a non-empty component | 1 | P/02.1 `domain.kept`; P/03.7 N1.6 |
| `<manifest:objects.rows>` | `objects/<sub>/<manifest:objects.rows>…` | an object family: an element of `objects.rows` without the final `/*` | non-empty components; the first is not `heartbeats`, `contenders`, `snapshot`, `controller`, `blobs`, `commands` | 1 or more | P/02.1 relation 84; P/05 N1.1 |
| `<manifest:domain.witness.report>` | `<sub>/<manifest:domain.witness.report>/<name>` | the family of witness reports | a non-empty component | 1 | P/10 N1.8 |
| `<member>`, `<cluster>` | `domain/members/<member>/…`, `domain/<sub>/<manifest:domain.books>/<member>`, `domain/{pending,outcomes,keepers,alarm-history}/<member>`, `domain/{grants,break-glass}/<cluster>` | a domain member — the `CLUSTER` of its installation | `[a-z0-9-]{1,64}` (`common.domain_member`) | 1 | P/08.1 N1.1; P/08.4 N1.3 |
| `<rev>` | `domain/members/<member>/reports/<rev>…`, `domain/backups/rev-<rev>`, `domain/shared-docs/rev-<rev>` | the number of a generation or an edit | `[1-9][0-9]*`, not more than 9007199254740991 | part of 1 | P/08.3 N1.3; P/08.8 N1.5; P/08.9 N1.2 |
| `<ref>` | `domain/{placement,placed}/<sub>/<ref>` | the value of the field `domain.ref` of the unit row | a non-empty component | 1 | P/08.1 N1.2 |
| `<events root>` | `<events root>/…` | the root of the event journal (`EVENTS`, by default `<PLATFORM_DIR>/events`) | non-empty components, with a leading `/` | several | the environment file contract; the event journal contract |
| `<unit>` | `<events root>/<sub>…/<unit>/…`, `<events root>/.mirror/<server>/<tree>/<unit>/…` | the unit of a bucket: the unit id in the tree of a subsystem, a role or an instance in the trees `audit`, `console` | a non-empty component | 1 | the event journal contract; P/05 N1.2 |
| `<epoch>` | `…/e<epoch>/…` | the epoch of the holder | `0\|[1-9][0-9]*` | part of 1 | the event journal contract |
| `<YYYYMMDDTHHMMSSZ>` | `…/<YYYYMMDDTHHMMSSZ>.events.jsonl` | the start of a bucket, UTC | `[0-9]{8}T[0-9]{6}Z`, the year `0001`–`9999` | part of 1 | the event journal contract |
| `<role>` | `<events root>/audit{,.alarms}/<role>/…`, `/etc/w2c/tls/<role>/…`, `/etc/w2c/roles/<role>.env` | the role of a process | `[a-z][a-z0-9_-]{0,63}` | 1 | P/01.2 N1.1 |
| `<instance>` | `<events root>/console{,.alarms}/<instance>/…`, `<events root>/.workers/<sub>/<instance>.lock` | the instance of a writer `<box>:<pid>:<6 hex>` | a non-empty component (on disk `:` — `%3a`) | 1 | the instance contract; the event journal contract |
| `<tree>` | `<events root>/.mirror/<server>/<tree>/…` | the tree of the source: `<sub>`, `console` or `audit`, with `.alarms` for alarms | a non-empty component | 1 | the event journal contract; P/05 N1.6 |
| `<object-key>` | `.gone/<object-key>` | the key of a removed object | non-empty components, without `.`, `..`, `\` and control characters | several | P/05 N1.1 «Tombstones» |
| `<domain recovery file>` | `<domain recovery file>` | the path of the domain recovery file | non-empty components, with a leading `/` | several | P/02.4 N3 «domain installation»; P/08.2 N1.1 |
| `<events or objects root>`, `<objects root>` | `<events or objects root>/<path>/%h<sha256>.name`, `<objects root>/<dir>/~lock` | the root of the event journal or of the objects | non-empty components, with a leading `/` | several | P/05 N1.1; the event journal contract «File names in shared trees» |
| `<path>`, `<dir>` | the same | the path of a directory under the root | non-empty components | several | P/05 N1.1 |
| `<sha256>` | `…/%h<sha256>.name` | the sha256 of the full name of a component | `[0-9a-f]{64}` | part of 1 | the event journal contract «File names in shared trees» |
