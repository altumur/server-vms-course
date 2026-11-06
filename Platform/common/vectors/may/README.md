# Vectors of the right by grants

This English text is the source; the Russian translation `ru/vectors/may/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The vectors of [the right contract](../../contracts/may.md): the function `may` — the right of a person by the grant lines (rank, scope,
the term of the line, the age of the copy, a disabled person, a break-glass session). The owner is lesson P/08, chapter 8.4; it is performed by the gate consoles
of a cluster ([P/06.3](../../../06-console/spec/06.3-console.norms.md) N1.3, chapter 6.7), by the consoles of the domain (lesson 10) and by the process
`domain` (8.4) (the Architect's decision of 2026-10-20, ADR-0083 addendum (14) item 1; the review analysis of stage A 8–10). The bytes are written by
«Specification» (ADR-0083); the conformance of the product is by its acceptance against this table (ADR-0080 addendum 16).

The rows were transferred from the inputs of the command `may` of the acceptance of M11/9 (`inputs/may-*.json`, sc. 07) without a change of values: the JSON
of the input is in one line, the order of keys and the lexemes of numbers are as in the file; `case` is the name of the input file. One exception is
`may-24-unit-id-not-grammar`: `"labels": []` was added to the unit of the input (the Architect's decision of 2026-10-20): a unit
`{sub, id}` without `labels` is itself an input not of the form (`unit` is `{sub, id, labels, about?}`), and `@exit 2` would not distinguish an id
of a scope `unit:` not by the grammar from a unit without labels. Sc. 07 of the acceptance of M11/9 and its inputs were removed by the move of lesson 8 (the Architect's
decision of 2026-10-20, ADR-0083 addendum (14) item 17): the table is the only source of these cases; the log is the acceptance of chapter 8.4 (`corrections-4.tsv` (historical correction record), a log, not in the export).

## Form of the input of the command `may`

The input is one JSON object (the column `input`); the function and its steps are [the right contract](../../contracts/may.md) «The function `may`».
The form was moved here from [P/08.4](../../../08-domain/spec/08.4-domain.norms.md) N5 `exit` together with the choices of the log
(the guesses of stage C MAY-G01/G02, the Architect's decision of 2026-10-23): a common algorithm is a common form.

```yaml
input:     a JSON object; eight fields are required: grants, as_of, disabled, user, glass, cap, unit, now; optional are sub, roles,
           unread, iat, anywhere, as_role (ADR-0097–ADR-0100, ADR-0105, ADR-0110; no field — null, for unread — []); fields beyond them are not read (not a refusal)
grants:    null | exactly {lines: [line…]}
line:      exactly {subject, cap, sub?, scope, until, by} — a trusted input (a copy already parsed by P/08.4 N1.3): a line not of the
           form is an input not of the form, code 2, not a skip
  subject: by the form of P/08.4 doc.lines[].subject — non-empty, 1–64 characters without whitespace (White_Space Unicode 15.0.0),
           control characters and : | ( ) " /, not break-glass; subject "" is an input not of the form, code 2 (the guess of stage C MAY-G03, the Architect's decision of 2026-10-23);
           or role: and a name of the same grammar, except admin (ADR-0098 §2, ADR-0100 §1)
  cap:     none | view | edit | admin; none — only at a role line (ADR-0099 §1)
  sub:     a manifest name [a-z][a-z0-9_-]{0,31} (P/02.1); platform passes the same grammar
  scope:   "*" | "unit:<sub>/<id>" | "labels:<label>[,<label>…]" | "folder:<id>"; at a role line labels: is not of the form (ADR-0099 §1);
           the <id> of a folder is 32 lowercase hex digits (P/06.8 N1.1); <sub> is a manifest name [a-z][a-z0-9_-]{0,31} (P/02.1),
           <id> is by the row check contract «Identifier and field constraints» named (`unit:testsub/a,b` — 2),
           a label is by the labels alphabet contract
  until:   a time — 0 or a non-negative JSON number; read tolerantly, as a time in a row (P/01.1 N0 «Time in a row»),
           without rounding by the reader (rounding to thousandths is the row writer's, P/08.4 N1.3 until); the value is finite in
           binary64, as now and as_of: it does not fit — an input not of the form, code 2, before parsing glass (MAY-UNTIL-D8-01, the Architect's decision of 2026-10-25)
  by:      a string
as_of:     null | a finite JSON number
disabled:  [string…]
user:      a string without lone surrogates; "" is of the form (step 8: deny no_grant, code 0)
glass:     true | false
cap:       view | edit | admin
unit:      null | "*" | "any" | exactly {sub, id, labels, about?, chains?}: sub, id — strings (the id of the door unit is not checked by the grammar:
           `"a,b"` — code 0), labels — [string…]; about — exactly {sub, id, labels, chains?} of the same form or "unknown"
chains:    [[string…]…] | "unknown"; no field — the same as "unknown"
now:       a finite JSON number
sub:       a string by the grammar of a manifest name | null
roles:     null | "unreadable" | {<name>: [exactly {role, until, at}…]}: role — a string; until and at — a time, as the until of a line
unread:    "all" | [exactly {role, sub?}…]: role and sub — strings
iat:       a finite JSON number | null
repeats:   repeats in disabled, labels, lines and in the labels of a scope labels: are not a form error
order:     the whole form is checked before steps 1–2 (glass, disabled): an input not of the form — code 2 even at glass: true
exit:      0 — computed (the output is the right contract output); 2 — an input not of the form (P/08.4 N5 exit)
```

Examples of code 2 (P/08.4 N5): `until` as a string, a line without `by`, `lines` not a list, an unknown `cap`, `labels` as a string, a surrogate
in `user`, `as_of` as a string, no `now`, `glass` not `true | false`, `disabled` not a list, `about` not an object and not `"unknown"`, an extra field
of a line of `lines`, of `unit` or of `about`; `sub` not by the grammar; `chains` not a list; `roles` not a table; `none` at a direct line; `labels:` and `role:admin` at a role line; the `cap` of the input `none`.

## `covers`

Whether one grant scope covers the door unit ([the gate contract](../../contracts/gate-and-pass.md) `scope`; step 7 of the function
`may` — by the scope; C06-EVENTS-QUERY-UNKNOWN-138-10, the Architect's decision of 2026-10-26). The file [`covers.tsv`](covers.tsv), the same
file rules as `cases.tsv`.

```yaml
input:   {scope, ref, row}
  scope: "*" | "unit:<sub>/<id>" | "labels:<label>[,<label>…]" | "folder:<id>" — the grammar of a grant line (above); otherwise — code 2
  ref:   exactly {sub, id} — the unit named in the path or ?unit=; a folder as the object of a write — {sub: platform, id: <folder id>}
  row:   exactly {labels: [<label>…], about?: {sub, id, labels, chains?}, chains?} — the unit row as read (labels — the field
         declared in unit.fields; none — []); chains — as at the input of may; "@unreadable" — the row is unreadable or the read is not confirmed
output:  true | false (stdout JSON); code 2 — an input not of the form
rule:    "*" — true; unit:<s>/<i> = ref — true by the name, not reading the row; otherwise unit:<s>/<i> — true when row is readable and
         row.about = (s, i); labels:L — true when row is readable and all labels of L are at about if about exists, otherwise at row;
         folder:<id> — true when row is readable, the chains are known and id is in a chain of row or of row.about;
         row "@unreadable" and chains "unknown" — a grant by labels, on an about-unit and folder: do not cover (not 503);
         ref.sub = platform — unit: and labels: do not cover
```

19 rows. Tiers 1–4 and the choice of the first non-empty one are judged by the role group, not by one scope, so they are in [`cases.tsv`](cases.tsv) (may-62…may-92), not here. The first 9: `unit:` by the name at an unreadable row — `true`; `labels:` and a grant on an about-unit at an unreadable one — `false`; `*` at
an unreadable one — `true`; at a readable one — the labels at the row itself, the labels at about, a grant on an about-unit — `true`, `unit:` of a foreign
unit without about — `false`; a scope not by the grammar — `@exit 2`. Another 10 — `folder:`: at a unit, at about, at a subfolder, at a folder as an object, over a dead chain, at an unknown membership.

## Run

Without a stand: the function of an implementation gets the input (the column `input`) and gives the output; `expect` is a subset of the fields of the output (`{"result":"unavailable"}` — the third outcome, the door answers 503) or
`@exit 2` (an input not of the form of [P/08.4](../../../08-domain/spec/08.4-domain.norms.md) N5 `exit`: the lines of `grants` are a trusted input, a line not of the form — 2, not a skip). The time is
by the input `now`, not by the process clock. Who performs: `cases.tsv` — the gate consoles of a cluster (`06-console`) and of the domain
(`10-domain-console`) and the process `domain` (`08-domain`); `covers.tsv` — only `06-console` and `10-domain-console` (the record `vectors` `common/may` or the former command
`covers` of the common acceptance README; one is enough — ACC-VECTORS-COVERS-STAND-01) (ACC-VECTORS-CONNECT-02, the Architect's decision of 2026-10-26).

## Units

`c1` `testsub` with the labels `east`, `ground`; `c2` without labels; `t1` `testsub2` with the label `west` and `about` — `c1`. Folders — ids of 32 hex digits: `0f…`, `0b…` are root ones, `0a…` is a root one with the subfolder `0c…`. `now` is
1760000000; the age of the copy is `GRANT_LIFETIME` ([P/08.4](../../../08-domain/spec/08.4-domain.norms.md) N1.3).

## Files

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first non-skipped one is the header; `note` is the scenario and the step
of the acceptance.

| File | Input → expectation |
|---|---|
| [`cases.tsv`](cases.tsv), 126 rows: 52 `allow`, 44 `deny`, 7 `unavailable`, 23 `@exit 2` (may-26 — `until` does not fit in binary64, MAY-UNTIL-D8-01; may-27…may-106 — ADR-0097–ADR-0100, there is no dry run by an implementation) | `input` is the input of the command `may` as JSON text → `expect`: `{"result":"allow"}` (a break-glass session without grants, a copy of exactly one day of age, a holder line without `as_of`, `view` without a unit — any line, `*`, `unit:` its own and through `about`, `labels:` all labels, the labels of `about`, a higher rank, the term of the line ahead) or `{"result":"deny","reason":<word>}`: `disabled` (disabled at a grant), `stale` (a copy older than one day), `no_grant` (no line, `edit` without a unit not by `*`, a foreign unit, one label missing, the labels of the unit itself at `about`, a lower rank, an expired line, `"*"` not by `*`, a line of another subject, a unit without labels); `@exit 2` — a scope `unit:` with an id not by the grammar of [P/06.1](../../../06-console/spec/06.1-console.norms.md) N1.3; `subject` "" of a grant line (`may-25`, MAY-G03) |

The vectors were checked by an oracle against the text of the contract (steps 1–8) and the form of the input of [P/08.4](../../../08-domain/spec/08.4-domain.norms.md) N1.3, N5 `exit`, not against the code of implementations; on a
divergence the contract is right, the vector is corrected by «Specification».

## Vector wire

The wire of `cases.tsv`, `covers.tsv` is set by the `common/may` rows of [the single form](../wire.tsv); [grammar](../wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.
