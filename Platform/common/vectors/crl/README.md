# Vectors: the file `crl.pem`

This English text is the source; the Russian translation `ru/vectors/crl/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is the common [role certificate contract](../../contracts/role-certificate.md) `revoke` (`crl`, `both`, `absent`;
stage C guesses RC-02, S03, RC-05 and RC-06, the Architect's decision 2026-10-23). The participants are the same doors as at the package
[`revoked`](../revoked/README.md). The bytes are written by «Спецификация»; the centres and the CRLs were issued once with keys from constant
bytes (Ed25519 and ECDSA P-256), the validity — 2026-01-01…2036-01-01, unless the row says otherwise.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped; the first line not skipped is the header `case<TAB>input<TAB>expect<TAB>note`.

| Field | Meaning |
|---|---|
| `case` | the name of the row |
| `input` | a JSON object: `ca` — the content of `ca.pem` (PEM), `ca_next` — `ca.next.pem` or `null`, `crl` — the content of `crl.pem`, `now` — Unix seconds |
| `expect` | `@bad` — the file is wrong (the contract `crl`): the refusal is closed; otherwise a JSON object: `ca`, `ca_next` — the serials revoked for the leaves of this centre (the canonical notation of the package `revoked`: lowercase hex without leading zeros, ascending by value; `[]` — there is no block of this centre; `ca_next` — `null` when there is no `ca.next.pem`), `stale` — the centres whose block is without `nextUpdate`, with `nextUpdate` earlier than `now` or with `thisUpdate` later than `now` by more than 60 s: for each a log line and a count, the list is in effect |
| `note` | the rule |

## Run

A side reads `crl` by its own code with the centres `ca`, `ca_next` and the time `now`, without TLS, and compares by each centre
the set of the revoked serials of the leaves of this centre and the set of the centres with a log line about the term with `expect`, or the refusal
of the file with `@bad`. A serial is reconciled only with the CRL of the issuer of the leaf: `same-serial` — a leaf of `ca.next.pem` with the same serial
is not revoked.
Who performs it — every role whose door or client checks revocation (`revoke` of the role certificate contract): the doors — the store (`01-store`, P/01.3 N1.6), the worker (`03-worker`, the process door P/03.4 N1.7 and the door on the domain P/03.7 N1.6), the resource (`05-resource`, the admission to the doors of P/05), the process `domain` (`08-domain`, the listener `SIGNER_URL`, P/08.0 N1.6), the domain console (`10-domain-console`, the role door P/10 N1.4); the clients of its own cluster (`own_client`: peer, then revocation) — the installer (`02-installer`, the workers script P/02.4 N1.6), the controller (`04-controller`, a client of the resource door — the object client contract, as at the package `loopback`), the resource (`05-resource`, the doors of the neighbours), the console (`06-console`, P/06.7 N1.4, N1.8; a client of the resource door), the agent (`09-agent`, P/09.1), the domain console (`10-domain-console`, P/10 N1.3) (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision 2026-10-27).

## Vector wire

The wire of `cases.tsv` is set by the `common/crl` rows of [the single form](../wire.tsv); [grammar](../wire.md). The form is the source of the header, selected inputs, fixtures, native outcome and comparison. Algorithm meaning and consumer obligations remain here.
