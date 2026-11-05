# Vectors of issuing a worker token

This English text is the source; the Russian translation `ru/vectors/issue/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The vectors of the function `issue` of [chapter P/08.7](../../spec/08.7-domain.norms.md): the issuing of a token by the holder without a store, a network and
a stand — the input is the kind declaration, the role and the requesting member, the request body, the placements, the topology, the units of the members, the shared
document and `now`; the output is the token claims without `jti` or a refusal `{status, reason}` (Н1.1 `computed`, Н1.3 `body`, Н1.4,
Н3 «issue» steps 2–7; Н5 «`issue`»). Steps 0–1 (a displaced process, the agent signature) the input does not carry. The owner is lesson P/08,
chapter 8.7; the function is performed by the process `domain` at the door `POST /api/tokens/<member>/<sub>/<kind>`. The bytes are written by «Спецификация»
(ADR-0083); the conformance of the product is by its acceptance against this table (ADR-0080 addendum 16).

The rows were transferred from the steps of the acceptance of М11/07
(sc. 03, 30 steps; the command `issue` on `inputs/issue-*.json`) at the move of lesson 8 (the plan of the move of lesson 8, § 3 and V1;
the decision of «Архитектор» 2026-10-20, ADR-0083 addendum (14)). `case` is the name of the input file, `note` is the scenario and the step of the acceptance of М11/07.
The input is the JSON of the file in one line: only insignificant whitespace outside strings is removed; the order of keys, the lexemes of numbers and the values are as
in the file. The expectation is a subset of the acceptance step as it is (after `ok `). The scenario М11/07 sc. 03 and its inputs were removed by the move
of lesson 8 (the directory М11/07 is removed; the log is the acceptance of chapter P/08.7 (`journal/corrections-7.tsv`, a log, not in the export)): the table is the only
source of these cases.

## Run

Without a stand: the command `issue` of an implementation gets the input (the column `input`) and prints JSON; `expect` is a subset of the fields
of the output by the dictionary of the «Stand» ([the common acceptance README](../../../common/acceptance/README.md), `<code> <JSON>`: the named fields
exist and are equal, an array — by length, order and elements, a number — by value) or `@exit 2` (an input not of the form of Н5, including
a `decl` not of the loading form of [P/02.1 Н1.2б](../../../02-installer/spec/02.1-installer.norms.md)). There are three `@exit 2` rows
(`issue-37`, `issue-38`, `issue-keep-too-long`); the other 37 inputs are of the form. `iat`, `exp` are from the `now` of the input, not from the process clock.

## Inputs

The input is Н5 of the chapter: `decl` is the kind declaration (`null` — there is no kind), `role` is the role that the agent certified, `member` is
the requesting member, `body` is the body `{request_id, ref, by?}`, `members`, `holder`, `placements` (`"garbled"` — the record is unreadable,
a record without `copies` is unreadable too), `topology` (`centre?`, `star`, `via`), `units` are the owners of units by ref, `shared` is
the shared document, `now` is 1760000000. The domain is `acme`; the members are `hold`, `m1`, `m2`, `relay`. The kind declarations in the inputs are the kinds
`tally`, `probe` of the manifest `testsub` and `feed`, `tally2` of the manifest `testsub2` from the specification data
([`testsub`](../../../../Source/tests/testdata/testsub.subsystem.yaml),
[`testsub2`](../../../../Source/tests/testdata/testsub2.subsystem.yaml)) — the inputs carry them whole and do not depend on the bytes of the manifests.
The rows `issue-31`…`issue-35` carry the declaration `tally` with a changed scope `placement` (`target_fields`
`[cluster, star_centre]` or `[cluster, origin]`, `caller: copies`) — of the loading form of P/02.1 Н1.2б (both witnesses
accept it), not the bytes of the manifest.

## Files

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first non-skipped one is the header.

| File | Input → expectation |
|---|---|
| [`cases.tsv`](cases.tsv), 40 rows: 13 `ok`, 24 `refused`, 3 `@exit 2` | `input` is the input of `issue` as JSON text → `expect`: `{"result":"ok","claims":…}` (the claims of Н1.4: `iss`, `sub`, `kind`, `iat`, `exp`, the claim of ref and of the audience from the scope that gave the audience, at `scenario` — `by`, `acts` by JCS, `up`) or `{"result":"refused","status":…,"reason":<word>}`: `bad_request`, `by_misplaced` (400); `not_granted`, `outside_scope`, `no_assignment`, `assignment_unreadable`, `unit_not_unique`, `not_poll_home`, `trigger_not_reported`, `no_shared_doc`, `no_item`, `no_home`, `no_audience` (403); `no_centre` (409) |

| Cases | What it checks |
|---|---|
| 01, 06–09, 30 | `placement`: the audience `cluster` and `copies`; not `origin`, the name in the record is not a member — `outside_scope`; there is no record — `no_assignment`; unreadable, without `copies` — `assignment_unreadable` |
| 02–05, 22, 24 | the order of the first steps: the role is not in `grant`, there is no kind — `not_granted`; the body is not of the form — `bad_request`; `by` not at `scenario` and absent at `scenario` — `by_misplaced`; `not_granted` before `by_misplaced` |
| 10–12 | `unit` `self`: the owner is this member; not the owner, two owners — `unit_not_unique` |
| 13–15, 27 | `placement` without a record falls to `unit` (`poll_home`): the relay is the nearest door of the owner; not it — `not_poll_home`; `centre` without a centre — `no_centre`; `poll_home` through `centre`, not the holder |
| 16–21, 23, 25, 26, 28, 29 | `scenario`: directly, behind a relay (`up`), the lift of the relay, the home by placement; no element, a foreign `by`, no document, a name twice — `no_item`; `acts` by JCS; the home is unreadable — `no_home`; the home is not a member — `no_audience` |
| 31–36 (the coverage audit of P/08, the second pass) | `star_centre` (Н1.1 `computed`): the `cluster` of the record in `star` — `centre` in the audience, without `centre` — `no_centre`, outside `star` — nothing; `origin` `""` with `caller: origin` — `outside_scope`, in `target_fields` — not in the audience; `scenario` behind a relay ≠ the home without `centre` — `no_centre` |
| 37, 38 (the coverage audit of P/08, the second pass) | an input not of the form — `@exit 2`: `decl` not of the loading form (`lifetime` 0, the М11 check, T4), `now` as a string |
| `keep-too-long`, `keep-ok` (ADR-0110 addendum (10) item 2) | `decl` with `keep` and `lifetime` greater than `KEEP_OLD` — `@exit 2`; `keep` — the assertions are the same, `jti` is not judged |

The vectors are checked by an oracle against the text of the norms (Н1.1 `computed`, Н1.3 `body`, Н1.4, Н3 «issue»), not against the code of implementations: the output
of the oracle contains the expectation of each row. The rows `issue-31`…`issue-38` (the coverage audit of P/08, the second pass of Gemini, the draft
G07 `e32df6f8b`, rewritten into the input of `issue` of this table; the inputs are `issue-01` and `issue-17` with the named change) — the expectation
of each row is a subset of the output of the command `issue` of both witness implementations `cammeta-python` and `cammeta-go` (the export
`d27f95d`); all 38 rows `issue-01`…`issue-38` agree at both. Not taken from the draft: the skipping of a `scenario` element without the field at the path `act`: at
the declarations of the manifests (`tally2`: `act` `then`, `target` `then.item`) an element without `act` has no `target` either — it is filtered out
earlier, so the skipping rule cannot be distinguished (by reading). On a divergence the text of the norm is right, the vector is corrected by «Спецификация».
