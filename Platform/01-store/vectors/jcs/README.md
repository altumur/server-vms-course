# JCS (RFC 8785) — vector

This English text is the source; the Russian translation `ru/vectors/jcs/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The owner is lesson P/01: the store introduces the first contract that writes a JSON text; the norm is ADR-0072
(the canon of a signed document is RFC 8785 in full). It is read by everyone who signs or compares a JSON text by bytes: the body
of a request and the digest ([P/06.4](../../../06-console/spec/06.4-console.norms.md) N1.5), the door token, the signatures of the domain (lessons M11).

## `canonical_json.tsv`

The table is outside the model input (judge-only: `canonical_json.tsv`); it checks the canon of ADR-0072 named above. No header; three fields separated by TAB: `raw` — a JSON text as it may arrive; `canonical` — its RFC 8785 form; `sha256` —
the sha256 of the UTF-8 of this form (hex). The implementation reads each input, brings it to the canon and compares both columns. Lines with `#` are
notes (including the mandatory cases of ADR-0072). The command binding is the wire form below.

## Who executes

Each role whose norm brings JSON to the RFC 8785 canon (a row is executed by the role whose norm calls
its function): the store (`01-store`, the owner); the installer (`02-installer`: the canonical view of the manifest,
P/02.2 N1.1); the worker (`03-worker`: `value` of the state, P/03.6); the cluster console (`06-console`: `digest` of a request and the fields of the
body, P/06.4 N1.5; the claims of the door token, P/06.5 N3 and the door token contract); the process `domain` (`08-domain`: signatures and
documents of the domain, generations, the Entry limit, P/08.2, P/08.3, P/08.10); the agent (`09-agent`: signatures and documents of the domain,
a change of object, P/09.1). All rows — for each of these roles.

## Vector wire

The vector wire is set by the `01-store/jcs` rows of [the single form](../../../common/vectors/wire.tsv); [grammar](../../../common/vectors/wire.md). The form is the source of the header, selected inputs, fixtures, native outcome and comparison. Algorithm meaning and consumer obligations remain here.
