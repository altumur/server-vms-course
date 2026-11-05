# JCS (RFC 8785) — vector

This English text is the source; the Russian translation `ru/vectors/jcs/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The owner is lesson P/01 (the module design note, «Vectors»: the first contract that writes a JSON text is the store); the norm is ADR-0072
(the canon of a signed document is RFC 8785 in full). It is read by everyone who signs or compares a JSON text by bytes: the body
of a request and the digest ([P/06.4](../../../06-console/spec/06.4-console.norms.md) Н1.5), the door token, the signatures of the domain (lessons М11).

The package was moved from `Source/tests/testdata/canonical_json.tsv` (stage A) together with the vectors of lesson 6 (stage B; the review
analysis of stage B 3–5, V5); the bytes of the table are as before.

## `canonical_json.tsv`

No header; three fields separated by TAB: `raw` — a JSON text as it may arrive; `canonical` — its RFC 8785 form; `sha256` —
the sha256 of the UTF-8 of this form (hex). The implementation reads each input, brings it to the canon and compares both columns. Lines with `#` are
notes (including the mandatory cases of ADR-0072). The command binding is the wire form below (inventory C04/C06-NEXT-167, the Architect's decision of 2026-10-27).

## Who executes

Each role whose norm brings JSON to the RFC 8785 canon (ACC-VECTORS-CONNECT-03: a row is executed by the role whose norm calls
its function; inventory C04/C06-NEXT-167, the Architect's decision of 2026-10-27): the store (`01-store`, the owner); the installer (`02-installer`: the canonical view of the manifest,
P/02.2 Н1.1); the worker (`03-worker`: `value` of the state, P/03.6); the cluster console (`06-console`: `digest` of a request and the fields of the
body, P/06.4 Н1.5; the claims of the door token, P/06.5 Н3 and the door token contract); the process `domain` (`08-domain`: signatures and
documents of the domain, generations, the Entry limit, P/08.2, P/08.3, P/08.10); the agent (`09-agent`: signatures and documents of the domain,
a change of object, P/09.1). All rows — for each of these roles.

## Vector wire

The wire of `canonical_json.tsv` is set by the `01-store/jcs` rows of [the single form](../../../common/vectors/wire.tsv); [grammar](../../../common/vectors/wire.md). The form is the source of the header, selected inputs, fixtures, native outcome and comparison. Algorithm meaning and consumer obligations remain here.
