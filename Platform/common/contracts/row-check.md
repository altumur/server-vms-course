# The row check contract: the form of a unit row and the common check

This English text is the source; the Russian translation `ru/contracts/row-check.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Platform» (ADR-0083 addendum (5), addendum (13): a common algorithm of several processes
is a contract, not copies in chapters; the stage C guess W03-E07, the Architect's decision of 2026-10-23). The owner is
chapter [P/06.1](../../06-console/spec/06.1-console.norms.md) of the console (N1.2 «Unit row», N1.3 «Identifier», N3
«Common row check»). Participants: the units and tables door of the console (P/06.1 N3 «create», «edit», «table — write a
row») and the customer's library of the worker ([P/03.6](../../03-worker/spec/03.6-worker.norms.md) N1.6, N3 «order»;
ADR-0091 item 1) — one check over one form of the row. Moved from P/06.1 N1.2, N1.3 (named, tombstone, unique,
canonical_url, ref_and_must_match), N3 «Common row check» and steps 4–7 of «create», 2, 4–5 of «edit» without a change of
behaviour; what the door does around the check (the claim, the number, the write, HTTP codes, `made_prefix`, `made_key`,
secrets) — P/06.1 and [P/06.2](../../06-console/spec/06.2-console.norms.md), what the library does — P/03.6.

Normative keywords follow the [course canon](../NORMATIVE-TERMS.md). «N1.2», «N1.3», «N3», «N4» in the moved text
are addresses of chapters of P/06.1 unless said otherwise; «step N» of «create»/«edit» is a step of the door procedure of
P/06.1 N3, their checks are the section «Order of checks» below.

## Form

The unit row follows the catalogue manifest (`unit.fields`; the form of the manifest is `Platform/02-installer/spec/02.1-installer.schema.json`,
[form](../../02-installer/spec/02.1-installer.schema.json)) and the section «Unit row» below. The unit state row
`<sub>/state/<name>/<id>` (section «Unit state») — the form `Platform/03-worker/data/state.schema.json`, the outcomes
`Platform/03-worker/data/state.outcomes.tsv` ([form](../../03-worker/data/state.schema.json),
[outcomes](../../03-worker/data/state.outcomes.tsv); C149-STATE-SUPPORT-01, the Architect's decision of 2026-10-26).

## Unit row

```yaml
<sub>/<rows>/<id>:
  id:        <id as a string>                      # MUST
  revision:  <a decimal integer ≥ 1>               # MUST; 1 at creation, +1 on each edit, a deletion does not change it
  born:      <32 lowercase hex digits>             # the life of the row (ADR-0091 item 3): set by the creator — the door (N3 «create» step 8)
                                                   # or the customer's library (P/03.6 N1.6) — with a new random value at
                                                   # each creation, over a tombstone too; an edit, a deletion mark and
                                                   # resealing keep it; absent or empty born is unreadable, not a life value
  made:      <canonical JSON {by, at, keep, gone?}>  # only in a customer's row (P/03.6 N1.6; ADR-0091 item 1): by — the customer subsystem;
                                                   # at — the time of the event, keep — the time until which nobody deletes the row
                                                   # physically (time — Platform/common/data/codec.tsv row time, P/01.1 N0; JSON numbers) — set only by
                                                   # the customer's library; gone — the time the door deleted the row, set by the door
                                                   # by its own clock (N3 «delete»)
  deleted:   "true"                                # only in a tombstone; otherwise there is no element
  <field>:    <a value by its type>                 # each field of the manifest except the absent ones (below)
values_by_type:
  string, url: as is
  int:        decimal notation
  float:      decimal notation without an exponent: of the notations that read in binary64 as this number — the one with the fewest
              significant digits; of those — the one closest to the exact value of the number; of two equally close ones — the one with an even
              last digit; -0 → 0 (the selection rule — ADR-0091 item 1; the notation — the same: 5e-7 → 0.0000005, 1e21 →
              1000000000000000000000)
  bool:       "true" | "false"
  list:       elements separated by commas; if there is an empty element, an element contains a comma or the text begins with `[` — a JSON array;
              [] is stored as ""; [""] — as the JSON text '[""]'. On reading "" → [], a leading '[' → a JSON array,
              otherwise split by commas; a field not given at an edit is kept in this form;
              a field of placement labels (`placement.constraint: labels-subset`) — only words by the [label alphabet](../labels.md) (1–64 ASCII: first a letter or a digit, then a letter, a digit, `_`, `.`, `:`, `-`)
  json:       canonical JSON (ADR-0072); the value null — there is no element
  blob:       "sha256-<hex>"; the bytes — the object <sub>/blobs/sha256-<hex> (N1.5); the digest gets into the row
              only through the bytes door PUT /{rows}/{id}/{blob_field} (N2 «Doors of bodies and tables»):
              an edit of fields accepts only the former digest of the row or "" (to remove); at creation — only ""
  *_secret:   the envelope enc:v2:… (the sealing contract); the client never gets the value: in the answer — the mask "***" (chapter 6.2 N1.1)
absent:
  - a field with inherit, if not set: there is no element (not "" and not "null")
  - a json field with the value null
platform_fields:   [id, revision, deleted, worker, placement, epoch, phase, observed_revision, born, made, index]   # unit rows
table_platform_fields: [by, at, made_at, held_by, garbled, revision, index]   # table rows — their own list (P/02.1 tables.<name>.fields «not from»;
  # P/06.1 N3 «table — write a row» step 1): a table field declared with a name from platform_fields of the unit (worker,
  # epoch, …) is an ordinary field; an unknown one is a refusal, as before (the stage C guess C06-ROWCHECK-TABLE-FIELDS-707-01, the
  # Architect's decision of 2026-10-25)
  # index — the store index of the row (P/01.1 index) in the answer of the door (P/06.1 N2 «Versions»), not stored in the row; revision of a table row — P/06.1 N1.6 (ADR-0094 B4)
  # unit.fields does not declare them (a load refusal of P/02.1), the client does not set them; a live row has only id, revision, born and
  # made (in a customer's row), deleted — only in a tombstone; born and made the door does not give the client to write: a body with them —
  # 400 «a client may not set …» (N3 step 4), an edit keeps them (ADR-0091 items 1, 3); made — in the answer (N2);
  # state is not an element of the row: the effective state of the unit — in the GET answer (N2; P/03.6 N1.7); worker/placement — the row <sub>/placement/<id> (P/04 N1.1, added by M10/4);
  # epoch — the epoch row; phase, observed_revision — status[].phase, status[].observed_revision
  # of the object <sub>/heartbeats/<name> (P/03.4 N1.1, added by M10/5)
```

The text forms of values by type are the vectors [`values-by-type`](../vectors/values-by-type/README.md) (review of stage A
6–7, № 33).

## The customer's row: `made`

Moved from [P/03.6](../../03-worker/spec/03.6-worker.norms.md) N1.6 (`made`, `ORDER_HORIZON`, `not_after`, `tombstone`,
`deletes`) without a change of behaviour: the rule is read by the customer's library (P/03.6), the controller (P/04 N3 step 8)
and the units door of the console (P/06.1 N3 «delete») (layout audit A-11, the Architect's decision of 2026-10-25).

```yaml
made:        {by: C, at, keep} («Unit row» made above): at — the time of the event, at a renewal — max(former at, t_E); keep does not decrease:
             max(former keep, at + ORDER_HORIZON + 120); gone is set by the door at the deletion (P/06.1 N3 «delete»)
ORDER_HORIZON: 600                           # s; a constant of the platform, not a manifest declaration: an event older by the clock
                                             # of the customer (now − t_E > ORDER_HORIZON) is not executed; a lower freshness threshold is
                                             # the customer's logic, the platform does not know it (ADR-0091 item 1, the owner's decision of 2026-10-22)
not_after:   each write of an order carries the store condition not_after = t_E + ORDER_HORIZON + 60 (P/01.1 N1, N3 «Admission time»):
             the write applies only if its admission time is not later; otherwise 409 expired — the outcome expired, it is not
             repeated by the same write. An accepted write of a repeat stands in the journal before the deletion of the row and fails on
             CAS, a later one — expired: not_after of the repeat = t_E + 660 ≤ keep − 60 = not_before of the deleted life (P/04 N3 step 8)
tombstone:   over a tombstone of a row of its own made — only for an event later than made.gone + 60: a creation with cas of the version
             of the tombstone and the same fixed («Identifier and field constraints» tombstone below), revision of the tombstone + 1, a new born; an event within a minute after
             the deletion counts as the former one — a repeat of the former event does not revive what the operator deleted (a deliberate narrowing)
delete:      a row with made is deleted (by the worker of the addressee by worker.deletes — P/03.6 N1.6, by the controller — P/04 N3 step 8) only when the clock
             of the deleter is strictly later than made.keep, with the store condition not_before = max(0, made.keep − 60) (P/01.1 N1: time ≥ 0; C04-KEEP-01): 409 early — not deleted, a repeat by a new write on
             the next pass
```

## Unit state

Moved from [P/03.6](../../03-worker/spec/03.6-worker.norms.md) N1.7 (`acts`, `unreadable`) without a change of behaviour:
the rule «the state is in effect» is read by the holder of the unit (P/03.6), the controller (P/04 N1.3 `retire_when`, N1.3a `state`) and the console
(P/06.1 N2 «State in the answer») (layout audit A-05, the Architect's decision of 2026-10-25). The form of the state row is `Platform/03-worker/data/state.schema.json`, the outcomes are `Platform/03-worker/data/state.outcomes.tsv`
(P/03.6 N1.7; C149-STATE-SUPPORT-01, the Architect's decision of 2026-10-26).

```yaml
acts:        a state is in effect when the unit row is live (not a tombstone), its born and revision equal the born and revision
             of the state, and value reads by the schema; the epoch is not compared at reading — the outcome survives a move: the new holder
             reads the effective state, and the subsystem does not execute a finished task again; for the cursor (unit.state.cursor)
             only born is compared — revision is not compared: an edit of the row does not reset the cursor (P/03.6 N1.7 cursor;
             C170-STATE-CURSOR-01, the Architect's decision of 2026-10-27)
unreadable:  a row not by the form of the family or a value not by the schema — not in effect, as if absent; a reader that assembles
             many rows counts it (P/04 N1.2 snapshot_state_garbled; P/01.1 N0 «Stability of output»)
```

## Preparation of fields

At creation the composition of client fields is determined for each field of the manifest (before the row is written):

1. The field is given — take exactly the given value, including `0`, `false`, `[]` and `null` (except `null` of a field with
   `inherit` — step 2); a default does not replace it. The admissibility of the value is checked by the sections «Order of checks» and «Refusals».
2. The field is not given or is given as `null` and has `inherit` — do not create an element; the value of `inherit` is the end
   of the read chain, not a value to write into the new row.
3. The field is not given and has `default` — take the value of `default` from the loaded manifest; for a field `string` with
   `unit.id: numeric` each `{id}` in it is replaced by the decimal notation of the id issued to this creation (N3 «create»
   step 3), once: an edit does not recompute the value (P/02.1 N1.3; VMS request № 1, the Architect's decision of 2026-10-23).
4. Otherwise take the empty form of the type from the table below. `default` and `inherit` together are forbidden by P/02.1.

| Type | Empty JSON value | Row element (section «Unit row») |
|---|---|---|
| string, url, blob | `""` | `""` |
| int, float | `0` | `"0"` |
| bool | `false` | `"false"` |
| list | `[]` | `""` |
| json | `null` | absent |

The checks of type and constraints apply to the obtained values in the order of the section «Order of checks»; a default
does not bypass `fixed`, `enum`, references and the other constraints. A required field that was not given still gives the
refusal P4: preparing the empty form or the default does not count as the client giving it.
After the check `json: null` is not stored. A secret is stored by the ring boundary (below) and given out as the mask `"***"` (chapter 6.2 N1.1), and a blob at creation
is empty: default/inherit for blob are forbidden by P/02.1. At an edit the fields not given are kept from the row,
defaults are not applied again. A creation over a tombstone applies the same rules of preparation;
the fixed check compares the prepared value with the tombstone.

**Table row** (P/06.1 N2 «Doors of bodies and tables» `TableRow`, N3 «table — write a row» — by reference; the stage C guess
C06-ROWCHECK-TABLE-33-01, the Architect's decision of 2026-10-23). Preparation — steps 1 and 3 above; step 4 does not apply to tables:
a field not given in `POST` and without `default` is absent in the row — the empty form of the type is not added. `POST` of a table is a full
replacement of the row by the manifest, not an edit: a field of the former row with the same name that the client did not give is not
carried over to the new row, except secrets and stamps — they are kept by their own rules: a top-level secret that is empty, `null` or not
given — the former one,
a change of `bound_to` without a new secret — 400 «must be given anew» (chapter 6.2 N3 step 3); the stamps `by`, `at`, `made_at` are set by
the console, `made_at` of a row with the same name — the former one (P/06.1 N3 «table — write a row» step 2), a stamp in the body — 400
`unknown field` (ibid., step 1).

**Ring boundary** (P/06.2 N1.2 `no_key`, N4 — by reference; the stage C guess C06-ROWCHECK-DEV-01, the Architect's decision of
2026-10-23). The check gets the state of the ring from the caller (an option of the library API; it does not need to read P/06.2):

| Ring | Secret in the prepared row |
|---|---|
| `SECRETS_KEY` not set (development mode, P/06.2 `no_key.unset`) | an edit (`PUT`) with a non-empty `*_secret` — the value is written in the clear, as is; a creation (`POST`) of a unit with a non-empty `*_secret` at any depth — 400 before the claim (ibid.). A table row — the same rule (one for the units and tables doors, P/06.2 N3 «create/edit» step 3): there is no row with this name — `POST` of the table is a creation, a non-empty `*_secret` at any depth — 400 before the write; the row exists — `POST` over it is an edit, a non-empty secret is written in the clear; an empty, `null` or not given top-level secret — the former value (the stage C guess C06-ROWCHECK-TABLE-RING-33-01, the Architect's decision of 2026-10-23) |
| set and opens | the envelope `enc:v2` by the [sealing contract](sealing.md) |
| set, but does not read or does not open (including `SECRETS_KEY=""`, P/06.2 `no_key.unreadable`) | 503 `unavailable` before the row check (before P1), nothing is written |

A list has only string elements; another JSON element is a refusal of the field type (section «Refusals»).
An `int` value at the input of the door is a JSON number without a fraction part and an exponent within ±(2^53 − 1): `1.0`, `1e2` and
`9007199254740992` for `int` are `not_number` (such a number is read by a JSON client of any language). The number `-0` is stored as `0`
(JCS, ADR-0072).
The value of a json field is any JSON value; its `schema` is JSON Schema 2020-12 by the definition `jsonSchemaLite` of
`Platform/02-installer/spec/02.1-installer.schema.json` ([manifest form](../../02-installer/spec/02.1-installer.schema.json); the list of keywords and the depth are there; layout audit, B-06; review of stage A 6–7,
№ 11); a schema with another keyword is a load refusal `refused:value` (P/02.1), so all implementations check the same thing.
An empty element is admissible in an ordinary list, but not in placement labels by the [label alphabet](labels.md).

## Identifier and field constraints

```yaml
id:
  named:                                    # unit.id: <field>
    rule:    the value of a non-secret field of type string, including the default of the type; a source with the suffix _secret is forbidden by the loader of P/02.1; one line; MUST be non-empty
    update:  the source field of the id is immutable even without fixed in the manifest; PUT may omit it or give the same id;
             another value — 400 «<field> is fixed» without a write; this door does not rename
    refused: empty; "." and ".."; contains `/`, `\`, `|`, `"`, `,`; control characters (Cc), line and
             paragraph separators (Zl, Zp); digits outside 0–9 (Nd not ASCII); categories — by the Unicode 15.0.0 tables (UnicodeData), as the NFKC of
             chapter 6.2; a character not assigned in this version belongs to none of them (added by review of stage A 2)
  tombstone:                                # the return of a name after deletion
    rule:    a creation over a tombstone passes only with the same values of the fixed fields; revision = that of the tombstone + 1,
             by a write with cas by the version of the tombstone; otherwise 400 with the name of the field
  unique:    true | canonical            # a preliminary check of the new value over live units;
                                         # an empty ("") and an absent value do not take part: two live units with
                                         # an empty unique field are not a conflict (the stage C guess RC-17, the
                                         # Architect's decision of 2026-10-23)
                                         # canonical — a URL in the canonical spelling (below); a conflict — 409 unique;
                                         # there is no atomic uniqueness between rows (N3 «Races» of an edit)
  canonical_url:                         # the syntactic canon of RFC 3986 §6.2.2 (ADR-0057)
    - the scheme and the host — in lower case; the hexadecimal digits of percent-encoding — in upper case
    - a percent-encoded unreserved character (a letter, a digit, - . _ ~) is decoded
    - the dot segments of the path are removed (RFC 3986 §5.2.4); an empty port («host:») is removed
    - the default port is not removed, the query is not sorted, an empty path is not replaced with «/»: «the same stream» is a meaning
      of the subsystem, not of the platform (ADR-0057)
ref_and_must_match:                      # a field of a unit or a table (P/02.1 N1.3)
  ref:        <subsystem>/<family>       # the target of the value v is the row <ref>/<v>
  must_match: {<target field>: <field of this row>}   # with a live target the values are equal; otherwise 409 conflict, fault must_match;
                                                  # an absent element of the target is equal to nothing, and "" too
  rules:
    - there is no target — not a refusal: ref without must_match does not require the target to exist (ADR-0057)
    - the target does not read — 409 conflict, fault garbled
    - both ways (as with tables, N3 «table — write a row», step 2): a creation or an edit of a unit that
      is itself a target checks the live units and the table rows of the catalogue whose field with ref to its family and must_match names it:
      their values equal the new values of the target, otherwise 409 conflict, fault must_match; a referring row does not read — fault garbled
```

## The url value

A field `type: url` is read thus: not by RFC 3986 (`%zz`, control characters, `\`), no scheme or host (the place of the host and the values of
«no host» — `schemes.<s>.host`/`none` of the [address contract](url-credentials.md) «Schemes»; with `host: path` there is no path — there is no place of the host: `mirror://local`),
with credentials (`@` in the authority; a password or a login in the address by the rule of the field — [address contract](url-credentials.md)),
with `#` (except a scheme with `fragment: none`), a scheme not from `schemes`, a non-numeric port — refusal `bad_url` (the address contract «Schemes»).

## Order of checks

A check is a function of the prepared fields, the table manifest, the catalogue of manifests and the rows read. Within each
check the fields go in the order of declaration of `unit.fields`; the first refusal is that of the first field by the manifest.

```
creation (the prepared fields of the row; at the library — the fields F of the order, the id and born/made it sets itself, P/03.6 N1.6):
P1. body fields: a platform field → an unknown field. Platform fields are platform_fields for a unit row, table_platform_fields
    for a table row; of the platform fields the refusal names the first in the order of its own list;
    unknown fields — all their names in ascending order of UTF-8 bytes in one «unknown field(s) …» (RC-10)
P2. preparation (section «Preparation of fields»), keeping the information on what the client gave; then the checks of values:
    blob (not a digest; at creation not "") → json (not_json, too_long 4000 bytes of the canonical text — there is no other
    limit, nesting included: RC-13; schema) → enum →
    value types (not_number) → schema of a field of any type except json — over the parsed value (C06-SCHEMA-ANY-TYPE-01) → weight: a present value of the field placement.weight.field ≥ 1 (P/04 N1.3; after
    the default is filled) → url (section «The url value») → group → labels ([label alphabet](../labels.md))
    group: there is no refusal — there is no value, it is empty or the host does not read — the unit is not in a group; bad_url of the source — the
    url step with the name of the field; the row check does not compute the group (explanation — P/04 N1.3 group_by; RC-12)
P3. named: the source field of the id is given or obtained non-empty from the default → by the section «Identifier and field constraints»; an empty or
    not given id P3 skips: the refusal comes from P4 («needs a <field>»), and for a field that is not required — bad id «is empty» after P4;
    a creation over a tombstone: other fixed → «<field> is fixed» (tombstone)
P4. required: each required field is given by the client and is not ""
P5. references in order: direct ref / must_match of the row itself → reverse must_match (the rows that refer to it) →
    unique over live rows; within each — the order of unit.fields (RC-11). Reverse must_match, the first refusal: the referring
    subsystems in ascending order of name bytes; within a subsystem — unit rows, then tables in ascending order of name bytes;
    within them — the order of the manifest fields; rows — in ascending order of key bytes (RC-15). The target of ref/must_match is the key
    of the checked row itself: the target is the row itself in its new prepared state, both sides are compared by the new values
    (a consistent edit of the pair passes, an inconsistent one — must_match); the same at creation (RC-16)

edit (only the given fields, without filling defaults):
R1. P1 and the checks of values of P2 over the given fields, except the blob subcase «not the former digest of the row» — it is in R2
R2. by the row read: a fixed field changes or the given source field of a named id is not equal to the id → «<field> is
    fixed»; a blob field: the value is not the former digest of the row and not ""
R3. references by the new values, in the order of P5
```

The order of refusals of P1, P2 «group», P5 and R3 — the stage C guesses RC-10–RC-12, RC-15, RC-16, the Architect's decision of 2026-10-23.

**Batch** ([P/06.1](../../06-console/spec/06.1-console.norms.md) N3 «batch»; ADR-0094 B9, refinement (b)). The row check of the batch door reads references by the state after
the batch: a target and a referring row written by the same batch are in the new prepared state; a row removed by it is as absent, a tombstone is as a tombstone; a row outside
the batch is as usual. `unique` of P5 is counted the same way: two rows of the batch with one value — a refusal. The order and the words of refusals are the same; the first refused row is by the order of `writes`. The library has no batch.

The value of a list field in `fixed` (P3 tombstone, R2) and in the comparisons of references is compared by the JSON value — a list of strings,
order and repeats kept — not by the text of the row element: `["a", ""]` and `'["a",""]'` are one value; `unique` on a
list is forbidden by the loader (P/02.1, corpus `c3_unique_list`) (the stage C guess RC-14, the Architect's decision of 2026-10-23).

The reads of the check are the targets of `ref` and `must_match` of the row itself and the rows of the catalogue whose field with `ref` to this table and `must_match`
name it (section «Identifier and field constraints» `ref_and_must_match`); a deletion does not check references. A `blob` field at creation is empty.

The checks `ref`/`must_match`/`unique` of a creation and an edit run before the write and are not atomic
with the change of other rows. Two edits of different units, both of which checked the former values,
can successfully write the same unique value. Likewise the result of a link check
can become stale because of an edit or a deletion of the linked row. The subsequent pass of the placement
controller does not check these constraints; there is no guarantee of automatic detection, of writing a
diagnostic or of a correction of such a divergence. The check at the next POST/PUT
runs by the same rules and does not serve as a background audit. `ref` by itself does not introduce
the requirement that the target exists (ADR-0057): the refusal conditions remain the conditions of the corresponding field. The same at the library.

## Refusals

The words of a refusal are `error` (a word of the closed list of the door, [P/06.1](../../06-console/spec/06.1-console.norms.md) N2 «Refusal: `error` and `field`»; the test does not compare the text of `detail`) and `fault` from the closed vocabulary
[`../../vectors/fault/`](../vectors/fault/README.md). At the door — the code and the body by P/06.1 N4 «Units door» (the column «Door»); at the
library — the outcome of the order `refused` and the count `creates.refused` of the heartbeat (P/03.6 N1.6, P/03.4 N1.1).

| Reason | Step | Word | Door |
|---|---|---|---|
| a platform field is set | P1, R1 | `error: platform_field` (for a table row `unknown field`), `detail` «a client may not set …» | 400 |
| an unknown field | P1, R1 | `error: unknown field`, `detail` «unknown field(s) …» | 400 |
| `blob` is not a digest; at creation not `""`; at an edit not the former digest and not `""` | P2, R2 | `error: blob` | 400 |
| a json field is larger than 4000 bytes of the canonical text / not by the schema | P2 | `error: too_long`, `fault: too_long` / `error: type` | 400 |
| `enum` is not from the list | P2 | `error: enum` | 400 |
| the value of a field that is not `json` is not by the `schema` of the field | P2 | `error: type`, `detail` with the name of the field | 400 |
| the value is not by the type of the field: not a number for `int`/`float`, not a boolean, not a list of strings, not a string | P2 | for numbers `error: not_number`, `fault: not_number`; otherwise `error: type`; `detail` with the name of the field | 400 |
| an integer value of the field placement.weight.field < 1 | P2 | `{detail, error: type}`, without fault; `detail` «\<field> must be at least 1» | 400 |
| `url` does not read, with credentials, with `#`, a scheme not from `schemes` | P2 | `error: bad_url`, `fault: bad_url`; `detail` without the value, with the names of the fields `credentials` ([address contract](url-credentials.md) A15) | 400 |
| the labels are not by the label alphabet | P2 | `error: labels` | 400 |
| the id is not by the section «Identifier and field constraints» | P3 | `error: bad_id`, `detail` with the name and the reason | 400 |
| a `fixed` field changes (an edit or a return over a tombstone); the source field of the id changes | P3, R2 | `error: fixed`, `detail` «\<field> is fixed …» | 400 |
| a `required` field is not set or is `""` | P4 | `error: required`, `detail` `a <sub> unit needs a <field>` | 400 |
| `unique`/`ref`/`must_match` are violated; a referenced row does not read | P5, R3 | `error: conflict`, `fault: unique \| must_match \| garbled` | 409 |

## Vectors

The packages [`row-check`](../vectors/row-check/README.md) (the common row check), [`values-by-type`](../vectors/values-by-type/README.md) (the forms of values), [`fault`](../vectors/fault/README.md) (the words of refusals); the address — the package [`secret-in`](../vectors/secret-in/README.md) of the address contract. (ADR-0083 addendum (32) item 2) The unit state — the table
`state.tsv` of the package `row-check` (`acts`, `unreadable`; STATE169-VECTORS-01, the Architect's decision of 2026-10-27).

The input of the single command `vectors` of the package `row-check`: `files` are the manifests with the keys `testsub.subsystem.yaml` and `testsub2.subsystem.yaml` (the bytes of these files of the export, loaded together: the catalogue of both; for `state.tsv` `testsub2.subsystem.yaml`, the schemas of `unit.state`). The cells of `cases.tsv` are `unit`, `op`, `body`, `stored`, `rows`: `unit` is `<subsystem>/<rows>` (the units table of a manifest) or `<subsystem>/<table>` (a table of a manifest); `op` is `create` or `edit`; `body` is the passed fields, a JSON object, numbers are lexemes as written; `stored` is the read row (`edit`) or the tombstone over which one creates (`create`), a JSON object in the form of a unit row (the elements are strings), empty — there is no row; `rows` is the other rows of the store that the check reads, a JSON object `{key: row}`, `"@garbled"` instead of a row — the row is not read by its form. The native outcome is code 0 and one JSON object: `{"result": "ok", "row": {…}}` (`row` is the prepared row `{element: text}`, no element — no key) or `{"result": "refused", "word": "<fault or class>", "field": "<field>"}` (no field — no key `field`). `word` is the `fault` from the dictionary of the package `fault`, if the refusal carries it, otherwise the class of the row «Refusals» of this contract: `platform_field`, `unknown_field`, `blob`, `enum`, `type`, `labels`, `bad_id`, `fixed`, `required`; `field` is the field that the refusal names; for `unknown_field` it is all unknown names in ascending byte order separated by commas, while a door names the smallest (P/06.1 N2; the Architect's decision of 2026-11-09).

The cells of `state.tsv` are `name`, `unit`, `state`: `name` is the name of the state, a JSON string from `unit.state` of the manifest; `unit` is the unit row as read, an object of elements (`born`, `revision`; `deleted: "true"` — a tombstone) or `"@absent"` — there is no row; `state` is the row `<sub>/state/<name>/<id>` as read, an object of elements (`born`, `revision`, `epoch`, `value` — JSON text) or `"@absent"`. The native outcome is code 0 and the object `{acts, unreadable}`, for an acting state also `value`, the parsed value.

The canonical JSON (RFC 8785, ADR-0072) that the contract relies on — the package [`jcs`](../vectors/jcs/README.md)
of the common JCS contract (`canonical_json.tsv`: input → the RFC 8785 form → sha256; ADR-0083 addendum (33) item 2).
