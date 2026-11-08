# Native input forms for may and covers

This English text is the source; the Russian translation `ru/contracts/may-input.md` is derived from it (ADR-0121).

These are the existing payload forms of the common functions [may](may.md#the-function-may) and [covers](gate-and-pass.md). They define function input and native exit meanings, not a new product route, profile field or command. Case values and expected answers remain judge-owned.

## may

The input is one JSON object. The function steps and output are defined by the [right contract](may.md#the-function-may); the trusted grant line and row Time remain those of their existing owners. The whole input form is checked before the function steps.

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
  until:   a time — 0 or a non-negative JSON number by the current P/01.1 N0 Time reader, with the writer's same three-digit fraction bound;
           without rounding or truncation by the reader; its value is finite in
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

## covers

Whether one grant scope covers the door unit follows the [gate contract](gate-and-pass.md) `scope` and step 7 of may.

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
