# Vectors of issuing a worker token

This English text is the source; the Russian translation `ru/vectors/issue/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The vectors of the function `issue` of [chapter P/08.7](../../spec/08.7-domain.norms.md): the issuing of a token by the holder without a store, a network and
a stand — the input is the kind declaration, the role and the requesting member, the request body, the placements, the topology, the units of the members, the shared
document and `now`; the output is the token claims without `jti` or a refusal `{status, reason}` (N1.1 `computed`, N1.3 `body`, N1.4,
N3 «issue» steps 2–7; N5 «`issue`»). Steps 0–1 (a displaced process, the agent signature) the input does not carry. The owner is lesson P/08,
chapter 8.7; the function is performed by the process `domain` at the door `POST /api/tokens/<member>/<sub>/<kind>`. The bytes are written by «Specification»;
the conformance of the product is by its acceptance against this table.

`case` is the name of the case, `note` is a comment on the row.
The input is JSON text in one line: only insignificant whitespace outside strings is removed; the order of keys, the lexemes of numbers and the values are kept
as they are. The expectation is written as in a stand step after `ok `. The table is the only source of these cases.

## Run

Without a stand: the command `issue` of an implementation gets the input (the column `input`) and prints JSON; `expect` is a subset of the fields
of the output by the dictionary of the «Stand» ([the common acceptance README](../../../common/acceptance/README.md), `<code> <JSON>`: the named fields
exist and are equal, an array — by length, order and elements, a number — by value) or `@exit 2` (an input not of the form of N5, including
a `decl` not of the loading form of [P/02.1 N1.2b](../../../02-installer/spec/02.1-installer.norms.md)).
`iat`, `exp` are from the `now` of the input, not from the process clock.

## Inputs

The input is N5 of the chapter: `decl` is the kind declaration (`null` — there is no kind), `role` is the role that the agent certified, `member` is
the requesting member, `body` is the body `{request_id, ref, by?}`, `members`, `holder`, `placements` (`"garbled"` — the record is unreadable,
a record without `copies` is unreadable too), `topology` (`centre?`, `star`, `via`), `units` are the owners of units by ref, `shared` is
the shared document, `now` is 1760000000. The domain is `acme`; the members are `hold`, `m1`, `m2`, `relay`. The kind declarations in the inputs are the kinds
`tally`, `probe` of the manifest `testsub` and `feed`, `tally2` of the manifest `testsub2` from the specification data
([`testsub`](../../../common/data/testsub/testsub.subsystem.yaml),
[`testsub2`](../../../common/data/testsub/testsub2.subsystem.yaml)) — the inputs carry them whole and do not depend on the bytes of the manifests.
The rows `issue-31`…`issue-35` carry the declaration `tally` with a changed scope `placement` (`target_fields`
`[cluster, star_centre]` or `[cluster, origin]`, `caller: copies`) — of the loading form of P/02.1 N1.2b,
not the bytes of the manifest.

## Files

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first non-skipped one is the header.

| File | Input → expectation |
|---|---|
| the vector cases, 40 rows: 13 `ok`, 24 `refused`, 3 `@exit 2` | `input` is the input of `issue` as JSON text → `expect`: `{"result":"ok","claims":…}` (the claims of N1.4: `iss`, `sub`, `kind`, `iat`, `exp`, the claim of ref and of the audience from the scope that gave the audience, at `scenario` — `by`, `acts` by JCS, `up`) or `{"result":"refused","status":…,"reason":<word>}`: `bad_request`, `by_misplaced` (400); `not_granted`, `outside_scope`, `no_assignment`, `assignment_unreadable`, `unit_not_unique`, `not_poll_home`, `trigger_not_reported`, `no_shared_doc`, `no_item`, `no_home`, `no_audience` (403); `no_centre` (409) |

The vectors are checked by an oracle against the text of the norms (N1.1 `computed`, N1.3 `body`, N1.4, N3 «issue»), not against the code of implementations: the output
of the oracle contains the expectation of each row. The rows `issue-31`…`issue-38` are the inputs `issue-01` and `issue-17` with the change named in `note`.
The vectors do not cover the skipping of a `scenario` element without the field at the path `act`: at
the declarations of the manifests (`tally2`: `act` `then`, `target` `then.item`) an element without `act` has no `target` either — it is filtered out
earlier, so the skipping rule cannot be distinguished (by reading). On a divergence the text of the norm is right, the vector is corrected by «Specification».
