# Vectors: the trust set of a role door and the leaf check

This English text is the source; the Russian translation `ru/vectors/trust-set/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is [the role certificate contract](../../contracts/role-certificate.md) «The server side: the class `role`» (`trust_set`,
`unreadable`; stage C guess C10-SDK-ROLE83, the Architect's decision 2026-10-25). The participant is the domain console (the role door,
lesson P/10). The bytes are written by «Спецификация»; the rows are by the text of the contract.

The certificates in the vectors are replaced by their fingerprints: the sha256 hex of the DER of the certificate (the contract `fingerprint`); instead of the DER — the strings
`sha256("w2c test ca <word>")`. A side reconciles its set function over the fingerprints; PEM parsing and the handshake are the contract
`peer` and reading.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first line not skipped is the header `case<TAB>op<TAB>input<TAB>expect<TAB>note`.

| `op` | Input → output |
|---|---|
| `set` | `{own, members, ca_certs}`: `own` — the fingerprints of its own `ca.pem`, `ca.next.pem`; `members` — `{<member>: {ca?: [<fingerprint>…]} \| "@garbled"}` (`ca` — Entry.ca from `domain/member-rows/<part>`; `"@garbled"` at a member — Entry.ca not of the form) or `"@garbled"` (the row `domain/member-rows/<part>` is unreadable); `ca_certs` — `{<member>: [<fingerprint of the certificate of the ca-certs row>…] \| "@garbled"}` (no entry — there is no row) → the fingerprints of the trust set in ascending order, without repeats |
| `check` | `{set, leaf_ca}` — the set and the fingerprint of the centre to which the client's leaf converges → `"trusted"` or `"refused"` |

The comparison — JSON by value. 12 rows: 9 `set` (only its own; a member with Entry.ca and a certificate; a certificate outside Entry.ca;
a member without Entry.ca; fingerprints without certificates; a repeat — one; `domain/member-rows/<part>` is unreadable; the `ca-certs` of a member are unreadable;
Entry.ca not of the form), 3 `check` (its own centre, a member's centre, a foreign one).

## Run

Without a stand: a side gives the input to its trust set function (the reads of the rows are replaced by the input) and to the leaf check.
Who performs it — the domain console (`10-domain-console`: the role door computes the trust set and checks the leaf, P/10 Н1.4 `server.role`). The cluster console (`06-console`) is only a client of this door and does not compute the set (P/06.7 Н1.4 `holds`) (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision 2026-10-27).
